"""Cartes de l'étude de marché (Leaflet, fourni avec NiceGUI) :

- autour du bien : le bien, le rayon de recherche retenu et les ventes
  comparables colorées selon leur prix au m² par rapport à la médiane ;
- rentabilité des communes du département, sur le modèle de la carte
  Horiz.io (rentabilité brute = loyer d'annonce / prix médian des ventes).

Les calques sont dessinés en JavaScript (styles et infobulles propres à
chaque élément, impossibles à transmettre en JSON via l'API Python)."""
from __future__ import annotations

import json

from nicegui import ui

from app import donnees_marche
from app.market_data import DEPARTEMENTS_SANS_DVF

from . import theme

VERT, GRIS, ROUGE, BIEN = "#1d6f5c", "#9aa3ad", "#d1453b", "#c9822a"
CENTRE_FRANCE = (46.6, 2.4)

# Dessine `code` (corps de fonction recevant la carte `m`) dès que la carte
# Leaflet est initialisée ; le calque précédent du même nom est retiré.
_JS_DESSINER = """
(function retry(n) {
    var el = getElement(%d);
    if (!el || !el.map || !window.L) { if (n > 0) setTimeout(function () { retry(n - 1); }, 100); return; }
    var m = el.map;
    // Le conteneur vient parfois d'être affiché : Leaflet doit recalculer sa taille.
    m.invalidateSize();
    if (el._calque) { m.removeLayer(el._calque); }
    el._calque = (function (m) { %s })(m);
})(50);
"""
# Laisse au navigateur le temps d'afficher le conteneur avant de dessiner.
_JS_DESSINER = "setTimeout(function () {" + _JS_DESSINER + "}, 60);"


def _eur(v: float) -> str:
    return f"{v:,.0f} €".replace(",", " ")


def _legende(elements: list[tuple[str, str]]) -> None:
    with ui.row().classes("items-center gap-x-4 gap-y-1 flex-wrap " + theme.HINT_CLASSES):
        for couleur, libelle in elements:
            with ui.row().classes("items-center gap-1 no-wrap"):
                ui.element("span").style(
                    f"display:inline-block;width:12px;height:12px;border-radius:3px;background:{couleur}"
                )
                ui.label(libelle)


class CarteVentes:
    """Le bien, le rayon de recherche et les ventes comparables."""

    def __init__(self) -> None:
        self.titre = ui.label("Carte des ventes comparables").classes(theme.SUBSECTION_TITLE_CLASSES)
        self.carte = ui.leaflet(center=CENTRE_FRANCE, zoom=5).classes("w-full h-80 rounded-xl")
        self.legende = ui.row().classes("w-full")
        with self.legende:
            _legende(
                [
                    (BIEN, "Le bien"),
                    (VERT, "Vente 10 % ou plus sous la médiane"),
                    (GRIS, "Proche de la médiane"),
                    (ROUGE, "Vente 10 % ou plus au-dessus"),
                ]
            )

    def afficher(self, lat: float, lon: float, comparables: dict) -> None:
        ventes = comparables.get("ventes") or []
        visible = bool(ventes)
        for element in (self.titre, self.carte, self.legende):
            element.visible = visible
        if not visible:
            return
        mediane = comparables["prix_m2_moyen"]
        points = []
        for v in ventes:
            ecart = v["prix_m2"] / mediane - 1
            couleur = VERT if ecart <= -0.10 else (ROUGE if ecart >= 0.10 else GRIS)
            points.append(
                {
                    "lat": v["lat"],
                    "lon": v["lon"],
                    "couleur": couleur,
                    "infobulle": f"<b>{_eur(v['prix_m2'])}/m²</b><br>{v['surface']} m², {_eur(v['prix'])}"
                    f"<br>{v['date']} — {v['adresse']}",
                }
            )
        code = """
            var g = L.featureGroup();
            var cercle = L.circle([%f, %f], {radius: %d, color: '%s', weight: 1, fillOpacity: 0.05}).addTo(g);
            %s.forEach(function (p) {
                L.circleMarker([p.lat, p.lon], {radius: 6, color: '#ffffff', weight: 1,
                    fillColor: p.couleur, fillOpacity: 0.9}).bindTooltip(p.infobulle).addTo(g);
            });
            L.circleMarker([%f, %f], {radius: 9, color: '#ffffff', weight: 2, fillColor: '%s',
                fillOpacity: 1}).bindTooltip('Le bien').addTo(g);
            g.addTo(m);
            m.fitBounds(cercle.getBounds(), {padding: [10, 10]});
            return g;
        """ % (lat, lon, comparables["rayon_utilise"], VERT, json.dumps(points), lat, lon, BIEN)
        self.titre.set_text(
            f"Carte des ventes comparables ({len(ventes)} plus récentes, rayon de "
            f"{comparables['rayon_utilise']} m)".replace("de 1000 m", "de 1 km").replace("de 2000 m", "de 2 km")
        )
        ui.run_javascript(_JS_DESSINER % (self.carte.id, code))


