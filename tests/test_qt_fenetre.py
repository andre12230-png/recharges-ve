"""Fenetre principale de la version PySide6 (fenetre.py) — etape 1 de la
migration : bandeau, en-tete, navigation, page d'erreur, raccourcis,
sauvegardes. Les pages elles-memes sont testees dans leurs propres fichiers.

Tout se passe hors ecran, sur le dossier de donnees temporaire pose par
tests/conftest.py : jamais les vraies recharges.

    py -m pytest tests/test_qt_fenetre.py
"""

from __future__ import annotations

import json
from datetime import datetime

import pytest
from PySide6.QtWidgets import (QFileDialog, QLabel, QMessageBox, QPushButton,
                               QScrollArea)

import fenetre as module_fenetre
import menu
import recharges
import sauvegarde_externe
from constantes import APP_NAME, APP_VERSION
from filtres import annee_en_cours, mois_en_cours


@pytest.fixture
def fenetre(qapp):
    f = module_fenetre.FenetrePrincipale()
    f.afficher_vue("dashboard")
    yield f
    # Fermer sans passer par closeEvent (qui copierait les donnees).
    f.deleteLater()


@pytest.fixture
def fenetre_publiee(qapp, monkeypatch):
    """La fenetre d'une version publiee : « Votre avis » et « Mise a jour »
    presents (liens.AIDE_EN_LIGNE, voir test_sans_publication_...)."""
    import liens
    monkeypatch.setattr(liens, "AIDE_EN_LIGNE", True)
    f = module_fenetre.FenetrePrincipale()
    f.afficher_vue("dashboard")
    yield f
    f.deleteLater()


def textes(widget) -> list[str]:
    return [e.text() for e in widget.findChildren(QLabel)]


# ---------- la fenetre ----------

def test_titre_et_taille(fenetre):
    assert fenetre.windowTitle() == f"{APP_NAME} — {APP_VERSION}"
    # Tenir sur un portable 1366x768, barre des taches deduite.
    assert fenetre.minimumWidth() == 1000
    assert fenetre.minimumHeight() == 640


def test_le_bandeau_a_un_bouton_par_page(fenetre):
    assert list(fenetre.boutons_nav) == menu.pages()
    for vue_id, bouton in fenetre.boutons_nav.items():
        assert bouton.isCheckable(), vue_id


def test_publiee_avec_avis_et_mise_a_jour(fenetre):
    """Masques du 22/10/2026 au 24/10/2026, tant que l'application restait
    chez son auteur. Depuis la preparation de la premiere publication
    (24/10/2026), l'exe distribue montre « Votre avis » et « Mise a jour »,
    avec leur section de la notice."""
    import liens
    from notice_texte import SECTIONS
    assert liens.AIDE_EN_LIGNE is True
    textes_bandeau = [b.text() for b in fenetre.findChildren(QPushButton)]
    assert "💬 Votre avis" in textes_bandeau
    assert "🔄 Mise à jour" in textes_bandeau
    assert "📖 Notice" in textes_bandeau
    assert "Nouvelles versions et avis" in [titre for titre, _ in SECTIONS]


def test_l_ordre_du_bandeau(fenetre_publiee):
    """Reorganise le 28/09/2026 (demande de l'auteur) dans l'ordre de
    l'usage : saisir (les deux facons d'entrer une recharge, puis
    l'Historique pour les corriger), analyser (et exporter ce qu'on
    analyse), sauvegarder puis restaurer, regler, se faire aider."""
    from PySide6.QtWidgets import QScrollArea
    bandeau = fenetre_publiee.findChildren(QScrollArea)[0].widget()
    disposition = bandeau.layout()
    lus = []
    for i in range(disposition.count()):
        w = disposition.itemAt(i).widget()
        if w is not None and w.objectName() == "TitreSection":
            lus.append(w.text())
        elif w is not None and w.objectName() in ("EntreeMenu", "ActionMenu"):
            lus.append(w.text().split(" ", 1)[1])      # sans l'emoji
    # Fin du menu comme dans Pecule (29/09/2026) : MES DONNÉES, RÉGLAGES,
    # puis AIDE avec Notice, Votre avis, Mise à jour.
    # 11/10/2026 (choix de l'auteur) : « Essence ou électrique ? » et
    # « Exporter » passent sous un seul bouton à petit menu, comme les pages
    # occasionnelles du Photovoltaïque.
    assert lus == [
        "PRINCIPAL", "Tableau de bord", "Ajouter une recharge",
        "Importer un CSV", "Historique",
        "ANALYSE", "Statistiques", "Kilométrage", "Comparer et exporter…",
        "MES DONNÉES", "Sauvegarde externe", "Restaurer une sauvegarde",
        "RÉGLAGES", "Tarifs", "Paramètres",
        "AIDE", "Notice", "Votre avis", "Mise à jour"]


