"""La notice d'utilisation (version PySide6).

Le texte vit dans notice_texte.py, sans interface : cette page ne fait que
le mettre en cartes, une par section.
"""

from __future__ import annotations

from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

from composants import carte, paragraphe, texte_a_lire
from constantes import APP_VERSION
from notice_texte import SECTIONS
from recharges import dossier_donnees


def construire(fenetre) -> QWidget:
    page = QWidget()
    colonne = QVBoxLayout(page)
    colonne.setContentsMargins(0, 0, 0, 0)
    colonne.setSpacing(12)

    for titre, paragraphes in SECTIONS:
        cadre, corps = carte(titre)
        for intitule, texte in paragraphes:
            if intitule:
                gras = QLabel(intitule)
                gras.setStyleSheet("font-weight: bold;")
                corps.addWidget(gras)
            corps.addWidget(texte_a_lire(texte))
        colonne.addWidget(cadre)

    # Version et emplacement REEL des donnees : lu a l'affichage, jamais
    # ecrit en dur (il change selon qu'on tourne depuis les sources ou en .exe).
    colonne.addWidget(paragraphe(
        f"Recharges VE {APP_VERSION}   ·   vos données : {dossier_donnees()}",
        "Discret"))
    colonne.addStretch(1)
    return page
