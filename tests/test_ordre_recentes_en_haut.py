"""Les listes datees montrent la date la plus recente en haut (10/10/2026).

Demande de l'auteur, pour les deux applis : l'Historique, les releves et les
periodes tarifaires le faisaient deja ; les frais des cartes de recharge,
le tableau « Année par année » et les prix du litre par annee allaient
encore du plus ancien au plus recent. Seul l'affichage change : tarifs.json
garde son ordre. Donnees inventees, dossier temporaire de tests/conftest.py.

    py -m pytest tests/test_ordre_recentes_en_haut.py
"""

from __future__ import annotations

import json

import pytest
from PySide6.QtWidgets import QLabel

import fenetre as module_fenetre
import recharges as r
from pages import essence as es
from pages import parametres as pa
from pages import tarifs as ta

ANCIEN = {"carte": "Réseau A", "type": "unique", "date": "2024-03-10",
          "fin": None, "montant": 20.0}
RECENT = {"carte": "Réseau B", "type": "unique", "date": "2025-05-02",
          "fin": None, "montant": 10.0}


@pytest.fixture
def fenetre(qapp, monkeypatch):
    r.TARIFS_FILE.write_text(json.dumps({"tarifs": []}), encoding="utf-8")
    monkeypatch.setattr(module_fenetre, "charger_donnees",
                        lambda: {"recharges": []})
    f = module_fenetre.FenetrePrincipale()
    yield f
    f.deleteLater()


def test_frais_de_cartes_le_plus_recent_en_haut(fenetre):
    r.ajouter_frais_carte(ANCIEN)
    r.ajouter_frais_carte(RECENT)
    page = ta.construire(fenetre)
    textes = [ligne.findChild(QLabel).text() for ligne in page.lignes_frais]
    assert "Réseau B" in textes[0] and "Réseau A" in textes[1]
    # Le fichier, lui, reste dans l'ordre chronologique.
    assert [f["carte"] for f in r.charger_frais_cartes()] == [
        "Réseau A", "Réseau B"]


def test_annee_par_annee_la_plus_recente_en_haut(fenetre, monkeypatch):
    releves = [{"id": "r1", "date": "2024-07-01T12:00", "km": 10000.0},
               {"id": "r2", "date": "2025-07-01T12:00", "km": 20000.0}]
    recharges = [{"id": "a", "date": "2025-01-10T22:00", "lieu": "maison",
                  "kwh": 100.0, "cout_eur": 20.0}]
    monkeypatch.setattr(es, "charger_donnees",
                        lambda: {"recharges": recharges})
    monkeypatch.setattr(es, "charger_releves_km", lambda: releves)
    monkeypatch.setattr(es, "charger_config", lambda: {
        "conso_essence": 6.0, "prix_essence": 2.0,
        "prix_essence_annees": {}})
    page = es.construire(fenetre)
    assert [ligne[0] for ligne in page.lignes_annees] == ["2025", "2024"]


def test_prix_du_litre_l_annee_la_plus_recente_en_premier(fenetre,
                                                           monkeypatch):
    monkeypatch.setattr(pa, "charger_donnees", lambda: {"recharges": [
        {"id": "a", "date": "2023-05-01T22:00"},
        {"id": "b", "date": "2024-05-01T22:00"}]})
    page = pa.construire(fenetre)
    annees = list(page.cases_prix_annees)
    assert annees == sorted(annees, reverse=True)
    assert annees[-1] == "2023"
