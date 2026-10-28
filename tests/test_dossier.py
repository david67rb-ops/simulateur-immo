"""Contenu du dossier Word. Lancement : venv/bin/python -m unittest discover -s tests"""
from __future__ import annotations

import io
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from docx import Document  # noqa: E402

from app import dossier_export, schemas  # noqa: E402


def _texte(contenu: bytes) -> str:
    """Tout le texte du document, tableaux imbriqués compris."""
    doc = Document(io.BytesIO(contenu))
    return "\n".join(t.text for t in doc.element.body.iter("{http://schemas.openxmlformats.org/wordprocessingml/2006/main}t"))


class RegimeLocatif(unittest.TestCase):
    def test_courte_duree_jamais_en_location_nue(self):
        # Le champ « nue / meublée » reste à « nue » par défaut, masqué en courte durée.
        inp = schemas.SimulationInput(
            type_projet="location_courte_duree", regime_location="nue", surface_m2=42, prix_achat=70_000,
            frais_notaire=6_541, montant_travaux=8_000, prix_nuitee=80, taux_occupation_pct=0.5,
        )
        texte = _texte(dossier_export.generer_dossier_word(schemas.ExportDossierInput(simulation=inp)))
        self.assertIn("Meublé de tourisme (location courte durée)", texte)
        self.assertNotIn("Location nue", texte)


if __name__ == "__main__":
    unittest.main()
