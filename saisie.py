"""Controle des saisies : un message en francais plutot qu'une erreur Python.

Sorti des vues. Jusqu'a la v1.26.2, un champ « Energie » laisse vide ouvrait
une boite de dialogue disant « could not convert string to float: '' » : un
message ecrit par Python, en anglais, qui ne disait meme pas quel champ etait
en cause.

Ces fonctions ne connaissent ni CustomTkinter ni l'application. Elles
prennent le texte tape, rendent la valeur, et levent ErreurSaisie avec une
phrase en francais et le nom du champ fautif ; la vue n'a plus qu'a afficher
la phrase au bon endroit. C'est aussi ce qui les rend verifiables sans
ouvrir de fenetre (tests/test_saisie.py).
"""

from __future__ import annotations

import math
from datetime import datetime, timedelta

from temps_reel import apres_duree


class ErreurSaisie(Exception):
    """Une saisie refusee : quel champ, et pourquoi, en francais.

    `champ` est le nom de l'attribut qui porte le champ de saisie
    (« champ_m_kwh ») : la vue s'en sert pour ecrire le message sous le bon
    champ et y ramener le curseur.
    """

    def __init__(self, champ: str, message: str):
        super().__init__(message)
        self.champ = champ
        self.message = message


def _majuscule(texte: str) -> str:
    """« l'energie consommee » -> « L'energie consommee ».

    capitalize() ne conviendrait pas : il met tout le reste en minuscules,
    ce qui abimerait un libelle contenant un nom propre.
    """
    return texte[:1].upper() + texte[1:]


def lire_nombre(texte: str, champ: str, quoi: str, *,
                obligatoire: bool = True,
                strictement_positif: bool = False) -> float | None:
    """Le nombre tape dans un champ, ou None si le champ facultatif est vide.

    `quoi` decrit ce qu'on attend, au milieu d'une phrase : « l'energie
    consommee », « le cout total ». Il sert a composer les messages.

    La virgule decimale et les espaces des milliers sont acceptes
    (« 123 456,7 ») : c'est ainsi qu'on ecrit un kilometrage en francais, et
    le pave numerique du clavier donne une virgule.
    """
    brut = texte.strip()
    if not brut:
        if obligatoire:
            raise ErreurSaisie(champ, f"Indiquez {quoi}.")
        return None
    # split() sans argument coupe sur toutes les espaces, y compris les
    # insecables que collent les tableurs : les recoller supprime les
    # separateurs de milliers.
    nettoye = "".join(brut.split()).replace(",", ".")
    try:
        valeur = float(nettoye)
    except ValueError:
        raise ErreurSaisie(
            champ,
            f"« {brut} » n'est pas un nombre (exemple : 12,4).") from None
    # float() accepte « inf » et « nan » : ce ne sont pas des saisies
    # valables, et elles fausseraient tous les calculs sans rien signaler.
    if not math.isfinite(valeur):
        raise ErreurSaisie(
            champ, f"« {brut} » n'est pas un nombre (exemple : 12,4).")
    if valeur < 0:
        raise ErreurSaisie(champ, "Indiquez un nombre positif.")
    if strictement_positif and valeur == 0:
        raise ErreurSaisie(
            champ, f"{_majuscule(quoi)} ne peut pas être à zéro.")
    return valeur


# Le message le plus utile est celui qui montre ce qui est accepte.
AIDE_JOUR = "Attendu : jj/mm/aaaa, ou plus court « 18/09 » (l'année en cours)."
AIDE_HEURE = "Attendu : hh:mm, ou « 22h30 », ou « 22h »."
AIDE_DATE = ("Attendu : jj/mm/aaaa hh:mm, ou plus court : « 18/09 22h30 », "
             "« 18/09 », ou « 22h30 » pour aujourd'hui.")


def _normaliser(s: str) -> str:
    """Met le texte tape sous une forme que strptime comprend.

    Le « h » sert de separateur d'heure (22h30, 22 h 30, 22h) : une date ne
    contient que des chiffres, des barres obliques et des espaces, la lettre
    ne peut donc rien designer d'autre. Le « : » final vient de « 22h ».
    """
    texte = s.strip().lower().replace("h", ":")
    while " :" in texte or ": " in texte:
        texte = texte.replace(" :", ":").replace(": ", ":")
    return texte.rstrip(":")


