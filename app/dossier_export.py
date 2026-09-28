"""Génération du dossier de financement au format Word (.docx)."""
from __future__ import annotations

import io
from datetime import datetime

from docx import Document
from docx.shared import Cm, Mm, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_TAB_ALIGNMENT
from docx.enum.table import WD_ALIGN_VERTICAL, WD_TABLE_ALIGNMENT
from docx.enum.section import WD_ORIENT, WD_SECTION
from docx.oxml import OxmlElement
from docx.oxml.ns import qn

from . import charts_export as charts
from . import analyse
from . import endettement as endet_mod
from . import saisonnalite
from .chapitres_dossier import CHAPITRES_OBLIGATOIRES
from .schemas import ExportDossierInput, TypeProjet
from .simulation import simuler
from .utils import clean_result, libelle_regime

POLICE = "Calibri"
PRIMARY_COLOR = RGBColor(0x1D, 0x6F, 0x5C)
GRIS_COLOR = RGBColor(0x99, 0x99, 0x99)
GRIS_LIBELLE = RGBColor(0x5A, 0x5A, 0x5A)
TEXTE_FONCE = RGBColor(0x22, 0x2A, 0x27)
ZEBRA_HEX = "F2F7F5"
BORDURE_HEX = "E2E2E2"
BLANC = RGBColor(0xFF, 0xFF, 0xFF)
ROUGE = RGBColor(0xC6, 0x3F, 0x35)
VERT_HEX = "1D6F5C"
ROUGE_HEX = "C63F35"
FOND_TUILE_HEX = "EEF6F3"
# (couleur du filet et du titre, fond) selon le niveau du verdict
COULEURS_VERDICT = {"vert": ("1D6F5C", "E8F3EF"), "orange": ("B8761F", "FAF0E2"), "rouge": ("C63F35", "FBE9E7")}

# Page A4 paysage : plus de largeur pour les mises en page tableau + graphique.
LARGEUR_PAGE_CM = 29.7
HAUTEUR_PAGE_CM = 21.0
MARGE_CM = 1.8
LARGEUR_CONTENU_CM = LARGEUR_PAGE_CM - 2 * MARGE_CM

# Budget vertical d'un chapitre (une page) : hauteur utile moins l'en-tête de
# chapitre et la rangée de tuiles, avec une marge de sécurité (le rendu exact
# dépend de Word). Le bloc tableau + graphique doit tenir dans ce reste.
HAUTEUR_UTILE_CM = HAUTEUR_PAGE_CM - 2 * MARGE_CM
HAUTEUR_ENTETE_CHAPITRE_CM = 2.2
HAUTEUR_TUILES_CM = 2.1
HAUTEUR_NOTE_CM = 1.0
HAUTEUR_VERDICT_CM = 2.6
MARGE_SECURITE_CM = 1.0
HAUTEUR_BLOC_CM = HAUTEUR_UTILE_CM - HAUTEUR_ENTETE_CHAPITRE_CM - HAUTEUR_TUILES_CM - MARGE_SECURITE_CM
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
            _bordure_bas_cellule(cell, color=VERT_HEX if est_total else BORDURE_HEX, size=8 if est_total else 4)
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
    run.font.name = POLICE
    run.font.size = Pt(taille)
    run.font.color.rgb = couleur or TEXTE_FONCE
    run.bold = gras
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
        accent = ROUGE_HEX if favorable is False else VERT_HEX
        _bordures_cellule(cell, left=(accent, 24), right=("FFFFFF", 48) if i < len(tuiles) - 1 else None)
        _cell_marges(cell, haut=110, bas=130, gauche=200, droite=120)
        _texte(cell.paragraphs[0], libelle.upper(), 7.5, GRIS_LIBELLE, gras=True)
        couleur = PRIMARY_COLOR if favorable else (ROUGE if favorable is False else TEXTE_FONCE)
        p_valeur = cell.add_paragraph()
        p_valeur.paragraph_format.space_before = Pt(2)
        _texte(p_valeur, valeur, taille_valeur, couleur, gras=True)
    _espace(container, 10)


def _bandeau_verdict(doc, verdict: dict) -> None:
    filet, fond = COULEURS_VERDICT[verdict["niveau"]]
    table = doc.add_table(rows=1, cols=1)
    table.autofit = False
    _supprimer_bordures(table)
    table.columns[0].width = Cm(LARGEUR_CONTENU_CM)
    cell = table.rows[0].cells[0]
    cell.width = Cm(LARGEUR_CONTENU_CM)
    _set_cell_background(cell, fond)
    _bordures_cellule(cell, left=(filet, 36))
    _cell_marges(cell, haut=140, bas=140, gauche=260, droite=260)
    _texte(cell.paragraphs[0], verdict["titre"], 15, RGBColor.from_string(filet), gras=True)
    p = cell.add_paragraph()
    p.paragraph_format.space_before = Pt(2)
    _texte(p, verdict["detail"], 10, GRIS_LIBELLE)
    _espace(doc, 10)


