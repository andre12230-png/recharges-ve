"""Un changement de tarif s'enregistre en entier ou pas du tout
(second audit du 16/10/2026, constat A5).

Defaut d'origine : ajouter une nouvelle periode fermait d'abord l'ancienne
(une ecriture de tarifs.json), puis enregistrait la nouvelle (une seconde
ecriture). Une panne entre les deux laissait l'ancien tarif clos et aucun
tarif apres lui : les recharges suivantes n'avaient plus de prix. L'erreur
etait signalee, mais la moitie du changement etait deja faite.

Tarifs inventes, dans le dossier temporaire de tests/conftest.py.

    py -m pytest tests/test_changement_tarif_entier.py
"""

from __future__ import annotations

import json

import pytest

import dialogue_tarif as dt
import recharges as r

ANCIEN = {"id": "ancien", "nom": "Ancien", "type": "simple",
          "debut": "2026-01-01", "fin": None, "prix_kwh": 0.20,
          "abonnement_mensuel": 0.0}
NOUVEAU = {"nom": "Nouveau", "type": "simple", "debut": "2026-07-01",
           "fin": None, "prix_kwh": 0.30, "abonnement_mensuel": 0.0}


@pytest.fixture
def grille():
    r.TARIFS_FILE.write_text(json.dumps(
        {"tarifs": [dict(ANCIEN)], "capacite_batterie": 50}),
        encoding="utf-8")
    r.vider_cache()
    yield
    r.vider_cache()


@pytest.fixture
def ecritures(monkeypatch):
    """Compte les ecritures de tarifs.json ; `panne` fait echouer celle de
    ce rang (1 = la premiere), `panne_nouveau` celle qui ajoute le tarif
    « Nouveau »."""
    vraie = r._ecrire_tarifs
    etat = {"n": 0, "panne": None, "panne_nouveau": False}

    def ecrire(contenu):
        etat["n"] += 1
        ajoute = any(t.get("nom") == "Nouveau" for t in contenu["tarifs"])
        if (etat["n"] == etat["panne"]
                or (etat["panne_nouveau"] and ajoute)):
            raise OSError("panne inventée pendant l'écriture")
        vraie(contenu)
    monkeypatch.setattr(r, "_ecrire_tarifs", ecrire)
    return etat


def _sur_disque() -> list[dict]:
    return json.loads(r.TARIFS_FILE.read_text(encoding="utf-8"))["tarifs"]


# ---------- le moteur ----------

def test_fermer_l_ancien_et_ajouter_le_nouveau_en_une_ecriture(
        grille, ecritures):
    r.enregistrer_tarif(dict(NOUVEAU), cloturer="ancien")
    assert ecritures["n"] == 1
    tarifs = _sur_disque()
    assert [(t["nom"], t["fin"]) for t in tarifs] == [
        ("Ancien", "2026-06-30"), ("Nouveau", None)]


def test_une_panne_laisse_l_ancienne_grille_entiere(grille, ecritures):
    ecritures["panne"] = 1
    with pytest.raises(OSError):
        r.enregistrer_tarif(dict(NOUVEAU), cloturer="ancien")
    assert _sur_disque() == [ANCIEN]


def test_fermer_un_tarif_introuvable_ne_touche_a_rien(grille, ecritures):
    with pytest.raises(ValueError):
        r.enregistrer_tarif(dict(NOUVEAU), cloturer="disparu")
    assert ecritures["n"] == 0
    assert _sur_disque() == [ANCIEN]


# ---------- la fenetre, comme l'utilisateur ----------

def test_la_fenetre_ne_laisse_jamais_un_changement_a_moitie(
        qapp, grille, ecritures, monkeypatch):
    # « Le terminer le 30/06/2026 ? » -> oui ; puis panne en ecrivant le
    # nouveau tarif : avant, l'ancien etait deja clos a ce moment-la.
    monkeypatch.setattr(dt, "confirmer", lambda *a, **k: True)
    ecritures["panne_nouveau"] = True
    d = dt.DialogueTarif(None, None)
    f = d.formulaire
    f.ecrire("nom", "Nouveau")
    f.ecrire("debut", "01/07/2026")
    f.ecrire("prix_kwh", "0,30")
    d.choix_unique.setChecked(True)
    d.enregistrer()
    assert d.result() != dt.QDialog.Accepted
    assert _sur_disque() == [ANCIEN]          # rien de fait a moitie
    d.deleteLater()


def test_la_fenetre_enregistre_le_changement_entier(
        qapp, grille, ecritures, monkeypatch):
    monkeypatch.setattr(dt, "confirmer", lambda *a, **k: True)
    d = dt.DialogueTarif(None, None)
    f = d.formulaire
    f.ecrire("nom", "Nouveau")
    f.ecrire("debut", "01/07/2026")
    f.ecrire("prix_kwh", "0,30")
    d.choix_unique.setChecked(True)
    d.enregistrer()
    assert d.result() == dt.QDialog.Accepted
    assert ecritures["n"] == 1
    assert [(t["nom"], t["fin"]) for t in _sur_disque()] == [
        ("Ancien", "2026-06-30"), ("Nouveau", None)]
    d.deleteLater()
