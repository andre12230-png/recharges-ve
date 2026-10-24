"""Tests du menu de gauche.

Le menu est decrit une seule fois, dans menu.SECTIONS, et trois choses en
dependent : la barre laterale, le titre affiche en haut de la page, et la
verification automatique (--autotest). Ces tests verifient qu'aucune des
trois ne peut se desynchroniser des autres.

Ils lisent menu.py et pages/ sans ouvrir de fenetre.

    py -m pytest
"""

import os
import sys
import tempfile
import unittest
from pathlib import Path

# pages/ importe recharges.py, qui fixe l'emplacement des donnees a son
# import : sans cette redirection posee AVANT, l'importer ici suffirait a
# faire ecrire toute la suite de tests dans les vraies recharges. C'est
# exactement ce qui est arrive le 07/09/2026 (avec app.py) — voir
# test_isolation.py.
os.environ.setdefault("RECHARGES_DATA_DIR",
                      tempfile.mkdtemp(prefix="recharges_menu_"))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import menu  # noqa: E402


def entrees():
    """Toutes les entrees du menu, sections confondues."""
    return [(vue_id, texte, picto)
            for _, items in menu.SECTIONS for vue_id, texte, picto in items]


class TestMenu(unittest.TestCase):
    def test_le_billet_reste_a_l_argent_comme_au_photovoltaique(self):
        """💶 est « Synthèse financière » dans le Photovoltaïque : le même
        emoji ne peut pas dire « Tarifs » ici (harmonisé le 11/10/2026, la
        page Tarifs prend ⚡)."""
        pictos = {vue_id: picto for vue_id, _, picto in entrees()}
        self.assertNotIn("💶", pictos.values())
        self.assertEqual(pictos["tarifs"], "⚡")

    def test_chaque_entree_mene_a_une_page(self):
        """Une entree sans constructeur donnerait une page blanche, en
        silence : afficher_vue ne trouve rien et ne dit rien."""
        from pages import CONSTRUCTEURS

        for vue_id, texte, _ in entrees():
            self.assertIn(vue_id, CONSTRUCTEURS,
                          f"l'entree « {texte} » n'a pas de page")

    def test_chaque_entree_a_un_titre(self):
        """Sans titre, l'en-tete de la page afficherait l'identifiant
        interne (« notice ») au lieu d'un libelle. Les titres sont decrits
        une seule fois, dans menu.py."""
        for vue_id, texte, _ in entrees():
            self.assertIn(vue_id, menu.TITRES,
                          f"l'entree « {texte} » n'a pas de titre de page")
            titre, sous_titre = menu.TITRES[vue_id]
            self.assertTrue(titre and sous_titre, vue_id)

    def test_les_sous_titres_disent_ce_que_contient_la_page(self):
        """11/10/2026 : le sous-titre sert aussi d'infobulle au bouton du
        bandeau. Charte : des mots, pas de « / » entre deux mots ; et une
        phrase qui dit ce qu'on trouve (c'etait « Analyse detaillee »)."""
        for vue_id, (_, sous_titre) in menu.TITRES.items():
            self.assertNotIn(" / ", sous_titre, vue_id)
        self.assertEqual(menu.TITRES["stats"][1],
                         "Énergie et coût mois par mois, et par tarif, "
                         "opérateur et carte")
        self.assertEqual(menu.TITRES["historique"][1],
                         "Toutes vos recharges, à modifier ou supprimer")
        # Les pages qui ont leur pendant dans le Photovoltaique se
        # repondent (11/10/2026).
        self.assertEqual(menu.TITRES["ajouter"][1],
                         "Saisir une recharge, à la maison ou sur une borne "
                         "extérieure")
        self.assertEqual(menu.TITRES["parametres"][1],
                         "Votre voiture, votre borne, l'abonnement de la "
                         "maison et vos données")

    def test_la_fenetre_lit_le_menu(self):
        """La fenetre construit son bandeau depuis menu.SECTIONS : une page
        ajoutee a menu.py y apparait d'office."""
        import fenetre
        self.assertIs(fenetre.menu.SECTIONS, menu.SECTIONS)

    def test_les_identifiants_sont_uniques(self):
        """Deux entrees de meme identifiant se partageraient un seul bouton :
        la seconde ecraserait la premiere dans boutons_nav."""
        ids = [vue_id for vue_id, _, _ in entrees()]

        self.assertEqual(len(ids), len(set(ids)))

    def test_chaque_entree_a_un_pictogramme(self):
        """Un pictogramme vide decalerait le libelle par rapport aux autres."""
        for vue_id, _, picto in entrees():
            self.assertTrue(picto.strip(), vue_id)
            # Un emoji, comme dans Pecule et le Photovoltaique (v1.24.0) :
            # jamais une lettre ou un chiffre, qu'on lirait avec le libelle.
            self.assertFalse(any(c.isalnum() for c in picto), vue_id)

    def test_la_notice_est_dans_le_menu(self):
        """Elle est la raison d'etre de la section AIDE : si elle disparait,
        la section reste et n'a plus rien a montrer."""
        self.assertIn("notice", [vue_id for vue_id, _, _ in entrees()])


if __name__ == "__main__":
    unittest.main()
