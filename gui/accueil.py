"""Page d'accueil du site (maquette validée le 5 octobre 2026) : la promesse,
le formulaire « Vérifie ton projet », le verdict et le dossier, comment ça
marche, les tarifs et la FAQ. Le formulaire ouvre le simulateur complet déjà
rempli, sur la même page.

Bêta gratuite : tant que le paiement n'existe pas, le dossier est offert et
les tarifs sont annoncés « à l'ouverture ». Pas de témoignages tant qu'on n'a
pas de vrais avis de testeurs (à afficher marqués « avis vérifié »).
"""
from __future__ import annotations

from typing import Awaitable, Callable

from nicegui import ui

from . import pages_legales

BLEU, ENCRE, LAITON, LAITON_CLAIR, LAITON_FONCE = "#1B3358", "#13243F", "#A8823B", "#E9D8B0", "#86662A"

CSS = """
.accueil { width: 100%; background: #F5F7FA; color: #13243F; font-family: 'Public Sans', sans-serif; font-size: 16px; line-height: 1.5; }
.accueil h1, .accueil h2, .accueil p { margin: 0; letter-spacing: normal; }
.accueil a { color: #1B3358; }
.accueil .bloc { max-width: 1200px; margin: 0 auto; box-sizing: border-box; padding-left: clamp(16px, 4vw, 48px); padding-right: clamp(16px, 4vw, 48px); }
.accueil .surtitre { font-size: 13px; font-weight: 600; letter-spacing: 0.14em; color: #86662A; }
.accueil .titre-section { font-family: Sora, sans-serif; font-weight: 600; font-size: clamp(26px, 3vw, 36px); line-height: 1.2; }
.accueil .gris { color: #4A5563; }
.nav-mobile { display: none; position: relative; }
.nav-mobile summary { list-style: none; cursor: pointer; width: 44px; height: 44px; border-radius: 10px; border: 1.5px solid rgba(233, 216, 176, 0.5); display: flex; align-items: center; justify-content: center; }
.nav-mobile summary::-webkit-details-marker { display: none; }
.nav-mobile .menu-deroulant { position: absolute; right: 0; top: 52px; z-index: 20; background: #FFFFFF; border-radius: 12px; padding: 8px; min-width: 230px; display: flex; flex-direction: column; box-shadow: 0 16px 40px rgba(8, 20, 40, 0.3); }
.nav-mobile .menu-deroulant a { color: #13243F; text-decoration: none; padding: 12px 14px; border-radius: 8px; }
.nav-mobile .menu-deroulant a:hover { background: #F0F3F7; }
@media (max-width: 760px) { .nav-liens { display: none !important; } .nav-mobile { display: block; } }
.carte-verif { background: #FFFFFF; color: #13243F; }
.body--dark .carte-verif { background: #151C27; color: #E6ECF3; }
.body--dark .carte-verif .gris { color: #AEB9C7; }
.body--dark .carte-verif a { color: #9DBBE2; }
.faq details { border-bottom: 1px solid #DCE3EC; padding: 18px 0; }
.faq summary { font-weight: 600; font-size: 17px; cursor: pointer; }
.faq details p { margin-top: 10px; color: #4A5563; }
"""

COCHE = (
    '<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="#C9A45E" stroke-width="2.4" '
    'stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" style="flex-shrink:0"><path d="M5 12.5l4.5 4.5L19 7.5"/></svg>'
)
LOGO = (
    '<svg width="44" height="44" viewBox="0 0 64 64" aria-hidden="true"><rect width="64" height="64" rx="15" fill="#22406B"/>'
    '<circle cx="32" cy="32.5" r="23" fill="none" stroke="#C9A45E" stroke-width="2.4"/>'
    '<path d="M32 19 L44.5 29.5 V43.5 H19.5 V29.5 Z" fill="#FFFFFF"/><rect x="28.8" y="35" width="6.4" height="8.5" rx="0.8" fill="#22406B"/></svg>'
)
# Dans l'ordre des sections de la page.
LIENS_MENU = (
    ("#resultat", "Le dossier"),
    ("#comment", "Comment ça marche"),
    ("#tarifs", "Tarifs"),
    ("#faq", "FAQ"),
)


