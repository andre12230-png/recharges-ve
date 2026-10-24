"""Paramètres : les reglages de la voiture et de la borne, et le dossier des
donnees.

Page ajoutee le 28/09/2026, comme « ⚙️ Paramètres » dans Pecule et le
Photovoltaique. Les trois reglages etaient jusque-la en bas de la page
Tarifs, ou on ne pensait pas a les chercher ; ils restent enregistres au
meme endroit (tarifs.json), rien ne change dans les donnees.
"""

from __future__ import annotations

from datetime import datetime

from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices, QGuiApplication
from PySide6.QtWidgets import (QButtonGroup, QGridLayout, QHBoxLayout, QLabel,
                               QLineEdit, QMessageBox, QPushButton,
                               QRadioButton, QVBoxLayout, QWidget)

from composants import carte, paragraphe, texte_fixe
from erreurs import erreur_en_clair
from liens import PRIX_CARBURANTS_MOYENNES_URL, PRIX_CARBURANTS_STATIONS_URL
from recharges import (charger_config, charger_donnees, dossier_donnees,
                       enregistrer_config, enregistrer_reglages_borne,
                       valider_comparaison_essence,
                       valider_part_abonnement, valider_prix_annees,
                       valider_reglages)
from suivi_saisie import marquer_enregistre
import theme_qt
from theme_qt import ROUGE, VERT


def construire(fenetre) -> QWidget:
    page = QWidget()
    colonne = QVBoxLayout(page)
    colonne.setContentsMargins(0, 0, 0, 0)
    colonne.setSpacing(12)
    colonne.addWidget(_carte_reglages(page))
    colonne.addWidget(_carte_part_abonnement(page))
    colonne.addWidget(_carte_essence(page))
    colonne.addWidget(_carte_apparence(page))
    colonne.addWidget(_carte_dossier(page))
    colonne.addStretch(1)
    return page


def _carte_reglages(page) -> QWidget:
    """Les reglages de la voiture et de la borne : chacun sa case, et
    une phrase qui dit a quoi il sert. La saisie est controlee par
    valider_reglages() avant d'etre ecrite."""
    config = charger_config()
    cadre, corps = carte("Réglages de la voiture et de la borne")
    formulaire = QWidget()
    formulaire.setObjectName("Formulaire")      # le style des cases de saisie
    grille = QGridLayout(formulaire)
    grille.setContentsMargins(0, 0, 0, 0)
    grille.setHorizontalSpacing(10)
    grille.setColumnStretch(2, 1)
    capacite = config["capacite_batterie"]
    puissance = config["puissance_borne_kw"]
    cases = {}
    for rang, (cle, libelle, valeur, aide) in enumerate((
            ("capacite", "Capacité de la batterie (kWh)",
             f"{capacite:g}".replace(".", ",") if capacite else "",
             "Repère une énergie impossible à la saisie. Vide : inconnue."),
            ("rendement", "Rendement de charge (%)",
             f"{config['rendement_charge'] * 100:g}".replace(".", ","),
             "Part de l'énergie qui arrive à la batterie. 90 convient à la "
             "plupart des voitures."),
            ("correction", "Correction de l'horloge (min)",
             str(config["correction_csv_minutes"]),
             "Si les heures exportées par votre borne sont décalées : -60 "
             "recule d'une heure. Sinon 0. Les recharges déjà importées "
             "suivent le nouveau réglage."),
            # 23/10/2026 : la borne charge a pleine puissance des le debut,
            # puis s'arrete ; sans elle, l'energie est etalee sur toute la
            # duree ou la voiture reste branchee.
            ("puissance", "Puissance de charge de la borne (kW)",
             f"{puissance:g}".replace(".", ",") if puissance else "",
             "Compte l'énergie dès le début de la recharge, à pleine "
             "puissance, et non étalée jusqu'au débranchement. Vide : "
             "étalée. Change le coût de toutes les recharges."))):
        etiquette = QLabel(libelle)
        etiquette.setObjectName("LibelleChamp")
        grille.addWidget(etiquette, rang, 0)
        case = QLineEdit(valeur)
        case.setFixedWidth(90)
        grille.addWidget(case, rang, 1)
        grille.addWidget(paragraphe(aide, "Discret"), rang, 2)
        cases[cle] = case
    corps.addWidget(formulaire)

    ligne = QHBoxLayout()
    bouton = QPushButton("Enregistrer les réglages")
    message = QLabel("")
    message.setWordWrap(True)
    bouton.clicked.connect(lambda: enregistrer_reglages(cases, message))
    ligne.addWidget(bouton)
    ligne.addSpacing(12)
    ligne.addWidget(message, 1)
    corps.addSpacing(4)
    corps.addLayout(ligne)
    page.cases_reglages, page.message_reglages = cases, message
    page.bouton_reglages = bouton
    return cadre


