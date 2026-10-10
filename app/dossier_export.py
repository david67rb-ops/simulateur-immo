"""Génération du dossier de financement au format Word (.docx)."""
from __future__ import annotations

import io
import re
import threading
from datetime import datetime

from docx import Document
from docx.shared import Cm, Mm, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_TAB_ALIGNMENT, WD_TAB_LEADER
from docx.enum.table import WD_ALIGN_VERTICAL, WD_TABLE_ALIGNMENT
from docx.enum.section import WD_ORIENT, WD_SECTION
from docx.oxml import OxmlElement, parse_xml
from docx.oxml.ns import qn
from docx.table import _Cell

from . import charts_export as charts
from . import analyse
from . import endettement as endet_mod
from . import photos_dossier, saisonnalite
from . import visuels_dossier as visuels
from .chapitres_dossier import CHAPITRES_OBLIGATOIRES, LIGNES_PATRIMOINE, MENTION_LEGALE, PARTIE_DU_CHAPITRE, PARTIES
from .polices_word import integrer_polices
from .schemas import ExportDossierInput, TypeProjet
from .simulation import simuler
from .utils import clean_result, libelle_regime, libelle_rentabilite_ar

# Charte « bleu notaire & laiton » ; polices intégrées au document (polices_word).
POLICE = "Public Sans"
POLICE_GRAS = "Public Sans SemiBold"
POLICE_TITRE_GRAS = "Sora SemiBold"  # titres et grands chiffres
PRIMARY_COLOR = RGBColor(0x1B, 0x33, 0x58)  # bleu notaire
GRIS_COLOR = RGBColor(0x96, 0x9E, 0xA8)
GRIS_LIBELLE = RGBColor(0x5B, 0x66, 0x72)
TEXTE_FONCE = RGBColor(0x1F, 0x28, 0x33)
# Fond des pages, le même que celui des graphiques et des cartes (charts_export.FOND).
FOND_PAGE_HEX = "F5F7FA"
ZEBRA_HEX = "ECF0F5"
BORDURE_HEX = "E1E6EC"
BLANC = RGBColor(0xFF, 0xFF, 0xFF)
ROUGE = RGBColor(0xB2, 0x3A, 0x32)
VERT = RGBColor(0x2D, 0x6A, 0x4F)
LAITON_CLAIR = RGBColor(0xE9, 0xD8, 0xB0)
LAITON = RGBColor(0xA8, 0x82, 0x3B)
MARQUE_HEX = "1B3358"
LAITON_HEX = "A8823B"
VERT_HEX = "2D6A4F"
ROUGE_HEX = "B23A32"
FOND_TUILE_HEX = "E6ECF3"
# (couleur du filet et du titre, fond) selon le niveau du verdict
COULEURS_VERDICT = {
    "vert": ("2D6A4F", "E9F2ED"),
    "orange": ("B7791F", "FBF3E6"),
    "rouge": ("B23A32", "F8E9E7"),
    "neutre": ("1B3358", "E6ECF3"),
}
# Icône de chaque chapitre (Material Icons, comme les rubriques du simulateur).
ICONES_CHAPITRES = {
    "carte": "place",
    "photos": "photo_camera",
    "marche": "price_check",
    "presentation": "home",
    "charges": "receipt_long",
    "loyer_mensuel": "account_balance_wallet",
    "saisonnalite": "calendar_month",
    "patrimoine": "show_chart",
    "achat_revente": "swap_horiz",
    "financement": "account_balance",
    "profil": "person",
    "endettement": "speed",
    "avertissements": "warning",
    "synthese": "dashboard",
    "annexes": "fact_check",
    "mentions": "info",
}

NS_W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
NS_W14 = "http://schemas.microsoft.com/office/word/2010/wordml"

# Page A4 paysage : plus de largeur pour les mises en page tableau + graphique.
LARGEUR_PAGE_CM = 29.7
HAUTEUR_PAGE_CM = 21.0
MARGE_CM = 1.8
LARGEUR_CONTENU_CM = LARGEUR_PAGE_CM - 2 * MARGE_CM

# Budget vertical d'un chapitre (une page) : hauteur utile moins l'en-tête de
# chapitre et la rangée de tuiles, avec une marge de sécurité (le rendu exact
# dépend de Word). Le bloc tableau + graphique doit tenir dans ce reste.
HAUTEUR_UTILE_CM = HAUTEUR_PAGE_CM - 2 * MARGE_CM
HAUTEUR_ENTETE_CHAPITRE_CM = 2.3  # numéro, titre et description
HAUTEUR_A_RETENIR_CM = 1.6  # encadré « À retenir » en bas de page (et son espace au-dessus)
HAUTEUR_TUILES_CM = 2.1
HAUTEUR_NOTE_CM = 1.0
HAUTEUR_VERDICT_CM = 2.6
HAUTEUR_PHRASE_CM = 1.5  # le projet en une phrase (deux lignes)
MARGE_SECURITE_CM = 1.0
HAUTEUR_BLOC_CM = (
    HAUTEUR_UTILE_CM - HAUTEUR_ENTETE_CHAPITRE_CM - HAUTEUR_A_RETENIR_CM - HAUTEUR_TUILES_CM - MARGE_SECURITE_CM
)
# Hauteur d'une ligne de tableau clé/valeur selon sa densité (cm).
HAUTEUR_LIGNE_CM = {"normal": 0.84, "compact": 0.64, "serre": 0.52}

LABELS_TYPE_PROJET = {
    "location_longue_duree": "Location longue durée",
    "location_courte_duree": "Location courte durée (type Airbnb)",
    "achat_revente": "Achat-revente",
}
LABELS_STRUCTURE = {
    "personne_physique": "Personne physique",
    "sci_ir": "SCI à l'IR",
    "sci_is": "SCI à l'IS",
}
LABELS_DIFFERE = {
    "partiel": "Différé partiel (intérêts seuls payés)",
    "total": "Différé total (intérêts capitalisés)",
}


def _eur(v: float) -> str:
    v = 0.0 if round(v) == 0 else v  # évite « -0 € »
    return f"{v:,.0f} €".replace(",", " ")


def _pct(v: float, digits: int = 1) -> str:
    return f"{v * 100:.{digits}f} %".replace(".", ",")


def _label_type_projet(v: str) -> str:
    return LABELS_TYPE_PROJET.get(v, v.replace("_", " "))


def _label_structure(v: str) -> str:
    return LABELS_STRUCTURE.get(v, v.replace("_", " "))


# ---------------------------------------------------------------------------
# Aides bas niveau (mise en forme Word via oxml)
# ---------------------------------------------------------------------------

def _add_bottom_border(paragraph, color: str = "1D6F5C", size: int = 6) -> None:
    p_pr = paragraph._p.get_or_add_pPr()
    p_bdr = OxmlElement("w:pBdr")
    bottom = OxmlElement("w:bottom")
    bottom.set(qn("w:val"), "single")
    bottom.set(qn("w:sz"), str(size))
    bottom.set(qn("w:space"), "4")
    bottom.set(qn("w:color"), color)
    p_bdr.append(bottom)
    p_pr.append(p_bdr)


def _add_field(paragraph, instr: str) -> None:
    run = paragraph.add_run()
    begin = OxmlElement("w:fldChar")
    begin.set(qn("w:fldCharType"), "begin")
    instr_el = OxmlElement("w:instrText")
    instr_el.set(qn("xml:space"), "preserve")
    instr_el.text = instr
    sep = OxmlElement("w:fldChar")
    sep.set(qn("w:fldCharType"), "separate")
    end = OxmlElement("w:fldChar")
    end.set(qn("w:fldCharType"), "end")
    run._r.append(begin)
    run._r.append(instr_el)
    run._r.append(sep)
    run._r.append(end)


def _set_cell_background(cell, hex_color: str) -> None:
    tc_pr = cell._tc.get_or_add_tcPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), hex_color)
    tc_pr.append(shd)


def _bordure_bas_cellule(cell, color: str = BORDURE_HEX, size: int = 4) -> None:
    tc_pr = cell._tc.get_or_add_tcPr()
    bordures = OxmlElement("w:tcBorders")
    bottom = OxmlElement("w:bottom")
    bottom.set(qn("w:val"), "single")
    bottom.set(qn("w:sz"), str(size))
    bottom.set(qn("w:color"), color)
    bordures.append(bottom)
    tc_pr.append(bordures)


def _cell_marges(cell, haut: int = 90, bas: int = 90, gauche: int = 120, droite: int = 120) -> None:
    tc_pr = cell._tc.get_or_add_tcPr()
    marges = OxmlElement("w:tcMar")
    for cote, valeur in (("top", haut), ("bottom", bas), ("left", gauche), ("right", droite)):
        el = OxmlElement(f"w:{cote}")
        el.set(qn("w:w"), str(valeur))
        el.set(qn("w:type"), "dxa")
        marges.append(el)
    tc_pr.append(marges)


def _densite_pour(nb_lignes: int, hauteur_max_cm: float | None) -> str:
    if hauteur_max_cm is None:
        return "normal"
    for densite in ("normal", "compact"):
        if nb_lignes * HAUTEUR_LIGNE_CM[densite] <= hauteur_max_cm:
            return densite
    return "serre"


# (taille libellé, taille valeur, marge haut/bas en twips) par densité
STYLE_DENSITE = {"normal": (10.5, 11, 90), "compact": (9.5, 10, 45), "serre": (9, 9.5, 25)}


def _ajouter_table_kv(container, lignes: list[tuple], densite: str = "normal", largeur_cm: float | None = None):
    """Tableau clé/valeur épuré : un filet clair sous chaque ligne, un léger
    zébrage, les montants négatifs en rouge. Une ligne (clé, valeur, "total")
    est mise en évidence (fond teinté, texte en gras)."""
    taille_cle, taille_valeur, marge = STYLE_DENSITE[densite]
    table = container.add_table(rows=0, cols=2)
    table.style = "Normal Table"
    table.autofit = largeur_cm is None
    # Largeurs fixes : sinon Word partage la place à parts égales et coupe
    # les libellés sur deux lignes, ce qui allonge le tableau.
    largeurs = (largeur_cm * 0.64, largeur_cm * 0.36) if largeur_cm else None
    for i, ligne in enumerate(lignes):
        cle, valeur = ligne[0], ligne[1]
        est_total = len(ligne) > 2 and ligne[2] == "total"
        row = table.add_row()
        cell_cle, cell_valeur = row.cells
        if largeurs:
            cell_cle.width, cell_valeur.width = Cm(largeurs[0]), Cm(largeurs[1])

        _texte(cell_cle.paragraphs[0], cle, taille_cle, TEXTE_FONCE if est_total else GRIS_LIBELLE, gras=est_total)

        p_valeur = cell_valeur.paragraphs[0]
        p_valeur.alignment = WD_ALIGN_PARAGRAPH.RIGHT
        negatif = valeur.lstrip().startswith(("-", "−"))
        couleur = ROUGE if negatif else (PRIMARY_COLOR if est_total else TEXTE_FONCE)
        _texte(p_valeur, valeur, taille_valeur + (0.5 if est_total else 0), couleur, gras=True)

        for cell in (cell_cle, cell_valeur):
            _cell_marges(cell, haut=marge, bas=marge)
            _bordure_bas_cellule(cell, color=MARQUE_HEX if est_total else BORDURE_HEX, size=8 if est_total else 4)
            if est_total:
                _set_cell_background(cell, FOND_TUILE_HEX)
            elif i % 2 == 1:
                _set_cell_background(cell, ZEBRA_HEX)
    if largeurs:
        table.columns[0].width, table.columns[1].width = Cm(largeurs[0]), Cm(largeurs[1])
    return table


def _texte(paragraphe, texte: str, taille: float, couleur=None, gras: bool = False, italique: bool = False):
    # Pas d'espacement automatique après le paragraphe (Word en ajoute par
    # défaut) : les éléments de mise en page gèrent leurs espaces eux-mêmes.
    paragraphe.paragraph_format.space_after = Pt(0)
    paragraphe.paragraph_format.line_spacing = 1.0
    run = paragraphe.add_run(texte)
    # Le gras passe par les familles demi-grasses incorporées (voir polices_word).
    if gras:
        run.font.name = POLICE_TITRE_GRAS if taille >= 14 else POLICE_GRAS
    else:
        run.font.name = POLICE
    run.font.size = Pt(taille)
    run.font.color.rgb = couleur or TEXTE_FONCE
    run.bold = False
    run.italic = italique
    return run


def _bordures_cellule(cell, **cotes) -> None:
    """Bordures d'une cellule : cote=(couleur hex, épaisseur en 1/8 pt) ; les
    côtés non cités sont supprimés."""
    tc_pr = cell._tc.get_or_add_tcPr()
    bordures = OxmlElement("w:tcBorders")
    for cote in ("top", "left", "bottom", "right"):
        el = OxmlElement(f"w:{cote}")
        if cotes.get(cote):
            couleur, taille = cotes[cote]
            el.set(qn("w:val"), "single")
            el.set(qn("w:sz"), str(taille))
            el.set(qn("w:color"), couleur)
        else:
            el.set(qn("w:val"), "nil")
        bordures.append(el)
    tc_pr.append(bordures)


def _espace(container, points: float = 6) -> None:
    p = container.add_paragraph()
    p.paragraph_format.space_before = Pt(0)
    p.paragraph_format.space_after = Pt(0)
    p.paragraph_format.line_spacing = Pt(points)


def _tuiles(container, tuiles: list[tuple[str, str, bool | None]], largeur_cm: float = LARGEUR_CONTENU_CM, taille_valeur: float = 17) -> None:
    """Rangée de tuiles d'indicateurs (libellé, valeur, favorable). La valeur
    est verte si favorable, rouge si défavorable, foncée si neutre ; un filet
    coloré à gauche rappelle le sens. Un filet blanc à droite fait office
    d'espacement entre les tuiles (Word ne gère pas les marges entre cellules)."""
    table = container.add_table(rows=1, cols=len(tuiles))
    table.autofit = False
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    _supprimer_bordures(table)
    largeur = largeur_cm / len(tuiles)
    for i, (cell, (libelle, valeur, favorable)) in enumerate(zip(table.rows[0].cells, tuiles)):
        table.columns[i].width = Cm(largeur)
        cell.width = Cm(largeur)
        cell.vertical_alignment = WD_ALIGN_VERTICAL.CENTER
        _set_cell_background(cell, FOND_TUILE_HEX)
        accent = ROUGE_HEX if favorable is False else (VERT_HEX if favorable else MARQUE_HEX)
        _bordures_cellule(cell, left=(accent, 24), right=(FOND_PAGE_HEX, 48) if i < len(tuiles) - 1 else None)
        _cell_marges(cell, haut=110, bas=130, gauche=200, droite=120)
        _texte(cell.paragraphs[0], libelle.upper(), 7.5, GRIS_LIBELLE, gras=True)
        couleur = VERT if favorable else (ROUGE if favorable is False else PRIMARY_COLOR)
        p_valeur = cell.add_paragraph()
        p_valeur.paragraph_format.space_before = Pt(2)
        _texte(p_valeur, valeur, taille_valeur, couleur, gras=True)
    _espace(container, 10)


