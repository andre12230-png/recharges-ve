"""Pages portees a l'etape 2 de la migration PySide6 : Tableau de bord,
Notice, Restaurer — et le changement de periode de bout en bout.

Donnees inventees, injectees a la place des fonctions de lecture : jamais
les vraies recharges.

    py -m pytest tests/test_qt_pages_etape2.py
"""

from __future__ import annotations

from datetime import datetime

import pytest
from PySide6.QtWidgets import QLabel, QMessageBox, QPushButton

import fenetre as module_fenetre
from filtres import mois_en_cours
from notice_texte import SECTIONS
from pages import notice, restaurer, tableau_de_bord as tdb
from pages.periode import BarrePeriode

MAINTENANT = datetime.now()
CE_MOIS = f"{MAINTENANT.year}-{MAINTENANT.month:02d}"

RECHARGES = [
    {"date": f"{CE_MOIS}-01T23:00", "lieu": "maison", "kwh": 20.0,
     "kwh_hc": 15.0, "cout_eur": 3.0, "tarif_nom": "Mon contrat HP/HC"},
    {"date": f"{CE_MOIS}-02T12:00", "lieu": "exterieur", "kwh": 10.0,
     "cout_eur": 5.0, "operateur": "E.Leclerc", "prix_kwh": 0.5},
    {"date": "2020-01-05T10:00", "lieu": "maison", "kwh": 7.0,
     "kwh_hc": 7.0, "cout_eur": 1.0, "tarif_nom": "Ancien"},
]


def textes(widget) -> list[str]:
    return [e.text() for e in widget.findChildren(QLabel)]


@pytest.fixture
def donnees(monkeypatch):
    """Remplace les lectures du tableau de bord par des donnees inventees."""
    monkeypatch.setattr(tdb, "charger_donnees", lambda: {"recharges": RECHARGES})
    monkeypatch.setattr(tdb, "rappel_releve_km", lambda: "")
    monkeypatch.setattr(tdb, "calculer_abonnement",
                        lambda debut, fin: {"total": 20.50, "jours": 30})
    monkeypatch.setattr(tdb, "calculer_consommation", lambda: {
        "n_releves": 2, "km": 1234.0, "kwh": 200.0, "cout_100": 3.456,
        "controle": {"verdict": "energie_exterieure", "ecart_pct": -12.0}})
    monkeypatch.setattr(tdb, "charger_releves_km", lambda: [
        {"date": "2026-01-01T09:00"}, {"date": "2026-03-01T09:00"}])
    monkeypatch.setattr(module_fenetre, "charger_donnees",
                        lambda: {"recharges": RECHARGES})


@pytest.fixture
def fenetre(qapp, donnees):
    f = module_fenetre.FenetrePrincipale()
    f.afficher_vue("dashboard")
    yield f
    f.deleteLater()


# ---------- tableau de bord : les calculs ----------

def test_chiffres_du_mois(donnees):
    c = tdb.chiffres_de_la_periode(RECHARGES, mois_en_cours())
    assert c["n"] == 2
    assert c["kwh"] == 30.0
    assert c["cout"] == 8.0
    assert c["prix_moyen"] == pytest.approx(8 / 30)
    assert c["maison"]["pct_hc"] == pytest.approx(75.0)
    assert c["maison"]["abonnement"] == {"total": 20.50, "jours": 30}
    assert c["exterieur"]["prix"] == pytest.approx(0.5)
    # Les plus recentes d'abord.
    assert [r["lieu"] for r in c["dernieres"]] == ["exterieur", "maison"]


def test_chiffres_sur_tout(donnees):
    c = tdb.chiffres_de_la_periode(RECHARGES, "Tout")
    assert c["n"] == 3
    assert c["cout"] == 9.0


def test_une_periode_vide_ne_divise_pas_par_zero(donnees):
    c = tdb.chiffres_de_la_periode([], "Tout")
    assert (c["n"], c["prix_moyen"], c["maison"]["pct_hc"]) == (0, 0, 0)
    assert c["exterieur"]["prix"] == 0


def test_ligne_d_une_recharge_exterieure():
    """Les « 5 dernières recharges » sont un tableau aux colonnes de
    l'Historique (audit de design du 03/10/2026)."""
    from pages.historique import cellules
    ligne = cellules(RECHARGES[1])
    # Nombres a la francaise, mais le point de « E.Leclerc » est garde.
    assert ligne[2:5] == ("10,00", "5,00", "0,5000")
    assert ligne[5] == "E.Leclerc"