def _entete_chapitre(doc, numero: int, titre: str, description: str | None) -> None:
    """Numéro dans un pavé vert, titre et phrase d'explication à côté."""
    table = doc.add_table(rows=1, cols=2)
    table.autofit = False
    _supprimer_bordures(table)
    largeurs = (1.9, LARGEUR_CONTENU_CM - 1.9)
    cell_num, cell_titre = table.rows[0].cells
    for i, (cell, largeur) in enumerate(zip((cell_num, cell_titre), largeurs)):
        table.columns[i].width = Cm(largeur)
        cell.width = Cm(largeur)
        cell.vertical_alignment = WD_ALIGN_VERTICAL.CENTER
    _set_cell_background(cell_num, VERT_HEX)
    _cell_marges(cell_num, haut=80, bas=80, gauche=60, droite=60)
    p_num = cell_num.paragraphs[0]
    p_num.alignment = WD_ALIGN_PARAGRAPH.CENTER
    _texte(p_num, f"{numero:02d}", 22, BLANC, gras=True)
    _cell_marges(cell_titre, haut=40, bas=60, gauche=260, droite=60)
    _bordures_cellule(cell_titre, bottom=(VERT_HEX, 12))
    _texte(cell_titre.paragraphs[0], titre, 20, TEXTE_FONCE, gras=True)
    if description:
        p = cell_titre.add_paragraph()
        p.paragraph_format.space_before = Pt(1)
        _texte(p, description, 10, GRIS_LIBELLE)
    _espace(doc, 14)


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
    _alignement_vertical(section, "center" if centrer else "top")


def _configurer_page(doc: Document) -> None:
    _mettre_en_page(doc.sections[0], centrer=True)


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

    header_p = section.header.paragraphs[0]
    _taquet_a_droite(header_p)
    _texte(header_p, "DOSSIER DE FINANCEMENT IMMOBILIER", 8, PRIMARY_COLOR, gras=True)
    _texte(header_p, "\t" + libelle_projet, 8, GRIS_COLOR)
    _add_bottom_border(header_p, color=VERT_HEX, size=6)

    footer_p = section.footer.paragraphs[0]
    _taquet_a_droite(footer_p)
    _texte(footer_p, "Estimation pédagogique — à faire valider par un professionnel", 8, GRIS_COLOR, italique=True)
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
    return resultat.get("mensualite_credit_hors_assurance", 0.0), resultat["annees"][0]["loyers_bruts"] / 12


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
            ("Rentabilité", _pct(ar["rentabilite_operation_pct"]), ar["rentabilite_operation_pct"] >= 0),
        ]
    revenu = (
        ("Chiffre d'affaires mensuel", _eur(resultat["annees"][0]["loyers_bruts"] / 12))
        if inp.type_projet == TypeProjet.location_courte_duree
        else ("Loyer mensuel", _eur(inp.loyer_mensuel_hors_charges))
    )
    cf = resultat["cashflow_mensuel_an1"]
    return [
        ("Prix d'achat", _eur(inp.prix_achat), None),
        (*revenu, None),
        ("Cash-flow net mensuel", _eur(cf), cf >= 0),
        ("Rendement brut", _pct(resultat["rendement_brut"]), None),
    ]


def _ajouter_page_de_garde(doc: Document, payload: ExportDossierInput, inp, resultat: dict, is_achat_revente: bool) -> None:
    # Bandeau vert : logo à gauche, titre du dossier et du projet à droite.
    bandeau = doc.add_table(rows=1, cols=2)
    bandeau.autofit = False
    _supprimer_bordures(bandeau)
    largeurs = (3.6, LARGEUR_CONTENU_CM - 3.6)
    cell_logo, cell_titre = bandeau.rows[0].cells
    for i, (cell, largeur) in enumerate(zip((cell_logo, cell_titre), largeurs)):
        bandeau.columns[i].width = Cm(largeur)
        cell.width = Cm(largeur)
        cell.vertical_alignment = WD_ALIGN_VERTICAL.CENTER
        _set_cell_background(cell, VERT_HEX)
    _cell_marges(cell_logo, haut=500, bas=500, gauche=400, droite=100)
    cell_logo.paragraphs[0].add_run().add_picture(io.BytesIO(charts.logo_png()), width=Cm(2.6))
    _cell_marges(cell_titre, haut=500, bas=500, gauche=200, droite=400)
    _texte(cell_titre.paragraphs[0], "DOSSIER DE FINANCEMENT IMMOBILIER", 11, RGBColor(0xCF, 0xE6, 0xDE), gras=True)
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
        "Document généré automatiquement — estimation pédagogique, à faire valider par un professionnel "
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
        titre="Où va le loyer chaque mois (année 1)",
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


