"""Barre de chargement de 0 à 100 % pour les traitements longs (étude de
marché, dossier Word).

Les traitements avancent par étapes connues (géocodage, ventes DVF, loyers,
cartes…) dont la durée varie : la barre saute au début de chaque étape puis
progresse doucement vers sa fin, sans jamais l'atteindre avant qu'elle soit
réellement terminée. Le pourcentage affiché reflète donc l'étape en cours."""
from __future__ import annotations

import time

from nicegui import ui

from . import theme


class Progression:
    def __init__(self) -> None:
        with ui.row().classes("w-full items-center gap-3 no-wrap") as self.conteneur:
            self.barre = ui.linear_progress(value=0, show_value=False).props("rounded color=primary size=8px").classes(
                "flex-1"
            )
            self.pourcentage = ui.label("0 %").classes(theme.HINT_CLASSES + " w-10 text-right")
        self.conteneur.visible = False
        self.valeur = 0.0
        self.cible = 0.0
        self.fin_affichee: float | None = None
        self.minuteur = ui.timer(0.2, self._avancer, active=False)

    def demarrer(self) -> None:
        self.valeur = self.cible = 0.0
        self.fin_affichee = None
        self._afficher()
        self.conteneur.visible = True
        self.minuteur.activate()

    def etape(self, debut: float, fin: float) -> None:
        """Début d'une étape : la barre va de `debut` vers `fin` (0 à 1)."""
        self.valeur = max(self.valeur, debut)
        self.cible = fin
        self._afficher()

    def terminer(self) -> None:
        """100 %, laissé visible un court instant puis masqué."""
        self.valeur = self.cible = 1.0
        self._afficher()
        self.fin_affichee = time.monotonic()

    def _avancer(self) -> None:
        if self.fin_affichee is not None:
            if time.monotonic() - self.fin_affichee > 0.6:
                self.conteneur.visible = False
                self.minuteur.deactivate()
            return
        if self.valeur < self.cible - 0.002:
            # Un douzième de l'écart restant à chaque pas : rapide au début
            # de l'étape, de plus en plus lent en approchant de sa fin.
            self.valeur += (self.cible - self.valeur) / 12
            self._afficher()

    def _afficher(self) -> None:
        self.barre.set_value(round(self.valeur, 3))
        self.pourcentage.set_text(f"{round(self.valeur * 100)} %")
