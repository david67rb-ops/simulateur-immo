"""Fichier projet signé (.credaura) : l'utilisateur garde son projet sur son
propre appareil (rien n'est conservé sur le serveur) et le rouvre plus tard.

La signature (HMAC-SHA256) prouve que le fichier vient de Credaura et n'a pas
été retouché. Elle couvre aussi l'identifiant du dossier et sa date limite :
pendant 30 jours après l'ouverture d'un dossier avec un code, ce même dossier
se modifie et se retélécharge sans consommer de nouveau code.

Clé de signature : IMMO_SIGNATURE_SECRET (à définir sur le serveur avant
l'ouverture de la vente ; la clé de développement ne protège rien)."""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import secrets
from datetime import date, timedelta

FORMAT = "credaura-projet"
VERSION = 1
MODIFICATION_JOURS = 30
CLE_DEV = "credaura-cle-de-developpement"


class FichierProjetInvalide(Exception):
    pass


def _cle() -> bytes:
    return (os.environ.get("IMMO_SIGNATURE_SECRET") or os.environ.get("IMMO_STORAGE_SECRET") or CLE_DEV).encode()


def nouvel_identifiant() -> str:
    return secrets.token_urlsafe(12)


def _signer(contenu: dict) -> str:
    brut = json.dumps(contenu, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()
    return base64.urlsafe_b64encode(hmac.new(_cle(), brut, hashlib.sha256).digest()).decode()


def exporter(etat: dict, dossier_id: str, modifiable_jusqu_au: str | None, aujourd_hui: date | None = None) -> bytes:
    """`modifiable_jusqu_au` : date ISO jusqu'à laquelle le dossier se
    retélécharge sans nouveau code (None : aucun dossier ouvert)."""
    contenu = {
        "format": FORMAT,
        "version": VERSION,
        "enregistre_le": (aujourd_hui or date.today()).isoformat(),
        "dossier_id": dossier_id,
        "modifiable_jusqu_au": modifiable_jusqu_au,
        "etat": etat,
    }
    contenu["signature"] = _signer(contenu)
    return json.dumps(contenu, ensure_ascii=False, indent=1).encode()


def importer(donnees: bytes) -> dict:
    """Le contenu vérifié (format, version, signature), sinon
    FichierProjetInvalide avec une explication lisible."""
    try:
        contenu = json.loads(donnees.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise FichierProjetInvalide("Ce fichier n'est pas un projet Credaura.") from exc
    if not isinstance(contenu, dict) or contenu.get("format") != FORMAT:
        raise FichierProjetInvalide("Ce fichier n'est pas un projet Credaura.")
    if contenu.get("version") != VERSION:
        raise FichierProjetInvalide("Ce projet a été enregistré avec une autre version de Credaura.")
    signature = contenu.pop("signature", "")
    if not hmac.compare_digest(signature, _signer(contenu)):
        raise FichierProjetInvalide("Ce fichier a été modifié après son enregistrement : il ne peut pas être rouvert.")
    return contenu


def limite_modification(aujourd_hui: date | None = None) -> str:
    return ((aujourd_hui or date.today()) + timedelta(days=MODIFICATION_JOURS)).isoformat()


def encore_modifiable(contenu: dict, aujourd_hui: date | None = None) -> bool:
    limite = contenu.get("modifiable_jusqu_au")
    return bool(limite) and (aujourd_hui or date.today()).isoformat() <= limite
