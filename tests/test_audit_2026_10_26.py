"""Audits du 26/10/2026, etape 1 : calculs et import.

Cinq defauts reproduits ici avant leur correction :

- #1 (A1) : avec la puissance de borne reglee, la fin de charge etait
  calculee par une simple addition d'horloge. La nuit du passage a l'heure
  d'ete, elle tombait une heure trop tot : cout faux, sans aucun signe.
- #2 : une ligne CSV avec plus de champs que la ligne de titres (virgule
  decimale sans guillemets, dans un fichier separe par des virgules) etait
  lue de travers : energie et cout decales, « 1 ajoutee » sans alerte.
- A8 : une recharge finissant pile a minuit, le dernier jour couvert par la
  grille, etait refusee a l'import alors que le cout se calcule.
- #7 : une recharge qui traverse un trou de la grille tarifaire faisait
  echouer l'import avec le message de la saisie a la main, au lieu du
  message prevu pour l'import.
- #13 et #14 : la case de duree plantait sur « +99999999999999min » et
  repondait en anglais sur « +²min ».

Le fuseau est fixe a Paris pour les calculs d'heure. Donnees inventees,
dans un dossier temporaire.

    py -m pytest tests/test_audit_2026_10_26.py
"""

import json
import os
import sys
import tempfile
from datetime import datetime
from pathlib import Path

import pytest

os.environ.setdefault("RECHARGES_DATA_DIR",
                      tempfile.mkdtemp(prefix="recharges_audit_1026_"))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import recharges as r  # noqa: E402
import saisie  # noqa: E402
import temps_reel  # noqa: E402

zoneinfo = pytest.importorskip("zoneinfo")
try:
    PARIS = zoneinfo.ZoneInfo("Europe/Paris")
except zoneinfo.ZoneInfoNotFoundError:          # base des fuseaux absente
    pytest.skip("fuseau Europe/Paris indisponible", allow_module_level=True)


@pytest.fixture(autouse=True)
def fuseau_de_paris(monkeypatch):
    monkeypatch.setattr(temps_reel, "FUSEAU_DES_DUREES", PARIS)


# Heures creuses de 3 h a 5 h ; prix ronds inventes.
GRILLE_HP_HC = [{"id": "t", "nom": "HP/HC inventé", "type": "hp_hc",
                 "debut": "2020-01-01", "fin": None,
                 "prix_hp": 0.30, "prix_hc": 0.10,
                 "plages_hc": [["03:00", "05:00"]]}]


# ---------- #1 : fin de charge la nuit du changement d'heure ----------

def test_puissance_reglee_nuit_du_passage_a_l_heure_d_ete():
    """Depart a 1 h 30, 14 kWh a 7 kW : 2 h de charge reelle. L'horloge
    saute de 2 h a 3 h : la charge finit a 4 h 30, pas a 3 h 30.
    30 min reelles en heures pleines (3,5 kWh), 1 h 30 en heures creuses
    (10,5 kWh) : 3,5 x 0,30 + 10,5 x 0,10 = 2,10 EUR."""
    calc = r.calculer_cout(datetime(2026, 3, 29, 1, 30),
                           datetime(2026, 3, 29, 6, 0), 14.0,
                           GRILLE_HP_HC, puissance_kw=7)
    assert calc["kwh_hp"] == pytest.approx(3.5, abs=0.001)
    assert calc["kwh_hc"] == pytest.approx(10.5, abs=0.001)
    assert calc["cout"] == pytest.approx(2.10, abs=0.001)


def test_puissance_reglee_nuit_du_retour_a_l_heure_d_hiver():
    """Depart a 2 h 30 (premier passage), 2 h de charge reelle : l'horloge
    revient de 3 h a 2 h, la charge finit a 3 h 30. Meme resultat que la
    meme recharge sans puissance, arretee a 3 h 30."""
    debut = datetime(2026, 10, 25, 2, 30)
    avec = r.calculer_cout(debut, datetime(2026, 10, 25, 6, 0), 14.0,
                           GRILLE_HP_HC, puissance_kw=7)
    sans = r.calculer_cout(debut, datetime(2026, 10, 25, 3, 30), 14.0,
                           GRILLE_HP_HC)
    assert avec == sans


def test_puissance_reglee_une_nuit_ordinaire_ne_change_pas():
    """Un autre jour : 2 h de charge de 1 h 30 a 3 h 30, comme avant."""
    debut = datetime(2026, 7, 8, 1, 30)
    avec = r.calculer_cout(debut, datetime(2026, 7, 8, 6, 0), 14.0,
                           GRILLE_HP_HC, puissance_kw=7)
    sans = r.calculer_cout(debut, datetime(2026, 7, 8, 3, 30), 14.0,
                           GRILLE_HP_HC)
    assert avec == sans


# ---------- #2 : ligne CSV avec des champs en trop ----------

TITRES = "NS du chargeur,Heure de debut,Heure de fin,Consommation,Duree,Cout"


