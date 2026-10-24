"""Sauvegarde sur un support externe (cle USB, disque).

Ajout du 15/09/2026, le meme module que dans Gestion Photovoltaique : les
sauvegardes de backups\\ restent sur le meme disque que les donnees, elles
ne protegent donc pas d'une panne de ce disque.
"""
from __future__ import annotations

import os
import sys
import tempfile
from datetime import datetime
from pathlib import Path

import pytest

# Meme precaution que test_menu.py : importer app.py (ici via le test du
# bouton) ne doit jamais toucher aux vraies donnees.
os.environ.setdefault("RECHARGES_DATA_DIR",
                      tempfile.mkdtemp(prefix="recharges_sauvegarde_"))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import sauvegarde_externe as se  # noqa: E402

QUAND = datetime(2026, 9, 15, 14, 30)


@pytest.fixture
def donnees(tmp_path):
    """Un dossier de donnees et une « cle USB », tous deux jetables."""
    dossier = tmp_path / "donnees"
    dossier.mkdir()
    (dossier / "recharges.json").write_text('{"recharges": []}', encoding="utf-8")
    (dossier / "tarifs.json").write_text('{"tarifs": []}', encoding="utf-8")
    cle = tmp_path / "cle"
    cle.mkdir()
    return dossier, cle


def _sauver(dossier, cle, fichiers=None):
    fichiers = fichiers or [dossier / "recharges.json", dossier / "tarifs.json"]
    return se.sauvegarder(fichiers, cle, dossier, "Recharges VE", "v1.25.0",
                          QUAND)


def test_copie_dans_un_dossier_date(donnees):
    dossier, cle = donnees
    cible, copies = _sauver(dossier, cle)
    assert cible == cle / "Sauvegarde Recharges VE 2026-09-15 14h30"
    assert copies == ["recharges.json", "tarifs.json"]
    for nom in copies:
        assert (cible / nom).read_bytes() == (dossier / nom).read_bytes()


def test_un_mode_d_emploi_accompagne_la_copie(donnees):
    dossier, cle = donnees
    cible, _ = _sauver(dossier, cle)
    texte = (cible / "LISEZMOI.txt").read_text(encoding="utf-8")
    assert "Recharges VE v1.25.0" in texte
    assert "Fermez Recharges VE" in texte
    assert str(dossier) in texte


def test_un_nouvel_utilisateur_sans_recharge(donnees):
    """recharges.json n'apparait qu'a la premiere recharge : on sauve le
    reste sans s'arreter."""
    dossier, cle = donnees
    (dossier / "recharges.json").unlink()
    _, copies = _sauver(dossier, cle)
    assert copies == ["tarifs.json"]


def test_deux_sauvegardes_dans_la_meme_minute(donnees):
    dossier, cle = donnees
    premiere, _ = _sauver(dossier, cle)
    seconde, _ = _sauver(dossier, cle)
    assert premiere != seconde


def test_cle_retiree(donnees, tmp_path):
    dossier, _ = donnees
    with pytest.raises(se.SauvegardeImpossible, match="retirée"):
        _sauver(dossier, tmp_path / "cle-debranchee")


def test_refuse_le_dossier_des_donnees(donnees):
    dossier, _ = donnees
    (dossier / "backups").mkdir()
    for mauvais in (dossier, dossier / "backups"):
        with pytest.raises(se.SauvegardeImpossible):
            _sauver(dossier, mauvais)


def test_une_copie_differente_est_denoncee(donnees, monkeypatch):
    dossier, cle = donnees

    def copie_abimee(source, dest):
        Path(dest).write_bytes(b"abime")
    monkeypatch.setattr(se.shutil, "copy2", copie_abimee)
    with pytest.raises(se.SauvegardeImpossible, match="ne correspond pas"):
        _sauver(dossier, cle)


# ---------- sauvegarde a la fermeture (24/09/2026) ----------

def _fermer(dossier, quand=QUAND):
    return se.sauvegarder_a_la_fermeture(
        [dossier / "recharges.json", dossier / "tarifs.json"],
        dossier, "Recharges VE", "v1.31.0", quand)


def test_fermeture_copie_dans_sauvegardes(donnees):
    """La copie va dans <donnees>\\Sauvegardes, bien que ce soit le dossier
    des donnees : c'est voulu, contrairement a la sauvegarde externe."""
    dossier, _ = donnees
    cible = _fermer(dossier)
    assert cible == (dossier / "Sauvegardes"
                     / "Sauvegarde Recharges VE 2026-09-15 14h30")
    for nom in ("recharges.json", "tarifs.json"):
        assert (cible / nom).read_bytes() == (dossier / nom).read_bytes()


def test_fermeture_sans_changement_ne_copie_rien(donnees):
    dossier, _ = donnees
    _fermer(dossier)
    assert _fermer(dossier, datetime(2026, 9, 15, 18, 0)) is None
    assert len(list((dossier / "Sauvegardes").iterdir())) == 1


