"""Tests du moteur de calcul de Recharges VE.

Pour les lancer, depuis le dossier du projet :

    py -m pytest

ou tout simplement :

    py tests\\test_recharges.py

La suite complete se lance avec pytest (voir requirements-dev.txt). Ce fichier
seul tourne aussi sans rien installer : unittest fait partie de Python.

IMPORTANT — ces tests n'ecrivent JAMAIS dans vos vraies donnees. La variable
d'environnement RECHARGES_DATA_DIR est posee ci-dessous AVANT d'importer
recharges.py : recharges.json, tarifs.json et backups/ sont donc rediriges vers
un dossier temporaire, efface a la fin. Vos 251 recharges ne sont pas touchees.
"""

import json
import os
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest
from datetime import date, datetime
from pathlib import Path

# --- redirection des donnees : doit venir AVANT l'import de recharges -------
DOSSIER_TEST = Path(tempfile.mkdtemp(prefix="recharges_tests_"))
os.environ["RECHARGES_DATA_DIR"] = str(DOSSIER_TEST)
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import recharges as r  # noqa: E402  (l'import doit suivre la redirection)

# Ceinture et bretelles : la variable d'environnement ci-dessus ne fait effet
# que si ce fichier est le premier a importer recharges. Depuis qu'un autre
# test importe app.py (donc recharges), ce n'est plus garanti — on redirige
# donc aussi apres coup, ce qui marche quel que soit l'ordre des fichiers.
r.rediriger_donnees(DOSSIER_TEST)


def tearDownModule():
    """Efface le dossier temporaire une fois tous les tests passes."""
    shutil.rmtree(DOSSIER_TEST, ignore_errors=True)


def effacer_vraiment(dossier: Path) -> None:
    """Efface un dossier, meme s'il contient un depot git.

    Sous Windows, git marque ses fichiers internes en lecture seule et
    shutil.rmtree refuse alors de les supprimer (PermissionError). On leve
    la protection au vol sur les fichiers qui resistent.
    """
    def insister(fonction, chemin, _exception):
        os.chmod(chemin, stat.S_IWRITE)
        fonction(chemin)

    shutil.rmtree(dossier, onexc=insister)


# ---------------------------------------------------------------------------
# Fabriques de tarifs : evitent de repeter dix cles a chaque test
# ---------------------------------------------------------------------------

def tarif_simple(prix_kwh, debut="2026-01-01", fin=None, nom="Simple",
                 abonnement=0.0, id_tarif="t_simple"):
    return {"id": id_tarif, "nom": nom, "type": "simple", "debut": debut,
            "fin": fin, "prix_kwh": prix_kwh, "abonnement_mensuel": abonnement}


def tarif_hp_hc(prix_hp, prix_hc, plages, debut="2026-01-01", fin=None,
                nom="HP/HC", abonnement=0.0, id_tarif="t_hphc"):
    return {"id": id_tarif, "nom": nom, "type": "hp_hc", "debut": debut,
            "fin": fin, "prix_hp": prix_hp, "prix_hc": prix_hc,
            "plages_hc": plages, "abonnement_mensuel": abonnement}


def dt(texte):
    """« 2026-03-02 21:00 » -> datetime. Raccourci de lecture."""
    return datetime.fromisoformat(texte)


# ---------------------------------------------------------------------------
# calculer_cout
# ---------------------------------------------------------------------------

class TestCalculerCout(unittest.TestCase):
    """La charge de reference : 40 kWh du 2 mars 21:00 au 3 mars 01:00 (4 h).

    Avec des heures creuses de 22:00 a 06:00, 3 des 4 heures tombent en
    heures creuses, soit 30 kWh HC et 10 kWh HP.
    """

    DEBUT = "2026-03-02 21:00"
    FIN = "2026-03-03 01:00"
    KWH = 40.0

    def cout_reference(self, plages):
        return r.calculer_cout(dt(self.DEBUT), dt(self.FIN), self.KWH,
                               [tarif_hp_hc(0.20, 0.10, plages)])

    def test_tarif_simple(self):
        res = r.calculer_cout(dt("2026-03-02 10:00"), dt("2026-03-02 12:00"),
                              10.0, [tarif_simple(0.20)])
        self.assertAlmostEqual(res["cout"], 2.00, places=2)
        self.assertAlmostEqual(res["kwh_hp"], 10.0, places=3)
        self.assertAlmostEqual(res["kwh_hc"], 0.0, places=3)

    def test_plage_a_cheval_sur_minuit(self):
        res = self.cout_reference([["22:00", "06:00"]])
        self.assertAlmostEqual(res["kwh_hc"], 30.0, places=3)
        self.assertAlmostEqual(res["kwh_hp"], 10.0, places=3)
        self.assertAlmostEqual(res["cout"], 5.00, places=2)

    def test_plages_qui_se_chevauchent(self):
        """Bug § 2.1 de l'audit : le chevauchement faisait tout basculer en HC.

        Les secondes communes aux deux plages etaient comptees deux fois, la
        part d'heures creuses depassait 100 %, et le min(..., 1.0) l'ecrasait
        a 1 : 40 kWh en heures creuses au lieu de 30, soit 4,00 EUR au lieu
        de 5,00 (20 % de sous-facturation, sans aucun avertissement).
        """
        res = self.cout_reference([["22:00", "06:00"], ["23:00", "02:00"]])
        self.assertAlmostEqual(res["kwh_hc"], 30.0, places=3)
        self.assertAlmostEqual(res["cout"], 5.00, places=2)

    def test_plages_jointives_ne_sont_pas_un_chevauchement(self):
        """22:00-00:00 puis 00:00-06:00 se touchent : total inchange."""
        res = self.cout_reference([["22:00", "00:00"], ["00:00", "06:00"]])
        self.assertAlmostEqual(res["kwh_hc"], 30.0, places=3)
        self.assertAlmostEqual(res["cout"], 5.00, places=2)

    def test_plages_decalees_de_quelques_minutes(self):
        """Des plages qui ne tombent pas sur l'heure ronde (23:45-05:15 et
        14:15-16:45), comme en proposent certaines offres.

        Sur la charge de reference, seules 23:45->01:00 tombent en heures
        creuses, soit 75 minutes sur 240 : 12,5 kWh. Ce test fige le
        comportement actuel — si un jour ce chiffre bouge, c'est une
        regression.
        """
        res = self.cout_reference([["23:45", "05:15"], ["14:15", "16:45"]])
        self.assertAlmostEqual(res["kwh_hc"], 12.5, places=3)

    def test_charge_entierement_en_heures_pleines(self):
        res = self.cout_reference([["02:00", "04:00"]])
        self.assertAlmostEqual(res["kwh_hc"], 0.0, places=3)
        self.assertAlmostEqual(res["cout"], 8.00, places=2)

    def test_session_d_une_minute(self):
        res = r.calculer_cout(dt("2026-03-02 23:00"), dt("2026-03-02 23:01"),
                              0.5, [tarif_hp_hc(0.20, 0.10,
                                                [["22:00", "06:00"]])])
        self.assertAlmostEqual(res["kwh_hc"], 0.5, places=3)
        self.assertAlmostEqual(res["cout"], 0.05, places=2)

    def test_aucun_tarif_pour_la_date(self):
        """Refuser plutot qu'enregistrer 0 EUR en silence."""
        with self.assertRaises(ValueError) as ctx:
            r.calculer_cout(dt("2025-06-01 10:00"), dt("2025-06-01 12:00"),
                            10.0, [tarif_simple(0.20, debut="2026-01-01")])
        self.assertIn("Aucun tarif", str(ctx.exception))

    def test_plage_couvrant_toute_la_journee(self):
        """00:00-00:00 ne compte rien : c'est le comportement d'avant."""
        res = self.cout_reference([["00:00", "00:00"], ["22:00", "06:00"]])
        self.assertAlmostEqual(res["kwh_hc"], 30.0, places=3)


