from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class TypeBien(str, Enum):
    appartement = "appartement"
    maison = "maison"


class RegimeLocation(str, Enum):
    nue = "nue"
    meublee = "meublee"


class TypeProjet(str, Enum):
    location_longue_duree = "location_longue_duree"
    location_courte_duree = "location_courte_duree"
    achat_revente = "achat_revente"


class StructureJuridique(str, Enum):
    personne_physique = "personne_physique"
    sci_ir = "sci_ir"
    sci_is = "sci_is"


class SimulationInput(BaseModel):
    # --- Projet & structure ---
    type_projet: TypeProjet = TypeProjet.location_longue_duree
    structure_juridique: StructureJuridique = StructureJuridique.personne_physique

    # --- Bien ---
    type_bien: TypeBien = TypeBien.appartement
    bien_neuf: bool = Field(default=False, description="Neuf/VEFA (<5 ans) : frais de notaire réduits")
    surface_m2: float = Field(gt=0)
    prix_achat: float = Field(gt=0)
    frais_notaire: float = Field(ge=0, description="Frais d'acquisition (notaire, garantie...)")
    montant_travaux: float = Field(default=0, ge=0)
    montant_mobilier: float = Field(default=0, ge=0, description="Utile si location meublée")

    # --- Financement ---
    apport: float = Field(default=0, ge=0)
    taux_credit_annuel: float = Field(default=0.035, ge=0, le=0.2)
    duree_credit_annees: int = Field(default=20, gt=0, le=35)
    taux_assurance_emprunteur: float = Field(default=0.003, ge=0, le=0.02)

    # --- Exploitation (location longue/courte durée) ---
    loyer_mensuel_hors_charges: float = Field(default=0, ge=0)
    charges_copropriete_annuelles: float = Field(default=0, ge=0)
    charges_recuperables_annuelles: float = Field(
        default=0, ge=0, description="Charges refacturées au locataire (souvent neutres)"
    )
    taxe_fonciere_annuelle: float = Field(default=0, ge=0)
    assurance_pno_annuelle: float = Field(default=0, ge=0)
    frais_gestion_pct_loyers: float = Field(default=0.0, ge=0, le=0.15)
    vacance_locative_pct: float = Field(
        default=0.0, ge=0, le=0.9, description="Part de l'année sans locataire"
    )
    entretien_annuel: float = Field(default=0, ge=0)
    frais_comptable_annuel: float = Field(
        default=0, ge=0, description="Utile pour le régime réel BIC / SCI à l'IS"
    )

    # --- Spécifique location courte durée ---
    meuble_tourisme_classe: bool = Field(
        default=True, description="Classé (abattement micro-BIC 50 %) sinon non classé (30 %, plafond réduit)"
    )
    frais_plateforme_pct: float = Field(
        default=0.0, ge=0, le=0.3, description="Commission Airbnb/Booking (% des recettes)"
    )
    frais_menage_annuel: float = Field(default=0, ge=0)

    # --- Régime locatif & fiscalité (personne physique / SCI IR) ---
    regime_location: RegimeLocation = RegimeLocation.nue
    taux_marginal_imposition: float = Field(
        default=0.30, ge=0, le=0.45, description="TMI du foyer fiscal (0/0.11/0.30/0.41/0.45)"
    )

    # --- Amortissement (LMNP réel / SCI à l'IS) ---
    part_terrain_pct: float = Field(default=0.15, ge=0, le=0.5)
    duree_amortissement_bati_annees: int = Field(default=25, gt=0, le=50)
    duree_amortissement_travaux_annees: int = Field(default=15, gt=0, le=50)
    duree_amortissement_mobilier_annees: int = Field(default=7, gt=0, le=15)

    # --- Projection (location longue/courte durée) ---
    duree_projection_annees: int = Field(default=20, gt=0, le=35)
    taux_revalorisation_bien_annuel: float = Field(default=0.01, ge=-0.05, le=0.1)
    taux_revalorisation_loyers_annuel: float = Field(default=0.01, ge=-0.05, le=0.1)

    # --- Spécifique achat-revente ---
    duree_portage_mois: int = Field(default=9, gt=0, le=60)
    prix_revente_vise: float | None = Field(default=None, gt=0)
    frais_agence_revente_pct: float = Field(default=0.0, ge=0, le=0.15)
    marchand_de_biens_professionnel: bool = Field(
        default=False,
        description="Activité habituelle de marchand de biens (régime BIC/IS pro sur la marge)",
    )


class MarketStudyInput(BaseModel):
    adresse: str = Field(min_length=3)
    type_projet: TypeProjet = TypeProjet.location_longue_duree
    type_bien: TypeBien = TypeBien.appartement
    surface_m2: float | None = Field(default=None, gt=0)
    nb_pieces: int | None = Field(default=None, gt=0)
    rayon_metres: int = Field(default=500, ge=100, le=3000)


class ListingUrlInput(BaseModel):
    url: str = Field(min_length=10)


class FraisNotaireInput(BaseModel):
    prix_achat: float = Field(gt=0)
    neuf: bool = False
