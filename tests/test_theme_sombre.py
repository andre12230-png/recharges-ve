"""Le mode sombre (decision de l'auteur du 12/10/2026).

La palette sombre est commune aux trois applications (charte d'interface,
validee sur maquette le 12/10/2026, d'abord mise en oeuvre dans le
Photovoltaique). Ces tests verifient qu'elle tient les memes seuils de
lisibilite que la claire, que le reglage choisit le bon theme sans toucher
aux donnees, et reprennent les corrections de l'audit de design du
Photovoltaique (curseur clavier, boutons desactives, menus, infobulles).

    py -m pytest tests/test_theme_sombre.py
"""

from __future__ import annotations

import time
from collections import Counter

import pytest
from PySide6.QtCore import QEvent, QPoint, Qt
from PySide6.QtGui import QPalette
from PySide6.QtWidgets import (QComboBox, QLineEdit, QMenu,
                               QPushButton, QToolTip, QVBoxLayout, QWidget)

import theme_qt
from tests.test_qt_theme import contraste

CLAIRE, SOMBRE = theme_qt.PALETTE_CLAIRE, theme_qt.PALETTE_SOMBRE


def _poser(qapp, nom):
    """Pose un theme sur toute l'application.

    Range d'abord les fenetres laissees par les tests precedents : Qt
    redessine chaque element vivant quand le style change, et la suite
    complete passait de 1 min 45 a 10 min 40 (12/10/2026)."""
    for fenetre in qapp.topLevelWidgets():
        # Masquer, pas fermer : la fermeture d'une fenetre principale
        # demanderait quoi faire d'une saisie en cours.
        fenetre.hide()
        fenetre.deleteLater()
    qapp.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    theme_qt.choisir_theme(nom)
    theme_qt.appliquer_theme(qapp)


@pytest.fixture
def sombre(qapp):
    """Le theme sombre le temps d'un test (palette, style, feuille de style),
    puis retour au clair."""
    _poser(qapp, "sombre")
    yield SOMBRE
    _poser(qapp, "clair")


@pytest.fixture(params=["clair", "sombre"])
def theme(request, qapp):
    """Chacun des deux themes, puis retour au clair."""
    _poser(qapp, request.param)
    yield theme_qt.THEMES[request.param]
    _poser(qapp, "clair")


def _attendre(app):
    for _ in range(8):
        app.processEvents()
        time.sleep(0.01)


# ── La palette ──────────────────────────────────────────────────────────────

def test_chaque_couleur_claire_a_sa_jumelle_sombre():
    assert set(CLAIRE) == set(SOMBRE) == set(theme_qt.NOMS_DES_COULEURS)


def test_le_clair_n_a_pas_bouge():
    """Le clair reste la reference : memes valeurs qu'avant le 12/10/2026."""
    assert (CLAIRE["CREME"], CLAIRE["BLANC"], CLAIRE["ENCRE"],
            CLAIRE["FOND_CARTE"], CLAIRE["BLEU_NUIT"]) == (
        "#ECE9D8", "#FFFFFF", "#000000", "#FAF8F1", "#1F3A6B")


def test_ce_sont_les_couleurs_du_photovoltaique():
    """La meme palette sombre dans les trois applications (charte)."""
    assert (SOMBRE["CREME"], SOMBRE["FOND_CARTE"], SOMBRE["BLANC"],
            SOMBRE["ENCRE"], SOMBRE["BLEU_NUIT"], SOMBRE["VERT"],
            SOMBRE["ROUGE"]) == ("#1C1B18", "#262521", "#302F2B", "#EDEAE2",
                                 "#A9C2EC", "#5CC281", "#F2806F")


