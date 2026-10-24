"""Le tableau de bord (version PySide6) : chiffres cles de la periode choisie.

Reprise de l'ancienne page vues/dashboard.py. Les calculs sont a part, sans interface
(chiffres_de_la_periode, cout_des_kilometres) : ils se testent sans fenetre,
et l'affichage ne fait que les mettre en page, dans le style du Bilan de
Pecule (tuiles a trait de couleur, cartes a en-tete bleute).
"""

from __future__ import annotations

from datetime import date

from PySide6.QtWidgets import (QGridLayout, QHBoxLayout, QLabel, QVBoxLayout,
                               QWidget)

import sauvegarde_externe
from composants import (bandeau_alerte, bandeau_info, carte, paragraphe,
                        tableau, tuile)
from constantes import COLONNES_HISTORIQUE
from pages.historique import cellules
from filtres import (bornes_frais, bornes_periode, conseil_si_vide,
                     filtrer_par_periode)
from pages.periode import BarrePeriode
from recharges import (calculer_abonnement, calculer_consommation,
                       calculer_frais_cartes, charger_config,
                       comparer_essence_periode,
                       charger_donnees, charger_releves_km, charger_tarifs,
                       rappel_prix_essence, rappel_releve_km)
from formats import fmt_date_fr, fmt_eur, fmt_kwh, fmt_nb_recharges, fmt_prix_kwh
from theme_qt import BLEU_NUIT, ENCRE


# ---------- calculs (sans interface) ----------

def chiffres_de_la_periode(toutes: list[dict], periode: str) -> dict:
    """Tout ce que la page affiche pour une periode, deja calcule."""
    recharges = filtrer_par_periode(toutes, periode)
    total_kwh = sum(r.get("kwh", 0) for r in recharges)
    total_cout = sum(r.get("cout_eur", 0) for r in recharges)

    maison = [r for r in recharges if r.get("lieu") == "maison"]
    ext = [r for r in recharges if r.get("lieu") == "exterieur"]
    kwh_m = sum(r.get("kwh", 0) for r in maison)
    kwh_hc = sum(r.get("kwh_hc", 0) for r in maison)
    kwh_e = sum(r.get("kwh", 0) for r in ext)
    cout_e = sum(r.get("cout_eur", 0) for r in ext)

    # Abonnement : indicateur a part, JAMAIS inclus dans le cout des recharges
    # ni le prix/kWh. Il couvre toute la periode choisie (le mois entier quand
    # un mois est affiche, meme s'il n'est pas fini), car il est du que l'on
    # recharge ou non.
    abonnement = None
    bornes = bornes_periode(periode, toutes)
    if bornes and bornes[1] >= bornes[0]:
        abonnement = calculer_abonnement(*bornes)
    # La part de l'abonnement que l'utilisateur attribue a la voiture
    # (10/10/2026) : a part elle aussi, jamais dans le cout des recharges.
    part_voiture = None
    pct = charger_config()["part_abonnement_voiture"]
    if abonnement and abonnement["total"] and pct:
        part_voiture = {"pct": pct,
                        "montant": round(abonnement["total"] * pct / 100, 2)}
    # Les frais des cartes de recharge (28/09/2026) : a part eux aussi, et
    # sur « Tout » y compris ceux d'avant la premiere recharge.
    frais_cartes = 0.0
    bornes_f = bornes_frais(periode, toutes)
    if bornes_f and bornes_f[1] >= bornes_f[0]:
        frais_cartes = calculer_frais_cartes(*bornes_f)["total"]

    return {
        "n": len(recharges),
        "kwh": total_kwh,
        "cout": total_cout,
        "prix_moyen": total_cout / total_kwh if total_kwh else 0,
        "maison": {"n": len(maison), "kwh": kwh_m,
                   "cout": sum(r.get("cout_eur", 0) for r in maison),
                   "pct_hc": 100 * kwh_hc / kwh_m if kwh_m else 0,
                   "abonnement": abonnement,
                   "part_voiture": part_voiture},
        "exterieur": {"n": len(ext), "kwh": kwh_e, "cout": cout_e,
                      "prix": cout_e / kwh_e if kwh_e else 0,
                      "frais_cartes": frais_cartes},
        "dernieres": sorted(recharges, key=lambda r: r.get("date", ""),
                            reverse=True)[:5],
    }


