"""Fenetres « Mise à jour » et « Votre avis » de la version PySide6.

Reprises de Pecule et du Photovoltaique, avec les textes et les adresses de
Recharges VE (liens.py). Les deux passent par le navigateur : l'application
ne se connecte elle-meme a aucun serveur (tests/test_aide_en_ligne.py).
"""

from __future__ import annotations

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices, QGuiApplication, QIcon
from PySide6.QtWidgets import (QDialog, QHBoxLayout, QLabel, QPushButton,
                               QVBoxLayout)

from constantes import (APP_NAME, APP_VERSION, COPYRIGHT_TITULAIRE,
                        chemin_ressource)
from liens import (DEPOT_URL, FORMULAIRE_AVIS_URL, INSTALLEUR_URL,
                   PAGE_VERSIONS_URL, description_systeme)
from theme_qt import ROUGE


def _texte(texte: str, gras: bool = False) -> QLabel:
    etiquette = QLabel(texte)
    etiquette.setWordWrap(True)
    if gras:
        etiquette.setStyleSheet("font-weight: bold;")
    return etiquette


class _FenetreNavigateur(QDialog):
    """Base commune : quelques paragraphes, une ligne de confirmation verte,
    et une rangee de boutons en bas a droite. Echap ferme (comportement
    standard d'une fenetre de dialogue Qt)."""

    def __init__(self, parent, titre: str):
        super().__init__(parent)
        self.setWindowTitle(titre)
        self.setModal(True)
        self.setMinimumWidth(520)
        self.disposition = QVBoxLayout(self)
        self.disposition.setContentsMargins(22, 20, 22, 20)
        self.disposition.setSpacing(8)

    def _finir(self, boutons: list[QPushButton]) -> None:
        # Confirmation affichee une fois le navigateur sollicite.
        self.confirmation = QLabel("")
        self.confirmation.setObjectName("Confirmation")
        self.confirmation.setWordWrap(True)
        self.disposition.addWidget(self.confirmation)
        self.disposition.addStretch(1)
        rangee = QHBoxLayout()
        rangee.addStretch(1)
        for bouton in boutons:
            rangee.addWidget(bouton)
        fermer = QPushButton("Fermer")
        fermer.clicked.connect(self.reject)
        rangee.addWidget(fermer)
        self.disposition.addLayout(rangee)

    def _ouvrir(self, adresse: str, message: str) -> None:
        """Confie l'adresse au navigateur : l'application, elle, ne
        telecharge rien.

        Si Windows n'a pas pu ouvrir le navigateur, la fenetre le dit et
        donne l'adresse, copiee pour etre collee. Avant, elle annoncait la
        page ouverte sans le verifier (second audit du 16/10/2026)."""
        if QDesktopServices.openUrl(QUrl(adresse)):
            self.confirmation.setStyleSheet("")      # le vert du theme
            self.confirmation.setText(message)
            return
        QGuiApplication.clipboard().setText(adresse)
        self.confirmation.setStyleSheet(f"color: {ROUGE};")
        self.confirmation.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.confirmation.setText(
            "Windows n'a pas pu ouvrir votre navigateur. L'adresse est "
            "copiée : collez-la (Ctrl+V) dans la barre d'adresse de votre "
            f"navigateur.\n{adresse}")


class FenetreMiseAJour(_FenetreNavigateur):
    """Fenetre ouverte par le bouton « Mise à jour » du menu de gauche.

    L'application ne verifie pas d'elle-meme s'il existe une nouvelle
    version : c'est l'utilisateur qui compare les numeros."""

    def __init__(self, parent=None):
        super().__init__(parent, "Rechercher une mise à jour")
        self.disposition.addWidget(
            _texte(f"Vous utilisez {APP_NAME} {APP_VERSION}.", gras=True))
        for texte in (
                "L'application ne vérifie pas toute seule qu'une nouvelle "
                "version existe.",
                "« Voir les nouveautés » ouvre dans votre navigateur la page "
                "de la dernière version. Si son numéro est plus grand que le "
                "vôtre, une mise à jour vous attend.",
                "« Télécharger l'installeur » récupère directement la "
                "dernière version. Fermez l'application avant de le lancer : "
                "vos données ne sont pas touchées."):
            self.disposition.addWidget(_texte(texte))
        nouveautes = QPushButton("🌐 Voir les nouveautés")
        nouveautes.setDefault(True)
        nouveautes.clicked.connect(lambda: self._ouvrir(
            PAGE_VERSIONS_URL,
            "✓ Page des nouveautés ouverte dans votre navigateur."))
        installeur = QPushButton("⬇  Télécharger l'installeur")
        installeur.clicked.connect(lambda: self._ouvrir(
            INSTALLEUR_URL,
            "✓ Téléchargement lancé dans votre navigateur. Fermez "
            "l'application avant de lancer l'installeur."))
        self._finir([nouveautes, installeur])