def _entete() -> str:
    liens = "".join(f'<a href="{h}" style="color:#FFFFFF;text-decoration:none">{t}</a>' for h, t in LIENS_MENU)
    # Le menu se referme quand on choisit une rubrique.
    liens_menu = "".join(f'<a href="{h}" onclick="this.closest(\'details\').open=false">{t}</a>' for h, t in LIENS_MENU)
    exemple = '<a href="/exemple-dossier" target="_blank" rel="noopener"'
    return f"""
<header style="display:flex;flex-wrap:wrap;align-items:center;justify-content:space-between;gap:12px 32px">
  <a href="/" style="display:flex;align-items:center;gap:12px;text-decoration:none;color:#FFFFFF">{LOGO}
    <span style="display:flex;flex-direction:column;gap:3px">
      <span style="font-family:Sora,sans-serif;font-weight:700;font-size:22px;line-height:1">Cred<span style="color:{LAITON_CLAIR}">aura</span></span>
      <span style="font-size:10px;font-weight:600;letter-spacing:0.16em;color:{LAITON_CLAIR}">CONVAINCRE MON BANQUIER</span>
    </span>
  </a>
  <nav class="nav-liens" aria-label="Navigation principale" style="display:flex;flex-wrap:wrap;align-items:center;gap:8px 24px;font-size:15px">
    {liens}
    {exemple} style="color:{ENCRE};background:{LAITON_CLAIR};text-decoration:none;font-weight:600;padding:10px 16px;border-radius:10px">Voir un exemple de dossier</a>
  </nav>
  <details class="nav-mobile">
    <summary aria-label="Ouvrir le menu"><svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="#FFFFFF" stroke-width="2.2" stroke-linecap="round" aria-hidden="true"><path d="M4 7h16M4 12h16M4 17h16"/></svg></summary>
    <div class="menu-deroulant">{liens_menu}{exemple}>Voir un exemple de dossier</a></div>
  </details>
</header>"""


ACCROCHE = f"""
<div style="display:flex;flex-direction:column;gap:20px">
  <span style="font-size:13px;font-weight:600;letter-spacing:0.14em;color:{LAITON_CLAIR}">VÉRIFICATION GRATUITE · SANS COMPTE</span>
  <h1 style="font-family:Sora,sans-serif;font-weight:700;font-size:clamp(32px,4.6vw,54px);line-height:1.1;letter-spacing:-0.01em">Ton projet immo tient-il la route&#8239;? Vérifie-le avant ton banquier.</h1>
  <p style="font-size:clamp(17px,1.6vw,20px);color:#D9E1EC;max-width:560px">Je vérifie la rentabilité de ton projet immo et je t'aide à monter ton dossier pour convaincre ta banque.</p>
  <ul style="margin:4px 0 0;padding:0;list-style:none;display:flex;flex-direction:column;gap:10px">
    <li style="display:flex;gap:10px;align-items:flex-start">{COCHE}<span>Ton prix comparé aux ventes réelles du quartier</span></li>
    <li style="display:flex;gap:10px;align-items:flex-start">{COCHE}<span>La rentabilité et le cash-flow réels, après charges et impôts</span></li>
    <li style="display:flex;gap:10px;align-items:flex-start">{COCHE}<span>Ton taux d'endettement, calculé comme le fait la banque</span></li>
  </ul>
</div>"""


def _critere(couleur: str, nom: str, texte: str) -> str:
    return (
        '<li style="display:flex;gap:12px;align-items:flex-start">'
        f'<span style="width:12px;height:12px;border-radius:50%;background:{couleur};margin-top:6px;flex-shrink:0"></span>'
        f"<span><strong>{nom}</strong> : {texte}</span></li>"
    )


def _page_dossier(contenu: str) -> str:
    return (
        '<div style="flex:1 1 0;aspect-ratio:3/4;background:#FFFFFF;border-radius:6px;padding:10px;box-sizing:border-box;'
        f'display:flex;flex-direction:column;gap:6px;filter:blur(1.5px)">{contenu}</div>'
    )


_LIGNE = '<div style="height:5px;background:#C7D0DB;border-radius:2px"></div>'
_TITRE = '<div style="height:10px;width:60%;background:#1B3358;border-radius:2px"></div>'

