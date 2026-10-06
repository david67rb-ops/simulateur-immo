"""Partage entre le simulateur gratuit et le dossier de financement (payant à
terme) : le gratuit montre les conclusions, le dossier montre les preuves.

Mode payant ÉTEINT pendant la bêta gratuite (tout est offert). Il s'allume
sur le serveur avec la variable d'environnement IMMO_MODE_PAYANT=1, le jour
de l'ouverture de la vente. Il faut alors aussi, sur Render : le disque
persistant et IMMO_DONNEES_DIR (codes de dossiers), IMMO_SIGNATURE_SECRET
(fichiers projet) et IMMO_ADMIN_MDP (page de création des codes)."""
from __future__ import annotations

import os

MODE_PAYANT = os.environ.get("IMMO_MODE_PAYANT") == "1"

# Détail réservé au dossier : liste des ventes comparables (adresse, date,
# prix, distance) et saisonnalité mois par mois. Le simulateur garde le
# verdict, les indicateurs, la médiane du marché et les cartes.
DETAIL_DANS_LE_SIMULATEUR = False

# Aperçu gratuit du dossier : la page de garde, le sommaire et les N premiers
# chapitres sont rédigés et lisibles ; les chapitres suivants ne gardent que
# leur titre (le serveur n'envoie pas leur contenu) et sont floutés.
CHAPITRES_APERCU = 1
PAGES_APERCU_LISIBLES = 2 + CHAPITRES_APERCU
