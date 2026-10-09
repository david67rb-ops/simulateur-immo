"""Thème visuel de l'application : couleurs, typographie, composants stylés
réutilisables. Charte « bleu notaire & laiton » : bleu nuit pour la
structure, laiton pour les détails, Sora (titres, chiffres) et Public Sans
(texte), angles arrondis. Les polices sont servies par l'application
elle-même (app/fonts) : pas de dépendance à Google Fonts, hors ligne compris."""
from __future__ import annotations

from pathlib import Path

from nicegui import app, ui

# Couleurs de la charte (valeurs fixes, pour Quasar et les graphiques).
MARQUE_HEX = "#1b3358"  # bleu notaire
ENCRE_HEX = "#13243f"
LAITON_HEX = "#a8823b"
OK_HEX = "#2d6a4f"
VIGILANCE_HEX = "#b7791f"
KO_HEX = "#b23a32"

# Couleurs à utiliser dans les styles des éléments : variables CSS, dont la
# valeur s'éclaircit en mode sombre pour rester lisible.
PRIMARY = "var(--c-marque-texte)"
POSITIVE = "var(--c-ok)"
ACCENT = "var(--c-vigilance)"  # « vigilance » : orange-laiton des points d'attention
NEGATIVE = "var(--c-ko)"

DOSSIER_POLICES = Path(__file__).resolve().parent.parent / "app" / "fonts"
app.add_static_files("/polices", DOSSIER_POLICES)

# Logo Credaura : une maison dans un sceau d'or (l'« aura », le cachet
# d'approbation), sur un badge bleu notaire à coins arrondis. Même dessin que
# app/visuels_dossier.logo() (rapport Word, icône de l'application).
LOGO_SVG = f"""
<svg width="38" height="38" viewBox="0 0 64 64" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="Logo Credaura">
  <rect width="64" height="64" rx="15" fill="{MARQUE_HEX}"/>
  <circle cx="32" cy="32.5" r="23" fill="none" stroke="{LAITON_HEX}" stroke-width="2.4"/>
  <path d="M32 19 L44.5 29.5 V43.5 H19.5 V29.5 Z" fill="#FFFFFF"/>
  <rect x="28.8" y="35" width="6.4" height="8.5" rx="0.8" fill="{MARQUE_HEX}"/>
</svg>
""".strip()

CARD_CLASSES = "w-full rounded-2xl shadow-sm border border-[color:var(--c-filet)] p-4 sm:p-5 md:p-6"
SECTION_TITLE_CLASSES = "text-xl font-semibold mb-1 titre-sora"
SUBSECTION_TITLE_CLASSES = "text-sm font-semibold uppercase tracking-wide text-[color:var(--primary-color)] mt-2 mb-1"
HINT_CLASSES = "text-xs text-gray-500"
GRID_CLASSES = "w-full grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4"