# (texte, fond) : les memes paires que tests/test_qt_theme.py, par leur nom.
TEXTES = [
    ("ENCRE", "CREME"), ("ENCRE", "BLANC"), ("ENCRE", "FOND_PAGE"),
    ("ENCRE", "LIGNE_PAIRE"), ("ENCRE_BULLE", "BULLE"),
    ("TEXTE_SELECTION", "SELECTION"), ("GRIS_PALE", "BLANC"),
    ("LIEN", "BLANC"), ("LIEN_VU", "BLANC"), ("BLEU_NUIT", "CREME"),
    ("SB_TITRE", "CREME"), ("SB_BOUTON_TEXTE", "SB_BOUTON"),
    ("SB_BOUTON_TEXTE", "SB_SURVOL"), ("SB_ACTIF_TEXTE", "SB_ACTIF"),
    ("GRIS_SOUS", "FOND_PAGE"), ("GRIS_LIBELLE", "BLANC"),
    ("BLEU_NUIT", "BLANC"), ("BLEU_NUIT", "ENTETE_BAS"),
    ("BLEU_NUIT", "ENTETE_HAUT"), ("ROUGE", "BLANC"),
    ("ROUGE", "ERREUR_FOND"), ("ERREUR_TEXTE", "ERREUR_FOND"),
    ("TRACE", "ERREUR_FOND"), ("VERT", "BLANC"), ("VERT", "CREME"),
    ("GRIS_SOUS", "BLANC"), ("ALERTE_TEXTE", "ALERTE_FOND"),
    ("ENCRE", "FOND_CARTE"), ("GRIS_SOUS", "FOND_CARTE"),
    ("GRIS_LIBELLE", "FOND_CARTE"), ("ROUGE", "FOND_CARTE"),
    ("VERT", "FOND_CARTE"), ("ALERTE_TEXTE", "FOND_CARTE"),
    ("BLEU_NUIT", "FOND_CARTE"), ("ENCRE", "INFO_FOND"),
    ("ROUGE", "CREME"), ("ALERTE_TEXTE", "CREME"),
]
CADRES = [
    ("SB_BOUTON_CADRE", "SB_BOUTON"), ("SB_BOUTON_CADRE", "CREME"),
    ("SB_SURVOL_CADRE", "SB_SURVOL"), ("SB_SURVOL_CADRE", "SB_ACTIF"),
    ("SB_SURVOL_CADRE", "BLANC"), ("CHAMP_CADRE", "BLANC"),
    ("CHAMP_CADRE", "FOND_CARTE"), ("CONTOUR_CASE", "CREME"),
    ("CONTOUR_CASE", "FOND_CARTE"), ("GRAPHE_ENERGIE", "FOND_CARTE"),
    ("GRAPHE_COUT", "FOND_CARTE"),
]


@pytest.mark.parametrize("nom", ["clair", "sombre"])
@pytest.mark.parametrize("texte, fond", TEXTES,
                         ids=[f"{a}-sur-{b}" for a, b in TEXTES])
def test_chaque_texte_est_lisible(nom, texte, fond):
    p = theme_qt.THEMES[nom]
    assert contraste(p[texte], p[fond]) >= 4.5, (
        f"{nom} : {texte} {p[texte]} sur {fond} {p[fond]}")


@pytest.mark.parametrize("nom", ["clair", "sombre"])
@pytest.mark.parametrize("cadre, fond", CADRES,
                         ids=[f"{a}-sur-{b}" for a, b in CADRES])
def test_chaque_contour_cliquable_se_voit(nom, cadre, fond):
    p = theme_qt.THEMES[nom]
    assert contraste(p[cadre], p[fond]) >= 3.0, (
        f"{nom} : {cadre} {p[cadre]} sur {fond} {p[fond]}")


def test_le_lisere_des_cartes_se_voit_en_sombre():
    assert contraste(SOMBRE["CARTE_CADRE"], SOMBRE["FOND_PAGE"]) >= 1.3
    assert contraste(SOMBRE["CARTE_CADRE"], SOMBRE["FOND_CARTE"]) >= 1.3


def test_la_feuille_sombre_ne_garde_aucune_couleur_claire(sombre):
    """Toute couleur propre au clair restee dans la feuille sombre serait
    une tache claire (ou un texte noir) sur l'ecran sombre."""
    feuille = theme_qt.feuille_de_style().upper()
    communes = {v for k, v in CLAIRE.items() if SOMBRE[k] == v}
    restees = sorted(v for v in set(CLAIRE.values()) - communes
                     if v.upper() in feuille)
    assert not restees, f"couleurs du clair dans la feuille sombre : {restees}"


