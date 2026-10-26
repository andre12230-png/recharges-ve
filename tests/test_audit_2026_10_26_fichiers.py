"""Audits du 26/10/2026, etape 2 : robustesse des fichiers.

Defauts reproduits ici avant leur correction :

- A9 : sauvegarde externe ; si la cle est retiree pendant la verification
  des empreintes, l'erreur n'etait pas rattrapee (OSError brute au lieu de
  SauvegardeImpossible, dossier non marque « INACHEVÉE »).
- #8 : tarifs.json illisible ; contrairement a recharges.json, il n'etait
  pas repare depuis backups\\ : l'application s'arretait sur une erreur
  alors qu'une copie saine existait.
- #9 : sous Windows, l'ecriture echoue si un autre programme lit le fichier
  a cet instant (antivirus, indexation) ; aucune nouvelle tentative.
- #16 : deux enregistrements dans la meme seconde ; la sauvegarde du second
  etat n'etait pas faite.
- A3 : la page Parametres ecrit les recharges puis les reglages ; une panne
  entre les deux laissait des recharges decalees avec l'ancien reglage, que
  rien ne permettait de remettre d'aplomb.

Toutes les donnees sont inventees, dans un dossier temporaire.

    py -m pytest tests/test_audit_2026_10_26_fichiers.py
"""

import json
import os
import sys
import tempfile
from datetime import datetime
from pathlib import Path

import pytest

os.environ.setdefault("RECHARGES_DATA_DIR",
                      tempfile.mkdtemp(prefix="recharges_audit_1026f_"))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import recharges as r  # noqa: E402
import sauvegarde_externe as se  # noqa: E402

GRILLE = {"id": "t", "nom": "HP/HC", "type": "hp_hc",
          "debut": "2020-01-01", "fin": None,
          "prix_hp": 0.20, "prix_hc": 0.10,
          "abonnement_mensuel": 0.0,
          "plages_hc": [["23:00", "05:00"]]}

ENTETE_CSV = ("NS du chargeur,Heure de debut,Heure de fin,Consommation,"
              "Duree,Cout")
NUIT = ("WB-0001,2026-07-08 00:00:00,2026-07-08 05:30:00,11.000kWh,"
        "05h30min,1.10€")
REGLAGES = {"capacite_batterie": 0.0, "rendement_charge": 0.9}


def ecrire(chemin: Path, contenu) -> None:
    chemin.parent.mkdir(parents=True, exist_ok=True)
    chemin.write_text(json.dumps(contenu, ensure_ascii=False),
                      encoding="utf-8")


@pytest.fixture
def dossier(tmp_path, monkeypatch):
    """Un dossier de donnees neuf, correction d'horloge a -60."""
    ancien = r.BASE
    r.rediriger_donnees(tmp_path)
    monkeypatch.setattr(r, "DERNIERE_RESTAURATION", None)
    monkeypatch.setattr(r, "ECHEC_BACKUP", None, raising=False)
    monkeypatch.setattr(r, "INCIDENT_TARIFS", None)
    ecrire(tmp_path / "tarifs.json", {"correction_csv_minutes": -60,
                                      "tarifs": [GRILLE]})
    r.vider_cache()
    yield tmp_path
    r.rediriger_donnees(ancien)


# ---------- A9 : verification de la sauvegarde externe ----------

def test_cle_retiree_pendant_la_verification(tmp_path, monkeypatch):
    donnees = tmp_path / "donnees"
    donnees.mkdir()
    (donnees / "recharges.json").write_text('{"recharges": []}',
                                           encoding="utf-8")
    cle = tmp_path / "cle"
    cle.mkdir()

    def empreinte_impossible(chemin):
        raise OSError(5, "Erreur d'entrée/sortie", str(chemin))
    monkeypatch.setattr(se, "_empreinte", empreinte_impossible)
    with pytest.raises(se.SauvegardeImpossible):
        se.sauvegarder([donnees / "recharges.json"], cle, donnees,
                       "Recharges VE", "v2.2.22", datetime(2026, 10, 26, 12))
    noms = [p.name for p in cle.iterdir()]
    assert len(noms) == 1 and "INACHEVÉE" in noms[0]


