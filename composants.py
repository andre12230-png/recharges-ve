"""Elements d'interface communs a toutes les pages de la version PySide6.

Leur allure vient de la feuille de style (theme_qt.py) : ici, on se
contente de les construire et de leur donner leur NOM, que la feuille de
style vise.
"""

from __future__ import annotations

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (QAbstractItemView, QFrame, QHBoxLayout,
                               QHeaderView, QLabel,
                               QMessageBox, QSizePolicy, QTableWidget,
                               QTableWidgetItem, QVBoxLayout, QWidget)


def carte(titre: str) -> tuple[QFrame, QVBoxLayout]:
    """Une carte blanche a en-tete bleute, comme celles du Bilan de Pecule.

    Rend la carte (a placer dans la page) et la disposition de son corps
    (ou ranger le contenu)."""
    cadre = QFrame()
    cadre.setObjectName("Carte")
    exterieur = QVBoxLayout(cadre)
    exterieur.setContentsMargins(0, 0, 0, 0)
    exterieur.setSpacing(0)
    entete = QLabel(titre.upper())
    entete.setObjectName("EnteteCarte")
    # L'en-tete garde sa hauteur : quand deux cartes cote a cote n'ont pas
    # autant de contenu, c'est le bas de la plus courte qui s'allonge, pas
    # son en-tete (vu sur Maison / Exterieur, 25/09/2026).
    entete.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
    exterieur.addWidget(entete)
    corps = QVBoxLayout()
    corps.setContentsMargins(12, 10, 12, 12)
    corps.setSpacing(6)
    exterieur.addLayout(corps)
    exterieur.addStretch(1)
    cadre._entete = entete          # pour les cartes dont le titre change
    return cadre, corps


def tuile(libelle: str, valeur: str, couleur: str) -> QFrame:
    """Une tuile de chiffre cle, comme celles du Bilan de Pecule : intitule
    en petites capitales grises, valeur en gros, trait de couleur en haut.

    La couleur est posee sur CETTE tuile, et visee par son nom : sans cela,
    le trait de couleur se repetait sur chaque libelle (piege vu dans
    Pecule)."""
    cadre = QFrame()
    cadre.setObjectName("TuileKpi")
    cadre.setStyleSheet(f"QFrame#TuileKpi {{ border-top: 3px solid {couleur}; }}")
    colonne = QVBoxLayout(cadre)
    colonne.setContentsMargins(12, 8, 12, 10)
    colonne.setSpacing(2)
    etiquette = QLabel(libelle)
    etiquette.setObjectName("LibelleTuile")
    etiquette.setWordWrap(True)
    chiffre = QLabel(valeur)
    chiffre.setObjectName("ValeurTuile")
    chiffre.setStyleSheet(f"color: {couleur};")
    colonne.addWidget(etiquette)
    colonne.addWidget(chiffre)
    cadre._valeur = chiffre         # pour les tests
    return cadre


def bandeau_info(texte: str) -> QFrame:
    """Un bandeau d'information discret (fond jaune pale de Pecule) : une
    remarque utile, pas une alerte."""
    cadre = QFrame()
    cadre.setObjectName("BandeauInfo")
    colonne = QVBoxLayout(cadre)
    colonne.setContentsMargins(12, 8, 12, 8)
    colonne.addWidget(paragraphe(texte))
    return cadre


def bandeau_alerte(texte: str) -> QFrame:
    """Un bandeau d'alerte (orange de Pecule) : quelque chose a faire, comme
    une sauvegarde externe trop ancienne."""
    cadre = QFrame()
    cadre.setObjectName("BandeauAlerte")
    colonne = QVBoxLayout(cadre)
    colonne.setContentsMargins(12, 8, 12, 8)
    colonne.addWidget(paragraphe(texte))
    return cadre


