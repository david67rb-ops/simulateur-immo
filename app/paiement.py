"""Paiement des dossiers par Stripe Checkout (page de paiement hébergée par
Stripe : carte, Apple Pay, Google Pay).

Parcours :
1. Dans l'étape Dossier, un vrai lien ouvre /paiement/commander dans un nouvel
   onglet (le simulateur reste ouvert dans le sien) ; le serveur y crée une
   session Checkout pour le lot choisi et redirige vers Stripe.
2. Une fois le paiement fait, Stripe renvoie sur /paiement/merci, qui affiche
   le code de dossier. En parallèle, le webhook /stripe/webhook confirme le
   paiement même si l'acheteur ferme l'onglet avant la redirection.
3. L'onglet du simulateur interroge le serveur toutes les quelques secondes et
   ouvre le dossier tout seul dès que le code existe.

Un seul code par session de paiement (app.codes.code_du_paiement), quel que
soit le chemin qui confirme en premier. Aucune donnée personnelle côté
Credaura : Stripe garde l'e-mail et la carte, Credaura l'identifiant de la
session, le lot et le code. Le code est aussi noté dans les métadonnées du
paiement chez Stripe, pour le retrouver si un acheteur l'a perdu.

Variables d'environnement (serveur) :
- IMMO_STRIPE_CLE_SECRETE : clé secrète (sk_test_… en test, sk_live_… en réel).
  Sans elle, le paiement est désactivé et aucun bouton d'achat n'apparaît.
- IMMO_STRIPE_SECRET_WEBHOOK : secret de signature du webhook (whsec_…).
- IMMO_URL_SITE : adresse publique du site (https://credaura.fr), pour les
  adresses de retour depuis Stripe ; à défaut, celle de la requête.
- IMMO_STRIPE_CGV=1 : case « J'accepte les CGV » sur la page Stripe (l'adresse
  des CGV se règle dans le tableau de bord Stripe, Paramètres > Public).
- IMMO_STRIPE_FACTURES=1 : facture PDF envoyée par Stripe après l'achat.
"""
from __future__ import annotations

import asyncio
import hashlib
import hmac
import logging
import os
import re
import secrets
import time

import httpx

from app import codes

log = logging.getLogger(__name__)

# Prix TTC en centimes (franchise de TVA : pas de TVA facturée).
LOTS: dict[int, int] = {1: 1990, 2: 3490, 3: 4490}

# Adresse de l'API : remplacée seulement par les tests (faux serveur Stripe).
API = os.environ.get("IMMO_STRIPE_API", "https://api.stripe.com")

EVENEMENTS_PAYES = ("checkout.session.completed", "checkout.session.async_payment_succeeded")
TOLERANCE_SIGNATURE_S = 300
# Une session Checkout expire au bout de 31 minutes (minimum Stripe : 30) ;
# l'onglet du simulateur guette le paiement pendant 30 minutes.
DUREE_SESSION_S = 31 * 60
REUTILISATION_SESSION_S = 25 * 60
# Pendant que l'onglet guette, Stripe n'est interrogé qu'une fois toutes les
# 15 secondes par session (le webhook, lui, arrive tout de suite).
INTERVALLE_VERIFICATION_S = 15.0
_dernieres_verifications: dict[str, float] = {}
_taches: set[asyncio.Task] = set()

_FORMAT_ACHAT = re.compile(r"^[A-Za-z0-9_-]{16,64}$")
_FORMAT_SESSION = re.compile(r"^cs_[A-Za-z0-9_]{8,250}$")

# Remplacé par les tests (httpx.MockTransport) ; None = réseau réel.
_transport: httpx.AsyncBaseTransport | None = None


class ErreurPaiement(Exception):
    """Stripe injoignable ou requête refusée : message destiné aux journaux.
    statut : code HTTP renvoyé par Stripe (None si Stripe est injoignable)."""

    def __init__(self, message: str, statut: int | None = None) -> None:
        super().__init__(message)
        self.statut = statut

    @property
    def definitive(self) -> bool:
        """Requête refusée (session inconnue…) : inutile de réessayer."""
        return self.statut is not None and 400 <= self.statut < 500 and self.statut != 429


def cle_secrete() -> str:
    return os.environ.get("IMMO_STRIPE_CLE_SECRETE", "").strip()


def secret_webhook() -> str:
    return os.environ.get("IMMO_STRIPE_SECRET_WEBHOOK", "").strip()


def actif() -> bool:
    return bool(cle_secrete())


def mode_test() -> bool:
    return cle_secrete().startswith(("sk_test_", "rk_test_"))


def libelle_lot(lot: int) -> str:
    return f"{lot} dossier{'s' if lot > 1 else ''} de financement"


def prix_lot(lot: int) -> str:
    """1990 → « 19,90 € »."""
    euros, centimes = divmod(LOTS[lot], 100)
    return f"{euros},{centimes:02d} €"


