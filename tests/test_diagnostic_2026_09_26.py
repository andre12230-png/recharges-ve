"""Les neuf defauts du diagnostic du 26/09/2026 (v2.0.0), un test chacun.

Chaque test reproduit un defaut trouve par la relecture du code, et doit
rester vert apres sa correction :

1. l'application ouverte deux fois : la derniere fenetre qui enregistre
   effacait les saisies de l'autre ;
2. un recharges.json aux accents mal codes (Bloc-notes, encodage Windows)
   n'etait pas repare depuis les sauvegardes, et la page Restaurer ne
   s'affichait plus ;
3. modifier une recharge maison saisie SANS heure de fin ne recalculait pas
   son cout ;
4. l'ecart avec la wallbox comptait aussi les recharges que la wallbox
   n'avait jamais chiffrees ;
5. une recharge saisie a la main (30,5 kWh) et la meme lue dans le CSV
   (30,497 kWh) etaient comptees deux fois ;
6. une charge de fin decembre saisie en janvier finissait un an plus tard ;
7. un CSV reenregistre par Excel (encodage Windows) etait refuse en entier ;
8. « Recalculer tous les couts » passait des recharges sans le dire ;
9. tarifs.json disparu chez un utilisateur en place : l'application se
   croyait au premier demarrage, sans signaler la perte ni la copie.

Toutes les donnees sont inventees, dans un dossier temporaire.

    py -m pytest tests/test_diagnostic_2026_09_26.py
"""

import json
import os
import sys
import tempfile
from datetime import datetime
from pathlib import Path

import pytest

os.environ.setdefault("RECHARGES_DATA_DIR",
                      tempfile.mkdtemp(prefix="recharges_diagnostic_"))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import recharges as r  # noqa: E402
from saisie import ErreurSaisie, lire_recharge_maison  # noqa: E402
from saisie import lire_modification_recharge  # noqa: E402

PRIX_UNIQUE = {"id": "t_simple", "nom": "Prix unique", "type": "simple",
               "debut": "2020-01-01", "fin": None, "prix_kwh": 0.20,
               "abonnement_mensuel": 0.0}


def ecrire_tarifs(dossier: Path, tarifs: list[dict]) -> None:
    (dossier / "tarifs.json").write_text(
        json.dumps({"tarifs": tarifs, "correction_csv_minutes": 0},
                   ensure_ascii=False), encoding="utf-8")


@pytest.fixture
def dossier(tmp_path, monkeypatch):
    """Un dossier de donnees neuf avec un tarif a prix unique, rendu a la
    fin du test. Les indicateurs du demarrage repartent de zero."""
    ancien = r.BASE
    r.rediriger_donnees(tmp_path)
    monkeypatch.setattr(r, "DERNIERE_RESTAURATION", None)
    monkeypatch.setattr(r, "PREMIER_DEMARRAGE", False)
    monkeypatch.setattr(r, "INCIDENT_TARIFS", None, raising=False)
    ecrire_tarifs(tmp_path, [PRIX_UNIQUE])
    yield tmp_path
    r.rediriger_donnees(ancien)


# ---------- 1. une seule fenetre a la fois ----------

def test_1_une_seule_fenetre_par_dossier_de_donnees(qapp, tmp_path):
    from fenetre import verrou_instance_unique
    premier = verrou_instance_unique(tmp_path)
    assert premier is not None
    try:
        # Second lancement sur les memes donnees : refuse.
        assert verrou_instance_unique(tmp_path) is None
        # Un autre dossier de donnees reste libre (l'autotest s'en sert).
        autre = verrou_instance_unique(tmp_path / "autre")
        assert autre is not None
        autre.unlock()
    finally:
        premier.unlock()
    # La premiere fenetre fermee, on peut rouvrir.
    ensuite = verrou_instance_unique(tmp_path)
    assert ensuite is not None
    ensuite.unlock()


# ---------- 2. fichier aux accents mal codes ----------

def _fichier_en_encodage_windows(dossier: Path) -> None:
    """Une sauvegarde saine, puis le fichier de travail reenregistre en
    encodage Windows par le Bloc-notes (un « e accent » dans un lieu)."""
    sain = {"recharges": [{"id": "a", "date": "2026-03-01T10:00",
                           "lieu": "exterieur", "kwh": 10.0,
                           "cout_eur": 4.0, "lieu_detail": "Aire des Prés"}]}
    (dossier / "backups").mkdir()
    (dossier / "backups" / "recharges_20260301_100000.json").write_text(
        json.dumps(sain, ensure_ascii=False), encoding="utf-8")
    (dossier / "recharges.json").write_bytes(
        json.dumps(sain, ensure_ascii=False).encode("cp1252"))


