"""Theme de la version PySide6 (theme_qt.py) : les couleurs de Pecule,
lisibles partout, et insensibles au mode sombre de Windows.

    py -m pytest tests/test_qt_theme.py
"""

from __future__ import annotations

import re

import pytest
from PySide6.QtGui import QColor, QPalette

import theme_qt as t


def luminance(couleur: str) -> float:
    """Luminance relative d'une couleur #rrggbb (definition WCAG)."""
    def canal(c: int) -> float:
        c = c / 255
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b = (int(couleur[i:i + 2], 16) for i in (1, 3, 5))
    return 0.2126 * canal(r) + 0.7152 * canal(g) + 0.0722 * canal(b)


def contraste(texte: str, fond: str) -> float:
    a, b = sorted((luminance(texte), luminance(fond)), reverse=True)
    return (a + 0.05) / (b + 0.05)


# (texte, fond, ou on le voit). Chaque couple REELLEMENT employe par la
# feuille de style ou la palette ; minimum 4,5 pour 1.
COUPLES = [
    (t.ENCRE, t.CREME, "texte des fenetres et des boutons"),
    (t.ENCRE, t.BLANC, "texte des champs et des cartes"),
    (t.ENCRE, t.FOND_PAGE, "titre de la page"),
    (t.ENCRE, t.LIGNE_PAIRE, "ligne paire d'un tableau"),
    (t.ENCRE, t.BULLE, "info-bulle"),
    (t.BLANC, t.SELECTION, "ligne selectionnee"),
    (t.GRIS_PALE, t.BLANC, "texte d'invite d'une case vide"),
    (t.LIEN, t.BLANC, "lien"),
    (t.BLEU_NUIT, t.CREME, "nom de l'application (bandeau)"),
    (t.SB_TITRE, t.CREME, "titres de section du bandeau"),
    (t.SB_BOUTON_TEXTE, t.SB_BOUTON, "bouton du menu"),
    (t.SB_BOUTON_TEXTE, t.SB_SURVOL, "bouton du menu survole"),
    (t.BLEU_NUIT, t.SB_ACTIF, "page affichee (bouton coche)"),
    (t.GRIS_SOUS, t.FOND_PAGE, "sous-titre de la page"),
    (t.GRIS_LIBELLE, t.BLANC, "intitule d'une tuile"),
    (t.BLEU_NUIT, t.BLANC, "valeur d'une tuile"),
    (t.BLEU_NUIT, t.ENTETE_BAS, "en-tete de carte (bas du degrade)"),
    (t.BLEU_NUIT, t.ENTETE_HAUT, "en-tete de carte (haut du degrade)"),
    (t.ROUGE, t.BLANC, "montant defavorable, suppression"),
    (t.ROUGE, t.ERREUR_FOND, "titre du bloc d'erreur"),
    (t.ERREUR_TEXTE, t.ERREUR_FOND, "texte du bloc d'erreur"),
    (t.TRACE, t.ERREUR_FOND, "detail technique"),
    (t.VERT, t.BLANC, "montant favorable, confirmation sur une carte"),
    (t.VERT, t.CREME, "confirmation dans une petite fenetre"),
    (t.GRIS_SOUS, t.BLANC, "libelle d'une case, aide discrete"),
    (t.ALERTE_TEXTE, t.ALERTE_FOND, "bandeau d'alerte"),
    # Le fond ivoire des cartes et formulaires (25/09/2026) : les textes qui
    # s'y posent restent lisibles.
    (t.ENCRE, t.FOND_CARTE, "texte d'une carte"),
    (t.GRIS_SOUS, t.FOND_CARTE, "libelle d'une case, aide discrete (carte)"),
    (t.GRIS_LIBELLE, t.FOND_CARTE, "intitule d'une tuile (carte)"),
    (t.ROUGE, t.FOND_CARTE, "message sous une case"),
    (t.VERT, t.FOND_CARTE, "confirmation, montant favorable (carte)"),
    (t.ALERTE_TEXTE, t.FOND_CARTE, "montant de la tuile prix moyen"),
    (t.BLEU_NUIT, t.FOND_CARTE, "valeur d'une tuile (carte)"),
    (t.ENCRE, t.INFO_FOND, "bandeau d'information"),
]


@pytest.mark.parametrize("texte, fond, ou", COUPLES,
                         ids=[c[2] for c in COUPLES])
