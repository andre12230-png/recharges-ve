"""Audit « nouvel utilisateur » du 11/11/2026 : les trois chiffres faux qui
arrivent par un geste ordinaire (constats V1, V2 et V3).

V2 : deux tarifs qui commencent le même jour (un prix corrigé en ajoutant
une période au lieu de modifier la première). L'avertissement annonçait
que le nouveau s'appliquait ; le calcul prenait l'ancien.

V1 : tant que la capacité de la batterie n'était pas renseignée, aucune
énergie n'était jugée invraisemblable : 30 000 « kWh » (des Wh) passaient
sans question à la saisie, et sans un mot à l'import. Désormais, capacité
inconnue : un plafond fixe prend le relais (ENERGIE_MAX_SANS_CAPACITE).

V3 : une recharge importée, puis corrigée à la main dans l'Historique
(30 kWh ramenés à 28), était ajoutée une seconde fois au réimport du même
fichier. Même heure de borne et même chargeur : c'est la même ligne, quelle
que soit l'énergie ; le compte rendu signale l'écart.

Données inventées, dans un dossier temporaire.

    py -m pytest tests/test_audit_2026_11_11.py
"""

import json
import os
import sys
import tempfile
from datetime import date, datetime
from pathlib import Path

import pytest

os.environ.setdefault("RECHARGES_DATA_DIR",
                      tempfile.mkdtemp(prefix="recharges_audit_1111_"))
RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))

import recharges as r  # noqa: E402

PRIX_UNIQUE = {"id": "t_simple", "nom": "Prix unique", "type": "simple",
               "debut": "2020-01-01", "fin": None, "prix_kwh": 0.20,
               "abonnement_mensuel": 0.0}


def _dossier_neuf(tmp_path, monkeypatch, reglages: dict):
    ancien = r.BASE
    r.rediriger_donnees(tmp_path)
    monkeypatch.setattr(r, "DERNIERE_RESTAURATION", None)
    monkeypatch.setattr(r, "PREMIER_DEMARRAGE", False)
    monkeypatch.setattr(r, "INCIDENT_TARIFS", None, raising=False)
    (tmp_path / "tarifs.json").write_text(
        json.dumps({"correction_csv_minutes": 0, **reglages},
                   ensure_ascii=False), encoding="utf-8")
    return ancien


@pytest.fixture
def grille_vide(tmp_path, monkeypatch):
    """Un dossier neuf, sans aucun tarif."""
    ancien = _dossier_neuf(tmp_path, monkeypatch, {"tarifs": []})
    yield tmp_path
    r.rediriger_donnees(ancien)


@pytest.fixture
def sans_capacite(tmp_path, monkeypatch):
    """Un tarif à prix unique ; capacité de la batterie NON renseignée."""
    ancien = _dossier_neuf(tmp_path, monkeypatch,
                           {"tarifs": [PRIX_UNIQUE], "capacite_batterie": 0})
    yield tmp_path
    r.rediriger_donnees(ancien)


@pytest.fixture
def avec_capacite(tmp_path, monkeypatch):
    """Un tarif à prix unique ; batterie de 50 kWh, rendement 90 %."""
    ancien = _dossier_neuf(tmp_path, monkeypatch,
                           {"tarifs": [PRIX_UNIQUE], "capacite_batterie": 50,
                            "rendement_charge": 0.9})
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


# ---------- V2 : deux tarifs du même jour ----------

def _tarif(nom: str, prix: float, abonnement: float = 0.0, **autres) -> dict:
    return {"nom": nom, "debut": "2026-01-01", "fin": None, "type": "simple",
            "abonnement_mensuel": abonnement, "prix_kwh": prix, **autres}


def test_v2_le_dernier_saisi_s_applique_comme_le_dit_le_message(grille_vide):
    r.enregistrer_tarif(_tarif("Ancien prix", 0.252))
    avertissements = r.enregistrer_tarif(_tarif("Nouveau prix", 0.30))
    # Le message annonce le nouveau…
    assert any("c'est « Nouveau prix », plus récent" in a
               for a in avertissements)
    # … et c'est bien lui qui sert au calcul : 10 kWh à 0,30 €.
    calc = r.calculer_cout(datetime(2026, 3, 1, 10, 0),
                           datetime(2026, 3, 1, 11, 0), 10.0)
    assert calc["tarif_nom"] == "Nouveau prix"
    assert round(calc["cout"], 2) == 3.00


def test_v2_l_abonnement_suit_le_meme_tarif(grille_vide):
    r.enregistrer_tarif(_tarif("Ancien prix", 0.252, abonnement=10.0))
    r.enregistrer_tarif(_tarif("Nouveau prix", 0.30, abonnement=12.0))
    abonnement = r.calculer_abonnement(date(2026, 3, 1), date(2026, 3, 31))
    assert abonnement["par_tarif"] == {"Nouveau prix": 12.0}


def test_v2_une_periode_plus_recente_garde_la_main(grille_vide):
    """La règle d'avant ne change pas : la période qui commence le plus tard
    l'emporte, même si elle est écrite la première dans le fichier."""
    r.enregistrer_tarif(dict(_tarif("Exception de mars", 0.50),
                             debut="2026-03-01", fin="2026-03-31"))
    r.enregistrer_tarif(_tarif("Toute l'année", 0.20))
    calc = r.calculer_cout(datetime(2026, 3, 10, 10, 0),
                           datetime(2026, 3, 10, 11, 0), 10.0)
    assert calc["tarif_nom"] == "Exception de mars"
    calc = r.calculer_cout(datetime(2026, 4, 10, 10, 0),
                           datetime(2026, 4, 10, 11, 0), 10.0)
    assert calc["tarif_nom"] == "Toute l'année"


# ---------- V1 : énergie invraisemblable sans capacité renseignée ----------