def test_choisir_le_sombre_puis_revenir_au_clair():
    try:
        assert theme_qt.choisir_theme("sombre") == "sombre"
        assert theme_qt.CREME == "#1C1B18" and theme_qt.VERT == "#5CC281"
        assert theme_qt.theme_actif() == "sombre"
    finally:
        theme_qt.choisir_theme("clair")
    assert theme_qt.CREME == "#ECE9D8" and theme_qt.VERT == "#18733A"


def test_la_palette_qt_sombre_ignore_windows(sombre, qapp):
    """Fonds ET textes remplaces, comme pour le clair : Windows ne decide
    de rien."""
    pal = qapp.palette()
    assert pal.color(QPalette.Window).name().upper() == SOMBRE["CREME"]
    assert pal.color(QPalette.WindowText).name().upper() == SOMBRE["ENCRE"]
    assert pal.color(QPalette.Base).name().upper() == SOMBRE["BLANC"]
    assert pal.color(QPalette.HighlightedText).name().upper() == "#FFFFFF"
    assert (QToolTip.palette().color(QPalette.ToolTipBase).name().upper()
            == SOMBRE["BULLE"])


# ── Le reglage ──────────────────────────────────────────────────────────────

class _Prefs:
    def __init__(self, valeur):
        self.valeur = valeur

    def value(self, cle):
        assert cle == theme_qt.CLE_THEME
        return self.valeur


def test_le_reglage_choisit_le_theme():
    assert theme_qt.nom_du_theme(_Prefs("sombre")) == "sombre"
    assert theme_qt.nom_du_theme(_Prefs("clair")) == "clair"
    # Absent ou inconnu : le clair, theme de reference.
    assert theme_qt.nom_du_theme(_Prefs(None)) == "clair"
    assert theme_qt.nom_du_theme(_Prefs("dark")) == "clair"
    assert theme_qt.nom_du_theme(None) == "clair"


def test_les_tests_n_ecrivent_jamais_dans_le_registre():
    """conftest.py envoie les preferences dans un fichier jetable."""
    import os
    from pathlib import Path
    reglages = theme_qt.preferences()
    assert (Path(reglages.fileName())
            == Path(os.environ["RECHARGES_PREFERENCES"]))


def test_l_ancienne_cle_theme_de_tarifs_json_n_est_pas_lue(tmp_path):
    """Avant la v1.24.0, tarifs.json pouvait porter "theme": "sombre". Le
    nouveau reglage vit ailleurs : ce vieux reste ne rallume rien."""
    from PySide6.QtCore import QSettings
    vierges = QSettings(str(tmp_path / "p.ini"), QSettings.Format.IniFormat)
    assert theme_qt.nom_du_theme(vierges) == "clair"


def test_les_parametres_proposent_clair_ou_sombre(qapp, monkeypatch,
                                                  tmp_path):
    """Deux boutons, Clair coche par defaut ; choisir Sombre l'enregistre
    dans les preferences (pas dans tarifs.json) et previent que cela
    s'applique au prochain demarrage."""
    from PySide6.QtCore import QSettings
    from PySide6.QtWidgets import QMessageBox

    from pages import parametres
    jetables = QSettings(str(tmp_path / "p.ini"), QSettings.Format.IniFormat)
    monkeypatch.setattr(theme_qt, "preferences", lambda: jetables)
    messages = []
    monkeypatch.setattr(QMessageBox, "information",
                        lambda *a, **k: messages.append(a[2]))
    page = QWidget()
    carte = parametres._carte_apparence(page)
    assert set(page.choix_apparence) == {"clair", "sombre"}
    assert page.choix_apparence["clair"].isChecked()
    assert carte.findChild(QWidget, "EnteteCarte").text() == "APPARENCE"

    page.choix_apparence["sombre"].click()
    assert jetables.value(theme_qt.CLE_THEME) == "sombre"
    assert len(messages) == 1 and "prochain démarrage" in messages[0]
    # La session garde son theme jusqu'au redemarrage.
    assert theme_qt.theme_actif() == "clair"

    page.choix_apparence["clair"].click()
    assert jetables.value(theme_qt.CLE_THEME) == "clair"


