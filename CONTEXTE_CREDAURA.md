# Credaura : document de contexte

*Mis à jour le 16 octobre 2026 (vente ouverte sans attendre le SIRET, choix de David du 16 octobre : identité du vendeur complétée dans `app/editeur.py`, EI, adresse, téléphone, « SIRET en cours d'attribution » dans les CGV, les mentions légales et le pied des factures ; page « Comment ça marche » détaillée sur /comment-ca-marche, ouverte par le menu et par un lien sous les 3 étapes de l'accueil), précédemment le 15 octobre 2026 (repère de prix saisi par l'utilisateur dans les zones sans DVF ; diagnostic du paiement dans la page d'administration, contenu de la page construit après le mot de passe ; disque permanent, clé de signature et mot de passe d'administration sur Render ; fichiers projet de la bêta rouverts sans déblocage ; conditions générales de vente sur /cgv, sans engagement au-delà de la loi et sans médiateur au lancement, identité du vendeur et médiateur dans `app/editeur.py` ; facture Stripe qui confirme la renonciation à la rétractation ; désactivation d'un code remboursé depuis la page d'administration ; CGU sans mention de la bêta en mode payant), précédemment le 10 octobre (indicateurs mensuels en année courante : cash-flow, effort d'épargne et net-net après un différé et hors déductions ponctuelles de l'année 1 ; meilleur régime choisi sur l'enrichissement de toute la durée ; « Montant à financer » à côté du crédit ; exemple de dossier à +23 €/mois), précédemment le 9 octobre (paiement Stripe branché, éteint tant que le mode payant et la clé Stripe ne sont pas définis ; textes de l'accueil et confidentialité qui suivent le mode payant ; visite gardée 10 minutes sur téléphone), précédemment le 8 octobre (conditions générales d'utilisation sur /cgu ; page Contact : bouton « Envoie-nous un mail » à la place de l'adresse affichée ; passe esthétique PC et iPhone : accueil, simulateur, résultats en cartes ; fond bleuté unique du dossier Word ; test complet et relecture : compteur GoatCounter des vérifications réparé, endettement assurance comprise, textes ; droits de mutation à 6,32 % ; bandeau du menu fixe, page /simulateur, reprise automatique des valeurs du marché), d'après le dépôt (code, README, historique git). Ce qui est déduit sans être écrit dans le dépôt est marqué [à confirmer].*

## 1. Vision

- **Produit** : simulateur de rentabilité immobilière qui produit un **dossier de financement Word** à remettre à la banque. Signature : « Convaincre mon banquier ».
- **Public** : investisseur particulier qui prépare un achat locatif (longue durée, courte durée type Airbnb) ou un achat-revente, et va demander un crédit.
- **Problème résolu** : vérifier qu'un bien tient la route (prix face aux ventes réelles du quartier, rentabilité et cash-flow après impôts, taux d'endettement calculé comme la banque), puis présenter le projet dans un dossier clair.
- **Promesses affichées** : ni compte ni e-mail, rien n'est conservé ; ni conseil, ni courtier, ni intermédiaire bancaire (IOBSP) ; la banque reste seule décisionnaire.

## 2. État actuel

