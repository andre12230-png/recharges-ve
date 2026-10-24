"""Le garde-fou : les tests n'ecrivent jamais dans les vraies donnees.

Le 07/09/2026, l'ajout d'un test qui importait app.py a suffi a faire ecrire
la suite de tests dans recharges.json : le fichier a ete vide de ses 255
recharges (recupere depuis les sauvegardes automatiques). recharges.py fixe
l'emplacement des donnees a son import, et la redirection posee par
test_recharges.py arrivait trop tard.

Ce test verifie ce qu'aucun autre ne verifiait : que le dossier de donnees
utilise pendant les tests n'est PAS celui de l'application. Il tombe avant
que des donnees ne soient perdues, et non apres.

    py -m pytest
"""

import os
import sys
import tempfile
import unittest
from pathlib import Path

# Meme precaution que les autres fichiers de test : la variable doit etre
# posee avant l'import du projet, pour le cas ou ce fichier serait le premier
# a l'importer (unittest ne lit pas conftest.py).
os.environ.setdefault("RECHARGES_DATA_DIR",
                      tempfile.mkdtemp(prefix="recharges_isolation_"))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import recharges as r  # noqa: E402

RACINE = Path(__file__).resolve().parent.parent


class TestIsolationDesDonnees(unittest.TestCase):
    def test_le_dossier_de_donnees_est_temporaire(self):
        """Si ce test echoue, ARRETEZ TOUT : la suite s'apprete a ecrire dans
        les vraies recharges. La cause est toujours la meme — un fichier de
        test a importe le projet avant que la redirection ne soit posee."""
        vrai = (RACINE / "dist").resolve()

        self.assertNotEqual(Path(r.BASE).resolve(), vrai,
                            "les tests pointent sur les vraies donnees")

    def test_le_fichier_de_recharges_suit_le_dossier(self):
        """DATA_FILE, TARIFS_FILE et BACKUP_DIR sont calcules a partir de
        BASE : ils doivent tous les trois rester dans le dossier temporaire."""
        base = Path(r.BASE).resolve()

        for chemin in (r.DATA_FILE, r.TARIFS_FILE, r.BACKUP_DIR):
            self.assertEqual(Path(chemin).resolve().parent, base, chemin)

    def test_la_redirection_est_bien_celle_de_l_environnement(self):
        """C'est RECHARGES_DATA_DIR qui commande — la porte de sortie prevue
        pour les tests, et la seule."""
        attendu = Path(os.environ["RECHARGES_DATA_DIR"]).resolve()

        self.assertEqual(Path(r.BASE).resolve(), attendu)


if __name__ == "__main__":
    unittest.main()
