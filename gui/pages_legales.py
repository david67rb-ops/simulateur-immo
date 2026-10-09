"""Pages légales du site : mentions légales (LCEN, art. 6), conditions
générales d'utilisation et politique de confidentialité (RGPD, art. 13),
avec les liens de pied de page.

Les informations sur l'éditeur sont regroupées ci-dessous : à mettre à jour
à l'immatriculation (statut, SIRET) et à chaque changement d'adresse.
"""
from __future__ import annotations

from nicegui import app, ui

from app import paiement
from app.chapitres_dossier import MENTION_LEGALE

from . import offre, statistiques, theme
from .accueil import barre_menu

# --- Éditeur (adresse vide = éditeur non professionnel, avant l'immatriculation)
EDITEUR_NOM = "David Lehmann"
EDITEUR_STATUT = ""  # ex. « entrepreneur individuel », après immatriculation
EDITEUR_ADRESSE = ""
EDITEUR_SIRET = ""
CONTACT_EMAIL = "credaura.contact@gmail.com"

HEBERGEUR = (
    "Render Services, Inc., 525 Brannan Street, Suite 300, San Francisco, CA 94107, "
    "États-Unis · +1 415 319 8186 · [render.com](https://render.com)"
)
MISE_A_JOUR = "9 octobre 2026"

A_COMPLETER = '<span style="background:#fde68a;color:#7c2d12;padding:0 4px;border-radius:4px">à compléter</span>'


def _contact() -> str:
    return f"[{CONTACT_EMAIL}](mailto:{CONTACT_EMAIL})" if CONTACT_EMAIL else A_COMPLETER


def liens_legaux(nouvel_onglet: bool = False) -> None:
    """Pied de page : depuis le simulateur, les pages s'ouvrent dans un nouvel
    onglet pour ne pas perdre la simulation en cours. Rien dans l'application
    de bureau, qui ne collecte rien en ligne."""
    if app.native.main_window:
        return
    cible = ' target="_blank" rel="noopener"' if nouvel_onglet else ""
    with ui.row().classes("w-full justify-center gap-x-5 gap-y-1 text-xs mb-4"):
        for adresse, texte in (
            ("/contact", "Nous contacter"),
            ("/mentions-legales", "Mentions légales"),
            ("/cgu", "Conditions d'utilisation"),
            ("/confidentialite", "Confidentialité"),
        ):
            ui.html(f'<a href="{adresse}"{cible} class="lien-exemple">{texte}</a>')


def _gabarit(titre: str, date: bool = True):
    """Bandeau du menu de l'accueil (fixé en haut, avec « Accueil ») et
    colonne de lecture."""
    theme.apply_theme()
    statistiques.installer()
    ui.dark_mode(value=None)
    ui.add_css(
        ".nicegui-content { padding: 0 !important; gap: 0 !important; }"
        ".texte-legal h2 { font-family: Sora, sans-serif; font-size: 1.15rem; font-weight: 600; line-height: 1.3; margin: 1.6em 0 0.4em; }"
        ".texte-legal p, .texte-legal li { line-height: 1.6; }"
        ".texte-legal ul { list-style: disc; padding-left: 1.3em; margin: 0.4em 0; }"
        ".texte-legal a { color: var(--c-marque-texte); }"
    )
    barre_menu(sur_accueil=False)
    colonne = ui.column().classes("w-full max-w-3xl mx-auto gap-2 p-4 pt-8 pb-10")
    with colonne:
        # Même bouton que dans le simulateur, visible aussi sur téléphone
        # (où « Accueil » est rangé dans le menu).
        with ui.element("a").props('href="/"').classes(
            "flex items-center gap-1 no-underline text-[color:var(--c-marque-texte)] font-semibold text-sm -ml-1 mb-1"
        ):
            ui.icon("arrow_back", size="20px")
            ui.label("Accueil")
        ui.label(titre).classes("text-3xl font-bold titre-sora")
        if date:
            ui.label(f"Dernière mise à jour : {MISE_A_JOUR}").classes(theme.HINT_CLASSES)
    return colonne


def _pied(colonne) -> None:
    with colonne:
        ui.separator().classes("mt-6")
        with ui.row().classes("w-full justify-between items-center"):
            ui.html('<a href="/" class="lien-exemple text-sm">← Revenir à l\'accueil</a>')
        liens_legaux()


