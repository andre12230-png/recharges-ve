"""Tarifs (version PySide6) : la grille tarifaire, et les frais des cartes
de recharge (28/09/2026). Les reglages de la voiture et de la borne sont
dans la page Parametres depuis le 28/09/2026.

Reprise de l'ancienne page vues/tarifs.py. Les textes de chaque periode sont composes a part,
sans interface (periode_du_tarif, detail_du_tarif) : ils se testent sans
fenetre.
"""

from __future__ import annotations

from datetime import datetime

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (QComboBox, QDialog, QFrame, QHBoxLayout,
                               QLabel, QLineEdit, QMessageBox, QPushButton,
                               QVBoxLayout, QWidget)

from composants import carte, confirmer, paragraphe
from constantes import CARTES
from dialogue_km_frais import DialogueFrais
from dialogue_tarif import DialogueTarif
from erreurs import erreur_en_clair
from recharges import (TYPES_FRAIS_CARTE, ajouter_frais_carte,
                       charger_frais_cartes, charger_tarifs, recalculer_tout,
                       recharges_du_tarif, supprimer_frais_carte,
                       supprimer_tarif)
from formats import fmt_date_fr, fmt_eur, fmt_prix_kwh
from saisie import ErreurSaisie, lire_frais_carte
import suivi_saisie
from theme_qt import ROUGE, VERT


# ---------- textes (sans interface) ----------

def periode_du_tarif(t: dict) -> str:
    """« du 01/02/2026 au 31/07/2026 », ou « depuis le 01/08/2026 » pour
    le tarif en cours : dates a la francaise, et non au format du fichier
    (« du … au … » de la charte, audit du 03/10/2026)."""
    debut = fmt_date_fr(t.get("debut", "?"))[:10]
    if not t.get("fin"):
        return f"depuis le {debut}"
    return f"du {debut} au {fmt_date_fr(t['fin'])[:10]}"


def detail_du_tarif(t: dict) -> str:
    abonnement = f"Abonnement {fmt_eur(t.get('abonnement_mensuel', 0))}/mois"
    if t.get("type") == "simple":
        return (f"{abonnement}  ·  {fmt_prix_kwh(t.get('prix_kwh', 0))} "
                "(prix unique)")
    # « de 22:00 à 06:00 », et non « 22:00-06:00 » (charte : pas de « - »
    # entre deux mots ; audit du 08/10/2026).
    plages = " et ".join(f"de {a} à {b}" for a, b in t.get("plages_hc", []))
    return (f"{abonnement}  ·  HP {fmt_prix_kwh(t.get('prix_hp', 0))}  ·  "
            f"HC {fmt_prix_kwh(t.get('prix_hc', 0))}  ·  Plages HC : {plages}")


def ordre_d_affichage(tarifs: list[dict]) -> list[dict]:
    """Les periodes de la plus recente a la plus ancienne."""
    return sorted(tarifs, key=lambda t: t.get("debut", ""), reverse=True)


def question_suppression(t: dict, n_recharges: int) -> str:
    texte = (f"Supprimer la période « {t.get('nom')} » "
             f"({periode_du_tarif(t)}) ?")
    if n_recharges:
        texte += (f"\n\nATTENTION : {n_recharges} recharges ont été calculées "
                  "avec ce tarif. Elles garderont leur montant actuel, mais un "
                  "recalcul les refusera faute de tarif pour leur date.")
    return texte


# ---------- affichage ----------

