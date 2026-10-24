"""Les formulaires de saisie de la version PySide6 : libelle, case, et
message d'erreur SOUS la case fautive.

Qt n'a rien de tel tout pret : ses formulaires signalent une erreur par une
boite de dialogue. Or le message doit rester sous les yeux pendant qu'on
corrige, et designer la case en cause (regle de Recharges VE depuis la
v1.26.2, voir tests/test_messages_saisie.py). Chaque case recoit donc sa
ligne de message, cachee tant qu'il n'y a rien a dire : une ligne cachee ne
prend aucune place.

Les cases sont rangees par NOM (« champ_m_kwh »...) : c'est le nom que
porte ErreurSaisie (saisie.py), et c'est ce qui permet d'ecrire le message
au bon endroit.

Servira aussi a la fenetre « Modifier la recharge » et a celle du tarif.
"""

from __future__ import annotations

from datetime import datetime

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QComboBox, QHBoxLayout, QLabel, QLineEdit,
                               QPushButton, QVBoxLayout, QWidget)

from composants import confirmer
from recharges import energie_invraisemblable, horodatage_deja_utilise


INVITE_A_SAISIR = "à saisir"


def exiger(cases: list, combien: int | None = None) -> None:
    """Encadre de bleu les cases obligatoires encore vides (demande du
    09/10/2026, comme la Saisie quotidienne du Photovoltaique).

    `combien` : nombre de cases du groupe a remplir (toutes par defaut).
    Tant qu'il en manque, les cases vides du groupe portent la propriete
    « aSaisir », que la feuille de style dessine en bleu (theme_qt.py).
    Une case sans texte d'invite recoit « à saisir ». L'etat se remet a
    jour a chaque frappe, et quand l'appli vide ou remplit les cases."""
    besoin = len(cases) if combien is None else combien

    def texte(case) -> str:
        if isinstance(case, QComboBox):
            return case.currentText()
        return case.text()

    def actualiser(*_args) -> None:
        manque = sum(1 for c in cases if texte(c).strip()) < besoin
        for case in cases:
            voulu = manque and not texte(case).strip()
            if bool(case.property("aSaisir")) != voulu:
                case.setProperty("aSaisir", voulu)
                # Qt ne relit pas la feuille de style tout seul quand une
                # propriete change : on le lui demande.
                case.style().unpolish(case)
                case.style().polish(case)

    for case in cases:
        if isinstance(case, QLineEdit) and not case.placeholderText():
            case.setPlaceholderText(INVITE_A_SAISIR)
        if isinstance(case, QComboBox):
            case.editTextChanged.connect(actualiser)
        else:
            case.textChanged.connect(actualiser)
    actualiser()


