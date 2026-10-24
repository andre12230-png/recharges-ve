"""Page « Ajouter une recharge » de la version PySide6 (etape 3).

Le moteur (ajouter_recharge_maison...) est remplace par des doublures qui
notent ce qu'on leur demande : ces tests verifient la PAGE — message sous la
case fautive, questions de garde-fou, resultat, remise a zero — et jamais
les vraies donnees. Les regles de lecture des cases ont leurs propres tests
(test_saisie_recharge.py).

    py -m pytest tests/test_qt_ajouter.py
"""

from __future__ import annotations

from datetime import datetime

import pytest
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QComboBox, QWidget

import formulaire
from pages import ajouter
from theme_qt import ROUGE, VERT

LIEUX = ["Aire de Lançon (A7)", "Supermarché du village"]


class FausseFenetre(QWidget):
    """Ce que la page demande a la fenetre principale : un parent pour ses
    questions, et la mise a jour de la tuile du total."""

    def __init__(self):
        super().__init__()
        self.bilans = 0

    def _maj_bilan(self):
        self.bilans += 1


@pytest.fixture
def moteur(monkeypatch):
    """Doublures du moteur : elles notent les appels, rien n'est ecrit."""
    appels = {"maison": [], "exterieur": [], "km": [], "questions": []}

    def maison(debut, fin, kwh):
        appels["maison"].append((debut, fin, kwh))
        return {"date": debut.isoformat(timespec="minutes"), "kwh_hc": 15.0,
                "kwh_hp": 5.0, "cout_eur": 3.08, "tarif_nom": "Mon contrat"}

    def exterieur(kwh, cout, operateur="", lieu_detail="", date=None,
                  carte=""):
        appels["exterieur"].append({"kwh": kwh, "cout": cout,
                                    "operateur": operateur,
                                    "lieu_detail": lieu_detail,
                                    "date": date, "carte": carte})
        return {"date": date or "2026-09-25T12:00", "cout_eur": cout,
                "prix_kwh": cout / kwh}

    def releve(km, date):
        appels["km"].append((km, date))
        return {"km": km}

    def demander(parent, titre, texte, *, oui_par_defaut, **_boutons):
        appels["questions"].append(titre)
        return appels.get("reponse", True)

    monkeypatch.setattr(ajouter, "ajouter_recharge_maison", maison)
    monkeypatch.setattr(ajouter, "ajouter_recharge_exterieur", exterieur)
    monkeypatch.setattr(ajouter, "ajouter_releve_km", releve)
    monkeypatch.setattr(ajouter, "dernier_choix_exterieur",
                        lambda: ("Ionity", "Chargemap"))
    monkeypatch.setattr(ajouter, "lieux_deja_saisis", lambda: list(LIEUX))
    monkeypatch.setattr(formulaire, "_demander", demander)
    monkeypatch.setattr(formulaire, "energie_invraisemblable", lambda kwh: "")
    monkeypatch.setattr(formulaire, "horodatage_deja_utilise",
                        lambda date: None)
    return appels


@pytest.fixture
def page(qapp, moteur):
    fenetre = FausseFenetre()
    p = ajouter.construire(fenetre)
    p.fenetre = fenetre
    yield p
    p.deleteLater()
    fenetre.deleteLater()


def remplir(f, **textes):
    for nom, texte in textes.items():
        f.ecrire(nom, texte)


def messages(f) -> dict[str, str]:
    return {nom: f.message(nom) for nom in f.cases if f.message(nom)}


# ---------- la page ----------

def test_deux_onglets_maison_d_abord(page):
    assert [page.onglets.tabText(i) for i in range(page.onglets.count())] \
        == ["Maison", "Extérieur"]
    assert page.onglets.currentIndex() == 0


