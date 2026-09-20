"""Moteur de simulation : cash-flows, fiscalité par régime/structure,
revente et TRI. Estimations pédagogiques, cf. limites dans le README."""
from __future__ import annotations

from dataclasses import dataclass, field

from . import fiscalite as fisc
from .finance import irr, tableau_amortissement_annuel
from .schemas import DiffereType, RegimeLocation, StructureJuridique, SimulationInput, TypeProjet

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


def _charges_hors_credit(inp: SimulationInput, loyers_bruts: float, is_meublee: bool) -> float:
    frais_gestion = loyers_bruts * inp.frais_gestion_pct_loyers
    frais_plateforme = (
        loyers_bruts * inp.frais_plateforme_pct
        if inp.type_projet == TypeProjet.location_courte_duree
        else 0.0
    )
    frais_menage = (
        inp.frais_menage_annuel if inp.type_projet == TypeProjet.location_courte_duree else 0.0
    )
    return (
        inp.charges_copropriete_annuelles
        + inp.taxe_fonciere_annuelle
        + inp.assurance_pno_annuelle
        + inp.entretien_annuel
        + frais_gestion
        + frais_plateforme
        + frais_menage
        + (inp.frais_comptable_annuel if is_meublee else 0.0)
    )


def _simuler_location(inp: SimulationInput) -> dict:
    """location_longue_duree ET location_courte_duree (même moteur pluriannuel ;
    seuls les paramètres de revenus/charges/fiscalité micro-BIC diffèrent)."""
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
        differe_mois=inp.differe_duree_mois if inp.differe_type != DiffereType.aucun else 0,
        differe_total=inp.differe_type == DiffereType.total,
    )
    loan_by_year = {ly.annee: ly for ly in loan_schedule}

    base_amortissable_bati = (inp.prix_achat + inp.frais_notaire) * (1 - inp.part_terrain_pct)

    is_lcd = inp.type_projet == TypeProjet.location_courte_duree
    # Une LCD est fiscalement un meublé ; en SCI à l'IR, le meublé habituel
    # est en principe requalifié à l'IS (cf. avertissement renvoyé au frontend).
    is_meublee = is_lcd or inp.regime_location == RegimeLocation.meublee
    is_sci_is = inp.structure_juridique == StructureJuridique.sci_is

    non_classe = is_lcd and not inp.meuble_tourisme_classe
    if is_lcd:
        nom_micro_bic = (
            "micro-BIC (meublé tourisme non classé)"
            if non_classe
            else "micro-BIC (meublé tourisme classé)"
        )
    else:
        nom_micro_bic = "micro-BIC (LMNP)"

    if is_sci_is:
        regimes_a_calculer = ["SCI-IS"]
    elif is_meublee:
        regimes_a_calculer = [nom_micro_bic, "LMNP-reel"]
    else:
        regimes_a_calculer = ["micro-foncier", "foncier-reel"]

    deficit_foncier_report = 0.0
    deficit_bic_report = 0.0
    amortissement_report = 0.0
    amortissement_bati_travaux_deduit_cumule = 0.0
    deficit_is_report = 0.0
    tresorerie_sci_cumulee = 0.0

    annees: list[AnneeResultat] = []
    cashflows_par_regime: dict[str, list[float]] = {r: [-apport_reel] for r in regimes_a_calculer}

    n = inp.duree_projection_annees
    for annee in range(1, n + 1):
        loyers_bruts = (
            inp.loyer_mensuel_hors_charges
            * 12
            * (1 - inp.vacance_locative_pct)
            * (1 + inp.taux_revalorisation_loyers_annuel) ** (annee - 1)
        )
        charges_hors_credit = _charges_hors_credit(inp, loyers_bruts, is_meublee)
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

        amortissement_dispo = (
            _amortissement_annee(base_amortissable_bati, inp.duree_amortissement_bati_annees, annee)
            + _amortissement_annee(inp.montant_travaux, inp.duree_amortissement_travaux_annees, annee)
            + _amortissement_annee(inp.montant_mobilier, inp.duree_amortissement_mobilier_annees, annee)
        )

        if is_sci_is:
            charges_deductibles = charges_hors_credit + interets
            r_is = fisc.sci_is(loyers_bruts, charges_deductibles, amortissement_dispo, deficit_is_report)
            deficit_is_report = r_is.deficit_reportable
            resultat_fiscal = fisc.ResultatFiscalAnnuel(
                regime="SCI-IS",
                revenu_imposable=max(r_is.resultat_fiscal, 0.0),
                impot_revenu=r_is.impot_societes,
                prelevements_sociaux=0.0,
                total_prelevements=r_is.impot_societes,
                deficit_reportable_revenus_futurs=r_is.deficit_reportable,
            )
            resultat_annee.fiscal["SCI-IS"] = resultat_fiscal
            cashflow_sci = cashflow_avant_impot - r_is.impot_societes
            resultat_annee.cashflow_apres_impot["SCI-IS"] = cashflow_sci
            if cashflow_sci < 0:
                # Trésorerie SCI insuffisante : l'associé doit injecter la
                # différence (compte courant d'associé), coût réel cette
                # année-là — symétrique au cas personne physique/SCI IR.
                cashflows_par_regime["SCI-IS"].append(cashflow_sci)
            else:
                tresorerie_sci_cumulee += cashflow_sci
                cashflows_par_regime["SCI-IS"].append(0.0)  # profit conservé en trésorerie SCI
        elif not is_meublee:
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
            r_micro = fisc.micro_bic_lmnp(
                loyers_bruts,
                inp.taux_marginal_imposition,
                meuble_tourisme_non_classe=non_classe,
            )
            resultat_annee.fiscal[nom_micro_bic] = r_micro
            resultat_annee.cashflow_apres_impot[nom_micro_bic] = (
                cashflow_avant_impot - r_micro.total_prelevements
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
            dotation_bati_travaux_annee = _amortissement_annee(
                base_amortissable_bati, inp.duree_amortissement_bati_annees, annee
            ) + _amortissement_annee(
                inp.montant_travaux, inp.duree_amortissement_travaux_annees, annee
            )
            dotation_totale_annee = dotation_bati_travaux_annee + _amortissement_annee(
                inp.montant_mobilier, inp.duree_amortissement_mobilier_annees, annee
            )
            part_bati_travaux = (
                dotation_bati_travaux_annee / dotation_totale_annee if dotation_totale_annee > 0 else 0.0
            )
            amortissement_bati_travaux_deduit_cumule += (
                amortissement_utilise_cette_annee * part_bati_travaux
            )
            amortissement_report = r_reel.amortissement_reporte_stock
            resultat_annee.fiscal["LMNP-reel"] = r_reel
            resultat_annee.cashflow_apres_impot["LMNP-reel"] = (
                cashflow_avant_impot - r_reel.total_prelevements
            )

        if not is_sci_is:
            for regime in regimes_a_calculer:
                cashflows_par_regime[regime].append(resultat_annee.cashflow_apres_impot[regime])

        annees.append(resultat_annee)

    # --- Revente en fin de projection ---
    valeur_revente = inp.prix_achat * (1 + inp.taux_revalorisation_bien_annuel) ** n
    crd_final = loan_by_year[n].capital_restant_du if n in loan_by_year else 0.0
    prix_acquisition_base = inp.prix_achat + inp.frais_notaire + inp.montant_travaux

    reventes: dict[str, ResultatRevente] = {}

    if is_sci_is:
        amortissements_cumules = (
            min(base_amortissable_bati, base_amortissable_bati / inp.duree_amortissement_bati_annees * n)
            + min(inp.montant_travaux, inp.montant_travaux / inp.duree_amortissement_travaux_annees * n if inp.montant_travaux else 0)
            + min(inp.montant_mobilier, inp.montant_mobilier / inp.duree_amortissement_mobilier_annees * n if inp.montant_mobilier else 0)
        )
        valeur_nette_comptable = prix_acquisition_base + inp.montant_mobilier - amortissements_cumules
        plus_value_pro = max(valeur_revente - valeur_nette_comptable, 0.0)

        dernier_resultat_fiscal = annees[-1].fiscal["SCI-IS"].revenu_imposable
        is_sans_pv = fisc.impot_sur_les_societes(dernier_resultat_fiscal)
        is_avec_pv = fisc.impot_sur_les_societes(dernier_resultat_fiscal + plus_value_pro)
        impot_is_sur_pv = is_avec_pv - is_sans_pv

        net_vendeur_sci = valeur_revente - crd_final - impot_is_sur_pv
        tresorerie_totale = tresorerie_sci_cumulee + net_vendeur_sci
        profit_distribuable = max(tresorerie_totale - apport_reel, 0.0)
        net_apres_distribution = tresorerie_totale - profit_distribuable * fisc.FLAT_TAX_DISTRIBUTION

        reventes["SCI-IS"] = ResultatRevente(
            valeur_revente=valeur_revente,
            capital_restant_du=crd_final,
            prix_acquisition_retenu=valeur_nette_comptable,
            amortissements_reintegres=amortissements_cumules,
            plus_value_brute=plus_value_pro,
            plus_value_imposable_ir=plus_value_pro,
            plus_value_imposable_ps=0.0,
            impot_plus_value_ir=impot_is_sur_pv,
            impot_plus_value_ps=0.0,
            surtaxe=0.0,
            net_vendeur=net_vendeur_sci,
        )
        cashflows_par_regime["SCI-IS"][-1] = net_apres_distribution
    else:
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

    avertissements = []
    if is_lcd and inp.structure_juridique == StructureJuridique.sci_ir:
        avertissements.append(
            "Une SCI à l'IR pratiquant la location meublée de façon habituelle est en "
            "principe requalifiée à l'IS par l'administration fiscale (sauf si les recettes "
            "meublées restent accessoires, < 10 % des recettes totales)."
        )
    differe_actif = inp.differe_type != DiffereType.aucun and inp.differe_duree_mois > 0
    if differe_actif:
        libelle = "total (rien n'est payé, intérêts capitalisés)" if inp.differe_type == DiffereType.total else "partiel (intérêts seuls payés)"
        avertissements.append(
            f"Différé de crédit {libelle} pendant {inp.differe_duree_mois} mois : la mensualité "
            "affiche ci-dessous est celle du régime de croisière (après différé), pas celle de "
            "la première année."
        )

    return {
        "type_projet": inp.type_projet.value,
        "cout_total_acquisition": cout_total_acquisition,
        "montant_emprunte": montant_emprunte,
        "apport_reel": apport_reel,
        "mensualite_credit_hors_assurance": (
            max((ly.mensualite_hors_assurance for ly in loan_schedule), default=0.0) / 12
            if differe_actif
            else (loan_schedule[0].mensualite_hors_assurance / 12 if loan_schedule else 0.0)
        ),
        "mensualite_annee1_hors_assurance": loan_schedule[0].mensualite_hors_assurance / 12
        if loan_schedule
        else 0.0,
        "differe_actif": differe_actif,
        "rendement_brut": rendement_brut,
        "rendement_net_charges": rendement_net_charges,
        "annees": annees,
        "reventes": reventes,
        "tri_par_regime": tri_par_regime,
        "cashflows_par_regime": cashflows_par_regime,
        "tresorerie_sci_cumulee": tresorerie_sci_cumulee if is_sci_is else None,
        "avertissements": avertissements,
    }


@dataclass
class ResultatAchatRevente:
    cout_total_acquisition: float
    montant_emprunte: float
    apport_reel: float
    frais_portage_interets: float
    frais_portage_taxe_fonciere: float
    frais_portage_assurance: float
    frais_portage_total: float
    prix_revente: float
    frais_agence_revente: float
    produit_net_vente: float
    marge_brute_avant_impot: float
    regime_fiscal: str
    base_imposable: float
    impot_total: float
    marge_nette: float
    cash_final_investisseur: float
    rentabilite_operation_pct: float
    tri_annualise: float | None


def _simuler_achat_revente(inp: SimulationInput) -> dict:
    cout_total_acquisition = inp.prix_achat + inp.frais_notaire + inp.montant_travaux
    montant_emprunte = max(cout_total_acquisition - inp.apport, 0.0)
    apport_reel = cout_total_acquisition - montant_emprunte

    duree_annees = inp.duree_portage_mois / 12
    frais_portage_interets = montant_emprunte * inp.taux_credit_annuel * duree_annees
    frais_portage_taxe_fonciere = inp.taxe_fonciere_annuelle * duree_annees
    frais_portage_assurance = inp.assurance_pno_annuelle * duree_annees
    frais_portage_total = frais_portage_interets + frais_portage_taxe_fonciere + frais_portage_assurance

    prix_revente = inp.prix_revente_vise or (
        inp.prix_achat * (1 + inp.taux_revalorisation_bien_annuel) ** duree_annees
    )
    frais_agence_revente = prix_revente * inp.frais_agence_revente_pct
    produit_net_vente = prix_revente - frais_agence_revente

    marge_brute_avant_impot = produit_net_vente - cout_total_acquisition - frais_portage_total

    professionnel = (
        inp.marchand_de_biens_professionnel
        or inp.structure_juridique == StructureJuridique.sci_is
    )

    if professionnel:
        regime_fiscal = "IS (marchand de biens / SCI à l'IS)"
        base_imposable = max(marge_brute_avant_impot, 0.0)
        impot_total = fisc.impot_sur_les_societes(base_imposable)
        if marge_brute_avant_impot < 0:
            impot_total = 0.0
    else:
        regime_fiscal = "Plus-value immobilière des particuliers (occasionnel)"
        # Frais financiers de portage non déductibles de la plus-value des
        # particuliers (contrairement à un résultat professionnel/IS).
        base_imposable = max(produit_net_vente - cout_total_acquisition, 0.0)
        annees_detention = max(int(duree_annees), 0)
        abat_ir = abattement_ir_plus_value(annees_detention)
        abat_ps = abattement_ps_plus_value(annees_detention)
        pv_ir = base_imposable * (1 - abat_ir)
        pv_ps = base_imposable * (1 - abat_ps)
        impot_total = pv_ir * TAUX_IR_PLUS_VALUE + pv_ps * TAUX_PS_PLUS_VALUE + surtaxe_plus_value(pv_ir)

    marge_nette = marge_brute_avant_impot - impot_total
    cash_final_investisseur = apport_reel + marge_nette
    rentabilite_operation_pct = marge_nette / apport_reel if apport_reel > 0 else marge_nette / cout_total_acquisition

    tri_annualise = None
    if apport_reel > 0 and duree_annees > 0:
        rendement_periode = marge_nette / apport_reel
        base = 1 + rendement_periode
        if base > 0:
            tri_annualise = base ** (1 / duree_annees) - 1

    resultat = ResultatAchatRevente(
        cout_total_acquisition=cout_total_acquisition,
        montant_emprunte=montant_emprunte,
        apport_reel=apport_reel,
        frais_portage_interets=frais_portage_interets,
        frais_portage_taxe_fonciere=frais_portage_taxe_fonciere,
        frais_portage_assurance=frais_portage_assurance,
        frais_portage_total=frais_portage_total,
        prix_revente=prix_revente,
        frais_agence_revente=frais_agence_revente,
        produit_net_vente=produit_net_vente,
        marge_brute_avant_impot=marge_brute_avant_impot,
        regime_fiscal=regime_fiscal,
        base_imposable=base_imposable,
        impot_total=impot_total,
        marge_nette=marge_nette,
        cash_final_investisseur=cash_final_investisseur,
        rentabilite_operation_pct=rentabilite_operation_pct,
        tri_annualise=tri_annualise,
    )
    return {"type_projet": inp.type_projet.value, "achat_revente": resultat, "avertissements": []}


def simuler(inp: SimulationInput) -> dict:
    if inp.type_projet == TypeProjet.achat_revente:
        return _simuler_achat_revente(inp)
    return _simuler_location(inp)
