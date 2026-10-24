"""Lot 1 de l'audit du 14/10/2026 (v2.2.1) : la protection des donnees.

Chaque test reproduit un defaut releve par l'audit, et doit rester vert
apres sa correction :

A01. recharges.json disparu alors que des sauvegardes existent :
     l'application repartait d'un historique vide, sans rien dire ;
A02. la copie de l'etat actuel ratait, et la restauration remplacait
     quand meme les donnees (on ne pouvait plus revenir en arriere) ;
     une sauvegarde ratee lors d'une ecriture ordinaire passait inapercue ;
A03. un fichier JSON lisible mais de mauvaise forme ({} ou
     {"recharges": {}}) passait pour une sauvegarde valide ;
A05. la sauvegarde Git emportait aussi des fichiers etrangers aux donnees,
     deja prepares dans le depot.

Toutes les donnees sont inventees, dans un dossier temporaire.

    py -m pytest tests/test_audit_2026_10_14.py
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

os.environ.setdefault("RECHARGES_DATA_DIR",
                      tempfile.mkdtemp(prefix="recharges_audit_1014_"))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import recharges as r  # noqa: E402

UNE_RECHARGE = {"recharges": [{"id": "a", "date": "2026-03-01T10:00",
                               "lieu": "exterieur", "kwh": 10.0,
                               "cout_eur": 4.0}]}


def ecrire(chemin: Path, contenu) -> None:
    chemin.parent.mkdir(parents=True, exist_ok=True)
    chemin.write_text(json.dumps(contenu, ensure_ascii=False),
                      encoding="utf-8")


@pytest.fixture
def dossier(tmp_path, monkeypatch):
    """Un dossier de donnees neuf, rendu a la fin du test."""
    ancien = r.BASE
    r.rediriger_donnees(tmp_path)
    monkeypatch.setattr(r, "DERNIERE_RESTAURATION", None)
    monkeypatch.setattr(r, "ECHEC_BACKUP", None, raising=False)
    ecrire(tmp_path / "tarifs.json", {"tarifs": []})
    yield tmp_path
    r.rediriger_donnees(ancien)


# ---------- A01 : fichier principal disparu ----------

def test_a01_fichier_disparu_retrouve_la_sauvegarde(dossier):
    ecrire(dossier / "backups" / "recharges_20260301_100000.json",
           UNE_RECHARGE)
    donnees = r.charger_donnees()
    assert len(donnees["recharges"]) == 1
    # L'utilisateur est prevenu, avec la cause exacte.
    assert r.DERNIERE_RESTAURATION is not None
    assert r.DERNIERE_RESTAURATION["cause"] == "absent"


def test_a01_premier_lancement_reste_vide_et_silencieux(dossier):
    """Aucune sauvegarde : c'est un vrai premier lancement."""
    assert r.charger_donnees() == {"recharges": []}
    assert r.DERNIERE_RESTAURATION is None


def test_a01_sauvegardes_toutes_invalides_reste_vide(dossier):
    ecrire(dossier / "backups" / "recharges_20260301_100000.json", {})
    assert r.charger_donnees() == {"recharges": []}
    assert r.DERNIERE_RESTAURATION is None


# ---------- A02 : restauration sans copie de l'etat actuel ----------

def test_a02_restauration_refusee_si_etat_actuel_non_preserve(
        dossier, monkeypatch):
    ecrire(dossier / "recharges.json", UNE_RECHARGE)
    vide = dossier / "backups" / "recharges_20260101_000000.json"
    ecrire(vide, {"recharges": []})
    r.vider_cache()

    def copie_impossible(*_args, **_kwargs):
        raise OSError(28, "No space left on device")

    monkeypatch.setattr(r.shutil, "copy2", copie_impossible)
    with pytest.raises(ValueError, match="mises de côté"):
        r.restaurer_backup(vide)
    # Les donnees actuelles sont intactes.
    contenu = json.loads((dossier / "recharges.json").read_text("utf-8"))
    assert len(contenu["recharges"]) == 1


