"""Audits du 26/10/2026, etape 5 : les petits soins retenus le 27/10/2026.

- #23 : l'autotest laissait ses dossiers dans %TEMP% (autotest_*,
  autotest_demo_*). Avec --donnees-reelles, l'export Excel et le PDF de
  30 vraies recharges y restaient : des donnees personnelles hors de leur
  dossier, sans que personne le sache.

- #22 et #26 : les erreurs imprevues n'etaient ecrites que par print(), et
  aucun sys.excepthook n'etait pose : dans l'exe, sans console, elles
  disparaissaient sans laisser de trace. Desormais : un journal erreurs.log
  dans le dossier des donnees, et un message en clair a l'ecran.

- #20 : une ligne CSV a l'energie negative etait comptee parmi les
  « branchements sans recharge ecartes » : une donnee fausse passait pour
  un cas normal. Elle compte desormais comme ligne non reconnue, annoncee
  en orange.

Donnees inventees, dans un dossier temporaire.

    py -m pytest tests/test_audit_2026_10_26_soins.py
"""

from __future__ import annotations

import sys
import tempfile

import pytest

import fenetre as module_fenetre
import recharges


@pytest.fixture
def donnees_rendues():
    """L'autotest redirige les donnees : on les remet ou elles etaient."""
    ancien = recharges.dossier_donnees()
    yield
    recharges.rediriger_donnees(ancien)


@pytest.fixture
def temp_isole(tmp_path, monkeypatch):
    """Un %TEMP% vide rien que pour ce test : on y voit ce qui reste."""
    temp = tmp_path / "temp"
    temp.mkdir()
    monkeypatch.setattr(tempfile, "tempdir", str(temp))
    return temp


# ---------- #23 : l'autotest ne laisse rien dans %TEMP% ----------

def test_23_autotest_demo_ne_laisse_rien(qapp, donnees_rendues, temp_isole,
                                          tmp_path):
    rapport = tmp_path / "rapport.txt"
    assert module_fenetre.autotest(str(rapport)) == 0
    restes = [p.name for p in temp_isole.iterdir()
              if p.name.startswith("autotest")]
    assert restes == []


def test_23_autotest_donnees_reelles_n_y_laisse_aucun_export(
        qapp, donnees_rendues, temp_isole, tmp_path, monkeypatch):
    # « Vraies » donnees : un jeu invente, dans son propre dossier.
    donnees = tmp_path / "donnees"
    donnees.mkdir()
    recharges.ecrire_jeu_demo(donnees)
    recharges.rediriger_donnees(donnees)
    monkeypatch.setattr(sys, "argv", ["Recharges-VE.exe", "--autotest",
                                      "x", "--donnees-reelles"])
    rapport = tmp_path / "rapport.txt"
    assert module_fenetre.autotest(str(rapport)) == 0
    assert "données        : les vôtres" in rapport.read_text(encoding="utf-8")
    exports = [p for p in temp_isole.rglob("*")
               if p.suffix in (".xlsx", ".pdf")]
    assert exports == []
    # Les donnees elles-memes ne sont jamais effacees.
    assert (donnees / "recharges.json").is_file()


# ---------- #22 et #26 : le journal des erreurs ----------

def test_22_le_journal_garde_chaque_erreur_datee(tmp_path):
    import journal_erreurs
    journal_erreurs.ecrire(tmp_path, "[backup] impossible : disque plein")
    journal_erreurs.ecrire(tmp_path, "[tarifs] seconde erreur")
    lignes = (tmp_path / "erreurs.log").read_text(
        encoding="utf-8").splitlines()
    assert len(lignes) == 2
    assert lignes[0].endswith("[backup] impossible : disque plein")
    assert lignes[0][:2].isdigit()          # commence par la date
    assert "[tarifs] seconde erreur" in lignes[1]


