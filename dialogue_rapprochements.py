"""La fenêtre « Recharges à vérifier » (audit indépendant du 04/11/2026, T1).

À l'import du fichier d'une borne, une ligne peut ressembler à une recharge
saisie à la main sans en être sûrement la même : proche dans le temps mais
sans recouvrement, plusieurs saisies candidates, ou la même plage horaire
avec une énergie trop différente. Avant, la saisie était remplacée d'office,
même par une AUTRE session. Cette fenêtre montre chaque cas AVANT toute
écriture, et laisse choisir :

- Garder les deux (par défaut : rien n'est perdu) ;
- Remplacer ma saisie par la ligne du fichier ;
- Ignorer la ligne du fichier (garder seulement ma saisie).

« Annuler l'import » n'enregistre rien.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QComboBox, QDialog, QDialogButtonBox,
                               QGridLayout, QLabel, QScrollArea, QVBoxLayout,
                               QWidget)

from formats import fmt_date_fr, fmt_kwh
from recharges import GARDER_LES_DEUX, IGNORER_LA_LIGNE


def _heure(iso: str | None) -> str:
    """« 11:30 » d'une date ISO, ou « ? » si elle manque."""
    return iso[11:16] if iso and len(iso) >= 16 else "?"


def decrire(recharge: dict) -> str:
    """« 01/03/2026 11:30 → 11:45, 1,05 kWh » (sans fin : « 01/03/2026
    11:30, 1,05 kWh »)."""
    texte = fmt_date_fr(recharge["date"])
    if recharge.get("fin"):
        texte += f" → {_heure(recharge['fin'])}"
    return f"{texte}, {fmt_kwh(recharge['kwh'])}"


class DialogueRapprochements(QDialog):
    def __init__(self, parent, cas: list[dict]):
        super().__init__(parent)
        self.cas = cas
        self.setWindowTitle("Recharges à vérifier avant l'import")
        if parent is not None:
            self.setWindowIcon(parent.windowIcon())
        self.setMinimumWidth(640)

        colonne = QVBoxLayout(self)
        colonne.setContentsMargins(0, 0, 0, 12)
        cases = QWidget()
        cases.setObjectName("Formulaire")
        cases.setAttribute(Qt.WA_StyledBackground, True)
        disposition = QVBoxLayout(cases)
        disposition.setContentsMargins(16, 8, 16, 12)
        disposition.setSpacing(6)

        n = len(cas)
        titre = QLabel("Ces recharges du fichier ressemblent à des saisies à "
                       "la main" if n > 1 else
                       "Cette recharge du fichier ressemble à une saisie à "
                       "la main")
        titre.setObjectName("TitreDialogue")
        titre.setWordWrap(True)
        disposition.addWidget(titre)
        # « pour chacune » seulement s'il y en a plusieurs (contrôle du
        # français du 05/11/2026, I1).
        choisir = ("Choisissez pour chacune" if n > 1
                   else "Choisissez ce qu'il faut en faire")
        doublon = "les doublons" if n > 1 else "le doublon"
        aide = QLabel(
            "L'application ne peut pas savoir à coup sûr s'il s'agit de la "
            "même charge : les heures ne se recouvrent pas, ou l'énergie "
            "diffère, ou plusieurs saisies sont possibles. Rien n'est encore "
            f"enregistré. {choisir} ; « Garder les deux » ne "
            f"fait rien perdre, vous pourrez supprimer {doublon} ensuite "
            "dans l'Historique.")
        aide.setObjectName("Discret")
        aide.setWordWrap(True)
        disposition.addWidget(aide)

        grille = QGridLayout()
        grille.setHorizontalSpacing(12)
        grille.setVerticalSpacing(4)
        self.choix: list[QComboBox] = []
        rang = 0
        for un_cas in cas:
            fichier = QLabel("Dans le fichier : " + decrire(un_cas["fichier"]))
            fichier.setObjectName("LibelleChamp")
            grille.addWidget(fichier, rang, 0, 1, 2)
            rang += 1
            for saisie in un_cas["saisies"]:
                grille.addWidget(QLabel("Votre saisie : " + decrire(saisie)),
                                 rang, 0, 1, 2)
                rang += 1
            liste = QComboBox()
            liste.addItem("Garder les deux", GARDER_LES_DEUX)
            # « la saisie » et non « ma saisie » : la fenêtre parle à
            # l'utilisateur (« Votre saisie : … »), les choix restent
            # neutres, comme « Garder les deux » (contrôle du 05/11, I3).
            for saisie in un_cas["saisies"]:
                quoi = ("la saisie" if len(un_cas["saisies"]) == 1
                        else f"la saisie du {decrire(saisie)}")
                liste.addItem(f"Remplacer {quoi} par la ligne du fichier",
                              saisie["id"])
            liste.addItem("Ignorer la ligne du fichier", IGNORER_LA_LIGNE)
            liste.setAccessibleName("Que faire de la recharge du fichier du "
                                    + decrire(un_cas["fichier"]))
            grille.addWidget(liste, rang, 0, 1, 2)
            rang += 1
            espace = QLabel("")
            espace.setFixedHeight(6)
            grille.addWidget(espace, rang, 0)
            rang += 1
            self.choix.append(liste)
        grille.setColumnStretch(1, 1)

        contenu = QWidget()
        contenu.setLayout(grille)
        defilement = QScrollArea()
        defilement.setWidgetResizable(True)
        defilement.setFrameShape(QScrollArea.NoFrame)
        defilement.setWidget(contenu)
        defilement.setMinimumHeight(min(110 * n, 360))
        disposition.addWidget(defilement, 1)
        colonne.addWidget(cases, 1)

        boutons = QDialogButtonBox()
        importer = boutons.addButton("Importer avec ces choix",
                                     QDialogButtonBox.AcceptRole)
        importer.setObjectName("BoutonEnregistrer")
        importer.setDefault(True)
        annuler = boutons.addButton("Annuler l'import",
                                    QDialogButtonBox.RejectRole)
        annuler.setAutoDefault(False)
        boutons.accepted.connect(self.accept)
        boutons.rejected.connect(self.reject)
        boutons.setContentsMargins(16, 6, 16, 0)
        colonne.addWidget(boutons)

    def reponses(self) -> list[str]:
        """Pour chaque cas, dans l'ordre : GARDER_LES_DEUX, IGNORER_LA_LIGNE
        ou l'identifiant de la saisie à remplacer."""
        return [liste.currentData() for liste in self.choix]


def demander_rapprochements(parent, cas: list[dict]) -> list[str] | None:
    """Montre les cas douteux ; rend les réponses, ou None si l'utilisateur
    annule l'import."""
    fenetre = DialogueRapprochements(parent, cas)
    if fenetre.exec() != QDialog.Accepted:
        return None
    return fenetre.reponses()