def test_cout_des_kilometres(donnees):
    km = tdb.cout_des_kilometres()
    assert km["cout_100"] == 3.456
    assert km["part_exterieure"] == 12.0


def test_pas_de_cout_au_km_sans_deux_releves(monkeypatch):
    monkeypatch.setattr(tdb, "calculer_consommation", lambda: {
        "n_releves": 1, "km": 0, "kwh": 0, "cout_100": 0,
        "controle": {"verdict": "trop_court"}})
    assert tdb.cout_des_kilometres() is None


# ---------- tableau de bord : la page ----------

def test_la_page_affiche_les_tuiles(fenetre):
    page = fenetre.zone_page.widget()
    tuiles = page.findChildren(type(tdb.tuile("", "", "#000000")))
    valeurs = [t._valeur.text() for t in tuiles if hasattr(t, "_valeur")]
    assert valeurs[0] == "2"
    tout = " ".join(textes(page)).replace(" ", " ").replace(" ", " ")
    assert "RECHARGES" in tout and "PRIX MOYEN" in tout
    # Le pourcentage dit sa base (charte, audit du 08/10/2026).
    assert "75,0 % de ces kWh en heures creuses" in tout
    assert "3,46 €/100 km" in tout
    assert "environ 12 % de votre énergie" in tout
    assert fenetre._derniere_erreur == ""


def test_sans_aucune_recharge_la_page_dit_comment_commencer(qapp, donnees,
                                                           monkeypatch):
    """Audit du 08/10/2026 : « Aucune recharge enregistrée. » ne disait pas
    quoi faire. La carte des dernieres recharges donne la suite."""
    from filtres import conseil_si_vide
    monkeypatch.setattr(tdb, "charger_donnees", lambda: {"recharges": []})
    f = module_fenetre.FenetrePrincipale()
    try:
        page = tdb.construire(f)
        assert any(conseil_si_vide(True) in t for t in textes(page))
    finally:
        f.deleteLater()


def test_rappel_du_tarif_manquant():
    """Audit du 08/10/2026 : sans tarif, le tableau de bord affichait des
    0,00 € sans dire pourquoi ; on ne l'apprenait qu'en enregistrant."""
    assert "⚡ Tarifs" in tdb.rappel_tarif_manquant([])
    assert tdb.rappel_tarif_manquant([{"id": "t"}]) == ""


def test_le_rappel_cite_le_bouton_du_menu():
    """Le rappel nomme le bouton tel que le menu l'affiche, emoji compris :
    on doit le reconnaître à gauche (11/10/2026, 💶 devenu ⚡)."""
    import menu
    bouton = next(f"{picto} {texte}" for _, items in menu.SECTIONS
                  for vue_id, texte, picto in items if vue_id == "tarifs")
    assert f"« {bouton} »" in tdb.rappel_tarif_manquant([])


def test_la_page_montre_le_rappel_du_tarif(qapp, donnees, monkeypatch):
    monkeypatch.setattr(tdb, "charger_tarifs", lambda: [])
    f = module_fenetre.FenetrePrincipale()
    try:
        page = tdb.construire(f)
        assert any("⚡ Tarifs" in t for t in textes(page))
    finally:
        f.deleteLater()


def test_changer_de_periode_reconstruit_la_page(fenetre, qapp):
    """Un clic sur « Tout » : le filtre change, la page se reconstruit (un
    instant plus tard), la tuile du total suit."""
    barre = fenetre.zone_page.widget().findChild(BarrePeriode)
    barre._changer_annee("Tout")
    qapp.processEvents()
    assert fenetre.filtre_periode_dashboard == "Tout"
    nouvelle = fenetre.zone_page.widget().findChild(BarrePeriode)
    assert nouvelle is not barre
    assert nouvelle.menu_annee.currentText() == "Toute la période"
    assert nouvelle.menu_annee.currentData() == "Tout"
    assert fenetre.bilan_titre.text() == "DÉPENSE · DEPUIS LE DÉBUT"


# ---------- notice ----------