def _section_synthese(doc, payload, inp, resultat, is_achat_revente):
    _bandeau_verdict(doc, analyse.verdict(inp, resultat))
    cout_total, apport, montant_emprunte = _cout_apport_emprunt(resultat, is_achat_revente)
    tuile_endettement = None
    if payload.profil is not None:
        r = _taux_endettement(payload, inp, resultat, is_achat_revente)
        tuile_endettement = ("Taux d'endettement", _pct(r.taux_endettement), not r.depasse_seuil)

    if is_achat_revente:
        ar = resultat["achat_revente"]
        tri = ar.get("tri_annualise")
        tuiles = [
            ("Marge nette", _eur(ar["marge_nette"]), ar["marge_nette"] >= 0),
            ("Rentabilité", _pct(ar["rentabilite_operation_pct"]), ar["rentabilite_operation_pct"] >= 0),
            ("TRI annualisé", _pct(tri) if tri is not None else "n/a", tri >= 0 if tri is not None else None),
            ("Coût total", _eur(cout_total), None),
            ("Frais de portage", _eur(ar["frais_portage_total"]), None),
            tuile_endettement or ("Impôt", _eur(ar["impot_total"]), None),
        ]
        image = _image_pont_marge(resultat)
        lignes_projet = [("Durée de portage", f"{inp.duree_portage_mois} mois"), ("Prix de revente", _eur(ar["prix_revente"]))]
    else:
        regime = resultat["meilleur_regime"]
        cf = resultat["cashflow_mensuel_an1"]
        effort = resultat["effort_epargne_mensuel"]
        enrichissement = resultat["enrichissement_par_regime"][regime]
        net_net = resultat["rendement_net_net_par_regime"][regime]
        tuiles = [
            ("Cash-flow net / mois", _eur(cf), cf >= 0),
            ("Effort d'épargne / mois", _eur(effort) if effort > 0 else "Aucun", effort <= 0),
            (f"Enrichissement {inp.duree_projection_annees} ans", _eur(enrichissement), enrichissement >= 0),
            ("Rendement brut", _pct(resultat["rendement_brut"]), None),
            ("Rendement net-net", _pct(net_net), net_net >= 0),
            tuile_endettement or ("Coût total", _eur(cout_total), None),
        ]
        image = _image_cascade_loyer(resultat)
        lignes_projet = [("Régime fiscal le plus favorable", libelle_regime(regime))]
    _tuiles(doc, tuiles, taille_valeur=15)

    lignes = [
        ("Type de projet", _label_type_projet(inp.type_projet.value)),
        ("Structure juridique", _label_structure(inp.structure_juridique.value)),
        ("Coût total de l'opération", _eur(cout_total), "total"),
        ("Apport personnel", _eur(apport)),
        ("Montant emprunté", _eur(montant_emprunte))
        if montant_emprunte > 0
        else ("Financement", "100 % fonds propres (sans crédit)"),
    ]
    if montant_emprunte > 0 and not is_achat_revente:
        lignes.append(("Mensualité du crédit (hors assurance)", _eur(resultat["mensualite_credit_hors_assurance"]) + "/mois"))
    lignes += lignes_projet
    _ajouter_table_et_graphique(
        doc, lignes, image, largeur_table_cm=13.4, largeur_image_cm=11.0, hauteur_max_cm=HAUTEUR_BLOC_CM - HAUTEUR_VERDICT_CM
    )


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