def construire(fenetre) -> QWidget:
    tarifs = charger_tarifs()
    page = QWidget()
    colonne = QVBoxLayout(page)
    colonne.setContentsMargins(0, 0, 0, 0)
    colonne.setSpacing(12)

    cadre, corps = carte("Grille tarifaire")
    corps.addWidget(paragraphe(
        "Modifiez un tarif ou ajoutez une période quand vos prix changent, "
        "puis recalculez les coûts."))
    ligne = QHBoxLayout()
    ajouter = QPushButton("＋  Ajouter une période tarifaire")
    ajouter.setObjectName("BoutonEnregistrer")
    ajouter.clicked.connect(lambda: ouvrir_tarif(fenetre, None))
    ligne.addWidget(ajouter)
    page.bouton_ajouter = ajouter
    # Sans aucune periode, il n'y a rien a recalculer : le bouton ne ferait
    # que semer le doute chez qui decouvre la page.
    if tarifs:
        recalculer = QPushButton("Recalculer tous les coûts")
        recalculer.clicked.connect(lambda: recalculer_les_couts(fenetre))
        ligne.addWidget(recalculer)
        page.bouton_recalculer = recalculer
    ligne.addStretch(1)
    corps.addSpacing(4)
    corps.addLayout(ligne)
    colonne.addWidget(cadre)

    cadre, corps = carte("Périodes tarifaires")
    page.periodes = []
    # Premier demarrage : la liste est vide, et c'est ici que l'accueil a
    # conduit le nouvel utilisateur. On lui dit quoi faire.
    if not tarifs:
        corps.addWidget(paragraphe(
            "Aucune période pour l'instant. Cliquez sur « ＋ Ajouter une "
            "période tarifaire » ci-dessus et saisissez le prix du kWh de "
            "votre contrat d'électricité : sans lui, aucun coût ne peut être "
            "calculé.", "Discret"))
    # La plus recente en tete, l'actuelle d'abord (demande de l'auteur,
    # 25/09/2026). L'ordre du fichier, lui, ne change pas : du plus ancien
    # au plus recent, c'est celui que le calcul des couts parcourt.
    for t in ordre_d_affichage(tarifs):
        bloc = _bloc_tarif(fenetre, t)
        corps.addWidget(bloc)
        page.periodes.append(bloc)
    colonne.addWidget(cadre)

    colonne.addWidget(_carte_frais(fenetre, page))
    colonne.addStretch(1)
    return page


def _bloc_tarif(fenetre, t: dict) -> QFrame:
    """Une periode : nom, dates, boutons, puis le detail des prix."""
    bloc = QFrame()
    bloc.setObjectName("BlocTarif")
    dedans = QVBoxLayout(bloc)
    dedans.setContentsMargins(10, 8, 10, 8)
    dedans.setSpacing(2)
    haut = QHBoxLayout()
    nom = QLabel(t.get("nom", "?"))
    nom.setObjectName("NomRepartition")
    haut.addWidget(nom)
    haut.addStretch(1)
    dates = QLabel(periode_du_tarif(t))
    dates.setObjectName("Discret")
    haut.addWidget(dates)
    haut.addSpacing(12)
    modifier = QPushButton("Modifier…")
    modifier.clicked.connect(lambda: ouvrir_tarif(fenetre, t))
    supprimer = QPushButton("Supprimer")
    supprimer.clicked.connect(lambda: supprimer_la_periode(fenetre, t))
    haut.addWidget(modifier)
    haut.addWidget(supprimer)
    dedans.addLayout(haut)
    dedans.addWidget(paragraphe(detail_du_tarif(t), "Discret"))
    bloc.bouton_modifier, bloc.bouton_supprimer = modifier, supprimer
    return bloc


# ---------- frais des cartes de recharge (28/09/2026) ----------

# Les cartes proposees dans la liste : celles de la saisie d'une recharge,
# sauf « Direct (CB) » (pas une carte) et « Autre » (on tape le nom).
CARTES_A_FRAIS = [c for c in CARTES if c not in ("Direct (CB)", "Autre")]


def ligne_frais(f: dict) -> str:
    """« 10/03/2025 · Chargemap · achat unique · 20,00 € »."""
    debut = fmt_date_fr(f["date"])[:10]
    if f["type"] == "unique":
        return (f"{debut}  ·  {f['carte']}  ·  achat unique  ·  "
                f"{fmt_eur(f['montant'])}")
    quand = (f"du {debut} au {fmt_date_fr(f['fin'])[:10]}" if f.get("fin")
             else f"depuis le {debut}")
    annuel = f["type"] == "annuel"
    return (f"{quand}  ·  {f['carte']}  ·  abonnement "
            f"{'annuel' if annuel else 'mensuel'}  ·  "
            f"{fmt_eur(f['montant'])} par {'an' if annuel else 'mois'}")


