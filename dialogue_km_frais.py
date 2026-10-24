"""Les fenetres « Modifier le relevé » (page Kilometrage) et « Modifier les
frais » (page Tarifs).

Ajoutees apres l'analyse du 16/10/2026 : jusque-la, une faute dans un
releve kilometrique ou des frais de carte imposait de supprimer l'entree,
puis de la recreer. Les regles de lecture sont celles de la saisie
(saisie.lire_releve_km, saisie.lire_frais_carte), les controles ceux du
moteur (recharges.modifier_releve_km, recharges.modifier_frais_carte) :
une correction est verifiee exactement comme un ajout.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QComboBox, QDialog, QDialogButtonBox, QLabel,
                               QVBoxLayout, QWidget)

from dialogue_modifier import jour_et_heure, nombre_fr
from erreurs import erreur_en_clair
from formats import fmt_date_fr
from formulaire import Formulaire
from recharges import (TYPES_FRAIS_CARTE, modifier_frais_carte,
                       modifier_releve_km)
from saisie import ErreurSaisie, lire_frais_carte, lire_releve_km


def _nombre(valeur) -> str:
    """1000.0 -> « 1000 », 16.5 -> « 16,5 » : sans « ,0 » inutile."""
    if isinstance(valeur, float) and valeur.is_integer():
        valeur = int(valeur)
    return nombre_fr(valeur)


class _DialogueSimple(QDialog):
    """Le cadre commun : un titre, les cases, une ligne de message pour ce
    qui ne vient pas d'une case, puis « Enregistrer » et « Annuler »
    (Echap ferme aussi sans rien changer). Chaque fenetre fille a sa
    methode enregistrer()."""

    def __init__(self, parent, titre_fenetre: str, rappel: str):
        super().__init__(parent)
        self.setWindowTitle(titre_fenetre)
        if parent is not None:
            self.setWindowIcon(parent.windowIcon())
        self.setMinimumWidth(460)

        colonne = QVBoxLayout(self)
        colonne.setContentsMargins(0, 0, 0, 12)
        cases = QWidget()
        cases.setObjectName("Formulaire")       # le style des cases
        cases.setAttribute(Qt.WA_StyledBackground, True)
        self.disposition = QVBoxLayout(cases)
        self.disposition.setContentsMargins(16, 8, 16, 12)
        self.disposition.setSpacing(3)
        titre = QLabel(rappel)
        titre.setObjectName("TitreDialogue")
        titre.setWordWrap(True)
        self.disposition.addWidget(titre)
        # Pas de `valider` : dans une fenetre de dialogue, Entree declenche
        # deja le bouton par defaut. Le brancher aussi enregistrerait deux
        # fois.
        self.formulaire = Formulaire(self.disposition)
        colonne.addWidget(cases, 1)

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
        self._boutons = boutons

    def _finir(self) -> None:
        """A appeler une fois les cases posees : les boutons en bas."""
        self.disposition.addStretch(1)
        self.layout().addWidget(self._boutons)

    def _erreur_generale(self, texte: str) -> None:
        self.message.setText(texte)
        self.message.show()


class DialogueReleve(_DialogueSimple):
    """Corriger un releve du compteur : date, kilometrage, consommation
    affichee. Rend QDialog.Accepted si le releve a ete modifie."""

    def __init__(self, parent, releve: dict):
        km = f"{releve.get('km', 0):,.0f}".replace(",", "\xa0")
        super().__init__(parent, "Modifier le relevé",
                         f"Relevé du {fmt_date_fr(releve.get('date', ''))}"
                         f"  ·  {km}\xa0km")
        self.releve = releve
        f = self.formulaire
        # Les noms des cases sont ceux de la page Kilometrage : les messages
        # de saisie.lire_releve_km designent ainsi la bonne case.
        f.champ_date_heure("Date du relevé", "champ_km_date",
                           bouton_maintenant=False)
        f.champ("Kilométrage (km)", "champ_km_valeur")
        f.champ("Consommation affichée par la voiture (kWh/100\xa0km, "
                "facultative)", "champ_km_conso")
        jour, heure = jour_et_heure(releve.get("date", ""))
        f.ecrire("champ_km_date_jour", jour)
        f.ecrire("champ_km_date_heure", heure)
        f.ecrire("champ_km_valeur", _nombre(releve.get("km")))
        f.ecrire("champ_km_conso", _nombre(releve.get("conso")))
        self._finir()
        self.resize(480, 330)

    def enregistrer(self) -> None:
        f = self.formulaire
        f.effacer_erreurs()
        self.message.hide()
        try:
            lu = lire_releve_km(f.texte("champ_km_date_jour"),
                                f.texte("champ_km_date_heure"),
                                f.texte("champ_km_valeur"),
                                f.texte("champ_km_conso"))
        except ErreurSaisie as e:
            f.erreur(e.champ, e.message)
            return
        # Date effacee : le releve garde la sienne (a la saisie, une date
        # vide vaut « maintenant », ce qui n'a pas de sens pour corriger).
        quand = (lu["date"].isoformat(timespec="minutes")
                 if lu["date"] is not None else self.releve.get("date"))
        try:
            modifier_releve_km(self.releve.get("id", ""), lu["km"], quand,
                               lu["conso"])
        except (ValueError, OSError) as e:
            # Kilometrage en recul, consommation hors des clous : comme sur
            # la page, le message va sous la case concernee.
            texte = erreur_en_clair(e)
            if "introuvable" in texte or isinstance(e, OSError):
                self._erreur_generale(texte)
            else:
                f.erreur("champ_km_conso" if "consommation" in texte
                         else "champ_km_valeur", texte)
            return
        self.accept()


class DialogueFrais(_DialogueSimple):
    """Corriger des frais de carte : carte, type, dates, montant. Rend
    QDialog.Accepted si les frais ont ete modifies."""

    def __init__(self, parent, frais: dict, cartes: list[str] | None = None):
        super().__init__(parent, "Modifier les frais",
                         f"Frais de la carte {frais.get('carte', '')}")
        self.frais = frais
        f = self.formulaire
        f.liste("Carte", "carte", cartes or [], frais.get("carte", ""))
        # Le type : une liste fermee, avec la cle du fichier en donnee.
        etiquette = QLabel("Type")
        etiquette.setObjectName("LibelleChamp")
        self.disposition.addSpacing(6)
        self.disposition.addWidget(etiquette)
        self.choix_type = QComboBox()
        for cle, texte in TYPES_FRAIS_CARTE.items():
            self.choix_type.addItem(texte, cle)
        self.choix_type.setCurrentIndex(
            max(0, self.choix_type.findData(frais.get("type"))))
        self.disposition.addWidget(self.choix_type)
        self.case_date = f.champ("Date d'achat ou de début", "date",
                                 "jj/mm/aaaa")
        f.champ("Fin de l'abonnement (facultative)", "fin", "jj/mm/aaaa")
        self.case_montant = f.champ("Montant (€)", "montant")
        # Le libelle qui vient d'etre pose : il dira « par mois » ou « par
        # an » selon le type, comme sur la page.
        self.libelle_montant = [e for e in self.findChildren(QLabel)
                                if e.text() == "Montant (€)"][-1]
        f.ecrire("date", fmt_date_fr(frais.get("date", ""))[:10])
        f.ecrire("fin", fmt_date_fr(frais["fin"])[:10]
                 if frais.get("fin") else "")
        f.ecrire("montant", _nombre(frais.get("montant")))
        self.choix_type.currentIndexChanged.connect(
            lambda _: self._selon_le_type())
        self._selon_le_type()
        self._finir()
        self.resize(480, 400)

    def _selon_le_type(self) -> None:
        """Comme sur la page : la fin ne sert qu'a un abonnement, et le
        montant d'un abonnement est celui d'un mois ou d'une annee."""
        type_ = self.choix_type.currentData()
        self.formulaire.cases["fin"].setEnabled(type_ != "unique")
        self.libelle_montant.setText(
            {"mensuel": "Montant (€ par mois)",
             "annuel": "Montant (€ par an)"}.get(type_, "Montant (€)"))

    def enregistrer(self) -> None:
        f = self.formulaire
        f.effacer_erreurs()
        self.message.hide()
        try:
            lu = lire_frais_carte({
                "carte": f.texte("carte"),
                "type": self.choix_type.currentData(),
                "date": f.texte("date"), "fin": f.texte("fin"),
                "montant": f.texte("montant")})
        except ErreurSaisie as e:
            f.erreur(e.champ, e.message)
            return
        try:
            modifier_frais_carte(self.frais.get("id", ""), lu)
        except (ValueError, OSError) as e:
            self._erreur_generale(erreur_en_clair(e))
            return
        self.accept()
