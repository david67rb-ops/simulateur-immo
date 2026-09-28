"""Étude de marché automatique à partir de sources open-data françaises :

- Géocodage : API Adresse (api-adresse.data.gouv.fr, Base Adresse Nationale)
- Prix de vente : DVF géolocalisé (files.data.gouv.fr/geo-dvf), par département,
  agrégé en une ligne par vente d'un logement unique
- Loyers de marché : "Carte des loyers" (data.gouv.fr / DHUP), par commune

Les fichiers DVF et loyers sont volumineux : on les télécharge une fois par
département/catégorie puis on les met en cache sur disque (data_cache/),
rafraîchi périodiquement.
"""
from __future__ import annotations

import gzip
import io
import sys
import time
from datetime import date
from pathlib import Path
from typing import TYPE_CHECKING

import httpx

if TYPE_CHECKING:
    import pandas as pd

if getattr(sys, "frozen", False):
    # Application packagée (PyInstaller) : le dossier de l'app est en lecture
    # seule (ex. /Applications), le cache doit vivre dans le profil utilisateur.
    CACHE_DIR = Path.home() / "Library" / "Application Support" / "Simulateur Immobilier" / "data_cache"
else:
    CACHE_DIR = Path(__file__).parent / "data_cache"
CACHE_DIR.mkdir(parents=True, exist_ok=True)

GEOCODE_URL = "https://api-adresse.data.gouv.fr/search/"
DVF_URL_TEMPLATE = "https://files.data.gouv.fr/geo-dvf/latest/csv/{annee}/departements/{dept}.csv.gz"

LOYERS_URLS = {
    "appartement": "https://static.data.gouv.fr/resources/carte-des-loyers-indicateurs-de-loyers-dannonce-par-commune-en-2025/20251211-145010/pred-app-mef-dhup.csv",
    "maison": "https://static.data.gouv.fr/resources/carte-des-loyers-indicateurs-de-loyers-dannonce-par-commune-en-2025/20251211-145039/pred-mai-mef-dhup.csv",
}

# DVF est publié deux fois par an : on garde les ventes des 24 derniers mois
# disponibles, et on retélécharge les fichiers passé ce délai de cache.
PERIODE_MOIS = 24
CACHE_DVF_JOURS = 30
CACHE_DVF_ABSENT_JOURS = 7  # année pas encore publiée : on revérifie plus souvent

# En dessous, la médiane n'est pas représentative : on élargit la recherche.
MIN_VENTES = 15
VENTES_FIABILITE_ELEVEE = 30
TOLERANCE_SURFACE = 0.30  # comparables à ±30 % de la surface du bien
TOLERANCE_SURFACE_ELARGIE = 0.50
RAYONS_ELARGIS_M = (1_000, 2_000)
NB_VENTES_LISTEES = 50

# L'Alsace-Moselle (livre foncier) et Mayotte ne sont pas couverts par DVF.
DEPARTEMENTS_SANS_DVF = {"57": "la Moselle", "67": "le Bas-Rhin", "68": "le Haut-Rhin", "976": "Mayotte"}

NATURE_ANCIEN = "Vente"
NATURE_NEUF = "Vente en l'état futur d'achèvement"
TYPES_LOGEMENT = ("Appartement", "Maison")

# Ancien format de cache (lignes DVF brutes), remplacé par les ventes agrégées.
for _ancien in CACHE_DIR.glob("dvf_*.parquet"):
    _ancien.unlink(missing_ok=True)


class MarketDataError(Exception):
    pass


def code_departement(code_insee: str) -> str:
    # Outre-mer : département sur 3 caractères (971, 972…).
    return code_insee[:3] if code_insee.startswith("97") else code_insee[:2]


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
        "code_departement": code_departement(props.get("citycode", "")),
        "lon": lon,
        "lat": lat,
    }


def _age_jours(path: Path) -> float:
    return (time.time() - path.stat().st_mtime) / 86_400


