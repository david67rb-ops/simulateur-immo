"""Contrôles de cohérence de la saisie : valeurs probablement erronées
(faute de frappe, mauvaise unité), signalées en rouge dans le formulaire."""
from __future__ import annotations


def controles_coherence(saisie: dict) -> dict[str, str]:
    """Valeurs probablement erronées (faute de frappe, mauvaise unité) :
    {clé du champ: message}. Les unités sont celles du formulaire (taux en %)."""
    alertes: dict[str, str] = {}
    prix = saisie.get("prix_achat") or 0
    surface = saisie.get("surface_m2") or 0
    loyer = saisie.get("loyer_mensuel_hors_charges") or 0
    location_classique = saisie.get("type_projet") == "location_longue_duree"

    if prix and surface:
        prix_m2 = prix / surface
        if prix_m2 < 300 or prix_m2 > 25_000:
            texte = f"{prix_m2:,.0f}".replace(",", " ")
            alertes["prix_achat"] = f"{texte} € par m² : vérifie le prix ou la surface."
    if surface and (surface < 9 or surface > 500):
        alertes["surface_m2"] = "Surface inhabituelle pour un logement : vérifie la saisie."
    if location_classique and prix and loyer:
        brut = loyer * 12 / prix
        if brut > 0.15:
            alertes["loyer_mensuel_hors_charges"] = "Plus de 15 % de rentabilité brute : loyer très élevé pour ce prix."
        elif brut < 0.02:
            alertes["loyer_mensuel_hors_charges"] = "Moins de 2 % de rentabilité brute : loyer très faible pour ce prix."
    taxe = saisie.get("taxe_fonciere_annuelle") or 0
    if location_classique and loyer and taxe > 5 * loyer:
        alertes["taxe_fonciere_annuelle"] = "Plus de 5 mois de loyer : faute de frappe ?"
    copro = saisie.get("charges_copropriete_annuelles") or 0
    if surface and copro > 80 * surface:
        alertes["charges_copropriete_annuelles"] = "Plus de 80 € par m² et par an : montant inhabituel."
    taux = saisie.get("taux_credit_annuel")
    if saisie.get("avec_credit") and taux is not None and (taux > 8 or 0 < taux < 0.5):
        alertes["taux_credit_annuel"] = "Taux inhabituel : saisir 3,5 pour un crédit à 3,5 %."
    apport = saisie.get("apport") or 0
    if saisie.get("avec_credit") and prix and apport > prix * 1.15:
        alertes["apport"] = "Apport supérieur au coût de l'opération : le crédit est-il nécessaire ?"
    nuitee = saisie.get("prix_nuitee") or 0
    if saisie.get("type_projet") == "location_courte_duree" and nuitee > 1_000:
        alertes["prix_nuitee"] = "Plus de 1 000 € la nuit : vérifie la saisie."
    revenus = saisie.get("revenus_nets_mensuels_foyer") or 0
    if revenus and revenus < 300:
        alertes["revenus_nets_mensuels_foyer"] = "Revenus mensuels très faibles : montant annuel saisi par erreur ?"
    return alertes
