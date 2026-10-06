"""Page d'administration des codes de dossiers (/admin/codes) : créer un code
à la main (testeur, presse, geste commercial, paiement hors Stripe) et voir
où en sont les codes. Protégée par le mot de passe IMMO_ADMIN_MDP, défini
sur le serveur ; sans lui, la page est désactivée."""
from __future__ import annotations

import hmac
import os

from nicegui import ui

from app import codes

from . import theme
from .pages_legales import _gabarit

ORIGINES = ("testeur", "presse", "geste commercial", "paiement hors Stripe", "partenaire")


def _mot_de_passe() -> str:
    return os.environ.get("IMMO_ADMIN_MDP", "")


@ui.page("/admin/codes", title="Codes de dossiers · Credaura")
def page_admin_codes() -> None:
    colonne = _gabarit("Codes de dossiers", date=False)
    with colonne:
        if not _mot_de_passe():
            ui.label("Page désactivée : aucun mot de passe d'administration n'est défini sur le serveur.")
            return
        acces = ui.column().classes("w-full gap-2 mt-2")
        contenu = ui.column().classes("w-full gap-4 mt-2")
        contenu.visible = False

    with acces:
        mdp = ui.input("Mot de passe", password=True).props("outlined dense").classes("w-full max-w-sm")

        def entrer() -> None:
            if hmac.compare_digest((mdp.value or "").encode(), _mot_de_passe().encode()):
                acces.visible = False
                contenu.visible = True
                afficher_liste()
            else:
                ui.notify("Mot de passe incorrect", type="negative")

        mdp.on("keydown.enter", entrer)
        ui.button("Entrer", on_click=entrer).props("unelevated no-caps")

    with contenu:
        theme.subsection_title("Créer un code")
        with ui.row().classes("items-end gap-3 flex-wrap"):
            nombre = ui.select([1, 2, 3, 5, 10], value=1, label="Dossiers").props("outlined dense").classes("w-28")
            origine = ui.select(list(ORIGINES), value=ORIGINES[0], label="Origine").props("outlined dense").classes("w-56")
            note = ui.input("Note (prénom, média…)").props("outlined dense").classes("w-64")
        resultat = ui.label("").classes("text-lg font-semibold")

        def creer() -> None:
            code = codes.creer(int(nombre.value), origine.value, note.value or "")
            resultat.set_text(f"Nouveau code : {code} ({nombre.value} dossier{'s' if nombre.value > 1 else ''}, 12 mois)")
            note.set_value("")
            afficher_liste()

        ui.button("Créer le code", on_click=creer).props("unelevated no-caps")

        theme.subsection_title("Codes existants")
        tableau = ui.table(
            columns=[
                {"name": "code", "label": "Code", "field": "code", "align": "left"},
                {"name": "utilises", "label": "Utilisés", "field": "utilises"},
                {"name": "dossiers", "label": "Dossiers", "field": "dossiers"},
                {"name": "expire_le", "label": "Expire le", "field": "expire_le"},
                {"name": "origine", "label": "Origine", "field": "origine", "align": "left"},
                {"name": "note", "label": "Note", "field": "note", "align": "left"},
            ],
            rows=[],
            row_key="code",
        ).classes("w-full").props("dense flat")

        def afficher_liste() -> None:
            tableau.rows = codes.lister()
            tableau.update()
