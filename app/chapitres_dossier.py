"""Catalogue des chapitres du dossier Word, séparé de dossier_export pour
que l'interface puisse l'utiliser sans charger python-docx ni matplotlib."""
from __future__ import annotations

# Le dossier suit les questions du banquier, en quatre parties : le bien (où,
# à quoi il ressemble, à quel prix, quoi ?), la rentabilité (le bien paie-t-il
# son crédit ?), le financement (qui emprunte, peut-il rembourser ?) et la
# conclusion, avec la synthèse du projet.
PARTIES = ["Le bien", "La rentabilité", "Le financement", "Conclusion"]
PARTIE_DU_CHAPITRE = {
    "carte": "Le bien",
    "photos": "Le bien",
    "presentation": "Le bien",
    "marche": "Le bien",
    "charges": "La rentabilité",
    "loyer_mensuel": "La rentabilité",
    "saisonnalite": "La rentabilité",
    "patrimoine": "La rentabilité",
    "achat_revente": "La rentabilité",
    "financement": "Le financement",
    "profil": "Le financement",
    "endettement": "Le financement",
    "avertissements": "Conclusion",
    "synthese": "Conclusion",
    "annexes": "Conclusion",
    "mentions": "Conclusion",
}

# Chapitres que l'utilisateur peut retirer du rapport (clé : titre), dans
# l'ordre du dossier, et formules prêtes à l'emploi.
CHAPITRES_OPTIONNELS = {
    "carte": "Le bien sur la carte",
    "photos": "Le bien en photos",
    "marche": "Étude de marché",
    "presentation": "Le bien et le projet",
    "charges": "Recettes et charges annuelles",
    "loyer_mensuel": "Où va le loyer chaque mois",
    "saisonnalite": "Saisonnalité mois par mois",
    "patrimoine": "Évolution du patrimoine",
    "achat_revente": "L'opération d'achat-revente",
    "financement": "Plan de financement",
    "profil": "Profil de l'emprunteur",
    "endettement": "Taux d'endettement",
    "annexes": "Pièces à fournir à la banque",
}
CHAPITRES_OBLIGATOIRES = {"synthese", "avertissements", "mentions"}
FORMULES_DOSSIER = {
    "complet": ("Complet", set(CHAPITRES_OPTIONNELS)),
    "banque": ("Banque", set(CHAPITRES_OPTIONNELS) - {"patrimoine"}),
    "personnel": ("Personnel", set(CHAPITRES_OPTIONNELS) - {"profil", "endettement", "annexes"}),
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
