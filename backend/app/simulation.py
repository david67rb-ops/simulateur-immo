"""Moteur de simulation pluriannuel : cash-flows, fiscalité par régime,
revente et TRI. Estimations pédagogiques, cf. limites dans le README."""
from __future__ import annotations

from dataclasses import dataclass, field

from . import fiscalite as fisc
from .finance import irr, tableau_amortissement_annuel
from .schemas import RegimeLocation, SimulationInput

TAUX_IR_PLUS_VALUE = 0.19
TAUX_PS_PLUS_VALUE = 0.172


def abattement_ir_plus_value(annees_detention: int) -> float:
    if annees_detention <= 5:
        return 0.0
    if annees_detention < 22:
        return min(1.0, (annees_detention - 5) * 0.06)
    return 1.0


def abattement_ps_plus_value(annees_detention: int) -> float:
    if annees_detention <= 5:
        return 0.0
    if annees_detention < 22:
        return min(1.0, (annees_detention - 5) * 0.0165)
    if annees_detention < 30:
        return min(1.0, 21 * 0.0165 + (annees_detention - 21) * 0.09)
    return 1.0


@dataclass
class AnneeResultat:
    annee: int
    loyers_bruts: float
    charges_hors_credit: float
    interets_credit: float
    capital_rembourse: float
    mensualite_totale_credit: float
    cashflow_avant_impot: float
    fiscal: dict[str, fisc.ResultatFiscalAnnuel] = field(default_factory=dict)
    cashflow_apres_impot: dict[str, float] = field(default_factory=dict)


@dataclass
class ResultatRevente:
    valeur_revente: float
    capital_restant_du: float
    prix_acquisition_retenu: float
    amortissements_reintegres: float
    plus_value_brute: float
    plus_value_imposable_ir: float
    plus_value_imposable_ps: float
    impot_plus_value_ir: float
    impot_plus_value_ps: float
    surtaxe: float
    net_vendeur: float


def _amortissement_annee(montant: float, duree: int, annee: int) -> float:
    if duree <= 0 or annee > duree:
        return 0.0
    return montant / duree


