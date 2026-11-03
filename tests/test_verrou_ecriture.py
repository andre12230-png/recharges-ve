"""Un seul ecrivain a la fois sur recharges.json, bureau ou telephone.

L'application de bureau et le serveur du telephone sont deux programmes qui
reecrivent tout recharges.json. Sans verrou commun, si le telephone lisait
le fichier, puis que le bureau enregistrait une recharge, l'ecriture du
telephone (faite sur sa copie d'avant) effacait la recharge du bureau, sans
un mot (audit a blanc du 03/11/2026, chantier C2).

Ici, un second programme joue le telephone : il lit le fichier, attend un
peu, puis ecrit. Pendant ce temps, ce programme-ci enregistre une recharge.

    py -m pytest tests/test_verrou_ecriture.py
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
# setdefault : sous pytest, conftest.py a deja pose la sienne. Ce fichier-ci
# travaille dans son propre dossier, redirige au debut de chaque test et
# rendu a la fin (comme test_mobile.py) : le rediriger des l'import
# deplacait aussi les donnees des AUTRES fichiers de test.
DOSSIER_TEST = Path(tempfile.mkdtemp(prefix="recharges_verrou_"))
os.environ.setdefault("RECHARGES_DATA_DIR", str(DOSSIER_TEST))
PROJET = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJET))

import recharges as r  # noqa: E402

# Le « telephone » : il prend le verrou (s'il existe), lit, se signale,
# patiente, puis ecrit sa copie avec sa propre recharge.
TELEPHONE = textwrap.dedent("""
    import contextlib, sys, time
    sys.path.insert(0, sys.argv[1])
    import recharges as r
    verrou = getattr(r, "verrou_donnees", contextlib.nullcontext)
    with verrou():
        data = r.charger_donnees(pour_modification=True)
        data["recharges"].append({
            "id": "telephone", "date": "2026-03-02T10:00",
            "lieu": "exterieur", "operateur": "Telephone",
            "kwh": 30.0, "cout_eur": 15.0, "prix_kwh": 0.5})
        open(sys.argv[2], "w").close()          # « j'ai lu »
        time.sleep(float(sys.argv[3]))
        r.sauvegarder_donnees(data)
""")


class TestVerrouEcriture(unittest.TestCase):

    def setUp(self):
        self.origine = r.dossier_donnees()
        r.rediriger_donnees(DOSSIER_TEST)
        self.addCleanup(r.rediriger_donnees, self.origine)
        # Dossier vide, backups/ compris : sinon un recharges.json disparu
        # est restaure depuis la sauvegarde du test precedent.
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
        self.script = DOSSIER_TEST / "telephone.py"
        self.script.write_text(TELEPHONE, encoding="utf-8")
        self.pret = DOSSIER_TEST / "pret.txt"
        self.pret.unlink(missing_ok=True)

    def lancer_telephone(self, pause: float) -> subprocess.Popen:
        env = dict(os.environ, RECHARGES_DATA_DIR=str(DOSSIER_TEST))
        proc = subprocess.Popen([sys.executable, str(self.script),
                                 str(PROJET), str(self.pret), str(pause)],
                                env=env)
        limite = time.monotonic() + 30
        while not self.pret.exists():
            self.assertIsNone(proc.poll(), "le « telephone » s'est arrete")
            self.assertLess(time.monotonic(), limite, "le « telephone » tarde")
            time.sleep(0.05)
        return proc

    def test_le_bureau_attend_et_rien_n_est_efface(self):
        telephone = self.lancer_telephone(pause=1.5)
        # Le telephone a lu le fichier et n'a pas encore ecrit.
        r.ajouter_recharge_exterieur(25.0, 12.0, operateur="Bureau",
                                     date="2026-03-03T10:00")
        self.assertEqual(telephone.wait(timeout=30), 0)
        r.vider_cache()
        presentes = {x.get("operateur") for x in r.charger_donnees()["recharges"]}
        self.assertEqual(presentes, {"Depart", "Telephone", "Bureau"})

    def test_trop_longue_attente_dit_que_les_donnees_sont_occupees(self):
        """Au-dela de l'attente prevue, un message clair, et rien d'ecrit."""
        attente = r.ATTENTE_VERROU_S
        r.ATTENTE_VERROU_S = 0.5
        try:
            telephone = self.lancer_telephone(pause=3)
            with self.assertRaises(r.DonneesOccupees) as occupe:
                r.ajouter_recharge_exterieur(25.0, 12.0, operateur="Bureau",
                                             date="2026-03-03T10:00")
            self.assertIn("réessayez", str(occupe.exception))
            self.assertEqual(telephone.wait(timeout=30), 0)
        finally:
            r.ATTENTE_VERROU_S = attente
        r.vider_cache()
        presentes = {x.get("operateur") for x in r.charger_donnees()["recharges"]}
        self.assertEqual(presentes, {"Depart", "Telephone"})

    def test_un_verrou_pris_deux_fois_par_le_meme_programme(self):
        """Une fonction qui en appelle une autre (reglages de la borne, puis
        recalcul) reprend le verrou deja tenu : pas de blocage."""
        with r.verrou_donnees():
            with r.verrou_donnees():
                r.ajouter_recharge_exterieur(25.0, 12.0, operateur="Bureau",
                                             date="2026-03-03T10:00")
        self.assertEqual(len(r.charger_donnees()["recharges"]), 2)


if __name__ == "__main__":
    unittest.main()
