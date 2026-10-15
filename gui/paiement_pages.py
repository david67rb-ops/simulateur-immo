"""Pages et adresses du paiement Stripe (logique dans app/paiement.py) :

- /paiement/commander : crée la session de paiement et redirige vers Stripe.
  Ouvert par un vrai lien dans un nouvel onglet, pour que le simulateur reste
  ouvert dans le sien (et qu'iPhone ne bloque pas l'ouverture).
- /paiement/merci : retour de Stripe, affiche le code de dossier.
- /paiement/annule et /paiement/erreur : retours sans paiement.
- /stripe/webhook : confirmation envoyée par Stripe (signée), qui crée le code
  même si l'acheteur ferme l'onglet avant la redirection.

Rien ne s'affiche ni ne s'ouvre tant que le mode payant et la clé Stripe ne
sont pas définis sur le serveur."""
from __future__ import annotations

import hmac
import json
import logging
import os
import time
from collections import defaultdict, deque
from datetime import date
from urllib.parse import urlencode

from fastapi import Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from nicegui import app, ui

from app import codes, editeur, paiement

from . import offre, statistiques, theme
from .pages_legales import _gabarit, _pied

log = logging.getLogger(__name__)

CSS = """
.code-achete { font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-size: clamp(1.6rem, 6vw, 2.2rem);
  font-weight: 700; letter-spacing: 0.06em; color: var(--c-marque-texte); }
.carte-code { border: 2px solid var(--c-laiton); border-radius: 16px; padding: 20px 22px; }
"""


def jeton_essai() -> str:
    return os.environ.get("IMMO_STRIPE_ESSAI", "").strip()


def essai_valide(jeton: str) -> bool:
    """Lien d'essai privé (?essai=…) : le vrai paiement Stripe, visible
    seulement par qui a le lien, même quand le mode payant est éteint."""
    attendu = jeton_essai()
    return len(attendu) >= 8 and hmac.compare_digest(attendu.encode(), (jeton or "").strip().encode())


def essai_depuis_requete() -> str:
    """Le jeton d'essai de la page en cours s'il est valide, sinon ""."""
    try:
        jeton = ui.context.client.request.query_params.get("essai", "")
    except Exception:  # noqa: BLE001  (pas de requête : application de bureau)
        return ""
    return jeton if paiement.actif() and essai_valide(jeton) else ""


def paiement_ouvert(essai: str = "") -> bool:
    return paiement.actif() and (offre.MODE_PAYANT or essai_valide(essai))


def adresse_publique(request: Request) -> str:
    """Adresse du site pour les retours depuis Stripe : IMMO_URL_SITE si elle
    est définie, l'ordinateur local pour les essais, sinon le domaine principal.
    Jamais l'en-tête Host d'une requête publique, qui se falsifie."""
    definie = os.environ.get("IMMO_URL_SITE", "").strip()
    if definie:
        return definie.rstrip("/")
    hote = request.headers.get("host", "")
    if hote.startswith(("localhost:", "127.0.0.1:")) or hote in ("localhost", "127.0.0.1"):
        return f"http://{hote}"
    return f"https://{os.environ.get('IMMO_DOMAINE_PRINCIPAL') or 'credaura.fr'}"


# Garde-fou contre les appels en rafale à /paiement/commander : chaque appel
# peut créer une session chez Stripe, dont le nombre de requêtes est limité.
LIMITE_COMMANDES = 20
FENETRE_COMMANDES_S = 600.0
_commandes_par_ip: dict[str, deque] = defaultdict(deque)


def _adresse_ip(request: Request) -> str:
    transmise = request.headers.get("x-forwarded-for", "")
    if transmise:
        return transmise.split(",")[0].strip()
    return request.client.host if request.client else ""


def _trop_de_commandes(ip: str) -> bool:
    maintenant = time.monotonic()
    file = _commandes_par_ip[ip]
    while file and maintenant - file[0] > FENETRE_COMMANDES_S:
        file.popleft()
    if len(file) >= LIMITE_COMMANDES:
        return True
    file.append(maintenant)
    if len(_commandes_par_ip) > 10_000:  # mémoire bornée
        for cle in [cle for cle, f in _commandes_par_ip.items() if not f or maintenant - f[-1] > FENETRE_COMMANDES_S]:
            del _commandes_par_ip[cle]
    return False


