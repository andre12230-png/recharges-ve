"""La restauration d'une sauvegarde anterieure (version PySide6).

Reprise de l'ancienne page vues/restaurer.py. Les sauvegardes existaient deja, mais il
fallait aller copier un fichier a la main dans le dossier backups pour s'en
servir : un dispositif de securite invisible, donc inutilisable au moment
precis ou l'on en a besoin.
"""

from __future__ import annotations

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QMessageBox, QPushButton, QVBoxLayout, QWidget

from composants import carte, confirmer, paragraphe, tableau
from erreurs import erreur_en_clair
from formats import fmt_nb_recharges
from recharges import charger_donnees, lister_backups, restaurer_backup
from theme_qt import ALERTE_TEXTE


ENTETES = ["Date", "Contenu", "Taille", "Genre"]


def cellules_sauvegarde(fiche: dict) -> tuple[str, ...]:
    """Une sauvegarde de la liste. Un tableau, et non plus une ligne en
    caracteres de largeur fixe (audit de design du 03/10/2026)."""
    quand = fiche["date"].strftime("%d/%m/%Y à %H:%M")
    contenu = ("illisible" if fiche["n_recharges"] is None
               else fmt_nb_recharges(fiche["n_recharges"]))
    genre = "du jour" if fiche["quotidienne"] else ""
    return (quand, contenu, f"{fiche['taille'] / 1024:.0f} Ko", genre)


def recharges_actuelles() -> str:
    """« 259 recharges », ou « fichier illisible ».

    Cette page est la seule issue quand le fichier est abime et qu'aucune
    sauvegarde n'a pu le reparer au demarrage : elle ne doit donc pas
    dependre de sa lecture. Jusqu'a la v2.0.0, elle affichait « CETTE PAGE
    N'A PAS PU S'AFFICHER » precisement dans ce cas."""
    try:
        return fmt_nb_recharges(len(charger_donnees()['recharges']))
    except Exception:           # noqa: BLE001 — tout echec de lecture
        return "fichier illisible"


def construire(fenetre) -> QWidget:
    page = QWidget()
    colonne = QVBoxLayout(page)
    colonne.setContentsMargins(0, 0, 0, 0)
    colonne.setSpacing(12)

    cadre, corps = carte("Avant de restaurer")
    corps.addWidget(paragraphe(
        "Restaurer remplace vos recharges actuelles par celles de la "
        "sauvegarde choisie. L'état actuel est mis de côté au passage : vous "
        "pourrez revenir en arrière en restaurant la sauvegarde la plus "
        "récente."))
    colonne.addWidget(cadre)

    fiches = lister_backups()
    # Le titre dit ce que montre la carte ; le nombre actuel de recharges,
    # qui coiffait la liste, passe en premiere ligne (audit du 03/10/2026).
    cadre, corps = carte("Sauvegardes disponibles")
    corps.addWidget(paragraphe(
        f"Vos données actuelles : {recharges_actuelles()}.", "Discret"))
    page.boutons = []
    if not fiches:
        # Un etat vide dit pourquoi, et quand la premiere apparaitra.
        corps.addWidget(paragraphe(
            "Aucune sauvegarde pour l'instant. L'application en fait une "
            "toute seule avant chaque modification de vos recharges (ajout, "
            "import, suppression) : la première apparaîtra ici dès votre "
            "prochaine saisie.", "Discret"))
    else:
        boutons, couleurs = [], []
        for fiche in fiches:
            if fiche["n_recharges"] is None:
                # Une sauvegarde abimee se signale, et ne se propose pas.
                boutons.append(None)
                couleurs.append(ALERTE_TEXTE)
                continue
            bouton = QPushButton("Restaurer")
            bouton.setToolTip("Remettre en service cette sauvegarde")
            bouton.clicked.connect(
                lambda _=False, f=fiche: _restaurer(fenetre, f))
            boutons.append(bouton)
            couleurs.append(None)
            page.boutons.append(bouton)
        page.tableau = tableau(
            ENTETES, [cellules_sauvegarde(f) for f in fiches],
            a_droite=(2,), boutons=boutons, couleurs=couleurs)
        corps.addWidget(page.tableau)
    colonne.addWidget(cadre)
    colonne.addStretch(1)
    return page


def _restaurer(fenetre, fiche: dict) -> None:
    """Confirme, puis remet en service la sauvegarde choisie."""
    quand = fiche["date"].strftime("%d/%m/%Y à %H:%M")
    # « Garder mes données » par defaut : un appui sur Entree par reflexe ne
    # remplace rien (audit du 03/10/2026 ; Qt mettait « Oui »).
    if not confirmer(
            fenetre, "Restaurer une sauvegarde",
            f"Remplacer vos données actuelles ({recharges_actuelles()}) par "
            f"la sauvegarde du {quand}, qui en contient "
            f"{fiche['n_recharges']} ?\n\n"
            "L'état actuel sera mis de côté et restera restaurable.",
            action="Restaurer cette sauvegarde",
            garder="Garder mes données", danger=True):
        return
    try:
        n = restaurer_backup(fiche["chemin"])
    except Exception as e:
        QMessageBox.critical(fenetre, "Restauration", erreur_en_clair(e))
        return
    QMessageBox.information(
        fenetre, "Restauration",
        f"{fmt_nb_recharges(n)} "
        f"{'restaurées' if n > 1 else 'restaurée'} depuis la sauvegarde du "
        f"{quand}.")
    # Reconstruire la page un instant plus tard : le bouton clique en fait
    # partie, et il ne doit pas etre detruit pendant qu'il traite son clic.
    QTimer.singleShot(0, fenetre, lambda: fenetre.afficher_vue("restaurer"))