@ui.page("/mentions-legales", title="Mentions légales · Credaura")
def page_mentions_legales() -> None:
    colonne = _gabarit("Mentions légales")
    editeur = EDITEUR_NOM + (f", {EDITEUR_STATUT}" if EDITEUR_STATUT else "")
    if EDITEUR_ADRESSE:
        identite = f"Adresse : {EDITEUR_ADRESSE}<br>\nContact : {_contact()}<br>\n" + (
            f"SIRET : {EDITEUR_SIRET}." if EDITEUR_SIRET else "SIRET : en cours d'immatriculation."
        )
    else:
        # Avant l'immatriculation : éditeur non professionnel, dispensé de
        # publier son adresse (LCEN, art. 6) ; elle est connue de l'hébergeur.
        identite = (
            f"Contact : {_contact()}<br>\n"
            "Activité en cours d'immatriculation. Éditeur à titre non professionnel : conformément à "
            "l'article 6 de la loi pour la confiance dans l'économie numérique, son adresse n'est pas "
            "publiée ; son identité est connue de l'hébergeur."
        )
    with colonne:
        ui.markdown(
            f"""
## Éditeur du site

Le site credaura.fr est édité par {editeur}.

{identite}

Directeur de la publication : {EDITEUR_NOM}.

## Hébergement

{HEBERGEUR}

## Nature du service

{MENTION_LEGALE}

Les résultats sont des estimations calculées à partir des informations que vous saisissez et de données
publiques qui peuvent comporter des erreurs ou des retards. Ils ne garantissent ni la rentabilité d'un
projet, ni l'accord d'une banque : vérifiez-les et, au besoin, faites-vous accompagner par un professionnel.
Les règles d'utilisation du site figurent dans les [conditions générales d'utilisation](/cgu).

## Propriété intellectuelle

Le nom Credaura, le logo, les textes, la mise en page et le code du site appartiennent à l'éditeur.
Toute reproduction ou réutilisation sans autorisation écrite est interdite. Les dossiers que vous
générez vous appartiennent : vous pouvez les utiliser et les transmettre librement.

## Données publiques et crédits

- Base Adresse Nationale, demandes de valeurs foncières (DVF, DGFiP), carte des loyers (DHUP / ANIL) et
  découpage administratif (geo.api.gouv.fr) : données publiques réutilisées sous Licence Ouverte Etalab 2.0.
- Fréquentation touristique : Eurostat.
- Fonds de carte du site : © les contributeurs d'[OpenStreetMap](https://www.openstreetmap.org/copyright) (licence ODbL) ; cartes du dossier : Plan IGN (Géoplateforme), Licence Ouverte Etalab 2.0.
- Polices Sora et Public Sans : SIL Open Font License.

## Données personnelles

Credaura ne demande ni compte ni adresse e-mail et ne conserve aucune information saisie.
Le détail figure dans la [politique de confidentialité](/confidentialite).
"""
        ).classes("texte-legal w-full")
    _pied(colonne)