def apply_theme() -> None:
    ui.colors(
        primary=MARQUE_HEX,
        secondary=ENCRE_HEX,
        accent=LAITON_HEX,
        positive=OK_HEX,
        negative=KO_HEX,
        warning=VIGILANCE_HEX,
        dark="#151c27",
        dark_page="#0e131b",
    )
    ui.add_head_html(
        """
        <style>
          @font-face { font-family: 'Sora'; font-weight: 400; src: url('/polices/Sora-Regular.ttf') format('truetype'); font-display: swap; }
          @font-face { font-family: 'Sora'; font-weight: 600; src: url('/polices/Sora-SemiBold.ttf') format('truetype'); font-display: swap; }
          @font-face { font-family: 'Sora'; font-weight: 700; src: url('/polices/Sora-Bold.ttf') format('truetype'); font-display: swap; }
          @font-face { font-family: 'Public Sans'; font-weight: 400; src: url('/polices/PublicSans-Regular.ttf') format('truetype'); font-display: swap; }
          @font-face { font-family: 'Public Sans'; font-weight: 600; src: url('/polices/PublicSans-SemiBold.ttf') format('truetype'); font-display: swap; }
          @font-face { font-family: 'Public Sans'; font-weight: 700; src: url('/polices/PublicSans-Bold.ttf') format('truetype'); font-display: swap; }
          @font-face { font-family: 'Public Sans'; font-style: italic; font-weight: 400; src: url('/polices/PublicSans-Italic.ttf') format('truetype'); font-display: swap; }

          :root {
            --c-marque: #1b3358; --c-marque-texte: #1b3358; --c-laiton: #a8823b;
            --c-ok: #2d6a4f; --c-vigilance: #b7791f; --c-ko: #b23a32;
            --c-fond: #f5f7fa; --c-filet: #dde3ea; --stat-bg: #eef2f7;
            --primary-color: #1b3358;
          }
          .body--dark {
            --c-marque-texte: #a9c1e8; --c-laiton: #c9a45e;
            --c-ok: #6fbf95; --c-vigilance: #e0a24a; --c-ko: #ec8078;
            --c-fond: #0e131b; --c-filet: #263245; --stat-bg: #1a2436;
            --primary-color: #a9c1e8;
          }
          html, body { background: var(--c-fond) !important; color-scheme: light; }
          body.body--dark { color-scheme: dark; }
          body, .q-field, .q-btn, .q-tab, .q-item { font-family: 'Public Sans', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif !important; }
          .titre-sora, .stat-card .valeur, .text-2xl, .text-3xl, .text-xl { font-family: 'Sora', 'Public Sans', -apple-system, sans-serif !important; letter-spacing: -0.01em; }
          .stat-card .valeur { color: var(--c-marque-texte); font-variant-numeric: tabular-nums; }
          .q-card { transition: box-shadow .15s ease; }
          .q-btn { border-radius: 10px !important; font-weight: 600 !important; text-transform: none !important; }
          .q-field--outlined .q-field__control { border-radius: 10px !important; }
          .stat-card { background: var(--stat-bg); border-radius: 14px; padding: 14px 16px; }
          /* Mode sombre : le bleu notaire est trop foncé sur fond nuit pour le texte. */
          .body--dark .text-primary { color: var(--c-marque-texte) !important; }
          .body--dark .q-tab--active .q-tab__indicator { background: var(--c-laiton) !important; }
          .body--dark .bg-primary { background: #2c4a78 !important; }
          /* Les panneaux d'onglets coupent le débordement, ce qui empêche la
             colonne de synthèse de rester fixe (position: sticky). */
          .q-tab-panels, .q-tab-panels .q-panel, .q-panel-parent { overflow: visible !important; }
          .q-tab-panels { background: transparent !important; }
          /* Les cartes des étapes s'alignent sur la carte « Type de projet » et la barre Suivant. */
          .q-tab-panel { padding-left: 0; padding-right: 0; }
          /* Texte secondaire en mode sombre (remplace la variante Tailwind dark:, voir basculer_theme). */
          .body--dark .text-gray-500 { color: #9ca3af !important; }
          .q-tabs--dense .q-tab { padding: 0 10px; }
          .q-table tbody tr:nth-child(even) { background: rgba(127, 127, 127, 0.06); }
          .q-table td.text-right, .q-table th.text-right { font-variant-numeric: tabular-nums; }
          .synthese-ligne { font-variant-numeric: tabular-nums; }
          /* Quasar force .hidden en !important : classes dédiées pour la synthèse. */
          .colonne-synthese { display: none; }
          .barre-synthese-mobile { background: #ffffff; }
          .body--dark .barre-synthese-mobile { background: #151c27; border-color: #263245; }
          @media (min-width: 1024px) {
            .colonne-synthese { display: block; }
            .barre-synthese-mobile, .espace-barre-mobile { display: none !important; }
          }
          /* Téléphone : les 6 onglets sur deux lignes, tous visibles (au lieu d'une barre qui
             défile et cache l'onglet en cours), et pas de double marge autour des cartes. */
          /* Frise des étapes du parcours (remplace la barre d'onglets) et assistant. */
          .frise-ligne { display: flex; align-items: flex-start; width: 100%; }
          .frise-etape { display: flex; flex-direction: column; align-items: center; gap: 5px; cursor: pointer; min-width: 40px; }
          .frise-rond { width: 32px; height: 32px; border-radius: 50%; display: flex; align-items: center; justify-content: center;
                        font-weight: 600; font-size: 14px; border: 2px solid var(--c-filet); color: #6b7280;
                        background: var(--c-fond); transition: all 0.2s ease; }
          .frise-etape:hover .frise-rond { border-color: var(--c-marque-texte); }
          .frise-courant .frise-rond { background: var(--c-marque); border-color: var(--c-marque); color: #fff;
                                      box-shadow: 0 0 0 4px color-mix(in srgb, var(--c-marque) 18%, transparent); }
          .frise-fait .frise-rond { background: var(--c-ok); border-color: var(--c-ok); color: #fff; }
          .frise-trait { flex: 1; height: 2px; background: var(--c-filet); margin-top: 16px; min-width: 8px; }
          .frise-trait-fait { background: var(--c-ok); }
          .frise-libelle { font-size: 12px; color: #6b7280; white-space: nowrap; }
          .frise-courant .frise-libelle { color: var(--c-marque-texte); font-weight: 600; }
          /* Fenêtre « il manque… » (accueil et simulateur), dans la charte. */
          .carte-manque { max-width: 320px; padding: 24px 22px !important; border-radius: 18px !important; border-top: 5px solid #A8823B; color: #13243F; }
          .body--dark .carte-manque { color: #E6ECF3; }
          .etape-compteur { font-size: 12px; text-transform: uppercase; letter-spacing: 0.06em; color: var(--c-laiton); font-weight: 600; white-space: nowrap; }
          .etape-titre { font-family: 'Sora', 'Public Sans', sans-serif; font-size: 1.15rem; font-weight: 600; }
          .nav-etapes { position: sticky; bottom: 0; z-index: 30; padding: 10px 0; background: var(--c-fond); }
          @media (max-width: 1023px) { .nav-etapes { bottom: 52px; } }
          /* Barre Précédent / Suivant toujours sur une ligne ; sur téléphone, « Précédent »
             se réduit à sa flèche pour laisser la place au bouton Suivant. */
          .nav-etapes .q-btn__content { flex-wrap: nowrap; white-space: nowrap; }
          @media (max-width: 639px) {
            .nav-etapes .bouton-precedent .q-btn__content > span.block { display: none; }
            .nav-etapes .bouton-precedent { min-width: 44px; }
          }
          @media (max-width: 639px) { .frise-libelle { display: none; } }
          /* Onglets : passent à la ligne quand la place manque (fenêtre étroite, app Mac) au lieu
             d'une barre qui défile et cache des onglets. */
          .onglets-parcours .q-tabs__content { flex-wrap: wrap; overflow: visible; transform: none !important; }
          .onglets-parcours .q-tabs__arrow { display: none; }
          @media (max-width: 639px) {
            .onglets-parcours .q-tab { flex: 1 1 33%; min-height: 44px; padding: 0 4px; }
            .onglets-parcours .q-tab__label { font-size: 13px; text-transform: none; letter-spacing: 0; white-space: normal; line-height: 1.2; text-align: center; }
            .onglets-parcours .q-tabs__arrow { display: none; }
            .q-tab-panel { padding-left: 0; padding-right: 0; }
            /* Cartes de chiffres par deux (les grandes, une par ligne) : moins de défilement. */
            .grid:has(> .stat-card) { grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 10px; }
            .grid:has(> .stat-card .text-3xl) { grid-template-columns: minmax(0, 1fr); }
            .stat-card { padding: 10px 12px; }
            .stat-card.carte-pleine-largeur { grid-column: 1 / -1; }
            /* Intitulés sur deux lignes au plus : les chiffres d'une même ligne restent alignés. */
            .stat-card:not(:has(.text-3xl)) .entete-stat { min-height: 2.5em; }
            .stat-card .valeur.text-xl { font-size: 1.1rem; line-height: 1.45rem; }
            /* Tableaux en mode cartes (une carte par ligne) : lisibles sans défilement horizontal. */
            .q-table__grid-content .q-table__grid-item { width: 100%; padding: 4px 0; }
            .q-table__grid-item-card { padding: 12px 14px; }
            .q-table__grid-item-row { display: flex; justify-content: space-between; align-items: baseline; gap: 12px; }
            .q-table__grid-item-row + .q-table__grid-item-row { margin-top: 4px; }
            .q-table__grid-item-title { font-size: 13px; opacity: 0.75; }
            .q-table__grid-item-value { font-weight: 600; text-align: right; font-variant-numeric: tabular-nums; }
            /* Première ligne de chaque carte (régime, scénario…) : en titre. */
            .q-table__grid-item-row:first-child { margin-bottom: 6px; }
            .q-table__grid-item-row:first-child .q-table__grid-item-value { font-size: 15px; }
          }
          /* Champ calculé automatiquement (frais de notaire) : fond bleu, mention « auto ». */
          .champ-calcule.q-field--outlined .q-field__control { background: var(--c-fond-calcule); }
          .champ-calcule.q-field--outlined .q-field__control:before { border-color: var(--c-bord-calcule); }
          .champ-calcule .q-field__label::after { content: " · auto"; color: var(--c-texte-calcule); font-weight: 600; }
          :root { --c-fond-calcule: #e8f0fa; --c-bord-calcule: #a9c3e3; --c-texte-calcule: #2f5d93; }
          .body--dark { --c-fond-calcule: rgba(58, 100, 158, 0.22); --c-bord-calcule: #3a649e; --c-texte-calcule: #9dbbe2; }
          /* Verdict : un repère de couleur par critère (rentabilité, prix, financement). */
          /* Bulles d'aide ⓘ (ouvertes au clic ou au toucher). */
          .aide-icone { padding: 4px; margin: -4px; flex-shrink: 0; }
          .aide-bulle { padding: 10px 12px; line-height: 1.4; }
          /* Lien vers l'exemple de dossier (en-tête, étape Dossier). */
          .lien-exemple { color: var(--c-marque-texte); text-decoration: none; }
          .lien-exemple:hover { text-decoration: underline; }
          /* Boutons d'achat d'un lot (étape Dossier, mode payant) : de vrais liens. */
          .bouton-achat { display: inline-flex; align-items: center; gap: 4px; padding: 9px 16px; border-radius: 10px;
                          background: var(--c-laiton); color: #fff !important; text-decoration: none; font-size: 0.95rem;
                          cursor: pointer; transition: opacity 0.15s; }
          .bouton-achat:hover { opacity: 0.9; }
          .bouton-achat-off { opacity: 0.45; cursor: not-allowed; }
          .pastille-critere { display: inline-block; flex-shrink: 0; width: 10px; height: 10px; border-radius: 50%; margin-top: 3px; }
          .pastille-legende { display: inline-block; width: 28px; height: 16px; border-radius: 5px; vertical-align: -3px; margin-right: 8px; flex-shrink: 0; }
          /* Jauge (taux d'endettement face au seuil). */
          .jauge { position: relative; height: 12px; border-radius: 6px; background: var(--c-filet); overflow: visible; }
          .jauge-remplissage { height: 100%; border-radius: 6px; transition: width 0.4s ease; }
          .jauge-seuil { position: absolute; top: -4px; bottom: -4px; width: 2px; background: var(--c-marque-texte); }
          /* Chiffre qui vient de changer : bref surlignage. */
          @keyframes maj-flash { 0% { background: color-mix(in srgb, var(--c-laiton) 35%, transparent); } 100% { background: transparent; } }
          .maj-flash { animation: maj-flash 1.2s ease-out; border-radius: 6px; }
          /* Import des photos du dossier : pas de liste de fichiers, les miniatures suffisent. */
          .uploader-photos .q-uploader__list, .uploader-photos .q-uploader__subtitle, .uploader-projet .q-uploader__list, .uploader-projet .q-uploader__subtitle { display: none; }
          /* iPhone : un champ en dessous de 16 px fait zoomer la page à la saisie, et la page reste
             ensuite décalée. */
          @media (max-width: 760px) { .q-field__native, .q-field__input, .q-select__dropdown-icon + input { font-size: 16px !important; } }
          /* Patrimoine du foyer : une ligne par poste (nature, détail, valeur, reste dû) sur ordinateur. */
          .grille-patrimoine { display: grid; grid-template-columns: 1fr; gap: 0.5rem; }
          @media (min-width: 640px) {
            .grille-patrimoine { grid-template-columns: 1.6fr 1.6fr 1.2fr 1.2fr; align-items: center; }
          }
        </style>
        """
    )


