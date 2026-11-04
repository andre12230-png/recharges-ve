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
from formats import fmt_date_fr, fmt_kwh
from recharges import (FormatCsvInconnu, ImportAnnule, apercu_csv,
                       dossier_donnees, importer_csv_maison,
                       retenir_correspondance)
from theme_qt import ALERTE_TEXTE, VERT


def _accord(n: int, singulier: str, pluriel: str) -> str:
    """« 1 doublon », « 2 doublons » : 0 et 1 au singulier."""
    return f"{n} {singulier if n <= 1 else pluriel}"


def texte_resultat(res: dict) -> tuple[str, bool]:
    """Le compte rendu d'un import, et s'il faut alerter (lignes non
    reconnues, donc PAS enregistrees : l'alerte ne doit pas se noyer dans un
    message de succes)."""
    # Chaque nombre accorde son mot : « 1 doublon », « 2 doublons » (0 et 1
    # au singulier). « ✓ » comme les autres succès de l'appli, et non
    # « OK » (contrôle du français du 26/10/2026).
    texte = ("✓ " + _accord(res["ajoutes"], "ajoutée", "ajoutées") + ", "
             + _accord(res["remplaces"], "saisie manuelle remplacée",
                       "saisies manuelles remplacées") + ", "
             + _accord(res["doublons"], "doublon", "doublons") + ", "
             + _accord(res["zero_kwh"], "ignorée", "ignorées"))
    if res.get("ignorees_par_choix"):
        texte += ", " + _accord(res["ignorees_par_choix"],
                                "ignorée à votre demande",
                                "ignorées à votre demande")
    if res.get("parasites"):
        texte += ", " + _accord(res["parasites"],
                                "branchement sans recharge écarté",
                                "branchements sans recharge écartés")
    texte += ", " + _accord(res["total_lus"], "lue", "lues")
    if not res["ajoutes"] and not res["remplaces"]:
        texte += "   (rien de nouveau : le fichier n'a pas été modifié)"
    # Les saisies manuelles remplacées, une par ligne : l'utilisateur doit
    # pouvoir le vérifier (audits du 26/10/2026, #5). Depuis l'audit du
    # 04/11/2026 (T1), seules les saisies qui recouvrent la session, ou
    # celles qu'il a choisies, sont remplacées ; la règle reste une règle,
    # d'où « à vérifier ».
    remplacements = res.get("remplacements") or []
    if remplacements:
        texte += ("\nSaisies à la main remplacées par une session de la "
                  "borne (à vérifier) :")
        for rp in remplacements:
            texte += (f"\n  • {fmt_date_fr(rp['avant_date'])}, "
                      f"{fmt_kwh(rp['avant_kwh'])} → "
                      f"{fmt_date_fr(rp['apres_date'])}, "
                      f"{fmt_kwh(rp['apres_kwh'])}")
    # Lignes proches d'une saisie à la main, gardées en double faute de
    # réponse (import sans question) : à vérifier dans l'Historique.
    a_verifier = res.get("a_verifier") or []
    if a_verifier:
        texte += ("\nÀ vérifier : ces recharges du fichier ressemblent à une "
                  "saisie à la main ; les deux sont gardées. Supprimez le "
                  "doublon dans l'Historique s'il s'agit de la même charge :")
        for cas in a_verifier:
            texte += (f"\n  • {fmt_date_fr(cas['fichier']['date'])}, "
                      f"{fmt_kwh(cas['fichier']['kwh'])}")
    alerte = bool(a_verifier)
    if res.get("non_reconnues"):
        alerte = True
        # Accorde avec le nombre (29/09/2026 ; c'etait « ligne(s) »)
        n = res["non_reconnues"]
        texte += ("\nATTENTION : 1 ligne non reconnue, donc pas enregistrée."
                  if n == 1 else
                  f"\nATTENTION : {n} lignes non reconnues, donc pas "
                  "enregistrées.")
    # Les sessions au-delà de ce que la batterie peut absorber (des Wh lus
    # comme des kWh, par exemple) : mises de côté par le moteur, listées
    # ici une par ligne, en orange (décision d'André du 03/11/2026).
    trop = res.get("trop_kwh") or []
    if trop:
        alerte = True
        if len(trop) == 1:
            texte += ("\nATTENTION : 1 session mise de côté, donc pas "
                      "enregistrée : son énergie dépasse ce que la batterie "
                      "peut absorber en une charge.")
        else:
            texte += (f"\nATTENTION : {len(trop)} sessions mises de côté, "
                      "donc pas enregistrées : leur énergie dépasse ce que la "
                      "batterie peut absorber en une charge.")
        texte += (" Vérifiez la capacité de la batterie dans Paramètres ; si "
                  "une recharge est réelle, saisissez-la à la main :")
        for t in trop:
            texte += f"\n  • {fmt_date_fr(t['date'])}, {fmt_kwh(t['kwh'])}"
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
        "Une charge déjà importée n'est pas ajoutée une seconde fois. Une "
        "charge saisie à la main est remplacée par la ligne du fichier "
        "quand leurs heures se recouvrent ; en cas de doute, l'application "
        "vous montre les deux et vous demande quoi faire avant d'enregistrer. "
        "Si "
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
    """Importe sans demander de confirmation : une charge deja importee
    n'est pas ajoutee une seconde fois, reimporter est donc sans danger.
    Une ligne proche d'une saisie a la main sans en etre surement la meme
    ouvre la fenetre « Recharges a verifier », AVANT toute ecriture (audit
    du 04/11/2026, T1).

    Un fichier d'un modele inconnu ouvre la fenetre « Quelles colonnes ? »
    (28/09/2026) ; le choix est retenu apres un import reussi."""
    from dialogue_rapprochements import demander_rapprochements

    def decider(cas):
        return demander_rapprochements(fenetre, cas)

    try:
        try:
            bilan = importer_csv_maison(chemin, decider=decider)
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
            bilan = importer_csv_maison(chemin, correspondance=correspondance,
                                        decider=decider)
            retenir_correspondance(apercu, correspondance)
        texte, alerte = texte_resultat(bilan)
    except ImportAnnule:
        texte, alerte = ("Import annulé : rien n'a été enregistré. Le fichier "
                         "est intact, vous pourrez l'importer plus tard."), True
    except Exception as e:      # noqa: BLE001
        # Un fichier illisible peut echouer de bien des facons (encodage,
        # colonnes, droits) : le message du moteur est deja en francais, et
        # il dit de NE PAS supprimer le fichier. Il doit s'afficher.
        texte, alerte = f"Erreur : {erreur_en_clair(e)}", True
    resultat.setText(texte)
    resultat.setStyleSheet(f"color: {ALERTE_TEXTE if alerte else VERT};")
    resultat.show()
    fenetre._maj_bilan()
