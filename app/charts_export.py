"""Génération de graphiques (PNG) affichés à côté des tableaux du dossier Word.

Les figures sont dimensionnées pour un affichage à ~11-12 cm de large (colonne
de droite d'une mise en page tableau/graphique côte à côte, format paysage),
proche de leur taille finale pour rester lisibles une fois insérées.
"""
from __future__ import annotations

import io
from typing import Callable

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

PRIMARY = "#1D6F5C"
PRIMARY_LIGHT = "#6FAE9E"
ACCENT = "#B0862A"
NEGATIVE = "#B0442A"
RECETTE = "#2E6F9E"
PALETTE = [PRIMARY, ACCENT, "#4A7FB5", "#8A5FB5", "#8A8A8A"]
PALETTE_CHARGES = [
    "#B0862A",  # or
    "#B0442A",  # terracotta
    "#8A5FB5",  # violet
    "#5C8A3A",  # olive
    "#C97B3D",  # orange
    "#A65A8A",  # mauve
    "#6B4E9E",  # indigo
    "#8A8A8A",  # gris
]

plt.rcParams.update(
    {
        "font.size": 10.5,
        "axes.edgecolor": "#CCCCCC",
        "axes.linewidth": 0.8,
        "figure.facecolor": "white",
        "axes.facecolor": "white",
    }
)


def _eur(v: float) -> str:
    v = 0.0 if v == 0 else v  # évite l'affichage de "-0 €"
    return f"{v:,.0f} €".replace(",", " ")


def _fig_to_png(fig) -> bytes:
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=200, bbox_inches="tight")
    plt.close(fig)
    return buf.getvalue()


def chart_donut(valeurs: list[float], labels: list[str], titre: str, total_label: str = "Total") -> bytes | None:
    valeurs_labels = [(v, l) for v, l in zip(valeurs, labels) if v > 0]
    if not valeurs_labels:
        return None
    valeurs = [v for v, _ in valeurs_labels]
    labels = [l for _, l in valeurs_labels]
    total = sum(valeurs)

    fig, ax = plt.subplots(figsize=(4.1, 4.1))
    couleurs = PALETTE[: len(valeurs)]
    wedges, _texts, autotexts = ax.pie(
        valeurs,
        colors=couleurs,
        startangle=90,
        wedgeprops={"width": 0.42, "edgecolor": "white"},
        autopct=lambda p: f"{p:.0f} %",
        pctdistance=0.78,
    )
    for t in autotexts:
        t.set_color("white")
        t.set_fontsize(10.5)
        t.set_fontweight("bold")
    ax.text(0, 0, f"{total_label}\n{_eur(total)}", ha="center", va="center", fontsize=11, color="#333333")
    ax.legend(
        wedges,
        [f"{l}\n{_eur(v)}" for l, v in zip(labels, valeurs)],
        loc="upper center",
        bbox_to_anchor=(0.5, -0.03),
        frameon=False,
        fontsize=10,
    )
    ax.set_title(titre, fontsize=13, color=PRIMARY, pad=10)
    ax.axis("equal")
    return _fig_to_png(fig)


def chart_barres(
    items: list[tuple[str, float]],
    titre: str,
    formatter: Callable[[float], str] = _eur,
    seuil: float | None = None,
    seuil_label: str = "",
) -> bytes | None:
    items = [(l, v) for l, v in items if v is not None]
    if not items:
        return None
    labels = [l for l, _ in items]
    valeurs = [v for _, v in items]
    couleurs = [PRIMARY if v >= 0 else NEGATIVE for v in valeurs]

    fig, ax = plt.subplots(figsize=(4.6, 0.72 * len(items) + 1.2))
    bars = ax.barh(labels, valeurs, color=couleurs, height=0.52)

    bornes = valeurs + [0.0]
    if seuil is not None:
        bornes.append(seuil)
    vmin, vmax = min(bornes), max(bornes)
    marge = (vmax - vmin) * 0.3 or 1.0
    ax.set_xlim(vmin - marge, vmax + marge)

    for bar, v in zip(bars, valeurs):
        ha = "left" if v >= 0 else "right"
        decalage = 5 if v >= 0 else -5
        ax.annotate(
            formatter(v),
            (bar.get_width(), bar.get_y() + bar.get_height() / 2),
            xytext=(decalage, 0),
            textcoords="offset points",
            va="center",
            ha=ha,
            fontsize=10.5,
            color="#333333",
        )

    if seuil is not None:
        ax.axvline(seuil, color=ACCENT, linestyle="--", linewidth=1.4)
        ax.text(
            seuil,
            1.03,
            seuil_label,
            transform=ax.get_xaxis_transform(),
            color=ACCENT,
            fontsize=10,
            ha="center",
            va="bottom",
        )

    ax.axvline(0, color="#999999", linewidth=0.8)
    ax.set_title(titre, fontsize=13, color=PRIMARY, pad=24 if seuil is not None else 10)
    ax.set_xticks([])
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["bottom"].set_visible(False)
    ax.tick_params(axis="y", labelsize=10.5)
    return _fig_to_png(fig)


