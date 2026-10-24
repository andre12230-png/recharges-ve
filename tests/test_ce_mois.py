"""Bouton « Ce mois-ci » et raccourcis clavier du selecteur de periode
(23/09/2026 — meme ajout que Pecule et le Photovoltaique).

Apres etre alle voir un mois passe, il fallait rouvrir les deux menus pour
revenir au mois en cours.

    py -m pytest

Les dates sont construites par rapport a MAINTENANT (voir
test_selecteur_periode.py) : le mois en cours fait partie de ce qui est teste.
"""

import os
import sys
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

# Redirection des donnees AVANT tout import du projet, comme dans
# test_menu.py (voir test_isolation.py).
os.environ.setdefault("RECHARGES_DATA_DIR",
                      tempfile.mkdtemp(prefix="recharges_ce_mois_"))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import filtres as f  # noqa: E402

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


class TestPeriodeParRaccourci(unittest.TestCase):
    """Ce que fait chaque touche : -1 (Ctrl+←), +1 (Ctrl+→), 0 (Ctrl+Origine)."""

    def test_ctrl_gauche_et_droite_suivent_les_fleches(self):
        self.assertEqual(f.periode_par_raccourci(RECHARGES, JUIN, -1), MAI)
        self.assertEqual(f.periode_par_raccourci(RECHARGES, MAI, +1), JUIN)

    def test_ctrl_origine_ramene_au_mois_en_cours(self):
        for depart in (MAI, "Tout", AN_DERNIER, "30 derniers jours"):
            self.assertEqual(f.periode_par_raccourci(RECHARGES, depart, 0),
                             f.mois_en_cours())

    def test_rien_quand_il_n_y_a_nulle_part_ou_aller(self):
        self.assertIsNone(f.periode_par_raccourci(RECHARGES, MAI, -1))
        self.assertIsNone(
            f.periode_par_raccourci(RECHARGES, f.mois_en_cours(), 0))


    def test_les_raccourcis_avancent_d_une_annee(self):
        """Page Statistiques : l'annee seulement (demande de l'auteur, 23/09/2026)."""
        self.assertEqual(
            f.periode_par_raccourci(RECHARGES, ANNEE, -1, annuel=True), AN_DERNIER)
        self.assertEqual(
            f.periode_par_raccourci(RECHARGES, AN_DERNIER, 0, annuel=True), ANNEE)


# Le bouton « Ce mois-ci » / « Cette année », la barre annuelle et les
# raccourcis attaches a la barre sont eprouves sur la barre PySide6, dans
# test_qt_periode.py. Les tests de la barre customtkinter ont disparu avec
# elle (2.0.0) : c'etaient eux qui echouaient de temps en temps en
# « tcl_findLibrary ».


if __name__ == "__main__":
    unittest.main()
