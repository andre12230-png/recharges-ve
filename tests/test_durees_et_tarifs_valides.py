"""Durées impossibles à l'import et validation de tarifs.json (audit
indépendant du 04/11/2026, constats T4 et T5).

T4 : « 1:99 » ou « 1h99 » devenaient 2 h 39 sans prévenir ; une recharge
pouvait ainsi changer de plage horaire (heures creuses / pleines). Les
minutes et les secondes d'une durée vont de 0 à 59 ; un nombre seul de
minutes (« 99 ») reste un format accepté.

T5 : un nom de tarif qui n'est pas un texte (fichier modifié à la main)
faisait remonter une erreur Python au lieu d'un message en français ; des
frais de carte de montant infini étaient acceptés par le moteur, écrits
« Infinity » dans tarifs.json et comptés dans un total infini.

Données inventées, dans le dossier temporaire de tests/conftest.py.

    py -m pytest tests/test_durees_et_tarifs_valides.py
"""

from __future__ import annotations

import json
from datetime import timedelta

import pytest

import recharges as r

# ---------- T4 : les durées ----------


@pytest.mark.parametrize("texte", ["1:99", "1h99", "1:02:99", "0:60",
                                   "2h60"])
def test_duree_impossible_refusee(texte):
    assert r._duree_csv(texte) is None


@pytest.mark.parametrize("texte, attendu", [
    ("1:30", timedelta(hours=1, minutes=30)),
    ("1:02:59", timedelta(hours=1, minutes=2, seconds=59)),
    ("8:00", timedelta(hours=8)),
    ("1h30", timedelta(hours=1, minutes=30)),
    ("1h5", timedelta(hours=1, minutes=5)),
    ("2h", timedelta(hours=2)),
    ("99", timedelta(minutes=99)),          # un nombre seul de minutes
    ("90 min", timedelta(minutes=90)),
])
def test_durees_valables_toujours_lues(texte, attendu):
    assert r._duree_csv(texte) == attendu


def test_ligne_csv_a_duree_impossible_non_reconnue():
    """La ligne est comptée parmi les lignes non reconnues, au lieu d'être
    importée avec une fin inventée (0 h 39 le lendemain)."""
    contenu = "Début;Durée;Énergie\n2026-03-02 22:00;1:99;10\n"
    colonnes = {"debut": 0, "duree": 1, "kwh": 2}
    records, non_reconnues, *_ = r._depouiller_avec(contenu, colonnes)
    assert records == []
    assert non_reconnues == 1


# ---------- T5 : tarifs.json ----------

BASE = {"nom": "Base", "debut": "2026-01-01", "fin": None, "type": "simple",
        "abonnement_mensuel": 10.0, "prix_kwh": 0.2}


@pytest.mark.parametrize("nom", [123, None, ["Base"], "  "])
def test_nom_de_tarif_qui_n_est_pas_un_texte(nom):
    with pytest.raises(ValueError, match="nom du tarif"):
        r.valider_tarif(dict(BASE, nom=nom))


def test_plages_illisibles_message_en_francais():
    tarif = dict(BASE, type="hp_hc", prix_hp=0.25, prix_hc=0.15,
                 plages_hc=12)
    tarif.pop("prix_kwh")
    with pytest.raises(ValueError, match="plage"):
        r.valider_tarif(tarif)
    tarif["plages_hc"] = [12]
    with pytest.raises(ValueError, match="plage"):
        r.valider_tarif(tarif)


@pytest.fixture
def grille():
    r.vider_cache()
    r.TARIFS_FILE.write_text(json.dumps(
        {"tarifs": [dict(BASE, id="t1")]}), encoding="utf-8")
    r.sauvegarder_donnees({"recharges": []})
    yield


def test_fichier_avec_nom_numerique_message_en_francais(grille):
    r.TARIFS_FILE.write_text(json.dumps(
        {"tarifs": [dict(BASE, id="t1", nom=123)]}), encoding="utf-8")
    with pytest.raises(ValueError, match="tarifs.json est invalide"):
        r.charger_tarifs()


FRAIS = {"carte": "Carte A", "type": "unique", "date": "2026-02-01",
         "montant": 10.0}


@pytest.mark.parametrize("montant", [float("inf"), float("-inf"),
                                     float("nan"), "inf", "Infinity"])
def test_frais_de_montant_non_fini_refuses(grille, montant):
    with pytest.raises(ValueError, match="montant"):
        r.ajouter_frais_carte(dict(FRAIS, montant=montant))
    assert "Infinity" not in r.TARIFS_FILE.read_text(encoding="utf-8")


def test_frais_valables_toujours_acceptes(grille):
    r.ajouter_frais_carte(dict(FRAIS))
    assert r.charger_frais_cartes()[0]["montant"] == 10.0


def test_fichier_avec_frais_infinis_message_en_francais(grille):
    """tarifs.json modifié à la main : « Infinity » est refusé à la lecture,
    au lieu de donner un total de frais infini."""
    r.TARIFS_FILE.write_text(
        '{"tarifs": [], "frais_cartes": [{"carte": "Carte A", '
        '"type": "unique", "date": "2026-02-01", "montant": Infinity}]}',
        encoding="utf-8")
    with pytest.raises(ValueError, match="tarifs.json est invalide"):
        r.charger_frais_cartes()


def test_tarifs_json_jamais_ecrit_avec_une_valeur_infinie(grille):
    """Dernier filet : même si une valeur non finie échappait aux contrôles,
    elle n'est pas écrite (comme pour recharges.json)."""
    contenu = json.loads(r.TARIFS_FILE.read_text(encoding="utf-8"))
    avant = r.TARIFS_FILE.read_text(encoding="utf-8")
    contenu["capacite_batterie"] = float("inf")
    with pytest.raises(ValueError):
        r._ecrire_tarifs(contenu)
    assert r.TARIFS_FILE.read_text(encoding="utf-8") == avant
