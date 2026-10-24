"""Le Kilometrage (version PySide6) : releves du compteur, consommation
reelle, et part d'energie non enregistree.

Reprise de l'ancienne page vues/km.py. Les textes qui dependent des chiffres sont composes a
part, sans interface (textes_controle, cellules_intervalle, cellules_releve,
message_enregistre) : ils se testent sans fenetre.
"""

from __future__ import annotations

from datetime import datetime

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (QDialog, QGridLayout, QHBoxLayout, QLabel,
                               QLineEdit, QMessageBox, QPushButton,
                               QVBoxLayout, QWidget)

from composants import (carte, confirmer, paragraphe, tableau,
                        texte_a_lire, tuile)
from dialogue_km_frais import DialogueReleve
from erreurs import erreur_en_clair
from formulaire import exiger
from recharges import (ajouter_releve_km, calculer_consommation,
                       charger_config, charger_releves_km,
                       comparer_essence_periode, supprimer_releve_km)
from saisie import ErreurSaisie, lire_releve_km
import suivi_saisie
from formats import fmt_date_fr, fmt_eur, fmt_kwh, fmt_nombre, fmt_signe
from theme_qt import (ALERTE_TEXTE, BLEU_NUIT, ENCRE, GRIS_SOUS,
                      ROUGE, VERT)


# ---------- textes (sans interface) ----------

def textes_controle(ctrl: dict) -> dict:
    """Ce que dit la carte « Part d'énergie non enregistrée ».

    L'ecart n'est pas presente comme une faute : une partie des recharges
    (chez des proches, sur des bornes gratuites) n'est pas mesurable. La
    carte dit donc quelle part de l'energie vient d'ailleurs, en la donnant
    pour ce qu'elle est : une estimation. Seul un EXCEDENT reste signale,
    comme un ecart inhabituel a verifier et non comme une impossibilite :
    le calcul repose sur la consommation de reference du dernier releve et
    sur un rendement de charge regle, qui peuvent eux-memes etre faux
    (analyse du 16/10/2026).

    Rend {"invitation"} tant que la consommation affichee par la voiture
    n'a jamais ete notee, sinon {"reference", "detail", "verdict",
    "couleur"}."""
    if ctrl["verdict"] == "non_configure":
        return {"invitation":
                "Indiquez la consommation affichée par votre voiture lors "
                "d'un prochain relevé (case « Consommation affichée » ci-dessus) : "
                "l'application pourra alors estimer la part d'énergie qui "
                "n'est pas passée par vos recharges enregistrées."}
    conso = f"{ctrl['conso_reference']:.1f}".replace(".", ",")
    reference = (f"Référence : {conso}\xa0kWh/100\xa0km, d'après le dernier relevé "
                 "où vous l'avez notée.")
    detail = (f"La voiture a consommé environ {fmt_nombre(ctrl['kwh_batterie'])}\xa0kWh "
              f"à la batterie, soit environ {fmt_nombre(ctrl['kwh_attendu'])}\xa0kWh "
              f"pris à la prise (rendement de charge "
              f"{100 * ctrl['rendement']:.0f}\xa0%).")
    if ctrl["verdict"] == "coherent":
        couleur = VERT
        verdict = (f"Cohérent : l'écart n'est que de {ctrl['ecart_pct']:+.0f}\xa0%. "
                   "Vos recharges semblent toutes enregistrées.")
    elif ctrl["verdict"] == "trop_court":
        if ctrl.get("capacite_batterie"):
            capacite = f"{ctrl['capacite_batterie']:.1f}".replace(".", ",")
            charge = (f"une charge complète de votre batterie ({capacite}\xa0kWh, "
                      f"soit {fmt_nombre(ctrl['marge_kwh'])}\xa0kWh pris à la prise)")
        else:
            charge = f"une charge complète ({fmt_nombre(ctrl['marge_kwh'])}\xa0kWh)"
        couleur = GRIS_SOUS
        verdict = (f"Pas encore assez de recul pour conclure : l'écart "
                   f"({fmt_signe(ctrl['ecart_kwh'])}\xa0kWh) reste inférieur à {charge}. "
                   "Entre deux relevés rapprochés, la voiture roule en partie "
                   "sur de l'énergie chargée avant le premier relevé, ce qui "
                   "suffit à expliquer la différence. Continuez à noter votre "
                   "kilométrage : le contrôle deviendra fiable avec plus de "
                   "recul.")
    elif ctrl["verdict"] == "energie_exterieure":
        couleur = ENCRE
        reelle = f"{ctrl['conso_reference']:.1f}".replace(".", ",")
        connue = f"{ctrl['conso_enregistree']:.1f}".replace(".", ",")
        verdict = (f"Environ {fmt_nombre(abs(ctrl['ecart_kwh']))}\xa0kWh "
                   f"({abs(ctrl['ecart_pct']):.0f}\xa0% de l'énergie consommée) "
                   "viendraient, selon cette estimation, de recharges non "
                   "enregistrées : chez des proches, sur des bornes gratuites, "
                   "ou toute charge dont vous ne connaissez pas les kWh. C'est "
                   "normal si cela vous arrive régulièrement.\n"
                   f"La voiture affiche {reelle}\xa0kWh/100\xa0km, en comptant "
                   "l'énergie arrivée à la batterie ; vos recharges "
                   "enregistrées, ramenées à la batterie de la même façon, "
                   f"n'en expliquent que {connue}.")
    else:
        couleur = ALERTE_TEXTE
        verdict = (f"Écart inhabituel, à vérifier : vos recharges enregistrées "
                   f"dépassent de {fmt_signe(ctrl['ecart_kwh'])}\xa0kWh "
                   f"({ctrl['ecart_pct']:+.0f}\xa0%) ce que la voiture semble "
                   "avoir consommé. Ce calcul repose sur la consommation de "
                   "référence ci-dessus et sur le rendement de charge réglé "
                   "dans « ⚙️ Paramètres ». À vérifier : le kilométrage saisi, "
                   "une énergie mal tapée, la consommation de référence ou le "
                   "rendement de charge.")
    return {"reference": reference, "detail": detail, "verdict": verdict,
            "couleur": couleur}