RESULTAT = f"""
<section id="resultat" class="bloc" style="padding-top:clamp(48px,7vw,88px);padding-bottom:clamp(48px,7vw,88px);display:flex;flex-direction:column;gap:32px">
  <div style="display:flex;flex-direction:column;gap:8px;max-width:720px">
    <span class="surtitre">CE QUE TU OBTIENS</span>
    <h2 class="titre-section">Un verdict clair tout de suite, puis le dossier pour la banque</h2>
  </div>
  <div style="display:flex;flex-wrap:wrap;gap:24px">
    <div style="flex:1 1 420px;min-width:0;background:#FFFFFF;border:1px solid #DCE3EC;border-radius:20px;padding:clamp(20px,2.6vw,32px);box-sizing:border-box;display:flex;flex-direction:column;gap:18px">
      <span class="gris" style="font-size:13px;font-weight:600">GRATUIT · EXEMPLE : T3 DE 65 m² À SAINT-ÉTIENNE</span>
      <div style="display:flex;align-items:center;gap:12px">
        <span style="width:44px;height:44px;border-radius:50%;background:#E3F1EA;display:flex;align-items:center;justify-content:center;flex-shrink:0"><svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="#2D6A4F" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M5 12.5l4.5 4.5L19 7.5"/></svg></span>
        <span style="font-family:Sora,sans-serif;font-weight:700;font-size:26px;color:#2D6A4F">Projet solide</span>
      </div>
      <ul style="margin:0;padding:0;list-style:none;display:flex;flex-direction:column;gap:14px">
        {_critere("#2D6A4F", "Prix", "4 % sous la médiane des ventes du quartier")}
        {_critere("#2D6A4F", "Rentabilité", "cash-flow positif, +46 € par mois après crédit, charges et impôts")}
        {_critere("#8A94A0", "Financement", "ajoute tes revenus pour connaître ton taux d'endettement")}
      </ul>
    </div>
    <div id="dossier" style="flex:1 1 420px;min-width:0;background:{ENCRE};color:#FFFFFF;border-radius:20px;padding:clamp(20px,2.6vw,32px);box-sizing:border-box;display:flex;flex-direction:column;gap:18px">
      <span style="font-size:13px;font-weight:600;letter-spacing:0.08em;color:{LAITON_CLAIR}">LE DOSSIER DE FINANCEMENT</span>
      <span style="font-family:Sora,sans-serif;font-weight:600;font-size:24px;line-height:1.25">Un dossier Word complet, à ton nom, prêt à remettre à ton conseiller</span>
      <div style="display:flex;gap:12px" aria-hidden="true">
        {_page_dossier(_TITRE + '<div style="height:40%;background:#DCE7F3;border-radius:3px"></div>' + _LIGNE + _LIGNE)}
        {_page_dossier(_TITRE + '<div style="display:flex;gap:4px;align-items:flex-end;height:40%"><div style="flex:1;height:40%;background:#A8823B"></div><div style="flex:1;height:70%;background:#A8823B"></div><div style="flex:1;height:55%;background:#A8823B"></div><div style="flex:1;height:90%;background:#A8823B"></div></div>' + _LIGNE + _LIGNE)}
        {_page_dossier(_TITRE + _LIGNE + _LIGNE + _LIGNE + '<div style="height:30%;background:#E3F1EA;border-radius:3px"></div>')}
      </div>
      <ul style="margin:0;padding:0 0 0 18px;display:flex;flex-direction:column;gap:6px;font-size:15px;color:#D9E1EC">
        <li>Étude de marché du quartier, avec la carte et les ventes comparables</li>
        <li>Plan de financement, recettes et charges, cash-flow mois par mois</li>
        <li>Profil de l'emprunteur et taux d'endettement</li>
        <li>La liste des pièces à fournir à la banque</li>
      </ul>
      <div style="display:flex;flex-wrap:wrap;gap:12px;align-items:center">
        <a href="#verifier" style="background:{LAITON};color:#FFFFFF;text-decoration:none;font-weight:700;padding:13px 18px;border-radius:10px">Obtenir mon dossier · offert pendant la bêta</a>
        <a href="/exemple-dossier" target="_blank" rel="noopener" style="color:{LAITON_CLAIR};font-weight:600">Voir un exemple complet</a>
      </div>
    </div>
  </div>
</section>"""


def _etape(numero: str, titre: str, texte: str) -> str:
    return f"""
    <div style="flex:1 1 280px;min-width:0;display:flex;flex-direction:column;gap:10px;padding:24px;border-radius:16px;background:#F5F7FA">
      <span style="font-family:Sora,sans-serif;font-weight:700;font-size:34px;color:{LAITON};line-height:1">{numero}</span>
      <span style="font-family:Sora,sans-serif;font-weight:600;font-size:19px">{titre}</span>
      <span class="gris">{texte}</span>
    </div>"""


