"""Theme de la version PySide6 : les couleurs de Pecule.

Decision de l'auteur (25/09/2026) : les trois applications suivent les couleurs
de Pecule — fenetre et bandeau creme, texte noir, champs et tableaux blancs,
cartes blanches a liseré gris-bleu sur un fond gris clair, en-tetes de carte
en degrade bleu pale, selection bleue. Les valeurs ci-dessous sont reprises
du code de Pecule (comptesbudget/app.py, ui/main_window.py, ui/views/bilan.py).

Trois garde-fous, comme dans Pecule :
- le style « Fusion » et une palette construite entierement : un Windows
  regle en mode sombre ne peut plus rien changer (defaut vu dans Pecule le
  16/09/2026 : texte blanc sur fond clair) ;
- chaque couleur de texte atteint 4,5 pour 1 de contraste sur son fond
  (tests/test_qt_theme.py) : quand une couleur de Pecule n'y arrivait pas,
  elle est foncee d'un cran et c'est dit a cote ;
- les boutons fournis par Qt (« Oui », « Non », « Annuler ») sont en francais.
"""

from __future__ import annotations

import os

from PySide6.QtCore import QLibraryInfo, QRectF, Qt, QTranslator
from PySide6.QtGui import QColor, QPalette, QPen
from PySide6.QtWidgets import (QApplication, QMenu, QProxyStyle, QStyle,
                               QStyleFactory, QToolTip)

from constantes import chemin_ressource

# ---------- couleurs de Pecule ----------

# Palette de base (comptesbudget/app.py)
CREME = "#ECE9D8"          # fond des fenetres et du bandeau
BLANC = "#FFFFFF"          # fond des champs, des listes et des cartes
LIGNE_PAIRE = "#F5F5F0"    # une ligne sur deux dans les tableaux
ENCRE = "#000000"          # le texte courant
SELECTION = "#316AC5"      # ligne ou texte selectionne
BULLE = "#FFFFDC"          # fond des info-bulles
GRIS_PALE = "#666666"      # texte d'invite et libelles desactives
LIEN = "#0B5AA8"
LIEN_VU = "#6A3FA0"

# Zone des pages et cartes (comptesbudget/ui/views/bilan.py)
# Fond des pages : le creme de la fenetre et du bandeau, comme les pages
# ordinaires de Pecule. Le gris-bleu du Bilan de Pecule (#ECEEF2), pose
# d'abord sous toutes les pages, jurait avec le bandeau creme (demande
# de l'auteur, 25/09/2026).
FOND_PAGE = CREME
# Liseré des cartes et des tuiles : celui de Pecule, fonce d'un cran le
# 25/09/2026 (#C8D0DC -> #BEC7D4) pour rester visible sur le fond creme.
CARTE_CADRE = "#BEC7D4"
# Fond des cartes, des tuiles et des formulaires : un ivoire, le creme de la
# fenetre en bien plus pale. Le blanc pur tranchait trop sur le creme
# (demande de l'auteur, 25/09/2026). Les cases de saisie restent blanches : on
# voit ainsi ou taper.
FOND_CARTE = "#FAF8F1"
ENTETE_HAUT = "#E8EEF7"    # en-tete de carte : degrade du bleu tres pale...
ENTETE_BAS = "#C9D6E8"     # ... au bleu pale
ENTETE_FILET = "#B0BFD3"   # trait sous l'en-tete de carte
BLEU_NUIT = "#1F3A6B"      # titres de carte, solde, valeur principale
GRIS_LIBELLE = "#666666"   # intitule d'une tuile
GRIS_SOUS = "#555555"      # ligne secondaire d'une tuile

# Couleurs de sens (comptesbudget/ui/assistants.py, report.py)
VERT = "#18733A"           # favorable, confirme. (Pecule met #229954 sur les
                           # montants positifs — 3,5 pour 1 sur blanc — et
                           # #1A7A3A pour les coches — 4,4 sur le creme des
                           # petites fenetres. Fonce d'un cran : 5,9 sur blanc,
                           # 4,85 sur le creme.)
ROUGE = "#BC3729"          # defavorable, a supprimer, erreur (5,7 / 4,6 sur le creme)
CHAMP_CADRE = "#6F7885"    # contour des cases de saisie, celui de la charte
                           # (4,6 pour 1 sur blanc ; c'etait #808080, 3,9)