def enregistrer_reglages(cases: dict, message: QLabel) -> None:
    try:
        reglages = valider_reglages(cases["capacite"].text(),
                                    cases["rendement"].text(),
                                    cases["correction"].text(),
                                    cases["puissance"].text())
        # Une correction d'horloge changee replace aussi les recharges deja
        # importees, et recalcule leur cout (23/10/2026).
        bilan = enregistrer_reglages_borne(reglages)
    except (ValueError, OSError) as e:
        message.setText(erreur_en_clair(e))
        message.setStyleSheet(f"color: {ROUGE};")
        return
    marquer_enregistre(*cases.values())
    texte = "✓ Réglages enregistrés."
    n = bilan["decalees"]
    if n:
        texte += (f" Heures de {n} recharge{'s' if n > 1 else ''} "
                  f"importée{'s' if n > 1 else ''} replacées selon la "
                  "nouvelle correction, coûts recalculés.")
    n = bilan.get("recalculees", 0)
    if n:
        texte += (f" Coût de {n} recharge{'s' if n > 1 else ''} à la maison "
                  "recalculé avec la puissance de la borne.")
    if bilan["laissees"]:
        texte += (f" Coût inchangé faute de tarif pour : "
                  f"{', '.join(bilan['laissees'])}.")
    message.setText(texte)
    message.setStyleSheet(f"color: {VERT};")


def _carte_part_abonnement(page) -> QWidget:
    """La part de l'abonnement de la maison attribuee a la voiture
    (10/10/2026), en pour cent. Le tableau de bord l'affiche sous
    l'abonnement, a part : le cout des recharges ne change pas."""
    pct = charger_config()["part_abonnement_voiture"]
    cadre, corps = carte("Abonnement de la maison")
    corps.addWidget(paragraphe(
        "L'abonnement est dû que la voiture recharge ou non : il n'entre "
        "pas dans le coût des recharges. Pour voir, à part, la part qui "
        "revient à la voiture, indiquez-la ici. Par exemple : les kWh "
        "rechargés à la maison divisés par tous les kWh achetés au réseau "
        "sur un an. Case vide : l'abonnement reste affiché en entier, "
        "sans la part de la voiture.", "Discret"))
    formulaire = QWidget()
    formulaire.setObjectName("Formulaire")      # le style des cases de saisie
    grille = QGridLayout(formulaire)
    grille.setContentsMargins(0, 0, 0, 0)
    grille.setHorizontalSpacing(10)
    grille.setColumnStretch(2, 1)
    etiquette = QLabel("Part liée à la voiture (%)")
    etiquette.setObjectName("LibelleChamp")
    grille.addWidget(etiquette, 0, 0)
    case = QLineEdit(f"{pct:g}".replace(".", ",") if pct else "")
    case.setFixedWidth(90)
    grille.addWidget(case, 0, 1)
    grille.addWidget(paragraphe("Entre 0 et 100.", "Discret"), 0, 2)
    corps.addWidget(formulaire)

    ligne = QHBoxLayout()
    bouton = QPushButton("Enregistrer la part")
    message = QLabel("")
    message.setWordWrap(True)
    bouton.clicked.connect(lambda: enregistrer_part(case, message))
    ligne.addWidget(bouton)
    ligne.addSpacing(12)
    ligne.addWidget(message, 1)
    corps.addSpacing(4)
    corps.addLayout(ligne)
    page.case_part, page.message_part = case, message
    page.bouton_part = bouton
    return cadre


