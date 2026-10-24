"""Importer, Exporter, Tarifs et fenetre de tarif de la version PySide6
(etape 6).

Donnees inventees ; les ecritures (import, export, tarifs) sont remplacees
par des doublures : jamais les vraies donnees.

    py -m pytest tests/test_qt_etape6.py
"""

from __future__ import annotations

from datetime import date

import pytest
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QDialog, QFileDialog

import dialogue_tarif as dt
import fenetre as module_fenetre
from pages import exporter as ex
from pages import importer as im
from pages import tarifs as ta
from saisie import ErreurSaisie, lire_plages, lire_tarif
from theme_qt import ALERTE_TEXTE, VERT

RECHARGES = [
    {"id": "a", "date": "2026-09-01T23:00", "lieu": "maison", "kwh": 20.0,
     "cout_eur": 3.0},
    {"id": "b", "date": "2026-09-02T12:00", "lieu": "exterieur", "kwh": 10.0,
     "cout_eur": 5.0},
    {"id": "c", "date": "2020-01-05T10:00", "lieu": "maison", "kwh": 7.0,
     "cout_eur": 1.0},
]

HP_HC = {"id": "t2", "nom": "Mon contrat HP/HC", "debut": "2026-08-01",
         "fin": None, "type": "hp_hc", "abonnement_mensuel": 20.50,
         "prix_hp": 0.2345, "prix_hc": 0.135,
         "plages_hc": [["23:45", "05:15"], ["14:15", "16:45"]],
         "_commentaire": "Grille d'essai, inventée."}
UNIQUE = {"id": "t1", "nom": "Tarif Bleu", "debut": "2025-02-01",
          "fin": "2025-12-31", "type": "simple", "abonnement_mensuel": 15.61,
          "prix_kwh": 0.2016}


@pytest.fixture
def fenetre(qapp, monkeypatch):
    donnees = lambda: {"recharges": RECHARGES}      # noqa: E731
    monkeypatch.setattr(ex, "charger_donnees", donnees)
    monkeypatch.setattr(module_fenetre, "charger_donnees", donnees)
    f = module_fenetre.FenetrePrincipale()
    yield f
    f.deleteLater()


# ---------- lecture d'un tarif (sans fenetre) ----------

def textes_tarif(**modifs):
    base = {"nom": "Mon contrat", "debut": "01/08/2026", "fin": "",
            "abonnement_mensuel": "20,50", "prix_kwh": "",
            "prix_hp": "0,2345", "prix_hc": "0,135",
            "plages_hc": "23:45-05:15, 14:15-16:45"}
    base.update(modifs)
    return base


def test_lire_tarif_hp_hc():
    assert lire_tarif(textes_tarif(), True) == {
        "nom": "Mon contrat", "debut": "2026-08-01", "fin": None,
        "abonnement_mensuel": 20.50, "type": "hp_hc", "prix_hp": 0.2345,
        "prix_hc": 0.135, "plages_hc": [["23:45", "05:15"],
                                        ["14:15", "16:45"]]}


def test_lire_tarif_prix_unique_et_abonnement_vide():
    t = lire_tarif(textes_tarif(prix_kwh="0,2016", abonnement_mensuel=""),
                   False)
    assert (t["type"], t["prix_kwh"], t["abonnement_mensuel"]) == \
        ("simple", 0.2016, 0.0)
    assert "plages_hc" not in t


@pytest.mark.parametrize("modifs, hp_hc, case", [
    ({"nom": " "}, True, "nom"),
    ({"debut": ""}, True, "debut"),
    ({"debut": "31/02/2026"}, True, "debut"),
    ({"fin": "01/07/2026"}, True, "fin"),          # avant le debut
    ({"abonnement_mensuel": "abc"}, True, "abonnement_mensuel"),
    ({"prix_kwh": ""}, False, "prix_kwh"),
    ({"prix_hp": "0"}, True, "prix_hp"),
    ({"plages_hc": ""}, True, "plages_hc"),
    ({"plages_hc": "22:00 06:00"}, True, "plages_hc"),
    ({"plages_hc": "25:00-06:00"}, True, "plages_hc"),
])
def test_lire_tarif_designe_la_case_fautive(modifs, hp_hc, case):
    with pytest.raises(ErreurSaisie) as e:
        lire_tarif(textes_tarif(**modifs), hp_hc)
    assert e.value.champ == case


