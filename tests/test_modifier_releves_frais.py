"""Modifier un releve kilometrique ou des frais de carte (analyse du
16/10/2026, point 3).

Jusqu'ici, une faute imposait de supprimer puis de recreer l'entree. Un
bouton « Modifier » corrige directement, avec les memes controles qu'a la
saisie (un compteur ne recule pas, un montant est positif...). L'entree
garde son identifiant : rien ne change dans le format des fichiers.

Donnees inventees, dans le dossier temporaire de tests/conftest.py.

    py -m pytest tests/test_modifier_releves_frais.py
"""

from __future__ import annotations

import json

import pytest
from PySide6.QtWidgets import QDialog

import recharges as r

ACHAT = {"carte": "Réseau A", "type": "unique", "date": "2025-03-10",
         "fin": None, "montant": 20.0}


@pytest.fixture
def releves():
    """Trois releves inventes, croissants."""
    r.DATA_FILE.write_text(json.dumps({"recharges": [], "releves_km": [
        {"id": "k1", "date": "2026-01-05T10:00", "km": 1000.0, "conso": 16.0},
        {"id": "k2", "date": "2026-02-05T10:00", "km": 2000.0},
        {"id": "k3", "date": "2026-03-05T10:00", "km": 3000.0},
    ]}), encoding="utf-8")
    r.vider_cache()
    yield
    r.vider_cache()


@pytest.fixture
def frais():
    r.TARIFS_FILE.write_text(json.dumps(
        {"tarifs": [], "capacite_batterie": 50}), encoding="utf-8")
    r.vider_cache()
    yield r.ajouter_frais_carte(ACHAT)


# ---------- le moteur : releves ----------

def test_modifier_un_releve_garde_son_identifiant(releves):
    r.modifier_releve_km("k2", 2100, "2026-02-06T09:30", 15.5)
    k2 = next(x for x in r.charger_releves_km() if x["id"] == "k2")
    assert k2 == {"id": "k2", "date": "2026-02-06T09:30", "km": 2100.0,
                  "conso": 15.5}
    assert len(r.charger_releves_km()) == 3


def test_vider_la_consommation_la_retire(releves):
    r.modifier_releve_km("k1", 1000, "2026-01-05T10:00", None)
    k1 = next(x for x in r.charger_releves_km() if x["id"] == "k1")
    assert "conso" not in k1


def test_le_releve_corrige_ne_se_compare_pas_a_lui_meme(releves):
    """Corriger seulement la consommation, au meme kilometrage et a la meme
    date : ce n'est pas « un releve qui existe deja »."""
    r.modifier_releve_km("k3", 3000, "2026-03-05T10:00", 17.0)
    assert r.charger_releves_km()[-1]["conso"] == 17.0


@pytest.mark.parametrize("km, quand, morceau", [
    (900, "2026-02-05T10:00", "ne peut pas diminuer"),
    (3500, "2026-02-05T10:00", "plus ancien ne peut pas"),
    (-1, "2026-02-05T10:00", "négatif"),
])
def test_un_releve_modifie_reste_coherent(releves, km, quand, morceau):
    with pytest.raises(ValueError, match=morceau):
        r.modifier_releve_km("k2", km, quand, None)
    k2 = next(x for x in r.charger_releves_km() if x["id"] == "k2")
    assert k2["km"] == 2000.0                       # rien n'a change


def test_une_consommation_hors_des_clous_est_refusee(releves):
    with pytest.raises(ValueError, match="entre 5 et"):
        r.modifier_releve_km("k2", 2000, "2026-02-05T10:00", 90)


def test_un_releve_introuvable(releves):
    with pytest.raises(ValueError, match="introuvable"):
        r.modifier_releve_km("absent", 2000, "2026-02-05T10:00", None)


# ---------- le moteur : frais de cartes ----------

def test_modifier_des_frais_garde_leur_identifiant(frais):
    r.modifier_frais_carte(frais["id"], {
        "carte": "Réseau B", "type": "mensuel", "date": "2025-04-01",
        "fin": "2025-06-30", "montant": 6.0})
    tous = r.charger_frais_cartes()
    assert len(tous) == 1
    assert tous[0] == {"id": frais["id"], "carte": "Réseau B",
                       "type": "mensuel", "date": "2025-04-01",
                       "fin": "2025-06-30", "montant": 6.0}


def test_des_frais_modifies_restent_valides(frais):
    with pytest.raises(ValueError, match="supérieur à zéro"):
        r.modifier_frais_carte(frais["id"], dict(ACHAT, montant=0))
    assert r.charger_frais_cartes()[0]["montant"] == 20.0