def test_chaque_texte_est_lisible(texte, fond, ou):
    assert contraste(texte, fond) >= 4.5, (
        f"{ou} : {texte} sur {fond} = {contraste(texte, fond):.2f} pour 1")


# Contour de ce qu'on clique : 3 pour 1 au moins sur son fond (regle du
# 15/09/2026, la meme que dans le Photovoltaique).
CADRES_CLIQUABLES = [
    (t.SB_BOUTON_CADRE, t.SB_BOUTON, "bouton du menu"),
    (t.SB_BOUTON_CADRE, t.CREME, "bouton du menu, cote bandeau"),
    (t.SB_SURVOL_CADRE, t.SB_SURVOL, "bouton du menu survole"),
    (t.SB_SURVOL_CADRE, t.SB_ACTIF, "page affichee"),
    (t.CHAMP_CADRE, t.BLANC, "case de saisie"),
    (t.SELECTION, t.BLANC, "case de saisie qui a le curseur"),
    (t.GRAPHE_ENERGIE, t.BLANC, "barres du graphique"),
    (t.GRAPHE_COUT, t.BLANC, "courbe du graphique"),
    (t.CHAMP_CADRE, t.FOND_CARTE, "case de saisie, cote carte"),
    (t.GRAPHE_ENERGIE, t.FOND_CARTE, "barres du graphique (fond ivoire)"),
    (t.GRAPHE_COUT, t.FOND_CARTE, "courbe du graphique (fond ivoire)"),
]


@pytest.mark.parametrize("cadre, fond, ou", CADRES_CLIQUABLES,
                         ids=[c[2] for c in CADRES_CLIQUABLES])
def test_chaque_contour_cliquable_se_voit(cadre, fond, ou):
    assert contraste(cadre, fond) >= 3.0, (
        f"{ou} : {cadre} sur {fond} = {contraste(cadre, fond):.2f} pour 1")


def test_le_texte_grise_reste_visible():
    """Desactive, un libelle s'efface sans disparaitre (3 pour 1 au moins,
    comme dans Pecule)."""
    assert contraste(t.GRIS_PALE, t.CREME) >= 3.0


# Les seuls noms en majuscules qui ne sont pas des couleurs : le reglage
# du theme (mode sombre, 12/10/2026).
PAS_DES_COULEURS = {"ORGANISATION_PREFERENCES", "CLE_THEME", "_THEME_ACTIF"}


def test_toutes_les_couleurs_sont_bien_ecrites():
    for nom, valeur in vars(t).items():
        if (nom.isupper() and isinstance(valeur, str)
                and nom not in PAS_DES_COULEURS):
            assert re.fullmatch(r"#[0-9A-Fa-f]{6}", valeur), nom


def test_les_couleurs_sont_celles_de_pecule():
    """Decision du 25/09/2026 : les trois applications suivent Pecule.
    Les couleurs de base ne doivent pas deriver (comptesbudget/app.py)."""
    assert (t.CREME, t.BLANC, t.ENCRE, t.SELECTION) == (
        "#ECE9D8", "#FFFFFF", "#000000", "#316AC5")
    assert (t.CARTE_CADRE, t.BLEU_NUIT) == ("#BEC7D4", "#1F3A6B")


def test_le_contour_des_cartes_se_voit_sur_le_creme():
    """Contour decoratif : 1,3 pour 1 au moins (regle du Photovoltaique)."""
    assert contraste(t.CARTE_CADRE, t.FOND_PAGE) >= 1.3
    assert contraste(t.CARTE_CADRE, t.FOND_CARTE) >= 1.3


def test_les_pages_ont_le_fond_du_bandeau():
    """Demande de l'auteur du 25/09/2026 : le fond des pages en harmonie avec le
    reste de l'application — le creme du bandeau, comme les pages
    ordinaires de Pecule, et non plus le gris-bleu de son Bilan."""
    assert t.FOND_PAGE == t.CREME


