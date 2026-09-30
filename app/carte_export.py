"""Cartes du dossier Word (images PNG), équivalentes à celles de l'onglet
Marché :

- autour du bien : le bien, le rayon de recherche et les ventes comparables
  colorées selon leur prix au m² par rapport à la médiane, sur fond Plan IGN ;
- rentabilité brute des communes du département (carte choroplèthe).

Fond de carte : Géoplateforme IGN (WMTS, Web Mercator, licence ouverte
Etalab), tuiles mises en cache sur disque. Sans réseau, la carte est tracée
sur fond uni."""
from __future__ import annotations

import io
import math
from concurrent.futures import ThreadPoolExecutor

import httpx
from matplotlib.collections import PolyCollection
from matplotlib.lines import Line2D
from matplotlib.patches import Circle, Patch

from . import charts_export as charts
from .charts_export import plt
from .donnees_marche import COULEUR_SANS_DONNEE, ECHELLE_RENDEMENT, MIN_VENTES_CARTE
from .market_data import CACHE_DIR

URL_TUILES = (
    "https://data.geopf.fr/wmts?SERVICE=WMTS&REQUEST=GetTile&VERSION=1.0.0"
    "&LAYER=GEOGRAPHICALGRIDSYSTEMS.PLANIGNV2&STYLE=normal&TILEMATRIXSET=PM"
    "&TILEMATRIX={z}&TILEROW={y}&TILECOL={x}&FORMAT=image/png"
)
TAILLE_TUILE = 256
CACHE_TUILES = CACHE_DIR / "tuiles_ign"
# Mêmes couleurs que la carte de l'onglet Marché (gui/cartes.py).
VERT, GRIS, ROUGE, BIEN = "#2d6a4f", "#9aa3ad", "#b23a32", "#a8823b"


def _pixels(lat: float, lon: float, zoom: int) -> tuple[float, float]:
    """Coordonnées pixel Web Mercator au niveau de zoom donné."""
    n = TAILLE_TUILE * 2**zoom
    lat_rad = math.radians(lat)
    x = (lon + 180) / 360 * n
    y = (1 - math.log(math.tan(lat_rad) + 1 / math.cos(lat_rad)) / math.pi) / 2 * n
    return x, y


def _tuile(client: httpx.Client, z: int, x: int, y: int) -> bytes | None:
    fichier = CACHE_TUILES / str(z) / str(x) / f"{y}.png"
    if fichier.exists():
        return fichier.read_bytes()
    try:
        resp = client.get(URL_TUILES.format(z=z, x=x, y=y))
        resp.raise_for_status()
    except httpx.HTTPError:
        return None
    fichier.parent.mkdir(parents=True, exist_ok=True)
    fichier.write_bytes(resp.content)
    return resp.content