def _lire_jour(texte: str, maintenant: datetime) -> tuple[datetime, bool]:
    """Le jour, a minuit, et si son annee a ete devinee plutot que tapee."""
    elements = texte.split("/")
    annee_implicite = False
    if len(elements) == 2:
        # « 18/09 » : l'annee en cours. On la colle au texte plutot que
        # d'ajouter un format « %d/%m », qui refuserait le 29 fevrier
        # (strptime le daterait de 1900, qui n'est pas bissextile).
        elements.append(str(maintenant.year))
        annee_implicite = True
    if len(elements) != 3:
        raise ValueError(AIDE_JOUR)
    # Annee sur deux chiffres (« 26 ») : les annees 2000. Sans ce traitement,
    # strptime lirait « %Y » = l'an 26 sans rien dire.
    if len(elements[2]) == 2:
        elements[2] = f"20{elements[2]}"
    elif len(elements[2]) != 4:
        raise ValueError(AIDE_JOUR)
    try:
        return datetime.strptime("/".join(elements), "%d/%m/%Y"), annee_implicite
    except ValueError:
        raise ValueError(AIDE_JOUR) from None


def _lire_heure(texte: str) -> tuple[int, int]:
    """L'heure et les minutes. « 22h » vaut 22:00."""
    for fmt in ("%H:%M", "%H"):
        try:
            moment = datetime.strptime(texte, fmt)
            return moment.hour, moment.minute
        except ValueError:
            continue
    raise ValueError(AIDE_HEURE)


def _reculer_si_futur(resultat: datetime, maintenant: datetime,
                      annee_implicite: bool, passe: bool) -> datetime:
    """Rapporte a l'annee precedente une date devinee trop loin dans l'avenir.

    Ne joue que si `passe` est demande ET si l'annee a ete devinee. Le 2
    janvier, « 30/12 » designe le 30 decembre qui vient de s'ecouler.

    Six mois, et non « des que c'est dans l'avenir » : le 18 septembre,
    « 20/09 » est une faute de frappe de deux jours, pas une date de l'annee
    derniere. Mieux vaut une date visiblement fausse de deux jours qu'une
    date fausse d'un an sans que rien ne le signale.
    """
    if not (passe and annee_implicite):
        return resultat
    if resultat <= maintenant + timedelta(days=183):
        return resultat
    try:
        return resultat.replace(year=resultat.year - 1)
    except ValueError:
        return resultat   # 29 fevrier : l'annee precedente ne l'a pas


def parse_date_fr(s: str, *, passe: bool = False,
                  maintenant: datetime | None = None) -> datetime:
    """La date et l'heure tapees D'UN SEUL TENANT.

    Formes acceptees, de la plus complete a la plus courte :

        18/09/2026 22:30     18/09/2026 22h30     18/09/2026
        18/09 22h30          18/09                22h30

    Sans annee, c'est l'annee courante ; sans heure, minuit ; sans date du
    tout, aujourd'hui.

    Les formulaires de saisie ont DEUX cases separees depuis le 18/09/2026
    et passent par lire_date_heure(). Celle-ci sert encore aux fenetres de
    modification et de tarif (dialogues.py), ou la date tient en une case.

    `maintenant` n'est renseigne que par les tests, pour eprouver le passage
    d'annee sans dependre du jour ou ils tournent.
    """
    morceaux = _normaliser(s).split()
    if not morceaux or len(morceaux) > 2:
        raise ValueError(AIDE_DATE)
    if len(morceaux) == 2:
        part_jour, part_heure = morceaux
    elif "/" in morceaux[0]:
        part_jour, part_heure = morceaux[0], ""
    else:
        part_jour, part_heure = "", morceaux[0]

    maintenant = maintenant or datetime.now()
    annee_implicite = False
    if part_jour:
        try:
            jour, annee_implicite = _lire_jour(part_jour, maintenant)
        except ValueError:
            raise ValueError(AIDE_DATE) from None
    else:
        jour = maintenant
    try:
        heures, minutes = _lire_heure(part_heure) if part_heure else (0, 0)
    except ValueError:
        raise ValueError(AIDE_DATE) from None

    resultat = jour.replace(hour=heures, minute=minutes,
                            second=0, microsecond=0)
    return _reculer_si_futur(resultat, maintenant, annee_implicite, passe)


