"""Construction des options ECharts des graphiques de l'onglet Résultats."""
from __future__ import annotations

from app.analyse import etapes_loyer_mensuel, evolution_patrimoine
from app.utils import libelle_regime

# Bleu acier plutôt que bleu notaire pour les tracés : lisible sur fond clair
# comme sur fond sombre.
BLEU = "#3a649e"
LAITON = "#a8823b"
SERIES_COLORS = [BLEU, LAITON]
POSITIF = BLEU
NEGATIF = "#b23a32"
TOTAL = LAITON
TEXTE = "#8a8f98"  # lisible sur fond clair comme sombre

_AXES_TEXTE = {"color": TEXTE}


def _eur(v: float) -> str:
    v = 0.0 if round(v) == 0 else v
    return f"{v:,.0f} €".replace(",", " ")


def cashflow_chart_option(resultat: dict, regimes: list[str]) -> dict:
    labels = [f"An {a['annee']}" for a in resultat["annees"]]
    series = []
    for i, regime in enumerate(regimes):
        cumul = 0.0
        valeurs = []
        for cf in resultat["cashflows_par_regime"][regime][1:]:
            cumul += cf
            valeurs.append(round(cumul, 0))
        series.append(
            {
                "name": libelle_regime(regime),
                "type": "line",
                "data": valeurs,
                "smooth": True,
                "showSymbol": False,
                "itemStyle": {"color": SERIES_COLORS[i % len(SERIES_COLORS)]},
                "lineStyle": {"color": SERIES_COLORS[i % len(SERIES_COLORS)]},
            }
        )
    return {
        "tooltip": {"trigger": "axis", "confine": True},
        "legend": {"bottom": 0, "data": [libelle_regime(r) for r in regimes], "textStyle": _AXES_TEXTE},
        "grid": {"left": 10, "right": 20, "top": 20, "bottom": 50, "containLabel": True},
        # « An 1 », « An 2 »… à plat : ECharts n'affiche qu'une année sur deux ou trois
        # quand la place manque (téléphone), au lieu de libellés obliques serrés.
        "xAxis": {"type": "category", "data": labels, "axisLabel": {"fontSize": 10, **_AXES_TEXTE}},
        "yAxis": {"type": "value", "axisLabel": {"formatter": "{value} €", **_AXES_TEXTE}},
        "series": series,
    }


def _barre(valeur: float, couleur: str, texte: str, visible: bool, position: str) -> dict:
    return {
        "value": round(valeur),
        "itemStyle": {"color": couleur},
        "label": {"show": visible, "formatter": texte, "position": position},
    }


def repartition_loyer_option(resultat: dict) -> dict:
    """Cascade mensuelle de l'année de référence : du loyer encaissé au cash-flow net, pour
    le régime le plus favorable. Barres flottantes obtenues par empilement
    d'une base invisible ; les étapes qui traversent zéro sont coupées en une
    partie positive et une partie négative pour que l'empilement reste juste."""
    etapes = etapes_loyer_mensuel(resultat)

    categories, base, positif, negatif = [], [], [], []
    cumul = 0.0
    points = [0.0]
    for libelle, montant in etapes:
        debut, fin = cumul, cumul + montant
        bas, haut = min(debut, fin), max(debut, fin)
        couleur = POSITIF if montant >= 0 else NEGATIF
        texte = ("+" if montant >= 0 else "") + _eur(montant)
        categories.append(libelle)
        if bas >= 0:
            base.append(round(bas))
            positif.append(_barre(haut - bas, couleur, texte, True, "top"))
            negatif.append(0)
        elif haut <= 0:
            base.append(round(haut))
            positif.append(0)
            negatif.append(_barre(bas - haut, couleur, texte, True, "bottom"))
        else:
            base.append(0)
            positif.append(_barre(haut, couleur, texte, montant >= 0, "top"))
            negatif.append(_barre(bas, couleur, texte, montant < 0, "bottom"))
        cumul = fin
        points.append(cumul)

    categories.append("Cash-flow net")
    texte = ("+" if cumul >= 0 else "") + _eur(cumul)
    base.append(0)
    if cumul >= 0:
        positif.append(_barre(cumul, TOTAL, texte, True, "top"))
        negatif.append(0)
    else:
        positif.append(0)
        negatif.append(_barre(cumul, TOTAL, texte, True, "bottom"))

    # Marge sous la barre la plus basse et au-dessus de la plus haute pour
    # que les montants affichés ne chevauchent pas les noms des colonnes.
    bas_min, haut_max = min(points), max(points)
    marge = (haut_max - bas_min) * 0.15
    # Bornes arrondies hors graduation : leurs libellés chevaucheraient la
    # graduation voisine (« 900 € / 1 000 € »), on ne les affiche pas.
    axe_y = {
        "type": "value",
        "axisLabel": {"formatter": "{value} €", "showMinLabel": False, "showMaxLabel": False, **_AXES_TEXTE},
    }
    if bas_min < 0:
        axe_y["min"] = -round((-bas_min + marge) / 100 + 0.5) * 100
    axe_y["max"] = round((haut_max + marge) / 100 + 0.5) * 100

    serie = {"type": "bar", "stack": "cascade", "barWidth": "55%", "label": {"color": TEXTE, "fontSize": 11}}
    return {
        "grid": {"left": 10, "right": 10, "top": 30, "bottom": 10, "containLabel": True},
        "xAxis": {
            "type": "category",
            # Un mot par ligne (« Économie / d'impôt ») : les libellés ne se
            # chevauchent plus, même sur un écran de téléphone.
            "data": [c.replace(" ", "\n") for c in categories],
            "axisLine": {"onZero": False},
            "axisLabel": {"interval": 0, "fontSize": 10, "lineHeight": 12, **_AXES_TEXTE},
        },
        "yAxis": axe_y,
        "series": [
            {
                **serie,
                "name": "base",
                "data": base,
                "itemStyle": {"color": "transparent"},
                "label": {"show": False},
                "emphasis": {"disabled": True},
            },
            {**serie, "name": "positif", "data": positif},
            {**serie, "name": "negatif", "data": negatif},
        ],
    }


