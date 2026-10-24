"""Lot 3 de l'audit du 14/10/2026 (v2.2.3) : les calculs.

Chaque test reproduit un defaut releve par l'audit, et doit rester vert
apres sa correction :

A08. la comparaison essence « Tout » oubliait le cout d'une annee sans
     kilometres (une recharge a l'instant d'un releve du 1er janvier) ;
A09. elle annoncait une part d'energie non enregistree que la marge d'une
     batterie pleine ou vide suffisait a expliquer ;
A10. « 30 derniers jours » : 30 x 24 h glissantes pour les recharges, mais
     30 jours du calendrier pour l'abonnement et les frais ;
A11. le cumul d'energie du Kilometrage additionnait des valeurs deja
     arrondies ;
A12. le jeu de demonstration ne declenchait jamais le controle d'energie
     (« conso_ref » au lieu de « conso »).

Toutes les donnees sont inventees, dans un dossier temporaire.

    py -m pytest tests/test_audit_2026_10_14_calculs.py
"""

import json
import os
import sys
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

import pytest

os.environ.setdefault("RECHARGES_DATA_DIR",
                      tempfile.mkdtemp(prefix="recharges_audit_calculs_"))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import recharges as r  # noqa: E402
from filtres import bornes_periode, filtrer_par_periode  # noqa: E402

REGLAGES = {"correction_csv_minutes": 0, "rendement_charge": 0.90,
            "capacite_batterie": 0, "conso_essence": 6.0,
            "prix_essence": 2.0, "tarifs": []}


def ecrire(chemin: Path, contenu) -> None:
    chemin.write_text(json.dumps(contenu, ensure_ascii=False),
                      encoding="utf-8")


@pytest.fixture
def dossier(tmp_path):
    """Un dossier de donnees neuf, rendu a la fin du test. Renvoie une
    fonction qui ecrit recharges, releves et reglages d'un coup."""
    ancien = r.BASE
    r.rediriger_donnees(tmp_path)

    def remplir(recharges, releves, **reglages):
        ecrire(tmp_path / "recharges.json",
               {"recharges": recharges, "releves_km": releves})
        ecrire(tmp_path / "tarifs.json", {**REGLAGES, **reglages})
        r.vider_cache()

    yield remplir
    r.rediriger_donnees(ancien)


def recharge(date, kwh, cout, ident=None):
    return {"id": ident or date, "date": date, "lieu": "exterieur",
            "kwh": kwh, "cout_eur": cout}


# ---------- A08 : couts omis dans la comparaison essence ----------

def test_a08_recharge_a_l_instant_du_releve_du_1er_janvier(dossier):
    """Variante de l'audit : une recharge datee exactement du releve du
    1er janvier tombe dans une annee sans kilometres."""
    recharges = [recharge("2025-12-15T10:00", 10.0, 2.0),
                 recharge("2026-01-01T00:00", 20.0, 4.0)]
    releves = [{"id": "k0", "date": "2025-12-01T00:00", "km": 1000},
               {"id": "k1", "date": "2026-01-01T00:00", "km": 1100}]
    dossier(recharges, releves)
    c = r.comparer_essence_periode("Tout", r.charger_config())
    # Le meme cout que la page Kilometrage, pour les memes releves.
    assert c["cout_electrique"] == r.calculer_consommation()["cout"] == 6.0
    assert c["economie"] == round(c["cout_essence"] - 6.0, 2)


def test_a08_annee_sans_distance_comptee_dans_le_total(dossier):
    """Exemple de l'audit : 30 EUR au Kilometrage, 20 seulement dans la
    comparaison, soit 10 EUR d'economie artificielle."""
    recharges = [recharge("2025-06-01T10:00", 50.0, 20.0),
                 recharge("2026-01-01T00:00", 25.0, 10.0)]
    releves = [{"id": "k0", "date": "2025-01-01T00:00", "km": 1000},
               {"id": "k1", "date": "2026-01-01T00:00", "km": 2000}]
    dossier(recharges, releves)
    c = r.comparer_essence_periode("Tout", r.charger_config())
    assert r.calculer_consommation()["cout"] == 30.0
    assert c["cout_electrique"] == 30.0
    # L'annee sans kilometres ne fait pas de ligne « annee par annee »,
    # mais elle est nommee pour que le total reste explicable.
    assert [a["annee"] for a in c["par_annee"]] == [2025]
    assert c["sans_km"] == [{"annee": 2026, "cout_electrique": 10.0,
                             "kwh": 25.0}]


