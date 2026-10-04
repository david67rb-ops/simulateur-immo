"""Génération de graphiques (PNG) affichés à côté des tableaux du dossier Word.

Les figures sont dimensionnées pour un affichage à ~11-12 cm de large (colonne
de droite d'une mise en page tableau/graphique côte à côte, format paysage),
proche de leur taille finale pour rester lisibles une fois insérées.
"""
from __future__ import annotations

import io
from pathlib import Path
from typing import Callable

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.ticker import MaxNLocator

from matplotlib import font_manager

# Charte « bleu notaire & laiton ».
PRIMARY = "#1B3358"  # bleu notaire
PRIMARY_LIGHT = "#8AA4C8"
ACCENT = "#A8823B"  # laiton
NEGATIVE = "#B23A32"
POSITIVE = "#2D6A4F"
RECETTE = "#3A649E"  # bleu acier
PALETTE = [PRIMARY, ACCENT, "#3A649E", "#8AA4C8", "#C9B48A"]
PALETTE_CHARGES = [
    "#A8823B",  # laiton
    "#B23A32",  # brique
    "#3A649E",  # acier
    "#6E8B74",  # sauge
    "#C9B48A",  # sable
    "#7A5C8A",  # prune
    "#1B3358",  # bleu notaire
    "#9AA3AD",  # gris
]

# Polices de la charte, livrées avec l'application (app/fonts).
for _police in (Path(__file__).parent / "fonts").glob("*.ttf"):
    font_manager.fontManager.addfont(str(_police))
TITRE = "Sora"

