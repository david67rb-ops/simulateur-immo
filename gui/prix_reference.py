"""Étape Marché, adresse sans ventes publiées (Alsace-Moselle, Mayotte : hors
base DVF) : l'utilisateur recopie le prix au m² qu'il lit sur MeilleursAgents
ou ailleurs. Credaura ne va jamais chercher ce chiffre lui-même : seuls des
liens à ouvrir sont proposés, et le chiffre reste dans le projet de
l'utilisateur."""
from __future__ import annotations

from collections.abc import Callable

from nicegui import ui

from app import analyse

from . import theme

TYPES_BIEN = {"appartement": "un appartement", "maison": "une maison"}
INTRODUCTION = (
    "En Alsace-Moselle, les ventes immobilières ne sont pas publiées (régime du Livre foncier) : pas de "
    "comparables automatiques ici. Relève le prix au m² sur MeilleursAgents et recopie-le ci-dessous. "
    "Le verdict et le dossier s'en serviront."
)
MAYOTTE = (
    "À Mayotte, les ventes immobilières ne sont pas publiées dans la base nationale DVF : pas de comparables "
    "automatiques ici. Relève le prix au m² sur MeilleursAgents ou auprès d'une agence et recopie-le ci-dessous. "
    "Le verdict et le dossier s'en serviront."
)


class BlocPrixReference:
    """Saisie du repère de prix. `etat` : l'état de l'étude de marché (champs
    prix_ref_*) ; `sur_changement` : appelé à chaque modification ;
    `liens` : [(nom du site, fonction qui ouvre sa page)], dans l'ordre."""

    def __init__(self, etat: dict, sur_changement: Callable[[], None], liens: list[tuple[str, Callable[[], None]]]) -> None:
        self.etat = etat
        self.sur_changement = sur_changement
        with ui.column().classes("w-full gap-2") as self.conteneur:
            ui.label("Prix de référence du marché").classes(theme.SUBSECTION_TITLE_CLASSES)
            self.introduction = ui.label(INTRODUCTION).classes("text-sm")
            with ui.column().classes("gap-1 text-sm"):
                ui.label("1. Ouvre MeilleursAgents et tape l'adresse du bien.")
                self.etape_type = ui.label("")
                ui.label("3. Indique si le prix vaut pour l'adresse ou s'il s'agit de la moyenne de la commune.")
            with ui.row().classes("items-center gap-1"):
                for nom, ouvrir in liens:
                    ui.button(nom, icon="open_in_new", on_click=ouvrir).props("flat dense no-caps")

            with ui.row().classes(theme.GRID_CLASSES):
                self.moyen = theme.ChampMontant("Prix moyen au m²", suffixe="€/m²", nullable=True).props(
                    "outlined dense"
                ).classes("w-full")
                self.bas = theme.ChampMontant("Bas (facultatif)", suffixe="€/m²", nullable=True).props(
                    "outlined dense"
                ).classes("w-full")
                self.haut = theme.ChampMontant(
                    "Haut (facultatif)", suffixe="€/m²", nullable=True
                ).props("outlined dense").classes("w-full")
                self.source = ui.select(analyse.SOURCES_PRIX_REF, label="Source", value=etat["prix_ref_source"]).props(
                    "outlined dense"
                ).classes("w-full")
                self.date = ui.input("Date du relevé", value=etat["prix_ref_date"]).props(
                    "outlined dense type=date"
                ).classes("w-full")
            self.niveau = ui.toggle(
                {"adresse": "Prix à l'adresse", "commune": "Moyenne de la commune"}, value=etat["prix_ref_niveau"]
            ).props("no-caps unelevated toggle-color=primary")
            self.message = ui.label("").classes("text-sm")
            self.message.visible = False
            ui.label("Credaura ne va pas chercher ce chiffre lui-même. Il reste dans ton projet, chez toi.").classes(
                theme.HINT_CLASSES
            )
        self.conteneur.visible = False

        # Écriture dans l'état à chaque saisie, sans renvoyer le champ au
        # navigateur (un renvoi pendant la frappe effacerait des lettres).
        for champ, cle in ((self.moyen, "prix_ref_m2"), (self.bas, "prix_ref_bas_m2"), (self.haut, "prix_ref_haut_m2")):
            champ.on_value_change(lambda e, c=champ, k=cle: self._modifier(k, c.lire(e.value)))
        self.source.on_value_change(lambda e: self._modifier("prix_ref_source", e.value))
        self.date.on_value_change(lambda e: self._modifier("prix_ref_date", e.value or ""))
        self.niveau.on_value_change(lambda e: self._modifier("prix_ref_niveau", e.value))

    def _modifier(self, cle: str, valeur) -> None:
        if self.etat.get(cle) == valeur:
            return
        self.etat[cle] = valeur
        self._valider()
        self.sur_changement()

    def _valider(self) -> None:
        erreurs, avertissements = analyse.valider_prix_reference(
            self.etat.get("prix_ref_m2"),
            self.etat.get("prix_ref_bas_m2"),
            self.etat.get("prix_ref_haut_m2"),
            self.etat.get("prix_ref_date"),
        )
        messages = erreurs or avertissements
        self.message.visible = bool(messages)
        self.message.set_text(" ".join(("⚠️ " if not erreurs else "") + m for m in messages))
        self.message.style(f"color: {theme.NEGATIVE if erreurs else theme.ACCENT}")

    def afficher(self, visible: bool, type_bien: str, introduction_mayotte: bool = False) -> None:
        """Après l'étude de marché : visible seulement pour une adresse sans
        ventes publiées. Les champs reprennent l'état (projet rouvert)."""
        self.conteneur.visible = visible
        if not visible:
            return
        self.introduction.set_text(MAYOTTE if introduction_mayotte else INTRODUCTION)
        self.etape_type.set_text(
            f"2. Recopie le prix moyen au m² pour {TYPES_BIEN.get(type_bien, 'ce type de bien')}, "
            "et la fourchette si elle est affichée."
        )
        for champ, cle in ((self.moyen, "prix_ref_m2"), (self.bas, "prix_ref_bas_m2"), (self.haut, "prix_ref_haut_m2")):
            champ.set_value(champ.ecrire(self.etat.get(cle)))
        self.source.set_value(self.etat.get("prix_ref_source"))
        self.date.set_value(self.etat.get("prix_ref_date"))
        self.niveau.set_value(self.etat.get("prix_ref_niveau"))
        self._valider()