# ---------------------------------------------------------------------------
# recharge a cheval sur un changement de tarif (§ 2.2)
# ---------------------------------------------------------------------------

class TestChangementDeTarif(unittest.TestCase):
    """Charge de 40 kWh du 10 juin 21:00 au 11 juin 05:00, soit 8 heures.

    L'ancien tarif s'arrete le 10 juin au soir, le nouveau prend la suite a
    minuit : 3 heures a l'ancien prix, 5 heures au nouveau.
    """

    DEBUT = "2026-06-10 21:00"
    FIN = "2026-06-11 05:00"
    KWH = 40.0

    ANCIEN = tarif_simple(0.10, debut="2026-01-01", fin="2026-06-10",
                          nom="Ancien", id_tarif="t_a")
    NOUVEAU = tarif_simple(0.30, debut="2026-06-11", fin=None,
                           nom="Nouveau", id_tarif="t_b")

    def cout(self, debut=None, fin=None, tarifs=None):
        return r.calculer_cout(dt(debut or self.DEBUT), dt(fin or self.FIN),
                               self.KWH, tarifs or [self.ANCIEN, self.NOUVEAU])

    def test_a_cheval_sur_deux_tarifs(self):
        """Bug § 2.2 : tout etait facture a l'ancien prix, 4,00 au lieu de 9,00.

        15 kWh (3 h sur 8) a 0,10 = 1,50, puis 25 kWh (5 h sur 8) a 0,30
        = 7,50.
        """
        res = self.cout()
        self.assertAlmostEqual(res["cout"], 9.00, places=2)

    def test_entierement_dans_l_ancien_tarif(self):
        res = self.cout(debut="2026-06-09 21:00", fin="2026-06-10 05:00")
        self.assertAlmostEqual(res["cout"], 4.00, places=2)
        self.assertEqual(res["tarif_nom"], "Ancien")

    def test_entierement_dans_le_nouveau_tarif(self):
        res = self.cout(debut="2026-06-11 21:00", fin="2026-06-12 05:00")
        self.assertAlmostEqual(res["cout"], 12.00, places=2)
        self.assertEqual(res["tarif_nom"], "Nouveau")

    def test_chaque_morceau_utilise_ses_propres_plages_hc(self):
        """Les plages d'heures creuses suivent le tarif du morceau, pas celui
        du debut de la session.

        Ancien : creux de 22:00 a 23:00 -> 1 h sur les 3 premieres heures.
        Nouveau : creux de 00:00 a 02:00 -> 2 h sur les 5 suivantes.
        """
        tarifs = [
            tarif_hp_hc(0.20, 0.10, [["22:00", "23:00"]], debut="2026-01-01",
                        fin="2026-06-10", nom="Ancien", id_tarif="t_a"),
            tarif_hp_hc(0.20, 0.10, [["00:00", "02:00"]], debut="2026-06-11",
                        fin=None, nom="Nouveau", id_tarif="t_b"),
        ]
        res = self.cout(tarifs=tarifs)
        self.assertAlmostEqual(res["kwh_hc"], 15.0, places=3)   # 5 + 10
        self.assertAlmostEqual(res["kwh_hp"], 25.0, places=3)   # 10 + 15
        self.assertAlmostEqual(res["cout"], 6.50, places=2)

    def test_les_deux_noms_sont_accoles(self):
        self.assertEqual(self.cout()["tarif_nom"], "Ancien + Nouveau")

    def test_un_nom_inchange_ne_produit_pas_de_doublon(self):
        """Le cas reel : un changement de prix qui garde le meme nom."""
        tarifs = [
            tarif_simple(0.10, debut="2026-01-01", fin="2026-06-10",
                         nom="Mon contrat HP/HC", id_tarif="t_a"),
            tarif_simple(0.30, debut="2026-06-11", fin=None,
                         nom="Mon contrat HP/HC", id_tarif="t_b"),
        ]
        self.assertEqual(self.cout(tarifs=tarifs)["tarif_nom"], "Mon contrat HP/HC")

    def test_le_tarif_retenu_est_celui_du_morceau_le_plus_long(self):
        """5 heures sur le nouveau contre 3 sur l'ancien : c'est le nouveau."""
        self.assertEqual(self.cout()["tarif_id"], "t_b")

    def test_trou_dans_la_grille_leve_une_erreur(self):
        """La session entre dans une periode non couverte : on refuse."""
        tarifs = [self.ANCIEN,
                  tarif_simple(0.30, debut="2026-06-12", fin=None,
                               nom="Plus tard", id_tarif="t_c")]
        with self.assertRaises(ValueError) as ctx:
            self.cout(tarifs=tarifs)
        self.assertIn("Aucun tarif", str(ctx.exception))

    def test_energie_repartie_au_prorata_de_la_duree(self):
        """Somme des deux morceaux = energie totale, rien ne se perd."""
        res = self.cout()
        self.assertAlmostEqual(res["kwh_hp"] + res["kwh_hc"], self.KWH,
                               places=3)


# ---------------------------------------------------------------------------
# fusion des plages horaires (le detail du correctif § 2.1)
# ---------------------------------------------------------------------------

class TestFusionDesPlages(unittest.TestCase):

    def test_plage_simple(self):
        self.assertEqual(r._fusionner_plages([["14:00", "16:00"]]),
                         [(840, 960)])

    def test_plage_a_cheval_sur_minuit_est_coupee_en_deux(self):
        self.assertEqual(r._fusionner_plages([["22:00", "06:00"]]),
                         [(0, 360), (1320, 1440)])

    def test_recouvrement_fusionne(self):
        """Le chevauchement donne exactement le meme resultat que la plage seule."""
        self.assertEqual(
            r._fusionner_plages([["22:00", "06:00"], ["23:00", "02:00"]]),
            r._fusionner_plages([["22:00", "06:00"]]))

    def test_plages_jointives_fusionnees_en_une_seule(self):
        self.assertEqual(r._fusionner_plages([["06:00", "08:00"],
                                              ["08:00", "10:00"]]),
                         [(360, 600)])

    def test_plage_vide_ecartee(self):
        self.assertEqual(r._fusionner_plages([["22:00", "22:00"]]), [])

    def test_detection_du_chevauchement(self):
        self.assertEqual(
            r._chevauchement_plages([["22:00", "06:00"], ["23:00", "02:00"]]),
            ("00:00", "02:00"))

    def test_pas_de_chevauchement_signale_a_tort(self):
        for plages in ([["22:00", "06:00"]],
                       [["22:00", "00:00"], ["00:00", "06:00"]],
                       [["23:45", "05:15"], ["14:15", "16:45"]]):
            with self.subTest(plages=plages):
                self.assertIsNone(r._chevauchement_plages(plages))


