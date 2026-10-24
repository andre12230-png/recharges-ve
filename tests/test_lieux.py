"""Les lieux de recharge : liste proposee, et orthographe unique.

Constat du 19/09/2026 sur de vraies donnees : une trentaine de libelles
pour quelques dizaines de recharges exterieures, et le meme lieu ecrit de trois facons —
« Tilleuls (A7) », « Tilleuls - Aire des Tilleuls (A7) »,
« Tilleuls - Aire des Tilleuls, A7 ». Chacune compte pour un lieu distinct
dans les statistiques.

Deux parades, verifiees ici : le formulaire propose les lieux deja employes
(on choisit au lieu de reecrire), et une ecriture qui ne differe que par la
casse, les accents ou les espaces rejoint celle deja en service.

    py -m pytest
"""

import os
import shutil
import sys
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

# --- redirection des donnees : AVANT l'import de recharges (test_isolation) --
DOSSIER_TEST = Path(tempfile.mkdtemp(prefix="recharges_lieux_"))
os.environ["RECHARGES_DATA_DIR"] = str(DOSSIER_TEST)
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import recharges as r  # noqa: E402

r.rediriger_donnees(DOSSIER_TEST)


def tearDownModule():
    shutil.rmtree(DOSSIER_TEST, ignore_errors=True)


class BaseLieux(unittest.TestCase):
    def setUp(self):
        r.sauvegarder_donnees({"recharges": []})

    def poser(self, *lieux: str):
        """Enregistre une recharge exterieure par lieu, dans l'ordre donne."""
        for i, lieu in enumerate(lieux):
            r.ajouter_recharge_exterieur(
                20, 10, operateur="Ionity", lieu_detail=lieu,
                date=datetime(2026, 9, 1, 8, i).isoformat(timespec="minutes"))

    def poser_brut(self, *recharges: dict):
        """Ecrit les recharges TELLES QUELLES, sans passer par la saisie.

        Indispensable pour les cas d'avant : depuis que lieu_canonique()
        s'applique a l'enregistrement, on ne PEUT plus creer deux
        orthographes d'un meme lieu par le formulaire. Elles n'existent que
        dans les fichiers deja constitues — comme celui d'André, ou
        « Tilleuls (A7) » et « Tilleuls - Aire des Tilleuls (A7) » cohabitent.
        """
        data = r.charger_donnees(pour_modification=True)
        for i, recharge in enumerate(recharges):
            data["recharges"].append({
                "id": f"essai{i}", "lieu": "exterieur",
                "date": datetime(2026, 9, 1, 8, i).isoformat(timespec="minutes"),
                "kwh": 20, "cout_eur": 10, **recharge})
        r.sauvegarder_donnees(data)