def test_la_notice_montre_toutes_les_sections(qapp, fenetre):
    fenetre.afficher_vue("notice")
    page = fenetre.zone_page.widget()
    tout = textes(page)
    for titre, _ in SECTIONS:
        assert titre.upper() in tout, titre
    assert any("vos données :" in t for t in tout)


def test_la_notice_se_construit_seule(qapp):
    page = notice.construire(None)
    assert len(page.findChildren(QLabel)) > 2 * len(SECTIONS)


# ---------- restaurer ----------

FICHES = [
    {"date": datetime(2026, 9, 24, 10, 5), "n_recharges": 120,
     "taille": 51200, "quotidienne": True, "chemin": "b1.json"},
    {"date": datetime(2026, 9, 20, 9, 0), "n_recharges": None,
     "taille": 1024, "quotidienne": False, "chemin": "b2.json"},
]


@pytest.fixture
def sauvegardes(monkeypatch):
    monkeypatch.setattr(restaurer, "lister_backups", lambda: FICHES)
    monkeypatch.setattr(restaurer, "charger_donnees",
                        lambda: {"recharges": RECHARGES})


def test_liste_des_sauvegardes(qapp, sauvegardes):
    page = restaurer.construire(None)
    tout = textes(page)
    assert "SAUVEGARDES DISPONIBLES" in tout
    assert "Vos données actuelles : 3 recharges." in tout
    assert page.tableau.lignes[0] == restaurer.cellules_sauvegarde(FICHES[0])
    # La sauvegarde illisible est montree, sans bouton.
    assert page.tableau.lignes[1][1] == "illisible"
    assert len(page.boutons) == 1


def test_restaurer_demande_confirmation(qapp, sauvegardes, monkeypatch):
    appels = []
    monkeypatch.setattr(restaurer, "restaurer_backup",
                        lambda chemin: appels.append(chemin) or 120)
    questions = []
    monkeypatch.setattr(restaurer, "confirmer",
                        lambda *a, **k: questions.append(k) or False)
    restaurer._restaurer(None, FICHES[0])
    assert appels == []               # « Garder mes données » : rien n'est fait
    # Le bouton dit l'action, et c'est « Garder » qui est propose par defaut
    # (audit de design du 03/10/2026 : Qt mettait « Oui »).
    assert questions[0]["action"] == "Restaurer cette sauvegarde"
    assert questions[0]["garder"] == "Garder mes données"


def test_restaurer_apres_confirmation(qapp, sauvegardes, monkeypatch):
    appels, infos = [], []
    monkeypatch.setattr(restaurer, "restaurer_backup",
                        lambda chemin: appels.append(chemin) or 120)
    monkeypatch.setattr(restaurer, "confirmer", lambda *a, **k: True)
    monkeypatch.setattr(QMessageBox, "information",
                        lambda *a, **k: infos.append(a[2]))

    from PySide6.QtCore import QObject

    class Fenetre(QObject):          # un objet Qt : la page s'y attache
        def afficher_vue(self, vue):
            pass
    restaurer._restaurer(Fenetre(), FICHES[0])
    assert appels == ["b1.json"]
    assert infos and infos[0].startswith("120 recharges restaurées")


def test_bouton_restaurer_present(qapp, sauvegardes):
    page = restaurer.construire(None)
    assert [b.text() for b in page.findChildren(QPushButton)] == ["Restaurer"]


# ---------- audit de design du 03/10/2026 : zeros trompeurs ----------

def test_un_lieu_sans_recharge_n_affiche_pas_de_faux_chiffres(qapp):
    """Sans recharge exterieure, l'ecran disait « Prix moyen : 0,0000 €/kWh »
    et « 0,00 € » en couleur : un tiret, et un zero sans couleur."""
    from theme_qt import ALERTE_TEXTE
    cadre = tdb._bloc_lieu("Extérieur", 0, 0.0, 0.0,
                           [tdb.ligne_prix_moyen(0, 0.0)], ALERTE_TEXTE)
    tout = textes(cadre)
    assert "Prix moyen : —" in tout
    montant = [e for e in cadre.findChildren(QLabel)
               if e.objectName() == "GrandeValeur"][0]
    assert montant.text().startswith("0,00")
    assert ALERTE_TEXTE not in montant.styleSheet()
    assert tdb.ligne_prix_moyen(2, 0.5) == "Prix moyen : 0,5000\xa0€/kWh"
