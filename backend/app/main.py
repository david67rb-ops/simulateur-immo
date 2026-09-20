from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from . import dossier_export, endettement as endet_mod, listing_parser, market_data, notaire
from .schemas import (
    EndettementInput,
    ExportDossierInput,
    FraisNotaireInput,
    ListingUrlInput,
    MarketStudyInput,
    SimulationInput,
    TypeProjet,
)
from .simulation import simuler
from .utils import clean_result

app = FastAPI(title="Simulateur de rentabilité immobilière")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


_clean = clean_result


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.post("/api/simulate")
def api_simulate(payload: SimulationInput):
    try:
        resultat = simuler(payload)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _clean(resultat)


@app.post("/api/frais-notaire")
def api_frais_notaire(payload: FraisNotaireInput):
    return notaire.calculer_frais_notaire(payload.prix_achat, payload.neuf)


@app.post("/api/endettement")
def api_endettement(payload: EndettementInput):
    try:
        resultat = simuler(payload.simulation)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if payload.simulation.type_projet == TypeProjet.achat_revente:
        ar = resultat["achat_revente"]
        mensualite_projet = ar.frais_portage_interets / payload.simulation.duree_portage_mois
        loyers_mensuels = 0.0
    else:
        mensualite_projet = resultat.get("mensualite_credit_hors_assurance", 0.0)
        loyers_mensuels = resultat["annees"][0].loyers_bruts / 12

    r = endet_mod.calculer_taux_endettement(
        payload.profil.revenus_nets_mensuels_foyer,
        payload.profil.autres_revenus_mensuels,
        payload.profil.mensualites_credits_existants,
        mensualite_projet,
        loyers_mensuels,
    )
    return _clean({**r.__dict__, "mensualite_projet": mensualite_projet, "loyers_mensuels_projet": loyers_mensuels})


@app.post("/api/export-dossier-word")
def api_export_dossier_word(payload: ExportDossierInput):
    try:
        contenu = dossier_export.generer_dossier_word(payload)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return Response(
        content=contenu,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": "attachment; filename=dossier-financement.docx"},
    )


@app.post("/api/parse-listing")
async def api_parse_listing(payload: ListingUrlInput):
    try:
        donnees = await listing_parser.extraire_infos_annonce(payload.url)
    except listing_parser.ListingParseError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return donnees


@app.post("/api/market-study")
async def api_market_study(payload: MarketStudyInput):
    try:
        geo = await market_data.geocoder_adresse(payload.adresse)
    except market_data.MarketDataError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    comparables = None
    try:
        comparables = await market_data.comparables_dvf(
            geo["code_insee"],
            geo["code_departement"],
            geo["lat"],
            geo["lon"],
            payload.type_bien.value,
            payload.rayon_metres,
        )
    except Exception as exc:  # noqa: BLE001
        comparables = {"erreur": str(exc)}

    # Pas de loyer de marché pertinent pour une opération d'achat-revente
    # (pas de mise en location prévue).
    loyer = None
    avertissement_loyer = None
    if payload.type_projet != TypeProjet.achat_revente:
        try:
            loyer = await market_data.loyer_marche(geo["code_insee"], payload.type_bien.value)
        except Exception as exc:  # noqa: BLE001
            loyer = {"erreur": str(exc)}
        if payload.type_projet == TypeProjet.location_courte_duree:
            avertissement_loyer = (
                "Indicateur basé sur la location longue durée (aucune donnée ouverte "
                "fiable sur les loyers courte durée/Airbnb) : à utiliser comme plancher, "
                "une location courte durée bien gérée dépasse souvent ce niveau."
            )

    loyer_mensuel_estime = None
    prix_marche_estime = None
    if payload.surface_m2:
        if loyer and loyer.get("loyer_m2_moyen"):
            loyer_mensuel_estime = round(loyer["loyer_m2_moyen"] * payload.surface_m2, 0)
        if comparables and comparables.get("prix_m2_moyen"):
            prix_marche_estime = round(comparables["prix_m2_moyen"] * payload.surface_m2, 0)

    return _clean(
        {
            "adresse": geo,
            "comparables_ventes": comparables,
            "loyers_marche": loyer,
            "avertissement_loyer": avertissement_loyer,
            "loyer_mensuel_estime_pour_surface": loyer_mensuel_estime,
            "prix_marche_estime_pour_surface": prix_marche_estime,
        }
    )


frontend_dir = Path(__file__).resolve().parents[2] / "frontend"
if frontend_dir.exists():
    app.mount("/", StaticFiles(directory=frontend_dir, html=True), name="frontend")
