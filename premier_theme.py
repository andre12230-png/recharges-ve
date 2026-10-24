"""Choix Clair / Sombre au tout premier lancement (16/10/2026).

Demande de l'auteur : le mode sombre ne se trouvait que dans Parametres ›
Apparence, ou un nouvel utilisateur ne le cherchait pas. Au premier
lancement, avant d'ouvrir la fenetre, l'application demande donc « Clair ou
Sombre ? ».

La question vient AVANT la fenetre parce que les pages prennent leurs
couleurs au moment ou elles sont importees (voir theme_qt.py) : posee
apres, elle obligerait a redemarrer pour voir le choix.

Elle n'est posee qu'une fois, et seulement a un vrai nouvel utilisateur :
- aucun theme encore choisi dans les preferences ;
- ni recharges.json ni tarifs.json dans le dossier des donnees. Quelqu'un qui
  met a jour une ancienne version a deja ses donnees : on ne le derange pas,
  il garde le clair et peut changer dans Parametres.

Ce module n'importe ni la fenetre ni les pages : il peut tourner avant elles.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import QMessageBox

import theme_qt


def est_premier_lancement(reglages, dossier: Path) -> bool:
    """Vrai si aucun theme n'a encore ete choisi ET si le dossier des
    donnees ne contient ni recharges ni tarifs. Une preference abimee
    (revenue en liste) compte comme absente."""
    valeur = reglages.value(theme_qt.CLE_THEME)
    if isinstance(valeur, str) and valeur in theme_qt.THEMES:
        return False
    dossier = Path(dossier)
    return not ((dossier / "recharges.json").exists()
                or (dossier / "tarifs.json").exists())


def boite_du_choix(parent=None):
    """La petite fenetre de la question, et ses deux boutons.
    Rend (boite, bouton_clair, bouton_sombre)."""
    boite = QMessageBox(parent)
    boite.setWindowTitle("Recharges VE — Apparence")
    boite.setIcon(QMessageBox.Icon.Question)
    boite.setText(
        "Comment préférez-vous voir l'application ?\n\n"
        "• Clair : fond crème, texte noir.\n"
        "• Sombre : fond brun très foncé, texte clair, plus reposant le "
        "soir.\n\n"
        "Vous pourrez changer d'avis à tout moment dans "
        # Espaces insecables autour de « › » : le chemin ne se coupe pas.
        "Paramètres › Apparence.")
    clair = boite.addButton("Clair", QMessageBox.ButtonRole.AcceptRole)
    sombre = boite.addButton("Sombre", QMessageBox.ButtonRole.AcceptRole)
    # Entree ou la croix de fermeture : le clair, theme de reference.
    boite.setDefaultButton(clair)
    boite.setEscapeButton(clair)
    return boite, clair, sombre


def demander_a_l_ecran() -> str:
    """Montre la question et rend « clair » ou « sombre ».

    Appelee avant la fenetre : l'application Qt n'existe pas encore, on la
    cree ici (fenetre.main la reprend ensuite), habillee du theme clair
    pour que la question ait deja l'allure de l'application."""
    import sys
    from PySide6.QtWidgets import QApplication
    application = QApplication.instance() or QApplication(sys.argv)
    theme_qt.installer_traduction_qt(application)
    theme_qt.appliquer_theme(application)
    boite, _clair, sombre = boite_du_choix()
    boite.exec()
    return "sombre" if boite.clickedButton() is sombre else "clair"


def demander_au_premier_lancement(reglages=None, dossier=None,
                                  demander=demander_a_l_ecran) -> str | None:
    """Pose la question si c'est le premier lancement, et retient la
    reponse dans les preferences (registre de Windows), pour ne plus la
    reposer. Rend le theme choisi, ou None si rien n'a ete demande.

    `reglages`, `dossier` et `demander` : remplaçables par les tests."""
    if reglages is None:
        reglages = theme_qt.preferences()
    if dossier is None:
        from recharges import dossier_donnees
        dossier = dossier_donnees()
    if not est_premier_lancement(reglages, dossier):
        return None
    nom = demander()
    reglages.setValue(theme_qt.CLE_THEME, nom)
    reglages.sync()
    return nom
