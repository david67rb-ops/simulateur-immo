"""Calcul automatique des frais de notaire (« frais d'acquisition »).

Barème réglementé des émoluments (arrêté du 28/02/2020, tranches HT),
+ droits de mutation à titre onéreux (DMTO), + contribution de sécurité
immobilière (CSI), + débours forfaitaires. Estimation standard, les
départements ayant conservé le taux réduit de DMTO (Indre, Mayotte...)
ne sont pas pris en compte (hypothèse simplificatrice).
"""
from __future__ import annotations

TVA = 0.20
CSI_TAUX = 0.001
CSI_MINIMUM = 15.0
DEBOURS_FORFAIT = 900.0

DMTO_ANCIEN = 0.0580665
DMTO_NEUF = 0.00715  # taxe de publicité foncière réduite (le prix supporte déjà la TVA)

BAREME_EMOLUMENTS = [
    (6_500, 0.03870),
    (17_000, 0.01596),
    (60_000, 0.01064),
    (float("inf"), 0.00799),
]


def _emoluments_ht(prix: float) -> float:
    total = 0.0
    borne_basse = 0.0
    for borne_haute, taux in BAREME_EMOLUMENTS:
        if prix > borne_basse:
            tranche = min(prix, borne_haute) - borne_basse
            total += tranche * taux
            borne_basse = borne_haute
        else:
            break
    return total


def calculer_frais_notaire(prix_achat: float, neuf: bool = False) -> dict:
    emoluments_ht = _emoluments_ht(prix_achat)
    emoluments_ttc = emoluments_ht * (1 + TVA)
    csi = max(prix_achat * CSI_TAUX, CSI_MINIMUM)
    droits_mutation = prix_achat * (DMTO_NEUF if neuf else DMTO_ANCIEN)
    total = emoluments_ttc + csi + droits_mutation + DEBOURS_FORFAIT
    return {
        "emoluments_notaire_ttc": round(emoluments_ttc, 2),
        "droits_mutation": round(droits_mutation, 2),
        "contribution_securite_immobiliere": round(csi, 2),
        "debours_forfait": DEBOURS_FORFAIT,
        "total": round(total, 2),
        "taux_effectif": round(total / prix_achat, 4) if prix_achat else 0.0,
    }
