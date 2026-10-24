"""L'Historique (version PySide6) : toutes les recharges, dans un tableau
qui defile.

Reprise de l'ancienne page vues/historique.py, avec deux changements voulus (25/09/2026) :
- un seul tableau qui defile, au lieu de pages de 25 lignes : la
  pagination n'etait qu'une limite de l'ancienne technique, trop lente pour
  afficher plusieurs centaines de lignes ;
- on choisit une ligne, puis « Modifier… » ou « Supprimer » (ou double-clic,
  touche Suppr, clic droit), comme dans Pecule, au lieu de deux boutons sur
  chaque ligne.
La recherche filtre pendant la frappe, comme dans Pecule.

Le choix des lignes (selection) est a part, sans interface : il se teste
sans fenetre.
"""

from __future__ import annotations

from PySide6.QtCore import QAbstractTableModel, QModelIndex, Qt, QTimer
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (QAbstractItemView, QComboBox, QDialog,
                               QHBoxLayout, QHeaderView, QLabel, QLineEdit,
                               QMenu, QMessageBox, QPushButton, QTableView,
                               QVBoxLayout, QWidget)

from composants import confirmer
from constantes import COLONNES_HISTORIQUE
from dialogue_modifier import DialogueModifier
from filtres import (conseil_si_vide, filtrer_par_periode, filtrer_par_recherche, texte_resume,
                     trier_recharges)
from pages.periode import BarrePeriode
from erreurs import erreur_en_clair
from recharges import charger_donnees, supprimer_recharge
from formats import fmt_date_fr

LIEUX = ["Tout", "Maison", "Extérieur"]
# Ce que montre le menu ; la valeur gardee reste « Tout » (audit du
# 08/10/2026 : « Tout » seul se lisait comme une periode).
NOMS_LIEUX = {"Tout": "Tous les lieux"}
NUMERIQUES = {"kwh", "cout_eur", "prix_kwh"}


# ---------- calculs (sans interface) ----------

def selection(toutes: list[dict], lieu: str, periode: str, recherche: str,
              tri: tuple[str, bool]) -> list[dict]:
    """Les recharges a afficher, dans l'ordre : lieu, puis periode, puis
    recherche, puis tri."""
    if lieu == "Maison":
        recharges = [r for r in toutes if r.get("lieu") == "maison"]
    elif lieu == "Extérieur":
        recharges = [r for r in toutes if r.get("lieu") == "exterieur"]
    else:
        recharges = list(toutes)
    recharges = filtrer_par_periode(recharges, periode)
    recharges = filtrer_par_recherche(recharges, recherche)
    return trier_recharges(recharges, *tri)


def tri_apres_clic(tri: tuple[str, bool], cle: str) -> tuple[str, bool]:
    """Clic sur un titre de colonne : un second clic inverse le sens ; une
    nouvelle colonne part du plus recent / du plus gros pour les dates et
    les nombres, de l'ordre alphabetique pour le texte."""
    cle_active, decroissant = tri
    if cle == cle_active:
        return cle, not decroissant
    return cle, cle in ("date", *NUMERIQUES)


def cellules(r: dict) -> tuple[str, ...]:
    """Le texte des six colonnes d'une recharge."""
    if r.get("lieu") == "maison":
        info = r.get("tarif_nom", "")
    else:
        op, carte = r.get("operateur", ""), r.get("carte", "")
        info = f"{op} ({carte})" if carte else op
    return (fmt_date_fr(r.get("date", "")),
            "Maison" if r.get("lieu") == "maison" else "Extérieur",
            f"{r.get('kwh', 0):.2f}".replace(".", ","),
            f"{r.get('cout_eur', 0):.2f}".replace(".", ","),
            f"{r.get('prix_kwh', 0):.4f}".replace(".", ","),
            info)


def message_si_vide(lieu: str, recherche: str,
                    aucune_recharge: bool = False) -> str:
    """Pourquoi le tableau est vide, et comment continuer."""
    if recherche:
        return f"Aucun résultat pour « {recherche} »."
    if aucune_recharge:
        return ("Aucune recharge pour l'instant.\n"
                + conseil_si_vide(True))
    raison = {"Maison": "Aucune recharge à la maison sur cette période.",
              "Extérieur": "Aucune recharge à l'extérieur sur cette période."
              }.get(lieu, "Aucune recharge sur cette période.")
    return raison + "\n" + conseil_si_vide(False)


# ---------- le tableau ----------