def test_2_accents_mal_codes_repares_depuis_la_sauvegarde(dossier):
    _fichier_en_encodage_windows(dossier)
    donnees = r.charger_donnees()
    assert len(donnees["recharges"]) == 1
    assert r.DERNIERE_RESTAURATION is not None
    # Le fichier abime est garde a part, pour y repecher des saisies.
    assert list(dossier.glob("recharges_illisible_*.json"))


def test_2_page_restaurer_s_affiche_meme_fichier_illisible(dossier, qapp,
                                                           monkeypatch):
    """Si aucune sauvegarde ne peut reparer le fichier, la page Restaurer
    est la seule issue : elle doit s'afficher quand meme."""
    from PySide6.QtWidgets import QLabel

    from pages import restaurer
    (dossier / "recharges.json").write_text("{ abime", encoding="utf-8")
    r.vider_cache()
    page = restaurer.construire(None)
    # Les titres de carte sont en majuscules : on compare en minuscules.
    textes = " ".join(e.text() for e in page.findChildren(QLabel)).lower()
    assert "données actuelles : fichier illisible" in textes


# ---------- 3. modifier une recharge sans heure de fin ----------

def test_3_modifier_sans_heure_de_fin_recalcule_le_cout(dossier):
    recharge = r.ajouter_recharge_maison(datetime(2026, 3, 1, 22, 0), None,
                                         30.0)
    assert recharge["cout_eur"] == 6.0
    modifiee = r.modifier_recharge(recharge["id"], {"kwh": 10.0})
    assert modifiee["cout_eur"] == 2.0
    assert modifiee["prix_kwh"] == 0.2


# ---------- 4. ecart avec la wallbox ----------

def test_4_ecart_wallbox_seulement_sur_ce_qu_elle_a_chiffre():
    from pages import statistiques as st
    recharges = [
        {"lieu": "maison", "kwh": 10, "cout_eur": 2.0, "cout_wallbox": 2.5},
        {"lieu": "maison", "kwh": 10, "cout_eur": 2.0},   # saisie a la main
    ]
    assert st.ecart_wallbox(recharges) == {"wallbox": 2.5, "reel": 2.0,
                                           "ecart": -0.5, "n": 1}


# ---------- 5. saisie a la main puis import du CSV ----------

def _csv(dossier: Path, lignes: list[str], encodage: str = "utf-8",
         entete: str = "Chargeur;Début;Fin;Énergie;Durée;Coût €") -> Path:
    chemin = dossier / "export.csv"
    chemin.write_bytes("\r\n".join([entete, *lignes]).encode(encodage))
    return chemin


def test_5_saisie_manuelle_arrondie_remplacee_par_le_csv(dossier):
    r.ajouter_recharge_maison(datetime(2026, 3, 1, 22, 0),
                              datetime(2026, 3, 2, 6, 0), 30.5)
    chemin = _csv(dossier, ["BORNE1;2026-03-01 22:00:00;2026-03-02 06:00:00;"
                            "30.497;8:00;6.10"])
    bilan = r.importer_csv_maison(chemin)
    assert (bilan["ajoutes"], bilan["remplaces"]) == (0, 1)
    assert len(r.charger_donnees()["recharges"]) == 1


def test_5_une_energie_vraiment_differente_reste_une_autre_recharge(dossier):
    r.ajouter_recharge_maison(datetime(2026, 3, 1, 22, 0),
                              datetime(2026, 3, 2, 6, 0), 20.0)
    chemin = _csv(dossier, ["BORNE1;2026-03-01 22:30:00;2026-03-02 06:00:00;"
                            "30.497;7:30;6.10"])
    bilan = r.importer_csv_maison(chemin)
    assert (bilan["ajoutes"], bilan["remplaces"]) == (1, 0)


# ---------- 6. charge de fin decembre saisie en janvier ----------