# Pastille d'un critère pas encore évalué (gris, comme sur le site).
GRIS_NEUTRE = "9AA3AD"


def _pour_la_banque(payload) -> bool:
    """Le dossier est-il destiné à la banque ? Oui sauf la formule
    « Personnel », sans les chapitres profil, endettement et pièces à fournir
    (ni sans crédit : pas de banque à convaincre)."""
    if payload.chapitres is None:
        return True
    return bool({"profil", "endettement", "annexes"} & set(payload.chapitres))


def _texte_repere_banque(critere: dict, inp, resultat: dict) -> str:
    """Pour la banque, des faits sans jugement : « Effort d'épargne de
    141 €/mois » plutôt que « Effort d'épargne important »."""
    if critere["nom"] == "Rentabilité":
        cf = resultat["cashflow_mensuel"]
        if cf >= 0:
            return f"cash-flow net de +{_eur(cf)} par mois après crédit, charges et impôts"
        return f"effort d'épargne de {_eur(-cf)} par mois après crédit, charges et impôts"
    if critere["nom"] == "Marge":
        ar = resultat["achat_revente"]
        part = ar["marge_nette"] / ar["cout_total_acquisition"] if ar["cout_total_acquisition"] else 0
        return f"marge nette de {_eur(ar['marge_nette'])}, soit {_pct(part)} du coût total de l'opération"
    texte = critere["texte"].replace(", souvent jugé faible", "")
    return texte[0].lower() + texte[1:]


def _bandeau_reperes(doc, v: dict, inp, resultat: dict, pour_banque: bool) -> None:
    """En tête de synthèse, les trois repères du projet (rentabilité ou
    marge, prix, financement), chacun avec sa pastille de couleur. Pour la
    banque : titre neutre et faits ; formule Personnel : le verdict du site
    (projet solide, à renforcer, à revoir)."""
    filet, fond = COULEURS_VERDICT["neutre" if pour_banque else v["niveau"]]
    table = doc.add_table(rows=1, cols=1)
    table.autofit = False
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    _supprimer_bordures(table)
    table.columns[0].width = Cm(LARGEUR_CONTENU_CM)
    cell = table.rows[0].cells[0]
    cell.width = Cm(LARGEUR_CONTENU_CM)
    _set_cell_background(cell, fond)
    _bordures_cellule(cell, left=(filet, 36))
    _cell_marges(cell, haut=140, bas=150, gauche=260, droite=260)
    titre = "Les 3 repères du projet" if pour_banque else v["titre"]
    _texte(cell.paragraphs[0], titre, 15, RGBColor.from_string(filet), gras=True)
    cell.paragraphs[0].paragraph_format.space_after = Pt(4)
    for critere in v["criteres"]:
        p = cell.add_paragraph()
        p.paragraph_format.space_before = Pt(3)
        couleur = GRIS_NEUTRE if critere["niveau"] == "neutre" else COULEURS_VERDICT[critere["niveau"]][0]
        _texte(p, "●  ", 11, RGBColor.from_string(couleur))
        if pour_banque:
            texte = _texte_repere_banque(critere, inp, resultat)
        else:
            # « Effort d'épargne modéré : 141 €/mois » → « effort d'épargne modéré, 141 €/mois ».
            texte = critere["texte"].replace(" : ", ", ")
            texte = texte[0].lower() + texte[1:]
        _texte(p, critere["nom"], 10.5, TEXTE_FONCE, gras=True)
        _texte(p, f" : {texte}", 10.5, TEXTE_FONCE)
    p = cell.add_paragraph()
    p.paragraph_format.space_before = Pt(6)
    _texte(p, v["detail"], 9.5, GRIS_LIBELLE)
    _espace(doc, 10)


def _signet(paragraphe, nom: str, identifiant: int) -> None:
    """Signet Word autour du paragraphe : cible des liens du sommaire."""
    debut = OxmlElement("w:bookmarkStart")
    debut.set(qn("w:id"), str(identifiant))
    debut.set(qn("w:name"), nom)
    fin = OxmlElement("w:bookmarkEnd")
    fin.set(qn("w:id"), str(identifiant))
    paragraphe._p.insert(0, debut)
    paragraphe._p.append(fin)


def _entete_chapitre(
    doc,
    numero: int,
    titre: str,
    description: str | None,
    partie: str | None = None,
    parties: tuple[str, ...] = (),
    icone: str | None = None,
) -> None:
    """Numéro dans un pavé bleu, icône, titre et phrase d'explication (le
    fil des parties est dans le pied de page, voir _pied_de_page_chapitre)."""
    table = doc.add_table(rows=1, cols=2)
    table.autofit = False
    _supprimer_bordures(table)
    largeurs = (1.9, LARGEUR_CONTENU_CM - 1.9)
    cell_num, cell_titre = table.rows[0].cells
    for i, (cell, largeur) in enumerate(zip((cell_num, cell_titre), largeurs)):
        table.columns[i].width = Cm(largeur)
        cell.width = Cm(largeur)
        cell.vertical_alignment = WD_ALIGN_VERTICAL.CENTER
    # Pavé du numéro : image aux coins arrondis (une cellule Word reste carrée).
    _cell_marges(cell_num, haut=0, bas=0, gauche=0, droite=0)
    p_num = cell_num.paragraphs[0]
    p_num.alignment = WD_ALIGN_PARAGRAPH.LEFT
    p_num.paragraph_format.space_after = Pt(0)
    p_num.add_run().add_picture(io.BytesIO(visuels.pave_numero(numero)), height=Cm(1.55))
    _cell_marges(cell_titre, haut=40, bas=60, gauche=260, droite=60)
    _bordures_cellule(cell_titre, bottom=(MARQUE_HEX, 12))
    p_titre = cell_titre.paragraphs[0]
    if icone:
        run_icone = p_titre.add_run()
        run_icone.add_picture(io.BytesIO(visuels.icone(icone)), height=Cm(0.62))
        run_icone.font.position = Pt(-3)  # icône alignée sur le milieu du titre
        _texte(p_titre, "  ", 20, TEXTE_FONCE)
    _texte(p_titre, titre, 20, TEXTE_FONCE, gras=True)
    _signet(p_titre, f"chapitre_{numero:02d}", numero)
    if description:
        p = cell_titre.add_paragraph()
        p.paragraph_format.space_before = Pt(1)
        _texte(p, description, 10, GRIS_LIBELLE)
    _espace(doc, 14)


def _a_retenir(doc, niveau: str, texte: str) -> None:
    """Encadré « À retenir » : la conclusion du chapitre en une phrase, en
    couleur selon qu'elle est favorable, à surveiller ou défavorable."""
    filet, fond = COULEURS_VERDICT[niveau]
    table = doc.add_table(rows=1, cols=1)
    table.autofit = False
    table.alignment = WD_TABLE_ALIGNMENT.CENTER  # aligné sur les tuiles, centrées elles aussi
    _supprimer_bordures(table)
    _ancrer_en_bas_de_page(table)
    table.columns[0].width = Cm(LARGEUR_CONTENU_CM)
    cell = table.rows[0].cells[0]
    cell.width = Cm(LARGEUR_CONTENU_CM)
    _set_cell_background(cell, fond)
    _bordures_cellule(cell, left=(filet, 36))
    _cell_marges(cell, haut=90, bas=100, gauche=240, droite=240)
    _texte(cell.paragraphs[0], "À RETENIR", 7.5, RGBColor.from_string(filet), gras=True)
    p = cell.add_paragraph()
    p.paragraph_format.space_before = Pt(1)
    _texte(p, texte, 11.5, RGBColor.from_string(filet))
    _espace(doc, 1)


def _ancrer_en_bas_de_page(table) -> None:
    """Tableau flottant posé en bas de la zone de texte de la page, centré :
    le contenu du chapitre s'écoule au-dessus sans le recouvrir."""
    tbl_pr = table._tbl.tblPr
    position = OxmlElement("w:tblpPr")
    for attribut, valeur in (
        ("w:leftFromText", "0"),
        ("w:rightFromText", "0"),
        ("w:topFromText", "200"),
        ("w:bottomFromText", "0"),
        ("w:vertAnchor", "margin"),
        ("w:horzAnchor", "margin"),
        ("w:tblpXSpec", "center"),
        ("w:tblpYSpec", "bottom"),
    ):
        position.set(qn(attribut), valeur)
    style = tbl_pr.find(qn("w:tblStyle"))
    if style is not None:
        style.addnext(position)
    else:
        tbl_pr.insert(0, position)
    chevauchement = OxmlElement("w:tblOverlap")
    chevauchement.set(qn("w:val"), "never")
    position.addnext(chevauchement)


def _pied_de_page_chapitre(section, fil: bytes) -> None:
    """Pied de page propre au chapitre : fil des parties (où en est le
    lecteur) à gauche, mention au centre, pagination à droite."""
    section.footer.is_linked_to_previous = False
    p = section.footer.paragraphs[0]
    _taquet_a_droite(p)
    p.paragraph_format.tab_stops.add_tab_stop(Cm(LARGEUR_CONTENU_CM - 2.6), WD_TAB_ALIGNMENT.RIGHT)
    run = p.add_run()
    run.add_picture(io.BytesIO(fil), height=Cm(0.62))
    run.font.position = Pt(-4)
    _texte(p, "\tÉtabli avec Credaura — estimation à faire valider par un professionnel", 7.5, GRIS_COLOR, italique=True)
    _texte(p, "\tPage ", 8, GRIS_COLOR)
    _add_field(p, "PAGE")
    _texte(p, " / ", 8, GRIS_COLOR)
    _add_field(p, "NUMPAGES")
    for run in p.runs:  # numéros de page : même style que le texte du pied
        if not run._r.xpath(".//w:drawing") and not run.italic:
            run.font.size = Pt(8)
            run.font.name = POLICE
            run.font.color.rgb = GRIS_COLOR


def _supprimer_bordures(table) -> None:
    tbl_pr = table._tbl.tblPr
    bordures = OxmlElement("w:tblBorders")
    for cote in ("top", "left", "bottom", "right", "insideH", "insideV"):
        el = OxmlElement(f"w:{cote}")
        el.set(qn("w:val"), "nil")
        bordures.append(el)
    tbl_pr.append(bordures)


def _proportions_png(image_bytes: bytes) -> float:
    """Largeur ÷ hauteur d'une image PNG (lues dans l'en-tête IHDR)."""
    largeur = int.from_bytes(image_bytes[16:20], "big")
    hauteur = int.from_bytes(image_bytes[20:24], "big")
    return largeur / hauteur


def _ajouter_table_et_graphique(
    doc: Document,
    lignes: list[tuple[str, str]],
    image_bytes: bytes | None,
    largeur_table_cm: float = 13.2,
    largeur_image_cm: float = 11.5,
    hauteur_max_cm: float = HAUTEUR_BLOC_CM,
) -> None:
    """Tableau de chiffres à gauche, graphique correspondant à droite (mise en
    page côte à côte). Le graphique est réduit s'il dépasse `hauteur_max_cm`
    et le tableau passe en version compacte s'il ne tient pas, pour que le
    chapitre reste sur une seule page."""
    densite = _densite_pour(len(lignes), hauteur_max_cm)
    if not image_bytes:
        _ajouter_table_kv(doc, lignes, densite)
        return

    conteneur = doc.add_table(rows=1, cols=2)
    conteneur.autofit = False
    conteneur.alignment = WD_TABLE_ALIGNMENT.CENTER
    _supprimer_bordures(conteneur)
    conteneur.columns[0].width = Cm(largeur_table_cm)
    conteneur.columns[1].width = Cm(largeur_image_cm)
    cell_table, cell_image = conteneur.rows[0].cells
    cell_table.width = Cm(largeur_table_cm)
    cell_image.width = Cm(largeur_image_cm)

    _ajouter_table_kv(cell_table, lignes, densite, largeur_cm=largeur_table_cm - 0.4)

    p_image = cell_image.paragraphs[0]
    p_image.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_image.paragraph_format.space_after = Pt(0)
    largeur = min(largeur_image_cm - 0.5, hauteur_max_cm * _proportions_png(image_bytes))
    p_image.add_run().add_picture(io.BytesIO(image_bytes), width=Cm(largeur))


def _alignement_vertical(section, valeur: str) -> None:
    """« center » pour la couverture, « top » pour les chapitres. add_section()
    recopie les propriétés de la section précédente : on remplace l'éventuel
    alignement hérité."""
    sect_pr = section._sectPr
    for ancien in sect_pr.findall(qn("w:vAlign")):
        sect_pr.remove(ancien)
    valign = OxmlElement("w:vAlign")
    valign.set(qn("w:val"), valeur)
    sect_pr.append(valign)


def _mettre_en_page(section, centrer: bool = False) -> None:
    section.orientation = WD_ORIENT.LANDSCAPE
    section.page_width = Mm(LARGEUR_PAGE_CM * 10)
    section.page_height = Mm(HAUTEUR_PAGE_CM * 10)
    section.left_margin = Cm(MARGE_CM)
    section.right_margin = Cm(MARGE_CM)
    section.top_margin = Cm(MARGE_CM)
    section.bottom_margin = Cm(MARGE_CM)
    # Pied de page plus bas que le réglage par défaut (1,27 cm) : de l'air
    # entre l'encadré « À retenir », posé en bas de la zone de texte, et le fil.
    section.footer_distance = Cm(0.6)
    _alignement_vertical(section, "center" if centrer else "top")


def _image_fond_de_page() -> bytes:
    from PIL import Image

    image = Image.new("RGB", (16, 16), "#" + FOND_PAGE_HEX)
    tampon = io.BytesIO()
    image.save(tampon, format="PNG")
    return tampon.getvalue()