MASQUE_MILLIERS = "### ### ### ###"


class ChampMontant(ui.input):
    """Montant en euros, chiffres groupés par trois pendant la saisie
    (315 000) : le masque est appliqué dans le navigateur, le serveur reçoit
    les chiffres seuls (pas d'aller-retour qui ferait sauter le curseur)."""

    def __init__(self, label: str = "", *, suffixe: str | None = None, nullable: bool = False, **kwargs) -> None:
        super().__init__(label, **kwargs)
        self._nullable = nullable
        self.props(f'mask="{MASQUE_MILLIERS}" reverse-fill-mask unmasked-value inputmode=numeric')
        if suffixe:
            self.props(f'suffix="{suffixe}"')

    def lire(self, texte) -> float | None:
        chiffres = "".join(c for c in str(texte or "") if c.isdigit())
        if not chiffres:
            return None if self._nullable else 0.0
        return float(chiffres)

    def ecrire(self, valeur) -> str:
        if valeur is None or valeur == "":
            return ""
        return str(int(round(float(valeur))))

    def set_value(self, value) -> None:
        if isinstance(value, (int, float)):
            value = self.ecrire(value)
        super().set_value(value)

    def lier(self, state: dict, cle: str) -> "ChampMontant":
        return self.bind_value(state, cle, forward=self.lire, backward=self.ecrire)