@ui.page("/cgu", title="Conditions d'utilisation · Credaura")
def page_cgu() -> None:
    colonne = _gabarit("Conditions générales d'utilisation")
    with colonne:
        ui.markdown(
            f"""
**En bref :** Credaura est un outil de calcul, gratuit pendant la bêta et sans compte. Ses résultats sont
des estimations, pas un conseil : vous restez seul juge de votre projet, et la banque reste seule
décisionnaire de votre prêt.

## 1. Objet

Les présentes conditions générales d'utilisation (CGU) encadrent l'utilisation du site credaura.fr et de
ses services, édités par {EDITEUR_NOM} (voir les [mentions légales](/mentions-legales)). Utiliser le site
vaut acceptation de ces conditions ; si vous ne les acceptez pas, n'utilisez pas le site.

## 2. Le service

Credaura permet de :

- simuler la rentabilité d'un investissement immobilier (location longue durée, location courte durée,
  achat-revente) : coût du projet, financement, cash-flow, fiscalité et taux d'endettement ;
- réaliser une étude de marché du quartier à partir de données publiques (ventes réelles, loyers de
  référence, fréquentation touristique) ;
- générer un dossier de financement au format Word, à présenter à une banque ;
- enregistrer son projet dans un fichier gardé sur son appareil, pour le reprendre plus tard.

Pendant la bêta, le service est entièrement gratuit, et ses fonctions peuvent évoluer, être modifiées ou
retirées. À l'ouverture de la vente, le dossier de financement deviendra payant : son achat sera régi par
des conditions générales de vente, présentées avant tout paiement. Les présentes conditions continueront
de s'appliquer à l'utilisation du site.

## 3. Accès au site

Le site est accessible gratuitement, sans compte, à toute personne disposant d'un accès à internet ; les
frais de connexion restent à votre charge. L'éditeur s'efforce de le maintenir accessible, sans pouvoir
le garantir : il peut être interrompu pour une maintenance, une mise à jour, une panne de l'hébergeur ou
l'indisponibilité d'une source de données publiques. Une interruption ne donne droit à aucune indemnité.

Comme rien n'est conservé sur le serveur, une simulation en cours peut être perdue lors d'une interruption
ou d'un rechargement de la page : utilisez « Enregistrer mon projet » pour la garder.

## 4. Nature des résultats

{MENTION_LEGALE}

Les résultats sont des estimations :

- ils reposent sur les informations que vous saisissez, dont vous êtes seul responsable de l'exactitude ;
- ils utilisent des données publiques (ventes DVF, loyers de référence, barèmes fiscaux) qui peuvent
  comporter des erreurs, des lacunes ou des retards ;
- ils appliquent des règles et des hypothèses simplifiées (fiscalité, frais de notaire, assurance,
  évolution des loyers et des prix), rappelées à la fin du dossier, qui ne reflètent pas forcément votre
  situation personnelle ni les critères de votre banque ;
- l'étude de marché, le verdict et les indicateurs ne sont ni une expertise ni une estimation immobilière,
  ni une recommandation d'acheter ou de vendre.

Avant toute décision (offre d'achat, demande de prêt, choix d'un régime fiscal), vérifiez les résultats
et, au besoin, faites-vous accompagner par un professionnel : notaire, expert-comptable, conseiller en
gestion de patrimoine ou courtier.

## 5. Vos engagements

En utilisant le site, vous vous engagez à :

- l'utiliser pour un usage personnel et conforme à la loi ;
- ne saisir les informations d'une autre personne (un co-emprunteur, par exemple) qu'avec son accord ;
- n'ajouter au dossier que des photos dont vous détenez les droits, sans contenu illicite ;
- ne pas perturber le fonctionnement du site, ne pas tenter d'en contourner les protections, et ne pas
  l'interroger de façon automatisée ou massive (robots, aspiration de données) ;
- ne pas remettre un dossier que vous savez inexact ou modifié de façon trompeuse : le dossier engage la
  personne qui le présente à sa banque.

L'éditeur peut restreindre l'accès au site en cas d'utilisation contraire à ces règles.

## 6. Responsabilité

L'éditeur met en œuvre des moyens raisonnables pour fournir des calculs justes et un site fiable : il est
tenu d'une obligation de moyens, et non de résultat. Il ne peut être tenu responsable :

- des décisions prises sur la base des résultats, notamment d'un achat, de l'accord ou du refus d'un prêt,
  ou d'une rentabilité inférieure aux prévisions ;
- des conséquences d'informations inexactes ou incomplètes saisies par l'utilisateur ;
- des erreurs ou retards des données publiques et des services extérieurs utilisés par le site ;
- d'une interruption du site ou de la perte d'une simulation non enregistrée ;
- de l'usage fait du dossier une fois téléchargé.

Ces limites s'appliquent dans la mesure permise par la loi. Elles n'écartent pas la responsabilité de
l'éditeur en cas de faute lourde ou intentionnelle, et ne retirent rien aux droits que le Code de la
consommation reconnaît aux consommateurs.

## 7. Propriété intellectuelle

Le nom Credaura, le logo, les textes, la mise en page, la structure du dossier et le code du site
appartiennent à l'éditeur. Vous pouvez les consulter et les utiliser pour votre usage personnel ; toute
reproduction ou réutilisation, totale ou partielle, sans autorisation écrite est interdite. Les données
publiques utilisées et leurs licences sont citées dans les [mentions légales](/mentions-legales).

Les dossiers que vous générez vous appartiennent : vous pouvez les utiliser, les modifier et les
transmettre librement, notamment à votre banque. Les photos que vous ajoutez restent les vôtres : le site
les traite seulement (recadrage) pour les insérer dans votre dossier, et n'en garde aucune copie.

## 8. Fichier projet

« Enregistrer mon projet » crée un fichier sur votre appareil. Le site n'en garde aucune copie : sa
conservation est de votre ressort. Le fichier est protégé contre les modifications : modifié en dehors du
site, il ne peut plus être rouvert.

## 9. Données personnelles

Le traitement de vos informations est décrit dans la [politique de confidentialité](/confidentialite).
En résumé : ni compte, ni adresse e-mail, et rien de ce que vous saisissez n'est conservé après votre visite.

## 10. Liens vers d'autres sites

Le site propose des liens vers des sites extérieurs (recherches de prix, annonces, réseaux sociaux).
L'éditeur n'en contrôle pas le contenu et n'en est pas responsable.

## 11. Modification des conditions

L'éditeur peut modifier ces conditions, notamment à l'ouverture de la vente. La version applicable est
celle en ligne au moment où vous utilisez le site ; la date de dernière mise à jour figure en haut de la page.

## 12. Droit applicable et litiges

Ces conditions sont soumises au droit français. En cas de difficulté, écrivez d'abord à {_contact()} :
nous chercherons ensemble une solution amiable. À défaut, le litige sera porté devant le tribunal
compétent ; si vous êtes consommateur, vous pouvez saisir celui de votre domicile.
"""
        ).classes("texte-legal w-full")
    _pied(colonne)


