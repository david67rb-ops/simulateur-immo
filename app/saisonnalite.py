"""Saisonnalité de la location courte durée : répartition mois par mois de
l'occupation et du prix par nuitée, et cash-flow mensuel de l'année 1.

Les profils types répartissent les moyennes annuelles saisies (taux
d'occupation, prix par nuitée) sans les modifier : les recettes annuelles
restent prix × 365 × occupation, seule leur répartition dans l'année change.
Le profil personnalisé, lui, définit directement les 12 mois.
"""
from __future__ import annotations

from .schemas import SimulationInput

MOIS = ["Janv.", "Févr.", "Mars", "Avr.", "Mai", "Juin", "Juil.", "Août", "Sept.", "Oct.", "Nov.", "Déc."]
JOURS = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]

# Coefficients relatifs (1 = moyenne annuelle) d'occupation puis de prix, de
# janvier à décembre. Ordres de grandeur indicatifs de la saisonnalité des
# meublés de tourisme en France, à ajuster selon la zone.
PROFILS: dict[str, tuple[str, list[float], list[float]]] = {
    "uniforme": ("Sans saisonnalité", [1.0] * 12, [1.0] * 12),
    "ville": (
        "Grande ville",
        [0.80, 0.85, 0.95, 1.05, 1.10, 1.10, 1.10, 1.00, 1.10, 1.05, 0.90, 0.90],
        [0.90, 0.90, 0.95, 1.00, 1.05, 1.10, 1.10, 1.05, 1.05, 1.00, 0.95, 1.00],
    ),
    "littoral": (
        "Littoral",
        [0.35, 0.40, 0.55, 0.80, 1.00, 1.40, 1.85, 1.90, 1.20, 0.70, 0.40, 0.45],
        [0.75, 0.75, 0.80, 0.90, 1.00, 1.20, 1.45, 1.50, 1.05, 0.85, 0.75, 0.80],
    ),
    "montagne": (
        "Montagne (hiver et été)",
        [1.60, 1.80, 1.40, 0.70, 0.30, 0.60, 1.20, 1.30, 0.50, 0.30, 0.30, 1.20],
        [1.30, 1.45, 1.20, 0.90, 0.70, 0.80, 1.00, 1.05, 0.75, 0.70, 0.70, 1.25],
    ),
    "campagne": (
        "Campagne / tourisme vert",
        [0.40, 0.45, 0.60, 0.90, 1.10, 1.30, 1.70, 1.80, 1.10, 0.80, 0.45, 0.60],
        [0.85, 0.85, 0.90, 0.95, 1.00, 1.10, 1.25, 1.25, 1.00, 0.95, 0.85, 0.90],
    ),
}
REGION = "region"
PERSONNALISE = "personnalise"
LIBELLES_PROFILS = (
    {cle: libelle for cle, (libelle, _, _) in PROFILS.items()}
    | {REGION: "Réservations de la région (Eurostat)"}
    | {PERSONNALISE: "Personnalisé"}
)


def _repartir_occupation(taux: float, coefs: list[float]) -> list[float]:
    """Occupation de chaque mois proportionnelle aux coefficients, plafonnée à
    100 %, avec une moyenne annuelle (pondérée par les jours) égale à `taux`."""
    occupation = [0.0] * 12
    plafonnes: set[int] = set()
    for _ in range(12):
        libres = [m for m in range(12) if m not in plafonnes]
        cible = 365 * taux - sum(JOURS[m] for m in plafonnes)
        poids = sum(JOURS[m] * coefs[m] for m in libres)
        k = cible / poids if poids else 0.0
        for m in libres:
            occupation[m] = coefs[m] * k
        depasse = [m for m in libres if occupation[m] > 1.0]
        if not depasse:
            break
        for m in depasse:
            occupation[m] = 1.0
            plafonnes.add(m)
    return occupation