def test_la_palette_ignore_le_mode_sombre_de_windows(qapp):
    """Sur un poste regle en sombre, Qt fournit une palette a textes blancs.
    Le theme doit tout remplacer, fonds ET textes (defaut vu dans Pecule le
    16/09/2026)."""
    sombre = QPalette()
    for role in (QPalette.Window, QPalette.Base, QPalette.Button):
        sombre.setColor(role, QColor("#202020"))
    for role in (QPalette.WindowText, QPalette.Text, QPalette.ButtonText):
        sombre.setColor(role, QColor("#FFFFFF"))
    qapp.setPalette(sombre)

    t.appliquer_theme(qapp)

    palette = qapp.palette()
    assert palette.color(QPalette.Window).name().upper() == t.CREME
    assert palette.color(QPalette.WindowText).name().upper() == t.ENCRE
    assert palette.color(QPalette.Text).name().upper() == t.ENCRE
    assert palette.color(QPalette.Base).name().upper() == t.BLANC
    # Une feuille de style posee, Qt enveloppe le style dans un intermediaire
    # sans nom (QStyleSheetStyle) : on la retire un instant pour lire le style
    # qui est dessous, puis on la remet.
    qapp.setStyleSheet("")
    # Fusion, a travers StyleClair (contour des cases, 08/10/2026).
    assert qapp.style().baseStyle().name().lower() == "fusion"
    t.appliquer_theme(qapp)


def test_la_feuille_de_style_vise_les_elements_par_leur_nom():
    """Une regle « QFrame { ... } » descendrait sur chaque libelle (un QLabel
    est un QFrame) : toutes les regles de cadre visent un nom."""
    feuille = t.feuille_de_style()
    assert not re.search(r"(^|\})\s*QFrame\s*\{", feuille)
    for nom in ("Bandeau", "EntreeMenu", "TitreSection", "TuileTotal",
                "Carte", "EnteteCarte", "BlocErreur"):
        assert f"#{nom}" in feuille, nom


def _regle(feuille: str, objet: str) -> str:
    """Le contenu de la regle « QFrame#<objet> { ... } » (ou QLabel#...)."""
    regle = re.search(r"Q(?:Frame|Label)#%s\s*\{([^}]*)\}" % objet, feuille)
    assert regle, f"pas de regle #{objet}"
    return regle.group(1)


def test_cartes_et_tuiles_arrondies_a_12_px():
    """Choix de l'auteur du 07/10/2026 pour les trois applis : cartes et
    tuiles a 12 px (bandeaux et boutons gardent 4 px). L'en-tete bleute
    arrondit ses coins du haut a 11 px, sinon il depasse de la carte."""
    feuille = t.feuille_de_style()
    for nom in ("Carte", "TuileKpi", "TuileTotal"):
        assert re.findall(r"border-radius:\s*(\d+)px",
                          _regle(feuille, nom)) == ["12"], nom
    entete = _regle(feuille, "EnteteCarte")
    assert re.search(r"border-top-left-radius:\s*11px", entete)
    assert re.search(r"border-top-right-radius:\s*11px", entete)
    # Les bandeaux restent a 4 px.
    assert "border-radius: 4px" in _regle(feuille, "BandeauAlerte")



def test_la_fleche_des_listes_est_livree():
    """Des qu'on retouche le contour d'une liste, Qt ne dessine plus sa
    fleche : la feuille de style la redessine avec fleche_bas.svg. Si le
    fichier manque, les listes perdent leur fleche sans aucune erreur."""
    from constantes import chemin_ressource
    fleche = chemin_ressource("fleche_bas.svg")
    assert fleche.is_file()
    assert fleche.as_posix() in t.feuille_de_style()


def test_infobulles_en_clair(qapp):
    """Les infobulles ont leur palette a elles, prise au systeme :
    app.setPalette() ne la touche pas. Sur un Windows regle en sombre, elles
    sortaient en gris fonce (vu dans Pecule). Audit de design du 03/10/2026 :
    Recharges VE ne la posait pas."""
    from PySide6.QtGui import QPalette
    from PySide6.QtWidgets import QToolTip
    from theme_qt import BULLE, ENCRE, appliquer_theme, feuille_de_style

    appliquer_theme(qapp)
    pal = QToolTip.palette()
    assert pal.color(QPalette.ToolTipBase).name().upper() == BULLE
    assert pal.color(QPalette.ToolTipText).name().upper() == ENCRE
    # Et la feuille de style les vise aussi : une regle posee sur un parent
    # (fond transparent, texte colore) ne doit pas deteindre sur elles.
    assert "QToolTip" in feuille_de_style()


