"""Choix Clair / Sombre au tout premier lancement (demande de l'auteur,
16/10/2026).

Jusqu'ici, le mode sombre ne se trouvait que dans Parametres › Apparence :
un nouvel utilisateur ne savait pas qu'il existait. Au premier lancement,
avant que la fenetre ne s'ouvre, l'application demande maintenant « Clair ou
Sombre ? ». Elle ne le demande jamais a quelqu'un qui a deja des donnees
(mise a jour d'une ancienne version) ni a quelqu'un qui a deja choisi.
"""

from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QMessageBox

import premier_theme
import theme_qt


def _reglages(tmp_path):
    """Des preferences jetables, jamais le registre de l'utilisateur."""
    return QSettings(str(tmp_path / "preferences.ini"),
                     QSettings.Format.IniFormat)


def _dossier(tmp_path):
    dossier = tmp_path / "donnees"
    dossier.mkdir()
    return dossier


def test_dossier_vide_et_aucun_choix_c_est_un_premier_lancement(tmp_path):
    assert premier_theme.est_premier_lancement(_reglages(tmp_path),
                                               _dossier(tmp_path))


def test_dossier_absent_c_est_aussi_un_premier_lancement(tmp_path):
    assert premier_theme.est_premier_lancement(_reglages(tmp_path),
                                               tmp_path / "pas_encore_cree")


def test_deja_des_recharges_on_ne_demande_rien(tmp_path):
    """Une mise a jour d'une ancienne version : l'utilisateur a deja ses
    habitudes, la question le surprendrait."""
    dossier = _dossier(tmp_path)
    (dossier / "recharges.json").write_text("{}", encoding="utf-8")
    assert not premier_theme.est_premier_lancement(_reglages(tmp_path),
                                                   dossier)


def test_deja_des_tarifs_on_ne_demande_rien(tmp_path):
    dossier = _dossier(tmp_path)
    (dossier / "tarifs.json").write_text("{}", encoding="utf-8")
    assert not premier_theme.est_premier_lancement(_reglages(tmp_path),
                                                   dossier)


def test_theme_deja_choisi_on_ne_demande_rien(tmp_path):
    reglages = _reglages(tmp_path)
    reglages.setValue(theme_qt.CLE_THEME, "clair")
    assert not premier_theme.est_premier_lancement(reglages,
                                                   _dossier(tmp_path))


def test_preference_abimee_traitee_comme_absente(tmp_path):
    """Une valeur revenue en liste (vu dans le Photovoltaique, audit du
    13/10/2026) ne fait pas planter le demarrage : on repose la question."""
    reglages = _reglages(tmp_path)
    reglages.setValue(theme_qt.CLE_THEME, ["clair", "sombre"])
    assert premier_theme.est_premier_lancement(reglages, _dossier(tmp_path))


def test_preference_abimee_lue_comme_le_clair(tmp_path):
    """Meme cas, a chaque demarrage (app.py) : le clair, pas un plantage."""
    reglages = _reglages(tmp_path)
    reglages.setValue(theme_qt.CLE_THEME, ["clair", "sombre"])
    assert theme_qt.nom_du_theme(reglages) == "clair"


def test_le_choix_sombre_est_retenu(tmp_path):
    reglages = _reglages(tmp_path)
    nom = premier_theme.demander_au_premier_lancement(
        reglages, _dossier(tmp_path), demander=lambda: "sombre")
    assert nom == "sombre"
    assert theme_qt.nom_du_theme(reglages) == "sombre"


def test_le_choix_est_retenu_pour_ne_plus_redemander(tmp_path):
    """Une fois repondu, la question ne revient plus, meme si l'utilisateur
    n'a encore rien saisi."""
    reglages, dossier = _reglages(tmp_path), _dossier(tmp_path)
    premier_theme.demander_au_premier_lancement(
        reglages, dossier, demander=lambda: "clair")
    assert not premier_theme.est_premier_lancement(reglages, dossier)


def test_pas_de_question_hors_premier_lancement(tmp_path):
    dossier = _dossier(tmp_path)
    (dossier / "recharges.json").write_text("{}", encoding="utf-8")

    def demander():
        raise AssertionError("la question n'aurait pas du etre posee")
    assert premier_theme.demander_au_premier_lancement(
        _reglages(tmp_path), dossier, demander=demander) is None


def test_la_boite_propose_clair_et_sombre_clair_par_defaut(qapp):
    """Deux boutons qui disent le choix ; Entree garde le clair, le theme
    de reference ; la boite dit ou changer d'avis."""
    boite, clair, sombre = premier_theme.boite_du_choix()
    assert clair.text() == "Clair"
    assert sombre.text() == "Sombre"
    assert boite.defaultButton() is clair
    assert boite.escapeButton() is clair
    # Insecable : le chemin ne se coupe pas en fin de ligne.
    assert "Paramètres › Apparence" in boite.text()
    assert isinstance(boite, QMessageBox)
