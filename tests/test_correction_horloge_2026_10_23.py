"""Correction d'horloge changee : les recharges deja importees suivent.

Constat du 23/10/2026 : changer la « Correction de l'horloge » dans la page
Parametres ne touchait que les imports suivants. Les recharges deja
importees gardaient leurs heures et leurs couts calcules avec l'ancien
reglage. Exemple : une recharge de nuit lue 0 h -> 5 h 30 dans le CSV,
importee avec -60, restait enregistree 23 h -> 4 h 30, toute en heures
creuses ; repasser le reglage a 0 ne la replacait pas a sa vraie heure, dont
une demi-heure en heures pleines.

Desormais, enregistrer_reglages_borne() decale les recharges importees
d'un CSV et recalcule leur cout. Les saisies a la main ne bougent pas.

Toutes les donnees sont inventees, dans un dossier temporaire.

    py -m pytest tests/test_correction_horloge_2026_10_23.py
"""

import json
import os
import sys
import tempfile
from pathlib import Path

import pytest

os.environ.setdefault("RECHARGES_DATA_DIR",
                      tempfile.mkdtemp(prefix="recharges_horloge_1023_"))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import recharges as r  # noqa: E402

ENTETE_CSV = ("NS du chargeur,Heure de debut,Heure de fin,Consommation,"
              "Duree,Cout")
# Une nuit : 5 h 30 de charge, 11 kWh, soit 2 kWh par heure.
NUIT = ("WB-0001,2026-07-08 00:00:00,2026-07-08 05:30:00,11.000kWh,"
        "05h30min,1.10€")

# Heures creuses de 23 h a 5 h ; heures et prix ronds inventes.
GRILLE_HP_HC = {"id": "t", "nom": "HP/HC", "type": "hp_hc",
                "debut": "2020-01-01", "fin": None,
                "prix_hp": 0.20, "prix_hc": 0.10,
                "abonnement_mensuel": 0.0,
                "plages_hc": [["23:00", "05:00"]]}

REGLAGES = {"capacite_batterie": 0.0, "rendement_charge": 0.9}


def ecrire(chemin: Path, contenu) -> None:
    chemin.parent.mkdir(parents=True, exist_ok=True)
    chemin.write_text(json.dumps(contenu, ensure_ascii=False),
                      encoding="utf-8")


def ecrire_csv(dossier: Path, lignes: list[str]) -> Path:
    chemin = dossier / "borne.csv"
    chemin.write_text("\n".join([ENTETE_CSV] + lignes), encoding="utf-8")
    return chemin


@pytest.fixture
def dossier(tmp_path, monkeypatch):
    """Un dossier de donnees neuf, reglage d'horloge a -60."""
    ancien = r.BASE
    r.rediriger_donnees(tmp_path)
    monkeypatch.setattr(r, "DERNIERE_RESTAURATION", None)
    monkeypatch.setattr(r, "ECHEC_BACKUP", None, raising=False)
    ecrire(tmp_path / "tarifs.json", {"correction_csv_minutes": -60,
                                      "tarifs": [GRILLE_HP_HC]})
    r.vider_cache()
    yield tmp_path
    r.rediriger_donnees(ancien)


def la_recharge() -> dict:
    return r.charger_donnees()["recharges"][0]


def test_import_avec_moins_60_compte_tout_en_heures_creuses(dossier):
    """Le point de depart du constat."""
    r.importer_csv_maison(ecrire_csv(dossier, [NUIT]))
    rec = la_recharge()
    assert rec["date"] == "2026-07-07T23:00"
    assert rec["kwh_hp"] == 0


