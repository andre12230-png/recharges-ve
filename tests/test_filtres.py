"""Tests des fonctions de selection, tri et regroupement (filtres.py).

Ces fonctions sont pures : elles recoivent une liste de recharges et en
renvoient une autre. Aucun fichier n'est lu ni ecrit, aucune fenetre ouverte.

    py -m pytest

Les periodes (« Septembre 2026 », « 30 derniers jours »...) dependent de la
date du jour : les jeux d'essai sont donc construits PAR RAPPORT a maintenant,
jamais avec des dates ecrites en dur, sinon les tests cesseraient de passer le
mois suivant.
"""

import sys
import unittest
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import filtres as f  # noqa: E402


def recharge(quand: datetime, kwh=10.0, cout=2.0, lieu="maison", **extra):
    """Une recharge minimale, a la date indiquee."""
    base = {"date": quand.isoformat(timespec="minutes"), "kwh": kwh,
            "cout_eur": cout, "lieu": lieu,
            "prix_kwh": round(cout / kwh, 4) if kwh else 0}
    base.update(extra)
    return base


def le_mois_dernier(maintenant: datetime) -> datetime:
    """Une date situee dans le mois precedent, jamais le 29, 30 ni 31."""
    premier = maintenant.replace(day=1, hour=12, minute=0)
    return premier - timedelta(days=1)     # le dernier jour du mois d'avant


class TestFiltrerParPeriode(unittest.TestCase):

    def setUp(self):
        self.maintenant = datetime.now().replace(hour=12, minute=0,
                                                 second=0, microsecond=0)
        self.ce_mois = recharge(self.maintenant)
        self.mois_dernier = recharge(le_mois_dernier(self.maintenant))
        self.vieux = recharge(self.maintenant.replace(
            year=self.maintenant.year - 2))
        self.toutes = [self.ce_mois, self.mois_dernier, self.vieux]

    def test_tout_ne_filtre_rien(self):
        self.assertEqual(len(f.filtrer_par_periode(self.toutes, "Tout")), 3)

    def test_annee_precise(self):
        annee = str(self.maintenant.year - 2)
        self.assertEqual(f.filtrer_par_periode(self.toutes, annee),
                         [self.vieux])

    def test_mois_precis(self):
        self.assertEqual(f.filtrer_par_periode(self.toutes, f.mois_en_cours()),
                         [self.ce_mois])

    def test_mois_dernier_par_son_nom(self):
        """Ce que fait desormais la fleche « precedent » : on nomme le mois,
        au lieu de demander « le mois dernier »."""
        veille = le_mois_dernier(self.maintenant)
        libelle = f"{f.MOIS_FR[veille.month - 1]} {veille.year}"

        self.assertEqual(f.filtrer_par_periode(self.toutes, libelle),
                         [self.mois_dernier])

    def test_trente_derniers_jours(self):
        recente = recharge(self.maintenant - timedelta(days=5))
        ancienne = recharge(self.maintenant - timedelta(days=45))
        gardees = f.filtrer_par_periode([recente, ancienne],
                                        "30 derniers jours")
        self.assertEqual(gardees, [recente])

    def test_liste_vide(self):
        self.assertEqual(f.filtrer_par_periode([], f.mois_en_cours()), [])

    def test_date_illisible_ne_fait_pas_planter(self):
        bancale = {"date": "pas une date", "kwh": 1, "cout_eur": 1}
        f.filtrer_par_periode([bancale], "30 derniers jours")   # ne leve pas


class TestBornesPeriode(unittest.TestCase):

    def test_mois_precis(self):
        """Fevrier 2026 : du 1er au 28."""
        debut, fin = f.bornes_periode("Fevrier 2026", [])
        self.assertEqual((debut.day, debut.month), (1, 2))
        self.assertEqual((fin.day, fin.month), (28, 2))

    def test_mois_de_31_jours(self):
        debut, fin = f.bornes_periode("Mars 2026", [])
        self.assertEqual(fin.day, 31)

    def test_annee_precise(self):
        debut, fin = f.bornes_periode("2025", [])
        self.assertEqual((debut.month, debut.day), (1, 1))
        self.assertEqual((fin.month, fin.day), (12, 31))

    def test_tout_sans_donnees(self):
        self.assertIsNone(f.bornes_periode("Tout", []))


class TestMoisContinus(unittest.TestCase):

    def test_comble_les_trous(self):
        self.assertEqual(f.mois_continus(["2024-01", "2024-04"]),
                         ["2024-01", "2024-02", "2024-03", "2024-04"])

    def test_passe_l_annee(self):
        self.assertEqual(f.mois_continus(["2024-11", "2025-02"]),
                         ["2024-11", "2024-12", "2025-01", "2025-02"])

    def test_un_seul_mois(self):
        self.assertEqual(f.mois_continus(["2024-01"]), ["2024-01"])

    def test_liste_vide(self):
        self.assertEqual(f.mois_continus([]), [])


