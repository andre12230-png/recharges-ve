"""Une saisie en cours survit a la correction d'une autre ligne de la page
(second audit du 16/10/2026, constat A1).

Defaut d'origine : sur Kilometrage, taper un nouveau releve puis corriger un
releve existant avec « Modifier… » (ou en supprimer un) reconstruisait la
page et vidait le formulaire, sans un mot. Meme chose sur Tarifs pour des
frais de carte en cours de saisie. Seul l'enregistrement du formulaire
lui-meme doit le vider.

Donnees inventees, dans le dossier temporaire de tests/conftest.py.

    py -m pytest tests/test_brouillon_apres_modifier.py
"""

from __future__ import annotations

import json

import pytest
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QDialog, QWidget

import recharges as r
from pages import kilometrage as km
from pages import tarifs as ta

ACHAT = {"carte": "Réseau A", "type": "unique", "date": "2025-03-10",
         "fin": None, "montant": 20.0}


class _DialogueAccepte:
    """Remplace la fenetre « Modifier… » : comme si l'on avait corrige puis
    clique sur Enregistrer."""
    def __init__(self, *args, **kwargs):
        pass

    def exec(self):
        return QDialog.Accepted


@pytest.fixture
def donnees():
    r.DATA_FILE.write_text(json.dumps({"recharges": [], "releves_km": [
        {"id": "k1", "date": "2026-01-05T10:00", "km": 1000.0},
        {"id": "k2", "date": "2026-02-05T10:00", "km": 2000.0},
    ]}), encoding="utf-8")
    r.TARIFS_FILE.write_text(json.dumps(
        {"tarifs": [], "capacite_batterie": 50}), encoding="utf-8")
    r.vider_cache()
    r.ajouter_frais_carte(ACHAT)
    yield
    r.vider_cache()


@pytest.fixture
def fenetre(qapp, donnees, monkeypatch):
    import fenetre as module_fenetre
    monkeypatch.setattr(km, "DialogueReleve", _DialogueAccepte)
    monkeypatch.setattr(ta, "DialogueFrais", _DialogueAccepte)
    monkeypatch.setattr(km, "confirmer", lambda *a, **k: True)
    monkeypatch.setattr(ta, "confirmer", lambda *a, **k: True)
    f = module_fenetre.FenetrePrincipale(accueil=False)
    qapp.processEvents()
    yield f
    f._pages_gardees.clear()
    f.afficher_vue("dashboard", forcer=True)
    f.deleteLater()


def _page(f, attribut: str) -> QWidget:
    """La page affichee, celle qui porte `attribut` (cases_km, cases_frais)."""
    enveloppe = f.zone_page.widget()
    return next(w for w in enveloppe.findChildren(QWidget)
                if hasattr(w, attribut))


def _attendre(qapp) -> None:
    """La reconstruction de la page attend le prochain instant libre."""
    for _ in range(5):
        qapp.processEvents()
        QTest.qWait(20)


# ---------- Kilometrage ----------

def _taper_un_releve(qapp, f) -> None:
    f.afficher_vue("km")
    qapp.processEvents()
    QTest.keyClicks(_page(f, "cases_km").cases_km["champ_km_valeur"], "50000")
    assert f.saisies_en_attente() == ["km"]


def test_modifier_un_releve_garde_le_nouveau_releve_tape(qapp, fenetre):
    _taper_un_releve(qapp, fenetre)
    km.modifier_releve(fenetre, r.charger_releves_km()[0])
    _attendre(qapp)
    cases = _page(fenetre, "cases_km").cases_km
    assert cases["champ_km_valeur"].text() == "50000"
    # Toujours repere comme non enregistre : la fermeture le demandera.
    assert fenetre.saisies_en_attente() == ["km"]


def test_supprimer_un_releve_garde_le_nouveau_releve_tape(qapp, fenetre):
    _taper_un_releve(qapp, fenetre)
    km.supprimer_releve(fenetre, r.charger_releves_km()[0])
    _attendre(qapp)
    assert len(r.charger_releves_km()) == 1
    cases = _page(fenetre, "cases_km").cases_km
    assert cases["champ_km_valeur"].text() == "50000"
    assert fenetre.saisies_en_attente() == ["km"]


def test_enregistrer_le_releve_vide_toujours_le_formulaire(qapp, fenetre):
    _taper_un_releve(qapp, fenetre)
    page = _page(fenetre, "cases_km")
    page.bouton_km.click()
    _attendre(qapp)
    assert len(r.charger_releves_km()) == 3
    assert _page(fenetre, "cases_km").cases_km["champ_km_valeur"].text() == ""
    assert fenetre.saisies_en_attente() == []


# ---------- Tarifs : frais de carte ----------

def _taper_des_frais(qapp, f) -> None:
    f.afficher_vue("tarifs")
    qapp.processEvents()
    cases = _page(f, "cases_frais").cases_frais
    # Une carte choisie dans la liste, comme d'un clic. (Taper dans cette
    # liste modifiable ouvre ses suggestions, qui font planter Qt sans
    # ecran : d'ou ce choix simule.)
    carte = cases["carte"]
    carte.setCurrentIndex(1)
    carte.activated.emit(1)
    QTest.keyClicks(cases["montant"], "123")
    assert f.saisies_en_attente() == ["tarifs"]


def test_modifier_des_frais_garde_les_frais_tapes(qapp, fenetre):
    _taper_des_frais(qapp, fenetre)
    ta.modifier_les_frais(fenetre, r.charger_frais_cartes()[0])
    _attendre(qapp)
    cases = _page(fenetre, "cases_frais").cases_frais
    assert cases["montant"].text() == "123"
    assert cases["carte"].currentText() == ta.CARTES_A_FRAIS[1]
    assert fenetre.saisies_en_attente() == ["tarifs"]


def test_supprimer_des_frais_garde_les_frais_tapes(qapp, fenetre):
    _taper_des_frais(qapp, fenetre)
    ta.supprimer_les_frais(fenetre, r.charger_frais_cartes()[0])
    _attendre(qapp)
    assert r.charger_frais_cartes() == []
    cases = _page(fenetre, "cases_frais").cases_frais
    assert cases["montant"].text() == "123"
    assert fenetre.saisies_en_attente() == ["tarifs"]
