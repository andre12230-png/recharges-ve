"""Les Statistiques (version PySide6) : graphique par mois et repartitions.

Reprise de l'ancienne page vues/stats.py. Les calculs sont a part, sans interface
(par_mois, repartitions, ecart_wallbox) : ils se testent sans fenetre.
La barre de periode n'offre que l'annee : le graphique compare les mois
d'une annee, choisir un mois n'y a aucun interet (demande de l'auteur,
23/09/2026).
"""

from __future__ import annotations

from collections import defaultdict

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QGridLayout, QHBoxLayout, QLabel, QVBoxLayout,
                               QWidget)

from composants import carte, paragraphe
from filtres import (MOIS_FR, agreger_par, conseil_si_vide, filtrer_par_periode,
                     mois_continus, texte_resume)
from pages.periode import BarrePeriode
from recharges import charger_donnees
from formats import fmt_eur, fmt_kwh, fmt_nb_recharges, fmt_prix_kwh
from theme_qt import ALERTE_TEXTE, ENCRE, VERT


# ---------- calculs (sans interface) ----------

def par_mois(recharges: list[dict]) -> tuple[list[str], list[float],
                                             list[float]]:
    """Les mois (« AAAA-MM »), l'energie et le cout de chacun.

    Les mois sans aucune recharge figurent a zero : sinon deux mois
    eloignes se retrouvent cote a cote et la courbe laisse croire a une
    consommation continue."""
    kwh: dict[str, float] = defaultdict(float)
    cout: dict[str, float] = defaultdict(float)
    for r in recharges:
        m = r.get("date", "")[:7]
        kwh[m] += r.get("kwh", 0)
        cout[m] += r.get("cout_eur", 0)
    mois = mois_continus(sorted(kwh))
    return mois, [kwh[m] for m in mois], [cout[m] for m in mois]


def repartitions(recharges: list[dict]) -> list[tuple[str, list]]:
    """Les trois repartitions, chacune du poste le plus cher au moins cher :
    [(titre, [(nom, texte des chiffres), ...]), ...]. Une repartition sans
    rien n'est pas rendue."""
    blocs = (
        ("Répartition par tarif",
         agreger_par(recharges, "tarif_nom", "maison", "?")),
        ("Répartition par opérateur (extérieur)",
         agreger_par(recharges, "operateur", "exterieur")),
        ("Répartition par carte / moyen de paiement (extérieur)",
         agreger_par(recharges, "carte", "exterieur", "Non précisé")),
    )
    resultat = []
    for titre, agregats in blocs:
        if not agregats:
            continue
        lignes = []
        for nom, a in sorted(agregats.items(), key=lambda x: -x[1]["cout"]):
            moyen = a["cout"] / a["kwh"] if a["kwh"] else 0
            lignes.append((nom, f"{fmt_nb_recharges(a['n'])} · "
                                f"{fmt_kwh(a['kwh'])} · {fmt_eur(a['cout'])}"
                                f" · {fmt_prix_kwh(moyen)}"))
        resultat.append((titre, lignes))
    return resultat


def ecart_wallbox(recharges: list[dict]) -> dict | None:
    """Le cout annonce par la wallbox face au cout calcule sur le tarif
    reel, pour les recharges a la maison QU'ELLE A CHIFFREES (celles
    importees de son CSV). None si la wallbox n'a rien annonce sur la
    periode.

    Jusqu'a la v2.0.0, le cout reel comptait aussi les recharges saisies a
    la main, que la wallbox n'a jamais chiffrees : des qu'une periode
    melait les deux, l'ecart etait faux, et souvent de signe inverse."""
    chiffrees = [r for r in recharges
                 if r.get("lieu") == "maison" and "cout_wallbox" in r]
    wallbox = sum(r["cout_wallbox"] for r in chiffrees)
    if not wallbox:
        return None
    reel = sum(r.get("cout_eur", 0) for r in chiffrees)
    return {"wallbox": wallbox, "reel": reel, "ecart": reel - wallbox,
            "n": len(chiffrees)}


# ---------- affichage ----------