def test_des_frais_introuvables(frais):
    with pytest.raises(ValueError, match="introuvables"):
        r.modifier_frais_carte("absent", ACHAT)


def test_modifier_des_frais_garde_le_reste_du_fichier(frais):
    r.modifier_frais_carte(frais["id"], dict(ACHAT, montant=25))
    contenu = json.loads(r.TARIFS_FILE.read_text(encoding="utf-8"))
    assert contenu["capacite_batterie"] == 50


# ---------- les fenetres ----------

@pytest.fixture
def fenetre(qapp):
    import fenetre as module_fenetre
    f = module_fenetre.FenetrePrincipale()
    yield f
    f.deleteLater()


def test_la_fenetre_du_releve_est_preremplie_et_enregistre(
        releves, fenetre):
    from dialogue_km_frais import DialogueReleve
    k1 = r.charger_releves_km()[0]
    d = DialogueReleve(fenetre, k1)
    f = d.formulaire
    assert f.texte("champ_km_date_jour") == "05/01/2026"
    assert f.texte("champ_km_date_heure") == "10:00"
    assert f.texte("champ_km_valeur") == "1000"
    assert f.texte("champ_km_conso") == "16"
    f.ecrire("champ_km_valeur", "1050")
    d.enregistrer()
    assert d.result() == QDialog.Accepted
    assert r.charger_releves_km()[0]["km"] == 1050.0


def test_la_fenetre_du_releve_refuse_un_compteur_qui_recule(
        releves, fenetre):
    from dialogue_km_frais import DialogueReleve
    d = DialogueReleve(fenetre, r.charger_releves_km()[1])
    d.formulaire.ecrire("champ_km_valeur", "500")
    d.enregistrer()
    assert d.result() != QDialog.Accepted
    assert "ne peut pas diminuer" in d.formulaire.message("champ_km_valeur")
    assert r.charger_releves_km()[1]["km"] == 2000.0


def test_la_fenetre_des_frais_est_preremplie_et_enregistre(frais, fenetre):
    from dialogue_km_frais import DialogueFrais
    d = DialogueFrais(fenetre, frais)
    f = d.formulaire
    assert f.texte("carte") == "Réseau A"
    assert f.texte("date") == "10/03/2025"
    assert f.texte("montant") == "20"
    assert d.choix_type.currentData() == "unique"
    assert not f.cases["fin"].isEnabled()
    assert d.libelle_montant.text() == "Montant (€)"
    d.choix_type.setCurrentIndex(d.choix_type.findData("annuel"))
    assert f.cases["fin"].isEnabled()
    assert d.libelle_montant.text() == "Montant (€ par an)"
    f.ecrire("montant", "30,5")
    d.enregistrer()
    assert d.result() == QDialog.Accepted
    tous = r.charger_frais_cartes()
    assert (tous[0]["type"], tous[0]["montant"]) == ("annuel", 30.5)


def test_la_fenetre_des_frais_refuse_un_montant_illisible(frais, fenetre):
    from dialogue_km_frais import DialogueFrais
    d = DialogueFrais(fenetre, frais)
    d.formulaire.ecrire("montant", "douze")
    d.enregistrer()
    assert d.result() != QDialog.Accepted
    assert "n'est pas un nombre" in d.formulaire.message("montant")


def test_chaque_releve_a_son_bouton_modifier(releves, fenetre):
    from pages import kilometrage as km
    page = km.construire(fenetre)
    textes = [b.text() for b in page.findChildren(km.QPushButton)]
    assert textes.count("Modifier…") == 3


def test_mes_releves_tient_dans_une_fenetre_de_1000_px(releves, fenetre):
    """Avec « Modifier… » et « Supprimer », l'en-tete « Parcourus depuis le
    relevé précédent » (247 px) faisait deborder la page de 104 px a 1 000 px
    (deja 18 px avant ces boutons). Il devient « Parcourus », le detail au
    survol. La largeur elle-meme se mesure hors des tests (les polices
    manquent a l'affichage « offscreen ») : voir le JOURNAL du 16/10/2026."""
    from pages import kilometrage as km
    from PySide6.QtWidgets import QTableWidget
    assert km.ENTETES_RELEVES[2] == "Parcourus"
    page = km.construire(fenetre)
    table = [t for t in page.findChildren(QTableWidget)
             if t.horizontalHeaderItem(0).text() == "Date"][0]
    assert "relevé précédent" in table.horizontalHeaderItem(2).toolTip()


def test_chaque_frais_a_son_bouton_modifier(frais, fenetre):
    from pages import tarifs as ta
    page = ta.construire(fenetre)
    assert page.lignes_frais[0].bouton_modifier.text() == "Modifier…"