# Les colonnes des deux tableaux (audit de design du 03/10/2026 : c'etaient
# des lignes en caracteres de largeur fixe, avec des fleches « -> » et des
# milliers non separes).
ENTETES_INTERVALLES = ["Du", "Au", "Distance", "Recharges", "Énergie",
                       "Consommation", "Coût aux 100\xa0km"]
# « Parcourus » tout court, le detail au survol (16/10/2026) : l'en-tete
# entier faisait deborder la page a 1 000 px, plus encore avec les deux
# boutons « Modifier… » et « Supprimer » de chaque ligne.
ENTETES_RELEVES = ["Date", "Compteur", "Parcourus", "Consommation affichée"]
INFOBULLE_PARCOURUS = "Distance parcourue depuis le relevé précédent"


def cellules_intervalle(i: dict) -> tuple[str, ...]:
    """Une ligne du « Détail entre chaque relevé ».

    Sans recharge entre deux releves, ni consommation ni cout : un tiret, et
    non « 0,00 €/100 km », qui ferait croire a des kilometres gratuits."""
    sans_recharge = not i["n_recharges"]
    return (fmt_date_fr(i["debut"])[:10],
            fmt_date_fr(i["fin"])[:10],
            f"{fmt_nombre(i['km'])}\xa0km",
            str(i["n_recharges"]),
            fmt_kwh(i["kwh"]),
            "—" if sans_recharge
            else f"{fmt_nombre(i['kwh_100'], 1)}\xa0kWh/100\xa0km",
            "—" if sans_recharge
            else f"{fmt_nombre(i['cout_100'], 2)}\xa0€/100\xa0km")


def cellules_releve(r: dict, ecart: float | None) -> tuple[str, ...]:
    """Une ligne de « Mes relevés ». L'ecart est la distance parcourue
    depuis le releve precedent : il s'affiche sur la ligne du plus RECENT
    des deux, puisque c'est a cette date que la distance a ete atteinte."""
    return (fmt_date_fr(r["date"]),
            f"{fmt_nombre(r['km'])}\xa0km",
            "" if ecart is None else f"+{fmt_nombre(ecart)}\xa0km",
            (f"{fmt_nombre(r['conso'], 1)}\xa0kWh/100\xa0km"
             if r.get("conso") else ""))


def renvoi_essence(c: dict | None) -> str:
    """La phrase qui renvoie a la page « Essence ou électrique ? »."""
    page = "la page « ⛽ Essence ou électrique ? »"
    if c is None:
        return f"Pour comparer avec une voiture essence : {page}."
    if c["economie"] >= 0:
        return (f"Face à une voiture essence, ces kilomètres vous ont fait "
                f"économiser {fmt_eur(c['economie'])} : détail dans {page}.")
    return (f"Face à une voiture essence, ces kilomètres vous ont coûté "
            f"{fmt_eur(-c['economie'])} de plus : détail dans {page}.")