@ui.page("/confidentialite", title="Confidentialité · Credaura")
def page_confidentialite() -> None:
    colonne = _gabarit("Politique de confidentialité")
    # Paragraphes sur la mesure d'audience, seulement quand elle est active.
    if statistiques.CODE:
        en_bref = "Une mesure d'audience anonyme, sans cookie ; aucune publicité, aucun cookie tiers."
        prestataire = (
            "- **GoatCounter** (statistiques de fréquentation) : votre navigateur y charge un petit script qui compte "
            "les pages vues, la provenance et le type d'appareil, sans cookie ni identifiant ; il reçoit votre "
            "adresse IP, qu'il n'enregistre pas. Sont aussi comptés, sans aucun contenu, le lancement d'une "
            "vérification et le téléchargement d'un dossier.\n"
        )
    else:
        en_bref = "Aucune mesure d'audience, aucune publicité, aucun cookie tiers."
        prestataire = ""
    # Paragraphes sur le paiement, seulement quand la vente est ouverte.
    vente = offre.MODE_PAYANT and paiement.actif()
    if vente:
        sans_email = (
            "Credaura ne vous demande ni compte ni adresse e-mail (si vous achetez un dossier, c'est Stripe, le "
            "prestataire de paiement, qui vous demande la vôtre pour le reçu), et ne conserve aucune des informations"
        )
        info_paiement = (
            "- **Votre paiement, si vous achetez un dossier** : il se fait sur la page sécurisée de Stripe, qui "
            "recueille votre adresse e-mail et les données de votre carte. Credaura ne les voit pas : il reçoit "
            "seulement la confirmation du paiement, le lot acheté et la référence du paiement, auxquels il associe "
            "votre code de dossier.\n"
        )
        base_paiement = (
            " ; l'exécution de la vente (article 6.1.b) et les obligations comptables (article 6.1.c) pour le "
            "paiement"
        )
        duree_paiement = (
            "- Le code de dossier et la référence du paiement sont conservés le temps d'utiliser le code (12 mois) "
            "et de tenir la comptabilité. Stripe conserve les données du paiement selon ses propres obligations.\n"
        )
        prestataire_paiement = (
            "- **Stripe** (paiement, Irlande et États-Unis, adhérent au Data Privacy Framework) : traite le paiement "
            "et vous envoie le reçu, selon sa propre [politique de confidentialité](https://stripe.com/fr/privacy).\n"
        )
        modifications = "Cette politique sera mise à jour si le service évolue."
    else:
        sans_email = "Credaura ne vous demande ni compte ni adresse e-mail, et ne conserve aucune des informations"
        info_paiement = base_paiement = duree_paiement = prestataire_paiement = ""
        modifications = "Cette politique sera mise à jour si le service évolue, en particulier à l'ouverture du paiement en ligne."
    with colonne:
        ui.markdown(
            f"""
**En bref :** {sans_email}
que vous saisissez. Elles servent au calcul et à votre dossier, puis disparaissent quand vous quittez la page.
{en_bref}

## Responsable du traitement

{EDITEUR_NOM}, éditeur du site (voir les [mentions légales](/mentions-legales)). Contact : {_contact()}.

## Les informations traitées et pourquoi

- **Votre projet** : adresse et caractéristiques du bien, prix, travaux, loyers, financement, fiscalité.
  Ils servent à calculer la rentabilité et à réaliser l'étude de marché du quartier.
- **Votre situation, si vous la renseignez** : nom de l'emprunteur, revenus du foyer, crédits en cours,
  patrimoine, photos du bien. Ils servent uniquement au calcul du taux d'endettement et au dossier de financement.
- **Données techniques** : adresse IP, type de navigateur, pages demandées, date et heure. Elles sont
  enregistrées par l'hébergeur pour faire fonctionner et sécuriser le site.
- **Vos messages, si vous écrivez** (page [Nous contacter](/contact)) : votre adresse e-mail et le contenu
  du message, pour vous répondre.
{info_paiement}
Base légale : la fourniture du service que vous demandez (article 6.1.b du RGPD) pour votre projet et
votre situation ; l'intérêt légitime à assurer la sécurité du site (article 6.1.f) pour les données techniques et à
répondre aux messages reçus{base_paiement}.

## Combien de temps

- Votre projet et votre situation restent uniquement dans la mémoire du serveur pendant votre visite :
  ils ne sont écrits dans aucune base de données ni aucun fichier, et sont effacés peu après la fermeture
  de la page. Rechargez la page et tout repart de zéro.
- Le dossier Word est fabriqué à la demande et téléchargé sur votre appareil. Pour l'aperçu, il est gardé
  en mémoire le temps de l'afficher, à une adresse à usage unique.
- « Enregistrer mon projet » crée un fichier sur votre appareil, et nulle part ailleurs : le site n'en garde
  aucune copie. Vous le rouvrez quand vous le souhaitez pour reprendre votre projet.
- Les journaux techniques de l'hébergeur sont conservés pour une durée limitée, selon sa propre politique.
  Ils ne contiennent pas les informations que vous saisissez.
- Les messages reçus par e-mail sont conservés le temps de traiter votre demande ; vous pouvez demander
  leur suppression à tout moment.
{duree_paiement}
## Qui y a accès

Personne d'autre que vous : vos informations ne sont ni vendues, ni louées, ni partagées. Le site fait
appel à des prestataires techniques, chacun pour une seule raison :

- **Render** (hébergeur, États-Unis) : exécute le site. Render adhère au cadre de protection des données
  UE–États-Unis (Data Privacy Framework), qui encadre ce transfert hors de l'Union européenne.
- **Base Adresse Nationale** (État français) : notre serveur lui envoie l'adresse du bien pour la situer
  sur la carte, sans votre nom ni votre adresse IP.
- **OpenStreetMap** (Royaume-Uni, pays reconnu par l'Union européenne comme offrant une protection adéquate) :
  votre navigateur y charge les fonds de carte, ce qui lui transmet votre adresse IP.
- **jsDelivr** (réseau de diffusion de fichiers) : votre navigateur y charge les deux bibliothèques qui
  affichent l'aperçu du dossier, ce qui lui transmet votre adresse IP.
- **Google** (messagerie Gmail, États-Unis, adhérent au Data Privacy Framework) : reçoit les messages
  que vous envoyez à l'adresse de contact.
{prestataire}{prestataire_paiement}
Les liens vers des sites extérieurs (recherches de prix, annonces) ne transmettent rien tant que vous
ne cliquez pas dessus.

## Cookies

Le site dépose un seul cookie, technique, qui maintient la liaison entre votre page et le serveur.
Indispensable au fonctionnement, il est dispensé de consentement (recommandations de la CNIL).
Aucun cookie de mesure d'audience, de publicité ou de réseau social.

## Vos droits

Vous disposez des droits d'accès, de rectification, d'effacement, de limitation, d'opposition et de
portabilité. Comme rien n'est conservé après votre visite, aucune information ne peut être retrouvée
ensuite ; pour toute question, écrivez à {_contact()}.

Vous pouvez aussi adresser une réclamation à la CNIL : [cnil.fr](https://www.cnil.fr/fr/plaintes),
3 place de Fontenoy, TSA 80715, 75334 Paris Cedex 07.

## Sécurité

Les échanges avec le site sont chiffrés (HTTPS). Les aperçus de dossier sont servis à une adresse
aléatoire, valable une seule fois.

## Modifications

{modifications}
La date de dernière mise à jour figure en haut de la page.
"""
        ).classes("texte-legal w-full")
    _pied(colonne)