def _carte_frais(fenetre, page) -> QWidget:
    """La liste des frais de cartes, chacun avec son bouton Supprimer, puis
    le formulaire pour en ajouter. Une seule ligne de message sous le
    formulaire, comme pour les releves du Kilometrage."""
    cadre, corps = carte("Frais de vos cartes de recharge")
    corps.addWidget(paragraphe(
        "L'achat d'une carte, ou l'abonnement (mensuel ou annuel) à un "
        "réseau de bornes. "
        "Ces frais sont comptés à part, comme l'abonnement de la maison : "
        "jamais dans le coût des recharges ni dans le prix du kWh.",
        "Discret"))

    page.lignes_frais = []
    # Les plus recents en haut (10/10/2026), comme les periodes tarifaires.
    for f in sorted(charger_frais_cartes(), key=lambda f: f.get("date", ""),
                    reverse=True):
        ligne = QWidget()
        rangee = QHBoxLayout(ligne)
        rangee.setContentsMargins(0, 0, 0, 0)
        rangee.addWidget(QLabel(ligne_frais(f)), 1)
        # « Modifier » corrige sur place (analyse du 16/10/2026) : avant,
        # il fallait supprimer puis ressaisir les frais.
        modifier = QPushButton("Modifier…")
        modifier.setToolTip("Corriger ces frais")
        modifier.clicked.connect(
            lambda _=False, ff=f: modifier_les_frais(fenetre, ff))
        rangee.addWidget(modifier)
        bouton = QPushButton("Supprimer")
        bouton.setToolTip("Supprimer ces frais")
        bouton.clicked.connect(
            lambda _=False, ff=f: supprimer_les_frais(fenetre, ff))
        rangee.addWidget(bouton)
        ligne.bouton = bouton
        ligne.bouton_modifier = modifier
        corps.addWidget(ligne)
        page.lignes_frais.append(ligne)

    formulaire = QWidget()
    formulaire.setObjectName("Formulaire")      # le style des cases de saisie
    dedans = QVBoxLayout(formulaire)
    dedans.setContentsMargins(0, 6, 0, 0)
    dedans.setSpacing(8)

    def libelle(texte):
        e = QLabel(texte)
        e.setObjectName("LibelleChamp")
        return e

    # La carte : dans la liste, ou tapee a la main si elle n'y est pas.
    choix_carte = QComboBox()
    choix_carte.setEditable(True)
    choix_carte.addItems(CARTES_A_FRAIS)
    choix_carte.setCurrentIndex(-1)
    choix_carte.lineEdit().setPlaceholderText("choisissez ou tapez")
    choix_carte.setFixedWidth(180)
    choix_type = QComboBox()
    for cle, texte in TYPES_FRAIS_CARTE.items():
        choix_type.addItem(texte, cle)
    cases = {"carte": choix_carte, "type": choix_type}
    for nom, largeur, invite in (("date", 110, "jj/mm/aaaa"),
                                 ("fin", 110, "facultative"),
                                 ("montant", 80, "")):
        case = QLineEdit()
        case.setFixedWidth(largeur)
        case.setPlaceholderText(invite)
        cases[nom] = case

    ligne1 = QHBoxLayout()
    ligne1.setSpacing(6)
    ligne1.addWidget(libelle("Carte :"))
    ligne1.addWidget(choix_carte)
    ligne1.addSpacing(18)
    ligne1.addWidget(libelle("Type :"))
    ligne1.addWidget(choix_type)
    ligne1.addStretch(1)
    dedans.addLayout(ligne1)

    ligne2 = QHBoxLayout()
    ligne2.setSpacing(6)
    etiquette_date = libelle("Achetée le :")
    ligne2.addWidget(etiquette_date)
    ligne2.addWidget(cases["date"])
    ligne2.addSpacing(12)
    etiquette_fin = libelle("Fin :")
    ligne2.addWidget(etiquette_fin)
    ligne2.addWidget(cases["fin"])
    ligne2.addSpacing(12)
    ligne2.addWidget(libelle("Montant :"))
    ligne2.addWidget(cases["montant"])
    etiquette_euros = libelle("€")
    ligne2.addWidget(etiquette_euros)
    ligne2.addSpacing(18)
    bouton = QPushButton("Ajouter ces frais")
    bouton.setObjectName("BoutonEnregistrer")
    ligne2.addWidget(bouton)
    ligne2.addStretch(1)
    dedans.addLayout(ligne2)

    def selon_le_type() -> None:
        """La date de fin n'a de sens que pour un abonnement ; le montant
        est alors celui d'un mois ou d'une annee."""
        type_ = choix_type.currentData()
        abonnement = type_ != "unique"
        cases["fin"].setEnabled(abonnement)
        etiquette_fin.setEnabled(abonnement)
        etiquette_date.setText("Début :" if abonnement else "Achetée le :")
        etiquette_euros.setText({"mensuel": "€ par mois",
                                 "annuel": "€ par an"}.get(type_, "€"))
    choix_type.currentIndexChanged.connect(lambda _: selon_le_type())
    selon_le_type()

    message = QLabel(fenetre.message_frais)
    message.setWordWrap(True)
    message.setTextInteractionFlags(Qt.TextSelectableByMouse)
    message.setStyleSheet(f"color: {VERT};")
    message.setVisible(bool(fenetre.message_frais))  # cachee tant que vide
    fenetre.message_frais = ""              # affiche une fois
    dedans.addWidget(message)
    corps.addWidget(formulaire)

    page.cases_frais, page.message_frais = cases, message
    suivi_saisie.nommer(cases)          # reportees si la page se reconstruit
    page.bouton_frais = bouton
    ajouter = lambda: ajouter_les_frais(fenetre, cases, message)  # noqa: E731
    bouton.clicked.connect(ajouter)
    for nom in ("date", "fin", "montant"):
        cases[nom].returnPressed.connect(ajouter)
    return cadre


