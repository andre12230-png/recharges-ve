"""L'installeur et l'archive ne doivent emporter aucune donnee personnelle,
a aucune profondeur du dossier construit.

Ajoute le 15/10/2026 : le controle d'avant l'installeur ne regardait que le
premier niveau de dist/Recharges-VE, et la relecture de l'archive sautait
tout le sous-dossier _internal. Un recharges.json glisse la-dedans serait
parti chez un inconnu. Meme correction que le Photovoltaique le meme jour.
"""
from __future__ import annotations

import zipfile

import faire_installeur as fi
import preparer_distribution as pd

# Les trois fichiers d'exemple que matplotlib embarque : seuls .csv admis.
EXEMPLE_MATPLOTLIB = "_internal/matplotlib/mpl-data/sample_data/msft.csv"


def _dossier(tmp_path, noms):
    """Cree un faux dossier construit avec les fichiers donnes."""
    racine = tmp_path / "Recharges-VE"
    for nom in noms:
        chemin = racine / nom
        chemin.parent.mkdir(parents=True, exist_ok=True)
        chemin.write_text("x", encoding="utf-8")
    return racine


def _archive(tmp_path, noms):
    chemin = tmp_path / "essai.zip"
    with zipfile.ZipFile(chemin, "w") as z:
        for nom in noms:
            z.writestr(nom, "x")
    return chemin


# --- Le dossier construit (avant l'installeur et l'archive) ---------------

def test_un_dossier_propre_passe(tmp_path):
    racine = _dossier(tmp_path, [
        "Recharges-VE.exe",
        "_internal/python314.dll",
        EXEMPLE_MATPLOTLIB,
    ])
    assert fi.chercher_donnees_personnelles(racine) == []


def test_les_donnees_au_premier_niveau_sont_trouvees(tmp_path):
    racine = _dossier(tmp_path, [
        "Recharges-VE.exe", "recharges.json", "borne.csv"])
    assert fi.chercher_donnees_personnelles(racine) == [
        "borne.csv", "recharges.json"]


def test_les_donnees_dans_les_sous_dossiers_sont_trouvees(tmp_path):
    racine = _dossier(tmp_path, [
        "Recharges-VE.exe",
        "_internal/recharges.json",
        "_internal/tarifs.json",
        "sous-dossier/tarifs.json.avant",
        "_internal/backups/recharges_20260101.json",
        "_internal/export.csv",
    ])
    assert fi.chercher_donnees_personnelles(racine) == [
        "_internal/backups",
        "_internal/export.csv",
        "_internal/recharges.json",
        "_internal/tarifs.json",
        "sous-dossier/tarifs.json.avant",
    ]


def test_la_casse_ne_trompe_pas_le_controle(tmp_path):
    """Windows ne distingue pas majuscules et minuscules : le controle non
    plus."""
    racine = _dossier(tmp_path, ["_internal/Recharges.JSON", "Borne.CSV"])
    assert fi.chercher_donnees_personnelles(racine) == [
        "Borne.CSV", "_internal/Recharges.JSON"]


# --- L'archive produite ---------------------------------------------------

def test_une_archive_propre_passe(tmp_path):
    archive = _archive(tmp_path, [
        "Recharges-VE/Recharges-VE.exe",
        f"Recharges-VE/{EXEMPLE_MATPLOTLIB}",
        "README.md",
        "LICENSE",
    ])
    assert pd.verifier_archive(archive) == []


def test_les_donnees_cachees_dans_internal_sont_denoncees(tmp_path):
    archive = _archive(tmp_path, [
        f"Recharges-VE/{EXEMPLE_MATPLOTLIB}",
        "Recharges-VE/_internal/recharges.json",
        "Recharges-VE/_internal/Tarifs.json",
        "Recharges-VE/_internal/backups/copie.json",
        "Recharges-VE/_internal/borne.csv",
    ])
    assert sorted(pd.verifier_archive(archive)) == [
        "Recharges-VE/_internal/Tarifs.json",
        "Recharges-VE/_internal/backups/copie.json",
        "Recharges-VE/_internal/borne.csv",
        "Recharges-VE/_internal/recharges.json",
    ]


def test_les_donnees_hors_du_dossier_de_l_appli_sont_denoncees(tmp_path):
    archive = _archive(tmp_path, [
        "Recharges-VE/Recharges-VE.exe",
        "recharges.json",
        "backups/recharges_20260101.json",
        "borne.csv",
    ])
    assert sorted(pd.verifier_archive(archive)) == [
        "backups/recharges_20260101.json",
        "borne.csv",
        "recharges.json",
    ]
