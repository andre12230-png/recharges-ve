"""Tests du controle des saisies (saisie.py).

Ces fonctions sont pures : elles recoivent le texte tape et rendent une
valeur, ou levent ErreurSaisie. Aucun fichier n'est lu ni ecrit, aucune
fenetre ouverte — pas de redirection RECHARGES_DATA_DIR a poser ici, comme
pour test_filtres.py et test_contraste.py.

    py -m pytest

Ce qui est verifie en plus des valeurs rendues : que CHAQUE message est en
francais et designe le champ fautif. C'est tout l'objet du module : avant
lui, l'ecran affichait « could not convert string to float: '' ».
"""

import sys
import unittest
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from saisie import (  # noqa: E402
    ErreurSaisie,
    lire_date_heure,
    lire_duree,
    lire_nombre,
    parse_date_fr,
)


class TestLireNombre(unittest.TestCase):
    def test_nombre_simple(self):
        self.assertEqual(lire_nombre("12.4", "c", "l'énergie"), 12.4)

    def test_virgule_decimale(self):
        """Le pave numerique du clavier donne une virgule, pas un point."""
        self.assertEqual(lire_nombre("12,4", "c", "l'énergie"), 12.4)

    def test_espaces_des_milliers(self):
        """« 123 456,7 » : un kilometrage ecrit a la francaise."""
        self.assertEqual(lire_nombre("123 456,7", "c", "le kilométrage"),
                         123456.7)

    def test_espace_insecable(self):
        """Celui que collent les tableurs quand on copie une cellule."""
        self.assertEqual(lire_nombre("1 234", "c", "le kilométrage"), 1234)

    def test_champ_vide_obligatoire(self):
        with self.assertRaises(ErreurSaisie) as ctx:
            lire_nombre("   ", "champ_m_kwh", "l'énergie consommée")
        self.assertEqual(ctx.exception.champ, "champ_m_kwh")
        self.assertEqual(ctx.exception.message,
                         "Indiquez l'énergie consommée.")

    def test_champ_vide_facultatif(self):
        self.assertIsNone(lire_nombre("", "c", "la conso", obligatoire=False))

    def test_texte_qui_n_est_pas_un_nombre(self):
        """Le cas qui affichait l'erreur Python en anglais."""
        with self.assertRaises(ErreurSaisie) as ctx:
            lire_nombre("douze", "champ_m_kwh", "l'énergie")
        self.assertEqual(ctx.exception.champ, "champ_m_kwh")
        self.assertIn("n'est pas un nombre", ctx.exception.message)
        self.assertIn("douze", ctx.exception.message)

    def test_valeur_negative(self):
        with self.assertRaises(ErreurSaisie) as ctx:
            lire_nombre("-3", "c", "l'énergie")
        self.assertEqual(ctx.exception.message, "Indiquez un nombre positif.")

    def test_zero_refuse_quand_il_doit_etre_positif(self):
        with self.assertRaises(ErreurSaisie) as ctx:
            lire_nombre("0", "c", "l'énergie consommée",
                        strictement_positif=True)
        self.assertEqual(ctx.exception.message,
                         "L'énergie consommée ne peut pas être à zéro.")

    def test_zero_accepte_par_defaut(self):
        """Un cout de 0 € est legitime : une borne gratuite."""
        self.assertEqual(lire_nombre("0", "c", "le coût"), 0)

    def test_infini_et_nan_refuses(self):
        """float() les accepte ; ils fausseraient tous les calculs."""
        for texte in ("inf", "nan", "-inf"):
            with self.subTest(texte=texte):
                with self.assertRaises(ErreurSaisie) as ctx:
                    lire_nombre(texte, "c", "l'énergie")
                self.assertIn("n'est pas un nombre", ctx.exception.message)