def ajouter_les_frais(fenetre, cases: dict, message: QLabel) -> None:
    def erreur(nom: str, texte: str) -> None:
        message.setText(texte)
        message.setStyleSheet(f"color: {ROUGE};")
        message.show()
        cases[nom].setFocus()

    try:
        frais = lire_frais_carte({
            "carte": cases["carte"].currentText(),
            "type": cases["type"].currentData(),
            "date": cases["date"].text(), "fin": cases["fin"].text(),
            "montant": cases["montant"].text()})
    except ErreurSaisie as e:
        erreur(e.champ, e.message)
        return
    try:
        ajoute = ajouter_frais_carte(frais)
    except (ValueError, OSError) as e:
        erreur("montant", erreur_en_clair(e))
        return
    # La page se reconstruit (la liste change) et affiche alors ce message,
    # garde sur la fenetre en attendant.
    fenetre.message_frais = f"Frais enregistrés : {ligne_frais(ajoute)}"
    # Le formulaire vient d'etre enregistre : il repart vide.
    _recharger(fenetre, garder_saisie=False)


def modifier_les_frais(fenetre, f: dict) -> None:
    dialogue = DialogueFrais(fenetre, f, CARTES_A_FRAIS)
    if dialogue.exec() != QDialog.Accepted:
        return
    fenetre.message_frais = "Frais corrigés."
    _recharger(fenetre)


def supprimer_les_frais(fenetre, f: dict) -> None:
    if not confirmer(
            fenetre, "Supprimer des frais",
            "Supprimer ces frais ?" + chr(10) * 2 + ligne_frais(f),
            action="Supprimer ces frais", garder="Garder", danger=True):
        return
    try:
        supprimer_frais_carte(f.get("id", ""))
    except (ValueError, OSError) as e:
        QMessageBox.critical(fenetre, "Suppression impossible", erreur_en_clair(e))
        return
    _recharger(fenetre)