def test_22_le_journal_ne_grossit_pas_sans_fin(tmp_path, monkeypatch):
    import journal_erreurs
    monkeypatch.setattr(journal_erreurs, "TAILLE_MAX", 100)
    for i in range(20):
        journal_erreurs.ecrire(tmp_path, f"erreur numero {i}")
    assert (tmp_path / "erreurs.log").stat().st_size <= 200
    assert (tmp_path / "erreurs.log.ancien").is_file()


def test_22_un_journal_impossible_a_ecrire_ne_plante_pas(tmp_path):
    import journal_erreurs
    # Un dossier qui n'existe pas : rien n'est ecrit, et rien ne casse.
    journal_erreurs.ecrire(tmp_path / "absent", "erreur")
    assert not (tmp_path / "absent").exists()


def test_22_les_messages_du_moteur_vont_au_journal(donnees_rendues,
                                                   tmp_path, capsys):
    recharges.rediriger_donnees(tmp_path)
    recharges.signaler("[backup] impossible : essai")
    assert "[backup] impossible : essai" in capsys.readouterr().out
    assert "[backup] impossible : essai" in (
        tmp_path / "erreurs.log").read_text(encoding="utf-8")


def test_26_une_erreur_imprevue_est_notee_et_dite(qapp, donnees_rendues,
                                                   tmp_path, monkeypatch):
    recharges.rediriger_donnees(tmp_path)
    messages = []
    monkeypatch.setattr(module_fenetre.QMessageBox, "warning",
                        lambda *args: messages.append(args[2]))
    try:
        raise ZeroDivisionError("division by zero")
    except ZeroDivisionError:
        module_fenetre.erreur_imprevue(*sys.exc_info())
    journal = (tmp_path / "erreurs.log").read_text(encoding="utf-8")
    assert "ZeroDivisionError" in journal and "Traceback" in journal
    assert len(messages) == 1
    assert "erreurs.log" in messages[0]
    assert "imprévue" in messages[0]


def test_26_main_pose_le_journal_des_erreurs(monkeypatch):
    monkeypatch.setattr(sys, "excepthook", sys.__excepthook__)
    module_fenetre.installer_journal_erreurs()
    assert sys.excepthook is module_fenetre.erreur_imprevue


# ---------- #20 : energie negative = ligne non reconnue ----------

def test_20_energie_negative_signalee_et_non_enregistree(donnees_rendues,
                                                         tmp_path):
    import json
    (tmp_path / "tarifs.json").write_text(json.dumps({
        "tarifs": [{"id": "t", "nom": "Prix unique", "type": "simple",
                    "debut": "2020-01-01", "fin": None, "prix_kwh": 0.20,
                    "abonnement_mensuel": 0.0}],
        "correction_csv_minutes": 0}), encoding="utf-8")
    recharges.rediriger_donnees(tmp_path)
    chemin = tmp_path / "export.csv"
    chemin.write_bytes("\r\n".join([
        "Chargeur;Début;Fin;Énergie;Durée;Coût €",
        "BORNE1;2026-03-01 22:00:00;2026-03-02 02:00:00;10.0;4:00;2.00",
        "BORNE1;2026-03-03 22:00:00;2026-03-04 02:00:00;-3.0;4:00;0.00",
    ]).encode("utf-8"))
    bilan = recharges.importer_csv_maison(chemin)
    assert bilan["ajoutes"] == 1
    assert bilan["parasites"] == 0
    assert bilan["non_reconnues"] == 1


# ---------- #24 : l'outil de construction fige lui aussi ----------

def test_24_pyinstaller_fige_dans_requirements_lock():
    """Sans lui, « reconstruire l'exe a l'identique » restait faux : une
    autre version de PyInstaller change ce qui entre dans l'exe."""
    from pathlib import Path
    texte = (Path(recharges.__file__).parent / "requirements.lock").read_text(
        encoding="utf-8")
    lignes = {ligne.split("==")[0].lower() for ligne in texte.splitlines()
              if "==" in ligne and not ligne.startswith("#")}
    for outil in ("pyinstaller", "pyinstaller-hooks-contrib", "altgraph",
                  "pefile", "pywin32-ctypes"):
        assert outil in lignes, outil
