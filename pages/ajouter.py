"""Ajouter une recharge (version PySide6) : onglets Maison et Extérieur.

Reprise de l'ancienne page vues/ajout.py. Les regles de lecture des cases sont dans saisie.py
(lire_recharge_maison, lire_recharge_exterieur) et se testent sans fenetre ;
cette page pose les cases, affiche les messages sous la case fautive, pose
les questions de garde-fou, puis enregistre.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QLabel, QPushButton, QSizePolicy, QTabWidget,
                               QVBoxLayout, QWidget)

from constantes import CARTES, OPERATEURS
from formulaire import Formulaire, confirmer_energie, confirmer_horodatage
from erreurs import erreur_en_clair
from recharges import (ajouter_recharge_exterieur, ajouter_recharge_maison,
                       ajouter_releve_km, dernier_choix_exterieur,
                       lieux_deja_saisis)
from suivi_saisie import marquer_enregistre
from saisie import ErreurSaisie, lire_recharge_exterieur, lire_recharge_maison
from formats import fmt_eur, fmt_kwh, fmt_prix_kwh
from theme_qt import ROUGE, VERT

# Largeur maximale du formulaire : des cases qui s'etirent sur toute la
# largeur d'un grand ecran se lisent mal.
LARGEUR_FORMULAIRE = 760


class OngletsAjustes(QTabWidget):
    """Des onglets a la hauteur de l'onglet AFFICHE.

    Qt leur donne d'office la hauteur du plus long (Exterieur) : sur
    l'onglet Maison, un grand cadre blanc vide restait sous le bouton, et
    faisait tache sur le fond creme."""

    def _hauteur(self, taille, mesure):
        page = self.currentWidget()
        if page is not None:
            # Barre des onglets, page affichee, et le liseré du cadre.
            taille.setHeight(self.tabBar().sizeHint().height()
                             + mesure(page).height() + 4)
        return taille

    def sizeHint(self):
        return self._hauteur(super().sizeHint(), lambda p: p.sizeHint())

    def minimumSizeHint(self):
        return self._hauteur(super().minimumSizeHint(),
                             lambda p: p.minimumSizeHint())

    def hasHeightForWidth(self):
        # Sinon Qt recalcule la hauteur « selon la largeur » sur tous les
        # onglets, et le plus long l'emporte de nouveau.
        return False


def construire(fenetre) -> QWidget:
    page = QWidget()
    colonne = QVBoxLayout(page)
    colonne.setContentsMargins(0, 0, 0, 0)

    onglets = OngletsAjustes()
    onglets.setObjectName("OngletsSaisie")
    onglets.setMaximumWidth(LARGEUR_FORMULAIRE)
    # A la hauteur de son contenu, pas jusqu'au bas de la fenetre.
    onglets.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Maximum)
    maison, page.maison = _onglet(
        fenetre, _poser_maison, enregistrer_maison,
        "Enregistrer la recharge maison")
    exterieur, page.exterieur = _onglet(
        fenetre, _poser_exterieur, enregistrer_exterieur,
        "Enregistrer la recharge extérieure")
    onglets.addTab(maison, "Maison")
    onglets.addTab(exterieur, "Extérieur")
    onglets.currentChanged.connect(lambda _rang: onglets.updateGeometry())
    # Cale en haut ; en largeur, il prend la place disponible jusqu'a son
    # maximum, et reste cale a gauche.
    colonne.addWidget(onglets, 0, Qt.AlignTop)
    colonne.addStretch(1)
    page.onglets = onglets                  # pour les tests
    return page


def _onglet(fenetre, poser, enregistrer,
            texte_bouton: str) -> tuple[QWidget, Formulaire]:
    """Un onglet : fond blanc, cases, ligne de resultat, bouton."""
    onglet = QWidget()
    onglet.setObjectName("Formulaire")
    onglet.setAttribute(Qt.WA_StyledBackground, True)
    disposition = QVBoxLayout(onglet)
    disposition.setContentsMargins(16, 8, 16, 16)
    disposition.setSpacing(3)
    # Entree dans une case enregistre, comme le bouton.
    f = Formulaire(disposition, valider=lambda: enregistrer(fenetre, f))
    poser(f)

    f.resultat = QLabel("")
    f.resultat.setWordWrap(True)
    f.resultat.setTextInteractionFlags(Qt.TextSelectableByMouse)
    disposition.addSpacing(8)
    disposition.addWidget(f.resultat)

    bouton = QPushButton(texte_bouton)
    bouton.setObjectName("BoutonEnregistrer")
    bouton.clicked.connect(lambda: enregistrer(fenetre, f))
    disposition.addSpacing(8)
    disposition.addWidget(bouton)
    # Le blanc restant va sous le bouton : l'onglet le plus court (Maison)
    # prend la hauteur du plus long, et ses cases ne doivent pas s'ecarter.
    disposition.addStretch(1)
    f.bouton = bouton
    return onglet, f


def _poser_maison(f: Formulaire):
    f.champ_date_heure("Début de la recharge", "champ_m_debut",
                       remplir_maintenant=True)
    # Facultative avec un tarif a prix unique : la duree ne change alors
    # rien au cout, et l'exiger n'etait qu'une corvee de plus.
    f.champ_date_heure(
        "Fin de la recharge   (vide si tarif à prix unique ; l'heure seule "
        "suffit, ou une durée : « +6h12 »)", "champ_m_fin")
    f.champ("Énergie consommée (kWh)", "champ_m_kwh")
    f.champ("Kilométrage du compteur  (facultatif)", "champ_m_km")
    # Les cases a remplir s'encadrent de bleu tant qu'elles sont vides.
    f.exiger("champ_m_debut_jour", "champ_m_debut_heure", "champ_m_kwh")


def _poser_exterieur(f: Formulaire):
    f.champ_date_heure("Date et heure de la recharge", "champ_e_date",
                       remplir_maintenant=True)
    # Les recus des operateurs ne donnent pas tous les memes chiffres :
    # certains le total paye, d'autres le prix au kWh. Deux suffisent.
    f.aide("Remplissez deux de ces trois cases, la troisième se calcule. "
           "Si vous les remplissez toutes, c'est le coût payé qui fait foi.")
    f.champ("Énergie (kWh)", "champ_e_kwh")
    f.champ("Coût total (€)", "champ_e_cout")
    f.champ("Prix du kWh (€/kWh)", "champ_e_prix")
    # Pre-remplis avec les derniers choix faits, et non avec un reseau et
    # une carte ecrits en dur : on recharge le plus souvent aux memes
    # endroits, et un formulaire neuf ne doit pas afficher les habitudes de
    # quelqu'un d'autre.
    operateur, carte_paiement = dernier_choix_exterieur()
    f.liste("Opérateur", "champ_e_operateur", OPERATEURS, operateur)
    f.liste("Carte / Moyen de paiement", "champ_e_carte", CARTES,
            carte_paiement)
    # Liste, et non case libre : on recharge presque toujours aux memes
    # endroits. On peut y taper un lieu nouveau.
    f.liste("Lieu (choisissez dans la liste, ou tapez un nouveau lieu)",
            "champ_e_lieu", lieux_deja_saisis())
    f.champ("Kilométrage du compteur  (facultatif)", "champ_e_km")
    # Deux des trois suffisent : les vides s'encadrent tant qu'il en manque.
    # La date, vide, vaut « maintenant » : elle n'est pas exigee.
    f.exiger("champ_e_kwh", "champ_e_cout", "champ_e_prix", combien=2)


def _resultat(f: Formulaire, texte: str, ok: bool) -> None:
    f.resultat.setText(texte)
    f.resultat.setStyleSheet(f"color: {VERT if ok else ROUGE};")


def noter_le_compteur(km: float | None, quand: str) -> tuple[str, bool]:
    """Enregistre le releve facultatif saisi avec la recharge.

    Rend la phrase a ajouter au message de resultat (vide s'il n'y avait
    rien a noter) et si le releve a bien ete pris.

    Appelee APRES l'enregistrement de la recharge, jamais avant : si le
    releve est refuse (compteur qui recule, releve deja la), la recharge,
    elle, est valable et doit rester. Le message le dit alors sans
    ambiguite. Le releve est date de la recharge : c'est en branchant la
    voiture qu'on lit le compteur."""
    if km is None:
        return "", True
    try:
        releve = ajouter_releve_km(km, quand)
    except (ValueError, OSError) as e:
        return ("  —  Recharge enregistrée, mais PAS le relevé : "
                f"{erreur_en_clair(e)}", False)
    return (f"  —  relevé noté : {releve['km']:,.0f}\xa0km".replace(",", "\xa0"),
            True)