AIDE_DUREE = ("Une durée s'écrit avec un « + » devant : « +6h12 », « +6h », "
              "ou « +45min ».")


def lire_duree(texte: str) -> timedelta | None:
    """La durée tapée à la place d'une heure, ou None si ce n'en est pas une.

    Le « + » est obligatoire, et c'est lui qui lève l'ambiguïté : sans lui,
    « 6h12 » est une heure de la matinée, pas une durée de six heures. On
    saisit souvent la durée plutôt que l'heure de fin — la borne l'affiche,
    et c'est une soustraction de moins à faire de tête.

    Formes acceptées : « +6h12 », « +6:12 », « +6h », « +45min ».
    """
    brut = texte.strip()
    if not brut.startswith("+"):
        return None
    reste = brut[1:].strip().lower()
    if not reste:
        raise ValueError(AIDE_DUREE)

    if reste.endswith("min"):
        nombre = reste[:-3].strip()
        if not nombre.isdigit():
            raise ValueError(AIDE_DUREE)
        duree = timedelta(minutes=int(nombre))
    else:
        try:
            heures, minutes = _lire_heure(_normaliser(reste))
        except ValueError:
            raise ValueError(AIDE_DUREE) from None
        duree = timedelta(hours=heures, minutes=minutes)

    if duree <= timedelta(0):
        raise ValueError("La durée doit être supérieure à zéro.")
    return duree


def lire_date_heure(texte_jour: str, texte_heure: str,
                    champ_jour: str, champ_heure: str, quoi: str, *,
                    obligatoire: bool = True, passe: bool = False,
                    maintenant: datetime | None = None) -> datetime | None:
    """La date lue dans DEUX cases distinctes : le jour, puis l'heure.

    Les formulaires les reunissaient dans une seule case jusqu'au
    18/09/2026 : il fallait alors expliquer dans le libelle comment composer
    « jj/mm/aaaa hh:mm ». Separees, chaque case dit ce qu'elle attend, et le
    message d'erreur designe la bonne.

    Une case vide ne bloque pas l'autre : sans jour, c'est aujourd'hui ;
    sans heure, minuit. Les deux vides valent None quand la saisie est
    facultative.
    """
    jour_brut, heure_brute = texte_jour.strip(), texte_heure.strip()
    # Habitude de l'ancienne case unique : « 18/09 22h30 » tape en entier
    # dans celle du jour. On repartit plutot que de refuser.
    if " " in jour_brut and not heure_brute:
        jour_brut, heure_brute = jour_brut.split(None, 1)

    if not jour_brut and not heure_brute:
        if obligatoire:
            raise ErreurSaisie(champ_jour, f"Indiquez {quoi}.")
        return None

    maintenant = maintenant or datetime.now()
    annee_implicite = False
    if jour_brut:
        try:
            jour, annee_implicite = _lire_jour(_normaliser(jour_brut),
                                               maintenant)
        except ValueError:
            raise ErreurSaisie(
                champ_jour,
                f"« {jour_brut} » n'est pas une date. {AIDE_JOUR}") from None
    else:
        jour = maintenant
    if heure_brute:
        try:
            heures, minutes = _lire_heure(_normaliser(heure_brute))
        except ValueError:
            raise ErreurSaisie(
                champ_heure,
                f"« {heure_brute} » n'est pas une heure. {AIDE_HEURE}"
            ) from None
    else:
        heures, minutes = 0, 0

    resultat = jour.replace(hour=heures, minute=minutes,
                            second=0, microsecond=0)
    return _reculer_si_futur(resultat, maintenant, annee_implicite, passe)


# ---------- les formulaires « Ajouter une recharge » ----------
#
# Les regles de lecture des deux formulaires, sans aucune fenetre : elles
# recoivent les TEXTES tapes et rendent des valeurs pretes a enregistrer,
# ou levent ErreurSaisie avec le nom de la case fautive. Les noms de cases
# (« champ_m_kwh »...) sont ceux des formulaires. La page PySide6
# (pages/ajouter.py) n'a plus qu'a les appeler ; les tests les eprouvent
# sans ecran (tests/test_saisie_recharge.py).