def _ventes_par_mutation(df: pd.DataFrame) -> pd.DataFrame:
    """Une ligne par vente d'un logement unique. Dans DVF, une vente occupe
    plusieurs lignes (lots, parcelles, natures de culture) qui répètent toutes
    le prix total : une vente en bloc de 5 appartements à 1 M€ afficherait
    sinon 1 M€ pour chacun. On ne garde donc que les ventes portant sur un
    seul logement (caves, parkings et terrain acceptés)."""
    import pandas as pd

    df = df[df["nature_mutation"].isin([NATURE_ANCIEN, NATURE_NEUF])].dropna(subset=["valeur_fonciere"])
    bati = df[df["type_local"].notna() & (df["type_local"] != "Dépendance")]
    bati = bati.drop_duplicates(
        subset=["id_mutation", "type_local", "surface_reelle_bati", "nombre_pieces_principales", "id_parcelle"]
    )
    locaux = bati.groupby("id_mutation").agg(
        nb_locaux=("type_local", "size"),
        type_local=("type_local", "first"),
        surface=("surface_reelle_bati", "first"),
        pieces=("nombre_pieces_principales", "first"),
        latitude=("latitude", "first"),
        longitude=("longitude", "first"),
        adresse_numero=("adresse_numero", "first"),
        adresse_nom_voie=("adresse_nom_voie", "first"),
    )
    locaux = locaux[(locaux["nb_locaux"] == 1) & locaux["type_local"].isin(TYPES_LOGEMENT)]
    infos = df.groupby("id_mutation").agg(
        date=("date_mutation", "first"),
        nature=("nature_mutation", "first"),
        valeur=("valeur_fonciere", "first"),
        nom_commune=("nom_commune", "first"),
    )
    ventes = locaux.join(infos, how="inner").dropna(subset=["surface", "latitude", "longitude"])
    ventes = ventes[ventes["surface"] >= 9]
    ventes["prix_m2"] = ventes["valeur"] / ventes["surface"]
    ventes = ventes[(ventes["prix_m2"] > 200) & (ventes["prix_m2"] < 30_000)]
    ventes["date"] = pd.to_datetime(ventes["date"])
    numero = ventes["adresse_numero"].map(lambda n: "" if pd.isna(n) else f"{int(n)} ")
    ventes["adresse"] = (numero + ventes["adresse_nom_voie"].fillna("")).str.strip() + ", " + ventes["nom_commune"]
    return ventes[
        ["date", "nature", "type_local", "surface", "pieces", "valeur", "prix_m2", "latitude", "longitude", "adresse"]
    ].reset_index(drop=True)


async def _ventes_annee(dept: str, annee: int) -> pd.DataFrame | None:
    """Ventes d'une année pour un département, None si l'année n'est pas (encore)
    publiée. Cache disque rafraîchi tous les CACHE_DVF_JOURS ; en cas d'échec
    réseau, on se rabat sur le cache même périmé."""
    import pandas as pd

    cache = CACHE_DIR / f"ventes_{dept}_{annee}.parquet"
    absent = CACHE_DIR / f"ventes_{dept}_{annee}.absent"
    if cache.exists() and _age_jours(cache) < CACHE_DVF_JOURS:
        return pd.read_parquet(cache)
    if absent.exists() and _age_jours(absent) < CACHE_DVF_ABSENT_JOURS:
        return None

    url = DVF_URL_TEMPLATE.format(annee=annee, dept=dept)
    try:
        async with httpx.AsyncClient(timeout=60, follow_redirects=True) as client:
            resp = await client.get(url)
        if resp.status_code == 404:
            absent.touch()
            return None
        resp.raise_for_status()
    except httpx.HTTPError:
        if cache.exists():
            return pd.read_parquet(cache)
        raise

    brut = pd.read_csv(
        io.BytesIO(gzip.decompress(resp.content)),
        usecols=[
            "id_mutation",
            "date_mutation",
            "nature_mutation",
            "valeur_fonciere",
            "adresse_numero",
            "adresse_nom_voie",
            "nom_commune",
            "id_parcelle",
            "type_local",
            "surface_reelle_bati",
            "nombre_pieces_principales",
            "longitude",
            "latitude",
        ],
        dtype={"id_parcelle": str, "adresse_nom_voie": str, "nom_commune": str},
        low_memory=False,
    )
    ventes = _ventes_par_mutation(brut)
    ventes.to_parquet(cache)
    absent.unlink(missing_ok=True)
    return ventes


