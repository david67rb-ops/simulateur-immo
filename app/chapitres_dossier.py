"""Catalogue des chapitres du dossier Word, séparé de dossier_export pour
que l'interface puisse l'utiliser sans charger python-docx ni matplotlib."""
from __future__ import annotations

# Chapitres que l'utilisateur peut retirer du rapport (clé : titre), dans
# l'ordre du dossier, et formules prêtes à l'emploi.
CHAPITRES_OPTIONNELS = {
    "presentation": "Le bien et le projet",
    "photos": "Le bien en photos",
    "marche": "Étude de marché",
    "carte": "Le bien sur la carte",
    "profil": "Profil de l'emprunteur",
    "financement": "Plan de financement",
    "achat_revente": "L'opération d'achat-revente",
    "charges": "Recettes et charges annuelles",
    "loyer_mensuel": "Où va le loyer chaque mois",
    "saisonnalite": "Saisonnalité mois par mois",
    "patrimoine": "Évolution du patrimoine",
    "endettement": "Taux d'endettement",
    "annexes": "Pièces à fournir à la banque",
}
CHAPITRES_OBLIGATOIRES = {"synthese", "avertissements", "mentions"}
FORMULES_DOSSIER = {
    "complet": ("Complet", set(CHAPITRES_OPTIONNELS)),
    "banque": (
        "Banque",
        {
            "presentation",
            "photos",
            "marche",
            "carte",
            "profil",
            "financement",
            "achat_revente",
            "charges",
            "loyer_mensuel",
            "saisonnalite",
            "endettement",
            "annexes",
        },
    ),
    "personnel": (
        "Personnel",
        {
            "presentation",
            "photos",
            "marche",
            "carte",
            "financement",
            "achat_revente",
            "charges",
            "loyer_mensuel",
            "saisonnalite",
            "patrimoine",
        },
    ),
}


def chapitres_disponibles(type_projet: str, avec_credit: bool) -> list[str]:
    """Chapitres optionnels qui existent pour ce type de projet."""
    exclus = set()
    if type_projet == "achat_revente":
        exclus |= {"charges", "loyer_mensuel", "saisonnalite", "patrimoine"}
    else:
        exclus.add("achat_revente")
        if type_projet != "location_courte_duree":
            exclus.add("saisonnalite")
    if not avec_credit:
        # Sans crédit, pas de banque à convaincre.
        exclus |= {"profil", "endettement", "annexes"}
    return [cle for cle in CHAPITRES_OPTIONNELS if cle not in exclus]
