"""Extérieur : deux valeurs sur trois parmi kWh, coût et prix du kWh.

Les reçus des opérateurs ne donnent pas tous les mêmes chiffres : l'un le
total payé, l'autre le prix au kWh. Le formulaire accepte les deux cases
qu'on a, et calcule la troisième.

`energie_et_cout()` reçoit les textes tapés, pas la fenêtre : ces tests ne
lancent donc aucun écran.

    py -m pytest
"""

import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

# Redirection des donnees par precaution, AVANT tout import du projet
# (voir test_isolation.py).
DOSSIER_TEST = Path(tempfile.mkdtemp(prefix="recharges_energie_"))
os.environ["RECHARGES_DATA_DIR"] = str(DOSSIER_TEST)
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from saisie import ErreurSaisie  # noqa: E402
from saisie import energie_et_cout  # noqa: E402


def tearDownModule():
    shutil.rmtree(DOSSIER_TEST, ignore_errors=True)


class TestDeuxCasesSurTrois(unittest.TestCase):
    def test_energie_et_cout(self):
        """Le cas d'avant : les deux cases historiques."""
        self.assertEqual(energie_et_cout("30", "18", ""), (30.0, 18.0))

    def test_prix_superflu_a_zero_ne_bloque_pas(self):
        """Audit du 14/10/2026 : kWh et coût remplis, le coût fait foi ; un
        prix à zéro (borne gratuite recopiée du reçu) bloquait pourtant la
        saisie. Il est ignoré, comme tout prix superflu."""
        self.assertEqual(energie_et_cout("30", "0", "0"), (30.0, 0.0))
        self.assertEqual(energie_et_cout("30", "18", "0"), (30.0, 18.0))

    def test_prix_superflu_qui_n_est_pas_un_nombre_reste_signale(self):
        """Une faute de frappe dans la case reste signalée : elle trahit
        peut-être une erreur dans les deux autres."""
        with self.assertRaises(ErreurSaisie):
            energie_et_cout("30", "18", "abc")

    def test_energie_et_prix(self):
        """Un reçu qui donne les kWh et le tarif, pas le total."""
        self.assertEqual(energie_et_cout("30", "", "0,60"), (30.0, 18.0))

    def test_cout_et_prix(self):
        """Un reçu qui donne le montant et le tarif, pas les kWh."""
        self.assertEqual(energie_et_cout("", "18", "0,60"), (30.0, 18.0))

    def test_les_trois_le_cout_fait_foi(self):
        """C'est le montant qu'on retrouve sur le relevé bancaire ; la règle
        existait déjà dans la notice. Un prix incohérent est ignoré, pas
        appliqué en douce."""
        self.assertEqual(energie_et_cout("30", "18", "0,99"), (30.0, 18.0))

    def test_la_virgule_decimale_partout(self):
        self.assertEqual(energie_et_cout("28,5", "", "0,45"), (28.5, 12.83))

    def test_le_cout_calcule_est_arrondi_au_centime(self):
        kwh, cout = energie_et_cout("31,7", "", "0,4567")
        self.assertEqual(cout, 14.48)

    def test_l_energie_calculee_garde_trois_decimales(self):
        kwh, cout = energie_et_cout("", "14,48", "0,4567")
        self.assertEqual(kwh, 31.706)


class TestCeQuiEstRefuse(unittest.TestCase):
    def messages(self, *args):
        with self.assertRaises(ErreurSaisie) as ctx:
            energie_et_cout(*args)
        return ctx.exception

    def test_une_seule_case(self):
        erreur = self.messages("30", "", "")
        self.assertEqual(erreur.champ, "champ_e_kwh")
        self.assertIn("deux cases", erreur.message)

    def test_aucune_case(self):
        self.assertIn("deux cases", self.messages("", "", "").message)

    def test_recharge_gratuite_sans_energie(self):
        """0 € divisé par un prix donne 0 kWh, que l'enregistrement refuse :
        autant le dire ici, et dire quoi faire."""
        erreur = self.messages("", "0", "0,45")
        self.assertEqual(erreur.champ, "champ_e_kwh")
        self.assertIn("gratuite", erreur.message)

    def test_recharge_gratuite_avec_energie_passe(self):
        """L'autre face du test ci-dessus : 0 € est parfaitement légitime."""
        self.assertEqual(energie_et_cout("22", "0", ""), (22.0, 0.0))

    def test_prix_a_zero(self):
        """Il servirait de diviseur : lire_nombre le refuse en amont."""
        erreur = self.messages("", "18", "0")
        self.assertEqual(erreur.champ, "champ_e_prix")

    def test_energie_a_zero(self):
        erreur = self.messages("0", "18", "")
        self.assertEqual(erreur.champ, "champ_e_kwh")

    def test_texte_au_lieu_d_un_nombre(self):
        erreur = self.messages("trente", "18", "")
        self.assertEqual(erreur.champ, "champ_e_kwh")
        self.assertIn("n'est pas un nombre", erreur.message)


if __name__ == "__main__":
    unittest.main()