def chart_recettes_charges(recette: float, charges_items: list[tuple[str, float]], titre: str) -> bytes | None:
    """Deux barres empilées comparables : les recettes (une seule couleur) et
    les charges (empilées, une couleur par poste de dépense)."""
    charges_items = [(l, v) for l, v in charges_items if v > 0]
    if recette <= 0 and not charges_items:
        return None

    fig, ax = plt.subplots(figsize=(5.6, 2.9))
    y_recette, y_charges = 1, 0

    if recette > 0:
        ax.barh(y_recette, recette, color=RECETTE, height=0.5)
        ax.annotate(
            _eur(recette),
            (recette, y_recette),
            xytext=(6, 0),
            textcoords="offset points",
            va="center",
            fontsize=10.5,
            fontweight="bold",
            color="#333333",
        )

    cumul = 0.0
    for i, (label, valeur) in enumerate(charges_items):
        couleur = PALETTE_CHARGES[i % len(PALETTE_CHARGES)]
        ax.barh(y_charges, valeur, left=cumul, color=couleur, height=0.5, label=label)
        cumul += valeur
    if charges_items:
        ax.annotate(
            f"Total {_eur(cumul)}",
            (cumul, y_charges),
            xytext=(6, 0),
            textcoords="offset points",
            va="center",
            fontsize=10.5,
            fontweight="bold",
            color="#333333",
        )

    ax.set_yticks([y_charges, y_recette])
    ax.set_yticklabels(["Charges", "Recettes"], fontsize=11)
    ax.set_xticks([])
    for cote in ("top", "right", "bottom"):
        ax.spines[cote].set_visible(False)
    if charges_items:
        ax.legend(
            loc="upper center",
            bbox_to_anchor=(0.5, -0.14),
            ncol=3,
            fontsize=9,
            frameon=False,
            handlelength=1.2,
            columnspacing=1.2,
        )
    ax.set_title(titre, fontsize=13, color=PRIMARY, pad=10)
    return _fig_to_png(fig)


def chart_pont_marge(etapes: list[tuple[str, float, bool]]) -> bytes:
    """etapes : (libellé, valeur, est_un_total). Les valeurs non-totales sont
    des deltas (positifs ou négatifs) appliqués au cumul courant."""
    fig, ax = plt.subplots(figsize=(5.6, 3.9))
    cumul = 0.0
    for i, (label, valeur, est_total) in enumerate(etapes):
        if est_total:
            bas, hauteur = 0.0, valeur
            cumul = valeur
            couleur = PRIMARY
        else:
            nouveau_cumul = cumul + valeur
            if valeur < 0:
                bas, hauteur = nouveau_cumul, -valeur
            else:
                bas, hauteur = cumul, valeur
            couleur = NEGATIVE if valeur < 0 else PRIMARY_LIGHT
            cumul = nouveau_cumul
        ax.bar(i, hauteur, bottom=bas, color=couleur, width=0.55)
        ax.annotate(
            _eur(valeur),
            (i, bas + hauteur),
            xytext=(0, 4),
            textcoords="offset points",
            ha="center",
            va="bottom",
            fontsize=9.5,
            color="#333333",
        )
    ax.set_xticks(range(len(etapes)))
    ax.set_xticklabels([e[0] for e in etapes], rotation=20, ha="right", fontsize=10)
    ax.axhline(0, color="#999999", linewidth=0.8)
    ax.set_title("Décomposition de la marge", fontsize=13, color=PRIMARY, pad=10)
    ax.margins(y=0.2)
    ax.set_yticks([])
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_visible(False)
    return _fig_to_png(fig)
