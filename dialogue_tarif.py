"""La fenetre de tarif (version PySide6) : creer ou modifier une periode
tarifaire.

Reprise de l'ancienne fenetre dialogues.py (DialogueTarif), avec trois changements voulus
(25/09/2026) :
- chaque erreur s'ecrit SOUS la case fautive, comme dans les autres
  formulaires, au lieu d'une boite « Tarif refuse » ;
- passer de « Prix unique » a « Heures pleines / creuses » ne perd plus ce
  qui a ete tape : les deux blocs de prix existent, on montre l'un ou
  l'autre ;
- le tarif est verifie en entier AVANT de fermer le tarif precedent :
  l'ancienne fenetre pouvait fermer l'ancien tarif puis refuser le nouveau.

Les regles de lecture sont dans saisie.py (lire_tarif, lire_plages).
"""

from __future__ import annotations

from datetime import date, datetime, timedelta

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QButtonGroup, QComboBox, QDialog,
                               QDialogButtonBox, QHBoxLayout, QLabel,
                               QRadioButton, QScrollArea,
                               QVBoxLayout, QWidget)

from composants import confirmer
from constantes import PLAGES_COURANTES
from formulaire import Formulaire
from erreurs import erreur_en_clair
from recharges import (charger_tarifs, enregistrer_tarif,
                       tarif_ouvert_avant, valider_tarif)
from saisie import ErreurSaisie, lire_tarif


def date_fr(iso: str | None) -> str:
    """« 2026-08-01 » -> « 01/08/2026 » ; vide si rien ou illisible."""
    try:
        return datetime.fromisoformat(iso).strftime("%d/%m/%Y")
    except (TypeError, ValueError):
        return ""


def nombre_fr(valeur) -> str:
    """0.2345 -> « 0,2345 », recopie en entier (sans arrondi)."""
    if valeur in (None, ""):
        return ""
    return str(valeur).replace(".", ",")


def debut_propose() -> str:
    """Date de debut proposee pour le TOUT PREMIER tarif : le 1er janvier
    de l'annee en cours. Un nouvel utilisateur ne sait pas quoi mettre dans
    une case vide ; les periodes suivantes, elles, commencent a la date du
    changement de prix, qu'on ne peut pas deviner."""
    try:
        if charger_tarifs():
            return ""
    except (ValueError, OSError):
        return ""
    return f"01/01/{date.today().year}"