def cout_des_kilometres() -> dict | None:
    """Le cout du kilometre en recharges enregistrees, ou None s'il ne peut pas se calculer.

    ATTENTION, il ne suit PAS la periode choisie, et c'est voulu : il se
    calcule entre deux releves du compteur, pas entre deux dates du
    calendrier. Rien tant qu'il n'y a pas deux releves (pas de distance),
    ni si aucune recharge ne tombe entre eux (« 0,00 €/100 km » ferait croire
    que rouler ne coute rien)."""
    conso = calculer_consommation()
    if conso["n_releves"] < 2 or not conso["km"] or not conso["kwh"]:
        return None
    releves = charger_releves_km()
    part = None
    # Des recharges echappent au comptage : on le dit, sans afficher une
    # consommation en kWh qui, elle, serait faussee (la page Kilometrage
    # l'explique). Le cout ne compte que les recharges saisies.
    if conso["controle"]["verdict"] == "energie_exterieure":
        part = abs(conso["controle"]["ecart_pct"])
    # La meme distance avec une voiture essence, si l'utilisateur a saisi
    # sa consommation et le prix du litre dans Parametres (28/09/2026).
    essence = comparer_essence_periode("Tout", charger_config())
    return {"cout_100": conso["cout_100"], "km": conso["km"],
            "debut": releves[0]["date"], "fin": releves[-1]["date"],
            "part_exterieure": part,
            "essence_100": essence["cout_100_essence"] if essence else None}


def rappel_de_sauvegarde(toutes: list[dict], config: dict,
                         aujourd_hui: date | None = None) -> str | None:
    """Le rappel de sauvegarde externe, commun aux trois applications
    (sauvegarde_externe.rappel_sauvegarde_externe). Sans sauvegarde jamais
    faite, on compte depuis la premiere recharge : l'application sert
    depuis ce jour-la."""
    dates = [r["date"] for r in toutes if r.get("date")]
    return sauvegarde_externe.rappel_sauvegarde_externe(
        config.get("sauvegarde_externe_derniere"),
        min(dates) if dates else None, aujourd_hui)


def rappel_tarif_manquant(tarifs: list[dict]) -> str:
    """Le bandeau du premier lancement : sans tarif, le cout des recharges
    a la maison ne peut pas etre calcule (audit du 08/10/2026 : on ne
    l'apprenait qu'en enregistrant une recharge)."""
    if tarifs:
        return ""
    # Le même emoji que le bouton du menu (⚡ depuis le 11/10/2026 : 💶 est
    # « Synthèse financière » dans le Photovoltaïque).
    return ("⚡ Aucun tarif d'électricité pour l'instant : le coût de vos "
            "recharges à la maison ne peut pas être calculé. Saisissez le "
            "prix du kWh de votre contrat dans « ⚡ Tarifs », à gauche.")


# ---------- affichage ----------

