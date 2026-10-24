"""Garde-fou : plus de boite de dialogue ni d'erreur Python a la saisie.

Jusqu'a la v1.26.2, les trois fonctions d'enregistrement etaient bornees
par un `except Exception` qui affichait `str(e)` dans une messagebox. Un
champ « Energie » laisse vide ouvrait donc une boite disant
« could not convert string to float: '' ».

Ce test lit le code des fonctions d'enregistrement de chaque formulaire
(et non leur comportement : il faudrait ouvrir une fenetre) et refuse le
retour en arriere : un test qui observe peut rester vert par hasard, un
test qui lit le code, non. Depuis la 2.0.0, ce sont les formulaires
PySide6 (pages/, dialogue_*.py) ; le comportement lui-meme est eprouve par
les tests test_qt_*.py.

    py -m pytest
"""

import ast
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

RACINE = Path(__file__).resolve().parent.parent


def corps(fichier: str, fonction: str) -> ast.FunctionDef:
    arbre = ast.parse((RACINE / fichier).read_text(encoding="utf-8"))
    for noeud in ast.walk(arbre):
        if isinstance(noeud, ast.FunctionDef) and noeud.name == fonction:
            return noeud
    raise AssertionError(f"{fonction} est introuvable dans {fichier}")


def appels(noeud: ast.AST) -> set[str]:
    """Les noms des fonctions appelees, « messagebox.showerror » compris."""
    noms = set()
    for n in ast.walk(noeud):
        if isinstance(n, ast.Call):
            noms.add(ast.unparse(n.func))
    return noms


# Chaque formulaire : fichier, fonction d'enregistrement, fonction de
# saisie.py qui lit ses cases, et ce qui affiche l'erreur sous la case.
FORMULAIRES_QT = [
    ("pages/ajouter.py", "enregistrer_maison", "lire_recharge_maison",
     "f.erreur"),
    ("pages/ajouter.py", "enregistrer_exterieur", "lire_recharge_exterieur",
     "f.erreur"),
    ("pages/kilometrage.py", "enregistrer_releve", "lire_releve_km", "erreur"),
    ("dialogue_modifier.py", "enregistrer", "lire_modification_recharge",
     "f.erreur"),
    ("dialogue_tarif.py", "enregistrer", "lire_tarif", "f.erreur"),
]


class TestFormulaires(unittest.TestCase):
    def test_messages_sous_la_case_sans_boite_ni_attrape_tout(self):
        for fichier, fonction, lecture, afficheur in FORMULAIRES_QT:
            with self.subTest(fonction=fonction):
                noeud = corps(fichier, fonction)
                noms = appels(noeud)
                # Les cases passent par saisie.py...
                self.assertIn(lecture, noms)
                self.assertNotIn("float", noms)
                # ... et l'erreur s'ecrit sous la case fautive.
                self.assertIn(afficheur, noms)
                for appel in noms:
                    self.assertNotIn("critical", appel)
                    self.assertNotIn("showerror", appel)
                for n in ast.walk(noeud):
                    if isinstance(n, ast.ExceptHandler):
                        attrapes = ast.unparse(n.type) if n.type else "tout"
                        self.assertNotIn("Exception", attrapes)


if __name__ == "__main__":
    unittest.main()
