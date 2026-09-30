"""Partage entre le simulateur gratuit et le dossier de financement (payant à
terme) : le gratuit montre les conclusions, le dossier montre les preuves."""
from __future__ import annotations

# Détail réservé au dossier : liste des ventes comparables (adresse, date,
# prix, distance) et saisonnalité mois par mois. Le simulateur garde le
# verdict, les indicateurs, la médiane du marché et les cartes.
DETAIL_DANS_LE_SIMULATEUR = False

# Aperçu du dossier : nombre de pages lisibles avant paiement, les suivantes
# floutées. None : toutes lisibles, en attendant la commercialisation.
# Quand le paiement existera, le serveur ne devra plus envoyer au navigateur
# que ces pages (le flou seul se contourne).
PAGES_APERCU_LISIBLES: int | None = None
