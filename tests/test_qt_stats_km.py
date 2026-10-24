"""Statistiques et Kilometrage de la version PySide6 (etape 5).

Donnees inventees, injectees a la place des fonctions de lecture ; les
ecritures (releve ajoute, supprime) sont remplacees par des doublures :
jamais les vraies donnees.

    py -m pytest tests/test_qt_stats_km.py
"""

from __future__ import annotations

from datetime import datetime

import pytest
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QLabel

import fenetre as module_fenetre
from pages import kilometrage as km
from pages import statistiques as st
from saisie import ErreurSaisie, lire_releve_km
from theme_qt import ALERTE_TEXTE, ROUGE, VERT

ANNEE = str(datetime.now().year)

RECHARGES = [
    {"id": "a", "date": f"{ANNEE}-01-10T23:00", "lieu": "maison", "kwh": 20.0,
     "cout_eur": 3.0, "tarif_nom": "Mon contrat", "cout_wallbox": 4.0},
    {"id": "b", "date": f"{ANNEE}-03-02T12:00", "lieu": "exterieur",
     "kwh": 10.0, "cout_eur": 5.0, "operateur": "Ionity", "carte": ""},
    {"id": "c", "date": f"{ANNEE}-03-20T09:00", "lieu": "exterieur",
     "kwh": 30.0, "cout_eur": 18.0, "operateur": "E.Leclerc",
     "carte": "Chargemap"},
    {"id": "d", "date": "2020-01-05T10:00", "lieu": "maison", "kwh": 7.0,
     "cout_eur": 1.0, "tarif_nom": "Ancien"},
]


def textes(widget) -> list[str]:
    return [e.text() for e in widget.findChildren(QLabel)]


# ---------- Statistiques : les calculs ----------

def test_par_mois_garde_les_mois_vides():
    mois, kwh, cout = st.par_mois(RECHARGES[:3])
    assert mois == [f"{ANNEE}-01", f"{ANNEE}-02", f"{ANNEE}-03"]
    assert kwh == [20.0, 0.0, 40.0]
    assert cout == [3.0, 0.0, 23.0]


def test_repartitions_du_plus_cher_au_moins_cher():
    blocs = dict(st.repartitions(RECHARGES[:3]))
    operateurs = blocs["Répartition par opérateur (extérieur)"]
    assert [nom for nom, _ in operateurs] == ["E.Leclerc", "Ionity"]
    assert operateurs[0][1] == "1 recharge · 30,00\xa0kWh · 18,00\xa0€ · 0,6000\xa0€/kWh"
    # Sans carte : « Non précisé » (accentué le 19/10/2026).
    cartes = dict(blocs["Répartition par carte / moyen de paiement (extérieur)"])
    assert "Non précisé" in cartes


def test_une_repartition_vide_n_est_pas_rendue():
    titres = [t for t, _ in st.repartitions(RECHARGES[:1])]
    assert titres == ["Répartition par tarif"]


def test_ecart_wallbox():
    # La recharge « d » (1 €) n'a pas de montant wallbox : elle reste hors
    # de la comparaison. Ce test attendait 4 € de « reel » avant le
    # diagnostic du 26/09/2026 : il entérinait le défaut.
    assert st.ecart_wallbox(RECHARGES) == {"wallbox": 4.0, "reel": 3.0,
                                           "ecart": -1.0, "n": 1}
    assert st.ecart_wallbox(RECHARGES[1:]) is None


# ---------- Statistiques : la page ----------

@pytest.fixture
def fenetre(qapp, monkeypatch):
    donnees = lambda: {"recharges": RECHARGES}      # noqa: E731
    monkeypatch.setattr(st, "charger_donnees", donnees)
    monkeypatch.setattr(module_fenetre, "charger_donnees", donnees)
    f = module_fenetre.FenetrePrincipale()
    yield f
    f.deleteLater()


