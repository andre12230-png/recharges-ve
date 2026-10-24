"""Selection, tri et regroupement des recharges.

Sorti de app.py : ce sont des fonctions pures — elles recoivent une liste de
recharges et en renvoient une autre, sans toucher a l'interface ni aux
fichiers. C'est ce qui les rend testables, alors qu'elles concentrent une
bonne partie de la logique d'affichage (le decoupage en annees et en mois,
les bornes d'abonnement...).
"""

import re
import unicodedata
from datetime import date, datetime, timedelta

from formats import fmt_date_fr

# Les deux seules periodes qui ne se disent ni en annee ni en mois, proposees
# en tete du menu des annees. Il y en avait quatre autres — « Ce mois »,
# « Mois dernier », « Cette annee », « Annee derniere » — retirees le
# 07/09/2026 : les deux menus et les deux fleches font le meme geste en plus
# direct, et plus rien ne produisait ces valeurs.
PERIODES = ["Tout", "30 derniers jours"]

MOIS_FR = ["Janvier", "Février", "Mars", "Avril", "Mai", "Juin",
           "Juillet", "Août", "Septembre", "Octobre", "Novembre", "Décembre"]

# Entree « toute l'annee » du menu des mois : elle ne filtre pas sur un mois,
# elle rend la main a l'annee choisie a cote.
TOUTE_ANNEE = "Toute l'année"


def _sans_accents(texte: str) -> str:
    """« Février » et « Fevrier » doivent designer le meme mois : les noms de
    mois ont ete accentues, et rien ne garantit qu'une ancienne ecriture ne
    traine pas quelque part."""
    return "".join(c for c in unicodedata.normalize("NFD", texte)
                   if unicodedata.category(c) != "Mn")


def numero_du_mois(nom: str) -> int | None:
    """Numero (1 a 12) d'un nom de mois francais, accentue ou non."""
    cible = _sans_accents(nom).lower()
    for i, mois in enumerate(MOIS_FR, start=1):
        if _sans_accents(mois).lower() == cible:
            return i
    return None


def _mois_tries(recharges: list[dict]) -> list[str]:
    """Mois « AAAA-MM » presents dans les donnees, du plus recent au plus
    ancien."""
    mois_set = {r.get("date", "")[:7] for r in recharges}
    return sorted((m for m in mois_set if re.fullmatch(r"\d{4}-\d{2}", m)),
                  reverse=True)


def periodes_disponibles(recharges: list[dict]) -> list[str]:
    """Raccourcis + annees + mois reellement presents dans les donnees
    (du plus recent au plus ancien).

    Ne remplit plus aucun menu depuis que le selecteur est coupe en deux
    (voir annees_disponibles et mois_disponibles), mais reste la liste de
    reference de ce qui est selectionnable.
    """
    mois_tries = _mois_tries(recharges)
    annees = sorted({m[:4] for m in mois_tries}, reverse=True)
    libelles_mois = [f"{MOIS_FR[int(m[5:7]) - 1]} {m[:4]}" for m in mois_tries]
    return PERIODES + annees + libelles_mois


# ---------------------------------------------------------------------------
# Selecteur en deux menus (annee, puis mois)
# ---------------------------------------------------------------------------
# Une seule liste finissait par compter 42 lignes, et une de plus chaque mois.
# Coupee en deux, elle tient en quelques entrees qui ne s'allongeront plus.
# Les valeurs restent celles que filtrer_par_periode a toujours comprises
# (« Tout », « 2025 », « Juin 2026 ») : rien d'autre ne change.

def mois_en_cours() -> str:
    """Libelle du mois courant, ex. « Septembre 2026 ».

    Recalcule a chaque appel : c'est ce qui fait que l'application s'ouvre sur
    le mois en cours sans jamais rien memoriser.
    """
    now = datetime.now()
    return f"{MOIS_FR[now.month - 1]} {now.year}"


def annee_en_cours() -> str:
    """L'annee courante, « 2026 », telle que filtrer_par_periode l'attend.

    Recalculee a chaque appel, comme mois_en_cours() : rien n'est memorise
    d'un lancement a l'autre.
    """
    return str(datetime.now().year)