class ModeleRecharges(QAbstractTableModel):
    """Les lignes du tableau. Le tableau ne garde rien : il demande au
    modele le texte de chaque case visible, ce qui reste rapide quel que
    soit le nombre de recharges."""

    def __init__(self):
        super().__init__()
        self.recharges: list[dict] = []
        self._textes: list[tuple[str, ...]] = []

    def remplacer(self, recharges: list[dict]) -> None:
        self.beginResetModel()
        self.recharges = recharges
        self._textes = [cellules(r) for r in recharges]
        self.endResetModel()

    def rowCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self.recharges)

    def columnCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(COLONNES_HISTORIQUE)

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid():
            return None
        if role == Qt.DisplayRole:
            return self._textes[index.row()][index.column()]
        if role == Qt.TextAlignmentRole:
            # Nombres cales a droite : les virgules s'alignent.
            if COLONNES_HISTORIQUE[index.column()][0] in NUMERIQUES:
                return int(Qt.AlignRight | Qt.AlignVCenter)
            return int(Qt.AlignLeft | Qt.AlignVCenter)
        if role == Qt.ToolTipRole:
            # Le lieu d'une recharge exterieure n'a pas de colonne : il
            # s'affiche au survol.
            lieu = self.recharges[index.row()].get("lieu_detail", "")
            return lieu or None
        return None

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if orientation == Qt.Horizontal and role == Qt.DisplayRole:
            return COLONNES_HISTORIQUE[section][1]
        if orientation == Qt.Horizontal and role == Qt.TextAlignmentRole:
            if COLONNES_HISTORIQUE[section][0] in NUMERIQUES:
                return int(Qt.AlignRight | Qt.AlignVCenter)
            return int(Qt.AlignLeft | Qt.AlignVCenter)
        return None


# ---------- la page ----------

