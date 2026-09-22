"""Extraction best-effort d'informations (adresse, prix, surface...) à partir
du lien d'une annonce immobilière.

Limite importante : les grands portails (SeLoger, LeBonCoin, PAP...)
protègent systématiquement leurs pages contre la récupération automatique
(Cloudflare, DataDome...). Cette app ne cherche PAS à contourner ces
protections (captcha, challenge JS) : si le site bloque la requête, on le
signale clairement à l'utilisateur au lieu de renvoyer un résultat
partiel/faux. Ça fonctionne mieux sur les sites d'agences indépendantes,
notaires, ou annonces sans protection anti-robot.
"""
from __future__ import annotations

import json
import re

import httpx

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    ),
    "Accept-Language": "fr-FR,fr;q=0.9",
}

SIGNATURES_PROTECTION = [
    "captcha-delivery.com",
    "Just a moment",
    "cf-browser-verification",
    "Please enable JS and disable any ad blocker",
    "Pardon Our Interruption",
]


class ListingParseError(Exception):
    pass


def _mot_cle_type_bien(texte: str) -> str | None:
    t = texte.lower()
    if "maison" in t or "villa" in t or "pavillon" in t:
        return "maison"
    if "appartement" in t or "studio" in t or "duplex" in t:
        return "appartement"
    return None


def _parse_prix(texte: str) -> float | None:
    match = re.search(r"([\d][\d\s .]{2,})\s?€", texte)
    if not match:
        return None
    brut = match.group(1).replace(" ", "").replace(" ", "").replace(".", "")
    try:
        return float(brut)
    except ValueError:
        return None


def _parse_surface(texte: str) -> float | None:
    match = re.search(r"(\d+(?:[.,]\d+)?)\s?m(?:²|2)\b", texte)
    if not match:
        return None
    return float(match.group(1).replace(",", "."))


def _parse_nb_pieces(texte: str) -> int | None:
    match = re.search(r"(\d+)\s?pi[eè]ces?", texte, re.IGNORECASE)
    return int(match.group(1)) if match else None


def _parse_code_postal(texte: str) -> str | None:
    match = re.search(r"\b(\d{5})\b", texte)
    return match.group(1) if match else None


MOTS_VIDES_SLUG = {
    "vente", "achat", "location", "appartement", "maison", "studio",
    "duplex", "villa", "t1", "t2", "t3", "t4", "t5", "t6", "pieces",
    "piece", "www", "com", "fr", "html", "htm",
}


def _parse_adresse_depuis_url(url: str) -> str | None:
    """Heuristique sur les slugs SEO du type .../vente-appartement-t3-lyon-9-69009-xxxx/."""
    slug = re.sub(r"^https?://[^/]+/", "", url)
    tokens = re.split(r"[/_-]", slug)
    for i, tok in enumerate(tokens):
        if re.fullmatch(r"\d{5}", tok):
            debut = i
            while debut > 0 and (
                tokens[debut - 1].isalpha() or tokens[debut - 1].isdigit()
            ) and tokens[debut - 1].lower() not in MOTS_VIDES_SLUG:
                debut -= 1
            morceaux = [t for t in tokens[debut:i] if t.lower() not in MOTS_VIDES_SLUG]
            ville = " ".join(morceaux).strip()
            if ville:
                return f"{tok} {ville}".strip()
            return tok
    return None


def _extraire_json_ld(html: str) -> dict:
    resultat: dict = {}
    for match in re.finditer(
        r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
        html,
        re.DOTALL | re.IGNORECASE,
    ):
        try:
            data = json.loads(match.group(1).strip())
        except (json.JSONDecodeError, ValueError):
            continue
        candidats = data if isinstance(data, list) else [data]
        for c in candidats:
            if not isinstance(c, dict):
                continue
            offers = c.get("offers")
            if isinstance(offers, dict) and offers.get("price"):
                resultat.setdefault("prix_achat", float(offers["price"]))
            if isinstance(c.get("address"), dict):
                addr = c["address"]
                morceaux = [
                    addr.get("streetAddress"),
                    addr.get("postalCode"),
                    addr.get("addressLocality"),
                ]
                resultat.setdefault(
                    "adresse", " ".join(m for m in morceaux if m)
                )
            if c.get("name"):
                resultat.setdefault("titre", c["name"])
    return resultat


def _extraire_meta_og(html: str) -> dict:
    resultat = {}
    for prop in ("og:title", "og:description"):
        match = re.search(
            rf'<meta[^>]+property=["\']{prop}["\'][^>]+content=["\']([^"\']*)["\']',
            html,
            re.IGNORECASE,
        )
        if match:
            resultat[prop] = match.group(1)
    return resultat


async def extraire_infos_annonce(url: str) -> dict:
    async with httpx.AsyncClient(timeout=15, follow_redirects=True, headers=HEADERS) as client:
        try:
            resp = await client.get(url)
        except httpx.HTTPError as exc:
            raise ListingParseError(f"Impossible d'accéder à cette page : {exc}") from exc

    html = resp.text
    if resp.status_code != 200 or any(sig in html for sig in SIGNATURES_PROTECTION):
        raise ListingParseError(
            "Ce site protège ses annonces contre la récupération automatique "
            "(anti-robot). Merci de renseigner les champs manuellement à "
            "partir de l'annonce."
        )

    donnees = _extraire_json_ld(html)
    meta = _extraire_meta_og(html)
    texte_reference = " ".join(
        [donnees.get("titre", ""), meta.get("og:title", ""), meta.get("og:description", "")]
    )

    if "prix_achat" not in donnees:
        prix = _parse_prix(texte_reference) or _parse_prix(html[:5000])
        if prix:
            donnees["prix_achat"] = prix

    surface = _parse_surface(texte_reference)
    if surface:
        donnees["surface_m2"] = surface

    nb_pieces = _parse_nb_pieces(texte_reference)
    if nb_pieces:
        donnees["nb_pieces"] = nb_pieces

    type_bien = _mot_cle_type_bien(texte_reference)
    if type_bien:
        donnees["type_bien"] = type_bien

    if "adresse" not in donnees or not donnees["adresse"].strip():
        adresse_url = _parse_adresse_depuis_url(url)
        if adresse_url:
            donnees["adresse"] = adresse_url
        else:
            code_postal = _parse_code_postal(texte_reference)
            if code_postal:
                donnees["adresse"] = f"{code_postal} " + texte_reference[:60]

    champs_trouves = [
        k for k in ("adresse", "prix_achat", "surface_m2", "type_bien") if donnees.get(k)
    ]
    if not champs_trouves:
        raise ListingParseError(
            "Aucune information exploitable n'a pu être extraite de cette page. "
            "Merci de renseigner les champs manuellement."
        )

    donnees["champs_manquants"] = [
        k for k in ("adresse", "prix_achat", "surface_m2") if not donnees.get(k)
    ]
    return donnees
