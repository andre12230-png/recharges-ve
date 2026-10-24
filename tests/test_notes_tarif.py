"""Les notes d'un tarif survivent a sa modification.

Bug trouve le 25/09/2026 (v1.31.1) : tarifs.json peut porter, a cote des
prix, des notes « _commentaire », « _commentaire_plages »... (d'ou vient la
grille, les horaires officiels du compteur). La fenetre de tarif reconstruit
le tarif a partir de ses seules cases : enregistrer un tarif, meme sans rien
y changer, effacait donc ses notes.

La correction est dans le moteur (enregistrer_tarif), qui ecrit le fichier :
elle protege ainsi toute fenetre qui s'en sert.

    py -m pytest tests/test_notes_tarif.py
"""

import json
import os
import sys
import tempfile
from pathlib import Path

import pytest

os.environ.setdefault("RECHARGES_DATA_DIR",
                      tempfile.mkdtemp(prefix="recharges_notes_tarif_"))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import recharges as r  # noqa: E402

TARIF = {"id": "t1", "nom": "Mon contrat", "debut": "2026-08-01",
         "fin": None, "type": "hp_hc", "abonnement_mensuel": 20.50,
         "prix_hp": 0.2345, "prix_hc": 0.135,
         "plages_hc": [["23:45", "05:15"], ["14:15", "16:45"]],
         "_commentaire": "Grille d'essai, inventée.",
         "_commentaire_plages": "Horaires officiels du compteur."}


@pytest.fixture
def dossier(tmp_path):
    """Un dossier de donnees neuf, rendu a la fin du test."""
    ancien = r.BASE
    r.rediriger_donnees(tmp_path)
    (tmp_path / "tarifs.json").write_text(
        json.dumps({"tarifs": [TARIF]}, ensure_ascii=False), encoding="utf-8")
    yield tmp_path
    r.rediriger_donnees(ancien)


def test_modifier_un_tarif_garde_ses_notes(dossier):
    # Ce que renvoie une fenetre de tarif : les cases, sans les notes.
    saisi = {k: v for k, v in TARIF.items() if not k.startswith("_")}
    saisi["prix_hp"] = 0.23
    r.enregistrer_tarif(saisi, "t1")
    enregistre = r.charger_tarifs()[0]
    assert enregistre["prix_hp"] == 0.23
    assert enregistre["_commentaire"] == TARIF["_commentaire"]
    assert enregistre["_commentaire_plages"] == TARIF["_commentaire_plages"]


def test_une_note_retapee_l_emporte(dossier):
    saisi = dict(TARIF, _commentaire="Nouvelle note.")
    r.enregistrer_tarif(saisi, "t1")
    assert r.charger_tarifs()[0]["_commentaire"] == "Nouvelle note."