# Les couleurs de la charte commune aux trois applis (skill charte-applis),
# et les exceptions voulues, avec leur raison.
PALETTE_CHARTE = {
    "#ECE9D8", "#FAF8F1", "#BEC7D4", "#E8EEF7", "#C9D6E8", "#B0BFD3",
    "#FFFFFF", "#F5F5F0", "#000000", "#555555", "#666666",
    "#5A5A5A", "#A9A9A9", "#316AC5", "#FCFCFC", "#808080", "#222222",
    "#EAF2FB", "#D8E7F7", "#6F7885", "#1F3A6B", "#18733A", "#BC3729",
    "#FEF5E7", "#E67E22", "#7E5109", "#FFFBE6", "#E8D77B", "#FDEDEB",
    "#E74C3C", "#7B241C", "#EAF6EC", "#229954", "#1A5E32", "#0B5AA8",
    "#6A3FA0", "#FFFFDC",
    # Ajoutees a la charte le 12/10/2026, avec le mode sombre : bord d'un
    # controle desactive, grille des graphiques.
    "#C8D0DC", "#E2E8F0",
}
EXCEPTIONS = {
    "GRAPHE_ENERGIE": "barres du graphique : pas du texte (3,4 pour 1)",
    "GRAPHE_COUT": "courbe du graphique : pas du texte (3,7 pour 1)",
}


def test_toutes_les_couleurs_sont_celles_de_la_charte():
    """Une couleur absente de la charte est une couleur a justifier (audit
    de design du 03/10/2026 : un brun, un gris-bleu « ardoise », un contour
    de case plus pale que celui de la charte)."""
    import re
    import theme_qt
    hors = {nom: valeur for nom, valeur in vars(theme_qt).items()
            if isinstance(valeur, str)
            and re.fullmatch(r"#[0-9A-Fa-f]{6}", valeur)
            and valeur.upper() not in PALETTE_CHARTE
            and nom not in EXCEPTIONS}
    assert not hors, f"Couleurs hors charte : {hors}"


def test_contour_des_cases_de_la_charte():
    import theme_qt
    assert theme_qt.CHAMP_CADRE == "#6F7885"


def test_gris_et_rouge_se_lisent_sur_le_creme():
    """08/10/2026 : #6B6B6B (4,37) et #C0392B (4,46) restaient sous 4,5 sur
    le creme ; remplaces par #666666 et #BC3729 dans les trois applis."""
    for couleur in (t.GRIS_PALE, t.ROUGE):
        assert contraste(couleur, t.CREME) >= 4.5, couleur


def test_cases_et_boutons_ronds_ont_un_contour_lisible(qapp):
    """Charte : ce qu'on clique tient 3 pour 1 ; le contour de Fusion est
    trop pale. Audit du 08/10/2026 : les boutons ronds « Prix unique » /
    « Heures pleines / creuses » de la fenetre Tarif. Modele : StyleClair de
    Pecule."""
    from PySide6.QtWidgets import QCheckBox, QRadioButton
    t.appliquer_theme(qapp)
    qapp.setStyleSheet("")
    try:
        assert isinstance(qapp.style(), t.StyleClair)
        for classe in (QCheckBox, QRadioButton):
            bouton = classe("Essai")
            bouton.resize(bouton.sizeHint())
            image = bouton.grab().toImage()
            couleurs = {image.pixelColor(x, y).name().upper()
                        for x in range(image.width())
                        for y in range(image.height())}
            assert t.CONTOUR_CASE in couleurs, classe.__name__
            bouton.deleteLater()
    finally:
        t.appliquer_theme(qapp)


def test_pas_de_case_vide_dans_un_petit_menu(qapp):
    """11/10/2026 : les lignes du petit menu « Comparer et exporter… » se
    cochent pour dire la page affichee. Le contour des cases, pose pour les
    vraies cases a cocher, y dessinait une case vide devant chaque ligne :
    on aurait dit des cases a cocher. Une ligne non cochee n'a pas de cadre,
    comme dans le Photovoltaique."""
    from PySide6.QtWidgets import QMenu
    t.appliquer_theme(qapp)
    qapp.setStyleSheet("")
    try:
        menu = QMenu()
        action = menu.addAction("Exporter")
        action.setCheckable(True)
        menu.resize(menu.sizeHint())
        image = menu.grab().toImage()
        couleurs = {image.pixelColor(x, y).name().upper()
                    for x in range(image.width())
                    for y in range(image.height())}
        assert t.CONTOUR_CASE not in couleurs
        menu.deleteLater()
    finally:
        t.appliquer_theme(qapp)