async def _ventes_recentes(dept: str) -> pd.DataFrame:
    """Ventes des PERIODE_MOIS derniers mois publiés pour le département."""
    import pandas as pd

    frames: list[pd.DataFrame] = []
    annee = date.today().year
    for a in range(annee, annee - 5, -1):
        df = await _ventes_annee(dept, a)
        if df is None:
            if frames:
                break
            continue
        frames.append(df)
        date_max = max(f["date"].max() for f in frames)
        date_min = min(f["date"].min() for f in frames)
        # Une année publiée commence début janvier : un mois de marge évite de
        # télécharger une année de plus pour quelques jours manquants.
        if date_min <= date_max - pd.DateOffset(months=PERIODE_MOIS - 1):
            break
    if not frames:
        return pd.DataFrame()
    ventes = pd.concat(frames, ignore_index=True)
    return ventes[ventes["date"] > ventes["date"].max() - pd.DateOffset(months=PERIODE_MOIS)]


def _distances_m(lat: float, lon: float, lats, lons):
    import numpy as np

    phi1, phi2 = np.radians(lat), np.radians(lats)
    dphi = phi2 - phi1
    dlambda = np.radians(lons) - np.radians(lon)
    a = np.sin(dphi / 2) ** 2 + np.cos(phi1) * np.cos(phi2) * np.sin(dlambda / 2) ** 2
    return 2 * 6_371_000 * np.arcsin(np.sqrt(a))


def _etapes_recherche(rayon_m: int, surface_m2: float | None) -> list[tuple[int, float | None]]:
    """Recherches successives, de la plus précise à la plus large : rayon
    demandé puis 1 km et 2 km à surface proche, puis tolérance de surface
    élargie, puis toutes surfaces."""
    rayons = sorted({rayon_m, *(max(rayon_m, r) for r in RAYONS_ELARGIS_M)})
    if not surface_m2:
        return [(r, None) for r in rayons]
    return [(r, TOLERANCE_SURFACE) for r in rayons] + [
        (rayons[-1], TOLERANCE_SURFACE_ELARGIE),
        (rayons[-1], None),
    ]