def message_enregistre(r: dict) -> str:
    texte = (f"Relevé enregistré : {r['km']:,.0f}\xa0km au "
             f"{fmt_date_fr(r['date'])}").replace(",", "\xa0")
    if r.get("conso"):
        texte += (f", consommation affichée {r['conso']:.1f}\xa0kWh/100\xa0km"
                  .replace(".", ","))
    return texte


# ---------- affichage ----------

def construire(fenetre) -> QWidget:
    page = QWidget()
    colonne = QVBoxLayout(page)
    colonne.setContentsMargins(0, 0, 0, 0)
    colonne.setSpacing(12)

    colonne.addWidget(_carte_saisie(fenetre, page))

    conso = calculer_consommation()
    releves = charger_releves_km()
    cadre, corps = carte("Consommation réelle")
    if conso["n_releves"] < 2:
        corps.addWidget(paragraphe(
            "Enregistrez un deuxième relevé pour voir votre consommation : le "
            "premier ne sert que de point de départ."
            if conso["n_releves"] == 1 else
            "Aucun relevé pour l'instant. Saisissez ci-dessus le kilométrage "
            "actuel de la voiture pour démarrer.", "Discret"))
        colonne.addWidget(cadre)
    else:
        grille = QGridLayout()
        grille.setSpacing(8)
        # Les intitules disent d'ou vient chaque chiffre : la consommation
        # ne porte que sur l'energie enregistree (les recharges chez des
        # proches ou sur bornes gratuites lui echappent), alors que le cout,
        # lui, est exact puisque cette energie-la ne coute rien.
        page.tuiles = []
        for i, (libelle, valeur, couleur) in enumerate((
                ("DISTANCE PARCOURUE",
                 f"{conso['km']:,.0f}\xa0km".replace(",", "\xa0"), BLEU_NUIT),
                ("ÉNERGIE ENREGISTRÉE", fmt_kwh(conso["kwh"]), BLEU_NUIT),
                # « À la prise » : la voiture, elle, affiche ce qui arrive
                # a la batterie, apres les pertes de charge (audit du
                # 03/10/2026 : 9,2 ici, 8,2 plus bas, sans explication).
                ("CONSOMMATION À LA PRISE",
                 f"{conso['kwh_100']:.1f}\xa0kWh/100\xa0km".replace(".", ","),
                 BLEU_NUIT),
                # Le cout des seules recharges enregistrees : « Coût réel »
                # promettait un cout complet (analyse du 16/10/2026).
                ("COÛT DES RECHARGES",
                 f"{conso['cout_100']:.2f}\xa0€/100\xa0km".replace(".", ","),
                 BLEU_NUIT))):
            t = tuile(libelle, valeur, couleur)
            grille.addWidget(t, 0, i)
            grille.setColumnStretch(i, 1)
            page.tuiles.append(t)
        corps.addLayout(grille)
        corps.addWidget(paragraphe(
            f"Du {fmt_date_fr(releves[0]['date'])[:10]} au "
            f"{fmt_date_fr(releves[-1]['date'])[:10]}, soit "
            f"{fmt_eur(conso['cout'])} de recharges enregistrées (abonnement "
            "et frais de cartes non compris).",
            "Discret"))
        colonne.addWidget(cadre)

        # La comparaison avec une voiture essence a sa page : elle etait
        # repetee ici a l'identique (audit de design du 03/10/2026). Une
        # phrase y renvoie.
        corps.addWidget(paragraphe(renvoi_essence(
            comparer_essence_periode("Tout", charger_config())), "Discret"))
        colonne.addWidget(_carte_controle(conso["controle"]))

        # Les intervalles sans kilometre parcouru (deux releves au meme
        # compteur) n'ont rien a montrer.
        details = [i for i in conso["intervalles"] if i["km"] > 0]
        if len(details) > 1:
            cadre, corps = carte("Détail entre chaque relevé")
            corps.addWidget(tableau(
                ENTETES_INTERVALLES,
                [cellules_intervalle(i) for i in reversed(details)],
                a_droite=(2, 3, 4, 5, 6)))
            colonne.addWidget(cadre)

    colonne.addWidget(_carte_releves(fenetre, releves))
    colonne.addStretch(1)
    return page