COMMENT = f"""
<section id="comment" style="background:#FFFFFF;border-top:1px solid #E6ECF3;border-bottom:1px solid #E6ECF3">
  <div class="bloc" style="padding-top:clamp(48px,7vw,88px);padding-bottom:clamp(48px,7vw,88px);display:flex;flex-direction:column;gap:32px">
    <div style="display:flex;flex-direction:column;gap:8px">
      <span class="surtitre">COMMENT ÇA MARCHE</span>
      <h2 class="titre-section">De l'annonce au rendez-vous bancaire, en trois étapes</h2>
    </div>
    <div style="display:flex;flex-wrap:wrap;gap:20px">
      {_etape("1", "Tu entres l'adresse et le prix", "Surface, prix affiché, et ton loyer si tu le connais. Pas de compte, pas d'e-mail.")}
      {_etape("2", "Je vérifie le projet", "Prix comparé aux ventes réelles autour du bien, loyer du marché, rentabilité et cash-flow : tu sais tout de suite si ça tient.")}
      {_etape("3", "Tu repars avec ton dossier", "Tu complètes ton financement et ton profil, puis tu télécharges le dossier à remettre à ta banque.")}
    </div>
  </div>
</section>"""


def _tarif(nombre: str, prix: str, usage: str, mis_en_avant: bool = False) -> str:
    bordure = f"2px solid {LAITON}" if mis_en_avant else "1px solid #DCE3EC"
    return f"""
      <div style="flex:1 1 220px;min-width:0;background:#FFFFFF;border:{bordure};border-radius:16px;padding:24px;display:flex;flex-direction:column;gap:6px">
        <span style="font-weight:600">{nombre}</span>
        <span style="font-family:Sora,sans-serif;font-weight:700;font-size:32px">{prix}</span>
        <span class="gris" style="font-size:14px">{usage}</span>
      </div>"""


def _engagement(icone: str, titre: str, texte: str) -> str:
    return f"""
      <div style="flex:1 1 260px;min-width:0;display:flex;gap:12px;align-items:flex-start">
        <svg width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="{BLEU}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" style="flex-shrink:0">{icone}</svg>
        <span><strong>{titre}</strong> {texte}</span>
      </div>"""


TARIFS = f"""
<section id="tarifs" class="bloc" style="padding-top:clamp(48px,7vw,88px);padding-bottom:clamp(48px,7vw,88px);display:flex;flex-direction:column;gap:32px">
  <div style="display:flex;flex-direction:column;gap:8px">
    <span class="surtitre">TARIFS</span>
    <h2 class="titre-section">La vérification est gratuite. Pendant la bêta, le dossier aussi.</h2>
    <p class="gris">Tarifs à l'ouverture de la vente :</p>
  </div>
  <div style="display:flex;flex-wrap:wrap;gap:16px">
    {_tarif("1 dossier", "19,90 €", "Pour un projet précis")}
    {_tarif("2 dossiers", "34,90 €", "Pour comparer deux biens", True)}
    {_tarif("3 dossiers", "44,90 €", "Pour plusieurs pistes ou plusieurs banques")}
  </div>
  <div style="display:flex;flex-wrap:wrap;gap:16px 32px;padding-top:8px">
    {_engagement('<path d="M4 20V10M10 20V4M16 20v-7M22 20H2"/>', "Données officielles.", "Ventes DVF de l'État, carte des loyers du ministère, Base Adresse Nationale.")}
    {_engagement('<rect x="4" y="11" width="16" height="10" rx="2"/><path d="M8 11V7a4 4 0 0 1 8 0v4"/>', "Rien n'est conservé.", "Pas de compte, pas d'e-mail : tes chiffres disparaissent quand tu fermes la page.")}
    {_engagement('<circle cx="12" cy="12" r="9"/><path d="M8 12h8"/>', "Indépendant des banques.", "Ni courtier ni intermédiaire : aucune commission, aucun client revendu.")}
  </div>
</section>"""