# Graphique des Statistiques : les couleurs du Photovoltaique (bleu de
# l'injection, orange du soutirage), 3 pour 1 au moins sur blanc.
GRAPHE_ENERGIE = "#3987E5"
GRAPHE_COUT = "#D95926"

# Bandeaux d'information et d'alerte (bilan.py, assistants.py)
INFO_FOND = "#FFFBE6"
INFO_CADRE = "#E8D77B"
ALERTE_FOND = "#FEF5E7"
ALERTE_CADRE = "#E67E22"
ALERTE_TEXTE = "#7E5109"
ERREUR_FOND = "#FDEDEB"
ERREUR_TEXTE = "#7B241C"
TRACE = "#555555"          # pile d'appels du detail technique (gris
                           # secondaire de la charte ; c'etait #4A4A52)

# Bandeau de gauche (comptesbudget/ui/main_window.py)
SB_BOUTON = "#FCFCFC"
SB_BOUTON_CADRE = "#808080"  # Pecule a #DCDCDC (1,3 pour 1) : un contour de
                             # bouton doit faire 3 pour 1 (regle du 15/09/2026,
                             # la meme que le Photovoltaique).
SB_BOUTON_TEXTE = "#222222"
SB_SURVOL = "#EAF2FB"
SB_SURVOL_CADRE = SELECTION  # survol et page affichee : le bleu de selection
                             # de Pecule (son #9CC0E8 ne fait que 1,6 pour 1).
SB_ACTIF = "#D8E7F7"       # page affichee (Pecule s'en sert pour le bouton
                           # enfonce ; son bandeau n'a pas de page affichee)
SB_TITRE = "#5A5A5A"       # titres de section. (Pecule a #6E6E6E, qui ne fait
                           # que 4,2 pour 1 sur le creme : fonce d'un cran.)
SB_FILET = "#A9A9A9"       # trait sous les titres de section

# Ajoutees le 12/10/2026 avec le mode sombre : en clair, ce sont les memes
# valeurs qu'avant, ecrites jusque-la directement dans la palette ou le style.
ENCRE_BULLE = "#000000"        # texte des info-bulles
TEXTE_SELECTION = "#FFFFFF"    # texte sur le bleu de selection
SB_ACTIF_TEXTE = BLEU_NUIT     # texte de la page affichee, dans le bandeau
GRAPHE_GRILLE = "#E2E8F0"      # grille discrete des graphiques
CONTOUR_CASE = "#6F7885"       # contour des cases a cocher, des boutons ronds
                               # et des boutons (charte : 3 pour 1)
CONTOUR_ETEINT = "#C8D0DC"     # bord d'un bouton ou d'une liste desactive

# Largeur du bandeau : la meme dans les trois applis (Pecule s'y est aligne
# le 11/10/2026 ; il etait a 184).
LARGEUR_BANDEAU = 212