def _fond_de_page(entete) -> None:
    """Fond bleuté pleine page, posé derrière le texte depuis l'en-tête : il
    se répète sur chaque page et, contrairement à la couleur de page de Word,
    il reste à l'impression et dans l'export PDF."""
    run = entete.paragraphs[0].add_run()
    run.add_picture(io.BytesIO(_image_fond_de_page()), width=Cm(LARGEUR_PAGE_CM), height=Cm(HAUTEUR_PAGE_CM))
    dessin = run._r.find(qn("w:drawing"))
    inline = dessin.find(qn("wp:inline"))
    ancre = OxmlElement("wp:anchor")
    for attribut, valeur in (
        ("distT", "0"), ("distB", "0"), ("distL", "0"), ("distR", "0"), ("simplePos", "0"),
        ("relativeHeight", "0"), ("behindDoc", "1"), ("locked", "1"), ("layoutInCell", "1"), ("allowOverlap", "1"),
    ):
        ancre.set(attribut, valeur)
    position_simple = OxmlElement("wp:simplePos")
    position_simple.set("x", "0")
    position_simple.set("y", "0")
    ancre.append(position_simple)
    for axe in ("positionH", "positionV"):
        position = OxmlElement(f"wp:{axe}")
        position.set("relativeFrom", "page")
        decalage = OxmlElement("wp:posOffset")
        decalage.text = "0"
        position.append(decalage)
        ancre.append(position)
    ancre.append(inline.find(qn("wp:extent")))
    marges = OxmlElement("wp:effectExtent")
    for cote in ("l", "t", "r", "b"):
        marges.set(cote, "0")
    ancre.append(marges)
    ancre.append(OxmlElement("wp:wrapNone"))
    for enfant in ("wp:docPr", "wp:cNvGraphicFramePr", "a:graphic"):
        element = inline.find(qn(enfant))
        if element is not None:
            ancre.append(element)
    dessin.remove(inline)
    dessin.append(ancre)


def _configurer_page(doc: Document) -> None:
    _mettre_en_page(doc.sections[0], centrer=True)
    # Couleur de page légèrement bleutée, celle des graphiques : plus de
    # cadre blanc autour des images (à l'écran ; le fond posé dans les
    # en-têtes, voir _fond_de_page, la garde à l'impression et en PDF).
    fond = OxmlElement("w:background")
    fond.set(qn("w:color"), FOND_PAGE_HEX)
    doc.element.insert(0, fond)
    # Ordre imposé par le schéma de Word : après view, zoom et les réglages
    # qui les suivent, sinon Word peut juger le fichier abîmé.
    reglages = doc.settings.element
    precedents = ("writeProtection", "view", "zoom", "removePersonalInformation", "removeDateAndTime",
                  "doNotDisplayPageBoundaries")
    position = 0
    for i, enfant in enumerate(reglages):
        if enfant.tag in {qn(f"w:{nom}") for nom in precedents}:
            position = i + 1
    reglages.insert(position, OxmlElement("w:displayBackgroundShape"))


def _lien_interne(paragraphe, signet: str) -> None:
    """Transforme les runs du paragraphe en lien vers un signet du document."""
    lien = OxmlElement("w:hyperlink")
    lien.set(qn("w:anchor"), signet)
    lien.set(qn("w:history"), "1")
    for run in list(paragraphe._p.findall(qn("w:r"))):
        lien.append(run)
    paragraphe._p.append(lien)


def _ajouter_sommaire(doc: Document, sections: list[tuple]) -> None:
    """Sommaire sur une page, parties en deux colonnes. Chaque chapitre tient
    sur une page (vérifié par les tests de pagination) : le chapitre n
    commence page n + 2 (après la couverture et le sommaire). Chaque ligne
    renvoie au chapitre d'un clic."""
    _nouvelle_page_chapitre(doc)
    p = doc.add_paragraph()
    _texte(p, "Sommaire", 24, TEXTE_FONCE, gras=True)
    p.paragraph_format.space_after = Pt(4)
    _add_bottom_border(p, color=MARQUE_HEX, size=12)
    _espace(doc, 24)

    parties: dict[str, list[tuple[int, str]]] = {}
    for numero, (cle, titre, _description, _fn) in enumerate(sections, start=1):
        parties.setdefault(PARTIE_DU_CHAPITRE[cle], []).append((numero, titre))
    ordre = [partie for partie in PARTIES if partie in parties]
    # Deux colonnes équilibrées en nombre de lignes, sans couper une partie.
    lignes = [len(parties[partie]) + 1.5 for partie in ordre]
    total, cumul, coupure = sum(lignes), 0.0, len(ordre)
    for i, n in enumerate(lignes):
        if cumul + n / 2 > total / 2:
            coupure = max(i, 1)
            break
        cumul += n
    colonnes = [ordre[:coupure], ordre[coupure:]]

    largeur_colonne = (LARGEUR_CONTENU_CM - 1.5) / 2
    table = doc.add_table(rows=1, cols=3)
    table.autofit = False
    _supprimer_bordures(table)
    for j, largeur in enumerate((largeur_colonne, 1.5, largeur_colonne)):
        table.columns[j].width = Cm(largeur)
        table.rows[0].cells[j].width = Cm(largeur)
    for cell, parties_colonne in zip((table.rows[0].cells[0], table.rows[0].cells[2]), colonnes):
        cell.vertical_alignment = WD_ALIGN_VERTICAL.TOP
        _cell_marges(cell, haut=0, bas=0, gauche=0, droite=0)
        premier = True
        for partie in parties_colonne:
            p_partie = cell.paragraphs[0] if premier else cell.add_paragraph()
            _texte(p_partie, partie.upper(), 9.5, LAITON, gras=True)
            p_partie.paragraph_format.space_before = Pt(0 if premier else 22)
            p_partie.paragraph_format.space_after = Pt(6)
            premier = False
            for numero, titre in parties[partie]:
                p_ligne = cell.add_paragraph()
                taquets = p_ligne.paragraph_format.tab_stops
                taquets.add_tab_stop(Cm(1.2))
                taquets.add_tab_stop(Cm(largeur_colonne - 0.1), WD_TAB_ALIGNMENT.RIGHT, WD_TAB_LEADER.DOTS)
                _texte(p_ligne, f"{numero:02d}", 13, PRIMARY_COLOR, gras=True)
                _texte(p_ligne, f"\t{titre}", 13, TEXTE_FONCE)
                _texte(p_ligne, f"\t{numero + 2}", 13, GRIS_LIBELLE)
                p_ligne.paragraph_format.space_after = Pt(9)  # après _texte, qui le remet à 0
                _lien_interne(p_ligne, f"chapitre_{numero:02d}")


def _nouvelle_page_chapitre(doc: Document):
    """Un chapitre par page : nouvelle section démarrant sur une nouvelle
    page, contenu aligné en haut, en-tête/pied hérités de la page de garde."""
    section = doc.add_section(WD_SECTION.NEW_PAGE)
    _mettre_en_page(section)
    # add_section() copie different_first_page_header_footer=True de la page de
    # garde ; sans correction, chaque chapitre (qui est aussi la "première
    # page" de sa propre section) afficherait l'en-tête/pied vide du premier.
    section.different_first_page_header_footer = False
    return section


def _taquet_a_droite(paragraphe) -> None:
    """Un seul taquet, aligné à droite en bout de ligne : on neutralise ceux
    du style En-tête/Pied de page de Word (centre et droite à 8,3/16,5 cm)."""
    taquets = paragraphe.paragraph_format.tab_stops
    for position in (8.255, 16.51):
        taquets.add_tab_stop(Cm(position), WD_TAB_ALIGNMENT.CLEAR)
    taquets.add_tab_stop(Cm(LARGEUR_CONTENU_CM), WD_TAB_ALIGNMENT.RIGHT)


def _configurer_entete_pied(doc: Document, libelle_projet: str) -> None:
    """En-tête : titre du dossier à gauche, projet à droite, filet vert. Pied :
    mention à gauche, pagination à droite. Absents de la couverture."""
    section = doc.sections[0]
    section.different_first_page_header_footer = True
    _fond_de_page(section.first_page_header)

    header_p = section.header.paragraphs[0]
    _taquet_a_droite(header_p)
    _texte(header_p, "CREDAURA  ·  DOSSIER DE FINANCEMENT IMMOBILIER", 8, PRIMARY_COLOR, gras=True)
    _texte(header_p, "\t" + libelle_projet, 8, GRIS_COLOR)
    _add_bottom_border(header_p, color=LAITON_HEX, size=6)
    _fond_de_page(section.header)

    footer_p = section.footer.paragraphs[0]
    _taquet_a_droite(footer_p)
    _texte(footer_p, "Établi avec Credaura — estimation pédagogique, à faire valider par un professionnel", 8, GRIS_COLOR, italique=True)
    _texte(footer_p, "\tPage ", 8, GRIS_COLOR)
    _add_field(footer_p, "PAGE")
    _texte(footer_p, " / ", 8, GRIS_COLOR)
    _add_field(footer_p, "NUMPAGES")
    for run in footer_p.runs:
        run.font.size = Pt(8)
        run.font.name = POLICE
        run.font.color.rgb = GRIS_COLOR


def _mensualite_et_loyers(inp, resultat: dict, is_achat_revente: bool) -> tuple[float, float]:
    if is_achat_revente:
        ar = resultat["achat_revente"]
        return ar["frais_portage_interets"] / inp.duree_portage_mois, 0.0
    # Taux d'endettement HCSF : mensualité assurance comprise.
    mensualite = resultat.get("mensualite_credit_hors_assurance", 0.0) + resultat.get("assurance_emprunteur_mensuelle", 0.0)
    return mensualite, resultat["annees"][0]["loyers_bruts"] / 12


def _frais_bancaires(resultat: dict, is_achat_revente: bool) -> float:
    return (resultat["achat_revente"] if is_achat_revente else resultat).get("frais_bancaires", 0.0)


def _cout_apport_emprunt(resultat: dict, is_achat_revente: bool) -> tuple[float, float, float]:
    source = resultat["achat_revente"] if is_achat_revente else resultat
    return (
        source.get("cout_total_acquisition", 0.0),
        source.get("apport_reel", 0.0),
        source.get("montant_emprunte", 0.0),
    )


# ---------------------------------------------------------------------------
# Page de garde et sommaire
# ---------------------------------------------------------------------------

def _titre_projet(payload: ExportDossierInput, inp) -> str:
    if payload.adresse_bien:
        return payload.adresse_bien
    return f"{inp.type_bien.value.capitalize()} de {inp.surface_m2:.0f} m²"


def _tuiles_couverture(inp, resultat: dict, is_achat_revente: bool) -> list[tuple[str, str, bool | None]]:
    if is_achat_revente:
        ar = resultat["achat_revente"]
        return [
            ("Prix d'achat", _eur(inp.prix_achat), None),
            ("Prix de revente", _eur(ar["prix_revente"]), None),
            ("Marge nette", _eur(ar["marge_nette"]), ar["marge_nette"] >= 0),
            (libelle_rentabilite_ar(ar["apport_reel"]), _pct(ar["rentabilite_operation_pct"]), ar["rentabilite_operation_pct"] >= 0),
        ]
    revenu = (
        ("Chiffre d'affaires mensuel", _eur(resultat["annees"][0]["loyers_bruts"] / 12))
        if inp.type_projet == TypeProjet.location_courte_duree
        else ("Loyer mensuel", _eur(inp.loyer_mensuel_hors_charges))
    )
    cf = resultat["cashflow_mensuel"]
    return [
        ("Prix d'achat", _eur(inp.prix_achat), None),
        (*revenu, None),
        ("Cash-flow net mensuel", _eur(cf), cf >= 0),
        ("Rendement brut", _pct(resultat["rendement_brut"]), None),
    ]


def _ajouter_page_de_garde(doc: Document, payload: ExportDossierInput, inp, resultat: dict, is_achat_revente: bool) -> None:
    # Bandeau bleu notaire : logo à gauche, titre du dossier et du projet à droite.
    bandeau = doc.add_table(rows=1, cols=2)
    bandeau.autofit = False
    bandeau.alignment = WD_TABLE_ALIGNMENT.CENTER  # aligné sur les tuiles en dessous
    _supprimer_bordures(bandeau)
    largeurs = (3.6, LARGEUR_CONTENU_CM - 3.6)
    cell_logo, cell_titre = bandeau.rows[0].cells
    for i, (cell, largeur) in enumerate(zip((cell_logo, cell_titre), largeurs)):
        bandeau.columns[i].width = Cm(largeur)
        cell.width = Cm(largeur)
        cell.vertical_alignment = WD_ALIGN_VERTICAL.CENTER
        _set_cell_background(cell, MARQUE_HEX)
    _cell_marges(cell_logo, haut=500, bas=500, gauche=400, droite=100)
    cell_logo.paragraphs[0].add_run().add_picture(io.BytesIO(visuels.logo(320, visuels.LAITON_CLAIR)), width=Cm(2.6))
    _cell_marges(cell_titre, haut=500, bas=500, gauche=200, droite=400)
    _texte(cell_titre.paragraphs[0], "CREDAURA  ·  DOSSIER DE FINANCEMENT IMMOBILIER", 11, LAITON_CLAIR, gras=True)
    p_titre = cell_titre.add_paragraph()
    p_titre.paragraph_format.space_before = Pt(4)
    _texte(p_titre, _titre_projet(payload, inp), 28, BLANC, gras=True)
    p_sous = cell_titre.add_paragraph()
    p_sous.paragraph_format.space_before = Pt(4)
    _texte(
        p_sous,
        f"{_label_type_projet(inp.type_projet.value)}  ·  {_label_structure(inp.structure_juridique.value)}",
        12,
        BLANC,
    )
    _espace(doc, 22)

    _tuiles(doc, _tuiles_couverture(inp, resultat, is_achat_revente), taille_valeur=22)
    _espace(doc, 10)

    infos = []
    if payload.nom_emprunteur:
        infos.append(("Emprunteur" if inp.avec_credit else "Investisseur") + f" : {payload.nom_emprunteur}")
    infos.append(f"Document établi le {datetime.now().strftime('%d/%m/%Y')}")
    p_infos = doc.add_paragraph()
    p_infos.alignment = WD_ALIGN_PARAGRAPH.CENTER
    _texte(p_infos, "   ·   ".join(infos), 11, GRIS_LIBELLE)
    p_note = doc.add_paragraph()
    p_note.alignment = WD_ALIGN_PARAGRAPH.CENTER
    _texte(
        p_note,
        "Document établi avec Credaura — estimation pédagogique, à faire valider par un professionnel "
        "avant toute décision.",
        9,
        GRIS_COLOR,
        italique=True,
    )


# ---------------------------------------------------------------------------
# Sections
# ---------------------------------------------------------------------------

def _taux_endettement(payload, inp, resultat, is_achat_revente):
    mensualite_projet, loyers_mensuels = _mensualite_et_loyers(inp, resultat, is_achat_revente)
    return endet_mod.calculer_taux_endettement(
        payload.profil.revenus_nets_mensuels_foyer,
        payload.profil.autres_revenus_mensuels,
        payload.profil.mensualites_credits_existants,
        mensualite_projet,
        loyers_mensuels,
    )


