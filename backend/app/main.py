from __future__ import annotations

from dataclasses import asdict, is_dataclass
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from . import listing_parser, market_data, notaire
from .schemas import FraisNotaireInput, ListingUrlInput, MarketStudyInput, SimulationInput, TypeProjet
from .simulation import simuler

app = FastAPI(title="Simulateur de rentabilité immobilière")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


def _clean(obj):
    if is_dataclass(obj) and not isinstance(obj, type):
        return _clean(asdict(obj))
    if isinstance(obj, dict):
        return {k: _clean(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_clean(v) for v in obj]
    if isinstance(obj, float):
        return None if obj != obj else obj  # NaN -> None
    return obj


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
