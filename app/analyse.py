"""Aides à la décision construites sur le moteur de simulation : prix d'achat
maximum, scénarios de stress et verdict synthétique."""
from __future__ import annotations

from datetime import date

from .notaire import calculer_frais_notaire
from .saisonnalite import PERSONNALISE
from .schemas import SimulationInput, TypeProjet
from .simulation import simuler

SEUIL_EFFORT_MODERE = 150  # €/mois
SEUIL_MARGE_CONFORTABLE = 0.10  # marge nette / coût total, achat-revente


def _avec_prix(inp: SimulationInput, prix: float) -> SimulationInput:
    # Les frais de notaire suivent le prix, en conservant une éventuelle
    # correction manuelle (même rapport au barème).
    auto_actuel = calculer_frais_notaire(inp.prix_achat, inp.bien_neuf)["total"]
    ratio = inp.frais_notaire / auto_actuel if auto_actuel else 1.0
    notaire = calculer_frais_notaire(prix, inp.bien_neuf)["total"] * ratio
    return inp.model_copy(update={"prix_achat": prix, "frais_notaire": notaire})


def _indicateur_objectif(inp: SimulationInput) -> float:
    r = simuler(inp)
    if inp.type_projet == TypeProjet.achat_revente:
        return r["achat_revente"].marge_nette
    return r["cashflow_mensuel"]


def prix_achat_maximum(inp: SimulationInput) -> dict | None:
    """Prix d'achat le plus élevé qui respecte l'objectif (cash-flow mensuel en
    location, marge nette en achat-revente). None si le calcul n'a pas de sens :
    location sans crédit (le prix pèse peu sur le cash-flow) ou achat-revente
    sans prix de revente visé (la revente dépendrait alors du prix d'achat)."""
    if inp.type_projet == TypeProjet.achat_revente:
        if not inp.prix_revente_vise:
            return None
        objectif = inp.objectif_marge_nette
    else:
        if not inp.avec_credit:
            return None
        objectif = inp.objectif_cashflow_mensuel

    bas, haut = 1_000.0, inp.prix_achat * 4
    if _indicateur_objectif(_avec_prix(inp, bas)) < objectif:
        return {"statut": "inatteignable", "objectif": objectif, "prix_max": None}
    if _indicateur_objectif(_avec_prix(inp, haut)) >= objectif:
        return {"statut": "non_limitant", "objectif": objectif, "prix_max": haut}
    for _ in range(40):
        milieu = (bas + haut) / 2
        if _indicateur_objectif(_avec_prix(inp, milieu)) >= objectif:
            bas = milieu
        else:
            haut = milieu
    return {"statut": "ok", "objectif": objectif, "prix_max": round(bas / 100) * 100}


def scenarios_stress(inp: SimulationInput) -> list[dict]:
    """Rejoue la simulation avec des hypothèses dégradées, une à la fois."""
    scenarios: list[tuple[str, dict]] = [("Hypothèses de base", {})]
    if inp.type_projet == TypeProjet.achat_revente:
        prix_revente = inp.prix_revente_vise or simuler(inp)["achat_revente"].prix_revente
        scenarios += [
            ("Prix de revente −10 %", {"prix_revente_vise": prix_revente * 0.9}),
            ("Portage +3 mois", {"duree_portage_mois": min(inp.duree_portage_mois + 3, 60)}),
        ]
        if inp.montant_travaux > 0:
            scenarios.append(("Travaux +20 %", {"montant_travaux": inp.montant_travaux * 1.2}))
    else:
        if inp.avec_credit:
            scenarios.append(("Taux du crédit +1 point", {"taux_credit_annuel": min(inp.taux_credit_annuel + 0.01, 0.2)}))
        if inp.type_projet == TypeProjet.location_courte_duree and inp.profil_saisonnalite == PERSONNALISE:
            # Profil personnalisé : ce sont les 12 valeurs mensuelles qui comptent.
            scenarios += [
                (
                    "Occupation −10 points",
                    {"occupation_mensuelle": [max(o - 0.10, 0.0) for o in inp.occupation_mensuelle or []]},
                ),
                ("Prix à la nuitée −10 %", {"prix_nuitee_mensuel": [p * 0.9 for p in inp.prix_nuitee_mensuel or []]}),
            ]
        elif inp.type_projet == TypeProjet.location_courte_duree:
            scenarios += [
                ("Occupation −10 points", {"taux_occupation_pct": max(inp.taux_occupation_pct - 0.10, 0.0)}),
                ("Prix à la nuitée −10 %", {"prix_nuitee": inp.prix_nuitee * 0.9}),
            ]
        else:
            scenarios += [
                ("Vacance +1 mois par an", {"vacance_locative_pct": min(inp.vacance_locative_pct + 1 / 12, 0.9)}),
                ("Loyer −10 %", {"loyer_mensuel_hors_charges": inp.loyer_mensuel_hors_charges * 0.9}),
            ]

    lignes = []
    for libelle, modifs in scenarios:
        r = simuler(inp.model_copy(update=modifs))
        if inp.type_projet == TypeProjet.achat_revente:
            ar = r["achat_revente"]
            lignes.append(
                {"scenario": libelle, "marge_nette": ar.marge_nette, "rentabilite": ar.rentabilite_operation_pct}
            )
        else:
            regime = r["meilleur_regime"]
            lignes.append(
                {
                    "scenario": libelle,
                    "cashflow_mensuel": r["cashflow_mensuel"],
                    "tri": r["tri_par_regime"].get(regime),
                    "enrichissement": r["enrichissement_par_regime"][regime],
                }
            )
    return lignes


