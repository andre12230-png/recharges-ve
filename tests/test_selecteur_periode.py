"""Tests du selecteur de periode en deux menus (filtres.py).

Ces fonctions decident de ce que les deux menus proposent et de ce que font
les deux fleches. Comme le reste de filtres.py, elles sont pures : aucune
fenetre n'est ouverte ici.

    py -m pytest

Les jeux d'essai sont construits par rapport a MAINTENANT, jamais avec des
dates ecrites en dur : le mois en cours fait partie de ce qui est teste, et
un test date en dur cesserait de passer le mois suivant.
"""

import sys
import unittest
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import filtres as f  # noqa: E402

MAINTENANT = datetime.now()
ANNEE = str(MAINTENANT.year)
MOIS_COURANT = f.MOIS_FR[MAINTENANT.month - 1]


def recharge(iso: str) -> dict:
    """Une recharge reduite a ce que le selecteur regarde : sa date."""
    return {"date": iso, "kwh": 10.0, "cout_eur": 2.0, "lieu": "maison"}


class TestPeriodeDOuverture(unittest.TestCase):
    """Sur quelle période chaque page s'ouvre, et pourquoi pas la même.

    Règle du 07/09/2026 : on n'ouvre JAMAIS sur la dernière période
    consultée — prendre de vieux chiffres pour ceux du mois courant est une
    erreur qu'on ne voit pas. Les valeurs se recalculent donc à chaque
    lancement, elles ne se relisent nulle part.
    """

    def test_le_mois_en_cours_se_recalcule_toujours(self):
        self.assertEqual(f.mois_en_cours(), f"{MOIS_COURANT} {ANNEE}")

    def test_l_annee_en_cours_aussi(self):
        self.assertEqual(f.annee_en_cours(), ANNEE)

    def test_l_annee_est_une_periode_que_le_filtre_comprend(self):
        """« 2026 » doit filtrer, pas retomber en silence sur « tout »."""
        rs = [recharge(f"{ANNEE}-03-10T08:00"),
              recharge(f"{int(ANNEE) - 1}-03-10T08:00")]
        self.assertEqual(len(f.filtrer_par_periode(rs, f.annee_en_cours())), 1)

    def test_les_statistiques_ouvrent_sur_l_annee(self):
        """Leur graphique s'intitule « énergie & coût par mois » : réduit à
        un seul mois, il n'affiche qu'une barre qui ne se compare à rien.
        Demande d'André du 19/09/2026, en lisant son écran de septembre."""
        source = (Path(__file__).resolve().parent.parent / "fenetre.py"
                  ).read_text(encoding="utf-8")
        self.assertIn("self.filtre_periode_stats: str = annee_en_cours()",
                      source)

    def test_les_autres_pages_gardent_le_mois(self):
        """L'Historique et le Tableau de bord montrent des chiffres, pas une
        série : le mois y reste la bonne échelle. Sans recharge ce mois-ci,
        « Toute la période » (charte, 08/10/2026 ; voir
        test_ouverture_periode.py, qui le vérifie sur la fenêtre)."""
        source = (Path(__file__).resolve().parent.parent / "fenetre.py"
                  ).read_text(encoding="utf-8")
        for attribut in ("self.filtre_periode: str",
                         "self.filtre_periode_dashboard: str"):
            with self.subTest(attribut=attribut):
                self.assertIn(f"{attribut} = ouverture", source)

    def test_l_export_garde_tout(self):
        """On y choisit sa période exprès : voir la nuance du 07/09/2026."""
        source = (Path(__file__).resolve().parent.parent / "fenetre.py"
                  ).read_text(encoding="utf-8")
        self.assertIn('self.filtre_periode_export: str = "Tout"', source)


class TestMenuDesAnnees(unittest.TestCase):
    def test_les_raccourcis_puis_les_annees(self):
        """Le menu tient en quelques lignes, la ou l'ancienne liste unique en
        comptait 42."""
        rs = [recharge("2023-04-10T08:00"), recharge("2024-11-02T08:00")]

        annees = f.annees_disponibles(rs)

        self.assertEqual(annees[:2], ["Tout", "30 derniers jours"])
        self.assertEqual(annees[2:], sorted({ANNEE, "2024", "2023"},
                                            reverse=True))

    def test_l_annee_en_cours_est_toujours_la(self):
        """Sans elle, l'application ne pourrait pas s'ouvrir sur le mois en
        cours en debut d'annee, avant la premiere recharge."""
        annees = f.annees_disponibles([recharge("2019-01-05T08:00")])

        self.assertIn(ANNEE, annees)

    def test_les_raccourcis_relatifs_ont_disparu(self):
        """« Ce mois » et « Mois dernier » ne sont plus proposes : les deux
        menus et les deux fleches font le meme geste en plus direct."""
        annees = f.annees_disponibles([])

        self.assertNotIn("Ce mois", annees)
        self.assertNotIn("Mois dernier", annees)