# ---------- mode sombre (12/10/2026) ----------
#
# Decision de l'auteur du 12/10/2026 (elle remplace « un seul theme, le
# clair » de la v1.24.0) : un mode sombre dans les trois applications, la
# meme palette partout, validee sur maquette et ecrite dans la charte
# d'interface. Un sombre CHAUD (brun tres fonce), transposition du creme et de
# l'ivoire ; texte blanc casse, jamais blanc pur.
#
# Chaque nom de couleur ci-dessus a sa jumelle sombre ci-dessous.
# choisir_theme() remplace les valeurs du module par l'un ou l'autre jeu : a
# appeler AVANT d'importer les pages (app.py), qui prennent leurs couleurs
# au moment ou elles sont importees.
NOMS_DES_COULEURS = (
    "CREME", "BLANC", "LIGNE_PAIRE", "ENCRE", "SELECTION", "BULLE",
    "GRIS_PALE", "LIEN", "LIEN_VU", "FOND_PAGE", "CARTE_CADRE", "FOND_CARTE",
    "ENTETE_HAUT", "ENTETE_BAS", "ENTETE_FILET", "BLEU_NUIT", "GRIS_LIBELLE",
    "GRIS_SOUS", "VERT", "ROUGE", "CHAMP_CADRE", "GRAPHE_ENERGIE",
    "GRAPHE_COUT", "INFO_FOND", "INFO_CADRE", "ALERTE_FOND", "ALERTE_CADRE",
    "ALERTE_TEXTE", "ERREUR_FOND", "ERREUR_TEXTE", "TRACE", "SB_BOUTON",
    "SB_BOUTON_CADRE", "SB_BOUTON_TEXTE", "SB_SURVOL", "SB_SURVOL_CADRE",
    "SB_ACTIF", "SB_TITRE", "SB_FILET", "ENCRE_BULLE", "TEXTE_SELECTION",
    "SB_ACTIF_TEXTE", "GRAPHE_GRILLE", "CONTOUR_CASE", "CONTOUR_ETEINT",
)
PALETTE_CLAIRE = {nom: globals()[nom] for nom in NOMS_DES_COULEURS}
PALETTE_SOMBRE = {
    "CREME": "#1C1B18",          # fond des fenetres, des pages et du bandeau
    "BLANC": "#302F2B",          # champs et listes, un cran plus clairs que
                                 # la carte : on voit ou taper
    "LIGNE_PAIRE": "#2A2925",
    "ENCRE": "#EDEAE2",          # blanc casse
    "SELECTION": "#316AC5",      # inchangee (texte blanc, 5,25 pour 1)
    "BULLE": "#3B3826",
    "GRIS_PALE": "#ADAAA1",
    "LIEN": "#82B6F5",
    "LIEN_VU": "#BBA2EA",
    "FOND_PAGE": "#1C1B18",
    "CARTE_CADRE": "#55565B",
    "FOND_CARTE": "#262521",
    "ENTETE_HAUT": "#2E3B52",
    "ENTETE_BAS": "#27344A",
    "ENTETE_FILET": "#41557A",
    "BLEU_NUIT": "#A9C2EC",      # le bleu nuit devient un bleu clair
    "GRIS_LIBELLE": "#ADAAA1",
    "GRIS_SOUS": "#C9C6BD",
    "VERT": "#5CC281",
    "ROUGE": "#F2806F",
    "CHAMP_CADRE": "#8A919C",
    "GRAPHE_ENERGIE": "#4A95EC",
    "GRAPHE_COUT": "#E3693A",
    "INFO_FOND": "#35321C",
    "INFO_CADRE": "#8F7F33",
    "ALERTE_FOND": "#3A2D16",
    "ALERTE_CADRE": "#E67E22",
    "ALERTE_TEXTE": "#F3C783",
    "ERREUR_FOND": "#3E201D",
    "ERREUR_TEXTE": "#F6B3AA",
    "TRACE": "#C9C6BD",
    "SB_BOUTON": "#2B2A26",
    "SB_BOUTON_CADRE": "#8A8780",
    "SB_BOUTON_TEXTE": "#E6E3DA",
    "SB_SURVOL": "#24334A",
    "SB_SURVOL_CADRE": "#6FA0E8",
    "SB_ACTIF": "#2A3F5F",
    "SB_TITRE": "#ADAAA1",
    "SB_FILET": "#5E5C56",
    "ENCRE_BULLE": "#F2EFE6",
    "TEXTE_SELECTION": "#FFFFFF",
    "SB_ACTIF_TEXTE": "#CFDCF3",
    "GRAPHE_GRILLE": "#4A4944",
    "CONTOUR_CASE": "#8A919C",
    "CONTOUR_ETEINT": "#5E5C56",
}
THEMES = {"clair": PALETTE_CLAIRE, "sombre": PALETTE_SOMBRE}

# Le reglage est garde dans les preferences de l'application (registre de
# Windows, QSettings), jamais dans recharges.json ni tarifs.json : le format
# des donnees ne change pas. L'ancienne cle « theme » de tarifs.json (avant
# la v1.24.0) n'est pas lue : elle ne peut pas rallumer le sombre par
# surprise. Le choix s'applique au prochain demarrage : changer a chaud
# obligerait chaque page ouverte a se redessiner, et c'est la que se
# cachent les oublis.
ORGANISATION_PREFERENCES = "recharges-ve"
CLE_THEME = "ui/theme"
_THEME_ACTIF = "clair"


def preferences():
    """Les preferences de l'application (registre de Windows).

    Si la variable d'environnement RECHARGES_PREFERENCES donne un fichier,
    c'est lui qui sert : les tests y envoient leurs preferences (conftest.py),
    pour ne jamais lire ni ecrire celles de l'utilisateur."""
    from PySide6.QtCore import QSettings
    fichier = os.environ.get("RECHARGES_PREFERENCES")
    if fichier:
        return QSettings(fichier, QSettings.Format.IniFormat)
    return QSettings(ORGANISATION_PREFERENCES, ORGANISATION_PREFERENCES)