class TableauCarte(QTableWidget):
    """Un QTableWidget qui demande toute la hauteur de ses lignes, et au
    moins la largeur de ses colonnes. Mesure au moment de la mise en page,
    une fois la feuille de style appliquee : mesuree a la construction, la
    derniere ligne sortait rognee (marges des en-tetes pas encore connues).
    """

    colonnes_mesurees = 0

    def _taille(self) -> QSize:
        entete = self.horizontalHeader()
        hauteur = (entete.sizeHint().height()
                   + sum(self.rowHeight(i) for i in range(self.rowCount()))
                   + 2 * self.frameWidth() + 2)
        largeur = sum(max(self.sizeHintForColumn(c),
                          entete.sectionSizeHint(c))
                      for c in range(self.colonnes_mesurees))
        return QSize(largeur + 2 * self.frameWidth() + 2, hauteur)

    def sizeHint(self) -> QSize:
        return self._taille()

    def minimumSizeHint(self) -> QSize:
        return self._taille()


def tableau(entetes: list[str], lignes: list[tuple[str, ...]], *,
            a_droite: tuple[int, ...] = (), etirer: int | None = None,
            boutons: list[QWidget | None] | None = None,
            couleurs: list[str | None] | None = None) -> QTableWidget:
    """Un petit tableau en lecture seule, de la meme allure que celui de
    l'Historique : en-tetes, lignes alternees, nombres cales a droite.

    Remplace les listes ecrites en caracteres de largeur fixe (audit de
    design du 03/10/2026) : on y lisait des fleches « -> », des milliers non
    separes, et les colonnes tenaient a coups d'espaces.

    - `a_droite` : les colonnes de nombres, calees a droite ;
    - `etirer` : la colonne de texte qui prend la place restante ; les
      autres prennent la largeur de leur contenu, jamais moins (regle de la
      charte). Sans colonne de texte a etirer (un tableau de nombres), une
      colonne vide prend la place a droite : les chiffres restent groupes au
      lieu d'etre separes par un grand vide ;
    - `boutons` : un bouton (ou None) par ligne, pose dans une derniere
      colonne sans titre ;
    - `couleurs` : une couleur de texte (ou None) par ligne.

    Le tableau prend la hauteur de toutes ses lignes : c'est la page qui
    defile, pas le tableau."""
    remplissage = etirer is None
    n_col = len(entetes) + (1 if boutons else 0) + (1 if remplissage else 0)
    col_bouton = len(entetes)
    table = TableauCarte(len(lignes), n_col)
    table.setObjectName("TableCarte")
    table.setHorizontalHeaderLabels(
        list(entetes) + [""] * (n_col - len(entetes)))
    table.setEditTriggers(QAbstractItemView.NoEditTriggers)
    table.setSelectionMode(QAbstractItemView.NoSelection)
    table.setFocusPolicy(Qt.NoFocus if not boutons else Qt.TabFocus)
    table.setAlternatingRowColors(True)
    table.setWordWrap(False)
    table.verticalHeader().setVisible(False)
    table.verticalHeader().setDefaultSectionSize(32 if boutons else 26)
    table.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
    table.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
    for c in range(len(entetes)):
        table.horizontalHeaderItem(c).setTextAlignment(
            (Qt.AlignRight if c in a_droite else Qt.AlignLeft)
            | Qt.AlignVCenter)
    for i, ligne in enumerate(lignes):
        for c, texte in enumerate(ligne):
            case = QTableWidgetItem(texte)
            case.setTextAlignment(
                (Qt.AlignRight if c in a_droite else Qt.AlignLeft)
                | Qt.AlignVCenter)
            if couleurs and couleurs[i]:
                case.setForeground(QColor(couleurs[i]))
            table.setItem(i, c, case)
        if boutons and boutons[i] is not None:
            # Le bouton dans une petite boite a marges : il ne touche pas
            # les bords de sa case.
            boite = QWidget()
            dans_boite = QHBoxLayout(boite)
            dans_boite.setContentsMargins(4, 1, 4, 1)
            dans_boite.addWidget(boutons[i])
            table.setCellWidget(i, col_bouton, boite)
    entete = table.horizontalHeader()
    entete.setSectionResizeMode(QHeaderView.ResizeToContents)
    entete.setSectionResizeMode(n_col - 1 if remplissage else etirer,
                                QHeaderView.Stretch)
    entete.setHighlightSections(False)
    # Toute la hauteur (en-tete + lignes + cadre), et au moins la largeur
    # de toutes les colonnes : sur une fenetre etroite, c'est la page qui
    # defile de cote, aucune colonne n'est coupee.
    table.verticalHeader().setSectionResizeMode(QHeaderView.Fixed)
    table.colonnes_mesurees = n_col - (1 if remplissage else 0)
    table.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
    table.lignes = lignes          # pour les tests
    return table