def _image_cascade_loyer(resultat: dict) -> bytes:
    etapes = analyse.etapes_loyer_mensuel(resultat)
    cashflow = sum(v for _, v in etapes)
    return charts.chart_pont_marge(
        [(etapes[0][0], etapes[0][1], True)]
        + [(libelle, v, False) for libelle, v in etapes[1:]]
        + [("Cash-flow net", cashflow, True)],
        titre="Du loyer au cash-flow (mois type)",
    )


def _image_pont_marge(resultat: dict) -> bytes:
    ar = resultat["achat_revente"]
    return charts.chart_pont_marge(
        [
            ("Produit net de vente", ar["produit_net_vente"], True),
            ("Coût d'acquisition", -ar["cout_total_acquisition"], False),
            ("Frais de portage", -ar["frais_portage_total"], False),
            ("Impôt", -ar["impot_total"], False),
            ("Marge nette", ar["marge_nette"], True),
        ]
    )


def _lieu(adresse: str | None) -> str:
    """« à Lyon (69002) » à partir d'une adresse se terminant par le code
    postal et la commune ; vide sinon."""
    trouve = re.search(r"\b(\d{5})\s+([^,\d][^,]*)$", (adresse or "").strip())
    return f" à {trouve.group(2).strip()} ({trouve.group(1)})" if trouve else ""


def phrase_projet(payload, inp, resultat: dict, is_achat_revente: bool) -> str:
    """Le projet en une phrase, en tête de la synthèse : ce que le banquier
    lit en premier."""
    bien = "un appartement" if inp.type_bien.value == "appartement" else "une maison"
    neuf = " neuf" if inp.bien_neuf and not is_achat_revente else ""
    adresse = payload.adresse_bien or (payload.marche or {}).get("adresse")
    phrase = f"Achat d'{bien}{neuf} de {inp.surface_m2:.0f} m²{_lieu(adresse)} pour {_eur(inp.prix_achat)}"
    if inp.montant_travaux > 0:
        phrase += f", plus {_eur(inp.montant_travaux)} de travaux"
    cout_total, apport, montant_emprunte = _cout_apport_emprunt(resultat, is_achat_revente)
    if montant_emprunte > 0:
        taux = f"{inp.taux_credit_annuel * 100:.2f}".replace(".", ",")
        phrase += (
            f", financé à {montant_emprunte / cout_total * 100:.0f} % par un crédit sur {inp.duree_credit_annees} ans"
            f" à {taux} %"
        )
        if apport > 0:
            phrase += f" et un apport de {_eur(apport)}"
    else:
        phrase += ", financé sans crédit"
    if is_achat_revente:
        ar = resultat["achat_revente"]
        phrase += f", pour une revente à {_eur(ar['prix_revente'])} après {inp.duree_portage_mois} mois"
    elif inp.type_projet == TypeProjet.location_courte_duree:
        mois = saisonnalite.valeurs_mensuelles(inp)
        occupation, prix = saisonnalite.moyennes_annuelles([o for o, _ in mois], [p for _, p in mois])
        phrase += (
            f", en location courte durée à {_eur(prix)} la nuit en moyenne pour {occupation * 100:.0f} % d'occupation"
        )
    else:
        phrase += (
            f", loué {_eur(inp.loyer_mensuel_hors_charges)} par mois hors charges"
            + (" en meublé" if inp.regime_location.value == "meublee" else " vide")
        )
    return phrase + "."


def _bloc_tableau_de_bord(cell, icone: str, titre: str, niveau: str, lignes: list[tuple], largeur_cm: float) -> None:
    """Un bloc de la synthèse : icône et titre, puis 3 lignes libellé / valeur
    (valeur colorée si un sens est donné), filet de couleur selon le niveau."""
    filet, _fond = COULEURS_VERDICT[niveau]
    _set_cell_background(cell, FOND_TUILE_HEX)
    _bordures_cellule(cell, left=(filet, 30))
    _cell_marges(cell, haut=150, bas=170, gauche=260, droite=240)
    p_titre = cell.paragraphs[0]
    run = p_titre.add_run()
    run.add_picture(io.BytesIO(visuels.icone(icone, couleur="#" + filet)), height=Cm(0.55))
    run.font.position = Pt(-3)
    _texte(p_titre, "  ", 13, PRIMARY_COLOR)
    _texte(p_titre, titre, 13, PRIMARY_COLOR, gras=True)
    p_titre.paragraph_format.space_after = Pt(5)
    for libelle, valeur, *sens in lignes:
        p = cell.add_paragraph()
        _taquet_valeur(p, largeur_cm - 0.95)
        _texte(p, libelle, 10, GRIS_LIBELLE)
        couleur = TEXTE_FONCE if not sens or sens[0] is None else (VERT if sens[0] else ROUGE)
        _texte(p, "\t" + valeur, 11.5, couleur, gras=True)
        p.paragraph_format.space_before = Pt(3)


def _taquet_valeur(paragraphe, position_cm: float) -> None:
    paragraphe.paragraph_format.tab_stops.add_tab_stop(Cm(position_cm), WD_TAB_ALIGNMENT.RIGHT)


def _section_synthese(doc, payload, inp, resultat, is_achat_revente):
    """Tableau de bord : le projet en une phrase, les 3 repères, puis 4 blocs
    (le bien, la rentabilité ou l'opération, le financement, le long terme
    ou la marge), chacun avec son repère de couleur."""
    p_phrase = doc.add_paragraph()
    _texte(p_phrase, phrase_projet(payload, inp, resultat, is_achat_revente), 12.5, TEXTE_FONCE)
    p_phrase.paragraph_format.space_after = Pt(10)
    ecart = _ecart_au_marche(inp, payload.marche)
    endettement = _taux_endettement(payload, inp, resultat, is_achat_revente) if payload.profil is not None else None
    v = analyse.verdict_global(
        inp, resultat, ecart[0] if ecart else None, endettement, raison_prix="étude de marché non réalisée"
    )
    _bandeau_reperes(doc, v, inp, resultat, _pour_la_banque(payload))
    cout_total, apport, montant_emprunte = _cout_apport_emprunt(resultat, is_achat_revente)

    prix_m2 = f"{_eur(inp.prix_achat / inp.surface_m2)}/m²"
    if ecart:
        signe = "+" if ecart[0] > 0 else "−"
        prix_m2 += f" ({signe}{_pct(abs(ecart[0]), 0)} vs quartier)" if abs(ecart[0]) >= 0.005 else " (médiane)"
    bloc_bien = (
        "home",
        "Le bien",
        _niveau_ecart(ecart[0]) if ecart else "neutre",
        [("Prix d'achat", _eur(inp.prix_achat)), ("Prix au m²", prix_m2), ("Coût total de l'opération", _eur(cout_total))],
    )

    # Financement : taux d'endettement si le profil est renseigné, sinon part de l'apport.
    part_apport = apport / cout_total if cout_total else 0
    lignes_financement = [("Apport", f"{_eur(apport)} ({_pct(part_apport, 0)})")]
    if montant_emprunte > 0:
        credit = _eur(montant_emprunte)
        if not is_achat_revente:
            credit += f" · {inp.duree_credit_annees} ans à {_pct(inp.taux_credit_annuel, 2)}"
        lignes_financement.append(("Crédit", credit))
    else:
        lignes_financement.append(("Crédit", "Aucun (fonds propres)"))
    if payload.profil is not None:
        r = _taux_endettement(payload, inp, resultat, is_achat_revente)
        lignes_financement.append(("Taux d'endettement", _pct(r.taux_endettement), not r.depasse_seuil))
        niveau_financement = "rouge" if r.depasse_seuil else ("orange" if r.seuil_hcsf - r.taux_endettement < 0.03 else "vert")
    else:
        if montant_emprunte > 0 and not is_achat_revente:
            lignes_financement.append(("Mensualité", _eur(resultat["mensualite_credit_hors_assurance"]) + "/mois"))
        niveau_financement = "neutre" if montant_emprunte <= 0 else ("vert" if part_apport >= 0.10 else "orange")
    bloc_financement = ("account_balance", "Le financement", niveau_financement, lignes_financement)

    if is_achat_revente:
        ar = resultat["achat_revente"]
        part = ar["marge_nette"] / cout_total if cout_total else 0
        tri = ar.get("tri_annualise")
        bloc_2 = (
            "swap_horiz",
            "L'opération",
            "neutre",
            [
                ("Prix de revente", _eur(ar["prix_revente"])),
                ("Durée de portage", f"{inp.duree_portage_mois} mois"),
                ("Frais de portage", _eur(ar["frais_portage_total"])),
            ],
        )
        bloc_4 = (
            "show_chart",
            "La marge",
            "rouge" if part < 0 else ("orange" if part < 0.10 else "vert"),
            [
                ("Marge nette", _eur(ar["marge_nette"]), ar["marge_nette"] >= 0),
                (libelle_rentabilite_ar(ar["apport_reel"]), _pct(ar["rentabilite_operation_pct"])),
                ("TRI annualisé de l'apport", _pct(tri) if tri is not None else "n/a"),
            ],
        )
        blocs = [bloc_bien, bloc_2, bloc_financement, bloc_4]
    else:
        regime = resultat["meilleur_regime"]
        cf = resultat["cashflow_mensuel"]
        effort = resultat["effort_epargne_mensuel"]
        enrichissement = resultat["enrichissement_par_regime"][regime]
        couverture, _ = _couverture_loyer(resultat)
        bloc_2 = (
            "account_balance_wallet",
            "La rentabilité",
            "vert" if cf >= 0 else ("orange" if couverture >= 0.85 else "rouge"),
            [
                ("Cash-flow net / mois", _eur(cf), cf >= 0),
                ("Rendement brut", _pct(resultat["rendement_brut"])),
                ("Rendement net-net", _pct(resultat["rendement_net_net_par_regime"][regime])),
            ],
        )
        bloc_4 = (
            "show_chart",
            f"Sur {inp.duree_projection_annees} ans",
            "vert" if enrichissement > 0 else "rouge",
            [
                ("Enrichissement net", _eur(enrichissement), enrichissement > 0),
                ("Effort d'épargne / mois", _eur(effort) if effort > 0 else "Aucun"),
                ("Régime fiscal le plus favorable", libelle_regime(regime)),
            ],
        )
        blocs = [bloc_bien, bloc_2, bloc_financement, bloc_4]

    largeur_bloc = (LARGEUR_CONTENU_CM - 0.5) / 2
    for rang in range(2):
        table = doc.add_table(rows=1, cols=3)
        table.autofit = False
        table.alignment = WD_TABLE_ALIGNMENT.CENTER
        _supprimer_bordures(table)
        for j, largeur in enumerate((largeur_bloc, 0.5, largeur_bloc)):
            table.columns[j].width = Cm(largeur)
            table.rows[0].cells[j].width = Cm(largeur)
        for cell, (icone, titre, niveau, lignes) in zip(
            (table.rows[0].cells[0], table.rows[0].cells[2]), blocs[2 * rang : 2 * rang + 2]
        ):
            cell.vertical_alignment = WD_ALIGN_VERTICAL.TOP
            _bloc_tableau_de_bord(cell, icone, titre, niveau, lignes, largeur_bloc)
        _espace(doc, 9)


def _section_presentation(doc, payload, inp, resultat, is_achat_revente):
    cout_total = _cout_apport_emprunt(resultat, is_achat_revente)[0]
    _tuiles(
        doc,
        [
            ("Prix d'achat", _eur(inp.prix_achat), None),
            ("Prix au m²", _eur(inp.prix_achat / inp.surface_m2), None),
            ("Coût total de l'opération", _eur(cout_total), None),
        ],
    )
    lignes = []
    if payload.adresse_bien:
        lignes.append(("Adresse du bien", payload.adresse_bien))
    lignes += [
        ("Type de bien", inp.type_bien.value.capitalize()),
        ("Surface", f"{inp.surface_m2:.0f} m²"),
    ]
    if not is_achat_revente:
        lignes.append(("Bien neuf / VEFA", "Oui" if inp.bien_neuf else "Non"))
    lignes += [
        ("Prix d'achat", _eur(inp.prix_achat)),
        ("Frais de notaire", _eur(inp.frais_notaire)),
        ("Montant des travaux", _eur(inp.montant_travaux)),
    ]
    if inp.montant_mobilier:
        lignes.append(("Montant du mobilier", _eur(inp.montant_mobilier)))
    frais_bancaires = _frais_bancaires(resultat, is_achat_revente)
    if frais_bancaires > 0:
        lignes.append(("Frais bancaires (garantie, dossier, courtage)", _eur(frais_bancaires)))
    cout_total, _apport, _emprunt = _cout_apport_emprunt(resultat, is_achat_revente)
    lignes.append(("Coût total de l'opération", _eur(cout_total), "total"))
    if not is_achat_revente:
        lignes.append(
            ("Régime locatif", "Location meublée" if inp.regime_location.value == "meublee" else "Location nue")
        )
        if inp.type_projet == TypeProjet.location_courte_duree:
            lignes.append(("Meublé de tourisme classé", "Oui" if inp.meuble_tourisme_classe else "Non"))

    composition = [
        ("Prix d'achat", inp.prix_achat),
        ("Frais de notaire", inp.frais_notaire),
        ("Travaux", inp.montant_travaux),
    ]
    if inp.montant_mobilier:
        composition.append(("Mobilier", inp.montant_mobilier))
    if frais_bancaires > 0:
        composition.append(("Frais bancaires", frais_bancaires))
    image = charts.chart_donut(
        [v for _, v in composition], [l for l, _ in composition], "Composition du coût d'acquisition"
    )
    _ajouter_table_et_graphique(doc, lignes, image)


FIABILITE_LIBELLES = {"elevee": "élevée", "moyenne": "moyenne", "faible": "faible"}


def _ecart_marche(prix_m2: float, mediane: float) -> tuple[str, bool | None]:
    """Écart à la médiane (texte signé) et sens pour l'acheteur."""
    ecart = prix_m2 / mediane - 1
    favorable = True if ecart <= 0.03 else (False if ecart >= 0.10 else None)
    if round(ecart * 100) == 0:
        return "0 %", favorable
    return ("+" if ecart > 0 else "") + _pct(ecart, 0), favorable