def test_fermeture_apres_une_saisie_copie_a_nouveau(donnees):
    dossier, _ = donnees
    premiere = _fermer(dossier)
    (dossier / "recharges.json").write_text('{"recharges": [1]}',
                                            encoding="utf-8")
    seconde = _fermer(dossier, datetime(2026, 9, 15, 18, 0))
    assert seconde is not None and seconde != premiere
    assert premiere.is_dir()            # l'ancienne copie est gardee


# ---------- tri des copies de fermeture (28/09/2026) ----------
# Avant, aucune copie n'etait jamais retiree : le dossier grossissait sans
# fin. On garde les 10 plus recentes, puis la derniere de chaque mois ; les
# autres partent a la Corbeille, jamais en suppression definitive.

def _nom(date_heure: str) -> str:
    return f"Sauvegarde Recharges VE {date_heure}"


def test_moins_de_dix_copies_rien_ne_part():
    noms = [_nom(f"2026-09-{j:02d} 10h00") for j in range(1, 11)]
    assert se.copies_a_retirer(noms, "Recharges VE") == []


def test_au_dela_de_dix_on_garde_la_derniere_de_chaque_mois():
    # Juillet : 3 copies, aout : 3 copies, septembre : 10 copies recentes.
    juillet = [_nom(f"2026-07-{j:02d} 10h00") for j in (5, 12, 20)]
    aout = [_nom(f"2026-08-{j:02d} 10h00") for j in (2, 9, 30)]
    septembre = [_nom(f"2026-09-{j:02d} 10h00") for j in range(1, 11)]
    noms = septembre + aout + juillet          # l'ordre recu n'importe pas
    retirees = se.copies_a_retirer(noms, "Recharges VE")
    # La derniere de juillet (20) et d'aout (30) restent : l'etat de fin de
    # mois. Les dix de septembre restent toutes.
    assert sorted(retirees) == sorted(juillet[:2] + aout[:2])


def test_un_mois_deja_present_parmi_les_recentes_ne_garde_rien_de_plus():
    noms = [_nom(f"2026-09-{j:02d} 10h00") for j in range(1, 16)]
    retirees = se.copies_a_retirer(noms, "Recharges VE")
    assert retirees == [_nom(f"2026-09-{j:02d} 10h00") for j in range(1, 6)]


def test_deux_copies_dans_la_meme_minute():
    """« (2) » est la seconde copie de la minute : elle est plus recente."""
    noms = ([_nom("2026-08-30 10h00"), _nom("2026-08-30 10h00 (2)")]
            + [_nom(f"2026-09-{j:02d} 10h00") for j in range(1, 11)])
    assert se.copies_a_retirer(noms, "Recharges VE") == [
        _nom("2026-08-30 10h00")]


def test_un_dossier_etranger_n_est_jamais_touche():
    """Seuls les dossiers crees par l'application sont concernes : un
    dossier range la par l'utilisateur, ou une sauvegarde d'une autre
    application, reste en place."""
    noms = ([_nom(f"2026-09-{j:02d} 10h00") for j in range(1, 11)]
            + ["Mes photos", "Sauvegarde Pecule 2026-01-01 10h00",
               "Sauvegarde Recharges VE 2026-01-01 10h00 copie",
               _nom("2026-01-01 10h00"), _nom("2026-01-02 10h00")])
    assert se.copies_a_retirer(noms, "Recharges VE") == [
        _nom("2026-01-01 10h00")]


def _remplir(dossier, n):
    """n copies de fermeture, une par jour a partir du 1er aout 2026."""
    racine = dossier / "Sauvegardes"
    racine.mkdir(exist_ok=True)
    for i in range(n):
        d = racine / _nom(f"2026-08-{i + 1:02d} 10h00")
        d.mkdir()
        (d / "recharges.json").write_text("{}", encoding="utf-8")
    return racine


def test_la_fermeture_envoie_les_copies_en_trop_a_la_corbeille(donnees):
    dossier, _ = donnees
    racine = _remplir(dossier, 12)
    parties = []

    def corbeille(chemin):
        parties.append(chemin.name)
        import shutil
        shutil.rmtree(chemin)       # la doublure fait la place, rien de plus
        return True

    cible = se.sauvegarder_a_la_fermeture(
        [dossier / "recharges.json", dossier / "tarifs.json"],
        dossier, "Recharges VE", "v2.0.3", datetime(2026, 9, 15, 14, 30),
        corbeille=corbeille)
    # 13 copies : les 10 plus recentes (du 04/08 au 12/08, et la nouvelle)
    # restent. Aout y est deja represente : les trois plus anciennes partent.
    assert parties == [_nom("2026-08-01 10h00"), _nom("2026-08-02 10h00"),
                       _nom("2026-08-03 10h00")]
    assert cible.is_dir()
    assert len([d for d in racine.iterdir()]) == 10


def test_une_corbeille_indisponible_laisse_les_copies(donnees):
    """Si la Corbeille refuse (cle USB, lecteur reseau), la copie reste :
    jamais de suppression definitive, et la fermeture n'echoue pas."""
    dossier, _ = donnees
    racine = _remplir(dossier, 12)
    cible = se.sauvegarder_a_la_fermeture(
        [dossier / "recharges.json", dossier / "tarifs.json"],
        dossier, "Recharges VE", "v2.0.3", datetime(2026, 9, 15, 14, 30),
        corbeille=lambda chemin: False)
    assert cible.is_dir()
    assert len(list(racine.iterdir())) == 13


