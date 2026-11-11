"""L'energie d'une recharge calculee d'apres le niveau de la batterie.

Sans borne, rien n'affiche les kWh : l'onglet Maison propose deux cases
facultatives, le niveau au depart et a l'arrivee (en pour cent), et en tire
l'energie prise a la prise. Ce n'est qu'une aide au calcul : seuls les kWh
sont enregistres, le fichier des recharges ne change pas.

Valeurs inventees et rondes : une batterie de 50 kWh, un rendement de 90 %.

    py -m pytest tests/test_pourcentages_batterie.py
"""

from __future__ import annotations

import pytest

from recharges import energie_depuis_pourcentages
from saisie import ErreurSaisie, lire_pourcentages

CONFIG = {"capacite_batterie": 50.0, "rendement_charge": 0.90}


# ---------- le calcul ----------

def test_energie_prise_a_la_prise():
    """De 40 a 80 % sur 50 kWh : 20 kWh dans la batterie, donc 22,22 kWh
    tires de la prise avec un rendement de 90 %."""
    assert energie_depuis_pourcentages(40, 80, CONFIG) == 22.22


def test_charge_complete():
    assert energie_depuis_pourcentages(0, 100, CONFIG) == 55.56


def test_sans_capacite_pas_de_calcul():
    """Capacite non renseignee (0, la valeur d'origine) : on ne devine pas."""
    config = {"capacite_batterie": 0.0, "rendement_charge": 0.90}
    assert energie_depuis_pourcentages(40, 80, config) is None


# ---------- la lecture des deux cases ----------

def test_deux_cases_remplies():
    assert lire_pourcentages("40", "80", "d", "a") == (40.0, 80.0)


def test_virgule_et_signe_pour_cent_acceptes():
    assert lire_pourcentages("40,5 %", "80%", "d", "a") == (40.5, 80.0)


@pytest.mark.parametrize("depart, arrivee", [("", ""), ("40", ""), ("", "80"),
                                             ("  ", "80")])
def test_une_case_vide_rien_a_calculer(depart, arrivee):
    """Les cases sont facultatives : tant qu'il en manque une, pas d'erreur."""
    assert lire_pourcentages(depart, arrivee, "d", "a") is None


def test_arrivee_sous_le_depart():
    with pytest.raises(ErreurSaisie) as e:
        lire_pourcentages("80", "40", "d", "a")
    assert e.value.champ == "a"
    assert e.value.message == ("Le niveau à l'arrivée doit dépasser celui du "
                               "départ (80\xa0%).")


def test_arrivee_egale_au_depart():
    with pytest.raises(ErreurSaisie) as e:
        lire_pourcentages("50", "50", "d", "a")
    assert e.value.champ == "a"


@pytest.mark.parametrize("depart, arrivee, champ", [("40", "120", "a"),
                                                    ("101", "110", "d")])
def test_au_dela_de_cent(depart, arrivee, champ):
    with pytest.raises(ErreurSaisie) as e:
        lire_pourcentages(depart, arrivee, "d", "a")
    assert e.value.champ == champ
    assert e.value.message == "Un niveau de batterie va de 0 à 100\xa0%."


def test_texte_qui_n_est_pas_un_nombre():
    with pytest.raises(ErreurSaisie) as e:
        lire_pourcentages("plein", "80", "d", "a")
    assert e.value.champ == "d"
    assert "n'est pas un nombre" in e.value.message
