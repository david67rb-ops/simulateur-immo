"""Intégration des polices de la charte (Sora, Public Sans) dans un document
Word, pour qu'il s'affiche à l'identique chez un destinataire qui ne les a
pas installées (le banquier, typiquement).

Format standard des polices incorporées Office Open XML (ECMA-376, partie 1,
§ 17.8.1) : chaque fichier de police est « obscurci » (ses 32 premiers
octets combinés par XOR avec une clé tirée d'un GUID), déclaré dans
fontTable.xml (w:embedRegular, w:embedBold…) et relié à cette partie ; le
réglage w:embedTrueTypeFonts indique à Word de les conserver."""
from __future__ import annotations

import uuid
from pathlib import Path

from docx.opc.constants import RELATIONSHIP_TYPE as RT
from lxml import etree
from docx.opc.packuri import PackURI
from docx.opc.part import Part
from docx.oxml import parse_xml
from docx.oxml.ns import qn

DOSSIER_POLICES = Path(__file__).parent / "fonts"
TYPE_POLICE_OBSCURCIE = "application/vnd.openxmlformats-officedocument.obfuscatedFont"
NS_W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
NS_R = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"

# Famille Word → fichiers par style (w:embedRegular, w:embedItalic). Word
# (macOS au moins) n'utilise que la version normale d'une police incorporée
# et simule le gras : chaque graisse forte est donc une famille à part,
# appliquée sans l'attribut gras (voir dossier_export._texte).
POLICES = {
    "Sora": {"Regular": "Sora-Regular.ttf"},
    "Sora SemiBold": {"Regular": "Sora-SemiBold.ttf"},
    "Public Sans": {"Regular": "PublicSans-Regular.ttf", "Italic": "PublicSans-Italic.ttf"},
    "Public Sans SemiBold": {"Regular": "PublicSans-SemiBold.ttf"},
}


def _obscurcir(donnees: bytes, cle_guid: str) -> bytes:
    """XOR des 32 premiers octets avec la clé : les 16 octets du GUID pris
    dans l'ordre inverse de leur écriture."""
    cle = bytes.fromhex(cle_guid.strip("{}").replace("-", ""))[::-1]
    tete = bytes(octet ^ cle[i % 16] for i, octet in enumerate(donnees[:32]))
    return tete + donnees[32:]


def integrer_polices(document) -> None:
    table_polices = document.part.part_related_by(RT.FONT_TABLE)
    racine = parse_xml(table_polices.blob)
    package = document.part.package
    numero = 1
    for famille, styles in POLICES.items():
        for ancienne in racine.findall(qn("w:font")):
            if ancienne.get(qn("w:name")) == famille:
                racine.remove(ancienne)
        police = parse_xml(
            f'<w:font xmlns:w="{NS_W}" w:name="{famille}">'
            '<w:charset w:val="00"/><w:family w:val="swiss"/><w:pitch w:val="variable"/></w:font>'
        )
        for style, fichier in styles.items():
            cle = "{" + str(uuid.uuid4()).upper() + "}"
            partie = Part(
                PackURI(f"/word/fonts/font{numero}.odttf"),
                TYPE_POLICE_OBSCURCIE,
                _obscurcir((DOSSIER_POLICES / fichier).read_bytes(), cle),
                package,
            )
            numero += 1
            rid = table_polices.relate_to(partie, RT.FONT)
            element = parse_xml(f'<w:embed{style} xmlns:w="{NS_W}" xmlns:r="{NS_R}" r:id="{rid}" w:fontKey="{cle}"/>')
            police.append(element)
        racine.append(police)
    table_polices._blob = etree.tostring(racine, xml_declaration=True, encoding="UTF-8", standalone=True)

    # w:embedTrueTypeFonts se place juste après w:zoom (ordre imposé par le schéma).
    reglages = document.settings.element
    if reglages.find(qn("w:embedTrueTypeFonts")) is None:
        element = parse_xml(f'<w:embedTrueTypeFonts xmlns:w="{NS_W}"/>')
        zoom = reglages.find(qn("w:zoom"))
        if zoom is not None:
            zoom.addnext(element)
        else:
            reglages.insert(0, element)
