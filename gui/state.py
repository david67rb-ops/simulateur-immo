"""État par défaut des formulaires (unités d'affichage : les pourcentages
sont saisis en % comme dans l'UI, convertis en fraction juste avant l'appel
aux fonctions métier — voir build_simulation_input dans main.py)."""
from __future__ import annotations


def default_market_state() -> dict:
    return {
        "listing_url": "",
        "adresse": "",
        "type_bien": "appartement",
        "surface_m2": 50.0,
        "rayon_metres": 500,
    }


def default_sim_state() -> dict:
    return {
        # Projet & structure
        "type_projet": "location_longue_duree",
        "structure_juridique": "personne_physique",
        # Le bien
        "type_bien": "appartement",
        "bien_neuf": False,
        "surface_m2": 50.0,
        "prix_achat": 180000.0,
        "frais_notaire": 14400.0,
        "montant_travaux": 0.0,
        "montant_mobilier": 0.0,
        # Financement
        "avec_credit": True,
        "apport": 20000.0,
        "taux_credit_annuel": 3.5,
        "duree_credit_annees": 20,
        "taux_assurance_emprunteur": 0.3,
        "differe_type": "aucun",
        "differe_duree_mois": 0,
        "taux_frais_garantie": 1.0,
        "frais_dossier_bancaire": 800.0,
        "frais_courtage": 0.0,
        # Exploitation
        "loyer_mensuel_hors_charges": 750.0,
        "charges_copropriete_annuelles": 1200.0,
        "taxe_fonciere_annuelle": 1000.0,
        "assurance_pno_annuelle": 150.0,
        "frais_gestion_pct_loyers": 0.0,
        "vacance_locative_pct": 5.0,
        "entretien_annuel": 300.0,
        "frais_comptable_annuel": 0.0,
        "cfe_annuelle": 300.0,
        "gli_pct_loyers": 0.0,
        # Location courte durée
        "prix_nuitee": 80.0,
        "taux_occupation_pct": 50.0,
        "meuble_tourisme_classe": True,
        "frais_plateforme_pct": 3.0,
        "frais_menage_annuel": 0.0,
        # Régime locatif & fiscalité
        "regime_location": "nue",
        "taux_marginal_imposition": 0.30,
        # Amortissement
        "part_terrain_pct": 15.0,
        "duree_amortissement_bati_annees": 25,
        "duree_amortissement_travaux_annees": 15,
        "duree_amortissement_mobilier_annees": 7,
        # Projection
        "duree_projection_annees": 20,
        "taux_revalorisation_bien_annuel": 1.0,
        "taux_revalorisation_loyers_annuel": 1.0,
        "taux_revalorisation_charges_annuel": 2.0,
        # Objectifs (prix d'achat maximum)
        "objectif_cashflow_mensuel": 0.0,
        "objectif_marge_nette": 0.0,
        # Achat-revente
        "duree_portage_mois": 9,
        "prix_revente_vise": None,
        "frais_agence_revente_pct": 4.0,
        "marchand_de_biens_professionnel": False,
    }


def default_profil_state() -> dict:
    return {
        "revenus_nets_mensuels_foyer": 3000.0,
        "autres_revenus_mensuels": 0.0,
        "mensualites_credits_existants": 0.0,
    }


def default_dossier_meta_state() -> dict:
    return {
        "nom_emprunteur": "",
        "adresse_bien": "",
    }


PERCENT_FIELDS = [
    "taux_credit_annuel",
    "taux_assurance_emprunteur",
    "frais_gestion_pct_loyers",
    "vacance_locative_pct",
    "part_terrain_pct",
    "taux_revalorisation_bien_annuel",
    "taux_revalorisation_loyers_annuel",
    "frais_plateforme_pct",
    "frais_agence_revente_pct",
    "taux_occupation_pct",
    "taux_frais_garantie",
    "gli_pct_loyers",
    "taux_revalorisation_charges_annuel",
]
