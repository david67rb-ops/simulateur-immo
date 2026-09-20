"""Calculs financiers génériques : emprunt, cash-flows, TRI/VAN."""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class LoanYear:
    annee: int
    interets: float
    capital_rembourse: float
    capital_restant_du: float
    mensualite_hors_assurance: float
    assurance_annuelle: float
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
    differe_mois: int = 0,
    differe_total: bool = False,
) -> list[LoanYear]:
    """Tableau d'amortissement agrégé par année (intérêts, capital, CRD).

    Différé partiel : seuls les intérêts sont payés pendant `differe_mois`,
    le capital reste inchangé. Différé total : rien n'est payé, les intérêts
    courus sont capitalisés (ajoutés au capital restant dû) ; l'amortissement
    classique démarre ensuite sur ce capital augmenté, sur la durée restante.
    L'assurance emprunteur (sur capital initial) continue à courir pendant le
    différé, comme en pratique bancaire.
    """
    duree_mois = duree_annees * 12
    if duree_mois <= 1:
        differe_mois = 0
    else:
        differe_mois = max(0, min(differe_mois, duree_mois - 1))
    taux_mensuel = taux_annuel / 12
    assurance_mensuelle = capital * assurance_taux_annuel / 12

    crd = capital
    mensualite_post_differe: float | None = None
    resultats: list[LoanYear] = []

    for annee in range(1, duree_annees + 1):
        interets_annee = 0.0
        capital_annee = 0.0
        mensualite_annee = 0.0
        for mois_dans_annee in range(12):
            mois_absolu = (annee - 1) * 12 + mois_dans_annee
            if crd <= 0:
                break
            interet_mois = crd * taux_mensuel
            if mois_absolu < differe_mois:
                if differe_total:
                    crd += interet_mois  # intérêts capitalisés, non payés
                    capital_mois = 0.0
                    mensualite_mois = 0.0
                    interet_paye = 0.0
                else:
                    capital_mois = 0.0
                    mensualite_mois = interet_mois
                    interet_paye = interet_mois
            else:
                if mensualite_post_differe is None:
                    mensualite_post_differe = annuite_mensuelle(
                        crd, taux_annuel, duree_mois - differe_mois
                    )
                interet_paye = interet_mois
                capital_mois = min(mensualite_post_differe - interet_mois, crd)
                crd -= capital_mois
                mensualite_mois = mensualite_post_differe
            interets_annee += interet_paye
            capital_annee += capital_mois
            mensualite_annee += mensualite_mois
        resultats.append(
            LoanYear(
                annee=annee,
                interets=interets_annee,
                capital_rembourse=capital_annee,
                capital_restant_du=max(crd, 0.0),
                mensualite_hors_assurance=mensualite_annee,
                assurance_annuelle=assurance_mensuelle * 12,
                mensualite_totale=mensualite_annee + assurance_mensuelle * 12,
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