# ---------- #8 : tarifs.json illisible ----------

def test_tarifs_illisible_repare_depuis_les_sauvegardes(dossier):
    ecrire(dossier / "backups" / "tarifs_20261001_120000.json",
           {"correction_csv_minutes": 0, "tarifs": [GRILLE]})
    (dossier / "tarifs.json").write_text('{"tarifs": [', encoding="utf-8")

    tarifs = r.charger_tarifs()

    assert [t["id"] for t in tarifs] == ["t"]
    assert r.INCIDENT_TARIFS["cause"] == "illisible"
    assert r.INCIDENT_TARIFS["copie"] == "tarifs_20261001_120000.json"
    # Le fichier abime est garde a part, pour y repecher un prix.
    mis_de_cote = r.INCIDENT_TARIFS["mis_de_cote"]
    assert mis_de_cote.startswith("tarifs_illisible_")
    assert (dossier / mis_de_cote).read_text(encoding="utf-8") == '{"tarifs": ['
    # Et tarifs.json est de nouveau lisible pour la suite.
    assert json.loads((dossier / "tarifs.json").read_text("utf-8"))["tarifs"]


def test_tarifs_illisible_sans_copie_reste_une_erreur_claire(dossier):
    (dossier / "tarifs.json").write_text('{"tarifs": [', encoding="utf-8")
    with pytest.raises(ValueError, match="tarifs.json est invalide"):
        r.charger_tarifs()


# ---------- #9 : fichier tenu un instant par un autre programme ----------

def test_ecriture_reessayee_si_le_fichier_est_occupe(dossier, monkeypatch):
    vrai_replace = os.replace
    essais = []

    def replace_occupe(source, cible):
        essais.append(1)
        if len(essais) <= 2:
            raise PermissionError(13, "Accès refusé", str(cible))
        vrai_replace(source, cible)
    monkeypatch.setattr(r.os, "replace", replace_occupe)
    monkeypatch.setattr(r.time, "sleep", lambda s: None)

    r.sauvegarder_donnees({"recharges": []})

    assert len(essais) == 3
    assert json.loads((dossier / "recharges.json").read_text("utf-8")) == {
        "recharges": []}


def test_fichier_toujours_occupe_finit_par_une_erreur(dossier, monkeypatch):
    def toujours_occupe(source, cible):
        raise PermissionError(13, "Accès refusé", str(cible))
    monkeypatch.setattr(r.os, "replace", toujours_occupe)
    monkeypatch.setattr(r.time, "sleep", lambda s: None)
    with pytest.raises(PermissionError):
        r.sauvegarder_donnees({"recharges": []})
    # Aucun fichier temporaire laisse derriere.
    assert not list(dossier.glob("*.tmp"))


# ---------- #16 : deux enregistrements dans la meme seconde ----------

class SecondeFigee(datetime):
    @classmethod
    def now(cls, tz=None):
        return cls(2026, 10, 26, 12, 0, 0)


def test_deux_sauvegardes_dans_la_meme_seconde(dossier, monkeypatch):
    monkeypatch.setattr(r, "datetime", SecondeFigee)
    for n in (1, 2, 3):
        r.sauvegarder_donnees({"recharges": [], "n": n})
    copies = sorted((dossier / "backups").glob("recharges_2*.json"))
    contenus = [json.loads(c.read_text("utf-8"))["n"] for c in copies]
    assert contenus == [1, 2]


# ---------- A3 : reglages et recharges ecrits ensemble ----------

def importer_nuit(dossier: Path) -> None:
    chemin = dossier / "borne.csv"
    chemin.write_text(ENTETE_CSV + "\n" + NUIT, encoding="utf-8")
    r.importer_csv_maison(chemin)


