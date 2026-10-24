"""Pas de pluriel entre parentheses dans les textes de l'application.

Charte des trois applis (29/09/2026) : « 3 ligne(s) non reconnue(s) »,
« 2 recharge(s) laissee(s) »... L'application connait le nombre : elle
accorde (« 1 ligne », « 2 lignes »). Meme regle et meme test que dans le
Photovoltaique.

Le test lit le code de l'application : chaque chaine de caracteres (textes
des f-strings compris), hors commentaires et descriptions de fonctions
(docstrings), que l'utilisateur ne voit jamais.

    py -m pytest tests/test_pluriels.py
"""
from __future__ import annotations

import ast
import re
from pathlib import Path

PROJET = Path(__file__).resolve().parent.parent
# « ligne(s) », « nouveau(x) », « laissée(s) »... ; pas « f(x) ».
PLURIEL_ENTRE_PARENTHESES = re.compile(r"[a-zà-ÿ]{2,}\((s|x|e|es)\)")


def _fichiers_de_l_application() -> list[Path]:
    ignores = {"tests", "build", "dist", ".venv", "distribution",
               "installeur", "migration", "docs", "__pycache__"}
    return [p for p in PROJET.rglob("*.py")
            if not ignores.intersection(p.relative_to(PROJET).parts)]


def _docstrings(arbre: ast.AST) -> set[int]:
    """Identifiants des noeuds qui sont des docstrings."""
    ids = set()
    for noeud in ast.walk(arbre):
        if isinstance(noeud, (ast.Module, ast.ClassDef, ast.FunctionDef,
                              ast.AsyncFunctionDef)):
            corps = noeud.body
            if (corps and isinstance(corps[0], ast.Expr)
                    and isinstance(corps[0].value, ast.Constant)
                    and isinstance(corps[0].value.value, str)):
                ids.add(id(corps[0].value))
    return ids


def test_aucun_pluriel_entre_parentheses():
    trouves = []
    for fichier in _fichiers_de_l_application():
        arbre = ast.parse(fichier.read_text(encoding="utf-8"))
        docs = _docstrings(arbre)
        for noeud in ast.walk(arbre):
            if (isinstance(noeud, ast.Constant) and isinstance(noeud.value, str)
                    and id(noeud) not in docs
                    and PLURIEL_ENTRE_PARENTHESES.search(noeud.value)):
                trouves.append(f"{fichier.relative_to(PROJET)}:{noeud.lineno} "
                               f"{noeud.value.strip()[:60]!r}")
    assert not trouves, "\n".join(trouves)


def test_le_test_voit_bien_un_pluriel_entre_parentheses():
    """Garde-fou : le motif reconnait les formes relevees le 29/09/2026."""
    for texte in ("3 ligne(s) non", "0 nouveau(x)", "recharge(s) laissée(s)"):
        assert PLURIEL_ENTRE_PARENTHESES.search(texte), texte
    # Une formule a une lettre n'est pas un pluriel.
    assert not PLURIEL_ENTRE_PARENTHESES.search("f(x) et g(e)")
