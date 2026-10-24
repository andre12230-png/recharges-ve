"""La fenetre « Modifier la recharge » (version PySide6).

Reprise de l'ancienne fenetre dialogues.py (DialogueEdition). Les regles de lecture sont dans
saisie.py (lire_modification_recharge) et se testent sans fenetre ; les
cases et leurs messages viennent de formulaire.py, comme la page Ajouter.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QDialog, QDialogButtonBox, QLabel, QScrollArea,
                               QVBoxLayout, QWidget)

from constantes import CARTES, OPERATEURS
from formulaire import Formulaire, confirmer_energie
from erreurs import erreur_en_clair
from recharges import lieux_deja_saisis, modifier_recharge
from saisie import ErreurSaisie, lire_modification_recharge
from formats import fmt_date_fr


def jour_et_heure(iso: str) -> tuple[str, str]:
    """« 2026-09-18T22:30 » donne (« 18/09/2026 », « 22:30 »).

    Une recharge maison sans heure de fin rend deux chaines vides : deux
    cases vides, le cas legitime du tarif a prix unique."""
    texte = fmt_date_fr(iso) if iso else ""
    if " " in texte:
        jour, heure = texte.split(" ", 1)
        return jour, heure
    return texte, ""


def nombre_fr(valeur) -> str:
    """12.5 -> « 12,5 » : la case s'affiche comme on l'ecrirait soi-meme
    (l'ancienne fenetre montrait « 12.5 », a la maniere de Python).

    Le nombre est recopie EN ENTIER, sans arrondi : enregistrer sans rien
    toucher ne doit pas modifier discretement la valeur."""
    if valeur in (None, ""):
        return ""
    return str(valeur).replace(".", ",")


class DialogueModifier(QDialog):
    """Fenetre modale : on corrige, puis « Enregistrer » ou « Annuler »
    (Echap ferme aussi sans rien changer). Rend QDialog.Accepted si la
    recharge a ete modifiee."""

    def __init__(self, parent, recharge: dict):
        super().__init__(parent)
        self.recharge = recharge
        self.maison = recharge.get("lieu") == "maison"
        self.setWindowTitle("Modifier la recharge")
        if parent is not None:
            self.setWindowIcon(parent.windowIcon())
        self.setMinimumWidth(520)

        colonne = QVBoxLayout(self)
        colonne.setContentsMargins(0, 0, 0, 12)

        # Les cases, dans une zone qui defile si la fenetre est petite.
        zone = QScrollArea()
        zone.setWidgetResizable(True)
        zone.setFrameShape(QScrollArea.NoFrame)
        cases = QWidget()
        cases.setObjectName("Formulaire")
        cases.setAttribute(Qt.WA_StyledBackground, True)
        disposition = QVBoxLayout(cases)
        disposition.setContentsMargins(16, 8, 16, 12)
        disposition.setSpacing(3)
        # Pas de `valider` ici : dans une fenetre de dialogue, Entree
        # declenche deja le bouton par defaut (« Enregistrer »). Le brancher
        # aussi sur les cases enregistrerait deux fois.
        # Rappel de la recharge qu'on modifie, en tete.
        ou = "à la maison" if self.maison else "à l'extérieur"
        kwh = f"{recharge.get('kwh', 0):.2f}".replace(".", ",")
        titre = QLabel(f"Recharge {ou} du "
                       f"{fmt_date_fr(recharge.get('date', ''))}  ·  {kwh}\xa0kWh")
        titre.setObjectName("TitreDialogue")
        disposition.addWidget(titre)
        self.formulaire = f = Formulaire(disposition)
        self._poser_cases(f)
        disposition.addStretch(1)
        zone.setWidget(cases)
        colonne.addWidget(zone, 1)

        # Ce qui ne vient pas d'une case en particulier : aucune periode
        # tarifaire pour cette date, fichier impossible a ecrire.
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

        self.resize(560, 350 if self.maison else 500)

    def _poser_cases(self, f: Formulaire) -> None:
        r = self.recharge
        if self.maison:
            f.champ_date_heure("Début de la recharge", "date",
                               bouton_maintenant=False)
            f.champ_date_heure(
                "Fin de la recharge   (vide si tarif à prix unique ; ou une "
                "durée : « +6h12 »)", "fin", bouton_maintenant=False)
            f.champ("Énergie (kWh)", "kwh")
            self._ecrire_date("fin", r.get("fin", ""))
        else:
            f.champ_date_heure("Date et heure de la recharge", "date",
                               bouton_maintenant=False)
            f.champ("Énergie (kWh)", "kwh")
            f.champ("Coût (€)", "cout_eur")
            f.liste("Opérateur", "operateur", OPERATEURS,
                    r.get("operateur", ""))
            f.liste("Carte / Moyen de paiement", "carte", CARTES,
                    r.get("carte", ""))
            # Meme liste qu'a la saisie : corriger un lieu ne doit pas etre
            # l'occasion d'en inventer une nouvelle ecriture.
            f.liste("Lieu", "lieu_detail", lieux_deja_saisis(),
                    r.get("lieu_detail", ""))
            f.ecrire("cout_eur", nombre_fr(r.get("cout_eur")))
        self._ecrire_date("date", r.get("date", ""))
        f.ecrire("kwh", nombre_fr(r.get("kwh")))

    def _ecrire_date(self, nom: str, iso: str) -> None:
        jour, heure = jour_et_heure(iso)
        self.formulaire.ecrire(f"{nom}_jour", jour)
        self.formulaire.ecrire(f"{nom}_heure", heure)

    def enregistrer(self) -> None:
        f = self.formulaire
        f.effacer_erreurs()
        self.message.hide()
        try:
            modifs = lire_modification_recharge(
                self.recharge, {nom: f.texte(nom) for nom in f.cases})
        except ErreurSaisie as e:
            f.erreur(e.champ, e.message)
            return
        # Meme garde-fou qu'a la saisie.
        if not confirmer_energie(self, modifs["kwh"]):
            return
        try:
            modifier_recharge(self.recharge.get("id", ""), modifs)
        except (ValueError, OSError) as e:
            self.message.setText(erreur_en_clair(e))
            self.message.show()
            return
        self.accept()
