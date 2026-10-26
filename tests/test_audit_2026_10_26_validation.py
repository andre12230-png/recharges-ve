"""Audits du 26/10/2026, etape 3 : donnees et tarifs incoherents.

Defauts reproduits ici avant leur correction :

- A6 : le validateur de recharges.json acceptait une recharge sans energie
  ni cout ({} ou des « null ») ; les statistiques plantaient ensuite.
- #15 : les fonctions d'ajout et de modification acceptaient NaN (l'ecran
  le refuse, mais pas le moteur) ; le fichier etait ensuite juge abime.
- A7 : un prix ecrit en texte (« "0.2" ») passait la validation, puis le
  calcul plantait : la valeur verifiee n'etait pas celle utilisee.
- #11 : deux periodes tarifaires qui se chevauchent ; le prix dependait de
  leur ordre dans tarifs.json. Desormais la plus recente l'emporte.
- #18 : une plage d'heures creuses « 00:00-00:00 » etait acceptee et lue
  comme « aucune heure creuse ».
- #19 : une recharge dont la fin precede le debut etait calculee toute en
  heures pleines, sans erreur.

Toutes les donnees sont inventees, dans un dossier temporaire.

    py -m pytest tests/test_audit_2026_10_26_validation.py
"""

import json
import math
import os
import sys
import tempfile
from datetime import datetime
from pathlib import Path

import pytest

os.environ.setdefault("RECHARGES_DATA_DIR",
                      tempfile.mkdtemp(prefix="recharges_audit_1026v_"))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import recharges as r  # noqa: E402


def simple(ident, debut, fin, prix):
    return {"id": ident, "nom": f"Tarif {ident}", "type": "simple",
            "debut": debut, "fin": fin, "prix_kwh": prix,
            "abonnement_mensuel": 0.0}


@pytest.fixture
def dossier(tmp_path, monkeypatch):
    """Un dossier de donnees neuf avec un tarif simple a 0,20."""
    ancien = r.BASE
    r.rediriger_donnees(tmp_path)
    monkeypatch.setattr(r, "DERNIERE_RESTAURATION", None)
    monkeypatch.setattr(r, "ECHEC_BACKUP", None, raising=False)
    poser_grille(tmp_path, [simple("a", "2020-01-01", None, 0.20)])
    yield tmp_path
    r.rediriger_donnees(ancien)


def poser_grille(dossier: Path, tarifs: list[dict]) -> None:
    (dossier / "tarifs.json").write_text(
        json.dumps({"correction_csv_minutes": 0, "tarifs": tarifs},
                   ensure_ascii=False), encoding="utf-8")
    r.vider_cache()


# ---------- A6 : recharges sans energie ni cout ----------

@pytest.mark.parametrize("recharge", [
    {"date": "2026-06-01T12:00", "kwh": None, "cout_eur": None},
    {},
    {"date": "2026-06-01T12:00", "cout_eur": 2.0},          # energie absente
    {"kwh": 10.0, "cout_eur": 2.0},                         # date absente
])
def test_recharge_inexploitable_refusee(recharge):
    assert not r.structure_recharges_valide({"recharges": [recharge]})


@pytest.mark.parametrize("cout", [{"cout_eur": 2.0}, {"cout_eur": None}, {}])
def test_recharge_minimale_acceptee(cout):
    """Une date et une energie : ce que l'application a toujours ecrit. Le
    cout peut etre vide ou absent dans d'anciens fichiers (voir
    test_audit_2026_10_14 et _16) : ils restent acceptes."""
    assert r.structure_recharges_valide({"recharges": [
        {"date": "2026-06-01T12:00", "kwh": 10.0, **cout}]})


def test_cout_vide_ne_fait_pas_planter_les_statistiques():
    """Un cout vide (« null ») compte comme un cout absent : 0 dans les
    sommes. Il levait TypeError dans les totaux."""
    import filtres
    texte = filtres.texte_resume([
        {"date": "2026-06-01T12:00", "kwh": 10.0, "cout_eur": None},
        {"date": "2026-06-02T12:00", "kwh": 5.0, "cout_eur": 2.0}])
    assert "2 recharges" in texte and "2,00" in texte


# ---------- #15 : NaN refuse par le moteur ----------