class DialogueTarif(QDialog):
    """Rend QDialog.Accepted si le tarif a ete enregistre ; les
    avertissements sur la grille (trou, chevauchement) sont alors dans
    `self.avertissements`."""

    def __init__(self, parent, tarif: dict | None):
        super().__init__(parent)
        self.tarif = tarif or {}
        self.id_origine = self.tarif.get("id")
        self.avertissements: list[str] = []
        self.setWindowTitle("Modifier le tarif" if tarif else "Nouveau tarif")
        if parent is not None:
            self.setWindowIcon(parent.windowIcon())
        self.setMinimumWidth(540)

        colonne = QVBoxLayout(self)
        colonne.setContentsMargins(0, 0, 0, 12)
        zone = QScrollArea()
        zone.setWidgetResizable(True)
        zone.setFrameShape(QScrollArea.NoFrame)
        cases = QWidget()
        cases.setObjectName("Formulaire")
        cases.setAttribute(Qt.WA_StyledBackground, True)
        disposition = QVBoxLayout(cases)
        disposition.setContentsMargins(16, 8, 16, 12)
        disposition.setSpacing(3)

        titre = QLabel("Période tarifaire" if tarif else "Nouvelle période")
        titre.setObjectName("TitreDialogue")
        disposition.addWidget(titre)
        # Dire OU trouver les chiffres : sans grille tarifaire l'application
        # ne sait rien calculer, et c'est le premier ecran d'un nouvel
        # utilisateur.
        # TTC dit en clair (19/10/2026) : la facture donne aussi le HT, et
        # recopier celui-ci sous-estimait tous les couts sans rien signaler.
        aide = QLabel("Tout se lit sur votre facture d'électricité ou dans "
                      "votre espace client : le prix du kWh, l'abonnement "
                      "mensuel, et vos plages d'heures creuses si vous en "
                      "avez. Prenez les prix TTC (taxes comprises) : c'est "
                      "ce que vous payez.")
        aide.setObjectName("Discret")
        aide.setWordWrap(True)
        disposition.addWidget(aide)

        # Pas de `valider` : Entree declenche deja « Enregistrer », bouton
        # par defaut de la fenetre (voir dialogue_modifier.py).
        self.formulaire = f = Formulaire(disposition)
        t = self.tarif
        f.champ("Nom du tarif (ex. Mon contrat HP/HC)", "nom")
        f.champ("Début", "debut", "jj/mm/aaaa")
        f.champ("Fin   (vide si c'est le tarif actuel)", "fin", "jj/mm/aaaa")
        f.champ("Abonnement mensuel (€ TTC)", "abonnement_mensuel")
        f.ecrire("nom", t.get("nom", ""))
        f.ecrire("debut", date_fr(t.get("debut")) or debut_propose())
        f.ecrire("fin", date_fr(t.get("fin")))
        f.ecrire("abonnement_mensuel", nombre_fr(t.get("abonnement_mensuel")))

        # Le type : deux boutons radio, et le bloc de prix qui va avec.
        disposition.addSpacing(6)
        libelle = QLabel("Type de tarif")
        libelle.setObjectName("LibelleChamp")
        disposition.addWidget(libelle)
        ligne = QHBoxLayout()
        self.choix_unique = QRadioButton("Prix unique")
        self.choix_hp_hc = QRadioButton("Heures pleines / creuses")
        groupe = QButtonGroup(self)
        for bouton in (self.choix_unique, self.choix_hp_hc):
            groupe.addButton(bouton)
            ligne.addWidget(bouton)
        ligne.addStretch(1)
        disposition.addLayout(ligne)

        self.bloc_unique = QWidget()
        f.poser_dans(QVBoxLayout(self.bloc_unique))
        self.bloc_unique.layout().setContentsMargins(0, 0, 0, 0)
        f.champ("Prix du kWh (€ TTC)", "prix_kwh")
        disposition.addWidget(self.bloc_unique)

        self.bloc_hp_hc = QWidget()
        f.poser_dans(QVBoxLayout(self.bloc_hp_hc))
        self.bloc_hp_hc.layout().setContentsMargins(0, 0, 0, 0)
        f.champ("Prix en heures PLEINES (€/kWh TTC)", "prix_hp")
        f.champ("Prix en heures CREUSES (€/kWh TTC)", "prix_hc")
        f.champ("Plages d'heures creuses (ex. 22:00-06:00, ou 23:00-07:00, "
                "12:00-14:00)", "plages_hc")
        # Un menu qui REMPLIT la case, sans la remplacer : les plages
        # courantes evitent de composer l'ecriture a la main, et celles qui
        # sortent de l'ordinaire restent saisissables.
        self.menu_plages = QComboBox()
        self.menu_plages.addItems(list(PLAGES_COURANTES))
        self.menu_plages.activated.connect(self._poser_plage)
        self.bloc_hp_hc.layout().addWidget(self.menu_plages)
        disposition.addWidget(self.bloc_hp_hc)
        f.poser_dans(disposition)

        f.ecrire("prix_kwh", nombre_fr(t.get("prix_kwh")))
        f.ecrire("prix_hp", nombre_fr(t.get("prix_hp")))
        f.ecrire("prix_hc", nombre_fr(t.get("prix_hc")))
        f.ecrire("plages_hc", ", ".join(f"{a}-{b}"
                                        for a, b in t.get("plages_hc", [])))
        hp_hc = t.get("type") == "hp_hc"
        (self.choix_hp_hc if hp_hc else self.choix_unique).setChecked(True)
        self.choix_hp_hc.toggled.connect(self._montrer_bloc_prix)
        self._montrer_bloc_prix()

        disposition.addStretch(1)
        zone.setWidget(cases)
        colonne.addWidget(zone, 1)

        # Ce qui ne vient pas d'une case en particulier (plages qui se
        # chevauchent, fichier impossible a ecrire).
        self.message = QLabel("")
        self.message.setObjectName("MessageChamp")
        self.message.setWordWrap(True)
        self.message.setContentsMargins(16, 6, 16, 0)
        self.message.hide()
        colonne.addWidget(self.message)

        boutons = QDialogButtonBox()
        self.bouton_enregistrer = boutons.addButton(
            "Enregistrer", QDialogButtonBox.AcceptRole)
        self.bouton_enregistrer.setObjectName("BoutonEnregistrer")
        self.bouton_enregistrer.setDefault(True)
        annuler = boutons.addButton("Annuler", QDialogButtonBox.RejectRole)
        annuler.setAutoDefault(False)
        boutons.accepted.connect(self.enregistrer)
        boutons.rejected.connect(self.reject)
        boutons.setContentsMargins(16, 6, 16, 0)
        colonne.addWidget(boutons)
        self.resize(580, 700)

    def _montrer_bloc_prix(self) -> None:
        hp_hc = self.choix_hp_hc.isChecked()
        self.bloc_hp_hc.setVisible(hp_hc)
        self.bloc_unique.setVisible(not hp_hc)

    def _poser_plage(self, rang: int) -> None:
        """Recopie dans la case la plage choisie, puis remet le menu sur
        « Choisir une plage courante… »."""
        valeur = list(PLAGES_COURANTES.values())[rang]
        if valeur:
            self.formulaire.ecrire("plages_hc", valeur)
        self.menu_plages.setCurrentIndex(0)

    def enregistrer(self) -> None:
        f = self.formulaire
        f.effacer_erreurs()
        self.message.hide()
        try:
            tarif = lire_tarif({nom: f.texte(nom) for nom in f.cases},
                               self.choix_hp_hc.isChecked())
            tarif["id"] = self.id_origine
            # Les notes du tarif d'origine (« _commentaire »...) ne sont dans
            # aucune case : on les reprend telles quelles. Sans cela,
            # enregistrer un tarif les effacait de tarifs.json (bug trouve
            # le 25/09/2026).
            for cle, valeur in self.tarif.items():
                if cle.startswith("_"):
                    tarif.setdefault(cle, valeur)
            # Tout le tarif est verifie AVANT de toucher a la grille.
            valider_tarif(tarif)
        except ErreurSaisie as e:
            f.erreur(e.champ, e.message)
            return
        except ValueError as e:
            self._message(erreur_en_clair(e))
            return

        # Nouvelle periode : le tarif precedent doit etre ferme, sinon il
        # continue de s'appliquer et le nouveau ne sert a rien.
        ouvert = tarif_ouvert_avant(tarif["debut"], self.id_origine)
        a_cloturer = None
        try:
            if ouvert and not self.id_origine:
                veille = (datetime.fromisoformat(tarif["debut"])
                          - timedelta(days=1)).strftime("%d/%m/%Y")
                # L'action est proposee par defaut : elle ne detruit rien,
                # et sans elle le nouveau tarif ne servirait jamais.
                if confirmer(
                        self, "Fermer le tarif précédent ?",
                        f"« {ouvert['nom']} » n'a pas de date de fin : sans "
                        "quoi il continuerait de s'appliquer et votre nouveau "
                        "tarif ne servirait jamais.\n\n"
                        f"Voulez-vous le terminer le {veille} ?",
                        action=f"Le terminer le {veille}",
                        garder="Le laisser ouvert", action_par_defaut=True):
                    a_cloturer = ouvert["id"]
            # Fermer l'ancien et ajouter le nouveau : une seule ecriture,
            # pour ne jamais laisser le changement fait a moitie.
            self.avertissements = enregistrer_tarif(
                tarif, self.id_origine, cloturer=a_cloturer)
        except (ValueError, OSError) as e:
            self._message(erreur_en_clair(e))
            return
        self.accept()

    def _message(self, texte: str) -> None:
        self.message.setText(texte)
        self.message.show()
