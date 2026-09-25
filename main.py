"""Point d'entrée de l'application. Lance une fenêtre native par défaut ;
utiliser --web (ou IMMO_WEB_MODE=1) pour l'ouvrir dans un navigateur."""
import multiprocessing
import os
import sys
from pathlib import Path

if getattr(sys, "frozen", False):
    # PyInstaller force par défaut un dossier de cache matplotlib temporaire,
    # recréé à chaque lancement (pertinent pour --onefile, où le chemin
    # d'extraction change à chaque fois ; inutile ici en --onedir, où le
    # dossier de l'app est stable). Sans cette correction, matplotlib
    # reconstruit tout son cache de polices — opération lente — à CHAQUE
    # démarrage au lieu d'une seule fois. Doit s'exécuter avant tout import
    # de nicegui (qui importe matplotlib dès son propre chargement).
    _mpl_cache = Path.home() / "Library" / "Caches" / "Simulateur Immobilier" / "matplotlib"
    _mpl_cache.mkdir(parents=True, exist_ok=True)
    os.environ["MPLCONFIGDIR"] = str(_mpl_cache)

if __name__ == "__main__":
    # Requis pour les applications packagées (PyInstaller) : sur macOS/Windows,
    # multiprocessing relance l'exécutable pour chaque sous-processus interne
    # (ex. resource_tracker). Sans freeze_support() ET sans différer l'import
    # de gui.main (qui entraîne nicegui/pandas/pyarrow/matplotlib) après ce
    # garde, chaque sous-processus réimporterait toute l'application avant de
    # comprendre qu'il ne doit exécuter que son propre payload — provoquant un
    # nombre croissant de processus au démarrage.
    multiprocessing.freeze_support()
    from gui.main import main

    main()
