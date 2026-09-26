"""Application NiceGUI : simulateur de rentabilité immobilière & étude de
marché. Toute la logique métier vit dans le package `app` (inchangée) ;
ce module ne fait que construire l'interface et appeler ces fonctions.

Deux parcours :
- Agent immobilier : estimation rapide de prix/loyer de marché, rien d'autre.
- Particulier / investisseur : parcours complet, organisé en onglets qui
  s'adaptent au type de projet choisi (Marché, Financement, Exploitation,
  Fiscalité, Résultats, Dossier de financement).
"""
from __future__ import annotations

import argparse
import json
import os

from nicegui import app, native, ui
from pydantic import ValidationError

from app import analyse, endettement as endet_mod, listing_parser, market_data, notaire, schemas, simulation
from app.utils import clean_result, libelle_regime

from . import theme
from .charts import cashflow_chart_option, patrimoine_option, repartition_loyer_option
from .state import (
    PERCENT_FIELDS,
    default_dossier_meta_state,
    default_market_state,
    default_profil_state,
    default_sim_state,
)

TYPE_PROJET_OPTIONS = {
    "location_longue_duree": "Location longue durée",
    "location_courte_duree": "Location courte durée (type Airbnb)",
    "achat_revente": "Achat-revente",
}
STRUCTURE_OPTIONS = {
    "personne_physique": "Personne physique (en direct)",
    "sci_ir": "SCI à l'IR",
    "sci_is": "SCI à l'IS",
}
TYPE_BIEN_OPTIONS = {"appartement": "Appartement", "maison": "Maison"}
REGIME_LOCATION_OPTIONS = {"nue": "Location nue", "meublee": "Location meublée (LMNP)"}
DIFFERE_OPTIONS = {
    "aucun": "Aucun",
    "partiel": "Partiel (intérêts seuls payés)",
    "total": "Total (rien payé, intérêts capitalisés)",
}
TMI_OPTIONS = {0.0: "0 %", 0.11: "11 %", 0.30: "30 %", 0.41: "41 %", 0.45: "45 %"}


def eur(v) -> str:
    if v is None:
        return "–"
    v = 0.0 if round(v) == 0 else v  # évite « -0 € »
    return f"{v:,.0f} €".replace(",", " ")


def pct(v, digits: int = 2) -> str:
    if v is None:
        return "–"
    return f"{v * 100:.{digits}f} %".replace(".", ",")


def champ(label: str, state: dict, cle: str, *, suffixe: str | None = None, aide: str | None = None, **kwargs):
    """Champ numérique standard du formulaire, lié à `state[cle]`, avec unité
    affichée à droite et icône d'aide facultative."""
    field = (
        ui.number(label, value=state[cle], suffix=suffixe, **kwargs)
        .bind_value(state, cle)
        .props("outlined dense")
        .classes("w-full")
    )
    if aide:
        with field.add_slot("append"):
            theme.aide(aide)
    return field


def liste(options: dict, label: str, state: dict, cle: str, *, aide: str | None = None):
    field = ui.select(options, label=label, value=state[cle]).bind_value(state, cle).props("outlined dense").classes("w-full")
    if aide:
        with field.add_slot("append"):
            theme.aide(aide)
    return field


def plus_d_options(titre: str = "Plus d'options"):
    return ui.expansion(titre, icon="tune").props("dense").classes("w-full text-sm")


def build_simulation_input(sim_state: dict) -> schemas.SimulationInput:
    data = dict(sim_state)
    if not data.get("avec_credit", True):
        # Champs masqués sans crédit : on neutralise une éventuelle saisie
        # invalide laissée dedans, elle ne doit pas bloquer la simulation.
        defauts = default_sim_state()
        for key in ("apport", "taux_credit_annuel", "duree_credit_annees", "taux_assurance_emprunteur", "differe_type", "differe_duree_mois"):
            data[key] = defauts[key]
    for key in PERCENT_FIELDS:
        data[key] = (data[key] or 0) / 100
    for key in (
        "duree_credit_annees",
        "differe_duree_mois",
        "duree_amortissement_bati_annees",
        "duree_amortissement_travaux_annees",
        "duree_amortissement_mobilier_annees",
        "duree_projection_annees",
        "duree_portage_mois",
    ):
        data[key] = int(data[key] or 0)
    if not data.get("prix_revente_vise"):
        data["prix_revente_vise"] = None
    # Un champ numérique vidé par l'utilisateur renvoie None : on le traite comme 0.
    for key, value in data.items():
        if value is None and key != "prix_revente_vise":
            data[key] = 0
    return schemas.SimulationInput(**data)


def build_profil_input(profil_state: dict) -> schemas.ProfilEmprunteurInput:
    return schemas.ProfilEmprunteurInput(**{k: v or 0 for k, v in profil_state.items()})


LIBELLES_CHAMPS = {
    "surface_m2": "Surface (m²)",
    "prix_achat": "Prix d'achat (€)",
    "frais_notaire": "Frais de notaire (€)",
    "montant_travaux": "Montant travaux (€)",
    "montant_mobilier": "Montant mobilier (€)",
    "taxe_fonciere_annuelle": "Taxe foncière/an (€)",
    "assurance_pno_annuelle": "Assurance PNO/an (€)",
    "apport": "Apport personnel (€)",
    "taux_credit_annuel": "Taux crédit annuel (%)",
    "duree_credit_annees": "Durée crédit (années)",
    "taux_assurance_emprunteur": "Assurance emprunteur (% capital/an)",
    "differe_duree_mois": "Durée du différé (mois)",
    "loyer_mensuel_hors_charges": "Loyer mensuel hors charges (€)",
    "prix_nuitee": "Prix moyen par nuitée (€)",
    "taux_occupation_pct": "Taux d'occupation annuel (%)",
    "charges_copropriete_annuelles": "Charges copropriété/an (€)",
    "charges_recuperables_annuelles": "Charges récupérables/an (€)",
    "frais_gestion_pct_loyers": "Frais de gestion (% des loyers)",
    "vacance_locative_pct": "Vacance locative (%)",
    "entretien_annuel": "Entretien annuel (€)",
    "frais_comptable_annuel": "Frais comptable/an (€)",
    "cfe_annuelle": "CFE/an (€)",
    "gli_pct_loyers": "Assurance loyers impayés (% des loyers)",
    "taux_frais_garantie": "Frais de garantie (% du prêt)",
    "frais_dossier_bancaire": "Frais de dossier bancaire (€)",
    "frais_courtage": "Frais de courtage (€)",
    "taux_revalorisation_charges_annuel": "Hausse des charges (%/an)",
    "frais_plateforme_pct": "Commission plateforme (% des recettes)",
    "frais_menage_annuel": "Ménage/blanchisserie annuel (€)",
    "taux_marginal_imposition": "Taux marginal d'imposition (%)",
    "part_terrain_pct": "Part terrain (non amortissable, %)",
    "duree_amortissement_bati_annees": "Durée amortissement bâti (années)",
    "duree_amortissement_travaux_annees": "Durée amortissement travaux (années)",
    "duree_amortissement_mobilier_annees": "Durée amortissement mobilier (années)",
    "duree_projection_annees": "Durée de projection (années)",
    "taux_revalorisation_bien_annuel": "Revalorisation du bien (%/an)",
    "taux_revalorisation_loyers_annuel": "Revalorisation des loyers (%/an)",
    "duree_portage_mois": "Durée de portage (mois)",
    "prix_revente_vise": "Prix de revente visé (€)",
    "frais_agence_revente_pct": "Frais d'agence à la revente (% du prix)",
    "revenus_nets_mensuels_foyer": "Revenus nets mensuels du foyer (€)",
    "autres_revenus_mensuels": "Autres revenus mensuels (€)",
    "mensualites_credits_existants": "Mensualités de crédits existants (€)",
}


def _message_champ(err: dict) -> str:
    champ = next((str(p) for p in reversed(err["loc"]) if isinstance(p, str)), "")
    libelle = f"« {LIBELLES_CHAMPS.get(champ, champ.replace('_', ' '))} »"
    ctx = err.get("ctx") or {}

    def fmt(borne: float) -> str:
        # Les champs en % sont saisis ×100 à l'écran mais validés en fraction.
        if champ in PERCENT_FIELDS:
            return f"{borne * 100:g} %".replace(".", ",")
        return f"{borne:g}".replace(".", ",")

    type_err = err["type"]
    if type_err in ("missing", "float_type", "int_type", "float_parsing", "int_parsing"):
        return f"{libelle} doit être renseigné avec un nombre."
    if type_err == "greater_than":
        return f"{libelle} doit être supérieur à {fmt(ctx['gt'])}."
    if type_err == "greater_than_equal":
        if ctx["ge"] == 0:
            return f"{libelle} ne peut pas être négatif."
        return f"{libelle} doit être au moins égal à {fmt(ctx['ge'])}."
    if type_err == "less_than_equal":
        return f"{libelle} ne peut pas dépasser {fmt(ctx['le'])}."
    if type_err == "less_than":
        return f"{libelle} doit être inférieur à {fmt(ctx['lt'])}."
    return f"{libelle} : valeur invalide."


def message_erreur(exc: Exception) -> str:
    """Message lisible en français pour une erreur de saisie ; les autres
    erreurs sont renvoyées telles quelles."""
    if isinstance(exc, ValidationError):
        return "Valeur à corriger : " + " ".join(_message_champ(e) for e in exc.errors())
    return f"Erreur : {exc}"


@ui.page("/")
def index_page() -> None:
    theme.apply_theme()
    # None = mode auto : suit le réglage clair/sombre de l'ordinateur ou du téléphone.
    dark_mode = ui.dark_mode(value=None)

    async def basculer_theme() -> None:
        # En mode auto, seul le navigateur sait quel thème est affiché.
        sombre = await ui.run_javascript("document.body.classList.contains('body--dark')")
        dark_mode.value = not sombre

    with ui.column().classes("w-full max-w-6xl mx-auto gap-5 p-4"):
        with ui.row().classes("w-full items-center justify-center relative mb-2"):
            ui.button(icon="dark_mode", on_click=basculer_theme).props(
                "flat round dense"
            ).classes("absolute right-0")
            with ui.column().classes("items-center gap-0"):
                with ui.row().classes("items-center gap-2"):
                    ui.html(theme.LOGO_SVG).classes("shrink-0")
                    ui.label("Simulateur de rentabilité immobilier").classes(
                        "text-2xl font-bold text-center"
                    )
                ui.label(
                    "Outil pédagogique — les résultats sont des estimations, pas un conseil fiscal personnalisé."
                ).classes("text-sm text-gray-500 dark:text-gray-400 text-center")

        with ui.tabs().props("dense").classes("w-full max-w-4xl mx-auto") as profil_tabs:
            tab_investisseur = ui.tab("Particulier / Investisseur")
            tab_agent = ui.tab("Agent immobilier")

        with ui.tab_panels(profil_tabs, value=tab_investisseur).classes("w-full"):
            with ui.tab_panel(tab_investisseur).classes("p-0"):
                _build_investor_view(profil_tabs, tab_agent)
            with ui.tab_panel(tab_agent).classes("p-0"):
                with ui.column().classes("w-full max-w-4xl mx-auto gap-5"):
                    _build_agent_view()

        ui.label(
            "Sources marché : API Adresse (BAN), DVF géolocalisé (data.gouv.fr), Carte des loyers DHUP/ANIL. "
            "Fiscalité : barème IR 2026 sur revenus 2025, IS 2026, réforme LMNP (loi de finances 2025, art. 84). "
            "Voir le README pour les hypothèses détaillées."
        ).classes(theme.HINT_CLASSES + " text-center mt-2 mb-4")