def test_a02_sauvegarde_ratee_d_une_ecriture_ordinaire_est_signalee(
        dossier, monkeypatch):
    ecrire(dossier / "recharges.json", UNE_RECHARGE)
    r.vider_cache()

    def copie_impossible(*_args, **_kwargs):
        raise OSError(13, "Permission denied")

    monkeypatch.setattr(r.shutil, "copy2", copie_impossible)
    r.sauvegarder_donnees({"recharges": []})
    # L'ecriture elle-meme a eu lieu, mais l'echec de la copie est garde
    # pour que la fenetre le dise.
    assert r.ECHEC_BACKUP


# ---------- A03 : structure des fichiers JSON ----------

@pytest.mark.parametrize("mauvais", [
    {},
    {"recharges": {}},
    {"recharges": ["texte"]},
    {"recharges": [{"date": "2026-03-01T10:00", "kwh": "beaucoup"}]},
    {"recharges": [], "releves_km": "aucun"},
    [],
])
def test_a03_restauration_refuse_une_mauvaise_structure(dossier, mauvais):
    ecrire(dossier / "recharges.json", UNE_RECHARGE)
    r.vider_cache()
    autre = dossier / "backups" / "recharges_20260101_000000.json"
    ecrire(autre, mauvais)
    with pytest.raises(ValueError):
        r.restaurer_backup(autre)
    contenu = json.loads((dossier / "recharges.json").read_text("utf-8"))
    assert len(contenu["recharges"]) == 1


def test_a03_reparation_ecarte_une_sauvegarde_de_mauvaise_forme(dossier):
    """{} plus recent qu'une sauvegarde saine : la saine doit l'emporter."""
    saine = dossier / "backups" / "recharges_20260301_100000.json"
    ecrire(saine, UNE_RECHARGE)
    vide = dossier / "backups" / "recharges_20260302_100000.json"
    ecrire(vide, {})
    os.utime(saine, (1_700_000_000, 1_700_000_000))
    (dossier / "recharges.json").write_text("{ abime", encoding="utf-8")
    donnees = r.charger_donnees()
    assert len(donnees["recharges"]) == 1


def test_a03_fichier_principal_de_mauvaise_forme_est_repare(dossier):
    ecrire(dossier / "backups" / "recharges_20260301_100000.json",
           UNE_RECHARGE)
    ecrire(dossier / "recharges.json", {"recharges": {}})
    donnees = r.charger_donnees()
    assert len(donnees["recharges"]) == 1
    assert r.DERNIERE_RESTAURATION is not None


def test_a03_anciennes_donnees_compatibles_acceptees(dossier):
    """Les anciennes formes restent valides : pas de releves_km, champs
    facultatifs absents, nombres entiers, cout vide."""
    ancienne = {"recharges": [
        {"id": "a", "date": "2025-01-01T10:00", "lieu": "maison", "kwh": 10,
         "cout_eur": None},
        {"id": "b", "date": "2025-01-02T10:00", "lieu": "exterieur",
         "kwh": 7.5, "cout_eur": 3, "operateur": "Borne"}]}
    assert r.structure_recharges_valide(ancienne)
    assert r.structure_recharges_valide(
        {"recharges": [], "releves_km": [{"date": "2025-01-01",
                                          "km": 1000}]})


# ---------- A05 : la sauvegarde Git ne prend que les donnees ----------

@pytest.mark.skipif(not shutil.which("git"), reason="git n'est pas installe")
def test_a05_sauvegarde_git_n_emporte_pas_les_autres_fichiers(tmp_path):
    depot = tmp_path / "usage"
    distant = tmp_path / "distant.git"
    depot.mkdir()

    def git(*args, cwd=depot):
        return subprocess.run(["git", *args], cwd=str(cwd),
                              capture_output=True, text=True)

    git("init", "--bare", str(distant), cwd=tmp_path)
    ecrire(depot / "recharges.json", {"recharges": []})
    ecrire(depot / "tarifs.json", {"tarifs": []})
    git("init")
    git("config", "user.name", "Test")
    git("config", "user.email", "test@example.invalid")
    git("add", "-A")
    git("commit", "-m", "depart")
    git("remote", "add", "origin", str(distant))
    branche = git("rev-parse", "--abbrev-ref", "HEAD").stdout.strip()
    git("push", "-u", "origin", branche)

    # Un fichier etranger, deja prepare (indexe) avant la sauvegarde.
    (depot / "autre.txt").write_text("brouillon", encoding="utf-8")
    git("add", "autre.txt")

    ancien = r.BASE
    r.rediriger_donnees(depot)
    try:
        ecrire(depot / "recharges.json", UNE_RECHARGE)
        r.vider_cache()
        ok, message = r.synchroniser_github()
    finally:
        r.rediriger_donnees(ancien)
    assert ok, message
    fichiers = git("show", "--name-only", "--format=", "HEAD").stdout
    assert "recharges.json" in fichiers
    assert "autre.txt" not in fichiers
    # Le fichier etranger reste prepare, comme l'utilisateur l'avait laisse.
    assert "autre.txt" in git("diff", "--cached", "--name-only").stdout


