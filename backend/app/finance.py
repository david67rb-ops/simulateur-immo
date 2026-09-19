"""Calculs financiers génériques : emprunt, cash-flows, TRI/VAN."""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class LoanYear:
    annee: int
    interets: float
    capital_rembourse: float
    capital_restant_du: float
    mensualite_totale: float


def annuite_mensuelle(capital: float, taux_annuel: float, duree_mois: int) -> float:
    """Mensualité constante hors assurance (amortissement classique)."""
    if capital <= 0 or duree_mois <= 0:
        return 0.0
    taux_mensuel = taux_annuel / 12
    if taux_mensuel == 0:
        return capital / duree_mois
    return capital * taux_mensuel / (1 - (1 + taux_mensuel) ** (-duree_mois))


def tableau_amortissement_annuel(
    capital: float,
    taux_annuel: float,
    duree_annees: int,
    assurance_taux_annuel: float = 0.0,
) -> list[LoanYear]:
    """Tableau d'amortissement agrégé par année (intérêts, capital, CRD)."""
    duree_mois = duree_annees * 12
    mensualite = annuite_mensuelle(capital, taux_annuel, duree_mois)
    taux_mensuel = taux_annuel / 12
    assurance_mensuelle = capital * assurance_taux_annuel / 12

    crd = capital
    resultats: list[LoanYear] = []
    for annee in range(1, duree_annees + 1):
        interets_annee = 0.0
        capital_annee = 0.0
        for _ in range(12):
            if crd <= 0:
                break
            interet_mois = crd * taux_mensuel
            capital_mois = min(mensualite - interet_mois, crd)
            crd -= capital_mois
            interets_annee += interet_mois
            capital_annee += capital_mois
        resultats.append(
            LoanYear(
                annee=annee,
                interets=interets_annee,
                capital_rembourse=capital_annee,
                capital_restant_du=max(crd, 0.0),
                mensualite_totale=(mensualite + assurance_mensuelle) * 12
                if annee <= duree_annees
                else 0.0,
            )
        )
    return resultats


def irr(cashflows: list[float], guess: float = 0.08) -> float | None:
    """TRI annuel par la méthode de Newton, avec repli en bisection.

    cashflows[0] est le flux à t=0 (généralement négatif).
    """

    def van(rate: float) -> float:
        return sum(cf / (1 + rate) ** i for i, cf in enumerate(cashflows))

    def van_prime(rate: float) -> float:
        return sum(
            -i * cf / (1 + rate) ** (i + 1) for i, cf in enumerate(cashflows) if i > 0
        )

    rate = guess
    for _ in range(100):
        f = van(rate)
        fp = van_prime(rate)
        if abs(fp) < 1e-9:
            break
        new_rate = rate - f / fp
        if abs(new_rate - rate) < 1e-7:
            return new_rate
        rate = new_rate
        if rate <= -0.99:
            rate = -0.5

    lo, hi = -0.9, 5.0
    f_lo, f_hi = van(lo), van(hi)
    if f_lo * f_hi > 0:
        return None
    for _ in range(200):
        mid = (lo + hi) / 2
        f_mid = van(mid)
        if abs(f_mid) < 1e-6:
            return mid
        if f_lo * f_mid < 0:
            hi = mid
        else:
            lo, f_lo = mid, f_mid
    return (lo + hi) / 2


def van(cashflows: list[float], taux_actualisation: float) -> float:
    return sum(cf / (1 + taux_actualisation) ** i for i, cf in enumerate(cashflows))