# =========================================================================
# Vue agent immobilier : estimation rapide de prix/loyer de marché
# =========================================================================
def _build_agent_view() -> None:
    state = default_market_state()

    with theme.section_card():
        ui.label("Estimation rapide").classes(theme.SECTION_TITLE_CLASSES)
        ui.label(
            "Prix et loyer de marché à partir d'une simple adresse — sans financement ni fiscalité."
        ).classes(theme.HINT_CLASSES + " mb-2")

        with ui.row().classes(theme.GRID_CLASSES):
            adresse_input = (
                ui.input("Adresse du bien", placeholder="12 rue de la République, 69002 Lyon")
                .bind_value(state, "adresse")
                .props("outlined dense")
                .classes("w-full")
            )
            type_input = (
                ui.select(TYPE_BIEN_OPTIONS, label="Type de bien", value=state["type_bien"])
                .bind_value(state, "type_bien")
                .props("outlined dense")
                .classes("w-full")
            )
            surface_input = (
                ui.number("Surface (m²)", value=state["surface_m2"], min=1)
                .bind_value(state, "surface_m2")
                .props("outlined dense")
                .classes("w-full")
            )
            rayon_input = (
                ui.number("Rayon de recherche (m)", value=state["rayon_metres"], min=100, step=100)
                .bind_value(state, "rayon_metres")
                .props("outlined dense")
                .classes("w-full")
            )

        btn_estimer = ui.button("Estimer").props("unelevated").classes("mt-3")
        status = ui.label("").classes(theme.HINT_CLASSES)

        results = ui.column().classes("w-full gap-2 mt-2")
        results.visible = False
        with results:
            ui.label("Prix de vente au m² (transactions DVF comparables)").classes(theme.SUBSECTION_TITLE_CLASSES)
            with ui.row().classes(theme.GRID_CLASSES):
                v_prix_bas = theme.stat_card("Bas (p10)")
                v_prix_moyen = theme.stat_card("Moyen (médiane)")
                v_prix_haut = theme.stat_card("Haut (p90)")
                v_nb_trans = theme.stat_card("Transactions trouvées")
            ui.label("Loyer de marché au m²").classes(theme.SUBSECTION_TITLE_CLASSES)
            with ui.row().classes(theme.GRID_CLASSES):
                v_loyer_bas = theme.stat_card("Mini")
                v_loyer_moyen = theme.stat_card("Moyen")
                v_loyer_haut = theme.stat_card("Maxi")
                v_fiabilite = theme.stat_card("Fiabilité (R²)")
            with ui.row().classes(theme.GRID_CLASSES):
                v_prix_total = theme.stat_card("Prix total estimé pour la surface")
                v_loyer_total = theme.stat_card("Loyer mensuel estimé pour la surface")
            note = ui.label("").classes(theme.HINT_CLASSES)

    async def on_estimer() -> None:
        adresse = (state.get("adresse") or "").strip()
        if not adresse:
            status.set_text("Merci de saisir une adresse.")
            return
        status.set_text("Analyse en cours…")
        results.visible = False

        try:
            geo = await market_data.geocoder_adresse(adresse)
        except market_data.MarketDataError as exc:
            status.set_text(f"Erreur : {exc}")
            return

        try:
            comparables = await market_data.comparables_dvf(
                geo["code_insee"], geo["code_departement"], geo["lat"], geo["lon"],
                state["type_bien"], int(state["rayon_metres"]),
            )
        except Exception as exc:  # noqa: BLE001
            comparables = {"erreur": str(exc)}

        try:
            loyer = await market_data.loyer_marche(geo["code_insee"], state["type_bien"])
        except Exception as exc:  # noqa: BLE001
            loyer = {"erreur": str(exc)}
        loyer = loyer or {}

        status.set_text(f"Adresse localisée : {geo['label']} (INSEE {geo['code_insee']})")

        v_prix_bas.set_text(f"{eur(comparables.get('prix_m2_bas'))}/m²" if comparables.get("prix_m2_bas") else "–")
        v_prix_moyen.set_text(
            f"{eur(comparables.get('prix_m2_moyen'))}/m²" if comparables.get("prix_m2_moyen") else "Pas assez de données"
        )
        v_prix_haut.set_text(f"{eur(comparables.get('prix_m2_haut'))}/m²" if comparables.get("prix_m2_haut") else "–")
        v_nb_trans.set_text(str(comparables.get("nb_transactions") or 0))

        v_loyer_bas.set_text(f"{loyer['loyer_m2_bas']:.2f} €/m²" if loyer.get("loyer_m2_bas") else "–")
        v_loyer_moyen.set_text(f"{loyer['loyer_m2_moyen']:.2f} €/m²" if loyer.get("loyer_m2_moyen") else "Non disponible")
        v_loyer_haut.set_text(f"{loyer['loyer_m2_haut']:.2f} €/m²" if loyer.get("loyer_m2_haut") else "–")
        v_fiabilite.set_text(str(loyer.get("fiabilite_r2", "–")))

        surface = state.get("surface_m2") or 0
        v_prix_total.set_text(
            eur(comparables["prix_m2_moyen"] * surface) if surface and comparables.get("prix_m2_moyen") else "–"
        )
        v_loyer_total.set_text(
            eur(loyer["loyer_m2_moyen"] * surface) + "/mois" if surface and loyer.get("loyer_m2_moyen") else "–"
        )

        msg = ""
        if loyer.get("nb_observations_commune") is not None and loyer["nb_observations_commune"] < 30:
            msg += "⚠️ Peu d'observations pour cette commune : indicateur de loyer peu fiable. "
        if not comparables.get("nb_transactions"):
            msg += "⚠️ Aucune transaction DVF trouvée dans ce rayon/commune pour ce type de bien."
        note.set_text(msg)

        results.visible = True

    btn_estimer.on_click(on_estimer)