def nouvel_achat_id() -> str:
    """Relie un onglet du simulateur à ses sessions de paiement. Secret : qui
    le connaît peut lire le code acheté, il ne sort donc que dans le lien
    d'achat de cet onglet."""
    return secrets.token_urlsafe(16)


def achat_id_valide(achat_id: str) -> bool:
    return bool(_FORMAT_ACHAT.match(achat_id or ""))


def session_id_valide(session_id: str) -> bool:
    return bool(_FORMAT_SESSION.match(session_id or ""))


# ---------------------------------------------------------------------------
# Appels à l'API Stripe
# ---------------------------------------------------------------------------
def _client() -> httpx.AsyncClient:
    return httpx.AsyncClient(base_url=API, auth=(cle_secrete(), ""), timeout=20.0, transport=_transport)


async def _appel(methode: str, chemin: str, donnees: dict | None = None) -> dict:
    if not actif():
        raise ErreurPaiement("Paiement désactivé : IMMO_STRIPE_CLE_SECRETE n'est pas définie.")
    try:
        async with _client() as client:
            reponse = await client.request(methode, chemin, data=donnees)
    except httpx.HTTPError as exc:
        raise ErreurPaiement(f"Stripe injoignable : {exc}") from exc
    try:
        corps = reponse.json()
    except ValueError:
        corps = {}
    if reponse.status_code >= 400:
        message = (corps.get("error") or {}).get("message") or reponse.text[:300]
        raise ErreurPaiement(
            f"Stripe a refusé {methode} {chemin} ({reponse.status_code}) : {message}", statut=reponse.status_code
        )
    return corps


def parametres_session(lot: int, achat_id: str, base_url: str) -> dict[str, str]:
    """Paramètres de la session Checkout, au format attendu par l'API."""
    montant = LOTS[lot]
    libelle = libelle_lot(lot)
    base = base_url.rstrip("/")
    donnees = {
        "mode": "payment",
        "locale": "fr",
        "submit_type": "pay",
        # La carte inclut Apple Pay et Google Pay quand l'appareil les propose ;
        # que des moyens immédiats, pour livrer le code tout de suite.
        "payment_method_types[0]": "card",
        "line_items[0][quantity]": "1",
        "line_items[0][price_data][currency]": "eur",
        "line_items[0][price_data][unit_amount]": str(montant),
        "line_items[0][price_data][product_data][name]": f"Credaura · {libelle}",
        "line_items[0][price_data][product_data][description]": (
            "Code de dossier valable 12 mois. Chaque dossier se modifie et se retélécharge "
            "pendant 30 jours pour le même bien."
        ),
        "success_url": f"{base}/paiement/merci?session_id={{CHECKOUT_SESSION_ID}}",
        "cancel_url": f"{base}/paiement/annule",
        "client_reference_id": achat_id,
        "expires_at": str(int(time.time()) + DUREE_SESSION_S),
        "metadata[lot]": str(lot),
        "metadata[achat_id]": achat_id,
        "metadata[renonciation_retractation]": "accès immédiat demandé, case cochée sur credaura.fr",
        "payment_intent_data[description]": f"Credaura · {libelle}",
        "payment_intent_data[metadata][lot]": str(lot),
        "custom_text[submit][message]": (
            "Ton code de dossier s'affiche juste après le paiement, et ton dossier s'ouvre "
            "tout seul dans l'onglet du simulateur."
        ),
    }
    if os.environ.get("IMMO_STRIPE_CGV") == "1":
        donnees["consent_collection[terms_of_service]"] = "required"
    if os.environ.get("IMMO_STRIPE_FACTURES") == "1":
        donnees["invoice_creation[enabled]"] = "true"
        donnees["invoice_creation[invoice_data][footer]"] = "TVA non applicable, art. 293 B du CGI."
    return donnees


async def creer_session(lot: int, achat_id: str, base_url: str) -> str:
    """Crée la session de paiement et renvoie l'adresse de la page Stripe."""
    if lot not in LOTS:
        raise ValueError(f"Lot inconnu : {lot}")
    if not achat_id_valide(achat_id):
        raise ValueError("Identifiant d'achat invalide.")
    # Même onglet, même lot, session encore ouverte : on la réutilise (un
    # double clic ou un retour arrière ne crée pas de nouvelle session).
    deja = codes.session_ouverte(achat_id, lot, REUTILISATION_SESSION_S)
    if deja:
        return deja
    session = await _appel("POST", "/v1/checkout/sessions", parametres_session(lot, achat_id, base_url))
    if not session.get("id") or not session.get("url"):
        raise ErreurPaiement("Réponse de Stripe incomplète : ni id ni url de session.")
    codes.enregistrer_achat(session["id"], achat_id, lot, url=session["url"])
    return session["url"]


async def recuperer_session(session_id: str) -> dict:
    if not session_id_valide(session_id):
        raise ValueError("Identifiant de session invalide.")
    return await _appel("GET", f"/v1/checkout/sessions/{session_id}")


