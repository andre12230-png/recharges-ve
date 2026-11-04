"""Textes affichés (contrôle du 04/11/2026, écarts X1 à X6 et A1).

X1 : faute dans le bandeau de recalcul (« Le coût de recharges »).
X2 : la notice décrivait mal le bouton « Mise à jour », qui ouvre d'abord
     une petite fenêtre à deux boutons.
X3 : des titres de boîte trop vagues (« Restauration », « Recalcul »).
X4 : des guillemets anglais dans deux messages de tarifs.json.
X5 : des espaces en trop dans trois libellés de cases.
X6 : « COÛT RECHARGES » sur le tableau de bord, « COÛT DES RECHARGES »
     sur la page Kilométrage.
A1 : l'autotest passait même quand la traduction de Qt manquait.

Données inventées, dans le dossier temporaire de tests/conftest.py.

    py -m pytest tests/test_textes_affiches.py
"""

from __future__ import annotations

import ast
import json
from datetime import datetime
from pathlib import Path

import pytest
from PySide6.QtWidgets import QLabel

import recharges as r

RACINE = Path(__file__).resolve().parent.parent
BASE = {"nom": "Base", "debut": "2026-01-01", "fin": None, "type": "simple",
        "abonnement_mensuel": 10.0, "prix_kwh": 0.2}


@pytest.fixture
def donnees():
    r.vider_cache()
    r.TARIFS_FILE.write_text(json.dumps({"tarifs": []}), encoding="utf-8")
    r.sauvegarder_donnees({"recharges": []})
    yield


@pytest.fixture
def fenetre(qapp, donnees):
    import fenetre as module_fenetre
    f = module_fenetre.FenetrePrincipale()
    yield f
    f.deleteLater()


def recharge_sans_tarif():
    """Une recharge maison que plus aucun tarif ne couvre : le recalcul la
    laisse à son ancien coût, et le rappel reste affiché."""
    r.enregistrer_tarif(dict(BASE))
    r.ajouter_recharge_maison(datetime(2026, 3, 2, 22, 0),
                              datetime(2026, 3, 3, 1, 0), 20.0)
    base = r.charger_tarifs()[0]
    r.enregistrer_tarif(dict(BASE, debut="2026-04-01"), id_origine=base["id"])


def textes_des_libelles(widget) -> str:
    return " ".join(e.text() for e in widget.findChildren(QLabel))


# ---------- X1 ----------

def test_bandeau_de_recalcul_sans_faute(fenetre):
    from pages import tarifs as ta
    recharge_sans_tarif()
    bandeau = ta.bandeau_recalcul(fenetre, lambda: None)
    texte = textes_des_libelles(bandeau)
    assert "Le coût des recharges à la maison" in texte
    assert "coût de recharges" not in texte


# ---------- X2 ----------

def test_notice_decrit_la_fenetre_de_mise_a_jour():
    import notice_texte
    texte = " ".join(c for _, rubriques in notice_texte.SECTIONS
                     for titre, c in rubriques if titre == "Mise à jour")
    assert "Voir les nouveautés" in texte
    assert "Télécharger l'installeur" in texte


# ---------- X3 ----------

def test_titre_d_un_recalcul_incomplet(fenetre, monkeypatch):
    from pages import tarifs as ta
    recharge_sans_tarif()
    titres = []
    monkeypatch.setattr(ta.QMessageBox, "warning",
                        lambda parent, titre, *a, **k: titres.append(titre))
    ta.recalculer_les_couts(fenetre)
    assert titres == ["Recalcul incomplet"]


def test_titre_d_une_restauration_ratee(fenetre, monkeypatch):
    from pages import restaurer as re_
    titres = []
    monkeypatch.setattr(re_, "confirmer", lambda *a, **k: True)

    def en_panne(chemin):
        raise ValueError("Sauvegarde illisible.")
    monkeypatch.setattr(re_, "restaurer_backup", en_panne)
    monkeypatch.setattr(re_.QMessageBox, "critical",
                        lambda parent, titre, *a, **k: titres.append(titre))
    re_._restaurer(fenetre, {"date": datetime(2026, 3, 2, 22, 0),
                             "n_recharges": 3, "chemin": "inexistant.json"})
    assert titres == ["Restauration impossible"]


# ---------- X4 ----------

@pytest.mark.parametrize("contenu", [{"autre": 1}, {"tarifs": 12}])
def test_messages_de_tarifs_json_en_guillemets_francais(donnees, contenu):
    r.TARIFS_FILE.write_text(json.dumps(contenu), encoding="utf-8")
    with pytest.raises(ValueError) as erreur:
        r.charger_tarifs()
    assert "« tarifs »" in str(erreur.value)
    assert '"tarifs"' not in str(erreur.value)


# ---------- X5 ----------

@pytest.mark.parametrize("fichier", ["dialogue_tarif.py", "pages/ajouter.py"])
def test_libelles_sans_espaces_en_trop(fichier):
    arbre = ast.parse((RACINE / fichier).read_text(encoding="utf-8"))
    fautifs = [n.value for n in ast.walk(arbre)
               if isinstance(n, ast.Constant) and isinstance(n.value, str)
               and "  (" in n.value]
    assert fautifs == []


# ---------- X6 ----------

def test_tuile_du_cout_des_recharges(fenetre):
    from pages import tableau_de_bord as tb
    page = tb.construire(fenetre)
    libelles = " ".join(textes_des_libelles(t) for t in page.tuiles)
    assert "COÛT DES RECHARGES" in libelles


# ---------- A1 ----------

def test_autotest_signale_la_traduction_absente(qapp, tmp_path, monkeypatch):
    import fenetre as module_fenetre
    ancien = r.dossier_donnees()
    monkeypatch.setattr(module_fenetre, "installer_traduction_qt",
                        lambda application: False)
    rapport = tmp_path / "rapport.txt"
    try:
        assert module_fenetre.autotest(str(rapport)) == 1
    finally:
        r.rediriger_donnees(ancien)
    assert "boutons Qt     : EN ANGLAIS (qtbase_fr absent)" in \
        rapport.read_text(encoding="utf-8")