class TestAgregerPar(unittest.TestCase):

    def setUp(self):
        maintenant = datetime.now()
        self.recharges = [
            recharge(maintenant, kwh=10, cout=2, tarif_nom="Mon contrat"),
            recharge(maintenant, kwh=20, cout=4, tarif_nom="Mon contrat"),
            recharge(maintenant, kwh=30, cout=15, lieu="exterieur",
                     operateur="Ionity"),
        ]

    def test_regroupe_et_cumule(self):
        par_tarif = f.agreger_par(self.recharges, "tarif_nom", "maison")
        self.assertEqual(par_tarif["Mon contrat"]["n"], 2)
        self.assertAlmostEqual(par_tarif["Mon contrat"]["kwh"], 30)
        self.assertAlmostEqual(par_tarif["Mon contrat"]["cout"], 6)

    def test_le_lieu_limite_la_selection(self):
        par_op = f.agreger_par(self.recharges, "operateur", "exterieur")
        self.assertEqual(list(par_op), ["Ionity"])

    def test_valeur_par_defaut_quand_le_champ_manque(self):
        par_op = f.agreger_par(self.recharges, "operateur", defaut="Inconnu")
        self.assertEqual(par_op["Inconnu"]["n"], 2)


class TestRecherche(unittest.TestCase):

    def setUp(self):
        maintenant = datetime.now()
        self.ionity = recharge(maintenant, lieu="exterieur",
                               operateur="Ionity", lieu_detail="Montpellier")
        self.maison = recharge(maintenant, tarif_nom="Mon contrat HP/HC")
        self.toutes = [self.ionity, self.maison]

    def test_par_operateur(self):
        self.assertEqual(f.filtrer_par_recherche(self.toutes, "ionity"),
                         [self.ionity])

    def test_insensible_a_la_casse(self):
        self.assertEqual(f.filtrer_par_recherche(self.toutes, "IONITY"),
                         [self.ionity])

    def test_par_lieu(self):
        self.assertEqual(f.filtrer_par_recherche(self.toutes, "montpel"),
                         [self.ionity])

    def test_par_tarif(self):
        self.assertEqual(f.filtrer_par_recherche(self.toutes, "contrat"),
                         [self.maison])

    def test_recherche_vide_rend_tout(self):
        self.assertEqual(len(f.filtrer_par_recherche(self.toutes, "   ")), 2)

    def test_sans_resultat(self):
        self.assertEqual(f.filtrer_par_recherche(self.toutes, "zzzz"), [])


class TestTri(unittest.TestCase):

    def setUp(self):
        maintenant = datetime.now()
        self.petite = recharge(maintenant, kwh=5, cout=1,
                               tarif_nom="Zeta")
        self.grande = recharge(maintenant, kwh=50, cout=10,
                               tarif_nom="Alpha")
        self.toutes = [self.petite, self.grande]

    def test_par_energie_croissante(self):
        tries = f.trier_recharges(self.toutes, "kwh", decroissant=False)
        self.assertEqual(tries[0], self.petite)

    def test_par_energie_decroissante(self):
        tries = f.trier_recharges(self.toutes, "kwh", decroissant=True)
        self.assertEqual(tries[0], self.grande)

    def test_colonne_mixte_tarif_ou_operateur(self):
        tries = f.trier_recharges(self.toutes, "info", decroissant=False)
        self.assertEqual(tries[0], self.grande)      # Alpha avant Zeta

    def test_ne_modifie_pas_la_liste_d_origine(self):
        f.trier_recharges(self.toutes, "kwh", decroissant=True)
        self.assertEqual(self.toutes[0], self.petite)


class TestTexteResume(unittest.TestCase):

    def test_compte_energie_et_cout(self):
        maintenant = datetime.now()
        texte = f.texte_resume([recharge(maintenant, kwh=10, cout=2),
                                recharge(maintenant, kwh=20, cout=4)])
        self.assertIn("2 recharges", texte)
        self.assertIn("30,00\xa0kWh", texte)
        self.assertIn("6,00\xa0€", texte)

    def test_une_seule_recharge_au_singulier(self):
        texte = f.texte_resume([recharge(datetime.now(), kwh=10, cout=2)])
        self.assertIn(" 1 recharge · ", texte)

    def test_prix_exterieur_indique_a_part(self):
        """La moyenne globale seule serait trompeuse : l'exterieur coute plus cher."""
        maintenant = datetime.now()
        texte = f.texte_resume([recharge(maintenant, kwh=10, cout=1),
                                recharge(maintenant, kwh=10, cout=5,
                                         lieu="exterieur")])
        self.assertIn("extérieur", texte)

    def test_pas_de_mention_si_tout_est_exterieur(self):
        maintenant = datetime.now()
        texte = f.texte_resume([recharge(maintenant, lieu="exterieur")])
        self.assertNotIn("exterieur :", texte)

    def test_liste_vide(self):
        # Zero se construit au singulier en francais : « 0 recharge ».
        self.assertIn("0 recharge ·", f.texte_resume([]))


class TestPeriodesDisponibles(unittest.TestCase):

    def test_les_raccourcis_viennent_en_tete(self):
        periodes = f.periodes_disponibles([])
        self.assertEqual(periodes[:len(f.PERIODES)], f.PERIODES)

    def test_les_annees_et_mois_presents_sont_ajoutes(self):
        recharges = [{"date": "2026-06-01T10:00"}, {"date": "2025-03-01T10:00"}]
        periodes = f.periodes_disponibles(recharges)
        self.assertIn("2026", periodes)
        self.assertIn("2025", periodes)
        self.assertIn("Juin 2026", periodes)
        self.assertIn("Mars 2025", periodes)

    def test_date_illisible_ignoree(self):
        periodes = f.periodes_disponibles([{"date": "n'importe quoi"}])
        self.assertEqual(periodes, f.PERIODES)


if __name__ == "__main__":
    unittest.main(verbosity=2)