def test_ajout_maison_refuse_nan(dossier):
    with pytest.raises(ValueError):
        r.ajouter_recharge_maison(datetime(2026, 6, 1, 22),
                                  datetime(2026, 6, 2, 6), math.nan)
    with pytest.raises(ValueError):
        r.ajouter_recharge_maison(datetime(2026, 6, 1, 22),
                                  datetime(2026, 6, 2, 6), 10.0,
                                  cout_wallbox=math.nan)


@pytest.mark.parametrize("kwh, cout", [(math.nan, 5.0), (10.0, math.nan),
                                       (math.inf, 5.0)])
def test_ajout_exterieur_refuse_nan(dossier, kwh, cout):
    with pytest.raises(ValueError):
        r.ajouter_recharge_exterieur(kwh, cout, date="2026-06-01T12:00")


def test_modification_refuse_nan(dossier):
    rec = r.ajouter_recharge_exterieur(10.0, 5.0, date="2026-06-01T12:00")
    with pytest.raises(ValueError):
        r.modifier_recharge(rec["id"], {"cout_eur": math.nan})
    # Le fichier reste lisible, la recharge intacte.
    r.vider_cache()
    assert r.charger_donnees()["recharges"][0]["cout_eur"] == 5.0


# ---------- A7 : prix ecrit en texte ----------

def test_prix_en_texte_converti_pour_le_calcul(dossier):
    poser_grille(dossier, [simple("a", "2020-01-01", None, "0.2")])
    tarifs = r.charger_tarifs()
    assert tarifs[0]["prix_kwh"] == 0.2
    calc = r.calculer_cout(datetime(2026, 6, 1, 22), datetime(2026, 6, 2, 0),
                           10.0, tarifs)
    assert calc["cout"] == pytest.approx(2.0)


# ---------- #11 : periodes qui se chevauchent ----------

ANNUEL = simple("annuel", "2026-01-01", "2026-12-31", 0.25)
JUIN = simple("juin", "2026-06-01", "2026-06-30", 0.40)


@pytest.mark.parametrize("ordre", [[ANNUEL, JUIN], [JUIN, ANNUEL]])
def test_la_periode_la_plus_recente_l_emporte(ordre):
    calc = r.calculer_cout(datetime(2026, 6, 15, 10), datetime(2026, 6, 15, 12),
                           10.0, ordre)
    assert calc["cout"] == pytest.approx(4.00)
    # Hors du chevauchement, l'autre periode s'applique toujours.
    calc = r.calculer_cout(datetime(2026, 7, 15, 10), datetime(2026, 7, 15, 12),
                           10.0, ordre)
    assert calc["cout"] == pytest.approx(2.50)


def test_session_a_cheval_sur_le_debut_d_une_periode_plus_recente():
    """Ancienne periode sans date de fin, nouvelle a partir du 01/06 : une
    recharge du 31/05 22 h au 01/06 2 h paie 2 h a l'ancien prix et 2 h au
    nouveau (4 kWh repartis : 2 x 0,25 + 2 x 0,40 = 1,30)."""
    grille = [simple("ancien", "2026-01-01", None, 0.25),
              simple("nouveau", "2026-06-01", None, 0.40)]
    calc = r.calculer_cout(datetime(2026, 5, 31, 22), datetime(2026, 6, 1, 2),
                           4.0, grille)
    assert calc["cout"] == pytest.approx(1.30)


def test_avertissement_dit_quel_tarif_s_applique():
    textes = " ".join(r._avertissements_grille([ANNUEL, JUIN]))
    assert "c'est « Tarif juin »" in textes


# ---------- #18 : plage d'heures creuses vide ----------

def test_plage_vide_refusee():
    tarif = {"nom": "HP/HC", "type": "hp_hc", "debut": "2026-01-01",
             "fin": None, "prix_hp": 0.20, "prix_hc": 0.10,
             "plages_hc": [["00:00", "00:00"]]}
    with pytest.raises(ValueError, match="même heure"):
        r.valider_tarif(tarif)


# ---------- #19 : fin avant le debut ----------

@pytest.mark.parametrize("fin", [datetime(2026, 6, 1, 21),
                                 datetime(2026, 6, 1, 22)])
def test_fin_avant_ou_egale_au_debut_refusee(fin):
    with pytest.raises(ValueError, match="fin"):
        r.calculer_cout(datetime(2026, 6, 1, 22), fin, 10.0,
                        [simple("a", "2020-01-01", None, 0.20)])