def _enregistre(f: Formulaire, case_km: str, km_refuse: bool) -> None:
    """Recharge enregistree : ses cases ne sont plus « en attente » pour la
    fenetre (question a la fermeture, page gardee). Un kilometrage refuse,
    lui, reste a corriger : il garde sa marque."""
    marquer_enregistre(*(case for nom, case in f.cases.items()
                         if not (km_refuse and nom == case_km)))


def enregistrer_maison(fenetre, f: Formulaire) -> None:
    f.effacer_erreurs()
    f.resultat.setText("")
    try:
        lu = lire_recharge_maison(
            f.texte("champ_m_debut_jour"), f.texte("champ_m_debut_heure"),
            f.texte("champ_m_fin_jour"), f.texte("champ_m_fin_heure"),
            f.texte("champ_m_kwh"), f.texte("champ_m_km"))
    except ErreurSaisie as e:
        f.erreur(e.champ, e.message)
        return
    if not confirmer_energie(fenetre, lu["kwh"]):
        return
    try:
        r = ajouter_recharge_maison(lu["debut"], lu["fin"], lu["kwh"])
    except (ValueError, OSError) as e:
        # Ce qui ne vient pas d'une case en particulier : aucune periode
        # tarifaire pour cette date, fichier impossible a ecrire... Le
        # message de recharges.py est deja en francais.
        _resultat(f, erreur_en_clair(e), ok=False)
        return
    note, releve_pris = noter_le_compteur(lu["km"], r["date"])
    if lu["km"] is not None and releve_pris:
        f.vider("champ_m_km")
    _resultat(f, f"OK : {fmt_kwh(r['kwh_hc'])} HC + {fmt_kwh(r['kwh_hp'])} HP"
                 f" = {fmt_eur(r['cout_eur'])}  ({r['tarif_nom']}){note}",
              ok=releve_pris)
    # Formulaire vide : un second clic ne peut plus creer un doublon.
    f.mettre_maintenant("champ_m_debut")
    f.vider("champ_m_fin_jour", "champ_m_fin_heure", "champ_m_kwh")
    _enregistre(f, "champ_m_km", lu["km"] is not None and not releve_pris)
    fenetre._maj_bilan()


