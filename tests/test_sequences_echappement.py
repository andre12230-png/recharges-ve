"""Aucun antislash mal compris par Python dans le code (29/09/2026).

Le texte d'aide en tete d'app.py donnait l'exemple « C:\\chemin\\rapport.txt »
dans une chaine ordinaire : Python y lisait « \\c » (sequence inconnue :
avertissement « invalid escape sequence », erreur dans une version future)
et « \\r » (un retour chariot invisible, qui abimait le chemin sans rien
dire). Ce test compile chaque fichier du projet en traitant l'avertissement
comme une erreur.

    py -m pytest tests/test_sequences_echappement.py
"""

from __future__ import annotations

import warnings
from pathlib import Path

import pytest

PROJET = Path(__file__).resolve().parent.parent
FICHIERS = sorted([*PROJET.glob("*.py"), *(PROJET / "pages").glob("*.py"),
                   *(PROJET / "tests").glob("*.py")])


@pytest.mark.parametrize("fichier", FICHIERS, ids=lambda f: f.name)
def test_aucune_sequence_d_echappement_invalide(fichier):
    source = fichier.read_text(encoding="utf-8")
    with warnings.catch_warnings():
        warnings.simplefilter("error", SyntaxWarning)
        compile(source, str(fichier), "exec")


def test_le_chemin_d_exemple_d_app_py_est_intact():
    """Le « \\r » de « \\rapport.txt » ne doit pas devenir un retour chariot."""
    import app
    assert r"C:\chemin\rapport.txt" in app.__doc__
    assert "\r" not in app.__doc__
