"""Recherche de l'Historique : elle trouve ce qui est affiche (08/10/2026).

La recherche comparait le texte tape a des nombres ecrits a l'anglaise
(« 30.24 ») : un montant tape comme on le lit (« 30,24 ») ne trouvait
rien, « Extérieur » avec son accent non plus (seul « exterieur » marchait),
ni un nom de mois (« juillet »), pourtant annonce.

    py -m pytest tests/test_recherche_historique.py
"""

from __future__ import annotations

import pytest

from filtres import filtrer_par_recherche

MAISON = {"date": "2026-07-12T23:00", "lieu": "maison", "kwh": 30.24,
          "cout_eur": 4.54, "prix_kwh": 0.1501, "tarif_nom": "Mon contrat"}
DEHORS = {"date": "2026-08-20T14:00", "lieu": "exterieur", "kwh": 1234.5,
          "cout_eur": 39.55, "prix_kwh": 0.59, "operateur": "Ionity",
          "lieu_detail": "Aire du Lac"}
TOUTES = [MAISON, DEHORS]


@pytest.mark.parametrize("texte, attendues", [
    # Les montants tels qu'ils s'affichent, a la virgule
    ("30,24", [MAISON]), ("4,54", [MAISON]), ("39,55", [DEHORS]),
    ("0,5900", [DEHORS]), ("1234,50", [DEHORS]),
    # ... avec l'espace des milliers, ordinaire ou insecable
    ("1 234,50", [DEHORS]), ("1\xa0234,50", [DEHORS]),
    # ... et toujours a l'anglaise, pour qui a l'habitude
    ("30.24", [MAISON]), ("39.55", [DEHORS]),
    # Le lieu tel qu'il s'affiche, accent ou pas
    ("Extérieur", [DEHORS]), ("extérieur", [DEHORS]), ("exterieur", [DEHORS]),
    ("Maison", [MAISON]),
    # Le mois en toutes lettres
    ("juillet", [MAISON]), ("août 2026", [DEHORS]), ("aout", [DEHORS]),
    # Ce qui marchait deja
    ("ionity", [DEHORS]), ("aire du lac", [DEHORS]), ("mon contrat", [MAISON]),
    ("12/07/2026", [MAISON]), ("/2026", TOUTES), ("", TOUTES),
    # Et ce qui ne doit rien trouver
    ("31,00", []), ("septembre", []),
])
def test_la_recherche_trouve_ce_qui_est_affiche(texte, attendues):
    assert filtrer_par_recherche(TOUTES, texte) == attendues
