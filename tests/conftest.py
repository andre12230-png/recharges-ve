"""Isolation des donnees pendant les tests — a lire avant d'ajouter un test.

recharges.py fixe l'emplacement des donnees UNE SEULE FOIS, a son import :
la variable d'environnement RECHARGES_DATA_DIR doit donc etre posee avant
que le moindre module du projet ne soit importe. test_recharges.py le
faisait deja en tete de fichier, mais cette protection tombait des qu'un
autre fichier de test importait le projet en premier — ce qui est arrive le
07/09/2026 avec test_menu.py, qui importe app.py : les tests ont alors ecrit
dans les vraies donnees et les ont videes.

conftest.py est le seul endroit que pytest charge avant tous les fichiers de
test, quel que soit leur ordre alphabetique. La redirection est ici, une fois
pour toutes.

`py -m unittest discover -s tests` ne lit PAS ce fichier : chaque fichier de
test qui importe le projet garde donc sa propre redirection en tete, et
test_isolation.py verifie qu'elle a bien pris.
"""

import os
import shutil
import tempfile
from pathlib import Path

import pytest

DOSSIER = Path(tempfile.mkdtemp(prefix="recharges_conftest_"))
os.environ["RECHARGES_DATA_DIR"] = str(DOSSIER)
# Meme chose pour les preferences (theme Clair / Sombre, 12/10/2026) : un
# fichier jetable, jamais le registre de l'utilisateur. app.py les lit des
# son import (test_menu.py l'importe).
os.environ["RECHARGES_PREFERENCES"] = str(DOSSIER / "preferences.ini")

# Tests de la version PySide6 (migration en cours) : les fenetres Qt sont
# construites « hors ecran », sans rien afficher. A poser avant la creation
# de l'application Qt, donc ici.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


@pytest.fixture(scope="session")
def qapp():
    """L'application Qt, une seule pour toute la suite, avec le theme de
    l'application (Fusion, palette claire, feuille de style)."""
    from PySide6.QtWidgets import QApplication
    from theme_qt import appliquer_theme
    application = QApplication.instance() or QApplication([])
    appliquer_theme(application)
    return application


@pytest.fixture(autouse=True)
def pas_de_message_au_demarrage(monkeypatch):
    """Dans les tests, la fenetre PySide6 n'accueille pas et ne previent pas
    au demarrage : ces messages attendraient un clic que personne ne
    donnera, et la suite resterait bloquee. (Le dossier de donnees des tests
    est neuf : l'accueil du premier demarrage s'ouvrirait a chaque fois.)"""
    try:
        import fenetre
    except Exception:
        return
    monkeypatch.setattr(fenetre.FenetrePrincipale, "_avertir_etat_donnees",
                        lambda self: None)


def pytest_sessionfinish(session, exitstatus):
    """Fin de suite : ferme les fenetres Qt restantes, puis efface le
    dossier temporaire.

    Les fenetres d'abord : detruites par Python dans le desordre a la sortie,
    elles font planter l'interpreteur (erreur 0xC0000374, vue dans le
    Photovoltaique) alors que tous les tests sont passes."""
    try:
        from PySide6.QtCore import QCoreApplication, QEvent
        from PySide6.QtWidgets import QApplication
        application = QApplication.instance()
        if application is not None:
            for fenetre in application.topLevelWidgets():
                fenetre.deleteLater()
            QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
    except Exception:
        pass
    shutil.rmtree(DOSSIER, ignore_errors=True)


@pytest.fixture(autouse=True)
def aucune_boite_modale(monkeypatch):
    """Une boite de confirmation (composants.confirmer) ouverte pendant un
    test attendrait un clic que personne ne donnera : la suite resterait
    bloquee (vu le 03/10/2026). Elle fait echouer le test a la place, en
    disant pourquoi. Les tests repondent en remplacant `confirmer`."""
    from PySide6.QtWidgets import QMessageBox

    def refuser(self, *a, **k):
        raise AssertionError(
            f"Boîte « {self.windowTitle()} » ouverte pendant un test : "
            "remplacer `confirmer` par une réponse simulée.")
    monkeypatch.setattr(QMessageBox, "exec", refuser)