QUESTIONS = (
    (
        "C'est vraiment gratuit ?",
        "Oui, la vérification l'est : le verdict, ton prix comparé au quartier, la rentabilité et le cash-flow. "
        "Le dossier complet pour la banque sera payant à l'ouverture de la vente, à partir de 19,90 € ; pendant la bêta, il est offert.",
    ),
    (
        "Credaura est-il un courtier ?",
        "Non. Je ne propose aucun crédit, je ne te mets en relation avec aucune banque et je ne touche aucune commission. "
        "Tu présentes ton dossier à la banque de ton choix, et elle reste seule à décider.",
    ),
    (
        "Que deviennent mes données ?",
        "Rien n'est enregistré : pas de compte, pas d'adresse e-mail. Tes chiffres servent au calcul et au dossier, "
        'puis disparaissent quand tu fermes la page. Le détail est dans la <a href="/confidentialite">politique de confidentialité</a>.',
    ),
    (
        "D'où viennent les chiffres du marché ?",
        "Des sources publiques officielles : les ventes réelles DVF publiées par l'État, la carte des loyers du ministère "
        "du Logement et la Base Adresse Nationale. Elles sont mises à jour à chaque nouvelle publication.",
    ),
    (
        "Le dossier me garantit-il mon prêt ?",
        "Non, personne ne peut te le garantir. Le dossier présente ton projet de façon claire et complète, avec les chiffres "
        "que ta banque regarde : tu arrives préparé, et tu sais répondre à ses questions.",
    ),
    (
        "Sous quelle forme est le dossier ?",
        "Un document Word à ton nom, que tu peux relire et modifier avant de l'envoyer, ou enregistrer en PDF. "
        'Tu peux en feuilleter un <a href="/exemple-dossier" target="_blank" rel="noopener">exemple complet</a>.',
    ),
    (
        "Ça marche pour la location courte durée ou une SCI ?",
        "Oui : location nue ou meublée, location courte durée type Airbnb, achat-revente, en direct ou en SCI à l'IR ou à l'IS. "
        "Ces options sont dans le simulateur complet.",
    ),
)


def _faq() -> str:
    questions = "".join(
        f"<details{' open' if i == 0 else ''}><summary>{q}</summary><p>{r}</p></details>"
        for i, (q, r) in enumerate(QUESTIONS)
    )
    contact = pages_legales.CONTACT_EMAIL
    return f"""
<section id="faq" style="background:#FFFFFF;border-top:1px solid #E6ECF3">
  <div class="bloc" style="padding-top:clamp(48px,7vw,88px);padding-bottom:clamp(48px,7vw,88px)">
  <div class="faq" style="display:flex;flex-direction:column;gap:24px;max-width:820px">
    <div style="display:flex;flex-direction:column;gap:8px">
      <span class="surtitre">QUESTIONS FRÉQUENTES</span>
      <h2 class="titre-section">Tes questions, mes réponses</h2>
    </div>
    <div style="display:flex;flex-direction:column;border-top:1px solid #DCE3EC">{questions}</div>
    <p class="gris">Une autre question&#8239;? <a href="mailto:{contact}" style="font-weight:600">Écris-moi</a>.</p>
  </div>
  </div>
</section>"""


def _pied() -> str:
    contact = pages_legales.CONTACT_EMAIL
    liens = (
        (f"mailto:{contact}", "Nous contacter"),
        ("/mentions-legales", "Mentions légales"),
        ("/confidentialite", "Confidentialité"),
        ("https://www.instagram.com/credaura.fr/", "Instagram"),
        ("https://www.tiktok.com/@credaura.fr", "TikTok"),
        ("https://www.facebook.com/profile.php?id=61595308522377", "Facebook"),
        ("https://www.youtube.com/@credaura.fr1", "YouTube"),
    )
    html_liens = "".join(f'<a href="{h}" style="color:#FFFFFF">{t}</a>' for h, t in liens)
    return f"""
<footer style="background:{ENCRE};color:#C9D3E0">
  <div class="bloc" style="padding-top:36px;padding-bottom:36px;display:flex;flex-direction:column;gap:20px;font-size:14px">
    <div style="display:flex;flex-wrap:wrap;justify-content:space-between;gap:16px 32px;align-items:center">
      <span style="font-family:Sora,sans-serif;font-weight:700;font-size:18px;color:#FFFFFF">Cred<span style="color:{LAITON_CLAIR}">aura</span></span>
      <nav aria-label="Liens du pied de page" style="display:flex;flex-wrap:wrap;gap:8px 22px">{html_liens}</nav>
    </div>
    <p style="font-size:12px;line-height:1.6;color:#AEB9C7">Credaura produit des calculs à partir des données saisies. Ce n'est ni un conseil en investissement, en financement ou en fiscalité, ni une offre de prêt. Credaura n'est ni un établissement de crédit, ni un intermédiaire en opérations de banque et en services de paiement (IOBSP) : la banque reste seule décisionnaire.</p>
  </div>
</footer>"""


