"""Page « ⚙️ Paramètres » (28/09/2026), comme dans Pecule et le
Photovoltaique.

Les trois reglages de la voiture et de la borne y demenagent depuis le bas
de la page Tarifs, ou on ne pensait pas a les chercher ; la page montre aussi
le dossier des donnees. Donnees inventees, ecritures remplacees par des
doublures : jamais les vraies donnees.

    py -m pytest tests/test_qt_parametres.py
"""

from __future__ import annotations

import pytest

import fenetre as module_fenetre
import menu
from pages import parametres as pa
from pages import tarifs as ta
from theme_qt import ROUGE


@pytest.fixture
def fenetre(qapp, monkeypatch):
    monkeypatch.setattr(module_fenetre, "charger_donnees",
                        lambda: {"recharges": []})
    f = module_fenetre.FenetrePrincipale()
    yield f
    f.deleteLater()


def test_le_menu_a_une_rubrique_reglages():
    """Tarifs et Paramètres ensemble, comme la rubrique « Réglages » de
    Pecule ; Tarifs n'est plus avec les sauvegardes."""
    sections = {nom: [vue for vue, _, _ in items]
                for nom, items in menu.SECTIONS}
    assert sections["RÉGLAGES"] == ["tarifs", "parametres"]
    assert "tarifs" not in sections["MES DONNÉES"]
    entree = [e for _, items in menu.SECTIONS for e in items
              if e[0] == "parametres"][0]
    assert entree[1:] == ("Paramètres", "⚙️")


def test_le_bandeau_montre_le_bouton(fenetre):
    assert "parametres" in fenetre.boutons_nav
    fenetre.boutons_nav["parametres"].click()
    assert fenetre.vue_courante == "parametres"


def test_reglages(fenetre, monkeypatch):
    ecrits = []

    def enregistrer(reglages):
        ecrits.append(reglages)
        return {"decalees": 0, "laissees": []}

    monkeypatch.setattr(pa, "enregistrer_reglages_borne", enregistrer)
    page = pa.construire(fenetre)
    page.cases_reglages["rendement"].setText("120")
    page.bouton_reglages.click()
    assert ROUGE in page.message_reglages.styleSheet()
    assert ecrits == []
    page.cases_reglages["rendement"].setText("88")
    page.bouton_reglages.click()
    assert page.message_reglages.text() == "✓ Réglages enregistrés."
    assert ecrits[0]["rendement_charge"] == 0.88


def test_correction_changee_annonce_les_recharges_replacees(fenetre,
                                                           monkeypatch):
    """23/10/2026 : changer la correction replace les recharges importees ;
    le message le dit, avec leur nombre."""
    monkeypatch.setattr(pa, "enregistrer_reglages_borne",
                        lambda reglages: {"decalees": 12, "laissees": []})
    page = pa.construire(fenetre)
    page.cases_reglages["correction"].setText("0")
    page.bouton_reglages.click()
    texte = page.message_reglages.text()
    assert texte.startswith("✓ Réglages enregistrés.")
    assert "12 recharges importées replacées" in texte


def test_puissance_de_la_borne(fenetre, monkeypatch):
    """23/10/2026 : quatrieme case, facultative ; le message dit combien de
    recharges ont ete recalculees."""
    ecrits = []

    def enregistrer(reglages):
        ecrits.append(reglages)
        return {"decalees": 0, "recalculees": 30, "laissees": []}

    monkeypatch.setattr(pa, "enregistrer_reglages_borne", enregistrer)
    page = pa.construire(fenetre)
    page.cases_reglages["puissance"].setText("7,4")
    page.bouton_reglages.click()
    assert ecrits[0]["puissance_borne_kw"] == 7.4
    assert ("Coût de 30 recharges à la maison recalculé"
            in page.message_reglages.text())


def test_la_page_tarifs_ne_garde_que_les_prix(fenetre, monkeypatch):
    monkeypatch.setattr(ta, "charger_tarifs", lambda: [])
    page = ta.construire(fenetre)
    assert not hasattr(page, "cases_reglages")
    # Le sous-titre dit ce que la page contient, sans redire le titre de
    # sa premiere carte (audit de design du 03/10/2026).
    assert "Grille tarifaire" not in menu.TITRES["tarifs"][1]
    assert "prix de l'électricité" in menu.TITRES["tarifs"][1]


def test_le_dossier_des_donnees(fenetre, monkeypatch, tmp_path):
    monkeypatch.setattr(pa, "dossier_donnees", lambda: tmp_path)
    ouverts = []
    monkeypatch.setattr(pa.QDesktopServices, "openUrl",
                        lambda url: ouverts.append(url.toLocalFile()) or True)
    page = pa.construire(fenetre)
    assert str(tmp_path) in page.chemin_donnees.text()
    page.bouton_ouvrir_dossier.click()
    assert [p.replace("/", "\\") for p in ouverts] == [str(tmp_path)]