class TestMenuDesMois(unittest.TestCase):
    def test_seuls_les_mois_de_l_annee_choisie(self):
        """Choisir 2024 ne doit pas proposer les mois de 2023 : sinon on croit
        avoir change de mois alors qu'on a change d'annee."""
        rs = [recharge("2023-04-10T08:00"), recharge("2024-11-02T08:00"),
              recharge("2024-02-15T08:00")]

        self.assertEqual(f.mois_disponibles(rs, "2024"),
                         ["Toute l'année", "Novembre", "Février"])

    def test_les_mois_sont_accentues(self):
        rs = [recharge("2024-02-15T08:00"), recharge("2024-08-15T08:00"),
              recharge("2024-12-15T08:00")]

        mois = f.mois_disponibles(rs, "2024")

        self.assertIn("Février", mois)
        self.assertIn("Août", mois)
        self.assertIn("Décembre", mois)

    def test_le_mois_en_cours_est_propose_meme_vide(self):
        """C'est celui sur lequel l'application s'ouvre : « aucune recharge ce
        mois-ci » est une reponse, un menu qui ne le propose pas n'en est pas
        une."""
        mois = f.mois_disponibles([recharge("2019-01-05T08:00")], ANNEE)

        self.assertIn(MOIS_COURANT, mois)


class TestLectureDUnePeriode(unittest.TestCase):
    def test_annee_et_mois_d_une_periode(self):
        self.assertEqual(f.annee_de_periode("Juin 2026"), "2026")
        self.assertEqual(f.nom_du_mois("Juin 2026"), "Juin")
        self.assertEqual(f.annee_de_periode("2025"), "2025")
        self.assertIsNone(f.nom_du_mois("2025"))

    def test_un_raccourci_n_a_ni_annee_ni_mois(self):
        for raccourci in ("Tout", "30 derniers jours"):
            self.assertIsNone(f.annee_de_periode(raccourci), raccourci)
            self.assertIsNone(f.nom_du_mois(raccourci), raccourci)

    def test_l_ancienne_ecriture_sans_accent_reste_comprise(self):
        """Les noms de mois ont ete accentues ; « Fevrier 2026 » doit continuer
        a designer fevrier, sans quoi une valeur restee quelque part
        filtrerait dans le vide."""
        self.assertEqual(f.annee_de_periode("Fevrier 2026"), "2026")
        self.assertEqual(f.nom_du_mois("Fevrier 2026"), "Février")
        self.assertEqual(len(f.filtrer_par_periode(
            [recharge("2026-02-10T08:00")], "Fevrier 2026")), 1)

    def test_le_mois_en_cours_se_recalcule(self):
        """Aucune memorisation : le libelle est fabrique a chaque appel, donc
        il suit le calendrier tout seul."""
        self.assertEqual(f.mois_en_cours(), f"{MOIS_COURANT} {ANNEE}")


class TestLesDeuxFleches(unittest.TestCase):
    def setUp(self):
        self.rs = [recharge("2024-02-15T08:00"), recharge("2024-03-15T08:00"),
                   recharge("2024-05-15T08:00"), recharge("2025-01-15T08:00")]

    def test_recule_d_un_mois(self):
        self.assertEqual(f.periode_voisine(self.rs, "Mars 2024", -1),
                         "Février 2024")

    def test_saute_les_mois_sans_recharge(self):
        """Avril 2024 n'a aucune recharge : la fleche passe directement de mai
        a mars, plutot que d'afficher un mois vide."""
        self.assertEqual(f.periode_voisine(self.rs, "Mai 2024", -1),
                         "Mars 2024")

    def test_franchit_le_changement_d_annee(self):
        self.assertEqual(f.periode_voisine(self.rs, "Janvier 2025", -1),
                         "Mai 2024")

    def test_s_arrete_au_debut_de_l_historique(self):
        """None grise la fleche, au lieu de la laisser cliquable sans effet."""
        self.assertIsNone(f.periode_voisine(self.rs, "Février 2024", -1))

    def test_va_jusqu_au_mois_en_cours(self):
        """Meme sans recharge ce mois-ci : c'est la periode d'ouverture, elle
        doit rester atteignable a la fleche."""
        echelle = f._echelle_de_navigation(self.rs, "Mars 2024")

        self.assertEqual(echelle[-1], f.mois_en_cours())

    def test_garde_l_echelle(self):
        """Sur une annee, la fleche change d'annee — jamais de mois."""
        self.assertEqual(f.periode_voisine(self.rs, "2025", -1), "2024")

    def test_un_raccourci_n_a_ni_avant_ni_apres(self):
        """« Tout » couvre deja tout : les deux fleches sont grisees."""
        self.assertIsNone(f.periode_voisine(self.rs, "Tout", -1))
        self.assertIsNone(f.periode_voisine(self.rs, "Tout", +1))

    def test_aucune_recharge_ne_casse_rien(self):
        self.assertIsNone(f.periode_voisine([], "Mars 2024", -1))
        self.assertEqual(f.mois_disponibles([], "2024"), ["Toute l'année"])


if __name__ == "__main__":
    unittest.main()
