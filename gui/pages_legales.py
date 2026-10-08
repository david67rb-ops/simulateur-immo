"""Pages légales du site : mentions légales (LCEN, art. 6) et politique de
confidentialité (RGPD, art. 13), avec les liens de pied de page.

Les informations sur l'éditeur sont regroupées ci-dessous : à mettre à jour
à l'immatriculation (statut, SIRET) et à chaque changement d'adresse.
"""
from __future__ import annotations

from nicegui import app, ui

from app.chapitres_dossier import MENTION_LEGALE

from . import statistiques, theme
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
MISE_A_JOUR = "5 octobre 2026"

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

## Propriété intellectuelle

Le nom Credaura, le logo, les textes, la mise en page et le code du site appartiennent à l'éditeur.
Toute reproduction ou réutilisation sans autorisation écrite est interdite. Les dossiers que vous
générez vous appartiennent : vous pouvez les utiliser et les transmettre librement.

## Données publiques et crédits

- Base Adresse Nationale, demandes de valeurs foncières (DVF, DGFiP), carte des loyers (DHUP / ANIL) et
  découpage administratif (geo.api.gouv.fr) : données publiques réutilisées sous Licence Ouverte Etalab 2.0.
- Fréquentation touristique : Eurostat.
- Fonds de carte : © les contributeurs d'[OpenStreetMap](https://www.openstreetmap.org/copyright) (licence ODbL).
- Polices Sora et Public Sans : SIL Open Font License.

## Données personnelles

Credaura ne demande ni compte ni adresse e-mail et ne conserve aucune information saisie.
Le détail figure dans la [politique de confidentialité](/confidentialite).
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
    with colonne:
        ui.markdown(
            f"""
**En bref :** Credaura ne vous demande ni compte ni adresse e-mail, et ne conserve aucune des informations
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

Base légale : la fourniture du service que vous demandez (article 6.1.b du RGPD) pour votre projet et
votre situation ; l'intérêt légitime à assurer la sécurité du site (article 6.1.f) pour les données techniques et à
répondre aux messages reçus.

## Combien de temps

- Votre projet et votre situation restent uniquement dans la mémoire du serveur pendant votre visite :
  ils ne sont écrits dans aucune base de données ni aucun fichier, et sont effacés peu après la fermeture
  de la page. Rechargez la page et tout repart de zéro.
- Le dossier Word est fabriqué à la demande et téléchargé sur votre appareil. Pour l'aperçu, il est gardé
  en mémoire le temps de l'afficher, à une adresse à usage unique.
- Les journaux techniques de l'hébergeur sont conservés pour une durée limitée, selon sa propre politique.
  Ils ne contiennent pas les informations que vous saisissez.
- Les messages reçus par e-mail sont conservés le temps de traiter votre demande ; vous pouvez demander
  leur suppression à tout moment.

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
{prestataire}
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

Cette politique sera mise à jour si le service évolue, en particulier à l'ouverture du paiement en ligne.
La date de dernière mise à jour figure en haut de la page.
"""
        ).classes("texte-legal w-full")
    _pied(colonne)
