"""Petits visuels du dossier Word, dessinés en images (PNG) pour un rendu
identique dans Word, LibreOffice et l'aperçu du navigateur :

- icône de chapitre (police Material Icons, comme le simulateur) ;
- fil des parties en tête de page (parties passées cochées, partie en cours
  mise en avant, comme la frise d'étapes du simulateur) ;
- jauge horizontale avec seuil (taux d'endettement…) ;
- logo Credaura (couverture du rapport, icône de l'application)."""
from __future__ import annotations

import io
from functools import lru_cache
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

POLICES = Path(__file__).parent / "fonts"
MARQUE, LAITON, VERT, ROUGE, ORANGE = "#1B3358", "#A8823B", "#2D6A4F", "#B23A32", "#B7791F"
LAITON_CLAIR = "#C9A45E"  # laiton éclairci, lisible sur le bleu notaire
GRIS, GRIS_CLAIR, TEXTE = "#5B6672", "#DDE3EA", "#1F2833"
SURECH = 4  # suréchantillonnage : bords nets une fois l'image réduite par Word

# Points de code Material Icons (font/MaterialIcons-Regular.codepoints).
ICONES = {
    "place": 0xE55F,
    "photo_camera": 0xE412,
    "query_stats": 0xE4FC,
    "home": 0xE88A,
    "payments": 0xEF63,
    "calendar_month": 0xEBCC,
    "trending_up": 0xE8E5,
    "swap_horiz": 0xE8D4,
    "account_balance": 0xE84F,
    "person": 0xE7FD,
    "speed": 0xE9E4,
    "warning": 0xE002,
    "dashboard": 0xE871,
    "checklist": 0xE6B1,
    "gavel": 0xE90E,
    "price_check": 0xF04B,
    "receipt_long": 0xEF6E,
    "account_balance_wallet": 0xE850,
    "show_chart": 0xE6E1,
    "fact_check": 0xF0C5,
    "info": 0xE88E,
}


def _police(nom: str, taille: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(POLICES / nom), taille)


def _png(image: Image.Image, largeur: int, hauteur: int) -> bytes:
    sortie = io.BytesIO()
    image.resize((largeur, hauteur), Image.LANCZOS).save(sortie, format="PNG", optimize=True)
    return sortie.getvalue()


@lru_cache(maxsize=64)
def icone(nom: str, couleur: str = LAITON, taille: int = 96) -> bytes:
    """Icône carrée sur fond transparent."""
    t = taille * SURECH
    image = Image.new("RGBA", (t, t), (0, 0, 0, 0))
    dessin = ImageDraw.Draw(image)
    police = _police("MaterialIcons-Regular.ttf", int(t * 0.92))
    dessin.text((t / 2, t / 2), chr(ICONES[nom]), font=police, fill=couleur, anchor="mm")
    return _png(image, taille, taille)