def _fond_de_carte(x0: float, y0: float, largeur: int, hauteur: int, zoom: int):
    """Image (Pillow) du Plan IGN couvrant la fenêtre pixel (x0, y0, largeur,
    hauteur), éclaircie et désaturée pour faire ressortir les points. None si
    les tuiles sont inaccessibles."""
    from PIL import Image, ImageEnhance

    tx0, ty0 = int(x0 // TAILLE_TUILE), int(y0 // TAILLE_TUILE)
    tx1, ty1 = int((x0 + largeur) // TAILLE_TUILE), int((y0 + hauteur) // TAILLE_TUILE)
    positions = [(tx, ty) for tx in range(tx0, tx1 + 1) for ty in range(ty0, ty1 + 1)]
    with httpx.Client(timeout=10, headers={"User-Agent": "Fiabimmo (dossier de financement)"}) as client:
        with ThreadPoolExecutor(max_workers=8) as pool:
            contenus = list(pool.map(lambda p: _tuile(client, zoom, *p), positions))
    if not any(contenus):
        return None
    mosaique = Image.new("RGB", ((tx1 - tx0 + 1) * TAILLE_TUILE, (ty1 - ty0 + 1) * TAILLE_TUILE), "#f2f2ef")
    for (tx, ty), contenu in zip(positions, contenus):
        if contenu:
            tuile = Image.open(io.BytesIO(contenu)).convert("RGB")
            mosaique.paste(tuile, ((tx - tx0) * TAILLE_TUILE, (ty - ty0) * TAILLE_TUILE))
    gauche, haut = round(x0 - tx0 * TAILLE_TUILE), round(y0 - ty0 * TAILLE_TUILE)
    fond = mosaique.crop((gauche, haut, gauche + largeur, haut + hauteur))
    fond = ImageEnhance.Color(fond).enhance(0.35)
    return Image.blend(fond, Image.new("RGB", fond.size, "white"), 0.25)


def _titre(ax, texte: str) -> None:
    ax.set_title(texte, fontsize=13, color=charts.PRIMARY, fontfamily=charts.TITRE, fontweight="bold", pad=10)


def carte_ventes(lat: float, lon: float, comparables: dict, taille_cm: tuple[float, float] = (12.4, 10.2)) -> bytes:
    """Le bien, le cercle du rayon de recherche et les ventes comparables."""
    rayon = comparables["rayon_utilise"]
    mediane = comparables["prix_m2_moyen"]
    largeur_px = round(taille_cm[0] / 2.54 * 200)
    hauteur_px = round(taille_cm[1] / 2.54 * 200)
    # Zoom le plus fin (résolution des tuiles) pour lequel le cercle et une
    # marge de 15 % tiennent dans l'image ; l'image est ensuite mise à
    # l'échelle exacte.
    metres_par_pixel_z0 = 156_543.03 * math.cos(math.radians(lat))
    etendue_m = 2 * rayon * 1.15
    zoom = max(1, min(17, math.floor(math.log2(metres_par_pixel_z0 * min(largeur_px, hauteur_px) / etendue_m))))
    echelle_mpp = metres_par_pixel_z0 / 2**zoom
    # Fenêtre en pixels au zoom retenu, centrée sur le bien.
    cote_px = etendue_m / echelle_mpp
    rapport = largeur_px / hauteur_px
    fen_l, fen_h = (cote_px * rapport, cote_px) if rapport >= 1 else (cote_px, cote_px / rapport)
    cx, cy = _pixels(lat, lon, zoom)
    x0, y0 = cx - fen_l / 2, cy - fen_h / 2

    fig, ax = plt.subplots(figsize=(taille_cm[0] / 2.54, taille_cm[1] / 2.54))
    fond = _fond_de_carte(x0, y0, math.ceil(fen_l), math.ceil(fen_h), zoom)
    if fond is not None:
        ax.imshow(fond, extent=(0, fond.width, fond.height, 0), interpolation="lanczos")
    else:
        ax.set_facecolor("#f2f2ef")
    ax.set_xlim(0, fen_l)
    ax.set_ylim(fen_h, 0)
    ax.add_patch(Circle((cx - x0, cy - y0), rayon / echelle_mpp, facecolor=VERT, alpha=0.06, edgecolor=VERT, linewidth=1.2))
    for v in comparables.get("ventes") or []:
        ecart = v["prix_m2"] / mediane - 1
        couleur = VERT if ecart <= -0.10 else (ROUGE if ecart >= 0.10 else GRIS)
        x, y = _pixels(v["lat"], v["lon"], zoom)
        ax.scatter([x - x0], [y - y0], s=34, color=couleur, edgecolors="white", linewidths=0.8, zorder=3)
    ax.scatter([cx - x0], [cy - y0], s=150, color=BIEN, edgecolors="white", linewidths=2, zorder=4, marker="o")
    ax.set_xticks([])
    ax.set_yticks([])
    for cote in ax.spines.values():
        cote.set_edgecolor("#CCCCCC")
    rayon_txt = f"{rayon / 1000:g} km".replace(".", ",") if rayon >= 1000 else f"{rayon} m"
    _titre(ax, f"Ventes comparables dans un rayon de {rayon_txt}")
    ax.text(0.99, 0.01, "Fond : © IGN – Plan IGN", transform=ax.transAxes, ha="right", va="bottom", fontsize=6.5,
            color="#555555", bbox={"facecolor": "white", "alpha": 0.7, "edgecolor": "none", "pad": 1.5})
    legende = [
        Line2D([], [], marker="o", linestyle="", markersize=9, color=BIEN, markeredgecolor="white", label="Le bien"),
        Line2D([], [], marker="o", linestyle="", markersize=6, color=VERT, markeredgecolor="white", label="10 % ou plus sous la médiane"),
        Line2D([], [], marker="o", linestyle="", markersize=6, color=GRIS, markeredgecolor="white", label="Proche de la médiane"),
        Line2D([], [], marker="o", linestyle="", markersize=6, color=ROUGE, markeredgecolor="white", label="10 % ou plus au-dessus"),
    ]
    ax.legend(handles=legende, frameon=False, fontsize=8, loc="upper center", bbox_to_anchor=(0.5, -0.02), ncol=2)
    return charts._fig_to_png(fig)


def _mercator(lon: float, lat: float) -> tuple[float, float]:
    x, y = _pixels(lat, lon, 0)
    return x, -y  # y vers le haut pour matplotlib


def _anneaux(geometrie: dict) -> list[list[list[float]]]:
    if geometrie["type"] == "Polygon":
        return geometrie["coordinates"][:1]
    if geometrie["type"] == "MultiPolygon":
        return [polygone[0] for polygone in geometrie["coordinates"]]
    return []


def carte_rentabilite(geojson: dict, lat: float, lon: float, code_commune: str | None = None,
                      taille_cm: tuple[float, float] = (12.4, 10.2)) -> bytes:
    """Rentabilité brute de chaque commune du département (couleurs de la
    légende de l'onglet Marché), commune du bien soulignée."""
    polygones, couleurs, commune_bien = [], [], []
    for feature in geojson["features"]:
        props = feature["properties"]
        for anneau in _anneaux(feature["geometry"]):
            points = [_mercator(x, y) for x, y in anneau]
            polygones.append(points)
            couleurs.append(props.get("couleur") or COULEUR_SANS_DONNEE)
            if code_commune and props.get("code") == code_commune:
                commune_bien.append(points)

    fig, ax = plt.subplots(figsize=(taille_cm[0] / 2.54, taille_cm[1] / 2.54))
    ax.add_collection(PolyCollection(polygones, facecolors=couleurs, edgecolors="white", linewidths=0.3, alpha=0.9))
    if commune_bien:
        ax.add_collection(PolyCollection(commune_bien, facecolors="none", edgecolors=charts.PRIMARY, linewidths=1.6))
    bx, by = _mercator(lon, lat)
    ax.scatter([bx], [by], s=110, color=BIEN, edgecolors="white", linewidths=1.8, zorder=4)
    ax.autoscale_view()
    ax.set_aspect("equal")
    ax.axis("off")
    _titre(ax, "Rentabilité brute des communes du département")
    legende = [Patch(facecolor=couleur, label=libelle) for _, couleur, libelle in ECHELLE_RENDEMENT]
    legende.append(Patch(facecolor=COULEUR_SANS_DONNEE, label=f"Moins de {MIN_VENTES_CARTE} ventes"))
    legende.append(Line2D([], [], marker="o", linestyle="", markersize=8, color=BIEN, markeredgecolor="white", label="Le bien"))
    ax.legend(handles=legende, frameon=False, fontsize=7.5, loc="upper center", bbox_to_anchor=(0.5, 0.0), ncol=5,
              handlelength=1.2, columnspacing=0.9)
    return charts._fig_to_png(fig)
