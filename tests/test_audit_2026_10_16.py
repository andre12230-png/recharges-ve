"""Analyse critique du 16/10/2026 (v2.2.9), point 1 : le doublon de reimport.

Scenario de l'audit : importer une recharge courte (15 min, 1,5 kWh),
changer la correction d'horloge de 20 minutes, reimporter le meme CSV. Les
horaires corriges ne se recouvraient plus : la recharge etait ajoutee une
seconde fois, energie et cout comptes deux fois.

La correction : chaque recharge importee garde l'heure de debut ecrite par
la borne (« debut_borne »), avant correction. Une ligne reimportee est
reconnue a cette heure-la, qui ne depend pas du reglage.

Toutes les donnees sont inventees, dans un dossier temporaire.

    py -m pytest tests/test_audit_2026_10_16.py
"""

import json
import os
import sys
import tempfile
from datetime import datetime
from pathlib import Path

import pytest

os.environ.setdefault("RECHARGES_DATA_DIR",
                      tempfile.mkdtemp(prefix="recharges_audit_1016_"))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import recharges as r  # noqa: E402

ENTETE_CSV = ("NS du chargeur,Heure de debut,Heure de fin,Consommation,"
              "Duree,Cout")
COURTE = ("WB-0001,2026-03-02 10:00:00,2026-03-02 10:15:00,1.500kWh,"
          "00h15min,0.30€")
SUIVANTE = ("WB-0001,2026-03-02 11:00:00,2026-03-02 11:15:00,1.500kWh,"
            "00h15min,0.30€")


def ecrire(chemin: Path, contenu) -> None:
    chemin.parent.mkdir(parents=True, exist_ok=True)
    chemin.write_text(json.dumps(contenu, ensure_ascii=False),
                      encoding="utf-8")


def ecrire_csv(dossier: Path, lignes: list[str]) -> Path:
    chemin = dossier / "borne.csv"
    chemin.write_text("\n".join([ENTETE_CSV] + lignes), encoding="utf-8")
    return chemin


def regler_correction(dossier: Path, minutes: int) -> None:
    tarifs = json.loads((dossier / "tarifs.json").read_text("utf-8"))
    tarifs["correction_csv_minutes"] = minutes
    ecrire(dossier / "tarifs.json", tarifs)
    r.vider_cache()


@pytest.fixture
def dossier(tmp_path, monkeypatch):
    """Un dossier de donnees neuf, avec une grille a prix unique."""
    ancien = r.BASE
    r.rediriger_donnees(tmp_path)
    monkeypatch.setattr(r, "DERNIERE_RESTAURATION", None)
    monkeypatch.setattr(r, "ECHEC_BACKUP", None, raising=False)
    ecrire(tmp_path / "tarifs.json", {
        "correction_csv_minutes": 0,
        "tarifs": [{"id": "t", "nom": "Prix unique", "type": "simple",
                    "debut": "2020-01-01", "fin": None, "prix_kwh": 0.20,
                    "abonnement_mensuel": 0.0}]})
    r.vider_cache()
    yield tmp_path
    r.rediriger_donnees(ancien)


def test_recharge_courte_reimportee_apres_correction_d_horloge(dossier):
    """Le scenario exact de l'audit : aucun ajout au second import."""
    r.importer_csv_maison(ecrire_csv(dossier, [COURTE]))
    regler_correction(dossier, 20)
    bilan = r.importer_csv_maison(ecrire_csv(dossier, [COURTE]))
    assert bilan["ajoutes"] == 0 and bilan["doublons"] == 1
    assert len(r.charger_donnees()["recharges"]) == 1


def test_decalage_d_une_heure_ne_confond_pas_deux_sessions(dossier):
    """Correction changee d'une heure : la session de 10 h decalee tombe sur
    celle de 11 h. Les deux restent reconnues chacune pour elle-meme."""
    r.importer_csv_maison(ecrire_csv(dossier, [COURTE, SUIVANTE]))
    regler_correction(dossier, 60)
    bilan = r.importer_csv_maison(ecrire_csv(dossier, [COURTE, SUIVANTE]))
    assert bilan["ajoutes"] == 0 and bilan["doublons"] == 2
    assert len(r.charger_donnees()["recharges"]) == 2


def test_deux_vraies_sessions_restent_distinctes(dossier):
    """Meme energie, meme borne, une heure d'ecart : deux recharges."""
    bilan = r.importer_csv_maison(ecrire_csv(dossier, [COURTE, SUIVANTE]))
    assert bilan["ajoutes"] == 2