def energie_et_cout(texte_kwh: str, texte_cout: str,
                    texte_prix: str) -> tuple[float, float]:
    """L'énergie et le coût, déduits de deux des trois cases remplies.

    Les reçus des opérateurs ne donnent pas tous les mêmes chiffres : l'un
    le total payé, l'autre le prix au kWh. Plutôt que de faire la division
    de tête, on remplit les deux cases qu'on a.

    Le coût payé fait foi quand les trois sont remplies : c'est lui qu'on
    lit sur le relevé bancaire, et c'est déjà la règle de la notice.

    Venue de l'ancienne page vues/ajout.py (25/09/2026) ; eprouvee par
    tests/test_energie_cout.py.
    """
    kwh = lire_nombre(texte_kwh, "champ_e_kwh",
                      "l'énergie rechargée", obligatoire=False,
                      strictement_positif=True)
    # Zero est accepte pour le cout : une borne gratuite, cela existe.
    cout = lire_nombre(texte_cout, "champ_e_cout",
                       "le coût total", obligatoire=False)
    if kwh is not None and cout is not None:
        # Le cout fait foi : le prix eventuel est ignore. Il doit seulement
        # etre un nombre (une faute de frappe y trahit peut-etre une erreur
        # ailleurs) ; zero est accepte, puisqu'il ne sert a rien. Exiger un
        # prix positif bloquait la saisie d'une borne gratuite recopiee du
        # recu, kWh, 0 € et 0 €/kWh (audit du 14/10/2026).
        lire_nombre(texte_prix, "champ_e_prix", "le prix du kWh",
                    obligatoire=False)
        return kwh, cout
    prix = lire_nombre(texte_prix, "champ_e_prix",
                       "le prix du kWh", obligatoire=False,
                       strictement_positif=True)
    if kwh is not None and prix is not None:
        return kwh, round(kwh * prix, 2)
    if cout is not None and prix is not None:
        if not cout:
            # 0 € divise par un prix donne 0 kWh, que l'enregistrement
            # refusera : mieux vaut le dire ici, et clairement.
            raise ErreurSaisie(
                "champ_e_kwh",
                "Pour une recharge gratuite, indiquez l'énergie : le prix "
                "du kWh ne permet rien d'en déduire.")
        return round(cout / prix, 3), cout

    raise ErreurSaisie(
        "champ_e_kwh",
        "Remplissez deux cases parmi l'énergie, le coût total et le prix "
        "du kWh — la troisième se calcule toute seule.")


def placer_heure_de_fin(fin: datetime, debut: datetime) -> datetime:
    """L'heure de fin tapee SANS jour : le jour du debut, ou le lendemain
    si l'heure tombe avant celle du debut (une charge de nuit passe minuit).

    Jusqu'au 25/09/2026, l'heure seule etait placee aujourd'hui : saisie le
    25 d'une charge commencee le 20 a 22h30, « 6h » donnait le 25 a 6h, soit
    plus de cinq jours de charge. Cela ne se voyait pas en saisissant le
    lendemain matin, quand aujourd'hui EST le lendemain du debut.

    Deux heures identiques ne sont PAS decalees : elles restent une erreur a
    signaler (« La fin doit être après le début. »)."""
    fin = datetime.combine(debut.date(), fin.time())
    if fin < debut:
        fin += timedelta(days=1)
    return fin


# Au-dela, une charge a la maison est une faute de frappe sur la date de fin
# (l'annee, le mois), pas une vraie charge : meme une prise domestique lente
# remplit une grosse batterie en moins de trois jours. Jusqu'a la v2.0.0,
# une charge de 365 jours passait sans un mot.
DUREE_MAXIMALE = timedelta(hours=72)


def _verifier_duree(debut: datetime, fin: datetime, champ: str) -> None:
    """Refuse une duree de charge invraisemblable, en le disant."""
    if fin - debut > DUREE_MAXIMALE:
        jours = (fin - debut).total_seconds() / 86400
        raise ErreurSaisie(
            champ,
            f"Cette recharge durerait {jours:.0f} jours : vérifiez la date "
            "de fin (le jour, le mois, l'année).")


