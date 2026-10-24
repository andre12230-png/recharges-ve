"""Heures pleines et creuses justes la nuit du changement d'heure
(second audit du 16/10/2026, constat A2).

Les heures d'une recharge sont rangees « a l'heure de l'horloge », sans
fuseau. Le calcul comptait les heures d'horloge : la nuit ou l'on avance
l'heure, 01:30 -> 04:30 passait pour 3 h alors que la voiture n'a charge
que 2 h ; la nuit ou on la recule, 02:30 -> 03:30 passait pour 1 h au lieu
de 2. La part d'energie en heures creuses, donc le cout, etait faux.

Les plages d'heures creuses restent lues a l'horloge (c'est ainsi que le
compteur les applique) ; seules les durees sont mesurees en temps reel.

Le fuseau est fixe a Paris pour ces tests : ils donnent le meme resultat
sur tout ordinateur. Tarifs et energies inventes.

    py -m pytest tests/test_changement_heure.py
"""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest

import recharges as r
import temps_reel

zoneinfo = pytest.importorskip("zoneinfo")
try:
    PARIS = zoneinfo.ZoneInfo("Europe/Paris")
except zoneinfo.ZoneInfoNotFoundError:          # base des fuseaux absente
    pytest.skip("fuseau Europe/Paris indisponible", allow_module_level=True)


def _tarif(debut_hc: str, fin_hc: str) -> list[dict]:
    return [{"id": "t", "nom": "HP/HC inventé", "type": "hp_hc",
             "debut": "2020-01-01", "fin": None,
             "prix_hp": 0.20, "prix_hc": 0.10,
             "plages_hc": [[debut_hc, fin_hc]]}]


@pytest.fixture(autouse=True)
def fuseau_de_paris(monkeypatch):
    monkeypatch.setattr(temps_reel, "FUSEAU_DES_DUREES", PARIS)


def test_nuit_du_passage_a_l_heure_d_ete():
    # 00:30 -> 02:30 UTC le 29/03/2026 = 01:30 -> 04:30 a l'horloge, 2 h
    # reelles dont 1 h 30 en heures creuses (01:30 -> 04:00).
    res = r.calculer_cout(datetime(2026, 3, 29, 1, 30),
                          datetime(2026, 3, 29, 4, 30), 40,
                          _tarif("01:00", "04:00"))
    assert res["kwh_hc"] == pytest.approx(30.0)
    assert res["kwh_hp"] == pytest.approx(10.0)
    assert res["cout"] == pytest.approx(5.00)


def test_nuit_du_retour_a_l_heure_d_hiver():
    # 00:30 -> 02:30 UTC le 25/10/2026 = 02:30 (heure d'ete) -> 03:30 (heure
    # d'hiver) a l'horloge, 2 h reelles dont 30 min en heures creuses.
    res = r.calculer_cout(datetime(2026, 10, 25, 2, 30),
                          datetime(2026, 10, 25, 3, 30), 40,
                          _tarif("03:00", "04:00"))
    assert res["kwh_hc"] == pytest.approx(10.0)
    assert res["kwh_hp"] == pytest.approx(30.0)
    assert res["cout"] == pytest.approx(7.00)


def test_une_nuit_ordinaire_ne_change_pas():
    # Meme recharge un autre jour : le calcul d'avant, a l'identique.
    res = r.calculer_cout(datetime(2026, 3, 22, 1, 30),
                          datetime(2026, 3, 22, 4, 30), 30,
                          _tarif("01:00", "04:00"))
    assert res["kwh_hc"] == pytest.approx(25.0)
    assert res["kwh_hp"] == pytest.approx(5.0)
    assert res["cout"] == pytest.approx(3.50)


def test_import_csv_en_utc_la_nuit_du_changement_d_heure():
    # Bout a bout : une date UTC d'un fichier de borne, lue puis calculee.
    debut = r._date_csv("2026-03-29T00:30:00Z")
    fin = r._date_csv("2026-03-29T02:30:00Z")
    if (debut, fin) != (datetime(2026, 3, 29, 1, 30),
                        datetime(2026, 3, 29, 4, 30)):
        pytest.skip("cet ordinateur n'est pas a l'heure de Paris")
    res = r.calculer_cout(debut, fin, 40, _tarif("01:00", "04:00"))
    assert res["cout"] == pytest.approx(5.00)


def test_par_defaut_le_fuseau_est_celui_de_l_ordinateur(monkeypatch):
    monkeypatch.setattr(temps_reel, "FUSEAU_DES_DUREES", None)
    # Une heure d'horloge ordinaire dure une heure, quel que soit le fuseau.
    assert temps_reel.secondes_reelles(datetime(2026, 6, 1, 10, 0),
                                       datetime(2026, 6, 1, 11, 0)) == 3600.0


# ---------- une duree au lieu de l'heure de fin ----------

def test_une_duree_tapee_compte_en_temps_reel():
    # « +2h » depuis 01:30 la nuit du passage a l'heure d'ete : la voiture
    # s'arrete a 04:30 a l'horloge, pas a 03:30.
    import saisie
    lu = saisie.lire_recharge_maison("29/03/2026", "01:30", "", "+2h",
                                     "40", "",
                                     maintenant=datetime(2026, 10, 17))
    assert lu["fin"] == datetime(2026, 3, 29, 4, 30)


def test_une_duree_corrigee_compte_en_temps_reel():
    import saisie
    recharge = {"id": "x", "date": "2026-10-25T02:30",
                "fin": "2026-10-25T03:00", "lieu": "maison", "kwh": 40}
    lu = saisie.lire_modification_recharge(
        recharge, {"date_jour": "25/10/2026", "date_heure": "02:30",
                   "fin_jour": "", "fin_heure": "+2h", "kwh": "40"},
        maintenant=datetime(2026, 10, 27))
    # 02:30 (heure d'ete) + 2 h = 03:30 (heure d'hiver).
    assert lu["fin"] == "2026-10-25T03:30"


def test_une_duree_lue_dans_un_fichier_de_borne_compte_en_temps_reel():
    records, _, _ = r._depouiller_avec(
        "Début;Durée;kWh\n29/03/2026 01:30;2:00;40\n",
        {"debut": 0, "fin": None, "duree": 1, "kwh": 2, "unite": "kWh",
         "cout": None})
    assert records[0][2] == "2026-03-29 04:30:00"


def test_une_duree_un_jour_ordinaire_ne_change_pas():
    assert temps_reel.apres_duree(datetime(2026, 3, 1, 22, 0),
                                  timedelta(hours=8)) == datetime(2026, 3, 2, 6, 0)