def test_heure_de_la_borne_gardee_a_l_import(dossier):
    regler_correction(dossier, 20)
    r.importer_csv_maison(ecrire_csv(dossier, [COURTE]))
    recharge = r.charger_donnees()["recharges"][0]
    assert recharge["date"] == "2026-03-02T10:20"          # heure corrigee
    assert recharge["debut_borne"] == "2026-03-02T10:00:00"  # heure lue


def test_ancienne_recharge_completee_puis_reconnue(dossier):
    """Une recharge importee avant ce correctif n'a pas « debut_borne ».
    Reimportee avec le meme reglage, elle est reconnue comme avant et
    recoit l'heure de la borne ; un changement de reglage ensuite ne la
    double plus."""
    ecrire(dossier / "recharges.json", {"recharges": [
        {"id": "x", "date": "2026-03-02T10:00", "fin": "2026-03-02T10:15",
         "lieu": "maison", "kwh": 1.5, "cout_eur": 0.3,
         "source": "csv_import", "chargeur": "WB-0001"}]})
    r.vider_cache()
    bilan = r.importer_csv_maison(ecrire_csv(dossier, [COURTE]))
    assert bilan["ajoutes"] == 0 and bilan["doublons"] == 1
    recharge = r.charger_donnees()["recharges"][0]
    assert recharge["debut_borne"] == "2026-03-02T10:00:00"
    assert recharge["id"] == "x" and recharge["date"] == "2026-03-02T10:00"

    regler_correction(dossier, 20)
    bilan = r.importer_csv_maison(ecrire_csv(dossier, [COURTE]))
    assert bilan["ajoutes"] == 0
    assert len(r.charger_donnees()["recharges"]) == 1


def test_ancien_fichier_sans_heure_de_borne_reste_valide(dossier):
    """Le nouveau champ est facultatif : les anciens fichiers passent."""
    assert r.structure_recharges_valide({"recharges": [
        {"id": "x", "date": "2026-03-02T10:00", "lieu": "maison",
         "kwh": 1.5, "source": "csv_import"}]})


# ======================================================================
# Point 2 : estimations, perimetre du cout, sauvegardes inachevees
# ======================================================================

CONTROLE = {"conso_reference": 15.9, "kwh_batterie": 339.4,
            "kwh_attendu": 376.2, "rendement": 0.9, "ecart_kwh": 125.8,
            "ecart_pct": 33.5, "conso_enregistree": 21.2, "marge_kwh": 71.0,
            "capacite_batterie": 64.0}


def test_un_excedent_est_un_ecart_a_verifier_pas_une_impossibilite():
    """Le controle repose sur la consommation de reference et un rendement
    regle : il ne peut pas conclure « c'est impossible »."""
    from pages import kilometrage as km
    t = km.textes_controle(dict(CONTROLE, verdict="excedent"))
    assert "impossible" not in t["verdict"]
    assert t["verdict"].startswith("Écart inhabituel, à vérifier")
    assert "rendement de charge" in t["verdict"]


def test_la_part_non_enregistree_est_dite_estimee():
    from pages import kilometrage as km
    t = km.textes_controle(dict(CONTROLE, verdict="energie_exterieure",
                                ecart_kwh=-125.8, ecart_pct=-33.5,
                                conso_enregistree=10.6))
    assert "estimation" in t["verdict"]
    assert "proviennent" not in t["verdict"]
    assert "consommation réelle" not in t["verdict"]


def test_le_cout_aux_100_km_ne_promet_plus_un_cout_reel():
    """Sur le tableau de bord, dans le PDF et dans la notice : le cout aux
    100 km compte les recharges enregistrees, sans abonnement ni frais de
    cartes. « Coût réel » promettait un cout complet."""
    racine = Path(__file__).resolve().parent.parent
    for fichier in ("pages/tableau_de_bord.py", "pages/kilometrage.py",
                    "export.py"):
        texte = (racine / fichier).read_text(encoding="utf-8")
        assert "Coût réel de vos kilomètres" not in texte, fichier
        assert '"COÛT RÉEL"' not in texte, fichier
    notice = (racine / "notice_texte.py").read_text(encoding="utf-8")
    assert "affiche votre coût réel aux 100" not in notice