# ---------------------------------------------------------------------------
# valider_tarif
# ---------------------------------------------------------------------------

class TestValiderTarif(unittest.TestCase):

    def test_refuse_les_plages_qui_se_chevauchent(self):
        with self.assertRaises(ValueError) as ctx:
            r.valider_tarif(tarif_hp_hc(0.20, 0.10,
                                        [["22:00", "06:00"],
                                         ["23:00", "02:00"]]))
        self.assertIn("chevauchent", str(ctx.exception))

    def test_accepte_les_plages_jointives(self):
        propre = r.valider_tarif(tarif_hp_hc(0.20, 0.10,
                                             [["22:00", "00:00"],
                                              ["00:00", "06:00"]]))
        self.assertEqual(len(propre["plages_hc"]), 2)

    def test_accepte_les_plages_reelles(self):
        propre = r.valider_tarif(tarif_hp_hc(0.20, 0.10,
                                             [["23:45", "05:15"],
                                              ["14:15", "16:45"]]))
        self.assertEqual(propre["plages_hc"],
                         [["23:45", "05:15"], ["14:15", "16:45"]])

    def test_refuse_un_prix_nul(self):
        with self.assertRaises(ValueError):
            r.valider_tarif(tarif_simple(0.0))

    def test_refuse_une_fin_avant_le_debut(self):
        with self.assertRaises(ValueError):
            r.valider_tarif(tarif_simple(0.20, debut="2026-06-01",
                                         fin="2026-01-01"))


# ---------------------------------------------------------------------------
# calculer_abonnement
# ---------------------------------------------------------------------------

class TestCalculerAbonnement(unittest.TestCase):

    def test_mois_complet_de_31_jours(self):
        res = r.calculer_abonnement(date(2026, 3, 1), date(2026, 3, 31),
                                    [tarif_simple(0.20, abonnement=10.0)])
        self.assertAlmostEqual(res["total"], 10.00, places=2)
        self.assertEqual(res["jours"], 31)

    def test_mois_complet_de_28_jours(self):
        """Fevrier 2026 compte 28 jours : l'abonnement reste entier."""
        res = r.calculer_abonnement(date(2026, 2, 1), date(2026, 2, 28),
                                    [tarif_simple(0.20, abonnement=10.0)])
        self.assertAlmostEqual(res["total"], 10.00, places=2)
        self.assertEqual(res["jours"], 28)

    def test_demi_mois_proratise(self):
        res = r.calculer_abonnement(date(2026, 3, 1), date(2026, 3, 15),
                                    [tarif_simple(0.20, abonnement=10.0)])
        self.assertAlmostEqual(res["total"], 4.84, places=2)   # 15 x 10/31
        self.assertEqual(res["jours"], 15)

    def test_changement_de_tarif_au_milieu_du_mois(self):
        tarifs = [
            tarif_simple(0.20, debut="2026-01-01", fin="2026-03-15",
                         nom="Ancien", abonnement=10.0, id_tarif="t_a"),
            tarif_simple(0.30, debut="2026-03-16", fin=None,
                         nom="Nouveau", abonnement=20.0, id_tarif="t_b"),
        ]
        res = r.calculer_abonnement(date(2026, 3, 1), date(2026, 3, 31), tarifs)
        self.assertAlmostEqual(res["par_tarif"]["Ancien"], 4.84, places=2)
        self.assertAlmostEqual(res["par_tarif"]["Nouveau"], 10.32, places=2)
        self.assertAlmostEqual(res["total"], 15.16, places=2)

    def test_tarif_sans_date_de_fin_couvre_le_mois_entier(self):
        """Un tarif en cours court jusqu'a nouvel ordre, pas jusqu'a aujourd'hui."""
        res = r.calculer_abonnement(date(2026, 12, 1), date(2026, 12, 31),
                                    [tarif_simple(0.20, debut="2026-01-01",
                                                  fin=None, abonnement=10.0)])
        self.assertAlmostEqual(res["total"], 10.00, places=2)

    def test_periode_sur_plusieurs_mois_avec_changement_au_milieu(self):
        """Le parcours par tranches doit couper au mois ET au tarif.

        Fevrier entier a l'ancien (10 EUR), mars du 1er au 15 a l'ancien,
        du 16 au 31 au nouveau (20 EUR).
        """
        tarifs = [
            tarif_simple(0.20, debut="2026-01-01", fin="2026-03-15",
                         nom="Ancien", abonnement=10.0, id_tarif="t_a"),
            tarif_simple(0.30, debut="2026-03-16", fin=None,
                         nom="Nouveau", abonnement=20.0, id_tarif="t_b"),
        ]
        res = r.calculer_abonnement(date(2026, 2, 1), date(2026, 3, 31), tarifs)
        # fevrier : 10,00 -- mars : 15 x 10/31 puis 16 x 20/31
        self.assertAlmostEqual(res["par_tarif"]["Ancien"], 14.84, places=2)
        self.assertAlmostEqual(res["par_tarif"]["Nouveau"], 10.32, places=2)
        self.assertAlmostEqual(res["total"], 25.16, places=2)
        self.assertEqual(res["jours"], 59)

    def test_jours_non_couverts_ne_coutent_rien(self):
        """Un trou dans la grille : ces jours-la ne sont pas factures."""
        tarifs = [tarif_simple(0.20, debut="2026-03-16", fin=None,
                               abonnement=31.0)]
        res = r.calculer_abonnement(date(2026, 3, 1), date(2026, 3, 31), tarifs)
        self.assertAlmostEqual(res["total"], 16.00, places=2)   # 16 jours
        self.assertEqual(res["jours"], 31)

    def test_un_seul_jour(self):
        res = r.calculer_abonnement(date(2026, 3, 10), date(2026, 3, 10),
                                    [tarif_simple(0.20, abonnement=31.0)])
        self.assertAlmostEqual(res["total"], 1.00, places=2)
        self.assertEqual(res["jours"], 1)


# ---------------------------------------------------------------------------
# lecture de tarifs.json et import CSV : ces tests ecrivent des fichiers,
# tous dans le dossier temporaire
# ---------------------------------------------------------------------------

