"""Codes de dossiers : un code par achat (lot de 1, 2 ou 3 dossiers, valable
12 mois), décompté à chaque nouveau dossier téléchargé.

Rangés dans une base SQLite sur le disque persistant du serveur (Render :
dossier indiqué par IMMO_DONNEES_DIR), sans aucune donnée personnelle : le
code, le nombre de dossiers, les dates, l'origine (paiement, testeur…) et les
identifiants aléatoires des dossiers déjà ouverts avec ce code. Pour un achat
par Stripe, seulement l'identifiant de la session de paiement et le lot : ni
nom, ni e-mail (Stripe les garde de son côté)."""
from __future__ import annotations

import os
import secrets
import sqlite3
import threading
import time
from contextlib import contextmanager
from datetime import date, timedelta
from pathlib import Path

VALIDITE_JOURS = 365
# Sans ambiguïté à la lecture ou à la dictée : ni 0/O, ni 1/I/L.
ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"

_VERROU = threading.Lock()


def _chemin_base() -> Path:
    dossier = Path(os.environ.get("IMMO_DONNEES_DIR") or Path(__file__).resolve().parent.parent / "donnees-locales")
    dossier.mkdir(parents=True, exist_ok=True)
    return dossier / "codes.sqlite"


@contextmanager
def _base():
    """Connexion exclusive (une écriture à la fois), validée puis fermée."""
    with _VERROU:
        cnx = _connexion()
        try:
            with cnx:
                yield cnx
        finally:
            cnx.close()


def _connexion() -> sqlite3.Connection:
    cnx = sqlite3.connect(_chemin_base())
    cnx.row_factory = sqlite3.Row
    cnx.executescript(
        """
        CREATE TABLE IF NOT EXISTS codes (
            code TEXT PRIMARY KEY,
            dossiers INTEGER NOT NULL,
            cree_le TEXT NOT NULL,
            expire_le TEXT NOT NULL,
            origine TEXT NOT NULL,
            note TEXT NOT NULL DEFAULT ''
        );
        CREATE TABLE IF NOT EXISTS dossiers_ouverts (
            code TEXT NOT NULL REFERENCES codes(code),
            dossier_id TEXT NOT NULL,
            le TEXT NOT NULL,
            PRIMARY KEY (code, dossier_id)
        );
        -- Une ligne par session de paiement Stripe : créée au départ vers le
        -- paiement (code vide), complétée par le code une fois le paiement
        -- confirmé. achat_id relie la session à l'onglet du simulateur.
        CREATE TABLE IF NOT EXISTS achats (
            session_id TEXT PRIMARY KEY,
            achat_id TEXT NOT NULL,
            dossiers INTEGER NOT NULL,
            code TEXT REFERENCES codes(code),
            cree_le TEXT NOT NULL,
            url TEXT NOT NULL DEFAULT '',
            cree_a REAL NOT NULL DEFAULT 0
        );
        CREATE INDEX IF NOT EXISTS achats_par_achat ON achats(achat_id);
        """
    )
    # Colonnes ajoutées après la première version de la table achats.
    colonnes = {ligne["name"] for ligne in cnx.execute("PRAGMA table_info(achats)")}
    for nom, definition in (("url", "TEXT NOT NULL DEFAULT ''"), ("cree_a", "REAL NOT NULL DEFAULT 0")):
        if nom not in colonnes:
            cnx.execute(f"ALTER TABLE achats ADD COLUMN {nom} {definition}")
    return cnx


def normaliser(code: str) -> str:
    """« cred-ab12-cd34 », « CRED AB12CD34 »… → « CRED-AB12-CD34 »."""
    brut = "".join(c for c in (code or "").upper() if c.isalnum())
    if len(brut) == 12 and brut.startswith("CRED"):
        brut = brut[4:]
    return f"CRED-{brut[:4]}-{brut[4:8]}" if len(brut) == 8 else ""


def _nouveau_code(cnx: sqlite3.Connection, dossiers: int, origine: str, note: str, jour: date) -> str:
    if dossiers < 1:
        raise ValueError("Un code donne droit à au moins un dossier.")
    while True:
        alea = "".join(secrets.choice(ALPHABET) for _ in range(8))
        code = f"CRED-{alea[:4]}-{alea[4:]}"
        if not cnx.execute("SELECT 1 FROM codes WHERE code = ?", (code,)).fetchone():
            break
    cnx.execute(
        "INSERT INTO codes VALUES (?, ?, ?, ?, ?, ?)",
        (code, dossiers, jour.isoformat(), (jour + timedelta(days=VALIDITE_JOURS)).isoformat(), origine, note),
    )
    return code


def creer(dossiers: int, origine: str, note: str = "", aujourd_hui: date | None = None) -> str:
    with _base() as cnx:
        return _nouveau_code(cnx, dossiers, origine, note, aujourd_hui or date.today())


# ---------------------------------------------------------------------------
# Achats par Stripe : un code par session de paiement, jamais deux
# ---------------------------------------------------------------------------
ORIGINE_STRIPE = "paiement Stripe"


# Sessions jamais payées : effacées au bout de 2 jours (Stripe les expire bien avant).
DUREE_SESSIONS_NON_PAYEES_S = 2 * 86400


def enregistrer_achat(
    session_id: str, achat_id: str, dossiers: int, url: str = "", aujourd_hui: date | None = None
) -> None:
    """Départ vers le paiement : la session est connue, pas encore payée."""
    maintenant = time.time()
    with _base() as cnx:
        cnx.execute(
            "DELETE FROM achats WHERE code IS NULL AND cree_a < ?", (maintenant - DUREE_SESSIONS_NON_PAYEES_S,)
        )
        cnx.execute(
            "INSERT OR IGNORE INTO achats (session_id, achat_id, dossiers, code, cree_le, url, cree_a) "
            "VALUES (?, ?, ?, NULL, ?, ?, ?)",
            (session_id, achat_id, dossiers, (aujourd_hui or date.today()).isoformat(), url, maintenant),
        )