LIGNE_30_KWH = ("BORNE1;2026-03-01 22:00:00;2026-03-02 02:00:00;"
                "30;4:00;6.00")
LIGNE_30000_KWH = ("BORNE1;2026-03-03 22:00:00;2026-03-04 02:00:00;"
                   "30000;4:00;6.00")


def test_v1_la_saisie_pose_la_question_sans_capacite(sans_capacite):
    souci = r.energie_invraisemblable(30000.0)
    assert souci, "30 000 kWh doivent faire poser la question"
    assert "150" in souci                      # le plafond est dit
    assert "Paramètres" in souci               # et où régler la capacité


def test_v1_une_grosse_recharge_reelle_passe_sans_question(sans_capacite):
    assert r.energie_invraisemblable(95.0) == ""
    assert r.energie_invraisemblable(r.ENERGIE_MAX_SANS_CAPACITE) == ""


def test_v1_capacite_renseignee_la_regle_ne_change_pas(avec_capacite):
    """50 kWh, rendement 90 % : 55,6 kWh au plus. Le plafond fixe ne joue
    pas, dans un sens comme dans l'autre."""
    assert r.energie_invraisemblable(55.0) == ""
    souci = r.energie_invraisemblable(60.0)
    assert "votre batterie" in souci and "150" not in souci


def test_v1_l_import_met_de_cote_sans_capacite(sans_capacite):
    bilan = r.importer_csv_maison(_csv(sans_capacite,
                                       [LIGNE_30_KWH, LIGNE_30000_KWH]))
    assert bilan["ajoutes"] == 1
    assert bilan["trop_kwh"] == [{"date": "2026-03-03T22:00", "kwh": 30000.0}]
    assert bilan["capacite_connue"] is False
    assert _maison() == [("2026-03-01T22:00", 30.0)]


def test_v1_le_compte_rendu_dit_quoi_faire_sans_capacite(sans_capacite):
    import pages.importer as im
    bilan = r.importer_csv_maison(_csv(sans_capacite,
                                       [LIGNE_30_KWH, LIGNE_30000_KWH]))
    texte, alerte = im.texte_resultat(bilan)
    assert alerte
    assert "ATTENTION : 1 session mise de côté, donc pas enregistrée" in texte
    assert "150" in texte
    assert "Renseignez la capacité de la batterie dans Paramètres" in texte


def test_v1_le_compte_rendu_ne_change_pas_avec_capacite(avec_capacite):
    import pages.importer as im
    bilan = r.importer_csv_maison(_csv(avec_capacite,
                                       [LIGNE_30_KWH, LIGNE_30000_KWH]))
    assert bilan["capacite_connue"] is True
    texte, _alerte = im.texte_resultat(bilan)
    assert "Vérifiez la capacité de la batterie dans Paramètres" in texte


def test_v1_le_plafond_n_est_ecrit_qu_a_un_endroit():
    """La notice lit le plafond dans constantes.py : si le nombre change,
    elle suit toute seule."""
    import constantes
    import notice_texte
    assert r.ENERGIE_MAX_SANS_CAPACITE is constantes.ENERGIE_MAX_SANS_CAPACITE
    notice = " ".join(texte for _titre, paragraphes in notice_texte.SECTIONS
                      for _intitule, texte in paragraphes)
    plafond = f"{constantes.ENERGIE_MAX_SANS_CAPACITE:.0f}\xa0kWh"
    assert notice.count(plafond) == 2     # import, et réglages de la voiture


# ---------- V3 : recharge importée, corrigée, puis réimportée ----------

def test_v3_la_recharge_corrigee_n_est_pas_doublee(avec_capacite):
    chemin = _csv(avec_capacite, [LIGNE_30_KWH])
    assert r.importer_csv_maison(chemin)["ajoutes"] == 1
    importee = r.charger_donnees()["recharges"][0]
    r.modifier_recharge(importee["id"], {"kwh": 28.0})

    bilan = r.importer_csv_maison(chemin)

    assert bilan["ajoutes"] == 0 and bilan["doublons"] == 1
    assert _maison() == [("2026-03-01T22:00", 28.0)]   # la correction reste
    assert bilan["energie_differente"] == [
        {"date": "2026-03-01T22:00", "kwh": 28.0, "kwh_fichier": 30.0}]


def test_v3_le_compte_rendu_signale_l_ecart(avec_capacite):
    import pages.importer as im
    chemin = _csv(avec_capacite, [LIGNE_30_KWH])
    r.importer_csv_maison(chemin)
    importee = r.charger_donnees()["recharges"][0]
    r.modifier_recharge(importee["id"], {"kwh": 28.0})
    texte, _alerte = im.texte_resultat(r.importer_csv_maison(chemin))
    assert "n'a pas la même énergie que dans le fichier" in texte
    assert "01/03/2026 22:00" in texte
    assert "28,00\xa0kWh" in texte and "30,00\xa0kWh" in texte


def test_v3_reimport_sans_correction_rien_a_signaler(avec_capacite):
    chemin = _csv(avec_capacite, [LIGNE_30_KWH])
    r.importer_csv_maison(chemin)
    bilan = r.importer_csv_maison(chemin)
    assert bilan["ajoutes"] == 0 and bilan["doublons"] == 1
    assert bilan["energie_differente"] == []


def test_v3_un_autre_chargeur_reste_une_autre_recharge(avec_capacite):
    """Deux bornes qui démarrent à la même seconde : deux recharges."""
    autre = LIGNE_30_KWH.replace("BORNE1", "BORNE2").replace(";30;", ";12;")
    bilan = r.importer_csv_maison(_csv(avec_capacite, [LIGNE_30_KWH, autre]))
    assert bilan["ajoutes"] == 2 and bilan["energie_differente"] == []
