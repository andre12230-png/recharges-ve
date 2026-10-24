"""Le titre d'une boite de message dit de quoi il s'agit (charte).

Audit du 08/10/2026 : huit boites s'intitulaient « Erreur », ce qui ne dit
ni ce qui a echoue ni quoi faire. Le test lit le code de l'interface.

    py -m pytest tests/test_titres_des_boites.py
"""

from __future__ import annotations

import re
from pathlib import Path

PROJET = Path(__file__).resolve().parent.parent
# Une boite de message dont le titre est un mot vague, seul.
TITRE_VAGUE = re.compile(r'''QMessageBox\.\w+\(\s*[\w.]+,\s*"(Erreur|Attention|Information|Saisie)"''')


def test_aucun_titre_vague():
    fautes = []
    for p in [PROJET / "fenetre.py", *PROJET.glob("pages/*.py"),
              *PROJET.glob("dialogue_*.py")]:
        texte = p.read_text(encoding="utf-8")
        for m in TITRE_VAGUE.finditer(texte):
            ligne = texte.count("\n", 0, m.start()) + 1
            fautes.append(f"{p.name}:{ligne} « {m.group(1)} »")
    assert not fautes, fautes