def session_ouverte(achat_id: str, dossiers: int, age_max_s: float) -> str | None:
    """Adresse d'une session de paiement récente, pas encore payée, pour le
    même onglet et le même lot : la réutiliser plutôt qu'en créer une autre."""
    with _base() as cnx:
        ligne = cnx.execute(
            "SELECT url FROM achats WHERE achat_id = ? AND dossiers = ? AND code IS NULL AND url != '' "
            "AND cree_a > ? ORDER BY cree_a DESC LIMIT 1",
            (achat_id, dossiers, time.time() - age_max_s),
        ).fetchone()
    return ligne["url"] if ligne is not None else None


def code_du_paiement(
    session_id: str, achat_id: str, dossiers: int, note: str = "", aujourd_hui: date | None = None
) -> tuple[str, bool]:
    """Code d'une session payée, créé au premier appel. Le webhook de Stripe,
    la page de remerciement et l'onglet du simulateur peuvent confirmer le même
    paiement en même temps : un seul code est créé. Renvoie (code, nouveau)."""
    jour = aujourd_hui or date.today()
    with _base() as cnx:
        ligne = cnx.execute("SELECT code FROM achats WHERE session_id = ?", (session_id,)).fetchone()
        if ligne is not None and ligne["code"]:
            return ligne["code"], False
        code = _nouveau_code(cnx, dossiers, ORIGINE_STRIPE, note, jour)
        cnx.execute(
            "INSERT INTO achats (session_id, achat_id, dossiers, code, cree_le) VALUES (?, ?, ?, ?, ?) "
            "ON CONFLICT(session_id) DO UPDATE SET code = excluded.code",
            (session_id, achat_id, dossiers, code, jour.isoformat()),
        )
    return code, True


def code_de_session(session_id: str) -> str | None:
    with _base() as cnx:
        ligne = cnx.execute("SELECT code FROM achats WHERE session_id = ?", (session_id,)).fetchone()
    return ligne["code"] if ligne is not None and ligne["code"] else None


def achats(achat_id: str) -> list[dict]:
    """Sessions de paiement lancées depuis un onglet du simulateur."""
    with _base() as cnx:
        lignes = cnx.execute(
            "SELECT session_id, dossiers, code FROM achats WHERE achat_id = ? ORDER BY rowid", (achat_id,)
        ).fetchall()
    return [dict(ligne) for ligne in lignes]


def etat(code: str, aujourd_hui: date | None = None) -> dict | None:
    """Ce que le code permet encore : None si le code n'existe pas."""
    code = normaliser(code)
    if not code:
        return None
    with _base() as cnx:
        ligne = cnx.execute("SELECT * FROM codes WHERE code = ?", (code,)).fetchone()
        if ligne is None:
            return None
        utilises = cnx.execute("SELECT COUNT(*) FROM dossiers_ouverts WHERE code = ?", (code,)).fetchone()[0]
    jour = aujourd_hui or date.today()
    return {
        "code": code,
        "dossiers": ligne["dossiers"],
        "restants": max(ligne["dossiers"] - utilises, 0),
        "expire_le": ligne["expire_le"],
        "expire": jour.isoformat() > ligne["expire_le"],
        "origine": ligne["origine"],
        "note": ligne["note"],
        "cree_le": ligne["cree_le"],
    }


def ouvrir_dossier(code: str, dossier_id: str, aujourd_hui: date | None = None) -> tuple[bool, str]:
    """Décompte un dossier du code (une seule fois par dossier : retélécharger
    le même dossier ne coûte rien). Renvoie (accordé, explication)."""
    code = normaliser(code)
    jour = aujourd_hui or date.today()
    with _base() as cnx:
        ligne = cnx.execute("SELECT * FROM codes WHERE code = ?", (code,)).fetchone()
        if ligne is None:
            return False, "Ce code n'existe pas. Vérifie-le, il est de la forme CRED-XXXX-XXXX."
        deja = cnx.execute(
            "SELECT 1 FROM dossiers_ouverts WHERE code = ? AND dossier_id = ?", (code, dossier_id)
        ).fetchone()
        if deja:
            return True, "Dossier déjà ouvert avec ce code."
        if jour.isoformat() > ligne["expire_le"]:
            return False, f"Ce code a expiré le {date.fromisoformat(ligne['expire_le']).strftime('%d/%m/%Y')}."
        utilises = cnx.execute("SELECT COUNT(*) FROM dossiers_ouverts WHERE code = ?", (code,)).fetchone()[0]
        if utilises >= ligne["dossiers"]:
            return False, "Tous les dossiers de ce code ont déjà été utilisés."
        cnx.execute("INSERT INTO dossiers_ouverts VALUES (?, ?, ?)", (code, dossier_id, jour.isoformat()))
        restants = ligne["dossiers"] - utilises - 1
    return True, f"Dossier ouvert. Il reste {restants} dossier{'s' if restants > 1 else ''} sur ce code."


def lister(limite: int = 200) -> list[dict]:
    with _base() as cnx:
        lignes = cnx.execute(
            "SELECT c.*, (SELECT COUNT(*) FROM dossiers_ouverts d WHERE d.code = c.code) AS utilises "
            "FROM codes c ORDER BY cree_le DESC, code LIMIT ?",
            (limite,),
        ).fetchall()
    return [dict(ligne) for ligne in lignes]
