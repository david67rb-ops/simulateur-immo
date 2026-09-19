"""Étude de marché automatique à partir de sources open-data françaises :

- Géocodage : API Adresse (api-adresse.data.gouv.fr, Base Adresse Nationale)
- Prix de vente : DVF géolocalisé (files.data.gouv.fr/geo-dvf), par département
- Loyers de marché : "Carte des loyers" (data.gouv.fr / DHUP), par commune

Les fichiers DVF et loyers sont volumineux : on les télécharge une fois par
département/catégorie puis on les met en cache sur disque (data_cache/).
"""
from __future__ import annotations

import gzip
import io
import math
from pathlib import Path

import httpx
import pandas as pd

CACHE_DIR = Path(__file__).parent / "data_cache"
CACHE_DIR.mkdir(exist_ok=True)

GEOCODE_URL = "https://api-adresse.data.gouv.fr/search/"
DVF_URL_TEMPLATE = "https://files.data.gouv.fr/geo-dvf/latest/csv/{annee}/departements/{dept}.csv.gz"

LOYERS_URLS = {
    "appartement": "https://static.data.gouv.fr/resources/carte-des-loyers-indicateurs-de-loyers-dannonce-par-commune-en-2025/20251211-145010/pred-app-mef-dhup.csv",
    "maison": "https://static.data.gouv.fr/resources/carte-des-loyers-indicateurs-de-loyers-dannonce-par-commune-en-2025/20251211-145039/pred-mai-mef-dhup.csv",
}

DVF_ANNEES = [2024, 2023]  # dernières années disponibles, filtrées ensuite sur 24 mois


class MarketDataError(Exception):
    pass


async def geocoder_adresse(adresse: str) -> dict:
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(GEOCODE_URL, params={"q": adresse, "limit": 1})
        resp.raise_for_status()
        data = resp.json()
    features = data.get("features") or []
    if not features:
        raise MarketDataError(f"Adresse introuvable : {adresse!r}")
    props = features[0]["properties"]
    lon, lat = features[0]["geometry"]["coordinates"]
    return {
        "label": props.get("label"),
        "code_insee": props.get("citycode"),
        "code_postal": props.get("postcode"),
        "commune": props.get("city"),
        "code_departement": props.get("citycode", "")[:2],
        "lon": lon,
        "lat": lat,
    }


def _dvf_cache_path(dept: str, annee: int) -> Path:
    return CACHE_DIR / f"dvf_{dept}_{annee}.parquet"


async def _charger_dvf_departement(dept: str, annee: int) -> pd.DataFrame:
    cache_path = _dvf_cache_path(dept, annee)
    if cache_path.exists():
        return pd.read_parquet(cache_path)

    url = DVF_URL_TEMPLATE.format(annee=annee, dept=dept)
    async with httpx.AsyncClient(timeout=60, follow_redirects=True) as client:
        resp = await client.get(url)
        if resp.status_code == 404:
            return pd.DataFrame()
        resp.raise_for_status()
        raw = gzip.decompress(resp.content)

    df = pd.read_csv(
        io.BytesIO(raw),
        usecols=[
            "date_mutation",
            "nature_mutation",
            "valeur_fonciere",
            "code_commune",
            "type_local",
            "surface_reelle_bati",
            "nombre_pieces_principales",
            "longitude",
            "latitude",
        ],
        dtype={"code_commune": str},
    )
    df = df[df["nature_mutation"] == "Vente"]
    df = df.dropna(subset=["valeur_fonciere", "surface_reelle_bati", "longitude", "latitude"])
    df = df[df["surface_reelle_bati"] > 0]
    df["prix_m2"] = df["valeur_fonciere"] / df["surface_reelle_bati"]
    df.to_parquet(cache_path)
    return df


def _haversine_m(lat1, lon1, lat2, lon2):
    r = 6_371_000
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


async def comparables_dvf(
    code_insee: str, code_departement: str, lat: float, lon: float, type_local: str, rayon_m: int
) -> dict:
    type_local_dvf = "Appartement" if type_local == "appartement" else "Maison"
    frames = []
    for annee in DVF_ANNEES:
        df = await _charger_dvf_departement(code_departement, annee)
        if not df.empty:
            frames.append(df)
    vide = {
        "nb_transactions": 0,
        "prix_m2_bas": None,
        "prix_m2_moyen": None,
        "prix_m2_haut": None,
        "prix_m2_min": None,
        "prix_m2_max": None,
    }
    if not frames:
        return vide

    df = pd.concat(frames, ignore_index=True)
    df = df[df["type_local"] == type_local_dvf]
    df = df[df["code_commune"] == code_insee]
    df["distance_m"] = df.apply(
        lambda row: _haversine_m(lat, lon, row["latitude"], row["longitude"]), axis=1
    )
    df = df[df["distance_m"] <= rayon_m]

    # Filtre anti-aberrant : bornes larges + exclusion des très petites
    # surfaces (caves/parkings mal typés) qui faussent le prix au m².
    df = df[(df["prix_m2"] > 200) & (df["prix_m2"] < 30_000) & (df["surface_reelle_bati"] >= 9)]

    if df.empty:
        return vide

    # bas/moyen/haut = 10e/50e(médiane)/90e percentile : une fourchette
    # représentative, plus robuste aux valeurs extrêmes que min/max bruts
    # (conservés séparément à titre indicatif).
    p10, p50, p90 = df["prix_m2"].quantile([0.10, 0.50, 0.90])

    return {
        "nb_transactions": int(len(df)),
        "prix_m2_bas": round(float(p10), 0),
        "prix_m2_moyen": round(float(p50), 0),
        "prix_m2_haut": round(float(p90), 0),
        "prix_m2_min": round(float(df["prix_m2"].min()), 0),
        "prix_m2_max": round(float(df["prix_m2"].max()), 0),
    }


async def _charger_loyers(type_bien: str) -> pd.DataFrame:
    cache_path = CACHE_DIR / f"loyers_{type_bien}.parquet"
    if cache_path.exists():
        return pd.read_parquet(cache_path)

    url = LOYERS_URLS[type_bien]
    async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
        resp = await client.get(url)
        resp.raise_for_status()
    df = pd.read_csv(
        io.BytesIO(resp.content),
        sep=";",
        decimal=",",
        encoding="latin-1",
        dtype={"INSEE_C": str},
    )
    df.to_parquet(cache_path)
    return df


async def loyer_marche(code_insee: str, type_bien: str) -> dict | None:
    df = await _charger_loyers(type_bien)
    ligne = df[df["INSEE_C"] == code_insee]
    if ligne.empty:
        return None
    row = ligne.iloc[0]
    return {
        "loyer_m2_bas": round(float(row["lwr.IPm2"]), 2),
        "loyer_m2_moyen": round(float(row["loypredm2"]), 2),
        "loyer_m2_haut": round(float(row["upr.IPm2"]), 2),
        "nb_observations_commune": int(row["nbobs_com"]),
        "fiabilite_r2": round(float(row["R2_adj"]), 2),
    }