def libelle_mois(annee: str, nom_mois: str) -> str:
    """Assemble ce que les deux menus affichent en une periode : « Septembre »
    + « 2026 » -> « Septembre 2026 »."""
    return f"{nom_mois} {annee}"


def annees_disponibles(recharges: list[dict]) -> list[str]:
    """Contenu du menu de gauche : les raccourcis, puis les annees, de la plus
    recente a la plus ancienne.

    L'annee en cours y figure toujours, meme sans recharge : sinon
    l'application ne pourrait pas s'ouvrir dessus en debut d'annee.
    """
    annees = {m[:4] for m in _mois_tries(recharges)}
    annees.add(str(datetime.now().year))
    return PERIODES + sorted(annees, reverse=True)


def mois_disponibles(recharges: list[dict], annee: str) -> list[str]:
    """Contenu du menu de droite pour une annee : « Toute l'annee », puis les
    mois qui portent des recharges, du plus recent au plus ancien.

    Le mois en cours est toujours propose, meme vide : c'est celui sur lequel
    l'application s'ouvre, et « aucune recharge ce mois-ci » est une reponse.
    """
    mois = {int(m[5:7]) for m in _mois_tries(recharges) if m[:4] == annee}
    now = datetime.now()
    if annee == str(now.year):
        mois.add(now.month)
    return [TOUTE_ANNEE] + [MOIS_FR[m - 1] for m in sorted(mois, reverse=True)]


def annee_de_periode(periode: str) -> str | None:
    """Annee portee par une periode (« 2025 », « Juin 2026 »), ou None pour un
    raccourci comme « Tout »."""
    if re.fullmatch(r"\d{4}", periode):
        return periode
    parts = periode.split()
    if len(parts) == 2 and numero_du_mois(parts[0]) and parts[1].isdigit():
        return parts[1]
    return None


def nom_du_mois(periode: str) -> str | None:
    """Nom du mois d'une periode « Juin 2026 », ou None si ce n'en est pas
    une. Le nom renvoye est toujours l'ecriture accentuee du menu."""
    parts = periode.split()
    if len(parts) == 2 and parts[1].isdigit():
        numero = numero_du_mois(parts[0])
        if numero is not None:
            return MOIS_FR[numero - 1]
    return None


def _echelle_de_navigation(recharges: list[dict], periode: str) -> list[str]:
    """Suite ordonnee, du plus ancien au plus recent, dans laquelle les deux
    fleches se deplacent — les mois entre eux, les annees entre elles."""
    mois_tries = _mois_tries(recharges)
    if nom_du_mois(periode) is not None:
        libelles = [f"{MOIS_FR[int(m[5:7]) - 1]} {m[:4]}"
                    for m in reversed(mois_tries)]
        courant = mois_en_cours()
        if courant not in libelles:
            libelles.append(courant)
        return libelles
    if re.fullmatch(r"\d{4}", periode):
        return sorted({m[:4] for m in mois_tries} | {str(datetime.now().year)})
    return []   # « Tout » et « 30 derniers jours » n'ont ni avant ni apres


def periode_voisine(recharges: list[dict], periode: str,
                    sens: int) -> str | None:
    """Periode d'un cran plus ancienne (sens=-1) ou plus recente (sens=+1).

    None quand il n'y a plus rien de ce cote : c'est ce qui grise la fleche,
    plutot que de la laisser cliquable sans effet.
    """
    echelle = _echelle_de_navigation(recharges, periode)
    if periode not in echelle:
        return None
    i = echelle.index(periode) + sens
    return echelle[i] if 0 <= i < len(echelle) else None


