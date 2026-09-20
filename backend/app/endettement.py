"""Taux d'endettement du foyer pour un dossier de financement bancaire.

Reprend la pratique standard des banques françaises : les loyers prévisionnels
du projet ne sont retenus qu'à hauteur de 70 % (pondération de prudence sur
la vacance/les impayés). Seuil HCSF de référence : 35 % (avec une marge de
dérogation bancaire possible, non modélisée ici). Le « reste à vivre », autre
critère bancaire courant, n'est pas calculé (dépend du nombre de personnes au
foyer et de barèmes internes propres à chaque banque) — limite documentée.
"""
from __future__ import annotations

from dataclasses import dataclass

PONDERATION_LOYERS = 0.70
SEUIL_ENDETTEMENT_HCSF = 0.35


@dataclass
class ResultatEndettement:
    revenus_consideres_mensuels: float
    mensualites_totales_mensuelles: float
    taux_endettement: float
    seuil_hcsf: float
    depasse_seuil: bool
    marge_avant_seuil: float  # mensualité supplémentaire supportable avant d'atteindre le seuil


def calculer_taux_endettement(
    revenus_nets_mensuels_foyer: float,
    autres_revenus_mensuels: float,
    mensualites_credits_existants: float,
    mensualite_projet_mensuelle: float,
    loyers_mensuels_projet: float,
) -> ResultatEndettement:
    revenus_consideres = (
        revenus_nets_mensuels_foyer
        + autres_revenus_mensuels
        + loyers_mensuels_projet * PONDERATION_LOYERS
    )
    mensualites_totales = mensualites_credits_existants + mensualite_projet_mensuelle
    taux = mensualites_totales / revenus_consideres if revenus_consideres > 0 else float("inf")
    marge = max(revenus_consideres * SEUIL_ENDETTEMENT_HCSF - mensualites_totales, 0.0)
    return ResultatEndettement(
        revenus_consideres_mensuels=revenus_consideres,
        mensualites_totales_mensuelles=mensualites_totales,
        taux_endettement=taux,
        seuil_hcsf=SEUIL_ENDETTEMENT_HCSF,
        depasse_seuil=taux > SEUIL_ENDETTEMENT_HCSF,
        marge_avant_seuil=marge,
    )
