"""Construction des options ECharts (graphique de cash-flow cumulé)."""
from __future__ import annotations

from app.utils import libelle_regime

SERIES_COLORS = ["#1d6f5c", "#c9822a"]


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
        "legend": {"bottom": 0, "data": [libelle_regime(r) for r in regimes]},
        "grid": {"left": 60, "right": 20, "top": 20, "bottom": 50, "containLabel": True},
        "xAxis": {"type": "category", "data": labels, "axisLabel": {"rotate": 45, "fontSize": 10}},
        "yAxis": {"type": "value", "axisLabel": {"formatter": "{value} €"}},
        "series": series,
    }