def periode_par_raccourci(recharges: list[dict], periode: str,
                          sens: int, annuel: bool = False) -> str | None:
    """Periode visee par un raccourci clavier du selecteur (23/09/2026).

    sens -1 : Ctrl+Gauche, la periode precedente (comme la fleche ‹) ;
    sens +1 : Ctrl+Droite, la suivante (comme la fleche ›) ;
    sens 0  : Ctrl+Origine, le mois en cours (comme le bouton « Ce mois-ci »),
              toujours propose dans les menus meme sans recharge.

    None quand la touche ne mene nulle part : bout de l'historique, ou deja
    sur le mois en cours.

    `annuel=True` (barre de la page Statistiques) : Ctrl+Origine mene a
    l'annee en cours ; les fleches y parcourent deja les annees.
    """
    if sens == 0:
        courant = annee_en_cours() if annuel else mois_en_cours()
        return None if periode == courant else courant
    return periode_voisine(recharges, periode, sens)


def filtrer_par_periode(recharges: list[dict], periode: str) -> list[dict]:
    """Garde les recharges dont la date appartient a la periode demandee."""
    if periode == "Tout" or not recharges:
        return list(recharges)

    # Annee precise ("2025")
    if re.fullmatch(r"\d{4}", periode):
        return [r for r in recharges if r.get("date", "").startswith(periode)]

    # Mois precis ("Juin 2026"), accentue ou non
    parts = periode.split()
    numero = numero_du_mois(parts[0]) if len(parts) == 2 else None
    if numero is not None and parts[1].isdigit():
        prefixe = f"{parts[1]}-{numero:02d}"
        return [r for r in recharges if r.get("date", "").startswith(prefixe)]

    if periode == "30 derniers jours":
        def date_de(r):
            try:
                return datetime.fromisoformat(r.get("date", ""))
            except Exception:
                return None

        # 30 jours du calendrier, aujourd'hui compris : les memes que pour
        # l'abonnement et les frais (bornes_periode). Avant l'audit du
        # 14/10/2026, les recharges suivaient 30 x 24 h glissantes : a midi,
        # une recharge de la veille du premier jour au soir etait gardee,
        # mais pas les frais de ce jour-la.
        premier, dernier = _jours_des_30_derniers()
        return [r for r in recharges
                if (d := date_de(r)) is not None
                and premier <= d.date() <= dernier]

    return list(recharges)

def _jours_des_30_derniers() -> tuple[date, date]:
    """Premier et dernier jour de « 30 derniers jours » : 30 jours du
    calendrier, aujourd'hui compris. Une seule definition pour les
    recharges, l'abonnement et les frais."""
    aujourd_hui = datetime.now().date()
    return aujourd_hui - timedelta(days=29), aujourd_hui


def _fin_de_mois(annee: int, mois: int) -> date:
    """Dernier jour du mois indique."""
    if mois == 12:
        return date(annee, 12, 31)
    return date(annee, mois + 1, 1) - timedelta(days=1)

def bornes_periode(periode: str, recharges: list[dict]) -> tuple[date, date] | None:
    """Premier et dernier jour couverts par une periode, pour l'abonnement.

    L'abonnement est du au mois entier, meme si le mois n'est pas fini : sur
    « Juillet 2026 » affiche en juillet, on compte donc les 31 jours et pas
    seulement ceux qui separent la premiere de la derniere recharge. En
    revanche on ne va jamais au-dela du mois en cours : facturer des mois qui
    n'ont pas commence n'aurait pas de sens (sur « 2026 » en juillet, on
    s'arrete au 31 juillet).
    """
    now = datetime.now()
    limite = _fin_de_mois(now.year, now.month)

    def borner(debut: date, fin: date) -> tuple[date, date]:
        return debut, min(fin, limite)

    # Mois precis ("Juin 2026"), accentue ou non
    parts = periode.split()
    numero = numero_du_mois(parts[0]) if len(parts) == 2 else None
    if numero is not None and parts[1].isdigit():
        an, mo = int(parts[1]), numero
        return borner(date(an, mo, 1), _fin_de_mois(an, mo))

    # Annee precise ("2025")
    if re.fullmatch(r"\d{4}", periode):
        an = int(periode)
        return borner(date(an, 1, 1), date(an, 12, 31))

    if periode == "30 derniers jours":
        return borner(*_jours_des_30_derniers())

    if periode == "Tout":
        # de la toute premiere recharge jusqu'a la fin du mois en cours
        dates = sorted(r.get("date", "")[:10] for r in recharges if r.get("date"))
        if not dates:
            return None
        try:
            return borner(date.fromisoformat(dates[0]), limite)
        except ValueError:
            return None
    return None

