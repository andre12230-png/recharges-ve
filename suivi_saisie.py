"""Repere les cases ou l'utilisateur a tape ce qu'il n'a pas encore enregistre.

Seule une frappe au clavier (ou un choix dans une liste) compte : ce que
l'application ecrit elle-meme dans une case -- la date du jour, un reglage
relu du fichier, un formulaire vide apres enregistrement -- ne declenche rien,
car Qt n'emet `textEdited` et `activated` que pour l'utilisateur.

La fenetre s'en sert pour ne pas detruire une page qui porte une saisie en
cours, pour poser la question a la fermeture, et pour que Ctrl+S ne laisse
pas croire que le formulaire affiche est enregistre.
"""

from __future__ import annotations

from PySide6.QtWidgets import QComboBox, QLineEdit, QWidget

# Propriete Qt posee sur chaque case modifiee a la main.
_MARQUE = "saisie_non_enregistree"
# Propriete Qt qui porte le nom d'une case de formulaire (voir `nommer`).
_CLE = "nom_de_saisie"


def suivre(page: QWidget) -> None:
    """Branche le reperage sur toutes les cases et listes de `page`."""
    for case in page.findChildren(QLineEdit):
        case.textEdited.connect(
            lambda _texte, c=case: c.setProperty(_MARQUE, True))
    for liste in page.findChildren(QComboBox):
        liste.activated.connect(
            lambda _rang, x=liste: x.setProperty(_MARQUE, True))


def a_des_saisies(page: QWidget | None) -> bool:
    """Une case de `page` porte-t-elle une valeur tapee et non enregistree ?"""
    if page is None:
        return False
    return any(w.property(_MARQUE) for w in page.findChildren(QWidget))


def nommer(cases: dict[str, QWidget]) -> None:
    """Donne a chaque case d'un formulaire son nom, pour qu'une saisie en
    cours puisse etre reportee dans la page reconstruite (voir `relever`).

    Le nom est une propriete Qt a part, pas le nom d'objet : celui-ci sert
    deja au style de certains elements."""
    for nom, case in cases.items():
        case.setProperty(_CLE, nom)


def _cases_nommees(page: QWidget) -> list[QWidget]:
    return [w for w in page.findChildren(QWidget) if w.property(_CLE)]


def _est_marquee(case: QWidget) -> bool:
    # Une liste modifiable porte la marque sur sa case de texte interne.
    return bool(case.property(_MARQUE)) or any(
        w.property(_MARQUE) for w in case.findChildren(QWidget))


def relever(page: QWidget | None) -> dict[str, object]:
    """Ce que l'utilisateur a tape dans les cases nommees de `page` et pas
    encore enregistre, nom par nom. Les cases restees telles que
    l'application les a remplies ne sont pas relevees."""
    if page is None:
        return {}
    releve = {}
    for case in _cases_nommees(page):
        if not _est_marquee(case):
            continue
        if isinstance(case, QComboBox):
            releve[case.property(_CLE)] = (
                case.currentText() if case.isEditable()
                else case.currentIndex())
        elif isinstance(case, QLineEdit):
            releve[case.property(_CLE)] = case.text()
    return releve


def remettre(page: QWidget, releve: dict[str, object]) -> None:
    """Remet dans la page reconstruite les saisies relevees avant, et les
    marque toujours comme non enregistrees."""
    for case in _cases_nommees(page):
        nom = case.property(_CLE)
        if nom not in releve:
            continue
        valeur = releve[nom]
        if isinstance(case, QComboBox):
            if case.isEditable():
                case.setCurrentText(str(valeur))
            else:
                case.setCurrentIndex(int(valeur))
        elif isinstance(case, QLineEdit):
            case.setText(str(valeur))
        case.setProperty(_MARQUE, True)


def marquer_enregistre(*widgets: QWidget) -> None:
    """A appeler apres un enregistrement reussi, avec les cases enregistrees
    (ou le cadre qui les contient) : elles ne sont plus « en attente »."""
    for widget in widgets:
        for w in (widget, *widget.findChildren(QWidget)):
            w.setProperty(_MARQUE, False)
