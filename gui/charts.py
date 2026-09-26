"""Construction des options ECharts des graphiques de l'onglet Résultats."""
from __future__ import annotations

from app.utils import libelle_regime

SERIES_COLORS = ["#1d6f5c", "#c9822a"]
POSITIF = "#1d6f5c"
NEGATIF = "#d1453b"
TOTAL = "#c9822a"
TEXTE = "#8a8f98"  # lisible sur fond clair comme sombre

_AXES_TEXTE = {"color": TEXTE}


def _eur(v: float) -> str:
    v = 0.0 if round(v) == 0 else v
    return f"{v:,.0f} €".replace(",", " ")


def cashflow_chart_option(resultat: dict, regimes: list[str]) -> dict:
    labels = [f"Année {a['annee']}" for a in resultat["annees"]]
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
                "symbolSize": 5,
                "itemStyle": {"color": SERIES_COLORS[i % len(SERIES_COLORS)]},
                "lineStyle": {"color": SERIES_COLORS[i % len(SERIES_COLORS)]},
            }
        )
    return {
        "tooltip": {"trigger": "axis"},
        "legend": {"bottom": 0, "data": [libelle_regime(r) for r in regimes], "textStyle": _AXES_TEXTE},
        "grid": {"left": 60, "right": 20, "top": 20, "bottom": 50, "containLabel": True},
        "xAxis": {"type": "category", "data": labels, "axisLabel": {"rotate": 45, "fontSize": 10, **_AXES_TEXTE}},
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
    """Cascade mensuelle de l'année 1 : du loyer encaissé au cash-flow net, pour
    le régime le plus favorable. Barres flottantes obtenues par empilement
    d'une base invisible ; les étapes qui traversent zéro sont coupées en une
    partie positive et une partie négative pour que l'empilement reste juste."""
    annee1 = resultat["annees"][0]
    regime = resultat["meilleur_regime"]
    impots = annee1["fiscal"][regime]["total_prelevements"] / 12
    etapes = [("Loyers encaissés", annee1["loyers_bruts"] / 12), ("Charges", -annee1["charges_hors_credit"] / 12)]
    if annee1["mensualite_totale_credit"]:
        etapes.append(("Crédit", -annee1["mensualite_totale_credit"] / 12))
    etapes.append(("Économie d'impôt" if impots < 0 else "Impôts", -impots))

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
    axe_y = {"type": "value", "axisLabel": {"formatter": "{value} €", **_AXES_TEXTE}}
    if bas_min < 0:
        axe_y["min"] = -round((-bas_min + marge) / 100 + 0.5) * 100
    axe_y["max"] = round((haut_max + marge) / 100 + 0.5) * 100

    serie = {"type": "bar", "stack": "cascade", "barWidth": "55%", "label": {"color": TEXTE, "fontSize": 11}}
    return {
        "grid": {"left": 10, "right": 10, "top": 30, "bottom": 10, "containLabel": True},
        "xAxis": {
            "type": "category",
            "data": categories,
            "axisLine": {"onZero": False},
            "axisLabel": {"interval": 0, "fontSize": 11, **_AXES_TEXTE},
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
    regime = resultat["meilleur_regime"]
    apport = resultat["apport_reel"]
    annees, valeurs, crd, patrimoine = [], [], [], []
    cumul = 0.0
    for a in resultat["annees"]:
        cumul += a["cashflow_apres_impot"][regime]
        valeur = prix_achat * (1 + taux_revalorisation_bien) ** a["annee"]
        annees.append(f"Année {a['annee']}")
        valeurs.append(round(valeur))
        crd.append(round(a["capital_restant_du"]))
        patrimoine.append(round(valeur - a["capital_restant_du"] + cumul - apport))
    serie = {"type": "line", "smooth": True, "symbolSize": 4}
    return {
        "tooltip": {"trigger": "axis"},
        "legend": {"bottom": 0, "textStyle": _AXES_TEXTE},
        "grid": {"left": 10, "right": 20, "top": 20, "bottom": 50, "containLabel": True},
        "xAxis": {"type": "category", "data": annees, "axisLabel": {"rotate": 45, "fontSize": 10, **_AXES_TEXTE}},
        "yAxis": {"type": "value", "axisLabel": {"formatter": "{value} €", **_AXES_TEXTE}},
        "series": [
            {**serie, "name": "Valeur du bien", "data": valeurs, "itemStyle": {"color": "#4a7fb5"}},
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