def nom_du_theme(reglages) -> str:
    """« clair » ou « sombre », lu dans les preferences. Une valeur
    inconnue, absente ou abimee donne le clair, le theme de reference.
    Une preference abimee peut revenir en liste : sans le controle du type,
    le demarrage plantait (defaut vu dans le Photovoltaique, 13/10/2026)."""
    valeur = reglages.value(CLE_THEME) if reglages is not None else None
    return valeur if isinstance(valeur, str) and valeur in THEMES else "clair"


def choisir_theme(nom: str) -> str:
    """Fixe le theme de la session, « clair » ou « sombre », et le rend.
    Remplace les couleurs du module : a appeler avant d'importer les pages."""
    global _THEME_ACTIF
    _THEME_ACTIF = nom if nom in THEMES else "clair"
    globals().update(THEMES[_THEME_ACTIF])
    return _THEME_ACTIF


def theme_actif() -> str:
    """« clair » ou « sombre » : le theme de la session."""
    return _THEME_ACTIF


# ---------- palette ----------

def palette_claire() -> QPalette:
    """La palette de Pecule (ou sa jumelle sombre, si c'est le theme
    choisi), construite de zero — fonds ET textes.

    Ne prend rien a la palette du systeme : c'est ce qui garantit la meme
    apparence sur un poste regle en clair et sur un poste regle en sombre."""
    pal = QPalette()
    pal.setColor(QPalette.Window, QColor(CREME))
    pal.setColor(QPalette.WindowText, QColor(ENCRE))
    pal.setColor(QPalette.Base, QColor(BLANC))
    pal.setColor(QPalette.Text, QColor(ENCRE))
    pal.setColor(QPalette.AlternateBase, QColor(LIGNE_PAIRE))
    pal.setColor(QPalette.Button, QColor(CREME))
    pal.setColor(QPalette.ButtonText, QColor(ENCRE))
    pal.setColor(QPalette.ToolTipBase, QColor(BULLE))
    pal.setColor(QPalette.ToolTipText, QColor(ENCRE_BULLE))
    pal.setColor(QPalette.Highlight, QColor(SELECTION))
    pal.setColor(QPalette.HighlightedText, QColor(TEXTE_SELECTION))
    pal.setColor(QPalette.PlaceholderText, QColor(GRIS_PALE))
    pal.setColor(QPalette.BrightText, QColor(TEXTE_SELECTION))
    pal.setColor(QPalette.Link, QColor(LIEN))
    pal.setColor(QPalette.LinkVisited, QColor(LIEN_VU))
    # Ce qui est desactive s'efface, sans disparaitre pour autant.
    for role in (QPalette.WindowText, QPalette.Text, QPalette.ButtonText):
        pal.setColor(QPalette.Disabled, role, QColor(GRIS_PALE))
    return pal


# ---------- feuille de style ----------

