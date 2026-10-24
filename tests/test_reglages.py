"""Les trois réglages de la voiture et de la borne, saisis dans l'application.

Jusqu'à la v1.25.0 ils ne se modifiaient qu'au Bloc-notes, dans tarifs.json.
valider_reglages() contrôle ce qu'on tape dans la page Paramètres avant de
l'enregistrer.
"""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

import pytest

os.environ.setdefault("RECHARGES_DATA_DIR",
                      tempfile.mkdtemp(prefix="recharges_reglages_"))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import recharges as r  # noqa: E402


def test_saisie_ordinaire_a_la_francaise():
    assert r.valider_reglages("52,5", "90", "-60") == {
        "capacite_batterie": 52.5,
        "rendement_charge": 0.9,
        "correction_csv_minutes": -60,
        "puissance_borne_kw": 0.0,     # facultative (23/10/2026)
    }


def test_cases_vides_valeurs_neutres():
    """Un nouvel utilisateur qui ne sait pas quoi mettre laisse vide."""
    assert r.valider_reglages("", "", "") == {
        "capacite_batterie": 0.0,
        "rendement_charge": 0.9,
        "correction_csv_minutes": 0,
        "puissance_borne_kw": 0.0,
    }


@pytest.mark.parametrize("capacite, rendement, correction, motif", [
    ("beaucoup", "90", "0", "Capacité"),
    ("-5", "90", "0", "Capacité"),
    ("500", "90", "0", "Capacité"),
    ("64", "0,9", "0", "pour cent"),    # la fraction de l'ancien fichier
    ("64", "120", "0", "Rendement"),
    ("64", "90", "1,5", "entier"),
    ("64", "90", "2000", "Correction"),
])
def test_saisies_refusees_avec_un_message_clair(capacite, rendement,
                                                  correction, motif):
    with pytest.raises(ValueError, match=motif):
        r.valider_reglages(capacite, rendement, correction)


def test_enregistrer_puis_relire(tmp_path):
    """Le chemin exact du bouton « Enregistrer les réglages », sur un
    dossier jetable : ce qui est écrit est bien ce que l'application relit,
    et la grille tarifaire n'est pas touchée."""
    ancien = r.dossier_donnees()
    r.rediriger_donnees(tmp_path)
    try:
        tarifs_avant = r.charger_tarifs()
        r.enregistrer_config(r.valider_reglages("52", "88", "15"))
        config = r.charger_config()
        assert config["capacite_batterie"] == 52.0
        assert config["rendement_charge"] == 0.88
        assert config["correction_csv_minutes"] == 15
        assert r.charger_tarifs() == tarifs_avant
    finally:
        r.rediriger_donnees(ancien)
