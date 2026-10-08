"""Page « Nous contacter » : un motif par bouton, qui ouvre la messagerie du
visiteur avec l'objet déjà rempli. Pas de formulaire sur le serveur : aucun
message ne transite par le site ni n'y est conservé (promesse « rien n'est
conservé »)."""
from __future__ import annotations

from urllib.parse import quote

from nicegui import ui

from . import theme
from .accueil import RESEAUX
from .pages_legales import CONTACT_EMAIL, _gabarit, _pied

MOTIFS = (
    ("calculate", "Une question sur le simulateur", "Un calcul, une hypothèse, un chiffre que tu ne comprends pas.", "Question sur le simulateur"),
    ("description", "Mon dossier de financement", "Son contenu, sa mise en forme, ce que la banque en a pensé.", "Mon dossier de financement"),
    ("rate_review", "Donner mon avis de testeur", "Ce qui t'a servi, ce qui manque, et la réponse de ta banque.", "Mon avis de testeur"),
    ("bug_report", "Signaler un problème", "Dis-moi sur quel appareil et quel navigateur, et ce qui s'est passé.", "Problème sur le site"),
    ("handshake", "Professionnels et partenariats", "Courtiers, conseillers en patrimoine, créateurs de contenu.", "Partenariat"),
    ("campaign", "Presse", "Une interview, des chiffres sur le marché immobilier local.", "Presse"),
)

CSS = """
.motif-contact { display: flex; gap: 14px; align-items: flex-start; padding: 16px 18px; border-radius: 14px;
  border: 1px solid var(--c-filet); text-decoration: none; color: inherit; transition: border-color 0.15s, background 0.15s; }
.motif-contact:hover { border-color: var(--c-laiton); background: rgba(168, 130, 59, 0.06); }
.motif-contact .titre { font-weight: 600; font-size: 1.02rem; }
.motif-contact .texte { font-size: 0.9rem; opacity: 0.75; }
"""


def _mailto(objet: str) -> str:
    return f"mailto:{CONTACT_EMAIL}?subject={quote('Credaura · ' + objet)}"


@ui.page("/contact", title="Nous contacter · Credaura")
def page_contact() -> None:
    colonne = _gabarit("Nous contacter", date=False)
    ui.add_css(CSS)
    with colonne:
        ui.label(
            "Une question sur le simulateur, ton dossier ou un partenariat ? Écris-moi : je lis chaque message "
            "et je te réponds personnellement."
        ).classes("text-base mt-2")
        ui.html(
            'Avant d\'écrire, jette un œil à la <a href="/#faq" class="lien-exemple font-semibold">FAQ</a> : '
            "les questions les plus fréquentes y ont déjà leur réponse."
        ).classes("text-sm " + theme.HINT_CLASSES.replace("text-xs", ""))

        ui.label("Choisis ton sujet").classes(theme.SUBSECTION_TITLE_CLASSES + " mt-4")
        with ui.column().classes("w-full gap-2"):
            for icone, titre, texte, objet in MOTIFS:
                with ui.element("a").props(f'href="{_mailto(objet)}"').classes("motif-contact w-full"):
                    ui.icon(icone, size="26px").classes("text-[color:var(--c-laiton)] shrink-0 mt-0.5")
                    with ui.column().classes("gap-0.5"):
                        ui.label(titre).classes("titre")
                        ui.label(texte).classes("texte")
        ui.label("Chaque sujet ouvre ta messagerie, avec l'objet déjà rempli.").classes(theme.HINT_CLASSES)

        ui.label("Ou écris directement").classes(theme.SUBSECTION_TITLE_CLASSES + " mt-4")
        # L'adresse n'est pas affichée : un bouton ouvre la messagerie, et
        # « Copier l'adresse » sert quand aucune messagerie n'est configurée
        # (fréquent sur PC, où le lien mailto n'ouvre alors rien).
        with ui.row().classes("items-center gap-3 flex-wrap"):
            ui.button("Envoie-nous un mail", icon="mail").props(
                f'unelevated no-caps href="mailto:{CONTACT_EMAIL}"'
            ).classes("px-4")

            def copier() -> None:
                ui.clipboard.write(CONTACT_EMAIL)
                ui.notify("Adresse e-mail copiée", type="positive")

            ui.button("Copier l'adresse", icon="content_copy", on_click=copier).props("flat no-caps")

        with ui.element("div").classes("w-full rounded-xl p-4 mt-4").style(
            "background: var(--c-fond-calcule); border: 1px solid var(--c-bord-calcule)"
        ):
            ui.label("Bon à savoir").classes("font-semibold mb-1")
            ui.label(
                "N'envoie pas de pièces justificatives (bulletins de salaire, avis d'imposition, relevés de compte) : "
                "je n'en ai pas besoin pour te répondre, et elles n'ont rien à faire dans une messagerie."
            ).classes("text-sm")
            ui.label(
                "Credaura n'est ni une banque ni un courtier : je ne peux pas te mettre en relation avec un "
                "établissement ni intervenir dans ta demande de prêt."
            ).classes("text-sm mt-1")

        ui.label("Sur les réseaux").classes(theme.SUBSECTION_TITLE_CLASSES + " mt-4")
        with ui.row().classes("gap-x-5 gap-y-1 flex-wrap"):
            for adresse, nom in RESEAUX:
                ui.html(f'<a href="{adresse}" target="_blank" rel="noopener" class="lien-exemple">{nom}</a>')
    _pied(colonne)
