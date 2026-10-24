"""Les deux formulaires « Ajouter une recharge », lus sans fenetre.

lire_recharge_maison() et lire_recharge_exterieur() (saisie.py) recoivent
les textes tapes et rendent les valeurs a enregistrer, ou le nom de la case
fautive et le message. Ce sont les regles de l'ancienne page (vues/ajout.py),
sorties de l'interface a la migration PySide6 : on les eprouve ici une par
une, sans ecran.

    py -m pytest tests/test_saisie_recharge.py
"""

from __future__ import annotations

from datetime import datetime

import pytest

from saisie import ErreurSaisie, lire_recharge_exterieur, lire_recharge_maison

# Un instant fixe : les dates sans annee et les cases vides en dependent.
MAINTENANT = datetime(2026, 9, 25, 12, 0)


def maison(debut_jour="24/09/2026", debut_heure="22:30", fin_jour="",
           fin_heure="", kwh="20", km=""):
    return lire_recharge_maison(debut_jour, debut_heure, fin_jour, fin_heure,
                                kwh, km, maintenant=MAINTENANT)


def exterieur(jour="24/09/2026", heure="14:00", kwh="30", cout="", prix="",
              km=""):
    return lire_recharge_exterieur(jour, heure, kwh, cout, prix, km,
                                   maintenant=MAINTENANT)


def erreur(appel) -> ErreurSaisie:
    with pytest.raises(ErreurSaisie) as e:
        appel()
    return e.value


# ---------- Maison ----------

def test_maison_complete():
    lu = maison(fin_jour="25/09/2026", fin_heure="05:00", kwh="20,5",
                km="12 345")
    assert lu == {"debut": datetime(2026, 9, 24, 22, 30),
                  "fin": datetime(2026, 9, 25, 5, 0),
                  "kwh": 20.5, "km": 12345.0}


def test_fin_facultative():
    """Tarif a prix unique : la fin ne change rien au cout."""
    lu = maison()
    assert lu["fin"] is None and lu["km"] is None


def test_une_duree_se_compte_a_partir_du_debut():
    assert maison(fin_heure="+6h12")["fin"] == datetime(2026, 9, 25, 4, 42)
    assert maison(fin_heure="+45min")["fin"] == datetime(2026, 9, 24, 23, 15)


def test_duree_avec_un_jour_de_fin_refusee():
    e = erreur(lambda: maison(fin_jour="25/09", fin_heure="+6h"))
    assert e.champ == "champ_m_fin_jour"
    assert "laissez la case du jour vide" in e.message


def test_duree_illisible_signalee_sous_l_heure_de_fin():
    e = erreur(lambda: maison(fin_heure="+6h1x"))
    assert e.champ == "champ_m_fin_heure"
    assert "« +6h12 »" in e.message


def test_charge_de_nuit_heure_seule_passe_au_lendemain():
    """22h30 -> « 6h » sans jour : c'est le lendemain matin."""
    assert maison(fin_heure="6h")["fin"] == datetime(2026, 9, 25, 6, 0)


def test_jour_de_fin_ecrit_pris_au_mot():
    """Un jour ecrit n'est jamais decale : fin avant debut = erreur."""
    e = erreur(lambda: maison(fin_jour="24/09/2026", fin_heure="06:00"))
    assert (e.champ, e.message) == ("champ_m_fin_heure",
                                    "La fin doit être après le début.")


def test_meme_heure_debut_et_fin_refusee():
    e = erreur(lambda: maison(fin_jour="24/09/2026", fin_heure="22:30"))
    assert e.champ == "champ_m_fin_heure"


def test_debut_obligatoire():
    e = erreur(lambda: maison(debut_jour="", debut_heure=""))
    assert e.champ == "champ_m_debut_jour"
    assert e.message == "Indiquez la date et l'heure de début."


def test_heure_de_debut_illisible():
    e = erreur(lambda: maison(debut_heure="25h"))
    assert e.champ == "champ_m_debut_heure"


def test_energie_obligatoire_et_non_nulle():
    assert erreur(lambda: maison(kwh="")).champ == "champ_m_kwh"
    e = erreur(lambda: maison(kwh="0"))
    assert e.message == "L'énergie consommée ne peut pas être à zéro."


def test_kilometrage_illisible_refuse_avant_tout_enregistrement():
    """Tout est lu avant d'enregistrer : un « abc » dans la case du
    compteur ne doit pas laisser une recharge a moitie saisie."""
    e = erreur(lambda: maison(km="abc"))
    assert e.champ == "champ_m_km"


def test_date_courte_du_debut_rapportee_a_l_annee_passee():
    """Le 2 janvier, « 30/12 » designe le 30 decembre qui vient de passer :
    la regle `passe=True` des dates courtes s'applique au debut."""
    lu = lire_recharge_maison("30/12", "22h", "", "", "10", "",
                              maintenant=datetime(2027, 1, 2, 9, 0))
    assert lu["debut"] == datetime(2026, 12, 30, 22, 0)


# ---------- Extérieur ----------

def test_exterieur_date_vide_vaut_maintenant_au_moteur():
    lu = exterieur(jour="", heure="", kwh="30", cout="18")
    assert lu == {"date": None, "kwh": 30.0, "cout": 18.0, "km": None}


def test_exterieur_deux_cases_sur_trois():
    assert exterieur(kwh="30", prix="0,60")["cout"] == 18.0
    assert exterieur(kwh="", cout="18", prix="0,60")["kwh"] == 30.0


def test_exterieur_moins_de_deux_cases():
    e = erreur(lambda: exterieur(kwh="30"))
    assert e.champ == "champ_e_kwh"
    assert "Remplissez deux cases" in e.message


def test_exterieur_date_impossible():
    e = erreur(lambda: exterieur(jour="31/02", cout="18"))
    assert e.champ == "champ_e_date_jour"


def test_exterieur_kilometrage():
    assert exterieur(cout="18", km="45 000")["km"] == 45000.0
    assert erreur(lambda: exterieur(cout="18", km="-3")).champ == "champ_e_km"


def test_heure_de_fin_seule_prend_le_jour_du_debut():
    """Bug trouve le 25/09/2026 (present aussi dans la 1.31.0) : sans jour
    de fin, l'heure seule etait placee AUJOURD'HUI, pas le jour du debut.
    Saisie le 25 d'une charge commencee le 20 a 22h30, « 6h » donnait le 25
    a 6h : plus de cinq jours de charge. Cela ne se voyait pas en saisissant
    le lendemain matin, quand aujourd'hui EST le lendemain du debut."""
    lu = maison(debut_jour="20/09/2026", debut_heure="22:30", fin_heure="6h")
    assert lu["fin"] == datetime(2026, 9, 21, 6, 0)
    # Heure de fin plus tard le meme jour : le jour meme, pas le lendemain.
    lu = maison(debut_jour="20/09/2026", debut_heure="08:00", fin_heure="11h")
    assert lu["fin"] == datetime(2026, 9, 20, 11, 0)