def construire(fenetre) -> QWidget:
    toutes = charger_donnees()["recharges"]
    periode = fenetre.filtre_periode_dashboard
    c = chiffres_de_la_periode(toutes, periode)

    page = QWidget()
    colonne = QVBoxLayout(page)
    colonne.setContentsMargins(0, 0, 0, 0)
    colonne.setSpacing(12)

    barre = BarrePeriode(toutes, periode)
    barre.periode_changee.connect(
        lambda v: fenetre.changer_periode("filtre_periode_dashboard", v))
    colonne.addWidget(barre)
    page.barre = barre                      # pour les tests

    # Rappel doux : le compteur n'a pas ete releve depuis longtemps. Pas de
    # couleur d'alerte : ce n'est pas une erreur.
    rappel = rappel_releve_km()
    if rappel:
        colonne.addWidget(bandeau_info(f"🚗 {rappel}"))
    # Meme douceur pour le prix du litre de la comparaison essence.
    rappel = rappel_prix_essence()
    if rappel:
        colonne.addWidget(bandeau_info(f"⛽ {rappel}"))
    # Sans tarif, rien a la maison ne se chiffre : en orange, c'est a faire.
    rappel = rappel_tarif_manquant(charger_tarifs())
    if rappel:
        colonne.addWidget(bandeau_alerte(rappel))

    grille = QGridLayout()
    grille.setSpacing(8)
    page.tuiles = []
    for i, (libelle, valeur, couleur) in enumerate((
            ("RECHARGES", str(c["n"]), BLEU_NUIT),
            ("ÉNERGIE TOTALE", fmt_kwh(c["kwh"]), BLEU_NUIT),
            ("COÛT RECHARGES", fmt_eur(c["cout"]), BLEU_NUIT),
            # Sans recharge, pas de prix : un tiret, et non « 0,0000 €/kWh »
            # (audit de design du 03/10/2026).
            ("PRIX MOYEN",
             fmt_prix_kwh(c["prix_moyen"]) if c["n"] else "—",
             BLEU_NUIT))):
        t = tuile(libelle, valeur, couleur)
        grille.addWidget(t, 0, i)
        grille.setColumnStretch(i, 1)
        page.tuiles.append(t)
    colonne.addLayout(grille)

    km = cout_des_kilometres()
    if km:
        colonne.addWidget(_bande_cout_km(km))

    blocs = QHBoxLayout()
    blocs.setSpacing(8)
    m = c["maison"]
    lignes_m = ([f"{m['pct_hc']:.1f}".replace(".", ",")
                 + "\xa0% de ces kWh en heures creuses"] if m["n"] else [])
    if m["abonnement"]:
        jours = m["abonnement"]["jours"]
        lignes_m.append(f"Abonnement {fmt_eur(m['abonnement']['total'])} sur "
                        f"{jours} jour{'s' if jours > 1 else ''} "
                        "(hors recharges)")
        if m["part_voiture"]:
            lignes_m.append(ligne_part_voiture(m["part_voiture"]))
    blocs.addWidget(_bloc_lieu("Maison", m["n"], m["kwh"], m["cout"],
                               lignes_m, BLEU_NUIT), 1)
    e = c["exterieur"]
    lignes_e = [ligne_prix_moyen(e["n"], e["prix"])]
    if e["frais_cartes"]:
        lignes_e.append(f"Frais de cartes {fmt_eur(e['frais_cartes'])} "
                        "(hors recharges)")
    blocs.addWidget(_bloc_lieu("Extérieur", e["n"], e["kwh"], e["cout"],
                               lignes_e, BLEU_NUIT), 1)
    colonne.addLayout(blocs)

    # La sauvegarde externe (28/09/2026), elle, est en orange d'alerte, comme
    # dans Pecule et le Photovoltaique (29/09/2026) : des donnees sans copie
    # hors de l'ordinateur peuvent etre perdues. Placee juste avant
    # « Dernieres recharges » (17/10/2026, demande d'Andre) pour laisser les
    # chiffres de la periode en tete de page.
    rappel = rappel_de_sauvegarde(toutes, charger_config())
    if rappel:
        colonne.addWidget(bandeau_alerte(f"💾 {rappel}"))

    cadre, corps = carte("Dernières recharges")
    if not c["dernieres"]:
        corps.addWidget(paragraphe(
            ("Aucune recharge pour l'instant.\n" + conseil_si_vide(True))
            if not toutes else
            ("Aucune recharge sur cette période.\n" + conseil_si_vide(False)),
            "Discret"))
    else:
        # Les colonnes de l'Historique : un tableau, et non plus des lignes
        # en caracteres de largeur fixe (audit de design du 03/10/2026).
        corps.addWidget(tableau(
            [titre for _, titre in COLONNES_HISTORIQUE],
            [cellules(r) for r in c["dernieres"]], a_droite=(2, 3, 4),
            etirer=5))
    colonne.addWidget(cadre)
    colonne.addStretch(1)
    return page


