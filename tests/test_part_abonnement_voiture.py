"""Part de l'abonnement liee a la voiture (10/10/2026).

Un reglage facultatif de la page Parametres, en pour cent : la part de
l'abonnement de la maison que l'utilisateur attribue a la voiture (par
exemple sa part des kWh achetes au reseau). Le tableau de bord l'affiche
sur une ligne a part, sous l'abonnement ; elle n'entre jamais dans le cout
des recharges ni dans le prix du kWh. Case vide : 0, pas de ligne.
Enregistre dans tarifs.json, cle « part_abonnement_voiture ».
Donnees inventees, dans le dossier temporaire de tests/conftest.py.

    py -m pytest tests/test_part_abonnement_voiture.py
"""

from __future__ import annotations

import json

import pytest

import recharges as r

# Une grille inventee, ronde : 30 EUR par mois.
GRILLE = {"id": "essai", "nom": "Essai", "debut": "2025-01-01", "fin": None,
          "type": "simple", "abonnement_mensuel": 30.0, "prix_kwh": 0.2}


@pytest.fixture
def fichier():
    """Un tarifs.json neuf, avec une grille et un reglage a conserver."""
    r.TARIFS_FILE.write_text(json.dumps(
        {"tarifs": [GRILLE], "capacite_batterie": 50}), encoding="utf-8")
    yield r.TARIFS_FILE


# ---------- la saisie ----------

def test_saisie_a_la_francaise():
    assert r.valider_part_abonnement("25,5") == {
        "part_abonnement_voiture": 25.5}


def test_case_vide_vaut_zero():
    assert r.valider_part_abonnement("  ") == {"part_abonnement_voiture": 0.0}


@pytest.mark.parametrize("texte", ["beaucoup", "-5", "120"])
def test_saisies_refusees_avec_un_message_clair(texte):
    with pytest.raises(ValueError, match="Part de l'abonnement"):
        r.valider_part_abonnement(texte)


def test_ancien_fichier_sans_la_cle(fichier):
    """Les fichiers d'avant le 10/10/2026 n'ont pas la cle : 0, rien ne
    change pour eux."""
    assert r.charger_config()["part_abonnement_voiture"] == 0.0


def test_enregistrer_puis_relire_sans_toucher_au_reste(fichier):
    r.enregistrer_config(r.valider_part_abonnement("40"))
    assert r.charger_config()["part_abonnement_voiture"] == 40.0
    d = json.loads(fichier.read_text(encoding="utf-8"))
    assert d["capacite_batterie"] == 50
    assert d["tarifs"] == [GRILLE]


# ---------- le tableau de bord ----------

def test_la_part_est_calculee_sur_l_abonnement_de_la_periode(fichier):
    from pages import tableau_de_bord as tb
    r.enregistrer_config({"part_abonnement_voiture": 40.0})
    recharge = {"id": "x", "date": "2025-03-12T23:00", "lieu": "maison",
                "kwh": 10.0, "cout_eur": 2.0}
    m = tb.chiffres_de_la_periode([recharge], "Mars 2025")["maison"]
    assert m["abonnement"]["total"] == 30.0
    assert m["part_voiture"] == {"pct": 40.0, "montant": 12.0}
    # Le cout des recharges ne bouge pas.
    assert m["cout"] == 2.0


def test_sans_reglage_pas_de_part(fichier):
    from pages import tableau_de_bord as tb
    m = tb.chiffres_de_la_periode([], "Mars 2025")["maison"]
    assert m["part_voiture"] is None


def test_la_ligne_du_bloc_maison():
    from pages import tableau_de_bord as tb
    assert tb.ligne_part_voiture({"pct": 32.0, "montant": 6.4}) == (
        "dont part de la voiture (32\xa0%) : 6,40\xa0€")
    assert tb.ligne_part_voiture({"pct": 25.5, "montant": 1234.5}) == (
        "dont part de la voiture (25,5\xa0%) : 1\xa0234,50\xa0€")


# ---------- la page Parametres ----------

def test_la_page_parametres_enregistre_la_part(qapp, fichier, monkeypatch):
    import fenetre as module_fenetre
    from pages import parametres as pa
    from theme_qt import ROUGE
    monkeypatch.setattr(module_fenetre, "charger_donnees",
                        lambda: {"recharges": []})
    f = module_fenetre.FenetrePrincipale()
    try:
        page = pa.construire(f)
        page.case_part.setText("150")
        page.bouton_part.click()
        assert ROUGE in page.message_part.styleSheet()
        assert r.charger_config()["part_abonnement_voiture"] == 0.0
        page.case_part.setText("32")
        page.bouton_part.click()
        assert page.message_part.text() == "✓ Part enregistrée."
        assert r.charger_config()["part_abonnement_voiture"] == 32.0
    finally:
        f.deleteLater()


def test_le_texte_dit_que_l_abonnement_reste_affiche(qapp, fichier,
                                                    monkeypatch):
    """Case vide, le tableau de bord affiche toujours l'abonnement entier :
    seule la ligne « dont part de la voiture » disparait. L'ancien texte,
    « Case vide : rien n'est affiché », laissait croire que l'abonnement
    disparaissait aussi (vu a l'ecran le 11/10/2026)."""
    from PySide6.QtWidgets import QLabel

    import fenetre as module_fenetre
    from pages import parametres as pa
    monkeypatch.setattr(module_fenetre, "charger_donnees",
                        lambda: {"recharges": []})
    f = module_fenetre.FenetrePrincipale()
    try:
        page = pa.construire(f)
        textes = " ".join(e.text() for e in page.findChildren(QLabel))
        assert "rien n'est affiché" not in textes
        assert ("Case vide : l'abonnement reste affiché en entier, sans la "
                "part de la voiture.") in textes
    finally:
        f.deleteLater()
