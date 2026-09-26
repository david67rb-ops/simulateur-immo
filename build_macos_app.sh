#!/bin/bash
# Construit "Simulateur Immobilier.app", une application macOS autonome :
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

NICEGUI_DIR="$(python3 -c 'import nicegui, os; print(os.path.dirname(nicegui.__file__))')"
# python-docx lit ses modèles d'en-tête/pied de page via « docx/parts/../templates » :
# le dossier docx/parts doit donc exister dans l'app, sinon Errno 2.
DOCX_DIR="$(python3 -c 'import docx, os; print(os.path.dirname(docx.__file__))')"

echo "Construction en cours (plusieurs minutes, dépendances lourdes : pandas/pyarrow/matplotlib)..."
python3 -m PyInstaller \
    --name "Simulateur Immobilier" \
    --windowed \
    --add-data "${NICEGUI_DIR}:nicegui" \
    --collect-data docx \
    --add-data "${DOCX_DIR}/parts/__init__.py:docx/parts" \
    --osx-bundle-identifier com.davidlehmann.simulateurimmo \
    --distpath "$BUILD_DIR/dist" \
    --workpath "$BUILD_DIR/build" \
    --noconfirm \
    main.py

INSTALL_PATH="/Applications/Simulateur Immobilier.app"
rm -rf "$INSTALL_PATH"
cp -R "$BUILD_DIR/dist/Simulateur Immobilier.app" "$INSTALL_PATH"
xattr -cr "$INSTALL_PATH" || true

echo
echo "Terminé : $INSTALL_PATH"
echo
echo "Premier lancement (ou après chaque reconstruction, l'app étant considérée comme"
echo "nouvelle par macOS) : un avertissement de sécurité peut s'afficher. Fais un clic"
echo "droit sur l'app > Ouvrir, puis confirme — nécessaire une seule fois par version."