class PageHistorique(QWidget):
    def __init__(self, fenetre):
        super().__init__()
        self.fenetre = fenetre
        self.toutes = charger_donnees()["recharges"]

        colonne = QVBoxLayout(self)
        colonne.setContentsMargins(0, 0, 0, 0)
        colonne.setSpacing(10)

        # Ligne 1 : le lieu, puis la periode.
        ligne1 = QHBoxLayout()
        libelle = QLabel("Lieu :")
        libelle.setObjectName("LibellePeriode")
        ligne1.addWidget(libelle)
        self.choix_lieu = QComboBox()
        for lieu in LIEUX:
            self.choix_lieu.addItem(NOMS_LIEUX.get(lieu, lieu), lieu)
        self.choix_lieu.setCurrentIndex(
            max(0, self.choix_lieu.findData(fenetre.filtre_historique)))
        self.choix_lieu.currentIndexChanged.connect(
            lambda _i: self._choisir_lieu(self.choix_lieu.currentData()))
        ligne1.addWidget(self.choix_lieu)
        ligne1.addSpacing(16)
        self.barre = BarrePeriode(self.toutes, fenetre.filtre_periode)
        self.barre.periode_changee.connect(
            lambda v: fenetre.changer_periode("filtre_periode", v))
        ligne1.addWidget(self.barre)
        ligne1.addStretch(1)
        colonne.addLayout(ligne1)

        # Ligne 2 : la recherche, puis le resume de ce qui est affiche.
        ligne2 = QHBoxLayout()
        libelle = QLabel("Rechercher :")
        libelle.setObjectName("LibellePeriode")
        ligne2.addWidget(libelle)
        self.recherche = QLineEdit(fenetre.recherche_historique)
        self.recherche.setPlaceholderText(
            "opérateur, lieu, tarif, date, montant...")
        # Le raccourci écrit au survol, comme sur le bouton « 🔎 Rechercher »
        # de Pécule : Ctrl+F veut dire « chercher » dans les deux applis.
        # La recherche porte sur la période et le lieu choisis (selection()).
        self.recherche.setToolTip(
            "Recherche parmi les recharges de la période et du lieu choisis "
            "(Ctrl+F) : opérateur, lieu, tarif, date, montant")
        self.recherche.setClearButtonEnabled(True)   # la petite croix
        self.recherche.setFixedWidth(280)
        self.recherche.textChanged.connect(self._chercher)
        ligne2.addWidget(self.recherche)
        # Ctrl+F (fenetre.py) place le curseur ici.
        fenetre.champ_recherche = self.recherche
        ligne2.addSpacing(16)
        self.resume = QLabel("")
        self.resume.setObjectName("Resume")
        # Le resume prend la place qui reste et passe sur deux lignes quand
        # elle manque : a 1 000 px, il faisait deborder la page de 140 px
        # (second audit du 16/10/2026). A 1 280 px, rien ne change.
        self.resume.setWordWrap(True)
        self.resume.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        ligne2.addWidget(self.resume, 1)
        colonne.addLayout(ligne2)

        # Ligne 3 : ce qu'on peut faire de la ligne choisie.
        ligne3 = QHBoxLayout()
        self.bouton_modifier = QPushButton("✏️ Modifier…")
        self.bouton_modifier.clicked.connect(self.modifier)
        self.bouton_supprimer = QPushButton("🗑 Supprimer")
        self.bouton_supprimer.clicked.connect(self.supprimer)
        ligne3.addWidget(self.bouton_modifier)
        ligne3.addWidget(self.bouton_supprimer)
        aide = QLabel("Choisissez une ligne, ou double-cliquez dessus pour "
                      "la modifier.")
        aide.setObjectName("Discret")
        ligne3.addSpacing(8)
        ligne3.addWidget(aide)
        ligne3.addStretch(1)
        colonne.addLayout(ligne3)

        self.modele = ModeleRecharges()
        self.tableau = QTableView()
        self.tableau.setObjectName("TableHistorique")
        self.tableau.setModel(self.modele)
        self.tableau.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.tableau.setSelectionMode(QAbstractItemView.SingleSelection)
        self.tableau.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.tableau.setAlternatingRowColors(True)
        self.tableau.verticalHeader().setVisible(False)
        self.tableau.verticalHeader().setDefaultSectionSize(26)
        self.tableau.setWordWrap(False)
        entete = self.tableau.horizontalHeader()
        # Charte : date et nombres a la largeur de leur contenu, jamais
        # moins ; Tarif / Operateur prend le reste (c'etaient des largeurs
        # fixees a la main jusqu'au 08/10/2026).
        entete.setSectionResizeMode(QHeaderView.ResizeToContents)
        entete.setSectionResizeMode(len(COLONNES_HISTORIQUE) - 1,
                                    QHeaderView.Stretch)
        # Le tri est fait par filtres.trier_recharges, pas par Qt : ses
        # regles (sens de depart selon la colonne, colonne mixte
        # tarif / operateur) sont celles de l'ancienne version.
        entete.setSectionsClickable(True)
        entete.setSortIndicatorShown(True)
        entete.sectionClicked.connect(self._trier)
        self.tableau.doubleClicked.connect(lambda _index: self.modifier())
        self.tableau.selectionModel().selectionChanged.connect(
            lambda *_: self._maj_boutons())
        self.tableau.setContextMenuPolicy(Qt.CustomContextMenu)
        self.tableau.customContextMenuRequested.connect(self._menu_contextuel)
        # Raccourcis limites au tableau : Suppr ne doit rien supprimer
        # pendant qu'on efface une lettre dans la recherche.
        for touche, action in ((QKeySequence.Delete, self.supprimer),
                               (Qt.Key_Return, self.modifier),
                               (Qt.Key_Enter, self.modifier)):
            raccourci = QShortcut(QKeySequence(touche), self.tableau)
            raccourci.setContext(Qt.WidgetShortcut)
            raccourci.activated.connect(action)
        # Le tableau prend toute la hauteur visible, et defile a l'interieur.
        self.tableau.setMinimumHeight(420)
        colonne.addWidget(self.tableau, 1)

        self.message_vide = QLabel("")
        self.message_vide.setObjectName("Discret")
        self.message_vide.setAlignment(Qt.AlignHCenter | Qt.AlignTop)
        self.message_vide.setContentsMargins(0, 40, 0, 40)
        self.message_vide.setWordWrap(True)
        # Il prend la hauteur du tableau quand celui-ci est cache : sans cela,
        # les rangees de controles s'etalaient sur toute la page.
        colonne.addWidget(self.message_vide, 1)

        self.rafraichir()
        self._reprendre_la_selection()

    # ---------- remplissage ----------

    def rafraichir(self) -> None:
        """Remplit le tableau a partir des filtres courants, sans
        reconstruire la page (la recherche garde ainsi son curseur)."""
        f = self.fenetre
        recharges = selection(self.toutes, f.filtre_historique,
                              f.filtre_periode, f.recherche_historique,
                              f.tri_historique)
        self.modele.remplacer(recharges)
        self.resume.setText(texte_resume(recharges).strip())
        cle, decroissant = f.tri_historique
        colonnes = [c for c, _ in COLONNES_HISTORIQUE]
        self.tableau.horizontalHeader().setSortIndicator(
            colonnes.index(cle) if cle in colonnes else 0,
            Qt.DescendingOrder if decroissant else Qt.AscendingOrder)
        vide = not recharges
        self.tableau.setVisible(not vide)
        self.message_vide.setVisible(vide)
        self.message_vide.setText(
            message_si_vide(f.filtre_historique, f.recherche_historique,
                            not self.toutes)
            if vide else "")
        self._maj_boutons()

    def _maj_boutons(self) -> None:
        choisie = self.recharge_choisie() is not None
        self.bouton_modifier.setEnabled(choisie)
        self.bouton_supprimer.setEnabled(choisie)

    def _reprendre_la_selection(self) -> None:
        """Apres une modification, la page est reconstruite : on y
        retrouve la recharge qu'on vient de toucher, choisie et visible."""
        ident = self.fenetre.selection_historique
        # Servie une fois : revenir plus tard sur l'Historique ne doit pas
        # ramener de force a cette ligne.
        self.fenetre.selection_historique = None
        if not ident:
            return
        for ligne, r in enumerate(self.modele.recharges):
            if r.get("id") == ident:
                self.tableau.selectRow(ligne)
                self.tableau.scrollTo(self.modele.index(ligne, 0),
                                      QAbstractItemView.PositionAtCenter)
                return

    # ---------- commandes ----------

    def _choisir_lieu(self, valeur: str) -> None:
        self.fenetre.filtre_historique = valeur
        self.rafraichir()

    def _chercher(self, texte: str) -> None:
        self.fenetre.recherche_historique = texte.strip()
        self.rafraichir()

    def _trier(self, colonne: int) -> None:
        cle = COLONNES_HISTORIQUE[colonne][0]
        self.fenetre.tri_historique = tri_apres_clic(
            self.fenetre.tri_historique, cle)
        ident = (self.recharge_choisie() or {}).get("id")
        self.rafraichir()
        # La ligne choisie le reste, a sa nouvelle place.
        self.fenetre.selection_historique = ident
        self._reprendre_la_selection()

    def recharge_choisie(self) -> dict | None:
        lignes = self.tableau.selectionModel().selectedRows()
        if not lignes:
            return None
        return self.modele.recharges[lignes[0].row()]

    def _menu_contextuel(self, position) -> None:
        index = self.tableau.indexAt(position)
        if not index.isValid():
            return
        self.tableau.selectRow(index.row())
        menu = QMenu(self)
        menu.addAction("✏️ Modifier…", self.modifier)
        menu.addAction("🗑 Supprimer", self.supprimer)
        menu.exec(self.tableau.viewport().mapToGlobal(position))

    def _recharger_la_page(self, ident: str | None) -> None:
        """Reconstruit la page un instant plus tard : la liste des periodes
        peut avoir change (derniere recharge d'un mois supprimee, date
        deplacee), et on ne detruit pas la page pendant qu'un de ses
        boutons traite son clic."""
        fenetre = self.fenetre
        fenetre.selection_historique = ident
        QTimer.singleShot(0, fenetre,
                          lambda: fenetre.afficher_vue("historique"))

    def modifier(self) -> None:
        r = self.recharge_choisie()
        if r is None:
            return
        if DialogueModifier(self.fenetre, r).exec() == QDialog.Accepted:
            self._recharger_la_page(r.get("id"))

    def supprimer(self) -> None:
        r = self.recharge_choisie()
        if r is None:
            return
        kwh = f"{r.get('kwh', 0):.2f}".replace(".", ",")
        # « Garder » par defaut : une suppression ne se rattrape que par la
        # page Restaurer.
        if not confirmer(
                self.fenetre, "Supprimer la recharge",
                f"Supprimer la recharge du {fmt_date_fr(r.get('date', ''))} "
                f"({kwh}\xa0kWh) ?\n\n"
                "Elle ne se rattrape ensuite que par la page « Restaurer une sauvegarde ».",
                action="Supprimer la recharge", garder="Garder", danger=True):
            return
        # La ligne suivante sera choisie apres coup : on peut enchainer.
        lignes = self.modele.recharges
        rang = lignes.index(r)
        voisine = (lignes[rang + 1] if rang + 1 < len(lignes)
                   else lignes[rang - 1] if rang > 0 else {})
        try:
            ok = supprimer_recharge(r.get("id", ""))
        except (ValueError, OSError) as e:
            QMessageBox.critical(self.fenetre, "Suppression impossible", erreur_en_clair(e))
            return
        if not ok:
            # Sans ce test, la page se rechargeait comme si la suppression
            # avait eu lieu, et la ligne reapparaissait sans un mot.
            QMessageBox.critical(
                self.fenetre, "Suppression impossible",
                "Cette recharge est introuvable : rien n'a été supprimé.")
            return
        self._recharger_la_page(voisine.get("id"))


def construire(fenetre) -> QWidget:
    return PageHistorique(fenetre)