def test_plages_ecrites_comme_ailleurs():
    assert lire_plages("22h-6h, 12h30-14:00") == [["22:00", "06:00"],
                                                  ["12:30", "14:00"]]


# ---------- fenetre de tarif ----------

@pytest.fixture
def grille(monkeypatch):
    """Doublures de la grille : on note ce qui serait ecrit."""
    notes = {"enregistres": [], "clotures": [], "ouvert": None}
    monkeypatch.setattr(dt, "charger_tarifs", lambda: [UNIQUE, HP_HC])
    monkeypatch.setattr(dt, "tarif_ouvert_avant",
                        lambda debut, sauf: notes["ouvert"])
    def enregistrer(tarif, ident, cloturer=None):
        # La cloture de l'ancien tarif part avec le nouveau (une ecriture).
        if cloturer:
            notes["clotures"].append((cloturer, tarif["debut"]))
        notes["enregistres"].append((tarif, ident))
        return []
    monkeypatch.setattr(dt, "enregistrer_tarif", enregistrer)
    return notes


def test_fenetre_pre_remplie(qapp, grille):
    d = dt.DialogueTarif(None, HP_HC)
    f = d.formulaire
    assert (f.texte("debut"), f.texte("fin")) == ("01/08/2026", "")
    assert f.texte("prix_hp") == "0,2345"
    assert f.texte("plages_hc") == "23:45-05:15, 14:15-16:45"
    assert d.choix_hp_hc.isChecked()
    assert d.bloc_unique.isHidden() and not d.bloc_hp_hc.isHidden()


def test_changer_de_type_ne_perd_pas_la_saisie(qapp, grille):
    d = dt.DialogueTarif(None, HP_HC)
    d.choix_unique.setChecked(True)
    assert d.bloc_hp_hc.isHidden()
    d.choix_hp_hc.setChecked(True)
    assert d.formulaire.texte("prix_hp") == "0,2345"


def test_enregistrer_sans_rien_toucher(qapp, grille):
    d = dt.DialogueTarif(None, UNIQUE)
    d.enregistrer()
    tarif, ident = grille["enregistres"][0]
    assert ident == "t1"
    assert {k: tarif[k] for k in UNIQUE} == UNIQUE
    assert d.result() == QDialog.Accepted


def test_les_notes_du_tarif_sont_gardees(qapp, grille):
    """Bug trouve le 25/09/2026 (aussi dans la 1.31.1) : enregistrer un
    tarif, meme sans rien y changer, effacait ses notes « _commentaire »
    de tarifs.json — la fenetre reconstruisait le tarif a partir de ses
    seules cases."""
    d = dt.DialogueTarif(None, HP_HC)
    d.enregistrer()
    tarif, _ = grille["enregistres"][0]
    assert tarif["_commentaire"] == HP_HC["_commentaire"]


def test_erreur_sous_la_case(qapp, grille):
    d = dt.DialogueTarif(None, HP_HC)
    d.formulaire.ecrire("plages_hc", "22h 6h")
    d.enregistrer()
    assert d.formulaire.message("plages_hc").startswith("Plage mal écrite")
    assert grille["enregistres"] == []


def test_refus_du_moteur_en_bas(qapp, grille):
    """Des plages qui se chevauchent : le moteur refuse, rien n'est ecrit,
    et le tarif precedent n'est pas ferme."""
    grille["ouvert"] = {"id": "t0", "nom": "Ancien"}
    d = dt.DialogueTarif(None, None)
    for nom, texte in textes_tarif(plages_hc="22:00-06:00, 05:00-07:00",
                                   debut="01/10/2026").items():
        d.formulaire.ecrire(nom, texte)
    d.choix_hp_hc.setChecked(True)
    d.enregistrer()
    assert "chevauchent" in d.message.text()
    assert grille["clotures"] == [] and grille["enregistres"] == []


def test_nouveau_tarif_ferme_le_precedent(qapp, grille, monkeypatch):
    grille["ouvert"] = {"id": "t0", "nom": "Ancien"}
    questions = []
    monkeypatch.setattr(dt, "confirmer", lambda *a, **k: (
        questions.append((a[2], k)) or True))
    d = dt.DialogueTarif(None, None)
    for nom, texte in textes_tarif(debut="01/10/2026").items():
        d.formulaire.ecrire(nom, texte)
    d.choix_hp_hc.setChecked(True)
    d.enregistrer()
    texte, boutons = questions[0]
    assert "le terminer le 30/09/2026" in texte
    # Boutons qui disent l'action ; elle est proposee par defaut, car elle
    # ne detruit rien (audit de design du 03/10/2026).
    assert boutons["action"] == "Le terminer le 30/09/2026"
    assert boutons["action_par_defaut"] is True
    assert grille["clotures"] == [("t0", "2026-10-01")]
    assert grille["enregistres"][0][1] is None