@lru_cache(maxsize=32)
def fil_parties(parties: tuple[str, ...], courante: str) -> bytes:
    """Fil des parties du dossier : passées (rond vert coché), en cours (rond
    bleu plein, nom en gras), à venir (rond vide gris)."""
    h = 34 * SURECH
    rayon = 10 * SURECH
    police = _police("PublicSans-Regular.ttf", 19 * SURECH)
    police_gras = _police("PublicSans-SemiBold.ttf", 19 * SURECH)
    trait, ecart = 30 * SURECH, 8 * SURECH
    # Largeur totale : ronds, noms et traits.
    mesure = ImageDraw.Draw(Image.new("RGB", (1, 1)))
    largeurs = [mesure.textlength(p, font=police_gras if p == courante else police) for p in parties]
    largeur = int(sum(2 * rayon + ecart + l for l in largeurs) + trait * (len(parties) - 1) + 2 * ecart * (len(parties) - 1) + 4)
    image = Image.new("RGBA", (largeur, h), (0, 0, 0, 0))
    dessin = ImageDraw.Draw(image)
    rang = parties.index(courante)
    x, y = 2, h / 2
    for i, (partie, l) in enumerate(zip(parties, largeurs)):
        if i:
            couleur_trait = VERT if i <= rang else GRIS_CLAIR
            dessin.line([(x, y), (x + trait, y)], fill=couleur_trait, width=2 * SURECH)
            x += trait + ecart
        boite = [x, y - rayon, x + 2 * rayon, y + rayon]
        if i < rang:
            dessin.ellipse(boite, fill=VERT)
            # coche
            dessin.line(
                [(x + rayon * 0.55, y), (x + rayon * 0.9, y + rayon * 0.4), (x + rayon * 1.5, y - rayon * 0.4)],
                fill="white",
                width=int(2.2 * SURECH),
                joint="curve",
            )
            couleur_texte, fnt = VERT, police
        elif i == rang:
            dessin.ellipse(boite, fill=MARQUE)
            couleur_texte, fnt = MARQUE, police_gras
        else:
            dessin.ellipse(boite, outline="#9AA3AD", width=int(1.6 * SURECH))
            couleur_texte, fnt = "#8A939C", police
        x += 2 * rayon + ecart
        dessin.text((x, y), partie, font=fnt, fill=couleur_texte, anchor="lm")
        x += l + ecart
    return _png(image, largeur // 2, h // 2)  # double résolution : net une fois réduit par Word


def jauge(
    valeur: float,
    maximum: float,
    couleur: str,
    texte_valeur: str,
    libelle: str,
    seuil: float | None = None,
    texte_seuil: str = "",
    texte_min: str = "",
    texte_max: str = "",
    largeur_px: int = 520,
) -> bytes:
    """Jauge horizontale : libellé et valeur au-dessus, barre remplie jusqu'à
    `valeur` (sur une échelle de 0 à `maximum`), repère au `seuil`, bornes et
    seuil légendés en dessous."""
    s = SURECH
    w, h = largeur_px * s, 92 * s
    image = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    dessin = ImageDraw.Draw(image)
    police = _police("PublicSans-Regular.ttf", 20 * s)
    police_valeur = _police("Sora-SemiBold.ttf", 26 * s)
    petite = _police("PublicSans-Regular.ttf", 16 * s)
    dessin.text((0, 16 * s), libelle, font=police, fill=GRIS, anchor="lm")
    dessin.text((w, 16 * s), texte_valeur, font=police_valeur, fill=couleur, anchor="rm")
    haut, bas = 38 * s, 54 * s
    dessin.rounded_rectangle([0, haut, w, bas], radius=6 * s, fill=GRIS_CLAIR)
    fraction = max(0.0, min(valeur / maximum, 1.0)) if maximum else 0
    if fraction > 0:
        dessin.rounded_rectangle([0, haut, max(int(w * fraction), 12 * s), bas], radius=6 * s, fill=couleur)
    if seuil is not None:
        xs = int(w * min(seuil / maximum, 1.0))
        dessin.rectangle([xs - int(1.5 * s), haut - 6 * s, xs + int(1.5 * s), bas + 6 * s], fill=MARQUE)
        dessin.text((xs, 76 * s), texte_seuil, font=petite, fill=MARQUE, anchor="mm")
    dessin.text((0, 76 * s), texte_min, font=petite, fill="#8A939C", anchor="lm")
    dessin.text((w, 76 * s), texte_max, font=petite, fill="#8A939C", anchor="rm")
    return _png(image, largeur_px * 2, 92 * 2)


@lru_cache(maxsize=16)
def logo(taille: int = 256, laiton: str = LAITON) -> bytes:
    """Logo Credaura (maison dans un sceau d'or), mêmes proportions que le SVG
    de l'interface (gui/theme.LOGO_SVG, repère 64 × 64)."""
    s = taille * SURECH / 64
    image = Image.new("RGBA", (taille * SURECH,) * 2, (0, 0, 0, 0))
    dessin = ImageDraw.Draw(image)
    dessin.rounded_rectangle([0, 0, 64 * s - 1, 64 * s - 1], radius=15 * s, fill=MARQUE)
    r, e = 23 * s, 2.4 * s
    dessin.ellipse([32 * s - r - e / 2, 32.5 * s - r - e / 2, 32 * s + r + e / 2, 32.5 * s + r + e / 2], outline=laiton, width=round(e))
    dessin.polygon([(32 * s, 19 * s), (44.5 * s, 29.5 * s), (44.5 * s, 43.5 * s), (19.5 * s, 43.5 * s), (19.5 * s, 29.5 * s)], fill="white")
    dessin.rounded_rectangle([28.8 * s, 35 * s, 35.2 * s, 43.5 * s], radius=0.8 * s, fill=MARQUE)
    return _png(image, taille, taille)


@lru_cache(maxsize=64)
def pave_numero(numero: int, taille: int = 200) -> bytes:
    """Numéro de chapitre dans un carré bleu notaire aux coins arrondis (Word
    ne sait pas arrondir les angles d'une cellule de tableau)."""
    t = taille * SURECH
    image = Image.new("RGBA", (t, t), (0, 0, 0, 0))
    dessin = ImageDraw.Draw(image)
    dessin.rounded_rectangle([0, 0, t - 1, t - 1], radius=int(t * 0.22), fill=MARQUE)
    police = _police("Sora-SemiBold.ttf", int(t * 0.46))
    dessin.text((t / 2, t / 2), f"{numero:02d}", font=police, fill="#E9D8B0", anchor="mm")
    return _png(image, taille, taille)