def lien_commande(lot: int, achat_id: str, essai: str = "") -> str:
    lien = f"/paiement/commander?lot={lot}&achat={achat_id}&renonciation=1"
    return lien + (f"&{urlencode({'essai': essai})}" if essai else "")


@app.get("/paiement/commander")
async def commander(
    request: Request, lot: int = 0, achat: str = "", renonciation: str = "", essai: str = ""
) -> RedirectResponse:
    if not paiement_ouvert(essai):
        return RedirectResponse("/simulateur", status_code=303)
    if renonciation != "1":
        return RedirectResponse("/paiement/erreur?motif=renonciation", status_code=303)
    if lot not in paiement.LOTS or not paiement.achat_id_valide(achat):
        return RedirectResponse("/paiement/erreur?motif=lien", status_code=303)
    if _trop_de_commandes(_adresse_ip(request)):
        return RedirectResponse("/paiement/erreur?motif=rafale", status_code=303)
    try:
        url = await paiement.creer_session(lot, achat, adresse_publique(request))
    except paiement.ErreurPaiement as exc:
        log.error("Session de paiement non créée : %s", exc)
        if paiement.mode_test():
            # Clés de test seulement : le message de Stripe s'affiche pour le diagnostic.
            return RedirectResponse(f"/paiement/erreur?{urlencode({'detail': str(exc)[:400]})}", status_code=303)
        return RedirectResponse("/paiement/erreur", status_code=303)
    return RedirectResponse(url, status_code=303)


def _masquer(valeur: str) -> str:
    return f"{valeur[:8]}…{valeur[-4:]}" if len(valeur) > 14 else ("définie" if valeur else "")


