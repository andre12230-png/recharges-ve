"""Les adresses ouvertes dans le navigateur par « Mise à jour » et
« Votre avis », et la version a coller dans le questionnaire.

Donnees pures, sans interface, lues par fenetres_aide.py. L'application ne
se connecte elle-meme a aucun serveur : elle ne fait que confier ces
adresses au navigateur (tests/test_aide_en_ligne.py).
"""

import platform

from constantes import APP_NAME, APP_VERSION

# « Votre avis » et « Mise à jour » dans le menu (et leur section de la
# notice). False du 22/10/2026 au 24/10/2026, tant que l'application restait
# chez son auteur. True depuis la préparation de la première publication
# (24/10/2026) : l'exe distribué doit les montrer.
AIDE_EN_LIGNE = True

# La page de la derniere version publiee, et son installeur a nom fixe.
# Ils visent le depot PUBLIC de l'application : tant qu'il n'est pas publie,
# ces liens ne menent pas encore a une nouvelle version. Un nom fixe, et non
# numerote, pour que le lien ne change jamais (comme le Photovoltaique).
PAGE_VERSIONS_URL = "https://github.com/andre12230-png/recharges-ve/releases/latest"
INSTALLEUR_URL = PAGE_VERSIONS_URL + "/download/Recharges-VE-Setup.exe"

# Questionnaire en ligne (Microsoft Forms « Recharges VE — votre avis »,
# cree le 15/09/2026 dans le compte de l'auteur, comme ceux de Pecule et du
# Photovoltaique). Vide, le bouton « Ouvrir le questionnaire » serait grise.
# Changer le lien = changer cette seule constante et republier.
FORMULAIRE_AVIS_URL = "https://forms.cloud.microsoft/r/3EvSX9YEBP"

# Ou trouver le prix du litre, pour la voiture essence de comparaison
# (Parametres, 19/10/2026). Deux sites officiels de l'Etat, aucun site prive :
# le prix station par station, et les moyennes nationales hebdomadaires et
# mensuelles du ministere (utiles pour le prix par annee).
PRIX_CARBURANTS_STATIONS_URL = "https://www.prix-carburants.gouv.fr/"
PRIX_CARBURANTS_MOYENNES_URL = (
    "https://www.ecologie.gouv.fr/politiques-publiques/"
    "prix-produits-petroliers")


def description_systeme() -> str:
    """Version de l'application et de Windows, a coller dans le
    questionnaire : c'est la premiere chose a savoir pour comprendre un
    probleme."""
    return f"{APP_NAME} {APP_VERSION} — Windows {platform.release()}"