def verdict(inp: SimulationInput, resultat: dict) -> dict:
    """Niveau (vert/orange/rouge) et phrases de synthèse. `resultat` est la
    sortie de simuler() passée par clean_result (dictionnaires)."""
    if inp.type_projet == TypeProjet.achat_revente:
        ar = resultat["achat_revente"]
        ratio = ar["marge_nette"] / ar["cout_total_acquisition"] if ar["cout_total_acquisition"] else 0.0
        if ratio >= SEUIL_MARGE_CONFORTABLE:
            niveau, titre = "vert", "Opération rentable"
        elif ratio >= 0:
            niveau, titre = "orange", "Marge faible"
        else:
            niveau, titre = "rouge", "Opération à perte"
        detail = (
            f"Marge nette de {_eur(ar['marge_nette'])}, soit {_pct(ratio)} du coût total de l'opération "
            f"(repère : au moins {_pct(SEUIL_MARGE_CONFORTABLE, 0)} pour absorber les imprévus)."
        )
        return {"niveau": niveau, "titre": titre, "detail": detail}

    cf = resultat["cashflow_mensuel"]
    regime = resultat["meilleur_regime"]
    enrichissement = resultat["enrichissement_par_regime"][regime]
    n = inp.duree_projection_annees
    if enrichissement < 0:
        niveau, titre = "rouge", f"Opération perdante sur {n} ans"
    elif cf >= 0:
        niveau, titre = "vert", f"Autofinancé : +{_eur(cf)}/mois de cash-flow net"
    elif -cf <= SEUIL_EFFORT_MODERE:
        niveau, titre = "orange", f"Effort d'épargne modéré : {_eur(-cf)}/mois"
    else:
        niveau, titre = "rouge", f"Effort d'épargne important : {_eur(-cf)}/mois"
    detail = (
        f"Enrichissement net estimé sur {n} ans : {_eur(enrichissement)} "
        "(cash-flows après impôts et revente nette, apport déduit)."
    )
    return {"niveau": niveau, "titre": titre, "detail": detail}


TITRES_VERDICT_GLOBAL = {"vert": "Projet solide", "orange": "Projet à renforcer", "rouge": "Projet à revoir"}
SEUIL_APPORT_CONFORTABLE = 0.10  # apport / coût total
MARGE_ENDETTEMENT_CONFORTABLE = 0.03  # points sous le seuil HCSF


# Écart du prix au m² du projet à la référence du marché (médiane DVF ou
# repère saisi à l'adresse) : vert sous SEUIL_PRIX_VERT au-dessus, orange
# sous SEUIL_PRIX_ORANGE, rouge au-delà.
SEUIL_PRIX_VERT = 0.03
SEUIL_PRIX_ORANGE = 0.10


def prix_projet_m2(prix_achat: float | None, surface_m2: float | None) -> float | None:
    """Prix au m² du projet, tel qu'il est comparé au marché (ventes DVF ou
    repère de prix saisi) : prix d'achat seul, hors frais et travaux."""
    if not prix_achat or not surface_m2:
        return None
    return prix_achat / surface_m2