def _carte_saisie(fenetre, page) -> QWidget:
    """« Nouveau relevé » : deux lignes de cases, puis UNE ligne de message.

    Une seule ligne de message pour les quatre cases : elles sont cote a
    cote, un message sous chacune ferait sauter la mise en page. Elle sert
    au succes (en vert, apres reconstruction de la page) comme a l'erreur
    (en rouge, sans reconstruire : ce qui est tape reste a corriger)."""
    cadre, corps = carte("Nouveau relevé")
    formulaire = QWidget()
    formulaire.setObjectName("Formulaire")      # le style des cases de saisie
    dedans = QVBoxLayout(formulaire)
    dedans.setContentsMargins(0, 0, 0, 0)
    dedans.setSpacing(8)

    maintenant = datetime.now()
    cases = {}

    def case(nom, largeur, texte="", invite=""):
        c = QLineEdit(texte)
        c.setFixedWidth(largeur)
        c.setPlaceholderText(invite)
        cases[nom] = c
        return c

    def libelle(texte):
        e = QLabel(texte)
        e.setObjectName("LibelleChamp")
        return e

    # Deux lignes plutot qu'une : sur un portable (fenetre de 1000 px), tout
    # ne tenait pas cote a cote.
    ligne1 = QHBoxLayout()
    ligne1.setSpacing(6)
    ligne1.addWidget(libelle("Date :"))
    ligne1.addWidget(case("champ_km_date_jour", 120,
                          maintenant.strftime("%d/%m/%Y"), "jj/mm/aaaa"))
    ligne1.addWidget(libelle("à"))
    ligne1.addWidget(case("champ_km_date_heure", 80,
                          maintenant.strftime("%H:%M"), "hh:mm"))
    ligne1.addSpacing(18)
    ligne1.addWidget(libelle("Kilométrage actuel :"))
    ligne1.addWidget(case("champ_km_valeur", 110))
    ligne1.addWidget(libelle("km"))
    ligne1.addStretch(1)
    dedans.addLayout(ligne1)

    # La consommation affichee par la voiture, lue sur le meme ecran que le
    # compteur : elle sert de reference a la carte « Part d'énergie ».
    ligne2 = QHBoxLayout()
    ligne2.setSpacing(6)
    ligne2.addWidget(libelle("Consommation affichée :"))
    ligne2.addWidget(case("champ_km_conso", 80))
    ligne2.addWidget(libelle("kWh/100\xa0km"))
    ligne2.addSpacing(18)
    bouton = QPushButton("Enregistrer")
    bouton.setObjectName("BoutonEnregistrer")
    ligne2.addWidget(bouton)
    ligne2.addStretch(1)
    dedans.addLayout(ligne2)

    message = QLabel(fenetre.message_km)
    message.setWordWrap(True)
    message.setTextInteractionFlags(Qt.TextSelectableByMouse)
    message.setStyleSheet(f"color: {VERT};")
    message.setVisible(bool(fenetre.message_km))    # cachee tant que vide
    fenetre.message_km = ""                 # affiche une fois
    dedans.addWidget(message)
    corps.addWidget(formulaire)

    # Le kilometrage est la seule case exigee : encadree de bleu tant
    # qu'elle est vide (la date vide vaut « maintenant »).
    exiger([cases["champ_km_valeur"]])
    suivi_saisie.nommer(cases)          # reportees si la page se reconstruit
    page.cases_km, page.message_km, page.bouton_km = cases, message, bouton
    enregistrer = lambda: enregistrer_releve(fenetre, cases, message)  # noqa: E731
    bouton.clicked.connect(enregistrer)
    # Entree enregistre depuis n'importe laquelle des quatre cases.
    for c in cases.values():
        c.returnPressed.connect(enregistrer)
    return cadre


