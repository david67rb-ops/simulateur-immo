"""Photos du bien pour le dossier Word : préparation des photos importées
par l'utilisateur et emplacements vides à remplacer dans Word."""
from __future__ import annotations

import io
from pathlib import Path

# Toutes les photos sont recadrées au même format pour une grille régulière.
FORMAT_PHOTO = 4 / 3
LARGEUR_PHOTO_PX = 1600
NB_PHOTOS_MAX = 6
POLICES = Path(__file__).parent / "fonts"


class PhotoIllisible(ValueError):
    pass


def preparer_photo(contenu: bytes) -> bytes:
    """JPEG 1600 × 1200 recadré au centre (format 4:3), orientation de
    l'appareil appliquée : un dossier léger, quelle que soit la photo."""
    from PIL import Image, ImageOps, UnidentifiedImageError

    try:
        image = Image.open(io.BytesIO(contenu))
        image = ImageOps.exif_transpose(image).convert("RGB")
    except (UnidentifiedImageError, OSError) as exc:
        raise PhotoIllisible("Format de photo non reconnu (JPEG, PNG ou WebP attendu).") from exc
    image = ImageOps.fit(image, (LARGEUR_PHOTO_PX, round(LARGEUR_PHOTO_PX / FORMAT_PHOTO)), Image.Resampling.LANCZOS)
    sortie = io.BytesIO()
    image.save(sortie, format="JPEG", quality=85, optimize=True)
    return sortie.getvalue()


def preparer_photo_et_miniature(contenu: bytes) -> tuple[bytes, bytes]:
    """Photo pour le dossier et miniature (JPEG 320 × 240) pour l'aperçu."""
    from PIL import Image

    jpeg = preparer_photo(contenu)
    miniature = Image.open(io.BytesIO(jpeg))
    miniature.thumbnail((320, 240))
    sortie = io.BytesIO()
    miniature.save(sortie, format="JPEG", quality=80)
    return jpeg, sortie.getvalue()


def emplacement_photo() -> bytes:
    """Image d'attente (PNG 4:3) : l'utilisateur la remplace dans Word par
    clic droit > Modifier l'image, la taille et la position sont conservées."""
    from PIL import Image, ImageDraw, ImageFont

    largeur, hauteur = 1200, 900
    image = Image.new("RGB", (largeur, hauteur), "#E6ECF3")
    dessin = ImageDraw.Draw(image)
    # Cadre pointillé
    pas, trait, marge = 28, 16, 30
    for x in range(marge, largeur - marge, pas):
        for y in (marge, hauteur - marge):
            dessin.line([(x, y), (min(x + trait, largeur - marge), y)], fill="#9AA3AD", width=4)
    for y in range(marge, hauteur - marge, pas):
        for x in (marge, largeur - marge):
            dessin.line([(x, y), (x, min(y + trait, hauteur - marge))], fill="#9AA3AD", width=4)
    # Pictogramme d'appareil photo
    cx, cy = largeur // 2, hauteur // 2 - 90
    dessin.rounded_rectangle([cx - 110, cy - 65, cx + 110, cy + 85], radius=22, outline="#1B3358", width=10)
    dessin.rounded_rectangle([cx - 45, cy - 95, cx + 45, cy - 60], radius=10, fill="#1B3358")
    dessin.ellipse([cx - 48, cy - 38, cx + 48, cy + 58], outline="#A8823B", width=10)
    titre = ImageFont.truetype(str(POLICES / "Sora-SemiBold.ttf"), 54)
    aide = ImageFont.truetype(str(POLICES / "PublicSans-Regular.ttf"), 38)
    dessin.text((cx, cy + 170), "Photo du bien", font=titre, fill="#1B3358", anchor="mm")
    dessin.text((cx, cy + 250), "Clic droit › Modifier l'image", font=aide, fill="#5B6672", anchor="mm")
    sortie = io.BytesIO()
    image.save(sortie, format="PNG", optimize=True)
    return sortie.getvalue()