class Formulaire:
    """Les cases d'un formulaire, posees les unes sous les autres dans
    `disposition`, avec leurs messages.

    `valider` est appele quand on appuie sur Entree dans une case : Entree
    enregistre le formulaire, comme le dit la Notice."""

    def __init__(self, disposition: QVBoxLayout, valider=None):
        self._disposition = disposition
        self._valider = valider
        self.cases: dict[str, QLineEdit | QComboBox] = {}
        self._messages: dict[str, QLabel] = {}
        self.boutons_maintenant: dict[str, QPushButton] = {}

    # ---------- construction ----------

    def poser_dans(self, disposition: QVBoxLayout) -> None:
        """Les cases suivantes iront dans `disposition` (un bloc qu'on
        affiche ou cache, comme les prix d'un tarif selon son type). Elles
        restent rangees et signalees par ce meme formulaire."""
        self._disposition = disposition

    def _libelle(self, texte: str) -> None:
        etiquette = QLabel(texte)
        etiquette.setObjectName("LibelleChamp")
        etiquette.setWordWrap(True)
        self._disposition.addSpacing(6)
        self._disposition.addWidget(etiquette)

    def _ligne_de_message(self, *noms: str) -> None:
        """Pose, sous la derniere case, la ligne de message de `noms`.

        Les deux cases d'une date partagent la meme : elles forment une
        seule saisie, et deux messages l'un sous l'autre pour la meme date
        seraient deroutants."""
        message = QLabel("")
        message.setObjectName("MessageChamp")
        message.setWordWrap(True)
        message.setTextInteractionFlags(Qt.TextSelectableByMouse)
        message.hide()
        self._disposition.addWidget(message)
        for nom in noms:
            self._messages[nom] = message

    def _brancher_entree(self, case: QLineEdit) -> None:
        if self._valider is not None:
            case.returnPressed.connect(self._valider)

    def champ(self, libelle: str, nom: str, invite: str = "") -> QLineEdit:
        """Un libelle et sa case de saisie."""
        self._libelle(libelle)
        case = QLineEdit()
        case.setPlaceholderText(invite)
        self._brancher_entree(case)
        self._disposition.addWidget(case)
        self.cases[nom] = case
        self._ligne_de_message(nom)
        return case

    def champ_date_heure(self, libelle: str, nom: str, *,
                         remplir_maintenant: bool = False,
                         bouton_maintenant: bool = True) -> None:
        """Un libelle, puis DEUX cases : le jour, puis l'heure.

        Elles sont rangees sous « <nom>_jour » et « <nom>_heure ». Separees
        depuis le 18/09/2026 : chaque case annonce ce qu'elle attend par son
        texte grise, et le message d'erreur designe la bonne."""
        self._libelle(libelle)
        ligne = QHBoxLayout()
        ligne.setSpacing(8)
        jour = QLineEdit()
        jour.setPlaceholderText("jj/mm/aaaa")
        jour.setFixedWidth(130)
        heure = QLineEdit()
        heure.setPlaceholderText("hh:mm")
        heure.setFixedWidth(90)
        ligne.addWidget(jour)
        a = QLabel("à")
        a.setObjectName("LibelleChamp")
        ligne.addWidget(a)
        ligne.addWidget(heure)
        self.cases[f"{nom}_jour"] = jour
        self.cases[f"{nom}_heure"] = heure
        if bouton_maintenant:
            bouton = QPushButton("Maintenant")
            bouton.setToolTip("Remplir avec la date et l'heure de cet instant")
            bouton.clicked.connect(lambda: self.mettre_maintenant(nom))
            self.boutons_maintenant[nom] = bouton
            ligne.addSpacing(4)
            ligne.addWidget(bouton)
        ligne.addStretch(1)
        for case in (jour, heure):
            self._brancher_entree(case)
        self._disposition.addLayout(ligne)
        self._ligne_de_message(f"{nom}_jour", f"{nom}_heure")
        if remplir_maintenant:
            self.mettre_maintenant(nom)

    def liste(self, libelle: str, nom: str, valeurs: list[str],
              defaut: str = "") -> QComboBox:
        """Une liste deroulante dans laquelle on peut aussi taper (un
        operateur ou un lieu nouveau)."""
        self._libelle(libelle)
        case = QComboBox()
        case.setEditable(True)
        # Taper un nom nouveau ne doit pas l'ajouter a la liste a chaque
        # Entree : la liste vient des donnees, pas de la frappe.
        case.setInsertPolicy(QComboBox.NoInsert)
        case.addItems(valeurs)
        # Toujours poser la valeur, meme vide : sinon la liste affiche
        # d'office son premier choix (« Allego »), enregistre sans avoir
        # ete choisi (vu dans l'ancienne version).
        case.setCurrentIndex(-1)
        case.setEditText(defaut or "")
        self._brancher_entree(case.lineEdit())
        self._disposition.addWidget(case)
        self.cases[nom] = case
        self._ligne_de_message(nom)
        return case

    def aide(self, texte: str) -> QLabel:
        """Une phrase d'aide discrete, entre deux cases."""
        etiquette = QLabel(texte)
        etiquette.setObjectName("Discret")
        etiquette.setWordWrap(True)
        self._disposition.addSpacing(6)
        self._disposition.addWidget(etiquette)
        return etiquette

    def exiger(self, *noms: str, combien: int | None = None) -> None:
        """Les cases `noms` sont obligatoires : voir exiger() plus haut."""
        exiger([self.cases[nom] for nom in noms], combien)

    # ---------- lecture et ecriture ----------

    def texte(self, nom: str) -> str:
        case = self.cases[nom]
        if isinstance(case, QComboBox):
            return case.currentText()
        return case.text()

    def ecrire(self, nom: str, texte: str) -> None:
        case = self.cases[nom]
        if isinstance(case, QComboBox):
            case.setEditText(texte)
        else:
            case.setText(texte)

    def vider(self, *noms: str) -> None:
        for nom in noms:
            self.ecrire(nom, "")

    def mettre_maintenant(self, nom: str) -> None:
        """Remplit les deux cases d'une date avec l'instant present."""
        maintenant = datetime.now()
        self.ecrire(f"{nom}_jour", maintenant.strftime("%d/%m/%Y"))
        self.ecrire(f"{nom}_heure", maintenant.strftime("%H:%M"))

    # ---------- messages ----------

    def erreur(self, nom: str, message: str) -> None:
        """Ecrit le message sous la case fautive et y ramene le curseur."""
        etiquette = self._messages.get(nom)
        if etiquette is not None:
            etiquette.setText(message)
            etiquette.show()
        case = self.cases.get(nom)
        if case is not None:
            case.setFocus()

    def effacer_erreurs(self) -> None:
        """Chaque essai repart d'un formulaire propre : les messages du
        precedent ne doivent pas rester sous les cases qu'on vient de
        corriger."""
        for etiquette in self._messages.values():
            etiquette.hide()
            etiquette.setText("")

    def message(self, nom: str) -> str:
        """Le message affiche sous une case, vide s'il n'y en a pas."""
        etiquette = self._messages.get(nom)
        if etiquette is None or etiquette.isHidden():
            return ""
        return etiquette.text()