def test_premier_tarif_propose_le_1er_janvier(qapp, grille, monkeypatch):
    monkeypatch.setattr(dt, "charger_tarifs", lambda: [])
    d = dt.DialogueTarif(None, None)
    assert d.formulaire.texte("debut") == f"01/01/{date.today().year}"


def test_plage_courante_remplit_la_case(qapp, grille):
    d = dt.DialogueTarif(None, HP_HC)
    d._poser_plage(1)
    assert d.formulaire.texte("plages_hc") == "22:00-06:00"
    assert d.menu_plages.currentIndex() == 0


def test_entree_enregistre_une_seule_fois(qapp, grille):
    d = dt.DialogueTarif(None, UNIQUE)
    d.show()
    QTest.keyClick(d.formulaire.cases["nom"], Qt.Key_Return)
    assert len(grille["enregistres"]) == 1
    d.close()


# ---------- page Tarifs ----------

def test_textes_d_une_periode():
    assert ta.periode_du_tarif(HP_HC) == "depuis le 01/08/2026"
    assert ta.periode_du_tarif(UNIQUE) == "du 01/02/2025 au 31/12/2025"
    assert ta.detail_du_tarif(UNIQUE) == (
        "Abonnement 15,61\xa0€/mois  ·  0,2016\xa0€/kWh (prix unique)")
    assert "Plages HC : de 23:45 à 05:15 et de 14:15 à 16:45" in ta.detail_du_tarif(HP_HC)
    question = ta.question_suppression(UNIQUE, 12)
    assert question.startswith("Supprimer la période « Tarif Bleu » "
                               "(du 01/02/2025 au 31/12/2025) ?")
    assert "12 recharges" in question


def test_page_tarifs(fenetre, monkeypatch):
    monkeypatch.setattr(ta, "charger_tarifs", lambda: [UNIQUE, HP_HC])
    page = ta.construire(fenetre)
    assert len(page.periodes) == 2
    # La periode actuelle (la plus recente) en tete.
    premier = page.periodes[0].findChildren(ta.QLabel)
    assert HP_HC["nom"] in [e.text() for e in premier]
    assert hasattr(page, "bouton_recalculer")
    monkeypatch.setattr(ta, "charger_tarifs", lambda: [])
    page = ta.construire(fenetre)
    assert not hasattr(page, "bouton_recalculer")    # rien a recalculer


# test_reglages : parti dans tests/test_qt_parametres.py avec la carte
# des reglages (28/09/2026).


def test_apres_un_tarif_on_propose_de_recalculer(fenetre, monkeypatch):
    class Fausse:
        avertissements = ["Il manque une période."]

        def __init__(self, parent, tarif):
            pass

        def exec(self):
            return QDialog.Accepted
    monkeypatch.setattr(ta, "DialogueTarif", Fausse)
    vus = []
    monkeypatch.setattr(ta.QMessageBox, "warning",
                        lambda *a, **k: vus.append(a[1]))
    monkeypatch.setattr(ta, "confirmer",
                        lambda *a, **k: vus.append(a[1]) or True)
    monkeypatch.setattr(ta.QMessageBox, "information",
                        lambda *a, **k: vus.append(a[2]))
    monkeypatch.setattr(ta, "recalculer_tout", lambda: (42, []))
    ta.ouvrir_tarif(fenetre, None)
    assert vus == ["Grille tarifaire", "Recalculer les coûts ?",
                   "42 recharges recalculées."]


def test_supprimer_une_periode_non_par_defaut(fenetre, monkeypatch):
    supprimes = []
    monkeypatch.setattr(ta, "recharges_du_tarif", lambda ident: 0)
    monkeypatch.setattr(ta, "supprimer_tarif",
                        lambda ident: supprimes.append(ident) or True)
    questions = []
    monkeypatch.setattr(ta, "confirmer", lambda *a, **k: (
        questions.append(k) or False))
    ta.supprimer_la_periode(fenetre, UNIQUE)
    assert supprimes == []
    # « Garder » par defaut (confirmer ne propose jamais l'action par
    # defaut sans qu'on le demande) ; le bouton dit l'action.
    assert questions[0]["action"] == "Supprimer la période"
    assert not questions[0].get("action_par_defaut")


