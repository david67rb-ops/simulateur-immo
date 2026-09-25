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

from app import endettement as endet_mod, listing_parser, market_data, notaire, schemas, simulation
from app.utils import clean_result

from . import theme
from .charts import cashflow_chart_option
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
    return f"{v:,.0f} €".replace(",", " ")


def pct(v, digits: int = 2) -> str:
    if v is None:
        return "–"
    return f"{v * 100:.{digits}f} %"


def build_simulation_input(sim_state: dict) -> schemas.SimulationInput:
    data = dict(sim_state)
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
    return schemas.SimulationInput(**data)


@ui.page("/")
def index_page() -> None:
    theme.apply_theme()
    dark_mode = ui.dark_mode(value=False)

    with ui.column().classes("w-full max-w-4xl mx-auto gap-5 p-4"):
        with ui.row().classes("w-full items-center justify-center relative mb-2"):
            ui.button(icon="dark_mode", on_click=lambda: dark_mode.toggle()).props(
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

        with ui.tabs().props("dense").classes("w-full") as profil_tabs:
            tab_investisseur = ui.tab("Particulier / Investisseur")
            tab_agent = ui.tab("Agent immobilier")

        with ui.tab_panels(profil_tabs, value=tab_investisseur).classes("w-full"):
            with ui.tab_panel(tab_investisseur).classes("p-0"):
                _build_investor_view(profil_tabs, tab_agent)
            with ui.tab_panel(tab_agent).classes("p-0"):
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
    ctx = {"last_market_result": None}
    refs: dict[str, ui.element] = {}

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
        tab_endettement = ui.tab("Taux d'endettement")
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
                    ui.select(TYPE_BIEN_OPTIONS, label="Type de bien", value=sim_state["type_bien"]).bind_value(
                        sim_state, "type_bien"
                    ).props("outlined dense").classes("w-full")
                    ui.number("Surface (m²)", value=sim_state["surface_m2"], min=1).bind_value(
                        sim_state, "surface_m2"
                    ).props("outlined dense").classes("w-full")
                    prix_achat_input = (
                        ui.number("Prix d'achat (€)", value=sim_state["prix_achat"], min=1)
                        .bind_value(sim_state, "prix_achat")
                        .props("outlined dense")
                        .classes("w-full")
                    )
                    bien_neuf_switch = ui.switch("Bien neuf / VEFA (< 5 ans)", value=sim_state["bien_neuf"]).bind_value(
                        sim_state, "bien_neuf"
                    )
                    frais_notaire_input = (
                        ui.number(
                            "Frais de notaire (€) — calculé automatiquement, modifiable",
                            value=sim_state["frais_notaire"],
                            min=0,
                        )
                        .bind_value(sim_state, "frais_notaire")
                        .props("outlined dense")
                        .classes("w-full")
                    )
                    ui.number("Montant travaux (€)", value=sim_state["montant_travaux"], min=0).bind_value(
                        sim_state, "montant_travaux"
                    ).props("outlined dense").classes("w-full")
                    mobilier_field = ui.number(
                        "Montant mobilier (€) — location meublée", value=sim_state["montant_mobilier"], min=0
                    ).bind_value(sim_state, "montant_mobilier").props("outlined dense").classes("w-full")
                    refs["field_mobilier"] = mobilier_field
                    field_taxe_fonciere = ui.number(
                        "Taxe foncière/an (€)", value=sim_state["taxe_fonciere_annuelle"], min=0
                    ).bind_value(sim_state, "taxe_fonciere_annuelle").props("outlined dense").classes("w-full")
                    field_assurance_pno = ui.number(
                        "Assurance PNO/an (€)", value=sim_state["assurance_pno_annuelle"], min=0
                    ).bind_value(sim_state, "assurance_pno_annuelle").props("outlined dense").classes("w-full")

                theme.subsection_title("Emprunt")
                with ui.row().classes(theme.GRID_CLASSES):
                    ui.number("Apport personnel (€)", value=sim_state["apport"], min=0).bind_value(
                        sim_state, "apport"
                    ).props("outlined dense").classes("w-full")
                    ui.number(
                        "Taux crédit annuel (%)", value=sim_state["taux_credit_annuel"], min=0, max=20
                    ).bind_value(sim_state, "taux_credit_annuel").props("outlined dense").classes("w-full")
                    duree_credit_field = ui.number(
                        "Durée crédit (années)", value=sim_state["duree_credit_annees"], min=1, max=35
                    ).bind_value(sim_state, "duree_credit_annees").props("outlined dense").classes("w-full")
                    refs["field_duree_credit"] = duree_credit_field
                    ui.number(
                        "Assurance emprunteur (% capital/an)", value=sim_state["taux_assurance_emprunteur"], min=0, max=2
                    ).bind_value(sim_state, "taux_assurance_emprunteur").props("outlined dense").classes("w-full")
                    differe_type_field = (
                        ui.select(DIFFERE_OPTIONS, label="Différé de crédit", value=sim_state["differe_type"])
                        .bind_value(sim_state, "differe_type")
                        .props("outlined dense")
                        .classes("w-full")
                    )
                    refs["field_differe_type"] = differe_type_field
                    differe_duree_field = ui.number(
                        "Durée du différé (mois)", value=sim_state["differe_duree_mois"], min=0, max=60
                    ).bind_value(sim_state, "differe_duree_mois").props("outlined dense").classes("w-full")
                    refs["field_differe_duree"] = differe_duree_field

                fieldset_achat_revente = ui.column().classes("w-full gap-2")
                with fieldset_achat_revente:
                    theme.subsection_title("Achat-revente")
                    with ui.row().classes(theme.GRID_CLASSES):
                        ui.number(
                            "Durée de portage (mois)", value=sim_state["duree_portage_mois"], min=1, max=60
                        ).bind_value(sim_state, "duree_portage_mois").props("outlined dense").classes("w-full")
                        ui.number(
                            "Prix de revente visé (€) — sinon estimé via revalorisation",
                            value=sim_state["prix_revente_vise"],
                            min=0,
                        ).bind_value(sim_state, "prix_revente_vise").props("outlined dense").classes("w-full")
                        ui.number(
                            "Frais d'agence à la revente (% du prix)",
                            value=sim_state["frais_agence_revente_pct"],
                            min=0,
                            max=15,
                        ).bind_value(sim_state, "frais_agence_revente_pct").props("outlined dense").classes("w-full")
                refs["fieldset_achat_revente"] = fieldset_achat_revente

            _bouton_onglet_suivant(tab_financement)

        # -----------------------------------------------------------------
        # Onglet Exploitation
        # -----------------------------------------------------------------
        with ui.tab_panel(tab_exploitation):
            with theme.section_card():
                theme.subsection_title("Charges d'exploitation")
                with ui.row().classes(theme.GRID_CLASSES):
                    field_loyer = ui.number(
                        "Loyer mensuel hors charges (€)", value=sim_state["loyer_mensuel_hors_charges"], min=0
                    ).bind_value(sim_state, "loyer_mensuel_hors_charges").props("outlined dense").classes("w-full")
                    refs["field_loyer"] = field_loyer
                    field_prix_nuitee = ui.number(
                        "Prix moyen par nuitée (€)", value=sim_state["prix_nuitee"], min=0
                    ).bind_value(sim_state, "prix_nuitee").props("outlined dense").classes("w-full")
                    refs["field_prix_nuitee"] = field_prix_nuitee
                    field_taux_occupation = ui.number(
                        "Taux d'occupation annuel (%)", value=sim_state["taux_occupation_pct"], min=0, max=100
                    ).bind_value(sim_state, "taux_occupation_pct").props("outlined dense").classes("w-full")
                    refs["field_taux_occupation"] = field_taux_occupation
                    field_charges_copro = ui.number(
                        "Charges copropriété/an (€)", value=sim_state["charges_copropriete_annuelles"], min=0
                    ).bind_value(sim_state, "charges_copropriete_annuelles").props("outlined dense").classes("w-full")
                    refs["field_charges_copro"] = field_charges_copro
                    field_frais_gestion = ui.number(
                        "Frais de gestion (% des loyers)", value=sim_state["frais_gestion_pct_loyers"], min=0, max=15
                    ).bind_value(sim_state, "frais_gestion_pct_loyers").props("outlined dense").classes("w-full")
                    refs["field_frais_gestion"] = field_frais_gestion
                    field_vacance = ui.number(
                        "Vacance locative (%)", value=sim_state["vacance_locative_pct"], min=0, max=90
                    ).bind_value(sim_state, "vacance_locative_pct").props("outlined dense").classes("w-full")
                    refs["field_vacance"] = field_vacance
                    field_entretien = ui.number(
                        "Entretien annuel (€)", value=sim_state["entretien_annuel"], min=0
                    ).bind_value(sim_state, "entretien_annuel").props("outlined dense").classes("w-full")
                    refs["field_entretien"] = field_entretien
                    field_frais_comptable = ui.number(
                        "Frais comptable/an (€) — réel BIC / SCI IS", value=sim_state["frais_comptable_annuel"], min=0
                    ).bind_value(sim_state, "frais_comptable_annuel").props("outlined dense").classes("w-full")
                    refs["field_frais_comptable"] = field_frais_comptable

                fieldset_lcd = ui.column().classes("w-full gap-2")
                with fieldset_lcd:
                    theme.subsection_title("Location courte durée")
                    with ui.row().classes(theme.GRID_CLASSES):
                        ui.select(
                            {True: "Classé (abattement 50 %)", False: "Non classé (abattement 30 %, plafond réduit)"},
                            label="Meublé de tourisme classé",
                            value=sim_state["meuble_tourisme_classe"],
                        ).bind_value(sim_state, "meuble_tourisme_classe").props("outlined dense").classes("w-full")
                        ui.number(
                            "Commission plateforme (% des recettes)", value=sim_state["frais_plateforme_pct"], min=0, max=30
                        ).bind_value(sim_state, "frais_plateforme_pct").props("outlined dense").classes("w-full")
                        ui.number(
                            "Ménage/blanchisserie annuel (€)", value=sim_state["frais_menage_annuel"], min=0
                        ).bind_value(sim_state, "frais_menage_annuel").props("outlined dense").classes("w-full")
                refs["fieldset_lcd"] = fieldset_lcd

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
                        field_regime_location = ui.select(
                            REGIME_LOCATION_OPTIONS, label="Régime", value=sim_state["regime_location"]
                        ).bind_value(sim_state, "regime_location").props("outlined dense").classes("w-full")
                        refs["field_regime_location"] = field_regime_location
                        field_tmi = ui.select(
                            TMI_OPTIONS,
                            label="Tranche marginale d'imposition (TMI) — personne physique / SCI IR",
                            value=sim_state["taux_marginal_imposition"],
                        ).bind_value(sim_state, "taux_marginal_imposition").props("outlined dense").classes("w-full")
                        refs["field_tmi"] = field_tmi
                refs["fieldset_regime"] = fieldset_regime

                fieldset_amortissement = ui.column().classes("w-full gap-2")
                with fieldset_amortissement:
                    theme.subsection_title("Amortissement (LMNP réel / SCI à l'IS)")
                    with ui.row().classes(theme.GRID_CLASSES):
                        ui.number(
                            "Part terrain (non amortissable, %)", value=sim_state["part_terrain_pct"], min=0, max=50
                        ).bind_value(sim_state, "part_terrain_pct").props("outlined dense").classes("w-full")
                        ui.number(
                            "Durée amortissement bâti (années)",
                            value=sim_state["duree_amortissement_bati_annees"],
                            min=1,
                            max=50,
                        ).bind_value(sim_state, "duree_amortissement_bati_annees").props("outlined dense").classes("w-full")
                        ui.number(
                            "Durée amortissement travaux (années)",
                            value=sim_state["duree_amortissement_travaux_annees"],
                            min=1,
                            max=50,
                        ).bind_value(sim_state, "duree_amortissement_travaux_annees").props("outlined dense").classes(
                            "w-full"
                        )
                        ui.number(
                            "Durée amortissement mobilier (années)",
                            value=sim_state["duree_amortissement_mobilier_annees"],
                            min=1,
                            max=15,
                        ).bind_value(sim_state, "duree_amortissement_mobilier_annees").props("outlined dense").classes(
                            "w-full"
                        )
                refs["fieldset_amortissement"] = fieldset_amortissement

                theme.subsection_title("Projection")
                with ui.row().classes(theme.GRID_CLASSES):
                    field_duree_projection = ui.number(
                        "Durée de projection (années)", value=sim_state["duree_projection_annees"], min=1, max=35
                    ).bind_value(sim_state, "duree_projection_annees").props("outlined dense").classes("w-full")
                    refs["field_duree_projection"] = field_duree_projection
                    ui.number(
                        "Revalorisation du bien (%/an)", value=sim_state["taux_revalorisation_bien_annuel"], min=-5, max=10
                    ).bind_value(sim_state, "taux_revalorisation_bien_annuel").props("outlined dense").classes("w-full")
                    field_reval_loyers = ui.number(
                        "Revalorisation des loyers (%/an)",
                        value=sim_state["taux_revalorisation_loyers_annuel"],
                        min=-5,
                        max=10,
                    ).bind_value(sim_state, "taux_revalorisation_loyers_annuel").props("outlined dense").classes("w-full")
                    refs["field_reval_loyers"] = field_reval_loyers

                field_marchand_pro = ui.select(
                    {False: "Non (occasionnel)", True: "Oui (activité habituelle, régime BIC/IS)"},
                    label="Marchand de biens professionnel",
                    value=sim_state["marchand_de_biens_professionnel"],
                ).bind_value(sim_state, "marchand_de_biens_professionnel").props("outlined dense").classes("w-full")
                refs["field_marchand_pro"] = field_marchand_pro

            btn_simuler = ui.button("Calculer la rentabilité").props("unelevated").classes("mt-2")

        # -----------------------------------------------------------------
        # Onglet Résultats
        # -----------------------------------------------------------------
        with ui.tab_panel(tab_resultats):
            results_placeholder = ui.label(
                "Renseigne le projet puis clique sur « Calculer la rentabilité » (onglet Fiscalité)."
            ).classes(theme.HINT_CLASSES)

            results_location = ui.column().classes("w-full gap-3")
            results_location.visible = False
            with results_location:
                with ui.row().classes(theme.GRID_CLASSES):
                    v_cout_total = theme.stat_card("Coût total d'acquisition")
                    v_rendement_brut = theme.stat_card("Rendement brut")
                    v_rendement_net = theme.stat_card("Rendement net de charges")
                    v_mensualite = theme.stat_card("Mensualité crédit")

                avertissements_box = ui.column().classes("w-full gap-2")

                ui.label("Comparatif des régimes fiscaux (année 1)").classes(theme.SUBSECTION_TITLE_CLASSES)
                table_regimes = ui.table(
                    columns=[
                        {"name": "regime", "label": "Régime", "field": "regime", "align": "left"},
                        {"name": "revenu", "label": "Revenu imposable", "field": "revenu", "align": "left"},
                        {"name": "impot", "label": "Impôt total", "field": "impot", "align": "left"},
                        {"name": "cashflow", "label": "Cash-flow mensuel net", "field": "cashflow", "align": "left"},
                        {"name": "tri", "label": "TRI (avec revente)", "field": "tri", "align": "left"},
                    ],
                    rows=[],
                    row_key="regime",
                ).classes("w-full")

                ui.label("Cash-flow cumulé sur la durée de projection").classes(theme.SUBSECTION_TITLE_CLASSES)
                chart_cashflow = (
                    ui.echart(
                        {"xAxis": {"type": "category", "data": []}, "yAxis": {"type": "value"}, "series": []}
                    )
                    .props('id="cashflow-chart"')
                    .classes("w-full h-72")
                )

                ui.label("Revente en fin de projection").classes(theme.SUBSECTION_TITLE_CLASSES)
                table_revente = ui.table(
                    columns=[
                        {"name": "regime", "label": "Régime", "field": "regime", "align": "left"},
                        {"name": "valeur", "label": "Valeur revente", "field": "valeur", "align": "left"},
                        {"name": "plusvalue", "label": "Plus-value imposable", "field": "plusvalue", "align": "left"},
                        {"name": "impot", "label": "Impôt total", "field": "impot", "align": "left"},
                        {"name": "net", "label": "Net vendeur", "field": "net", "align": "left"},
                    ],
                    rows=[],
                    row_key="regime",
                ).classes("w-full")

            results_achat_revente = ui.column().classes("w-full gap-3")
            results_achat_revente.visible = False
            with results_achat_revente:
                with ui.row().classes(theme.GRID_CLASSES):
                    v_ar_marge_brute = theme.stat_card("Marge brute avant impôt")
                    v_ar_regime = theme.stat_card("Régime fiscal")
                    v_ar_impot = theme.stat_card("Impôt total")
                    v_ar_marge_nette = theme.stat_card("Marge nette")
                with ui.row().classes(theme.GRID_CLASSES):
                    v_ar_cash_final = theme.stat_card("Cash final investisseur")
                    v_ar_rentabilite = theme.stat_card("Rentabilité de l'opération")
                    v_ar_tri = theme.stat_card("TRI annualisé")
                    v_ar_portage = theme.stat_card("Frais de portage totaux")
                table_achat_revente = ui.table(
                    columns=[
                        {"name": "k", "label": "", "field": "k", "align": "left"},
                        {"name": "v", "label": "", "field": "v", "align": "left"},
                    ],
                    rows=[],
                    row_key="k",
                ).props("hide-header").classes("w-full")

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
                    ui.input(
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
        if is_achat_revente and tab_panels.value == tab_exploitation:
            tab_panels.set_value(tab_financement)

        refs["fieldset_lcd"].visible = is_lcd
        refs["fieldset_achat_revente"].visible = is_achat_revente
        refs["fieldset_amortissement"].visible = not is_achat_revente and (is_meublee or is_sci_is)
        refs["fieldset_regime"].visible = not is_achat_revente

        refs["field_regime_location"].visible = not is_lcd
        refs["field_tmi"].visible = not is_sci_is
        refs["field_marchand_pro"].visible = is_achat_revente

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
        refs["field_differe_duree"].visible = not is_achat_revente and differe_type != "aucun"

        refs["ms_loyer_block"].visible = type_projet != "achat_revente"

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

        loyer = None
        avertissement_loyer = None
        if sim_state["type_projet"] != "achat_revente":
            try:
                loyer = await market_data.loyer_marche(geo["code_insee"], market_state["type_bien"])
            except Exception as exc:  # noqa: BLE001
                loyer = {"erreur": str(exc)}
            if sim_state["type_projet"] == "location_courte_duree":
                avertissement_loyer = (
                    "Indicateur basé sur la location longue durée (aucune donnée ouverte fiable sur les "
                    "loyers courte durée/Airbnb) : à utiliser comme plancher."
                )

        surface = market_state.get("surface_m2") or 0
        loyer_mensuel_estime = None
        prix_marche_estime = None
        if surface and loyer and loyer.get("loyer_m2_moyen"):
            loyer_mensuel_estime = round(loyer["loyer_m2_moyen"] * surface)
        if surface and comparables and comparables.get("prix_m2_moyen"):
            prix_marche_estime = round(comparables["prix_m2_moyen"] * surface)

        ctx["last_market_result"] = {
            "loyer_mensuel_estime": loyer_mensuel_estime,
            "prix_marche_estime": prix_marche_estime,
        }

        market_status.set_text(f"Adresse localisée : {geo['label']} (INSEE {geo['code_insee']})")

        v_prix_bas.set_text(f"{eur(comparables.get('prix_m2_bas'))}/m²" if comparables.get("prix_m2_bas") else "–")
        v_prix_moyen.set_text(
            f"{eur(comparables.get('prix_m2_moyen'))}/m²" if comparables.get("prix_m2_moyen") else "Pas assez de données"
        )
        v_prix_haut.set_text(f"{eur(comparables.get('prix_m2_haut'))}/m²" if comparables.get("prix_m2_haut") else "–")
        v_nb_trans.set_text(str(comparables.get("nb_transactions") or 0))

        loyer = loyer or {}
        v_loyer_bas.set_text(f"{loyer['loyer_m2_bas']:.2f} €/m²" if loyer.get("loyer_m2_bas") else "–")
        v_loyer_moyen.set_text(f"{loyer['loyer_m2_moyen']:.2f} €/m²" if loyer.get("loyer_m2_moyen") else "Non disponible")
        v_loyer_haut.set_text(f"{loyer['loyer_m2_haut']:.2f} €/m²" if loyer.get("loyer_m2_haut") else "–")
        v_fiabilite.set_text(str(loyer.get("fiabilite_r2", "–")))

        note = ""
        if loyer.get("nb_observations_commune") is not None and loyer["nb_observations_commune"] < 30:
            note += "⚠️ Peu d'observations pour cette commune : indicateur de loyer peu fiable. "
        if not comparables.get("nb_transactions"):
            note += "⚠️ Aucune transaction DVF trouvée dans ce rayon/commune pour ce type de bien. "
        if avertissement_loyer:
            note += "⚠️ " + avertissement_loyer
        market_note.set_text(note)

        market_results.visible = True

    btn_market.on_click(on_analyser_marche)

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
        if result.get("loyer_mensuel_estime") and sim_state["type_projet"] != "location_courte_duree":
            sim_state["loyer_mensuel_hors_charges"] = result["loyer_mensuel_estime"]
            field_loyer.set_value(sim_state["loyer_mensuel_hors_charges"])
        ui.notify("Valeurs de marché appliquées dans l'onglet Financement.", type="positive")
        tab_panels.set_value(tab_financement)

    btn_use_market.on_click(on_use_market)

    # =====================================================================
    # Logique : simulateur
    # =====================================================================
    def render_results_location(resultat: dict) -> None:
        results_placeholder.visible = False
        results_location.visible = True
        results_achat_revente.visible = False

        v_cout_total.set_text(eur(resultat["cout_total_acquisition"]))
        v_rendement_brut.set_text(pct(resultat["rendement_brut"], 1))
        v_rendement_net.set_text(pct(resultat["rendement_net_charges"], 1))
        v_mensualite.set_text(eur(resultat["mensualite_credit_hors_assurance"]) + "/mois (hors assurance)")

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
            cashflow_mensuel = annee1["cashflow_apres_impot"][regime] / 12
            tri = resultat["tri_par_regime"].get(regime)
            eligible = "" if fiscal.get("eligible", True) else " ⚠️ non éligible"
            rows_regimes.append(
                {
                    "regime": regime + eligible,
                    "revenu": eur(fiscal["revenu_imposable"]),
                    "impot": eur(fiscal["total_prelevements"]),
                    "cashflow": eur(cashflow_mensuel),
                    "tri": pct(tri, 2) if tri is not None else "n/a",
                }
            )
        table_regimes.rows = rows_regimes
        table_regimes.update()

        rows_revente = []
        for regime in regimes:
            rev = resultat["reventes"][regime]
            rows_revente.append(
                {
                    "regime": regime,
                    "valeur": eur(rev["valeur_revente"]),
                    "plusvalue": eur(rev["plus_value_imposable_ir"]),
                    "impot": eur(rev["impot_plus_value_ir"] + rev["impot_plus_value_ps"] + rev["surtaxe"]),
                    "net": eur(rev["net_vendeur"]),
                }
            )
        table_revente.rows = rows_revente
        table_revente.update()

        option = cashflow_chart_option(resultat, regimes)
        # `.options` has no setter in this nicegui version, and .update() /
        # run_chart_method() go through nicegui's echart wrapper, which has a bug
        # reading `this.chart.options?.series.length` and never actually applies
        # the new option. Call ECharts' setOption directly via JS instead.
        # Le panneau "Résultats" vient d'être (re)monté (changement d'onglet) :
        # le composant ECharts s'initialise de façon asynchrone (setTimeout(0)
        # avant echarts.init dans nicegui), donc on retente jusqu'à ce que
        # l'instance existe plutôt que d'échouer sur un undefined.
        ui.run_javascript(
            """
            (function retry(n) {
                var el = document.getElementById('cashflow-chart');
                var inst = el && window.echarts && echarts.getInstanceByDom(el);
                if (inst) { inst.setOption(%s, true); }
                else if (n > 0) { setTimeout(function () { retry(n - 1); }, 50); }
            })(30);
            """
            % json.dumps(option)
        )

    def render_results_achat_revente(resultat: dict) -> None:
        results_placeholder.visible = False
        results_location.visible = False
        results_achat_revente.visible = True
        ar = resultat["achat_revente"]

        v_ar_marge_brute.set_text(eur(ar["marge_brute_avant_impot"]))
        v_ar_regime.set_text(ar["regime_fiscal"])
        v_ar_impot.set_text(eur(ar["impot_total"]))
        v_ar_marge_nette.set_text(eur(ar["marge_nette"]))
        v_ar_cash_final.set_text(eur(ar["cash_final_investisseur"]))
        v_ar_rentabilite.set_text(pct(ar["rentabilite_operation_pct"], 1))
        v_ar_tri.set_text(pct(ar["tri_annualise"], 1) if ar["tri_annualise"] is not None else "n/a")
        v_ar_portage.set_text(eur(ar["frais_portage_total"]))

        rows = [
            {"k": "Coût total d'acquisition", "v": eur(ar["cout_total_acquisition"])},
            {"k": "Montant emprunté", "v": eur(ar["montant_emprunte"])},
            {"k": "Apport réel", "v": eur(ar["apport_reel"])},
            {"k": "Intérêts de portage (crédit relais)", "v": eur(ar["frais_portage_interets"])},
            {"k": "Taxe foncière (prorata portage)", "v": eur(ar["frais_portage_taxe_fonciere"])},
            {"k": "Prix de revente retenu", "v": eur(ar["prix_revente"])},
            {"k": "Frais d'agence à la revente", "v": eur(ar["frais_agence_revente"])},
            {"k": "Produit net de vente", "v": eur(ar["produit_net_vente"])},
            {"k": "Base imposable", "v": eur(ar["base_imposable"])},
        ]
        table_achat_revente.rows = rows
        table_achat_revente.update()

    def on_simuler() -> None:
        try:
            inp = build_simulation_input(sim_state)
        except Exception as exc:  # noqa: BLE001
            ui.notify(f"Entrée invalide : {exc}", type="negative")
            return
        try:
            resultat = clean_result(simulation.simuler(inp))
        except Exception as exc:  # noqa: BLE001
            ui.notify(f"Erreur de calcul : {exc}", type="negative")
            return

        # Basculer sur l'onglet Résultats avant de peupler le graphique : le
        # panneau doit être monté dans le DOM pour que le JS de mise à jour
        # d'ECharts trouve l'élément #cashflow-chart.
        tab_panels.set_value(tab_resultats)
        if resultat.get("type_projet") == "achat_revente":
            render_results_achat_revente(resultat)
        else:
            render_results_location(resultat)

    btn_simuler.on_click(on_simuler)

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
        profil = schemas.ProfilEmprunteurInput(**profil_state)
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
            endettement_status.set_text(f"Erreur : {exc}")
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
    def _construire_apercu_dossier(inp, resultat, profil) -> list[tuple[str, str]]:
        lignes = [
            ("Type de projet", TYPE_PROJET_OPTIONS.get(inp.type_projet.value, inp.type_projet.value)),
            ("Structure juridique", STRUCTURE_OPTIONS.get(inp.structure_juridique.value, inp.structure_juridique.value)),
        ]
        if inp.type_projet == schemas.TypeProjet.achat_revente:
            ar = resultat["achat_revente"]
            lignes += [
                ("Coût total de l'opération", eur(ar["cout_total_acquisition"])),
                ("Apport personnel", eur(ar["apport_reel"])),
                ("Montant emprunté", eur(ar["montant_emprunte"])),
                ("Marge nette prévisionnelle", eur(ar["marge_nette"])),
                ("Rentabilité de l'opération", pct(ar["rentabilite_operation_pct"])),
            ]
            mensualite_projet = ar["frais_portage_interets"] / inp.duree_portage_mois
            loyers_mensuels = 0.0
        else:
            annee1 = resultat["annees"][0]
            meilleur = max(annee1["cashflow_apres_impot"], key=annee1["cashflow_apres_impot"].get)
            lignes += [
                ("Coût total de l'opération", eur(resultat.get("cout_total_acquisition", 0))),
                ("Apport personnel", eur(resultat.get("apport_reel", 0))),
                ("Montant emprunté", eur(resultat.get("montant_emprunte", 0))),
                ("Régime fiscal le plus favorable (année 1)", meilleur),
                ("Cash-flow net mensuel (ce régime)", eur(annee1["cashflow_apres_impot"][meilleur] / 12)),
                ("Rendement brut", pct(resultat.get("rendement_brut", 0))),
            ]
            mensualite_projet = resultat.get("mensualite_credit_hors_assurance", 0.0)
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
            profil = schemas.ProfilEmprunteurInput(**profil_state) if profil_rempli else None
            lignes = _construire_apercu_dossier(inp, resultat, profil)
        except Exception as exc:  # noqa: BLE001
            dossier_status.set_text(f"Erreur : {exc}")
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
            profil = schemas.ProfilEmprunteurInput(**profil_state) if profil_rempli else None
            nom_emprunteur = dossier_meta_state["nom_emprunteur"].strip() or None
            adresse_bien = dossier_meta_state["adresse_bien"].strip() or market_state.get("adresse", "").strip() or None
            payload = schemas.ExportDossierInput(
                simulation=inp, profil=profil, nom_emprunteur=nom_emprunteur, adresse_bien=adresse_bien
            )
            contenu = dossier_export.generer_dossier_word(payload)
        except Exception as exc:  # noqa: BLE001
            dossier_status.set_text(f"Erreur : {exc}")
            return

        if app.native.main_window:
            # En fenêtre native (pywebview), le téléchargement navigateur
            # classique n'existe pas (le fichier n'atterrit nulle part côté
            # utilisateur) : on passe par un vrai dialogue d'enregistrement.
            import webview

            chemins = await app.native.main_window.create_file_dialog(
                dialog_type=webview.FileDialog.SAVE,
                save_filename="dossier-financement.docx",
                file_types=("Documents Word (*.docx)",),
            )
            chemin = chemins[0] if chemins else None
            if not chemin:
                dossier_status.set_text("Export annulé.")
                return
            with open(chemin, "wb") as f:
                f.write(contenu)
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