def enregistrer_part(case: QLineEdit, message: QLabel) -> None:
    try:
        enregistrer_config(valider_part_abonnement(case.text()))
    except (ValueError, OSError) as e:
        message.setText(erreur_en_clair(e))
        message.setStyleSheet(f"color: {ROUGE};")
        return
    marquer_enregistre(case)
    message.setText("✓ Part enregistrée.")
    message.setStyleSheet(f"color: {VERT};")


def _carte_essence(page) -> QWidget:
    """La voiture essence de comparaison (28/09/2026) : sa consommation et
    le prix du litre, saisis par l'utilisateur. La comparaison s'affiche
    dans la page Kilometrage et sur le tableau de bord."""
    config = charger_config()
    cadre, corps = carte("Voiture essence de comparaison")
    corps.addWidget(paragraphe(
        "Pour comparer ce que vous coûte l'électricité à ce que vous aurait "
        "coûté une voiture essence comparable. Mettez à jour le prix du litre "
        "de temps en temps. Deux cases vides : pas de comparaison.",
        "Discret"))
    formulaire = QWidget()
    formulaire.setObjectName("Formulaire")      # le style des cases de saisie
    grille = QGridLayout(formulaire)
    grille.setContentsMargins(0, 0, 0, 0)
    grille.setHorizontalSpacing(10)
    grille.setColumnStretch(2, 1)
    cases = {}
    for rang, (cle, libelle, valeur, aide) in enumerate((
            ("conso", "Consommation (L/100\xa0km)", config["conso_essence"],
             "Celle d'une voiture essence de même taille que la vôtre."),
            ("prix", "Prix du litre (€)", config["prix_essence"],
             "Le prix affiché à la pompe."))):
        etiquette = QLabel(libelle)
        etiquette.setObjectName("LibelleChamp")
        grille.addWidget(etiquette, rang, 0)
        case = QLineEdit(f"{valeur:g}".replace(".", ",") if valeur else "")
        case.setFixedWidth(90)
        grille.addWidget(case, rang, 1)
        grille.addWidget(paragraphe(aide, "Discret"), rang, 2)
        cases[cle] = case
    corps.addWidget(formulaire)

    # Un prix du litre par annee, facultatif (28/09/2026) : l'essence ne
    # coutait pas le meme prix d'une annee a l'autre. Une case par annee,
    # de la premiere recharge a l'annee en cours.
    corps.addWidget(paragraphe(
        "Prix du litre par année (facultatif) : une année laissée vide prend "
        "le prix ci-dessus.", "Discret"))
    # L'annee la plus recente en premier (10/10/2026).
    annees = sorted({x.get("date", "")[:4]
                     for x in charger_donnees()["recharges"]
                     if x.get("date", "")[:4].isdigit()}
                    | {str(datetime.now().year)}, reverse=True)
    rangee_annees = QWidget()
    rangee_annees.setObjectName("Formulaire")
    grille_annees = QGridLayout(rangee_annees)
    grille_annees.setContentsMargins(0, 0, 0, 0)
    grille_annees.setHorizontalSpacing(6)
    cases_annees = {}
    for i, annee in enumerate(annees):
        etiquette = QLabel(annee)
        etiquette.setObjectName("LibelleChamp")
        valeur = config["prix_essence_annees"].get(annee)
        case = QLineEdit(f"{valeur:g}".replace(".", ",") if valeur else "")
        case.setFixedWidth(70)
        # Six annees par ligne : la carte reste lisible a 1000 px.
        grille_annees.addWidget(etiquette, i // 6, (i % 6) * 2)
        grille_annees.addWidget(case, i // 6, (i % 6) * 2 + 1)
        cases_annees[annee] = case
    grille_annees.setColumnStretch(12, 1)
    corps.addWidget(rangee_annees)

    message = QLabel("")
    message.setWordWrap(True)

    # Ou trouver le prix du litre (19/10/2026) : deux sites officiels,
    # ouverts dans le navigateur. L'application ne se connecte a rien.
    corps.addSpacing(4)
    corps.addWidget(paragraphe(
        "Où trouver le prix du litre ? Sur deux sites officiels de l'État : "
        "le prix dans les stations près de chez vous, et les moyennes "
        "nationales de chaque mois (pour le prix par année).", "Discret"))
    rangee_liens = QHBoxLayout()
    boutons_liens = {}
    for cle, texte, adresse in (
            ("stations", "🌐 Prix près de chez vous",
             PRIX_CARBURANTS_STATIONS_URL),
            ("moyennes", "🌐 Moyennes nationales",
             PRIX_CARBURANTS_MOYENNES_URL)):
        lien = QPushButton(texte)
        lien.setToolTip(adresse)
        lien.clicked.connect(
            lambda _=False, a=adresse: ouvrir_site(a, message))
        rangee_liens.addWidget(lien)
        boutons_liens[cle] = lien
    rangee_liens.addStretch(1)
    corps.addLayout(rangee_liens)

    ligne = QHBoxLayout()
    bouton = QPushButton("Enregistrer la comparaison")
    bouton.clicked.connect(
        lambda: enregistrer_essence(cases, cases_annees, message))
    ligne.addWidget(bouton)
    ligne.addSpacing(12)
    ligne.addWidget(message, 1)
    corps.addSpacing(4)
    corps.addLayout(ligne)
    page.cases_essence, page.message_essence = cases, message
    page.cases_prix_annees = cases_annees
    page.bouton_essence = bouton
    page.boutons_prix_carburant = boutons_liens
    return cadre


def ouvrir_site(adresse: str, message: QLabel) -> None:
    """Confie l'adresse au navigateur, comme « Mise à jour » et « Votre
    avis ». Si Windows n'a pas pu l'ouvrir, le dit et copie l'adresse pour
    qu'on la colle dans le navigateur (meme regle que fenetres_aide.py)."""
    if QDesktopServices.openUrl(QUrl(adresse)):
        message.setText("✓ Page ouverte dans votre navigateur.")
        message.setStyleSheet(f"color: {VERT};")
        return
    QGuiApplication.clipboard().setText(adresse)
    message.setText(
        "Windows n'a pas pu ouvrir votre navigateur. L'adresse est copiée : "
        "collez-la (Ctrl+V) dans la barre d'adresse de votre navigateur.\n"
        f"{adresse}")
    message.setStyleSheet(f"color: {ROUGE};")


def enregistrer_essence(cases: dict, cases_annees: dict,
                        message: QLabel) -> None:
    try:
        reglage = valider_comparaison_essence(cases["conso"].text(),
                                              cases["prix"].text())
        reglage["prix_essence_annees"] = valider_prix_annees(
            {annee: case.text() for annee, case in cases_annees.items()})
        # Le jour de l'enregistrement, pour le rappel du tableau de bord
        # quand le prix du litre vieillit (recharges.rappel_prix_essence).
        reglage["prix_essence_maj"] = datetime.now().date().isoformat()
        enregistrer_config(reglage)
    except (ValueError, OSError) as e:
        message.setText(erreur_en_clair(e))
        message.setStyleSheet(f"color: {ROUGE};")
        return
    marquer_enregistre(*cases.values(), *cases_annees.values())
    message.setText("✓ Comparaison enregistrée.")
    message.setStyleSheet(f"color: {VERT};")


def _carte_apparence(page) -> QWidget:
    """Le choix du theme, Clair ou Sombre (12/10/2026), comme dans le
    Photovoltaique.

    Garde dans les preferences de l'application (registre de Windows), pas
    dans tarifs.json : rien ne change dans les donnees. Il s'applique au
    prochain demarrage (voir theme_qt.py). Le reglage de Windows n'est
    jamais suivi : c'est l'application qui decide."""
    cadre, corps = carte("Apparence")
    corps.addWidget(paragraphe(
        "S'applique au prochain démarrage de l'application."))
    reglages = theme_qt.preferences()
    choisi = theme_qt.nom_du_theme(reglages)
    groupe = QButtonGroup(cadre)
    ligne = QHBoxLayout()
    ligne.setSpacing(24)
    page.choix_apparence = {}
    for nom, libelle in (("clair", "Clair"), ("sombre", "Sombre")):
        bouton = QRadioButton(libelle)
        bouton.setChecked(nom == choisi)
        # nom=nom : chaque bouton garde son propre nom.
        bouton.toggled.connect(
            lambda coche, nom=nom: coche and choisir_apparence(page, nom))
        groupe.addButton(bouton)
        ligne.addWidget(bouton)
        page.choix_apparence[nom] = bouton
    ligne.addStretch(1)
    corps.addLayout(ligne)
    page.groupe_apparence = groupe
    return cadre


def choisir_apparence(page, nom: str, reglages=None) -> None:
    """Enregistre le theme ; il s'applique au prochain demarrage.
    `reglages` : des preferences jetables, pour les tests."""
    reglages = reglages if reglages is not None else theme_qt.preferences()
    if nom == theme_qt.nom_du_theme(reglages):
        return
    reglages.setValue(theme_qt.CLE_THEME, nom)
    reglages.sync()
    QMessageBox.information(
        page, "Apparence",
        f"Le thème {nom} s'appliquera au prochain démarrage de "
        "l'application.\n\nFermez-la puis rouvrez-la pour le voir.")


def _ouvrir_dossier(bouton: QPushButton, dossier) -> None:
    """Ouvre le dossier des donnees dans l'Explorateur ; si Windows n'y
    arrive pas, le dit et redonne le chemin (second audit du 16/10/2026 :
    l'echec passait sans un mot)."""
    if QDesktopServices.openUrl(QUrl.fromLocalFile(str(dossier))):
        return
    QMessageBox.warning(
        bouton.window(), "Dossier non ouvert",
        "Windows n'a pas pu ouvrir le dossier de vos données. Ouvrez "
        f"l'Explorateur et allez à cet emplacement :\n\n{dossier}")


def _carte_dossier(page) -> QWidget:
    """Ou sont les donnees, et un bouton pour ouvrir ce dossier dans
    l'Explorateur : on y retrouve recharges.json et les sauvegardes sans
    chercher."""
    dossier = dossier_donnees()
    cadre, corps = carte("Emplacement de vos données")
    corps.addWidget(paragraphe(
        "Vos recharges (recharges.json), vos tarifs et réglages "
        "(tarifs.json) et leurs sauvegardes (sous-dossiers backups et "
        "Sauvegardes) sont dans ce dossier :"))
    chemin = texte_fixe(str(dossier))
    corps.addWidget(chemin)
    ligne = QHBoxLayout()
    bouton = QPushButton("📂 Ouvrir le dossier")
    bouton.clicked.connect(lambda: _ouvrir_dossier(bouton, dossier))
    ligne.addWidget(bouton)
    ligne.addStretch(1)
    corps.addSpacing(4)
    corps.addLayout(ligne)
    page.chemin_donnees, page.bouton_ouvrir_dossier = chemin, bouton
    return cadre