@app.get("/paiement/diagnostic", response_class=HTMLResponse)
async def diagnostic(request: Request, essai: str = "") -> HTMLResponse:
    """Vérifie la configuration du paiement, réglage par réglage (lien d'essai
    seulement). En mode test, crée aussi une vraie page de paiement Stripe."""
    if not essai_valide(essai):
        return HTMLResponse("Introuvable", status_code=404)
    lignes: list[tuple[bool | None, str, str]] = []
    cle = paiement.cle_secrete()
    lignes.append((bool(cle), "Clé secrète Stripe", (_masquer(cle) + (" (mode test)" if paiement.mode_test() else " (mode réel)")) if cle else "absente : IMMO_STRIPE_CLE_SECRETE"))
    secret = paiement.secret_webhook()
    lignes.append((secret.startswith("whsec_"), "Secret du webhook", _masquer(secret) or "absent : IMMO_STRIPE_SECRET_WEBHOOK"))
    base = adresse_publique(request)
    lignes.append((base.startswith("https://"), "Adresse du site (retours de Stripe)", base))
    lignes.append((None, "Mode payant (IMMO_MODE_PAYANT)", "allumé" if offre.MODE_PAYANT else "éteint : boutons visibles seulement avec le lien d'essai"))
    lignes.append((paiement.factures_actives(), "Facture jointe au reçu (IMMO_STRIPE_FACTURES=1)", "allumée : elle confirme la renonciation à la rétractation" if paiement.factures_actives() else "éteinte : à allumer avant l'ouverture (note obligatoire dès 25 €, confirmation de la renonciation)"))
    manque = [nom for nom, valeur in (("SIRET", editeur.SIRET), ("adresse", editeur.ADRESSE), ("téléphone", editeur.TELEPHONE), ("médiateur", editeur.MEDIATEUR_NOM)) if not valeur]
    lignes.append((not manque, "Identité du vendeur dans les CGV (app/editeur.py)", "complète" if not manque else f"à compléter : {', '.join(manque)}"))
    try:
        nb = len(codes.lister(5))
        dossier = os.environ.get("IMMO_DONNEES_DIR", "")
        lignes.append((True, "Base des codes", f"accessible ({nb} code(s) récents){'' if dossier else ' ; IMMO_DONNEES_DIR absent : base perdue à chaque déploiement'}"))
    except Exception as exc:  # noqa: BLE001
        lignes.append((False, "Base des codes", f"inaccessible : {exc}"))
    if cle:
        try:
            compte = await paiement._appel("GET", "/v1/account")
            nom = ((compte.get("business_profile") or {}).get("name")) or ((compte.get("settings") or {}).get("dashboard") or {}).get("display_name") or ""
            lignes.append((bool(nom), "Compte Stripe", f"{nom or 'SANS NOM : Paramètres > Entreprise > Informations publiques'} · pays {compte.get('country', '?')} · paiements réels {'activés' if compte.get('charges_enabled') else 'pas encore activés'}"))
        except paiement.ErreurPaiement as exc:
            lignes.append((False, "Compte Stripe", str(exc)))
        try:
            points = (await paiement._appel("GET", "/v1/webhook_endpoints?limit=20")).get("data") or []
            attendu = f"{base}/stripe/webhook"
            trouve = [p for p in points if (p.get("url") or "").rstrip("/") == attendu]
            if trouve:
                evts = set(trouve[0].get("enabled_events") or [])
                manque = [e for e in paiement.EVENEMENTS_PAYES if e not in evts and "*" not in evts]
                lignes.append((not manque and trouve[0].get("status") == "enabled", "Webhook chez Stripe", f"{attendu} · {trouve[0].get('status')}" + (f" · événements manquants : {', '.join(manque)}" if manque else " · événements OK")))
            else:
                lignes.append((False, "Webhook chez Stripe", f"aucun webhook vers {attendu} (trouvés : {', '.join(p.get('url', '') for p in points) or 'aucun'})"))
        except paiement.ErreurPaiement as exc:
            lignes.append((False, "Webhook chez Stripe", str(exc)))
        if paiement.mode_test():
            try:
                url = await paiement.creer_session(1, paiement.nouvel_achat_id(), base)
                lignes.append((True, "Création d'une page de paiement", f'OK : <a href="{url}">ouvrir la page Stripe et payer avec 4242 4242 4242 4242</a>'))
            except paiement.ErreurPaiement as exc:
                lignes.append((False, "Création d'une page de paiement", str(exc)))
    def ligne(ok: bool | None, titre: str, texte: str) -> str:
        signe = "—" if ok is None else ("✔" if ok else "✘")
        couleur = "#555" if ok is None else ("#2d6a4f" if ok else "#b23a32")
        return f'<tr><td style="color:{couleur};font-weight:700;padding:6px 10px">{signe}</td><td style="padding:6px 10px;font-weight:600">{titre}</td><td style="padding:6px 10px">{texte}</td></tr>'
    html = (
        "<!doctype html><html lang='fr'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width'>"
        "<meta name='robots' content='noindex'><title>Diagnostic du paiement · Credaura</title></head>"
        "<body style='font-family:system-ui,sans-serif;max-width:860px;margin:32px auto;padding:0 16px;line-height:1.5'>"
        "<h1 style='font-size:1.4rem'>Diagnostic du paiement</h1><table style='border-collapse:collapse'>"
        + "".join(ligne(*l) for l in lignes)
        + "</table></body></html>"
    )
    return HTMLResponse(html)


@app.post("/stripe/webhook")
async def webhook_stripe(request: Request) -> JSONResponse:
    secret = paiement.secret_webhook()
    if not secret:
        return JSONResponse({"erreur": "webhook désactivé"}, status_code=404)
    corps = await request.body()
    if not paiement.signature_valide(corps, request.headers.get("stripe-signature", ""), secret):
        return JSONResponse({"erreur": "signature invalide"}, status_code=400)
    try:
        evenement = json.loads(corps)
    except ValueError:
        return JSONResponse({"erreur": "contenu illisible"}, status_code=400)
    # Une erreur ici (base indisponible…) renvoie 500 : Stripe renverra
    # l'événement plus tard, sans risque de double code.
    await paiement.traiter_evenement(evenement)
    return JSONResponse({"recu": True})