def texte_fixe(texte: str) -> QLabel:
    """Une ligne en caracteres de largeur fixe (Consolas), pour que les
    colonnes d'une liste restent alignees."""
    etiquette = QLabel(texte)
    etiquette.setObjectName("TexteFixe")
    etiquette.setTextInteractionFlags(Qt.TextSelectableByMouse)
    return etiquette


# Largeur maximale d'un long texte : ~110 signes par ligne (charte des
# applis ; Pecule : notice.TexteALire). Au-dela, l'oeil perd la ligne.
LARGEUR_TEXTE = 780


def texte_a_lire(texte: str, nom: str = "") -> QWidget:
    """Un long texte (notice, explication) limite a LARGEUR_TEXTE.

    Le paragraphe est pose dans une rangee avec un vide a sa droite : limite
    tel quel dans une colonne plus large, Qt calculait sa hauteur pour la
    largeur de la colonne, et coupait ses dernieres lignes (piege vu dans la
    Notice du Photovoltaique, charte section 6). Audit du 03/10/2026."""
    rangee = QWidget()
    dedans = QHBoxLayout(rangee)
    dedans.setContentsMargins(0, 0, 0, 0)
    etiquette = paragraphe(texte, nom)
    etiquette.setMaximumWidth(LARGEUR_TEXTE)
    dedans.addWidget(etiquette, 1)
    dedans.addStretch(0)
    rangee.etiquette = etiquette    # pour les tests
    return rangee


def paragraphe(texte: str, nom: str = "") -> QLabel:
    """Un texte qui revient a la ligne tout seul, selectionnable a la souris
    (pour pouvoir copier un chemin ou un message)."""
    etiquette = QLabel(texte)
    etiquette.setWordWrap(True)
    etiquette.setTextInteractionFlags(Qt.TextSelectableByMouse)
    if nom:
        etiquette.setObjectName(nom)
    return etiquette


def boite_de_confirmation(parent, titre: str, question: str, action: str,
                          garder: str = "Annuler", danger: bool = False,
                          action_par_defaut: bool = False):
    """Construit, sans l'afficher, la boite qui demande confirmation d'une
    action sans retour. Rend (boite, bouton d'action). Meme modele que
    Pecule (widgets.boite_de_confirmation).

    - Le bouton par defaut est `garder` : Entree, par reflexe, ne change
      rien. Echap choisit aussi `garder`.
    - Le bouton d'action dit ce qu'il fait (« Supprimer le relevé »), au lieu
      d'un « Oui » qui oblige a relire la question.
    - `danger` : une suppression montre l'icone d'avertissement.
    - `action_par_defaut` : seulement pour une question qui ne detruit rien
      (fermer le tarif precedent, avertissement doux) ; Echap garde.

    Laissee a Qt, la question de la page Restaurer mettait « Oui » par
    defaut (audit de design du 03/10/2026)."""
    boite = QMessageBox(parent)
    boite.setWindowTitle(titre)
    boite.setIcon(QMessageBox.Warning if danger else QMessageBox.Question)
    boite.setTextFormat(Qt.PlainText)
    boite.setText(question)
    bouton_action = boite.addButton(action, QMessageBox.AcceptRole)
    bouton_garder = boite.addButton(garder, QMessageBox.RejectRole)
    boite.setDefaultButton(bouton_action if action_par_defaut
                           else bouton_garder)
    boite.setEscapeButton(bouton_garder)
    return boite, bouton_action


def confirmer(parent, titre: str, question: str, action: str,
              garder: str = "Annuler", danger: bool = False,
              action_par_defaut: bool = False) -> bool:
    """Pose la question (voir boite_de_confirmation). True seulement si
    l'utilisateur a clique le bouton d'action."""
    boite, bouton_action = boite_de_confirmation(
        parent, titre, question, action, garder, danger, action_par_defaut)
    boite.exec()
    return boite.clickedButton() is bouton_action