class TestFichiers(unittest.TestCase):

    # La wallbox termine ses lignes par un CR seul (pas un retour a la ligne
    # classique) : chr(13) le dit sans ambiguite.
    CR = chr(13)
    ENTETE = "NS du chargeur,Heure de debut,Heure de fin,Consommation,Duree,Cout"

    def setUp(self):
        """Repart d'un dossier de donnees propre avant chaque test."""
        # Le cache vit dans le module : sans cette ligne, un test verrait les
        # donnees laissees en memoire par le precedent.
        r.vider_cache()
        for chemin in DOSSIER_TEST.iterdir():
            if chemin.is_dir():
                shutil.rmtree(chemin, ignore_errors=True)
            else:
                chemin.unlink(missing_ok=True)
        self.ecrire_tarifs({
            "correction_csv_minutes": 0,
            "rendement_charge": 0.90,
            "theme": "dark",
            "capacite_batterie": 50.0,
            "tarifs": [tarif_hp_hc(0.20, 0.10, [["22:00", "06:00"]])],
        })

    def ecrire_tarifs(self, contenu):
        r.TARIFS_FILE.write_text(json.dumps(contenu, indent=2),
                                 encoding="utf-8")

    def ecrire_csv(self, lignes, nom="wallbox.csv"):
        """Ecrit un CSV au format de la wallbox et renvoie son chemin."""
        chemin = DOSSIER_TEST / nom
        chemin.write_text(self.CR.join([self.ENTETE] + lignes),
                          encoding="utf-8")
        return chemin

    # --- lecture de tarifs.json (§ 3.1) -----------------------------------

    def test_tarifs_json_casse_donne_un_message_lisible(self):
        """Avant : un JSONDecodeError brut s'affichait dans la boite Erreur."""
        r.TARIFS_FILE.write_text('{"tarifs": [,]}', encoding="utf-8")
        for fonction in (r.charger_tarifs, r.charger_config):
            with self.subTest(fonction=fonction.__name__):
                with self.assertRaises(ValueError) as ctx:
                    fonction()
                self.assertIn("tarifs.json est invalide", str(ctx.exception))

    def test_energie_invraisemblable_ne_montre_pas_de_jargon(self):
        """C'est cette fonction qui est appelee en premier a l'enregistrement."""
        r.TARIFS_FILE.write_text('{"tarifs": [,]}', encoding="utf-8")
        with self.assertRaises(ValueError):
            r.energie_invraisemblable(50)

    def test_tarifs_json_absent_est_recree_vide(self):
        """Une installation neuve ne doit pas etre dans une impasse.

        Avant : sans tarifs.json, le tableau de bord ET la page Tarifs — la
        seule ou l'on aurait pu saisir ses prix — affichaient la meme erreur.
        Il fallait creer le fichier a la main au Bloc-notes.
        """
        r.TARIFS_FILE.unlink()
        r.PREMIER_DEMARRAGE = False

        self.assertEqual(r.charger_tarifs(), [])
        self.assertTrue(r.TARIFS_FILE.exists())
        self.assertTrue(r.PREMIER_DEMARRAGE)

        # Les reglages crees ne decrivent aucune voiture ni aucun fournisseur.
        config = r.charger_config()
        self.assertEqual(config["capacite_batterie"], 0)
        self.assertEqual(config["correction_csv_minutes"], 0)

    def test_recharge_maison_sans_heure_de_fin_tarif_simple(self):
        """Avec un prix unique, la duree ne change rien : on ne l'exige plus."""
        self.ecrire_tarifs({"tarifs": [tarif_simple(0.20)]})
        r.vider_cache()
        recharge = r.ajouter_recharge_maison(
            datetime(2026, 3, 2, 23, 0), None, 30.0)
        self.assertAlmostEqual(recharge["cout_eur"], 6.00)
        # Aucune heure de fin inventee : le champ est simplement absent.
        self.assertNotIn("fin", recharge)

    def test_recharge_maison_sans_heure_de_fin_refusee_en_hp_hc(self):
        """En heures creuses, la duree commande tout : elle reste requise."""
        with self.assertRaises(ValueError) as ctx:
            r.ajouter_recharge_maison(
                datetime(2026, 3, 2, 23, 0), None, 30.0)
        self.assertIn("heure de fin est nécessaire", str(ctx.exception))

    def test_recalcul_reprend_les_recharges_sans_heure_de_fin(self):
        """Elles doivent suivre les changements de prix comme les autres."""
        self.ecrire_tarifs({"tarifs": [tarif_simple(0.20)]})
        r.vider_cache()
        r.ajouter_recharge_maison(datetime(2026, 3, 2, 23, 0), None, 30.0)

        self.ecrire_tarifs({"tarifs": [tarif_simple(0.30)]})
        self.assertEqual(r.recalculer_tout(), (1, []))
        self.assertAlmostEqual(
            r.charger_donnees()["recharges"][0]["cout_eur"], 9.00)

    def test_fin_videe_en_modification_est_effacee(self):
        """15/10/2026 : vider l'heure de fin dans « Modifier » doit la retirer.

        Avant, la fin videe etait ignoree sans un mot : impossible de revenir
        a une recharge sans heure de fin, pourtant permise a la saisie. Comme
        a la saisie, le champ disparait (pas de « fin »: null) et le cout est
        recalcule sans duree."""
        self.ecrire_tarifs({"tarifs": [tarif_simple(0.20)]})
        r.vider_cache()
        rec = r.ajouter_recharge_maison(
            datetime(2026, 3, 2, 23, 0), datetime(2026, 3, 3, 5, 0), 30.0)
        modifiee = r.modifier_recharge(rec["id"], {"fin": None, "kwh": 20.0})
        self.assertNotIn("fin", modifiee)
        self.assertAlmostEqual(modifiee["cout_eur"], 4.00)
        r.vider_cache()   # et c'est bien ce qui est ecrit sur le disque
        self.assertNotIn("fin", r.charger_donnees()["recharges"][0])

    def test_fin_videe_refusee_en_hp_hc_sans_rien_changer(self):
        """En heures creuses, la duree reste requise : le refus de la saisie
        vaut aussi en modification, et la recharge garde sa fin."""
        r.vider_cache()
        rec = r.ajouter_recharge_maison(
            datetime(2026, 3, 2, 23, 0), datetime(2026, 3, 3, 5, 0), 30.0)
        with self.assertRaises(ValueError) as ctx:
            r.modifier_recharge(rec["id"], {"fin": None})
        self.assertIn("heure de fin est nécessaire", str(ctx.exception))
        r.vider_cache()
        self.assertEqual(r.charger_donnees()["recharges"][0]["fin"],
                         "2026-03-03T05:00")

    def test_grille_vide_refuse_la_recharge_en_le_disant(self):
        """Le refus doit envoyer vers la page Tarifs, pas accuser la date."""
        self.ecrire_tarifs({"tarifs": []})
        with self.assertRaises(ValueError) as ctx:
            r.ajouter_recharge_maison(
                datetime(2026, 3, 2, 23, 0), datetime(2026, 3, 3, 5, 0), 30.0)
        self.assertIn("grille tarifaire est encore vide", str(ctx.exception))
        self.assertIn("Tarifs", str(ctx.exception))

    def test_cle_tarifs_manquante(self):
        r.TARIFS_FILE.write_text('{"theme": "dark"}', encoding="utf-8")
        with self.assertRaises(ValueError) as ctx:
            r.charger_tarifs()
        self.assertIn("tarifs", str(ctx.exception))

    # --- A4 : chaque tarif de tarifs.json est verifie au chargement --------

    def test_tarif_nan_dans_le_fichier_refuse(self):
        """Un prix « NaN » (fichier modifie a la main) donnait des couts
        invalides sans un mot : il doit etre refuse en nommant le tarif."""
        r.TARIFS_FILE.write_text(
            '{"tarifs": [{"id": "t1", "nom": "Base essai", "type": "simple",'
            ' "debut": "2026-01-01", "fin": null, "prix_kwh": NaN,'
            ' "abonnement_mensuel": 0}]}', encoding="utf-8")
        with self.assertRaises(ValueError) as ctx:
            r.charger_tarifs()
        self.assertIn("Base essai", str(ctx.exception))
        self.assertIn("tarifs.json", str(ctx.exception))

    def test_prix_illisible_dans_le_fichier_refuse_en_clair(self):
        """Un prix ecrit en texte ne doit pas remonter un message Python."""
        r.TARIFS_FILE.write_text(
            '{"tarifs": [{"id": "t1", "nom": "Base essai", "type": "simple",'
            ' "debut": "2026-01-01", "fin": null, "prix_kwh": "vingt",'
            ' "abonnement_mensuel": 0}]}', encoding="utf-8")
        with self.assertRaises(ValueError) as ctx:
            r.charger_tarifs()
        self.assertIn("Base essai", str(ctx.exception))
        self.assertNotIn("could not convert", str(ctx.exception))

    def test_tarif_qui_n_est_pas_un_objet_refuse(self):
        r.TARIFS_FILE.write_text('{"tarifs": [12]}', encoding="utf-8")
        with self.assertRaises(ValueError) as ctx:
            r.charger_tarifs()
        self.assertIn("tarifs.json", str(ctx.exception))

    def test_valider_tarif_refuse_nan_et_infini(self):
        for valeur in (float("nan"), float("inf")):
            with self.subTest(valeur=valeur):
                with self.assertRaises(ValueError):
                    r.valider_tarif({"nom": "Essai", "type": "simple",
                                     "debut": "2026-01-01",
                                     "prix_kwh": valeur})

    # --- cache memoire (§ 5.1) -------------------------------------------

    RECHARGE = {"id": "abc", "date": "2026-03-02T23:00",
                "fin": "2026-03-03T05:00", "lieu": "maison",
                "kwh": 30.0, "cout_eur": 3.90}

    def test_le_fichier_n_est_relu_qu_une_fois(self):
        r.sauvegarder_donnees({"recharges": [], "marqueur": "avant"})
        lectures = []
        origine = r._lire_donnees_du_disque
        r._lire_donnees_du_disque = lambda: lectures.append(1) or origine()
        try:
            for _ in range(5):
                self.assertEqual(r.charger_donnees()["marqueur"], "avant")
            self.assertEqual(lectures, [])   # inchange : tout vient de la memoire
        finally:
            r._lire_donnees_du_disque = origine

    def test_un_fichier_remplace_a_cote_est_relu(self):
        """Le serveur mobile ecrit pendant que l'application est ouverte."""
        r.sauvegarder_donnees({"recharges": [], "marqueur": "avant"})
        r.DATA_FILE.write_text('{"recharges": [], "marqueur": "apres, plus long"}',
                               encoding="utf-8")
        self.assertEqual(r.charger_donnees()["marqueur"], "apres, plus long")

    def test_une_recharge_ecrite_a_cote_n_est_pas_effacee(self):
        """Le vrai danger : l'application ouverte modifie une recharge apres
        qu'un autre programme (le serveur mobile) en a ajoute une. Avant, sa
        sauvegarde repartait de la memoire et effacait la recharge ajoutee."""
        r.sauvegarder_donnees({"recharges": [dict(self.RECHARGE)]})
        r.charger_donnees()   # l'application a tout en memoire
        venue_d_ailleurs = dict(self.RECHARGE, id="tel", kwh=12.0)
        r.DATA_FILE.write_text(
            json.dumps({"recharges": [dict(self.RECHARGE), venue_d_ailleurs]}),
            encoding="utf-8")
        r.modifier_recharge("abc", {"kwh": 25.0})
        r.vider_cache()
        ids = [x["id"] for x in r.charger_donnees()["recharges"]]
        self.assertEqual(sorted(ids), ["abc", "tel"])

    def test_une_modification_refusee_ne_reste_pas_en_memoire(self):
        """Le piege du cache : modifier_recharge applique avant de valider.

        Sans copie defensive, une energie negative refusee resterait dans le
        dictionnaire partage, et la premiere sauvegarde venue l'ecrirait.
        """
        r.sauvegarder_donnees({"recharges": [dict(self.RECHARGE)]})
        with self.assertRaises(ValueError):
            r.modifier_recharge("abc", {"kwh": -5})
        self.assertEqual(r.charger_donnees()["recharges"][0]["kwh"], 30.0)
        r.vider_cache()   # et le disque non plus n'a pas bouge
        self.assertEqual(r.charger_donnees()["recharges"][0]["kwh"], 30.0)

    def test_une_modification_acceptee_est_bien_visible(self):
        r.sauvegarder_donnees({"recharges": [dict(self.RECHARGE)]})
        r.modifier_recharge("abc", {"kwh": 25.0})
        self.assertEqual(r.charger_donnees()["recharges"][0]["kwh"], 25.0)
        r.vider_cache()
        self.assertEqual(r.charger_donnees()["recharges"][0]["kwh"], 25.0)

    def test_lire_puis_modifier_ne_partage_pas_le_dictionnaire(self):
        r.sauvegarder_donnees({"recharges": [dict(self.RECHARGE)]})
        lecture = r.charger_donnees()
        modification = r.charger_donnees(pour_modification=True)
        modification["recharges"][0]["kwh"] = 999
        self.assertEqual(lecture["recharges"][0]["kwh"], 30.0)

    def test_une_suppression_est_bien_repercutee(self):
        r.sauvegarder_donnees({"recharges": [dict(self.RECHARGE)]})
        self.assertTrue(r.supprimer_recharge("abc"))
        self.assertEqual(r.charger_donnees()["recharges"], [])

    # --- suppression qui echoue (§ 2.4) -----------------------------------

    def test_supprimer_une_recharge_inconnue_renvoie_faux(self):
        """Contrat sur lequel s'appuie l'interface pour prevenir l'utilisateur."""
        r.sauvegarder_donnees({"recharges": [dict(self.RECHARGE)]})
        self.assertFalse(r.supprimer_recharge(""))
        self.assertFalse(r.supprimer_recharge("identifiant_qui_n_existe_pas"))
        self.assertTrue(r.supprimer_recharge("abc"))

    def test_supprimer_un_releve_inconnu_renvoie_faux(self):
        r.sauvegarder_donnees({"recharges": [], "releves_km": [
            {"id": "k1", "date": "2026-03-02T12:00", "km": 10000}]})
        self.assertFalse(r.supprimer_releve_km(""))
        self.assertFalse(r.supprimer_releve_km("inconnu"))
        self.assertTrue(r.supprimer_releve_km("k1"))

    # --- horodatage deja utilise (§ 6.3) ----------------------------------

    def test_horodatage_deja_utilise(self):
        r.sauvegarder_donnees({"recharges": [
            {"id": "e1", "date": "2026-07-15T12:00", "lieu": "exterieur",
             "operateur": "Ionity", "kwh": 37.63, "cout_eur": 22.0},
        ]})
        autre = r.horodatage_deja_utilise("2026-07-15T12:00")
        self.assertIsNotNone(autre)
        self.assertEqual(autre["operateur"], "Ionity")

    def test_horodatage_libre(self):
        r.sauvegarder_donnees({"recharges": [
            {"id": "e1", "date": "2026-07-15T12:00", "lieu": "exterieur"},
        ]})
        # une minute d'ecart suffit : c'est justement ce qu'on veut obtenir
        self.assertIsNone(r.horodatage_deja_utilise("2026-07-15T12:01"))
        self.assertIsNone(r.horodatage_deja_utilise(""))
        self.assertIsNone(r.horodatage_deja_utilise(None))

    def test_horodatage_ignore_la_recharge_qu_on_modifie(self):
        """Sinon, modifier une recharge se plaindrait d'elle-meme."""
        r.sauvegarder_donnees({"recharges": [
            {"id": "e1", "date": "2026-07-15T12:00", "lieu": "exterieur"},
        ]})
        self.assertIsNone(r.horodatage_deja_utilise("2026-07-15T12:00",
                                                    sauf_id="e1"))

    # --- lister et restaurer les sauvegardes (§ 6.6) ----------------------

    def sauvegarder_n_recharges(self, n):
        """Ecrit n recharges et renvoie le dictionnaire ecrit."""
        data = {"recharges": [dict(self.RECHARGE, id=f"r{i}") for i in range(n)]}
        r.sauvegarder_donnees(data)
        return data

    def test_lister_les_sauvegardes(self):
        self.sauvegarder_n_recharges(3)     # cree le fichier
        self.sauvegarder_n_recharges(5)     # sauvegarde les 3 precedentes
        fiches = r.lister_backups()
        self.assertTrue(fiches)
        self.assertEqual(fiches[0]["n_recharges"], 3)
        self.assertIn("taille", fiches[0])

    def test_restaurer_une_sauvegarde(self):
        self.sauvegarder_n_recharges(3)
        self.sauvegarder_n_recharges(5)
        fiche = r.lister_backups()[0]
        self.assertEqual(r.restaurer_backup(fiche["chemin"]), 3)
        self.assertEqual(len(r.charger_donnees()["recharges"]), 3)
        r.vider_cache()
        self.assertEqual(len(r.charger_donnees()["recharges"]), 3)

    def test_restaurer_est_annulable(self):
        """L'etat d'avant la restauration doit rester recuperable."""
        self.sauvegarder_n_recharges(3)
        self.sauvegarder_n_recharges(5)
        r.restaurer_backup(r.lister_backups()[0]["chemin"])   # revient a 3
        # la sauvegarde la plus recente contient maintenant les 5 d'avant
        retour = next(f for f in r.lister_backups() if f["n_recharges"] == 5)
        self.assertEqual(r.restaurer_backup(retour["chemin"]), 5)

    def test_restaurer_un_fichier_illisible_est_refuse(self):
        self.sauvegarder_n_recharges(3)
        casse = DOSSIER_TEST / "backups" / "recharges_20200101_000000.json"
        casse.parent.mkdir(parents=True, exist_ok=True)
        casse.write_text("ceci n'est pas du JSON", encoding="utf-8")
        with self.assertRaises(ValueError):
            r.restaurer_backup(casse)
        # la sauvegarde reste listee, signalee comme illisible
        illisible = [f for f in r.lister_backups() if f["nom"] == casse.name]
        self.assertEqual(len(illisible), 1)
        self.assertIsNone(illisible[0]["n_recharges"])

    def test_restaurer_un_fichier_qui_n_est_pas_des_recharges(self):
        autre = DOSSIER_TEST / "backups" / "recharges_20200102_000000.json"
        autre.parent.mkdir(parents=True, exist_ok=True)
        autre.write_text('{"autre_chose": []}', encoding="utf-8")
        with self.assertRaises(ValueError) as ctx:
            r.restaurer_backup(autre)
        self.assertIn("ne ressemble pas", str(ctx.exception))

    def test_aucune_sauvegarde_au_depart(self):
        self.assertEqual(r.lister_backups(), [])

    # --- sauvegardes de tarifs.json (§ 3.2) ------------------------------

    def test_modifier_un_reglage_cree_une_sauvegarde(self):
        """Avant : tarifs.json n'avait qu'une copie .avant, ecrasee chaque fois."""
        r.enregistrer_config({"correction_csv_minutes": 15})
        backups = sorted((DOSSIER_TEST / "backups").glob("tarifs_*.json"))
        self.assertTrue(backups, "aucune sauvegarde de tarifs.json creee")
        # la sauvegarde contient l'etat d'AVANT la modification
        for backup in backups:
            with self.subTest(backup=backup.name):
                avant = json.loads(backup.read_text(encoding="utf-8"))
                self.assertEqual(avant["correction_csv_minutes"], 0)
        self.assertEqual(r.charger_config()["correction_csv_minutes"], 15)

    def test_un_ancien_reglage_theme_est_sans_effet(self):
        """Les tarifs.json d'avant la v1.24.0 portent encore "theme": "dark".
        Ils doivent se lire sans erreur, et le reglage n'est plus renvoye."""
        config = r.charger_config()
        self.assertNotIn("theme", config)
        self.assertEqual(config["rendement_charge"], 0.90)

    def test_la_copie_avant_est_conservee(self):
        """Les deux filets coexistent : .avant a cote, et backups/."""
        r.enregistrer_config({"correction_csv_minutes": 15})
        self.assertTrue((DOSSIER_TEST / "tarifs.json.avant").exists())

    def test_la_grille_survit_a_un_changement_de_reglage(self):
        avant = r.charger_tarifs()
        r.enregistrer_config({"correction_csv_minutes": 15})
        self.assertEqual(r.charger_tarifs(), avant)

    def test_les_deux_sauvegardes_ne_se_melangent_pas(self):
        """Sauvegarder les recharges ne doit pas toucher aux tarifs, ni l'inverse."""
        # Deux ecritures : la premiere cree recharges.json (rien a sauvegarder
        # encore), la seconde declenche la copie de securite.
        r.sauvegarder_donnees({"recharges": []})
        r.sauvegarder_donnees({"recharges": []})
        r.enregistrer_config({"correction_csv_minutes": 15})
        dossier = DOSSIER_TEST / "backups"
        self.assertTrue(list(dossier.glob("recharges_*.json")))
        self.assertTrue(list(dossier.glob("tarifs_*.json")))
        # Le plus recent de chaque famille est bien du bon type de fichier
        self.assertIn("recharges", json.loads(
            r._backup_le_plus_recent("recharges").read_text(encoding="utf-8")))
        self.assertIn("tarifs", json.loads(
            r._backup_le_plus_recent("tarifs").read_text(encoding="utf-8")))

    # --- import CSV (§ 2.3) ----------------------------------------------

    def test_import_csv_normal(self):
        chemin = self.ecrire_csv([
            "TACW000000S0000,2026-03-02 23:00:00,2026-03-03 05:00:00,"
            "30.000kWh,06h00min,3.90€",
            "TACW000000S0000,2026-03-05 23:00:00,2026-03-06 05:00:00,"
            "20.000kWh,06h00min,2.60€",
        ])
        res = r.importer_csv_maison(chemin)
        self.assertEqual(res["total_lus"], 2)
        self.assertEqual(res["ajoutes"], 2)
        self.assertEqual(res["non_reconnues"], 0)

    def test_import_csv_deux_fois_ne_duplique_rien(self):
        chemin = self.ecrire_csv([
            "TACW000000S0000,2026-03-02 23:00:00,2026-03-03 05:00:00,"
            "30.000kWh,06h00min,3.90€",
        ])
        r.importer_csv_maison(chemin)
        res = r.importer_csv_maison(chemin)
        self.assertEqual(res["ajoutes"], 0)
        self.assertEqual(res["doublons"], 1)
        self.assertEqual(len(r.charger_donnees()["recharges"]), 1)

    def test_import_csv_format_inconnu_leve_une_erreur(self):
        """Bug § 2.3 : l'import annoncait « 0 ajoutees, rien de nouveau ».

        L'utilisateur en concluait que le fichier etait deja importe, le
        supprimait, et perdait les recharges. Le fichier pris en exemple ici
        est reellement indechiffrable : ses colonnes ne sont pas celles d'un
        export de wallbox.
        """
        chemin = self.ecrire_csv([
            "seance 12,voiture,pleine charge,rien a lire ici",
            "seance 13,voiture,pleine charge,rien a lire ici",
        ])
        with self.assertRaises(ValueError) as ctx:
            r.importer_csv_maison(chemin)
        message = str(ctx.exception)
        self.assertIn("Aucune recharge reconnue", message)
        self.assertIn("SUPPRIMEZ PAS", message)

    def test_import_csv_point_virgule_et_virgule_decimale(self):
        """Une autre borne, ou une autre langue, doit passer.

        Le lecteur reconnaissait auparavant UNE seule borne : le motif
        exigeait un numero de serie commencant par « TACW », la virgule
        comme separateur et le point decimal. Tout le reste etait refuse.
        """
        chemin = self.ecrire_csv([
            "WB-0042;2026-03-02 23:00:00;2026-03-03 05:00:00;"
            "30,000 kWh;06h00min;3,90 €",
        ])
        res = r.importer_csv_maison(chemin)
        self.assertEqual(res["ajoutes"], 1)
        self.assertEqual(res["non_reconnues"], 0)
        enregistree = r.charger_donnees()["recharges"][0]
        self.assertAlmostEqual(enregistree["kwh"], 30.0)
        self.assertEqual(enregistree["chargeur"], "WB-0042")

    def test_import_csv_dates_a_la_francaise(self):
        """Certains exports datent en jj/mm/aaaa, sans les secondes."""
        chemin = self.ecrire_csv([
            "BORNE1,02/03/2026 23:00,03/03/2026 05:00,30.000kWh,06h00min,3.90",
        ])
        res = r.importer_csv_maison(chemin)
        self.assertEqual(res["ajoutes"], 1)
        self.assertEqual(r.charger_donnees()["recharges"][0]["date"],
                         "2026-03-02T23:00")

    def test_import_csv_vide_leve_une_erreur(self):
        chemin = self.ecrire_csv([])
        with self.assertRaises(ValueError) as ctx:
            r.importer_csv_maison(chemin)
        self.assertIn("aucune recharge", str(ctx.exception))

    def test_import_csv_partiellement_reconnu_le_signale(self):
        """Une seule ligne illisible : elle doit etre comptee, pas oubliee."""
        chemin = self.ecrire_csv([
            "TACW000000S0000,2026-03-02 23:00:00,2026-03-03 05:00:00,"
            "30.000kWh,06h00min,3.90€",
            "erreur de lecture du compteur",
        ])
        res = r.importer_csv_maison(chemin)
        self.assertEqual(res["total_lus"], 1)
        self.assertEqual(res["non_reconnues"], 1)

    def test_import_csv_ecarte_les_branchements_parasites(self):
        chemin = self.ecrire_csv([
            "TACW000000S0000,2026-03-02 23:00:00,2026-03-02 23:00:12,"
            "0.012kWh,00h00min12s,0.00€",
            "TACW000000S0000,2026-03-05 23:00:00,2026-03-06 05:00:00,"
            "20.000kWh,06h00min,2.60€",
        ])
        res = r.importer_csv_maison(chemin)
        self.assertEqual(res["ajoutes"], 1)
        self.assertEqual(res["parasites"], 1)

    # --- les donnees ecrites sont bien celles du dossier temporaire -------

    def test_les_donnees_vont_dans_le_dossier_temporaire(self):
        """Garde-fou : si ce test echoue, les tests ecrivent chez vous."""
        self.assertEqual(r.BASE, DOSSIER_TEST)
        self.assertTrue(str(r.DATA_FILE).startswith(str(DOSSIER_TEST)))