def test_page_statistiques(fenetre):
    page = st.construire(fenetre)
    assert page.barre.annuel                      # l'annee seulement
    assert page.resume.text().startswith("3 recharges · 60,00\xa0kWh · 26,00\xa0€")
    assert page.graphique.height() == 320
    assert len(page.repartitions) == 3
    # Audit de design du 03/10/2026 : « Écart : -24,76 € » en vert ne
    # disait pas qui etait le moins cher ; « wallbox » n'etait pas traduit.
    tout = " ".join(textes(page.wallbox))
    assert "VOTRE BORNE FACE AU TARIF RÉEL" in tout
    assert "que l'estimation de votre borne" in tout
    assert "wallbox" not in tout.lower() and "Écart :" not in tout


def test_statistiques_sans_donnees(fenetre):
    fenetre.filtre_periode_stats = "2019"
    page = st.construire(fenetre)
    from filtres import conseil_si_vide
    assert ("Aucune donnée sur la période « 2019 ».\n" + conseil_si_vide(False)
            in textes(page))
    assert not hasattr(page, "graphique")


def test_statistiques_sans_aucune_recharge(fenetre, monkeypatch):
    """Nouvel utilisateur : la page dit comment commencer (audit 08/10/2026)."""
    from filtres import conseil_si_vide
    monkeypatch.setattr(st, "charger_donnees", lambda: {"recharges": []})
    page = st.construire(fenetre)
    assert any(conseil_si_vide(True) in t for t in textes(page))


def test_changer_d_annee_reconstruit_la_page(fenetre):
    fenetre.afficher_vue("stats")
    page = fenetre.zone_page.widget().layout().itemAt(0).widget()
    appels = []
    fenetre.changer_periode = lambda attribut, valeur: appels.append(
        (attribut, valeur))
    page.barre.periode_changee.emit("2020")
    assert appels == [("filtre_periode_stats", "2020")]


# ---------- Kilometrage : les textes ----------

CONTROLE = {"conso_reference": 15.9, "kwh_batterie": 339.4,
            "kwh_attendu": 376.2, "rendement": 0.9, "ecart_kwh": -125.8,
            "ecart_pct": -33.5, "conso_enregistree": 10.6, "marge_kwh": 71.0,
            "capacite_batterie": 64.0}


def test_controle_non_configure():
    t = km.textes_controle({"verdict": "non_configure"})
    assert "Consommation affichée" in t["invitation"]


@pytest.mark.parametrize("verdict, couleur, debut", [
    ("coherent", VERT, "Cohérent : l'écart n'est que de -34\xa0%."),
    ("trop_court", None, "Pas encore assez de recul"),
    ("energie_exterieure", None, "Environ 126\xa0kWh (34\xa0% de l'énergie"),
    ("excedent", ALERTE_TEXTE, "Écart inhabituel, à vérifier"),
])
def test_controle_verdicts(verdict, couleur, debut):
    t = km.textes_controle(dict(CONTROLE, verdict=verdict))
    assert t["verdict"].startswith(debut)
    if couleur:
        assert t["couleur"] == couleur
    assert t["reference"].startswith("Référence : 15,9\xa0kWh/100\xa0km")


def test_trop_court_cite_la_batterie():
    t = km.textes_controle(dict(CONTROLE, verdict="trop_court"))
    assert "(64,0\xa0kWh, soit 71\xa0kWh pris à la prise)" in t["verdict"]


def test_lignes_de_releve_et_d_intervalle():
    """Deux tableaux, et non plus des lignes en caracteres de largeur fixe
    (audit de design du 03/10/2026) : plus de fleche « -> », des milliers
    separes, « kWh/100 km » avec son espace."""
    r = {"date": "2026-09-13T11:24", "km": 72912.0, "conso": 15.9}
    assert km.cellules_releve(r, 1079.0) == (
        "13/09/2026 11:24", "72\xa0912\xa0km", "+1\xa0079\xa0km", "15,9\xa0kWh/100\xa0km")
    # Premier releve : pas d'ecart ; sans consommation notee : case vide.
    assert km.cellules_releve({"date": "2026-07-30T09:37", "km": 70781.0},
                              None) == ("30/07/2026 09:37", "70\xa0781\xa0km", "", "")
    assert len(km.ENTETES_RELEVES) == 4
    i = {"debut": "2026-08-17T07:31", "fin": "2026-09-13T11:24", "km": 1079.0,
         "n_recharges": 5, "kwh": 6398.45, "kwh_100": 15.1, "cout_100": 3.16}
    assert km.cellules_intervalle(i) == (
        "17/08/2026", "13/09/2026", "1\xa0079\xa0km", "5", "6\xa0398,45\xa0kWh",
        "15,1\xa0kWh/100\xa0km", "3,16\xa0€/100\xa0km")
    assert len(km.ENTETES_INTERVALLES) == 7
    # Sans recharge entre deux releves : un tiret, pas « 0,00 €/100 km ».
    vide = km.cellules_intervalle(dict(i, n_recharges=0, kwh=0.0,
                                       kwh_100=0.0, cout_100=0.0))
    assert vide[5:] == ("—", "—")


