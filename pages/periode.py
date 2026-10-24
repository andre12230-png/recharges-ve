"""Barre de selection de la periode de la version PySide6.

La barre de Pecule (comptesbudget/ui/widgets.py, PeriodBar) branchee sur la
logique de periode de Recharges VE (filtres.py), qui ne change pas : les
valeurs manipulees restent « Tout », « 30 derniers jours », « 2025 »,
« Juin 2026 », que filtrer_par_periode a toujours comprises.

    Période :  ‹  [annee]  [mois]  ›  [Ce mois-ci]

`annuel=True` (page Statistiques) : pas de menu des mois, bouton
« Cette année », fleches et raccourcis qui avancent d'une annee.

Raccourcis, comme dans Pecule et le Photovoltaique : Ctrl+Gauche (periode
precedente), Ctrl+Droite (suivante), Ctrl+Origine (mois en cours). Ils
appartiennent a la barre : quand la page change, ils disparaissent avec
elle. Dans une case de saisie, Ctrl+Gauche / Ctrl+Droite gardent leur role
habituel (sauter d'un mot).
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (QAbstractSpinBox, QApplication, QComboBox,
                               QHBoxLayout, QLabel, QLineEdit, QPlainTextEdit,
                               QPushButton, QTextEdit, QWidget)

from filtres import (TOUTE_ANNEE, annee_de_periode, annee_en_cours,
                     annees_disponibles, libelle_mois, mois_disponibles,
                     mois_en_cours, nom_du_mois, periode_par_raccourci,
                     periode_voisine)

# Nom affiche d'une valeur du menu des annees, quand il differe d'elle.
NOMS_AFFICHES = {"Tout": "Toute la période"}


class BarrePeriode(QWidget):
    """La barre de periode. Emet `periode_changee(valeur)` quand
    l'utilisateur choisit une autre periode ; c'est a la page de ranger la
    valeur et de se reconstruire."""

    periode_changee = Signal(str)

    def __init__(self, recharges: list[dict], periode: str,
                 annuel: bool = False, parent=None):
        super().__init__(parent)
        self.recharges = recharges
        self.annuel = annuel
        annee = annee_de_periode(periode)
        mois = nom_du_mois(periode)
        if annuel and mois is not None:
            # Un mois n'a pas cours ici : on montre et on parcourt son annee.
            periode, mois = annee, None
        self.periode = periode
        self._mois = mois

        rangee = QHBoxLayout(self)
        rangee.setContentsMargins(0, 0, 0, 0)
        rangee.setSpacing(4)
        libelle = QLabel("Période :")
        libelle.setObjectName("LibellePeriode")
        rangee.addWidget(libelle)

        self.fleche_precedente = self._fleche(
            "‹", periode_voisine(recharges, periode, -1),
            "Période précédente (Ctrl+←)")
        rangee.addWidget(self.fleche_precedente)

        self.menu_annee = QComboBox()
        self.menu_annee.setMinimumWidth(130)
        # Chaque ligne garde sa valeur (« Tout », « 2026 »...) ; seul le nom
        # affiche peut differer : « Toute la periode », le nom commun aux
        # trois applis (choix de l'auteur du 08/10/2026).
        for valeur in annees_disponibles(recharges):
            self.menu_annee.addItem(NOMS_AFFICHES.get(valeur, valeur), valeur)
        # Sur un raccourci (« Tout »), c'est le raccourci lui-meme qui s'affiche.
        self.menu_annee.setCurrentIndex(self.menu_annee.findData(
            annee if annee is not None else periode))
        self.menu_annee.activated.connect(
            lambda i: self._changer_annee(self.menu_annee.itemData(i)))
        rangee.addWidget(self.menu_annee)

        self.menu_mois = None               # repere pour les tests
        if not annuel:
            self.menu_mois = QComboBox()
            self.menu_mois.setMinimumWidth(115)
            self.menu_mois.addItems(mois_disponibles(recharges, annee)
                                    if annee else [TOUTE_ANNEE])
            self.menu_mois.setCurrentText(mois if mois is not None
                                          else TOUTE_ANNEE)
            self.menu_mois.textActivated.connect(self._changer_mois)
            # « Tout » et « 30 derniers jours » ne se decoupent pas en mois :
            # le menu reste visible mais grise, sinon la barre sauterait d'un
            # choix a l'autre.
            self.menu_mois.setEnabled(annee is not None)
            rangee.addWidget(self.menu_mois)

        self.fleche_suivante = self._fleche(
            "›", periode_voisine(recharges, periode, +1),
            "Période suivante (Ctrl+→)")
        rangee.addWidget(self.fleche_suivante)

        # Retour au mois (a l'annee) en cours en un clic. Grise quand on y est
        # deja : il dit alors aussi qu'on regarde bien le present.
        courant = annee_en_cours() if annuel else mois_en_cours()
        self.bouton_ce_mois = QPushButton("Cette année" if annuel
                                          else "Ce mois-ci")
        self.bouton_ce_mois.setToolTip(
            "Revenir à l'année en cours" if annuel
            else "Revenir au mois en cours (Ctrl+Origine)")
        self.bouton_ce_mois.setEnabled(periode != courant)
        self.bouton_ce_mois.clicked.connect(lambda: self._choisir(courant))
        rangee.addSpacing(6)
        rangee.addWidget(self.bouton_ce_mois)
        rangee.addStretch(1)

        self.raccourcis = []
        for touches, sens in (("Ctrl+Left", -1), ("Ctrl+Right", +1),
                              ("Ctrl+Home", 0)):
            raccourci = QShortcut(QKeySequence(touches), self)
            # Actif dans toute la fenetre, pas seulement quand la barre a le
            # curseur : sinon il ne servirait presque jamais.
            raccourci.setContext(Qt.WindowShortcut)
            raccourci.activated.connect(lambda s=sens: self._raccourci(s))
            self.raccourcis.append(raccourci)

    # ---------- construction ----------

    def _fleche(self, signe: str, cible: str | None,
                aide: str) -> QPushButton:
        """Un des deux boutons de navigation. Sans cible (plus rien de ce
        cote), il est grise plutot que cliquable sans effet, ce qui ferait
        croire a une panne."""
        bouton = QPushButton(signe)
        bouton.setObjectName("FlechePeriode")
        bouton.setToolTip(aide)
        bouton.setAutoDefault(False)
        bouton.setEnabled(cible is not None)
        if cible is not None:
            bouton.clicked.connect(lambda: self._choisir(cible))
        return bouton

    # ---------- actions ----------

    def _choisir(self, valeur: str) -> None:
        """Annonce la nouvelle periode. (La page qui l'ecoute se reconstruit
        un instant plus tard, voir FenetrePrincipale.changer_periode : cette
        barre sera alors detruite, ce qui ne doit pas arriver pendant qu'elle
        traite encore le clic.)"""
        if valeur and valeur != self.periode:
            self.periode_changee.emit(valeur)

    def _changer_annee(self, valeur: str) -> None:
        """On garde le mois affiche s'il existe dans la nouvelle annee :
        c'est ce qu'on veut pour comparer un mois d'une annee sur l'autre.
        Sinon on montre l'annee entiere plutot qu'un ecran vide."""
        if annee_de_periode(valeur) is None:
            self._choisir(valeur)       # un raccourci : « Tout », « 30 derniers jours »
        elif (not self.annuel and self._mois is not None
              and self._mois in mois_disponibles(self.recharges, valeur)):
            self._choisir(libelle_mois(valeur, self._mois))
        else:
            self._choisir(valeur)

    def _changer_mois(self, valeur: str) -> None:
        annee = annee_de_periode(self.periode)
        if annee is None:
            self._choisir("Tout")
        elif valeur == TOUTE_ANNEE:
            self._choisir(annee)
        else:
            self._choisir(libelle_mois(annee, valeur))

    def _raccourci(self, sens: int) -> None:
        """Ctrl+Gauche / Ctrl+Droite / Ctrl+Origine.

        Dans une case de saisie, ces touches servent a se deplacer dans le
        texte : on les lui rend (le raccourci les a captees avant elle)."""
        champ = QApplication.focusWidget()
        if isinstance(champ, QLineEdit):
            if sens < 0:
                champ.cursorWordBackward(False)
            elif sens > 0:
                champ.cursorWordForward(False)
            else:
                champ.home(False)
            return
        if isinstance(champ, (QTextEdit, QPlainTextEdit, QAbstractSpinBox)):
            return
        cible = periode_par_raccourci(self.recharges, self.periode, sens,
                                      annuel=self.annuel)
        if cible:
            self._choisir(cible)