class TestLieuxDejaSaisis(BaseLieux):
    def test_aucune_recharge(self):
        self.assertEqual(r.lieux_deja_saisis(), [])

    def test_les_plus_frequents_en_tete(self):
        """On recharge presque toujours aux memes endroits : ils doivent
        tomber sous la main sans derouler toute la liste."""
        self.poser("Centre-ville", "Tilleuls", "Tilleuls", "Parking de la Gare", "Tilleuls",
                   "Centre-ville")
        self.assertEqual(r.lieux_deja_saisis(),
                         ["Tilleuls", "Centre-ville", "Parking de la Gare"])

    def test_a_egalite_le_plus_recent_dabord(self):
        self.poser("Centre-ville", "Parking de la Gare")
        self.assertEqual(r.lieux_deja_saisis(), ["Parking de la Gare", "Centre-ville"])

    def test_une_seule_orthographe_par_lieu(self):
        """Sur des donnees deja constituees, la liste ne doit pas proposer
        les deux facons d'ecrire un lieu : elle servirait a perpetuer le
        doublon. C'est la plus employee qui est retenue."""
        self.poser_brut({"lieu_detail": "AIRE DU LAC"},
                        {"lieu_detail": "Aire du Lac"},
                        {"lieu_detail": "Aire du Lac"})
        self.assertEqual(r.lieux_deja_saisis(), ["Aire du Lac"])

    def test_deux_libelles_differents_restent_distincts(self):
        """LIMITE ASSUMEE. « Tilleuls (A7) » et « Tilleuls - Aire des Tilleuls
        (A7) » designent le meme endroit chez l'auteur, mais ce sont deux
        libelles differents et le programme les garde tels quels : deviner
        qu'ils se valent supposerait de rapprocher aussi « Tilleuls » et
        « Tilleuls Nord », qui sont deux vraies bornes. Le rapprochement
        automatique ne porte que sur la casse, les accents et les espaces.

        La liste deroulante agit en amont : en proposant les deux, elle
        evite d'en inventer un troisieme. Fusionner ceux qui existent deja
        est une decision d'utilisateur, pas une regle de programme."""
        self.poser_brut({"lieu_detail": "Tilleuls (A7)"},
                        {"lieu_detail": "Tilleuls - Aire des Tilleuls (A7)"})
        self.assertEqual(sorted(r.lieux_deja_saisis()),
                         ["Tilleuls (A7)", "Tilleuls - Aire des Tilleuls (A7)"])

    def test_les_lieux_vides_sont_ignores(self):
        self.poser("Centre-ville", "", "   ")
        self.assertEqual(r.lieux_deja_saisis(), ["Centre-ville"])

    def test_les_recharges_maison_ne_comptent_pas(self):
        """Elles n'ont pas de lieu : rien ne doit remonter d'elles."""
        self.poser("Centre-ville")
        self.poser_brut({"lieu": "maison", "tarif_nom": "Base"})
        self.assertEqual(r.lieux_deja_saisis(), ["Centre-ville"])


class TestLieuCanonique(BaseLieux):
    def test_lieu_inconnu_rendu_tel_quel(self):
        self.assertEqual(r.lieu_canonique("Montélimar"), "Montélimar")

    def test_espaces_en_trop_nettoyes(self):
        self.assertEqual(r.lieu_canonique("  Aire   des  Tilleuls "),
                         "Aire des Tilleuls")

    def test_la_casse_rejoint_l_ecriture_en_service(self):
        self.poser("AIRE DU LAC")
        self.assertEqual(r.lieu_canonique("aire du lac"), "AIRE DU LAC")

    def test_les_accents_aussi(self):
        self.poser("Montélimar")
        self.assertEqual(r.lieu_canonique("MONTELIMAR"), "Montélimar")

    def test_vide_reste_vide(self):
        self.assertEqual(r.lieu_canonique("   "), "")


class TestAppliqueAuxEnregistrements(BaseLieux):
    def test_a_la_saisie(self):
        self.poser("AIRE DU LAC", "aire du lac")
        lieux = [x["lieu_detail"] for x in r.charger_donnees()["recharges"]]
        self.assertEqual(lieux, ["AIRE DU LAC", "AIRE DU LAC"])

    def test_a_la_modification(self):
        """Corriger une recharge ne doit pas non plus creer un second lieu."""
        self.poser("AIRE DU LAC", "Centre-ville")
        a_corriger = r.charger_donnees()["recharges"][1]
        r.modifier_recharge(a_corriger["id"], {"lieu_detail": "  aire du lac  "})
        lieux = [x["lieu_detail"] for x in r.charger_donnees()["recharges"]]
        self.assertEqual(lieux, ["AIRE DU LAC", "AIRE DU LAC"])

    def test_un_lieu_vraiment_nouveau_passe(self):
        """La normalisation ne doit pas empecher d'enregistrer un lieu neuf."""
        self.poser("AIRE DU LAC", "Tilleuls")
        self.assertEqual(
            sorted(x["lieu_detail"] for x in r.charger_donnees()["recharges"]),
            ["AIRE DU LAC", "Tilleuls"])


if __name__ == "__main__":
    unittest.main()