def lire_recharge_maison(jour_debut: str, heure_debut: str,
                         jour_fin: str, heure_fin: str,
                         texte_kwh: str, texte_km: str, *,
                         maintenant: datetime | None = None) -> dict:
    """Le formulaire « Maison » lu d'un bout a l'autre.

    Rend {"debut", "fin" (None si laissee vide), "kwh", "km" (None si
    vide)}. Tout est controle AVANT d'enregistrer quoi que ce soit : un
    kilometrage illisible ne doit pas laisser une recharge a moitie saisie.
    """
    debut = lire_date_heure(
        jour_debut, heure_debut, "champ_m_debut_jour", "champ_m_debut_heure",
        "la date et l'heure de début", passe=True, maintenant=maintenant)
    # Une durée (« +6h12 ») se reconnait a son « + » et se compte a partir
    # du debut : elle dispense de calculer l'heure de fin.
    try:
        duree = lire_duree(heure_fin)
    except ValueError as e:
        # Le « + » est la, mais la suite est illisible.
        raise ErreurSaisie("champ_m_fin_heure", str(e)) from None
    if duree is None:
        # passe=True, comme pour le debut : le 2 janvier, « 31/12 » est le
        # 31 decembre qui vient de s'ecouler, pas celui de la fin de l'annee
        # (la fenetre « Modifier » le faisait deja).
        fin = lire_date_heure(
            jour_fin, heure_fin, "champ_m_fin_jour", "champ_m_fin_heure",
            "la date et l'heure de fin", obligatoire=False, passe=True,
            maintenant=maintenant)
    else:
        if jour_fin.strip():
            raise ErreurSaisie(
                "champ_m_fin_jour",
                "Avec une durée, laissez la case du jour vide : "
                "elle se compte à partir du début.")
        # Compte en temps reel : juste la nuit du changement d'heure.
        fin = apres_duree(debut, duree)
    kwh = lire_nombre(texte_kwh, "champ_m_kwh", "l'énergie consommée",
                      strictement_positif=True)
    km = lire_nombre(texte_km, "champ_m_km", "le kilométrage du compteur",
                     obligatoire=False, strictement_positif=True)
    # L'heure seule (« 6h »), case du JOUR laissee vide : le jour du debut,
    # ou le lendemain matin pour une charge de nuit. Un jour ecrit est pris
    # au mot.
    if fin is not None and duree is None and not jour_fin.strip():
        fin = placer_heure_de_fin(fin, debut)
    if fin is not None and fin <= debut:
        raise ErreurSaisie("champ_m_fin_heure",
                           "La fin doit être après le début.")
    if fin is not None:
        _verifier_duree(debut, fin, "champ_m_fin_jour" if jour_fin.strip()
                        else "champ_m_fin_heure")
    return {"debut": debut, "fin": fin, "kwh": kwh, "km": km}


def lire_recharge_exterieur(jour: str, heure: str, texte_kwh: str,
                            texte_cout: str, texte_prix: str,
                            texte_km: str, *,
                            maintenant: datetime | None = None) -> dict:
    """Le formulaire « Extérieur » lu d'un bout a l'autre.

    Rend {"date" (None si les deux cases sont vides : la recharge sera
    alors datee de maintenant), "kwh", "cout", "km" (None si vide)}.
    """
    date = lire_date_heure(
        jour, heure, "champ_e_date_jour", "champ_e_date_heure",
        "la date et l'heure", obligatoire=False, passe=True,
        maintenant=maintenant)
    kwh, cout = energie_et_cout(texte_kwh, texte_cout, texte_prix)
    km = lire_nombre(texte_km, "champ_e_km", "le kilométrage du compteur",
                     obligatoire=False, strictement_positif=True)
    return {"date": date, "kwh": kwh, "cout": cout, "km": km}