**Terminé (en ligne sur credaura.fr, et en application Mac)**
- Page d'accueil (bêta gratuite) : formulaire rapide (adresse, type, surface, prix, loyer facultatif) qui ouvre le simulateur prérempli (sans lien « exemple » ni « simulateur complet » sous le bouton depuis le 8 octobre : on y accède par le menu et la carte du dossier) ; un champ obligatoire manquant ouvre une fenêtre « Il manque encore… » (la même dans le simulateur quand on analyse le marché sans adresse) ; bouton du dossier « Renseigne ton projet et obtiens ton dossier » (offert pendant la bêta) ; FAQ ; tarifs annoncés « à l'ouverture » (19,90 € / 34,90 € les deux / 44,90 € les trois).
- Page « Comment ça marche » détaillée (/comment-ca-marche, `gui/page_comment.py`, 16 octobre 2026) : les 6 étapes, la comparaison aux ventes DVF (rayon, surface, seuils), le calcul de rentabilité, le verdict, l'endettement, le dossier, les données et ce que Credaura ne fait pas. Les chiffres cités sont ceux du code : à mettre à jour avec lui. Le menu « Comment ça marche » ouvre cette page ; la section de l'accueil garde ses 3 étapes avec un lien « Tout le détail ».
- Bandeau du menu fixé en haut de l'écran, sur l'accueil et sur les pages Contact et légales (avec un bouton « ← Accueil ») ; credaura.fr/simulateur ouvre directement le simulateur.
- Simulateur en 6 étapes : Marché, Financement, Revenus et fiscalité, Résultats, Endettement, Dossier. Les saisies et estimations de l'étape Marché passent au financement en cliquant « Suivant » (plus de bouton « Utiliser ces valeurs ») ; prix et loyer saisis conservés.
- Étude de marché automatique : géocodage, ventes comparables DVF, loyer de marché, cartes.
- Verdict en 3 niveaux (solide / à renforcer / à revoir), prix d'achat maximum, scénarios de stress.
- Dossier Word (≈ 14 pages) : formules Complet, Banque, Personnel ; exemple fictif téléchargeable. Pages, graphiques et cartes sur le même fond bleuté #F5F7FA (fond pleine page posé dans les en-têtes, conservé à l'impression et en PDF ; couleur de page Word en plus pour l'écran). Les pages miniatures de l'accueil et l'aperçu du site reprennent ce fond.
- Enregistrer / rouvrir son projet (fichier signé `.credaura`, stocké chez l'utilisateur).
- Pages légales (mentions légales, conditions générales d'utilisation /cgu, conditions générales de vente /cgv en projet tant que la vente n'est pas ouverte, confidentialité), contact (par messagerie : un bouton par sujet, puis « Envoie-nous un mail » et « Copier l'adresse », sans afficher l'adresse), formulaire d'avis des testeurs (par messagerie), mesure d'audience sans cookie.

**Prêt mais éteint pendant la bêta**
- Mode payant : aperçu partiel du dossier (contenu non envoyé par le serveur), codes de dossiers (lots, 12 mois), page d'administration des codes. Interrupteur `IMMO_MODE_PAYANT`.
- Paiement Stripe Checkout (9 octobre 2026, `app/paiement.py`, `gui/paiement_pages.py`) : dans l'étape Dossier, case de renonciation au droit de rétractation puis 3 boutons (1, 2 ou 3 dossiers) qui ouvrent la page de paiement Stripe dans un nouvel onglet. Après le paiement, /paiement/merci affiche le code, et l'onglet du simulateur, qui interroge le serveur toutes les 4 secondes, ouvre le dossier tout seul. Le webhook /stripe/webhook (signé) crée le code même si l'acheteur ferme l'onglet. Un seul code par paiement, noté aussi dans les métadonnées du paiement chez Stripe. Une session Stripe expire au bout de 31 minutes et se réutilise pour le même onglet et le même lot ; au plus 20 départs vers le paiement par connexion et par 10 minutes ; Stripe interrogé au plus toutes les 15 secondes par session pendant l'attente ; le numéro de session est retiré de l'adresse envoyée à GoatCounter. Testé de bout en bout avec un faux serveur Stripe (avec et sans webhook), pas encore avec un vrai compte Stripe. Actif seulement si `IMMO_MODE_PAYANT=1` et `IMMO_STRIPE_CLE_SECRETE` sont définis.
- Lien d'essai privé (15 octobre 2026) : avec `IMMO_STRIPE_ESSAI` défini sur Render, credaura.fr/simulateur?essai=<jeton> affiche les boutons d'achat et verrouille le dossier comme en mode payant, pour cet onglet seulement, même quand `IMMO_MODE_PAYANT` est éteint. credaura.fr/paiement/diagnostic?essai=<jeton> vérifie la configuration (clé, webhook, adresse du site, base des codes, nom du compte Stripe, webhook déclaré chez Stripe) et, en mode test, crée une vraie page de paiement. Le jeton est retiré de l'adresse envoyée à GoatCounter.
- Pages / et /simulateur : la visite reste active 10 minutes sans réponse du navigateur (au lieu de 3 secondes), pour qu'un téléphone qui passe dans un autre onglet ou une autre application ne perde pas la simulation.
- Sortie de bêta (16 octobre 2026) : vérifié en local avec IMMO_MODE_PAYANT=1, aucune mention « bêta », « testeur » ni « offert » ne reste sur l'accueil, le simulateur, Comment ça marche, les CGU, les CGV, la confidentialité, les mentions légales et le contact ; avis « Ton avis » (au lieu de « Ton avis de testeur »), motif de contact « Donner mon avis », message des anciens fichiers « Enregistré avant l'ouverture de la vente ». Tout bascule en allumant IMMO_MODE_PAYANT sur Render, rien à modifier dans le code.
- Textes qui suivent le mode payant : bandeau « bêta », bouton du dossier, titre des tarifs et FAQ de l'accueil ; paragraphes Stripe de la politique de confidentialité ; « En bref », article 2 et article 11 des CGU ; lien « Conditions de vente » des pieds de page.
- Conditions générales de vente (15 octobre 2026, page /cgv, `gui/pages_legales.py`) : vendeur, produit (code de 1, 2 ou 3 dossiers valable 12 mois, un dossier par bien, modifiable 30 jours avec le fichier projet), prix TTC et mention 293 B, commande, paiement Stripe, livraison immédiate, exception au droit de rétractation (L.221-28 13°), garantie légale de conformité des contenus numériques (L.224-25-12 et suivants), limites du dossier (pas de garantie de prêt), service client, médiateur, droit applicable. Tant que le mode payant est éteint, la page s'affiche comme un projet et n'est pas dans les pieds de page. Les champs vides de `app/editeur.py` (adresse, SIRET, téléphone) s'affichent « à compléter » en jaune ; sans médiateur, l'article 14 dit qu'aucun n'est encore désigné et renvoie à l'adresse de contact. Sous les boutons d'achat : « En payant, tu acceptes les conditions de vente » (lien).
- Page d'administration /admin/codes (mot de passe `IMMO_ADMIN_MDP`, à lire dans Render) : bouton « Diagnostic du paiement » (mêmes vérifications que /paiement/diagnostic, plus la clé de signature), création et désactivation de codes, liste des codes. Son contenu n'est construit qu'après le bon mot de passe (15 octobre 2026), pour que ses boutons ne soient pas joignables avant.
- Facture Stripe (`IMMO_STRIPE_FACTURES=1`, 15 octobre 2026) : jointe au reçu par e-mail, elle rappelle la demande d'accès immédiat et la renonciation au droit de rétractation (support durable exigé par L.221-13), le lien des CGV, et porte en pied « David Lehmann EI · SIRET … · TVA non applicable, art. 293 B du CGI ». La page de diagnostic signale la facture éteinte et les champs manquants de `app/editeur.py`. Variable allumée sur Render le 15 octobre 2026 (encore en clés de test), reste à vérifier avec la page de diagnostic.

**Prévu** : compte Stripe et essai en mode test sur le site, puis passage en réel, voir §8.

## 3. Stack et architecture (pour non-développeur)

- **100 % Python**. L'interface (NiceGUI) est séparée de la logique métier (`app/`) : on pourrait changer d'interface sans toucher aux calculs.
- **Deux usages** : site web hébergé (Render) et application Mac autonome, avec le même code.
- **Pas de base de données utilisateur** : le projet vit dans la mémoire du serveur le temps de la visite. Seule exception : la base des codes de dossiers (SQLite sur le disque Render), sans donnée personnelle, utilisée uniquement en mode payant. Pour un achat, elle garde l'identifiant de la session Stripe, le lot et le code ; l'e-mail et la carte restent chez Stripe.
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
- Les régimes sont calculés côte à côte ; le « meilleur régime » est celui qui donne le meilleur enrichissement net sur toute la durée (revente comprise), parmi les régimes éligibles. Avant le 10 octobre 2026, il était choisi sur l'année 1 : la déduction des travaux au réel y faisait choisir le réel et monter le cash-flow quand on ajoutait des travaux.
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
- Rendement brut = loyer annuel ÷ coût total. Net de charges = (loyer − charges de l'an 1) ÷ coût total. Net-net = même chose, impôt de l'année de référence déduit.
- Cash-flow mensuel = (loyers − charges − mensualités − impôt) ÷ 12, pour le meilleur régime, en **année de référence** : la première année pleine après un différé, et au plus tôt l'année 2 (l'année 1 porte des effets ponctuels : déduction des travaux et des frais bancaires au réel, CFE exonérée). Effort d'épargne = le cash-flow s'il est négatif. La cascade « Où va ton loyer » et le comparatif des régimes utilisent la même année.
- « Montant à financer » affiché à côté du sélecteur de crédit : prix + notaire + travaux (+ mobilier) − apport ; les frais bancaires s'y ajoutent dans le montant emprunté.
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
- **Zones sans DVF** (Bas-Rhin, Haut-Rhin, Moselle, Mayotte : `DEPARTEMENTS_SANS_DVF`) : l'utilisateur recopie un repère de prix au m² (MeilleursAgents, SeLoger, agence ou autre), avec fourchette facultative, niveau (à l'adresse ou moyenne de la commune) et date du relevé (`gui/prix_reference.py`, champs `prix_ref_*` de l'étude de marché). Credaura ne va jamais chercher ce chiffre : liens seulement, aucun appel réseau. Validation : 300 à 20 000 €/m², bas ≤ moyen ≤ haut, date pas dans le futur ; avertissement au-delà de 6 mois. Écart = (prix du projet au m² − repère) ÷ repère, avec le même prix au m² que pour DVF (`analyse.prix_projet_m2`). À l'adresse : mêmes seuils que DVF (`SEUIL_PRIX_VERT` 3 %, `SEUIL_PRIX_ORANGE` 10 %) ; repère communal : vert ou orange, jamais rouge. Sans repère : critère Prix non évalué. Le repère est effacé quand on analyse une autre adresse, gardé à la réouverture d'un projet. À l'étape Marché, la comparaison au repère utilise la surface saisie sur cette étape (corrigé le 15 octobre 2026, zones sans DVF seulement) ; en zone DVF, la comparaison garde la surface du financement tant qu'on n'a pas cliqué sur « Suivant » (comportement inchangé, à décider). Dossier : chapitre « Étude de marché » sur le repère (factuel pour la banque, critère du site en plus dans la formule Personnel), sans carte ni liste de ventes ; « Aucun repère de prix n'a été renseigné » sinon.
- Loyer de marché = loyer au m² × surface.

## 5. Entrées et sorties

- **Saisies** :
  - type de projet et structure (en direct, SCI à l'IR, SCI à l'IS) ;
  - adresse, type de bien, surface, prix, travaux, mobilier ;
  - en zone sans DVF : repère de prix au m² (fourchette, niveau, source, date du relevé) ;
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
- **Paiement Stripe Checkout dans un nouvel onglet** (9 octobre 2026) : la page de paiement est celle de Stripe (pas de carte sur le site), et le simulateur reste ouvert dans son onglet, puisque son contenu n'est conservé nulle part. Moyens de paiement réglés dans le tableau de bord Stripe (Stripe refuse le paramètre payment_method_types depuis octobre 2026) : y garder la carte, Apple Pay et Google Pay, des moyens immédiats ; un moyen différé (prélèvement SEPA) livrerait le code seulement à la confirmation, par le webhook. Appels à l'API Stripe avec httpx, sans la bibliothèque Stripe. La renonciation au droit de rétractation (contenu numérique fourni immédiatement) est une case cochée sur le site, notée dans les métadonnées de la session.
- **CGV sans engagement commercial au-delà de la loi** (choix de David, 15 octobre 2026) : pas de remboursement d'un code jamais utilisé, pas de code de remplacement pour un bien décompté deux fois ; seule clause ajoutée, un refus de prêt n'est pas un défaut du dossier et n'est pas remboursé. Pour un remboursement décidé au cas par cas (garantie de conformité, geste), rembourser dans Stripe puis désactiver le code dans /admin/codes.
- **Lancement sans médiateur de la consommation** (choix de David, 15 octobre 2026), en connaissance du risque d'amende administrative : l'article 14 des CGV l'indique tant que `editeur.MEDIATEUR_NOM` est vide, et la page de diagnostic le signale.
- **Clé de signature des fichiers projet définie une fois pour toutes** (15 octobre 2026, générée par Render, jamais affichée) : la changer rendrait illisibles tous les fichiers enregistrés. Les fichiers de la bêta, signés avec la clé de développement (publique, le dépôt GitHub étant public), se rouvrent encore, mais sans débloquer de dossier.
- **Identité du vendeur centralisée dans `app/editeur.py`** : mentions légales, CGU, CGV et factures Stripe lisent les mêmes champs.
- **Mention IOBSP partout, aucun lien vers une banque ou un courtier**, pour rester un outil et non un intermédiaire.
- **Le prix et le loyer saisis ne sont jamais remplacés** par les valeurs de marché.
- **Mesure d'audience sans cookie (GoatCounter)**, donc sans bandeau de consentement.
- **Tutoiement et charte « bleu notaire et laiton »**, avec des polices embarquées pour que le dossier s'affiche à l'identique chez la banque.

## 7. Limites connues, bugs, TODO, questions ouvertes

- **Corrigé le 11 octobre 2026 (`theme.effacer_signalement_a_la_saisie`)** : chaque saisie dans un champ du formulaire (accueil, adresse du marché) retirait la propriété « error », et la saisie suivante provoquait un KeyError dans NiceGUI. La propriété reste désormais, à vide, et le champ n'est renvoyé au navigateur que s'il était signalé « À compléter » : le renvoyer à chaque frappe effaçait les lettres tapées entre-temps (adresse impossible à saisir en ligne, corrigé le même jour). En mode test Stripe, la page /paiement/erreur affiche aussi le message de Stripe pour le diagnostic.
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
- **Taux réduit d'IS supposé toujours applicable.** La flat tax en SCI à l'IS est une simplification (le compte courant d'associé n'est pas modélisé).
- **Achat-revente** : intérêts de portage simples, pas d'assurance emprunteur dans le portage.
- **Reste à vivre non calculé**, alors que c'est un critère bancaire courant.
- **Marché** :
  - pas de DVF en Alsace-Moselle ni à Mayotte, et les ventes ont 6 à 12 mois de décalage ; dans ces zones, le prix est comparé à un repère saisi par l'utilisateur : une estimation en ligne ou d'agence, pas une vente réelle ;
  - loyers peu fiables dans les communes avec peu d'annonces ;
  - aucune donnée ouverte sur les prix en courte durée ;
  - les grands portails d'annonces bloquent l'import par lien.
- **Avant le mode payant** : fait le 15 octobre 2026 sur Render : disque permanent de 1 Go monté sur /var/data (instantané quotidien gardé 7 jours ; plus de déploiement sans coupure), `IMMO_DONNEES_DIR=/var/data`, clé de signature et mot de passe d'administration générés par Render (à lire dans Render, « Show secret »), `IMMO_STRIPE_FACTURES=1`. Reste : les variables Stripe réelles (`IMMO_STRIPE_CLE_SECRETE`, `IMMO_STRIPE_SECRET_WEBHOOK`, `IMMO_URL_SITE`) et le webhook dans le tableau de bord Stripe (événements `checkout.session.completed` et `checkout.session.async_payment_succeeded`, adresse https://credaura.fr/stripe/webhook). Activer les reçus par e-mail dans Stripe.
- **Paiement, limites** : dans le navigateur intégré d'Instagram ou de TikTok, le nouvel onglet peut remplacer le simulateur ; le code reste affiché sur la page de remerciement, à entrer après avoir refait ou rouvert le projet. Un acheteur qui ferme tout avant la page de remerciement retrouve son code par le support (métadonnées du paiement chez Stripe). Pas de case « J'accepte les CGV » sur la page Stripe tant que `IMMO_STRIPE_CGV` n'est pas à 1 (il faut d'abord l'adresse https://credaura.fr/cgv dans les informations publiques du compte Stripe) ; pas de facture Stripe, donc pas de confirmation de la renonciation sur support durable, tant que `IMMO_STRIPE_FACTURES` n'est pas à 1 (à allumer avant l'ouverture et à vérifier avec la page de diagnostic). Une nouvelle saisie du code pour un bien déjà ouvert, sans le fichier projet, décompte un nouveau dossier [piste : reconnaître le même bien pendant 30 jours]. L'application Mac n'a pas de boutons d'achat (codes locaux).

## 8. Roadmap (dans le dépôt : `gui/offre.py`, README, commits)

- **Ouverture de la vente** : déclarer la micro-entreprise, créer le compte Stripe, essayer le parcours en mode test sur le site, puis passer en clés réelles et allumer le mode payant (le paiement, le bandeau, les tarifs, la FAQ et la confidentialité suivent l'interrupteur). Obligations légales avant le premier paiement : remplir `app/editeur.py` (statut EI, adresse, SIRET, téléphone, médiateur), ce qui complète les mentions légales et les CGV (rédigées le 15 octobre 2026) ; adhésion à un médiateur de la consommation (David démarre sans, à ajouter ensuite) ; `IMMO_STRIPE_FACTURES=1` ; prix affichés TTC ; relecture des CGU et CGV par un juriste conseillée. Dépôt de la marque à l'INPI recommandé.
- **Hors dépôt** [à confirmer, source : plan de commercialisation] :
  - témoignages vérifiés sur l'accueil ;
  - pages villes et articles pour Google ;
  - baromètre ;
  - affiliation ;
  - offre Pro (crédits, dossier à la marque d'un cabinet) ;
  - médiateur de la consommation (les CGV sont en ligne depuis le 15 octobre 2026).
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
- **Mode payant** : interrupteur `IMMO_MODE_PAYANT`, éteint pendant la bêta. Les boutons d'achat demandent en plus la clé Stripe.
- **Session de paiement** : page de paiement Stripe créée pour un lot (identifiant `cs_…`), reliée à l'onglet du simulateur par un identifiant d'achat aléatoire.