class TestLireDateHeure(unittest.TestCase):
    """Les deux cases des formulaires : le jour, puis l'heure.

    L'une peut rester vide sans bloquer l'autre : sans jour, c'est
    aujourd'hui ; sans heure, minuit.
    """

    def jour(self, **ecarts):
        return datetime.now().replace(second=0, microsecond=0, **ecarts)

    def lire(self, jour, heure, **kw):
        return lire_date_heure(jour, heure, "champ_jour", "champ_heure",
                               "la date et l'heure", **kw)

    def test_les_deux_cases_remplies(self):
        self.assertEqual(self.lire("18/09/2026", "22:30"),
                         datetime(2026, 9, 18, 22, 30))

    def test_forme_courte_dans_chaque_case(self):
        annee = datetime.now().year
        self.assertEqual(self.lire("18/09", "22h30"),
                         datetime(annee, 9, 18, 22, 30))

    def test_sans_jour_c_est_aujourd_hui(self):
        """Le cas le plus courant : on change l'heure, pas la date."""
        self.assertEqual(self.lire("", "22h30"),
                         self.jour(hour=22, minute=30))

    def test_sans_heure_c_est_minuit(self):
        self.assertEqual(self.lire("18/09/2026", ""),
                         datetime(2026, 9, 18))

    def test_les_deux_vides_quand_c_est_facultatif(self):
        self.assertIsNone(self.lire("", "  ", obligatoire=False))

    def test_les_deux_vides_quand_c_est_obligatoire(self):
        with self.assertRaises(ErreurSaisie) as ctx:
            self.lire("", "")
        self.assertEqual(ctx.exception.champ, "champ_jour")
        self.assertEqual(ctx.exception.message,
                         "Indiquez la date et l'heure.")

    def test_tout_tape_dans_la_case_du_jour(self):
        """Habitude de l'ancienne case unique : on repartit plutot que de
        refuser. « 18/09 22h30 » colle en entier dans la case du jour."""
        annee = datetime.now().year
        self.assertEqual(self.lire("18/09 22h30", ""),
                         datetime(annee, 9, 18, 22, 30))

    def test_le_message_designe_la_case_du_jour(self):
        with self.assertRaises(ErreurSaisie) as ctx:
            self.lire("32/13/2026", "10:00")
        self.assertEqual(ctx.exception.champ, "champ_jour")
        self.assertIn("n'est pas une date", ctx.exception.message)
        self.assertIn("jj/mm/aaaa", ctx.exception.message)

    def test_le_message_designe_la_case_de_l_heure(self):
        """Toute la valeur des deux cases : dire LAQUELLE est en cause."""
        with self.assertRaises(ErreurSaisie) as ctx:
            self.lire("18/09/2026", "25h30")
        self.assertEqual(ctx.exception.champ, "champ_heure")
        self.assertIn("n'est pas une heure", ctx.exception.message)
        self.assertIn("hh:mm", ctx.exception.message)

    def test_le_recul_d_annee_passe_par_les_deux_cases(self):
        self.assertEqual(
            lire_date_heure("30/12", "22h30", "champ_jour", "champ_heure",
                            "la date", passe=True,
                            maintenant=datetime(2027, 1, 2, 9, 0)),
            datetime(2026, 12, 30, 22, 30))


