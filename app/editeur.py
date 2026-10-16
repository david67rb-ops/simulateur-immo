"""Identité de l'éditeur du site et vendeur des dossiers, reprise par les
mentions légales, les CGU, les CGV et les factures Stripe.

À compléter à l'immatriculation (statut, adresse, SIRET), et à l'adhésion au
médiateur de la consommation. Tant qu'un champ est vide, les pages légales
l'affichent « à compléter » (en jaune) : rien à changer ailleurs.
"""
from __future__ import annotations

NOM = "David Lehmann"
# Après l'immatriculation : « entrepreneur individuel (EI) ». La mention EI
# accompagne le nom sur le site, les CGV et les factures (loi du 14 février 2022).
STATUT = "entrepreneur individuel (EI)"
ADRESSE = "3 rue de Hésingue, 68300 Saint-Louis"
SIRET = ""
TELEPHONE = "+33 6 75 67 76 91"  # exigé dans l'information avant l'achat (Code de la consommation, R.111-1)
CONTACT_EMAIL = "credaura.contact@gmail.com"

# Médiateur de la consommation (Code de la consommation, L.612-1 et L.616-1) :
# nom, adresse postale et site, recopiés de l'attestation d'adhésion.
MEDIATEUR_NOM = ""
MEDIATEUR_ADRESSE = ""
MEDIATEUR_SITE = ""


def identite_facture() -> str:
    """« David Lehmann EI · SIRET 123 456 789 00012 », pour le pied des factures."""
    nom = NOM + (" EI" if (SIRET or STATUT) else "")
    if SIRET:
        return f"{nom} · SIRET {SIRET}"
    return f"{nom} · SIRET en cours d'attribution" if STATUT else nom