# =========================================================================
# Vue particulier / investisseur : parcours complet en onglets
# =========================================================================
def _build_investor_view(profil_tabs, tab_agent) -> None:
    market_state = default_market_state()
    sim_state = default_sim_state()
    profil_state = default_profil_state()
    dossier_meta_state = default_dossier_meta_state()
    ctx = {"last_market_result": None, "commune": None}
    refs: dict[str, ui.element] = {}

    # -- Mise en page : saisie à gauche, synthèse en direct à droite (ordinateur),
    # bandeau dépliable en bas de l'écran (mobile).
    with ui.element("div").classes("w-full flex flex-col lg:flex-row gap-5 items-start"):
        colonne_saisie = ui.column().classes("flex-1 min-w-0 w-full gap-5")
        colonne_synthese = ui.element("div").classes("colonne-synthese w-80 shrink-0 sticky top-4 self-start")

    with colonne_saisie:
        # -- En-tête persistant : type de projet & structure (pilote tout le reste) --
        with theme.section_card():
            ui.label("Type de projet").classes(theme.SECTION_TITLE_CLASSES)
            with ui.row().classes("w-full gap-4"):
                type_projet_select = (
                    ui.select(TYPE_PROJET_OPTIONS, label="Type de projet", value=sim_state["type_projet"])
                    .bind_value(sim_state, "type_projet")
                    .props("outlined dense")
                    .classes("flex-1 min-w-[220px]")
                )
                structure_select = (
                    ui.select(STRUCTURE_OPTIONS, label="Structure juridique", value=sim_state["structure_juridique"])
                    .bind_value(sim_state, "structure_juridique")
                    .props("outlined dense")
                    .classes("flex-1 min-w-[220px]")
                )
            structure_note = ui.label("").classes(theme.HINT_CLASSES + " mt-1")

        # -- Barre d'onglets --
        with ui.tabs().props("dense").classes("w-full") as tabs:
            tab_marche = ui.tab("Marché")
            tab_financement = ui.tab("Financement")
            tab_exploitation = ui.tab("Exploitation")
            tab_fiscalite = ui.tab("Fiscalité")
            tab_resultats = ui.tab("Résultats")
            tab_endettement = ui.tab("Endettement")
            tab_dossier = ui.tab("Dossier")

        tabs_ordre = [
            tab_marche,
            tab_financement,
            tab_exploitation,
            tab_fiscalite,
            tab_resultats,
            tab_endettement,
            tab_dossier,
        ]

        def _bouton_onglet_suivant(tab_actuel) -> None:
            """Bouton de navigation générique : passe au prochain onglet visible
            (saute p. ex. Exploitation, masqué en achat-revente)."""

            def _aller_suivant() -> None:
                idx = tabs_ordre.index(tab_actuel)
                for suivant in tabs_ordre[idx + 1 :]:
                    if suivant.visible:
                        tab_panels.set_value(suivant)
                        return

            with ui.row().classes("w-full justify-end mt-1"):
                ui.button("Onglet suivant", icon="arrow_forward", on_click=_aller_suivant).props("outline")

        with ui.tab_panels(tabs, value=tab_marche).classes("w-full") as tab_panels:
            # -----------------------------------------------------------------
            # Onglet Marché
            # -----------------------------------------------------------------
            with ui.tab_panel(tab_marche):
                with theme.section_card():
                    ui.label("Étude de marché").classes(theme.SECTION_TITLE_CLASSES)
                    with ui.row().classes("w-full gap-3 items-end"):
                        listing_input = (
                            ui.input(
                                "Lien d'une annonce (optionnel)",
                                placeholder="https://www.orpi.com/annonce-... (portails majeurs souvent bloqués)",
                            )
                            .bind_value(market_state, "listing_url")
                            .props("outlined dense")
                            .classes("flex-1 min-w-[260px]")
                        )
                        btn_extraire = ui.button("Extraire les infos").props("outline")
                    extract_status = ui.label("").classes(theme.HINT_CLASSES)

                    with ui.row().classes(theme.GRID_CLASSES + " mt-2"):
                        ms_adresse = (
                            ui.input("Adresse du bien", placeholder="12 rue de la République, 69002 Lyon")
                            .bind_value(market_state, "adresse")
                            .props("outlined dense")
                            .classes("w-full")
                        )
                        ms_type = (
                            ui.select(TYPE_BIEN_OPTIONS, label="Type de bien", value=market_state["type_bien"])
                            .bind_value(market_state, "type_bien")
                            .props("outlined dense")
                            .classes("w-full")
                        )
                        ms_surface = (
                            ui.number("Surface (m²)", value=market_state["surface_m2"], min=1)
                            .bind_value(market_state, "surface_m2")
                            .props("outlined dense")
                            .classes("w-full")
                        )
                        ms_rayon = (
                            ui.number("Rayon de recherche (m)", value=market_state["rayon_metres"], min=100, step=100)
                            .bind_value(market_state, "rayon_metres")
                            .props("outlined dense")
                            .classes("w-full")
                        )

                    btn_market = ui.button("Analyser le marché").props("unelevated").classes("mt-3")
                    market_status = ui.label("").classes(theme.HINT_CLASSES)

                    market_results = ui.column().classes("w-full gap-2 mt-2")
                    market_results.visible = False
                    with market_results:
                        ui.label("Prix de vente au m² (transactions DVF comparables)").classes(theme.SUBSECTION_TITLE_CLASSES)
                        with ui.row().classes(theme.GRID_CLASSES):
                            v_prix_bas = theme.stat_card("Bas (p10)")
                            v_prix_moyen = theme.stat_card("Moyen (médiane)")
                            v_prix_haut = theme.stat_card("Haut (p90)")
                            v_nb_trans = theme.stat_card("Transactions trouvées")

                        loyer_block = ui.column().classes("w-full gap-2")
                        with loyer_block:
                            ui.label("Loyer de marché au m² (secteur / commune)").classes(theme.SUBSECTION_TITLE_CLASSES)
                            with ui.row().classes(theme.GRID_CLASSES):
                                v_loyer_bas = theme.stat_card("Mini")
                                v_loyer_moyen = theme.stat_card("Moyen")
                                v_loyer_haut = theme.stat_card("Maxi")
                                v_fiabilite = theme.stat_card("Fiabilité (R²)")
                        refs["ms_loyer_block"] = loyer_block

                        nuitee_block = ui.column().classes("w-full gap-2")
                        with nuitee_block:
                            ui.label("Location courte durée — estimation (secteur / commune)").classes(
                                theme.SUBSECTION_TITLE_CLASSES
                            )
                            ui.label(
                                "Dérivée du loyer nu de la zone, faute de donnée ouverte sur les tarifs Airbnb : "
                                "à ajuster selon l'attractivité touristique réelle."
                            ).classes(theme.HINT_CLASSES)
                            with ui.row().classes(theme.GRID_CLASSES):
                                v_nuitee_bas = theme.stat_card("Prix/nuitée mini")
                                v_nuitee_moyen = theme.stat_card("Prix/nuitée moyen")
                                v_nuitee_haut = theme.stat_card("Prix/nuitée maxi")
                            with ui.row().classes(theme.GRID_CLASSES):
                                v_occupation_bas = theme.stat_card("Taux d'occupation mini")
                                v_occupation_moyen = theme.stat_card("Taux d'occupation moyen")
                                v_occupation_haut = theme.stat_card("Taux d'occupation maxi")
                            with ui.row().classes("items-center gap-2"):
                                btn_airbnb = ui.button(
                                    "Comparer avec les annonces Airbnb du secteur", icon="open_in_new"
                                ).props("flat dense no-caps")
                                ui.label("pour vérifier l'estimation sur des annonces réelles").classes(theme.HINT_CLASSES)
                        refs["ms_nuitee_block"] = nuitee_block

                        market_note = ui.label("").classes(theme.HINT_CLASSES)
                        btn_use_market = ui.button("Utiliser ces valeurs dans l'onglet Financement →").props("outline")

                _bouton_onglet_suivant(tab_marche)

            # -----------------------------------------------------------------
            # Onglet Financement (le bien + emprunt + spécifique achat-revente)
            # -----------------------------------------------------------------
            with ui.tab_panel(tab_financement):
                with theme.section_card():
                    theme.subsection_title("Le bien")
                    with ui.row().classes(theme.GRID_CLASSES):
                        liste(TYPE_BIEN_OPTIONS, "Type de bien", sim_state, "type_bien")
                        champ("Surface", sim_state, "surface_m2", suffixe="m²", min=1)
                        prix_achat_input = champ("Prix d'achat", sim_state, "prix_achat", suffixe="€", min=1)
                        frais_notaire_input = champ(
                            "Frais de notaire",
                            sim_state,
                            "frais_notaire",
                            suffixe="€",
                            min=0,
                            aide="Calculés automatiquement selon le barème officiel (droits de mutation, "
                            "émoluments, débours). Tu peux les corriger.",
                        )
                        champ(
                            "Travaux",
                            sim_state,
                            "montant_travaux",
                            suffixe="€",
                            min=0,
                            aide="Travaux réalisés à l'achat. Amortissables en LMNP au réel et en SCI à l'IS.",
                        )
                        refs["field_mobilier"] = champ(
                            "Mobilier",
                            sim_state,
                            "montant_mobilier",
                            suffixe="€",
                            min=0,
                            aide="Meubles et équipements d'une location meublée, amortis sur la durée indiquée en Fiscalité.",
                        )
                        champ("Taxe foncière", sim_state, "taxe_fonciere_annuelle", suffixe="€/an", min=0)
                        champ(
                            "Assurance PNO",
                            sim_state,
                            "assurance_pno_annuelle",
                            suffixe="€/an",
                            min=0,
                            aide="Assurance propriétaire non occupant, obligatoire en copropriété.",
                        )
                    bien_neuf_switch = ui.switch("Bien neuf / VEFA (moins de 5 ans)", value=sim_state["bien_neuf"]).bind_value(
                        sim_state, "bien_neuf"
                    )

                    theme.subsection_title("Financement")
                    avec_credit_switch = ui.switch("Financement par crédit", value=sim_state["avec_credit"]).bind_value(
                        sim_state, "avec_credit"
                    )
                    refs["note_fonds_propres"] = ui.label(
                        "Bien financé intégralement en fonds propres : l'apport couvre la totalité du coût "
                        "de l'opération, sans mensualité ni intérêts d'emprunt."
                    ).classes(theme.HINT_CLASSES)
                    with ui.column().classes("w-full gap-2") as fieldset_credit:
                        with ui.row().classes(theme.GRID_CLASSES):
                            champ(
                                "Apport personnel",
                                sim_state,
                                "apport",
                                suffixe="€",
                                min=0,
                                aide="Somme que tu mets de ta poche ; le reste du coût total est emprunté.",
                            )
                            champ(
                                "Taux du crédit",
                                sim_state,
                                "taux_credit_annuel",
                                suffixe="%",
                                min=0,
                                max=20,
                                aide="Taux nominal annuel, hors assurance.",
                            )
                            refs["field_duree_credit"] = champ(
                                "Durée du crédit", sim_state, "duree_credit_annees", suffixe="ans", min=1, max=35
                            )
                        with plus_d_options("Plus d'options : assurance, différé, frais bancaires"):
                            with ui.row().classes(theme.GRID_CLASSES + " pt-2"):
                                champ(
                                    "Assurance emprunteur",
                                    sim_state,
                                    "taux_assurance_emprunteur",
                                    suffixe="%/an",
                                    min=0,
                                    max=2,
                                    aide="En % du capital emprunté, par an.",
                                )
                                differe_type_field = liste(
                                    DIFFERE_OPTIONS,
                                    "Différé de crédit",
                                    sim_state,
                                    "differe_type",
                                    aide="Début de prêt où l'on ne rembourse que les intérêts (partiel) ou rien "
                                    "du tout (total, les intérêts s'ajoutent au capital).",
                                )
                                refs["field_differe_type"] = differe_type_field
                                refs["field_differe_duree"] = champ(
                                    "Durée du différé", sim_state, "differe_duree_mois", suffixe="mois", min=0, max=60
                                )
                                champ(
                                    "Frais de garantie",
                                    sim_state,
                                    "taux_frais_garantie",
                                    suffixe="% du prêt",
                                    min=0,
                                    max=5,
                                    aide="Caution (type Crédit Logement) ou hypothèque : environ 1 à 1,5 % du prêt.",
                                )
                                champ(
                                    "Frais de dossier bancaire",
                                    sim_state,
                                    "frais_dossier_bancaire",
                                    suffixe="€",
                                    min=0,
                                    aide="Facturés par la banque, souvent 500 à 1 500 €.",
                                )
                                champ(
                                    "Frais de courtage",
                                    sim_state,
                                    "frais_courtage",
                                    suffixe="€",
                                    min=0,
                                    aide="Honoraires du courtier, s'il y en a un.",
                                )
                    refs["fieldset_credit"] = fieldset_credit

                    fieldset_achat_revente = ui.column().classes("w-full gap-2")
                    with fieldset_achat_revente:
                        theme.subsection_title("Achat-revente")
                        with ui.row().classes(theme.GRID_CLASSES):
                            champ(
                                "Durée de portage",
                                sim_state,
                                "duree_portage_mois",
                                suffixe="mois",
                                min=1,
                                max=60,
                                aide="Du jour de l'achat au jour de la revente.",
                            )
                            champ(
                                "Prix de revente visé",
                                sim_state,
                                "prix_revente_vise",
                                suffixe="€",
                                min=0,
                                aide="Laisse vide pour l'estimer à partir de la revalorisation du bien. "
                                "Nécessaire pour calculer le prix d'achat maximum.",
                            )
                            champ(
                                "Frais d'agence à la revente",
                                sim_state,
                                "frais_agence_revente_pct",
                                suffixe="% du prix",
                                min=0,
                                max=15,
                            )
                    refs["fieldset_achat_revente"] = fieldset_achat_revente

                _bouton_onglet_suivant(tab_financement)

            # -----------------------------------------------------------------
            # Onglet Exploitation
            # -----------------------------------------------------------------
            with ui.tab_panel(tab_exploitation):
                with theme.section_card():
                    theme.subsection_title("Revenus et charges")
                    with ui.row().classes(theme.GRID_CLASSES):
                        field_loyer = champ(
                            "Loyer mensuel",
                            sim_state,
                            "loyer_mensuel_hors_charges",
                            suffixe="€/mois",
                            min=0,
                            aide="Loyer hors charges récupérables sur le locataire.",
                        )
                        refs["field_loyer"] = field_loyer
                        field_prix_nuitee = champ("Prix moyen par nuitée", sim_state, "prix_nuitee", suffixe="€", min=0)
                        refs["field_prix_nuitee"] = field_prix_nuitee
                        field_taux_occupation = champ(
                            "Taux d'occupation",
                            sim_state,
                            "taux_occupation_pct",
                            suffixe="%",
                            min=0,
                            max=100,
                            aide="Part de l'année où le logement est loué (50 % ≈ 183 nuits).",
                        )
                        refs["field_taux_occupation"] = field_taux_occupation
                        refs["field_charges_copro"] = champ(
                            "Charges de copropriété",
                            sim_state,
                            "charges_copropriete_annuelles",
                            suffixe="€/an",
                            min=0,
                            aide="Part non récupérable sur le locataire.",
                        )
                        refs["field_vacance"] = champ(
                            "Vacance locative",
                            sim_state,
                            "vacance_locative_pct",
                            suffixe="%",
                            min=0,
                            max=90,
                            aide="Part de l'année sans locataire (5 % ≈ 18 jours).",
                        )

                    fieldset_lcd = ui.column().classes("w-full gap-2")
                    with fieldset_lcd:
                        theme.subsection_title("Location courte durée")
                        with ui.row().classes(theme.GRID_CLASSES):
                            liste(
                                {True: "Classé (abattement 50 %)", False: "Non classé (abattement 30 %, plafond réduit)"},
                                "Meublé de tourisme classé",
                                sim_state,
                                "meuble_tourisme_classe",
                                aide="Le classement (1 à 5 étoiles) donne un abattement micro-BIC plus élevé.",
                            )
                            champ(
                                "Commission plateforme",
                                sim_state,
                                "frais_plateforme_pct",
                                suffixe="% des recettes",
                                min=0,
                                max=30,
                                aide="Frais Airbnb/Booking côté hôte : environ 3 %, jusqu'à 15 % en formule tout compris.",
                            )
                            champ("Ménage / blanchisserie", sim_state, "frais_menage_annuel", suffixe="€/an", min=0)
                    refs["fieldset_lcd"] = fieldset_lcd

                    with plus_d_options("Plus d'options : gestion, entretien, comptable, CFE, loyers impayés"):
                        with ui.row().classes(theme.GRID_CLASSES + " pt-2"):
                            refs["field_frais_gestion"] = champ(
                                "Frais de gestion",
                                sim_state,
                                "frais_gestion_pct_loyers",
                                suffixe="% des loyers",
                                min=0,
                                max=15,
                                aide="Agence de gestion locative : en général 6 à 10 % des loyers.",
                            )
                            refs["field_entretien"] = champ(
                                "Entretien", sim_state, "entretien_annuel", suffixe="€/an", min=0,
                                aide="Budget annuel de petites réparations.",
                            )
                            refs["field_frais_comptable"] = champ(
                                "Frais comptable",
                                sim_state,
                                "frais_comptable_annuel",
                                suffixe="€/an",
                                min=0,
                                aide="Expert-comptable en LMNP au réel ou SCI à l'IS (souvent 400 à 800 €/an), déductible.",
                            )
                            refs["field_cfe"] = champ(
                                "CFE",
                                sim_state,
                                "cfe_annuelle",
                                suffixe="€/an",
                                min=0,
                                aide="Cotisation foncière des entreprises, due en meublé. Exonérée l'année de début "
                                "d'activité et sous 5 000 € de recettes annuelles.",
                            )
                            refs["field_gli"] = champ(
                                "Assurance loyers impayés",
                                sim_state,
                                "gli_pct_loyers",
                                suffixe="% des loyers",
                                min=0,
                                max=10,
                                aide="Garantie loyers impayés (GLI), souvent 2,5 à 3,5 % des loyers. Facultative.",
                            )

                _bouton_onglet_suivant(tab_exploitation)

            # -----------------------------------------------------------------
            # Onglet Fiscalité
            # -----------------------------------------------------------------
            with ui.tab_panel(tab_fiscalite):
                with theme.section_card():
                    fieldset_regime = ui.column().classes("w-full gap-2")
                    with fieldset_regime:
                        theme.subsection_title("Régime locatif & fiscalité")
                        with ui.row().classes(theme.GRID_CLASSES):
                            field_regime_location = liste(
                                REGIME_LOCATION_OPTIONS,
                                "Régime",
                                sim_state,
                                "regime_location",
                                aide="Location nue : revenus fonciers. Location meublée : LMNP, avec amortissement "
                                "possible au réel.",
                            )
                            refs["field_regime_location"] = field_regime_location
                            refs["field_tmi"] = liste(
                                TMI_OPTIONS,
                                "Tranche marginale d'imposition (TMI)",
                                sim_state,
                                "taux_marginal_imposition",
                                aide="Taux de la dernière tranche d'impôt de ton foyer : les revenus locatifs "
                                "sont imposés à ce taux.",
                            )
                    refs["fieldset_regime"] = fieldset_regime

                    field_marchand_pro = liste(
                        {False: "Non (occasionnel)", True: "Oui (activité habituelle, régime BIC/IS)"},
                        "Marchand de biens professionnel",
                        sim_state,
                        "marchand_de_biens_professionnel",
                    )
                    refs["field_marchand_pro"] = field_marchand_pro

                    refs["titre_projection"] = ui.label("Projection").classes(theme.SUBSECTION_TITLE_CLASSES)
                    with ui.row().classes(theme.GRID_CLASSES):
                        refs["field_duree_projection"] = champ(
                            "Durée de détention",
                            sim_state,
                            "duree_projection_annees",
                            suffixe="ans",
                            min=1,
                            max=35,
                            aide="Nombre d'années avant la revente simulée.",
                        )

                    fieldset_amortissement = plus_d_options("Plus d'options : amortissements (LMNP au réel / SCI à l'IS)")
                    with fieldset_amortissement:
                        with ui.row().classes(theme.GRID_CLASSES + " pt-2"):
                            champ(
                                "Part du terrain",
                                sim_state,
                                "part_terrain_pct",
                                suffixe="%",
                                min=0,
                                max=50,
                                aide="Le terrain ne s'amortit pas : en général 10 à 20 % du prix.",
                            )
                            champ("Amortissement du bâti", sim_state, "duree_amortissement_bati_annees", suffixe="ans", min=1, max=50)
                            champ(
                                "Amortissement des travaux", sim_state, "duree_amortissement_travaux_annees", suffixe="ans", min=1, max=50
                            )
                            champ(
                                "Amortissement du mobilier", sim_state, "duree_amortissement_mobilier_annees", suffixe="ans", min=1, max=15
                            )
                    refs["fieldset_amortissement"] = fieldset_amortissement

                    with plus_d_options("Plus d'options : évolution des prix et objectifs"):
                        with ui.row().classes(theme.GRID_CLASSES + " pt-2"):
                            champ(
                                "Revalorisation du bien",
                                sim_state,
                                "taux_revalorisation_bien_annuel",
                                suffixe="%/an",
                                min=-5,
                                max=10,
                            )
                            refs["field_reval_loyers"] = champ(
                                "Revalorisation des loyers",
                                sim_state,
                                "taux_revalorisation_loyers_annuel",
                                suffixe="%/an",
                                min=-5,
                                max=10,
                            )
                            refs["field_reval_charges"] = champ(
                                "Hausse des charges",
                                sim_state,
                                "taux_revalorisation_charges_annuel",
                                suffixe="%/an",
                                min=-5,
                                max=10,
                                aide="Taxe foncière, copropriété, assurance, entretien… Elles augmentent souvent "
                                "plus vite que les loyers.",
                            )
                            refs["field_objectif_cf"] = champ(
                                "Objectif de cash-flow",
                                sim_state,
                                "objectif_cashflow_mensuel",
                                suffixe="€/mois",
                                aide="Sert à calculer le prix d'achat maximum : le prix le plus élevé qui garde "
                                "ce cash-flow en année 1.",
                            )
                            refs["field_objectif_marge"] = champ(
                                "Objectif de marge nette",
                                sim_state,
                                "objectif_marge_nette",
                                suffixe="€",
                                aide="Sert à calculer le prix d'achat maximum : le prix le plus élevé qui garde "
                                "cette marge nette.",
                            )

                _bouton_onglet_suivant(tab_fiscalite)

            # -----------------------------------------------------------------
            # Onglet Résultats
            # -----------------------------------------------------------------
            with ui.tab_panel(tab_resultats):
                results_placeholder = ui.label("").classes(theme.HINT_CLASSES)

                verdict_box = ui.column().classes("w-full gap-1 rounded-xl p-4 border")
                verdict_box.visible = False
                with verdict_box:
                    verdict_titre = ui.label("").classes("text-lg font-bold")
                    verdict_detail = ui.label("").classes("text-sm")

                def colonne(nom: str, label: str, gauche: bool = False) -> dict:
                    return {"name": nom, "label": label, "field": nom, "align": "left" if gauche else "right"}

                results_location = ui.column().classes("w-full gap-3")
                results_location.visible = False
                with results_location:
                    with ui.row().classes(theme.GRID_CLASSES):
                        v_cashflow = theme.stat_card(
                            "Cash-flow net mensuel (an 1)",
                            grand=True,
                            aide_texte="Ce qui reste chaque mois après loyers, charges, crédit et impôts.",
                        )
                        v_effort = theme.stat_card(
                            "Effort d'épargne",
                            grand=True,
                            aide_texte="Ce que tu dois sortir de ta poche chaque mois quand le cash-flow est négatif.",
                        )
                        v_enrichissement = theme.stat_card(
                            "Enrichissement net",
                            grand=True,
                            aide_texte="Gain total sur la durée : cash-flows après impôts + revente nette "
                            "(impôts et capital restant dû déduits), moins l'apport.",
                        )
                    with ui.row().classes(theme.GRID_CLASSES):
                        v_rendement_brut = theme.stat_card(
                            "Rendement brut", aide_texte="Loyers annuels ÷ coût total de l'opération."
                        )
                        v_rendement_net = theme.stat_card(
                            "Rendement net de charges", aide_texte="(Loyers − charges) ÷ coût total."
                        )
                        v_rendement_net_net = theme.stat_card(
                            "Rendement net-net",
                            aide_texte="(Loyers − charges − impôts) ÷ coût total. Peut dépasser le rendement net "
                            "si le régime crée une économie d'impôt (déficit foncier).",
                        )
                        v_cout_total = theme.stat_card("Coût total d'acquisition")
                        v_mensualite = theme.stat_card("Mensualité du crédit")
                        v_prix_max = theme.stat_card(
                            "Prix d'achat maximum",
                            aide_texte="Prix le plus élevé qui respecte ton objectif de cash-flow "
                            "(Fiscalité > Plus d'options). Utile pour négocier.",
                        )
                    detail_location = ui.label("").classes(theme.HINT_CLASSES)

                    avertissements_box = ui.column().classes("w-full gap-2")

                    ui.label("Où va ton loyer (mois moyen, année 1)").classes(theme.SUBSECTION_TITLE_CLASSES)
                    ui.echart({"series": []}).props('id="loyer-chart"').classes("w-full h-72")

                    ui.label("Comparatif des régimes fiscaux (année 1)").classes(theme.SUBSECTION_TITLE_CLASSES)
                    table_regimes = ui.table(
                        columns=[
                            colonne("regime", "Régime", gauche=True),
                            colonne("revenu", "Revenu imposable"),
                            colonne("impot", "Impôt total"),
                            colonne("cashflow", "Cash-flow mensuel net"),
                            colonne("netnet", "Rendement net-net"),
                            colonne("tri", "TRI (avec revente)"),
                        ],
                        rows=[],
                        row_key="regime",
                    ).props("flat bordered").classes("w-full")

                    ui.label("Scénarios de stress (meilleur régime)").classes(theme.SUBSECTION_TITLE_CLASSES)
                    table_stress = ui.table(
                        columns=[
                            colonne("scenario", "Scénario", gauche=True),
                            colonne("cashflow", "Cash-flow mensuel net (an 1)"),
                            colonne("tri", "TRI"),
                            colonne("enrichissement", "Enrichissement net"),
                        ],
                        rows=[],
                        row_key="scenario",
                    ).props("flat bordered").classes("w-full")

                    ui.label("Évolution du patrimoine").classes(theme.SUBSECTION_TITLE_CLASSES)
                    ui.echart({"series": []}).props('id="patrimoine-chart"').classes("w-full h-80")

                    ui.label("Cash-flow cumulé par régime").classes(theme.SUBSECTION_TITLE_CLASSES)
                    ui.echart({"series": []}).props('id="cashflow-chart"').classes("w-full h-72")

                    ui.label("Revente en fin de détention").classes(theme.SUBSECTION_TITLE_CLASSES)
                    table_revente = ui.table(
                        columns=[
                            colonne("regime", "Régime", gauche=True),
                            colonne("valeur", "Valeur revente"),
                            colonne("plusvalue", "Plus-value imposable"),
                            colonne("impot", "Impôt total"),
                            colonne("net", "Net vendeur"),
                            colonne("enrichissement", "Enrichissement net"),
                        ],
                        rows=[],
                        row_key="regime",
                    ).props("flat bordered").classes("w-full")

                results_achat_revente = ui.column().classes("w-full gap-3")
                results_achat_revente.visible = False
                with results_achat_revente:
                    with ui.row().classes(theme.GRID_CLASSES):
                        v_ar_marge_nette = theme.stat_card("Marge nette", grand=True, aide_texte="Marge après frais et impôts.")
                        v_ar_rentabilite = theme.stat_card(
                            "Rentabilité de l'opération", grand=True, aide_texte="Marge nette ÷ apport investi."
                        )
                        v_ar_tri = theme.stat_card(
                            "TRI annualisé", grand=True, aide_texte="Rentabilité ramenée à une base annuelle."
                        )
                    with ui.row().classes(theme.GRID_CLASSES):
                        v_ar_marge_brute = theme.stat_card("Marge brute avant impôt")
                        v_ar_impot = theme.stat_card("Impôt total")
                        v_ar_regime = theme.stat_card("Régime fiscal")
                        v_ar_cash_final = theme.stat_card("Cash final investisseur")
                        v_ar_portage = theme.stat_card("Frais de portage totaux")
                        v_ar_prix_max = theme.stat_card(
                            "Prix d'achat maximum",
                            aide_texte="Prix le plus élevé qui respecte ton objectif de marge nette "
                            "(Fiscalité > Plus d'options). Nécessite un prix de revente visé.",
                        )
                    table_achat_revente = ui.table(
                        columns=[colonne("k", "", gauche=True), colonne("v", "")],
                        rows=[],
                        row_key="k",
                    ).props("hide-header flat bordered").classes("w-full")

                    ui.label("Scénarios de stress").classes(theme.SUBSECTION_TITLE_CLASSES)
                    table_stress_ar = ui.table(
                        columns=[
                            colonne("scenario", "Scénario", gauche=True),
                            colonne("marge", "Marge nette"),
                            colonne("rentabilite", "Rentabilité de l'opération"),
                        ],
                        rows=[],
                        row_key="scenario",
                    ).props("flat bordered").classes("w-full")

                _bouton_onglet_suivant(tab_resultats)

            # -----------------------------------------------------------------
            # Onglet Taux d'endettement
            # -----------------------------------------------------------------
            with ui.tab_panel(tab_endettement):
                with theme.section_card():
                    ui.label(
                        "Calcule le taux d'endettement du foyer à partir de la simulation (onglets précédents), "
                        "indépendamment du calcul de rentabilité."
                    ).classes(theme.HINT_CLASSES + " mb-2")

                    with ui.row().classes(theme.GRID_CLASSES):
                        ui.number(
                            "Revenus nets mensuels du foyer (€)", value=profil_state["revenus_nets_mensuels_foyer"], min=0
                        ).bind_value(profil_state, "revenus_nets_mensuels_foyer").props("outlined dense").classes("w-full")
                        ui.number(
                            "Autres revenus mensuels (€)", value=profil_state["autres_revenus_mensuels"], min=0
                        ).bind_value(profil_state, "autres_revenus_mensuels").props("outlined dense").classes("w-full")
                        ui.number(
                            "Mensualités de crédits existants (€)",
                            value=profil_state["mensualites_credits_existants"],
                            min=0,
                        ).bind_value(profil_state, "mensualites_credits_existants").props("outlined dense").classes("w-full")

                    with ui.row().classes("gap-3 mt-3"):
                        btn_endettement = ui.button("Calculer le taux d'endettement").props("unelevated")
                    endettement_status = ui.label("").classes(theme.HINT_CLASSES)

                    endettement_results = ui.column().classes("w-full gap-2 mt-2")
                    endettement_results.visible = False
                    with endettement_results:
                        with ui.row().classes(theme.GRID_CLASSES):
                            v_end_revenus = theme.stat_card("Revenus considérés (dont 70 % des loyers)")
                            v_end_mensualites = theme.stat_card("Mensualités totales")
                            v_end_taux = theme.stat_card("Taux d'endettement")
                            v_end_statut = theme.stat_card("Statut")
                        end_marge_label = ui.label("").classes(theme.HINT_CLASSES)

                _bouton_onglet_suivant(tab_endettement)

            # -----------------------------------------------------------------
            # Onglet Dossier de financement
            # -----------------------------------------------------------------
            with ui.tab_panel(tab_dossier):
                with theme.section_card():
                    ui.label(
                        "Génère un dossier Word pour la banque à partir de la simulation. Commence par générer un "
                        "aperçu pour vérifier les chiffres, puis télécharge le document."
                    ).classes(theme.HINT_CLASSES + " mb-2")

                    with ui.row().classes(theme.GRID_CLASSES):
                        refs["field_nom_emprunteur"] = ui.input(
                            "Nom de l'emprunteur (optionnel)", value=dossier_meta_state["nom_emprunteur"]
                        ).bind_value(dossier_meta_state, "nom_emprunteur").props("outlined dense").classes("w-full")
                        ui.input(
                            "Adresse du bien (optionnel, sinon reprise de l'analyse de marché)",
                            value=dossier_meta_state["adresse_bien"],
                        ).bind_value(dossier_meta_state, "adresse_bien").props("outlined dense").classes("w-full")

                    with ui.row().classes("gap-3 mt-3"):
                        btn_generer_dossier = ui.button("Générer l'aperçu du dossier").props("unelevated")
                        btn_telecharger_dossier = ui.button("Télécharger le dossier (Word)").props("outline")
                        btn_telecharger_dossier.visible = False
                    dossier_status = ui.label("").classes(theme.HINT_CLASSES)

                    apercu_dossier = ui.column().classes("w-full gap-2 mt-2")
                    apercu_dossier.visible = False
                    with apercu_dossier:
                        theme.subsection_title("Aperçu des données du dossier")
                        table_apercu_dossier = ui.table(
                            columns=[
                                {"name": "k", "label": "", "field": "k", "align": "left"},
                                {"name": "v", "label": "", "field": "v", "align": "left"},
                            ],
                            rows=[],
                            row_key="k",
                        ).props("hide-header").classes("w-full")

        ui.element("div").classes("espace-barre-mobile h-16")  # place pour le bandeau mobile

    def onglet_actif(tab) -> bool:
        # La valeur est l'onglet lui-même après un set_value(), son nom après un clic.
        return tab_panels.value is tab or tab_panels.value == tab.props["name"]

    # =====================================================================
    # Synthèse en direct (colonne de droite + bandeau mobile)
    # =====================================================================
    COULEURS_VERDICT = {"vert": theme.POSITIVE, "orange": theme.ACCENT, "rouge": theme.NEGATIVE}
    syntheses: list[dict] = []

    def voir_detail() -> None:
        tab_panels.set_value(tab_resultats)
        if barre_detail.visible:
            basculer_barre()

    def construire_synthese() -> None:
        with ui.column().classes("w-full gap-2"):
            boite = ui.column().classes("w-full gap-0 rounded-xl p-3 border")
            with boite:
                titre = ui.label("").classes("font-bold leading-tight")
                detail = ui.label("").classes("text-xs mt-1")
            principal_label = ui.label("").classes("text-xs text-gray-500 dark:text-gray-400 mt-1")
            principal = ui.label("–").classes("text-3xl font-bold leading-none")
            lignes = []
            for _ in range(6):
                with ui.row().classes("w-full justify-between items-baseline no-wrap synthese-ligne") as rangee:
                    libelle = ui.label("").classes("text-sm text-gray-500 dark:text-gray-400")
                    valeur = ui.label("").classes("text-sm font-semibold text-right")
                lignes.append((rangee, libelle, valeur))
            erreur = ui.label("").classes("text-sm").style(f"color: {theme.NEGATIVE}")
            ui.button("Voir le détail", icon="arrow_forward", on_click=voir_detail).props("flat dense no-caps").classes(
                "self-end"
            )
        syntheses.append(
            {
                "boite": boite,
                "titre": titre,
                "detail": detail,
                "principal_label": principal_label,
                "principal": principal,
                "lignes": lignes,
                "erreur": erreur,
            }
        )

    def remplir_synthese(sy: dict, v: dict, principal: tuple[str, str, float], lignes: list[tuple[str, str]]) -> None:
        couleur = COULEURS_VERDICT[v["niveau"]]
        sy["boite"].style(f"background: color-mix(in srgb, {couleur} 12%, transparent); border-color: {couleur};")
        sy["boite"].visible = True
        sy["titre"].set_text(v["titre"])
        sy["titre"].style(f"color: {couleur}")
        sy["detail"].set_text(v["detail"])
        sy["principal_label"].set_text(principal[0])
        sy["principal"].set_text(principal[1])
        theme.colorer(sy["principal"], principal[2])
        for i, (rangee, libelle, valeur) in enumerate(sy["lignes"]):
            rangee.visible = i < len(lignes)
            if i < len(lignes):
                libelle.set_text(lignes[i][0])
                valeur.set_text(lignes[i][1])
        sy["erreur"].set_text("")

    def maj_syntheses(inp, resultat: dict) -> None:
        v = analyse.verdict(inp, resultat)
        if inp.type_projet == schemas.TypeProjet.achat_revente:
            ar = resultat["achat_revente"]
            principal = ("Marge nette", eur(ar["marge_nette"]), ar["marge_nette"])
            lignes = [
                ("Rentabilité de l'opération", pct(ar["rentabilite_operation_pct"], 1)),
                ("TRI annualisé", pct(ar["tri_annualise"], 1) if ar["tri_annualise"] is not None else "n/a"),
                ("Coût total", eur(ar["cout_total_acquisition"])),
                ("Frais de portage", eur(ar["frais_portage_total"])),
                ("Impôt", eur(ar["impot_total"])),
            ]
        else:
            regime = resultat["meilleur_regime"]
            effort = resultat["effort_epargne_mensuel"]
            principal = (
                "Cash-flow net mensuel (an 1)",
                eur(resultat["cashflow_mensuel_an1"]) + "/mois",
                resultat["cashflow_mensuel_an1"],
            )
            lignes = [
                ("Effort d'épargne", eur(effort) + "/mois" if effort > 0 else "Aucun"),
                ("Rendement brut", pct(resultat["rendement_brut"], 1)),
                ("Rendement net-net", pct(resultat["rendement_net_net_par_regime"][regime], 1)),
                (
                    f"Enrichissement ({inp.duree_projection_annees} ans)",
                    eur(resultat["enrichissement_par_regime"][regime]),
                ),
                ("Coût total", eur(resultat["cout_total_acquisition"])),
                (
                    "Mensualité du crédit",
                    eur(resultat["mensualite_credit_hors_assurance"]) + "/mois"
                    if resultat["montant_emprunte"] > 0
                    else "Aucune",
                ),
            ]
        for sy in syntheses:
            remplir_synthese(sy, v, principal, lignes)
        barre_pastille.style(f"background: {COULEURS_VERDICT[v['niveau']]}")
        barre_titre.set_text(v["titre"])

    def erreur_syntheses(message: str) -> None:
        for sy in syntheses:
            sy["boite"].visible = False
            sy["principal_label"].set_text("")
            sy["principal"].set_text("")
            for rangee, _, _ in sy["lignes"]:
                rangee.visible = False
            sy["erreur"].set_text(message)
        barre_pastille.style(f"background: {theme.NEGATIVE}")
        barre_titre.set_text("Saisie à compléter")

    with colonne_synthese:
        with theme.section_card().classes("p-4"):
            ui.label("Synthèse en direct").classes("text-base font-semibold")
            construire_synthese()

    with ui.element("div").classes(
        "barre-synthese-mobile fixed bottom-0 inset-x-0 z-40 border-t shadow-lg"
    ):
        with ui.row().classes("w-full items-center gap-2 px-4 py-3 cursor-pointer no-wrap") as barre_entete:
            barre_pastille = ui.element("div").classes("w-3 h-3 rounded-full shrink-0")
            barre_titre = ui.label("").classes("text-sm font-semibold flex-1 truncate")
            barre_chevron = ui.icon("expand_less")
        barre_detail = ui.element("div").classes("px-4 pb-3 max-h-[60vh] overflow-y-auto")
        barre_detail.visible = False
        with barre_detail:
            construire_synthese()

    def basculer_barre() -> None:
        barre_detail.visible = not barre_detail.visible
        barre_chevron.set_name("expand_more" if barre_detail.visible else "expand_less")

    barre_entete.on("click", basculer_barre)

    # =====================================================================
    # Logique : visibilité dynamique (champs + onglets) selon le projet
    # =====================================================================
    def update_visibility() -> None:
        type_projet = sim_state["type_projet"]
        structure = sim_state["structure_juridique"]
        regime_location = sim_state["regime_location"]
        differe_type = sim_state["differe_type"]

        is_lcd = type_projet == "location_courte_duree"
        is_achat_revente = type_projet == "achat_revente"
        is_meublee = is_lcd or regime_location == "meublee"
        is_sci_is = structure == "sci_is"

        tab_exploitation.visible = not is_achat_revente
        if is_achat_revente and onglet_actif(tab_exploitation):
            tab_panels.set_value(tab_financement)

        avec_credit = sim_state["avec_credit"]
        tab_endettement.visible = avec_credit
        if not avec_credit and onglet_actif(tab_endettement):
            tab_panels.set_value(tab_dossier)
        libelle_nom = "Nom de l'emprunteur (optionnel)" if avec_credit else "Nom de l'investisseur (optionnel)"
        refs["field_nom_emprunteur"].props(f'label="{libelle_nom}"')

        refs["fieldset_lcd"].visible = is_lcd
        refs["fieldset_achat_revente"].visible = is_achat_revente
        refs["fieldset_amortissement"].visible = not is_achat_revente and (is_meublee or is_sci_is)
        refs["fieldset_regime"].visible = not is_achat_revente

        refs["field_regime_location"].visible = not is_lcd
        refs["field_tmi"].visible = not is_sci_is
        refs["field_marchand_pro"].visible = is_achat_revente
        refs["titre_projection"].visible = not is_achat_revente

        for key in (
            "field_charges_copro",
            "field_frais_gestion",
            "field_entretien",
            "field_duree_credit",
            "field_duree_projection",
            "field_reval_loyers",
            "field_differe_type",
        ):
            refs[key].visible = not is_achat_revente
        refs["field_loyer"].visible = not is_achat_revente and not is_lcd
        refs["field_vacance"].visible = not is_achat_revente and not is_lcd
        refs["field_prix_nuitee"].visible = is_lcd
        refs["field_taux_occupation"].visible = is_lcd
        refs["field_frais_comptable"].visible = not is_achat_revente and (is_meublee or is_sci_is)
        refs["field_mobilier"].visible = not is_achat_revente and is_meublee
        refs["field_cfe"].visible = not is_achat_revente and is_meublee
        refs["field_gli"].visible = not is_achat_revente and not is_lcd
        refs["field_reval_charges"].visible = not is_achat_revente
        refs["field_objectif_cf"].visible = not is_achat_revente and sim_state["avec_credit"]
        refs["field_objectif_marge"].visible = is_achat_revente
        refs["field_differe_duree"].visible = not is_achat_revente and differe_type != "aucun"
        refs["fieldset_credit"].visible = sim_state["avec_credit"]
        refs["note_fonds_propres"].visible = not sim_state["avec_credit"]

        refs["ms_loyer_block"].visible = type_projet == "location_longue_duree"
        refs["ms_nuitee_block"].visible = type_projet == "location_courte_duree"

        note = ""
        if is_lcd and structure == "sci_ir":
            note = (
                "⚠️ Une SCI à l'IR pratiquant la location meublée de façon habituelle est en principe "
                "requalifiée à l'IS par l'administration (sauf recettes meublées accessoires, < 10 % du total)."
            )
        elif is_sci_is:
            note = (
                "SCI à l'IS : impôt sur les sociétés (15 %/25 %), amortissement du bien, mais fiscalité "
                "différente à la revente (pas d'abattement pour durée de détention) et flat tax de 30 % "
                "en cas de distribution du résultat aux associés."
            )
        elif structure == "sci_ir":
            note = "SCI à l'IR : transparente fiscalement, imposée comme en direct au nom des associés."
        structure_note.set_text(note)

    type_projet_select.on_value_change(lambda e: update_visibility())
    structure_select.on_value_change(lambda e: update_visibility())
    field_regime_location.on_value_change(lambda e: update_visibility())
    differe_type_field.on_value_change(lambda e: update_visibility())
    avec_credit_switch.on_value_change(lambda e: update_visibility())
    update_visibility()

    # =====================================================================
    # Logique : frais de notaire automatiques
    # =====================================================================
    def recalc_notaire() -> None:
        prix = sim_state.get("prix_achat") or 0
        if prix <= 0:
            return
        resultat = notaire.calculer_frais_notaire(prix, bool(sim_state["bien_neuf"]))
        sim_state["frais_notaire"] = round(resultat["total"])
        frais_notaire_input.set_value(sim_state["frais_notaire"])

    prix_achat_input.on_value_change(lambda e: recalc_notaire())
    bien_neuf_switch.on_value_change(lambda e: recalc_notaire())
    recalc_notaire()

    # =====================================================================
    # Logique : extraction depuis un lien d'annonce
    # =====================================================================
    async def on_extraire() -> None:
        url = (market_state.get("listing_url") or "").strip()
        if not url:
            extract_status.set_text("Colle le lien d'une annonce ci-dessus.")
            return
        extract_status.set_text("Extraction en cours…")
        try:
            donnees = await listing_parser.extraire_infos_annonce(url)
        except listing_parser.ListingParseError as exc:
            extract_status.set_text(f"Erreur : {exc}")
            return

        if donnees.get("adresse"):
            market_state["adresse"] = donnees["adresse"]
            ms_adresse.set_value(donnees["adresse"])
        if donnees.get("type_bien"):
            market_state["type_bien"] = donnees["type_bien"]
            ms_type.set_value(donnees["type_bien"])
            sim_state["type_bien"] = donnees["type_bien"]
        if donnees.get("surface_m2"):
            market_state["surface_m2"] = donnees["surface_m2"]
            ms_surface.set_value(donnees["surface_m2"])
            sim_state["surface_m2"] = donnees["surface_m2"]
        if donnees.get("prix_achat"):
            sim_state["prix_achat"] = round(donnees["prix_achat"])
            prix_achat_input.set_value(sim_state["prix_achat"])
            recalc_notaire()

        manquants = donnees.get("champs_manquants") or []
        extract_status.set_text(
            f"Extrait (à vérifier) — champs non trouvés : {', '.join(manquants)}."
            if manquants
            else "Informations extraites et préremplies ci-dessous."
        )

    btn_extraire.on_click(on_extraire)

    # =====================================================================
    # Logique : étude de marché
    # =====================================================================
    async def on_analyser_marche() -> None:
        adresse = (market_state.get("adresse") or "").strip()
        if not adresse:
            market_status.set_text("Merci de saisir une adresse.")
            return
        market_status.set_text("Analyse en cours…")
        market_results.visible = False

        try:
            geo = await market_data.geocoder_adresse(adresse)
        except market_data.MarketDataError as exc:
            market_status.set_text(f"Erreur : {exc}")
            return

        try:
            comparables = await market_data.comparables_dvf(
                geo["code_insee"],
                geo["code_departement"],
                geo["lat"],
                geo["lon"],
                market_state["type_bien"],
                int(market_state["rayon_metres"]),
            )
        except Exception as exc:  # noqa: BLE001
            comparables = {"erreur": str(exc)}

        is_lcd = sim_state["type_projet"] == "location_courte_duree"
        loyer = None
        if sim_state["type_projet"] != "achat_revente":
            try:
                loyer = await market_data.loyer_marche(geo["code_insee"], market_state["type_bien"])
            except Exception as exc:  # noqa: BLE001
                loyer = {"erreur": str(exc)}

        surface = market_state.get("surface_m2") or 0
        loyer_mensuel_estime = None
        prix_marche_estime = None
        nuitee = None
        if surface and loyer and loyer.get("loyer_m2_moyen"):
            loyer_mensuel_estime = round(loyer["loyer_m2_moyen"] * surface)
            if is_lcd:
                nuitee = market_data.estimer_nuitee_et_occupation(loyer, surface)
        if surface and comparables and comparables.get("prix_m2_moyen"):
            prix_marche_estime = round(comparables["prix_m2_moyen"] * surface)

        ctx["last_market_result"] = {
            "loyer_mensuel_estime": loyer_mensuel_estime,
            "prix_marche_estime": prix_marche_estime,
            "prix_nuitee_estime": (nuitee or {}).get("prix_nuitee_moyen"),
            "taux_occupation_estime": (nuitee or {}).get("taux_occupation_moyen"),
        }

        ctx["commune"] = geo.get("commune")
        market_status.set_text(f"Adresse localisée : {geo['label']} (INSEE {geo['code_insee']})")

        v_prix_bas.set_text(f"{eur(comparables.get('prix_m2_bas'))}/m²" if comparables.get("prix_m2_bas") else "–")
        v_prix_moyen.set_text(
            f"{eur(comparables.get('prix_m2_moyen'))}/m²" if comparables.get("prix_m2_moyen") else "Pas assez de données"
        )
        v_prix_haut.set_text(f"{eur(comparables.get('prix_m2_haut'))}/m²" if comparables.get("prix_m2_haut") else "–")
        v_nb_trans.set_text(str(comparables.get("nb_transactions") or 0))

        loyer = loyer or {}
        nuitee = nuitee or {}
        if is_lcd:
            v_nuitee_bas.set_text(eur(nuitee["prix_nuitee_bas"]) if nuitee.get("prix_nuitee_bas") else "–")
            v_nuitee_moyen.set_text(eur(nuitee["prix_nuitee_moyen"]) if nuitee.get("prix_nuitee_moyen") else "Non disponible")
            v_nuitee_haut.set_text(eur(nuitee["prix_nuitee_haut"]) if nuitee.get("prix_nuitee_haut") else "–")
            v_occupation_bas.set_text(pct(nuitee["taux_occupation_bas"]) if nuitee.get("taux_occupation_bas") else "–")
            v_occupation_moyen.set_text(pct(nuitee["taux_occupation_moyen"]) if nuitee.get("taux_occupation_moyen") else "–")
            v_occupation_haut.set_text(pct(nuitee["taux_occupation_haut"]) if nuitee.get("taux_occupation_haut") else "–")
        else:
            v_loyer_bas.set_text(f"{loyer['loyer_m2_bas']:.2f} €/m²" if loyer.get("loyer_m2_bas") else "–")
            v_loyer_moyen.set_text(f"{loyer['loyer_m2_moyen']:.2f} €/m²" if loyer.get("loyer_m2_moyen") else "Non disponible")
            v_loyer_haut.set_text(f"{loyer['loyer_m2_haut']:.2f} €/m²" if loyer.get("loyer_m2_haut") else "–")
            v_fiabilite.set_text(str(loyer.get("fiabilite_r2", "–")))

        note = ""
        if not is_lcd and loyer.get("nb_observations_commune") is not None and loyer["nb_observations_commune"] < 30:
            note += "⚠️ Peu d'observations pour cette commune : indicateur de loyer peu fiable. "
        if not comparables.get("nb_transactions"):
            note += "⚠️ Aucune transaction DVF trouvée dans ce rayon/commune pour ce type de bien. "
        if is_lcd and nuitee:
            note += "⚠️ Prix/nuitée et occupation estimés à partir du loyer nu, faute de donnée ouverte sur les tarifs Airbnb — à ajuster selon l'attractivité touristique réelle de la zone."
        market_note.set_text(note)

        market_results.visible = True

    btn_market.on_click(on_analyser_marche)

    def on_ouvrir_airbnb() -> None:
        from urllib.parse import quote

        url = f"https://www.airbnb.fr/s/{quote((ctx['commune'] or '') + ', France')}/homes"
        if app.native.main_window:
            # Fenêtre native : ouvrir dans le navigateur de l'ordinateur.
            import webbrowser

            webbrowser.open(url)
        else:
            ui.navigate.to(url, new_tab=True)

    btn_airbnb.on_click(on_ouvrir_airbnb)

    def on_use_market() -> None:
        result = ctx.get("last_market_result")
        if not result:
            return
        sim_state["type_bien"] = market_state["type_bien"]
        sim_state["surface_m2"] = market_state["surface_m2"]
        if result.get("prix_marche_estime"):
            sim_state["prix_achat"] = result["prix_marche_estime"]
            prix_achat_input.set_value(sim_state["prix_achat"])
            recalc_notaire()
        if sim_state["type_projet"] == "location_courte_duree":
            if result.get("prix_nuitee_estime"):
                sim_state["prix_nuitee"] = result["prix_nuitee_estime"]
                field_prix_nuitee.set_value(sim_state["prix_nuitee"])
            if result.get("taux_occupation_estime"):
                sim_state["taux_occupation_pct"] = result["taux_occupation_estime"] * 100
                field_taux_occupation.set_value(sim_state["taux_occupation_pct"])
        elif result.get("loyer_mensuel_estime"):
            sim_state["loyer_mensuel_hors_charges"] = result["loyer_mensuel_estime"]
            field_loyer.set_value(sim_state["loyer_mensuel_hors_charges"])
        ui.notify("Valeurs de marché appliquées dans l'onglet Financement.", type="positive")
        tab_panels.set_value(tab_financement)

    btn_use_market.on_click(on_use_market)

    # =====================================================================
    # Logique : simulateur (recalcul automatique, onglet Résultats)
    # =====================================================================
    def maj_graphique(element_id: str, option: dict) -> None:
        # `.options` n'a pas de setter dans cette version de NiceGUI et son
        # wrapper n'applique pas les nouvelles options : on appelle setOption
        # d'ECharts directement. Le composant s'initialise de façon asynchrone
        # quand le panneau vient d'être affiché, d'où les nouvelles tentatives.
        ui.run_javascript(
            """
            (function retry(n) {
                var el = document.getElementById('%s');
                var inst = el && window.echarts && echarts.getInstanceByDom(el);
                if (!inst) { if (n > 0) { setTimeout(function () { retry(n - 1); }, 50); } return; }
                var opt = %s;
                var euros = function (v) { return Math.round(v).toLocaleString('fr-FR') + ' €'; };
                if (opt.yAxis && opt.yAxis.axisLabel) { opt.yAxis.axisLabel.formatter = euros; }
                if (opt.tooltip) { opt.tooltip.valueFormatter = euros; }
                inst.setOption(opt, true);
            })(30);
            """
            % (element_id, json.dumps(option))
        )

    def render_verdict(v: dict) -> None:
        couleur = COULEURS_VERDICT[v["niveau"]]
        verdict_box.style(
            f"background: color-mix(in srgb, {couleur} 12%, transparent); border-color: {couleur};"
        )
        verdict_titre.set_text(v["titre"])
        verdict_titre.style(f"color: {couleur}")
        verdict_detail.set_text(v["detail"])
        verdict_box.visible = True

    def texte_prix_max(pm: dict | None, objectif_libelle: str) -> str:
        if pm is None:
            return "–"
        if pm["statut"] == "inatteignable":
            return "Objectif inatteignable"
        if pm["statut"] == "non_limitant":
            return f"> {eur(pm['prix_max'])}"
        return f"{eur(pm['prix_max'])} ({objectif_libelle} {eur(pm['objectif'])})"

    def render_results_location(inp, resultat: dict) -> None:
        results_placeholder.visible = False
        results_location.visible = True
        results_achat_revente.visible = False

        meilleur = resultat["meilleur_regime"]
        render_verdict(analyse.verdict(inp, resultat))

        v_cashflow.set_text(eur(resultat["cashflow_mensuel_an1"]) + "/mois")
        theme.colorer(v_cashflow, resultat["cashflow_mensuel_an1"])
        effort = resultat["effort_epargne_mensuel"]
        v_effort.set_text(eur(effort) + "/mois" if effort > 0 else "Aucun")
        theme.colorer(v_effort, effort, inverse=True)
        enrichissement = resultat["enrichissement_par_regime"][meilleur]
        v_enrichissement.set_text(eur(enrichissement))
        theme.colorer(v_enrichissement, enrichissement)
        v_rendement_brut.set_text(pct(resultat["rendement_brut"], 1))
        v_rendement_net.set_text(pct(resultat["rendement_net_charges"], 1))
        v_rendement_net_net.set_text(pct(resultat["rendement_net_net_par_regime"][meilleur], 1))
        theme.colorer(v_rendement_net_net, resultat["rendement_net_net_par_regime"][meilleur])
        v_cout_total.set_text(eur(resultat["cout_total_acquisition"]))
        v_mensualite.set_text(
            eur(resultat["mensualite_credit_hors_assurance"]) + "/mois"
            if resultat["montant_emprunte"] > 0
            else "Aucune (fonds propres)"
        )
        v_prix_max.set_text(
            texte_prix_max(analyse.prix_achat_maximum(inp), "cash-flow ≥")
            if inp.avec_credit
            else "Sans objet sans crédit"
        )
        detail_location.set_text(
            f"Indicateurs calculés pour le régime le plus favorable : {libelle_regime(meilleur)}, "
            f"enrichissement sur {inp.duree_projection_annees} ans. "
            f"Coût total = prix + notaire + travaux + mobilier + frais bancaires ({eur(resultat['frais_bancaires'])}). "
            "Mensualité hors assurance."
        )

        avertissements_box.clear()
        for a in resultat.get("avertissements") or []:
            with avertissements_box:
                ui.label("⚠️ " + a).classes(
                    "w-full text-sm rounded-xl p-3 border"
                ).style(f"background: color-mix(in srgb, {theme.NEGATIVE} 10%, transparent); border-color: {theme.NEGATIVE};")

        annee1 = resultat["annees"][0]
        regimes = list(annee1["cashflow_apres_impot"].keys())

        rows_regimes = []
        for regime in regimes:
            fiscal = annee1["fiscal"][regime]
            tri = resultat["tri_par_regime"].get(regime)
            marque = " ★" if regime == meilleur else ""
            eligible = "" if fiscal.get("eligible", True) else " ⚠️ non éligible"
            rows_regimes.append(
                {
                    "regime": libelle_regime(regime) + marque + eligible,
                    "revenu": eur(fiscal["revenu_imposable"]),
                    "impot": eur(fiscal["total_prelevements"]),
                    "cashflow": eur(annee1["cashflow_apres_impot"][regime] / 12),
                    "netnet": pct(resultat["rendement_net_net_par_regime"][regime], 2),
                    "tri": pct(tri, 2) if tri is not None else "n/a",
                }
            )
        table_regimes.rows = rows_regimes
        table_regimes.update()

        table_stress.rows = [
            {
                "scenario": l["scenario"],
                "cashflow": eur(l["cashflow_mensuel"]) + "/mois",
                "tri": pct(l["tri"], 2) if l["tri"] is not None else "n/a",
                "enrichissement": eur(l["enrichissement"]),
            }
            for l in analyse.scenarios_stress(inp)
        ]
        table_stress.update()

        table_revente.rows = [
            {
                "regime": libelle_regime(regime) + (" ★" if regime == meilleur else ""),
                "valeur": eur(rev["valeur_revente"]),
                "plusvalue": eur(rev["plus_value_imposable_ir"]),
                "impot": eur(rev["impot_plus_value_ir"] + rev["impot_plus_value_ps"] + rev["surtaxe"]),
                "net": eur(rev["net_vendeur"]),
                "enrichissement": eur(resultat["enrichissement_par_regime"][regime]),
            }
            for regime, rev in ((r, resultat["reventes"][r]) for r in regimes)
        ]
        table_revente.update()

        maj_graphique("loyer-chart", repartition_loyer_option(resultat))
        maj_graphique(
            "patrimoine-chart", patrimoine_option(resultat, inp.prix_achat, inp.taux_revalorisation_bien_annuel)
        )
        maj_graphique("cashflow-chart", cashflow_chart_option(resultat, regimes))

    def render_results_achat_revente(inp, resultat: dict) -> None:
        results_placeholder.visible = False
        results_location.visible = False
        results_achat_revente.visible = True
        ar = resultat["achat_revente"]
        render_verdict(analyse.verdict(inp, resultat))

        v_ar_marge_nette.set_text(eur(ar["marge_nette"]))
        theme.colorer(v_ar_marge_nette, ar["marge_nette"])
        v_ar_rentabilite.set_text(pct(ar["rentabilite_operation_pct"], 1))
        theme.colorer(v_ar_rentabilite, ar["rentabilite_operation_pct"])
        v_ar_tri.set_text(pct(ar["tri_annualise"], 1) if ar["tri_annualise"] is not None else "n/a")
        theme.colorer(v_ar_tri, ar["tri_annualise"])
        v_ar_marge_brute.set_text(eur(ar["marge_brute_avant_impot"]))
        theme.colorer(v_ar_marge_brute, ar["marge_brute_avant_impot"])
        v_ar_regime.set_text(ar["regime_fiscal"])
        v_ar_impot.set_text(eur(ar["impot_total"]))
        v_ar_cash_final.set_text(eur(ar["cash_final_investisseur"]))
        v_ar_portage.set_text(eur(ar["frais_portage_total"]))
        pm = analyse.prix_achat_maximum(inp)
        v_ar_prix_max.set_text(
            texte_prix_max(pm, "marge ≥") if pm is not None else "Renseigne un prix de revente visé"
        )

        table_achat_revente.rows = [
            {"k": "Coût total d'acquisition", "v": eur(ar["cout_total_acquisition"])},
            {"k": "dont frais bancaires (garantie, dossier, courtage)", "v": eur(ar["frais_bancaires"])},
            {"k": "Montant emprunté", "v": eur(ar["montant_emprunte"])},
            {"k": "Apport réel", "v": eur(ar["apport_reel"])},
            {"k": "Intérêts de portage (crédit relais)", "v": eur(ar["frais_portage_interets"])},
            {"k": "Taxe foncière (prorata portage)", "v": eur(ar["frais_portage_taxe_fonciere"])},
            {"k": "Prix de revente retenu", "v": eur(ar["prix_revente"])},
            {"k": "Frais d'agence à la revente", "v": eur(ar["frais_agence_revente"])},
            {"k": "Produit net de vente", "v": eur(ar["produit_net_vente"])},
            {"k": "Base imposable", "v": eur(ar["base_imposable"])},
        ]
        table_achat_revente.update()

        table_stress_ar.rows = [
            {"scenario": l["scenario"], "marge": eur(l["marge_nette"]), "rentabilite": pct(l["rentabilite"], 1)}
            for l in analyse.scenarios_stress(inp)
        ]
        table_stress_ar.update()

    def afficher_resultats(inp=None, resultat: dict | None = None) -> None:
        if inp is None:
            try:
                inp = build_simulation_input(sim_state)
                resultat = clean_result(simulation.simuler(inp))
            except Exception as exc:  # noqa: BLE001
                results_placeholder.set_text(message_erreur(exc))
                results_placeholder.visible = True
                for bloc in (verdict_box, results_location, results_achat_revente):
                    bloc.visible = False
                return
        if resultat["type_projet"] == "achat_revente":
            render_results_achat_revente(inp, resultat)
        else:
            render_results_location(inp, resultat)

    tab_panels.on_value_change(lambda e: afficher_resultats() if onglet_actif(tab_resultats) else None)

    derniere_saisie = {"signature": None}

    def recalculer() -> None:
        """Appelée en continu : ne recalcule que si une saisie a changé. Le
        calcul complet prend quelques millisecondes ; le prix max et les
        scénarios de stress, plus lourds, ne sont calculés que si l'onglet
        Résultats est affiché."""
        signature = json.dumps(sim_state, sort_keys=True, default=str)
        if signature == derniere_saisie["signature"]:
            return
        derniere_saisie["signature"] = signature
        try:
            inp = build_simulation_input(sim_state)
            resultat = clean_result(simulation.simuler(inp))
        except Exception as exc:  # noqa: BLE001
            erreur_syntheses(message_erreur(exc))
            if onglet_actif(tab_resultats):
                afficher_resultats()
            return
        maj_syntheses(inp, resultat)
        if onglet_actif(tab_resultats):
            afficher_resultats(inp, resultat)

    ui.timer(0.5, recalculer)

    # =====================================================================
    # Logique : dossier de financement (endettement + export Word)
    # =====================================================================
    def compute_endettement():
        inp = build_simulation_input(sim_state)
        resultat = simulation.simuler(inp)
        if inp.type_projet == schemas.TypeProjet.achat_revente:
            ar = resultat["achat_revente"]
            mensualite_projet = ar.frais_portage_interets / inp.duree_portage_mois
            loyers_mensuels = 0.0
        else:
            mensualite_projet = resultat.get("mensualite_credit_hors_assurance", 0.0)
            loyers_mensuels = resultat["annees"][0].loyers_bruts / 12
        profil = build_profil_input(profil_state)
        r = endet_mod.calculer_taux_endettement(
            profil.revenus_nets_mensuels_foyer,
            profil.autres_revenus_mensuels,
            profil.mensualites_credits_existants,
            mensualite_projet,
            loyers_mensuels,
        )
        return r

    def on_calc_endettement() -> None:
        endettement_status.set_text("Calcul en cours…")
        try:
            r = compute_endettement()
        except Exception as exc:  # noqa: BLE001
            endettement_status.set_text(message_erreur(exc))
            return
        endettement_status.set_text("")

        v_end_revenus.set_text(eur(r.revenus_consideres_mensuels))
        v_end_mensualites.set_text(eur(r.mensualites_totales_mensuelles))
        v_end_taux.set_text(pct(r.taux_endettement, 1))
        v_end_statut.set_text(
            f"⚠️ Dépasse le seuil HCSF ({pct(r.seuil_hcsf, 0)})" if r.depasse_seuil else f"OK (seuil HCSF {pct(r.seuil_hcsf, 0)})"
        )
        end_marge_label.set_text(
            "Le taux d'endettement dépasse le seuil de 35 % généralement retenu par les banques."
            if r.depasse_seuil
            else f"Marge avant d'atteindre le seuil : {eur(r.marge_avant_seuil)}/mois de mensualité supplémentaire supportable."
        )
        endettement_results.visible = True

    btn_endettement.on_click(on_calc_endettement)

    # =====================================================================
    # Logique : dossier Word (aperçu des données, puis téléchargement)
    # =====================================================================
    def _lignes_credit(montant_emprunte, inp, libelle_mensualite, mensualite) -> list[tuple[str, str]]:
        if montant_emprunte <= 0:
            return [("Financement", "100 % fonds propres (sans crédit)")]
        return [
            ("Montant emprunté", eur(montant_emprunte)),
            ("Taux du crédit", pct(inp.taux_credit_annuel)),
            (libelle_mensualite, eur(mensualite) + "/mois"),
        ]

    def _construire_apercu_dossier(inp, resultat, profil) -> list[tuple[str, str]]:
        lignes = [
            ("Type de projet", TYPE_PROJET_OPTIONS.get(inp.type_projet.value, inp.type_projet.value)),
            ("Structure juridique", STRUCTURE_OPTIONS.get(inp.structure_juridique.value, inp.structure_juridique.value)),
            ("Prix d'achat", eur(inp.prix_achat)),
            ("Frais de notaire", eur(inp.frais_notaire)),
            ("Montant des travaux", eur(inp.montant_travaux)),
        ]
        frais_bancaires = (
            resultat["achat_revente"]["frais_bancaires"]
            if inp.type_projet == schemas.TypeProjet.achat_revente
            else resultat["frais_bancaires"]
        )
        if frais_bancaires > 0:
            lignes.append(("Frais bancaires (garantie, dossier, courtage)", eur(frais_bancaires)))
        if inp.type_projet == schemas.TypeProjet.achat_revente:
            ar = resultat["achat_revente"]
            mensualite_projet = ar["frais_portage_interets"] / inp.duree_portage_mois
            lignes += [
                ("Coût total de l'opération", eur(ar["cout_total_acquisition"])),
                ("Apport personnel", eur(ar["apport_reel"])),
                *_lignes_credit(ar["montant_emprunte"], inp, "Mensualité (intérêts de portage)", mensualite_projet),
                ("Marge nette prévisionnelle", eur(ar["marge_nette"])),
                ("Rentabilité de l'opération", pct(ar["rentabilite_operation_pct"])),
            ]
            loyers_mensuels = 0.0
        else:
            annee1 = resultat["annees"][0]
            meilleur = resultat["meilleur_regime"]
            mensualite_projet = resultat.get("mensualite_credit_hors_assurance", 0.0)
            loyers_mensuels_apercu = annee1["loyers_bruts"] / 12
            label_loyer = (
                "Chiffre d'affaires mensuel"
                if inp.type_projet == schemas.TypeProjet.location_courte_duree
                else "Loyer appliqué (mensuel)"
            )
            lignes += [
                ("Coût total de l'opération", eur(resultat.get("cout_total_acquisition", 0))),
                ("Apport personnel", eur(resultat.get("apport_reel", 0))),
                *_lignes_credit(resultat.get("montant_emprunte", 0), inp, "Mensualité du crédit", mensualite_projet),
                (label_loyer, eur(loyers_mensuels_apercu) + "/mois"),
                ("Régime fiscal le plus favorable", libelle_regime(meilleur)),
                ("Cash-flow net mensuel", eur(annee1["cashflow_apres_impot"][meilleur] / 12)),
                ("Rendement brut", pct(resultat.get("rendement_brut", 0))),
                ("Rendement net", pct(resultat.get("rendement_net_charges", 0))),
            ]
            loyers_mensuels = annee1["loyers_bruts"] / 12

        if profil is not None:
            r = endet_mod.calculer_taux_endettement(
                profil.revenus_nets_mensuels_foyer,
                profil.autres_revenus_mensuels,
                profil.mensualites_credits_existants,
                mensualite_projet,
                loyers_mensuels,
            )
            lignes.append(
                (
                    "Taux d'endettement",
                    pct(r.taux_endettement, 1) + (" ⚠️ dépasse le seuil HCSF" if r.depasse_seuil else " (sous le seuil HCSF)"),
                )
            )
        return lignes

    def on_generer_apercu() -> None:
        dossier_status.set_text("Génération de l'aperçu…")
        try:
            inp = build_simulation_input(sim_state)
            resultat = clean_result(simulation.simuler(inp))
            profil_rempli = any(v for v in profil_state.values())
            profil = build_profil_input(profil_state) if profil_rempli and inp.avec_credit else None
            lignes = _construire_apercu_dossier(inp, resultat, profil)
        except Exception as exc:  # noqa: BLE001
            dossier_status.set_text(message_erreur(exc))
            return

        table_apercu_dossier.rows = [{"k": k, "v": v} for k, v in lignes]
        table_apercu_dossier.update()
        apercu_dossier.visible = True
        btn_telecharger_dossier.visible = True
        dossier_status.set_text("Aperçu généré — vérifie les chiffres ci-dessous puis télécharge le dossier.")

    btn_generer_dossier.on_click(on_generer_apercu)

    async def on_telecharger_dossier() -> None:
        dossier_status.set_text("Génération du dossier Word…")
        try:
            # Importé ici plutôt qu'au démarrage : entraîne matplotlib (via
            # app.charts_export), coûteux à charger et inutile tant qu'aucun
            # dossier Word n'est généré.
            from app import dossier_export

            inp = build_simulation_input(sim_state)
            profil_rempli = any(v for v in profil_state.values())
            profil = build_profil_input(profil_state) if profil_rempli and inp.avec_credit else None
            nom_emprunteur = dossier_meta_state["nom_emprunteur"].strip() or None
            adresse_bien = dossier_meta_state["adresse_bien"].strip() or market_state.get("adresse", "").strip() or None
            payload = schemas.ExportDossierInput(
                simulation=inp, profil=profil, nom_emprunteur=nom_emprunteur, adresse_bien=adresse_bien
            )
            contenu = dossier_export.generer_dossier_word(payload)
        except Exception as exc:  # noqa: BLE001
            dossier_status.set_text(message_erreur(exc))
            return

        if app.native.main_window:
            # En fenêtre native (pywebview), le téléchargement navigateur
            # classique n'existe pas (le fichier n'atterrit nulle part côté
            # utilisateur) : on passe par un vrai dialogue d'enregistrement.
            import webview

            choix = await app.native.main_window.create_file_dialog(
                dialog_type=webview.FileDialog.SAVE,
                save_filename="dossier-financement.docx",
                file_types=("Documents Word (*.docx)",),
            )
            # Sur macOS, le dialogue d'enregistrement renvoie un chemin (str),
            # pas une liste comme le dialogue d'ouverture.
            chemin = choix if isinstance(choix, str) else (choix[0] if choix else None)
            if not chemin:
                dossier_status.set_text("Export annulé.")
                return
            try:
                with open(chemin, "wb") as f:
                    f.write(contenu)
            except OSError as exc:
                dossier_status.set_text(f"Erreur lors de l'enregistrement : {exc}")
                return
            dossier_status.set_text(f"Dossier enregistré : {chemin}")
        else:
            ui.download(contenu, "dossier-financement.docx")
            dossier_status.set_text("Dossier téléchargé.")

    btn_telecharger_dossier.on_click(on_telecharger_dossier)