def test_dates_pre_remplies_avec_maintenant(page):
    aujourd_hui = datetime.now().strftime("%d/%m/%Y")
    assert page.maison.texte("champ_m_debut_jour") == aujourd_hui
    assert page.exterieur.texte("champ_e_date_jour") == aujourd_hui
    # La fin reste vide : facultative avec un tarif a prix unique.
    assert page.maison.texte("champ_m_fin_jour") == ""


def test_listes_pre_remplies_avec_les_derniers_choix(page):
    e = page.exterieur
    assert e.texte("champ_e_operateur") == "Ionity"
    assert e.texte("champ_e_carte") == "Chargemap"
    # Le lieu reste vide, mais la liste propose les lieux deja saisis.
    assert e.texte("champ_e_lieu") == ""
    assert e.cases["champ_e_lieu"].count() == len(LIEUX)


def test_liste_sans_dernier_choix_reste_vide(qapp, moteur, monkeypatch):
    """Sinon elle afficherait d'office son premier choix (« Allego »),
    enregistre sans avoir ete choisi."""
    monkeypatch.setattr(ajouter, "dernier_choix_exterieur", lambda: ("", ""))
    p = ajouter.construire(FausseFenetre())
    assert p.exterieur.texte("champ_e_operateur") == ""
    assert p.exterieur.texte("champ_e_carte") == ""


def test_bouton_maintenant(page):
    m = page.maison
    m.vider("champ_m_debut_jour", "champ_m_debut_heure")
    bouton = m.boutons_maintenant["champ_m_debut"]
    assert bouton.text() == "Maintenant"
    bouton.click()
    assert m.texte("champ_m_debut_jour") == datetime.now().strftime("%d/%m/%Y")
    assert m.texte("champ_m_debut_heure") != ""


# ---------- Maison ----------

def test_erreur_sous_la_case_fautive(page, moteur):
    m = page.maison
    m.bouton.click()                        # energie laissee vide
    assert messages(m) == {"champ_m_kwh": "Indiquez l'énergie consommée."}
    assert moteur["maison"] == []


def test_les_deux_cases_d_une_date_partagent_un_message(page):
    m = page.maison
    remplir(m, champ_m_debut_heure="25h", champ_m_kwh="20")
    m.bouton.click()
    assert m.message("champ_m_debut_heure").startswith("« 25h »")
    assert m.message("champ_m_debut_jour") == m.message("champ_m_debut_heure")


def test_nouvel_essai_efface_le_message_precedent(page, moteur):
    m = page.maison
    m.bouton.click()
    remplir(m, champ_m_kwh="20")
    m.bouton.click()
    assert messages(m) == {}
    assert len(moteur["maison"]) == 1


def test_enregistrement_maison(page, moteur):
    m = page.maison
    remplir(m, champ_m_debut_jour="24/09/2026", champ_m_debut_heure="22h30",
            champ_m_fin_heure="+6h12", champ_m_kwh="20,5")
    m.bouton.click()
    assert moteur["maison"] == [(datetime(2026, 9, 24, 22, 30),
                                 datetime(2026, 9, 25, 4, 42), 20.5)]
    assert m.resultat.text().startswith("OK : 15,00\xa0kWh HC + 5,00\xa0kWh HP")
    assert "(Mon contrat)" in m.resultat.text()
    assert VERT in m.resultat.styleSheet()
    # Formulaire remis a zero : un second clic ne cree pas de doublon.
    assert m.texte("champ_m_kwh") == m.texte("champ_m_fin_heure") == ""
    assert m.texte("champ_m_debut_jour") == datetime.now().strftime("%d/%m/%Y")
    assert page.fenetre.bilans == 1


def test_releve_du_compteur_note_avec_la_recharge(page, moteur):
    m = page.maison
    remplir(m, champ_m_kwh="20", champ_m_km="12\xa0345")
    m.bouton.click()
    assert moteur["km"] == [(12345.0, moteur["maison"][0][0].isoformat(
        timespec="minutes"))]
    assert "relevé noté : 12\xa0345\xa0km" in m.resultat.text()
    assert m.texte("champ_m_km") == ""