async def _noter_code_chez_stripe(payment_intent: str, code: str) -> None:
    """Le code dans les métadonnées du paiement : retrouvable depuis le tableau
    de bord Stripe (recherche par e-mail de l'acheteur). Sans incidence si
    l'appel échoue, le code existe déjà côté Credaura."""
    try:
        await _appel("POST", f"/v1/payment_intents/{payment_intent}", {"metadata[code_dossier]": code})
    except ErreurPaiement as exc:
        log.warning("Code %s non noté chez Stripe : %s", code, exc)


# ---------------------------------------------------------------------------
# Confirmation d'un paiement → code de dossier
# ---------------------------------------------------------------------------
async def traiter_session(session: dict) -> str | None:
    """Code de dossier d'une session payée (créé au premier passage), ou None
    si la session n'est pas payée ou ne vient pas du site."""
    if session.get("payment_status") != "paid":
        return None
    metadonnees = session.get("metadata") or {}
    try:
        lot = int(metadonnees.get("lot", ""))
    except ValueError:
        return None
    if lot not in LOTS:
        return None
    if session.get("amount_total") != LOTS[lot] or (session.get("currency") or "").lower() != "eur":
        log.error(
            "Session %s : montant %s %s inattendu pour le lot %s, aucun code créé.",
            session.get("id"),
            session.get("amount_total"),
            session.get("currency"),
            lot,
        )
        return None
    achat_id = session.get("client_reference_id") or metadonnees.get("achat_id") or ""
    payment_intent = session.get("payment_intent") or ""
    if isinstance(payment_intent, dict):
        payment_intent = payment_intent.get("id") or ""
    code, nouveau = codes.code_du_paiement(session["id"], achat_id, lot, note=f"Stripe {payment_intent}".strip())
    if nouveau:
        log.info("Paiement %s confirmé : code %s (%s dossier(s)).", session["id"], code, lot)
        if payment_intent:
            # En tâche de fond : le webhook doit répondre vite à Stripe.
            tache = asyncio.get_running_loop().create_task(_noter_code_chez_stripe(payment_intent, code))
            _taches.add(tache)
            tache.add_done_callback(_taches.discard)
    return code


async def confirmer(session_id: str) -> str | None:
    """Pour la page de remerciement : le code s'il existe déjà, sinon demande
    à Stripe où en est le paiement."""
    deja = codes.code_de_session(session_id)
    if deja:
        return deja
    return await traiter_session(await recuperer_session(session_id))


async def verifier_achat(achat_id: str) -> list[str]:
    """Pour l'onglet du simulateur : codes des paiements lancés depuis cet
    onglet. Interroge Stripe seulement pour les sessions pas encore confirmées."""
    if not achat_id_valide(achat_id):
        return []
    trouves: list[str] = []
    for achat in codes.achats(achat_id):
        code = achat["code"]
        session_id = achat["session_id"]
        maintenant = time.monotonic()
        if not code and maintenant - _dernieres_verifications.get(session_id, 0.0) >= INTERVALLE_VERIFICATION_S:
            _dernieres_verifications[session_id] = maintenant
            try:
                code = await confirmer(session_id)
            except ErreurPaiement as exc:
                log.warning("Vérification du paiement %s impossible : %s", session_id, exc)
        if code:
            _dernieres_verifications.pop(session_id, None)
            trouves.append(code)
    return trouves


# ---------------------------------------------------------------------------
# Webhook
# ---------------------------------------------------------------------------
def signature_valide(
    corps: bytes, entete: str, secret: str, tolerance: int = TOLERANCE_SIGNATURE_S, maintenant: float | None = None
) -> bool:
    """Vérifie l'en-tête Stripe-Signature (« t=…,v1=… ») : HMAC-SHA256 de
    « t.corps » avec le secret du webhook, et horodatage récent."""
    if not secret or not entete:
        return False
    horodatage = None
    signatures: list[str] = []
    for morceau in entete.split(","):
        cle, _, valeur = morceau.strip().partition("=")
        if cle == "t":
            horodatage = valeur
        elif cle == "v1":
            signatures.append(valeur)
    if not horodatage or not signatures:
        return False
    try:
        ecart = abs((maintenant if maintenant is not None else time.time()) - int(horodatage))
    except ValueError:
        return False
    if ecart > tolerance:
        return False
    attendu = hmac.new(secret.encode(), horodatage.encode() + b"." + corps, hashlib.sha256).hexdigest().encode()
    return any(hmac.compare_digest(attendu, signature.encode()) for signature in signatures)


async def traiter_evenement(evenement: dict) -> str | None:
    """Événement du webhook déjà vérifié : crée le code d'une session payée."""
    if evenement.get("type") not in EVENEMENTS_PAYES:
        return None
    session = ((evenement.get("data") or {}).get("object")) or {}
    if session.get("object") != "checkout.session" or not session.get("id"):
        return None
    return await traiter_session(session)
