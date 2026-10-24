"""Comparaison essence sur « Tout » ou sur une annee choisie (28/09/2026).

Les kilometres ne se connaissent qu'entre deux releves du compteur. Quand un
intervalle chevauche deux annees, ses kilometres sont partages au calendrier
(28/09/2026 : le partage selon l'energie rechargee, essaye d'abord, suivait
l'energie ENREGISTREE, et un utilisateur qui recharge souvent gratuitement
chez des proches obtenait des annees invraisemblables).
Un prix du litre par annee est facultatif ; a defaut, le prix general.
Donnees inventees.

    py -m pytest tests/test_essence_par_annee.py
"""

from __future__ import annotations

import json

import pytest

import recharges as r
from saisie import lire_releve_km

# Un premier intervalle a cheval sur 2024 et 2025 : 365 jours, dont 183 en
# 2024 et 182 en 2025, et 3 650 km (10 par jour). Puis un second tout en
# 2025 (5 000 km).
RELEVES = [
    {"id": "r1", "date": "2024-07-02T00:00", "km": 0.0},
    {"id": "r2", "date": "2025-07-02T00:00", "km": 3650.0},
    {"id": "r3", "date": "2025-12-31T23:00", "km": 8650.0},
]
RECHARGES = [
    {"id": "a", "date": "2024-09-10T22:00", "lieu": "maison", "kwh": 300.0,
     "cout_eur": 45.0},
    {"id": "b", "date": "2024-12-10T22:00", "lieu": "maison", "kwh": 300.0,
     "cout_eur": 45.0},
    {"id": "c", "date": "2025-03-10T22:00", "lieu": "exterieur",
     "kwh": 400.0, "cout_eur": 80.0},
    {"id": "d", "date": "2025-10-10T22:00", "lieu": "maison", "kwh": 750.0,
     "cout_eur": 100.0},
]
REGLAGE = {"conso_essence": 5.0, "prix_essence": 2.0,
           "prix_essence_annees": {}}


def comparer(periode, reglage=REGLAGE, releves=RELEVES, recharges=RECHARGES):
    return r.comparer_essence_periode(periode, reglage, releves, recharges)


# ---------- les kilometres de chaque annee ----------

def test_un_intervalle_a_cheval_se_partage_au_calendrier():
    annees = r.kilometres_par_annee(RELEVES, RECHARGES)
    # Intervalle 1 : 183 jours en 2024, 182 en 2025 -> 1 830 et 1 820 km,
    # quelle que soit l'energie rechargee de chaque cote. Intervalle 2, tout
    # en 2025 : 5 000 km. Le cout, lui, suit la date de chaque recharge.
    assert annees[2024]["km"] == 1830.0 and annees[2024]["cout"] == 90.0
    assert annees[2025]["km"] == 6820.0 and annees[2025]["cout"] == 180.0
    assert annees[2024]["debut"] == "2024-07-02T00:00"
    assert annees[2025]["fin"] == "2025-12-31T23:00"


def test_sans_energie_dans_l_intervalle_aussi():
    releves = [{"id": "x", "date": "2024-12-01T00:00", "km": 0.0},
               {"id": "y", "date": "2025-01-31T00:00", "km": 610.0}]
    annees = r.kilometres_par_annee(releves, [])
    # 31 jours en 2024, 30 en 2025.
    assert annees[2024]["km"] == 310.0 and annees[2025]["km"] == 300.0


def test_moins_de_deux_releves():
    assert r.kilometres_par_annee(RELEVES[:1], RECHARGES) == {}


# ---------- la comparaison ----------

def test_une_annee():
    c = comparer("2024")
    # 1 830 km a 5 L/100 = 91,5 L a 2 EUR = 183 EUR, contre 90 EUR.
    assert (c["km"], c["litres"], c["cout_essence"], c["cout_electrique"],
            c["economie"]) == (1830.0, 91.5, 183.0, 90.0, 93.0)


def test_tout_additionne_les_annees():
    c = comparer("Tout")
    assert c["km"] == 8650.0 and c["cout_essence"] == 865.0
    assert c["cout_electrique"] == 270.0
    assert [a["annee"] for a in c["par_annee"]] == [2024, 2025]
    assert c["debut"] == "2024-07-02T00:00" and c["fin"] == "2025-12-31T23:00"


def test_un_prix_par_annee():
    reglage = dict(REGLAGE, prix_essence_annees={"2024": 1.5})
    c = comparer("Tout", reglage)
    # 2024 : 91,5 L a 1,50 = 137,25 ; 2025 : 341 L a 2,00 (prix general)
    # = 682.
    assert c["cout_essence"] == 819.25
    assert [a["prix"] for a in c["par_annee"]] == [1.5, 2.0]
    assert c["prix_essence"] == 1.894                # moyen, pondere


def test_une_annee_sans_kilometres():
    assert comparer("2023") is None


def test_rien_sans_reglage():
    assert comparer("Tout", dict(REGLAGE, conso_essence=0)) is None
    assert comparer("Tout", dict(REGLAGE, prix_essence=0)) is None


def test_meme_resultat_qu_avant_quand_les_releves_sont_dans_une_annee():
    """Sans intervalle a cheval ni prix par annee, « Tout » redonne le
    calcul d'avant : km entre releves x consommation x prix."""
    releves = RELEVES[1:]
    c = comparer("Tout", releves=releves)
    assert c["km"] == 5000.0 and c["cout_electrique"] == 100.0
    assert c["cout_essence"] == 500.0


