"""La fenetre « Quelles colonnes ? » (28/09/2026) : importer l'export d'une
borne qui n'a pas le format d'origine.

Elle montre les premieres lignes du fichier, et une liste par information
utile (debut, fin ou duree, energie et son unite, cout annonce par la
borne), pre-remplie avec ce que recharges.deviner_correspondance a pu
deviner des titres. Le choix est verifie par recharges.
verifier_correspondance ; la page Importer le retient ensuite pour les
fichiers suivants du meme modele.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QComboBox, QDialog, QDialogButtonBox,
                               QGridLayout, QLabel, QTableWidget,
                               QTableWidgetItem, QVBoxLayout, QWidget)

from erreurs import erreur_en_clair
from recharges import deviner_correspondance, verifier_correspondance

AUCUNE = "(aucune)"

# (cle, libelle, aide) : dans l'ordre de la fenetre.
CHAMPS = (
    ("debut", "Début de la recharge", "obligatoire"),
    ("fin", "Fin de la recharge", "la fin OU la durée"),
    ("duree", "Durée", "si le fichier n'a pas l'heure de fin"),
    ("kwh", "Énergie", "obligatoire"),
    ("cout", "Coût annoncé par la borne", "facultatif"),
)


class DialogueColonnes(QDialog):
    def __init__(self, parent, apercu: dict):
        super().__init__(parent)
        self.apercu = apercu
        self.setWindowTitle("Colonnes du fichier")
        if parent is not None:
            self.setWindowIcon(parent.windowIcon())
        self.setMinimumWidth(620)

        colonne = QVBoxLayout(self)
        colonne.setContentsMargins(0, 0, 0, 12)
        cases = QWidget()
        cases.setObjectName("Formulaire")
        cases.setAttribute(Qt.WA_StyledBackground, True)
        disposition = QVBoxLayout(cases)
        disposition.setContentsMargins(16, 8, 16, 12)
        disposition.setSpacing(6)

        titre = QLabel("Quelle colonne contient quoi ?")
        titre.setObjectName("TitreDialogue")
        disposition.addWidget(titre)
        aide = QLabel(
            "Ce fichier ne vient pas d'une borne que l'application connaît. "
            "Voici ses premières lignes : indiquez les colonnes du début, de "
            "la fin (ou de la durée) et de l'énergie. Ce choix sera retenu "
            "pour les prochains fichiers du même modèle.")
        aide.setObjectName("Discret")
        aide.setWordWrap(True)
        disposition.addWidget(aide)

        # Les premieres lignes du fichier, telles quelles.
        entetes = apercu["entetes"]
        tableau = QTableWidget(len(apercu["lignes"]), len(entetes))
        tableau.setHorizontalHeaderLabels(entetes)
        tableau.setEditTriggers(QTableWidget.NoEditTriggers)
        tableau.verticalHeader().setVisible(False)
        for i, ligne in enumerate(apercu["lignes"]):
            for j, valeur in enumerate(ligne[:len(entetes)]):
                tableau.setItem(i, j, QTableWidgetItem(valeur))
        tableau.resizeColumnsToContents()
        tableau.setMaximumHeight(170)
        disposition.addWidget(tableau)

        # Une liste par information, pre-remplie avec ce qui a ete devine.
        devine = deviner_correspondance(apercu)
        grille = QGridLayout()
        grille.setHorizontalSpacing(10)
        self.choix: dict[str, QComboBox] = {}
        for rang, (cle, libelle, precision) in enumerate(CHAMPS):
            etiquette = QLabel(libelle)
            etiquette.setObjectName("LibelleChamp")
            grille.addWidget(etiquette, rang, 0)
            liste = QComboBox()
            liste.addItems([AUCUNE, *entetes])
            if devine.get(cle) is not None:
                liste.setCurrentIndex(devine[cle] + 1)
            grille.addWidget(liste, rang, 1)
            note = QLabel(precision)
            note.setObjectName("Discret")
            grille.addWidget(note, rang, 2)
            self.choix[cle] = liste
        unite = QComboBox()
        unite.addItems(["kWh", "Wh"])
        unite.setCurrentText(devine.get("unite") or "kWh")
        grille.addWidget(unite, 3, 2)                 # a cote de l'energie
        self.choix["unite"] = unite
        grille.setColumnStretch(1, 1)
        disposition.addLayout(grille)
        disposition.addStretch(1)
        colonne.addWidget(cases, 1)

        self.message = QLabel("")
        self.message.setObjectName("MessageChamp")
        self.message.setWordWrap(True)
        self.message.setContentsMargins(16, 6, 16, 0)
        self.message.hide()
        colonne.addWidget(self.message)

        boutons = QDialogButtonBox()
        importer = boutons.addButton("Importer", QDialogButtonBox.AcceptRole)
        importer.setObjectName("BoutonEnregistrer")
        importer.setDefault(True)
        annuler = boutons.addButton("Annuler", QDialogButtonBox.RejectRole)
        annuler.setAutoDefault(False)
        boutons.accepted.connect(self.valider)
        boutons.rejected.connect(self.reject)
        boutons.setContentsMargins(16, 6, 16, 0)
        colonne.addWidget(boutons)

    def correspondance(self) -> dict:
        """Le choix de l'utilisateur : le numero de chaque colonne (None pour
        « (aucune) ») et l'unite de l'energie."""
        choix = {cle: (self.choix[cle].currentIndex() - 1
                       if self.choix[cle].currentIndex() > 0 else None)
                 for cle, _, _ in CHAMPS}
        choix["unite"] = self.choix["unite"].currentText()
        return choix

    def valider(self) -> None:
        """« Importer » : refuse, en le disant, s'il manque une colonne."""
        try:
            verifier_correspondance(self.correspondance())
        except ValueError as e:
            self.message.setText(erreur_en_clair(e))
            self.message.show()
            return
        self.accept()
