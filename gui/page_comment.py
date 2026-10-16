"""Page « Comment ça marche » : le parcours détaillé, de l'adresse du bien au
dossier pour la banque, avec les données utilisées et les limites. Les
chiffres cités (seuils, rayons, taux) sont ceux du code : à mettre à jour
avec lui (voir CONTEXTE_CREDAURA.md, logique métier)."""
from __future__ import annotations

from nicegui import ui

from . import offre
from .pages_legales import _gabarit, _pied

CSS = """
.etapes-comment { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 12px; margin: 8px 0 4px; }
.etapes-comment > a { display: flex; gap: 12px; align-items: flex-start; padding: 14px 16px; border-radius: 14px;
  border: 1px solid var(--c-filet); text-decoration: none; color: inherit; }
.etapes-comment > a:hover { border-color: var(--c-laiton); }
.etapes-comment .numero { flex: none; width: 30px; height: 30px; border-radius: 50%; background: var(--c-laiton); color: #fff;
  display: flex; align-items: center; justify-content: center; font-weight: 700; font-family: Sora, sans-serif; }
.etapes-comment .titre { font-weight: 600; }
.etapes-comment .texte { font-size: 0.88rem; opacity: 0.75; }
.texte-legal [id] { scroll-margin-top: 84px; }
.appel-comment { display: flex; flex-wrap: wrap; gap: 10px; margin-top: 18px; }
.appel-comment a { padding: 11px 18px; border-radius: 10px; font-weight: 700; text-decoration: none; }
.appel-comment .principal { background: var(--c-laiton); color: #fff; }
.appel-comment .secondaire { border: 1.5px solid var(--c-filet); color: inherit; }
"""

ETAPES = (
    ("1", "Tu entres ton projet", "L'adresse, la surface et le prix. Le reste, je l'estime.", "#projet"),
    ("2", "Je vérifie", "Prix face aux ventes réelles, loyer, rentabilité, endettement.", "#prix"),
    ("3", "Tu repars avec ton dossier", "Un dossier Word clair, à remettre à ta banque.", "#dossier"),
)


def _texte_prix_dossier() -> str:
    if offre.MODE_PAYANT:
        return (
            "La vérification est gratuite. Le dossier est payant, sans abonnement : les prix sont sur la "
            "[page d'accueil](/#tarifs). Avant de payer, tu feuillettes un aperçu de ton propre dossier."
        )
    return (
        "La vérification est gratuite. Pendant la bêta, le dossier l'est aussi ; les tarifs prévus à "
        "l'ouverture de la vente sont sur la [page d'accueil](/#tarifs)."
    )