def _section_marche(doc, inp, marche: dict, is_achat_revente: bool):
    comp = marche["comparables"]
    mediane = comp["prix_m2_moyen"]
    prix_projet_m2 = inp.prix_achat / inp.surface_m2
    ecart_txt, ecart_favorable = _ecart_marche(prix_projet_m2, mediane)
    tuiles = [
        ("Prix d'achat du projet", f"{_eur(prix_projet_m2)}/m²", None),
        (f"Médiane de {comp['nb_transactions']} ventes", f"{_eur(mediane)}/m²", None),
        ("Écart au marché", ecart_txt, ecart_favorable),
    ]
    loyer = marche.get("loyer") or {}
    if is_achat_revente and inp.prix_revente_vise:
        revente_m2 = inp.prix_revente_vise / inp.surface_m2
        # Revendre au-dessus de la fourchette haute est un pari : signalé en rouge.
        tuiles.append(("Revente visée", f"{_eur(revente_m2)}/m²", revente_m2 <= comp["prix_m2_haut"]))
    elif inp.type_projet == TypeProjet.location_longue_duree and loyer.get("loyer_m2_moyen"):
        loyer_projet_m2 = inp.loyer_mensuel_hors_charges / inp.surface_m2
        tuiles.append(
            (
                "Loyer projet / marché",
                f"{loyer_projet_m2:.1f} / {loyer['loyer_m2_moyen']:.1f} €/m²".replace(".", ","),
                loyer_projet_m2 <= loyer["loyer_m2_moyen"] * 1.05,
            )
        )
    else:
        tuiles.append(("Fiabilité de l'échantillon", FIABILITE_LIBELLES[comp["fiabilite"]].capitalize(), comp["fiabilite"] != "faible"))
    _tuiles(doc, tuiles)

    largeur_table, largeur_image = 13.2, 11.5
    conteneur = doc.add_table(rows=1, cols=2)
    conteneur.autofit = False
    conteneur.alignment = WD_TABLE_ALIGNMENT.CENTER
    _supprimer_bordures(conteneur)
    conteneur.columns[0].width = Cm(largeur_table)
    conteneur.columns[1].width = Cm(largeur_image)
    cell_table, cell_image = conteneur.rows[0].cells
    cell_table.width = Cm(largeur_table)
    cell_image.width = Cm(largeur_image)

    # Les ventes les plus proches du bien parmi les plus récentes.
    ventes = sorted(comp["ventes"], key=lambda v: v["distance_m"])[:10]
    _ajouter_table_colonnes(
        cell_table,
        ["Date", "Adresse", "Surface", "Prix", "Prix / m²", "Distance"],
        [
            [
                v["date"],
                v["adresse"].split(",")[0].title(),
                f"{v['surface']} m²",
                _eur(v["prix"]),
                _eur(v["prix_m2"]),
                f"{v['distance_m']} m",
            ]
            for v in ventes
        ],
        [1.9, 4.6, 1.5, 2.1, 1.8, 1.3],
        colonnes_texte=2,
    )
    image = charts.chart_marche(
        [v["prix_m2"] for v in comp["ventes"]],
        comp["prix_m2_bas"],
        mediane,
        comp["prix_m2_haut"],
        prix_projet_m2,
        inp.prix_revente_vise / inp.surface_m2 if is_achat_revente and inp.prix_revente_vise else None,
    )
    p_image = cell_image.paragraphs[0]
    p_image.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_image.paragraph_format.space_after = Pt(0)
    hauteur_max = HAUTEUR_BLOC_CM - HAUTEUR_NOTE_CM
    p_image.add_run().add_picture(io.BytesIO(image), width=Cm(min(largeur_image - 0.5, hauteur_max * _proportions_png(image))))

    rayon = comp["rayon_utilise"]
    rayon_txt = f"{rayon / 1000:g} km".replace(".", ",") if rayon >= 1000 else f"{rayon} m"
    surfaces = (
        f"surfaces de {comp['surface_min']} à {comp['surface_max']} m²" if comp.get("surface_min") else "toutes surfaces"
    )
    phrases = [
        f"{comp['nb_transactions']} ventes réelles "
        + ("de logements neufs (VEFA)" if comp.get("neuf") else "dans l'ancien")
        + f" entre {comp['periode_debut']} et {comp['periode_fin']}, dans un rayon de {rayon_txt} autour du bien, "
        f"{surfaces} (fiabilité {FIABILITE_LIBELLES[comp['fiabilite']]}). Fourchette de 80 % des ventes : "
        f"{_eur(comp['prix_m2_bas'])} à {_eur(comp['prix_m2_haut'])}/m²."
    ]
    commune = marche.get("commune_indicateurs") or {}
    if commune.get("rendement_brut"):
        loyer_commune = f"{commune['loyer_m2']:.1f}".replace(".", ",")
        phrases.append(
            f"Commune : prix médian {_eur(commune['prix_m2'])}/m², loyer d'annonce {loyer_commune} €/m², "
            f"rentabilité brute moyenne {_pct(commune['rendement_brut'])}."
        )
    phrases.append("Sources : DVF (DGFiP, data.gouv.fr), carte des loyers (ANIL). Ventes en bloc exclues.")
    _ajouter_note(doc, " ".join(phrases))


ECART_PHOTOS_CM = 0.4


def _disposition_photos(nb: int, largeur: float, hauteur: float) -> tuple[str, float, float]:
    """(disposition, largeur de la grande photo, largeur des petites) : une
    photo seule ; deux côte à côte ; trois en « vitrine » (une grande à gauche,
    deux empilées à droite) ; quatre en 2 × 2 ; cinq ou six en 2 × 3."""
    f, g = photos_dossier.FORMAT_PHOTO, ECART_PHOTOS_CM
    if nb == 3:
        # Grande photo de hauteur h, petites de hauteur (h - g) / 2, côte à côte :
        # f·h + g + f·(h - g)/2 ≤ largeur.
        h = min(hauteur, (largeur - g + f * g / 2) / (1.5 * f))
        return "vitrine", f * h, f * (h - g) / 2
    lignes, colonnes = {1: (1, 1), 2: (1, 2), 4: (2, 2)}.get(nb, (2, 3))
    w = min((largeur - (colonnes - 1) * g) / colonnes, (hauteur - (lignes - 1) * g) / lignes * f)
    return f"{lignes}x{colonnes}", w, w


def _cellule_photo(cell, image: bytes, largeur_cm: float, espace_apres_cm: float = 0) -> None:
    _cell_marges(cell, haut=0, bas=0, gauche=0, droite=0)
    p = cell.paragraphs[0]
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_before = Pt(0)
    p.paragraph_format.space_after = Cm(espace_apres_cm)
    p.add_run().add_picture(io.BytesIO(image), width=Cm(largeur_cm))


def _section_photos(doc, photos: list[bytes]):
    """Photos importées par l'utilisateur, ou emplacements d'attente à
    remplacer dans Word (clic droit > Modifier l'image)."""
    images = photos[: photos_dossier.NB_PHOTOS_MAX] or [photos_dossier.emplacement_photo()] * 3
    hauteur = HAUTEUR_UTILE_CM - HAUTEUR_ENTETE_CHAPITRE_CM - MARGE_SECURITE_CM
    largeur = LARGEUR_CONTENU_CM - 0.2
    disposition, grande, petite = _disposition_photos(len(images), largeur, hauteur)
    g = ECART_PHOTOS_CM
    if disposition == "vitrine":
        table = doc.add_table(rows=2, cols=2)
        largeurs = (grande + g, petite)
        cellule_grande = table.cell(0, 0).merge(table.cell(1, 0))
        cellule_grande.vertical_alignment = WD_ALIGN_VERTICAL.TOP
        _cellule_photo(cellule_grande, images[0], grande)
        cellule_grande.paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.LEFT
        _cellule_photo(table.cell(0, 1), images[1], petite, espace_apres_cm=g)
        _cellule_photo(table.cell(1, 1), images[2], petite)
    else:
        lignes, colonnes = (int(n) for n in disposition.split("x"))
        table = doc.add_table(rows=lignes, cols=colonnes)
        largeurs = (grande + g,) * colonnes  # photos resserrées, tableau centré
        for i, image in enumerate(images):
            ligne, colonne = divmod(i, colonnes)
            _cellule_photo(table.cell(ligne, colonne), image, grande, espace_apres_cm=g if ligne < lignes - 1 else 0)
    table.autofit = False
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    _supprimer_bordures(table)
    for j, largeur_colonne in enumerate(largeurs):
        table.columns[j].width = Cm(largeur_colonne)
        for cell in table.columns[j].cells:
            cell.width = Cm(largeur_colonne)


def _section_carte(doc, marche: dict, carte_communes: bool):
    """Les cartes de l'onglet Marché : ventes comparables autour du bien et,
    en location longue durée, rentabilité brute des communes du département."""
    from . import carte_export
    from .donnees_marche import periode_donnees

    comp = marche["comparables"]
    hauteur = HAUTEUR_UTILE_CM - HAUTEUR_ENTETE_CHAPITRE_CM - HAUTEUR_A_RETENIR_CM - HAUTEUR_NOTE_CM - MARGE_SECURITE_CM
    geojson = marche["communes_geojson"] if carte_communes else None
    if geojson:
        images = [
            carte_export.carte_ventes(marche["lat"], marche["lon"], comp),
            carte_export.carte_rentabilite(geojson, marche["lat"], marche["lon"], marche.get("code_insee")),
        ]
    else:
        images = [carte_export.carte_ventes(marche["lat"], marche["lon"], comp, taille_cm=(20.0, 10.6))]
    largeur_colonne = LARGEUR_CONTENU_CM / len(images)
    table = doc.add_table(rows=1, cols=len(images))
    table.autofit = False
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    _supprimer_bordures(table)
    for j, (cell, image) in enumerate(zip(table.rows[0].cells, images)):
        table.columns[j].width = Cm(largeur_colonne)
        cell.width = Cm(largeur_colonne)
        cell.vertical_alignment = WD_ALIGN_VERTICAL.TOP
        _cellule_photo(cell, image, min(largeur_colonne - 0.3, hauteur * _proportions_png(image)))

    phrases = [
        f"Couleur des ventes : écart de leur prix au m² à la médiane du secteur ({_eur(comp['prix_m2_moyen'])}/m²)."
    ]
    if geojson:
        periode = periode_donnees()
        phrases.append(
            "Rentabilité brute d'une commune = loyer d'annonce au m² × 12 ÷ prix médian au m² des ventes dans l'ancien"
            + (f" ({periode})" if periode else "")
            + "."
        )
    phrases.append(
        "Sources : DVF (DGFiP), carte des loyers (ANIL), contours geo.api.gouv.fr, fond de carte © IGN."
        if geojson
        else "Sources : DVF (DGFiP), fond de carte © IGN."
    )
    _ajouter_note(doc, " ".join(phrases))


def _case_a_cocher(paragraphe) -> None:
    """Case à cocher Word (contrôle de contenu) : se coche d'un clic dans
    Word, s'imprime comme une case vide."""
    police = '<w:rFonts w:ascii="MS Gothic" w:eastAsia="MS Gothic" w:hAnsi="MS Gothic"/><w:color w:val="1B3358"/><w:sz w:val="22"/>'
    paragraphe._p.append(
        parse_xml(
            f'<w:sdt xmlns:w="{NS_W}" xmlns:w14="{NS_W14}"><w:sdtPr><w:rPr>{police}</w:rPr>'
            '<w14:checkbox><w14:checked w14:val="0"/>'
            '<w14:checkedState w14:val="2612" w14:font="MS Gothic"/>'
            '<w14:uncheckedState w14:val="2610" w14:font="MS Gothic"/></w14:checkbox></w:sdtPr>'
            f'<w:sdtContent><w:r><w:rPr>{police}</w:rPr><w:t>☐</w:t></w:r></w:sdtContent></w:sdt>'
        )
    )


def _pieces_a_fournir(inp) -> list[tuple[str, list[tuple[str, str]]]]:
    """(rubrique, [(pièce, précision)]) : pièces demandées par la banque pour
    ouvrir l'étude de financement."""
    if inp.montant_travaux > 0:
        precision_travaux = f"Travaux prévus au plan de financement : {_eur(inp.montant_travaux)}"
    else:
        precision_travaux = "Si des travaux sont prévus et que les devis sont disponibles"
    return [
        (
            "Identité et domicile",
            [
                ("Pièce d'identité", "Carte d'identité ou passeport en cours de validité"),
                ("Justificatif de domicile", "Facture d'énergie, quittance de loyer ou avis de taxe foncière récent"),
            ],
        ),
        (
            "Revenus et situation professionnelle",
            [
                ("3 derniers bulletins de salaire", "Ainsi que celui de décembre de l'année précédente (cumul annuel)"),
                ("Contrat de travail", "Ou, à défaut, attestation de l'employeur"),
                ("2 derniers avis d'imposition", "Toutes les pages"),
            ],
        ),
        ("Comptes bancaires", [("3 derniers relevés de compte", "Tous les comptes courants")]),
        (
            "Le bien",
            [
                ("Compromis de vente", "Si déjà signé"),
                ("DPE (diagnostic de performance énergétique)", "Fourni par le vendeur ou l'agence"),
                ("Devis des travaux", precision_travaux),
            ],
        ),
    ]


def _section_annexes(doc, inp):
    taille, _, marge = STYLE_DENSITE["compact"]
    largeurs = (1.1, 10.0, LARGEUR_CONTENU_CM - 11.1)
    table = doc.add_table(rows=0, cols=3)
    table.style = "Normal Table"
    table.autofit = False
    for rubrique, pieces in _pieces_a_fournir(inp):
        ligne = table.add_row()
        cellule = ligne.cells[0].merge(ligne.cells[2])
        _set_cell_background(cellule, FOND_TUILE_HEX)
        _cell_marges(cellule, haut=70, bas=70, gauche=120, droite=90)
        _texte(cellule.paragraphs[0], rubrique.upper(), 8, PRIMARY_COLOR, gras=True)
        for piece, precision in pieces:
            ligne = table.add_row()
            case, cellule_piece, cellule_precision = ligne.cells
            for cell in ligne.cells:
                cell.vertical_alignment = WD_ALIGN_VERTICAL.CENTER
                _bordure_bas_cellule(cell)
                _cell_marges(cell, haut=marge, bas=marge, gauche=120, droite=90)
            for cell in ligne.cells:
                cell.paragraphs[0].paragraph_format.space_after = Pt(0)
                cell.paragraphs[0].paragraph_format.line_spacing = 1.0
            case.paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.CENTER
            _case_a_cocher(case.paragraphs[0])
            _texte(cellule_piece.paragraphs[0], piece, taille, TEXTE_FONCE, gras=True)
            _texte(cellule_precision.paragraphs[0], precision, taille, GRIS_LIBELLE)
    for j, largeur in enumerate(largeurs):
        table.columns[j].width = Cm(largeur)
    for ligne in table.rows:
        cellules = [_Cell(tc, table) for tc in ligne._tr.tc_lst]
        if len(cellules) == 1:  # ligne de rubrique fusionnée
            cellules[0].width = Cm(sum(largeurs))
        else:
            for cell, largeur in zip(cellules, largeurs):
                cell.width = Cm(largeur)
    _ajouter_note(
        doc,
        "Pièces à fournir pour chaque emprunteur. Les cases se cochent d'un clic dans Word. La banque peut demander "
        "des justificatifs complémentaires selon la situation (épargne constituant l'apport, crédits en cours, "
        "revenus locatifs existants…).",
    )