def construire(fenetre) -> QWidget:
    toutes = charger_donnees()["recharges"]
    periode = fenetre.filtre_periode_stats
    recharges = filtrer_par_periode(toutes, periode)

    page = QWidget()
    colonne = QVBoxLayout(page)
    colonne.setContentsMargins(0, 0, 0, 0)
    colonne.setSpacing(12)

    ligne = QHBoxLayout()
    barre = BarrePeriode(toutes, periode, annuel=True)
    barre.periode_changee.connect(
        lambda v: fenetre.changer_periode("filtre_periode_stats", v))
    ligne.addWidget(barre)
    ligne.addSpacing(16)
    # Memes chiffres que l'Historique (voir texte_resume).
    resume = QLabel(texte_resume(recharges).strip())
    resume.setObjectName("Resume")
    # Sur deux lignes quand la place manque : a 1 000 px, il faisait
    # deborder la page de 132 px (second audit du 16/10/2026).
    resume.setWordWrap(True)
    ligne.addWidget(resume, 1)
    colonne.addLayout(ligne)
    page.barre, page.resume = barre, resume          # pour les tests

    if not recharges:
        vide = paragraphe(
            ("Aucune recharge pour l'instant.\n" + conseil_si_vide(True))
            if not toutes else
            (f"Aucune donnée sur la période « {periode} ».\n"
             + conseil_si_vide(False)),
            "Discret")
        vide.setAlignment(Qt.AlignCenter)
        vide.setContentsMargins(0, 40, 0, 40)
        colonne.addWidget(vide)
        colonne.addStretch(1)
        return page

    cadre, corps = carte("Énergie et coût par mois")
    # Importe ici, et non en tete : voir graphique.py.
    from graphique import GraphiqueMois
    from graphique import mois_en_cours_affiche
    mois_du_graphique = par_mois(recharges)
    page.graphique = GraphiqueMois(*mois_du_graphique)
    corps.addWidget(page.graphique)
    # Charte : une periode incomplete est hachuree, et une note le dit.
    en_cours = mois_en_cours_affiche(mois_du_graphique[0])
    if en_cours is not None:
        nom = f"{MOIS_FR[int(en_cours[5:7]) - 1]} {en_cours[:4]}"
        corps.addWidget(paragraphe(
            f"{nom} n'est pas terminé : sa barre est hachurée, ses chiffres "
            "vont encore augmenter.", "Discret"))
    colonne.addWidget(cadre)

    page.repartitions = []
    for titre, lignes in repartitions(recharges):
        cadre, corps = carte(titre)
        grille = QGridLayout()
        grille.setHorizontalSpacing(16)
        grille.setVerticalSpacing(6)
        grille.setColumnStretch(0, 1)
        for i, (nom, chiffres) in enumerate(lignes):
            etiquette = QLabel(nom)
            etiquette.setObjectName("NomRepartition")
            grille.addWidget(etiquette, i, 0)
            valeur = QLabel(chiffres)
            valeur.setObjectName("Discret")
            grille.addWidget(valeur, i, 1, Qt.AlignRight)
        corps.addLayout(grille)
        colonne.addWidget(cadre)
        page.repartitions.append(cadre)

    ecart = ecart_wallbox(recharges)
    if ecart:
        # « Votre borne », et une phrase qui dit qui est le moins cher : la
        # carte affichait « Écart : -24,76 € » en vert, sans dire dans quel
        # sens (audit de design du 03/10/2026).
        cadre, corps = carte("Votre borne face au tarif réel")
        # Ce qui est compare : les seules recharges importees de son CSV.
        if ecart["n"] > 1:
            portee = (f"Sur les {ecart['n']} recharges dont votre borne a "
                      "affiché le coût :")
        else:
            portee = "Sur la recharge dont votre borne a affiché le coût :"
        corps.addWidget(QLabel(portee))
        corps.addWidget(QLabel(
            f"Coût affiché par la borne : {fmt_eur(ecart['wallbox'])}   ·   "
            f"Coût selon votre tarif réel : {fmt_eur(ecart['reel'])}"))
        difference = abs(ecart["ecart"])
        if difference < 0.005:
            phrase, couleur = "Même coût que l'estimation de votre borne.", ENCRE
        elif ecart["ecart"] < 0:
            phrase = (f"{fmt_eur(difference)} de moins que l'estimation de "
                      "votre borne")
            couleur = VERT
        else:
            phrase = (f"{fmt_eur(difference)} de plus que l'estimation de "
                      "votre borne")
            couleur = ALERTE_TEXTE
        valeur = QLabel(phrase)
        valeur.setObjectName("GrandeValeur")
        valeur.setWordWrap(True)
        # La couleur souligne, la phrase dit le sens : vert quand le tarif
        # reel coute moins que ce qu'annonce la borne.
        valeur.setStyleSheet(f"color: {couleur};")
        corps.addWidget(valeur)
        colonne.addWidget(cadre)
        page.wallbox = cadre

    colonne.addStretch(1)
    return page