def _section_profil(doc, payload):
    p = payload.profil
    _tuiles(
        doc,
        [
            ("Revenus mensuels retenus", _eur(p.revenus_nets_mensuels_foyer + p.autres_revenus_mensuels), None),
            ("Crédits en cours / mois", _eur(p.mensualites_credits_existants), None),
        ],
    )
    lignes = []
    if payload.nom_emprunteur:
        lignes.append(("Emprunteur", payload.nom_emprunteur))
    lignes += [
        ("Revenus nets mensuels du foyer", _eur(p.revenus_nets_mensuels_foyer)),
        ("Autres revenus mensuels", _eur(p.autres_revenus_mensuels)),
        ("Mensualités de crédits existants", _eur(p.mensualites_credits_existants)),
        ("Total des revenus mensuels retenus", _eur(p.revenus_nets_mensuels_foyer + p.autres_revenus_mensuels), "total"),
    ]
    image = charts.chart_barres(
        [
            ("Revenus mensuels retenus", p.revenus_nets_mensuels_foyer + p.autres_revenus_mensuels),
            ("Mensualités de crédits existants", p.mensualites_credits_existants),
        ],
        "Profil de l'emprunteur",
    )
    _ajouter_table_et_graphique(doc, lignes, image)


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
    image = charts.chart_donut([apport, montant_emprunte], ["Apport personnel", "Montant emprunté"], "Plan de financement", total_label="Coût total")
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
        lignes.append(("Frais comptable annuel", _eur(inp.frais_comptable_annuel)))
        if inp.cfe_annuelle > 0:
            lignes.append(("CFE (due à partir de la 2e année)", _eur(inp.cfe_annuelle)))
    lignes.append(("Total des charges hors crédit (année 1)", _eur(annee1["charges_hors_credit"]), "total"))
    lignes.append(("Hausse annuelle des charges retenue", _pct(inp.taux_revalorisation_charges_annuel)))

    # Le graphique inclut en plus le crédit (contrairement au tableau, exprimé
    # hors crédit) pour donner une vision complète de la rentabilité du projet.
    charges_graphique = charges_items + [("Crédit (annuité)", annee1["mensualite_totale_credit"])]
    charges_graphique_non_nulles = [(l, v) for l, v in charges_graphique if v > 0]
    image = charts.chart_recettes_charges(
        loyers_bruts_an1, charges_graphique_non_nulles, "Recettes et charges annuelles (crédit inclus)"
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
    lignes = [(libelle, ("+" if v >= 0 else "") + _eur(v)) for libelle, v in etapes]
    lignes.append(("Cash-flow net mensuel", _eur(cashflow), "total"))
    _ajouter_table_et_graphique(doc, lignes, _image_cascade_loyer(resultat), hauteur_max_cm=HAUTEUR_BLOC_CM - HAUTEUR_NOTE_CM)
    _ajouter_note(
        doc,
        f"Moyenne mensuelle de la première année, régime {libelle_regime(resultat['meilleur_regime'])}. "
        "Les charges comprennent copropriété, taxe foncière, assurances, entretien et frais de gestion.",
    )


def _ajouter_table_colonnes(container, entetes: list[str], lignes: list[list[str]], largeurs_cm: list[float]) -> None:
    """Tableau à plusieurs colonnes (en-tête, zébrage, montants négatifs en
    rouge), serré pour tenir sur la page."""
    taille, _, marge = STYLE_DENSITE["serre"]
    table = container.add_table(rows=0, cols=len(entetes))
    table.style = "Normal Table"
    table.autofit = False
    for i, valeurs in enumerate([entetes] + lignes):
        row = table.add_row()
        for j, (cell, valeur) in enumerate(zip(row.cells, valeurs)):
            cell.width = Cm(largeurs_cm[j])
            p = cell.paragraphs[0]
            p.alignment = WD_ALIGN_PARAGRAPH.LEFT if j == 0 else WD_ALIGN_PARAGRAPH.RIGHT
            if i == 0:
                _texte(p, valeur, taille - 0.5, BLANC, gras=True)
                _set_cell_background(cell, VERT_HEX)
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
            ("Rentabilité de l'opération", _pct(ar["rentabilite_operation_pct"]), ar["rentabilite_operation_pct"] >= 0),
            ("TRI annualisé", _pct(tri) if tri is not None else "n/a", tri >= 0 if tri is not None else None),
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
        ("Mensualité du projet retenue (hors assurance)", _eur(mensualite_projet)),
        ("Recettes locatives prévisionnelles retenues à 70 %", _eur(loyers_mensuels * endet_mod.PONDERATION_LOYERS)),
        ("Revenus considérés par la banque", _eur(r.revenus_consideres_mensuels)),
        ("Mensualités totales (crédits existants + projet)", _eur(r.mensualites_totales_mensuelles)),
        ("Taux d'endettement", _pct(r.taux_endettement, 1), "total"),
        ("Seuil HCSF", _pct(r.seuil_hcsf, 0)),
    ]
    image = charts.chart_barres(
        [("Taux d'endettement du projet", r.taux_endettement)],
        "Taux d'endettement vs seuil HCSF",
        formatter=lambda v: _pct(v, 1),
        seuil=r.seuil_hcsf,
        seuil_label=f"Seuil {_pct(r.seuil_hcsf, 0)}",
    )
    _ajouter_table_et_graphique(doc, lignes, image)