def _carte_code(code: str) -> None:
    infos = codes.etat(code) or {}
    nb = infos.get("dossiers", 1)
    with ui.column().classes("carte-code w-full gap-2 mt-2"):
        ui.label("Ton code de dossier").classes(theme.SUBSECTION_TITLE_CLASSES)
        with ui.row().classes("items-center gap-3 flex-wrap"):
            ui.label(code).classes("code-achete")

            def copier() -> None:
                ui.clipboard.write(code)
                ui.notify("Code copié", type="positive")

            ui.button("Copier", icon="content_copy", on_click=copier).props("outline no-caps dense")
        expire = infos.get("expire_le")
        ui.label(
            f"{nb} dossier{'s' if nb > 1 else ''}"
            + (f", valable jusqu'au {date.fromisoformat(expire).strftime('%d/%m/%Y')}." if expire else ".")
        ).classes("text-sm")
    ui.label(
        "Ton dossier s'ouvre tout seul dans l'onglet du simulateur : tu peux fermer celui-ci. Si l'onglet du "
        "simulateur est fermé, rouvre ton projet ou refais la simulation, puis entre ce code à l'étape Dossier."
    ).classes("text-base mt-2")
    ui.label(
        "Note ce code : il sert pour tous les dossiers de ton lot pendant 12 mois. Stripe t'envoie aussi le reçu "
        "du paiement par e-mail."
    ).classes("text-sm")
    with ui.element("a").props('href="/simulateur"').classes(
        "self-start mt-2 no-underline rounded-lg px-4 py-2 font-semibold text-white"
    ).style(f"background:{theme.LAITON_HEX}"):
        ui.label("Ouvrir le simulateur")


@ui.page("/paiement/merci", title="Merci · Credaura")
def page_merci(session_id: str = "") -> None:
    colonne = _gabarit("Merci pour ton achat", date=False)
    ui.add_css(CSS)
    with colonne:
        zone = ui.column().classes("w-full gap-3 mt-2")
        with zone:
            with ui.row().classes("items-center gap-3"):
                ui.spinner(size="md")
                ui.label("Confirmation du paiement en cours…").classes("text-base")
    etat = {"essais": 0, "fini": False}

    def afficher(texte: str) -> None:
        etat["fini"] = True
        minuteur.deactivate()
        zone.clear()
        with zone:
            ui.label(texte).classes("text-base")

    async def charger() -> None:
        if etat["fini"]:
            return
        etat["essais"] += 1
        try:
            code = await paiement.confirmer(session_id)
        except ValueError:
            afficher("Ce lien de paiement n'est pas valide.")
            return
        except paiement.ErreurPaiement as exc:
            if exc.definitive:
                afficher("Ce lien de paiement n'est pas valide.")
                return
            log.warning("Page merci : vérification impossible (%s)", exc)
            code = None
        if etat["fini"]:
            return
        if code:
            etat["fini"] = True
            minuteur.deactivate()
            zone.clear()
            with zone:
                _carte_code(code)
            statistiques.evenement("dossier-achete", "Dossier acheté")
            return
        if etat["essais"] >= 20:
            afficher(
                "Le paiement n'est pas encore confirmé. Recharge cette page dans une minute. Si rien ne change, "
                "écris-moi depuis la page Contact avec la date du paiement : je te renvoie ton code."
            )

    # Premier appel tout de suite, puis toutes les 3 secondes (une minute au plus).
    minuteur = ui.timer(3.0, charger)
    _pied(colonne)


@ui.page("/paiement/annule", title="Paiement annulé · Credaura")
def page_annule() -> None:
    colonne = _gabarit("Paiement annulé", date=False)
    with colonne:
        ui.label("Aucun montant n'a été débité.").classes("text-base mt-2")
        ui.label(
            "Ton simulateur est toujours ouvert dans l'autre onglet : tu peux fermer celui-ci et reprendre où tu en étais."
        ).classes("text-base")
    _pied(colonne)


MOTIFS_ERREUR = {
    "renonciation": "Coche d'abord la case d'accès immédiat au dossier, dans l'étape Dossier du simulateur, puis choisis ton lot.",
    "lien": "Ce lien de paiement n'est pas valide. Retourne dans l'étape Dossier du simulateur et choisis ton lot.",
    "rafale": "Trop de tentatives de paiement depuis ta connexion. Patiente quelques minutes, puis réessaie.",
}


@ui.page("/paiement/erreur", title="Paiement indisponible · Credaura")
def page_erreur(motif: str = "", detail: str = "") -> None:
    colonne = _gabarit("Le paiement n'a pas pu démarrer", date=False)
    with colonne:
        ui.label(
            MOTIFS_ERREUR.get(motif, "Le service de paiement ne répond pas. Aucun montant n'a été débité : réessaie dans quelques minutes.")
        ).classes("text-base mt-2")
        if detail and paiement.mode_test():
            ui.label(f"Diagnostic (mode test Stripe) : {detail}").classes("text-sm mt-4 " + theme.HINT_CLASSES)
    _pied(colonne)