class CarteRentabilite:
    """Rentabilité brute des communes du département."""

    def __init__(self) -> None:
        self.contexte: dict | None = None
        with ui.row().classes("w-full items-center justify-between"):
            ui.label("Carte de rentabilité des communes").classes(theme.SUBSECTION_TITLE_CLASSES)
            self.choix = ui.toggle({"appartement": "Appartements", "maison": "Maisons"}, value="appartement").props(
                "dense no-caps"
            )
        self.message = ui.label("").classes(theme.HINT_CLASSES)
        self.carte = ui.leaflet(center=CENTRE_FRANCE, zoom=5).classes("w-full h-96 rounded-xl")
        _legende(
            [(couleur, libelle) for _, couleur, libelle in donnees_marche.ECHELLE_RENDEMENT]
            + [(donnees_marche.COULEUR_SANS_DONNEE, "Données insuffisantes")]
        )
        self.source = ui.label("").classes(theme.HINT_CLASSES)
        self.choix.on_value_change(self._sur_changement_type)

    async def afficher(self, dept: str, lat: float, lon: float, type_bien: str) -> None:
        self.contexte = {"dept": dept, "lat": lat, "lon": lon}
        if self.choix.value != type_bien:
            self.choix.set_value(type_bien)  # redessine via on_value_change
        else:
            await self._dessiner()

    async def _sur_changement_type(self, _e) -> None:
        if self.contexte:
            await self._dessiner()

    async def _dessiner(self) -> None:
        dept = self.contexte["dept"]
        if dept in DEPARTEMENTS_SANS_DVF:
            self.carte.visible = False
            self.message.set_text(
                f"Carte indisponible : les ventes ne sont pas publiées pour {DEPARTEMENTS_SANS_DVF[dept]}."
            )
            return
        self.message.set_text("Chargement de la carte…")
        try:
            geojson = await donnees_marche.carte_rentabilite(dept, self.choix.value)
        except Exception as exc:  # noqa: BLE001
            self.carte.visible = False
            self.message.set_text(f"Carte indisponible pour le moment : {exc}")
            return
        self.carte.visible = True
        for feature in geojson["features"]:
            p = feature["properties"]
            if p["rendement"] is not None:
                detail = (
                    f"Rentabilité brute : <b>{p['rendement'] * 100:.1f} %</b>".replace(".", ",")
                    + f"<br>Prix médian : {_eur(p['prix_m2'])}/m² ({p['nb_ventes']} ventes)"
                    + f"<br>Loyer d'annonce : {p['loyer_m2']:.1f} €/m²".replace(".", ",")
                )
            elif p["nb_ventes"]:
                detail = f"Données insuffisantes ({p['nb_ventes']} vente{'s' if p['nb_ventes'] > 1 else ''})"
            else:
                detail = "Aucune vente sur la période"
            p["infobulle"] = f"<b>{p['nom']}</b><br>{detail}"
        code = """
            var g = L.featureGroup();
            L.geoJSON(%s, {
                style: function (f) { return {fillColor: f.properties.couleur, color: '#ffffff',
                    weight: 0.6, fillOpacity: 0.75}; },
                onEachFeature: function (f, l) { l.bindTooltip(f.properties.infobulle, {sticky: true}); }
            }).addTo(g);
            var zone = g.getBounds();
            L.circleMarker([%f, %f], {radius: 8, color: '#ffffff', weight: 2, fillColor: '%s',
                fillOpacity: 1}).bindTooltip('Le bien').addTo(g);
            g.addTo(m);
            m.fitBounds(zone, {padding: [10, 10]});
            return g;
        """ % (json.dumps(geojson), self.contexte["lat"], self.contexte["lon"], BIEN)
        ui.run_javascript(_JS_DESSINER % (self.carte.id, code))
        periode = donnees_marche.periode_donnees()
        self.message.set_text("Survolez une commune pour le détail.")
        self.source.set_text(
            "Rentabilité brute = loyer d'annonce × 12 ÷ prix médian au m² des ventes dans l'ancien"
            + (f" ({periode})" if periode else "")
            + f", à partir de {donnees_marche.MIN_VENTES_CARTE} ventes. Sources : DVF, carte des loyers "
            "(ANIL), contours geo.api.gouv.fr."
        )
