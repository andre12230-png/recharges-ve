"""Import CSV d'autres bornes (28/09/2026).

Jusque-la, seul un export a six colonnes dans un ordre fixe (chargeur,
debut, fin, energie, duree, cout) etait reconnu. Pour un autre fichier,
l'utilisateur indique les colonnes (debut, fin ou duree, energie en kWh ou
Wh, cout facultatif) ; ce choix est retenu pour les imports suivants du meme
modele. Le format d'origine reste reconnu sans rien demander. Donnees
inventees, dans un dossier jetable.

    py -m pytest tests/test_import_autres_bornes.py
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import pytest

import recharges as r

PRIX_UNIQUE = {"id": "t_simple", "nom": "Prix unique", "type": "simple",
               "debut": "2020-01-01", "fin": None, "prix_kwh": 0.20,
               "abonnement_mensuel": 0.0}

# Un export d'une autre borne : colonnes dans un autre ordre, virgules,
# dates ISO avec « T », energie en Wh, pas de cout.
AUTRE = ("Session,Energy (Wh),Start,End,User\n"
         "1,30000,2026-03-01T22:00:00,2026-03-02T06:00:00,Moi\n"
         "2,12500,2026-03-05T21:30:00,2026-03-06T01:30:00,Moi\n")
CORRESPONDANCE = {"debut": 2, "fin": 3, "duree": None, "kwh": 1,
                  "unite": "Wh", "cout": None}


@pytest.fixture
def dossier(tmp_path, monkeypatch):
    ancien = r.BASE
    r.rediriger_donnees(tmp_path)
    monkeypatch.setattr(r, "DERNIERE_RESTAURATION", None)
    monkeypatch.setattr(r, "PREMIER_DEMARRAGE", False)
    monkeypatch.setattr(r, "INCIDENT_TARIFS", None, raising=False)
    (tmp_path / "tarifs.json").write_text(json.dumps(
        {"tarifs": [PRIX_UNIQUE], "correction_csv_minutes": 0}),
        encoding="utf-8")
    yield tmp_path
    r.rediriger_donnees(ancien)


def _fichier(dossier: Path, texte: str, nom="autre.csv") -> Path:
    chemin = dossier / nom
    chemin.write_text(texte, encoding="utf-8")
    return chemin


# ---------- l'apercu ----------

def test_apercu_d_un_fichier(dossier):
    a = r.apercu_csv(_fichier(dossier, AUTRE))
    assert a["separateur"] == ","
    assert a["entetes"] == ["Session", "Energy (Wh)", "Start", "End", "User"]
    assert a["lignes"][0] == ["1", "30000", "2026-03-01T22:00:00",
                              "2026-03-02T06:00:00", "Moi"]


def test_apercu_sans_ligne_de_titres(dossier):
    a = r.apercu_csv(_fichier(dossier, "01/03/2026 22:00;8;4,5\n"))
    assert a["separateur"] == ";"
    assert a["entetes"] == ["Colonne 1", "Colonne 2", "Colonne 3"]
    assert len(a["lignes"]) == 1


def test_les_colonnes_sont_devinees_d_apres_les_titres(dossier):
    a = r.apercu_csv(_fichier(dossier, AUTRE))
    assert r.deviner_correspondance(a) == CORRESPONDANCE
    francais = r.apercu_csv(_fichier(dossier, (
        "Date de début;Durée;Énergie (kWh);Montant €\n"
        "01/03/2026 22:00;8:00;30,5;6,10\n"), "fr.csv"))
    assert r.deviner_correspondance(francais) == {
        "debut": 0, "fin": None, "duree": 1, "kwh": 2, "unite": "kWh",
        "cout": 3}


# ---------- l'import avec les colonnes choisies ----------

def test_un_format_inconnu_est_signale_a_part(dossier):
    with pytest.raises(r.FormatCsvInconnu):
        r.importer_csv_maison(_fichier(dossier, AUTRE))


def test_import_avec_les_colonnes_choisies(dossier):
    bilan = r.importer_csv_maison(_fichier(dossier, AUTRE),
                                  correspondance=CORRESPONDANCE)
    assert bilan["ajoutes"] == 2 and bilan["non_reconnues"] == 0
    recharges = sorted(r.charger_donnees()["recharges"],
                       key=lambda x: x["date"])
    assert recharges[0]["date"] == "2026-03-01T22:00"
    assert recharges[0]["fin"] == "2026-03-02T06:00"
    assert recharges[0]["kwh"] == 30.0                 # Wh -> kWh
    assert recharges[0]["cout_eur"] == 6.0             # d'apres le tarif
    assert "cout_wallbox" not in recharges[0]          # la borne n'en dit rien
    # Reimporter ne compte rien deux fois.
    bilan = r.importer_csv_maison(_fichier(dossier, AUTRE),
                                  correspondance=CORRESPONDANCE)
    assert (bilan["ajoutes"], bilan["doublons"]) == (0, 2)


def test_une_duree_au_lieu_de_la_fin(dossier):
    texte = ("Début;Durée;kWh;Coût\n"
             "01/03/2026 22:00;8:00;30,5;6,10\n"
             "05/03/2026 21:30;240;10;2\n")          # 240 minutes
    bilan = r.importer_csv_maison(
        _fichier(dossier, texte),
        correspondance={"debut": 0, "fin": None, "duree": 1, "kwh": 2,
                        "unite": "kWh", "cout": 3})
    assert bilan["ajoutes"] == 2
    fins = sorted(x["fin"] for x in r.charger_donnees()["recharges"])
    assert fins == ["2026-03-02T06:00", "2026-03-06T01:30"]
    assert sorted(x["cout_wallbox"] for x in
                  r.charger_donnees()["recharges"]) == [2.0, 6.1]


def test_une_ligne_illisible_est_comptee(dossier):
    texte = AUTRE + "3,beaucoup,pas une date,2026-03-09T06:00:00,Moi\n"
    bilan = r.importer_csv_maison(_fichier(dossier, texte),
                                  correspondance=CORRESPONDANCE)
    assert (bilan["ajoutes"], bilan["non_reconnues"]) == (2, 1)


def test_des_dates_avec_fuseau_horaire(dossier):
    texte = ("Start;End;kWh\n"
             "2026-03-01T21:00:00Z;2026-03-02T05:00:00Z;30\n")
    bilan = r.importer_csv_maison(
        _fichier(dossier, texte),
        correspondance={"debut": 0, "fin": 1, "duree": None, "kwh": 2,
                        "unite": "kWh", "cout": None})
    assert bilan["ajoutes"] == 1
    # 21:00 temps universel = 22:00 heure de Paris en mars.
    debut = r.charger_donnees()["recharges"][0]["date"]
    attendu = datetime.fromisoformat("2026-03-01T21:00:00+00:00").astimezone(
        ).replace(tzinfo=None).isoformat(timespec="minutes")
    assert debut == attendu


def test_d_autres_formats_de_date():
    for texte in ("01.03.2026 22:00", "01.03.2026 22:00:00",
                  "2026-03-01T22:00", "01-03-2026 22:00"):
        assert r._date_csv(texte) == datetime(2026, 3, 1, 22, 0), texte


def test_une_correspondance_incomplete_est_refusee(dossier):
    with pytest.raises(ValueError, match="début"):
        r.importer_csv_maison(_fichier(dossier, AUTRE), correspondance=dict(
            CORRESPONDANCE, debut=None))
    with pytest.raises(ValueError, match="fin ou la durée"):
        r.importer_csv_maison(_fichier(dossier, AUTRE), correspondance=dict(
            CORRESPONDANCE, fin=None))


# ---------- le choix retenu ----------

def test_le_choix_est_retenu_pour_le_meme_modele(dossier):
    chemin = _fichier(dossier, AUTRE)
    r.retenir_correspondance(r.apercu_csv(chemin), CORRESPONDANCE)
    # Un autre fichier du meme modele (memes titres) : import direct.
    autre = _fichier(dossier, AUTRE.replace("2026-03", "2026-04"), "avril.csv")
    bilan = r.importer_csv_maison(autre)
    assert bilan["ajoutes"] == 2
    contenu = json.loads((dossier / "tarifs.json").read_text(encoding="utf-8"))
    assert contenu["tarifs"] == [PRIX_UNIQUE]            # le reste est garde


def test_le_format_d_origine_reste_reconnu_sans_rien_demander(dossier):
    texte = ("Chargeur;Début;Fin;Énergie;Durée;Coût €\n"
             "BORNE1;2026-03-01 22:00:00;2026-03-02 06:00:00;30.5;8:00;6.10\n")
    assert r.importer_csv_maison(_fichier(dossier, texte))["ajoutes"] == 1


def test_une_seule_ligne_est_au_singulier(dossier):
    """Audit du 08/10/2026 : « il contient 1 lignes de données »."""
    texte = "Quand;Combien\nhier;beaucoup\n"
    with pytest.raises(r.FormatCsvInconnu) as e:
        r.importer_csv_maison(_fichier(dossier, texte))
    assert "1 ligne de données" in str(e.value)
    assert "1 lignes" not in str(e.value)


def test_le_format_d_origine_en_wh_est_converti(dossier):
    """Audit du 08/10/2026 : un export a six colonnes dont le titre dit
    « (Wh) » etait lu en kWh — 12 500 Wh enregistres comme 12 500 kWh,
    sans un mot. Le titre de la colonne fait foi."""
    texte = ("Chargeur;Début;Fin;Énergie (Wh);Durée;Coût\n"
             "BORNE1;2026-03-01 22:00:00;2026-03-02 01:00:00;12500;3:00;0\n")
    assert r.importer_csv_maison(_fichier(dossier, texte))["ajoutes"] == 1
    (recharge,) = r.charger_donnees()["recharges"]
    assert recharge["kwh"] == pytest.approx(12.5)


def test_le_format_d_origine_en_kwh_n_est_pas_divise(dossier):
    """« kWh » contient « Wh » : il ne doit surtout pas etre divise."""
    texte = ("Chargeur;Début;Fin;Énergie (kWh);Durée;Coût\n"
             "BORNE1;2026-03-01 22:00:00;2026-03-02 01:00:00;12.5;3:00;0\n")
    r.importer_csv_maison(_fichier(dossier, texte))
    (recharge,) = r.charger_donnees()["recharges"]
    assert recharge["kwh"] == pytest.approx(12.5)


# ---------- la fenetre des colonnes ----------

def test_la_fenetre_des_colonnes(qapp, dossier):
    from dialogue_colonnes import DialogueColonnes
    fenetre = DialogueColonnes(None, r.apercu_csv(_fichier(dossier, AUTRE)))
    # Pre-remplie avec ce qui a ete devine.
    assert fenetre.correspondance() == CORRESPONDANCE
    fenetre.choix["cout"].setCurrentIndex(0)             # « (aucune) »
    fenetre.choix["unite"].setCurrentText("kWh")
    assert fenetre.correspondance()["unite"] == "kWh"
    # Sans colonne de debut, le bouton Importer refuse et le dit.
    fenetre.choix["debut"].setCurrentIndex(0)
    fenetre.valider()
    assert not fenetre.result() and "début" in fenetre.message.text()


def test_la_page_ouvre_la_fenetre_pour_un_format_inconnu(qapp, dossier,
                                                        monkeypatch):
    import fenetre as module_fenetre
    from pages import importer as im
    monkeypatch.setattr(module_fenetre, "charger_donnees",
                        lambda: {"recharges": []})
    f = module_fenetre.FenetrePrincipale()
    demandes = []

    def choisir(parent, apercu):
        demandes.append(apercu["entetes"])
        return CORRESPONDANCE
    monkeypatch.setattr(im, "demander_colonnes", choisir)
    page = im.construire(f)
    im.importer_fichier(f, str(_fichier(dossier, AUTRE)), page.resultat)
    assert demandes and page.resultat.text().startswith("OK : 2 ajoutées")
    # Le choix est retenu : le fichier suivant ne redemande rien.
    im.importer_fichier(f, str(_fichier(dossier, AUTRE.replace(
        "2026-03", "2026-05"), "mai.csv")), page.resultat)
    assert len(demandes) == 1
    f.deleteLater()


def test_la_page_annulee_ne_fait_rien(qapp, dossier, monkeypatch):
    import fenetre as module_fenetre
    from pages import importer as im
    monkeypatch.setattr(module_fenetre, "charger_donnees",
                        lambda: {"recharges": []})
    f = module_fenetre.FenetrePrincipale()
    monkeypatch.setattr(im, "demander_colonnes", lambda parent, apercu: None)
    page = im.construire(f)
    im.importer_fichier(f, str(_fichier(dossier, AUTRE)), page.resultat)
    assert "annulé" in page.resultat.text()
    assert r.charger_donnees()["recharges"] == []
    f.deleteLater()


def test_import_csv_refuse_nan_et_infinity(dossier):
    """Les nombres non finis ne doivent pas entrer dans les recharges."""
    texte = (
        "Chargeur;Début;Fin;Énergie;Durée;Coût\n"
        "BORNE1;2026-03-01 22:00:00;2026-03-02 06:00:00;NaN;8:00;6.10\n"
        "BORNE1;2026-03-03 22:00:00;2026-03-04 06:00:00;Infinity;8:00;6.10\n"
        "BORNE1;2026-03-05 22:00:00;2026-03-06 06:00:00;12.5;8:00;2.50\n"
    )
    bilan = r.importer_csv_maison(_fichier(dossier, texte))
    assert bilan["non_reconnues"] == 2
    recharges = r.charger_donnees()["recharges"]
    assert len(recharges) == 1
    assert recharges[0]["kwh"] == pytest.approx(12.5)