async def comparables_dvf(
    code_departement: str,
    lat: float,
    lon: float,
    type_local: str,
    rayon_m: int,
    surface_m2: float | None = None,
    neuf: bool = False,
) -> dict:
    """Prix au m² des ventes comparables (même type de bien, ancien ou neuf,
    surface proche, autour de l'adresse) sur les 24 derniers mois publiés.
    Le rayon et la tolérance de surface s'élargissent tant qu'il y a moins de
    MIN_VENTES ventes ; le résultat indique la recherche réellement retenue
    et un niveau de fiabilité."""
    resultat = {
        "nb_transactions": 0,
        "prix_m2_bas": None,
        "prix_m2_moyen": None,
        "prix_m2_haut": None,
        "rayon_demande": rayon_m,
        "ventes": [],
    }
    if code_departement in DEPARTEMENTS_SANS_DVF:
        resultat["indisponible"] = (
            f"Les ventes immobilières ne sont pas publiées pour {DEPARTEMENTS_SANS_DVF[code_departement]} "
            "(régime du livre foncier, hors base DVF) : saisissez le prix d'achat à partir d'annonces "
            "ou d'une estimation d'agence."
        )
        return resultat

    ventes = await _ventes_recentes(code_departement)
    if ventes.empty:
        return resultat

    type_dvf = "Appartement" if type_local == "appartement" else "Maison"
    ventes = ventes[ventes["type_local"] == type_dvf]
    ventes = ventes.assign(distance_m=_distances_m(lat, lon, ventes["latitude"], ventes["longitude"]))
    periode = (ventes["date"].min(), ventes["date"].max())

    natures = [NATURE_NEUF, NATURE_ANCIEN] if neuf else [NATURE_ANCIEN]
    for nature in natures:
        candidats = ventes[ventes["nature"] == nature]
        retenu = None
        for rayon, tolerance in _etapes_recherche(rayon_m, surface_m2):
            selection = candidats[candidats["distance_m"] <= rayon]
            if tolerance is not None:
                selection = selection[
                    selection["surface"].between(surface_m2 * (1 - tolerance), surface_m2 * (1 + tolerance))
                ]
            retenu = (rayon, tolerance, selection)
            if len(selection) >= MIN_VENTES:
                break
        if retenu is not None and len(retenu[2]):
            break

    rayon, tolerance, selection = retenu
    if selection.empty:
        return resultat

    n = len(selection)
    elargi = rayon > rayon_m or (bool(surface_m2) and tolerance != TOLERANCE_SURFACE)
    if n >= VENTES_FIABILITE_ELEVEE and not elargi:
        fiabilite = "elevee"
    elif n >= MIN_VENTES:
        fiabilite = "moyenne"
    else:
        fiabilite = "faible"

    p10, p50, p90 = selection["prix_m2"].quantile([0.10, 0.50, 0.90])
    liste = selection.sort_values("date", ascending=False).head(NB_VENTES_LISTEES)
    resultat.update(
        {
            "nb_transactions": n,
            "prix_m2_bas": round(float(p10), 0),
            "prix_m2_moyen": round(float(p50), 0),
            "prix_m2_haut": round(float(p90), 0),
            "rayon_utilise": rayon,
            "tolerance_surface": tolerance if surface_m2 else None,
            "surface_min": round(surface_m2 * (1 - tolerance)) if surface_m2 and tolerance is not None else None,
            "surface_max": round(surface_m2 * (1 + tolerance)) if surface_m2 and tolerance is not None else None,
            "neuf": nature == NATURE_NEUF,
            "repli_ancien": neuf and nature == NATURE_ANCIEN,
            "periode_debut": periode[0].strftime("%m/%Y"),
            "periode_fin": periode[1].strftime("%m/%Y"),
            "fiabilite": fiabilite,
            "ventes": [
                {
                    "date": v.date.strftime("%d/%m/%Y"),
                    "adresse": v.adresse,
                    "surface": round(float(v.surface)),
                    "pieces": None if v.pieces != v.pieces else int(v.pieces),
                    "prix": round(float(v.valeur)),
                    "prix_m2": round(float(v.prix_m2)),
                    "distance_m": round(float(v.distance_m) / 10) * 10,
                }
                for v in liste.itertuples()
            ],
        }
    )
    return resultat


async def _charger_loyers(type_bien: str) -> pd.DataFrame:
    import pandas as pd

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


# Aucune source ouverte fiable (équivalent DVF/DHUP) n'existe pour les tarifs
# et taux d'occupation des meublés de tourisme par commune. On dérive un
# ordre de grandeur à partir du loyer nu de la zone (donnée réelle DHUP) :
# - prix/nuitée = loyer nu ramené à la journée × un multiplicateur usuel
#   (une location à la nuitée se facture historiquement plus cher au
#   prorata qu'une location nue, pour compenser vacance/ménage/services) ;
# - taux d'occupation = hypothèse nationale générique (indépendante de la
#   commune, faute de signal disponible sur l'attractivité touristique réelle).
# À ajuster impérativement selon la zone (littoral/montagne/grande ville vs
# secteur peu touristique).
MULTIPLICATEUR_NUITEE = 3.0
TAUX_OCCUPATION_ESTIME = {"bas": 0.35, "moyen": 0.50, "haut": 0.65}


def estimer_nuitee_et_occupation(loyer: dict | None, surface_m2: float) -> dict | None:
    """Estimation pédagogique du prix/nuitée et du taux d'occupation pour une
    location courte durée, à partir du loyer nu de marché (voir note
    ci-dessus). Renvoie None si aucun loyer de référence n'est disponible."""
    if not loyer or not surface_m2:
        return None
    resultat: dict[str, float] = {}
    for niveau, cle in (("bas", "loyer_m2_bas"), ("moyen", "loyer_m2_moyen"), ("haut", "loyer_m2_haut")):
        loyer_m2 = loyer.get(cle)
        if not loyer_m2:
            continue
        loyer_mensuel = loyer_m2 * surface_m2
        resultat[f"prix_nuitee_{niveau}"] = round((loyer_mensuel / 30) * MULTIPLICATEUR_NUITEE, 0)
        resultat[f"taux_occupation_{niveau}"] = TAUX_OCCUPATION_ESTIME[niveau]
    return resultat or None
