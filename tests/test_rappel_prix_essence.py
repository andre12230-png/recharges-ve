"""Rappel du prix du litre (28/09/2026).

La comparaison essence depend d'un prix saisi a la main : s'il n'est plus
touche, il vieillit sans prevenir (la raison meme pour laquelle aucun prix
n'est ecrit dans le code). Le tableau de bord le rappelle doucement, au bout
de 90 jours. Donnees inventees.

    py -m pytest tests/test_rappel_prix_essence.py
"""

from __future__ import annotations

import json
from datetime import datetime

import pytest

import recharges as r

REGLE = {"conso_essence": 5.0, "prix_essence": 2.0,
         "prix_essence_annees": {"2026": 1.9}, "prix_essence_maj": "2026-06-01"}


def rappel(config, jour):
    return r.rappel_prix_essence(config=config, aujourd_hui=jour)


def test_rien_avant_90_jours():
    assert rappel(REGLE, datetime(2026, 8, 29)) is None       # 89 jours


def test_le_rappel_au_bout_de_90_jours():
    phrase = rappel(REGLE, datetime(2026, 8, 30))
    assert "il y a 90 jours" in phrase
    # Le prix affiche est celui de l'annee en cours, s'il est saisi.
    assert "1,90\xa0€/L" in phrase and "Paramètres" in phrase


def test_prix_general_sans_prix_de_l_annee():
    config = dict(REGLE, prix_essence_annees={})
    assert "2,00\xa0€/L" in rappel(config, datetime(2026, 12, 1))


def test_rien_sans_comparaison():
    assert rappel(dict(REGLE, conso_essence=0), datetime(2027, 1, 1)) is None


def test_rien_sans_date_de_mise_a_jour():
    """Un fichier d'avant ce rappel n'a pas la date : on ne sait pas, on se
    tait plutot que de relancer a tort."""
    config = dict(REGLE)
    del config["prix_essence_maj"]
    assert rappel(config, datetime(2027, 1, 1)) is None


@pytest.fixture
def fichier():
    r.TARIFS_FILE.write_text(json.dumps({"tarifs": []}), encoding="utf-8")
    yield r.TARIFS_FILE


def test_enregistrer_la_comparaison_date_le_prix(fichier, qapp, monkeypatch):
    import fenetre as module_fenetre
    from pages import parametres as pa
    monkeypatch.setattr(module_fenetre, "charger_donnees",
                        lambda: {"recharges": []})
    f = module_fenetre.FenetrePrincipale()
    page = pa.construire(f)
    page.cases_essence["conso"].setText("5")
    page.cases_essence["prix"].setText("2")
    page.bouton_essence.click()
    assert r.charger_config()["prix_essence_maj"] == \
        datetime.now().date().isoformat()
    f.deleteLater()


def test_le_tableau_de_bord_montre_le_rappel(fichier, qapp, monkeypatch):
    import fenetre as module_fenetre
    from pages import tableau_de_bord as tb
    monkeypatch.setattr(tb, "rappel_prix_essence",
                        lambda: "Prix de l'essence à revoir.")
    monkeypatch.setattr(module_fenetre, "charger_donnees",
                        lambda: {"recharges": []})
    f = module_fenetre.FenetrePrincipale()
    page = tb.construire(f)
    from PySide6.QtWidgets import QLabel
    assert any("Prix de l'essence à revoir." in e.text()
               for e in page.findChildren(QLabel))
    f.deleteLater()