def test_lecture_du_releve():
    maintenant = datetime(2026, 9, 25, 12, 0)
    lu = lire_releve_km("", "", "72 912", "15,9", maintenant=maintenant)
    assert lu == {"date": None, "km": 72912.0, "conso": 15.9}
    with pytest.raises(ErreurSaisie) as e:
        lire_releve_km("", "", "", "", maintenant=maintenant)
    assert e.value.champ == "champ_km_valeur"


# ---------- Kilometrage : la page ----------

RELEVES = [
    {"id": "r1", "date": "2026-07-30T09:37", "km": 70781.0, "conso": 16.1},
    {"id": "r2", "date": "2026-08-17T07:31", "km": 71833.0},
]


@pytest.fixture
def page_km(fenetre, monkeypatch):
    monkeypatch.setattr(km, "charger_releves_km", lambda: list(RELEVES))
    monkeypatch.setattr(km, "calculer_consommation", lambda: {
        "n_releves": 2, "km": 1052.0, "kwh": 120.0, "kwh_100": 11.4,
        "cout_100": 2.13, "cout": 22.4,
        "intervalles": [{"debut": RELEVES[0]["date"], "fin": RELEVES[1]["date"],
                         "km": 1052.0, "n_recharges": 3, "kwh": 120.0,
                         "kwh_100": 11.4, "cout_100": 2.13}],
        "controle": dict(CONTROLE, verdict="coherent")})
    return km.construire(fenetre)


def test_page_kilometrage(page_km):
    assert [t._valeur.text() for t in page_km.tuiles] == [
        "1\xa0052\xa0km", "120,00\xa0kWh", "11,4\xa0kWh/100\xa0km", "2,13\xa0€/100\xa0km"]
    assert page_km.message_km.isHidden()          # rien a dire encore
    tout = " ".join(textes(page_km))
    # Un seul intervalle : pas de carte de detail.
    assert "DÉTAIL ENTRE CHAQUE RELEVÉ" not in tout
    # Le plus recent en premier, avec la distance depuis le precedent.
    from PySide6.QtWidgets import QTableWidget
    releves = page_km.findChildren(QTableWidget)[-1]
    assert releves.lignes[0][:3] == ("17/08/2026 07:31", "71\xa0833\xa0km",
                                     "+1\xa0052\xa0km")


def test_releve_enregistre(page_km, fenetre, monkeypatch):
    notes = []
    monkeypatch.setattr(km, "ajouter_releve_km", lambda k, quand, conso: (
        notes.append((k, quand, conso)) or
        {"km": k, "date": quand, "conso": conso}))
    cases = page_km.cases_km
    cases["champ_km_date_jour"].setText("25/09/2026")
    cases["champ_km_date_heure"].setText("8h")
    cases["champ_km_valeur"].setText("73\xa0000")
    cases["champ_km_conso"].setText("15,5")
    QTest.keyClick(cases["champ_km_conso"], Qt.Key_Return)   # Entree
    assert notes == [(73000.0, "2026-09-25T08:00", 15.5)]
    assert fenetre.message_km == ("Relevé enregistré : 73\xa0000\xa0km au "
                                  "25/09/2026 08:00, consommation affichée 15,5\xa0kWh/100\xa0km")


