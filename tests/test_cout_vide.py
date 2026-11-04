"""Recharge sans coût dans un ancien fichier (audit indépendant du
04/11/2026, constat T2).

Le contrôle à la lecture accepte un coût vide (« cout_eur »: null) ou un
autre nombre facultatif vide : d'anciens fichiers en contiennent. Pourtant
les exports, le tableau de l'Historique, la recherche, le tri, le tableau
de bord et les statistiques faisaient alors des calculs sur « rien » et
s'arrêtaient sur une erreur. Un fichier jugé valide doit pouvoir s'ouvrir,
se chercher, se trier et s'exporter.

Données inventées ; les fichiers sont écrits dans un dossier jetable.

    py -m pytest tests/test_cout_vide.py
"""

from __future__ import annotations

import export
import filtres
import recharges as r
from pages import historique as hi
from pages import statistiques as st
from pages import tableau_de_bord as tb

# Une recharge maison d'un ancien fichier : coût, prix et répartition
# HP/HC jamais calculés, coût annoncé par la wallbox vide.
SANS_COUT = {"id": "a", "date": "2025-03-10T23:00", "lieu": "maison",
             "kwh": 1.0, "cout_eur": None, "prix_kwh": None,
             "kwh_hc": None, "kwh_hp": None, "cout_wallbox": None,
             "tarif_nom": "Mon contrat"}
# Une recharge ordinaire à côté, pour vérifier que les totaux restent justes.
AVEC_COUT = {"id": "b", "date": "2025-03-12T12:00", "lieu": "exterieur",
             "kwh": 10.0, "cout_eur": 5.0, "prix_kwh": 0.5,
             "operateur": "Ionity", "carte": ""}
RECHARGES = [SANS_COUT, AVEC_COUT]


def test_le_fichier_est_bien_juge_valide():
    """Point de départ du constat : la lecture l'accepte."""
    assert r.structure_recharges_valide({"recharges": RECHARGES})


def test_export_excel(tmp_path):
    chemin = export.exporter_excel(RECHARGES, tmp_path / "e.xlsx", "Tout")
    assert chemin.exists()


def test_export_pdf(tmp_path):
    chemin = export.exporter_pdf(RECHARGES, tmp_path / "e.pdf", "Tout")
    assert chemin.exists()


def test_le_cout_vide_compte_zero_dans_les_totaux():
    stats = export._stats(RECHARGES)
    assert stats["cout"] == 5.0
    assert stats["maison"]["cout"] == 0


def test_cellules_de_l_historique():
    """Un coût inconnu s'affiche « — », pas « 0,00 » : ce n'est pas une
    recharge gratuite."""
    cellules = hi.cellules(SANS_COUT)
    assert cellules[3] == "—"
    assert cellules[4] == "—"


def test_recherche():
    assert filtres.filtrer_par_recherche(RECHARGES, "ionity") == [AVEC_COUT]
    assert filtres.filtrer_par_recherche(RECHARGES, "contrat") == [SANS_COUT]


def test_tri_sur_les_colonnes_chiffrees():
    for cle in ("kwh", "cout_eur", "prix_kwh"):
        for sens in (True, False):
            assert len(filtres.trier_recharges(RECHARGES, cle, sens)) == 2


def test_tableau_de_bord():
    chiffres = tb.chiffres_de_la_periode(RECHARGES, "Tout")
    assert chiffres is not None


def test_statistiques():
    st.par_mois(RECHARGES)
    st.repartitions(RECHARGES)
    assert st.ecart_wallbox(RECHARGES) is None
