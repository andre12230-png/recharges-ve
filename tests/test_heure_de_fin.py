"""L'heure de fin tapee sans jour : le jour du debut, pas aujourd'hui.

Bug trouve le 25/09/2026 (v1.31.0) : avec la case du jour de fin vide,
l'heure seule etait placee AUJOURD'HUI. Saisie le 25 d'une charge commencee
le 20 a 22h30, « 6h » donnait le 25 a 6h : plus de cinq jours de charge, et
une repartition heures pleines / creuses fausse. Cela ne se voyait pas en
saisissant le lendemain matin, quand aujourd'hui EST le lendemain du debut.

La page Ajouter et la fenetre « Modifier » doivent toutes deux passer par
saisie.placer_heure_de_fin. Le dernier test lit le code de saisie.py ; le
comportement complet est eprouve par test_saisie_recharge.py et
test_saisie_modification.py.

    py -m pytest tests/test_heure_de_fin.py
"""

import ast
import os
import sys
import tempfile
from datetime import datetime
from pathlib import Path

os.environ.setdefault("RECHARGES_DATA_DIR",
                      tempfile.mkdtemp(prefix="recharges_heure_fin_"))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from saisie import placer_heure_de_fin  # noqa: E402

RACINE = Path(__file__).resolve().parent.parent


def test_le_jour_du_debut_meme_saisi_des_jours_plus_tard():
    """L'heure lue dans la case vaut pour aujourd'hui (le 25) ; elle doit
    se replacer apres le debut (le 20 a 22h30)."""
    debut = datetime(2026, 9, 20, 22, 30)
    lue = datetime(2026, 9, 25, 6, 0)
    assert placer_heure_de_fin(lue, debut) == datetime(2026, 9, 21, 6, 0)


def test_plus_tard_le_meme_jour():
    debut = datetime(2026, 9, 20, 8, 0)
    lue = datetime(2026, 9, 25, 11, 0)
    assert placer_heure_de_fin(lue, debut) == datetime(2026, 9, 20, 11, 0)


def test_deux_heures_identiques_ne_sont_pas_decalees():
    """Elles restent une erreur a signaler (« La fin doit être après le
    début. »), pas une charge de 24 heures."""
    debut = datetime(2026, 9, 20, 22, 30)
    lue = datetime(2026, 9, 25, 22, 30)
    assert placer_heure_de_fin(lue, debut) == debut


def _appels(fichier: str, fonction: str) -> set[str]:
    arbre = ast.parse((RACINE / fichier).read_text(encoding="utf-8"))
    for noeud in ast.walk(arbre):
        if isinstance(noeud, ast.FunctionDef) and noeud.name == fonction:
            return {ast.unparse(n.func) for n in ast.walk(noeud)
                    if isinstance(n, ast.Call)}
    raise AssertionError(f"{fonction} introuvable dans {fichier}")


def test_la_saisie_et_la_modification_s_en_servent():
    """Depuis la 2.0.0, les formulaires lisent leurs cases dans saisie.py :
    c'est la que la regle doit etre appliquee, pour la page Ajouter comme
    pour la fenetre « Modifier »."""
    assert "placer_heure_de_fin" in _appels("saisie.py",
                                            "lire_recharge_maison")
    assert "placer_heure_de_fin" in _appels("saisie.py",
                                            "lire_modification_recharge")