def test_6_fin_de_decembre_saisie_en_janvier():
    lu = lire_recharge_maison("30/12", "22h", "31/12", "6h", "20", "",
                              maintenant=datetime(2027, 1, 2, 9, 0))
    assert lu["debut"] == datetime(2026, 12, 30, 22, 0)
    assert lu["fin"] == datetime(2026, 12, 31, 6, 0)


def test_6_une_duree_de_plusieurs_jours_est_refusee():
    with pytest.raises(ErreurSaisie) as erreur:
        lire_recharge_maison("01/03/2026", "22h", "10/03/2026", "6h", "20",
                             "", maintenant=datetime(2026, 3, 15))
    assert erreur.value.champ == "champ_m_fin_jour"
    with pytest.raises(ErreurSaisie):
        lire_modification_recharge(
            {"lieu": "maison", "date": "2026-03-01T22:00"},
            {"fin_jour": "10/03/2026", "fin_heure": "6h", "kwh": "20"},
            maintenant=datetime(2026, 3, 15))


# ---------- 7. CSV reenregistre par Excel ----------

@pytest.mark.parametrize("encodage", ["cp1252", "utf-16"])
def test_7_csv_en_encodage_windows_ou_utf16(dossier, encodage):
    chemin = _csv(dossier, ["BORNE1;01/03/2026 22:00;02/03/2026 06:00;"
                            "30,5;8:00;6,10"], encodage=encodage)
    bilan = r.importer_csv_maison(chemin)
    assert bilan["ajoutes"] == 1


# ---------- 8. le recalcul dit ce qu'il laisse de cote ----------

def test_8_recalcul_compte_les_recharges_laissees(dossier):
    r.ajouter_recharge_maison(datetime(2026, 3, 1, 22, 0),
                              datetime(2026, 3, 2, 6, 0), 10.0)
    donnees = r.charger_donnees(pour_modification=True)
    # Une recharge d'avant tout tarif connu : impossible a recalculer.
    donnees["recharges"].append({
        "id": "vieille", "date": "2019-06-01T22:00",
        "fin": "2019-06-02T06:00", "lieu": "maison", "kwh": 10.0,
        "cout_eur": 1.5})
    r.sauvegarder_donnees(donnees)
    recalculees, laissees = r.recalculer_tout()
    assert recalculees == 1
    assert laissees == ["2019-06-01T22:00"]


def test_8_le_message_nomme_les_recharges_laissees():
    from pages.tarifs import message_recalcul
    assert message_recalcul(3, []) == "3 recharges recalculées."
    texte = message_recalcul(3, ["2019-06-01T22:00"])
    # Accorde (29/09/2026 ; c'etait « 1 recharge(s) laissée(s) »)
    assert "1 recharge laissée avec son ancien montant" in texte
    assert "01/06/2019" in texte and "couvre sa date" in texte
    texte = message_recalcul(1, ["2019-06-01T22:00", "2019-06-02T22:00"])
    assert texte.startswith("1 recharge recalculée.")
    assert "2 recharges laissées avec leur ancien montant" in texte


# ---------- 9. tarifs.json disparu ----------

def test_9_tarifs_disparus_remis_depuis_la_sauvegarde(dossier):
    (dossier / "backups").mkdir()
    (dossier / "backups" / "tarifs_20260301_100000.json").write_text(
        json.dumps({"tarifs": [PRIX_UNIQUE]}), encoding="utf-8")
    (dossier / "tarifs.json").unlink()
    assert r.charger_tarifs() == [PRIX_UNIQUE]
    assert not r.PREMIER_DEMARRAGE
    assert r.INCIDENT_TARIFS["copie"] == "tarifs_20260301_100000.json"
    # Le fichier de travail est remis en place.
    assert (dossier / "tarifs.json").exists()


def test_9_tarifs_disparus_sans_copie_ne_sont_pas_un_premier_demarrage(
        dossier):
    r.ajouter_recharge_maison(datetime(2026, 3, 1, 22, 0), None, 10.0)
    (dossier / "tarifs.json").unlink()
    assert r.charger_tarifs() == []
    assert not r.PREMIER_DEMARRAGE
    assert r.INCIDENT_TARIFS == {"copie": None, "date": None}


def test_9_vrai_premier_demarrage_inchange(dossier):
    (dossier / "tarifs.json").unlink()
    assert r.charger_tarifs() == []
    assert r.PREMIER_DEMARRAGE
    assert r.INCIDENT_TARIFS is None