# ---------- questions avant d'enregistrer ----------

def _demander(parent: QWidget, titre: str, texte: str, *,
              oui_par_defaut: bool, action: str, garder: str) -> bool:
    """Une question avec l'icone d'avertissement et des boutons qui disent
    l'action (« Enregistrer quand même » / « Corriger »), et non plus Oui /
    Non (audit de design du 03/10/2026). Rend True pour l'action. A part
    pour que les tests puissent y repondre a la place de l'utilisateur."""
    return confirmer(parent, titre, texte, action=action, garder=garder,
                     danger=True, action_par_defaut=oui_par_defaut)


def confirmer_energie(parent: QWidget, kwh: float) -> bool:
    """Avertit si l'energie saisie ne peut pas tenir dans la batterie.

    Rend True s'il faut poursuivre l'enregistrement : valeur plausible, ou
    utilisateur qui confirme malgre l'avertissement. La page Ajouter et la
    fenetre « Modifier » doivent poser la MEME question."""
    souci = energie_invraisemblable(kwh)
    if not souci:
        return True
    # « Corriger » par defaut : en cas de doute ou de clic trop rapide, on
    # n'enregistre pas une valeur qui est presque surement fausse.
    return _demander(
        parent, "Énergie inhabituelle",
        f"{souci}\n\nC'est probablement une faute de frappe.\n\n"
        "Voulez-vous quand même enregistrer cette valeur ?",
        oui_par_defaut=False, action="Enregistrer quand même",
        garder="Corriger")


def confirmer_horodatage(parent: QWidget, date_iso: str | None) -> bool:
    """Avertit si une recharge porte deja exactement cette date et cette
    heure.

    Avertissement doux : deux recharges le meme jour sont normales sur un
    trajet, et « Enregistrer quand même » est la reponse par defaut. Le but est seulement de
    faire penser a preciser l'heure, faute de quoi l'ordre des recharges de
    la journee est arbitraire."""
    autre = horodatage_deja_utilise(date_iso)
    if autre is None:
        return True
    quoi = autre.get("operateur") or autre.get("lieu_detail") or "une recharge"
    kwh = f"{autre.get('kwh', 0):.2f}".replace(".", ",")
    return _demander(
        parent, "Même date et même heure",
        f"{quoi} est déjà enregistrée à cette date et cette heure "
        f"({kwh}\xa0kWh).\n\n"
        "Ce n'est pas forcément un doublon, mais tant que les deux portent "
        "la même heure, leur ordre dans la journée est arbitraire — ce qui "
        "peut fausser le rattachement aux relevés kilométriques.\n\n"
        "Enregistrer quand même ?",
        oui_par_defaut=True, action="Enregistrer quand même",
        garder="Corriger l'heure")