def construire_accueil(
    on_verifier: Callable[[dict], Awaitable[None]], on_simulateur: Callable[[], None]
) -> ui.element:
    """Construit la page d'accueil et renvoie son conteneur (masqué une fois
    le simulateur ouvert)."""
    ui.add_css(CSS)
    racine = ui.element("div").classes("accueil")
    with racine:
        ui.html(
            f'<div style="background:{LAITON_CLAIR};color:{ENCRE};text-align:center;font-size:14px;font-weight:600;padding:9px 16px">'
            "Bêta gratuite : pendant le lancement, le dossier de financement est offert.</div>"
        ).classes("w-full")
        with ui.element("div").style(f"background:{BLEU};color:#FFFFFF").classes("w-full"):
            with ui.element("div").classes("bloc").style(
                "padding-top:20px;padding-bottom:clamp(40px,7vw,88px);display:flex;flex-direction:column;gap:clamp(28px,5vw,64px)"
            ):
                ui.html(_entete()).classes("w-full")
                with ui.element("div").style("display:flex;flex-wrap:wrap;gap:40px 56px;align-items:center"):
                    ui.html(ACCROCHE).style("flex:1 1 440px;min-width:0")
                    _formulaire(on_verifier, on_simulateur)
        ui.html(RESULTAT).classes("w-full")
        ui.html(COMMENT).classes("w-full")
        ui.html(TARIFS).classes("w-full")
        ui.html(_faq()).classes("w-full")
        ui.html(_pied()).classes("w-full")
    return racine


def _formulaire(on_verifier: Callable[[dict], Awaitable[None]], on_simulateur: Callable[[], None]) -> None:
    with ui.element("div").props('id="verifier"').classes("carte-verif").style(
        "flex:1 1 360px;min-width:0;max-width:480px;border-radius:20px;padding:clamp(20px,2.6vw,32px);"
        "box-sizing:border-box;display:flex;flex-direction:column;gap:14px;box-shadow:0 24px 60px rgba(8,20,40,0.35)"
    ):
        ui.html(
            '<div style="display:flex;flex-direction:column;gap:4px">'
            '<h2 style="font-family:Sora,sans-serif;font-size:22px;font-weight:600;line-height:1.3">Vérifie ton projet</h2>'
            '<span class="gris" style="font-size:14px">4 informations suffisent. Le reste, je l\'estime pour toi.</span></div>'
        )
        adresse = ui.input("Adresse du bien", placeholder="Ex. 12 rue Michelet, Saint-Étienne").props("outlined").classes("w-full")
        type_bien = ui.toggle({"appartement": "Appartement", "maison": "Maison"}, value="appartement").props(
            "spread no-caps unelevated toggle-color=primary"
        ).classes("w-full")
        with ui.element("div").classes("w-full").style("display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px"):
            surface = ui.number("Surface (m²)", min=1).props("outlined").classes("w-full")
            prix = ui.number("Prix affiché (€)", min=1).props("outlined").classes("w-full")
        loyer = ui.number("Loyer prévu (€/mois, facultatif)", min=0).props("outlined").classes("w-full")
        ui.label("Sans loyer, j'utilise le loyer du marché.").classes("gris text-xs -mt-2")

        async def verifier() -> None:
            manque = [
                nom
                for nom, champ in (("l'adresse", adresse), ("la surface", surface), ("le prix", prix))
                if not champ.value
            ]
            if manque:
                ui.notify("Il manque " + ", ".join(manque) + ".", type="warning")
                return
            await on_verifier(
                {
                    "adresse": adresse.value.strip(),
                    "type_bien": type_bien.value,
                    "surface": float(surface.value),
                    "prix": float(prix.value),
                    "loyer": float(loyer.value) if loyer.value else None,
                }
            )

        ui.button("Vérifier mon projet gratuitement", on_click=verifier).props(
            "unelevated no-caps size=lg color=accent text-color=white"
        ).classes("w-full font-bold")
        ui.label("Aucun compte, aucune adresse e-mail, rien n'est conservé.").classes("gris text-xs text-center w-full")
        with ui.row().classes("w-full justify-center gap-x-4 gap-y-1 text-sm"):
            ui.html('<a href="/exemple-dossier" target="_blank" rel="noopener" style="font-weight:600">Voir un exemple de dossier</a>')
            ui.button("Ouvrir le simulateur complet", on_click=on_simulateur).props("flat dense no-caps").classes(
                "text-sm -my-1"
            )