def test_ligne_avec_champs_en_trop_non_reconnue():
    """« 5,25 » et « 1,50 » sans guillemets : huit champs au lieu de six.
    La ligne ne doit pas etre lue (5,0 kWh et 60 EUR), mais comptee comme
    non reconnue."""
    contenu = (TITRES + "\n"
               "B1,2026-05-01 10:00,2026-05-01 11:00,5,25,60,1,50\n")
    records, non_reconnues, n_lignes = r._depouiller_csv(contenu)
    assert records == []
    assert non_reconnues == 1
    assert n_lignes == 1


def test_meme_ligne_avec_guillemets_lue_correctement():
    contenu = (TITRES + "\n"
               'B1,2026-05-01 10:00,2026-05-01 11:00,"5,25",60,"1,50"\n')
    records, non_reconnues, _ = r._depouiller_csv(contenu)
    assert non_reconnues == 0
    assert float(records[0][3]) == pytest.approx(5.25)
    assert float(records[0][5]) == pytest.approx(1.50)


def test_separateur_final_toujours_accepte():
    """Certains tableurs terminent chaque ligne par un separateur : une
    derniere colonne vide n'est pas un champ en trop."""
    contenu = (TITRES + "\n"
               "B1,2026-05-01 10:00,2026-05-01 11:00,5.25,60,1.50,\n")
    records, non_reconnues, _ = r._depouiller_csv(contenu)
    assert non_reconnues == 0
    assert float(records[0][3]) == pytest.approx(5.25)


# ---------- A8 et #7 : import et grille tarifaire ----------

ENTETE_CSV = ("NS du chargeur,Heure de debut,Heure de fin,Consommation,"
              "Duree,Cout")


def tarif_simple(ident, debut, fin, prix):
    return {"id": ident, "nom": f"Tarif {ident}", "type": "simple",
            "debut": debut, "fin": fin, "prix_kwh": prix,
            "abonnement_mensuel": 0.0}


@pytest.fixture
def dossier(tmp_path, monkeypatch):
    """Un dossier de donnees neuf ; la grille est posee par chaque test."""
    ancien = r.BASE
    r.rediriger_donnees(tmp_path)
    monkeypatch.setattr(r, "DERNIERE_RESTAURATION", None)
    monkeypatch.setattr(r, "ECHEC_BACKUP", None, raising=False)
    yield tmp_path
    r.rediriger_donnees(ancien)


def poser_grille(dossier: Path, tarifs: list[dict]) -> None:
    (dossier / "tarifs.json").write_text(
        json.dumps({"correction_csv_minutes": 0, "tarifs": tarifs},
                   ensure_ascii=False), encoding="utf-8")
    r.vider_cache()


def importer(dossier: Path, ligne: str) -> dict:
    chemin = dossier / "export.csv"
    chemin.write_text(ENTETE_CSV + "\n" + ligne + "\n", encoding="utf-8")
    return r.importer_csv_maison(chemin)


def test_recharge_finie_a_minuit_le_dernier_jour_du_tarif(dossier):
    """Tarif valable jusqu'au 30/06 inclus ; recharge du 30/06 23 h au
    01/07 0 h : entierement couverte, 7 kWh a 0,20 = 1,40 EUR."""
    poser_grille(dossier, [tarif_simple("a", "2026-01-01", "2026-06-30", 0.20)])
    bilan = importer(dossier, "WB-0001,2026-06-30 23:00:00,"
                              "2026-07-01 00:00:00,7.000kWh,01h00min,1.40€")
    assert bilan["ajoutes"] == 1
    recharge = r.charger_donnees()["recharges"][0]
    assert recharge["cout_eur"] == pytest.approx(1.40)


def test_recharge_qui_traverse_un_trou_de_grille(dossier):
    """Aucun tarif le 01/04 : la recharge du 31/03 au 02/04 est hors grille.
    L'import est refuse avec le message de l'import (« Rien n'a été
    importé »), pas celui de la saisie a la main."""
    poser_grille(dossier, [
        tarif_simple("a", "2026-01-01", "2026-03-31", 0.20),
        tarif_simple("b", "2026-04-02", None, 0.25)])
    with pytest.raises(ValueError, match="Rien n'a été importé"):
        importer(dossier, "WB-0001,2026-03-31 22:00:00,"
                          "2026-04-02 06:00:00,20.000kWh,32h00min,4.00€")
    assert r.charger_donnees()["recharges"] == []


# ---------- #13 et #14 : la case de duree ----------

def test_duree_avec_exposant_message_en_francais():
    with pytest.raises(ValueError, match="Une durée s'écrit"):
        saisie.lire_duree("+²min")


def test_duree_gigantesque_refusee_sans_planter():
    with pytest.raises(ValueError, match="plus de 30 jours"):
        saisie.lire_duree("+99999999999999min")


def test_durees_ordinaires_toujours_acceptees():
    assert saisie.lire_duree("+45min").total_seconds() == 45 * 60
    assert saisie.lire_duree("+6h12").total_seconds() == (6 * 60 + 12) * 60
