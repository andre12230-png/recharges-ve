"""Importer un CSV (version PySide6) : l'historique exporte par la borne de
recharge (wallbox).

Reprise de l'ancienne page vues/import_csv.py. La page explique ce qu'est ce fichier et quoi
faire sans lui, met le bouton de choix du fichier en avant, et ne montre la
liste des CSV du dossier des donnees que s'il y en a.
"""

from __future__ import annotations

from PySide6.QtWidgets import (QDialog, QFileDialog, QHBoxLayout, QLabel,
                               QPushButton, QVBoxLayout, QWidget)

from composants import carte, paragraphe, texte_a_lire, texte_fixe
from erreurs import erreur_en_clair
from recharges import (FormatCsvInconnu, apercu_csv, dossier_donnees,
                       importer_csv_maison, retenir_correspondance)
from theme_qt import ALERTE_TEXTE, VERT


def texte_resultat(res: dict) -> tuple[str, bool]:
    """Le compte rendu d'un import, et s'il faut alerter (lignes non
    reconnues, donc PAS enregistrees : l'alerte ne doit pas se noyer dans un
    message de succes)."""
    texte = (f"OK : {res['ajoutes']} ajoutées, {res['remplaces']} saisies "
             f"manuelles remplacées, {res['doublons']} doublons, "
             f"{res['zero_kwh']} ignorées")
    if res.get("parasites"):
        texte += f", {res['parasites']} branchements sans recharge écartés"
    texte += f", {res['total_lus']} lues"
    if not res["ajoutes"] and not res["remplaces"]:
        texte += "   (rien de nouveau : le fichier n'a pas été modifié)"
    alerte = bool(res.get("non_reconnues"))
    if alerte:
        # Accorde avec le nombre (29/09/2026 ; c'etait « ligne(s) »)
        n = res["non_reconnues"]
        texte += ("\nATTENTION : 1 ligne non reconnue, donc pas enregistrée."
                  if n == 1 else
                  f"\nATTENTION : {n} lignes non reconnues, donc pas "
                  "enregistrées.")
    return texte, alerte


def construire(fenetre) -> QWidget:
    page = QWidget()
    colonne = QVBoxLayout(page)
    colonne.setContentsMargins(0, 0, 0, 0)
    colonne.setSpacing(12)
    resultat = QLabel("")
    resultat.setWordWrap(True)
    resultat.hide()

    cadre, corps = carte("Comment ça marche")
    corps.addWidget(texte_a_lire(
        "Beaucoup de bornes de recharge à domicile (wallbox) savent exporter "
        "l'historique de leurs charges dans un fichier CSV, depuis leur "
        "application ou leur site : cherchez « exporter » ou « historique ». "
        "Importez ce fichier ici : chaque charge est ajoutée avec ses heures "
        "exactes et son énergie, et son coût est calculé d'après vos tarifs. "
        "Une charge déjà enregistrée n'est jamais comptée deux fois. Si "
        "l'application ne reconnaît pas le fichier, elle vous demande quelle "
        "colonne contient quoi, et s'en souvient pour la fois suivante."))
    corps.addWidget(paragraphe(
        "Votre borne n'exporte rien ? Ce n'est pas grave : saisissez vos "
        "recharges dans « Ajouter une recharge ».", "Discret"))
    bouton = QPushButton("📂 Choisir le fichier de ma borne…")
    bouton.setObjectName("BoutonEnregistrer")
    bouton.clicked.connect(lambda: _choisir(fenetre, resultat))
    ligne = QHBoxLayout()
    ligne.addWidget(bouton)
    ligne.addStretch(1)
    corps.addSpacing(4)
    corps.addLayout(ligne)
    colonne.addWidget(cadre)
    page.bouton_choisir = bouton                # pour les tests

    # Les CSV deposes dans le dossier des donnees sont proposes directement.
    # Sans aucun, la carte n'aurait rien a dire : elle n'apparait pas.
    page.boutons_fichiers = []
    csvs = sorted(dossier_donnees().glob("*.csv"))
    if csvs:
        cadre, corps = carte("Fichiers déjà dans le dossier de vos données")
        for chemin in csvs:
            ligne = QHBoxLayout()
            ligne.addWidget(texte_fixe(chemin.name), 1)
            importer = QPushButton("Importer")
            importer.clicked.connect(
                lambda _=False, p=str(chemin): importer_fichier(
                    fenetre, p, resultat))
            ligne.addWidget(importer)
            corps.addLayout(ligne)
            page.boutons_fichiers.append(importer)
        colonne.addWidget(cadre)

    colonne.addWidget(resultat)
    page.resultat = resultat
    colonne.addStretch(1)
    return page


def _choisir(fenetre, resultat: QLabel) -> None:
    chemin, _filtre = QFileDialog.getOpenFileName(
        fenetre, "Choisissez le fichier exporté par votre borne", "",
        "Fichier CSV (*.csv);;Tous les fichiers (*.*)")
    if chemin:
        importer_fichier(fenetre, chemin, resultat)


def demander_colonnes(parent, apercu: dict) -> dict | None:
    """La fenetre « Quelles colonnes ? » ; None si l'utilisateur annule."""
    from dialogue_colonnes import DialogueColonnes
    fenetre_colonnes = DialogueColonnes(parent, apercu)
    if fenetre_colonnes.exec() != QDialog.Accepted:
        return None
    return fenetre_colonnes.correspondance()


def importer_fichier(fenetre, chemin: str, resultat: QLabel) -> None:
    """Importe sans demander de confirmation : une charge deja enregistree
    n'est jamais comptee deux fois, reimporter est donc sans danger.

    Un fichier d'un modele inconnu ouvre la fenetre « Quelles colonnes ? »
    (28/09/2026) ; le choix est retenu apres un import reussi."""
    try:
        try:
            bilan = importer_csv_maison(chemin)
        except FormatCsvInconnu:
            apercu = apercu_csv(chemin)
            correspondance = demander_colonnes(fenetre, apercu)
            if correspondance is None:
                resultat.setText("Import annulé : rien n'a été enregistré. Le "
                                 "fichier est intact, vous pourrez "
                                 "l'importer plus tard.")
                resultat.setStyleSheet(f"color: {ALERTE_TEXTE};")
                resultat.show()
                return
            bilan = importer_csv_maison(chemin, correspondance=correspondance)
            retenir_correspondance(apercu, correspondance)
        texte, alerte = texte_resultat(bilan)
    except Exception as e:      # noqa: BLE001
        # Un fichier illisible peut echouer de bien des facons (encodage,
        # colonnes, droits) : le message du moteur est deja en francais, et
        # il dit de NE PAS supprimer le fichier. Il doit s'afficher.
        texte, alerte = f"Erreur : {erreur_en_clair(e)}", True
    resultat.setText(texte)
    resultat.setStyleSheet(f"color: {ALERTE_TEXTE if alerte else VERT};")
    resultat.show()
    fenetre._maj_bilan()