def test_les_trois_actions_sont_dans_le_bandeau(fenetre_publiee):
    """💾 / 💬 / 🔄 : des actions, jamais cochees. Une seule espace apres
    l'emoji, comme dans les deux autres applis (29/09/2026)."""
    actions = [b for b in fenetre_publiee.findChildren(QPushButton)
               if b.objectName() == "ActionMenu"]
    assert [b.text() for b in actions] == [
        "💾 Sauvegarde externe", "💬 Votre avis", "🔄 Mise à jour"]
    assert not any(b.isCheckable() for b in actions)
    # Leur libellé ne dit pas tout : une infobulle, comme dans Pécule et le
    # Photovoltaïque (ménage du bandeau, 11/10/2026).
    assert all(b.toolTip() for b in actions)


def test_espacement_du_bandeau_comme_les_autres_applis(fenetre):
    """29/09/2026 : 1 px entre deux boutons, contre 4 dans Pecule et le
    Photovoltaique ; les boutons paraissaient colles."""
    bandeau = fenetre.findChildren(QScrollArea)[0].widget()
    assert bandeau.layout().spacing() == 4
    entrees = [b for b in bandeau.findChildren(QPushButton)
               if b.objectName() == "EntreeMenu"]
    assert all("  " not in b.text() for b in entrees)


def test_comparer_et_exporter_dans_un_petit_menu(fenetre):
    """Les deux pages occasionnelles d'ANALYSE sous un seul bouton : la page
    choisie s'affiche, sa ligne est cochée et le bouton surligné ; revenir à
    une autre page les libère (11/10/2026)."""
    bouton = fenetre.bouton_comparer
    assert [a.text() for a in bouton.menu().actions()] == [
        "⛽ Essence ou électrique ?", "📤 Exporter"]
    fenetre.boutons_nav["export"].trigger()
    assert fenetre.vue_courante == "export"
    assert bouton.isChecked() and fenetre.boutons_nav["export"].isChecked()
    assert not fenetre.boutons_nav["essence"].isChecked()
    fenetre.boutons_nav["essence"].trigger()
    assert fenetre.boutons_nav["essence"].isChecked()
    assert not fenetre.boutons_nav["export"].isChecked()
    fenetre.boutons_nav["stats"].click()
    assert fenetre.vue_courante == "stats"
    assert not bouton.isChecked()
    assert not fenetre.boutons_nav["essence"].isChecked()


def test_comparer_et_exporter_pas_coupe_en_gras(fenetre):
    """Actif, donc en gras, le libelle s'affichait « exporter.. » : il lui
    manquait environ 6 px (mesure du 14/10/2026, vraies polices). Le bouton
    porte un retrait a droite reduit, que la feuille de style applique.
    (La largeur elle-meme ne se mesure pas ici : les polices des tests ne
    sont pas celles de Windows.)"""
    import theme_qt
    bouton = fenetre.bouton_comparer
    assert bouton.property("avecMenu") is True
    feuille = theme_qt.feuille_de_style()
    assert 'QPushButton#EntreeMenu[avecMenu="true"] { padding-right: 2px; }' \
        in feuille


def test_chaque_entree_du_bandeau_a_son_infobulle(fenetre_publiee):
    """11/10/2026, comme Pécule : chaque bouton du bandeau, et chaque ligne
    du petit menu, a son infobulle. Pour une page, c'est le sous-titre
    qu'elle affiche en tête. « Mise à jour » dit la même chose dans les
    trois applis."""
    bandeau = fenetre_publiee.findChildren(QScrollArea)[0].widget()
    for b in bandeau.findChildren(QPushButton):
        assert b.toolTip(), b.text()
    for vue_id, entree in fenetre_publiee.boutons_nav.items():
        assert entree.toolTip() == menu.TITRES[vue_id][1], vue_id
    maj = next(b for b in bandeau.findChildren(QPushButton)
               if b.text() == "🔄 Mise à jour")
    assert maj.toolTip() == (
        "Voir s'il existe une version plus récente (la page s'ouvre dans "
        "votre navigateur ; rien n'est vérifié automatiquement)")