def test_la_bande_du_tableau_de_bord_dit_ce_qui_n_est_pas_compte(qapp):
    from pages import tableau_de_bord
    from PySide6.QtWidgets import QLabel
    cadre = tableau_de_bord._bande_cout_km(
        {"cout_100": 3.2, "km": 1000, "debut": "2026-01-01T10:00",
         "fin": "2026-02-01T10:00", "part_exterieure": None,
         "essence_100": None})
    textes = " ".join(e.text() for e in cadre.findChildren(QLabel))
    assert "abonnement" in textes and "frais de cartes" in textes


def test_la_part_non_enregistree_du_tableau_de_bord_est_une_estimation(qapp):
    from pages import tableau_de_bord
    from PySide6.QtWidgets import QLabel
    cadre = tableau_de_bord._bande_cout_km(
        {"cout_100": 3.2, "km": 1000, "debut": "2026-01-01T10:00",
         "fin": "2026-02-01T10:00", "part_exterieure": 15.0,
         "essence_100": None})
    textes = " ".join(e.text() for e in cadre.findChildren(QLabel))
    assert "estimation" in textes


# ---------- sauvegarde externe inachevee ----------

import sauvegarde_externe as se  # noqa: E402

QUAND = datetime(2026, 9, 15, 14, 30)


@pytest.fixture
def cle(tmp_path):
    donnees = tmp_path / "donnees"
    donnees.mkdir()
    (donnees / "recharges.json").write_text('{"recharges": []}', "utf-8")
    (donnees / "tarifs.json").write_text('{"tarifs": []}', "utf-8")
    support = tmp_path / "cle"
    support.mkdir()
    return donnees, support


def _sauver(donnees, support):
    return se.sauvegarder([donnees / "recharges.json",
                           donnees / "tarifs.json"],
                          support, donnees, "Recharges VE", "v2.2.9", QUAND)


def test_panne_pendant_la_copie_laisse_un_dossier_marque_inacheve(
        cle, monkeypatch):
    """Panne sur le deuxieme fichier : le dossier partiel ne porte jamais le
    nom d'une sauvegarde complete."""
    donnees, support = cle
    vraie_copie = se.shutil.copy2
    appels = []

    def copie_en_panne(source, dest):
        appels.append(source)
        if len(appels) == 2:
            raise OSError(28, "No space left on device")
        return vraie_copie(source, dest)

    monkeypatch.setattr(se.shutil, "copy2", copie_en_panne)
    with pytest.raises(se.SauvegardeImpossible):
        _sauver(donnees, support)
    noms = [d.name for d in support.iterdir()]
    assert "Sauvegarde Recharges VE 2026-09-15 14h30" not in noms
    assert len(noms) == 1 and "INACHEVÉE" in noms[0]


def test_copie_differente_laisse_un_dossier_marque_inacheve(
        cle, monkeypatch):
    donnees, support = cle
    monkeypatch.setattr(se.shutil, "copy2",
                        lambda source, dest: Path(dest).write_bytes(b"abime"))
    with pytest.raises(se.SauvegardeImpossible, match="ne correspond pas"):
        _sauver(donnees, support)
    noms = [d.name for d in support.iterdir()]
    assert len(noms) == 1 and "INACHEVÉE" in noms[0]


def test_sauvegarde_reussie_garde_son_nom_habituel(cle):
    donnees, support = cle
    cible, _ = _sauver(donnees, support)
    assert [d.name for d in support.iterdir()] == [
        "Sauvegarde Recharges VE 2026-09-15 14h30"]
    assert (cible / "LISEZMOI.txt").is_file()


def test_fermeture_ne_prend_pas_une_copie_inachevee_pour_la_derniere(
        cle):
    """Une copie de fermeture inachevee, identique en apparence, ne doit pas
    faire croire que les donnees sont deja sauvegardees."""
    donnees, _ = cle
    sous = donnees / se.DOSSIER_FERMETURE
    partielle = sous / "Sauvegarde Recharges VE 2026-09-15 14h30 INACHEVÉE"
    partielle.mkdir(parents=True)
    for nom in ("recharges.json", "tarifs.json"):
        (partielle / nom).write_bytes((donnees / nom).read_bytes())
    cible = se.sauvegarder_a_la_fermeture(
        [donnees / "recharges.json", donnees / "tarifs.json"], donnees,
        "Recharges VE", "v2.2.9", datetime(2026, 9, 16, 9, 0),
        corbeille=lambda _chemin: False)
    assert cible is not None and "INACHEVÉE" not in cible.name


