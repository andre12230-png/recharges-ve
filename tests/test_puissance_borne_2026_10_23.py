"""Puissance de charge de la borne (23/10/2026).

Constat : l'appli repartit l'energie d'une recharge uniformement du debut a
la fin de la session. Or une borne charge a pleine puissance des le debut,
puis s'arrete quand la batterie est pleine ; la voiture reste ensuite
branchee sans charger. Une recharge de nuit qui finit en realite bien avant
la fin des heures creuses se voyait attribuer des heures pleines.

Reglage facultatif « Puissance de charge de la borne » (kW) : vide (0), on
garde la repartition uniforme ; renseigne, l'energie est comptee a cette
puissance des le debut, jusqu'a epuisement des kWh. Si la puissance est trop
faible pour livrer les kWh dans la session, la charge occupe toute la
session (on ne depasse jamais l'heure de fin).

Toutes les donnees sont inventees, dans un dossier temporaire.

    py -m pytest tests/test_puissance_borne_2026_10_23.py
"""

import json
import os
import sys
import tempfile
from datetime import datetime
from pathlib import Path

import pytest

os.environ.setdefault("RECHARGES_DATA_DIR",
                      tempfile.mkdtemp(prefix="recharges_puissance_1023_"))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import recharges as r  # noqa: E402

# Heures creuses de 23 h a 5 h ; heures et prix ronds inventes.
GRILLE_HP_HC = {"id": "t", "nom": "HP/HC", "type": "hp_hc",
                "debut": "2020-01-01", "fin": None,
                "prix_hp": 0.20, "prix_hc": 0.10,
                "abonnement_mensuel": 0.0,
                "plages_hc": [["23:00", "05:00"]]}

DEBUT = datetime(2026, 7, 8, 0, 0)
FIN = datetime(2026, 7, 8, 5, 30)        # 5 h 30 branchee, dont 30 min en HP

ENTETE_CSV = ("NS du chargeur,Heure de debut,Heure de fin,Consommation,"
              "Duree,Cout")
PETITE = ("WB-0001,2026-07-08 00:00:00,2026-07-08 05:30:00,5.000kWh,"
          "05h30min,0.50€")

REGLAGES = {"capacite_batterie": 0.0, "rendement_charge": 0.9,
            "correction_csv_minutes": 0}


def ecrire(chemin: Path, contenu) -> None:
    chemin.parent.mkdir(parents=True, exist_ok=True)
    chemin.write_text(json.dumps(contenu, ensure_ascii=False),
                      encoding="utf-8")


@pytest.fixture
def dossier(tmp_path, monkeypatch):
    """Un dossier de donnees neuf, sans puissance de borne reglee."""
    ancien = r.BASE
    r.rediriger_donnees(tmp_path)
    monkeypatch.setattr(r, "DERNIERE_RESTAURATION", None)
    monkeypatch.setattr(r, "ECHEC_BACKUP", None, raising=False)
    ecrire(tmp_path / "tarifs.json", {"correction_csv_minutes": 0,
                                      "tarifs": [GRILLE_HP_HC]})
    r.vider_cache()
    yield tmp_path
    r.rediriger_donnees(ancien)


def regler_puissance(dossier: Path, kw: float) -> None:
    tarifs = json.loads((dossier / "tarifs.json").read_text("utf-8"))
    tarifs["puissance_borne_kw"] = kw
    ecrire(dossier / "tarifs.json", tarifs)
    r.vider_cache()


# ---------- le calcul ----------

def test_sans_puissance_la_repartition_reste_uniforme():
    calc = r.calculer_cout(DEBUT, FIN, 5.5, [GRILLE_HP_HC])
    assert calc["kwh_hp"] == pytest.approx(0.5, abs=0.001)


def test_petite_recharge_finie_avant_les_heures_pleines():
    """5 kWh a 10 kW : finie a 0 h 30, entierement en heures creuses."""
    calc = r.calculer_cout(DEBUT, FIN, 5.0, [GRILLE_HP_HC], puissance_kw=10)
    assert calc["kwh_hp"] == 0
    assert calc["kwh_hc"] == pytest.approx(5.0, abs=0.001)
    assert calc["cout"] == pytest.approx(0.50, abs=0.001)