class TestParseDateFr(unittest.TestCase):
    """Le parseur lui-meme, sous toutes ses formes."""

    JOUR = datetime(2026, 9, 18)

    def test_formes_completes(self):
        """Ce qui marchait avant doit marcher encore."""
        for texte in ("18/09/2026 22:30", "18/09/2026 22h30",
                      "18/09/2026 22 h 30"):
            with self.subTest(texte=texte):
                self.assertEqual(parse_date_fr(texte),
                                 datetime(2026, 9, 18, 22, 30))

    def test_date_seule_vaut_minuit(self):
        self.assertEqual(parse_date_fr("18/09/2026"), self.JOUR)

    def test_heure_sans_minutes(self):
        """« 22h » : une recharge branchee a l'heure pile."""
        self.assertEqual(parse_date_fr("18/09/2026 22h"),
                         datetime(2026, 9, 18, 22, 0))

    def test_annee_implicite(self):
        """« 18/09 » : l'annee en cours, qu'on ne retape pas."""
        annee = datetime.now().year
        self.assertEqual(parse_date_fr("18/09"), datetime(annee, 9, 18))

    def test_heure_seule_vaut_aujourd_hui(self):
        """« 22h30 » : le cas le plus courant, une recharge du soir."""
        attendu = datetime.now().replace(hour=22, minute=30, second=0,
                                         microsecond=0)
        self.assertEqual(parse_date_fr("22h30"), attendu)

    def test_annee_sur_deux_chiffres(self):
        """Le piege : « %Y » de strptime lirait « 26 » comme l'an 26, sans
        rien dire, et la recharge partirait vingt siecles en arriere."""
        self.assertEqual(parse_date_fr("18/09/26"), self.JOUR)
        self.assertEqual(parse_date_fr("18/09/26 8h05"),
                         datetime(2026, 9, 18, 8, 5))

    def test_jour_et_mois_sans_zero(self):
        self.assertEqual(parse_date_fr("8/9/2026"), datetime(2026, 9, 8))

    def test_29_fevrier_d_une_annee_bissextile(self):
        """Colle l'annee au texte plutot que d'utiliser un format « %d/%m » :
        strptime daterait celui-ci de 1900, qui n'est pas bissextile."""
        self.assertEqual(parse_date_fr("29/02/2024"), datetime(2024, 2, 29))


class TestAnneeImpliciteDansLePasse(unittest.TestCase):
    """Le reglage `passe=True` des recharges et des releves kilometriques.

    `maintenant` est impose : ces regles ne doivent pas dependre du jour ou
    les tests tournent.
    """

    DEUX_JANVIER = datetime(2027, 1, 2, 9, 0)

    def test_fin_d_annee_saisie_en_janvier(self):
        """Le 2 janvier, « 30/12 » est le 30 decembre qui vient de passer."""
        self.assertEqual(
            parse_date_fr("30/12", passe=True, maintenant=self.DEUX_JANVIER),
            datetime(2026, 12, 30))

    def test_l_heure_suit_le_recul_d_annee(self):
        self.assertEqual(
            parse_date_fr("30/12 22h30", passe=True,
                          maintenant=self.DEUX_JANVIER),
            datetime(2026, 12, 30, 22, 30))

    def test_une_date_deja_passee_ne_bouge_pas(self):
        self.assertEqual(
            parse_date_fr("01/01", passe=True, maintenant=self.DEUX_JANVIER),
            datetime(2027, 1, 1))

    def test_faute_de_frappe_de_quelques_jours(self):
        """Le 18 septembre, « 20/09 » est une faute de deux jours, pas une
        date de l'annee derniere : le recul ne joue qu'au-dela de six mois.
        Une date fausse de deux jours se voit ; fausse d'un an, non."""
        self.assertEqual(
            parse_date_fr("20/09", passe=True,
                          maintenant=datetime(2026, 9, 18, 9, 0)),
            datetime(2026, 9, 20))

    def test_sans_le_reglage_l_annee_courante_est_gardee(self):
        """Une periode tarifaire peut commencer plus tard : pas de recul."""
        self.assertEqual(
            parse_date_fr("30/12", maintenant=self.DEUX_JANVIER),
            datetime(2027, 12, 30))

    def test_une_annee_ecrite_est_prise_au_mot(self):
        """Le recul ne concerne que les annees devinees."""
        self.assertEqual(
            parse_date_fr("30/12/2027", passe=True,
                          maintenant=self.DEUX_JANVIER),
            datetime(2027, 12, 30))