class TestJeuDemo(unittest.TestCase):
    """Le jeu de demonstration sur lequel tourne la verification automatique."""

    def setUp(self):
        self.dossier = Path(tempfile.mkdtemp(prefix="demo_test_"))
        r.ecrire_jeu_demo(self.dossier)
        self.contenu = json.loads(
            (self.dossier / "recharges.json").read_text(encoding="utf-8"))

    def tearDown(self):
        shutil.rmtree(self.dossier, ignore_errors=True)

    def test_couvre_ce_qu_il_faut_pour_exercer_les_pages(self):
        recharges = self.contenu["recharges"]
        self.assertEqual(len(recharges), 10)
        lieux = {x["lieu"] for x in recharges}
        self.assertEqual(lieux, {"maison", "exterieur"})
        noms = {x["tarif_nom"] for x in recharges if x["lieu"] == "maison"}
        self.assertEqual(noms, {"Demo Bleu", "Demo HP/HC"})   # les deux types
        passent_minuit = [x for x in recharges
                          if x.get("fin") and x["fin"][:10] != x["date"][:10]]
        self.assertGreaterEqual(len(passent_minuit), 2)
        self.assertTrue(self.contenu["releves_km"])

    def test_les_montants_sont_coherents_avec_le_moteur(self):
        """Les couts sont calcules, jamais ecrits en dur : ils doivent donc
        resister a un recalcul."""
        for x in self.contenu["recharges"]:
            if x["lieu"] != "maison":
                continue
            with self.subTest(date=x["date"]):
                calc = r.calculer_cout(r._parse_dt(x["date"]),
                                       r._parse_dt(x["fin"]),
                                       float(x["kwh"]), r.TARIFS_DEMO)
                self.assertAlmostEqual(round(calc["cout"], 2), x["cout_eur"],
                                       places=2)
                self.assertAlmostEqual(calc["kwh_hc"], x["kwh_hc"], places=3)

    def test_le_fichier_de_tarifs_est_lisible(self):
        base_origine = r.BASE
        r.rediriger_donnees(self.dossier)
        try:
            self.assertEqual(len(r.charger_tarifs()), 2)
            self.assertEqual(r.charger_config()["capacite_batterie"], 52.0)
            self.assertEqual(r.dossier_donnees(), self.dossier)
        finally:
            r.rediriger_donnees(base_origine)

    def test_rediriger_puis_revenir(self):
        """Garde-fou : la redirection doit etre parfaitement reversible."""
        avant = r.dossier_donnees()
        r.rediriger_donnees(self.dossier)
        self.assertEqual(r.dossier_donnees(), self.dossier)
        r.rediriger_donnees(avant)
        self.assertEqual(r.dossier_donnees(), avant)
        self.assertEqual(r.DATA_FILE, avant / "recharges.json")