# ======================================================================
# Lot 2 : imports, exports et construction
# ======================================================================

ENTETE_CSV = ("NS du chargeur,Heure de debut,Heure de fin,Consommation,"
              "Duree,Cout")


def ecrire_csv(dossier: Path, lignes: list[str], nom="borne.csv") -> Path:
    chemin = dossier / nom
    chemin.write_text(chr(13).join([ENTETE_CSV] + lignes), encoding="utf-8")
    return chemin


@pytest.fixture
def dossier_import(dossier):
    """Le dossier de donnees, avec une grille a prix unique."""
    ecrire(dossier / "tarifs.json", {
        "correction_csv_minutes": 0,
        "tarifs": [{"id": "t", "nom": "Prix unique", "type": "simple",
                    "debut": "2020-01-01", "fin": None, "prix_kwh": 0.20,
                    "abonnement_mensuel": 0.0}]})
    r.vider_cache()
    return dossier


# ---------- A04 : deux sessions distinctes du meme CSV ----------

def test_a04_deux_sessions_distinctes_meme_energie(dossier_import):
    chemin = ecrire_csv(dossier_import, [
        "WB-0001,2026-03-02 10:00:00,2026-03-02 10:15:00,1.000kWh,00h15min,"
        "0.20€",
        "WB-0001,2026-03-02 11:00:00,2026-03-02 11:15:00,1.000kWh,00h15min,"
        "0.20€",
    ])
    bilan = r.importer_csv_maison(chemin)
    assert bilan["ajoutes"] == 2
    assert len(r.charger_donnees()["recharges"]) == 2


def test_a04_reimporter_le_meme_csv_ne_double_rien(dossier_import):
    lignes = ["WB-0001,2026-03-02 10:00:00,2026-03-02 10:15:00,1.000kWh,"
              "00h15min,0.20€",
              "WB-0001,2026-03-02 11:00:00,2026-03-02 11:15:00,1.000kWh,"
              "00h15min,0.20€"]
    r.importer_csv_maison(ecrire_csv(dossier_import, lignes))
    bilan = r.importer_csv_maison(ecrire_csv(dossier_import, lignes))
    assert bilan["ajoutes"] == 0 and bilan["doublons"] == 2


def test_a04_correction_d_horloge_changee_reste_un_doublon(dossier_import):
    """La meme session, decalee de quelques minutes parce que la correction
    d'horloge a change entre deux imports : toujours un doublon."""
    ligne = ("WB-0001,2026-03-02 22:00:00,2026-03-03 04:00:00,30.000kWh,"
             "06h00min,6.00€")
    r.importer_csv_maison(ecrire_csv(dossier_import, [ligne]))
    tarifs = json.loads((dossier_import / "tarifs.json").read_text("utf-8"))
    tarifs["correction_csv_minutes"] = 7
    ecrire(dossier_import / "tarifs.json", tarifs)
    bilan = r.importer_csv_maison(ecrire_csv(dossier_import, [ligne]))
    assert bilan["doublons"] == 1 and bilan["ajoutes"] == 0


def test_a04_deux_bornes_au_meme_moment(dossier_import):
    """Deux chargeurs differents : deux sessions, meme a la meme heure."""
    chemin = ecrire_csv(dossier_import, [
        "WB-0001,2026-03-02 22:00:00,2026-03-03 04:00:00,30.000kWh,06h00min,"
        "6.00€",
        "WB-0002,2026-03-02 22:00:00,2026-03-03 04:00:00,30.000kWh,06h00min,"
        "6.00€",
    ])
    assert r.importer_csv_maison(chemin)["ajoutes"] == 2


