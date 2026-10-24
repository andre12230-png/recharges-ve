"""Barre de periode de la version PySide6 (pages/periode.py).

Les memes cas que tests/test_ce_mois.py pour l'ancienne barre, plus ce que
Qt permet : une case de saisie garde son Ctrl+fleche. Les dates sont
construites par rapport a MAINTENANT : le mois en cours fait partie de ce
qui est teste.

    py -m pytest tests/test_qt_periode.py
"""

from __future__ import annotations

from datetime import datetime

import pytest
from PySide6.QtWidgets import QLineEdit, QVBoxLayout, QWidget

import filtres as f
from pages.periode import BarrePeriode

MAINTENANT = datetime.now()
ANNEE = str(MAINTENANT.year)
AN_DERNIER = str(MAINTENANT.year - 1)


def recharge(iso: str) -> dict:
    return {"date": iso, "kwh": 10.0, "cout_eur": 2.0, "lieu": "maison"}


RECHARGES = [recharge(f"{AN_DERNIER}-05-10T08:00"),
             recharge(f"{AN_DERNIER}-06-10T08:00"),
             recharge(f"{ANNEE}-{MAINTENANT.month:02d}-01T08:00")]
MAI = f"Mai {AN_DERNIER}"
JUIN = f"Juin {AN_DERNIER}"


@pytest.fixture
def barre(qapp):
    """Fabrique une barre et note chaque periode qu'elle annonce."""
    faites = []

    def fabriquer(periode: str, annuel: bool = False) -> BarrePeriode:
        b = BarrePeriode(RECHARGES, periode, annuel=annuel)
        b.annonces = []
        b.periode_changee.connect(b.annonces.append)
        faites.append(b)
        return b
    yield fabriquer
    for b in faites:
        b.deleteLater()


def test_valeurs_affichees(barre):
    b = barre(JUIN)
    assert b.menu_annee.currentText() == AN_DERNIER
    assert b.menu_mois.currentText() == "Juin"
    assert b.menu_mois.isEnabled()


def test_sur_tout_le_menu_des_mois_est_grise(barre):
    b = barre("Tout")
    # Le menu dit « Toute la période », comme Pécule et le Photovoltaïque
    # (choix de l'auteur du 08/10/2026) ; la valeur reste « Tout ».
    assert b.menu_annee.currentText() == "Toute la période"
    assert b.menu_annee.currentData() == "Tout"
    assert not b.menu_mois.isEnabled()
    assert not b.fleche_precedente.isEnabled()


def test_choisir_toute_la_periode_annonce_tout(barre):
    b = barre(JUIN)
    assert b.menu_annee.itemText(0) == "Toute la période"
    assert b.menu_annee.itemText(1) == "30 derniers jours"
    b.menu_annee.activated.emit(0)
    assert b.annonces[-1] == "Tout"
    # Et depuis « Toute la période », une année se choisit par sa valeur.
    b = barre("Tout")
    b.menu_annee.activated.emit(b.menu_annee.findData(AN_DERNIER))
    assert b.annonces == [AN_DERNIER]


def test_les_fleches_avancent_d_un_mois(barre):
    b = barre(JUIN)
    b.fleche_precedente.click()
    assert b.annonces == [MAI]
    b = barre(MAI)
    assert not b.fleche_precedente.isEnabled()      # plus rien avant
    b.fleche_suivante.click()
    assert b.annonces == [JUIN]


def test_ce_mois_ci(barre):
    b = barre(MAI)
    assert b.bouton_ce_mois.text() == "Ce mois-ci"
    b.bouton_ce_mois.click()
    assert b.annonces == [f.mois_en_cours()]
    # Deja sur le mois en cours : le bouton est grise.
    assert not barre(f.mois_en_cours()).bouton_ce_mois.isEnabled()


def test_changer_d_annee_garde_le_mois_s_il_existe(barre):
    b = barre(JUIN)
    b._changer_annee(ANNEE)          # juin n'existe pas cette annee...
    assert b.annonces[-1] in (ANNEE, f"Juin {ANNEE}")
    b._changer_annee("Tout")
    assert b.annonces[-1] == "Tout"


def test_toute_l_annee(barre):
    b = barre(JUIN)
    b._changer_mois(f.TOUTE_ANNEE)
    assert b.annonces == [AN_DERNIER]


def test_barre_annuelle(barre):
    b = barre(JUIN, annuel=True)
    assert b.menu_mois is None
    assert b.periode == AN_DERNIER            # le mois est ramene a son annee
    assert b.bouton_ce_mois.text() == "Cette année"
    b.bouton_ce_mois.click()
    assert b.annonces == [f.annee_en_cours()]
    assert not barre(f.annee_en_cours(), annuel=True).bouton_ce_mois.isEnabled()


def test_raccourcis_installes(barre):
    b = barre(JUIN)
    touches = sorted(r.key().toString() for r in b.raccourcis)
    assert touches == sorted(["Ctrl+Left", "Ctrl+Right", "Ctrl+Home"])


def test_raccourcis(barre):
    b = barre(JUIN)
    b._raccourci(-1)
    b._raccourci(0)
    assert b.annonces == [MAI, f.mois_en_cours()]


def test_raccourci_annuel(barre):
    b = barre(AN_DERNIER, annuel=True)
    b._raccourci(0)
    assert b.annonces == [f.annee_en_cours()]


def test_une_case_de_saisie_garde_son_ctrl_fleche(barre, qapp):
    """Dans une case, Ctrl+Gauche saute d'un mot au lieu de changer de mois."""
    b = barre(JUIN)
    hote = QWidget()
    colonne = QVBoxLayout(hote)
    case = QLineEdit("un deux trois")
    colonne.addWidget(case)
    colonne.addWidget(b)
    hote.show()
    case.setFocus()
    case.end(False)
    qapp.processEvents()
    if qapp.focusWidget() is not case:
        pytest.skip("le mode hors ecran ne donne pas le focus")
    b._raccourci(-1)
    assert b.annonces == []
    assert case.cursorPosition() == len("un deux ")
    hote.deleteLater()
