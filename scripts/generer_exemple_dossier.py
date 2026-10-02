"""Génère l'exemple de dossier de financement proposé en téléchargement
(app/data/exemple-dossier/) : un emprunteur fictif, un appartement en
location meublée à Saint-Étienne, avec la vraie étude de marché du quartier.

À relancer après chaque évolution du dossier ou des données de marché, puis
committer app/data/exemple-dossier/. Sur macOS, la version PDF est produite
par Microsoft Word s'il est installé (seul le document généré est ouvert puis
refermé).

    venv/bin/python scripts/generer_exemple_dossier.py
"""
from __future__ import annotations

import asyncio
import shutil
import subprocess
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))

from app import dossier_export, donnees_marche, market_data, schemas  # noqa: E402
from app.chapitres_dossier import CHAPITRES_OPTIONNELS  # noqa: E402
from gui.main import _marche_pour_dossier, build_simulation_input  # noqa: E402
from gui.state import default_sim_state  # noqa: E402

DOSSIER = RACINE / "app" / "data" / "exemple-dossier"
NOM = "Exemple de dossier de financement"
ADRESSE = "12 rue Michelet, 42000 Saint-Étienne"
SURFACE = 65


async def etude_de_marche() -> tuple[dict, dict, dict, dict]:
    geo = await market_data.geocoder_adresse(ADRESSE)
    comparables = await market_data.comparables_dvf(
        geo["code_departement"], geo["lat"], geo["lon"], "appartement", 500, SURFACE
    )
    loyer = await market_data.loyer_marche(geo["code_insee"], "appartement")
    marche = _marche_pour_dossier(geo, comparables, loyer, "appartement")
    marche["communes_geojson"] = await donnees_marche.carte_rentabilite(geo["code_departement"], "appartement")
    return geo, comparables, loyer, marche


def main() -> None:
    geo, comparables, loyer, marche = asyncio.run(etude_de_marche())
    etat = default_sim_state()
    etat.update(
        {
            "surface_m2": SURFACE,
            # Un projet équilibré, sans être idéal : prix 5 % sous la médiane du
            # quartier, loyer meublé 10 % au-dessus du loyer de marché (nu).
            "prix_achat": round(comparables["prix_m2_moyen"] * SURFACE * 0.95, -3),
            "loyer_mensuel_hors_charges": round(loyer["loyer_m2_moyen"] * SURFACE * 1.10, -1),
            "regime_location": "meublee",
            "montant_mobilier": 5000,
            "montant_travaux": 8000,
            "charges_copropriete_annuelles": 800,
            "taxe_fonciere_annuelle": 850,
            "apport": 25000,
            "duree_credit_annees": 25,
            "frais_comptable_annuel": 400,
        }
    )
    L = schemas.LignePatrimoine
    contenu = dossier_export.generer_dossier_word(
        schemas.ExportDossierInput(
            simulation=build_simulation_input(etat),
            profil=schemas.ProfilEmprunteurInput(revenus_nets_mensuels_foyer=4500, mensualites_credits_existants=200),
            nom_emprunteur="Camille Exemple (emprunteur fictif)",
            adresse_bien=geo["label"],
            marche=marche,
            # Pas de photos : l'exemple montrerait des emplacements vides.
            chapitres=[c for c in CHAPITRES_OPTIONNELS if c != "photos"],
            patrimoine=[
                L(nature="Résidence principale", detail="Saint-Étienne", valeur=210000, reste_du=95000),
                L(nature="Comptes courants et livrets", detail="Livret A, LDDS", valeur=18000),
                L(nature="Assurance-vie", valeur=25000),
            ],
        )
    )
    DOSSIER.mkdir(parents=True, exist_ok=True)
    docx = DOSSIER / f"{NOM}.docx"
    docx.write_bytes(contenu)
    print(f"Word : {docx}")
    if sys.platform == "darwin" and Path("/Applications/Microsoft Word.app").exists():
        pdf = docx.with_suffix(".pdf")
        # Word (application isolée) n'écrit que dans son propre dossier : on
        # y convertit une copie, puis on rapatrie le PDF.
        bac = Path.home() / "Library/Containers/com.microsoft.Word/Data/Documents/exemple-dossier"
        bac.mkdir(parents=True, exist_ok=True)
        copie = bac / docx.name
        shutil.copy(docx, copie)
        script = f'''
        tell application "Microsoft Word"
            open file name ((POSIX file "{copie}") as string)
            set d to active document
            save as d file name ((POSIX file "{copie.with_suffix('.pdf')}") as string) file format format PDF
            close d saving no
        end tell
        '''
        subprocess.run(["osascript", "-e", script], check=True)
        shutil.move(copie.with_suffix(".pdf"), pdf)
        copie.unlink()
        print(f"PDF : {pdf}")

if __name__ == "__main__":
    main()