def bornes_frais(periode: str, recharges: list[dict]) -> tuple[date, date] | None:
    """Premier et dernier jour couverts par une periode, pour les frais des
    cartes de recharge.

    Comme bornes_periode, sauf pour « Tout » : il ne commence pas a la
    premiere recharge, car une carte s'achete AVANT de s'en servir (defaut
    trouve le 28/09/2026 : deux cartes achetees avant la premiere recharge
    manquaient sur « Tout »). « Tout » compte alors tous les frais, jusqu'a
    la fin du mois en cours, meme sans aucune recharge.
    """
    if periode == "Tout":
        now = datetime.now()
        return date.min, _fin_de_mois(now.year, now.month)
    return bornes_periode(periode, recharges)


def mois_continus(mois_presents: list[str]) -> list[str]:
    """Complete une liste de mois 'AAAA-MM' par ceux qui manquent entre les deux bouts.

    Exemple : ['2024-01', '2024-04'] devient
    ['2024-01', '2024-02', '2024-03', '2024-04'].
    """
    if len(mois_presents) < 2:
        return list(mois_presents)
    annee, mois = (int(x) for x in mois_presents[0].split("-"))
    fin_annee, fin_mois = (int(x) for x in mois_presents[-1].split("-"))
    tous = []
    while (annee, mois) <= (fin_annee, fin_mois):
        tous.append(f"{annee}-{mois:02d}")
        mois += 1
        if mois == 13:
            annee, mois = annee + 1, 1
    return tous

def agreger_par(recharges: list[dict], champ: str, lieu: str | None = None,
                defaut: str = "Inconnu") -> dict[str, dict]:
    """Regroupe les recharges par valeur d'un champ (tarif, operateur, carte).

    `lieu` limite au besoin a « maison » ou « exterieur ». Retourne, pour
    chaque valeur : nombre de recharges, energie et cout cumules.
    """
    agregats: dict[str, dict] = {}
    for r in recharges:
        if lieu and r.get("lieu") != lieu:
            continue
        cle = r.get(champ) or defaut
        a = agregats.setdefault(cle, {"n": 0, "kwh": 0.0, "cout": 0.0})
        a["n"] += 1
        a["kwh"] += r.get("kwh", 0)
        a["cout"] += r.get("cout_eur", 0)
    return agregats

def filtrer_par_recherche(recharges: list[dict], texte: str) -> list[dict]:
    """Garde les recharges dont une information visible contient le texte.

    La recherche porte sur ce qui est affiche dans le tableau : operateur,
    tarif, lieu (« Maison », « Extérieur »), carte, date, energie, cout et
    prix, plus le mois en toutes lettres. Ainsi « ionity », « juillet »,
    « 39,55 », « 1 234,50 » ou « aire du lac » trouvent tous quelque chose.
    Les accents et le type d'espace ne comptent pas, et un montant ecrit a
    l'anglaise (« 39.55 ») est encore compris (corrige le 08/10/2026 : seul
    « 39.55 » trouvait, ni « 39,55 » affiche a l'ecran, ni « Extérieur »).
    """
    besoin = _texte_comparable(texte)
    # « 1 234,50 » : l'espace des milliers ne doit pas empecher de trouver
    # « 1234,50 », tel que le tableau l'affiche.
    besoin = re.sub(r"(?<=\d) (?=\d{3}(?!\d))", "", besoin)
    if not besoin:
        return list(recharges)
    trouvees = []
    for r in recharges:
        morceaux = [str(r.get(c, "")) for c in
                    ("operateur", "tarif_nom", "lieu_detail", "carte", "lieu")]
        morceaux.append("Maison" if r.get("lieu") == "maison" else "Extérieur")
        morceaux.append(fmt_date_fr(r.get("date", "")))
        try:
            quand = datetime.fromisoformat(r.get("date", ""))
            morceaux.append(f"{MOIS_FR[quand.month - 1]} {quand.year}")
        except ValueError:
            pass                    # date illisible : le reste suffit
        nombres = (f"{r.get('kwh', 0):.2f} {r.get('cout_eur', 0):.2f} "
                   f"{r.get('prix_kwh', 0):.4f}")
        morceaux.append(nombres.replace(".", ","))   # comme a l'ecran
        morceaux.append(nombres)                     # et a l'anglaise
        # Un retour a la ligne entre deux informations : une recherche ne
        # chevauche jamais la fin de l'une et le debut de l'autre.
        if besoin in _texte_comparable("\n".join(morceaux)):
            trouvees.append(r)
    return trouvees