def test_passer_a_zero_replace_la_recharge_a_sa_vraie_heure(dossier):
    r.importer_csv_maison(ecrire_csv(dossier, [NUIT]))
    bilan = r.enregistrer_reglages_borne(
        dict(REGLAGES, correction_csv_minutes=0))
    assert bilan["decalees"] == 1 and bilan["laissees"] == []
    rec = la_recharge()
    assert rec["date"] == "2026-07-08T00:00"
    assert rec["fin"] == "2026-07-08T05:30"
    # 5 h -> 5 h 30 en heures pleines : 30 min sur 5 h 30, soit 1 kWh.
    assert rec["kwh_hp"] == pytest.approx(1.0, abs=0.01)
    assert rec["kwh_hc"] == pytest.approx(10.0, abs=0.01)
    assert rec["cout_eur"] == pytest.approx(1 * 0.20 + 10 * 0.10, abs=0.01)
    # L'heure ecrite par la borne ne change pas : c'est elle qui reconnait
    # la ligne au prochain import.
    assert rec["debut_borne"] == "2026-07-08T00:00:00"
    assert r.charger_config()["correction_csv_minutes"] == 0


def test_reimport_apres_changement_n_ajoute_rien(dossier):
    r.importer_csv_maison(ecrire_csv(dossier, [NUIT]))
    r.enregistrer_reglages_borne(dict(REGLAGES, correction_csv_minutes=0))
    bilan = r.importer_csv_maison(ecrire_csv(dossier, [NUIT]))
    assert bilan["ajoutes"] == 0 and bilan["doublons"] == 1
    assert len(r.charger_donnees()["recharges"]) == 1
    assert la_recharge()["date"] == "2026-07-08T00:00"


def test_recharge_importee_sans_heure_de_borne_est_decalee_aussi(dossier):
    """Les recharges importees avant le 16/10/2026 n'ont pas debut_borne :
    elles portent l'ancienne correction, on les decale de la difference.
    On ne leur invente pas d'heure de borne (elle n'aurait pas les
    secondes du CSV, et la ligne ne serait plus reconnue au reimport)."""
    ecrire(dossier / "recharges.json", {"recharges": [
        {"id": "x", "date": "2026-07-07T23:00", "fin": "2026-07-08T04:30",
         "lieu": "maison", "kwh": 11.0, "kwh_hp": 0.0, "kwh_hc": 11.0,
         "cout_eur": 1.1, "source": "csv_import", "chargeur": "WB-0001"}]})
    r.vider_cache()
    r.enregistrer_reglages_borne(dict(REGLAGES, correction_csv_minutes=0))
    rec = la_recharge()
    assert rec["date"] == "2026-07-08T00:00"
    assert rec["fin"] == "2026-07-08T05:30"
    assert rec["kwh_hp"] == pytest.approx(1.0, abs=0.01)
    assert "debut_borne" not in rec
    # Et le CSV reimporte la reconnait toujours.
    bilan = r.importer_csv_maison(ecrire_csv(dossier, [NUIT]))
    assert bilan["ajoutes"] == 0
    assert len(r.charger_donnees()["recharges"]) == 1


def test_une_saisie_a_la_main_ne_bouge_pas(dossier):
    manuelle = {"id": "m", "date": "2026-07-07T23:00",
                "fin": "2026-07-08T04:30", "lieu": "maison", "kwh": 11.0,
                "kwh_hp": 0.0, "kwh_hc": 11.0, "cout_eur": 1.1,
                "source": "manuel"}
    ecrire(dossier / "recharges.json", {"recharges": [manuelle]})
    r.vider_cache()
    bilan = r.enregistrer_reglages_borne(
        dict(REGLAGES, correction_csv_minutes=0))
    assert bilan["decalees"] == 0
    assert la_recharge() == manuelle


def test_meme_correction_ne_touche_a_rien(dossier):
    r.importer_csv_maison(ecrire_csv(dossier, [NUIT]))
    avant = la_recharge()
    bilan = r.enregistrer_reglages_borne(
        dict(REGLAGES, correction_csv_minutes=-60))
    assert bilan["decalees"] == 0
    assert la_recharge() == avant


def test_aller_retour_rend_les_valeurs_d_origine(dossier):
    r.importer_csv_maison(ecrire_csv(dossier, [NUIT]))
    avant = la_recharge()
    r.enregistrer_reglages_borne(dict(REGLAGES, correction_csv_minutes=0))
    r.enregistrer_reglages_borne(dict(REGLAGES, correction_csv_minutes=-60))
    assert la_recharge() == avant