class FenetreAPropos(_FenetreNavigateur):
    """Fenetre « À propos » : version, licence, auteur, depot.

    Meme fenetre que dans Pecule et le Photovoltaique. Ouverte par un clic sur
    le numero de version, en bas du bandeau de gauche. Rien n'est envoye
    nulle part : la page du projet ne s'ouvre que si l'on clique le bouton."""

    def __init__(self, parent=None):
        super().__init__(parent, f"À propos de {APP_NAME}")
        self.setMinimumWidth(440)
        # Logo : l'icone de l'application, si le fichier est la.
        icone = chemin_ressource("icone_voiture.ico")
        if icone.is_file():
            logo = QLabel()
            logo.setPixmap(QIcon(str(icone)).pixmap(64, 64))
            logo.setAlignment(Qt.AlignCenter)
            self.disposition.addWidget(logo)
        titre = _texte(APP_NAME, gras=True)
        titre.setStyleSheet("font-weight: bold; font-size: 16pt;")
        for etiquette, texte in (
                (titre, None),
                (_texte(f"Version {APP_VERSION}"), None),
                (_texte("Recharges VE suit le coût réel des recharges de "
                        "votre véhicule électrique, sur votre ordinateur. "
                        "Il est écrit en Python et bâti avec PySide6 (Qt). "
                        "Il ne se connecte à aucun serveur : vos données "
                        "restent chez vous."), None),
                (_texte(f"Copyright © {COPYRIGHT_TITULAIRE}", gras=True), None),
                (_texte("Ce logiciel est fourni sans aucune garantie, dans "
                        "la mesure permise par la loi."), None),
                (_texte("Logiciel libre, sous licence MIT."), None)):
            etiquette.setAlignment(Qt.AlignCenter)
            self.disposition.addWidget(etiquette)
        self.btn_depot = QPushButton("🌐 Page du projet sur GitHub")
        self.btn_depot.clicked.connect(lambda: self._ouvrir(
            DEPOT_URL, "✓ Page du projet ouverte dans votre navigateur."))
        self._finir([self.btn_depot])


class FenetreAvis(_FenetreNavigateur):
    """Fenetre ouverte par le bouton « Votre avis » du menu de gauche."""

    def __init__(self, parent=None):
        super().__init__(parent, f"Votre avis sur {APP_NAME}")
        self.disposition.addWidget(_texte(
            "Un problème à l'installation, un calcul qui vous surprend, une "
            "idée pour faire mieux ? Dites-le : c'est ainsi que "
            "l'application s'améliore."))
        if FORMULAIRE_AVIS_URL:
            consigne = ("Le questionnaire s'ouvre dans votre navigateur. Il "
                        "prend deux minutes et aucune réponse n'est "
                        "obligatoire. Votre version sera copiée pour vous : "
                        "collez-la (Ctrl+V) dans la question « Votre "
                        "version ».")
        else:
            consigne = ("Le questionnaire n'est pas encore en ligne : il "
                        "arrivera avec la version publique de "
                        "l'application.")
        self.disposition.addWidget(_texte(consigne))
        self.disposition.addWidget(
            _texte(f"Votre version : {description_systeme()}", gras=True))
        self.btn_ouvrir = QPushButton("Ouvrir le questionnaire")
        self.btn_ouvrir.setDefault(True)
        # Tant que le lien n'existe pas, le bouton ne ferait rien.
        self.btn_ouvrir.setEnabled(bool(FORMULAIRE_AVIS_URL))
        self.btn_ouvrir.clicked.connect(self._ouvrir_questionnaire)
        self._finir([self.btn_ouvrir])

    def _ouvrir_questionnaire(self) -> None:
        """Copie la version dans le presse-papiers, puis ouvre le
        questionnaire dans le navigateur."""
        QGuiApplication.clipboard().setText(description_systeme())
        self._ouvrir(FORMULAIRE_AVIS_URL,
                     "✓ Questionnaire ouvert dans votre navigateur, version "
                     "copiée. Merci !")
