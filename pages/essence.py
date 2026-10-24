"""Essence ou électrique ? (28/09/2026) : la comparaison avec une voiture
essence, avec son propre bouton dans le bandeau (rubrique Analyse).

En haut, le selecteur « Tout / année » des Statistiques : la page s'ouvre
sur « Tout » (l'etat global). Sur « Tout », un tableau donne aussi chaque
annee. Le calcul est celui de recharges.comparer_essence_periode, la carte
celle de la page Kilometrage (kilometrage._carte_essence) : un seul calcul,
deux endroits pour le voir. La page dit aussi ce qui manque quand rien ne
s'affiche, et mene aux Parametres pour changer la voiture ou le prix du
litre.
"""

from __future__ import annotations

import re

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QHBoxLayout, QPushButton, QVBoxLayout, QWidget

from composants import carte, paragraphe, tableau, texte_a_lire
from formats import fmt_eur, fmt_nombre
from pages.kilometrage import _carte_essence
from pages.periode import BarrePeriode
from recharges import (charger_config, charger_donnees, charger_releves_km,
                       comparer_essence_periode)


ENTETES_ANNEES = ["Année", "Distance", "Essence consommée", "Prix du litre",
                  "Coût en essence", "Coût en électricité", "Économie"]


def cellules_annee(a: dict) -> tuple[str, ...]:
    """Une ligne du tableau « Année par année ». Un vrai tableau, et non
    plus une ligne en caracteres de largeur fixe (audit du 03/10/2026)."""
    return (str(a["annee"]),
            f"{fmt_nombre(a['km'])}\xa0km",
            f"{fmt_nombre(a['litres'])}\xa0L",
            f"{fmt_nombre(a['prix'], 2)}\xa0€/L",
            fmt_eur(a["cout_essence"]),
            fmt_eur(a["cout_electrique"]),
            fmt_eur(a["economie"]))


def construire(fenetre) -> QWidget:
    page = QWidget()
    colonne = QVBoxLayout(page)
    colonne.setContentsMargins(0, 0, 0, 0)
    colonne.setSpacing(12)

    toutes = charger_donnees()["recharges"]
    periode = fenetre.filtre_periode_essence
    barre = BarrePeriode(toutes, periode, annuel=True)
    barre.periode_changee.connect(
        lambda v: fenetre.changer_periode("filtre_periode_essence", v))
    colonne.addWidget(barre)
    page.barre = barre

    config = charger_config()
    reglee = config["conso_essence"] > 0 and config["prix_essence"] > 0
    c = comparer_essence_periode(periode, config, charger_releves_km(), toutes)
    page.lignes_annees = []
    if not reglee:
        colonne.addWidget(_carte_essence(None))     # l'invitation
    elif periode != "Tout" and not re.fullmatch(r"\d{4}", periode):
        cadre, corps = carte("Comparaison avec une voiture essence")
        corps.addWidget(paragraphe(
            "La comparaison se fait sur « Tout » ou sur une année : "
            "choisissez-en une ci-dessus.", "Discret"))
        colonne.addWidget(cadre)
    elif c is None:
        # La voiture essence est saisie : ce qui manque, ce sont les
        # kilometres, qui ne se connaissent qu'entre deux releves.
        cadre, corps = carte("Comparaison avec une voiture essence")
        corps.addWidget(paragraphe(
            ("Il faut au moins deux relevés du compteur, et des recharges "
             "entre eux" if periode == "Tout" else
             f"Aucun relevé du compteur n'encadre {periode}")
            + " : sans eux, l'application ne connaît pas vos kilomètres. "
            "Saisissez-les dans la page « 🚗 Kilométrage ».", "Discret"))
        colonne.addWidget(cadre)
    else:
        colonne.addWidget(_carte_essence(c))
        if periode == "Tout" and len(c["par_annee"]) > 1:
            cadre, corps = carte("Année par année")
            # L'annee la plus recente en haut (10/10/2026).
            page.lignes_annees = [cellules_annee(a)
                                  for a in reversed(c["par_annee"])]
            corps.addWidget(tableau(ENTETES_ANNEES, page.lignes_annees,
                                    a_droite=(1, 2, 3, 4, 5, 6)))
            colonne.addWidget(cadre)

    cadre, corps = carte("Comment c'est calculé")
    corps.addWidget(texte_a_lire(
        "Les kilomètres viennent de vos relevés du compteur. Quand deux "
        "relevés encadrent plusieurs années, les kilomètres entre eux sont "
        "partagés au prorata du temps passé dans chaque année. Côté essence : ces kilomètres, à la consommation "
        "indiquée et au prix du litre de chaque année. Côté électricité : ce "
        "qu'ont coûté vos recharges sur la même période, sans l'abonnement ni "
        "les frais de cartes."))
    ligne = QHBoxLayout()
    bouton = QPushButton("⚙️ Changer la voiture ou le prix du litre")
    # La page se reconstruit un instant plus tard : on ne la detruit pas
    # pendant que son bouton traite son clic.
    bouton.clicked.connect(lambda: QTimer.singleShot(
        0, fenetre, lambda: fenetre.afficher_vue("parametres")))
    ligne.addWidget(bouton)
    ligne.addStretch(1)
    corps.addSpacing(4)
    corps.addLayout(ligne)
    colonne.addWidget(cadre)
    page.bouton_parametres = bouton

    colonne.addStretch(1)
    return page