class TestSauvegardeGitHub(unittest.TestCase):
    """Sauvegarde cloud : le cas du depot sans branche distante (§ 2.5)."""

    def setUp(self):
        if not shutil.which("git"):
            self.skipTest("git n'est pas installe")
        # Un depot jetable, avec la meme forme que le vrai : depot/dist/
        self.racine = Path(tempfile.mkdtemp(prefix="depot_test_"))
        self.dist = self.racine / "dist"
        self.dist.mkdir()
        (self.dist / "recharges.json").write_text('{"recharges": []}',
                                                  encoding="utf-8")
        (self.dist / "tarifs.json").write_text('{"tarifs": []}',
                                               encoding="utf-8")
        self.git("init")
        self.git("config", "user.name", "Test")
        self.git("config", "user.email", "test@example.invalid")
        self.git("add", "-A")
        self.git("commit", "-m", "depart")
        # recharges.py deduit le depot de BASE.parent : on detourne le
        # dossier de donnees le temps du test, puis on le remet. Passer par
        # rediriger_donnees() et non par BASE seul : les chemins des fichiers
        # en decoulent, et git a besoin qu'ils soient dans le depot.
        self.base_origine = r.BASE
        r.rediriger_donnees(self.dist)

    def tearDown(self):
        r.rediriger_donnees(self.base_origine)
        effacer_vraiment(self.racine)

    def git(self, *args):
        return subprocess.run(["git", *args], cwd=str(self.racine),
                              capture_output=True, text=True)

    def test_sans_branche_distante_on_ne_dit_pas_que_c_est_sauvegarde(self):
        """Avant : « Donnees deja sauvegardees sur GitHub » — c'etait faux.

        La commande qui compte les commits en attente echoue quand aucune
        branche distante n'est configuree. Cet echec etait pris pour « rien
        en attente », et l'utilisateur croyait ses donnees a l'abri.
        """
        ok, message = r.synchroniser_github()
        self.assertFalse(ok)
        self.assertIn("Aucune branche distante", message)

    def test_sans_depot_git_du_tout(self):
        """Un dossier ordinaire, sans depot : on le dit clairement."""
        ailleurs = Path(tempfile.mkdtemp(prefix="sans_git_"))
        (ailleurs / "dist").mkdir()
        r.rediriger_donnees(ailleurs / "dist")
        try:
            self.assertFalse(r.sauvegarde_cloud_configuree())
            ok, message = r.synchroniser_github()
        finally:
            effacer_vraiment(ailleurs)
        self.assertFalse(ok)
        self.assertIn("Pas de dépôt git", message)

    def test_avec_depot_git_la_sauvegarde_est_declaree_configuree(self):
        """C'est ce booleen qui decide d'afficher, ou non, le bouton."""
        self.assertTrue(r.sauvegarde_cloud_configuree())
        self.assertEqual(r.depot_git_des_donnees(), self.racine)

    def test_clone_du_depot_public_pas_de_sauvegarde_cloud(self):
        """Un clone du depot public : dist\\ est dans un depot de CODE, qui
        ignore les donnees. Avant : le bouton « Sauvegarder » apparaissait, et
        Ctrl+S poussait vers le depot clone (le depot public, ou la copie de
        l'utilisateur). Les donnees ne doivent jamais partir vers un depot
        qui ne les suit pas."""
        self.git("rm", "--cached", "-q", "dist/recharges.json",
                 "dist/tarifs.json")
        (self.racine / ".gitignore").write_text("*.json\n", encoding="utf-8")
        self.git("add", ".gitignore")
        self.git("commit", "-m", "donnees ignorees")
        self.assertIsNone(r.depot_git_des_donnees())
        self.assertFalse(r.sauvegarde_cloud_configuree())
        ok, _message = r.synchroniser_github()
        self.assertFalse(ok)
        journal = self.git("log", "--oneline").stdout
        self.assertNotIn("Sauvegarde auto", journal)

    def test_depot_git_dans_le_dossier_des_donnees_lui_meme(self):
        """Un dossier d'usage separe du projet est son propre depot : les
        donnees a sa racine, le programme dans un sous-dossier. La sauvegarde
        doit y trouver le depot, et y faire son commit."""
        donnees = Path(tempfile.mkdtemp(prefix="usage_test_"))

        def git(*args):
            return subprocess.run(["git", *args], cwd=str(donnees),
                                  capture_output=True, text=True)

        try:
            (donnees / "recharges.json").write_text('{"recharges": []}',
                                                    encoding="utf-8")
            (donnees / "tarifs.json").write_text('{"tarifs": []}',
                                                 encoding="utf-8")
            git("init")
            git("config", "user.name", "Test")
            git("config", "user.email", "test@example.invalid")
            git("add", "-A")
            git("commit", "-m", "depart")
            r.rediriger_donnees(donnees)
            self.assertEqual(r.depot_git_des_donnees(), donnees)
            (donnees / "tarifs.json").write_text('{"tarifs": [], "x": 1}',
                                                 encoding="utf-8")
            ok, message = r.synchroniser_github()
            journal = git("log", "--oneline").stdout
        finally:
            # tearDown remet ensuite le dossier d'origine.
            r.rediriger_donnees(self.dist)
            effacer_vraiment(donnees)
        # Ce depot jetable n'a pas de branche distante : le commit est fait,
        # et l'envoi dit clairement qu'il n'a nulle part ou aller.
        self.assertIn("Sauvegarde auto", journal)
        self.assertFalse(ok)
        self.assertIn("Aucune branche distante", message)


if __name__ == "__main__":
    unittest.main(verbosity=2)
