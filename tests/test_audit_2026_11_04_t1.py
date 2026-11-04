"""Audit indépendant du 04/11/2026, T1 : l'import d'un CSV de borne ne
remplace plus une recharge saisie à la main sur un simple rapprochement.

Avant : une saisie de 10 h à 10 h 15 (1,00 kWh) était remplacée par une
AUTRE session du CSV, de 11 h 30 à 11 h 45 (1,05 kWh) : début à moins de
2 h et énergie dans la tolérance suffisaient, sans recouvrement.

Désormais :
- cas sûr (une seule saisie qui recouvre la session, énergie dans la
  tolérance) : remplacée automatiquement, comme avant ;
- cas douteux (proche sans recouvrement, plusieurs saisies, ou recouvrement
  avec une énergie trop différente) : rien n'est décidé seul. La fonction
  `decider` reçoit ces cas AVANT toute écriture ; sans elle, les deux
  recharges sont gardées et le bilan les liste ;
- annuler (decider rend None) : rien n'est écrit.

Données inventées, dans un dossier temporaire.

    py -m pytest tests/test_audit_2026_11_04_t1.py
"""

import json
import os
import sys
import tempfile
from datetime import datetime
from pathlib import Path

import pytest

os.environ.setdefault("RECHARGES_DATA_DIR",
                      tempfile.mkdtemp(prefix="recharges_t1_1104_"))
RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))

import recharges as r  # noqa: E402

PRIX_UNIQUE = {"id": "t_simple", "nom": "Prix unique", "type": "simple",
               "debut": "2020-01-01", "fin": None, "prix_kwh": 0.20,
               "abonnement_mensuel": 0.0}


@pytest.fixture
def dossier(tmp_path, monkeypatch):
    """Un dossier de données neuf avec un tarif à prix unique."""
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


def _maison():
    return sorted((x["date"], x["kwh"]) for x in r.charger_donnees()["recharges"]
                  if x.get("lieu") == "maison")


def _saisie(debut_h, debut_m, fin_h, fin_m, kwh):
    r.ajouter_recharge_maison(datetime(2026, 3, 1, debut_h, debut_m),
                              datetime(2026, 3, 1, fin_h, fin_m), kwh)
    return next(x["id"] for x in r.charger_donnees()["recharges"]
                if x["date"] == f"2026-03-01T{debut_h:02d}:{debut_m:02d}")


CSV_AUTRE_SESSION = ["BORNE1;2026-03-01 11:30:00;2026-03-01 11:45:00;"
                     "1.05;0:15;0.21"]


class Espion:
    """Fonction `decider` qui répond ce qu'on lui dit et retient les cas."""

    def __init__(self, reponses):
        self.reponses = reponses
        self.cas = None

    def __call__(self, cas):
        self.cas = cas
        return self.reponses(cas) if callable(self.reponses) else self.reponses


# ---------- Le scénario de l'audit ----------

def test_une_autre_session_ne_remplace_plus_la_saisie(dossier):
    _saisie(10, 0, 10, 15, 1.0)
    bilan = r.importer_csv_maison(_csv(dossier, CSV_AUTRE_SESSION))
    # Sans réponse : les deux sont gardées, et le bilan le signale.
    assert bilan["remplaces"] == 0 and bilan["ajoutes"] == 1
    assert _maison() == [("2026-03-01T10:00", 1.0), ("2026-03-01T11:30", 1.05)]
    assert len(bilan["a_verifier"]) == 1


def test_le_cas_douteux_est_presente_avant_d_ecrire(dossier):
    id_saisie = _saisie(10, 0, 10, 15, 1.0)
    espion = Espion(lambda cas: [r.GARDER_LES_DEUX] * len(cas))
    r.importer_csv_maison(_csv(dossier, CSV_AUTRE_SESSION), decider=espion)
    assert len(espion.cas) == 1
    cas = espion.cas[0]
    assert cas["fichier"]["date"] == "2026-03-01T11:30"
    assert cas["fichier"]["kwh"] == 1.05
    assert [s["id"] for s in cas["saisies"]] == [id_saisie]


