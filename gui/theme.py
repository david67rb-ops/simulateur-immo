"""Thème visuel de l'application : couleurs, typographie, composants stylés
réutilisables. Look moderne (cartes arrondies, palette verte, police Inter)."""
from __future__ import annotations

from nicegui import ui

PRIMARY = "#1d6f5c"
PRIMARY_DARK = "#14503f"
ACCENT = "#c9822a"
POSITIVE = "#1d6f5c"
NEGATIVE = "#d1453b"

# Logo : silhouette de maison + courbe ascendante (rentabilité), deux couleurs
# de la palette de l'app. Badge à coins arrondis, dans l'esprit d'une icône
# d'app moderne plutôt qu'un pictogramme emoji.
LOGO_SVG = f"""
<svg width="38" height="38" viewBox="0 0 64 64" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="Logo Simulateur de rentabilité immobilier">
  <rect width="64" height="64" rx="16" fill="{PRIMARY}"/>
  <path d="M32 13 L49 27.5 V47 H15 V27.5 Z" fill="#FFFFFF"/>
  <rect x="27" y="35" width="10" height="12" fill="{PRIMARY}"/>
  <polyline points="13,42 24,29 32,34 47,16" fill="none" stroke="{ACCENT}" stroke-width="3.4" stroke-linecap="round" stroke-linejoin="round"/>
  <polygon points="47,16 39,17.5 45.5,23" fill="{ACCENT}"/>
</svg>
""".strip()

CARD_CLASSES = "w-full rounded-2xl shadow-sm border border-[#e3e5e8] dark:border-[#2c3036] p-5 md:p-6"
SECTION_TITLE_CLASSES = "text-xl font-semibold mb-1"
SUBSECTION_TITLE_CLASSES = "text-sm font-semibold uppercase tracking-wide text-[color:var(--primary-color)] mt-2 mb-1"
HINT_CLASSES = "text-xs text-gray-500 dark:text-gray-400"
GRID_CLASSES = "w-full grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4"


def apply_theme() -> None:
    ui.colors(
        primary=PRIMARY,
        secondary=PRIMARY_DARK,
        accent=ACCENT,
        positive=POSITIVE,
        negative=NEGATIVE,
        dark="#14161a",
        dark_page="#0f1113",
    )
    ui.add_head_html(
        """
        <link rel="preconnect" href="https://fonts.googleapis.com">
        <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
        <style>
          :root { --primary-color: #1d6f5c; }
          html, body { background: #f5f6f8 !important; color-scheme: light; }
          body.body--dark { background: #14161a !important; color-scheme: dark; }
          body, .q-field, .q-btn { font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif !important; }
          .q-card { transition: box-shadow .15s ease; }
          .q-btn { border-radius: 10px !important; font-weight: 600 !important; text-transform: none !important; }
          .q-field--outlined .q-field__control { border-radius: 10px !important; }
          .stat-card { background: var(--stat-bg, #eef6f3); border-radius: 14px; padding: 14px 16px; }
          .body--dark .stat-card { --stat-bg: #1a2b26; }
        </style>
        """
    )


def stat_card(label: str, initial: str = "–") -> ui.label:
    """Petite carte 'métrique' (fond teinté, valeur en gros). Renvoie le label
    de valeur pour pouvoir le mettre à jour ensuite (`.set_text(...)`)."""
    with ui.column().classes("stat-card gap-0"):
        ui.label(label).classes("text-xs text-gray-500 dark:text-gray-400")
        value = ui.label(initial).classes("text-xl font-bold").style(f"color: {PRIMARY}")
    return value


def section_card():
    """Contexte 'carte' standard pour une section de la page."""
    return ui.card().classes(CARD_CLASSES)


def subsection_title(text: str) -> None:
    ui.label(text).classes(SUBSECTION_TITLE_CLASSES)
