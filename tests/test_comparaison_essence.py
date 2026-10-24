"""Comparaison avec une voiture essence (28/09/2026).

Sur les memes kilometres que le cout aux 100 km (entre deux releves du
compteur) : ce qu'aurait coute l'essence, a la consommation et au prix du
litre saisis par l'utilisateur dans Parametres (aucun prix ecrit dans le
code), face a ce qu'a coute l'electricite. Donnees inventees.

    py -m pytest tests/test_comparaison_essence.py
"""

from __future__ import annotations

import json

import pytest

import recharges as r

# 1 000 km entre deux releves, 150 kWh recharges pour 30 EUR.
RELEVES = [{"id": "r1", "date": "2025-01-01T12:00", "km": 20000.0},
           {"id": "r2", "date": "2025-06-01T12:00", "km": 21000.0}]
RECHARGES = [{"id": "a", "date": "2025-03-01T22:00", "lieu": "maison",
              "kwh": 150.0, "cout_eur": 30.0}]
REGLAGE = {"conso_essence": 6.0, "prix_essence": 2.0}


def comparer(reglage=REGLAGE, releves=RELEVES, recharges=RECHARGES):
    """Depuis le 28/09/2026, la comparaison passe par
    comparer_essence_periode (« Tout » ou une annee)."""
    return r.comparer_essence_periode("Tout", reglage, releves, recharges)


@pytest.fixture
def fichier():
    r.TARIFS_FILE.write_text(json.dumps(
        {"tarifs": [], "capacite_batterie": 50}), encoding="utf-8")
    yield r.TARIFS_FILE


# ---------- le calcul ----------

def test_la_comparaison():
    c = comparer()
    # 1000 km a 6 L/100 km = 60 L, a 2 EUR/L = 120 EUR.
    assert (c["km"], c["litres"], c["cout_essence"], c["cout_electrique"],
            c["economie"], c["cout_100_essence"], c["cout_100_electrique"],
            c["conso_essence"], c["prix_essence"]) == (
        1000.0, 60.0, 120.0, 30.0, 90.0, 12.0, 3.0, 6.0, 2.0)


def test_rien_sans_reglage():
    assert comparer({"conso_essence": 0, "prix_essence": 0}) is None


def test_rien_sans_kilometres_ni_energie():
    """Comme le cout aux 100 km : sans distance ou sans recharge entre les
    releves, la comparaison ferait croire a une economie totale."""
    immobile = [RELEVES[0], dict(RELEVES[1], km=20000.0)]
    assert comparer(releves=immobile) is None
    assert comparer(recharges=[]) is None


# ---------- les reglages ----------

def test_un_ancien_fichier_n_a_pas_de_comparaison(fichier):
    config = r.charger_config()
    assert config["conso_essence"] == 0 and config["prix_essence"] == 0


def test_valider_et_enregistrer(fichier):
    reglage = r.valider_comparaison_essence("6,5", "1,85")
    assert reglage == {"conso_essence": 6.5, "prix_essence": 1.85}
    r.enregistrer_config(reglage)
    assert r.charger_config()["prix_essence"] == 1.85
    contenu = json.loads(fichier.read_text(encoding="utf-8"))
    assert contenu["capacite_batterie"] == 50          # le reste est garde


def test_deux_cases_vides_desactivent(fichier):
    assert r.valider_comparaison_essence(" ", "") == {
        "conso_essence": 0.0, "prix_essence": 0.0}


@pytest.mark.parametrize("conso, prix, morceau", [
    ("6,5", "", "les deux"),
    ("", "1,85", "les deux"),
    ("six", "1,85", "n'est pas un nombre"),
    ("45", "1,85", "entre 2 et 30"),
    ("6,5", "12", "entre 0,50 et 5"),
])
def test_saisies_refusees(conso, prix, morceau):
    with pytest.raises(ValueError, match=morceau):
        r.valider_comparaison_essence(conso, prix)


# ---------- les ecrans ----------

@pytest.fixture
def fenetre(qapp, monkeypatch, fichier):
    import fenetre as module_fenetre
    monkeypatch.setattr(module_fenetre, "charger_donnees",
                        lambda: {"recharges": []})
    f = module_fenetre.FenetrePrincipale()
    yield f
    f.deleteLater()


def test_parametres_enregistre_la_comparaison(fenetre, monkeypatch):
    from pages import parametres as pa
    from theme_qt import ROUGE
    page = pa.construire(fenetre)
    page.cases_essence["conso"].setText("45")
    page.cases_essence["prix"].setText("1,85")
    page.bouton_essence.click()
    assert ROUGE in page.message_essence.styleSheet()
    page.cases_essence["conso"].setText("6,5")
    page.bouton_essence.click()
    assert page.message_essence.text() == "✓ Comparaison enregistrée."
    assert r.charger_config()["conso_essence"] == 6.5


def textes(widget) -> list[str]:
    from PySide6.QtWidgets import QLabel
    return [e.text() for e in widget.findChildren(QLabel)]


def test_la_carte_du_kilometrage(fenetre, monkeypatch):
    from pages import kilometrage as km
    carte = km._carte_essence(comparer())
    tout = " ".join(textes(carte))
    assert "120,00\xa0€" in tout and "30,00\xa0€" in tout and "90,00\xa0€" in tout
    assert "6,0\xa0L/100\xa0km" in tout and "2,00\xa0€/L" in tout
    # Sans reglage : une invitation vers Parametres.
    carte = km._carte_essence(None)
    assert "Paramètres" in " ".join(textes(carte))


def test_la_bande_du_tableau_de_bord(fichier, monkeypatch):
    from pages import tableau_de_bord as tb
    monkeypatch.setattr(tb, "calculer_consommation", lambda: {
        "km": 1000.0, "cout": 30.0, "kwh": 150.0, "n_releves": 2,
        "cout_100": 3.0, "controle": {"verdict": "coherent"}})
    monkeypatch.setattr(tb, "comparer_essence_periode",
                        lambda periode, config: comparer(config))
    monkeypatch.setattr(tb, "charger_releves_km", lambda: [
        {"date": "2026-01-01T08:00"}, {"date": "2026-03-01T08:00"}])
    assert tb.cout_des_kilometres()["essence_100"] is None
    r.enregistrer_config(REGLAGE)
    assert tb.cout_des_kilometres()["essence_100"] == 12.0