# ---------- Importer ----------

def test_compte_rendu_d_import():
    res = {"ajoutes": 0, "remplaces": 0, "doublons": 182, "zero_kwh": 3,
           "parasites": 2, "total_lus": 187}
    texte, alerte = im.texte_resultat(res)
    assert texte == ("OK : 0 ajoutées, 0 saisies manuelles remplacées, 182 "
                     "doublons, 3 ignorées, 2 branchements sans recharge "
                     "écartés, 187 lues   (rien de nouveau : le fichier n'a "
                     "pas été modifié)")
    assert not alerte
    texte, alerte = im.texte_resultat(dict(res, ajoutes=5, non_reconnues=2))
    assert alerte and "ATTENTION : 2 lignes non reconnues" in texte
    une_ligne, _ = im.texte_resultat(dict(res, non_reconnues=1))
    assert "ATTENTION : 1 ligne non reconnue, donc pas enregistrée." in une_ligne
    assert "rien de nouveau" not in texte


def test_page_importer(fenetre, monkeypatch, tmp_path):
    (tmp_path / "borne.csv").write_text("x", encoding="utf-8")
    monkeypatch.setattr(im, "dossier_donnees", lambda: tmp_path)
    appels = []
    monkeypatch.setattr(im, "importer_csv_maison", lambda chemin: (
        appels.append(chemin) or {"ajoutes": 1, "remplaces": 0, "doublons": 0,
                                  "zero_kwh": 0, "total_lus": 1}))
    page = im.construire(fenetre)
    assert len(page.boutons_fichiers) == 1
    page.boutons_fichiers[0].click()
    assert appels == [str(tmp_path / "borne.csv")]
    assert VERT in page.resultat.styleSheet()


def test_import_rate_en_orange(fenetre, monkeypatch, tmp_path):
    monkeypatch.setattr(im, "dossier_donnees", lambda: tmp_path)

    def refus(chemin):
        raise ValueError("Aucune recharge reconnue. NE LE SUPPRIMEZ PAS.")
    monkeypatch.setattr(im, "importer_csv_maison", refus)
    monkeypatch.setattr(QFileDialog, "getOpenFileName",
                        lambda *a: ("C:/borne.csv", ""))
    page = im.construire(fenetre)
    assert page.boutons_fichiers == []         # aucun CSV dans le dossier
    page.bouton_choisir.click()
    assert page.resultat.text().startswith("Erreur : Aucune recharge")
    assert ALERTE_TEXTE in page.resultat.styleSheet()


# ---------- Exporter ----------

def test_recharges_a_exporter_et_nom():
    assert [r["id"] for r in ex.recharges_a_exporter(RECHARGES, "Maison",
                                                     "Tout")] == ["a", "c"]
    assert ex.nom_propose("Extérieur", ".pdf", date(2026, 9, 25)) == \
        "recharges_extérieur_20260925.pdf"


def test_page_exporter(fenetre, monkeypatch, tmp_path):
    fenetre.filtre_lieu_export, fenetre.filtre_periode_export = "Tout", "Tout"
    faits = []
    monkeypatch.setitem(ex.FORMATS, "excel", (
        "Exporter en Excel", ".xlsx", "Excel (*.xlsx)",
        lambda recharges, chemin, titre, complements: faits.append(
            (len(recharges), titre)) or chemin))
    monkeypatch.setattr(QFileDialog, "getSaveFileName",
                        lambda *a: (str(tmp_path / "essai.xlsx"), ""))
    page = ex.construire(fenetre)
    assert page.apercu.text() == "3 recharges · 37,00\xa0kWh · 9,00\xa0€"
    page.boutons["excel"].click()
    assert faits == [(3, "Tous les lieux · Toute la période")]
    assert page.resultat.text() == "OK : 3 recharges exportées vers essai.xlsx"


def test_exporter_rien(fenetre):
    fenetre.filtre_periode_export = "2019"
    page = ex.construire(fenetre)
    page.boutons["pdf"].click()
    assert page.resultat.text() == "Aucune recharge à exporter."


def test_export_annule(fenetre, monkeypatch):
    fenetre.filtre_periode_export = "Tout"
    monkeypatch.setattr(QFileDialog, "getSaveFileName", lambda *a: ("", ""))
    page = ex.construire(fenetre)
    page.boutons["pdf"].click()
    assert page.resultat.isHidden()
