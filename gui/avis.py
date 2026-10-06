"""Formulaire d'avis des testeurs de la bêta, proposé après le téléchargement
du dossier. L'avis part depuis la messagerie du testeur (lien mailto avec
l'objet et le texte préremplis) : rien n'est enregistré sur le site, et
l'adresse e-mail de l'expéditeur rend l'avis vérifiable (« avis vérifié »
sur la page d'accueil, avec l'accord explicite de publication)."""
from __future__ import annotations

from urllib.parse import quote

from nicegui import app, ui

from . import statistiques, theme
from .pages_legales import CONTACT_EMAIL

ISSUES_BANQUE = (
    "Pas encore de rendez-vous",
    "Rendez-vous prévu",
    "Prêt accordé",
    "Prêt refusé",
    "Projet abandonné",
)
LONGUEUR_MAX = 800  # par réponse : un lien mailto trop long est tronqué par certaines messageries


def _texte(valeur: str | None) -> str:
    texte = (valeur or "").strip()
    return texte[:LONGUEUR_MAX] if texte else "(pas de réponse)"


def mailto_avis(note: int, utile: str, manque: str, banque: str, publier: bool, prenom: str, ville: str) -> str:
    lignes = [
        f"Note : {note}/5" if note else "Note : (pas de note)",
        "",
        f"Ce qui m'a le plus servi : {_texte(utile)}",
        "",
        f"Ce qui manque ou m'a gêné : {_texte(manque)}",
        "",
        f"Ma banque : {banque}",
        "",
    ]
    if publier:
        signature = ", ".join(x for x in (prenom.strip(), ville.strip()) if x) or "(prénom et ville à compléter)"
        lignes.append(f"J'accepte que cet avis soit publié sur credaura.fr, signé : {signature}.")
    else:
        lignes.append("Je ne souhaite pas que cet avis soit publié.")
    sujet = "Credaura · Mon avis de testeur"
    return f"mailto:{CONTACT_EMAIL}?subject={quote(sujet)}&body={quote(chr(10).join(lignes))}"


def construire_carte() -> ui.element | None:
    """Carte « Ton avis », masquée jusqu'au premier téléchargement du dossier.
    Rien dans l'application de bureau (pas de messagerie du navigateur)."""
    if app.native.main_window:
        return None
    etat = {"note": 0}
    carte = ui.column().classes("w-full gap-3 rounded-xl p-4 mt-3").style(
        "background: var(--c-fond-calcule); border: 1px solid var(--c-bord-calcule)"
    )
    carte.visible = False
    with carte:
        with ui.row().classes("items-center gap-2 no-wrap"):
            ui.icon("rate_review", size="26px").classes("text-[color:var(--c-laiton)]")
            ui.label("Ton avis de testeur").classes("text-lg font-semibold titre-sora")
        ui.label(
            "Pendant la bêta, le dossier est offert : en échange, ton avis m'aide à améliorer Credaura. "
            "Quatre questions, deux minutes. Il part depuis ta messagerie : rien n'est enregistré sur le site."
        ).classes("text-sm")

        ui.label("Le dossier t'a-t-il été utile ?").classes("text-sm font-semibold mt-1")
        etoiles = ui.element("q-rating").props("max=5 size=32px color=accent icon=star_border icon-selected=star")
        etoiles._props["model-value"] = 0

        def noter(e) -> None:
            etat["note"] = int(e.args or 0)
            etoiles._props["model-value"] = etat["note"]
            etoiles.update()

        etoiles.on("update:model-value", noter)

        utile = ui.textarea("Ce qui t'a le plus servi").props("outlined autogrow").classes("w-full")
        manque = ui.textarea("Ce qui manque ou t'a gêné").props("outlined autogrow").classes("w-full")
        banque = ui.select(list(ISSUES_BANQUE), value=ISSUES_BANQUE[0], label="Et avec ta banque ?").props(
            "outlined"
        ).classes("w-full")

        publier = ui.checkbox("J'accepte que mon avis soit publié sur credaura.fr, avec mon prénom et ma ville")
        with ui.row().classes("w-full gap-3 no-wrap").bind_visibility_from(publier, "value"):
            prenom = ui.input("Prénom").props("outlined dense").classes("flex-1 min-w-0")
            ville = ui.input("Ville").props("outlined dense").classes("flex-1 min-w-0")

        def envoyer() -> None:
            statistiques.evenement("avis-envoye", "Avis de testeur")
            ui.navigate.to(
                mailto_avis(
                    etat["note"],
                    utile.value,
                    manque.value,
                    banque.value,
                    publier.value,
                    prenom.value or "",
                    ville.value or "",
                )
            )
            ui.notify("Ta messagerie s'ouvre avec ton avis : il ne reste qu'à l'envoyer. Merci !", type="positive")

        ui.button("Envoyer mon avis", icon="send", on_click=envoyer).props(
            "unelevated no-caps color=accent text-color=white"
        ).classes("self-start")
        ui.label(f"Ou écris directement à {CONTACT_EMAIL}.").classes(theme.HINT_CLASSES)
    return carte