def main() -> None:
    parser = argparse.ArgumentParser(description="Simulateur de rentabilité immobilière")
    parser.add_argument("--web", action="store_true", help="Lance dans le navigateur au lieu d'une fenêtre native")
    parser.add_argument("--port", type=int, default=None)
    parser.add_argument("--host", type=str, default=None)
    args = parser.parse_args()

    # PORT est fourni par la plupart des hébergeurs (Render, Railway, Fly.io...) :
    # sa seule présence indique qu'on tourne en environnement serveur/conteneur.
    env_port = os.environ.get("PORT")
    is_hosted = env_port is not None
    web_mode = args.web or os.environ.get("IMMO_WEB_MODE") == "1" or is_hosted
    # En natif, un port fixe peut être déjà pris par une autre instance ou un
    # autre logiciel sur la machine de l'utilisateur : on en choisit un libre.
    if args.port:
        port = args.port
    elif env_port:
        port = int(env_port)
    elif web_mode:
        port = 8080
    else:
        port = native.find_open_port()
    # "0.0.0.0" est nécessaire pour écouter sur toutes les interfaces en
    # hébergement web, mais une fenêtre native (pywebview) doit pointer sur
    # "localhost" : 0.0.0.0 n'est pas une adresse valide à charger dans un
    # navigateur/webview, ce qui donne un écran blanc.
    host = args.host or ("0.0.0.0" if web_mode else "localhost")

    ui.run(
        title="Simulateur de rentabilité immobilière",
        native=not web_mode,
        window_size=(1180, 900) if not web_mode else None,
        reload=False,
        host=host,
        port=port,
        show=web_mode and not is_hosted,
        storage_secret=os.environ.get("IMMO_STORAGE_SECRET", "immo-rentabilite-local-dev"),
    )


if __name__ in {"__main__", "__mp_main__"}:
    main()