def _section_avertissements(doc, avertissements):
    for texte in avertissements:
        p = doc.add_paragraph(style="List Bullet")
        run = p.add_run(texte)
        run.font.color.rgb = RGBColor(0x99, 0x5C, 0x00)


def _section_mentions(doc):
    doc.add_paragraph(
        "Ce document est une estimation pédagogique générée automatiquement à partir des "
        "hypothèses saisies par l'utilisateur (prix, loyers ou tarifs de location, charges, taux, durée...). Il ne "
        "constitue ni une offre de prêt, ni un conseil fiscal ou juridique personnalisé."
    )
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

def generer_dossier_word(payload: ExportDossierInput) -> bytes:
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

    # (clé, titre, phrase d'explication sous le titre, contenu). La synthèse,
    # les points d'attention et les mentions sont toujours inclus.
    sections: list[tuple[str, str, str, "callable"]] = [
        (
            "synthese",
            "Synthèse du projet",
            "L'essentiel en un coup d'œil : verdict, indicateurs clés et "
            + ("décomposition de la marge." if is_achat_revente else "répartition du loyer chaque mois."),
            lambda d: _section_synthese(d, payload, inp, resultat, is_achat_revente),
        ),
        (
            "presentation",
            "Le bien et le projet",
            "Le bien, son prix et la composition du coût total de l'opération.",
            lambda d: _section_presentation(d, payload, inp, resultat, is_achat_revente),
        ),
    ]
    if payload.profil is not None:
        sections.append(
            (
                "profil",
                "Profil de l'emprunteur",
                "Revenus et engagements du foyer pris en compte par la banque.",
                lambda d: _section_profil(d, payload),
            )
        )
    sections.append(
        (
            "financement",
            "Plan de financement",
            "Comment l'opération est financée : apport, crédit et mensualités.",
            lambda d: _section_financement(d, inp, resultat, is_achat_revente),
        )
    )
    if is_achat_revente:
        sections.append(
            (
                "achat_revente",
                "L'opération d'achat-revente",
                "Du prix d'achat à la marge nette : frais de portage, revente et fiscalité.",
                lambda d: _section_achat_revente_detail(d, inp, resultat),
            )
        )
    else:
        sections.append(
            (
                "charges",
                "Recettes et charges annuelles",
                "Ce que rapporte le bien et ce qu'il coûte chaque année.",
                lambda d: _section_charges(d, inp, annee1, is_meublee, is_lcd),
            )
        )
        sections.append(
            (
                "loyer_mensuel",
                "Où va le loyer chaque mois",
                "Du loyer encaissé au cash-flow net : charges, crédit et impôts, mois par mois.",
                lambda d: _section_loyer_mensuel(d, resultat),
            )
        )
        if is_lcd:
            sections.append(
                (
                    "saisonnalite",
                    "Saisonnalité mois par mois",
                    "Recettes, dépenses et cash-flow de chaque mois de la première année.",
                    lambda d: _section_saisonnalite(d, inp, resultat),
                )
            )
        sections.append(
            (
                "patrimoine",
                "Évolution du patrimoine",
                "Comment le patrimoine se construit au fil du remboursement du crédit.",
                lambda d: _section_patrimoine(d, inp, resultat),
            )
        )
    if payload.profil is not None:
        sections.append(
            (
                "endettement",
                "Taux d'endettement",
                "Capacité d'emprunt du foyer au regard de la règle des 35 % du HCSF.",
                lambda d: _section_endettement(d, inp, payload, resultat, is_achat_revente),
            )
        )
    avertissements = resultat.get("avertissements") or []
    if avertissements:
        sections.append(
            (
                "avertissements",
                "Points d'attention",
                "Éléments à vérifier avant de s'engager.",
                lambda d: _section_avertissements(d, avertissements),
            )
        )
    sections.append(
        (
            "mentions",
            "Mentions et méthodologie",
            "Hypothèses de calcul et limites de l'estimation.",
            lambda d: _section_mentions(d),
        )
    )
    if payload.chapitres is not None:
        retenus = set(payload.chapitres) | CHAPITRES_OBLIGATOIRES
        sections = [section for section in sections if section[0] in retenus]

    for i, (_cle, titre, description, fn) in enumerate(sections, start=1):
        _nouvelle_page_chapitre(doc)
        _entete_chapitre(doc, i, titre, description)
        fn(doc)

    buffer = io.BytesIO()
    doc.save(buffer)
    return buffer.getvalue()
