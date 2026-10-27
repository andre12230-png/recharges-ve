"""Audits du 26/10/2026, etape 4 : les decisions prises le 27/10/2026.

- #5 (A5) : a l'import du CSV, une saisie manuelle proche (moins de 2 h,
  meme energie) est remplacee par la session de la borne. La regle est
  gardee, mais elle agissait sans dire laquelle : le compte rendu ne donnait
  qu'un nombre. Une AUTRE session de la borne pouvait ainsi effacer une
  vraie saisie sans que personne le voie. Desormais, le bilan de l'import
  donne la liste des remplacements, et le compte rendu l'affiche.
- A10 : l'installeur prenait tout le dossier construit, sauf une liste
  d'exclusions. Un fichier personnel au nom imprevu (un export Excel, par
  exemple) serait parti dans l'installeur public. Desormais, il ne prend
  que ce qui est nomme : le programme et son dossier _internal.

#6 et A2 ne sont pas corriges, par decision : voir PROJET.md (reserves).

Donnees inventees, dans un dossier temporaire.

    py -m pytest tests/test_audit_2026_10_26_decisions.py
"""

import json
import os
import re
import sys
import tempfile
from datetime import datetime
from pathlib import Path

import pytest

os.environ.setdefault("RECHARGES_DATA_DIR",
                      tempfile.mkdtemp(prefix="recharges_decisions_1026_"))
RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))

import recharges as r  # noqa: E402

PRIX_UNIQUE = {"id": "t_simple", "nom": "Prix unique", "type": "simple",
               "debut": "2020-01-01", "fin": None, "prix_kwh": 0.20,
               "abonnement_mensuel": 0.0}


@pytest.fixture
def dossier(tmp_path, monkeypatch):
    """Un dossier de donnees neuf avec un tarif a prix unique."""
    ancien = r.BASE
    r.rediriger_donnees(tmp_path)
    monkeypatch.setattr(r, "DERNIERE_RESTAURATION", None)
    monkeypatch.setattr(r, "PREMIER_DEMARRAGE", False)
    monkeypatch.setattr(r, "INCIDENT_TARIFS", None, raising=False)
    (tmp_path / "tarifs.json").write_text(
        json.dumps({"tarifs": [PRIX_UNIQUE], "correction_csv_minutes": 0},
                   ensure_ascii=False), encoding="utf-8")
    yield tmp_path
    r.rediriger_donnees(ancien)


def _csv(dossier: Path, lignes: list[str]) -> Path:
    chemin = dossier / "export.csv"
    entete = "Chargeur;Début;Fin;Énergie;Durée;Coût €"
    chemin.write_bytes("\r\n".join([entete, *lignes]).encode("utf-8"))
    return chemin


# ---------- #5 : la liste des saisies remplacees ----------

def test_5_le_bilan_dit_quelle_saisie_a_ete_remplacee(dossier):
    # Saisie a la main a 8 h, 10 kWh ; le CSV contient une session a 9 h 30,
    # 10,05 kWh : la regle les rapproche (moins de 2 h, meme energie).
    r.ajouter_recharge_maison(datetime(2026, 3, 1, 8, 0),
                              datetime(2026, 3, 1, 10, 0), 10.0)
    chemin = _csv(dossier, ["BORNE1;2026-03-01 09:30:00;2026-03-01 11:00:00;"
                            "10.05;1:30;2.01"])
    bilan = r.importer_csv_maison(chemin)
    assert bilan["remplaces"] == 1
    assert bilan["remplacements"] == [{
        "avant_date": "2026-03-01T08:00", "avant_kwh": 10.0,
        "apres_date": "2026-03-01T09:30", "apres_kwh": 10.05,
    }]


def test_5_sans_remplacement_la_liste_est_vide(dossier):
    chemin = _csv(dossier, ["BORNE1;2026-03-01 09:30:00;2026-03-01 11:00:00;"
                            "10.05;1:30;2.01"])
    bilan = r.importer_csv_maison(chemin)
    assert bilan["remplacements"] == []


def _res(**autres) -> dict:
    return {"ajoutes": 0, "remplaces": 0, "doublons": 0, "zero_kwh": 0,
            "total_lus": 1, **autres}


def test_5_le_compte_rendu_affiche_chaque_remplacement():
    from pages import importer as im
    texte, _ = im.texte_resultat(_res(remplaces=1, remplacements=[{
        "avant_date": "2026-03-01T08:00", "avant_kwh": 10.0,
        "apres_date": "2026-03-01T09:30", "apres_kwh": 10.05}]))
    assert "01/03/2026 08:00" in texte
    assert "01/03/2026 09:30" in texte
    assert "10,00\xa0kWh" in texte and "10,05\xa0kWh" in texte
    assert "vérifier" in texte


def test_5_compte_rendu_inchange_sans_remplacement():
    """Un ancien bilan (sans la cle) ou une liste vide : rien n'est ajoute."""
    from pages import importer as im
    texte, _ = im.texte_resultat(_res(ajoutes=1))
    assert "\n" not in texte
    texte_vide, _ = im.texte_resultat(_res(ajoutes=1, remplacements=[]))
    assert texte_vide == texte


# ---------- A10 : l'installeur ne prend que ce qui est nomme ----------

def _sources_installeur() -> list[str]:
    iss = (RACINE / "installeur" / "recharges-ve.iss").read_text(
        encoding="utf-8-sig")
    return [m.group(1) for m in re.finditer(r'^Source:\s*"([^"]+)"', iss,
                                            re.MULTILINE)]


def test_a10_installeur_liste_explicite():
    sources = _sources_installeur()
    # Aucune ligne ne prend la racine du dossier construit en vrac.
    assert '{#Construit}\\*' not in sources
    assert sorted(sources) == sorted([
        "{#Construit}\\Recharges-VE.exe",
        "{#Construit}\\_internal\\*",
        "{#Racine}LICENSE",
    ])