def _hauteur_ligne(row, hauteur_cm: float) -> None:
    """Hauteur minimale de ligne : de la place pour écrire à la main ou
    saisir dans Word."""
    tr_pr = row._tr.get_or_add_trPr()
    hauteur = OxmlElement("w:trHeight")
    hauteur.set(qn("w:val"), str(round(hauteur_cm / 2.54 * 1440)))
    hauteur.set(qn("w:hRule"), "atLeast")
    tr_pr.append(hauteur)


def _lignes_tableau_patrimoine(saisies) -> list[tuple[str, str, str, str, str]]:
    """(nature, détail, valeur, reste dû, style) de chaque ligne : les lignes
    saisies dans le simulateur avec total et patrimoine net, sinon toutes
    les lignes vides à compléter dans Word. Style : "", "total" ou "net"."""
    if not saisies:
        lignes = [(nature, "", "€", "€" if credit else "—", "") for _, nature, credit in LIGNES_PATRIMOINE]
        return lignes + [("Total", "", "€", "€", "total")]
    credit_par_nature = {nature: credit for _, nature, credit in LIGNES_PATRIMOINE}
    lignes = []
    for ligne in saisies:
        reste_du = _eur(ligne.reste_du) if ligne.reste_du else ("—" if not credit_par_nature.get(ligne.nature) else "")
        lignes.append((ligne.nature, ligne.detail or "", _eur(ligne.valeur) if ligne.valeur else "", reste_du, ""))
    valeur = sum(ligne.valeur or 0 for ligne in saisies)
    reste_du = sum(ligne.reste_du or 0 for ligne in saisies)
    lignes.append(("Total", "", _eur(valeur), _eur(reste_du), "total"))
    lignes.append(("Patrimoine net (valeur − reste dû)", "", _eur(valeur - reste_du), "", "net"))
    return lignes


def _tableau_patrimoine(container, largeur_cm: float, saisies=None) -> None:
    """Patrimoine du foyer : lignes saisies dans le simulateur, ou cellules
    vides à compléter dans Word."""
    largeurs = [largeur_cm * r for r in (0.42, 0.28, 0.15, 0.15)]
    table = container.add_table(rows=0, cols=4)
    table.style = "Normal Table"
    table.autofit = False
    entetes = ["Nature", "Établissement / détail", "Valeur", "Reste dû"]
    vide = not saisies
    for i, valeurs in enumerate([None] + _lignes_tableau_patrimoine(saisies)):
        row = table.add_row()
        _hauteur_ligne(row, 0.62 if i == 0 or not vide else 0.74)
        style = valeurs[4] if valeurs else ""
        for j, cell in enumerate(row.cells):
            cell.width = Cm(largeurs[j])
            cell.vertical_alignment = WD_ALIGN_VERTICAL.CENTER
            _cell_marges(cell, haut=30, bas=30, gauche=90, droite=90)
            p = cell.paragraphs[0]
            p.alignment = WD_ALIGN_PARAGRAPH.LEFT if j < 2 else WD_ALIGN_PARAGRAPH.RIGHT
            _texte(p, "", 9)  # cellule vide : même hauteur de ligne que les autres
            if valeurs is None:
                _texte(p, entetes[j], 8.5, BLANC, gras=True)
                _set_cell_background(cell, MARQUE_HEX)
                continue
            texte = valeurs[j]
            if j == 0:
                _texte(p, texte, 9, TEXTE_FONCE if style else GRIS_LIBELLE, gras=bool(style))
            elif texte in ("€", "—"):
                if texte == "—":
                    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
                _texte(p, texte, 9, GRIS_COLOR)
            elif texte:
                couleur = PRIMARY_COLOR if style == "net" else TEXTE_FONCE
                _texte(p, texte, 9.5 if style else 9, couleur, gras=j >= 2)
            if style:
                _bordure_bas_cellule(cell, color=MARQUE_HEX, size=8)
                _set_cell_background(cell, FOND_TUILE_HEX)
            else:
                _bordure_bas_cellule(cell)
                if i % 2 == 0:
                    _set_cell_background(cell, ZEBRA_HEX)
    for j, largeur in enumerate(largeurs):
        table.columns[j].width = Cm(largeur)


def _section_profil(doc, payload):
    p = payload.profil
    saisies = payload.patrimoine or []
    tuiles = [
        ("Revenus mensuels retenus", _eur(p.revenus_nets_mensuels_foyer + p.autres_revenus_mensuels), None),
        ("Crédits en cours / mois", _eur(p.mensualites_credits_existants), None),
    ]
    if saisies:
        net = sum(ligne.valeur or 0 for ligne in saisies) - sum(ligne.reste_du or 0 for ligne in saisies)
        tuiles.append(("Patrimoine net", _eur(net), None))
    _tuiles(doc, tuiles)
    lignes = []
    if payload.nom_emprunteur:
        lignes.append(("Emprunteur", payload.nom_emprunteur))
    lignes += [
        ("Revenus nets mensuels du foyer", _eur(p.revenus_nets_mensuels_foyer)),
        ("Autres revenus mensuels", _eur(p.autres_revenus_mensuels)),
        ("Mensualités de crédits existants", _eur(p.mensualites_credits_existants)),
        ("Total des revenus mensuels retenus", _eur(p.revenus_nets_mensuels_foyer + p.autres_revenus_mensuels), "total"),
    ]
    # Revenus à gauche, patrimoine du foyer (à compléter) à droite.
    largeur_gauche, ecart = 11.0, 0.8
    largeur_droite = LARGEUR_CONTENU_CM - largeur_gauche - ecart
    conteneur = doc.add_table(rows=1, cols=3)
    conteneur.autofit = False
    _supprimer_bordures(conteneur)
    for j, (cell, largeur) in enumerate(zip(conteneur.rows[0].cells, (largeur_gauche, ecart, largeur_droite))):
        conteneur.columns[j].width = Cm(largeur)
        cell.width = Cm(largeur)
        cell.vertical_alignment = WD_ALIGN_VERTICAL.TOP
        _cell_marges(cell, haut=0, bas=0, gauche=0, droite=0)
    cell_revenus, _, cell_patrimoine = conteneur.rows[0].cells
    _texte(cell_revenus.paragraphs[0], "Revenus et engagements", 11, PRIMARY_COLOR, gras=True)
    cell_revenus.paragraphs[0].paragraph_format.space_after = Pt(6)
    _ajouter_table_kv(cell_revenus, lignes, largeur_cm=largeur_gauche)
    titre = "Patrimoine du foyer" if saisies else "Patrimoine du foyer (à compléter)"
    _texte(cell_patrimoine.paragraphs[0], titre, 11, PRIMARY_COLOR, gras=True)
    cell_patrimoine.paragraphs[0].paragraph_format.space_after = Pt(6)
    _tableau_patrimoine(cell_patrimoine, largeur_droite, saisies)
    note = cell_patrimoine.add_paragraph()
    _texte(
        note,
        ("Déclaré par l'emprunteur : valeur estimée" if saisies else "Valeur estimée")
        + " à ce jour ; pour les biens financés à crédit, capital restant dû. "
        "Le patrimoine rassure la banque sur la capacité à faire face à un imprévu.",
        8.5,
        GRIS_COLOR,
        italique=True,
    )
    note.paragraph_format.space_before = Pt(5)


def _lignes_credit(inp, resultat, montant_emprunte, is_achat_revente) -> list[tuple[str, str]]:
    lignes = [
        ("Montant emprunté", _eur(montant_emprunte)),
        ("Taux du crédit", _pct(inp.taux_credit_annuel, 2)),
        ("Durée du crédit", f"{inp.duree_credit_annees} ans"),
        ("Frais bancaires (garantie, dossier, courtage)", _eur(_frais_bancaires(resultat, is_achat_revente))),
    ]
    if is_achat_revente:
        lignes.append(("Durée de portage retenue pour les intérêts", f"{inp.duree_portage_mois} mois"))
        return lignes
    lignes.append(("Taux d'assurance emprunteur", _pct(inp.taux_assurance_emprunteur, 2)))
    if inp.differe_type.value != "aucun":
        libelle = LABELS_DIFFERE.get(inp.differe_type.value, inp.differe_type.value)
        lignes.append(("Différé de crédit", f"{libelle} — {inp.differe_duree_mois} mois"))
        lignes.append(
            ("Mensualité 1ère année (hors assurance)", _eur(resultat.get("mensualite_annee1_hors_assurance", 0)) + "/mois")
        )
        lignes.append(
            ("Mensualité en régime de croisière (hors assurance)", _eur(resultat.get("mensualite_credit_hors_assurance", 0)) + "/mois")
        )
    else:
        lignes.append(
            ("Mensualité du crédit (hors assurance)", _eur(resultat.get("mensualite_credit_hors_assurance", 0)) + "/mois")
        )
    return lignes


def _section_financement(doc, inp, resultat, is_achat_revente):
    cout_total, apport, montant_emprunte = _cout_apport_emprunt(resultat, is_achat_revente)
    if montant_emprunte <= 0:
        tuiles = [("Apport personnel", _eur(apport), None), ("Financement", "100 % fonds propres", None)]
    elif is_achat_revente:
        ar = resultat["achat_revente"]
        tuiles = [
            ("Apport personnel", _eur(apport), None),
            ("Montant emprunté", _eur(montant_emprunte), None),
            ("Intérêts de portage", _eur(ar["frais_portage_interets"]), None),
        ]
    else:
        tuiles = [
            ("Apport personnel", _eur(apport), None),
            ("Montant emprunté", _eur(montant_emprunte), None),
            ("Mensualité du crédit", _eur(resultat["mensualite_credit_hors_assurance"]) + "/mois", None),
        ]
    _tuiles(doc, tuiles)
    lignes = [
        ("Coût total d'acquisition", _eur(cout_total), "total"),
        ("Apport personnel", _eur(apport)),
    ]
    if montant_emprunte > 0:
        lignes += _lignes_credit(inp, resultat, montant_emprunte, is_achat_revente)
    else:
        lignes.append(("Mode de financement", "100 % fonds propres (sans crédit)"))
    image = charts.chart_donut(
        [apport, montant_emprunte], ["Apport personnel", "Montant emprunté"], "Apport et crédit", total_label="Coût total"
    )
    _ajouter_table_et_graphique(doc, lignes, image)


def _section_charges(doc, inp, annee1, is_meublee, is_lcd):
    loyers_bruts_an1 = annee1["loyers_bruts"]
    frais_gestion = loyers_bruts_an1 * inp.frais_gestion_pct_loyers
    cf_avant_impot = annee1["cashflow_avant_impot"]
    _tuiles(
        doc,
        [
            ("Recettes locatives (année 1)", _eur(loyers_bruts_an1), None),
            ("Charges hors crédit (année 1)", _eur(annee1["charges_hors_credit"]), None),
            ("Cash-flow avant impôt (année 1)", _eur(cf_avant_impot), cf_avant_impot >= 0),
        ],
    )

    if is_lcd:
        lignes_recettes = [
            ("Prix moyen par nuitée", _eur(inp.prix_nuitee)),
            ("Taux d'occupation retenu", _pct(inp.taux_occupation_pct) + f" ({365 * inp.taux_occupation_pct:.0f} nuits)"),
        ]
    else:
        lignes_recettes = [
            ("Loyer mensuel hors charges", _eur(inp.loyer_mensuel_hors_charges)),
            ("Vacance locative retenue", _pct(inp.vacance_locative_pct)),
        ]
    lignes_recettes.append(("Recettes locatives brutes (année 1)", _eur(loyers_bruts_an1), "total"))

    charges_items: list[tuple[str, float]] = [
        ("Copropriété", inp.charges_copropriete_annuelles),
        ("Taxe foncière", inp.taxe_fonciere_annuelle),
        ("Assurance PNO", inp.assurance_pno_annuelle),
        ("Entretien", inp.entretien_annuel),
        ("Gestion locative", frais_gestion),
    ]
    gli = loyers_bruts_an1 * inp.gli_pct_loyers if not is_lcd else 0.0
    lignes = lignes_recettes + [
        ("Charges de copropriété", _eur(inp.charges_copropriete_annuelles)),
        ("Taxe foncière", _eur(inp.taxe_fonciere_annuelle)),
        ("Assurance PNO", _eur(inp.assurance_pno_annuelle)),
        ("Entretien annuel", _eur(inp.entretien_annuel)),
        ("Frais de gestion locative", _eur(frais_gestion) + f" ({_pct(inp.frais_gestion_pct_loyers)})"),
    ]
    if gli > 0:
        charges_items.append(("Loyers impayés (GLI)", gli))
        lignes.append(("Assurance loyers impayés (GLI)", _eur(gli) + f" ({_pct(inp.gli_pct_loyers)})"))
    if is_lcd:
        frais_plateforme = loyers_bruts_an1 * inp.frais_plateforme_pct
        charges_items.append(("Commission plateforme", frais_plateforme))
        charges_items.append(("Ménage", inp.frais_menage_annuel))
        lignes.append(
            ("Commission plateforme (Airbnb/Booking...)", _eur(frais_plateforme) + f" ({_pct(inp.frais_plateforme_pct)})")
        )
        lignes.append(("Frais de ménage annuels", _eur(inp.frais_menage_annuel)))
    if is_meublee:
        charges_items.append(("Comptable", inp.frais_comptable_annuel))
        lignes.append(("Frais de comptabilité annuels", _eur(inp.frais_comptable_annuel)))
        if inp.cfe_annuelle > 0:
            lignes.append(("CFE (due à partir de la 2e année)", _eur(inp.cfe_annuelle)))
    lignes.append(("Total des charges hors crédit (année 1)", _eur(annee1["charges_hors_credit"]), "total"))
    lignes.append(("Hausse annuelle des charges retenue", _pct(inp.taux_revalorisation_charges_annuel)))

    # Le graphique inclut en plus le crédit (contrairement au tableau, exprimé
    # hors crédit) pour donner une vision complète de la rentabilité du projet.
    charges_graphique = charges_items + [("Crédit (annuité)", annee1["mensualite_totale_credit"])]
    charges_graphique_non_nulles = [(l, v) for l, v in charges_graphique if v > 0]
    image = charts.chart_recettes_charges(
        loyers_bruts_an1, charges_graphique_non_nulles, "Ce qui entre et ce qui sort (crédit inclus)"
    )
    _ajouter_table_et_graphique(doc, lignes, image, largeur_table_cm=14.5, largeur_image_cm=11.6)


def _ajouter_note(doc, texte: str) -> None:
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(6)
    run = p.add_run(texte)
    run.italic = True
    run.font.size = Pt(9)
    run.font.color.rgb = GRIS_COLOR