def test_a08_la_carte_nomme_l_annee_sans_kilometres(dossier, qapp):
    from PySide6.QtWidgets import QLabel

    from pages import kilometrage
    recharges = [recharge("2025-06-01T10:00", 50.0, 20.0),
                 recharge("2026-01-01T00:00", 25.0, 10.0)]
    releves = [{"id": "k0", "date": "2025-01-01T00:00", "km": 1000},
               {"id": "k1", "date": "2026-01-01T00:00", "km": 2000}]
    dossier(recharges, releves)
    c = r.comparer_essence_periode("Tout", r.charger_config())
    carte = kilometrage._carte_essence(c)
    texte = " ".join(e.text() for e in carte.findChildren(QLabel))
    assert "recharges de 2026" in texte and "aucun kilomètre" in texte


# ---------- A09 : part d'energie affirmee malgre la marge batterie ----------

def test_a09_ecart_dans_la_marge_batterie_rien_n_est_affirme(dossier):
    """Exemple de l'audit : 100 km a 20 kWh/100 km, 10 kWh enregistres,
    batterie de 50 kWh. Le Kilometrage dit « trop court » ; la
    comparaison ne doit pas annoncer 50 % d'energie non enregistree."""
    releves = [{"id": "k0", "date": "2026-03-01T10:00", "km": 1000,
                "conso": 20.0},
               {"id": "k1", "date": "2026-03-10T10:00", "km": 1100,
                "conso": 20.0}]
    dossier([recharge("2026-03-05T10:00", 10.0, 4.0)], releves,
            capacite_batterie=50.0)
    assert r.calculer_consommation()["controle"]["verdict"] == "trop_court"
    c = r.comparer_essence_periode("Tout", r.charger_config())
    assert c["part_non_enregistree"] is None


def test_a09_ecart_hors_marge_toujours_annonce(dossier):
    """Au-dela de la marge, la part reste annoncee, et c'est le meme
    verdict que le Kilometrage."""
    releves = [{"id": "k0", "date": "2026-01-01T10:00", "km": 1000,
                "conso": 20.0},
               {"id": "k1", "date": "2026-06-01T10:00", "km": 3000,
                "conso": 20.0}]
    dossier([recharge("2026-03-05T10:00", 100.0, 40.0)], releves,
            capacite_batterie=50.0)
    ctrl = r.calculer_consommation()["controle"]
    assert ctrl["verdict"] == "energie_exterieure"
    c = r.comparer_essence_periode("Tout", r.charger_config())
    # 2 000 km a 20 kWh/100 km et 90 % : 444,4 kWh attendus, 100 saisis.
    assert c["part_non_enregistree"] == 78


def test_a09_le_tableau_de_bord_ne_dit_plus_qu_elle_est_gratuite(qapp):
    """Trouve en refaisant les captures du site (14/10/2026) : la carte
    « Coût réel de vos kilomètres » disait encore « gratuites, donc sans
    effet sur ce coût »."""
    from PySide6.QtWidgets import QLabel

    from pages import tableau_de_bord
    km = {"cout_100": 3.36, "km": 13073.0, "debut": "2025-11-12T08:30",
          "fin": "2026-10-13T08:30", "essence_100": None,
          "part_exterieure": 15.0}
    cadre = tableau_de_bord._bande_cout_km(km)
    texte = " ".join(e.text() for e in cadre.findChildren(QLabel))
    assert "15\xa0%" in texte
    assert "gratuites, donc" not in texte
    assert "prix ne sont pas connus" in texte


