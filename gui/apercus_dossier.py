"""Aperçu du dossier Word dans le navigateur.

Le serveur garde en mémoire les derniers dossiers générés pour l'aperçu et
les sert à une adresse à usage unique difficile à deviner ; le navigateur les
affiche page par page avec docx-preview (chargé à la demande depuis le CDN
jsDelivr, avec JSZip)."""
from __future__ import annotations

import secrets
from collections import OrderedDict

from fastapi import HTTPException, Response
from nicegui import app, ui

TYPE_DOCX = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
NB_APERCUS_EN_MEMOIRE = 20
_apercus: OrderedDict[str, bytes] = OrderedDict()


def publier(contenu: bytes) -> str:
    """Adresse à laquelle le navigateur récupère ce dossier (une seule fois)."""
    jeton = secrets.token_urlsafe(24)
    _apercus[jeton] = contenu
    while len(_apercus) > NB_APERCUS_EN_MEMOIRE:
        _apercus.popitem(last=False)
    return f"/apercu-dossier/{jeton}"


@app.get("/apercu-dossier/{jeton}")
def _servir(jeton: str) -> Response:
    contenu = _apercus.pop(jeton, None)
    if contenu is None:
        raise HTTPException(status_code=404)
    return Response(contenu, media_type=TYPE_DOCX, headers={"Cache-Control": "no-store"})


SCRIPT = """
<script>
window.afficherApercuDossier = async function (url, id, pagesLisibles) {
  const charger = (src) => new Promise((ok, ko) => {
    const s = document.createElement('script');
    s.src = src; s.onload = ok; s.onerror = () => ko(new Error('Chargement impossible : ' + src));
    document.head.appendChild(s);
  });
  if (!window.JSZip) await charger('https://cdn.jsdelivr.net/npm/jszip@3.10.1/dist/jszip.min.js');
  if (!window.docx) await charger('https://cdn.jsdelivr.net/npm/docx-preview@0.4.1/dist/docx-preview.min.js');
  const cible = document.getElementById(id);
  const contenu = await (await fetch(url)).arrayBuffer();
  cible.innerHTML = '';
  await docx.renderAsync(contenu, cible, cible, {
    className: 'docx', inWrapper: false, breakPages: true, ignoreLastRenderedPageBreak: true,
    renderHeaders: true, renderFooters: true, useBase64URL: true, experimental: false,
  });
  const pages = Array.from(cible.querySelectorAll('section.docx'));
  const ajuster = () => pages.forEach((page) => {
    page.style.zoom = '';
    page.style.zoom = Math.min(1, cible.clientWidth / page.offsetWidth);
  });
  ajuster();
  if (!cible._ajustement) { cible._ajustement = true; window.addEventListener('resize', ajuster); }
  if (pagesLisibles !== null) {
    pages.forEach((page, i) => { if (i >= pagesLisibles) page.classList.add('page-floutee'); });
  }
  return pages.length;
};
</script>
<style>
  .apercu-dossier { background: var(--c-fond); border-radius: 12px; padding: 12px; overflow: hidden; }
  .apercu-dossier section.docx { margin: 0 auto 14px; box-shadow: 0 1px 8px rgba(15, 23, 42, 0.18); }
  .apercu-dossier section.docx:last-child { margin-bottom: 0; }
  .apercu-dossier .page-floutee { filter: blur(7px); pointer-events: none; user-select: none; }
</style>
"""


def installer() -> None:
    """Fonction d'affichage de l'aperçu, à ajouter à la page."""
    ui.add_head_html(SCRIPT)