# ---------- les reglages ----------

@pytest.fixture
def fichier():
    r.TARIFS_FILE.write_text(json.dumps({"tarifs": []}), encoding="utf-8")
    yield r.TARIFS_FILE


def test_prix_par_annee_enregistres(fichier):
    assert r.charger_config()["prix_essence_annees"] == {}
    prix = r.valider_prix_annees({"2023": "1,87", "2024": " ", "2025": "1,8"})
    assert prix == {"2023": 1.87, "2025": 1.8}
    r.enregistrer_config({"prix_essence_annees": prix})
    assert r.charger_config()["prix_essence_annees"] == prix


@pytest.mark.parametrize("textes", [{"2023": "douze"}, {"2023": "9"}])
def test_prix_par_annee_refuses(textes):
    with pytest.raises(ValueError, match="2023"):
        r.valider_prix_annees(textes)


# ---------- le releve a 0 km ----------

def test_un_releve_a_zero_km_pour_une_voiture_neuve(fichier):
    lu = lire_releve_km("20/06/2023", "12:00", "0", "")
    assert lu["km"] == 0.0
    releve = r.ajouter_releve_km(0, "2023-06-20T12:00")
    assert releve["km"] == 0.0
    with pytest.raises(ValueError):
        r.ajouter_releve_km(-5, "2023-06-21T12:00")
    r.supprimer_releve_km(releve["id"])


# ---------- la page ----------

@pytest.fixture
def fenetre(qapp, monkeypatch):
    import fenetre as module_fenetre
    monkeypatch.setattr(module_fenetre, "charger_donnees",
                        lambda: {"recharges": RECHARGES})
    f = module_fenetre.FenetrePrincipale()
    yield f
    f.deleteLater()


def textes(widget) -> str:
    from PySide6.QtWidgets import QLabel
    return " ".join(e.text() for e in widget.findChildren(QLabel))


@pytest.fixture
def page_essence(monkeypatch):
    from pages import essence as es
    monkeypatch.setattr(es, "charger_donnees",
                        lambda: {"recharges": RECHARGES})
    monkeypatch.setattr(es, "charger_releves_km", lambda: RELEVES)
    monkeypatch.setattr(es, "charger_config", lambda: REGLAGE)
    return es


def test_la_page_sur_tout_montre_chaque_annee(fenetre, page_essence):
    fenetre.filtre_periode_essence = "Tout"
    page = page_essence.construire(fenetre)
    tout = textes(page)
    assert "865,00\xa0€" in tout and "270,00\xa0€" in tout
    assert len(page.lignes_annees) == 2


def test_la_page_sur_une_annee(fenetre, page_essence):
    fenetre.filtre_periode_essence = "2024"
    page = page_essence.construire(fenetre)
    tout = textes(page)
    assert "183,00\xa0€" in tout and "90,00\xa0€" in tout
    assert page.lignes_annees == []


def test_la_page_sur_une_annee_sans_releve(fenetre, page_essence):
    fenetre.filtre_periode_essence = "2023"
    page = page_essence.construire(fenetre)
    assert "relevé" in textes(page)


def test_la_page_s_ouvre_sur_tout(qapp):
    import fenetre as module_fenetre
    f = module_fenetre.FenetrePrincipale()
    assert f.filtre_periode_essence == "Tout"
    f.deleteLater()


# ---------- l'energie non enregistree (28/09/2026) ----------
# Un utilisateur qui recharge gratuitement chez des proches : cette energie
# manque aux recharges saisies. Le cout reste juste (elle ne coute rien),
# mais la comparaison doit le dire.

def test_la_part_d_energie_non_enregistree_est_signalee():
    # La voiture affiche 20 kWh/100 km ; a 100 % de rendement, 8 650 km
    # demandent 1 730 kWh. Les recharges n'en font que 1 750... -> rien.
    avec_conso = [dict(x) for x in RELEVES]
    avec_conso[-1]["conso"] = 20.0
    reglage = dict(REGLAGE, rendement_charge=1.0)
    assert comparer("Tout", reglage, releves=avec_conso)[
        "part_non_enregistree"] is None
    # A 40 kWh/100 km, il en faudrait 3 460 : environ la moitie manque.
    avec_conso[-1]["conso"] = 40.0
    c = comparer("Tout", reglage, releves=avec_conso)
    assert c["part_non_enregistree"] == 49


def test_sans_conso_affichee_pas_de_signalement():
    assert comparer("Tout")["part_non_enregistree"] is None


def test_la_carte_le_dit():
    from pages import kilometrage as km
    avec_conso = [dict(x) for x in RELEVES]
    avec_conso[-1]["conso"] = 40.0
    c = comparer("Tout", dict(REGLAGE, rendement_charge=1.0),
                 releves=avec_conso)
    tout = textes(km._carte_essence(c))
    # Audit du 14/10/2026 : une estimation, dont l'origine et le prix ne
    # sont pas connus ; la carte ne dit plus qu'elle « n'a rien coûté ».
    assert "49\xa0%" in tout and "prix ne sont pas connus" in tout
    assert "rien coûté" not in tout
