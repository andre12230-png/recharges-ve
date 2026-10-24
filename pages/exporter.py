"""Exporter (version PySide6) : Excel ou PDF, sur la periode choisie.

Reprise de l'ancienne page vues/export.py. Le choix des recharges et le nom de fichier
propose sont a part, sans interface : ils se testent sans fenetre. Les
fichiers eux-memes sont faits par export.py, qui ne change pas.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

from PySide6.QtWidgets import (QComboBox, QFileDialog, QHBoxLayout, QLabel,
                               QPushButton, QVBoxLayout, QWidget)

from composants import carte, paragraphe
from export import exporter_excel, exporter_pdf
from filtres import bornes_frais, bornes_periode, filtrer_par_periode
from pages.historique import NOMS_LIEUX
from pages.periode import NOMS_AFFICHES, BarrePeriode
from erreurs import erreur_en_clair
from recharges import (calculer_abonnement, calculer_consommation,
                       calculer_frais_cartes, charger_config, charger_donnees,
                       comparer_essence_periode, dossier_donnees)
from formats import fmt_eur, fmt_kwh, fmt_nb_recharges
from theme_qt import ALERTE_TEXTE, VERT

LIEUX = ["Tout", "Maison", "Extérieur"]
FORMATS = {
    "excel": ("Exporter en Excel", ".xlsx", "Excel (*.xlsx)", exporter_excel),
    "pdf": ("Exporter en PDF", ".pdf", "PDF (*.pdf)", exporter_pdf),
}


# ---------- calculs (sans interface) ----------

def recharges_a_exporter(toutes: list[dict], lieu: str,
                         periode: str) -> list[dict]:
    if lieu == "Maison":
        choisies = [r for r in toutes if r.get("lieu") == "maison"]
    elif lieu == "Extérieur":
        choisies = [r for r in toutes if r.get("lieu") == "exterieur"]
    else:
        choisies = list(toutes)
    return filtrer_par_periode(choisies, periode)


def complements(toutes: list[dict], lieu: str, periode: str,
                conso: dict | None = None,
                calcul_abonnement=calculer_abonnement,
                calcul_frais=calculer_frais_cartes,
                calcul_essence=None) -> dict:
    """Ce que les exports ajoutent aux recharges (28/09/2026) :

    - « abonnement » : l'abonnement electrique de la periode, compte comme
      au tableau de bord (mois entiers, jamais au-dela du mois en cours).
      Rien pour un export des seules recharges exterieures : c'est
      l'abonnement du compteur de la maison.
    - « km » : distance, cout et cout aux 100 km, sur les intervalles entre
      deux releves du compteur qui tiennent ENTIERS dans la periode (un
      intervalle n'est jamais coupe a une date du calendrier). Seulement
      pour « Tout » les lieux : le calcul prend toutes les recharges de
      l'intervalle. Rien sans energie : « 0,00 €/100 km » ferait croire que
      rouler ne coute rien.
    - « frais_cartes » : les frais des cartes de recharge de la periode
      (achats, abonnements). Rien pour un export des seules recharges a la
      maison.

    - « essence » : la comparaison avec une voiture essence
      (recharges.comparer_essence_periode), pour « Tout » ou une annee, et
      seulement pour tous les lieux : elle compare TOUTES les recharges aux
      kilometres parcourus.

    `conso`, `calcul_abonnement`, `calcul_frais` et `calcul_essence` ne
    sont remplaces que par les tests."""
    bornes = bornes_periode(periode, toutes)
    abonnement = None
    if lieu != "Extérieur" and bornes and bornes[1] >= bornes[0]:
        total = calcul_abonnement(*bornes)["total"]
        abonnement = total if total else None

    km = None
    if lieu == "Tout":
        if conso is None:
            conso = calculer_consommation()
        intervalles = conso["intervalles"]
        if periode != "Tout":
            intervalles = [
                i for i in intervalles if bornes
                and bornes[0].isoformat() <= i["debut"][:10]
                and i["fin"][:10] <= bornes[1].isoformat()]
        distance = sum(i["km"] for i in intervalles)
        energie = sum(i["kwh"] for i in intervalles)
        if distance > 0 and energie > 0:
            cout = round(sum(i["cout"] for i in intervalles), 2)
            km = {"debut": intervalles[0]["debut"],
                  "fin": intervalles[-1]["fin"],
                  "km": round(distance, 1), "cout": cout,
                  "cout_100": round(100 * cout / distance, 2)}
    frais = None
    bornes_f = bornes_frais(periode, toutes)
    if lieu != "Maison" and bornes_f and bornes_f[1] >= bornes_f[0]:
        frais = calcul_frais(*bornes_f)["total"] or None
    essence = None
    if lieu == "Tout":
        if calcul_essence is None:
            calcul_essence = lambda p: comparer_essence_periode(  # noqa: E731
                p, charger_config())
        essence = calcul_essence(periode)
    return {"abonnement": abonnement, "km": km, "frais_cartes": frais,
            "essence": essence}


def libelle_export(lieu: str, periode: str) -> str:
    """En-tete du fichier : le lieu et la periode, avec le nom que montre
    l'ecran (« Toute la periode », et non la valeur interne « Tout »)."""
    return (f"{NOMS_LIEUX.get(lieu, lieu)} · "
            f"{NOMS_AFFICHES.get(periode, periode)}")


def nom_propose(lieu: str, extension: str, jour: date | None = None) -> str:
    """« recharges_maison_20260925.xlsx »."""
    jour = jour or date.today()
    return f"recharges_{lieu.lower()}_{jour:%Y%m%d}{extension}"


# ---------- affichage ----------

def construire(fenetre) -> QWidget:
    toutes = charger_donnees()["recharges"]
    lieu, periode = fenetre.filtre_lieu_export, fenetre.filtre_periode_export
    choisies = recharges_a_exporter(toutes, lieu, periode)

    page = QWidget()
    colonne = QVBoxLayout(page)
    colonne.setContentsMargins(0, 0, 0, 0)
    colonne.setSpacing(12)

    cadre, corps = carte("Que voulez-vous exporter ?")
    ligne = QHBoxLayout()
    libelle = QLabel("Lieu :")
    libelle.setObjectName("LibellePeriode")
    ligne.addWidget(libelle)
    choix_lieu = QComboBox()
    for valeur in LIEUX:
        choix_lieu.addItem(NOMS_LIEUX.get(valeur, valeur), valeur)
    choix_lieu.setCurrentIndex(max(0, choix_lieu.findData(lieu)))
    # Le lieu change l'apercu : la page se reconstruit, comme pour la
    # periode.
    choix_lieu.currentIndexChanged.connect(
        lambda _i: fenetre.changer_periode("filtre_lieu_export",
                                           choix_lieu.currentData()))
    ligne.addWidget(choix_lieu)
    ligne.addSpacing(16)
    barre = BarrePeriode(toutes, periode)
    barre.periode_changee.connect(
        lambda v: fenetre.changer_periode("filtre_periode_export", v))
    ligne.addWidget(barre)
    ligne.addStretch(1)
    corps.addLayout(ligne)
    kwh = sum(r.get("kwh", 0) for r in choisies)
    cout = sum(r.get("cout_eur", 0) for r in choisies)
    apercu = QLabel(f"{fmt_nb_recharges(len(choisies))} · {fmt_kwh(kwh)} · "
                    f"{fmt_eur(cout)}")
    apercu.setObjectName("Resume")
    corps.addWidget(apercu)
    colonne.addWidget(cadre)
    page.choix_lieu, page.barre, page.apercu = choix_lieu, barre, apercu

    resultat = QLabel("")
    resultat.setWordWrap(True)
    resultat.hide()

    cadre, corps = carte("Format")
    ligne = QHBoxLayout()
    page.boutons = {}
    for fmt, texte in (("excel", "📊 Exporter en Excel (.xlsx)"),
                       ("pdf", "📄 Exporter en PDF")):
        bouton = QPushButton(texte)
        bouton.setObjectName("BoutonEnregistrer")
        bouton.clicked.connect(
            lambda _=False, f=fmt: exporter(fenetre, f, resultat))
        ligne.addWidget(bouton, 1)
        page.boutons[fmt] = bouton
    corps.addLayout(ligne)
    corps.addWidget(paragraphe(
        "Excel = tableau complet détaillé (2 feuilles).  PDF = rapport "
        "imprimable : synthèse, puis la liste des recharges. Les deux "
        "donnent aussi l'abonnement de la période et, pour tous les lieux, "
        "le coût aux 100\xa0km entre vos relevés du compteur.", "Discret"))
    colonne.addWidget(cadre)
    colonne.addWidget(resultat)
    page.resultat = resultat
    colonne.addStretch(1)
    return page


def exporter(fenetre, fmt: str, resultat: QLabel) -> None:
    lieu, periode = fenetre.filtre_lieu_export, fenetre.filtre_periode_export
    toutes = charger_donnees()["recharges"]
    recharges = recharges_a_exporter(toutes, lieu, periode)

    def dire(texte: str, ok: bool) -> None:
        resultat.setText(texte)
        resultat.setStyleSheet(f"color: {VERT if ok else ALERTE_TEXTE};")
        resultat.show()

    if not recharges:
        dire("Aucune recharge à exporter.", False)
        return
    titre, extension, filtre, fabriquer = FORMATS[fmt]
    propose = str(Path(dossier_donnees()) / nom_propose(lieu, extension))
    chemin, _ = QFileDialog.getSaveFileName(fenetre, titre, propose, filtre)
    if not chemin:
        return
    try:
        fichier = Path(fabriquer(recharges, chemin,
                                 libelle_export(lieu, periode),
                                 complements=complements(toutes, lieu,
                                                         periode)))
    except Exception as e:      # noqa: BLE001
        # Fichier ouvert dans Excel, disque plein, bibliotheque absente de
        # l'exe... : le dire plutot que de laisser croire que c'est fait.
        dire(f"Erreur : {erreur_en_clair(e)}", False)
        return
    if fmt == "excel":
        dire(f"OK : {fmt_nb_recharges(len(recharges))} "
             f"{'exportées' if len(recharges) > 1 else 'exportée'} vers "
             f"{fichier.name}",
             True)
    else:
        dire(f"OK : rapport PDF généré -> {fichier.name}", True)
