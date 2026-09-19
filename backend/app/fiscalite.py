"""Fiscalité des revenus locatifs (France, barème 2026 sur revenus 2025).

Sources (voir README) : barème IR, seuils micro-foncier / micro-BIC,
taux de prélèvements sociaux, réforme LMNP (loi de finances 2025, art. 84).
Ce module fournit des ESTIMATIONS pédagogiques, pas un conseil fiscal
personnalisé.
"""
from __future__ import annotations

from dataclasses import dataclass, field

PS_TAUX_LOCATION_NUE = 0.172
PS_TAUX_LMNP = 0.186  # LFSS 2026 : CSG relevée à 10,6 % sur les revenus LMNP

PLAFOND_MICRO_FONCIER = 15_000
PLAFOND_MICRO_BIC_LMNP = 77_700
ABATTEMENT_MICRO_FONCIER = 0.30
ABATTEMENT_MICRO_BIC_LMNP = 0.50
PLAFOND_IMPUTATION_DEFICIT_FONCIER = 10_700

# Barème IR 2026 (revenus 2025), par part : (borne_haute, taux_marginal)
BAREME_IR_2026 = [
    (11_600, 0.0),
    (29_579, 0.11),
    (84_577, 0.30),
    (181_917, 0.41),
    (float("inf"), 0.45),
]


def impot_bareme(revenu_imposable_foyer: float, nb_parts: float = 1.0) -> float:
    """Impôt total du foyer selon le barème progressif (quotient familial)."""
    if nb_parts <= 0:
        nb_parts = 1.0
    revenu_par_part = max(revenu_imposable_foyer, 0.0) / nb_parts
    impot_par_part = 0.0
    borne_basse = 0.0
    for borne_haute, taux in BAREME_IR_2026:
        if revenu_par_part > borne_basse:
            tranche = min(revenu_par_part, borne_haute) - borne_basse
            impot_par_part += tranche * taux
            borne_basse = borne_haute
        else:
            break
    return impot_par_part * nb_parts


def impot_marginal_supplement(
    revenu_foyer_hors_bien: float, supplement: float, nb_parts: float = 1.0
) -> float:
    """Coût réel en IR d'un supplément de revenu (méthode précise, gère les
    changements de tranche), à comparer au raccourci TMI x supplément."""
    return impot_bareme(revenu_foyer_hors_bien + supplement, nb_parts) - impot_bareme(
        revenu_foyer_hors_bien, nb_parts
    )


@dataclass
class ResultatFiscalAnnuel:
    regime: str
    revenu_imposable: float
    impot_revenu: float
    prelevements_sociaux: float
    total_prelevements: float
    deficit_reportable_revenu_global: float = 0.0
    deficit_reportable_revenus_futurs: float = 0.0
    amortissement_reporte_stock: float = 0.0
    eligible: bool = True
    motif_inelig: str = ""


def micro_foncier(loyers_annuels_bruts: float, tmi: float) -> ResultatFiscalAnnuel:
    eligible = loyers_annuels_bruts <= PLAFOND_MICRO_FONCIER
    revenu_imposable = loyers_annuels_bruts * (1 - ABATTEMENT_MICRO_FONCIER)
    impot = revenu_imposable * tmi
    ps = revenu_imposable * PS_TAUX_LOCATION_NUE
    return ResultatFiscalAnnuel(
        regime="micro-foncier",
        revenu_imposable=revenu_imposable,
        impot_revenu=impot,
        prelevements_sociaux=ps,
        total_prelevements=impot + ps,
        eligible=eligible,
        motif_inelig="" if eligible else f"Loyers > {PLAFOND_MICRO_FONCIER} €/an",
    )