def aide(texte: str) -> None:
    """Petite icône ⓘ : l'explication s'ouvre d'un clic ou d'un toucher (pas
    d'appui long sur téléphone), et se referme en touchant ailleurs."""
    with ui.icon("info_outline", size="18px").classes("aide-icone text-gray-400 cursor-pointer").props(
        'aria-label="Aide" role="button" tabindex="0"'
    ).on("click.stop", lambda: None):
        with ui.menu().props("max-width=300px anchor='bottom middle' self='top middle'"):
            ui.label(texte).classes("aide-bulle text-sm")


def fenetre_a_completer():
    """Petite fenêtre « il manque… » au centre de l'écran (accueil et
    simulateur). Renvoie la fonction qui l'ouvre avec le texte voulu ;
    « Compléter » la referme et place le curseur dans le champ à remplir."""
    cible = {"champ": None}

    def completer() -> None:
        fenetre.close()
        if cible["champ"] is not None:
            cible["champ"].run_method("focus")

    with ui.dialog() as fenetre, ui.card().classes("carte-manque items-center text-center gap-3"):
        ui.icon("edit_note", size="40px").classes("text-[color:#A8823B]")
        texte = ui.label("").classes("text-base")
        ui.button("Compléter", on_click=completer).props("unelevated no-caps color=primary").classes("w-full")

    def signaler(message: str, champ: ui.element | None = None) -> None:
        texte.set_text(message)
        cible["champ"] = champ
        fenetre.open()

    return signaler