def _texte_comparable(texte: str) -> str:
    """Minuscules, sans accents, espaces insecables ramenees a l'espace
    ordinaire : « Extérieur » et « exterieur » se comparent pareil."""
    texte = texte.replace("\xa0", " ").replace(" ", " ")
    return _sans_accents(texte).strip().lower()

def trier_recharges(recharges: list[dict], cle: str,
                    decroissant: bool) -> list[dict]:
    """Trie selon la colonne demandee de l'Historique."""
    def valeur(r):
        if cle == "info":
            # colonne mixte : le tarif pour la maison, l'operateur pour
            # l'exterieur
            return (r.get("tarif_nom") or r.get("operateur") or "").lower()
        if cle in ("kwh", "cout_eur", "prix_kwh"):
            return r.get(cle, 0)
        return str(r.get(cle, "")).lower()

    return sorted(recharges, key=valeur, reverse=decroissant)

def texte_resume(recharges: list[dict]) -> str:
    """Ligne « N recharges - X kWh - Y € - prix moyen » d'une selection.

    Le prix moyen des recharges exterieures est indique a part : il est bien
    plus eleve que celui de la maison, donc la moyenne globale prise seule
    serait trompeuse. Utilisee par l'Historique et les Statistiques.
    Nombres a la francaise (virgule decimale), comme partout a l'ecran.
    """
    def fr(v: float, decimales: int) -> str:
        return f"{v:,.{decimales}f}".replace(",", "\xa0").replace(".", ",")

    n = len(recharges)
    total_kwh = sum(r.get("kwh", 0) for r in recharges)
    total_cout = sum(r.get("cout_eur", 0) for r in recharges)
    txt = (f"   {n} recharge{'s' if n > 1 else ''} · {fr(total_kwh, 2)}\xa0kWh · "
           f"{fr(total_cout, 2)}\xa0€")
    if total_kwh:
        txt += f" · {fr(total_cout / total_kwh, 4)}\xa0€/kWh"
    exterieures = [r for r in recharges if r.get("lieu") == "exterieur"]
    kwh_ext = sum(r.get("kwh", 0) for r in exterieures)
    # inutile de repeter la moyenne si la selection ne contient QUE de
    # l'exterieur (elle serait identique a la moyenne globale)
    if kwh_ext and len(exterieures) != len(recharges):
        cout_ext = sum(r.get("cout_eur", 0) for r in exterieures)
        txt += f"   ·   extérieur : {fr(cout_ext / kwh_ext, 4)}\xa0€/kWh"
    return txt


def conseil_si_vide(aucune_recharge: bool) -> str:
    """La suite d'un message « Aucune recharge… » : un etat vide dit pourquoi
    ET comment continuer (charte, audit du 08/10/2026). Sans aucune recharge,
    comment commencer ; sinon, changer de periode."""
    if aucune_recharge:
        return ("Pour commencer, ajoutez une recharge (📝 Ajouter une "
                "recharge, à gauche) ou importez l'historique de votre borne "
                "(📥 Importer un CSV).")
    return ("Changez de période avec les flèches ‹ ›, ou choisissez "
            "« Toute la période ».")