def test_a09_le_pdf_ne_dit_plus_que_l_energie_n_a_rien_coute(tmp_path):
    import export
    essence = {"km": 2000, "debut": "2026-01-01T10:00",
               "fin": "2026-06-01T10:00", "conso_essence": 6.0,
               "prix_essence": 2.0, "cout_essence": 240.0,
               "cout_electrique": 40.0, "economie": 200.0,
               "part_non_enregistree": 78}
    assert "rien coûté" not in export.texte_part_non_enregistree(essence)


# ---------- A10 : « 30 derniers jours » ----------

def test_a10_trente_jours_du_calendrier_aujourd_hui_compris():
    aujourd_hui = datetime.now().replace(hour=0, minute=0, second=0,
                                         microsecond=0)
    premier_jour = aujourd_hui - timedelta(days=29)
    dedans = recharge((premier_jour + timedelta(minutes=5)).isoformat(
        timespec="minutes"), 10.0, 2.0)
    veille = recharge((premier_jour - timedelta(hours=1)).isoformat(
        timespec="minutes"), 10.0, 2.0)
    gardees = filtrer_par_periode([dedans, veille], "30 derniers jours")
    assert gardees == [dedans]
    # Le meme premier jour que l'abonnement et les frais.
    debut, fin = bornes_periode("30 derniers jours", [])
    assert debut == premier_jour.date()
    assert fin == aujourd_hui.date()


# ---------- A11 : cumul d'energie arrondi avant l'addition ----------

def test_a11_cumul_d_energie_sans_arrondi_intermediaire(dossier):
    """Exemple de l'audit : 100 intervalles de 10,054 kWh."""
    depart = datetime(2026, 1, 1, 8, 0)
    releves = [{"id": f"k{i}",
                "date": (depart + timedelta(days=i)).isoformat(
                    timespec="minutes"),
                "km": 1000 + 50 * i} for i in range(101)]
    recharges = [recharge((depart + timedelta(days=i, hours=12)).isoformat(
        timespec="minutes"), 10.054, 2.0, ident=f"r{i}") for i in range(100)]
    dossier(recharges, releves)
    conso = r.calculer_consommation()
    assert conso["kwh"] == 1005.4
    assert r.kilometres_par_annee()[2026]["kwh"] == 1005.4


# ---------- A12 : le jeu de demonstration exerce le controle ----------

def test_a12_jeu_de_demonstration_exerce_le_controle(tmp_path):
    ancien = r.BASE
    try:
        r.ecrire_jeu_demo(tmp_path)
        r.rediriger_donnees(tmp_path)
        ctrl = r.calculer_consommation()["controle"]
    finally:
        r.rediriger_donnees(ancien)
    assert ctrl["verdict"] != "non_configure"
    assert ctrl["kwh_attendu"] > 0


def test_a12_controle_change_d_annee(dossier):
    """Des releves qui enjambent le 1er janvier : un seul controle sur tout
    l'intervalle, et des kilometres partages au prorata entre les deux
    annees."""
    releves = [{"id": "k0", "date": "2025-12-01T00:00", "km": 1000,
                "conso": 18.0},
               {"id": "k1", "date": "2026-02-01T00:00", "km": 1620,
                "conso": 18.0}]
    recharges = [recharge("2025-12-20T10:00", 60.0, 12.0),
                 recharge("2026-01-20T10:00", 64.0, 13.0)]
    dossier(recharges, releves, capacite_batterie=50.0)
    conso = r.calculer_consommation()
    assert conso["km"] == 620 and conso["kwh"] == 124.0
    # 620 km a 18 kWh/100 km, ramenes a la prise : 124 kWh. Coherent.
    assert conso["controle"]["verdict"] == "coherent"
    annees = r.kilometres_par_annee()
    assert annees[2025]["km"] == 310.0 and annees[2026]["km"] == 310.0
    assert annees[2025]["kwh"] == 60.0 and annees[2026]["kwh"] == 64.0
