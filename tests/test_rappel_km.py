"""Le rappel doux de relevé kilométrique, affiché sur le tableau de bord.

Les recharges faites APRÈS le dernier relevé ne sont rattachées à aucune
distance : elles ne comptent ni dans la consommation ni dans le coût aux
100 km (voir calculer_consommation, qui travaille par intervalles entre deux
relevés). L'oubli coûte donc cher, et en silence.

Ces tests portent surtout sur ce que le rappel doit TAIRE : un rappel qui
s'affiche à tort, à chaque ouverture, se fait ignorer — et le jour où il a
raison, il n'est plus lu.

`aujourd_hui` est imposé partout : ces règles ne doivent pas dépendre du jour
où les tests tournent.

    py -m pytest
"""

import os
import shutil
import sys
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path

# --- redirection des donnees : AVANT l'import de recharges (test_isolation) --
DOSSIER_TEST = Path(tempfile.mkdtemp(prefix="recharges_rappel_"))
os.environ["RECHARGES_DATA_DIR"] = str(DOSSIER_TEST)
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import recharges as r  # noqa: E402

r.rediriger_donnees(DOSSIER_TEST)

AUJOURD_HUI = datetime(2026, 9, 19, 10, 0)


def tearDownModule():
    shutil.rmtree(DOSSIER_TEST, ignore_errors=True)


class BaseRappel(unittest.TestCase):
    def setUp(self):
        r.sauvegarder_donnees({"recharges": [], "releves_km": []})

    def poser(self, releves_il_y_a: list[int], recharges_il_y_a: list[int]):
        """Construit un jeu d'essai en JOURS avant AUJOURD_HUI.

        Les donnees sont ecrites telles quelles : ajouter_releve_km refuse un
        kilometrage qui recule, et on veut ici maitriser les dates au jour
        pres sans se battre avec ces controles.
        """
        data = r.charger_donnees(pour_modification=True)
        data["releves_km"] = [
            {"id": f"k{i}", "km": 10000 + i * 1000,
             "date": (AUJOURD_HUI - timedelta(days=j)).isoformat(
                 timespec="minutes")}
            for i, j in enumerate(sorted(releves_il_y_a, reverse=True))]
        data["recharges"] = [
            {"id": f"r{i}", "lieu": "exterieur", "kwh": 30, "cout_eur": 18,
             "date": (AUJOURD_HUI - timedelta(days=j)).isoformat(
                 timespec="minutes")}
            for i, j in enumerate(sorted(recharges_il_y_a, reverse=True))]
        r.sauvegarder_donnees(data)

    def rappel(self, **kw):
        return r.rappel_releve_km(aujourd_hui=AUJOURD_HUI, **kw)


class TestQuandIlSeTait(BaseRappel):
    def test_aucun_releve(self):
        """Qui ne se sert pas du kilometrage ne doit pas etre relance a
        chaque ouverture. La page Kilometrage, elle, l'invite a commencer."""
        self.poser(releves_il_y_a=[], recharges_il_y_a=[60, 30, 10])
        self.assertIsNone(self.rappel())

    def test_releve_recent(self):
        self.poser(releves_il_y_a=[40, 5], recharges_il_y_a=[3])
        self.assertIsNone(self.rappel())

    def test_aucune_recharge_depuis_le_dernier_releve(self):
        """Sans recharge a rattacher, l'oubli ne fausse rien : c'est le cas
        d'André le 19/09/2026 — dernier releve il y a 5 jours, rien depuis."""
        self.poser(releves_il_y_a=[200, 90], recharges_il_y_a=[300, 120])
        self.assertIsNone(self.rappel())

    def test_la_veille_du_seuil_il_se_tait(self):
        """La frontiere est figee des deux cotes : muet a 29 jours, il parle
        a 30. « Seuil de 30 jours » veut dire qu'il parle A 30."""
        self.poser(releves_il_y_a=[90, 29], recharges_il_y_a=[10])
        self.assertIsNone(self.rappel(seuil_jours=30))

    def test_application_vide(self):
        self.assertIsNone(self.rappel())


class TestQuandIlParle(BaseRappel):
    def test_la_phrase_dit_les_jours_et_le_nombre_de_recharges(self):
        self.poser(releves_il_y_a=[120, 47], recharges_il_y_a=[40, 30, 20, 5])
        message = self.rappel()
        self.assertIn("il y a 47 jours", message)
        self.assertIn("4 recharges", message)
        self.assertIn("aucune distance", message)

    def test_une_seule_recharge_depuis(self):
        """L'accord doit suivre : « 1 recharge n'est rattachée »."""
        self.poser(releves_il_y_a=[120, 47], recharges_il_y_a=[10])
        message = self.rappel()
        self.assertIn("1 recharge n'est rattachée", message)
        self.assertNotIn("recharges", message)

    def test_un_seul_releve_la_phrase_change(self):
        """Avec un seul releve, aucun chiffre de consommation n'existe
        encore : c'est cela qu'il faut dire, pas le rattachement."""
        self.poser(releves_il_y_a=[47], recharges_il_y_a=[40, 10])
        message = self.rappel()
        self.assertIn("deuxième relevé", message)
        self.assertNotIn("rattachée", message)

    def test_les_recharges_d_avant_le_releve_ne_comptent_pas(self):
        """Seules celles faites APRÈS le dernier relevé sont orphelines."""
        self.poser(releves_il_y_a=[120, 47], recharges_il_y_a=[100, 60, 10])
        self.assertIn("1 recharge n'est rattachée", self.rappel())

    def test_pile_au_seuil_il_parle(self):
        """L'autre cote de la frontiere ci-dessus."""
        self.poser(releves_il_y_a=[90, 30], recharges_il_y_a=[10])
        self.assertIn("il y a 30 jours", self.rappel(seuil_jours=30))

    def test_le_seuil_se_regle(self):
        self.poser(releves_il_y_a=[120, 12], recharges_il_y_a=[5])
        self.assertIsNone(self.rappel())
        self.assertIsNotNone(self.rappel(seuil_jours=10))


class TestRobustesse(BaseRappel):
    def test_un_releve_sans_date_ne_fait_pas_tomber_l_application(self):
        """Le rappel est un confort : il ne doit jamais empecher le tableau
        de bord de s'afficher."""
        data = r.charger_donnees(pour_modification=True)
        data["releves_km"] = [{"id": "k0", "km": 1000, "date": "n'importe quoi"}]
        data["recharges"] = [{"id": "r0", "lieu": "exterieur", "kwh": 30,
                              "cout_eur": 18, "date": "2026-09-01T10:00"}]
        r.sauvegarder_donnees(data)
        self.assertIsNone(self.rappel())


if __name__ == "__main__":
    unittest.main()