def test_choisir_remplacer(dossier):
    id_saisie = _saisie(10, 0, 10, 15, 1.0)
    bilan = r.importer_csv_maison(_csv(dossier, CSV_AUTRE_SESSION),
                                  decider=Espion([id_saisie]))
    assert bilan["remplaces"] == 1 and bilan["ajoutes"] == 0
    assert _maison() == [("2026-03-01T11:30", 1.05)]
    # L'identifiant de la saisie est conservé.
    assert [x["id"] for x in r.charger_donnees()["recharges"]] == [id_saisie]


def test_choisir_ignorer_la_ligne_du_fichier(dossier):
    _saisie(10, 0, 10, 15, 1.0)
    bilan = r.importer_csv_maison(_csv(dossier, CSV_AUTRE_SESSION),
                                  decider=Espion([r.IGNORER_LA_LIGNE]))
    assert bilan["ajoutes"] == 0 and bilan["remplaces"] == 0
    assert bilan["ignorees_par_choix"] == 1
    assert _maison() == [("2026-03-01T10:00", 1.0)]


def test_annuler_n_ecrit_rien(dossier):
    _saisie(10, 0, 10, 15, 1.0)
    avant = (dossier / "recharges.json").read_bytes()
    with pytest.raises(r.ImportAnnule):
        r.importer_csv_maison(_csv(dossier, CSV_AUTRE_SESSION),
                              decider=Espion(None))
    assert (dossier / "recharges.json").read_bytes() == avant


# ---------- Ce qui reste automatique ----------

def test_cas_sur_remplace_sans_rien_demander(dossier):
    # La même session : la saisie recouvre la ligne du fichier.
    _saisie(9, 25, 11, 0, 10.0)
    espion = Espion(None)
    bilan = r.importer_csv_maison(_csv(dossier, [
        "BORNE1;2026-03-01 09:30:00;2026-03-01 11:00:00;10.05;1:30;2.01"]),
        decider=espion)
    assert espion.cas is None
    assert bilan["remplaces"] == 1
    assert _maison() == [("2026-03-01T09:30", 10.05)]


def test_reimporter_le_meme_fichier_ne_demande_rien(dossier):
    chemin = _csv(dossier, CSV_AUTRE_SESSION)
    r.importer_csv_maison(chemin)
    espion = Espion(None)
    bilan = r.importer_csv_maison(chemin, decider=espion)
    assert espion.cas is None and bilan["doublons"] == 1


def test_saisie_sans_heure_de_fin_dans_la_session_est_sure(dossier):
    # Tarif à prix unique : la fin peut manquer. Son début tombe pendant
    # la session du fichier : c'est la même.
    r.ajouter_recharge_maison(datetime(2026, 3, 1, 9, 45), None, 10.0)
    espion = Espion(None)
    bilan = r.importer_csv_maison(_csv(dossier, [
        "BORNE1;2026-03-01 09:30:00;2026-03-01 11:00:00;10.05;1:30;2.01"]),
        decider=espion)
    assert espion.cas is None and bilan["remplaces"] == 1


# ---------- Les cas douteux que l'ancienne règle tranchait seule ----------

def test_meme_session_avec_une_energie_trop_differente_est_douteuse(dossier):
    # Avant : hors tolérance, la ligne du fichier était AJOUTÉE sans un mot,
    # et la recharge comptait deux fois.
    id_saisie = _saisie(9, 30, 11, 0, 8.0)
    espion = Espion(lambda cas: [r.GARDER_LES_DEUX])
    r.importer_csv_maison(_csv(dossier, [
        "BORNE1;2026-03-01 09:30:00;2026-03-01 11:00:00;10.05;1:30;2.01"]),
        decider=espion)
    assert [s["id"] for s in espion.cas[0]["saisies"]] == [id_saisie]