def niveau_ecart_au_marche(ecart: float) -> str:
    """Prix au m² du projet face à la médiane des ventes du quartier."""
    return "vert" if ecart < SEUIL_PRIX_VERT else ("orange" if ecart < SEUIL_PRIX_ORANGE else "rouge")


# ---------------------------------------------------------------------------
# Repère de prix saisi par l'utilisateur, là où les ventes ne sont pas
# publiées (Alsace-Moselle, Mayotte : hors base DVF). Credaura ne va jamais
# chercher ce chiffre lui-même : l'utilisateur le recopie (MeilleursAgents…).
# ---------------------------------------------------------------------------
PRIX_REF_MIN_M2 = 300
PRIX_REF_MAX_M2 = 20_000
PRIX_REF_ANCIENNETE_MAX_JOURS = 183  # au-delà de 6 mois : à mettre à jour
CHAMPS_PRIX_REF = (
    "prix_ref_m2",
    "prix_ref_bas_m2",
    "prix_ref_haut_m2",
    "prix_ref_niveau",
    "prix_ref_source",
    "prix_ref_date",
)
NIVEAUX_PRIX_REF = {"adresse": "à l'adresse du bien", "commune": "moyenne de la commune"}
SOURCES_PRIX_REF = {
    "meilleursagents": "MeilleursAgents",
    "seloger": "SeLoger",
    "agence": "Estimation d'agence",
    "autre": "Autre",
}
# Dans une phrase : « Repère de prix : 2 600 €/m², estimation MeilleursAgents… »
SOURCES_PRIX_REF_PHRASE = {
    "meilleursagents": "estimation MeilleursAgents",
    "seloger": "estimation SeLoger",
    "agence": "estimation d'agence",
    "autre": "source indiquée par l'emprunteur",
}
MESSAGE_REPERE_COMMUNAL = (
    "Repère communal : trop large pour conclure à un prix excessif. Vérifie avec une estimation d'agence."
)
RAISON_SANS_REPERE = "Saisis un prix de référence pour évaluer ce critère."


def _date_releve(valeur) -> date | None:
    if isinstance(valeur, date):
        return valeur
    try:
        return date.fromisoformat(str(valeur or "")[:10])
    except ValueError:
        return None


def valider_prix_reference(
    moyen: float | None,
    bas: float | None = None,
    haut: float | None = None,
    date_releve=None,
    aujourd_hui: date | None = None,
) -> tuple[list[str], list[str]]:
    """(erreurs, avertissements) du repère de prix saisi. Une erreur rend le
    repère inutilisable (critère Prix non évalué) ; un avertissement non."""
    aujourd_hui = aujourd_hui or date.today()
    erreurs: list[str] = []
    avertissements: list[str] = []
    for valeur in (moyen, bas, haut):
        if valeur is None:
            continue
        if valeur > PRIX_REF_MAX_M2:
            erreurs.append("Ce chiffre ressemble à un prix total, pas à un prix au m².")
            break
        if valeur < PRIX_REF_MIN_M2:
            erreurs.append("Ce prix au m² paraît trop bas : vérifie la saisie.")
            break
    if moyen is not None and not erreurs:
        if (bas is not None and bas > moyen) or (haut is not None and haut < moyen) or (
            bas is not None and haut is not None and bas > haut
        ):
            erreurs.append("La fourchette doit encadrer le prix moyen : bas ≤ moyen ≤ haut.")
    jour = _date_releve(date_releve)
    if date_releve and jour is None:
        erreurs.append("Date du relevé invalide.")
    elif jour is not None:
        if jour > aujourd_hui:
            erreurs.append("La date du relevé ne peut pas être dans le futur.")
        elif (aujourd_hui - jour).days > PRIX_REF_ANCIENNETE_MAX_JOURS:
            avertissements.append("Relevé de plus de 6 mois : mets-le à jour avant d'envoyer le dossier à la banque.")
    return erreurs, avertissements


