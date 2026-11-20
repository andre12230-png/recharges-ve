"""Rappel « coûts à recalculer » (audit à blanc du 03/11/2026, chantier C3).

Après un changement de grille, la question « Recalculer les coûts ? »
propose « Plus tard ». Rien ne rappelait ensuite que les coûts déjà
enregistrés ne suivaient plus la grille. Le moteur retient maintenant
« recalcul_en_attente » dans tarifs.json (clé facultative, accord de l'auteur :
un ancien fichier sans elle n'a rien à rappeler), et tout recalcul l'efface.
La page Tarifs et le tableau de bord affichent alors un bandeau, avec le
bouton qui recalcule.

Données inventées, dans le dossier temporaire de tests/conftest.py.

    py -m pytest tests/test_rappel_recalcul.py
"""

from __future__ import annotations

import json
from datetime import datetime

import pytest

import recharges as r

BASE = {"nom": "Base", "debut": "2026-01-01", "fin": None, "type": "simple",
        "abonnement_mensuel": 10.0, "prix_kwh": 0.2}
NOUVEAU = {"nom": "Nouveau", "debut": "2026-06-01", "fin": None,
           "type": "simple", "abonnement_mensuel": 12.0, "prix_kwh": 0.25}


@pytest.fixture
def donnees():
    """Une grille vide et aucune recharge : un fichier d'avant le rappel."""
    r.vider_cache()
    r.TARIFS_FILE.write_text(json.dumps(
        {"tarifs": [], "capacite_batterie": 50}), encoding="utf-8")
    r.sauvegarder_donnees({"recharges": []})
    yield


def avec_une_recharge_maison():
    """Un tarif, une recharge à la maison, et rien en attente au départ."""
    r.enregistrer_tarif(dict(BASE))
    r.ajouter_recharge_maison(datetime(2026, 3, 2, 22, 0),
                              datetime(2026, 3, 3, 1, 0), 20.0)
    r.recalculer_tout()


def cles_de_tarifs_json() -> dict:
    return json.loads(r.TARIFS_FILE.read_text(encoding="utf-8"))


# ---------- le moteur ----------

def test_ancien_fichier_sans_la_cle_rien_a_rappeler(donnees):
    assert r.recalcul_en_attente() is False


def test_premier_tarif_sans_recharge_pas_de_rappel(donnees):
    """Un nouvel utilisateur saisit son premier tarif : rien à recalculer."""
    r.enregistrer_tarif(dict(BASE))
    assert r.recalcul_en_attente() is False


def test_grille_changee_rappel_jusqu_au_recalcul(donnees):
    avec_une_recharge_maison()
    assert r.recalcul_en_attente() is False
    r.enregistrer_tarif(dict(NOUVEAU))
    assert r.recalcul_en_attente() is True
    r.recalculer_tout()
    assert r.recalcul_en_attente() is False
    # Effacée, et non laissée à « false » : le fichier redevient celui
    # d'avant le rappel.
    assert "recalcul_en_attente" not in cles_de_tarifs_json()


def test_supprimer_une_periode_aussi(donnees):
    avec_une_recharge_maison()
    r.enregistrer_tarif(dict(NOUVEAU))
    r.recalculer_tout()
    nouveau = next(t for t in r.charger_tarifs() if t["nom"] == "Nouveau")
    assert r.supprimer_tarif(nouveau["id"])
    assert r.recalcul_en_attente() is True


def recharge_sans_tarif():
    """La seule période de la grille commence après la recharge du 02-03 :
    plus aucun tarif ne la couvre, son coût ne peut pas être recalculé."""
    avec_une_recharge_maison()
    base = r.charger_tarifs()[0]
    r.enregistrer_tarif(dict(BASE, debut="2026-04-01"), id_origine=base["id"])


def test_recalcul_incomplet_garde_le_rappel(donnees):
    """Audit indépendant du 04/11/2026, constat T3 : le rappel était effacé
    même quand une recharge restait à son ancien coût."""
    recharge_sans_tarif()
    assert r.recalcul_en_attente() is True
    n, laissees = r.recalculer_tout()
    assert laissees == ["2026-03-02T22:00"]
    assert r.recalcul_en_attente() is True
    # Une fois la grille de nouveau complète, le recalcul l'efface.
    base = r.charger_tarifs()[0]
    r.enregistrer_tarif(dict(BASE), id_origine=base["id"])
    assert r.recalculer_tout()[1] == []
    assert r.recalcul_en_attente() is False


def test_recalcul_incomplet_pose_le_rappel(donnees):
    """Un recalcul lancé d'ailleurs (puissance de la borne changée dans les
    Paramètres) qui laisse un coût ancien doit lui aussi le rappeler, même
    sans rappel au départ."""
    recharge_sans_tarif()
    contenu = cles_de_tarifs_json()
    contenu.pop("recalcul_en_attente")
    r.TARIFS_FILE.write_text(json.dumps(contenu), encoding="utf-8")
    assert r.recalcul_en_attente() is False
    puissance = r.charger_config()["puissance_borne_kw"]
    resultat = r.enregistrer_reglages_borne(
        {"puissance_borne_kw": puissance + 1})
    assert resultat["laissees"] == ["2026-03-02T22:00"]
    assert r.recalcul_en_attente() is True


def test_les_autres_reglages_sont_gardes(donnees):
    avec_une_recharge_maison()
    r.enregistrer_tarif(dict(NOUVEAU))
    r.recalculer_tout()
    assert cles_de_tarifs_json()["capacite_batterie"] == 50


# ---------- les écrans ----------

@pytest.fixture
def fenetre(qapp, donnees):
    import fenetre as module_fenetre
    f = module_fenetre.FenetrePrincipale()
    yield f
    f.deleteLater()


def test_page_tarifs_rappel_et_bouton(fenetre, monkeypatch):
    from pages import tarifs as ta
    avec_une_recharge_maison()
    assert ta.construire(fenetre).rappel_recalcul is None
    r.enregistrer_tarif(dict(NOUVEAU))
    page = ta.construire(fenetre)
    assert page.rappel_recalcul is not None
    # Le bouton du bandeau recalcule (compte rendu remplacé par un silence).
    monkeypatch.setattr(ta.QMessageBox, "information", lambda *a, **k: None)
    monkeypatch.setattr(ta.QMessageBox, "warning", lambda *a, **k: None)
    page.rappel_recalcul.bouton.click()
    assert r.recalcul_en_attente() is False


def test_tableau_de_bord_rappel(fenetre):
    from pages import tableau_de_bord as tb
    avec_une_recharge_maison()
    assert tb.construire(fenetre).rappel_recalcul is None
    r.enregistrer_tarif(dict(NOUVEAU))
    assert tb.construire(fenetre).rappel_recalcul is not None