def test_une_corbeille_qui_plante_ne_bloque_pas_la_fermeture(donnees):
    dossier, _ = donnees
    _remplir(dossier, 12)

    def corbeille(chemin):
        raise OSError("refus")

    cible = se.sauvegarder_a_la_fermeture(
        [dossier / "recharges.json", dossier / "tarifs.json"],
        dossier, "Recharges VE", "v2.0.3", datetime(2026, 9, 15, 14, 30),
        corbeille=corbeille)
    assert cible.is_dir()


def test_la_corbeille_refuse_hors_d_un_disque_local(tmp_path, monkeypatch):
    """Sur une cle USB ou un lecteur reseau, Windows effacerait pour de bon
    au lieu de mettre a la Corbeille : on n'y touche pas."""
    d = tmp_path / "copie"
    d.mkdir()
    monkeypatch.setattr(se, "_disque_local", lambda chemin: False)
    assert se.mettre_a_la_corbeille(d) is False
    assert d.is_dir()


def test_la_fermeture_n_envoie_plus_rien_vers_github():
    """Demande de l'auteur du 24/09/2026 : plus d'envoi GitHub a la fermeture."""
    import inspect

    import fenetre
    source = inspect.getsource(fenetre.FenetrePrincipale.closeEvent)
    assert "sauvegarder_a_la_fermeture" in source
    assert "github" not in source.split('"""')[-1].lower()


def test_aucun_acces_reseau():
    source = (Path(__file__).resolve().parent.parent
              / "sauvegarde_externe.py").read_text(encoding="utf-8")
    for interdit in ("import urllib", "import http", "import socket",
                     "import requests", "import ssl"):
        assert interdit not in source


def test_le_bouton_sauvegarde_les_deux_fichiers(monkeypatch, tmp_path):
    """Le chemin exact du bouton, sans ouvrir de fenetre : la boite de choix
    du dossier et les messages sont remplaces."""
    import fenetre
    import recharges

    dossier = tmp_path / "donnees"
    recharges.ecrire_jeu_demo(dossier)
    cle = tmp_path / "cle"
    cle.mkdir()
    messages = []
    monkeypatch.setattr(fenetre.QFileDialog, "getExistingDirectory",
                        lambda *a: str(cle))
    monkeypatch.setattr(fenetre.QMessageBox, "information",
                        lambda parent, t, m: messages.append(("info", m)))
    monkeypatch.setattr(fenetre.QMessageBox, "warning",
                        lambda parent, t, m: messages.append(("alerte", m)))
    faux = type("Faux", (), {"_destination_sauvegarde": ""})()
    # Les donnees pointent vers le jeu de demonstration le temps du test,
    # puis reviennent la ou elles etaient, quoi qu'il arrive.
    ancien = recharges.dossier_donnees()
    recharges.rediriger_donnees(dossier)
    try:
        fenetre.FenetrePrincipale._sauvegarder_externe(faux)
    finally:
        recharges.rediriger_donnees(ancien)
    assert messages and messages[0][0] == "info", messages
    (sauvegarde,) = list(cle.iterdir())
    assert sorted(p.name for p in sauvegarde.iterdir()) == [
        "LISEZMOI.txt", "recharges.json", "tarifs.json"]
    assert faux._destination_sauvegarde == str(cle)


# ---------- rappel de sauvegarde externe (28/09/2026) ----------
# Le meme dans les trois applications.

def test_rappel_rien_avant_30_jours():
    from datetime import date
    assert se.rappel_sauvegarde_externe(
        "2026-09-01", None, aujourd_hui=date(2026, 9, 30)) is None   # 29 j


def test_rappel_au_bout_de_30_jours():
    from datetime import date
    phrase = se.rappel_sauvegarde_externe(
        "2026-09-01", None, aujourd_hui=date(2026, 10, 1))
    assert "depuis 30 jours" in phrase and "Sauvegarde externe" in phrase


def test_rappel_jamais_faite_apres_30_jours_d_utilisation():
    from datetime import date
    assert se.rappel_sauvegarde_externe(
        None, "2026-09-10", aujourd_hui=date(2026, 9, 30)) is None
    phrase = se.rappel_sauvegarde_externe(
        None, "2026-08-01", aujourd_hui=date(2026, 9, 30))
    assert "jamais" in phrase


def test_rappel_se_tait_sans_repere():
    """Jamais faite, et on ne sait pas depuis quand l'appli sert : rien,
    plutot que de relancer quelqu'un qui vient de l'installer."""
    from datetime import date
    assert se.rappel_sauvegarde_externe(
        None, None, aujourd_hui=date(2030, 1, 1)) is None
    assert se.rappel_sauvegarde_externe(
        "illisible", None, aujourd_hui=date(2030, 1, 1)) is None