# ======================================================================
# Point 4 : validation des fichiers JSON
# ======================================================================
# Une date au mois inexistant ou un nombre « NaN » (que json.load accepte)
# passaient le controle de forme, puis empechaient une page de s'afficher.
# Ils font desormais traiter le fichier comme abime : la sauvegarde la plus
# recente le remplace, il est mis de cote, et l'utilisateur est prevenu.

@pytest.mark.parametrize("mauvais", [
    {"recharges": [{"date": "2026-13-01T10:00", "kwh": 1.0}]},
    {"recharges": [{"date": "2026-02-30T10:00", "kwh": 1.0}]},
    {"recharges": [{"date": "2026-03-01T10:00", "fin": "hier",
                    "kwh": 1.0}]},
    {"recharges": [{"date": "2026-03-01T10:00", "kwh": float("nan")}]},
    {"recharges": [{"date": "2026-03-01T10:00", "cout_eur": float("inf")}]},
    {"recharges": [], "releves_km": [{"date": "2026-13-01T10:00",
                                      "km": 100.0}]},
    {"recharges": [], "releves_km": [{"date": "2026-03-01T10:00",
                                      "km": "cent"}]},
    {"recharges": [], "releves_km": [{"date": "2026-03-01T10:00",
                                      "km": float("nan")}]},
    {"recharges": [], "releves_km": [{"date": "2026-03-01T10:00",
                                      "km": 100.0, "conso": float("inf")}]},
])
def test_dates_impossibles_et_nombres_invalides_refuses(mauvais):
    assert not r.structure_recharges_valide(mauvais)


def test_formes_ordinaires_toujours_acceptees():
    """Les ecritures que l'application produit ou a produites."""
    assert r.structure_recharges_valide({"recharges": [
        {"date": "2026-03-01T10:00", "fin": "2026-03-01T12:00", "kwh": 10},
        {"date": "2026-03-02 10:00:00", "fin": None, "kwh": 5.5,
         "cout_eur": None},
        {"date": "2026-03-03T10:00", "fin": "", "kwh": 1.0,
         "debut_borne": "2026-03-03T09:59:30"},
    ], "releves_km": [{"date": "2026-01-01T00:00", "km": 0},
                      {"date": "2026-02-01T10:00", "km": 1000.5,
                       "conso": None}]})


def test_un_fichier_au_mois_impossible_est_repare_au_demarrage(dossier):
    """Le fichier abime n'empeche plus une page de s'afficher : il est
    remplace par la derniere sauvegarde saine, et mis de cote."""
    saine = {"recharges": [{"id": "a", "date": "2026-03-01T10:00",
                            "lieu": "exterieur", "kwh": 10.0,
                            "cout_eur": 4.0}]}
    ecrire(dossier / "backups" / "recharges_20260301_100000.json", saine)
    (dossier / "recharges.json").write_text(
        '{"recharges": [{"id": "a", "date": "2026-13-01T10:00", '
        '"lieu": "exterieur", "kwh": NaN}]}', encoding="utf-8")
    r.vider_cache()
    donnees = r.charger_donnees()
    assert donnees["recharges"][0]["date"] == "2026-03-01T10:00"
    assert r.DERNIERE_RESTAURATION is not None
    assert r.DERNIERE_RESTAURATION["mis_de_cote"]


# ---------- libelle « Restaurer une sauvegarde » rogne ----------

def test_la_page_affichee_rend_sa_place_au_libelle_en_gras():
    """En gras (page affichee), « Restaurer une sauvegarde » demandait
    182 px pour 175 disponibles : le dernier « e » disparaissait. Le retrait
    de droite du bouton coche est retire, avec ou sans curseur clavier ; le
    bandeau garde sa largeur commune de 212 px. La largeur du texte elle-meme
    ne se mesure pas ici (polices absentes en « offscreen ») : elle a ete
    mesuree a l'ecran, voir le JOURNAL du 16/10/2026."""
    import theme_qt
    feuille = theme_qt.feuille_de_style().replace(" ", "")
    assert "QPushButton#EntreeMenu:checked{padding-right:0px;}" in feuille
    assert "QPushButton#EntreeMenu:checked:focus{padding-right:0px;}" in feuille
    assert theme_qt.LARGEUR_BANDEAU == 212
