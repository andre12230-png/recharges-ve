"""La remise en etat du fichier au demarrage n'efface plus une saisie du
telephone (audit independant du 04/11/2026, constat T6).

Au demarrage, si recharges.json est abime, l'application le remplace par la
derniere sauvegarde puis le reecrit. Cette reecriture se faisait sans le
verrou d'ecriture commun : si le telephone enregistrait une recharge entre
la lecture et l'ecriture de la reparation, la reparation l'effacait, sans
un mot.

Ici, un second programme joue le telephone : il enregistre une recharge par
la fonction normale (verrouillee) au moment precis ou la reparation va
remplacer le fichier.

    py -m pytest tests/test_reparation_sous_verrou.py
"""

import os
import shutil
import subprocess
import sys
import tempfile
import textwrap
import time
import unittest
from pathlib import Path

# --- redirection des donnees : AVANT l'import de recharges (test_isolation) --
# Meme principe que test_verrou_ecriture.py : un dossier a soi, redirige au
# debut de chaque test et rendu a la fin.
DOSSIER_TEST = Path(tempfile.mkdtemp(prefix="recharges_reparation_"))
os.environ.setdefault("RECHARGES_DATA_DIR", str(DOSSIER_TEST))
PROJET = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJET))

import recharges as r  # noqa: E402

# Le « telephone » : il se signale pret, puis enregistre une recharge par la
# fonction ordinaire, qui prend le verrou commun.
TELEPHONE = textwrap.dedent("""
    import sys
    sys.path.insert(0, sys.argv[1])
    import recharges as r
    open(sys.argv[2], "w").close()          # « je vais ecrire »
    r.ajouter_recharge_exterieur(30.0, 15.0, operateur="Telephone",
                                 date="2026-03-02T10:00")
""")


def _remise_en_etat():
    """La fonction du moteur si elle existe ; sinon ce que faisait la
    fenetre jusqu'a la v2.2.32 (le test echoue alors : c'est le defaut)."""
    remettre = getattr(r, "remettre_en_etat", None)
    if remettre is not None:
        return remettre()
    r.sauvegarder_donnees(r.charger_donnees())
    return True


class TestReparationSousVerrou(unittest.TestCase):

    def setUp(self):
        self.origine = r.dossier_donnees()
        r.rediriger_donnees(DOSSIER_TEST)
        self.addCleanup(r.rediriger_donnees, self.origine)
        ancienne = r.DERNIERE_RESTAURATION
        self.addCleanup(setattr, r, "DERNIERE_RESTAURATION", ancienne)
        r.vider_cache()
        for chemin in DOSSIER_TEST.iterdir():
            if chemin.is_dir():
                shutil.rmtree(chemin, ignore_errors=True)
            else:
                chemin.unlink()
        r.enregistrer_tarif({"nom": "T", "debut": "2026-01-01", "fin": None,
                             "type": "simple", "abonnement_mensuel": 10.0,
                             "prix_kwh": 0.2})
        r.ajouter_recharge_exterieur(20.0, 10.0, operateur="Depart",
                                     date="2026-03-01T10:00")
        # Une seconde ecriture : la premiere version entre dans backups/.
        r.sauvegarder_donnees(r.charger_donnees(pour_modification=True))
        self.script = DOSSIER_TEST / "telephone.py"
        self.script.write_text(TELEPHONE, encoding="utf-8")
        self.pret = DOSSIER_TEST / "pret.txt"

    def abimer_et_demarrer(self):
        """Fichier abime, puis lecture du demarrage : la sauvegarde le
        remplace en memoire, le fichier abime est mis de cote."""
        r.DATA_FILE.write_text("{ pas du JSON", encoding="utf-8")
        r.vider_cache()
        r.DERNIERE_RESTAURATION = None
        r.charger_donnees()
        self.assertIsNotNone(r.DERNIERE_RESTAURATION)

    def operateurs(self) -> set:
        r.vider_cache()
        return {x.get("operateur") for x in r.charger_donnees()["recharges"]}

    def test_une_saisie_du_telephone_pendant_la_reparation_est_gardee(self):
        self.abimer_et_demarrer()
        remplacer = r._remplacer
        telephones = []

        def remplacer_avec_telephone(tmp, cible):
            # Juste avant que la reparation remplace recharges.json : le
            # telephone enregistre. Sans verrou, il ecrit tout de suite et
            # la reparation l'ecrase ; avec, il attend la fin.
            if cible == r.DATA_FILE and not telephones:
                env = dict(os.environ, RECHARGES_DATA_DIR=str(DOSSIER_TEST))
                proc = subprocess.Popen(
                    [sys.executable, str(self.script), str(PROJET),
                     str(self.pret)], env=env)
                telephones.append(proc)
                limite = time.monotonic() + 30
                while not self.pret.exists():
                    self.assertIsNone(proc.poll(), "le « telephone » s'est arrete")
                    self.assertLess(time.monotonic(), limite,
                                    "le « telephone » tarde")
                    time.sleep(0.05)
                # Lui laisser le temps d'ecrire s'il le peut (il en a
                # besoin de quelques centiemes de seconde).
                fin = time.monotonic() + 2
                while proc.poll() is None and time.monotonic() < fin:
                    time.sleep(0.05)
            remplacer(tmp, cible)

        r._remplacer = remplacer_avec_telephone
        try:
            _remise_en_etat()
        finally:
            r._remplacer = remplacer
        self.assertEqual(len(telephones), 1)
        self.assertEqual(telephones[0].wait(timeout=30), 0)
        self.assertEqual(self.operateurs(), {"Depart", "Telephone"})

    def test_rien_n_est_reecrit_si_le_fichier_est_deja_sain(self):
        """Le telephone a deja remis le fichier d'aplomb en enregistrant :
        la remise en etat n'a plus rien a faire, et ne touche a rien."""
        self.abimer_et_demarrer()
        r.ajouter_recharge_exterieur(25.0, 12.0, operateur="Telephone",
                                     date="2026-03-02T10:00")
        avant = r.DATA_FILE.read_bytes()
        self.assertFalse(r.remettre_en_etat())
        self.assertEqual(r.DATA_FILE.read_bytes(), avant)
        self.assertEqual(self.operateurs(), {"Depart", "Telephone"})

    def test_le_fichier_abime_est_bien_remis_en_etat(self):
        self.abimer_et_demarrer()
        # Une copie est mise de cote, le fichier lui-meme reste abime.
        self.assertFalse(r._fichier_lisible(r.DATA_FILE))
        self.assertTrue(r.remettre_en_etat())
        self.assertTrue(r._fichier_lisible(r.DATA_FILE))
        self.assertEqual(self.operateurs(), {"Depart"})

    def test_la_fenetre_passe_par_la_remise_en_etat_du_moteur(self):
        """La fenetre ne reecrit plus le fichier elle-meme, hors verrou."""
        source = (PROJET / "fenetre.py").read_text(encoding="utf-8")
        self.assertNotIn("sauvegarder_donnees(charger_donnees())", source)
        self.assertIn("remettre_en_etat()", source)


if __name__ == "__main__":
    unittest.main()