def _section_loyer_mensuel(doc, resultat):
    etapes = analyse.etapes_loyer_mensuel(resultat)
    cashflow = sum(v for _, v in etapes)
    effort = resultat["effort_epargne_mensuel"]
    _tuiles(
        doc,
        [
            ("Loyers encaissés / mois", _eur(etapes[0][1]), None),
            ("Cash-flow net / mois", _eur(cashflow), cashflow >= 0),
            ("Effort d'épargne / mois", _eur(effort) if effort > 0 else "Aucun", effort <= 0),
        ],
    )
    lignes = [(libelle, ("+" if round(v) > 0 else "") + _eur(v)) for libelle, v in etapes]
    lignes.append(("Cash-flow net mensuel", _eur(cashflow), "total"))
    _ajouter_table_et_graphique(doc, lignes, _image_cascade_loyer(resultat), hauteur_max_cm=HAUTEUR_BLOC_CM - HAUTEUR_NOTE_CM)
    _ajouter_note(
        doc,
        f"Moyenne mensuelle de l'année {resultat.get('annee_reference', 1)}, première année courante (hors différé "
        f"de crédit et hors déductions ponctuelles de l'année 1), régime {libelle_regime(resultat['meilleur_regime'])}. "
        "Les charges comprennent copropriété, taxe foncière, assurances, entretien et frais de gestion.",
    )


def _ajouter_table_colonnes(
    container, entetes: list[str], lignes: list[list[str]], largeurs_cm: list[float], colonnes_texte: int = 1
) -> None:
    """Tableau à plusieurs colonnes (en-tête, zébrage, montants négatifs en
    rouge), serré pour tenir sur la page. Les `colonnes_texte` premières
    colonnes sont alignées à gauche, les suivantes (montants) à droite."""
    taille, _, marge = STYLE_DENSITE["serre"]
    table = container.add_table(rows=0, cols=len(entetes))
    table.style = "Normal Table"
    table.autofit = False
    for i, valeurs in enumerate([entetes] + lignes):
        row = table.add_row()
        for j, (cell, valeur) in enumerate(zip(row.cells, valeurs)):
            cell.width = Cm(largeurs_cm[j])
            p = cell.paragraphs[0]
            p.alignment = WD_ALIGN_PARAGRAPH.LEFT if j < colonnes_texte else WD_ALIGN_PARAGRAPH.RIGHT
            if i == 0:
                _texte(p, valeur, taille - 0.5, BLANC, gras=True)
                _set_cell_background(cell, MARQUE_HEX)
            else:
                negatif = valeur.lstrip().startswith(("-", "−"))
                _texte(p, valeur, taille, ROUGE if negatif else (GRIS_LIBELLE if j == 0 else TEXTE_FONCE), gras=j > 0)
                _bordure_bas_cellule(cell)
                if i % 2 == 0:
                    _set_cell_background(cell, ZEBRA_HEX)
            _cell_marges(cell, haut=marge, bas=marge, gauche=90, droite=90)
    for j, largeur in enumerate(largeurs_cm):
        table.columns[j].width = Cm(largeur)


def _section_saisonnalite(doc, inp, resultat):
    saison = saisonnalite.analyse_mensuelle(inp, resultat)
    tresorerie = saison["tresorerie_securite"]
    deficitaires = saison["mois_deficitaires"]
    _tuiles(
        doc,
        [
            ("Trésorerie de sécurité", _eur(tresorerie), tresorerie <= 0),
            ("Mois déficitaires", f"{deficitaires} / 12", True if deficitaires == 0 else (None if deficitaires < 6 else False)),
            ("Meilleur / pire mois", f"{saison['meilleur_mois']} / {saison['pire_mois']}", None),
            ("Part des 3 meilleurs mois", _pct(saison["part_haute_saison"], 0), None),
        ],
    )
    largeur_table, largeur_image = 13.2, 11.5
    conteneur = doc.add_table(rows=1, cols=2)
    conteneur.autofit = False
    conteneur.alignment = WD_TABLE_ALIGNMENT.CENTER
    _supprimer_bordures(conteneur)
    conteneur.columns[0].width = Cm(largeur_table)
    conteneur.columns[1].width = Cm(largeur_image)
    cell_table, cell_image = conteneur.rows[0].cells
    cell_table.width = Cm(largeur_table)
    cell_image.width = Cm(largeur_image)
    lignes = [
        [
            l["mois"],
            _pct(l["occupation"], 0),
            _eur(l["prix_nuitee"]),
            _eur(l["recettes"]),
            _eur(l["depenses"]),
            ("+" if l["cashflow"] >= 0 else "") + _eur(l["cashflow"]),
        ]
        for l in saison["lignes"]
    ]
    total_cf = sum(l["cashflow"] for l in saison["lignes"])
    lignes.append(
        [
            "Année",
            _pct(sum(l["nuits"] for l in saison["lignes"]) / 365, 0),
            "",
            _eur(sum(l["recettes"] for l in saison["lignes"])),
            _eur(sum(l["depenses"] for l in saison["lignes"])),
            ("+" if total_cf >= 0 else "") + _eur(total_cf),
        ]
    )
    _ajouter_table_colonnes(
        cell_table,
        ["Mois", "Occupation", "Prix / nuit", "Recettes", "Dépenses", "Cash-flow"],
        lignes,
        [1.9, 2.1, 2.0, 2.3, 2.3, 2.2],
    )
    image = charts.chart_saisonnalite(saison["lignes"])
    p_image = cell_image.paragraphs[0]
    p_image.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_image.paragraph_format.space_after = Pt(0)
    hauteur_max = HAUTEUR_BLOC_CM - HAUTEUR_NOTE_CM
    largeur = min(largeur_image - 0.5, hauteur_max * _proportions_png(image))
    p_image.add_run().add_picture(io.BytesIO(image), width=Cm(largeur))
    _ajouter_note(
        doc,
        f"Profil de saisonnalité : {saison['profil'].lower()}. Cash-flow avant impôt de la première année ; "
        "charges fixes lissées sur 12 mois, commission et gestion proportionnelles aux recettes, ménage "
        "proportionnel aux nuits louées. La trésorerie de sécurité est la plus forte perte cumulée sur des "
        "mois consécutifs : la réserve à prévoir pour traverser la basse saison.",
    )


def _section_patrimoine(doc, inp, resultat):
    evolution = analyse.evolution_patrimoine(resultat, inp.prix_achat, inp.taux_revalorisation_bien_annuel)
    n = len(evolution)
    enrichissement = resultat["enrichissement_par_regime"][resultat["meilleur_regime"]]
    patrimoine_final = evolution[-1]["patrimoine_net"]
    _tuiles(
        doc,
        [
            (f"Patrimoine net — année {n}", _eur(patrimoine_final), patrimoine_final >= 0),
            ("Enrichissement net après revente", _eur(enrichissement), enrichissement >= 0),
            (f"Valeur estimée du bien — année {n}", _eur(evolution[-1]["valeur_bien"]), None),
        ],
    )
    jalons = sorted({a for a in (1, 5, 10, 15, 20, 25, 30, n) if 1 <= a <= n})
    lignes = [(f"Patrimoine net — année {a}", _eur(evolution[a - 1]["patrimoine_net"])) for a in jalons]
    lignes.append((f"Enrichissement net après revente ({n} ans)", _eur(enrichissement), "total"))
    _ajouter_table_et_graphique(
        doc, lignes, charts.chart_patrimoine(evolution), hauteur_max_cm=HAUTEUR_BLOC_CM - HAUTEUR_NOTE_CM
    )
    _ajouter_note(
        doc,
        "Patrimoine net = valeur du bien − capital restant dû + cash-flows cumulés − apport, avant impôt "
        "de revente. L'enrichissement net après revente tient compte de l'impôt sur la plus-value.",
    )


def _section_achat_revente_detail(doc, inp, resultat):
    ar = resultat["achat_revente"]
    tri = ar.get("tri_annualise")
    _tuiles(
        doc,
        [
            ("Marge nette", _eur(ar["marge_nette"]), ar["marge_nette"] >= 0),
            (libelle_rentabilite_ar(ar["apport_reel"]), _pct(ar["rentabilite_operation_pct"]), ar["rentabilite_operation_pct"] >= 0),
            ("TRI annualisé de l'apport", _pct(tri) if tri is not None else "n/a", tri >= 0 if tri is not None else None),
        ],
    )
    lignes = [
        ("Durée de portage", f"{inp.duree_portage_mois} mois"),
        ("Intérêts de portage", _eur(ar["frais_portage_interets"])),
        ("Taxe foncière de portage", _eur(ar["frais_portage_taxe_fonciere"])),
        ("Assurance de portage", _eur(ar["frais_portage_assurance"])),
        ("Total des frais de portage", _eur(ar["frais_portage_total"])),
        ("Prix de revente visé", _eur(ar["prix_revente"])),
        ("Frais d'agence à la revente", _eur(ar["frais_agence_revente"])),
        ("Produit net de la vente", _eur(ar["produit_net_vente"])),
        ("Marge brute avant impôt", _eur(ar["marge_brute_avant_impot"])),
        ("Régime fiscal applicable", ar["regime_fiscal"]),
        ("Impôt total", _eur(ar["impot_total"])),
        ("Marge nette", _eur(ar["marge_nette"]), "total"),
    ]
    _ajouter_table_et_graphique(doc, lignes, _image_pont_marge(resultat), largeur_table_cm=13.0, largeur_image_cm=12.3)


def _section_endettement(doc, inp, payload, resultat, is_achat_revente):
    mensualite_projet, loyers_mensuels = _mensualite_et_loyers(inp, resultat, is_achat_revente)
    r = _taux_endettement(payload, inp, resultat, is_achat_revente)
    _tuiles(
        doc,
        [
            ("Taux d'endettement", _pct(r.taux_endettement), not r.depasse_seuil),
            ("Seuil HCSF", _pct(r.seuil_hcsf, 0), None),
            (
                "Mensualité encore supportable",
                (_eur(r.marge_avant_seuil) + "/mois") if not r.depasse_seuil else "Seuil dépassé",
                not r.depasse_seuil,
            ),
        ],
    )
    lignes = [
        ("Mensualité du projet retenue (assurance comprise)", _eur(mensualite_projet)),
        ("Recettes locatives prévisionnelles retenues à 70 %", _eur(loyers_mensuels * endet_mod.PONDERATION_LOYERS)),
        ("Revenus considérés par la banque", _eur(r.revenus_consideres_mensuels)),
        ("Mensualités totales (crédits existants + projet)", _eur(r.mensualites_totales_mensuelles)),
        ("Taux d'endettement", _pct(r.taux_endettement, 1), "total"),
        ("Seuil HCSF", _pct(r.seuil_hcsf, 0)),
    ]
    couleur = visuels.ROUGE if r.depasse_seuil else (
        visuels.ORANGE if r.seuil_hcsf - r.taux_endettement < 0.03 else visuels.VERT
    )
    image = visuels.jauge(
        r.taux_endettement,
        0.5,
        couleur,
        _pct(r.taux_endettement, 1),
        "Taux d'endettement du foyer avec le projet",
        seuil=r.seuil_hcsf,
        texte_seuil=f"Seuil des banques : {_pct(r.seuil_hcsf, 0)}",
        texte_min="0 %",
        texte_max="50 %",
    )
    _ajouter_table_et_graphique(doc, lignes, image)


def _section_avertissements(doc, avertissements):
    for texte in avertissements:
        p = doc.add_paragraph(style="List Bullet")
        run = p.add_run(texte)
        run.font.color.rgb = RGBColor(0x99, 0x5C, 0x00)


def _section_mentions(doc):
    doc.add_paragraph(
        "Ce document est une estimation générée automatiquement à partir des hypothèses saisies par "
        "l'utilisateur (prix, loyers ou tarifs de location, charges, taux, durée…)."
    )
    doc.add_paragraph(MENTION_LEGALE)
    doc.add_paragraph(
        "Le barème de l'impôt sur le revenu, les taux de prélèvements sociaux et les règles "
        "d'amortissement appliqués correspondent à la législation en vigueur au moment de la "
        "génération du document et sont susceptibles d'évoluer."
    )
    note = doc.add_paragraph(
        "Ces éléments doivent être vérifiés et validés par un professionnel (notaire, "
        "expert-comptable, courtier en crédit) avant toute décision d'investissement ou "
        "constitution d'un dossier de financement définitif."
    )
    note.runs[0].italic = True


# ---------------------------------------------------------------------------
# Point d'entrée
# ---------------------------------------------------------------------------

def _ecart_au_marche(inp, marche: dict | None) -> tuple[float, float] | None:
    """(écart du prix au m² du projet à la médiane du quartier, médiane)."""
    mediane = ((marche or {}).get("comparables") or {}).get("prix_m2_moyen")
    if not mediane or not inp.surface_m2:
        return None
    return inp.prix_achat / inp.surface_m2 / mediane - 1, mediane


def _niveau_ecart(ecart: float) -> str:
    return analyse.niveau_ecart_au_marche(ecart)


def _couverture_loyer(resultat: dict) -> tuple[float, float]:
    """(part des dépenses mensuelles couverte par le loyer, cash-flow net)."""
    etapes = analyse.etapes_loyer_mensuel(resultat)
    loyers = etapes[0][1]
    cashflow = sum(v for _, v in etapes)
    depenses = loyers - cashflow
    return (loyers / depenses if depenses > 0 else 1.0), cashflow