def test_panne_des_reglages_remet_les_recharges_en_place(dossier,
                                                         monkeypatch):
    importer_nuit(dossier)
    assert r.charger_donnees()["recharges"][0]["date"] == "2026-07-07T23:00"

    def panne(modifs):
        raise OSError(28, "Disque plein", "tarifs.json")
    monkeypatch.setattr(r, "enregistrer_config", panne)
    with pytest.raises(OSError):
        r.enregistrer_reglages_borne(dict(REGLAGES, correction_csv_minutes=0))

    r.vider_cache()
    # Recharges et reglage disent toujours la meme chose : -60.
    assert r.charger_donnees()["recharges"][0]["date"] == "2026-07-07T23:00"
    assert r.charger_config()["correction_csv_minutes"] == -60


def test_panne_du_recalcul_laisse_l_ancienne_puissance(dossier, monkeypatch):
    """Si le recalcul pour une nouvelle puissance echoue, la puissance ne
    doit pas etre enregistree : sinon, la reenregistrer ne recalculerait
    plus rien (aucun changement vu)."""
    importer_nuit(dossier)

    def panne(data):
        raise OSError(28, "Disque plein", "recharges.json")
    monkeypatch.setattr(r, "sauvegarder_donnees", panne)
    with pytest.raises(OSError):
        r.enregistrer_reglages_borne(dict(REGLAGES, correction_csv_minutes=-60,
                                          puissance_borne_kw=7.0))
    assert r.charger_config()["puissance_borne_kw"] == 0


# ---------- #12 : la rotation de backups\ passe par la Corbeille ----------

def preparer_quinze_sauvegardes(dossier: Path) -> None:
    """15 sauvegardes anciennes (le maximum gardé) et un recharges.json :
    le prochain enregistrement en fait une 16e, la plus vieille doit
    partir."""
    for n in range(15):
        ecrire(dossier / "backups" / f"recharges_20260101_0000{n:02d}.json",
               {"recharges": []})
    ecrire(dossier / "recharges.json", {"recharges": []})
    r.vider_cache()


def test_la_plus_vieille_sauvegarde_part_a_la_corbeille(dossier,
                                                        monkeypatch):
    """Décision d'André du 26/10/2026 : jamais de suppression définitive
    quand la Corbeille est disponible."""
    corbeille = dossier / "corbeille_simulee"
    corbeille.mkdir()

    def a_la_corbeille(chemin):
        Path(chemin).rename(corbeille / Path(chemin).name)
        return True
    monkeypatch.setattr(r, "mettre_a_la_corbeille", a_la_corbeille)
    preparer_quinze_sauvegardes(dossier)

    r.sauvegarder_donnees({"recharges": []})

    assert [p.name for p in corbeille.iterdir()] == [
        "recharges_20260101_000000.json"]
    assert len(list((dossier / "backups").glob("recharges_2*.json"))) == 15


def test_sans_corbeille_la_rotation_continue(dossier, monkeypatch):
    """Données sur une clé USB ou un disque réseau : Windows n'a pas de
    Corbeille. La plus vieille sauvegarde est alors supprimée comme avant,
    sinon backups\\ grossirait sans fin."""
    monkeypatch.setattr(r, "mettre_a_la_corbeille", lambda chemin: False)
    preparer_quinze_sauvegardes(dossier)

    r.sauvegarder_donnees({"recharges": []})

    restantes = sorted((dossier / "backups").glob("recharges_2*.json"))
    assert len(restantes) == 15
    assert restantes[0].name == "recharges_20260101_000001.json"


def test_sans_panne_les_reglages_passent_toujours(dossier):
    importer_nuit(dossier)
    bilan = r.enregistrer_reglages_borne(
        dict(REGLAGES, correction_csv_minutes=0, puissance_borne_kw=7.0))
    assert bilan["decalees"] == 1 and bilan["recalculees"] == 1
    assert r.charger_donnees()["recharges"][0]["date"] == "2026-07-08T00:00"
    config = r.charger_config()
    assert config["correction_csv_minutes"] == 0
    assert config["puissance_borne_kw"] == 7.0