def feuille_de_style() -> str:
    """La feuille de style de l'application.

    Chaque regle vise un element par son NOM (setObjectName) et non « tout
    QFrame » : un QLabel est un QFrame, et une regle trop large descendrait
    sur chaque libelle (piege vu dans le Bilan de Pecule)."""
    # Chemin a barres obliques « / » : c'est ce qu'attend la feuille de
    # style, meme sous Windows.
    # En sombre, une fleche claire : la grise (#4A4A52) ne faisait que 1,4
    # pour 1 sur le fond des cases (12/10/2026).
    FLECHE_BAS = chemin_ressource(
        "fleche_bas_sombre.svg" if theme_actif() == "sombre"
        else "fleche_bas.svg").as_posix()
    return f"""
    QWidget {{ font-family: "Segoe UI"; font-size: 10pt; }}

    /* ----- bandeau de gauche ----- */
    QFrame#Bandeau {{ background: {CREME}; border-right: 1px solid {SB_FILET}; }}
    QLabel#Marque {{ color: {BLEU_NUIT}; font-size: 13pt; font-weight: bold; }}
    QLabel#SousMarque, QLabel#Version {{ color: {SB_TITRE}; font-size: 8pt; }}
    QLabel#TitreSection {{
        color: {SB_TITRE}; font-size: 8pt; font-weight: 700;
        letter-spacing: 1px; padding-bottom: 1px;
        border-bottom: 1px solid {SB_FILET};
    }}
    QPushButton#EntreeMenu, QPushButton#ActionMenu {{
        text-align: left; padding: 3px 8px; min-height: 22px;
        border: 1px solid {SB_BOUTON_CADRE}; border-radius: 4px;
        background: {SB_BOUTON}; color: {SB_BOUTON_TEXTE};
    }}
    QPushButton#EntreeMenu:hover, QPushButton#ActionMenu:hover {{
        background: {SB_SURVOL}; border-color: {SB_SURVOL_CADRE};
    }}
    QPushButton#EntreeMenu:pressed, QPushButton#ActionMenu:pressed {{
        background: {SB_ACTIF};
    }}
    /* Le curseur clavier se voit : bord bleu de 2 px, le retrait perd 1 px
       pour que le bouton garde sa taille (audit du 12/10/2026). */
    QPushButton#EntreeMenu:focus, QPushButton#ActionMenu:focus {{
        border: 2px solid {SB_SURVOL_CADRE}; padding: 2px 7px;
    }}
    /* La page affichee : fond bleu pale, contour bleu, texte gras. */
    QPushButton#EntreeMenu:checked {{
        background: {SB_ACTIF}; border-color: {SB_SURVOL_CADRE};
        color: {SB_ACTIF_TEXTE}; font-weight: bold;
    }}
    /* Le bouton qui ouvre un menu (« Comparer et exporter… ») : sa fleche
       prend de la place, et son libelle, en gras quand l'une de ses pages
       est affichee, etait coupe en « exporter.. » (14/10/2026). Moins de
       retrait a droite, ou la fleche laisse deja de l'air. */
    QPushButton#EntreeMenu[avecMenu="true"] {{ padding-right: 2px; }}
    QPushButton#EntreeMenu[avecMenu="true"]:focus {{ padding-right: 1px; }}
    /* Meme parade pour la page affichee : en gras, « Restaurer une
       sauvegarde » perdait son dernier « e » (analyse du 16/10/2026). Le
       texte est cale a gauche : retirer le retrait de droite lui rend de la
       place sans le deplacer, et le bandeau garde sa largeur commune. */
    QPushButton#EntreeMenu:checked {{ padding-right: 0px; }}
    QPushButton#EntreeMenu:checked:focus {{ padding-right: 0px; }}

    /* ----- zone des pages ----- */
    QWidget#ZonePrincipale {{ background: {FOND_PAGE}; }}
    QScrollArea#ZonePage, QWidget#ContenuPage {{
        background: {FOND_PAGE}; border: none;
    }}
    QLabel#TitrePage {{ color: {ENCRE}; font-size: 18pt; font-weight: bold; }}
    QLabel#SousTitrePage {{ color: {GRIS_SOUS}; font-size: 10pt; }}

    /* Tuile du total, en haut a droite : l'allure des tuiles du Bilan. */
    QFrame#TuileTotal {{
        background: {FOND_CARTE}; border: 1px solid {CARTE_CADRE};
        border-top: 3px solid {BLEU_NUIT}; border-radius: 12px;
    }}
    QFrame#TuileTotal QLabel {{ background: transparent; }}
    QLabel#TotalLibelle {{ color: {GRIS_LIBELLE}; font-size: 8pt; font-weight: 600; }}
    QLabel#TotalValeur {{ color: {BLEU_NUIT}; font-size: 15pt; font-weight: bold; }}

    /* Carte : fond blanc, liseré gris-bleu, en-tete en degrade. Coins de
       12 px, cartes et tuiles des trois applis (choix de l'auteur du
       07/10/2026) ; bandeaux et boutons gardent 4 px. */
    QFrame#Carte {{
        background: {FOND_CARTE}; border: 1px solid {CARTE_CADRE}; border-radius: 12px;
    }}
    QFrame#Carte QLabel {{ background: transparent; }}
    QLabel#EnteteCarte {{
        background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
            stop:0 {ENTETE_HAUT}, stop:1 {ENTETE_BAS});
        color: {BLEU_NUIT}; font-weight: 600; font-size: 9pt;
        padding: 4px 10px; border-bottom: 1px solid {ENTETE_FILET};
        letter-spacing: 0.5px;
        /* 11 px : le rayon de la carte moins son liseré, sinon l'en-tete
           depasse dans les deux coins du haut. */
        border-top-left-radius: 11px; border-top-right-radius: 11px;
    }}

    /* Tuile de chiffre cle : celles du Bilan de Pecule (fond blanc, liseré,
       trait de couleur en haut — la couleur est posee tuile par tuile). */
    QFrame#TuileKpi {{
        background: {FOND_CARTE}; border: 1px solid {CARTE_CADRE}; border-radius: 12px;
    }}
    QFrame#TuileKpi QLabel {{ background: transparent; }}
    QLabel#LibelleTuile {{ color: {GRIS_LIBELLE}; font-size: 8pt; font-weight: 600; }}
    QLabel#ValeurTuile {{ font-size: 15pt; font-weight: bold; }}
    QLabel#SousTuile {{ color: {GRIS_SOUS}; font-size: 9pt; }}
    QLabel#GrandeValeur {{ font-size: 17pt; font-weight: bold; }}
    QLabel#Discret {{ color: {GRIS_SOUS}; }}
    QLabel#TexteFixe {{ font-family: Consolas; font-size: 10pt; color: {ENCRE}; }}

    /* Bandeau d'information : celui des assistants de Pecule. */
    QFrame#BandeauInfo {{
        background: {INFO_FOND}; border: 1px solid {INFO_CADRE}; border-radius: 4px;
    }}
    QFrame#BandeauInfo QLabel {{ background: transparent; color: {ENCRE}; }}

    /* Bandeau d'alerte : l'orange de Pecule (rappel de sauvegarde externe,
       meme couleur dans les trois applis). */
    QFrame#BandeauAlerte {{
        background: {ALERTE_FOND}; border: 1px solid {ALERTE_CADRE}; border-radius: 4px;
    }}
    QFrame#BandeauAlerte QLabel {{ background: transparent; color: {ALERTE_TEXTE}; }}

    /* Barre de periode (celle de Pecule). */
    QLabel#LibellePeriode {{ color: {GRIS_SOUS}; }}
    QLabel#Resume {{ color: {ENCRE}; font-weight: bold; }}
    QLabel#NomRepartition {{ color: {ENCRE}; font-weight: bold; }}
    QLabel#Verdict {{ font-weight: bold; }}
    /* Une periode de la page Tarifs, dans sa carte. */
    QFrame#BlocTarif {{
        background: {LIGNE_PAIRE}; border: 1px solid {CARTE_CADRE}; border-radius: 4px;
    }}
    QFrame#BlocTarif QLabel {{ background: transparent; }}
    QPushButton#FlechePeriode {{
        font-size: 13pt; font-weight: bold; min-width: 26px; max-width: 26px;
        padding: 0px;
    }}

    /* Page qui n'a pas pu s'afficher. */
    QFrame#BlocErreur {{
        background: {ERREUR_FOND}; border: 1px solid {ROUGE}; border-radius: 4px;
    }}
    QFrame#BlocErreur QLabel {{ background: transparent; }}
    QLabel#TitreErreur {{ color: {ROUGE}; font-weight: bold; }}
    QLabel#TexteErreur {{ color: {ERREUR_TEXTE}; }}
    QLabel#Trace {{ color: {TRACE}; font-family: Consolas; font-size: 9pt; }}

    /* Formulaires de saisie (formulaire.py) : fond blanc, libelles gris
       fonce, message d'erreur rouge sous la case fautive. Les cases ont un
       contour plus marque que celui de Fusion, trop pale sur fond blanc
       (moins de 3 pour 1). */
    QWidget#Formulaire {{ background: {FOND_CARTE}; }}
    QTabWidget#OngletsSaisie::pane {{
        border: 1px solid {CARTE_CADRE}; top: -1px; background: {FOND_CARTE};
    }}
    QWidget#Formulaire QLabel {{ background: transparent; }}
    QLabel#LibelleChamp {{ color: {GRIS_SOUS}; }}
    QLabel#MessageChamp {{ color: {ROUGE}; }}
    QWidget#Formulaire QLineEdit, QWidget#Formulaire QComboBox {{
        border: 1px solid {CHAMP_CADRE}; border-radius: 3px;
        padding: 4px 6px; background: {BLANC}; min-height: 20px;
    }}
    QWidget#Formulaire QLineEdit:focus, QWidget#Formulaire QComboBox:focus {{
        border: 2px solid {SB_SURVOL_CADRE}; padding: 3px 5px;
    }}
    /* Case obligatoire encore vide (formulaire.exiger, 09/10/2026) : cadre
       bleu de 2 px ; le padding baisse d'autant pour que le texte ne bouge
       pas. Remplie, elle reprend le cadre ordinaire. */
    QWidget#Formulaire QLineEdit[aSaisir="true"],
    QWidget#Formulaire QComboBox[aSaisir="true"] {{
        border: 2px solid {SELECTION}; padding: 3px 5px;
    }}
    /* La fleche des listes. Des qu'on retouche le contour d'une liste, Qt
       ne dessine plus sa fleche : on la redessine avec une petite image
       (fleche_bas.svg, livree avec l'application comme l'icone). */
    QWidget#Formulaire QComboBox::drop-down {{ border: none; width: 22px; }}
    QWidget#Formulaire QComboBox::down-arrow {{
        image: url("{FLECHE_BAS}"); width: 10px; height: 6px;
    }}
    QLabel#TitreDialogue {{ color: {BLEU_NUIT}; font-weight: bold; padding: 4px 0px; }}
    QPushButton#BoutonEnregistrer {{ font-weight: bold; min-height: 30px; }}

    /* Confirmation verte des petites fenetres (Mise a jour, Votre avis). */
    QLabel#Confirmation {{ color: {VERT}; }}

    /* Petits tableaux des cartes (composants.tableau) : un peu d'air de
       part et d'autre de chaque colonne. */
    QTableWidget#TableCarte::item {{ padding: 0px 8px; }}
    QTableWidget#TableCarte QHeaderView::section {{ padding: 3px 8px; }}
    QTableView#TableHistorique::item {{ padding: 0px 8px; }}
    QTableView#TableHistorique QHeaderView::section {{ padding: 3px 8px; }}

    /* Menus (« Comparer et exporter… ») : un liseré, celui des cartes, pour
       qu'ils ne flottent pas sans limite sur la page (audit du 12/10/2026). */
    QMenu {{ border: 1px solid {CARTE_CADRE}; }}

    /* Infobulles : jaune pale, texte noir. Une infobulle recoit les regles
       du widget qui la montre et de ses parents (fond transparent, texte
       colore) : cette regle, en fin de feuille, les remet d'aplomb. Audit
       de design du 03/10/2026. */
    QToolTip {{
        background: {BULLE}; color: {ENCRE_BULLE};
        border: 1px solid {CHAMP_CADRE}; padding: 3px;
    }}
    """


