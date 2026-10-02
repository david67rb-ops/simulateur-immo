"""Estimations forfaitaires de la simulation express, quand l'utilisateur ne
connaît pas encore le montant exact : des ordres de grandeur, signalés comme
estimés dans l'interface, à remplacer par les montants réels (avis de taxe
foncière, relevé de charges de copropriété)."""
from __future__ import annotations

# Taxe foncière : environ un mois de loyer de marché ; sans loyer connu,
# environ 15 € par m² et par an.
TAXE_FONCIERE_MOIS_DE_LOYER = 1.0
TAXE_FONCIERE_EUR_M2_AN = 15
# Charges de copropriété non récupérables : environ 25 € par m² et par an
# (appartement ; aucune pour une maison individuelle).
COPROPRIETE_EUR_M2_AN = 25


def taxe_fonciere(loyer_mensuel_marche: float | None, surface_m2: float) -> float:
    if loyer_mensuel_marche:
        return round(loyer_mensuel_marche * TAXE_FONCIERE_MOIS_DE_LOYER, -1)
    return round(surface_m2 * TAXE_FONCIERE_EUR_M2_AN, -1)


def charges_copropriete(type_bien: str, surface_m2: float) -> float:
    if type_bien != "appartement":
        return 0.0
    return round(surface_m2 * COPROPRIETE_EUR_M2_AN, -1)
