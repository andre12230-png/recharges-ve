"""Les pages de l'application, une par fichier.

Chaque page expose `construire(fenetre) -> QWidget` : elle recoit la fenetre
principale (pour lire les filtres de periode, rafraichir le total...) et rend
le contenu a afficher.
"""

from pages import (ajouter, essence, exporter, historique, importer,
                   kilometrage, notice, parametres, restaurer, statistiques,
                   tableau_de_bord, tarifs)

# Identifiant de la page -> fonction qui la construit. Toutes les pages du
# menu (menu.py) doivent y etre : tests/test_menu.py le verifie.
CONSTRUCTEURS = {
    "dashboard": tableau_de_bord.construire,
    "ajouter": ajouter.construire,
    "historique": historique.construire,
    "stats": statistiques.construire,
    "km": kilometrage.construire,
    "essence": essence.construire,
    "import": importer.construire,
    "export": exporter.construire,
    "tarifs": tarifs.construire,
    "parametres": parametres.construire,
    "notice": notice.construire,
    "restaurer": restaurer.construire,
}
