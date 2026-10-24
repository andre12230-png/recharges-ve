"""Un emoji, puis UNE espace, puis le texte (charte, section 2).

Audit du 08/10/2026 : onze textes mettaient deux espaces apres l'emoji, ce
que ni Pecule ni le Photovoltaique ne font. Le test lit les chaines du code
de l'interface.

    py -m pytest tests/test_emoji_une_espace.py
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

PROJET = Path(__file__).resolve().parent.parent
EMOJI_PUIS_DEUX_ESPACES = re.compile(
    "[\U0001F300-\U0001FAFF\u2600-\u27BF][\uFE0F]?  ")


def _fichiers() -> list[Path]:
    ignores = {"tests", "build", "dist", ".venv", "distribution",
               "installeur", "migration", "docs", "__pycache__"}
    return [p for p in PROJET.rglob("*.py")
            if not ignores.intersection(p.relative_to(PROJET).parts)]


def test_une_seule_espace_apres_un_emoji():
    fautes = []
    for p in _fichiers():
        arbre = ast.parse(p.read_text(encoding="utf-8"))
        for noeud in ast.walk(arbre):
            if (isinstance(noeud, ast.Constant) and isinstance(noeud.value, str)
                    and EMOJI_PUIS_DEUX_ESPACES.search(noeud.value)):
                fautes.append(f"{p.name}:{noeud.lineno}")
    assert not fautes, fautes