def foncier_reel(
    loyers_annuels_bruts: float,
    charges_deductibles_hors_interets: float,
    interets_emprunt: float,
    tmi: float,
    deficit_reporte_entrant: float = 0.0,
) -> ResultatFiscalAnnuel:
    charges_totales = charges_deductibles_hors_interets + interets_emprunt
    resultat = loyers_annuels_bruts - charges_totales - deficit_reporte_entrant
    if resultat >= 0:
        revenu_imposable = resultat
        impot = revenu_imposable * tmi
        ps = revenu_imposable * PS_TAUX_LOCATION_NUE
        return ResultatFiscalAnnuel(
            regime="foncier-reel",
            revenu_imposable=revenu_imposable,
            impot_revenu=impot,
            prelevements_sociaux=ps,
            total_prelevements=impot + ps,
        )
    # Déficit : la part liée aux intérêts n'est imputable que sur des
    # revenus fonciers futurs ; le reste est imputable sur le revenu global
    # dans la limite de 10 700 €/an, l'économie d'impôt correspondante est
    # calculée au TMI.
    deficit_total = -resultat
    deficit_hors_interets = max(
        0.0, loyers_annuels_bruts - charges_deductibles_hors_interets
    )
    deficit_hors_interets = min(deficit_hors_interets, deficit_total)
    deficit_imputable_global = min(deficit_hors_interets, PLAFOND_IMPUTATION_DEFICIT_FONCIER)
    deficit_report_futur = deficit_total - deficit_imputable_global
    economie_impot = deficit_imputable_global * tmi
    return ResultatFiscalAnnuel(
        regime="foncier-reel",
        revenu_imposable=0.0,
        impot_revenu=-economie_impot,
        prelevements_sociaux=0.0,
        total_prelevements=-economie_impot,
        deficit_reportable_revenus_futurs=deficit_report_futur,
    )


def micro_bic_lmnp(recettes_annuelles: float, tmi: float) -> ResultatFiscalAnnuel:
    eligible = recettes_annuelles <= PLAFOND_MICRO_BIC_LMNP
    revenu_imposable = recettes_annuelles * (1 - ABATTEMENT_MICRO_BIC_LMNP)
    impot = revenu_imposable * tmi
    ps = revenu_imposable * PS_TAUX_LMNP
    return ResultatFiscalAnnuel(
        regime="micro-BIC (LMNP)",
        revenu_imposable=revenu_imposable,
        impot_revenu=impot,
        prelevements_sociaux=ps,
        total_prelevements=impot + ps,
        eligible=eligible,
        motif_inelig="" if eligible else f"Recettes > {PLAFOND_MICRO_BIC_LMNP} €/an",
    )


def lmnp_reel(
    recettes_annuelles: float,
    charges_deductibles: float,
    amortissement_disponible_annee: float,
    tmi: float,
    deficit_bic_reporte_entrant: float = 0.0,
    amortissement_reporte_entrant: float = 0.0,
) -> ResultatFiscalAnnuel:
    resultat_avant_amortissement = (
        recettes_annuelles - charges_deductibles - deficit_bic_reporte_entrant
    )
    if resultat_avant_amortissement <= 0:
        deficit_bic = -resultat_avant_amortissement
        amortissement_stock = amortissement_reporte_entrant + amortissement_disponible_annee
        return ResultatFiscalAnnuel(
            regime="LMNP-reel",
            revenu_imposable=0.0,
            impot_revenu=0.0,
            prelevements_sociaux=0.0,
            total_prelevements=0.0,
            deficit_reportable_revenus_futurs=deficit_bic,
            amortissement_reporte_stock=amortissement_stock,
        )
    amortissement_disponible_total = (
        amortissement_reporte_entrant + amortissement_disponible_annee
    )
    amortissement_utilise = min(amortissement_disponible_total, resultat_avant_amortissement)
    amortissement_reporte_sortant = amortissement_disponible_total - amortissement_utilise
    revenu_imposable = resultat_avant_amortissement - amortissement_utilise
    impot = revenu_imposable * tmi
    ps = revenu_imposable * PS_TAUX_LMNP
    return ResultatFiscalAnnuel(
        regime="LMNP-reel",
        revenu_imposable=revenu_imposable,
        impot_revenu=impot,
        prelevements_sociaux=ps,
        total_prelevements=impot + ps,
        amortissement_reporte_stock=amortissement_reporte_sortant,
    )