def test_air_avant_les_titres_comme_pecule(fenetre):
    """6 px d'air avant chaque titre de section, 4 sous le nom de l'appli,
    comme dans Pécule (11/10/2026 ; c'était 1 px, faute de place)."""
    disposition = fenetre.findChildren(QScrollArea)[0].widget().layout()
    airs = []
    for i in range(1, disposition.count()):
        w = disposition.itemAt(i).widget()
        if w is not None and w.objectName() == "TitreSection":
            espace = disposition.itemAt(i - 1).spacerItem()
            airs.append(espace.sizeHint().height() if espace else None)
    assert airs == [4, 6, 6, 6, 6]
    # 6 px au-dessus du nom, 4 sous la version, comme les deux autres
    # applis (11/10/2026 ; c'était 2 en bas).
    assert disposition.contentsMargins().top() == 6
    assert disposition.contentsMargins().bottom() == 4


def test_nom_et_version_dans_le_bandeau(fenetre):
    tout = textes(fenetre)
    assert APP_NAME in tout
    assert APP_VERSION in tout


# ---------- navigation ----------

@pytest.mark.parametrize("vue_id", menu.pages())
def test_chaque_page_s_affiche(fenetre, vue_id):
    fenetre.afficher_vue(vue_id)
    titre, sous_titre = menu.TITRES[vue_id]
    assert fenetre.titre_vue.text() == titre
    assert fenetre.sous_titre_vue.text() == sous_titre
    assert fenetre.boutons_nav[vue_id].isChecked()
    assert fenetre.zone_page.widget() is not None
    assert fenetre._derniere_erreur == ""


def test_une_seule_page_cochee_a_la_fois(fenetre):
    fenetre.afficher_vue("stats")
    fenetre.afficher_vue("notice")
    coches = [v for v, b in fenetre.boutons_nav.items() if b.isChecked()]
    assert coches == ["notice"]


def test_une_page_en_erreur_ne_casse_pas_la_fenetre(fenetre, monkeypatch):
    """Une page qui plante affiche un bloc d'erreur lisible, avec le detail
    technique replie, au lieu de laisser un trou."""
    def plante(_fenetre):
        raise ValueError("fichier des tarifs illisible")
    monkeypatch.setitem(module_fenetre.CONSTRUCTEURS, "tarifs", plante)

    fenetre.afficher_vue("tarifs")

    assert fenetre._derniere_erreur == "ValueError: fichier des tarifs illisible"
    page = fenetre.zone_page.widget()
    assert "CETTE PAGE N'A PAS PU S'AFFICHER" in textes(page)
    trace = page.findChild(QLabel, "Trace")
    assert trace is not None and not trace.isVisibleTo(page)
    # Et la fenetre continue de servir : une autre page s'affiche.
    fenetre.afficher_vue("notice")
    assert fenetre.titre_vue.text() == "Notice"


def test_une_page_en_erreur_parle_francais(fenetre, monkeypatch):
    """29/09/2026 : la page d'erreur recopiait str(e), donc l'anglais de
    Python (« No such file or directory »). Le texte visible est en
    francais ; l'anglais ne reste que dans le detail technique replie."""
    def plante(_fenetre):
        raise FileNotFoundError(2, "No such file or directory",
                                r"C:\Donnees\tarifs.json")
    monkeypatch.setitem(module_fenetre.CONSTRUCTEURS, "tarifs", plante)

    fenetre.afficher_vue("tarifs")

    page = fenetre.zone_page.widget()
    visibles = [e.text() for e in page.findChildren(QLabel, "TexteErreur")]
    assert "Fichier « tarifs.json » introuvable." in visibles
    assert not any("No such file" in t for t in visibles)


# ---------- tuile du total ----------

@pytest.fixture
def fenetre_du_mois(qapp, monkeypatch):
    """Une fenetre dont les donnees ont une recharge ce mois-ci : elle
    s'ouvre donc sur le mois en cours (sans, sur « Toute la periode »)."""
    maintenant = datetime.now()
    du_mois = {"recharges": [{
        "id": "m", "date": f"{maintenant.year}-{maintenant.month:02d}-01T10:00",
        "lieu": "exterieur", "kwh": 10.0, "cout_eur": 5.0, "prix_kwh": 0.5}]}
    monkeypatch.setattr(module_fenetre, "charger_donnees", lambda: du_mois)
    f = module_fenetre.FenetrePrincipale()
    yield f
    f.deleteLater()


def test_total_de_la_periode_de_la_page(fenetre_du_mois):
    fenetre = fenetre_du_mois
    fenetre.afficher_vue("dashboard")
    assert fenetre.bilan_titre.text() == f"DÉPENSE · {mois_en_cours().upper()}"
    fenetre.afficher_vue("stats")
    assert fenetre.bilan_titre.text() == f"DÉPENSE · {annee_en_cours().upper()}"
    fenetre.afficher_vue("tarifs")
    assert fenetre.bilan_titre.text() == "DÉPENSE · DEPUIS LE DÉBUT"


