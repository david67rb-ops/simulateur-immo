"""Mesure d'audience GoatCounter : sans cookie, sans donnée personnelle
(pas de bandeau de consentement). Pages vues, plus deux événements qui
servent de signaux de sortie de la bêta : la vérification d'un projet
(étude de marché lancée) et le téléchargement d'un dossier.

Rien dans l'application de bureau, ni tant que le code du compte
GoatCounter n'est pas renseigné (le site fonctionne alors sans mesure)."""
from __future__ import annotations

import json
import os

from nicegui import app, ui

# Code du compte : https://<code>.goatcounter.com
CODE = os.environ.get("IMMO_GOATCOUNTER", "credaura")


def actif() -> bool:
    return bool(CODE) and not app.native.main_window


def installer() -> None:
    """À appeler au début de chaque page du site."""
    if actif():
        # Le numéro de session de paiement (page de remerciement) suffit à
        # afficher un code de dossier : il ne part pas dans les statistiques.
        ui.add_head_html(
            "<script>window.goatcounter = {path: function (p) { return p.replace(/([?&])session_id=[^&#]*&?/, '$1')"
            ".replace(/[?&]$/, ''); }};</script>"
            f'<script data-goatcounter="https://{CODE}.goatcounter.com/count" async src="//gc.zgo.at/count.js"></script>'
        )


def evenement(nom: str, titre: str) -> None:
    if actif():
        # json.dumps : un titre avec une apostrophe (« d'un projet ») ne casse
        # plus le script, l'événement est bien compté.
        donnees = json.dumps({"path": nom, "title": titre, "event": True}, ensure_ascii=False)
        ui.run_javascript(f"window.goatcounter && window.goatcounter.count({donnees})")
