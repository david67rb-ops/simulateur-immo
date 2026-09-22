"""Point d'entrée de l'application. Lance une fenêtre native par défaut ;
utiliser --web (ou IMMO_WEB_MODE=1) pour l'ouvrir dans un navigateur."""
from gui.main import main

if __name__ == "__main__":
    main()