def test_a04_saisie_manuelle_toujours_remplacee(dossier_import):
    """La tolerance qui rapproche une saisie manuelle du CSV est gardee."""
    ecrire(dossier_import / "recharges.json", {"recharges": [
        {"id": "m", "date": "2026-03-02T22:30", "fin": "2026-03-03T04:00",
         "lieu": "maison", "kwh": 30.0, "cout_eur": 6.0}]})
    r.vider_cache()
    chemin = ecrire_csv(dossier_import, [
        "WB-0001,2026-03-02 22:00:00,2026-03-03 04:00:00,30.000kWh,06h00min,"
        "6.00€"])
    bilan = r.importer_csv_maison(chemin)
    assert bilan["remplaces"] == 1 and bilan["ajoutes"] == 0


# ---------- A06 : textes de la feuille Synthese ----------

def test_a06_excel_synthese_garde_les_noms_comme_texte(tmp_path):
    import openpyxl

    import export
    recharges = [
        {"id": "a", "date": "2026-03-02T22:00", "fin": "2026-03-03T04:00",
         "lieu": "maison", "kwh": 30.0, "cout_eur": 6.0, "prix_kwh": 0.2,
         "tarif_nom": "=1+1", "kwh_hp": 0.0, "kwh_hc": 30.0},
        {"id": "b", "date": "2026-03-05T10:00", "lieu": "exterieur",
         "kwh": 20.0, "cout_eur": 9.0, "prix_kwh": 0.45,
         "operateur": "=HYPERLINK(\"x\")"},
    ]
    chemin = export.exporter_excel(recharges, tmp_path / "e.xlsx",
                                   periode_label="=2+2")
    feuille = openpyxl.load_workbook(chemin)["Synthèse"]
    for ligne in feuille.iter_rows():
        for cellule in ligne:
            if isinstance(cellule.value, str) and cellule.value.startswith(
                    "="):
                assert cellule.data_type == "s", cellule.coordinate


# ---------- A07 : noms qui font echouer le PDF ----------

@pytest.mark.parametrize("nom", ["Borne <b>", "<i>Rapide</i>", "A & B",
                                 "Prix < 1 €"])
def test_a07_pdf_accepte_tous_les_noms(tmp_path, nom):
    import export
    recharges = [
        {"id": "a", "date": "2026-03-02T22:00", "fin": "2026-03-03T04:00",
         "lieu": "maison", "kwh": 30.0, "cout_eur": 6.0, "prix_kwh": 0.2,
         "tarif_nom": nom, "kwh_hp": 0.0, "kwh_hc": 30.0},
        {"id": "b", "date": "2026-03-05T10:00", "lieu": "exterieur",
         "kwh": 20.0, "cout_eur": 9.0, "prix_kwh": 0.45, "operateur": nom},
    ]
    chemin = export.exporter_pdf(recharges, tmp_path / "e.pdf",
                                 periode_label=nom)
    assert chemin.stat().st_size > 0


def test_a07_pdf_garde_le_texte_tel_quel():
    """Un nom avec des balises s'affiche tel quel, sans mise en forme."""
    import export
    assert export._texte_pdf("<i>Rapide</i> & co") == (
        "&lt;i&gt;Rapide&lt;/i&gt; &amp; co")


# ---------- A13 : build.bat et ses faux succes ----------

def test_a13_build_bat_verifie_pyinstaller_et_l_autotest():
    texte = (Path(__file__).resolve().parent.parent / "build.bat").read_text(
        encoding="utf-8", errors="replace").lower()
    apres_pyinstaller = texte.split("app.py", 1)[1]
    # Le code de retour de PyInstaller est lu avant tout « Termine ».
    assert apres_pyinstaller.index("errorlevel") < apres_pyinstaller.index(
        "termine")
    # L'ancien exe est retire avant la construction : sa seule presence ne
    # peut plus faire croire a un succes.
    avant = texte.split("py -m pyinstaller", 1)[0]
    assert "dist\\recharges-ve" in avant and ("rmdir" in avant
                                               or "rd " in avant)
    # Le resultat de l'autotest est controle, lui aussi.
    autotest = apres_pyinstaller.split("--autotest", 1)[1]
    assert "errorlevel" in autotest
