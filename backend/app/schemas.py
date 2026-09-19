from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class TypeBien(str, Enum):
    appartement = "appartement"
    maison = "maison"


class RegimeLocation(str, Enum):
    nue = "nue"
    meublee = "meublee"


class SimulationInput(BaseModel):
    # --- Bien ---
    type_bien: TypeBien = TypeBien.appartement
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

    # --- Exploitation ---
    loyer_mensuel_hors_charges: float = Field(gt=0)
    charges_copropriete_annuelles: float = Field(default=0, ge=0)
    charges_recuperables_annuelles: float = Field(
        default=0, ge=0, description="Charges refacturées au locataire (souvent neutres)"
    )
    taxe_fonciere_annuelle: float = Field(default=0, ge=0)
    assurance_pno_annuelle: float = Field(default=0, ge=0)
    frais_gestion_pct_loyers: float = Field(default=0.0, ge=0, le=0.15)
    vacance_locative_pct: float = Field(
        default=0.0, ge=0, le=0.5, description="Part de l'année sans locataire"
    )
    entretien_annuel: float = Field(default=0, ge=0)
    frais_comptable_annuel: float = Field(
        default=0, ge=0, description="Utile pour le régime réel BIC (LMNP réel)"
    )

    # --- Régime locatif & fiscalité ---
    regime_location: RegimeLocation = RegimeLocation.nue
    taux_marginal_imposition: float = Field(
        default=0.30, ge=0, le=0.45, description="TMI du foyer fiscal (0/0.11/0.30/0.41/0.45)"
    )

    # --- Amortissement (LMNP réel) ---
    part_terrain_pct: float = Field(default=0.15, ge=0, le=0.5)
    duree_amortissement_bati_annees: int = Field(default=25, gt=0, le=50)
    duree_amortissement_travaux_annees: int = Field(default=15, gt=0, le=50)
    duree_amortissement_mobilier_annees: int = Field(default=7, gt=0, le=15)

    # --- Projection ---
    duree_projection_annees: int = Field(default=20, gt=0, le=35)
    taux_revalorisation_bien_annuel: float = Field(default=0.01, ge=-0.05, le=0.1)
    taux_revalorisation_loyers_annuel: float = Field(default=0.01, ge=-0.05, le=0.1)


class MarketStudyInput(BaseModel):
    adresse: str = Field(min_length=3)
    type_bien: TypeBien = TypeBien.appartement
    surface_m2: float | None = Field(default=None, gt=0)
    nb_pieces: int | None = Field(default=None, gt=0)
    rayon_metres: int = Field(default=500, ge=100, le=3000)
