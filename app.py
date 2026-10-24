r"""Recharges VE : point d'entree de l'application.

Depuis la 2.0.0, l'interface est en PySide6 (Qt) : la fenetre est dans
fenetre.py, les pages dans pages/. Ce fichier ne fait que la lancer ; il
garde son nom parce que la construction de l'exe (build.bat) et la
documentation partent de lui.

    py app.py                                  l'application
    py app.py --autotest C:\chemin\rapport.txt   toutes les pages et les
                                               exports, sur un jeu de
                                               demonstration (voir
                                               fenetre.autotest)
"""

import sys

import theme_qt

# Tout premier lancement : demander Clair ou Sombre avant d'ouvrir la
# fenetre (16/10/2026, voir premier_theme.py). Seulement quand l'application
# est lancee pour de vrai : ni a l'autotest (personne devant l'ecran), ni
# quand un test importe ce fichier.
if __name__ == "__main__" and "--autotest" not in sys.argv:
    import premier_theme
    premier_theme.demander_au_premier_lancement()

# Le theme choisi dans Parametres (Clair ou Sombre, 12/10/2026) : AVANT
# d'importer la fenetre et les pages, qui prennent leurs couleurs au moment
# ou elles sont importees. Les preferences se lisent sans QApplication.
theme_qt.choisir_theme(theme_qt.nom_du_theme(theme_qt.preferences()))

from fenetre import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main())