def simuler(inp: SimulationInput) -> dict:
    cout_total_acquisition = (
        inp.prix_achat + inp.frais_notaire + inp.montant_travaux + inp.montant_mobilier
    )
    montant_emprunte = max(cout_total_acquisition - inp.apport, 0.0)
    apport_reel = cout_total_acquisition - montant_emprunte

    loan_schedule = tableau_amortissement_annuel(
        montant_emprunte,
        inp.taux_credit_annuel,
        inp.duree_credit_annees,
        inp.taux_assurance_emprunteur,
    )
    loan_by_year = {ly.annee: ly for ly in loan_schedule}

    # Amortissements LMNP réel (linéaires, hors terrain pour le bâti)
    base_amortissable_bati = (inp.prix_achat + inp.frais_notaire) * (1 - inp.part_terrain_pct)

    regimes_a_calculer: list[str]
    if inp.regime_location == RegimeLocation.nue:
        regimes_a_calculer = ["micro-foncier", "foncier-reel"]
    else:
        regimes_a_calculer = ["micro-BIC (LMNP)", "LMNP-reel"]

    deficit_foncier_report = 0.0
    deficit_bic_report = 0.0
    amortissement_report = 0.0
    amortissement_bati_travaux_deduit_cumule = 0.0

    annees: list[AnneeResultat] = []
    cashflows_par_regime: dict[str, list[float]] = {r: [-apport_reel] for r in regimes_a_calculer}

    for annee in range(1, inp.duree_projection_annees + 1):
        loyers_bruts = (
            inp.loyer_mensuel_hors_charges
            * 12
            * (1 - inp.vacance_locative_pct)
            * (1 + inp.taux_revalorisation_loyers_annuel) ** (annee - 1)
        )
        frais_gestion = loyers_bruts * inp.frais_gestion_pct_loyers
        charges_hors_credit = (
            inp.charges_copropriete_annuelles
            + inp.taxe_fonciere_annuelle
            + inp.assurance_pno_annuelle
            + inp.entretien_annuel
            + frais_gestion
            + (inp.frais_comptable_annuel if inp.regime_location == RegimeLocation.meublee else 0.0)
        )
        ly = loan_by_year.get(annee)
        interets = ly.interets if ly else 0.0
        capital_rembourse = ly.capital_rembourse if ly else 0.0
        mensualite_totale = ly.mensualite_totale if ly else 0.0

        cashflow_avant_impot = loyers_bruts - charges_hors_credit - mensualite_totale

        resultat_annee = AnneeResultat(
            annee=annee,
            loyers_bruts=loyers_bruts,
            charges_hors_credit=charges_hors_credit,
            interets_credit=interets,
            capital_rembourse=capital_rembourse,
            mensualite_totale_credit=mensualite_totale,
            cashflow_avant_impot=cashflow_avant_impot,
        )

        if inp.regime_location == RegimeLocation.nue:
            r_micro = fisc.micro_foncier(loyers_bruts, inp.taux_marginal_imposition)
            resultat_annee.fiscal["micro-foncier"] = r_micro
            resultat_annee.cashflow_apres_impot["micro-foncier"] = (
                cashflow_avant_impot - r_micro.total_prelevements
            )

            r_reel = fisc.foncier_reel(
                loyers_bruts,
                charges_hors_credit,
                interets,
                inp.taux_marginal_imposition,
                deficit_foncier_report,
            )
            deficit_foncier_report = r_reel.deficit_reportable_revenus_futurs
            resultat_annee.fiscal["foncier-reel"] = r_reel
            resultat_annee.cashflow_apres_impot["foncier-reel"] = (
                cashflow_avant_impot - r_reel.total_prelevements
            )
        else:
            r_micro = fisc.micro_bic_lmnp(loyers_bruts, inp.taux_marginal_imposition)
            resultat_annee.fiscal["micro-BIC (LMNP)"] = r_micro
            resultat_annee.cashflow_apres_impot["micro-BIC (LMNP)"] = (
                cashflow_avant_impot - r_micro.total_prelevements
            )

            amortissement_dispo = (
                _amortissement_annee(base_amortissable_bati, inp.duree_amortissement_bati_annees, annee)
                + _amortissement_annee(inp.montant_travaux, inp.duree_amortissement_travaux_annees, annee)
                + _amortissement_annee(inp.montant_mobilier, inp.duree_amortissement_mobilier_annees, annee)
            )
            charges_deductibles_reel = charges_hors_credit + interets
            r_reel = fisc.lmnp_reel(
                loyers_bruts,
                charges_deductibles_reel,
                amortissement_dispo,
                inp.taux_marginal_imposition,
                deficit_bic_report,
                amortissement_report,
            )
            deficit_bic_report = r_reel.deficit_reportable_revenus_futurs
            amortissement_utilise_cette_annee = (
                amortissement_report + amortissement_dispo - r_reel.amortissement_reporte_stock
            )
            # part bâti+travaux (hors mobilier) réintégrée à la revente
            dotation_bati_travaux_annee = _amortissement_annee(
                base_amortissable_bati, inp.duree_amortissement_bati_annees, annee
            ) + _amortissement_annee(
                inp.montant_travaux, inp.duree_amortissement_travaux_annees, annee
            )
            dotation_totale_annee = dotation_bati_travaux_annee + _amortissement_annee(
                inp.montant_mobilier, inp.duree_amortissement_mobilier_annees, annee
            )
            if dotation_totale_annee > 0:
                part_bati_travaux = dotation_bati_travaux_annee / dotation_totale_annee
            else:
                part_bati_travaux = 0.0
            amortissement_bati_travaux_deduit_cumule += (
                amortissement_utilise_cette_annee * part_bati_travaux
            )
            amortissement_report = r_reel.amortissement_reporte_stock
            resultat_annee.fiscal["LMNP-reel"] = r_reel
            resultat_annee.cashflow_apres_impot["LMNP-reel"] = (
                cashflow_avant_impot - r_reel.total_prelevements
            )

        for regime in regimes_a_calculer:
            cashflows_par_regime[regime].append(resultat_annee.cashflow_apres_impot[regime])

        annees.append(resultat_annee)

    # --- Revente en fin de projection ---
    n = inp.duree_projection_annees
    valeur_revente = inp.prix_achat * (1 + inp.taux_revalorisation_bien_annuel) ** n
    crd_final = loan_by_year[n].capital_restant_du if n in loan_by_year else 0.0

    reventes: dict[str, ResultatRevente] = {}
    prix_acquisition_base = inp.prix_achat + inp.frais_notaire + inp.montant_travaux

    for regime in regimes_a_calculer:
        reintegration = (
            amortissement_bati_travaux_deduit_cumule if regime == "LMNP-reel" else 0.0
        )
        prix_acquisition_retenu = prix_acquisition_base - reintegration
        plus_value_brute = max(valeur_revente - prix_acquisition_retenu, 0.0)
        abat_ir = abattement_ir_plus_value(n)
        abat_ps = abattement_ps_plus_value(n)
        pv_imposable_ir = plus_value_brute * (1 - abat_ir)
        pv_imposable_ps = plus_value_brute * (1 - abat_ps)
        impot_ir = pv_imposable_ir * TAUX_IR_PLUS_VALUE
        impot_ps = pv_imposable_ps * TAUX_PS_PLUS_VALUE
        surtaxe = surtaxe_plus_value(pv_imposable_ir)
        net_vendeur = valeur_revente - crd_final - impot_ir - impot_ps - surtaxe

        reventes[regime] = ResultatRevente(
            valeur_revente=valeur_revente,
            capital_restant_du=crd_final,
            prix_acquisition_retenu=prix_acquisition_retenu,
            amortissements_reintegres=reintegration,
            plus_value_brute=plus_value_brute,
            plus_value_imposable_ir=pv_imposable_ir,
            plus_value_imposable_ps=pv_imposable_ps,
            impot_plus_value_ir=impot_ir,
            impot_plus_value_ps=impot_ps,
            surtaxe=surtaxe,
            net_vendeur=net_vendeur,
        )
        cashflows_par_regime[regime][-1] += net_vendeur

    tri_par_regime = {r: irr(cfs) for r, cfs in cashflows_par_regime.items()}

    rendement_brut = (inp.loyer_mensuel_hors_charges * 12) / cout_total_acquisition
    charges_an1 = annees[0].charges_hors_credit
    rendement_net_charges = (
        (inp.loyer_mensuel_hors_charges * 12 - charges_an1) / cout_total_acquisition
    )

    return {
        "cout_total_acquisition": cout_total_acquisition,
        "montant_emprunte": montant_emprunte,
        "apport_reel": apport_reel,
        "mensualite_credit_hors_assurance": loan_schedule[0].mensualite_totale / 12
        if loan_schedule
        else 0.0,
        "rendement_brut": rendement_brut,
        "rendement_net_charges": rendement_net_charges,
        "annees": annees,
        "reventes": reventes,
        "tri_par_regime": tri_par_regime,
        "cashflows_par_regime": cashflows_par_regime,
    }


def surtaxe_plus_value(pv_imposable_ir: float) -> float:
    """Barème officiel 2024+ de la surtaxe sur les plus-values > 50 000 €."""
    pv = pv_imposable_ir
    if pv <= 50_000:
        return 0.0
    if pv <= 60_000:
        return pv * 0.02 - (60_000 - pv) * 0.01
    if pv <= 100_000:
        return pv * 0.02
    if pv <= 110_000:
        return pv * 0.03 - (110_000 - pv) * 0.01
    if pv <= 150_000:
        return pv * 0.03
    if pv <= 160_000:
        return pv * 0.04 - (160_000 - pv) * 0.01
    if pv <= 200_000:
        return pv * 0.04
    if pv <= 210_000:
        return pv * 0.05 - (210_000 - pv) * 0.01
    if pv <= 250_000:
        return pv * 0.05
    if pv <= 260_000:
        return pv * 0.06 - (260_000 - pv) * 0.01
    return pv * 0.06
