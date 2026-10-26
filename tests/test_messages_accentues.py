"""Les messages montres a l'utilisateur sont accentues (controle du 26/10/2026).

Le controle du francais a trouve des messages de la fenetre des tarifs
ecrits sans accents : « doit etre superieur a zero », « ne peut pas etre
negatif », « serait comptee deux fois ». Ce test lit tout le texte du code
de l'application et refuse les formes non accentuees les plus courantes.
Les docstrings, les messages d'assert et les journaux techniques (print)
ne s'affichent pas a l'ecran : ils sont laisses de cote.

    py -m pytest tests/test_messages_accentues.py
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

PROJET = Path(__file__).resolve().parent.parent
IGNORES = {"tests", "build", "dist", ".venv", "distribution", "installeur",
           "migration", "docs", "__pycache__", "outils", "mobile"}
# La feuille de style (ses commentaires sont dans une chaine) ne s'affiche pas.
HORS_ECRAN = {"theme_qt.py"}

# Mots qui ne s'ecrivent jamais ainsi en francais correct. « duree » et
# « annees » seuls sont aussi des noms de donnees internes : on ne les
# cherche que dans une tournure de phrase (« la duree du », « en annees »).
SANS_ACCENT = re.compile(
    r"\b(?:etre|negatifs?|negatives?|superieure?s?|inferieure?s?|comptees?|"
    r"fenetres?|rechargees|duree du|en annees|modeles?|a cote|a zero|"
    r"debut du|livre avec|annule\.)(?![\w'])",
    re.IGNORECASE)


def _fichiers() -> list[Path]:
    return [p for p in sorted(PROJET.rglob("*.py"))
            if not IGNORES.intersection(p.relative_to(PROJET).parts)
            and p.name not in HORS_ECRAN]


def _textes_affiches(fichier: Path):
    """Les chaines du code, sans docstrings, messages d'assert ni print."""
    arbre = ast.parse(fichier.read_text(encoding="utf-8"))
    ignores = set()
    for n in ast.walk(arbre):
        if isinstance(n, (ast.Module, ast.FunctionDef, ast.ClassDef,
                          ast.AsyncFunctionDef)):
            corps = n.body
            if (corps and isinstance(corps[0], ast.Expr)
                    and isinstance(corps[0].value, ast.Constant)):
                ignores.add(id(corps[0].value))
        if isinstance(n, ast.Assert) and n.msg is not None:
            ignores.update(id(m) for m in ast.walk(n.msg))
        if (isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
                and n.func.id == "print"):
            for arg in n.args:
                ignores.update(id(m) for m in ast.walk(arg))
    for n in ast.walk(arbre):
        if (isinstance(n, ast.Constant) and isinstance(n.value, str)
                and id(n) not in ignores):
            yield n.lineno, n.value


def test_aucun_message_sans_accent():
    fautes = []
    for fichier in _fichiers():
        for ligne, texte in _textes_affiches(fichier):
            trouve = SANS_ACCENT.search(texte)
            if trouve:
                fautes.append(f"{fichier.relative_to(PROJET)}:{ligne} "
                              f"« {trouve.group(0)} »")
    assert not fautes, "Accents manquants :\n" + "\n".join(fautes)


def test_les_messages_des_tarifs_sont_accentues():
    """Le cas trouve par le controle, verifie sur le message lui-meme."""
    import pytest
    import recharges as r

    tarif = {"nom": "Essai", "type": "simple", "debut": "2026-01-01",
             "fin": None, "prix_kwh": 0, "abonnement_mensuel": 10}
    with pytest.raises(ValueError) as erreur:
        r.valider_tarif(tarif)
    assert "doit être supérieur à zéro" in str(erreur.value)