def test_total_additionne_les_couts(fenetre, monkeypatch):
    donnees = {"recharges": [
        {"date": "2024-03-01T10:00", "cout_eur": 12.5},
        {"date": "2024-04-01T10:00", "cout_eur": 7.25},
    ]}
    monkeypatch.setattr(module_fenetre, "charger_donnees", lambda: donnees)
    fenetre.afficher_vue("tarifs")          # periode « Tout »
    assert fenetre.bilan_valeur.text().replace(" ", " ") in (
        "19,75 €", "19,75 €")


def test_ouverture_sur_le_mois_et_l_annee_en_cours(fenetre_du_mois):
    """Rien n'est memorise d'un lancement a l'autre."""
    fenetre = fenetre_du_mois
    assert fenetre.filtre_periode == mois_en_cours()
    assert fenetre.filtre_periode_dashboard == mois_en_cours()
    assert fenetre.filtre_periode_stats == annee_en_cours()
    assert fenetre.filtre_periode_export == "Tout"


# ---------- raccourcis ----------

def test_raccourcis_installes(fenetre):
    from PySide6.QtGui import QKeySequence, QShortcut
    touches = {r.key().toString() for r in fenetre.findChildren(QShortcut)}
    for attendu in ("Ctrl+S", "Ctrl+F", "F5"):
        assert QKeySequence(attendu).toString() in touches, attendu


def test_ctrl_f_ouvre_l_historique(fenetre):
    fenetre._aller_a_la_recherche()
    assert fenetre.vue_courante == "historique"


# ---------- sauvegardes ----------

def test_fermeture_copie_dans_sauvegardes_et_rien_vers_github(
        fenetre, monkeypatch):
    appels = []
    monkeypatch.setattr(sauvegarde_externe, "sauvegarder_a_la_fermeture",
                        lambda *a, **k: appels.append(a))
    monkeypatch.setattr(module_fenetre, "synchroniser_github",
                        lambda: pytest.fail("rien ne doit partir vers GitHub"))
    fenetre.close()
    assert len(appels) == 1
    fichiers = [p.name for p in appels[0][0]]
    assert fichiers == ["recharges.json", "tarifs.json"]


def test_fermeture_jamais_bloquee_par_un_echec(fenetre, monkeypatch):
    def echec(*a, **k):
        raise OSError("disque plein")
    monkeypatch.setattr(sauvegarde_externe, "sauvegarder_a_la_fermeture", echec)
    avertissements = []
    monkeypatch.setattr(QMessageBox, "warning",
                        lambda *a, **k: avertissements.append(a[1]))
    assert fenetre.close()
    assert avertissements == ["Sauvegarde à la fermeture"]


def test_sauvegarde_externe_copie_les_deux_fichiers(fenetre, monkeypatch,
                                                    tmp_path):
    dossier = recharges.dossier_donnees()
    (dossier / "recharges.json").write_text(json.dumps({"recharges": []}),
                                            encoding="utf-8")
    (dossier / "tarifs.json").write_text(json.dumps({"tarifs": []}),
                                         encoding="utf-8")
    cle = tmp_path / "cle_usb"
    cle.mkdir()
    monkeypatch.setattr(QFileDialog, "getExistingDirectory",
                        lambda *a, **k: str(cle))
    messages = []
    monkeypatch.setattr(QMessageBox, "information",
                        lambda *a, **k: messages.append(a[1]))

    fenetre._sauvegarder_externe()

    assert messages == ["Sauvegarde terminée"]
    copie = next(cle.iterdir())
    noms = {p.name for p in copie.iterdir()}
    assert {"recharges.json", "tarifs.json", "LISEZMOI.txt"} <= noms
    assert fenetre._destination_sauvegarde == str(cle)


def test_sauvegarde_externe_abandonnee(fenetre, monkeypatch):
    monkeypatch.setattr(QFileDialog, "getExistingDirectory",
                        lambda *a, **k: "")
    monkeypatch.setattr(QMessageBox, "information",
                        lambda *a, **k: pytest.fail("aucun message attendu"))
    fenetre._sauvegarder_externe()


# ---------- aide ----------

def test_fenetres_d_aide(qapp):
    from fenetres_aide import FenetreAvis, FenetreMiseAJour
    maj = FenetreMiseAJour()
    assert maj.windowTitle() == "Rechercher une mise à jour"
    assert f"Vous utilisez {APP_NAME} {APP_VERSION}." in textes(maj)
    avis = FenetreAvis()
    assert avis.btn_ouvrir.isEnabled()
    assert any(t.startswith("Votre version : ") for t in textes(avis))