def test_releve_refuse_la_recharge_reste(page, moteur, monkeypatch):
    def refus(km, date):
        raise ValueError("Le compteur ne peut pas reculer.")
    monkeypatch.setattr(ajouter, "ajouter_releve_km", refus)
    m = page.maison
    remplir(m, champ_m_kwh="20", champ_m_km="100")
    m.bouton.click()
    assert len(moteur["maison"]) == 1
    assert "Recharge enregistrée, mais PAS le relevé" in m.resultat.text()
    assert ROUGE in m.resultat.styleSheet()
    assert m.texte("champ_m_km") == "100"       # a corriger, donc garde


def test_refus_du_moteur_affiche_en_rouge(page, monkeypatch):
    def refus(debut, fin, kwh):
        raise ValueError("Aucune période tarifaire ne couvre cette date.")
    monkeypatch.setattr(ajouter, "ajouter_recharge_maison", refus)
    m = page.maison
    remplir(m, champ_m_kwh="20")
    m.bouton.click()
    assert m.resultat.text() == "Aucune période tarifaire ne couvre cette date."
    assert ROUGE in m.resultat.styleSheet()
    assert m.texte("champ_m_kwh") == "20"       # rien n'est perdu
    assert page.fenetre.bilans == 0


def test_energie_invraisemblable_non_par_defaut(page, moteur, monkeypatch):
    monkeypatch.setattr(formulaire, "energie_invraisemblable",
                        lambda kwh: "500 kWh ne tiennent pas dans la batterie.")
    moteur["reponse"] = False
    m = page.maison
    remplir(m, champ_m_kwh="500")
    m.bouton.click()
    assert moteur["questions"] == ["Énergie inhabituelle"]
    assert moteur["maison"] == []
    moteur["reponse"] = True
    m.bouton.click()
    assert len(moteur["maison"]) == 1


def test_entree_enregistre(page, moteur):
    m = page.maison
    remplir(m, champ_m_kwh="20")
    QTest.keyClick(m.cases["champ_m_kwh"], Qt.Key_Return)
    assert len(moteur["maison"]) == 1


# ---------- Extérieur ----------

def test_enregistrement_exterieur(page, moteur):
    e = page.exterieur
    remplir(e, champ_e_date_jour="24/09/2026", champ_e_date_heure="14h05",
            champ_e_kwh="30", champ_e_prix="0,60",
            champ_e_lieu="  Aire de Lançon (A7) ", champ_e_carte="Direct (CB)")
    e.bouton.click()
    assert moteur["exterieur"] == [{
        "kwh": 30.0, "cout": 18.0, "operateur": "Ionity",
        "lieu_detail": "Aire de Lançon (A7)", "date": "2026-09-24T14:05",
        "carte": "Direct (CB)"}]
    assert e.resultat.text() == "OK : 18,00\xa0€  (0,6000\xa0€/kWh)"
    # Chiffres et lieu vides ; operateur et carte gardes.
    assert e.texte("champ_e_kwh") == e.texte("champ_e_prix") == ""
    assert e.texte("champ_e_lieu") == ""
    assert e.texte("champ_e_operateur") == "Ionity"
    assert page.fenetre.bilans == 1


def test_exterieur_deux_cases_vides_de_date(page, moteur):
    e = page.exterieur
    e.vider("champ_e_date_jour", "champ_e_date_heure")
    remplir(e, champ_e_kwh="30", champ_e_cout="18")
    e.bouton.click()
    assert moteur["exterieur"][0]["date"] is None   # le moteur date de maintenant


def test_exterieur_une_seule_case_chiffree(page, moteur):
    e = page.exterieur
    remplir(e, champ_e_cout="18")
    e.bouton.click()
    assert e.message("champ_e_kwh").startswith("Remplissez deux cases")
    assert moteur["exterieur"] == []