class StyleClair(QProxyStyle):
    """Le style « Fusion », plus des contours lisibles. Repris de Pecule
    (app.StyleClair, audit du 08/10/2026), puis etendu le 12/10/2026 avec le
    mode sombre, comme le Photovoltaique :

    - cases a cocher et boutons ronds : le contour de la charte ;
    - boutons et listes deroulantes standard : le meme contour (Fusion ne
      leur donnait que 2 pour 1 en clair, 1,6 en sombre), un bord pale une
      fois desactives, pour qu'ils n'aient plus l'air cliquables ;
    - cases de saisie : ce contour en sombre (Fusion le tire du fond de la
      page, presque noir) ;
    - dans les deux themes, un bord bleu de 2 px sur ce qui a le curseur
      clavier (WCAG 2.4.7).

    Les couleurs sont lues a la creation, donc dans le theme choisi.
    """

    def __init__(self):
        super().__init__(QStyleFactory.create("Fusion"))
        self.contour = QColor(CONTOUR_CASE)
        self.eteint = QColor(CONTOUR_ETEINT)
        self.focus = QColor(SB_SURVOL_CADRE)
        self.cadrer_les_cases = theme_actif() == "sombre"

    def _cadrer(self, painter, rect, couleur, epaisseur=1) -> None:
        """Un contour aux coins arrondis de Fusion. Le demi-pixel cale le
        trait sur une seule rangee de pixels : sans lui, il se partage entre
        deux et sort pale."""
        painter.save()
        painter.setRenderHint(painter.RenderHint.Antialiasing, True)
        painter.setPen(QPen(couleur, 1))
        painter.setBrush(Qt.NoBrush)
        for i in range(epaisseur):
            marge = 0.5 + i
            painter.drawRoundedRect(
                QRectF(rect).adjusted(marge, marge, -marge, -marge), 2, 2)
        painter.restore()

    def _case(self, painter, option) -> None:
        """Case de saisie : bleu si elle a le curseur, sinon le contour des
        controles (en sombre seulement)."""
        if option.state & QStyle.State_HasFocus:
            self._cadrer(painter, option.rect, self.focus, 2)
        elif self.cadrer_les_cases:
            self._cadrer(painter, option.rect, self.contour)

    def _bouton(self, painter, option) -> None:
        """Bouton ou liste deroulante standard : contour des controles, pale
        si desactive, bleu s'il a le curseur clavier."""
        if not option.state & QStyle.State_Enabled:
            self._cadrer(painter, option.rect, self.eteint)
        elif option.state & QStyle.State_HasFocus:
            self._cadrer(painter, option.rect, self.focus, 2)
        else:
            self._cadrer(painter, option.rect, self.contour)

    def drawComplexControl(self, control, option, painter, widget=None):
        super().drawComplexControl(control, option, painter, widget)
        if control == QStyle.CC_SpinBox and option.frame:
            self._case(painter, option)
        elif control == QStyle.CC_ComboBox and option.frame:
            self._bouton(painter, option)

    def drawPrimitive(self, element, option, painter, widget=None):
        super().drawPrimitive(element, option, painter, widget)
        # Pas dans un menu : ses lignes cochees disent la page affichee
        # (« Comparer et exporter… »), et un contour y dessinait une case
        # vide devant chaque ligne (11/10/2026).
        if isinstance(widget, QMenu):
            return
        if element == QStyle.PE_FrameLineEdit:
            self._case(painter, option)
        elif element == QStyle.PE_PanelButtonCommand:
            self._bouton(painter, option)
        elif element in (QStyle.PE_IndicatorCheckBox,
                         QStyle.PE_IndicatorItemViewItemCheck,
                         QStyle.PE_IndicatorRadioButton):
            painter.save()
            painter.setRenderHint(painter.RenderHint.Antialiasing,
                                  element == QStyle.PE_IndicatorRadioButton)
            painter.setPen(QPen(self.contour, 1))
            painter.setBrush(Qt.NoBrush)
            cadre = option.rect.adjusted(0, 0, -1, -1)
            if element == QStyle.PE_IndicatorRadioButton:
                painter.drawEllipse(cadre)
            else:
                painter.drawRect(cadre)
            painter.restore()