def test_la_page_parametres_montre_la_carte_apparence(qapp):
    from pages import parametres
    page = parametres.construire(None)
    titres = [w.text() for w in page.findChildren(QWidget, "EnteteCarte")]
    assert "APPARENCE" in titres


# ── Ce que l'audit du Photovoltaique a appris ───────────────────────────────

def _bord(widget) -> set:
    image = widget.grab().toImage()
    milieu = image.height() // 2
    return {image.pixelColor(x, y).name().upper()
            for x in (0, 1) for y in (milieu - 2, milieu, milieu + 2)}


def _deux(qapp, fabrique):
    """Deux exemplaires dans une fenetre active : le premier a le curseur.
    (Pas de WA_DontShowOnScreen : la fenetre ne serait jamais active.)"""
    fenetre = QWidget()
    couche = QVBoxLayout(fenetre)
    a, b = fabrique(), fabrique()
    couche.addWidget(a)
    couche.addWidget(b)
    fenetre.resize(240, 120)
    fenetre.show()
    fenetre.activateWindow()
    _attendre(qapp)
    a.setFocus(Qt.TabFocusReason)
    _attendre(qapp)
    assert a.hasFocus()
    return fenetre, a, b


def _bouton(nom):
    def fabrique():
        bouton = QPushButton("Recharger")
        bouton.setObjectName(nom)
        return bouton
    return fabrique


@pytest.mark.parametrize("fabrique", [_bouton(""), _bouton("EntreeMenu"),
                                      QLineEdit],
                         ids=["bouton", "EntreeMenu", "QLineEdit"])
def test_le_curseur_clavier_se_voit(theme, qapp, fabrique):
    """Arrive avec Tab sur un bouton ou une case, un bord bleu (WCAG 2.4.7)."""
    fenetre, avec, sans = _deux(qapp, fabrique)
    try:
        focus = theme["SB_SURVOL_CADRE"].upper()
        assert focus in _bord(avec), _bord(avec)
        assert focus not in _bord(sans)
    finally:
        fenetre.close()


def _bord_le_plus_net(widget, fond) -> float:
    image = widget.grab().toImage()
    y = image.height() // 2
    return max(contraste(image.pixelColor(x, y).name(), fond)
               for x in range(3))


@pytest.mark.parametrize("genre", ["bouton", "liste"])
def test_bouton_actif_bien_cerne_desactive_efface(theme, qapp, genre):
    """Actif : 3 pour 1 au moins sur la page ; desactive : nettement plus
    pale, il n'a plus l'air cliquable."""
    fenetre = QWidget()
    couche = QVBoxLayout(fenetre)
    if genre == "liste":
        actif, eteint = QComboBox(), QComboBox()
        for liste in (actif, eteint):
            liste.addItems(["Octobre", "Septembre"])
    else:
        actif, eteint = QPushButton("Ce mois-ci"), QPushButton("Ce mois-ci")
    for x in (actif, eteint):
        x.setFocusPolicy(Qt.NoFocus)
        couche.addWidget(x)
    eteint.setEnabled(False)
    fenetre.show()
    _attendre(qapp)
    try:
        net_actif = _bord_le_plus_net(actif, theme["CREME"])
        net_eteint = _bord_le_plus_net(eteint, theme["CREME"])
        assert net_actif >= 3.0, net_actif
        assert net_eteint <= net_actif * 0.6, (net_actif, net_eteint)
    finally:
        fenetre.close()