def patrimoine_option(resultat: dict, prix_achat: float, taux_revalorisation_bien: float) -> dict:
    """Évolution annuelle : valeur du bien, capital restant dû et patrimoine net
    (valeur − capital restant dû + cash-flows cumulés − apport), avant impôt de
    revente, pour le régime le plus favorable."""
    lignes = evolution_patrimoine(resultat, prix_achat, taux_revalorisation_bien)
    annees = [f"An {l['annee']}" for l in lignes]
    valeurs = [round(l["valeur_bien"]) for l in lignes]
    crd = [round(l["capital_restant_du"]) for l in lignes]
    patrimoine = [round(l["patrimoine_net"]) for l in lignes]
    serie = {"type": "line", "smooth": True, "showSymbol": False}
    return {
        "tooltip": {"trigger": "axis", "confine": True},
        "legend": {"bottom": 0, "textStyle": _AXES_TEXTE},
        "grid": {"left": 10, "right": 20, "top": 20, "bottom": 50, "containLabel": True},
        "xAxis": {"type": "category", "data": annees, "axisLabel": {"fontSize": 10, **_AXES_TEXTE}},
        "yAxis": {"type": "value", "axisLabel": {"formatter": "{value} €", **_AXES_TEXTE}},
        "series": [
            {**serie, "name": "Valeur du bien", "data": valeurs, "itemStyle": {"color": "#8aa4c8"}},
            {**serie, "name": "Capital restant dû", "data": crd, "itemStyle": {"color": NEGATIF}},
            {
                **serie,
                "name": "Patrimoine net (avant impôt de revente)",
                "data": patrimoine,
                "itemStyle": {"color": POSITIF},
                "areaStyle": {"opacity": 0.15},
            },
        ],
    }


def saisonnalite_option(saison: dict) -> dict:
    """Recettes et dépenses de chaque mois (barres) et cash-flow avant impôt
    (courbe), année 1, location courte durée."""
    lignes = saison["lignes"]
    mois = [l["mois"] for l in lignes]
    return {
        "tooltip": {"trigger": "axis", "confine": True},
        "legend": {"bottom": 0, "textStyle": _AXES_TEXTE},
        "grid": {"left": 10, "right": 20, "top": 20, "bottom": 40, "containLabel": True},
        "xAxis": {"type": "category", "data": mois, "axisLabel": {"interval": 0, "fontSize": 10, **_AXES_TEXTE}},
        "yAxis": {"type": "value", "axisLabel": {"formatter": "{value} €", **_AXES_TEXTE}},
        "series": [
            {
                "name": "Recettes",
                "type": "bar",
                "data": [round(l["recettes"]) for l in lignes],
                "itemStyle": {"color": POSITIF},
                "barGap": "10%",
            },
            {
                "name": "Charges + crédit",
                "type": "bar",
                "data": [round(l["depenses"]) for l in lignes],
                "itemStyle": {"color": "#9aa3ad"},
            },
            {
                "name": "Cash-flow avant impôt",
                "type": "line",
                "data": [
                    {"value": round(l["cashflow"]), "itemStyle": {"color": POSITIF if l["cashflow"] >= 0 else NEGATIF}}
                    for l in lignes
                ],
                "symbolSize": 7,
                "lineStyle": {"color": TOTAL, "width": 2},
                "itemStyle": {"color": TOTAL},
                "markLine": {
                    "silent": True,
                    "symbol": "none",
                    "data": [{"yAxis": 0}],
                    "lineStyle": {"color": TEXTE, "type": "dashed"},
                    "label": {"show": False},
                },
            },
        ],
    }
