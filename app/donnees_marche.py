"""Données de marché préparées à l'avance (scripts/preparer_donnees.py) et
carte de rentabilité des communes.

- `data/communes_marche.parquet` : par commune (arrondissement pour Paris,
  Lyon, Marseille) et type de bien, prix médian au m² des ventes DVF des 24
  derniers mois publiés, loyer d'annonce au m² (carte des loyers) et
  rentabilité brute.
- `data/saisonnalite_regions.json` : nuitées réservées sur les plateformes en
  ligne, mois par mois, par région (Eurostat, tour_ce_omn12).
- Contours des communes : geo.api.gouv.fr, mis en cache sur disque.
"""
from __future__ import annotations

import json
import time
from functools import lru_cache
from pathlib import Path

from .market_data import CACHE_DIR, DEPARTEMENTS_SANS_DVF, requete

DATA_DIR = Path(__file__).parent / "data"
FICHIER_COMMUNES = DATA_DIR / "communes_marche.parquet"
FICHIER_SAISONS = DATA_DIR / "saisonnalite_regions.json"
GEO_API = "https://geo.api.gouv.fr"
CACHE_CONTOURS_JOURS = 90

# Communes découpées en arrondissements municipaux (DVF et loyers sont au
# niveau de l'arrondissement) : la carte affiche les arrondissements.
COMMUNES_A_ARRONDISSEMENTS = {"75": "75056", "69": "69123", "13": "13055"}

# Nombre minimal de ventes pour afficher un prix médian sur la carte.
MIN_VENTES_CARTE = 10

# Rentabilité brute : bornes et couleurs de la légende (du plus faible au
# plus élevé), comme la carte Horiz.io (≤ 3 % … ≥ 9 %).
ECHELLE_RENDEMENT = [
    (0.03, "#b23a32", "≤ 3 %"),
    (0.04, "#e07b4f", "3 à 4 %"),
    (0.05, "#e9b35a", "4 à 5 %"),
    (0.06, "#d7d36a", "5 à 6 %"),
    (0.07, "#9cc27a", "6 à 7 %"),
    (0.09, "#4f8f6c", "7 à 9 %"),
    (float("inf"), "#2d6a4f", "≥ 9 %"),
]
COULEUR_SANS_DONNEE = "#b8bec4"

# Régions NUTS 2 (anciennes régions) de chaque département, pour la
# saisonnalité Eurostat.
REGIONS_NUTS2 = {
    "FR10": ("Île-de-France", "75 77 78 91 92 93 94 95"),
    "FRB0": ("Centre-Val de Loire", "18 28 36 37 41 45"),
    "FRC1": ("Bourgogne", "21 58 71 89"),
    "FRC2": ("Franche-Comté", "25 39 70 90"),
    "FRD1": ("Basse-Normandie", "14 50 61"),
    "FRD2": ("Haute-Normandie", "27 76"),
    "FRE1": ("Nord-Pas-de-Calais", "59 62"),
    "FRE2": ("Picardie", "02 60 80"),
    "FRF1": ("Alsace", "67 68"),
    "FRF2": ("Champagne-Ardenne", "08 10 51 52"),
    "FRF3": ("Lorraine", "54 55 57 88"),
    "FRG0": ("Pays de la Loire", "44 49 53 72 85"),
    "FRH0": ("Bretagne", "22 29 35 56"),
    "FRI1": ("Aquitaine", "24 33 40 47 64"),
    "FRI2": ("Limousin", "19 23 87"),
    "FRI3": ("Poitou-Charentes", "16 17 79 86"),
    "FRJ1": ("Languedoc-Roussillon", "11 30 34 48 66"),
    "FRJ2": ("Midi-Pyrénées", "09 12 31 32 46 65 81 82"),
    "FRK1": ("Auvergne", "03 15 43 63"),
    "FRK2": ("Rhône-Alpes", "01 07 26 38 42 69 73 74"),
    "FRL0": ("Provence-Alpes-Côte d'Azur", "04 05 06 13 83 84"),
    "FRM0": ("Corse", "2A 2B"),
    "FRY1": ("Guadeloupe", "971"),
    "FRY2": ("Martinique", "972"),
    "FRY3": ("Guyane", "973"),
    "FRY4": ("La Réunion", "974"),
    "FRY5": ("Mayotte", "976"),
}
REGION_DU_DEPARTEMENT = {dept: code for code, (_, depts) in REGIONS_NUTS2.items() for dept in depts.split()}

# Départements couverts par la carte (DVF publié).
DEPARTEMENTS = [
    *(f"{n:02d}" for n in range(1, 96) if n != 20),
    "2A",
    "2B",
    "971",
    "972",
    "973",
    "974",
]
DEPARTEMENTS = [d for d in DEPARTEMENTS if d not in DEPARTEMENTS_SANS_DVF]