def enregistrer_releve(fenetre, cases: dict, message: QLabel) -> None:
    def erreur(nom: str, texte: str) -> None:
        message.setText(texte)
        message.setStyleSheet(f"color: {ROUGE};")
        message.show()
        cases[nom].setFocus()

    try:
        lu = lire_releve_km(cases["champ_km_date_jour"].text(),
                            cases["champ_km_date_heure"].text(),
                            cases["champ_km_valeur"].text(),
                            cases["champ_km_conso"].text())
    except ErreurSaisie as e:
        erreur(e.champ, e.message)
        return
    quand = (lu["date"].isoformat(timespec="minutes")
             if lu["date"] is not None else None)
    try:
        r = ajouter_releve_km(lu["km"], quand, lu["conso"])
    except (ValueError, OSError) as e:
        # Kilometrage en recul, releve deja saisi, consommation hors des
        # clous : les messages de recharges.py sont deja en francais et
        # portent tous sur ces deux cases-la.
        texte = erreur_en_clair(e)
        erreur("champ_km_conso" if "consommation" in texte
               else "champ_km_valeur", texte)
        return
    # La page se reconstruit (tous ses chiffres changent) et affiche alors
    # le message de succes, garde sur la fenetre en attendant.
    fenetre.message_km = message_enregistre(r)
    QTimer.singleShot(0, fenetre, lambda: fenetre.recharger_page("km"))


def texte_essence(c: dict) -> str:
    """La phrase sous les trois tuiles de la comparaison essence."""
    distance = f"{c['km']:,.0f}".replace(",", "\xa0")
    litres = f"{c['litres']:,.0f}".replace(",", "\xa0")
    prix = f"{c['prix_essence']:.2f}\xa0€/L".replace(".", ",")
    # Plusieurs annees a des prix differents : c'est un prix moyen.
    if len({a["prix"] for a in c.get("par_annee", [])}) > 1:
        prix += " en moyenne"
    return (f"Du {fmt_date_fr(c['debut'])[:10]} au {fmt_date_fr(c['fin'])[:10]}, "
            f"sur {distance}\xa0km, une voiture essence à "
            + f"{c['conso_essence']:.1f}\xa0L/100\xa0km".replace(".", ",")
            + f" aurait consommé environ {litres} litres, à {prix} : "
            + f"{c['cout_100_essence']:.2f}\xa0€/100\xa0km".replace(".", ",")
            + ", contre " + f"{c['cout_100_electrique']:.2f}".replace(".", ",")
            + " €/100\xa0km en électricité.")


def _carte_essence(c: dict | None) -> QWidget:
    """Comparaison avec une voiture essence (28/09/2026). `c` vient de
    recharges.comparer_essence_periode ; None : l'invitation a regler la
    voiture de comparaison dans les Parametres."""
    cadre, corps = carte("Comparaison avec une voiture essence")
    if c is None:
        corps.addWidget(texte_a_lire(
            "Indiquez dans « ⚙️ Paramètres » la consommation d'une voiture "
            "essence comparable et le prix du litre : l'application vous "
            "dira ce que ces kilomètres vous auraient coûté en essence.",
            "Discret"))
        return cadre
    grille = QGridLayout()
    grille.setSpacing(8)
    for i, (libelle, valeur, couleur) in enumerate((
            ("EN ESSENCE", fmt_eur(c["cout_essence"]), BLEU_NUIT),
            # Une couleur dit un sens (choix de l'auteur du 08/10/2026) :
            # un cout est neutre ; l'economie est favorable, le surcout non.
            ("EN ÉLECTRICITÉ", fmt_eur(c["cout_electrique"]), BLEU_NUIT),
            ("ÉCONOMIE" if c["economie"] >= 0 else "SURCOÛT",
             fmt_eur(abs(c["economie"])),
             VERT if c["economie"] >= 0 else ROUGE))):
        grille.addWidget(tuile(libelle, valeur, couleur), 0, i)
        grille.setColumnStretch(i, 1)
    corps.addLayout(grille)
    corps.addWidget(texte_a_lire(texte_essence(c), "Discret"))
    if c.get("part_non_enregistree"):
        # Recharges gratuites (chez des proches...) : pas une erreur, mais
        # l'utilisateur doit savoir d'ou vient une partie de l'economie.
        corps.addWidget(texte_a_lire(
            f"Environ {c['part_non_enregistree']}\xa0% de l'énergie de ces "
            "kilomètres ne figure pas dans vos recharges (estimation d'après "
            "la consommation affichée par la voiture) : recharges chez des "
            "proches, bornes gratuites, ou recharges payées sans être "
            "saisies. Son origine et son prix ne sont pas connus : le coût en "
            "électricité ne compte que vos recharges saisies. Si certaines "
            "ont été payées, l'économie réelle est plus faible.", "Discret"))
    for annee in c.get("sans_km", []):
        # Une annee qui a des recharges mais aucun kilometre (audit du
        # 14/10/2026) : son cout est dans le total, il faut le dire.
        corps.addWidget(texte_a_lire(
            f"Le coût en électricité comprend aussi {fmt_eur(annee['cout_electrique'])} "
            f"de recharges de {annee['annee']}, année où vos relevés ne "
            "donnent aucun kilomètre.", "Discret"))
    corps.addWidget(texte_a_lire(
        "Le prix du litre est celui saisi dans « ⚙️ Paramètres » (par année "
        "si vous l'avez indiqué). L'abonnement électrique et les frais de "
        "cartes ne sont pas comptés.", "Discret"))
    return cadre