def repere_prix(etat: dict, aujourd_hui: date | None = None) -> dict | None:
    """Le repère saisi (champs prix_ref_* de l'étude de marché), s'il est
    renseigné et valide ; None sinon."""
    moyen = etat.get("prix_ref_m2")
    if not moyen:
        return None
    erreurs, _ = valider_prix_reference(
        moyen, etat.get("prix_ref_bas_m2"), etat.get("prix_ref_haut_m2"), etat.get("prix_ref_date"), aujourd_hui
    )
    if erreurs:
        return None
    jour = _date_releve(etat.get("prix_ref_date")) or (aujourd_hui or date.today())
    return {
        "prix_m2": float(moyen),
        "bas_m2": float(etat["prix_ref_bas_m2"]) if etat.get("prix_ref_bas_m2") else None,
        "haut_m2": float(etat["prix_ref_haut_m2"]) if etat.get("prix_ref_haut_m2") else None,
        "niveau": etat.get("prix_ref_niveau") if etat.get("prix_ref_niveau") in NIVEAUX_PRIX_REF else "adresse",
        "source": etat.get("prix_ref_source") if etat.get("prix_ref_source") in SOURCES_PRIX_REF else "autre",
        "date": jour.isoformat(),
    }


def ecart_au_repere(prix_m2_projet: float, prix_ref_m2: float) -> float:
    """(prix du projet au m² − repère) ÷ repère : 0,05 = 5 % au-dessus."""
    return (prix_m2_projet - prix_ref_m2) / prix_ref_m2


def niveau_ecart_repere(ecart: float, niveau_ref: str) -> str:
    """À l'adresse : mêmes seuils que les ventes DVF. Repère communal :
    vert ou orange, jamais rouge (trop large pour conclure)."""
    if niveau_ref == "commune":
        return "vert" if ecart < SEUIL_PRIX_VERT else "orange"
    return niveau_ecart_au_marche(ecart)


def libelle_repere(repere: dict) -> str:
    """« Estimation MeilleursAgents à l'adresse, relevée le 15/10/2026 »."""
    source = SOURCES_PRIX_REF_PHRASE[repere["source"]]
    niveau = "à l'adresse" if repere["niveau"] == "adresse" else "moyenne de la commune"
    jour = date.fromisoformat(repere["date"]).strftime("%d/%m/%Y")
    return f"{source[0].upper()}{source[1:]}, {niveau}, relevée le {jour}"


def pct_une_decimale(v: float) -> str:
    """5,8 % (une décimale, virgule française, espace insécable)."""
    return f"{abs(v) * 100:.1f}\u00a0%".replace(".", ",")