def appliquer_theme(app: QApplication) -> None:
    """Impose a l'application son apparence : Fusion, palette du theme
    choisi (le clair de Pecule par defaut), feuille de style.

    Le style « Fusion » est indispensable : les styles natifs de Windows
    peignent certains textes eux-memes, sans consulter la palette. Il est
    pose a travers StyleClair, qui ajoute un contour lisible aux cases."""
    # Garde une reference vivante : Qt ne garde pas l'objet Python.
    app._style_clair = StyleClair()
    app.setStyle(app._style_clair)
    app.setPalette(palette_claire())
    # Les infobulles ont leur palette a elles, prise au systeme, que
    # app.setPalette() ne touche pas : sur un Windows regle en sombre, elles
    # sortaient en gris fonce dans Pecule (audit du 03/10/2026).
    QToolTip.setPalette(palette_claire())
    app.setStyleSheet(feuille_de_style())


def installer_traduction_qt(app: QApplication) -> bool:
    """Passe en francais les boutons et messages fournis par Qt lui-meme
    (« Yes / No », « Cancel », les fenetres de choix de fichier).

    Repris de Pecule. Qt livre ses traductions (`qtbase_fr.qm`) : on les
    charge plutot que de renommer les boutons un par un. Le traducteur est
    range sur `app`, sinon il serait ramasse par Python et cesserait de
    traduire. Rend False si le fichier est introuvable : l'application
    demarre quand meme, en anglais pour ces quelques mots."""
    chemins = [QLibraryInfo.path(QLibraryInfo.TranslationsPath)]
    # Second recours : le dossier livre avec PySide6, que PyInstaller recopie
    # dans `_internal/PySide6/translations/`.
    try:
        import PySide6
        chemins.append(os.path.join(os.path.dirname(PySide6.__file__),
                                    "translations"))
    except Exception:
        pass
    for dossier in chemins:
        if not dossier or not os.path.isdir(dossier):
            continue
        traducteur = QTranslator(app)
        if traducteur.load("qtbase_fr", dossier):
            app.installTranslator(traducteur)
            app._traducteur_qt = traducteur   # garde une reference vivante
            return True
    return False
