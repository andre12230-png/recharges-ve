"""Page « ⛽ Essence ou électrique ? » (28/09/2026) : la comparaison avec une
voiture essence a son bouton dans le bandeau, rubrique Analyse. Donnees
inventees, lectures remplacees : jamais les vraies donnees.

    py -m pytest tests/test_qt_essence.py
"""

from __future__ import annotations

import pytest
from PySide6.QtWidgets import QLabel

import fenetre as module_fenetre
import menu
from pages import essence as es

RELEVES = [{"id": "r1", "date": "2025-01-01T12:00", "km": 20000.0},
           {"id": "r2", "date": "2025-06-01T12:00", "km": 21000.0}]
RECHARGES = [{"id": "a", "date": "2025-03-01T22:00", "lieu": "maison",
              "kwh": 150.0, "cout_eur": 30.0}]
REGLAGE = {"conso_essence": 6.0, "prix_essence": 2.0,
           "prix_essence_annees": {}}
SANS = dict(REGLAGE, conso_essence=0.0, prix_essence=0.0)


def donnees(monkeypatch, reglage, releves=RELEVES):
    monkeypatch.setattr(es, "charger_donnees",
                        lambda: {"recharges": RECHARGES})
    monkeypatch.setattr(es, "charger_releves_km", lambda: releves)
    monkeypatch.setattr(es, "charger_config", lambda: reglage)


@pytest.fixture
def fenetre(qapp, monkeypatch):
    monkeypatch.setattr(module_fenetre, "charger_donnees",
                        lambda: {"recharges": []})
    f = module_fenetre.FenetrePrincipale()
    yield f
    f.deleteLater()


def textes(widget) -> str:
    return " ".join(e.text() for e in widget.findChildren(QLabel))


def test_le_bouton_est_dans_analyse():
    analyse = dict(menu.SECTIONS)["ANALYSE"]
    assert [v for v, _, _ in analyse] == ["stats", "km", "essence", "export"]
    assert ("essence", "Essence ou électrique ?", "⛽") in analyse
    assert menu.TITRES["essence"][0] == "Essence ou électrique ?"


def test_la_page_montre_la_comparaison(fenetre, monkeypatch):
    donnees(monkeypatch, REGLAGE)
    page = es.construire(fenetre)
    tout = textes(page)
    assert "120,00\xa0€" in tout and "30,00\xa0€" in tout and "90,00\xa0€" in tout


def test_sans_reglage_la_page_envoie_vers_parametres(fenetre, monkeypatch):
    donnees(monkeypatch, SANS)
    page = es.construire(fenetre)
    assert "Paramètres" in textes(page)


def test_sans_releves_la_page_le_dit(fenetre, monkeypatch):
    """Avec la voiture essence saisie mais moins de deux releves du
    compteur, ce qui manque, ce sont les releves : on le dit."""
    donnees(monkeypatch, REGLAGE, releves=RELEVES[:1])
    page = es.construire(fenetre)
    assert "deux relevés" in textes(page)


def test_le_bouton_ouvre_les_parametres(fenetre, monkeypatch, qapp):
    donnees(monkeypatch, REGLAGE)
    fenetre.afficher_vue("essence")
    page = es.construire(fenetre)
    page.bouton_parametres.click()
    for _ in range(5):
        qapp.processEvents()
    assert fenetre.vue_courante == "parametres"