def enregistrer_exterieur(fenetre, f: Formulaire) -> None:
    f.effacer_erreurs()
    f.resultat.setText("")
    try:
        lu = lire_recharge_exterieur(
            f.texte("champ_e_date_jour"), f.texte("champ_e_date_heure"),
            f.texte("champ_e_kwh"), f.texte("champ_e_cout"),
            f.texte("champ_e_prix"), f.texte("champ_e_km"))
    except ErreurSaisie as e:
        f.erreur(e.champ, e.message)
        return
    if not confirmer_energie(fenetre, lu["kwh"]):
        return
    # Deux cases de date vides : la recharge est datee de maintenant.
    date = (lu["date"].isoformat(timespec="minutes")
            if lu["date"] is not None else None)
    if not confirmer_horodatage(fenetre, date):
        return
    try:
        r = ajouter_recharge_exterieur(
            lu["kwh"], lu["cout"],
            operateur=f.texte("champ_e_operateur").strip(),
            lieu_detail=f.texte("champ_e_lieu").strip(),
            date=date,
            carte=f.texte("champ_e_carte").strip())
    except (ValueError, OSError) as e:
        _resultat(f, erreur_en_clair(e), ok=False)
        return
    note, releve_pris = noter_le_compteur(lu["km"], r["date"])
    if lu["km"] is not None and releve_pris:
        f.vider("champ_e_km")
    _resultat(f, f"OK : {fmt_eur(r['cout_eur'])}  "
                 f"({fmt_prix_kwh(r['prix_kwh'])}){note}", ok=releve_pris)
    # Formulaire vide : un second clic ne peut plus creer un doublon.
    # Operateur et carte restent : on recharge souvent au meme reseau.
    f.mettre_maintenant("champ_e_date")
    f.vider("champ_e_kwh", "champ_e_cout", "champ_e_prix")
    # Un lieu nouveau doit apparaitre dans la liste des la saisie suivante.
    lieu = f.cases["champ_e_lieu"]
    lieu.clear()
    lieu.addItems(lieux_deja_saisis())
    lieu.setCurrentIndex(-1)
    lieu.setEditText("")
    _enregistre(f, "champ_e_km", lu["km"] is not None and not releve_pris)
    fenetre._maj_bilan()