@ui.page("/comment-ca-marche", title="Comment ça marche · Credaura")
def page_comment() -> None:
    colonne = _gabarit("Comment ça marche", date=False)
    ui.add_css(CSS)
    with colonne:
        ui.label(
            "De l'adresse du bien au dossier pour ta banque : ce que fait Credaura à chaque étape, avec quelles "
            "données, et ce qu'il ne fait pas. Pas de compte, pas d'e-mail, rien n'est conservé."
        ).classes("text-base mt-2")
        ui.html(
            '<div class="etapes-comment">'
            + "".join(
                f'<a href="{ancre}"><span class="numero">{n}</span><span><span class="titre">{titre}</span><br>'
                f'<span class="texte">{texte}</span></span></a>'
                for n, titre, texte, ancre in ETAPES
            )
            + "</div>"
        ).classes("w-full")
        ui.markdown(
            f"""
<h2 id="projet">1. Tu entres ton projet</h2>

Depuis la page d'accueil, **quatre informations suffisent** : l'adresse du bien, appartement ou maison, la
surface et le prix affiché. Ajoute ton loyer si tu le connais ; sinon, je prends le loyer du marché.

Pour aller plus loin, le simulateur complet te guide en six étapes : **Marché, Financement, Revenus et
fiscalité, Résultats, Endettement, Dossier**. Il couvre :

- la **location longue durée**, nue ou meublée ;
- la **location courte durée** (type Airbnb), avec la saisonnalité mois par mois ;
- l'**achat-revente**, avec la marge nette après frais et impôts ;
- un achat **en direct ou en SCI** (à l'impôt sur le revenu ou à l'impôt sur les sociétés).

Tu peux aussi coller le lien d'une annonce pour préremplir l'adresse, la surface et le prix (les grands
portails bloquent souvent cette lecture : tu saisis alors à la main).

Chaque valeur que je calcule pour toi, comme les frais de notaire, apparaît sur fond bleu : tu peux la
modifier à tout moment.

<h2 id="prix">2. Je compare ton prix aux ventes réelles du quartier</h2>

Je cherche les **ventes réellement conclues** autour du bien, dans la base publique des demandes de valeurs
foncières (DVF), tenue par l'État :

- même type de bien, dans l'ancien ou dans le neuf selon ton projet ;
- une surface proche de la tienne (à 30 % près) ;
- dans un rayon de 500 m, sur les 24 derniers mois publiés.

S'il y a moins de 15 ventes, j'élargis la recherche (1 km, puis 2 km, puis des surfaces plus variées) et je
te le signale. Tu obtiens la **médiane** des prix au m², une **fourchette** (80 % des ventes s'y situent) et
un niveau de fiabilité, selon le nombre de ventes trouvées et l'élargissement éventuel.

Ton prix au m² est ensuite situé face à cette médiane : jusqu'à 3 % au-dessus, il est **conforme au
marché** ; de 3 à 10 % au-dessus, il y a **une marge de négociation** ; au-delà, il est **à justifier ou à
négocier**.

**En Alsace-Moselle et à Mayotte**, les ventes ne sont pas publiées dans cette base (en Alsace-Moselle, à
cause du régime du Livre foncier). Je te demande alors de recopier le prix au m² que tu lis sur MeilleursAgents
ou dans une estimation d'agence. Je ne vais jamais chercher ce chiffre moi-même.

**Le loyer de marché** vient de la carte des loyers publiée par le ministère du Logement et l'ANIL. En
courte durée, faute de données publiques sur les prix des nuitées, je l'estime à partir du loyer nu du
secteur : c'est un ordre de grandeur, à recouper avec les annonces du quartier.

<h2 id="rentabilite">3. Je calcule la rentabilité, après crédit et impôts</h2>

- **Le coût total** : prix, frais de notaire (calculés automatiquement au barème en vigueur), travaux,
  mobilier et frais bancaires.
- **Le crédit** : mensualité, assurance emprunteur, différé éventuel. Le montant à financer s'affiche
  pendant la saisie.
- **Les charges** : copropriété, taxe foncière, assurance, entretien, gestion, vacance locative.
- **L'impôt** : je calcule tous les régimes possibles côte à côte (micro-foncier, réel, micro-BIC, LMNP
  au réel, SCI à l'IS) et je retiens **le plus favorable sur la durée du projet**.

Tu obtiens alors :

- le **cash-flow mensuel** : ce qui te reste chaque mois après loyer, charges, crédit et impôts, pour une
  année courante (après un éventuel différé, hors effets ponctuels de la première année) ;
- l'**effort d'épargne**, si ce cash-flow est négatif ;
- les **rendements** brut, net de charges et net-net ;
- l'**enrichissement** sur 20 ans, revente comprise, et le **TRI** ;
- le **prix d'achat maximum** pour rester à l'équilibre ;
- des **scénarios de stress** : loyer en baisse, vacance plus longue, taux plus élevé.

<h2 id="verdict">4. Le verdict, en trois critères</h2>

Le verdict reprend les trois questions que se pose ton banquier :

- **La rentabilité** : le bien s'autofinance-t-il, ou combien dois-tu ajouter chaque mois ?
- **Le prix** : est-il cohérent avec les ventes du quartier ?
- **Le financement** : ton taux d'endettement, ou à défaut ton apport.

Chaque critère est vert, orange ou rouge, et le verdict prend **le moins bon des trois** : *projet solide*,
*projet à renforcer* ou *projet à revoir*. Tu vois tout de suite sur quoi agir : négocier le prix,
augmenter l'apport, allonger la durée…

<h2 id="endettement">5. Ton taux d'endettement, calculé comme la banque</h2>

Je divise tes mensualités (crédits en cours et nouveau crédit, assurance comprise) par tes revenus, en
comptant 70 % des loyers du projet, comme le font la plupart des banques. Le seuil de référence est de
**35 %**, fixé par le Haut Conseil de stabilité financière. Si un différé est prévu, je retiens la mensualité
qui suit le différé, par prudence.

<h2 id="dossier">6. Tu repars avec ton dossier de financement</h2>

Un **dossier Word d'une quinzaine de pages**, à ton nom, que tu peux encore modifier avant de l'envoyer :

- **Le bien** : sa situation sur la carte, tes photos, l'étude de marché, le projet et son coût ;
- **La rentabilité** : recettes et charges, où va le loyer chaque mois, évolution de ton patrimoine ;
- **Le financement** : plan de financement, ton profil, ton taux d'endettement ;
- **La conclusion** : la synthèse, les points d'attention, les pièces à fournir à la banque, et les
  hypothèses de calcul.

Trois formules : **Complet**, **Banque** (sans ton patrimoine détaillé) et **Personnel** (pour toi, avec le
verdict du site). Avant de télécharger, tu vois un aperçu. Tu peux aussi feuilleter un
[exemple de dossier complet](/exemple-dossier).

{_texte_prix_dossier()}

<h2 id="donnees">7. Tes données restent chez toi</h2>

Tes saisies servent au calcul et à ton dossier, puis disparaissent quand tu quittes la page. Pour reprendre
plus tard, **« Enregistrer mon projet »** crée un fichier sur ton appareil, et nulle part ailleurs. Le détail
est dans la [politique de confidentialité](/confidentialite).

<h2 id="limites">8. Ce que Credaura ne fait pas</h2>

- **Ce n'est pas un conseil** en investissement, en financement ou en fiscalité : ce sont des calculs à
  partir de tes saisies et de données publiques.
- **Credaura n'est ni une banque ni un courtier** : il ne propose aucun crédit et ne te met en relation
  avec aucun établissement. Ta banque reste seule décisionnaire.
- **Le dossier ne garantit pas ton prêt.** Il présente ton projet clairement, avec des chiffres vérifiables.
- **Les données publiques ont des limites** : les ventes sont publiées avec 6 à 12 mois de décalage, les
  loyers sont moins fiables dans les petites communes, et l'impôt est calculé avec ta tranche d'imposition,
  pas avec la déclaration complète de ton foyer. Fais vérifier ton projet par un professionnel avant de
  t'engager.
"""
        ).classes("texte-legal w-full")
        ui.html(
            '<div class="appel-comment">'
            '<a class="principal" href="/#verifier">Vérifier mon projet gratuitement</a>'
            '<a class="secondaire" href="/simulateur">Ouvrir le simulateur complet</a>'
            "</div>"
        )
    _pied(colonne)