def verdict_global(
    inp: SimulationInput,
    resultat: dict,
    ecart_marche: float | None = None,
    endettement=None,
    raison_prix: str = "Lance l'étude de marché pour le comparer au quartier",
    niveau_repere: str | None = None,
) -> dict:
    """Verdict en trois niveaux (solide, à renforcer, à revoir) sur les trois
    questions du banquier : la rentabilité, le prix face au marché, le
    financement. Un critère pas encore évalué (étude de marché non lancée…)
    reste « neutre » et ne compte pas dans le niveau.

    `ecart_marche` : écart du prix au m² à la médiane du quartier (0,05 = 5 %
    au-dessus). `endettement` : ResultatEndettement si le profil de
    l'emprunteur est renseigné. `resultat` : sortie de clean_result.
    `niveau_repere` : « adresse » ou « commune » quand l'écart est mesuré à un
    repère de prix saisi (zone sans DVF) plutôt qu'aux ventes du quartier."""
    is_ar = inp.type_projet == TypeProjet.achat_revente
    rentabilite = verdict(inp, resultat)
    criteres = [{"nom": "Marge" if is_ar else "Rentabilité", "niveau": rentabilite["niveau"], "texte": rentabilite["titre"]}]

    if ecart_marche is None:
        criteres.append({"nom": "Prix", "niveau": "neutre", "texte": raison_prix})
    elif niveau_repere:
        nom_repere = "repère communal" if niveau_repere == "commune" else "repère de prix"
        if abs(ecart_marche) < 0.005:
            texte = f"Au niveau du {nom_repere}"
        else:
            sens = "au-dessus du" if ecart_marche > 0 else "sous le"
            texte = f"{_pct(abs(ecart_marche), 0)} {sens} {nom_repere}"
        niveau_prix = niveau_ecart_repere(ecart_marche, niveau_repere)
        if niveau_repere == "commune" and niveau_prix != "vert":
            texte += ". " + MESSAGE_REPERE_COMMUNAL
        criteres.append({"nom": "Prix", "niveau": niveau_prix, "texte": texte})
    else:
        if abs(ecart_marche) < 0.005:
            texte = "Dans la médiane du quartier"
        else:
            sens = "au-dessus de" if ecart_marche > 0 else "sous"
            texte = f"{_pct(abs(ecart_marche), 0)} {sens} la médiane du quartier"
        criteres.append({"nom": "Prix", "niveau": niveau_ecart_au_marche(ecart_marche), "texte": texte})

    source = resultat["achat_revente"] if is_ar else resultat
    cout_total = source.get("cout_total_acquisition", 0.0)
    if source.get("montant_emprunte", 0.0) <= 0:
        criteres.append({"nom": "Financement", "niveau": "neutre", "texte": "Sans crédit, en fonds propres"})
    elif endettement is not None:
        taux, seuil = endettement.taux_endettement, endettement.seuil_hcsf
        if endettement.depasse_seuil:
            niveau, texte = "rouge", f"Endettement de {_pct(taux)}, au-delà du seuil de {_pct(seuil, 0)}"
        elif seuil - taux < MARGE_ENDETTEMENT_CONFORTABLE:
            niveau, texte = "orange", f"Endettement de {_pct(taux)}, proche du seuil de {_pct(seuil, 0)}"
        else:
            niveau, texte = "vert", f"Endettement de {_pct(taux)}, sous le seuil de {_pct(seuil, 0)}"
        criteres.append({"nom": "Financement", "niveau": niveau, "texte": texte})
    else:
        part = source.get("apport_reel", 0.0) / cout_total if cout_total else 0.0
        texte = f"Apport de {_pct(part, 0)} du coût total"
        if part < SEUIL_APPORT_CONFORTABLE:
            texte += ", souvent jugé faible"
        criteres.append(
            {"nom": "Financement", "niveau": "vert" if part >= SEUIL_APPORT_CONFORTABLE else "orange", "texte": texte}
        )

    niveaux = {c["niveau"] for c in criteres}
    niveau = "rouge" if "rouge" in niveaux else ("orange" if "orange" in niveaux else "vert")
    return {
        "niveau": niveau,
        "titre": TITRES_VERDICT_GLOBAL[niveau],
        "detail": rentabilite["detail"],
        "criteres": criteres,
    }


def _eur(v: float) -> str:
    # Espaces insécables : un montant n'est jamais coupé en fin de ligne.
    return f"{v:,.0f}\u00a0€".replace(",", "\u00a0")


def _pct(v: float, digits: int = 1) -> str:
    return f"{v * 100:.{digits}f}\u00a0%".replace(".", ",")


def etapes_loyer_mensuel(resultat: dict) -> list[tuple[str, float]]:
    """Du loyer encaissé au cash-flow net, en moyenne mensuelle de l'année de
    référence (hors différé et hors déductions ponctuelles de l'année 1), pour
    le régime le plus favorable. `resultat` : sortie de clean_result."""
    annee1 = resultat["annees"][resultat.get("annee_reference", 1) - 1]
    impots = annee1["fiscal"][resultat["meilleur_regime"]]["total_prelevements"] / 12
    etapes = [("Loyers encaissés", annee1["loyers_bruts"] / 12), ("Charges", -annee1["charges_hors_credit"] / 12)]
    if annee1["mensualite_totale_credit"]:
        etapes.append(("Crédit", -annee1["mensualite_totale_credit"] / 12))
    etapes.append(("Économie d'impôt" if impots < 0 else "Impôts", -impots))
    return etapes


def evolution_patrimoine(resultat: dict, prix_achat: float, taux_revalorisation_bien: float) -> list[dict]:
    """Par année : valeur du bien, capital restant dû et patrimoine net
    (valeur − capital restant dû + cash-flows cumulés − apport), avant impôt
    de revente, pour le régime le plus favorable."""
    regime = resultat["meilleur_regime"]
    lignes = []
    cumul = 0.0
    for a in resultat["annees"]:
        cumul += a["cashflow_apres_impot"][regime]
        valeur = prix_achat * (1 + taux_revalorisation_bien) ** a["annee"]
        lignes.append(
            {
                "annee": a["annee"],
                "valeur_bien": valeur,
                "capital_restant_du": a["capital_restant_du"],
                "patrimoine_net": valeur - a["capital_restant_du"] + cumul - resultat["apport_reel"],
            }
        )
    return lignes
