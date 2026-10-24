"""Confirmations : jamais « Oui » par defaut devant une action sans retour.

Audit de design du 03/10/2026 : la question de la page Restaurer laissait Qt
choisir le bouton par defaut — c'est alors « Oui » : un appui sur Entree par
reflexe remplacait les recharges par une sauvegarde.

Regle (charte des applis, « Ce qu'on dit a l'utilisateur ») : bouton par
defaut sur « Garder » / « Annuler », boutons qui disent l'action. Meme
modele que Pecule (widgets.confirmer).
"""

import ast
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent


def _fichiers_du_projet():
    for fichier in RACINE.rglob("*.py"):
        morceaux = fichier.relative_to(RACINE).parts
        if morceaux[0] in ("tests", "build", "dist", "distribution"):
            continue
        yield fichier


def test_aucune_question_ne_laisse_qt_choisir_le_bouton_par_defaut():
    """Chaque QMessageBox.question() nomme son bouton par defaut (5e
    argument) : un choix fait expres, jamais celui de Qt."""
    fautives = []
    for fichier in _fichiers_du_projet():
        arbre = ast.parse(fichier.read_text(encoding="utf-8"))
        for noeud in ast.walk(arbre):
            if (isinstance(noeud, ast.Call)
                    and isinstance(noeud.func, ast.Attribute)
                    and noeud.func.attr == "question"
                    and isinstance(noeud.func.value, ast.Name)
                    and noeud.func.value.id == "QMessageBox"):
                explicite = (len(noeud.args) >= 5 or any(
                    k.arg == "defaultButton" for k in noeud.keywords))
                if not explicite:
                    fautives.append(
                        f"{fichier.relative_to(RACINE)}:{noeud.lineno}")
    assert not fautives, ("Bouton par défaut laissé à Qt (« Oui ») : "
                          + ", ".join(fautives))


def test_boite_de_confirmation_garde_par_defaut(qapp):
    """Entree et Echap choisissent tous deux « Garder » ; le bouton d'action
    dit ce qu'il fait ; une suppression montre l'icone d'avertissement."""
    from PySide6.QtWidgets import QMessageBox
    from composants import boite_de_confirmation

    boite, bouton_action = boite_de_confirmation(
        None, "Supprimer le relevé", "Supprimer le relevé du 01/10/2026 ?",
        action="Supprimer le relevé", garder="Garder", danger=True)
    assert bouton_action.text() == "Supprimer le relevé"
    assert boite.defaultButton().text() == "Garder"
    assert boite.escapeButton() is boite.defaultButton()
    assert boite.icon() == QMessageBox.Warning
    boite.deleteLater()


def test_plus_de_boutons_oui_non():
    """Les boutons disent l'action (« Supprimer le relevé », « Garder »),
    au lieu d'un « Oui » qui oblige a relire la question (audit de design du
    03/10/2026). Toutes les questions passent par composants.confirmer()."""
    fautives = []
    for fichier in _fichiers_du_projet():
        arbre = ast.parse(fichier.read_text(encoding="utf-8"))
        for noeud in ast.walk(arbre):
            if (isinstance(noeud, ast.Attribute)
                    and noeud.attr in ("Yes", "No")
                    and isinstance(noeud.value, ast.Name)
                    and noeud.value.id == "QMessageBox"):
                fautives.append(f"{fichier.relative_to(RACINE)}:{noeud.lineno}")
    assert not fautives, "Boutons Oui / Non : " + ", ".join(fautives)


def test_l_action_peut_etre_proposee_par_defaut(qapp):
    """Pour une question qui ne detruit rien (fermer le tarif precedent,
    avertissement doux), le bouton d'action peut etre le choix par defaut."""
    from composants import boite_de_confirmation
    boite, bouton_action = boite_de_confirmation(
        None, "Fermer le tarif précédent ?", "…", action="Le terminer",
        garder="Le laisser ouvert", action_par_defaut=True)
    assert boite.defaultButton() is bouton_action
    assert boite.escapeButton().text() == "Le laisser ouvert"
    boite.deleteLater()
