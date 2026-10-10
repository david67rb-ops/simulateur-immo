# Credaura — simulateur de rentabilité et dossier de financement immobilier

Application 100 % Python ([NiceGUI](https://nicegui.io) — plus de HTML/CSS/JS
séparés), utilisable en fenêtre de bureau native ou en application web
hébergée. Un parcours complet organisé en onglets qui s'adaptent au
**type de projet** choisi (location longue durée, location courte durée,
achat-revente) :

1. **Marché** : étude de marché automatique (géocodage, comparables DVF,
   loyers DHUP/ANIL, extraction depuis un lien d'annonce), carte des ventes
   comparables autour du bien, carte de rentabilité brute des communes
   du département, position du prix d'achat par rapport à la médiane des
   ventes et liens pour recouper sur MeilleursAgents ou SeLoger.
2. **Financement** : caractéristiques du bien, frais de notaire automatiques,
   emprunt (classique ou différé partiel/total), spécificités achat-revente.
3. **Exploitation** : loyers et charges (masqué en achat-revente).
4. **Fiscalité** : structure juridique (personne physique, SCI à l'IR, SCI à
   l'IS), régime locatif, amortissement, projection, TRI et plus-value.
5. **Résultats** : cash-flow, comparatif des régimes, graphique, revente.
6. **Dossier de financement** : taux d'endettement du foyer et export Word
   du dossier à présenter en banque (dont un chapitre « Étude de marché » :
   prix d'achat face aux ventes réelles voisines, pour justifier le prix),
   chapitre par chapitre au choix
   (formules Complet, Banque, Personnel ; synthèse, points d'attention et
   mentions toujours inclus).

## Lancer l'application

### Au quotidien (macOS) : double-clic

Une vraie application macOS autonome est disponible : **`Credaura.app`**,
installée dans /Applications par `./build_macos_app.sh`. Aucune installation
de Python ou de dépendances n'est nécessaire pour l'utiliser — double-clic,
ou glisse-la dans le Dock.

Premier lancement uniquement : macOS affichera un avertissement (application
non signée par un développeur identifié apple). Fais un clic droit sur l'app
> *Ouvrir*, puis confirme — à faire une seule fois.

Pour reconstruire cette application après une modification du code :

```bash
./build_macos_app.sh
```

(nécessite l'environnement de développement ci-dessous ; installe
automatiquement PyInstaller si besoin. Voir la note technique en tête du
script sur la construction hors du dossier iCloud du projet.)

### En développement

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python3 main.py
```

Ouvre une **fenêtre native** (icône dans le dock, pas de navigateur) grâce à
[pywebview](https://pywebview.flowrl.com/). Pour l'ouvrir dans un navigateur à
la place (utile pour du débogage ou un accès à distance) :

```bash
python3 main.py --web --port 8080
```

Les données de marché (DVF par département, indicateurs de loyers) sont
téléchargées à la demande depuis data.gouv.fr et mises en cache — dans
`app/data_cache/` en développement, ou dans `~/Library/Application
Support/Simulateur Immobilier/` pour l'application packagée (peut prendre
quelques secondes au premier appel pour un département donné).

## Déployer en hébergement web

L'app tourne sur FastAPI/uvicorn en interne (via NiceGUI), donc n'importe quel
hébergeur Python/conteneur convient. Pas de compte utilisateur, pas de base de
données — l'état de chaque simulation vit dans la session du navigateur de
la personne qui l'utilise (rien n'est partagé entre visiteurs).

**Avec Docker** (Render, Railway, Fly.io, un VPS...) :

```bash
docker build -t simulateur-immo .
docker run -p 8080:8080 -e PORT=8080 simulateur-immo
```

Le `Dockerfile` utilise `requirements-server.txt` (sans `pywebview`, inutile
et lourd à compiler en environnement Linux headless — réservé à l'usage
bureau local avec `requirements.txt`).

**Sans Docker**, sur un hébergeur qui détecte lui-même la commande de
démarrage (Render "Web Service" sans Docker, par exemple) :

- Build : `pip install -r requirements-server.txt`
- Start : `python3 main.py --web`
- La variable d'environnement `PORT` fournie par l'hébergeur est détectée
  automatiquement (l'app écoute dessus, sur `0.0.0.0`).

**Mise à jour** : il n'y a pas de mécanisme d'auto-update à gérer — un
déploiement web se met à jour en redéployant (`git push` vers l'hébergeur, ou
rebuild/redeploy de l'image Docker). Chaque redéploiement prend effet
immédiatement pour tous les visiteurs.

**Limite connue** : le cache DVF/loyers (`app/data_cache/`) est perdu à
chaque redéploiement si le système de fichiers de l'hébergeur n'est pas
persistant (cas fréquent des PaaS) — sans conséquence fonctionnelle, juste un
re-téléchargement au prochain appel pour un département donné.

## Architecture

Toute la logique métier (calculs financiers, fiscaux, appels aux API de
marché, génération du Word) vit dans le package `app/`, sans aucune
dépendance à une interface particulière — ce sont de simples fonctions/
modèles Pydantic. L'interface (`gui/`, construite avec NiceGUI) ne fait
qu'appeler ces fonctions et afficher le résultat ; elle pourrait être
remplacée par une CLI, une API HTTP ou une autre UI sans toucher à `app/`.

```
app/                  Logique métier (inchangée quelle que soit l'UI)
  schemas.py, finance.py, fiscalite.py, simulation.py, endettement.py,
  dossier_export.py, market_data.py, notaire.py, listing_parser.py, utils.py
gui/                 Interface NiceGUI
  main.py             Page unique : construit l'UI et appelle `app/`
  theme.py             Couleurs, police (Inter), composants stylés (cartes)
  charts.py             Construction des options ECharts
  state.py               Valeurs par défaut des formulaires
main.py              Point d'entrée (fenêtre native par défaut, --web sinon)
```

## Types de projet

- **Location longue durée** : nue ou meublée (LMNP), moteur pluriannuel complet.
- **Location courte durée** (type Airbnb) : fiscalement un meublé de tourisme
  (classé ou non classé, abattement/plafond micro-BIC différents), avec des
  charges spécifiques (commission plateforme, ménage) et une **saisonnalité**
  mois par mois : profils types (grande ville, littoral, montagne, campagne)
  qui répartissent l'occupation et le prix moyens sans changer les recettes
  annuelles, ou profil personnalisé saisi sur 12 mois. Les résultats et le
  dossier Word montrent le cash-flow de chaque mois et la trésorerie de
  sécurité (plus forte perte cumulée sur des mois consécutifs). **Limite importante** :
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
prudence. Le cash-flow, l'effort d'épargne et le rendement net-net affichés
sont ceux de la première année pleine après le différé (et au plus tôt de
l'année 2, sans les déductions ponctuelles de l'année 1).

## Dossier de financement (taux d'endettement + export Word)

Section indépendante du simulateur de rentabilité : à partir des revenus du
foyer, des autres revenus et des mensualités de crédits déjà en cours,
calcule le taux d'endettement en reprenant la pratique bancaire française
standard — les loyers prévisionnels du projet ne sont retenus qu'à hauteur de
**70 %** (pondération de prudence), la mensualité du projet est comptée
assurance emprunteur comprise, et le seuil de référence est celui du
HCSF (**35 %**). Le « reste à vivre », autre critère bancaire courant, n'est
pas calculé (dépend du nombre de personnes au foyer et de barèmes internes
propres à chaque banque) — limite documentée, à approfondir si besoin.

L'export Word (`python-docx`) reprend l'ensemble du projet (bien, financement,
rentabilité, profil emprunteur et taux d'endettement) dans un document
présentable à une banque. Estimation pédagogique, pas un dossier de crédit
formel.
Les pages, les graphiques et les cartes partagent le même fond bleuté
(#F5F7FA, `dossier_export.FOND_PAGE_HEX` et `charts_export.FOND`, à changer
ensemble) : posé derrière le texte depuis les en-têtes, il reste à
l'impression et dans l'export PDF.

## Frais de notaire automatiques

Barème réglementé des émoluments (arrêté 2020) + droits de mutation
(6,3185 % en ancien, taux départemental de 5 % appliqué presque partout
depuis le 1er avril 2025 ; 0,715 % en neuf/VEFA car le prix supporte déjà la
TVA) + contribution de sécurité immobilière + débours forfaitaires.
Estimation nationale standard (ne tient pas compte des rares départements
restés à 4,50 % ni de l'exonération des primo-accédants en résidence
principale).

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
- Travaux en location nue au régime réel : supposés d'entretien, de réparation
  ou d'amélioration, donc déduits des loyers l'année 1 (pas de travaux de
  construction ou d'agrandissement, non déductibles) ; déjà déduits, ils ne
  s'ajoutent pas au prix d'acquisition dans le calcul de la plus-value.
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

## Charte graphique

Charte « bleu notaire & laiton » : bleu notaire `#1B3358` (structure),
laiton `#A8823B` (détails), encre `#13243F` ; signaux favorable `#2D6A4F`,
vigilance `#B7791F`, défavorable `#B23A32`. Titres et chiffres en Sora, texte
en Public Sans, angles arrondis. Les polices (licence SIL OFL 1.1, voir
`app/fonts/OFL-*.txt`) sont livrées avec l'application : servies localement
par le site (aucun appel à Google Fonts) et incorporées dans les dossiers
Word (`app/polices_word.py`) pour s'afficher à l'identique chez le banquier.
Word n'utilisant que la version normale d'une police incorporée, les
demi-gras sont déclarés comme familles à part (« Sora SemiBold », « Public
Sans SemiBold »).

## Données préparées à l'avance

`app/data/` contient des données calculées une fois pour toute la France et
livrées avec l'application (carte de rentabilité, saisonnalité régionale) :

- `communes_marche.parquet` : par commune (arrondissement à Paris, Lyon,
  Marseille) et type de bien, prix médian au m² des ventes dans l'ancien sur
  les 24 derniers mois publiés, loyer d'annonce au m² et rentabilité brute
  (à partir de 10 ventes) ;
- `saisonnalite_regions.json` : nuitées réservées sur les plateformes en
  ligne, mois par mois, par région (Eurostat, `tour_ce_omn12`).

Pour les mettre à jour (après chaque publication DVF, en avril et octobre) :

```bash
venv/bin/python scripts/preparer_donnees.py
```

puis committer `app/data/`. Les comparables autour d'une adresse restent
téléchargés à la demande (trop volumineux pour être livrés).

## Limites connues de l'étude de marché

- DVF ne couvre pas l'Alsace-Moselle (67, 68, 57) ni Mayotte (l'app le
  signale), et les ventes très récentes (< 6 à 12 mois) sont absentes de
  l'export, publié deux fois par an.
- Prix au m² : ventes des 24 derniers mois publiés (années détectées
  automatiquement, cache rafraîchi tous les 30 jours), une ligne par vente
  d'un logement unique (les ventes en bloc, qui répètent le prix total sur
  chaque lot, sont exclues), ancien ou VEFA selon le bien, surface à ±30 %.
  Rayon puis tolérance de surface élargis (1 km, 2 km, ±50 %, toutes
  surfaces) tant qu'il y a moins de 15 ventes ; la fiabilité affichée en
  tient compte. Les caves et parkings vendus avec le logement restent inclus
  dans le prix.
- L'indicateur de loyer est un modèle statistique (annonces leboncoin/SeLoger)
  avec un intervalle de confiance ; il est peu fiable pour les communes ayant
  peu d'annonces (`nb_observations_commune` faible) — l'app affiche un
  avertissement dans ce cas. Il ne couvre que la location longue durée
  (aucune donnée ouverte sur les loyers courte durée/Airbnb).
- Les fourchettes prix/loyer (bas/moyen/haut) utilisent les 10e/50e/90e
  percentiles des transactions trouvées, plus robustes que le min/max brut
  mais qui restent des estimations statistiques, pas une expertise.

## Prochaines étapes possibles

- Packaging en exécutable autonome par OS (`nicegui-pack`, basé sur PyInstaller)
  pour distribuer l'app sans installation Python.
- Déploiement web (le mode `--web` existant tourne déjà sur FastAPI/uvicorn en
  interne) si un accès multi-utilisateurs à distance devient utile.
- Comptes utilisateurs + sauvegarde de plusieurs projets.
- Comparateur multi-biens.
- Calcul IR précis du foyer (au lieu d'une TMI) si l'utilisateur fournit son
  revenu imposable global.
- Modélisation d'un compte courant d'associé plus fine pour la SCI à l'IS.
