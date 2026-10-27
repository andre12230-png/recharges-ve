"""Controle du francais du 26/10/2026 : le lot de Recharges VE corrige le
27/10/2026 (rapport : F:\\Projets\\livrables\\controle-francais-applis-26-10-2026.md).

- Pluriels accordes selon le nombre : compte rendu de l'import, question
  de suppression d'un tarif (« 1 recharges ont ete calculees »).
- « OK : » remplace par « ✓ », comme « ✓ Réglages enregistrés. » ;
  « rapport PDF généré -> fichier » sans fleche ni anglicisme.
- La page Essence nomme la periode comme le menu : « Toute la période ».
- « … » et non « ... » dans les textes affiches.
- Jeu de demonstration accentue (autotest, captures du site).
- « sauvegarde en ligne » et non « sauvegarde cloud ».

    py -m pytest tests/test_francais_2026_10_27.py
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

import recharges

RACINE = Path(recharges.__file__).parent


def _res(n: int) -> dict:
    return {"ajoutes": n, "remplaces": n, "doublons": n, "zero_kwh": n,
            "total_lus": n}


# ---------- pluriels ----------

def test_import_un_de_chaque_au_singulier():
    from pages import importer as im
    texte, _ = im.texte_resultat(_res(1))
    assert texte.startswith("✓ ")
    for morceau in ("1 ajoutée,", "1 saisie manuelle remplacée,",
                    "1 doublon,", "1 ignorée,", "1 lue"):
        assert morceau in texte, morceau


def test_import_deux_de_chaque_au_pluriel():
    from pages import importer as im
    texte, _ = im.texte_resultat(_res(2))
    for morceau in ("2 ajoutées,", "2 saisies manuelles remplacées,",
                    "2 doublons,", "2 ignorées,", "2 lues"):
        assert morceau in texte, morceau


def test_import_zero_au_singulier_comme_en_francais():
    from pages import importer as im
    texte, _ = im.texte_resultat(_res(0))
    assert "0 ajoutée," in texte and "0 doublon," in texte


@pytest.mark.parametrize("n, attendu", [
    (1, "1 recharge a été calculée avec ce tarif. Elle gardera son montant "
        "actuel, mais un recalcul la refusera"),
    (3, "3 recharges ont été calculées avec ce tarif. Elles garderont leur "
        "montant actuel, mais un recalcul les refusera"),
])
def test_suppression_d_un_tarif_accordee(n, attendu):
    from pages import tarifs
    texte = tarifs.question_suppression(
        {"nom": "Essai", "debut": "2026-01-01", "fin": None}, n)
    assert attendu in texte


# ---------- textes affiches ----------

def test_message_essence_nomme_la_periode_comme_le_menu():
    from pages import periode
    textes = " ".join(t for _, t in _textes(RACINE / "pages" / "essence.py"))
    assert f"« {periode.NOMS_AFFICHES['Tout']} »" in textes
    assert "« Tout »" not in textes


def _textes(fichier: Path) -> list[tuple[int, str]]:
    """Les chaines du fichier, docstrings exclues."""
    arbre = ast.parse(fichier.read_text(encoding="utf-8"))
    docs = set()
    for n in ast.walk(arbre):
        corps = getattr(n, "body", None)
        if (isinstance(n, (ast.Module, ast.FunctionDef, ast.ClassDef))
                and corps and isinstance(corps[0], ast.Expr)
                and isinstance(corps[0].value, ast.Constant)):
            docs.add(id(corps[0].value))
    return [(n.lineno, n.value) for n in ast.walk(arbre)
            if isinstance(n, ast.Constant) and isinstance(n.value, str)
            and id(n) not in docs]


FICHIERS_AFFICHES = ["fenetre.py", "recharges.py", "saisie.py",
                     *(f"pages/{p.name}" for p in
                       sorted((RACINE / "pages").glob("*.py")))]


@pytest.mark.parametrize("nom", FICHIERS_AFFICHES)
def test_ni_trois_points_ni_fleche_ni_ok(nom):
    fautes = [(ligne, texte[:60]) for ligne, texte in _textes(RACINE / nom)
              if "..." in texte or " -> " in texte
              or texte.startswith("OK : ")]
    assert fautes == []


def test_jeu_de_demo_accentue(tmp_path):
    recharges.ecrire_jeu_demo(tmp_path)
    texte = ((tmp_path / "recharges.json").read_text(encoding="utf-8")
             + (tmp_path / "tarifs.json").read_text(encoding="utf-8"))
    assert "Demo " not in texte and "demonstration" not in texte
    assert "Démo" in texte and "démonstration" in texte


def test_sauvegarde_en_ligne_et_non_cloud():
    textes = [t for _, t in _textes(RACINE / "recharges.py")]
    assert not any("cloud" in t for t in textes)