def ligne_part_voiture(part: dict) -> str:
    """« dont part de la voiture (32 %) : 6,40 € », sous l'abonnement."""
    pct = f"{part['pct']:g}".replace(".", ",")
    return (f"dont part de la voiture ({pct}\xa0%) : "
            f"{fmt_eur(part['montant'])}")


def ligne_prix_moyen(n: int, prix: float) -> str:
    """« Prix moyen : 0,5000 €/kWh », ou un tiret sans recharge."""
    return f"Prix moyen : {fmt_prix_kwh(prix) if n else '—'}"


def _bloc_lieu(titre: str, n: int, kwh: float, cout: float,
               lignes: list[str], couleur: str):
    """Bloc « Maison » ou « Extérieur » : nombre, energie, cout en gros,
    puis les precisions."""
    cadre, corps = carte(titre)
    corps.addWidget(QLabel(f"{fmt_nb_recharges(n)} · {fmt_kwh(kwh)}"))
    montant = QLabel(fmt_eur(cout))
    montant.setObjectName("GrandeValeur")
    # Un montant nul s'ecrit sans couleur (charte) : la couleur ferait
    # croire a une depense.
    montant.setStyleSheet(f"color: {couleur if cout else ENCRE};")
    corps.addWidget(montant)
    for ligne in lignes:
        corps.addWidget(paragraphe(ligne, "Discret"))
    return cadre


def _bande_cout_km(km: dict):
    """Le cout du kilometre en recharges enregistrees, sous les tuiles et non parmi elles : il ne
    suit pas la periode, et son intitule comme sa derniere ligne le disent."""
    # « Coût réel » promettait un cout complet ; il ne compte que les
    # recharges enregistrees (analyse du 16/10/2026).
    cadre, corps = carte("Coût de vos recharges aux 100\xa0km")
    valeur = QLabel(f"{km['cout_100']:.2f}\xa0€/100\xa0km".replace(".", ","))
    valeur.setObjectName("GrandeValeur")
    valeur.setStyleSheet(f"color: {BLEU_NUIT};")
    corps.addWidget(valeur)
    distance = f"{km['km']:,.0f}".replace(",", "\xa0")
    corps.addWidget(paragraphe(
        f"Du {fmt_date_fr(km['debut'])[:10]} au {fmt_date_fr(km['fin'])[:10]}, "
        f"sur {distance}\xa0km parcourus, pour vos recharges enregistrées "
        "(abonnement et frais de cartes non compris).", "Discret"))
    if km.get("essence_100") is not None:
        corps.addWidget(paragraphe(
            "Avec une voiture essence : "
            + f"{km['essence_100']:.2f}\xa0€/100\xa0km".replace(".", ",")
            + " (détail dans la page « Essence ou électrique ? »).",
            "Discret"))
    corps.addWidget(paragraphe(
        "Ce chiffre se calcule entre vos relevés du compteur : il ne suit pas "
        "la période affichée.", "Discret"))
    if km["part_exterieure"] is not None:
        corps.addWidget(paragraphe(
            # Une estimation, dont l'origine et le prix ne sont pas connus :
            # elle n'est pas forcement gratuite (audit du 14/10/2026).
            f"Selon une estimation, environ {km['part_exterieure']:.0f}\xa0% de "
            "votre énergie viendrait de recharges non enregistrées, dont "
            "l'origine et le prix ne sont pas connus : ce coût ne compte que "
            "vos recharges saisies. Voir la page Kilométrage.", "Discret"))
    return cadre