def signaler_champ(champ: ui.element) -> None:
    """Bordure rouge et « À compléter » sous le champ ; le champ redevient
    normal dès qu'on le remplit (voir effacer_signalement_a_la_saisie)."""
    champ.props('error error-message="À compléter" no-error-icon')


def effacer_signalement_a_la_saisie(champ: ui.element) -> None:
    champ.on("update:model-value", lambda _e: champ.props(remove="error error-message no-error-icon"))


def stat_card(
    label: str, initial: str = "–", aide_texte: str | None = None, grand: bool = False, classes: str = ""
) -> ui.label:
    """Petite carte 'métrique' (fond teinté, valeur en gros). Renvoie le label
    de valeur pour pouvoir le mettre à jour ensuite (`.set_text(...)`)."""
    with ui.column().classes(f"stat-card gap-0 {classes}".strip()):
        # Intitulé à gauche, ⓘ calé en haut à droite : les cartes d'une même
        # ligne gardent leurs chiffres alignés, même si un intitulé passe sur
        # deux lignes.
        with ui.row().classes("entete-stat w-full items-start justify-between gap-1 no-wrap"):
            libelle = ui.label(label).classes("text-xs text-gray-500 leading-snug")
            if aide_texte:
                aide(aide_texte)
        value = ui.label(initial).classes("valeur " + ("text-3xl font-bold" if grand else "text-xl font-bold"))
        detail = ui.label("").classes("detail-stat text-xs text-gray-500 leading-snug")
        detail.visible = False
    value.libelle = libelle  # pour changer l'intitulé selon le contexte
    value.detail = detail  # précision sous le chiffre (« pour un cash-flow ≥ 0 € »)
    return value


def colorer(label: ui.label, valeur: float | None, inverse: bool = False) -> None:
    """Rouge si la valeur est défavorable (négative, ou positive si `inverse`),
    vert sinon ; sans appel, la valeur reste dans la couleur de la marque."""
    defavorable = valeur is not None and (valeur > 0 if inverse else valeur < 0)
    label.style(f"color: {NEGATIVE if defavorable else POSITIVE}")


def section_card():
    """Contexte 'carte' standard pour une section de la page."""
    return ui.card().classes(CARD_CLASSES)


# Icône de chaque rubrique du formulaire (Material Icons, fournis avec Quasar).
ICONES_RUBRIQUES = {
    "Le bien": "home",
    "Financement": "account_balance",
    "Achat-revente": "swap_horiz",
    "Revenus et charges": "payments",
    "Location courte durée": "luggage",
    "Régime locatif & fiscalité": "receipt_long",
    "Photos du bien": "photo_camera",
    "Contenu du dossier": "checklist",
    "Aperçu du dossier": "visibility",
}


def subsection_title(text: str) -> None:
    icone = ICONES_RUBRIQUES.get(text)
    if not icone:
        ui.label(text).classes(SUBSECTION_TITLE_CLASSES)
        return
    with ui.row().classes("items-center gap-2 no-wrap mt-2 mb-1"):
        ui.icon(icone).classes("text-lg text-[color:var(--c-laiton)]")
        ui.label(text).classes(SUBSECTION_TITLE_CLASSES.replace("mt-2 mb-1", ""))