def _recharger(fenetre, garder_saisie: bool = True) -> None:
    """La page se reconstruit un instant plus tard : on ne la detruit pas
    pendant qu'un de ses boutons traite son clic.

    Des frais en cours de saisie restent dans le formulaire, sauf apres
    l'enregistrement de ce formulaire lui-meme (`garder_saisie=False`)."""
    QTimer.singleShot(0, fenetre, lambda: fenetre.recharger_page(
        "tarifs", garder_saisie=garder_saisie))


def ouvrir_tarif(fenetre, tarif: dict | None) -> None:
    fenetre_tarif = DialogueTarif(fenetre, tarif)
    if fenetre_tarif.exec() != QDialog.Accepted:
        return
    if fenetre_tarif.avertissements:
        QMessageBox.warning(
            fenetre, "Grille tarifaire",
            "Le tarif est enregistré, mais :\n\n- "
            + "\n- ".join(fenetre_tarif.avertissements))
    # Sans recalcul, les recharges deja enregistrees gardent les anciens
    # montants : l'affichage serait incoherent avec la grille.
    # Le recalcul reecrit toutes les recharges maison : « Plus tard » par
    # defaut, comme toute reecriture en masse (charte, audit du 03/10/2026 ;
    # c'etait « Oui »).
    if confirmer(
            fenetre, "Recalculer les coûts ?",
            "La grille tarifaire a changé.\n\nRecalculer maintenant le coût "
            "de toutes les recharges maison ?\n\n"
            "Sans cela, les recharges déjà enregistrées garderont leurs "
            "anciens montants. Le bouton « Recalculer tous les coûts » de "
            "cette page le fait aussi plus tard.",
            action="Recalculer les coûts", garder="Plus tard"):
        recalculer_les_couts(fenetre)
    _recharger(fenetre)


def message_recalcul(n: int, laissees: list[str]) -> str:
    """Le compte rendu du recalcul, y compris ce qu'il n'a pas pu faire."""
    # Accorde avec le nombre (29/09/2026 ; c'etait « recharge(s) laissée(s) »)
    texte = ("1 recharge recalculée." if n == 1
             else f"{n} recharges recalculées.")
    if laissees:
        dates = ", ".join(
            datetime.fromisoformat(d).strftime("%d/%m/%Y") for d in laissees[:5])
        if len(laissees) > 5:
            dates += "…"
        if len(laissees) == 1:
            debut = "1 recharge laissée avec son ancien montant"
            raison = "aucun tarif ne couvre sa date, ou son"
        else:
            debut = (f"{len(laissees)} recharges laissées avec leur ancien "
                     "montant")
            raison = "aucun tarif ne couvre leur date, ou leur"
        texte += (
            f"\n\n{debut} ({dates}) : {raison} heure de fin manque alors "
            "que le tarif distingue les heures pleines et creuses.")
    return texte


def recalculer_les_couts(fenetre) -> None:
    try:
        n, laissees = recalculer_tout()
    except (ValueError, OSError) as e:
        # Fichier impossible a ecrire, grille tarifaire illisible.
        QMessageBox.critical(fenetre, "Recalcul impossible", erreur_en_clair(e))
        return
    if laissees:
        QMessageBox.warning(fenetre, "Recalcul", message_recalcul(n, laissees))
    else:
        QMessageBox.information(fenetre, "Recalcul", message_recalcul(n, []))
    fenetre._maj_bilan()


def supprimer_la_periode(fenetre, t: dict) -> None:
    n = recharges_du_tarif(t.get("id", ""))
    # « Garder » par defaut : les recharges calculees avec ce tarif ne
    # pourraient plus etre recalculees.
    if not confirmer(
            fenetre, "Supprimer un tarif", question_suppression(t, n),
            action="Supprimer la période", garder="Garder", danger=True):
        return
    try:
        ok = supprimer_tarif(t.get("id", ""))
    except (ValueError, OSError) as e:
        QMessageBox.critical(fenetre, "Suppression impossible", erreur_en_clair(e))
        return
    if not ok:
        QMessageBox.critical(
            fenetre, "Suppression impossible",
            "Ce tarif est introuvable : rien n'a été supprimé.")
        return
    _recharger(fenetre)
