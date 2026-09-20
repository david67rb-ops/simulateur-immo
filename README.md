# Simulateur de rentabilité immobilière

Application locale (FastAPI + JS vanilla) qui combine :

1. **Étude de marché automatique** : à partir d'une adresse (ou d'un lien
   d'annonce), l'app géocode le bien (API Adresse / Base Adresse Nationale),
   récupère les prix de vente comparables dans le secteur (DVF géolocalisé,
   fourchette bas/moyen/haut) et le loyer de marché estimé pour la commune
   (fourchette mini/moyen/maxi, "Carte des loyers" DHUP/ANIL).
2. **Simulateur de rentabilité** : cash-flow prévisionnel, fiscalité détaillée
   selon le **type de projet** (location longue durée, location courte durée,
   achat-revente) et la **structure juridique** (personne physique, SCI à
   l'IR, SCI à l'IS), différé de crédit (partiel/total), TRI et simulation de
   revente/plus-value.
3. **Dossier de financement** : taux d'endettement du foyer (pondération
   bancaire standard sur les loyers prévisionnels) et export Word du dossier
   à présenter en banque.

## Lancer en local

```bash
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app
```

Puis ouvrir http://localhost:8000

⚠️ Ne pas utiliser `--reload` : le rechargeur multiprocessing d'uvicorn plante
sur certaines installations Python (erreur `ImportError: cannot import name
'ASGIApplication'`). Relancer manuellement le process après une modification
du code backend.

Les données de marché (DVF par département, indicateurs de loyers) sont
téléchargées à la demande depuis data.gouv.fr et mises en cache dans
`backend/app/data_cache/` (peut prendre quelques secondes au premier appel
pour un département donné).

## Types de projet

- **Location longue durée** : nue ou meublée (LMNP), moteur pluriannuel complet.
- **Location courte durée** (type Airbnb) : fiscalement un meublé de tourisme
  (classé ou non classé, abattement/plafond micro-BIC différents), avec des
  charges spécifiques (commission plateforme, ménage). **Limite importante** :
  aucune source de données ouvertes fiable ne donne un loyer/nuitée de marché ;
  l'étude de marché affiche donc l'indicateur de loyer longue durée comme un
  plancher indicatif, pas comme un prix Airbnb réel.
- **Achat-revente** : opération courte (quelques mois), avec frais de portage
  (intérêts de crédit relais, taxe foncière/assurance au prorata), fiscalité
  différente selon que l'opération est occasionnelle (régime des plus-values
  des particuliers, frais financiers non déductibles de la base imposable) ou
  professionnelle/en société à l'IS (résultat net de tous les frais, taxé à l'IS).

## Structures juridiques

- **Personne physique** : calcul de référence (TMI + prélèvements sociaux).
- **SCI à l'IR** : transparente fiscalement, traitée comme la personne
  physique. ⚠️ Une SCI à l'IR qui loue en meublé de façon habituelle est en
  principe requalifiée à l'IS par l'administration (sauf recettes meublées
  accessoires, < 10 % du total) — l'app affiche cet avertissement.
- **SCI à l'IS** : résultat comptable (loyers − charges − amortissements),
  imposé à l'IS (15 % jusqu'à 42 500 €, 25 % au-delà). Les années où la
  trésorerie de la SCI est négative sont comptées comme un apport réel de
  l'associé (compte courant). À la revente, la plus-value professionnelle
  (prix − valeur nette comptable) n'a **aucun abattement pour durée de
  détention** (contrairement au régime des particuliers), et une hypothèse de
  distribution finale du résultat aux associés applique la flat tax de 30 %
  sur la part de trésorerie excédant l'apport initial — une simplification
  qui ignore le compte courant d'associé, le remboursement de capital non
  taxable, etc.

## Différé de crédit

Deux types, calculés dans `finance.py` :

- **Partiel** : seuls les intérêts sont payés pendant le différé (capital
  inchangé) ; l'amortissement classique démarre après, sur la durée restante.
- **Total** : rien n'est payé ; les intérêts courus sont **capitalisés**
  (ajoutés au capital restant dû), donc le capital à amortir ensuite est plus
  élevé. Coût total plus important, confort de trésorerie maximal pendant le
  différé (travaux, avant mise en location).

L'assurance emprunteur continue à courir pendant le différé (pratique
bancaire standard). Le résultat de simulation distingue la mensualité de la
première année de celle du « régime de croisière » (après différé) — c'est
cette dernière qui est utilisée pour le calcul du taux d'endettement, par
prudence.

## Dossier de financement (taux d'endettement + export Word)

Section indépendante du simulateur de rentabilité : à partir des revenus du
foyer, des autres revenus et des mensualités de crédits déjà en cours,
calcule le taux d'endettement en reprenant la pratique bancaire française
standard — les loyers prévisionnels du projet ne sont retenus qu'à hauteur de
**70 %** (pondération de prudence), et le seuil de référence est celui du
HCSF (**35 %**). Le « reste à vivre », autre critère bancaire courant, n'est
pas calculé (dépend du nombre de personnes au foyer et de barèmes internes
propres à chaque banque) — limite documentée, à approfondir si besoin.