def test_meme_date_et_heure_demande_confirmation(page, moteur, monkeypatch):
    monkeypatch.setattr(formulaire, "horodatage_deja_utilise",
                        lambda date: {"operateur": "Ionity", "kwh": 42.0})
    moteur["reponse"] = False
    e = page.exterieur
    remplir(e, champ_e_kwh="30", champ_e_cout="18")
    e.bouton.click()
    assert moteur["questions"] == ["Même date et même heure"]
    assert moteur["exterieur"] == []


def test_un_lieu_nouveau_rejoint_la_liste(page, moteur, monkeypatch):
    e = page.exterieur
    remplir(e, champ_e_kwh="30", champ_e_cout="18", champ_e_lieu="Péage neuf")
    monkeypatch.setattr(ajouter, "lieux_deja_saisis",
                        lambda: LIEUX + ["Péage neuf"])
    e.bouton.click()
    liste = e.cases["champ_e_lieu"]
    assert [liste.itemText(i) for i in range(liste.count())] \
        == LIEUX + ["Péage neuf"]


def test_entree_dans_une_liste_enregistre(page, moteur):
    e = page.exterieur
    remplir(e, champ_e_kwh="30", champ_e_cout="18")
    QTest.keyClick(e.cases["champ_e_lieu"].lineEdit(), Qt.Key_Return)
    assert len(moteur["exterieur"]) == 1
    # Taper un nom puis Entree ne l'ajoute pas a la liste : elle vient des
    # donnees, pas de la frappe.
    assert e.cases["champ_e_lieu"].insertPolicy() == QComboBox.NoInsert


# ---------- cases a saisir (demande du 09/10/2026) ----------
# Comme la Saisie quotidienne du Photovoltaique : une case obligatoire et
# encore vide est encadree de bleu et dit « à saisir ». Remplie, elle
# reprend le cadre ordinaire.

def a_saisir(f, nom) -> bool:
    return bool(f.cases[nom].property("aSaisir"))


def test_maison_energie_vide_est_a_saisir(page):
    m = page.maison
    assert a_saisir(m, "champ_m_kwh")
    assert m.cases["champ_m_kwh"].placeholderText() == "à saisir"
    # Pre-rempli : le debut n'est pas a saisir, mais le redevient vide.
    assert not a_saisir(m, "champ_m_debut_jour")
    m.ecrire("champ_m_debut_jour", "")
    assert a_saisir(m, "champ_m_debut_jour")
    # Les cases facultatives ne le sont jamais.
    for nom in ("champ_m_fin_jour", "champ_m_fin_heure", "champ_m_km"):
        assert not a_saisir(m, nom), nom


def test_maison_energie_remplie_n_est_plus_a_saisir(page):
    m = page.maison
    m.ecrire("champ_m_kwh", "12,5")
    assert not a_saisir(m, "champ_m_kwh")


def test_exterieur_deux_cases_sur_trois(page):
    e = page.exterieur
    trois = ("champ_e_kwh", "champ_e_cout", "champ_e_prix")
    assert all(a_saisir(e, n) for n in trois)
    e.ecrire("champ_e_kwh", "30")
    assert not a_saisir(e, "champ_e_kwh")
    assert a_saisir(e, "champ_e_cout") and a_saisir(e, "champ_e_prix")
    # Deux remplies : la troisieme se calcule, elle n'est plus a saisir.
    e.ecrire("champ_e_cout", "15")
    assert not any(a_saisir(e, n) for n in trois)
    for nom in ("champ_e_date_jour", "champ_e_operateur", "champ_e_carte",
                "champ_e_lieu", "champ_e_km"):
        assert not a_saisir(e, nom), nom


def test_le_cadre_bleu_est_dans_le_theme():
    import theme_qt
    feuille = theme_qt.feuille_de_style()
    assert '[aSaisir="true"]' in feuille
