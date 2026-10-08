# Credaura : document de contexte

*Mis à jour le 8 octobre 2026 (test complet et relecture : compteur GoatCounter des vérifications réparé, endettement assurance comprise, textes ; droits de mutation à 6,32 % ; bandeau du menu fixe, page /simulateur, reprise automatique des valeurs du marché), d'après le dépôt (code, README, historique git). Ce qui est déduit sans être écrit dans le dépôt est marqué [à confirmer].*

## 1. Vision

- **Produit** : simulateur de rentabilité immobilière qui produit un **dossier de financement Word** à remettre à la banque. Signature : « Convaincre mon banquier ».
- **Public** : investisseur particulier qui prépare un achat locatif (longue durée, courte durée type Airbnb) ou un achat-revente, et va demander un crédit.
- **Problème résolu** : vérifier qu'un bien tient la route (prix face aux ventes réelles du quartier, rentabilité et cash-flow après impôts, taux d'endettement calculé comme la banque), puis présenter le projet dans un dossier clair.
- **Promesses affichées** : ni compte ni e-mail, rien n'est conservé ; ni conseil, ni courtier, ni intermédiaire bancaire (IOBSP) ; la banque reste seule décisionnaire.

## 2. État actuel

**Terminé (en ligne sur credaura.fr, et en application Mac)**
- Page d'accueil (bêta gratuite) : formulaire rapide (adresse, type, surface, prix, loyer facultatif) qui ouvre le simulateur prérempli ; un champ obligatoire manquant ouvre une fenêtre « Il manque encore… » (la même dans le simulateur quand on analyse le marché sans adresse) ; bouton du dossier « Renseigne ton projet et obtiens ton dossier » (offert pendant la bêta) ; FAQ ; tarifs annoncés « à l'ouverture » (19,90 € / 34,90 € les deux / 44,90 € les trois).
- Bandeau du menu fixé en haut de l'écran, sur l'accueil et sur les pages Contact et légales (avec un bouton « ← Accueil ») ; credaura.fr/simulateur ouvre directement le simulateur.
- Simulateur en 6 étapes : Marché, Financement, Revenus et fiscalité, Résultats, Endettement, Dossier. Les saisies et estimations de l'étape Marché passent au financement en cliquant « Suivant » (plus de bouton « Utiliser ces valeurs ») ; prix et loyer saisis conservés.
- Étude de marché automatique : géocodage, ventes comparables DVF, loyer de marché, cartes.
- Verdict en 3 niveaux (solide / à renforcer / à revoir), prix d'achat maximum, scénarios de stress.
- Dossier Word (≈ 14 pages) : formules Complet, Banque, Personnel ; exemple fictif téléchargeable.
- Enregistrer / rouvrir son projet (fichier signé `.credaura`, stocké chez l'utilisateur).
- Pages légales, contact (par messagerie), formulaire d'avis des testeurs (par messagerie), mesure d'audience sans cookie.

**Prêt mais éteint pendant la bêta**
- Mode payant : aperçu partiel du dossier (contenu non envoyé par le serveur), codes de dossiers (lots, 12 mois), page d'administration des codes. Interrupteur `IMMO_MODE_PAYANT`.

**Prévu** : paiement Stripe (non commencé dans le code), voir §8.

## 3. Stack et architecture (pour non-développeur)

- **100 % Python**. L'interface (NiceGUI) est séparée de la logique métier (`app/`) : on pourrait changer d'interface sans toucher aux calculs.
- **Deux usages** : site web hébergé (Render) et application Mac autonome, avec le même code.
- **Pas de base de données utilisateur** : le projet vit dans la mémoire du serveur le temps de la visite. Seule exception : la base des codes de dossiers, sans donnée personnelle, utilisée uniquement en mode payant.
- **Données de marché publiques** : DVF (ventes, État), carte des loyers (ministère / ANIL), Base Adresse Nationale, Eurostat (saisonnalité). Certaines sont préparées à l'avance dans `app/data/` (à régénérer en avril et en octobre).
- **Fichiers clés** : calculs `app/simulation.py`, `finance.py`, `fiscalite.py`, `notaire.py`, `endettement.py`, `analyse.py`, `saisonnalite.py` ; marché `app/market_data.py` ; dossier `app/dossier_export.py` ; interface `gui/main.py`, `gui/accueil.py`.

## 4. Logique métier

**Coût et financement** (`simulation.py`, `finance.py`)
- Coût total = prix + frais de notaire + travaux + mobilier + frais bancaires.
- Montant emprunté E = (coût hors frais bancaires + frais de dossier + courtage − apport) ÷ (1 − taux de garantie). La garantie est un % du prêt qui l'inclut.
- Mensualité = E × t ÷ (1 − (1 + t)^−n), avec t le taux mensuel et n le nombre de mois. Assurance = E × taux annuel ÷ 12, sur le capital initial, payée aussi pendant un différé.
- Différé partiel : seuls les intérêts sont payés. Différé total : intérêts capitalisés, puis amortissement sur la durée restante.
- Défauts : prix 180 000 €, apport 20 000 €, taux 3,5 %, 20 ans, assurance 0,3 %, garantie 1 %, frais de dossier 800 €.

**Frais de notaire** (`notaire.py`)
- Émoluments au barème de 2020 (3,870 % / 1,596 % / 1,064 % / 0,799 % par tranches de 6 500 / 17 000 / 60 000 €), TVA 20 %.
- Plus droits de mutation : 6,3185 % dans l'ancien (taux départemental de 5 %, voté par presque tous les départements du 1er avril 2025 au 31 mars 2028 ; 5,80665 % avant), 0,715 % dans le neuf.
- Plus contribution de sécurité immobilière : 0,1 %, minimum 15 €.
- Plus 900 € de débours.
- Pas de taux départementaux réduits (départements restés à 4,50 %, Indre) ni d'exonération primo-accédant : estimation un peu prudente.

**Revenus et charges** (`simulation.py`, `saisonnalite.py`)
- Longue durée : loyer annuel = loyer mensuel × 12 × (1 − vacance). Défauts : loyer 750 €, vacance 5 %.
- Courte durée : recettes = Σ (jours du mois × occupation × prix par nuitée), réparties mois par mois par un profil (uniforme, types, région Eurostat ou personnalisé).
- Estimation de marché en courte durée : prix par nuitée = loyer nu mensuel ÷ 30 × 3 ; occupation 35 / 50 / 65 % (bas / moyen / haut). C'est une approximation pédagogique.
- Charges fixes indexées de 2 %/an : copropriété 1 200 €, taxe foncière 1 000 €, PNO 150 €, entretien 300 €, comptable (meublé seulement), ménage (courte durée seulement).
- CFE de 300 € : exonérée la 1re année et sous 5 000 € de recettes.
- Charges proportionnelles aux loyers : gestion, GLI, commission de plateforme 3 % en courte durée.
- Revalorisation : loyers +1 %/an, bien +1 %/an. Horizon de projection : 20 ans.

**Fiscalité** (`fiscalite.py`, `simulation.py`)
- Impôt sur le revenu = revenu imposable × TMI saisie (30 % par défaut), et non le barème complet du foyer.
- Prélèvements sociaux : 17,2 % en location nue, 18,6 % en meublé.
- Les régimes sont calculés côte à côte ; le « meilleur régime » est celui qui donne le meilleur cash-flow en année 1, parmi les régimes éligibles.
  - **Micro-foncier** : abattement 30 %, plafond 15 000 €.
  - **Foncier réel** : charges, intérêts et travaux (l'année 1) déduits. Les intérêts s'imputent d'abord sur les loyers ; le déficit dû aux autres charges est imputable sur le revenu global jusqu'à 10 700 €/an, le reste est reporté.
  - **Micro-BIC** : abattement 50 %, plafond 77 700 € (meublé, tourisme classé) ; 30 % et 15 000 € pour un meublé de tourisme non classé.
  - **LMNP réel** : amortissement linéaire du bâti (prix + notaire − 15 % de terrain, sur 25 ans), des travaux (15 ans) et du mobilier (7 ans). L'amortissement ne crée pas de déficit ; l'excédent est reporté.
  - **SCI à l'IS** : IS de 15 % jusqu'à 42 500 €, 25 % au-delà ; l'amortissement peut créer un déficit, reportable.
- Frais bancaires déductibles l'année 1 aux régimes réels.

**Revente et indicateurs** (`simulation.py`)
- Valeur de revente = prix × (1 + revalorisation)^n.
- Plus-value des particuliers :
  - IR de 19 % et prélèvements sociaux de 17,2 % ;
  - abattements pour durée de détention (exonération de l'IR à 22 ans, des prélèvements sociaux à 30 ans) ;
  - surtaxe au-delà de 50 000 € ;
  - en LMNP réel, les amortissements déduits sont réintégrés (loi de finances 2025, art. 84).
- SCI à l'IS : plus-value sur la valeur nette comptable, sans abattement, puis flat tax de 30 % sur la distribution finale (simplification).
- Rendement brut = loyer annuel ÷ coût total. Net de charges = (loyer − charges de l'an 1) ÷ coût total. Net-net = même chose, impôt de l'an 1 déduit.
- Cash-flow mensuel = (loyers − charges − mensualités − impôt) ÷ 12, en année 1, pour le meilleur régime. Effort d'épargne = le cash-flow s'il est négatif.
- Enrichissement = −apport + Σ des cash-flows + revente nette (d'impôt et du capital restant dû).
- TRI calculé sur ces mêmes flux.

**Achat-revente** (`simulation.py`)
- Portage = intérêts simples sur le prêt + taxe foncière + PNO, au prorata de la durée (9 mois par défaut).
- Frais d'agence à la revente : 4 %.
- Marge = vente nette − coût − portage − impôt.
- Particulier : régime des plus-values, frais financiers non déductibles. Marchand de biens ou SCI à l'IS : IS sur la marge.

**Endettement** (`endettement.py`)
- Taux = (crédits en cours + mensualité du projet, assurance emprunteur comprise) ÷ (revenus + autres revenus + 70 % des loyers du projet).
- Seuil HCSF : 35 %. On utilise la mensualité après différé, par prudence.

**Verdict** (`analyse.py`) : le pire des 3 critères donne le niveau global.
- **Rentabilité** : enrichissement négatif → rouge ; cash-flow ≥ 0 → vert ; effort ≤ 150 €/mois → orange ; au-delà → rouge. En achat-revente, la marge par rapport au coût : ≥ 10 % vert, ≥ 0 orange.
- **Prix** par rapport à la médiane du quartier : moins de 3 % au-dessus → vert ; moins de 10 % → orange ; au-delà → rouge.
- **Financement** : endettement > 35 % → rouge ; à moins de 3 points du seuil → orange. Sans profil saisi : apport ≥ 10 % du coût total → vert, sinon orange.
- Prix d'achat maximum : recherche par dichotomie du prix qui respecte l'objectif de cash-flow (location) ou de marge (achat-revente).

**Marché** (`market_data.py`)
- Ventes comparables DVF dans un rayon de 500 m et à ±30 % de surface.
- Élargissement à 1 km, 2 km, ±50 %, puis toutes surfaces, tant qu'il y a moins de 15 ventes.
- Fourchettes bas / médiane / haut = 10e / 50e / 90e percentiles.
- Loyer de marché = loyer au m² × surface.

## 5. Entrées et sorties

- **Saisies** :
  - type de projet et structure (en direct, SCI à l'IR, SCI à l'IS) ;
  - adresse, type de bien, surface, prix, travaux, mobilier ;
  - apport, taux, durée, assurance, différé ;
  - loyer ou nuitée et occupation, charges ;
  - TMI, régime (nu ou meublé) ;
  - revenus du foyer et crédits en cours ;
  - patrimoine, nom de l'emprunteur, photos, chapitres du dossier.
- **Affichages** :
  - verdict et ses 3 critères ;
  - cash-flow, rendements, enrichissement, TRI par régime, mensualité, coût total ;
  - position du prix face au marché, cartes ;
  - prix d'achat maximum, scénarios de stress, graphiques ;
  - taux d'endettement et jauge ;
  - aperçu puis téléchargement du dossier Word.

## 6. Décisions prises et raisons

- **Aucun compte, aucune donnée de projet conservée** : c'est la promesse de confiance. Le projet se garde dans un fichier signé côté utilisateur, et le contact et les avis passent par la messagerie.
- **Bêta gratuite**, avec tarifs annoncés et mode payant prêt mais éteint : valider l'intérêt avant d'encaisser [à confirmer : motivation détaillée hors dépôt].
- **Dossier, formules Banque et Complet** : « Les 3 repères du projet », des faits sans jugement, pour ne jamais écrire « Projet à revoir » devant un banquier. La formule Personnel affiche le verdict du site.
- **Aperçu payant tronqué côté serveur**, parce que le flou seul se contourne.
- **Mention IOBSP partout, aucun lien vers une banque ou un courtier**, pour rester un outil et non un intermédiaire.
- **Le prix et le loyer saisis ne sont jamais remplacés** par les valeurs de marché.
- **Mesure d'audience sans cookie (GoatCounter)**, donc sans bandeau de consentement.
- **Tutoiement et charte « bleu notaire et laiton »**, avec des polices embarquées pour que le dossier s'affiche à l'identique chez la banque.

## 7. Limites connues, bugs, TODO, questions ouvertes

- **Corrigé le 7 octobre 2026 (`fiscalite.foncier_reel`)** : le déficit foncier imputait mal la part du déficit sur le revenu global. Les intérêts s'imputent désormais d'abord sur les loyers, comme le prévoit la règle.
- **Corrigé le 7 octobre 2026 (`simulation.py`)** : en location nue au réel, les travaux sont désormais déduits des loyers l'année 1 et retirés du prix d'acquisition de la plus-value. Hypothèse : pas de travaux de construction ou d'agrandissement (non déductibles, non distingués dans le formulaire).
- **Corrigé le 8 octobre 2026 (`statistiques.py`)** : l'événement GoatCounter « Vérification d'un projet » cassait le script (apostrophe) et n'était jamais compté ; les données de l'événement sont désormais encodées en JSON.
- **Corrigé le 8 octobre 2026** : le taux d'endettement (site, verdict et dossier) compte désormais la mensualité assurance emprunteur comprise, comme la règle HCSF des 35 %.
- **Relevé le 8 octobre 2026, laissé tel quel (choix de David)** : la plus-value de revente des particuliers n'applique pas le forfait de 15 % pour travaux après 5 ans de détention, ce qui surestime l'impôt de revente (sens prudent).
- **Impôt calculé au taux marginal** (TMI), pas au barème du foyer. La fonction `impot_bareme` existe mais n'est pas utilisée.
- **README en partie dépassé** [à confirmer] :
  - il dit les charges constantes, or le code les indexe de 2 %/an ;
  - il cite la police « Inter » et des « comptes utilisateurs » en prochaine étape ;
  - il dit que l'avertissement sur la SCI à l'IR en meublé s'affiche, alors que le code ne l'affiche qu'en courte durée.
- **Meilleur régime choisi sur l'année 1 seulement**, et non sur toute la durée.
- **Taux réduit d'IS supposé toujours applicable.** La flat tax en SCI à l'IS est une simplification (le compte courant d'associé n'est pas modélisé).
- **Achat-revente** : intérêts de portage simples, pas d'assurance emprunteur dans le portage.
- **Reste à vivre non calculé**, alors que c'est un critère bancaire courant.
- **Marché** :
  - pas de DVF en Alsace-Moselle ni à Mayotte, et les ventes ont 6 à 12 mois de décalage ;
  - loyers peu fiables dans les communes avec peu d'annonces ;
  - aucune donnée ouverte sur les prix en courte durée ;
  - les grands portails d'annonces bloquent l'import par lien.
- **Avant le mode payant** : définir une vraie clé de signature des fichiers projet (sinon c'est la clé de développement), ajouter le disque Render, la page d'administration protégée et Stripe.

## 8. Roadmap (dans le dépôt : `gui/offre.py`, README, commits)

- **Ouverture de la vente** : allumer le mode payant, brancher Stripe (chaque paiement crée un code), retirer le bandeau bêta, mettre à jour tarifs, FAQ et confidentialité.
- **Hors dépôt** [à confirmer, source : plan de commercialisation] :
  - témoignages vérifiés sur l'accueil ;
  - pages villes et articles pour Google ;
  - baromètre ;
  - affiliation ;
  - offre Pro (crédits, dossier à la marque d'un cabinet) ;
  - CGV et médiateur.
- **Idées du README** : calcul de l'IR au barème du foyer, comparateur multi-biens, compte courant d'associé en SCI à l'IS.

## 9. Glossaire

- **Verdict / repères** : synthèse en 3 critères (rentabilité, prix, financement). « Repères » désigne la version factuelle du dossier pour la banque.
- **Cash-flow net / effort d'épargne** : ce qui reste (ou ce qu'il faut ajouter) chaque mois après crédit, charges et impôts.
- **Enrichissement** : gain net total sur la durée de projection, revente comprise.
- **TMI** : tranche marginale d'imposition saisie par l'utilisateur.
- **LMNP** : loueur en meublé non professionnel (régimes micro-BIC ou réel).
- **HCSF** : régulateur, à l'origine du seuil d'endettement de 35 %.
- **DVF** : demandes de valeurs foncières, les ventes réelles publiées par l'État.
- **IOBSP** : intermédiaire en opérations de banque. Credaura n'en est pas un.
- **Formules du dossier** : Complet, Banque (sans patrimoine), Personnel (sans profil, sans endettement, sans pièces).
- **Fichier projet `.credaura`** : sauvegarde signée du projet, chez l'utilisateur. En mode payant, elle garde le dossier ouvert 30 jours pour le même bien.
- **Code de dossier** : CRED-XXXX-XXXX, un lot de 1 à 3 dossiers valable 12 mois.
- **Mode payant** : interrupteur `IMMO_MODE_PAYANT`, éteint pendant la bêta.