def lire_modification_recharge(recharge: dict, textes: dict[str, str], *,
                               maintenant: datetime | None = None) -> dict:
    """La fenetre « Modifier la recharge » lue d'un bout a l'autre.

    `textes` porte le texte de chaque case, sous le nom de la case :
    « date_jour », « date_heure », « kwh » ; pour la maison « fin_jour » et
    « fin_heure » ; pour l'exterieur « cout_eur », « operateur », « carte »,
    « lieu_detail ». Rend les modifications a passer a modifier_recharge().

    Les deux cases du debut laissees vides veulent dire « inchange » : la
    date d'origine est gardee. Celles de la fin, pre-remplies, videes
    toutes les deux : l'heure de fin est retiree (« fin » vaut None), comme
    une recharge saisie sans fin (decision d'André du 15/10/2026 ; avant,
    ce geste etait ignore sans un mot).
    """
    maison = recharge.get("lieu") == "maison"
    modifs: dict = {}
    debut = lire_date_heure(
        textes.get("date_jour", ""), textes.get("date_heure", ""),
        "date_jour", "date_heure", "la date et l'heure",
        obligatoire=False, passe=True, maintenant=maintenant)
    if debut is not None:
        modifs["date"] = debut.isoformat(timespec="minutes")
    # Le debut qui vaudra apres la modification : celui qu'on vient de
    # taper, ou celui d'origine.
    reference = debut or datetime.fromisoformat(recharge.get("date", ""))

    fin = duree = None
    jour_fin = textes.get("fin_jour", "")
    if maison:
        # Comme a la saisie : « +6h12 » est une duree comptee depuis le debut.
        try:
            duree = lire_duree(textes.get("fin_heure", ""))
        except ValueError as e:
            raise ErreurSaisie("fin_heure", str(e)) from None
        if duree is None:
            fin = lire_date_heure(
                jour_fin, textes.get("fin_heure", ""), "fin_jour",
                "fin_heure", "la date et l'heure de fin", obligatoire=False,
                passe=True, maintenant=maintenant)
        elif jour_fin.strip():
            raise ErreurSaisie(
                "fin_jour",
                "Avec une durée, laissez la case du jour vide : "
                "elle se compte à partir du début.")
        else:
            fin = apres_duree(reference, duree)

    modifs["kwh"] = lire_nombre(textes.get("kwh", ""), "kwh", "l'énergie",
                                strictement_positif=True)
    if not maison:
        # Zero accepte : une borne gratuite, cela existe.
        modifs["cout_eur"] = lire_nombre(textes.get("cout_eur", ""),
                                         "cout_eur", "le coût")
        for cle in ("operateur", "carte", "lieu_detail"):
            modifs[cle] = textes.get(cle, "").strip()

    if fin is not None:
        # Meme regle qu'a la saisie : l'heure seule se place le jour du
        # debut, ou le lendemain pour une charge de nuit.
        if duree is None and not jour_fin.strip():
            fin = placer_heure_de_fin(fin, reference)
        if fin <= reference:
            raise ErreurSaisie("fin_heure", "La fin doit être après le début.")
        _verifier_duree(reference, fin,
                        "fin_jour" if jour_fin.strip() else "fin_heure")
        modifs["fin"] = fin.isoformat(timespec="minutes")
    elif maison:
        # Les deux cases de la fin videes : l'heure de fin est a retirer.
        # En heures pleines / creuses, modifier_recharge() refusera avec un
        # message qui la redemande, et rien ne sera enregistre.
        modifs["fin"] = None
    return modifs


def lire_releve_km(jour: str, heure: str, texte_km: str, texte_conso: str, *,
                   maintenant: datetime | None = None) -> dict:
    """Le formulaire « Nouveau relevé » de la page Kilométrage.

    Rend {"date" (None si les deux cases sont vides : le releve sera date
    de maintenant), "km", "conso" (None si vide)}. La consommation est celle
    qu'affiche la voiture, lue sur le meme ecran que le compteur.
    """
    date = lire_date_heure(
        jour, heure, "champ_km_date_jour", "champ_km_date_heure",
        "la date et l'heure", obligatoire=False, passe=True,
        maintenant=maintenant)
    # 0 km est permis : le compteur d'une voiture neuve a la livraison.
    km = lire_nombre(texte_km, "champ_km_valeur",
                     "le kilométrage de la voiture")
    conso = lire_nombre(texte_conso, "champ_km_conso",
                        "la consommation affichée", obligatoire=False)
    return {"date": date, "km": km, "conso": conso}


def lire_plages(texte: str) -> list[list[str]]:
    """« 22:00-06:00, 12h-14h » -> [["22:00", "06:00"], ["12:00", "14:00"]].

    Les heures s'ecrivent comme partout ailleurs (« 22h », « 22h30 »), et
    ressortent au format du fichier (« 22:00 »). ErreurSaisie sur la case
    « plages_hc » si une plage est illisible ou s'il n'y en a aucune."""
    plages = []
    for morceau in texte.split(","):
        brut = morceau.strip()
        if not brut:
            continue
        if brut.count("-") != 1:
            raise ErreurSaisie(
                "plages_hc",
                f"Plage mal écrite : « {brut} ». Attendu : 22:00-06:00.")
        paire = []
        for heure in brut.split("-"):
            try:
                h, m = _lire_heure(_normaliser(heure))
            except ValueError:
                raise ErreurSaisie(
                    "plages_hc",
                    f"Plage mal écrite : « {brut} ». Attendu : 22:00-06:00."
                ) from None
            paire.append(f"{h:02d}:{m:02d}")
        plages.append(paire)
    if not plages:
        raise ErreurSaisie(
            "plages_hc",
            "Indiquez au moins une plage d'heures creuses (ex. 22:00-06:00).")
    return plages


