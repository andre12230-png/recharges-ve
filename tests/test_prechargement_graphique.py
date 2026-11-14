"""Ouverture plus rapide des Statistiques (14-11-2026).

La premiere ouverture des Statistiques chargeait matplotlib (environ 2
secondes dans l'exe). Desormais la fenetre le charge en arriere-plan juste
apres son ouverture : au clic, il est deja pret.

    py -m pytest tests/test_prechargement_graphique.py
"""

from __future__ import annotations

import sys

import fenetre as module_fenetre


def test_la_fenetre_lance_le_prechargement(qapp, monkeypatch):
    """La fenetre demande le prechargement peu apres son ouverture."""
    from PySide6.QtTest import QTest
    appels = []
    monkeypatch.setattr(module_fenetre, "precharger_graphique",
                        lambda: appels.append(1))
    # Les fenetres laissees par les tests precedents ont aussi leur
    # minuterie : on la laisse passer, puis on ne compte que la notre.
    QTest.qWait(module_fenetre.DELAI_PRECHARGEMENT_MS + 300)
    appels.clear()
    f = module_fenetre.FenetrePrincipale(accueil=False)
    try:
        # Laisser passer le delai du prechargement (une seconde).
        QTest.qWait(module_fenetre.DELAI_PRECHARGEMENT_MS + 300)
        assert appels == [1]
    finally:
        f.deleteLater()


def test_le_prechargement_importe_le_graphique(monkeypatch):
    """Le fil d'arriere-plan importe bien graphique.py (et donc
    matplotlib), sans rien afficher."""
    monkeypatch.setattr(module_fenetre, "_prechargement_lance", False)
    fil = module_fenetre.precharger_graphique()
    assert fil is not None
    fil.join(timeout=60)
    assert not fil.is_alive()
    assert "graphique" in sys.modules


def test_le_prechargement_ne_se_lance_qu_une_fois(monkeypatch):
    """Plusieurs fenetres (les tests en ouvrent des dizaines) : un seul
    fil."""
    monkeypatch.setattr(module_fenetre, "_prechargement_lance", False)
    premier = module_fenetre.precharger_graphique()
    premier.join(timeout=60)
    assert module_fenetre.precharger_graphique() is None