L'export Word (`python-docx`) reprend l'ensemble du projet (bien, financement,
rentabilité, profil emprunteur et taux d'endettement) dans un document
présentable à une banque. Estimation pédagogique, pas un dossier de crédit
formel.

## Frais de notaire automatiques

Barème réglementé des émoluments (arrêté 2020) + droits de mutation
(5,80665 % en ancien, 0,715 % en neuf/VEFA car le prix supporte déjà la TVA)
+ contribution de sécurité immobilière + débours forfaitaires. Estimation
nationale standard (ne tient pas compte des rares départements à taux réduit).

## Extraction depuis un lien d'annonce

Best-effort : JSON-LD, méta-données Open Graph et heuristique sur les slugs
d'URL. **Les grands portails (SeLoger, LeBonCoin, PAP...) bloquent
systématiquement la récupération automatique** (Cloudflare/DataDome) — l'app
ne cherche pas à contourner ces protections et affiche un message clair dans
ce cas. Ça fonctionne en revanche bien sur les sites des réseaux d'agences
(Orpi, Century21, Laforêt...) testés en conditions réelles.

## Hypothèses et sources fiscales (à vérifier avant toute décision réelle)

- Barème IR 2026 sur les revenus 2025 (5 tranches : 0 / 11 / 30 / 41 / 45 %).
- Prélèvements sociaux : 17,2 % en location nue, 18,6 % en LMNP/meublé (LFSS
  2026, hausse de la CSG sur les revenus meublés non professionnels).
- IS 2026 : 15 % jusqu'à 42 500 € de bénéfice, 25 % au-delà.
- Plafonds micro : 15 000 €/an (micro-foncier et meublé de tourisme non
  classé), 77 700 €/an (micro-BIC LMNP/meublé classé). Abattements
  forfaitaires : 30 % (foncier et tourisme non classé), 50 % (LMNP/tourisme classé).
- Déficit foncier (régime réel, location nue) : la part liée aux intérêts
  d'emprunt n'est imputable que sur des revenus fonciers futurs ; le reste est
  imputable sur le revenu global dans la limite de 10 700 €/an.
- LMNP réel / SCI à l'IS : amortissement linéaire du bâti (hors quote-part de
  terrain), des travaux capitalisés et du mobilier. En LMNP réel (BIC non
  pro), l'amortissement ne peut pas créer ou aggraver un déficit (report
  illimité de l'amortissement non utilisé) ; en SCI à l'IS, il n'y a pas ce
  plafonnement (le déficit est reportable sans limite de montant ni de durée).
- Plus-value à la revente (personne physique / SCI IR) : régime des
  particuliers, abattements pour durée de détention (exonération IR à 22 ans,
  PS à 30 ans), surtaxe sur les plus-values > 50 000 €. Depuis la loi de
  finances 2025 (article 84), les amortissements déduits en LMNP réel sont
  réintégrés dans le calcul de la plus-value, ce qui n'est **pas** le cas en
  foncier réel/micro-foncier.
- Plus-value à la revente (SCI à l'IS) : régime des plus-values
  professionnelles (prix de cession − valeur nette comptable), taxée à l'IS
  avec le résultat de l'exercice, **sans** abattement pour durée de détention.
- Achat-revente occasionnel (particulier) : les frais financiers de portage
  (intérêts du crédit relais) ne sont pas déductibles de la plus-value
  immobilière taxable, contrairement à un résultat professionnel/IS.
- Les charges (hors loyers) sont supposées constantes sur la durée de
  projection (pas d'inflation appliquée), par simplification.
- La fiscalité personne physique/SCI IR est calculée à partir d'une TMI
  saisie par l'utilisateur, pas d'un calcul complet du foyer fiscal — c'est
  une approximation standard mais qui ignore les effets de seuil précis.

**Ceci reste un outil de simulation pédagogique.** Pour une décision réelle,
faites valider les hypothèses fiscales par un professionnel (notaire,
comptable, avocat fiscaliste, CGP).

## Limites connues de l'étude de marché

- DVF ne couvre pas l'Alsace-Moselle (67, 68, 57) ni Mayotte, et les ventes
  très récentes (< quelques mois) peuvent être absentes de l'export.
- L'indicateur de loyer est un modèle statistique (annonces leboncoin/SeLoger)
  avec un intervalle de confiance ; il est peu fiable pour les communes ayant
  peu d'annonces (`nb_observations_commune` faible) — l'app affiche un
  avertissement dans ce cas. Il ne couvre que la location longue durée
  (aucune donnée ouverte sur les loyers courte durée/Airbnb).
- Les fourchettes prix/loyer (bas/moyen/haut) utilisent les 10e/50e/90e
  percentiles des transactions trouvées, plus robustes que le min/max brut
  mais qui restent des estimations statistiques, pas une expertise.

## Architecture

```
backend/
  app/
    main.py            FastAPI : /api/simulate, /api/market-study,
                        /api/frais-notaire, /api/parse-listing,
                        /api/endettement, /api/export-dossier-word
    schemas.py          Modèles Pydantic (entrées, types de projet/structure)
    finance.py           Emprunt (dont différé), TRI/VAN génériques
    fiscalite.py          Barème IR, IS, régimes fiscaux locatifs
    simulation.py          Moteur location (pluriannuel) + achat-revente
    endettement.py           Taux d'endettement (dossier de financement)
    dossier_export.py         Génération du dossier Word (python-docx)
    market_data.py              Géocodage + DVF + loyers (téléchargement/cache)
    notaire.py                   Calcul automatique des frais de notaire
    listing_parser.py             Extraction best-effort depuis un lien d'annonce
    utils.py                       Sérialisation JSON partagée (dataclasses)
frontend/
  index.html, static/app.js, static/style.css   SPA vanilla JS (aucun build)
```

## Prochaines étapes possibles

- Déploiement (Docker/Render/Railway) une fois le prototype validé.
- Comptes utilisateurs + sauvegarde de plusieurs projets.
- Comparateur multi-biens.
- Calcul IR précis du foyer (au lieu d'une TMI) si l'utilisateur fournit son
  revenu imposable global.
- Modélisation d'un compte courant d'associé plus fine pour la SCI à l'IS.