def test_grosse_recharge_deborde_en_heures_pleines():
    """52 kWh a 10 kW : 5 h 12 de charge, de 0 h a 5 h 12, dont 12 min (2 kWh)
    en heures pleines."""
    calc = r.calculer_cout(DEBUT, FIN, 52.0, [GRILLE_HP_HC], puissance_kw=10)
    assert calc["kwh_hp"] == pytest.approx(2.0, abs=0.01)


def test_puissance_trop_faible_n_allonge_pas_la_session():
    """11 kWh a 1 kW demanderaient 11 h : la charge occupe alors toute la
    session, comme la repartition uniforme."""
    avec = r.calculer_cout(DEBUT, FIN, 11.0, [GRILLE_HP_HC], puissance_kw=1)
    sans = r.calculer_cout(DEBUT, FIN, 11.0, [GRILLE_HP_HC])
    assert avec == sans


# ---------- le reglage ----------

def test_ancien_fichier_sans_puissance(dossier):
    assert r.charger_config()["puissance_borne_kw"] == 0


@pytest.mark.parametrize("saisie, attendu", [
    ("", 0.0), (" ", 0.0), ("7,4", 7.4), ("11", 11.0), ("22.0", 22.0)])
def test_puissance_saisie_acceptee(saisie, attendu):
    reglages = r.valider_reglages("", "90", "0", saisie)
    assert reglages["puissance_borne_kw"] == attendu


@pytest.mark.parametrize("saisie", ["sept", "0,5", "-3", "100"])
def test_puissance_saisie_refusee(saisie):
    with pytest.raises(ValueError, match="Puissance de charge"):
        r.valider_reglages("", "90", "0", saisie)


def test_les_trois_reglages_d_avant_restent_valides():
    """Appel a trois cases : la puissance reste vide."""
    assert r.valider_reglages("", "90", "0")["puissance_borne_kw"] == 0


# ---------- saisie, import et recalcul ----------

def test_saisie_a_la_main_suit_la_puissance(dossier):
    regler_puissance(dossier, 10)
    rec = r.ajouter_recharge_maison(DEBUT, FIN, 5.0)
    assert rec["kwh_hp"] == 0


def test_import_suit_la_puissance(dossier):
    regler_puissance(dossier, 10)
    csv = dossier / "borne.csv"
    csv.write_text("\n".join([ENTETE_CSV, PETITE]), encoding="utf-8")
    r.importer_csv_maison(csv)
    assert r.charger_donnees()["recharges"][0]["kwh_hp"] == 0


def test_regler_la_puissance_recalcule_les_recharges(dossier):
    """Importee sans puissance (repartition uniforme), puis puissance reglee
    dans Parametres : le cout est recalcule."""
    csv = dossier / "borne.csv"
    csv.write_text("\n".join([ENTETE_CSV, PETITE]), encoding="utf-8")
    r.importer_csv_maison(csv)
    avant = r.charger_donnees()["recharges"][0]
    assert avant["kwh_hp"] == pytest.approx(5 * 0.5 / 5.5, abs=0.001)
    bilan = r.enregistrer_reglages_borne(dict(REGLAGES,
                                              puissance_borne_kw=10.0))
    assert bilan["recalculees"] == 1
    apres = r.charger_donnees()["recharges"][0]
    assert apres["kwh_hp"] == 0
    assert apres["cout_eur"] == pytest.approx(0.50, abs=0.001)
    assert apres["date"] == avant["date"] and apres["fin"] == avant["fin"]
    assert r.charger_config()["puissance_borne_kw"] == 10.0


def test_meme_puissance_ne_recalcule_rien(dossier):
    regler_puissance(dossier, 10)
    bilan = r.enregistrer_reglages_borne(dict(REGLAGES,
                                              puissance_borne_kw=10.0))
    assert bilan["recalculees"] == 0