def test_releve_refuse_message_rouge_sous_la_saisie(page_km, monkeypatch):
    def refus(k, quand, conso):
        raise ValueError("Le compteur ne peut pas reculer.")
    monkeypatch.setattr(km, "ajouter_releve_km", refus)
    page_km.cases_km["champ_km_valeur"].setText("100")
    page_km.bouton_km.click()
    assert not page_km.message_km.isHidden()
    assert page_km.message_km.text() == "Le compteur ne peut pas reculer."
    assert ROUGE in page_km.message_km.styleSheet()
    # La saisie reste a l'ecran, a corriger.
    assert page_km.cases_km["champ_km_valeur"].text() == "100"


def test_erreur_de_saisie(page_km):
    page_km.cases_km["champ_km_valeur"].setText("abc")
    page_km.bouton_km.click()
    assert page_km.message_km.text().startswith("« abc »")


def test_supprimer_un_releve(page_km, fenetre, monkeypatch):
    supprimes = []
    monkeypatch.setattr(km, "supprimer_releve_km",
                        lambda ident: supprimes.append(ident) or True)
    reponses = [False, True]
    monkeypatch.setattr(km, "confirmer", lambda *a, **k: reponses.pop(0))
    carte = [c for c in page_km.findChildren(QLabel)
             if c.text() == "MES RELEVÉS"][0].parent()
    carte.boutons[0].click()              # « Garder »
    assert supprimes == []
    carte.boutons[0].click()              # « Supprimer » : le plus recent
    assert supprimes == ["r2"]


# ---------- audit de design du 03/10/2026 ----------

def test_la_comparaison_essence_n_est_plus_en_double(page_km):
    """Le bloc « Comparaison avec une voiture essence » etait repete a
    l'identique dans le Kilometrage et dans « Essence ou électrique ? ». Il
    ne reste que dans sa page ; le Kilometrage y renvoie."""
    tout = " ".join(textes(page_km))
    assert "COMPARAISON AVEC UNE VOITURE ESSENCE" not in tout
    assert "Essence ou électrique ?" in tout


def test_les_deux_consommations_disent_leur_base(page_km):
    """La tuile (9,2, a la prise) et la phrase du controle (8,2, a la
    batterie) semblaient se contredire : chacune dit maintenant ce qu'elle
    mesure, et « Conso » s'ecrit en entier."""
    libelles = [t.findChild(QLabel, "LibelleTuile").text()
                for t in page_km.tuiles]
    assert "CONSOMMATION À LA PRISE" in libelles
    assert not any("CONSO " in lib for lib in libelles)
    t = km.textes_controle(dict(CONTROLE, verdict="energie_exterieure",
                                conso_enregistree=8.2))
    assert "à la batterie" in t["verdict"]


def test_note_du_mois_en_cours(fenetre, monkeypatch):
    """La barre hachuree du mois en cours est expliquee sous le graphique
    (charte : une note le dit). Audit du 08/10/2026."""
    from filtres import MOIS_FR
    maintenant = datetime.now()
    du_mois = dict(RECHARGES[0], id="m",
                   date=f"{ANNEE}-{maintenant.month:02d}-01T10:00")
    monkeypatch.setattr(st, "charger_donnees",
                        lambda: {"recharges": RECHARGES + [du_mois]})
    page = st.construire(fenetre)
    nom = f"{MOIS_FR[maintenant.month - 1]} {ANNEE}"
    assert any(nom in t and "hachurée" in t for t in textes(page))


def test_kilometrage_actuel_vide_est_a_saisir(page_km):
    """Demande du 09/10/2026 : la case obligatoire et vide s'encadre de
    bleu et dit « à saisir » ; la consommation, facultative, non."""
    cases = page_km.cases_km
    assert cases["champ_km_valeur"].property("aSaisir")
    assert cases["champ_km_valeur"].placeholderText() == "à saisir"
    assert not cases["champ_km_conso"].property("aSaisir")
    cases["champ_km_valeur"].setText("73000")
    assert not cases["champ_km_valeur"].property("aSaisir")


def test_le_resume_passe_a_la_ligne_si_la_place_manque(fenetre):
    """Second audit du 16/10/2026, constat A7 : a 1 000 px, le resume a
    cote de la periode debordait de 132 px (mesure hors des tests, voir le
    JOURNAL du 17/10/2026)."""
    page = st.construire(fenetre)
    assert page.resume.wordWrap()