plt.rcParams.update(
    {
        "font.family": "Public Sans",
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
        autopct=lambda p: f"{p:.0f} %" if p >= 4 else "",  # petites parts : montant dans la légende
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
    ax.set_title(titre, fontsize=13, color=PRIMARY, fontfamily=TITRE, fontweight="bold", pad=10)
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
    ax.set_title(titre, fontsize=13, color=PRIMARY, fontfamily=TITRE, fontweight="bold", pad=24 if seuil is not None else 10)
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
    ax.set_title(titre, fontsize=13, color=PRIMARY, fontfamily=TITRE, fontweight="bold", pad=10)
    return _fig_to_png(fig)


def chart_pont_marge(etapes: list[tuple[str, float, bool]], titre: str = "Décomposition de la marge") -> bytes:
    """etapes : (libellé, valeur, est_un_total). Les valeurs non-totales sont
    des deltas (positifs ou négatifs) appliqués au cumul courant."""
    fig, ax = plt.subplots(figsize=(5.6, 3.9))
    cumul = 0.0
    for i, (label, valeur, est_total) in enumerate(etapes):
        if est_total:
            bas, haut = sorted((0.0, valeur))
            cumul = valeur
            couleur = PRIMARY if valeur >= 0 else NEGATIVE
            texte = _eur(valeur)
        else:
            bas, haut = sorted((cumul, cumul + valeur))
            cumul += valeur
            couleur = NEGATIVE if valeur < 0 else PRIMARY_LIGHT
            texte = ("+" if valeur > 0 else "") + _eur(valeur)
        ax.bar(i, haut - bas, bottom=bas, color=couleur, width=0.55)
        # Montant au-dessus des barres positives, en dessous des négatives.
        ax.annotate(
            texte,
            (i, haut if valeur >= 0 else bas),
            xytext=(0, 4 if valeur >= 0 else -4),
            textcoords="offset points",
            ha="center",
            va="bottom" if valeur >= 0 else "top",
            fontsize=9.5,
            color="#333333",
        )
    ax.set_xticks(range(len(etapes)))
    ax.set_xticklabels([e[0] for e in etapes], rotation=20, ha="right", fontsize=10)
    ax.axhline(0, color="#999999", linewidth=0.8)
    ax.set_title(titre, fontsize=13, color=PRIMARY, fontfamily=TITRE, fontweight="bold", pad=10)
    ax.margins(y=0.2)
    bas_axe, haut_axe = ax.get_ylim()
    ax.set_ylim(bas_axe - (haut_axe - bas_axe) * 0.08, haut_axe)
    ax.tick_params(axis="x", length=0)
    ax.spines["bottom"].set_visible(False)
    ax.set_yticks([])
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_visible(False)
    return _fig_to_png(fig)


def chart_patrimoine(lignes: list[dict]) -> bytes:
    """Valeur du bien, capital restant dû et patrimoine net, année par année."""
    annees = [l["annee"] for l in lignes]
    fig, ax = plt.subplots(figsize=(5.8, 3.9))
    ax.plot(annees, [l["valeur_bien"] for l in lignes], color="#4A7FB5", linewidth=2, label="Valeur du bien")
    ax.plot(annees, [l["capital_restant_du"] for l in lignes], color=NEGATIVE, linewidth=2, label="Capital restant dû")
    patrimoine = [l["patrimoine_net"] for l in lignes]
    ax.plot(annees, patrimoine, color=PRIMARY, linewidth=2.4, label="Patrimoine net")
    ax.fill_between(annees, patrimoine, 0, color=PRIMARY, alpha=0.12)
    ax.axhline(0, color="#999999", linewidth=0.8)
    ax.yaxis.set_major_formatter(lambda v, _pos: _eur(v))
    ax.xaxis.set_major_locator(MaxNLocator(integer=True))
    ax.set_xlabel("Année", fontsize=9.5, color="#555555")
    ax.set_title("Valeur du bien, dette et patrimoine net", fontsize=13, color=PRIMARY, fontfamily=TITRE, fontweight="bold", pad=10)
    ax.legend(frameon=False, fontsize=9, loc="upper center", bbox_to_anchor=(0.5, -0.16), ncol=3)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.grid(axis="y", color="#EEEEEE", linewidth=0.8)
    return _fig_to_png(fig)


def chart_saisonnalite(lignes: list[dict]) -> bytes:
    """Recettes et dépenses de chaque mois (barres), cash-flow avant impôt
    (courbe), année 1, location courte durée."""
    mois = [l["mois"] for l in lignes]
    x = range(len(mois))
    fig, ax = plt.subplots(figsize=(5.8, 3.9))
    largeur = 0.38
    ax.bar([i - largeur / 2 for i in x], [l["recettes"] for l in lignes], largeur, color=PRIMARY, label="Recettes")
    ax.bar([i + largeur / 2 for i in x], [l["depenses"] for l in lignes], largeur, color="#B8BEC4", label="Charges + crédit")
    cashflows = [l["cashflow"] for l in lignes]
    ax.plot(list(x), cashflows, color=ACCENT, linewidth=2, zorder=3, label="Cash-flow avant impôt")
    ax.scatter(list(x), cashflows, color=[PRIMARY if c >= 0 else NEGATIVE for c in cashflows], s=22, zorder=4)
    ax.axhline(0, color="#999999", linewidth=0.8)
    ax.set_xticks(list(x))
    ax.set_xticklabels(mois, fontsize=8.5, rotation=45)
    ax.yaxis.set_major_formatter(lambda v, _pos: _eur(v))
    ax.set_title("Cash-flow mois par mois (année 1)", fontsize=13, color=PRIMARY, fontfamily=TITRE, fontweight="bold", pad=10)
    ax.legend(frameon=False, fontsize=9, loc="upper center", bbox_to_anchor=(0.5, -0.2), ncol=3)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.grid(axis="y", color="#EEEEEE", linewidth=0.8)
    return _fig_to_png(fig)


def chart_marche(
    prix_m2_ventes: list[float],
    bas: float,
    mediane: float,
    haut: float,
    prix_projet: float,
    prix_revente: float | None = None,
) -> bytes:
    """Prix au m² de chaque vente comparable (points), fourchette p10–p90
    (bande), médiane, prix d'achat du projet (losange) et, en achat-revente,
    prix de revente visé (triangle)."""
    import random

    aleatoire = random.Random(0)  # dispersion verticale reproductible
    fig, ax = plt.subplots(figsize=(5.8, 3.4))
    ax.axvspan(bas, haut, color=PRIMARY, alpha=0.10, label="80 % des ventes (p10 – p90)")
    ax.scatter(
        prix_m2_ventes,
        [aleatoire.uniform(-0.35, 0.35) for _ in prix_m2_ventes],
        s=22,
        color="#8A8A8A",
        alpha=0.75,
        edgecolors="none",
        label="Ventes comparables",
    )
    ax.axvline(mediane, color=PRIMARY, linewidth=2, label=f"Médiane : {_eur(mediane)}/m²")
    couleur_projet = POSITIVE if prix_projet <= mediane * 1.03 else (ACCENT if prix_projet < mediane * 1.10 else NEGATIVE)
    ax.scatter([prix_projet], [0], marker="D", s=140, color=couleur_projet, edgecolors="white", linewidths=1.5,
               zorder=5, label=f"Achat : {_eur(prix_projet)}/m²" if prix_revente else f"Projet : {_eur(prix_projet)}/m²")
    if prix_revente:
        ax.scatter([prix_revente], [0], marker="^", s=150, color=RECETTE, edgecolors="white", linewidths=1.5,
                   zorder=5, label=f"Revente visée : {_eur(prix_revente)}/m²")
    ax.set_ylim(-0.8, 0.8)
    ax.set_yticks([])
    ax.xaxis.set_major_formatter(lambda v, _pos: _eur(v))
    ax.tick_params(axis="x", labelsize=9)
    ax.set_title("Prix au m² : le projet face aux ventes réelles", fontsize=13, color=PRIMARY, fontfamily=TITRE, fontweight="bold", pad=10)
    ax.legend(frameon=False, fontsize=8.5, loc="upper center", bbox_to_anchor=(0.5, -0.14), ncol=2)
    for cote in ("top", "right", "left"):
        ax.spines[cote].set_visible(False)
    return _fig_to_png(fig)