def valeurs_mensuelles(inp: SimulationInput) -> list[tuple[float, float]]:
    """(taux d'occupation, prix par nuitée) de chaque mois de l'année 1."""
    if inp.profil_saisonnalite == PERSONNALISE and inp.occupation_mensuelle and inp.prix_nuitee_mensuel:
        return list(zip(inp.occupation_mensuelle, inp.prix_nuitee_mensuel))
    if inp.profil_saisonnalite == REGION and inp.coefs_occupation_region and inp.coefs_prix_region:
        coefs_occ, coefs_prix = inp.coefs_occupation_region, inp.coefs_prix_region
    else:
        _, coefs_occ, coefs_prix = PROFILS.get(inp.profil_saisonnalite, PROFILS["uniforme"])
    occupation = _repartir_occupation(inp.taux_occupation_pct, coefs_occ)
    nuits = [JOURS[m] * occupation[m] for m in range(12)]
    ponderation = sum(n * c for n, c in zip(nuits, coefs_prix))
    k = sum(nuits) / ponderation if ponderation else 1.0
    return [(occupation[m], inp.prix_nuitee * coefs_prix[m] * k) for m in range(12)]


def recettes_annuelles(inp: SimulationInput) -> float:
    return sum(JOURS[m] * occ * prix for m, (occ, prix) in enumerate(valeurs_mensuelles(inp)))


def moyennes_annuelles(occupation: list[float], prix: list[float]) -> tuple[float, float]:
    """Taux d'occupation annuel et prix moyen par nuitée d'un profil mensuel."""
    nuits = sum(JOURS[m] * occupation[m] for m in range(12))
    recettes = sum(JOURS[m] * occupation[m] * prix[m] for m in range(12))
    return nuits / 365, (recettes / nuits if nuits else 0.0)


def _pire_sequence(cashflows: list[float]) -> float:
    """Plus forte perte cumulée sur des mois consécutifs (l'année bouclant sur
    elle-même) : la trésorerie à prévoir pour traverser la basse saison."""
    pire = 0.0
    for debut in range(12):
        cumul = 0.0
        for d in range(12):
            cumul += cashflows[(debut + d) % 12]
            pire = min(pire, cumul)
    return max(0.0, -pire)


def analyse_mensuelle(inp: SimulationInput, resultat: dict) -> dict:
    """Recettes, dépenses et cash-flow avant impôt de chaque mois de l'année 1.
    `resultat` : sortie de simuler() passée par clean_result. Les charges
    fixes sont lissées sur 12 mois ; commission de plateforme et gestion
    suivent les recettes, le ménage suit le nombre de nuits."""
    annee1 = resultat["annees"][0]
    valeurs = valeurs_mensuelles(inp)
    nuits = [JOURS[m] * occ for m, (occ, _) in enumerate(valeurs)]
    recettes = [nuits[m] * valeurs[m][1] for m in range(12)]
    total_recettes = sum(recettes) or 1.0
    total_nuits = sum(nuits) or 1.0

    taux_proportionnel = inp.frais_gestion_pct_loyers + inp.frais_plateforme_pct
    proportionnelles = annee1["loyers_bruts"] * taux_proportionnel
    menage = inp.frais_menage_annuel
    fixes = annee1["charges_hors_credit"] - proportionnelles - menage
    credit = annee1["mensualite_totale_credit"] / 12

    lignes = []
    for m in range(12):
        charges = fixes / 12 + recettes[m] * taux_proportionnel + menage * nuits[m] / total_nuits
        depenses = charges + credit
        lignes.append(
            {
                "mois": MOIS[m],
                "occupation": valeurs[m][0],
                "prix_nuitee": valeurs[m][1],
                "nuits": nuits[m],
                "recettes": recettes[m],
                "charges": charges,
                "credit": credit,
                "depenses": depenses,
                "cashflow": recettes[m] - depenses,
            }
        )
    cashflows = [l["cashflow"] for l in lignes]
    meilleur = max(range(12), key=lambda m: cashflows[m])
    pire = min(range(12), key=lambda m: cashflows[m])
    return {
        "profil": LIBELLES_PROFILS.get(inp.profil_saisonnalite, inp.profil_saisonnalite),
        "lignes": lignes,
        "mois_deficitaires": sum(1 for c in cashflows if c < 0),
        "tresorerie_securite": _pire_sequence(cashflows),
        "meilleur_mois": MOIS[meilleur],
        "pire_mois": MOIS[pire],
        "part_haute_saison": sum(sorted(recettes, reverse=True)[:3]) / total_recettes,
    }