def _carte_controle(ctrl: dict) -> QWidget:
    cadre, corps = carte("Part d'énergie non enregistrée (estimation)")
    t = textes_controle(ctrl)
    if "invitation" in t:
        corps.addWidget(paragraphe(t["invitation"], "Discret"))
        return cadre
    corps.addWidget(paragraphe(t["reference"], "Discret"))
    corps.addWidget(paragraphe(t["detail"]))
    verdict = paragraphe(t["verdict"], "Verdict")
    verdict.setStyleSheet(f"color: {t['couleur']};")
    corps.addWidget(verdict)
    cadre.verdict = verdict                 # pour les tests
    return cadre


def _carte_releves(fenetre, releves: list[dict]) -> QWidget:
    cadre, corps = carte("Mes relevés")
    cadre.boutons = []                  # les « Supprimer »
    cadre.boutons_modifier = []
    if not releves:
        corps.addWidget(paragraphe("Aucun relevé enregistré.", "Discret"))
        return cadre
    ecarts = {recent["id"]: recent["km"] - ancien["km"]
              for ancien, recent in zip(releves, releves[1:])}
    lignes, paires = [], []
    for r in reversed(releves):
        lignes.append(cellules_releve(r, ecarts.get(r["id"])))
        # « Modifier » corrige sur place (analyse du 16/10/2026) : avant,
        # il fallait supprimer puis ressaisir le relevé.
        modifier = QPushButton("Modifier…")
        modifier.setToolTip("Corriger ce relevé")
        modifier.clicked.connect(
            lambda _=False, rr=r: modifier_releve(fenetre, rr))
        bouton = QPushButton("Supprimer")
        bouton.setToolTip("Supprimer ce relevé")
        bouton.clicked.connect(
            lambda _=False, rr=r: supprimer_releve(fenetre, rr))
        cadre.boutons_modifier.append(modifier)
        cadre.boutons.append(bouton)
        paire = QWidget()
        rangee = QHBoxLayout(paire)
        rangee.setContentsMargins(0, 0, 0, 0)
        rangee.setSpacing(6)
        rangee.addWidget(modifier)
        rangee.addWidget(bouton)
        paires.append(paire)
    table = tableau(ENTETES_RELEVES, lignes, a_droite=(1, 2, 3),
                    boutons=paires)
    table.horizontalHeaderItem(2).setToolTip(INFOBULLE_PARCOURUS)
    corps.addWidget(table)
    return cadre


def modifier_releve(fenetre, r: dict) -> None:
    if DialogueReleve(fenetre, r).exec() != QDialog.Accepted:
        return
    fenetre.message_km = "Relevé corrigé."
    # Un nouveau releve en cours de saisie reste dans le formulaire.
    QTimer.singleShot(0, fenetre,
                      lambda: fenetre.recharger_page("km", garder_saisie=True))


def supprimer_releve(fenetre, r: dict) -> None:
    km = f"{r['km']:,.0f}".replace(",", "\xa0")
    # « Garder » par defaut : une suppression ne se rattrape que par la page
    # Restaurer.
    if not confirmer(
            fenetre, "Supprimer le relevé",
            f"Supprimer le relevé du {fmt_date_fr(r['date'])} ({km}\xa0km) ?\n\n"
            "Il ne se rattrape ensuite que par la page « Restaurer une sauvegarde ».",
            action="Supprimer le relevé", garder="Garder", danger=True):
        return
    try:
        ok = supprimer_releve_km(r.get("id", ""))
    except (ValueError, OSError) as e:
        QMessageBox.critical(fenetre, "Suppression impossible", erreur_en_clair(e))
        return
    if not ok:
        # Sans ce test, un releve introuvable disparaissait de l'ecran sans
        # etre supprime.
        QMessageBox.critical(
            fenetre, "Suppression impossible",
            "Ce relevé est introuvable : rien n'a été supprimé.")
        return
    QTimer.singleShot(0, fenetre,
                      lambda: fenetre.recharger_page("km", garder_saisie=True))