def couleur_rendement(rendement: float | None) -> str:
    if rendement is None:
        return COULEUR_SANS_DONNEE
    for borne, couleur, _ in ECHELLE_RENDEMENT:
        if rendement <= borne:
            return couleur
    return ECHELLE_RENDEMENT[-1][1]


@lru_cache(maxsize=1)
def _table_communes():
    import pandas as pd

    if not FICHIER_COMMUNES.exists():
        return pd.DataFrame()
    return pd.read_parquet(FICHIER_COMMUNES)


def indicateurs_communes(dept: str, type_bien: str) -> dict[str, dict]:
    """{code commune: indicateurs} pour un département et un type de bien."""
    table = _table_communes()
    if table.empty:
        return {}
    lignes = table[(table["dept"] == dept) & (table["type_bien"] == type_bien)]
    return {ligne["code"]: ligne for ligne in lignes.to_dict("records")}


def periode_donnees() -> str | None:
    table = _table_communes()
    return None if table.empty else str(table["periode"].iloc[0])


async def _get_json(url: str, params: dict) -> dict:
    resp = await requete(url, params)
    resp.raise_for_status()
    return resp.json()


async def contours_departement(dept: str) -> dict:
    """GeoJSON des communes du département (arrondissements pour Paris, Lyon
    et Marseille), mis en cache sur disque."""
    cache = CACHE_DIR / f"contours_{dept}.json"
    if cache.exists() and (time.time() - cache.stat().st_mtime) / 86_400 < CACHE_CONTOURS_JOURS:
        return json.loads(cache.read_text())
    params = {"format": "geojson", "geometry": "contour", "fields": "code,nom"}
    communes = await _get_json(f"{GEO_API}/departements/{dept}/communes", params)
    if dept in COMMUNES_A_ARRONDISSEMENTS:
        arrondissements = await _get_json(
            f"{GEO_API}/communes",
            {**params, "codeDepartement": dept, "type": "arrondissement-municipal"},
        )
        parent = COMMUNES_A_ARRONDISSEMENTS[dept]
        communes["features"] = [
            f for f in communes["features"] if f["properties"]["code"] != parent
        ] + arrondissements["features"]
    for feature in communes["features"]:
        feature["geometry"]["coordinates"] = _arrondir(feature["geometry"]["coordinates"])
    cache.write_text(json.dumps(communes, separators=(",", ":")))
    return communes


def _arrondir(coordonnees):
    """Coordonnées arrondies à 4 décimales (~10 m) : carte deux fois plus
    légère à transmettre au navigateur, sans différence visible."""
    if isinstance(coordonnees, float):
        return round(coordonnees, 4)
    return [_arrondir(c) for c in coordonnees]


async def carte_rentabilite(dept: str, type_bien: str) -> dict:
    """GeoJSON des communes du département, avec pour chacune prix médian,
    loyer, rentabilité brute et couleur de la légende."""
    geojson = await contours_departement(dept)
    indicateurs = indicateurs_communes(dept, type_bien)
    for feature in geojson["features"]:
        props = feature["properties"]
        ind = indicateurs.get(props["code"]) or {}
        rendement = ind.get("rendement_brut")
        rendement = None if rendement != rendement else rendement  # NaN → None
        props.update(
            {
                "prix_m2": _nombre(ind.get("prix_m2")),
                "loyer_m2": _nombre(ind.get("loyer_m2")),
                "nb_ventes": int(ind.get("nb_ventes") or 0),
                "rendement": rendement,
                "couleur": couleur_rendement(rendement),
            }
        )
    return geojson


def _nombre(v) -> float | None:
    return None if v is None or v != v else float(v)


@lru_cache(maxsize=1)
def _saisons_regions() -> dict:
    if not FICHIER_SAISONS.exists():
        return {}
    return json.loads(FICHIER_SAISONS.read_text())


def saisonnalite_region(dept: str) -> dict | None:
    """Coefficients mensuels d'occupation (moyenne 1) tirés des nuitées
    réservées sur les plateformes dans la région, et coefficients de prix
    qui suivent la demande pour moitié (hypothèse : les hôtes relèvent leurs
    prix en haute saison, sans suivre toute la hausse de fréquentation)."""
    code = REGION_DU_DEPARTEMENT.get(dept)
    donnees = _saisons_regions().get(code or "")
    if not donnees:
        return None
    from .saisonnalite import JOURS

    par_jour = [n / j for n, j in zip(donnees["nuitees"], JOURS)]
    moyenne = sum(par_jour) / 12
    occupation = [v / moyenne for v in par_jour]
    prix = [min(max(1 + 0.5 * (c - 1), 0.7), 1.5) for c in occupation]
    return {
        "region": REGIONS_NUTS2[code][0],
        "annee": donnees["annee"],
        "occupation": [round(c, 3) for c in occupation],
        "prix": [round(c, 3) for c in prix],
    }