def phrases_a_retenir(payload, inp, resultat: dict, is_achat_revente: bool) -> dict[str, tuple[str, str]]:
    """{chapitre: (niveau, phrase)} : la conclusion de chaque chapitre en une
    phrase, celle que le banquier lit en premier. Niveaux : vert, orange,
    rouge (favorable, à surveiller, défavorable) ou neutre (constat)."""
    phrases: dict[str, tuple[str, str]] = {}
    marche = payload.marche
    cout_total, apport, montant_emprunte = _cout_apport_emprunt(resultat, is_achat_revente)

    comp = (marche or {}).get("comparables") or {}
    if comp.get("prix_m2_moyen"):
        rayon = comp["rayon_utilise"]
        rayon_txt = f"{rayon / 1000:g} km".replace(".", ",") if rayon >= 1000 else f"{rayon} m"
        texte = f"{comp['nb_transactions']} ventes comparables dans un rayon de {rayon_txt} autour du bien"
        commune = (marche or {}).get("commune_indicateurs") or {}
        if inp.type_projet == TypeProjet.location_longue_duree and commune.get("rendement_brut"):
            texte += f" ; rentabilité brute moyenne de la commune : {_pct(commune['rendement_brut'])}"
        phrases["carte"] = ("neutre", texte + ".")
    ecart = _ecart_au_marche(inp, marche)
    if ecart:
        e, mediane = ecart
        if e <= -0.03:
            texte = f"Prix d'achat {_pct(-e, 0)} sous la médiane des ventes du quartier ({_eur(mediane)}/m²) : un prix justifié."
        elif e < 0.03:
            texte = f"Prix d'achat dans la médiane des ventes du quartier ({_eur(mediane)}/m²) : un prix conforme au marché."
        elif e < 0.10:
            texte = f"Prix d'achat {_pct(e, 0)} au-dessus de la médiane du quartier ({_eur(mediane)}/m²) : une marge de négociation existe."
        else:
            texte = (
                f"Prix d'achat {_pct(e, 0)} au-dessus de la médiane du quartier ({_eur(mediane)}/m²) : "
                "à justifier (travaux, prestations) ou à négocier."
            )
        phrases["marche"] = (_niveau_ecart(e), texte)

    frais = cout_total - inp.prix_achat
    phrases["presentation"] = (
        "neutre",
        f"Coût total de l'opération : {_eur(cout_total)}, dont {_eur(frais)} de frais, travaux et équipement "
        f"({_pct(frais / cout_total, 0)} du total)." if cout_total else "Coût total de l'opération à préciser.",
    )

    if is_achat_revente:
        ar = resultat["achat_revente"]
        part = ar["marge_nette"] / cout_total if cout_total else 0
        tri = ar.get("tri_annualise")
        texte = f"Marge nette de {_eur(ar['marge_nette'])}, soit {_pct(part)} du coût total"
        texte += f" ; TRI annualisé de l'apport : {_pct(tri)}." if tri is not None else "."
        phrases["achat_revente"] = ("rouge" if part < 0 else ("orange" if part < 0.10 else "vert"), texte)
    else:
        annee1 = resultat["annees"][0]
        if annee1["loyers_bruts"]:
            ratio = annee1["charges_hors_credit"] / annee1["loyers_bruts"]
            constat = "un niveau maîtrisé" if ratio < 0.30 else ("un niveau à surveiller" if ratio < 0.45 else "elles pèsent lourd sur la rentabilité")
            phrases["charges"] = (
                "vert" if ratio < 0.30 else ("orange" if ratio < 0.45 else "rouge"),
                f"Les charges hors crédit représentent {_pct(ratio, 0)} des loyers : {constat}.",
            )
        couverture, cashflow = _couverture_loyer(resultat)
        if cashflow >= 0:
            phrases["loyer_mensuel"] = (
                "vert",
                f"Le loyer couvre toutes les dépenses du bien et dégage {_eur(cashflow)} par mois.",
            )
        else:
            phrases["loyer_mensuel"] = (
                "orange" if couverture >= 0.85 else "rouge",
                f"Le loyer couvre {_pct(couverture, 0)} des dépenses mensuelles : il reste {_eur(-cashflow)} "
                "par mois à compléter.",
            )
        if inp.type_projet == TypeProjet.location_courte_duree:
            saison = saisonnalite.analyse_mensuelle(inp, resultat)
            nb = saison["mois_deficitaires"]
            phrases["saisonnalite"] = (
                ("vert", "Aucun mois déficitaire sur l'année : la saisonnalité est absorbée.")
                if not nb
                else (
                    "orange",
                    f"{nb} mois déficitaire{'s' if nb > 1 else ''} en basse saison : prévoir une réserve de "
                    f"trésorerie de {_eur(saison['tresorerie_securite'])}.",
                )
            )
        enrichissement = resultat["enrichissement_par_regime"][resultat["meilleur_regime"]]
        n = inp.duree_projection_annees
        phrases["patrimoine"] = (
            ("vert", f"En {n} ans, l'opération enrichit l'investisseur de {_eur(enrichissement)} (revente nette, impôts et apport déduits).")
            if enrichissement > 0
            else ("rouge", f"Sur {n} ans, l'opération ferait perdre {_eur(-enrichissement)} (revente nette, impôts et apport déduits).")
        )

    if montant_emprunte > 0:
        part_apport = apport / cout_total if cout_total else 0
        texte = f"Apport de {_eur(apport)} ({_pct(part_apport, 0)} du coût total) et crédit de {_eur(montant_emprunte)}"
        if not is_achat_revente:
            texte += f" sur {inp.duree_credit_annees} ans à {_pct(inp.taux_credit_annuel, 2)}"
        texte += "."
        if part_apport < 0.05:
            texte += " Les banques demandent souvent un apport couvrant au moins les frais."
        phrases["financement"] = ("vert" if part_apport >= 0.10 else "orange", texte)
    else:
        phrases["financement"] = ("neutre", "Opération financée à 100 % en fonds propres, sans crédit.")

    if payload.profil is not None:
        p = payload.profil
        texte = f"Revenus retenus par la banque : {_eur(p.revenus_nets_mensuels_foyer + p.autres_revenus_mensuels)} par mois"
        if payload.patrimoine:
            net = sum(l.valeur or 0 for l in payload.patrimoine) - sum(l.reste_du or 0 for l in payload.patrimoine)
            texte += f" ; patrimoine net déclaré : {_eur(net)}"
        phrases["profil"] = ("neutre", texte + ".")
        r = _taux_endettement(payload, inp, resultat, is_achat_revente)
        marge = r.seuil_hcsf - r.taux_endettement
        if r.depasse_seuil:
            phrases["endettement"] = (
                "rouge",
                f"Avec ce projet, le foyer atteint {_pct(r.taux_endettement)} d'endettement, au-delà du seuil de "
                f"{_pct(r.seuil_hcsf, 0)} : à revoir (apport, durée du crédit ou prix).",
            )
        else:
            points = f"{marge * 100:.1f}".replace(".", ",")
            phrases["endettement"] = (
                "vert" if marge >= 0.03 else "orange",
                f"Avec ce projet, le foyer est à {_pct(r.taux_endettement)} d'endettement : {points} points sous le "
                f"seuil de {_pct(r.seuil_hcsf, 0)}.",
            )
    return phrases


# matplotlib (pyplot) n'est pas prévu pour tracer depuis plusieurs fils à la
# fois : une génération à la fois (l'interface la lance hors de la boucle
# d'événements).
_VERROU_GENERATION = threading.Lock()


def generer_dossier_word(payload: ExportDossierInput, chapitres_lisibles: int | None = None) -> bytes:
    """`chapitres_lisibles` : aperçu gratuit, seuls les N premiers chapitres
    sont rédigés ; les suivants gardent leur titre mais pas leur contenu (le
    serveur n'envoie jamais les pages payantes, le flou seul se contourne)."""
    with _VERROU_GENERATION:
        return _generer_dossier_word(payload, chapitres_lisibles)


def _section_reservee(doc) -> None:
    """Contenu d'un chapitre hors de l'aperçu gratuit."""
    filet, fond = COULEURS_VERDICT["neutre"]
    table = doc.add_table(rows=1, cols=1)
    table.autofit = False
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    _supprimer_bordures(table)
    table.columns[0].width = Cm(LARGEUR_CONTENU_CM)
    cell = table.rows[0].cells[0]
    cell.width = Cm(LARGEUR_CONTENU_CM)
    _set_cell_background(cell, fond)
    _bordures_cellule(cell, left=(filet, 36))
    _cell_marges(cell, haut=120, bas=120, gauche=240, droite=240)
    _texte(cell.paragraphs[0], "Ce chapitre figure dans le dossier complet.", 11.5, RGBColor.from_string(filet), gras=True)
    _espace(doc, 8)
    for largeur in (100, 92, 97, 60, 0, 95, 88, 99, 70):
        p = doc.add_paragraph()
        if largeur:
            _texte(p, "\u2588" * largeur, 6, RGBColor(0xE3, 0xE8, 0xEF))


def _generer_dossier_word(payload: ExportDossierInput, chapitres_lisibles: int | None = None) -> bytes:
    inp = payload.simulation
    if not inp.avec_credit:
        # Sans crédit, pas d'emprunteur ni de taux d'endettement à présenter.
        payload = payload.model_copy(update={"profil": None})
    resultat = clean_result(simuler(inp))
    is_achat_revente = inp.type_projet == TypeProjet.achat_revente
    is_lcd = inp.type_projet == TypeProjet.location_courte_duree
    is_meublee = is_lcd or inp.regime_location.value == "meublee"

    doc = Document()
    style = doc.styles["Normal"]
    style.font.name = POLICE
    style.font.size = Pt(10.5)

    _configurer_page(doc)
    _configurer_entete_pied(doc, f"{_titre_projet(payload, inp)} — {_label_type_projet(inp.type_projet.value)}")
    _ajouter_page_de_garde(doc, payload, inp, resultat, is_achat_revente)

    annee1 = None if is_achat_revente else resultat["annees"][0]
    marche = payload.marche
    avec_marche = bool(marche and (marche.get("comparables") or {}).get("prix_m2_moyen"))
    avertissements = resultat.get("avertissements") or []
    # Carte de rentabilité des communes : loyers de location classique, sans
    # objet en location courte durée ou en achat-revente.
    carte_communes = inp.type_projet == TypeProjet.location_longue_duree and bool(
        (marche or {}).get("communes_geojson")
    )

    # (clé, titre, phrase d'explication sous le titre, contenu), dans l'ordre
    # du dossier ; la partie de chaque chapitre est dans PARTIE_DU_CHAPITRE.
    # La synthèse, les points d'attention et les mentions sont toujours inclus.
    candidats: list[tuple[bool, str, str, str, "callable"]] = [
        # --- Le bien
        (
            avec_marche and marche.get("lat") is not None,
            "carte",
            "Le bien sur la carte",
            "Les ventes comparables autour du bien"
            + (" et la rentabilité des communes du département." if carte_communes else "."),
            lambda d: _section_carte(d, marche, carte_communes),
        ),
        (
            True,
            "photos",
            "Le bien en photos",
            "Photos du bien."
            if payload.photos
            else "Emplacements prévus pour les photos du bien : clic droit sur un cadre › Modifier l'image.",
            lambda d: _section_photos(d, payload.photos or []),
        ),
        (
            avec_marche,
            "marche",
            "Étude de marché",
            "Le prix d'achat comparé aux ventes réelles de biens similaires autour du bien.",
            lambda d: _section_marche(d, inp, marche, is_achat_revente),
        ),
        (
            True,
            "presentation",
            "Le bien et le projet",
            "Le bien, son prix et la composition du coût total de l'opération.",
            lambda d: _section_presentation(d, payload, inp, resultat, is_achat_revente),
        ),
        # --- La rentabilité
        (
            not is_achat_revente,
            "charges",
            "Recettes et charges annuelles",
            "Ce que rapporte le bien et ce qu'il coûte chaque année.",
            lambda d: _section_charges(d, inp, annee1, is_meublee, is_lcd),
        ),
        (
            not is_achat_revente,
            "loyer_mensuel",
            "Où va le loyer chaque mois",
            "Du loyer encaissé au cash-flow net : charges, crédit et impôts, mois par mois.",
            lambda d: _section_loyer_mensuel(d, resultat),
        ),
        (
            is_lcd,
            "saisonnalite",
            "Saisonnalité mois par mois",
            "Recettes, dépenses et cash-flow de chaque mois de la première année.",
            lambda d: _section_saisonnalite(d, inp, resultat),
        ),
        (
            not is_achat_revente,
            "patrimoine",
            "Évolution du patrimoine",
            "Comment le patrimoine se construit au fil du remboursement du crédit.",
            lambda d: _section_patrimoine(d, inp, resultat),
        ),
        (
            is_achat_revente,
            "achat_revente",
            "L'opération d'achat-revente",
            "Du prix d'achat à la marge nette : frais de portage, revente et fiscalité.",
            lambda d: _section_achat_revente_detail(d, inp, resultat),
        ),
        # --- Le financement
        (
            True,
            "financement",
            "Plan de financement",
            "Comment l'opération est financée : apport, crédit et mensualités.",
            lambda d: _section_financement(d, inp, resultat, is_achat_revente),
        ),
        (
            payload.profil is not None,
            "profil",
            "Profil de l'emprunteur",
            "Revenus, engagements et patrimoine du foyer pris en compte par la banque.",
            lambda d: _section_profil(d, payload),
        ),
        (
            payload.profil is not None,
            "endettement",
            "Taux d'endettement",
            "Capacité d'emprunt du foyer au regard de la règle des 35 % du HCSF.",
            lambda d: _section_endettement(d, inp, payload, resultat, is_achat_revente),
        ),
        # --- Conclusion
        (
            bool(avertissements),
            "avertissements",
            "Points d'attention",
            "Éléments à vérifier avant de s'engager.",
            lambda d: _section_avertissements(d, avertissements),
        ),
        (
            True,
            "synthese",
            "Synthèse du projet",
            "Le bilan du projet : les repères essentiels, puis les chiffres clés de chaque partie.",
            lambda d: _section_synthese(d, payload, inp, resultat, is_achat_revente),
        ),
        (
            inp.avec_credit,
            "annexes",
            "Pièces à fournir à la banque",
            "Les documents à réunir pour que la banque ouvre l'étude de financement.",
            lambda d: _section_annexes(d, inp),
        ),
        (
            True,
            "mentions",
            "Mentions et méthodologie",
            "Hypothèses de calcul et limites de l'estimation.",
            lambda d: _section_mentions(d),
        ),
    ]
    retenus = None if payload.chapitres is None else set(payload.chapitres) | CHAPITRES_OBLIGATOIRES
    sections = [
        (cle, titre, description, fn)
        for present, cle, titre, description, fn in candidats
        if present and (retenus is None or cle in retenus)
    ]

    _ajouter_sommaire(doc, sections)
    parties_presentes = tuple(p for p in PARTIES if any(PARTIE_DU_CHAPITRE[cle] == p for cle, *_ in sections))
    a_retenir = phrases_a_retenir(payload, inp, resultat, is_achat_revente)
    for i, (cle, titre, description, fn) in enumerate(sections, start=1):
        section = _nouvelle_page_chapitre(doc)
        _pied_de_page_chapitre(section, visuels.fil_parties(parties_presentes, PARTIE_DU_CHAPITRE[cle]))
        _entete_chapitre(
            doc,
            i,
            titre,
            description,
            partie=PARTIE_DU_CHAPITRE[cle],
            parties=parties_presentes,
            icone=ICONES_CHAPITRES.get(cle),
        )
        if chapitres_lisibles is not None and i > chapitres_lisibles:
            _section_reservee(doc)
            continue
        if cle in a_retenir:
            _a_retenir(doc, *a_retenir[cle])
        fn(doc)

    integrer_polices(doc)
    buffer = io.BytesIO()
    doc.save(buffer)
    return buffer.getvalue()
