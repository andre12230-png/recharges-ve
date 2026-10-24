"""Vocabulaire et typographie des textes affiches (charte des applis).

Audit de design du 03/10/2026 : le tiret court « - » separait les mots
partout (« 1 recharge - 30,24 kWh », « DÉPENSE - OCTOBRE 2026 », titre de la
fenetre). La charte veut le point median « · » ou le tiret long « — » entre
deux mots, et « du … au … » pour une periode.
"""

import ast
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
# Les fichiers qui composent ce que l'utilisateur lit a l'ecran.
INTERFACE = (sorted((RACINE / "pages").glob("*.py"))
             + [RACINE / f for f in (
                 "fenetre.py", "filtres.py", "composants.py",
                 "formulaire.py", "dialogue_modifier.py", "dialogue_tarif.py",
                 "dialogue_colonnes.py", "fenetres_aide.py", "menu.py")])


def _textes(fichier: Path):
    """Les morceaux de texte du code (chaines et parties fixes des
    f-strings), sans les docstrings ni les commentaires."""
    arbre = ast.parse(fichier.read_text(encoding="utf-8"))
    docstrings = set()
    for noeud in ast.walk(arbre):
        if isinstance(noeud, (ast.Module, ast.FunctionDef, ast.ClassDef,
                              ast.AsyncFunctionDef)):
            corps = noeud.body
            if (corps and isinstance(corps[0], ast.Expr)
                    and isinstance(corps[0].value, ast.Constant)):
                docstrings.add(id(corps[0].value))
    for noeud in ast.walk(arbre):
        if (isinstance(noeud, ast.Constant) and isinstance(noeud.value, str)
                and id(noeud) not in docstrings):
            yield noeud.lineno, noeud.value


def test_pas_de_tiret_court_entre_deux_mots():
    fautes = []
    for fichier in INTERFACE:
        for ligne, texte in _textes(fichier):
            if " - " in texte or texte.startswith("- ") and len(texte) > 2:
                fautes.append(f"{fichier.name}:{ligne} {texte!r}")
    assert not fautes, ("« - » entre deux mots (« · » ou « — ») :\n"
                        + "\n".join(fautes))


def test_pas_de_barre_verticale_entre_deux_mots():
    fautes = [f"{f.name}:{ligne} {texte!r}"
              for f in INTERFACE for ligne, texte in _textes(f)
              if " | " in texte]
    assert not fautes, "« | » entre deux mots : " + ", ".join(fautes)


def test_pas_d_abreviation_dans_les_textes():
    """« Consommation » et non « Conso » ; « 31 jours » et non « 31 j »
    (charte : ni anglicisme ni abreviation dans une phrase). Les cles de
    donnees (« conso », sans espace) ne sont pas du texte affiche."""
    import re
    fautes = []
    for fichier in INTERFACE:
        for ligne, texte in _textes(fichier):
            if " " not in texte.strip() and ":" not in texte:
                continue
            if (re.search(r"\b[Cc]onso\b|\bCONSO\b", texte)
                    or re.match(r"^ j\b", texte)):
                fautes.append(f"{fichier.name}:{ligne} {texte!r}")
    assert not fautes, "Abréviation dans un texte : " + ", ".join(fautes)


def test_pas_d_esperluette_entre_deux_mots():
    """« Énergie et coût par mois », pas « Énergie & coût » : la charte ne
    veut pas d'abreviation dans un texte (07/10/2026)."""
    fautes = [f"{f.name}:{ligne} {texte!r}"
              for f in INTERFACE for ligne, texte in _textes(f)
              if " & " in texte]
    assert not fautes, "« & » entre deux mots : " + ", ".join(fautes)