class TestDatesRefusees(unittest.TestCase):
    def test_formes_illisibles(self):
        cas = [
            ("2026-09-18", "format americain"),
            ("18-09-2026", "tirets"),
            ("hier soir", "du texte"),
            ("32/13/2026", "jour et mois impossibles"),
            ("18/09/226", "annee a trois chiffres"),
            ("25h30", "une heure qui n'existe pas"),
            ("18/09/2026 22:30 plus", "trois morceaux"),
            ("", "rien"),
            ("   ", "des espaces"),
        ]
        for texte, pourquoi in cas:
            with self.subTest(pourquoi=pourquoi):
                with self.assertRaises(ValueError):
                    parse_date_fr(texte)


class TestLireDuree(unittest.TestCase):
    """Une durée s'écrit avec un « + » devant, à la place de l'heure de fin.

    Le « + » n'est pas une coquetterie : sans lui, « 6h12 » est une heure de
    la matinée, pas une durée de six heures douze. C'est toute la raison
    d'être de ce signe.
    """

    def test_le_signe_leve_l_ambiguite(self):
        self.assertIsNone(lire_duree("6h12"))
        self.assertEqual(lire_duree("+6h12"), timedelta(hours=6, minutes=12))

    def test_les_formes_acceptees(self):
        cas = {
            "+6h12": timedelta(hours=6, minutes=12),
            "+6:12": timedelta(hours=6, minutes=12),
            "+6h": timedelta(hours=6),
            "+45min": timedelta(minutes=45),
            "+0h45": timedelta(minutes=45),
            "  +6h12  ": timedelta(hours=6, minutes=12),
        }
        for texte, attendu in cas.items():
            with self.subTest(texte=texte):
                self.assertEqual(lire_duree(texte), attendu)

    def test_rien_a_lire(self):
        """Sans « + », ce n'est pas une durée : la case reste une heure."""
        for texte in ("", "   ", "22:30", "18/09"):
            with self.subTest(texte=texte):
                self.assertIsNone(lire_duree(texte))

    def test_le_signe_seul_ou_suivi_de_n_importe_quoi(self):
        for texte in ("+", "+abc", "+6h12min", "+ 6 h 12 min"):
            with self.subTest(texte=texte):
                with self.assertRaises(ValueError) as ctx:
                    lire_duree(texte)
                self.assertIn("+6h12", str(ctx.exception))

    def test_duree_nulle_refusee(self):
        """Elle donnerait une fin égale au début."""
        for texte in ("+0h00", "+0min", "+0h"):
            with self.subTest(texte=texte):
                with self.assertRaises(ValueError) as ctx:
                    lire_duree(texte)
                self.assertIn("supérieure à zéro", str(ctx.exception))

    def test_une_charge_de_plus_de_douze_heures(self):
        """Rien ne l'interdit : une charge lente sur prise domestique."""
        self.assertEqual(lire_duree("+14h30"), timedelta(hours=14, minutes=30))


class TestMessagesEnFrancais(unittest.TestCase):
    """Aucun message ne doit laisser passer une phrase de Python."""

    CAS = [
        (lire_nombre, ("", "c", "l'énergie")),
        (lire_nombre, ("douze", "c", "l'énergie")),
        (lire_nombre, ("-1", "c", "l'énergie")),
        (lire_date_heure, ("", "", "cj", "ch", "la date")),
        (lire_date_heure, ("hier", "", "cj", "ch", "la date")),
        (lire_date_heure, ("18/09", "midi", "cj", "ch", "la date")),
    ]

    def test_pas_un_mot_d_anglais_dans_les_messages(self):
        interdits = ("could not", "invalid", "float", "ValueError",
                     "does not match", "Traceback")
        for fonction, args in self.CAS:
            with self.subTest(args=args):
                with self.assertRaises(ErreurSaisie) as ctx:
                    fonction(*args)
                message = ctx.exception.message
                for mot in interdits:
                    self.assertNotIn(mot.lower(), message.lower())
                self.assertTrue(message.endswith((".", ")")), message)


if __name__ == "__main__":
    unittest.main()
