"""Prépare les données de marché livrées avec l'application (app/data/) :

- communes_marche.parquet : prix médian au m² (ventes DVF des 24 derniers
  mois publiés, logement unique, ancien), loyer d'annonce au m² et
  rentabilité brute, par commune et type de bien ;
- saisonnalite_regions.json : nuitées réservées sur les plateformes en ligne,
  mois par mois, par région (Eurostat).

À relancer après chaque publication DVF (avril et octobre) ou une fois par
mois, puis committer app/data/. Tout télécharger prend 15 à 30 minutes ; les
fichiers bruts sont gardés en cache hors du projet (~/Library/Caches).

    venv/bin/python scripts/preparer_donnees.py
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path

CACHE = Path.home() / "Library" / "Caches" / "simulateur-immo"
CACHE.mkdir(parents=True, exist_ok=True)
os.environ.setdefault("IMMO_CACHE_DIR", str(CACHE))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import httpx  # noqa: E402
import pandas as pd  # noqa: E402

from app import market_data as md  # noqa: E402
from app.donnees_marche import (  # noqa: E402
    DATA_DIR,
    DEPARTEMENTS,
    FICHIER_COMMUNES,
    FICHIER_SAISONS,
    MIN_VENTES_CARTE,
    REGIONS_NUTS2,
)

EUROSTAT = "https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/tour_ce_omn12"
TYPES = {"Appartement": "appartement", "Maison": "maison"}


async def prix_par_commune() -> pd.DataFrame:
    lignes = []
    periodes = []
    for i, dept in enumerate(DEPARTEMENTS, start=1):
        try:
            ventes = await md._ventes_recentes(dept)
        except Exception as exc:  # noqa: BLE001
            print(f"  {dept} : échec ({exc}), ignoré")
            continue
        if ventes.empty:
            print(f"  {dept} : aucune vente")
            continue
        periodes.append((ventes["date"].min(), ventes["date"].max()))
        ancien = ventes[ventes["nature"] == md.NATURE_ANCIEN]
        stats = (
            ancien.groupby(["code_commune", "type_local"])["prix_m2"]
            .agg(prix_m2="median", nb_ventes="size")
            .reset_index()
        )
        stats["dept"] = dept
        lignes.append(stats)
        print(f"  {dept} ({i}/{len(DEPARTEMENTS)}) : {len(ancien)} ventes, {stats['code_commune'].nunique()} communes")
    table = pd.concat(lignes, ignore_index=True)
    table["type_bien"] = table["type_local"].map(TYPES)
    table = table.rename(columns={"code_commune": "code"}).drop(columns="type_local")
    debut = min(p[0] for p in periodes).strftime("%m/%Y")
    fin = max(p[1] for p in periodes).strftime("%m/%Y")
    table["periode"] = f"{debut} à {fin}"
    return table


async def loyers_par_commune() -> pd.DataFrame:
    frames = []
    for type_bien in ("appartement", "maison"):
        df = await md._charger_loyers(type_bien)
        frames.append(
            pd.DataFrame({"code": df["INSEE_C"], "type_bien": type_bien, "loyer_m2": df["loypredm2"].astype(float)})
        )
    return pd.concat(frames, ignore_index=True)


async def saisonnalite_regions() -> dict:
    """Nuitées mensuelles de la dernière année complète, par région."""
    resultat = {}
    async with httpx.AsyncClient(timeout=60) as client:
        for code, (nom, _) in REGIONS_NUTS2.items():
            params = {"format": "JSON", "lang": "fr", "geo": code, "c_resid": "TOTAL", "unit": "NR", "indic_to": "NGT_SP"}
            data = (await client.get(EUROSTAT, params=params)).json()
            if "value" not in data:
                print(f"  {code} {nom} : pas de données")
                continue
            dims = data["id"]
            tailles = data["size"]
            mois = list(data["dimension"]["month"]["category"]["index"].items())
            annees = sorted(data["dimension"]["time"]["category"]["index"].items(), key=lambda kv: kv[0], reverse=True)

            def valeur(mois_idx: int, annee_idx: int):
                # Index plat : dimensions dans l'ordre de `id`, toutes de taille 1
                # sauf month et time.
                pos = {"month": mois_idx, "time": annee_idx}
                index = 0
                for dim, taille in zip(dims, tailles):
                    index = index * taille + pos.get(dim, 0)
                return data["value"].get(str(index))

            for annee, annee_idx in annees:
                nuitees = [valeur(idx, annee_idx) for cle, idx in sorted(mois) if cle != "TOTAL"]
                if all(v for v in nuitees):
                    resultat[code] = {"annee": int(annee), "nuitees": nuitees}
                    print(f"  {code} {nom} : {annee}")
                    break
    return resultat


async def main() -> None:
    DATA_DIR.mkdir(exist_ok=True)
    print("Saisonnalité Eurostat…")
    saisons = await saisonnalite_regions()
    FICHIER_SAISONS.write_text(json.dumps(saisons, indent=1))

    print("Prix DVF par commune…")
    prix = await prix_par_commune()
    print("Loyers par commune…")
    loyers = await loyers_par_commune()
    table = prix.merge(loyers, on=["code", "type_bien"], how="left")
    fiable = table["nb_ventes"] >= MIN_VENTES_CARTE
    table["rendement_brut"] = (table["loyer_m2"] * 12 / table["prix_m2"]).where(fiable)
    table["prix_m2"] = table["prix_m2"].round(0)
    table["loyer_m2"] = table["loyer_m2"].round(2)
    table["rendement_brut"] = table["rendement_brut"].round(4)
    table = table[["code", "dept", "type_bien", "prix_m2", "nb_ventes", "loyer_m2", "rendement_brut", "periode"]]
    table.to_parquet(FICHIER_COMMUNES, index=False)
    print(f"Terminé : {len(table)} lignes, {FICHIER_COMMUNES.stat().st_size / 1e6:.1f} Mo")


if __name__ == "__main__":
    asyncio.run(main())