def test_deux_saisies_qui_recouvrent_la_session_sont_douteuses(dossier):
    a = _saisie(9, 30, 10, 15, 10.0)
    b = _saisie(10, 15, 11, 0, 10.0)
    espion = Espion(lambda cas: [r.GARDER_LES_DEUX])
    r.importer_csv_maison(_csv(dossier, [
        "BORNE1;2026-03-01 09:30:00;2026-03-01 11:00:00;10.05;1:30;2.01"]),
        decider=espion)
    assert sorted(s["id"] for s in espion.cas[0]["saisies"]) == sorted([a, b])


# ---------- La fenêtre et la page Importer ----------

CAS = [{"cle": "k", "fichier": {"date": "2026-03-01T11:30",
                                "fin": "2026-03-01T11:45", "kwh": 1.05},
        "saisies": [{"id": "s1", "date": "2026-03-01T10:00",
                     "fin": "2026-03-01T10:15", "kwh": 1.0}]}]


def test_la_fenetre_propose_garder_les_deux_par_defaut(qapp):
    from dialogue_rapprochements import DialogueRapprochements
    fenetre = DialogueRapprochements(None, CAS)
    assert fenetre.reponses() == [r.GARDER_LES_DEUX]
    liste = fenetre.choix[0]
    textes = [liste.itemText(i) for i in range(liste.count())]
    assert textes == ["Garder les deux",
                      "Remplacer ma saisie par la ligne du fichier",
                      "Ignorer la ligne du fichier"]
    liste.setCurrentIndex(1)
    assert fenetre.reponses() == ["s1"]


def test_la_fenetre_montre_les_deux_recharges(qapp):
    from PySide6.QtWidgets import QLabel
    from dialogue_rapprochements import DialogueRapprochements
    fenetre = DialogueRapprochements(None, CAS)
    textes = " ".join(e.text() for e in fenetre.findChildren(QLabel))
    assert "Dans le fichier : 01/03/2026 11:30 → 11:45" in textes
    assert "Votre saisie : 01/03/2026 10:00 → 10:15" in textes


def test_la_page_dit_quand_l_import_est_annule(dossier, qapp, monkeypatch):
    from PySide6.QtWidgets import QLabel
    import dialogue_rapprochements
    from pages import importer
    _saisie(10, 0, 10, 15, 1.0)
    monkeypatch.setattr(dialogue_rapprochements, "demander_rapprochements",
                        lambda _f, _cas: None)

    class Fenetre:
        def _maj_bilan(self):
            pass
    resultat = QLabel()
    importer.importer_fichier(Fenetre(), str(_csv(dossier, CSV_AUTRE_SESSION)),
                              resultat)
    assert "Import annulé : rien n'a été enregistré" in resultat.text()
    assert _maison() == [("2026-03-01T10:00", 1.0)]


def test_le_compte_rendu_signale_les_doublons_possibles():
    from pages.importer import texte_resultat
    bilan = {"ajoutes": 1, "remplaces": 0, "doublons": 0, "zero_kwh": 0,
             "total_lus": 1, "a_verifier": CAS}
    texte, alerte = texte_resultat(bilan)
    assert alerte and "À vérifier" in texte and "01/03/2026 11:30" in texte


def test_la_page_ne_promet_plus_jamais_deux_fois(qapp):
    """U1 : « jamais comptée deux fois » était une promesse trop absolue."""
    import inspect
    from pages import importer
    assert "jamais comptée deux fois" not in inspect.getsource(importer)


def test_doublons_possibles_sans_ligne_illisible_ne_parlent_pas_de_ligne():
    from pages.importer import texte_resultat
    bilan = {"ajoutes": 1, "remplaces": 0, "doublons": 0, "zero_kwh": 0,
             "total_lus": 1, "non_reconnues": 0, "a_verifier": CAS}
    texte, _alerte = texte_resultat(bilan)
    assert "non reconnue" not in texte
