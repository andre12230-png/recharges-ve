"""La fenetre « Modifier la recharge », lue sans fenetre.

lire_modification_recharge() (saisie.py) recoit la recharge d'origine et
le texte des cases ; elle rend les modifications a enregistrer, ou le nom
de la case fautive et le message.

    py -m pytest tests/test_saisie_modification.py
"""

from __future__ import annotations

from datetime import datetime

import pytest

from saisie import ErreurSaisie, lire_modification_recharge

MAINTENANT = datetime(2026, 9, 25, 12, 0)

MAISON = {"id": "m1", "lieu": "maison", "date": "2026-09-23T23:30",
          "fin": "2026-09-24T05:15", "kwh": 38.125}
EXTERIEUR = {"id": "e1", "lieu": "exterieur", "date": "2026-08-23T17:40",
             "kwh": 25.125, "cout_eur": 16.40, "operateur": "Ionity",
             "carte": "Chargemap", "lieu_detail": "Aire de repos"}


def maison(**textes):
    base = {"date_jour": "23/09/2026", "date_heure": "23:30",
            "fin_jour": "24/09/2026", "fin_heure": "05:15", "kwh": "38,125"}
    base.update(textes)
    return lire_modification_recharge(MAISON, base, maintenant=MAINTENANT)


def exterieur(**textes):
    base = {"date_jour": "23/08/2026", "date_heure": "17:40",
            "kwh": "25,125", "cout_eur": "16,40", "operateur": "Ionity",
            "carte": "Chargemap", "lieu_detail": "Aire de repos"}
    base.update(textes)
    return lire_modification_recharge(EXTERIEUR, base, maintenant=MAINTENANT)


def erreur(appel) -> ErreurSaisie:
    with pytest.raises(ErreurSaisie) as e:
        appel()
    return e.value


def test_sans_rien_toucher_rien_ne_change():
    """Enregistrer la fenetre telle qu'elle s'ouvre rend les memes
    valeurs : rien n'est arrondi ni decale au passage."""
    assert maison() == {"date": "2026-09-23T23:30", "fin": "2026-09-24T05:15",
                        "kwh": 38.125}
    assert exterieur() == {"date": "2026-08-23T17:40", "kwh": 25.125,
                           "cout_eur": 16.40, "operateur": "Ionity",
                           "carte": "Chargemap", "lieu_detail": "Aire de repos"}


def test_date_videe_reste_inchangee():
    """Le debut est obligatoire : ses deux cases videes veulent dire
    « inchange »."""
    modifs = maison(date_jour="", date_heure="")
    assert "date" not in modifs


def test_fin_videe_est_effacee():
    """15/10/2026 (decision d'André) : la fin est pre-remplie ; vider ses
    deux cases est un geste voulu, qui retire l'heure de fin. Avant, il
    etait ignore sans un mot. None = « a retirer » pour modifier_recharge."""
    assert maison(fin_jour="", fin_heure="")["fin"] is None
    modifs = maison(date_jour="", date_heure="", fin_jour="", fin_heure="")
    assert "date" not in modifs and modifs["fin"] is None


def test_duree_comptee_depuis_le_debut():
    assert maison(fin_jour="", fin_heure="+5h45")["fin"] == "2026-09-24T05:15"


def test_duree_avec_un_jour_de_fin():
    assert erreur(lambda: maison(fin_heure="+5h")).champ == "fin_jour"


def test_fin_avant_le_debut():
    e = erreur(lambda: maison(fin_jour="23/09/2026", fin_heure="22:00"))
    assert (e.champ, e.message) == ("fin_heure",
                                    "La fin doit être après le début.")


def test_energie():
    assert erreur(lambda: maison(kwh="")).champ == "kwh"
    assert erreur(lambda: maison(kwh="0")).champ == "kwh"


def test_cout_gratuit_accepte_negatif_refuse():
    assert exterieur(cout_eur="0")["cout_eur"] == 0.0
    assert erreur(lambda: exterieur(cout_eur="-1")).champ == "cout_eur"


def test_textes_nettoyes():
    assert exterieur(operateur="  Ionity ")["operateur"] == "Ionity"


def test_date_illisible():
    assert erreur(lambda: exterieur(date_jour="32/08")).champ == "date_jour"


def test_heure_de_fin_seule_prend_le_jour_du_debut():
    """Meme bug qu'a la saisie (voir test_saisie_recharge.py) : une recharge
    du 23/09 corrigee le 25 avec « 6h » en fin partait au 25 a 6h."""
    assert maison(fin_jour="", fin_heure="6h")["fin"] == "2026-09-24T06:00"
    modifs = maison(date_jour="", date_heure="", fin_jour="", fin_heure="4h")
    assert modifs["fin"] == "2026-09-24T04:00"
