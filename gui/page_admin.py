"""Page d'administration des codes de dossiers (/admin/codes) : créer un code
à la main (testeur, presse, geste commercial, paiement hors Stripe), voir où
en sont les codes, désactiver un code remboursé et lancer le diagnostic du
paiement. Protégée par le mot de passe IMMO_ADMIN_MDP, défini sur le
serveur ; sans lui, la page est désactivée.

Le contenu n'est construit qu'après le bon mot de passe : des boutons
seulement masqués resteraient joignables par un message fabriqué à la main."""
from __future__ import annotations

import hmac
import os

from nicegui import ui

from app import codes

from . import paiement_pages, theme
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
    try:
        base = paiement_pages.adresse_publique(ui.context.client.request)
    except Exception:  # noqa: BLE001  (pas de requête : application de bureau)
        base = "http://localhost"
    etat = {"connecte": False}

    with acces:
        mdp = ui.input("Mot de passe", password=True).props("outlined dense").classes("w-full max-w-sm")

        def entrer() -> None:
            if etat["connecte"]:
                return
            if hmac.compare_digest((mdp.value or "").encode(), _mot_de_passe().encode()):
                etat["connecte"] = True
                acces.delete()
                with contenu:
                    _construire(etat, base)
            else:
                ui.notify("Mot de passe incorrect", type="negative")

        mdp.on("keydown.enter", entrer)
        ui.button("Entrer", on_click=entrer).props("unelevated no-caps")


def _construire(etat: dict, base: str) -> None:
    """Le contenu de la page, une fois le mot de passe vérifié."""
    theme.subsection_title("Diagnostic du paiement")
    ui.label(
        "Vérifie la configuration (clés Stripe, webhook, facture, base des codes, clé de signature). En mode test, "
        "crée aussi une page de paiement d'essai."
    ).classes(theme.HINT_CLASSES)
    zone_diagnostic = ui.column().classes("w-full gap-1")

    async def diagnostiquer() -> None:
        if not etat["connecte"]:
            return
        bouton_diagnostic.disable()
        zone_diagnostic.clear()
        with zone_diagnostic:
            ui.spinner(size="sm")
        try:
            lignes = await paiement_pages.verifications(base)
        finally:
            bouton_diagnostic.enable()
        zone_diagnostic.clear()
        with zone_diagnostic:
            for ok, titre, texte, lien in lignes:
                signe, couleur = ("—", "#555") if ok is None else (("✔", "#2d6a4f") if ok else ("✘", "#b23a32"))
                with ui.row().classes("w-full items-start gap-2 no-wrap"):
                    ui.label(signe).classes("font-bold w-4 shrink-0").style(f"color:{couleur}")
                    with ui.column().classes("gap-0"):
                        ui.label(titre).classes("text-sm font-semibold")
                        if lien:
                            ui.link(texte, lien, new_tab=True).classes("text-sm")
                        else:
                            ui.label(texte).classes("text-sm")

    bouton_diagnostic = ui.button("Diagnostic du paiement", icon="fact_check", on_click=diagnostiquer).props(
        "outline no-caps"
    )

    theme.subsection_title("Créer un code")
    with ui.row().classes("items-end gap-3 flex-wrap"):
        nombre = ui.select([1, 2, 3, 5, 10], value=1, label="Dossiers").props("outlined dense").classes("w-28")
        origine = ui.select(list(ORIGINES), value=ORIGINES[0], label="Origine").props("outlined dense").classes("w-56")
        note = ui.input("Note (prénom, média…)").props("outlined dense").classes("w-64")
    resultat = ui.label("").classes("text-lg font-semibold")

    def creer() -> None:
        if not etat["connecte"]:
            return
        code = codes.creer(int(nombre.value), origine.value, note.value or "")
        resultat.set_text(f"Nouveau code : {code} ({nombre.value} dossier{'s' if nombre.value > 1 else ''}, 12 mois)")
        note.set_value("")
        afficher_liste()

    ui.button("Créer le code", on_click=creer).props("unelevated no-caps")

    theme.subsection_title("Désactiver un code (achat remboursé)")
    ui.label(
        "Après un remboursement (garantie de conformité, geste commercial) : rembourser dans Stripe, puis "
        "désactiver le code ici. La colonne « Utilisés » indique les dossiers déjà ouverts avec ce code."
    ).classes(theme.HINT_CLASSES)
    with ui.row().classes("items-end gap-3 flex-wrap"):
        code_a_desactiver = ui.input("Code", placeholder="CRED-XXXX-XXXX").props("outlined dense").classes("w-56")
    resultat_desactivation = ui.label("").classes("text-sm")

    def desactiver() -> None:
        if not etat["connecte"]:
            return
        avant = codes.desactiver(code_a_desactiver.value or "")
        if avant is None:
            resultat_desactivation.set_text("Code introuvable.")
            return
        utilises = avant["dossiers"] - avant["restants"]
        resultat_desactivation.set_text(
            f"{avant['code']} désactivé ({utilises} dossier{'s' if utilises > 1 else ''} déjà ouvert"
            f"{'s' if utilises > 1 else ''} avec ce code)."
        )
        code_a_desactiver.set_value("")
        afficher_liste()

    ui.button("Désactiver le code", on_click=desactiver).props("outline no-caps")

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

    afficher_liste()