def lire_tarif(textes: dict[str, str], hp_hc: bool) -> dict:
    """La fenetre de tarif lue d'un bout a l'autre, case par case.

    `textes` porte le texte des cases « nom », « debut », « fin »,
    « abonnement_mensuel », puis « prix_kwh » (prix unique) ou « prix_hp »,
    « prix_hc », « plages_hc » (heures pleines / creuses). Rend le tarif au
    format de tarifs.json, sans son identifiant. Le moteur le revérifie
    ensuite en entier (valider_tarif : plages qui se chevauchent...).

    Les dates n'ont pas de regle « passe » : un tarif peut commencer plus
    tard (nouveau contrat annonce)."""
    nom = textes.get("nom", "").strip()
    if not nom:
        raise ErreurSaisie("nom", "Indiquez le nom du tarif.")
    debut = lire_date_heure(textes.get("debut", ""), "", "debut", "debut",
                            "la date de début").date()
    fin = lire_date_heure(textes.get("fin", ""), "", "fin", "fin",
                          "la date de fin", obligatoire=False)
    if fin is not None and fin.date() < debut:
        raise ErreurSaisie(
            "fin", "La date de fin doit venir après la date de début.")
    abonnement = lire_nombre(textes.get("abonnement_mensuel", ""),
                             "abonnement_mensuel", "l'abonnement mensuel",
                             obligatoire=False)
    tarif = {"nom": nom, "debut": debut.isoformat(),
             "fin": fin.date().isoformat() if fin is not None else None,
             "abonnement_mensuel": abonnement or 0.0}
    if hp_hc:
        tarif["type"] = "hp_hc"
        tarif["prix_hp"] = lire_nombre(
            textes.get("prix_hp", ""), "prix_hp",
            "le prix en heures pleines", strictement_positif=True)
        tarif["prix_hc"] = lire_nombre(
            textes.get("prix_hc", ""), "prix_hc",
            "le prix en heures creuses", strictement_positif=True)
        tarif["plages_hc"] = lire_plages(textes.get("plages_hc", ""))
    else:
        tarif["type"] = "simple"
        tarif["prix_kwh"] = lire_nombre(
            textes.get("prix_kwh", ""), "prix_kwh", "le prix du kWh",
            strictement_positif=True)
    return tarif


def lire_frais_carte(textes: dict[str, str]) -> dict:
    """Les frais d'une carte de recharge, lus case par case (page Tarifs).

    `textes` porte « carte », « type » (« unique », « mensuel » ou
    « annuel »), « date » (achat, ou debut de l'abonnement), « fin »
    (abonnement seulement, facultative) et « montant » (par mois ou par an
    pour un abonnement). Rend les frais au format de tarifs.json,
    sans identifiant. La fin d'un achat unique est ignoree : elle n'a pas
    de sens."""
    carte = textes.get("carte", "").strip()
    if not carte:
        raise ErreurSaisie("carte", "Indiquez le nom de la carte.")
    type_ = textes.get("type")
    if type_ not in ("mensuel", "annuel"):
        type_ = "unique"
    abonnement = type_ != "unique"
    debut = lire_date_heure(textes.get("date", ""), "", "date", "date",
                            "la date").date()
    fin = None
    if abonnement:
        fin = lire_date_heure(textes.get("fin", ""), "", "fin", "fin",
                              "la date de fin", obligatoire=False)
        if fin is not None and fin.date() < debut:
            raise ErreurSaisie(
                "fin", "La date de fin doit venir après la date de début.")
    montant = lire_nombre(textes.get("montant", ""), "montant", "le montant",
                          strictement_positif=True)
    return {"carte": carte, "type": type_,
            "date": debut.isoformat(),
            "fin": fin.date().isoformat() if fin is not None else None,
            "montant": montant}