def test_la_ligne_choisie_d_une_liste_se_voit_en_sombre(sombre, qapp):
    liste = QComboBox()
    liste.addItems(["Toute l'année", "Octobre", "Septembre", "Août"])
    liste.resize(200, 26)
    liste.show()
    liste.setCurrentIndex(1)
    liste.showPopup()
    _attendre(qapp)
    vue = liste.view()
    fenetre = vue.window()
    image = fenetre.grab().toImage()

    def fond(rang):
        centre = vue.viewport().mapTo(
            fenetre, vue.visualRect(liste.model().index(rang, 0)).center())
        return image.pixelColor(image.width() - 12, centre.y()).name()
    choisie, autre = fond(1), fond(2)
    liste.hidePopup()
    liste.close()
    assert contraste(choisie, autre) >= 2.0, (choisie, autre)


def test_le_menu_a_un_bord_et_son_entree_survolee_se_voit(theme, qapp):
    menu = QMenu()
    for libelle in ("Essence ou électrique ?", "Exporter"):
        menu.addAction(libelle)
    menu.popup(QPoint(0, 0))
    menu.setActiveAction(menu.actions()[0])
    _attendre(qapp)
    try:
        image = menu.grab().toImage()
        gauche = image.pixelColor(0, image.height() // 2).name().upper()
        assert gauche == theme["CARTE_CADRE"].upper(), gauche
        x = image.width() - 6
        active = image.pixelColor(
            x, menu.actionGeometry(menu.actions()[0]).center().y()).name()
        autre = image.pixelColor(
            x, menu.actionGeometry(menu.actions()[1]).center().y()).name()
        assert contraste(active, autre) >= 1.15, (active, autre)
    finally:
        menu.close()


def test_l_infobulle_prend_les_couleurs_du_theme(theme, qapp):
    bouton = QPushButton("Paramètres")
    bouton.show()
    bouton.activateWindow()
    _attendre(qapp)
    QToolTip.showText(bouton.mapToGlobal(QPoint(5, 5)),
                      "Réglages de la voiture", bouton)
    _attendre(qapp)
    try:
        bulles = [w for w in qapp.allWidgets()
                  if w.metaObject().className() == "QTipLabel"
                  and w.isVisible()]
        assert bulles
        image = bulles[0].grab().toImage()
        couleurs = Counter(image.pixelColor(x, y).name().upper()
                           for x in range(image.width())
                           for y in range(image.height()))
        assert couleurs.most_common(1)[0][0] == theme["BULLE"].upper()
        assert theme["ENCRE_BULLE"].upper() in couleurs
    finally:
        QToolTip.hideText()
        bouton.close()


def test_la_legende_du_graphique_suit_le_theme():
    """Le noir par defaut de matplotlib disparaissait sur le fond sombre."""
    import inspect

    import graphique
    assert "labelcolor=ENCRE" in inspect.getsource(graphique)


def test_la_fleche_des_listes_se_voit_en_sombre(sombre):
    """La fleche grise des listes (#4A4A52) ne faisait que 1,4 pour 1 sur le
    fond des cases en sombre : une fleche claire, livree avec l'exe."""
    import re

    from constantes import chemin_ressource
    fleche = chemin_ressource("fleche_bas_sombre.svg")
    assert fleche.is_file()
    assert fleche.as_posix() in theme_qt.feuille_de_style()
    couleur = re.search(r'fill="(#[0-9A-Fa-f]{6})"',
                        fleche.read_text(encoding="utf-8")).group(1)
    assert contraste(couleur, SOMBRE["BLANC"]) >= 3.0, couleur


def test_la_fleche_claire_est_livree_avec_l_exe():
    """build.bat et Recharges-VE.spec la joignent, comme l'autre.

    Le .spec est regenere par PyInstaller a chaque construction et n'est pas
    suivi par git : absent d'un depot fraichement clone, il n'est verifie que
    s'il existe. build.bat, lui, est toujours verifie."""
    from pathlib import Path
    racine = Path(__file__).resolve().parent.parent
    fichiers = ["build.bat"]
    if (racine / "Recharges-VE.spec").is_file():
        fichiers.append("Recharges-VE.spec")
    for fichier in fichiers:
        assert "fleche_bas_sombre.svg" in (racine / fichier).read_text(
            encoding="utf-8", errors="replace"), fichier
