#!/bin/bash
# Construit "Credaura.app", une application macOS autonome :
# aucune installation de Python ni de dépendances n'est requise pour la
# lancer, il suffit de double-cliquer dessus.
#
# À relancer à chaque fois que le code de l'app change, pour mettre à jour
# l'application installée.
#
# Remarque technique : la construction se fait dans /tmp, puis l'app est
# installée directement dans /Applications (jamais dans le dossier du projet)
# — celui-ci est synchronisé par iCloud (Documents), qui retague en continu
# les fichiers avec des attributs (com.apple.provenance) que la signature de
# code refuse. Contrairement à ce qu'on pourrait penser, cela reste vrai même
# en copiant l'app déjà signée : tout fichier qui atterrit dans Documents se
# fait retaguer, signature ou non. D'où l'installation finale hors d'iCloud.
set -euo pipefail

cd "$(dirname "$0")"

if [ ! -d venv ]; then
    echo "Erreur : l'environnement virtuel 'venv' est introuvable. Créez-le d'abord (voir README)." >&2
    exit 1
fi

source venv/bin/activate


if ! python3 -c "import PyInstaller" 2>/dev/null; then
    echo "Installation de PyInstaller (outil de construction, pas une dépendance de l'app)..."
    python3 -m pip install pyinstaller
fi

BUILD_DIR="/tmp/immo-rentabilite-build"
rm -rf "$BUILD_DIR"
mkdir -p "$BUILD_DIR"

# iCloud (« optimiser le stockage ») retire en continu le contenu des fichiers
# du Mac quand le disque se remplit (fichiers « dataless ») ; PyInstaller les
# copiait vides (polices de 0 octet → erreur FT_Open_Face à la génération du
# dossier, le 28/10/2026). On construit donc à partir d'une copie hors iCloud,
# faite par rsync, qui lit chaque fichier et force iCloud à le retélécharger.
SRC_DIR="$BUILD_DIR/src"
mkdir -p "$SRC_DIR"
rsync -a --exclude "__pycache__" --exclude "data_cache" main.py app gui "$SRC_DIR/"
VIDES=$(find "$SRC_DIR" -type f -size 0 ! -name "__init__.py" || true)
if [ -n "$VIDES" ]; then
    echo "Erreur : fichiers vides après la copie (iCloud ?), construction annulée :" >&2
    echo "$VIDES" >&2
    exit 1
fi

NICEGUI_DIR="$(python3 -c 'import nicegui, os; print(os.path.dirname(nicegui.__file__))')"
# python-docx lit ses modèles d'en-tête/pied de page via « docx/parts/../templates » :
# le dossier docx/parts doit donc exister dans l'app, sinon Errno 2.
DOCX_DIR="$(python3 -c 'import docx, os; print(os.path.dirname(docx.__file__))')"

# Icône de l'application : le logo Credaura (app/visuels_dossier.logo), décliné
# dans les tailles attendues par macOS puis assemblé par iconutil.
ICONSET="$BUILD_DIR/Credaura.iconset"
mkdir -p "$ICONSET"
python3 - "$ICONSET" "$SRC_DIR" <<'PY'
import sys
from pathlib import Path
sys.path.insert(0, sys.argv[2])
from app.visuels_dossier import logo
dossier = Path(sys.argv[1])
for taille in (16, 32, 64, 128, 256, 512):
    (dossier / f"icon_{taille}x{taille}.png").write_bytes(logo(taille))
    (dossier / f"icon_{taille}x{taille}@2x.png").write_bytes(logo(taille * 2))
PY
iconutil -c icns "$ICONSET" -o "$BUILD_DIR/Credaura.icns"

echo "Construction en cours (plusieurs minutes, dépendances lourdes : pandas/pyarrow/matplotlib)..."
python3 -m PyInstaller \
    --name "Credaura" \
    --icon "$BUILD_DIR/Credaura.icns" \
    --windowed \
    --add-data "${NICEGUI_DIR}:nicegui" \
    --collect-data docx \
    --add-data "${DOCX_DIR}/parts/__init__.py:docx/parts" \
    --add-data "$SRC_DIR/app/data:app/data" \
    --add-data "$SRC_DIR/app/fonts:app/fonts" \
    --osx-bundle-identifier com.davidlehmann.credaura \
    --distpath "$BUILD_DIR/dist" \
    --workpath "$BUILD_DIR/build" \
    --specpath "$BUILD_DIR" \
    --noconfirm \
    "$SRC_DIR/main.py"

# Garde-fou : aucune police ni donnée vide dans l'app construite.
VIDES=$(find "$BUILD_DIR/dist/Credaura.app/Contents/Resources/app" -type f -size 0 | grep -v "__init__.py" || true)
if [ -n "$VIDES" ]; then
    echo "Erreur : fichiers vides dans l'app (iCloud ?), installation annulée :" >&2
    echo "$VIDES" >&2
    exit 1
fi

INSTALL_PATH="/Applications/Credaura.app"
# Anciens noms de l'application (avant le passage à la marque Credaura).
rm -rf "/Applications/Simulateur Immobilier.app" "/Applications/Fiabimmo.app"
rm -rf "$INSTALL_PATH"
cp -R "$BUILD_DIR/dist/Credaura.app" "$INSTALL_PATH"
xattr -cr "$INSTALL_PATH" || true

echo
echo "Terminé : $INSTALL_PATH"
echo
echo "Premier lancement (ou après chaque reconstruction, l'app étant considérée comme"
echo "nouvelle par macOS) : un avertissement de sécurité peut s'afficher. Fais un clic"
echo "droit sur l'app > Ouvrir, puis confirme — nécessaire une seule fois par version."
