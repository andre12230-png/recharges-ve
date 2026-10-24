"""Gestionnaire de recharges de véhicule électrique.

Calcule le coût réel de chaque recharge selon les tarifs en vigueur
(grille définie dans tarifs.json), en ventilant HP/HC quand applicable.
"""

import calendar
import copy
import csv
import json
import math
import unicodedata
import os
import re
import shutil
import subprocess
import sys
import tempfile
import uuid
from datetime import date, datetime, timedelta
from pathlib import Path

from erreurs import erreur_en_clair
from formats import fmt_kwh, fmt_nb_recharges, fmt_nombre
# Durees vraies la nuit du changement d'heure (voir temps_reel.py).
from temps_reel import apres_duree, secondes_reelles as _secondes_reelles

# Emplacement des données (recharges.json, tarifs.json, backups, CSV).
#
# Trois cas, dans cet ordre :
#
# 1. Variable d'environnement RECHARGES_DATA_DIR : elle a toujours le dernier
#    mot. Les tests automatises la font pointer sur un dossier temporaire, et
#    elle permet aussi d'essayer l'application sur une copie des donnees.
# 2. En .exe, si le dossier parent de l'application porte deja des donnees :
#    on les laisse la. C'est l'emplacement historique — l'exe vit dans
#    dist\Recharges-VE\, les donnees dans dist\, suivies par git pour servir
#    de sauvegarde cloud. Une installation en service ne doit jamais voir ses
#    donnees changer de place sous ses pieds.
# 3. En .exe, sinon (premiere utilisation, archive decompressee ailleurs) :
#    un dossier personnel dans %LOCALAPPDATA%. Sans cela, les donnees
#    atterrissaient systematiquement un cran au-dessus de l'application, donc
#    n'importe ou : en vrac dans C:\Apps si l'archive y avait ete
#    decompressee, ou dans un C:\Program Files ou Windows interdit purement
#    et simplement d'ecrire — et l'application ne pouvait plus rien
#    enregistrer.
#
# En développement (.py) : le sous-dossier dist/ à côté du script, pour
# travailler sur EXACTEMENT les mêmes données que l'application livrée et
# éviter toute divergence entre les deux emplacements.
DOSSIER_APP = "Recharges VE"


def _dossier_installation_avec_donnees() -> Path | None:
    """Le dossier parent de l'exe, s'il porte deja des donnees. Sinon None."""
    parent = Path(sys.executable).parent.parent
    for marqueur in ("recharges.json", "tarifs.json", "backups"):
        if (parent / marqueur).exists():
            return parent
    return None


def _dossier_personnel() -> Path:
    """Le dossier de donnees d'un nouvel utilisateur, toujours inscriptible."""
    racine = os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA")
    return (Path(racine) if racine else Path.home()) / DOSSIER_APP


if os.environ.get("RECHARGES_DATA_DIR"):
    BASE = Path(os.environ["RECHARGES_DATA_DIR"])
elif getattr(sys, "frozen", False):
    BASE = _dossier_installation_avec_donnees() or _dossier_personnel()
else:
    BASE = Path(__file__).parent / "dist"
DATA_FILE = BASE / "recharges.json"
TARIFS_FILE = BASE / "tarifs.json"
BACKUP_DIR = BASE / "backups"
MAX_BACKUPS = 15
# En plus des 15 sauvegardes tournantes (qui couvrent quelques jours a peine
# quand on saisit beaucoup), la premiere sauvegarde de chaque journee est
# conservee a part pendant un mois. De quoi revenir en arriere longtemps
# apres coup, meme si le probleme n'a ete remarque que des semaines plus tard.
MAX_BACKUPS_QUOTIDIENS = 30


def dossier_donnees() -> Path:
    """Le dossier des données, tel qu'il est A CET INSTANT.

    À utiliser partout ailleurs plutôt que d'importer BASE : un
    `from recharges import BASE` fige la valeur au moment de l'import, et
    ne verrait pas une redirection faite ensuite.
    """
    return BASE


def rediriger_donnees(dossier: str | Path) -> None:
    """Fait pointer toutes les lectures et écritures vers un autre dossier.

    Sert à la vérification automatique (`--autotest`), qui travaille ainsi
    sur un jeu de démonstration figé au lieu des données de l'utilisateur.
    """
    global BASE, DATA_FILE, TARIFS_FILE, BACKUP_DIR
    BASE = Path(dossier)
    DATA_FILE = BASE / "recharges.json"
    TARIFS_FILE = BASE / "tarifs.json"
    BACKUP_DIR = BASE / "backups"
    vider_cache()


# ---------- chargement / sauvegarde ----------

# Renseigné (une seule fois) quand charger_donnees() a dû réparer un fichier
# illisible. L'application le lit au démarrage pour prévenir l'utilisateur :
# sans cela, la réparation passait totalement inaperçue dans la version .exe.
DERNIERE_RESTAURATION: dict | None = None

# Renseigné quand la copie de secours faite avant une écriture ordinaire a
# échoué (dossier backups/ protégé, disque plein...). L'écriture a eu lieu,
# mais sans filet : la fenêtre le dit une fois, puis remet la valeur à None.
# Avant l'audit du 14/10/2026, l'échec n'allait qu'à une console invisible.
ECHEC_BACKUP: str | None = None

# Les champs chiffrés d'une recharge : un nombre, ou vide (None).
_CHAMPS_NOMBRES = ("kwh", "kwh_hp", "kwh_hc", "cout_eur", "cout_wallbox",
                   "prix_kwh")


def _est_nombre(valeur) -> bool:
    """Vrai pour un entier ou un décimal fini (True/False ne comptent pas,
    ni NaN ni l'infini, que json.load accepte pourtant)."""
    return (isinstance(valeur, (int, float)) and not isinstance(valeur, bool)
            and math.isfinite(valeur))


def _est_date(valeur) -> bool:
    """Vrai pour une date lisible au format du fichier (« 2026-03-01T10:00 »,
    ou avec une espace et des secondes). « 2026-13-01 » est refusée."""
    if not isinstance(valeur, str):
        return False
    try:
        datetime.fromisoformat(valeur.replace(" ", "T"))
    except ValueError:
        return False
    return True


def structure_recharges_valide(data) -> bool:
    """Vrai si `data` a bien la forme d'un fichier de recharges.

    Un JSON lisible ne suffit pas : « {} » ou « {"recharges": {}} » se lisent
    très bien, mais ne contiennent rien d'utilisable, et passaient jusqu'ici
    pour une sauvegarde saine (audit du 14/10/2026). On vérifie donc :
    - un objet avec une liste « recharges » ;
    - chaque recharge est un objet, ses dates (début si présent, fin et
      heure de la borne si renseignées) des dates lisibles, ses champs
      chiffrés (s'ils sont présents) des nombres finis ou des vides ;
    - « releves_km », s'il existe, est une liste d'objets avec une date
      lisible, un kilométrage chiffré et une consommation chiffrée ou vide.
    Les champs facultatifs peuvent manquer : les anciens fichiers restent
    acceptés.

    Depuis l'analyse du 16/10/2026, une date impossible (« 2026-13-01 ») ou
    un nombre « NaN » ne passent plus : ils étaient acceptés au chargement,
    puis empêchaient une page de s'afficher. Le fichier est alors traité
    comme abîmé (réparé depuis la sauvegarde la plus récente, mis de côté,
    et l'utilisateur prévenu).
    """
    if not isinstance(data, dict) or not isinstance(data.get("recharges"),
                                                    list):
        return False
    for recharge in data["recharges"]:
        if not isinstance(recharge, dict):
            return False
        if "date" in recharge and not _est_date(recharge["date"]):
            return False
        for champ in ("fin", "debut_borne"):
            if recharge.get(champ) not in (None, "") and not _est_date(
                    recharge[champ]):
                return False
        for champ in _CHAMPS_NOMBRES:
            valeur = recharge.get(champ)
            if valeur is not None and not _est_nombre(valeur):
                return False
    releves = data.get("releves_km", [])
    if not isinstance(releves, list):
        return False
    for releve in releves:
        if not isinstance(releve, dict):
            return False
        if not _est_date(releve.get("date")) or not _est_nombre(
                releve.get("km")):
            return False
        if releve.get("conso") is not None and not _est_nombre(
                releve["conso"]):
            return False
    return True


def _fichier_lisible(chemin: Path, prefixe: str = "recharges") -> bool:
    """Vrai si le fichier contient du JSON exploitable.

    Pour les recharges, « exploitable » veut aussi dire « de la bonne forme »
    (voir structure_recharges_valide). Pour la grille tarifaire, un objet
    avec une liste « tarifs ».
    """
    try:
        with chemin.open("r", encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError, UnicodeDecodeError):
        return False
    if prefixe == "tarifs":
        return isinstance(data, dict) and isinstance(data.get("tarifs"), list)
    return structure_recharges_valide(data)


def _mettre_de_cote(chemin: Path) -> Path | None:
    """Range le fichier illisible à part, pour pouvoir y repêcher des saisies.

    Il n'est surtout pas mis dans backups/ (voir _creer_backup) : il est
    renommé sur place, à côté des données.
    """
    try:
        horodatage = datetime.now().strftime("%Y%m%d_%H%M%S")
        dest = chemin.with_name(f"recharges_illisible_{horodatage}.json")
        shutil.copy2(chemin, dest)
        return dest
    except OSError as e:
        print(f"[données] impossible de mettre le fichier de cote : {e}")
        return None


# Cache mémoire de recharges.json. Sans lui, chaque fonction rouvrait et
# reparsait le fichier : afficher une seule page en déclenchait une dizaine,
# à 1,5 ms l'unité aujourd'hui — et bien davantage à mesure que l'historique
# grossit. tarifs.json n'est volontairement PAS mis en cache : il ne coûte que
# 0,2 ms, et le partager exposerait la grille tarifaire à une modification
# accidentelle pour un gain négligeable.
_cache_donnees: dict | None = None
# Empreinte (date de modification, taille) de recharges.json au moment où le
# cache a été rempli. Le serveur mobile écrit dans le même fichier pendant que
# l'application de bureau est ouverte : sans ce contrôle, le cache de
# l'application, devenu périmé, écrasait à la sauvegarde suivante la recharge
# saisie depuis le téléphone.
_empreinte_cache: tuple[int, int] | None = None


def _empreinte_fichier() -> tuple[int, int] | None:
    try:
        st = DATA_FILE.stat()
    except OSError:
        return None
    return (st.st_mtime_ns, st.st_size)


def vider_cache() -> None:
    """Oublie les données gardées en mémoire ; la prochaine lecture ira au disque.

    À appeler si recharges.json a été remplacé dans le dos de l'application
    (restauration manuelle d'une sauvegarde, par exemple). Un remplacement
    est de toute façon détecté tout seul (voir _empreinte_cache).
    """
    global _cache_donnees, _empreinte_cache
    _cache_donnees = None
    _empreinte_cache = None


def charger_donnees(pour_modification: bool = False) -> dict:
    """Contenu de recharges.json, lu une fois puis gardé en mémoire.

    ATTENTION : par défaut, le dictionnaire renvoyé est CELUI du cache,
    partagé par tous les appelants. Il est fait pour être lu, pas modifié.

    Toute fonction qui s'apprête à le modifier doit demander
    `pour_modification=True`, qui en renvoie une copie indépendante. Sans
    cela, une modification abandonnée en cours de route (une validation qui
    refuse, un tarif manquant) resterait dans le cache et finirait écrite sur
    le disque par la première sauvegarde venue.
    """
    global _cache_donnees, _empreinte_cache
    empreinte = _empreinte_fichier()
    if _cache_donnees is None or empreinte != _empreinte_cache:
        _cache_donnees = _lire_donnees_du_disque()
        _empreinte_cache = empreinte
    return copy.deepcopy(_cache_donnees) if pour_modification else _cache_donnees


def _lire_donnees_du_disque() -> dict:
    """Lecture réelle du fichier, avec réparation depuis un backup si besoin."""
    global DERNIERE_RESTAURATION
    if not DATA_FILE.exists():
        # Premier lancement, ou fichier disparu d'un dossier déjà utilisé ?
        # Des sauvegardes valides trahissent le second cas : repartir à vide
        # aurait fait commencer un nouvel historique sans les anciennes
        # recharges (audit du 14/10/2026). On reprend la plus récente, et la
        # fenêtre prévient l'utilisateur.
        backup = _backup_le_plus_recent()
        if backup is None:
            return {"recharges": []}
        with backup.open("r", encoding="utf-8") as f:
            data = json.load(f)
        if DERNIERE_RESTAURATION is None:
            DERNIERE_RESTAURATION = {
                "cause": "absent",
                "backup": backup.name,
                "date_backup": datetime.fromtimestamp(backup.stat().st_mtime),
                "n_recharges": len(data["recharges"]),
                "mis_de_cote": None,
                "erreur": "",
            }
        return data
    try:
        with DATA_FILE.open("r", encoding="utf-8") as f:
            data = json.load(f)
        if not structure_recharges_valide(data):
            # Lisible, mais pas un fichier de recharges : traité comme un
            # fichier abîmé, réparé depuis une sauvegarde.
            raise json.JSONDecodeError(
                "le fichier n'a pas la forme d'un fichier de recharges",
                "", 0)
        return data
    except (json.JSONDecodeError, OSError, UnicodeDecodeError) as e:
        # Fichier corrompu : tenter de restaurer le backup le plus récent.
        # UnicodeDecodeError : fichier réenregistré par le Bloc-notes en
        # encodage Windows (un « é » dans un lieu). Il n'était pas rattrapé
        # jusqu'à la v2.0.0 : ni réparation, ni page Restaurer.
        backup = _backup_le_plus_recent()
        if backup:
            print(f"[données] recharges.json illisible ({e}), "
                  f"restauration depuis {backup.name}")
            with backup.open("r", encoding="utf-8") as f:
                data = json.load(f)
            # premier passage seulement : les appels suivants ne doivent pas
            # empiler des copies ni ecraser le message deja prepare
            if DERNIERE_RESTAURATION is None:
                mis_de_cote = _mettre_de_cote(DATA_FILE)
                DERNIERE_RESTAURATION = {
                    "cause": "illisible",
                    "backup": backup.name,
                    "date_backup": datetime.fromtimestamp(backup.stat().st_mtime),
                    "n_recharges": len(data.get("recharges", [])),
                    "mis_de_cote": mis_de_cote.name if mis_de_cote else None,
                    "erreur": str(e),
                }
            return data
        raise


def _creer_backup(fichier: Path | None = None,
                  prefixe: str = "recharges") -> None:
    """Copie l'état actuel dans backups/ avant de l'écraser, avec rotation.

    Sans argument, sauvegarde `recharges.json` — le cas courant. Appelée avec
    `(TARIFS_FILE, "tarifs")`, elle sauvegarde la grille tarifaire dans le
    même dossier et avec la même rotation : `tarifs.json` commande TOUS les
    montants de l'application, le perdre rendrait les recharges
    non recalculables, et il n'avait jusqu'ici qu'une seule copie de secours
    écrasée à chaque modification.
    """
    global ECHEC_BACKUP
    if fichier is None:
        fichier = DATA_FILE
    if not fichier.exists():
        return
    # Un fichier illisible ne doit JAMAIS entrer dans backups/ : il occuperait
    # une des 15 places de la rotation et chasserait une sauvegarde saine.
    if not _fichier_lisible(fichier, prefixe):
        print(f"[backup] {fichier.name} est illisible : aucune copie n'est "
              "faite dans backups/ (les sauvegardes saines sont preservees)")
        return
    try:
        BACKUP_DIR.mkdir(parents=True, exist_ok=True)
        maintenant = datetime.now()
        horodatage = maintenant.strftime("%Y%m%d_%H%M%S")
        dest = BACKUP_DIR / f"{prefixe}_{horodatage}.json"
        if not dest.exists():
            shutil.copy2(fichier, dest)
        # rotation : ne garder que les MAX_BACKUPS plus récents. Le « 2 » du
        # motif est le debut de l'annee : il evite d'attraper les sauvegardes
        # du jour, nommees {prefixe}_jour_...
        backups = sorted(BACKUP_DIR.glob(f"{prefixe}_2*.json"))
        for vieux in backups[:-MAX_BACKUPS]:
            vieux.unlink(missing_ok=True)

        # sauvegarde du jour : la premiere de la journee est mise de cote et
        # echappe a la rotation ci-dessus (nom different)
        du_jour = BACKUP_DIR / f"{prefixe}_jour_{maintenant:%Y%m%d}.json"
        if not du_jour.exists():
            shutil.copy2(fichier, du_jour)
        quotidiens = sorted(BACKUP_DIR.glob(f"{prefixe}_jour_*.json"))
        for vieux in quotidiens[:-MAX_BACKUPS_QUOTIDIENS]:
            vieux.unlink(missing_ok=True)
    except OSError as e:
        print(f"[backup] impossible : {e}")
        # L'écriture qui suit aura lieu quand même (refuser d'enregistrer
        # une saisie serait pire), mais l'utilisateur doit savoir qu'elle
        # se fait sans copie de secours.
        ECHEC_BACKUP = erreur_en_clair(e)


def _backup_le_plus_recent(prefixe: str = "recharges") -> Path | None:
    """La sauvegarde la plus recente qui soit VRAIMENT lisible.

    Le tri se fait sur la date de modification et non sur le nom, car les
    sauvegardes du jour (recharges_jour_...) et les horodatees
    (recharges_20260731_...) ne se classent pas dans le meme ordre
    alphabetique. Et une sauvegarde illisible est ecartee : restaurer un
    fichier casse par un autre fichier casse n'avancerait a rien.
    """
    if not BACKUP_DIR.exists():
        return None
    backups = sorted(BACKUP_DIR.glob(f"{prefixe}_*.json"),
                     key=lambda p: p.stat().st_mtime, reverse=True)
    for backup in backups:
        if _fichier_lisible(backup, prefixe):
            return backup
    return None


def _relancer_au_nom_de(e: Exception, cible: Path) -> None:
    """Relance l'erreur d'une ecriture ratee en nommant le fichier que
    l'utilisateur connait (recharges.json), et non le fichier temporaire
    (« tmpo85oyjiz.tmp ») dont parlait le message (audit du 08/10/2026)."""
    if isinstance(e, OSError) and e.filename and str(e.filename).endswith(
            ".tmp"):
        raise type(e)(e.errno, e.strerror, str(cible)) from e
    raise e


def sauvegarder_donnees(data: dict) -> None:
    """Sauvegarde atomique : backup, écriture dans un fichier temporaire,
    fsync, puis remplacement atomique. Évite toute corruption en cas de crash."""
    global _cache_donnees, _empreinte_cache
    DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
    _creer_backup()
    fd, tmp = tempfile.mkstemp(dir=str(DATA_FILE.parent), suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, DATA_FILE)  # atomique sur un même volume
    except Exception as e:
        Path(tmp).unlink(missing_ok=True)
        _relancer_au_nom_de(e, DATA_FILE)
    # L'ecriture a reussi : le cache reflete desormais ce qui est sur le
    # disque. Mis a jour APRES le os.replace, pour qu'une ecriture ratee ne
    # laisse pas le cache en avance sur le fichier.
    _cache_donnees = data
    _empreinte_cache = _empreinte_fichier()


def lister_backups() -> list[dict]:
    """Les sauvegardes de recharges.json, de la plus récente à la plus ancienne.

    Chaque fiche donne le chemin, la date, la taille et le nombre de recharges
    — c'est ce dernier chiffre qui permet de choisir : « celle d'avant-hier,
    qui en contient 249 ». Une sauvegarde illisible garde n_recharges à None
    au lieu d'être cachée : mieux vaut la voir et savoir qu'elle ne vaut rien.
    """
    if not BACKUP_DIR.exists():
        return []
    fiches = []
    for chemin in BACKUP_DIR.glob("recharges_*.json"):
        infos = chemin.stat()
        fiche = {
            "chemin": chemin,
            "nom": chemin.name,
            "date": datetime.fromtimestamp(infos.st_mtime),
            "taille": infos.st_size,
            "n_recharges": None,
            # « du jour » : la copie mise de côté en début de journée, qui
            # échappe à la rotation des 15 et vit un mois.
            "quotidienne": "_jour_" in chemin.name,
        }
        try:
            with chemin.open("r", encoding="utf-8") as f:
                contenu = json.load(f)
            # Une sauvegarde de mauvaise forme est montrée comme illisible.
            if structure_recharges_valide(contenu):
                fiche["n_recharges"] = len(contenu["recharges"])
        except (json.JSONDecodeError, OSError, TypeError, AttributeError,
                UnicodeDecodeError):
            pass          # illisible : signalé comme tel dans l'interface
        fiches.append(fiche)
    fiches.sort(key=lambda f: f["date"], reverse=True)
    return fiches


def restaurer_backup(chemin: str | Path) -> int:
    """Remplace recharges.json par cette sauvegarde. Renvoie le nb de recharges.

    L'état actuel n'est pas perdu : il est mis de côté avant d'écrire. Une
    restauration faite par erreur peut donc être annulée en restaurant la
    sauvegarde qui vient d'être créée. Si cette copie échoue, la restauration
    est refusée : l'interface promet qu'on pourra revenir en arrière, et
    remplacer les données sans filet trahirait cette promesse (audit du
    14/10/2026).
    """
    chemin = Path(chemin)
    if not chemin.exists():
        raise ValueError(f"Sauvegarde introuvable : {chemin.name}.")
    try:
        with chemin.open("r", encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError, UnicodeDecodeError) as e:
        raise ValueError(f"« {chemin.name} » est illisible : impossible de "
                         f"restaurer cette sauvegarde. {erreur_en_clair(e)}")
    if not structure_recharges_valide(data):
        raise ValueError(f"« {chemin.name} » ne ressemble pas à un fichier de "
                         "recharges : restauration refusée.")
    _copier_avant_restauration()
    sauvegarder_donnees(data)
    return len(data["recharges"])


def _copier_avant_restauration() -> Path | None:
    """Met l'état courant de côté sous un nom qui lui est propre.

    Renvoie la copie, ou None s'il n'y avait rien à copier (aucun fichier).
    Lève ValueError si la copie n'a pas pu se faire : la restauration doit
    alors s'arrêter.

    La rotation ordinaire ne crée qu'une copie par seconde (elle évite ainsi
    d'engloutir ses 15 places lors d'une rafale d'écritures). Ça ne suffit pas
    ici : restaurer deux fois de suite ferait disparaître l'état intermédiaire,
    justement celui qu'on veut pouvoir reprendre si la restauration était une
    erreur. On ajoute donc un numéro tant que le nom est déjà pris.
    """
    if not DATA_FILE.exists():
        return None
    if not _fichier_lisible(DATA_FILE):
        # Un fichier illisible n'entre pas dans backups/ (voir _creer_backup),
        # mais il ne doit pas non plus disparaître sous la restauration : on
        # le range à côté, comme le fait la réparation du démarrage.
        copie = _mettre_de_cote(DATA_FILE)
        if copie is None:
            raise ValueError(_REFUS_SANS_COPIE)
        return copie
    try:
        BACKUP_DIR.mkdir(parents=True, exist_ok=True)
        horodatage = datetime.now().strftime("%Y%m%d_%H%M%S")
        dest = BACKUP_DIR / f"recharges_{horodatage}.json"
        suffixe = 1
        while dest.exists():
            dest = BACKUP_DIR / f"recharges_{horodatage}_{suffixe}.json"
            suffixe += 1
        shutil.copy2(DATA_FILE, dest)
        return dest
    except OSError as e:
        raise ValueError(f"{_REFUS_SANS_COPIE} {erreur_en_clair(e)}") from e


_REFUS_SANS_COPIE = (
    "Vos données actuelles n'ont pas pu être mises de côté : la restauration "
    "est annulée, rien n'a été remplacé.")


# Réglages d'une installation neuve. Volontairement neutres : ils ne décrivent
# aucune voiture, aucun fournisseur d'électricité et aucune wallbox en
# particulier. La grille tarifaire est vide, c'est à l'utilisateur de saisir
# la sienne dans la page Tarifs.
REGLAGES_PAR_DEFAUT = {
    "correction_csv_minutes": 0,
    "rendement_charge": 0.90,
    "capacite_batterie": 0,
    "tarifs": [],
}

# Passe à True quand _creer_tarifs_par_defaut() a fabriqué le fichier, c'est-à-
# dire au tout premier démarrage. L'application le lit pour accueillir le
# nouvel arrivant et l'envoyer saisir ses prix.
PREMIER_DEMARRAGE = False

# Renseigné quand tarifs.json a disparu chez un utilisateur déjà installé :
# {"copie": nom de la copie remise en place, "date": sa date} — ou les deux à
# None si aucune copie n'a été trouvée. L'application le lit au démarrage
# pour prévenir. Jusqu'à la v2.0.0, ce cas passait pour un premier démarrage
# (« Bienvenue »), sans rien dire de la perte ni des copies existantes.
INCIDENT_TARIFS: dict | None = None


def _copie_de_tarifs_lisible() -> Path | None:
    """La copie de tarifs.json la plus récente qui soit vraiment une grille."""
    candidates = []
    if BACKUP_DIR.exists():
        candidates = sorted(BACKUP_DIR.glob("tarifs_*.json"),
                            key=lambda p: p.stat().st_mtime, reverse=True)
    avant = TARIFS_FILE.with_suffix(".json.avant")
    if avant.exists():
        candidates.append(avant)
    for chemin in candidates:
        try:
            contenu = json.loads(chemin.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError, UnicodeDecodeError):
            continue
        if isinstance(contenu, dict) and isinstance(contenu.get("tarifs"), list):
            return chemin
    return None


def _tarifs_disparus() -> dict:
    """tarifs.json est absent : premier démarrage, ou fichier perdu ?

    - une copie existe (backups/ ou tarifs.json.avant) : elle est remise en
      place, et l'utilisateur en est prévenu ;
    - aucune copie, mais des recharges existent : grille vide, et
      l'utilisateur est prévenu de la perte (ce n'est pas un premier
      démarrage) ;
    - ni l'un ni l'autre : vrai premier démarrage, accueil habituel.
    """
    global INCIDENT_TARIFS, PREMIER_DEMARRAGE
    copie = _copie_de_tarifs_lisible()
    if copie is not None:
        TARIFS_FILE.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(copie, TARIFS_FILE)
        INCIDENT_TARIFS = {
            "copie": copie.name,
            "date": datetime.fromtimestamp(copie.stat().st_mtime),
        }
        return json.loads(TARIFS_FILE.read_text(encoding="utf-8"))
    contenu = _creer_tarifs_par_defaut()
    if DATA_FILE.exists():
        PREMIER_DEMARRAGE = False
        INCIDENT_TARIFS = {"copie": None, "date": None}
    return contenu


def _creer_tarifs_par_defaut() -> dict:
    """Fabrique un tarifs.json neuf, et le renvoie.

    Sans ce filet, une installation neuve était dans une impasse : faute de
    tarifs.json, le tableau de bord affichait une erreur — et la page Tarifs,
    la seule qui aurait permis de saisir ses prix, affichait la même. Il
    fallait créer le fichier à la main au Bloc-notes pour sortir de là.
    """
    global PREMIER_DEMARRAGE
    contenu = copy.deepcopy(REGLAGES_PAR_DEFAUT)
    TARIFS_FILE.parent.mkdir(parents=True, exist_ok=True)
    TARIFS_FILE.write_text(
        json.dumps(contenu, indent=2, ensure_ascii=False), encoding="utf-8")
    PREMIER_DEMARRAGE = True
    return contenu


def _lire_tarifs_json() -> dict:
    """Lit tarifs.json en entier, ou lève une erreur compréhensible.

    Toutes les lectures du fichier passent par ici. Auparavant seule
    charger_tarifs() était protégée : un fichier corrigé à la main et cassé
    faisait remonter un JSONDecodeError brut depuis charger_config(), et
    l'utilisateur voyait du jargon Python dans la boîte « Erreur ».

    Fichier absent : première utilisation, ou fichier perdu. Voir
    _tarifs_disparus : une copie est remise en place s'il en existe une,
    sinon on en fabrique un vide de tarifs plutôt que de bloquer
    l'application.
    """
    try:
        with TARIFS_FILE.open("r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        try:
            return _tarifs_disparus()
        except OSError as e:
            raise FileNotFoundError(
                f"Fichier de tarifs introuvable : {TARIFS_FILE}, et il n'a pas "
                f"pu être créé. {erreur_en_clair(e)} Vérifiez que ce dossier "
                "existe et qu'il est accessible en écriture."
            )
    except (json.JSONDecodeError, UnicodeDecodeError) as e:
        # _ecrire_tarifs conserve une copie d'avant la derniere modification :
        # autant l'indiquer, c'est la sortie de secours la plus simple.
        secours = TARIFS_FILE.with_suffix(".json.avant")
        piste = (f" Une copie d'avant la dernière modification existe "
                 f"({secours.name}) : vous pouvez la renommer en "
                 f"{TARIFS_FILE.name}.") if secours.exists() else ""
        raise ValueError(
            f"tarifs.json est invalide. {erreur_en_clair(e)} S'il a été "
            f"modifié à la main, c'est à cet endroit qu'il faut regarder.{piste}"
        )


def charger_tarifs() -> list[dict]:
    d = _lire_tarifs_json()
    try:
        tarifs = d["tarifs"]
    except (KeyError, TypeError):
        raise ValueError(
            'tarifs.json est invalide : la clé "tarifs" est absente ou le '
            "fichier ne contient pas ce qui est attendu."
        )
    if not isinstance(tarifs, list):
        raise ValueError(
            'tarifs.json est invalide : la clé "tarifs" devrait contenir une '
            "liste de périodes tarifaires.")
    # Défaut A4 : chaque période est vérifiée avec les mêmes règles qu'une
    # saisie de la page Tarifs. Un fichier modifié à la main ne doit pas
    # faire calculer des coûts faux sans prévenir. Les tarifs sont rendus
    # tels qu'ils sont écrits : la vérification ne les modifie pas.
    secours = TARIFS_FILE.with_suffix(".json.avant")
    piste = (f" Une copie d'avant la dernière modification existe "
             f"({secours.name}) : vous pouvez la renommer en "
             f"{TARIFS_FILE.name}.") if secours.exists() else ""
    for numero, tarif in enumerate(tarifs, start=1):
        if not isinstance(tarif, dict):
            raise ValueError(
                f"tarifs.json est invalide : la période n° {numero} n'est pas "
                f"une période tarifaire.{piste}")
        try:
            valider_tarif(tarif)
        except ValueError as e:
            nom = str(tarif.get("nom") or f"n° {numero}")
            raise ValueError(
                f"tarifs.json est invalide : le tarif « {nom} » est refusé. "
                f"{e} S'il a été modifié à la main, c'est à cet endroit "
                f"qu'il faut regarder.{piste}")
    return tarifs


def charger_config() -> dict:
    """Charge la configuration globale (correction d'horloge, références...)."""
    d = _lire_tarifs_json()
    return {
        "correction_csv_minutes": int(d.get("correction_csv_minutes", 0)),
        # Rendement de charge : une partie de l'énergie prise à la prise part
        # en chaleur et n'arrive jamais à la batterie. La consommation de
        # référence, elle, est saisie avec chaque relevé kilométrique.
        "rendement_charge": float(d.get("rendement_charge", 0.90) or 0.90),
        # Le reglage "theme" des anciens fichiers n'est plus lu : l'application
        # n'a plus qu'un theme, le clair (v1.24.0). Il reste dans le fichier,
        # sans effet, pour ne rien reecrire sans raison.
        # Capacite de la batterie de la voiture, en kWh. Sert de marge au
        # controle « des recharges manquent-elles ? » : l'ecart provoque par
        # l'etat de charge aux deux bouts ne peut pas la depasser.
        # 0 = non renseignee (on se rabat sur la plus grosse recharge vue).
        "capacite_batterie": float(d.get("capacite_batterie", 0) or 0),
        # Puissance de charge de la borne, en kW (23/10/2026). Sert a compter
        # l'energie des le debut de la recharge, a pleine puissance, plutot
        # que repartie sur toute la duree ou la voiture reste branchee.
        # 0 = inconnue : repartition uniforme, comme avant.
        "puissance_borne_kw": float(d.get("puissance_borne_kw", 0) or 0),
        # Voiture essence de comparaison (28/09/2026) : consommation en
        # L/100 km et prix du litre, saisis par l'utilisateur. 0 = pas de
        # comparaison (fichiers plus anciens, ou cases laissees vides).
        "conso_essence": float(d.get("conso_essence", 0) or 0),
        "prix_essence": float(d.get("prix_essence", 0) or 0),
        # Prix du litre par annee, facultatifs : {"2023": 1.87, ...}.
        "prix_essence_annees": {
            str(k): float(v)
            for k, v in (d.get("prix_essence_annees") or {}).items() if v},
        # Jour ou la comparaison a ete enregistree pour la derniere fois
        # (AAAA-MM-JJ), pour le rappel du prix du litre. None : inconnu.
        "prix_essence_maj": d.get("prix_essence_maj") or None,
        # Part de l'abonnement de la maison attribuee a la voiture, en pour
        # cent (10/10/2026). Affichee a part sur le tableau de bord, jamais
        # dans le cout des recharges. 0 = pas de part (fichiers plus
        # anciens, ou case laissee vide).
        "part_abonnement_voiture":
            float(d.get("part_abonnement_voiture", 0) or 0),
        # Jour de la derniere sauvegarde externe reussie (AAAA-MM-JJ), pour
        # le rappel du tableau de bord (28/09/2026). None : jamais faite.
        "sauvegarde_externe_derniere":
            d.get("sauvegarde_externe_derniere") or None,
    }


def enregistrer_config(modifs: dict) -> None:
    """Met à jour des réglages dans tarifs.json sans toucher au reste.

    La grille tarifaire est précieuse : on relit le fichier, on modifie
    seulement les clés demandées, et on réécrit par _ecrire_tarifs — qui
    s'occupe de l'écriture atomique et des sauvegardes. Auparavant cette
    fonction refaisait l'écriture de son côté, sans aucune copie de secours.
    """
    d = _lire_tarifs_json()
    d.update(modifs)
    _ecrire_tarifs(d)


def valider_reglages(capacite: str, rendement_pct: str,
                     correction: str, puissance: str = "") -> dict:
    """Contrôle les réglages de la voiture et de la borne saisis dans la
    page Paramètres, et les renvoie prêts pour enregistrer_config().

    La puissance de charge de la borne (23/10/2026) est facultative : case
    vide = 0, l'énergie reste répartie sur toute la recharge.

    Jusqu'à la v1.25.0, ils ne se modifiaient qu'au Bloc-notes dans
    tarifs.json : un débutant n'y touchait jamais, et une virgule mal placée
    rendait le fichier illisible. Les saisies sont écrites comme on les
    tape : virgule décimale, rendement en pour cent (90 et non 0.9). Une
    case vide reprend la valeur neutre.
    """
    def nombre(texte: str, nom: str) -> float | None:
        t = texte.strip().replace(" ", "").replace(",", ".")
        if not t:
            return None
        try:
            return float(t)
        except ValueError:
            raise ValueError(f"{nom} : « {texte.strip()} » n'est pas un nombre.")

    cap = nombre(capacite, "Capacité de la batterie")
    cap = 0.0 if cap is None else cap
    if not 0 <= cap <= 200:
        raise ValueError(
            "Capacité de la batterie : entre 0 et 200\xa0kWh (laissez 0 si vous "
            "ne la connaissez pas).")

    rend = nombre(rendement_pct, "Rendement de charge")
    rend = 90.0 if rend is None else rend
    if not 50 <= rend <= 100:
        raise ValueError(
            "Rendement de charge : en pour cent, entre 50 et 100 (90 convient "
            "à la plupart des voitures).")

    corr = nombre(correction, "Correction de l'horloge")
    corr = 0.0 if corr is None else corr
    if corr != int(corr) or not -720 <= corr <= 720:
        raise ValueError(
            "Correction de l'horloge : un nombre entier de minutes, entre "
            "-720 et 720 (-60 recule d'une heure).")

    puis = nombre(puissance, "Puissance de charge de la borne")
    puis = 0.0 if puis is None else puis
    if puis and not 1 <= puis <= 50:
        raise ValueError(
            "Puissance de charge de la borne : entre 1 et 50\xa0kW (7,4 pour "
            "une borne domestique courante), ou case vide si vous ne la "
            "connaissez pas.")

    return {"capacite_batterie": round(cap, 1),
            "rendement_charge": round(rend / 100, 3),
            "correction_csv_minutes": int(corr),
            "puissance_borne_kw": round(puis, 1)}


def valider_part_abonnement(texte: str) -> dict:
    """Controle la case « Part de l'abonnement liee a la voiture » (page
    Parametres, 10/10/2026) et la renvoie prete pour enregistrer_config().

    En pour cent, de 0 a 100. Case vide : 0, pas de part affichee. Aucune
    valeur n'est proposee d'avance : elle depend de chaque foyer."""
    t = texte.strip().replace(" ", "").replace(",", ".")
    if not t:
        return {"part_abonnement_voiture": 0.0}
    try:
        pct = float(t)
    except ValueError:
        raise ValueError(f"Part de l'abonnement : « {texte.strip()} » "
                         "n'est pas un nombre.")
    if not 0 <= pct <= 100:
        raise ValueError("Part de l'abonnement : en pour cent, entre 0 et "
                         "100 (laissez vide pour ne pas l'afficher).")
    return {"part_abonnement_voiture": round(pct, 1)}


def valider_comparaison_essence(conso: str, prix: str) -> dict:
    """Controle les deux cases de la voiture essence de comparaison (page
    Parametres) et les renvoie prets pour enregistrer_config().

    Les deux vides : pas de comparaison (0 et 0). Une seule remplie : refus,
    le calcul a besoin des deux. Aucun prix n'est propose d'avance : un prix
    ecrit dans le code vieillirait sans prevenir."""
    def nombre(texte: str, nom: str) -> float | None:
        t = texte.strip().replace(" ", "").replace(",", ".")
        if not t:
            return None
        try:
            return float(t)
        except ValueError:
            raise ValueError(
                f"{nom} : « {texte.strip()} » n'est pas un nombre.") from None

    litres = nombre(conso, "Consommation")
    euros = nombre(prix, "Prix du litre")
    if litres is None and euros is None:
        return {"conso_essence": 0.0, "prix_essence": 0.0}
    if litres is None or euros is None:
        raise ValueError("Remplissez les deux cases (consommation et prix du "
                         "litre), ou laissez-les vides toutes les deux.")
    if not 2 <= litres <= 30:
        raise ValueError("Consommation : en litres aux 100\xa0km, entre 2 et 30.")
    if not 0.5 <= euros <= 5:
        raise ValueError("Prix du litre : en euros, entre 0,50 et 5.")
    return {"conso_essence": round(litres, 2), "prix_essence": round(euros, 3)}


def valider_prix_annees(textes: dict[str, str]) -> dict[str, float]:
    """Les prix du litre par annee (page Parametres), facultatifs : une case
    vide est ignoree, l'annee prend alors le prix general. Rend
    {"2023": 1.87, ...}, pret pour enregistrer_config(). Leve ValueError en
    nommant l'annee fautive."""
    prix = {}
    for annee, texte in textes.items():
        t = texte.strip().replace(" ", "").replace(",", ".")
        if not t:
            continue
        try:
            valeur = float(t)
        except ValueError:
            raise ValueError(f"Prix du litre {annee} : « {texte.strip()} » "
                             "n'est pas un nombre.") from None
        if not 0.5 <= valeur <= 5:
            raise ValueError(
                f"Prix du litre {annee} : en euros, entre 0,50 et 5.")
        prix[str(annee)] = round(valeur, 3)
    return prix


def kilometres_par_annee(releves: list[dict] | None = None,
                         recharges: list[dict] | None = None
                         ) -> dict[int, dict]:
    """Kilometres, energie et cout des recharges de chaque annee, tires des
    releves du compteur (28/09/2026).

    Les kilometres ne se connaissent qu'entre deux releves. Quand un
    intervalle chevauche plusieurs annees, ses kilometres sont partages au
    calendrier (au prorata du temps passe dans chaque annee). Un partage
    selon l'energie rechargee a ete essaye d'abord : il suivait l'energie
    ENREGISTREE, et qui recharge souvent gratuitement chez des proches
    obtenait des annees invraisemblables (1 914 km une annee, 33 316 la
    suivante). Le cout, lui, suit la date de chaque recharge. Une recharge
    compte dans l'intervalle qui la suit, comme dans calculer_consommation
    (apres le premier releve, jusqu'au second inclus).

    Rend {annee: {"km", "kwh", "cout", "debut", "fin"}}, ou debut et fin
    disent quelle partie de l'annee les releves couvrent. Vide avec moins
    de deux releves."""
    if releves is None:
        releves = charger_releves_km()
    if recharges is None:
        recharges = charger_donnees()["recharges"]
    releves = sorted(releves, key=lambda x: x.get("date", ""))
    annees: dict[int, dict] = {}
    for precedent, suivant in zip(releves, releves[1:]):
        km = suivant["km"] - precedent["km"]
        dedans = [x for x in recharges
                  if precedent["date"] < x.get("date", "") <= suivant["date"]]
        t0 = datetime.fromisoformat(precedent["date"])
        t1 = datetime.fromisoformat(suivant["date"])
        duree = (t1 - t0).total_seconds()
        for annee in range(t0.year, t1.year + 1):
            de_l_annee = [x for x in dedans
                          if x.get("date", "")[:4] == str(annee)]
            kwh = sum(x.get("kwh", 0) for x in de_l_annee)
            cout = sum(x.get("cout_eur", 0) for x in de_l_annee)
            debut = max(t0, datetime(annee, 1, 1))
            fin = min(t1, datetime(annee + 1, 1, 1))
            part = (fin - debut).total_seconds() / duree if duree else 0
            a = annees.setdefault(annee, {"km": 0.0, "kwh": 0.0, "cout": 0.0,
                                          "debut": None, "fin": None})
            a["km"] += km * part
            a["kwh"] += kwh
            a["cout"] += cout
            # La fin d'annee s'affiche au 31/12, pas au 01/01 suivant.
            fin_affichee = min(t1, datetime(annee, 12, 31, 23, 59))
            debut_iso = debut.isoformat(timespec="minutes")
            fin_iso = fin_affichee.isoformat(timespec="minutes")
            a["debut"] = min(a["debut"] or debut_iso, debut_iso)
            a["fin"] = max(a["fin"] or fin_iso, fin_iso)
    for a in annees.values():
        a["km"] = round(a["km"], 1)
        a["kwh"] = round(a["kwh"], 2)
        a["cout"] = round(a["cout"], 2)
    return annees


def comparer_essence_periode(periode: str, config: dict,
                             releves: list[dict] | None = None,
                             recharges: list[dict] | None = None
                             ) -> dict | None:
    """Ce qu'auraient coute en essence les kilometres de « Tout » ou d'une
    annee (« 2025 »), face a l'electricite reellement payee.

    Les kilometres viennent de kilometres_par_annee (entre releves du
    compteur). Chaque annee a son prix du litre s'il est saisi, sinon le
    prix general. L'electricite est le cout des recharges, sans abonnement
    ni frais de cartes, comme le cout aux 100 km. Rien sans reglage, sans
    kilometres ou sans energie : une « economie totale » serait fausse.
    Une autre periode (un mois, « 30 derniers jours ») n'a pas de sens ici :
    rien non plus.

    « part_non_enregistree » : le pourcentage de l'energie de ces
    kilometres qui ne figure pas dans les recharges saisies (recharges
    gratuites chez des proches, par exemple), d'apres la consommation
    affichee par la voiture ; None s'il n'y a rien a signaler (pas de
    consommation affichee, ecart sous le seuil de controler_energie, ou que
    la marge d'une batterie pleine ou vide suffit a expliquer). C'est une
    estimation : l'origine et le prix de cette energie ne sont pas connus.

    « sans_km » : les annees qui ont des recharges mais aucun kilometre ;
    leur cout est dans le total, pas dans « par_annee »."""
    litres_100 = config.get("conso_essence", 0) or 0
    prix_general = config.get("prix_essence", 0) or 0
    if not (litres_100 > 0 and prix_general > 0):
        return None
    if releves is None:
        releves = charger_releves_km()
    annees = kilometres_par_annee(releves, recharges)
    if periode == "Tout":
        choisies = sorted(annees)
    elif re.fullmatch(r"\d{4}", periode):
        choisies = [int(periode)] if int(periode) in annees else []
    else:
        return None
    prix_annees = config.get("prix_essence_annees") or {}
    lignes = []
    # Une annee sans kilometres (une recharge datee de l'instant meme d'un
    # releve du 1er janvier, par exemple) ne fait pas de ligne annuelle : son
    # cout aux 100 km n'existe pas. Mais son energie et son cout restent dans
    # le total : les retirer faisait apparaitre une economie qui n'existe pas
    # (audit du 14/10/2026). On la nomme a part pour que le total s'explique.
    sans_km = []
    for annee in choisies:
        a = annees[annee]
        if a["km"] <= 0:
            if a["cout"] or a["kwh"]:
                sans_km.append({"annee": annee, "cout_electrique": a["cout"],
                                "kwh": a["kwh"]})
            continue
        prix = prix_annees.get(str(annee)) or prix_general
        litres = a["km"] * litres_100 / 100
        lignes.append({"annee": annee, "km": a["km"], "kwh": a["kwh"],
                       "litres": litres, "prix": prix,
                       "essence": litres * prix, "electrique": a["cout"],
                       "debut": a["debut"], "fin": a["fin"]})
    km = sum(x["km"] for x in lignes)
    kwh = (sum(x["kwh"] for x in lignes)
           + sum(x["kwh"] for x in sans_km))
    if km <= 0 or kwh <= 0:
        return None
    litres = sum(x["litres"] for x in lignes)
    essence = sum(x["essence"] for x in lignes)
    electrique = (sum(x["electrique"] for x in lignes)
                  + sum(x["cout_electrique"] for x in sans_km))
    # L'energie qu'ont du demander ces kilometres, face a celle des
    # recharges saisies : le controle du Kilometrage lui-meme, marge de la
    # batterie comprise. Sans elle, un ecart qu'une batterie partie pleine
    # suffisait a expliquer etait annonce comme de l'energie venue d'ailleurs
    # (audit du 14/10/2026).
    part = None
    if recharges is None:
        recharges = charger_donnees()["recharges"]
    controle = controler_energie(km, kwh, conso_reference(releves),
                                 marge_batterie(config, recharges), config)
    if controle["verdict"] == "energie_exterieure":
        part = round(-controle["ecart_pct"])
    return {
        "km": round(km, 1), "litres": round(litres, 1),
        "cout_essence": round(essence, 2),
        "cout_electrique": round(electrique, 2),
        "economie": round(essence - electrique, 2),
        "cout_100_essence": round(100 * essence / km, 2),
        "cout_100_electrique": round(100 * electrique / km, 2),
        "conso_essence": litres_100,
        # Plusieurs annees a des prix differents : le prix moyen pondere.
        "prix_essence": round(essence / litres, 3),
        "debut": min(x["debut"] for x in lignes),
        "fin": max(x["fin"] for x in lignes),
        "part_non_enregistree": part,
        "sans_km": sans_km,
        "par_annee": [{
            "annee": x["annee"], "km": x["km"], "litres": round(x["litres"], 1),
            "prix": x["prix"], "cout_essence": round(x["essence"], 2),
            "cout_electrique": round(x["electrique"], 2),
            "economie": round(x["essence"] - x["electrique"], 2)}
            for x in lignes],
    }


# ---------- modification de la grille tarifaire ----------

def _verifier_heure(texte: str) -> str:
    """Controle une heure « HH:MM » et la renvoie normalisee."""
    try:
        h, m = texte.strip().split(":")
        heure, minute = int(h), int(m)
        if not (0 <= heure <= 23 and 0 <= minute <= 59):
            raise ValueError
    except Exception:
        raise ValueError(
            f"Heure invalide : « {texte} ». Format attendu : HH:MM "
            "(par exemple 23:45).")
    return f"{heure:02d}:{minute:02d}"


def _montant_tarif(valeur, libelle: str) -> float:
    """Un prix ou un abonnement lu en nombre, ou ValueError en clair.

    Défaut A4 : float() acceptait « NaN » et « Infinity » (un tarifs.json
    modifié à la main), et les coûts devenaient invalides sans un mot. Un
    texte comme « vingt » remontait, lui, un message Python en anglais.
    """
    try:
        nombre = float(valeur)
    except (TypeError, ValueError):
        raise ValueError(f"{libelle} n'est pas un nombre lisible.")
    if not math.isfinite(nombre):
        raise ValueError(f"{libelle} n'est pas un nombre valable.")
    return nombre


def valider_tarif(tarif: dict) -> dict:
    """Verifie un tarif et le renvoie propre, ou leve ValueError.

    La grille tarifaire commande tous les montants de l'application : mieux
    vaut refuser une saisie douteuse que recalculer 250 recharges de travers.
    """
    propre = dict(tarif)
    if not propre.get("nom", "").strip():
        raise ValueError("Le nom du tarif est obligatoire.")
    propre["nom"] = propre["nom"].strip()

    try:
        debut = datetime.fromisoformat(propre["debut"]).date()
    except Exception:
        raise ValueError("La date de début est obligatoire et doit etre valide.")
    fin = None
    if propre.get("fin"):
        try:
            fin = datetime.fromisoformat(propre["fin"]).date()
        except Exception:
            raise ValueError("La date de fin est invalide.")
        if fin < debut:
            raise ValueError("La date de fin doit venir après la date de début.")
    propre["fin"] = fin.isoformat() if fin else None

    if _montant_tarif(propre.get("abonnement_mensuel", 0),
                      "L'abonnement mensuel") < 0:
        raise ValueError("L'abonnement mensuel ne peut pas etre negatif.")

    if propre.get("type") == "simple":
        if _montant_tarif(propre.get("prix_kwh", 0), "Le prix du kWh") <= 0:
            raise ValueError("Le prix du kWh doit etre superieur a zero.")
        for cle in ("prix_hp", "prix_hc", "plages_hc"):
            propre.pop(cle, None)
    elif propre.get("type") == "hp_hc":
        for cle, libelle in (("prix_hp", "heures pleines"),
                             ("prix_hc", "heures creuses")):
            if _montant_tarif(propre.get(cle, 0),
                              f"Le prix en {libelle}") <= 0:
                raise ValueError(
                    f"Le prix en {libelle} doit etre superieur a zero.")
        plages = []
        for paire in propre.get("plages_hc") or []:
            if len(paire) != 2:
                raise ValueError("Chaque plage doit avoir une heure de début "
                                 "et une heure de fin.")
            plages.append([_verifier_heure(paire[0]), _verifier_heure(paire[1])])
        if not plages:
            raise ValueError("Un tarif heures pleines / heures creuses doit "
                             "avoir au moins une plage d'heures creuses.")
        # Deux plages qui se recouvrent ne veulent rien dire : l'heure commune
        # ne peut pas etre creuse deux fois. Le calcul sait desormais s'en
        # sortir (les plages sont fusionnees), mais autant refuser la saisie
        # que laisser une grille fausse dans le fichier.
        recouvrement = _chevauchement_plages(plages)
        if recouvrement:
            raise ValueError(
                f"Vos plages d'heures creuses se chevauchent entre "
                f"{recouvrement[0]} et {recouvrement[1]} : cette heure serait "
                "comptee deux fois. Corrigez les plages.")
        propre["plages_hc"] = plages
        propre.pop("prix_kwh", None)
    else:
        raise ValueError("Type de tarif inconnu (attendu : simple ou hp_hc).")
    return propre


def _avertissements_grille(tarifs: list[dict]) -> list[str]:
    """Signale les chevauchements et les trous entre periodes tarifaires.

    Ce ne sont pas des erreurs bloquantes : c'est peut-etre voulu. Mais un
    chevauchement rend le tarif applique imprevisible, et un trou fait
    refuser les recharges qui tombent dedans.
    """
    messages = []
    tries = sorted(tarifs, key=lambda t: t["debut"])
    for precedent, suivant in zip(tries, tries[1:]):
        fin_prec = precedent.get("fin")
        if not fin_prec:
            messages.append(
                f"« {precedent['nom']} » n'a pas de date de fin : il continue "
                f"de s'appliquer, et « {suivant['nom']} » ne servira jamais. "
                f"Donnez une date de fin à « {precedent['nom']} ».")
            continue
        fin = datetime.fromisoformat(fin_prec).date()
        debut = datetime.fromisoformat(suivant["debut"]).date()
        if debut <= fin:
            messages.append(
                f"« {precedent['nom']} » et « {suivant['nom']} » se "
                "chevauchent : le tarif appliqué serait imprévisible.")
        elif (debut - fin).days > 1:
            messages.append(
                f"Il manque une période entre le {fin:%d/%m/%Y} et le "
                f"{debut:%d/%m/%Y} : les recharges de cet intervalle seront "
                "refusées.")
    return messages


def enregistrer_tarif(tarif: dict, id_origine: str | None = None,
                      cloturer: str | None = None) -> list[str]:
    """Ajoute ou remplace un tarif dans tarifs.json. Retourne les avertissements.

    L'ecriture est atomique et ne touche qu'a la liste des tarifs : les
    autres reglages du fichier (theme, capacite de la batterie...) sont
    conserves tels quels.

    `cloturer` : l'identifiant d'un tarif a terminer la veille du debut du
    nouveau. Les deux changements partent dans la MEME ecriture : avant, la
    cloture etait ecrite seule d'abord, et une panne juste apres laissait
    l'ancien tarif clos sans aucun tarif apres lui (second audit du
    16/10/2026).
    """
    propre = valider_tarif(tarif)
    contenu = _lire_tarifs_json()
    tarifs = contenu.get("tarifs", [])

    if cloturer:
        fin = (datetime.fromisoformat(propre["debut"]).date()
               - timedelta(days=1)).isoformat()
        for t in tarifs:
            if t.get("id") == cloturer:
                t["fin"] = fin
                break
        else:
            raise ValueError("Le tarif à terminer est introuvable : rien "
                             "n'a été enregistré.")

    if id_origine:
        for i, t in enumerate(tarifs):
            if t.get("id") == id_origine:
                propre["id"] = t.get("id")
                # Les notes du tarif (« _commentaire »...) ne sont dans
                # aucune case de la fenetre : on garde celles du tarif
                # remplace. Sans cela, enregistrer un tarif les effacait
                # (bug trouve le 25/09/2026).
                for cle, valeur in t.items():
                    if cle.startswith("_"):
                        propre.setdefault(cle, valeur)
                tarifs[i] = propre
                break
        else:
            raise ValueError("Tarif introuvable (a-t-il été supprimé ?).")
    else:
        if not propre.get("id"):
            propre["id"] = f"tarif_{_nouvel_id()[:8]}"
        if any(t.get("id") == propre["id"] for t in tarifs):
            raise ValueError("Un tarif porte déjà cet identifiant.")
        tarifs.append(propre)

    contenu["tarifs"] = sorted(tarifs, key=lambda t: t["debut"])
    _ecrire_tarifs(contenu)
    return _avertissements_grille(contenu["tarifs"])


def tarif_ouvert_avant(debut_iso: str, sauf_id: str | None = None) -> dict | None:
    """Tarif sans date de fin qui commence avant la date indiquee.

    C'est le piege classique quand les prix changent : on ajoute la nouvelle
    periode sans fermer l'ancienne. Comme le calcul retient le PREMIER tarif
    dont la periode contient la date, l'ancien (qui n'a pas de fin) continue
    de tout absorber et le nouveau ne sert jamais.
    """
    try:
        debut = datetime.fromisoformat(debut_iso).date()
    except Exception:
        return None
    for t in charger_tarifs():
        if t.get("id") == sauf_id or t.get("fin"):
            continue
        if datetime.fromisoformat(t["debut"]).date() < debut:
            return t
    return None


def supprimer_tarif(id_tarif: str) -> bool:
    contenu = _lire_tarifs_json()
    avant = len(contenu.get("tarifs", []))
    contenu["tarifs"] = [t for t in contenu.get("tarifs", [])
                         if t.get("id") != id_tarif]
    if len(contenu["tarifs"]) == avant:
        return False
    _ecrire_tarifs(contenu)
    return True


def recharges_du_tarif(id_tarif: str) -> int:
    """Combien de recharges ont ete calculees avec ce tarif."""
    return sum(1 for r in charger_donnees()["recharges"]
               if r.get("tarif_id") == id_tarif)


def _ecrire_tarifs(contenu: dict) -> None:
    """Ecriture atomique de tarifs.json, avec deux filets de securite.

    1. `tarifs.json.avant` : la copie immediatement precedente, a cote du
       fichier. C'est la sortie de secours la plus simple, celle que propose
       le message d'erreur de _lire_tarifs_json.
    2. `backups/tarifs_*.json` : la meme rotation de 15 sauvegardes (plus une
       par jour conservee un mois) que recharges.json.
    """
    try:
        shutil.copy2(TARIFS_FILE, TARIFS_FILE.with_suffix(".json.avant"))
    except OSError as e:
        print(f"[tarifs] copie de securite impossible : {e}")
    _creer_backup(TARIFS_FILE, "tarifs")
    fd, tmp = tempfile.mkstemp(dir=str(TARIFS_FILE.parent), suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(contenu, f, indent=2, ensure_ascii=False)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, TARIFS_FILE)
    except Exception as e:
        Path(tmp).unlink(missing_ok=True)
        _relancer_au_nom_de(e, TARIFS_FILE)


# ---------- sauvegarde cloud (GitHub) ----------

def depot_git_des_donnees() -> Path | None:
    """La racine du dépôt git qui abrite les données, s'il y en a un.

    La sauvegarde cloud est une commodité, pas une fonction de l'application :
    elle n'existe que si le dossier des données se trouve dans un dépôt git
    déjà configuré. Pour tous les autres, il n'y a rien à sauvegarder ailleurs
    — et donc rien à leur dire.

    Deux dispositions sont reconnues, dans cet ordre :
    - le dossier des données EST le dépôt : c'est un dossier d'usage séparé
      du projet, qui ne versionne que les données ;
    - le dossier des données est DANS un dépôt : dist\\ du projet,
      l'emplacement historique. Ce dépôt-là ne compte que s'il SUIT
      vraiment recharges.json : un dépôt de code qui ignore les données
      (un clone du dépôt public, par exemple) ne doit jamais recevoir les
      recharges de quelqu'un.
    """
    if (BASE / ".git").exists():
        return BASE
    if (BASE.parent / ".git").exists() and _suivi_par_git(DATA_FILE,
                                                          BASE.parent):
        return BASE.parent
    return None


def _suivi_par_git(fichier: Path, repo: Path) -> bool:
    """Vrai si git suit ce fichier dans ce dépôt (faux en cas de doute)."""
    try:
        r = subprocess.run(
            ["git", "ls-files", "--error-unmatch", "--",
             _chemin_pour_git(fichier, repo)],
            cwd=str(repo), capture_output=True, timeout=15,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    except (OSError, ValueError, subprocess.TimeoutExpired):
        return False
    return r.returncode == 0


def sauvegarde_cloud_configuree() -> bool:
    """Vrai si les données vivent dans un dépôt git."""
    return depot_git_des_donnees() is not None


def _chemin_pour_git(fichier: Path, repo: Path) -> str:
    """Le chemin d'un fichier tel que git l'attend : relatif, avec des /."""
    return fichier.relative_to(repo).as_posix()


def synchroniser_github() -> tuple[bool, str]:
    """Envoie les données (recharges.json, tarifs.json) vers GitHub.

    Fait un commit si les fichiers ont changé, puis un push (qui envoie
    aussi les commits restés en attente d'une fois précédente).
    Retourne (succès, message explicatif). Ne lève jamais d'exception :
    en cas de problème, les données restent sauvegardées localement.
    """
    repo = depot_git_des_donnees()
    if repo is None:
        return False, "Pas de dépôt git : sauvegarde cloud non configurée."
    # Les chemins sont calcules, non ecrits en dur : le dossier des donnees ne
    # s'appelle « dist » que chez celui qui construit l'application lui-meme.
    try:
        fichiers = [_chemin_pour_git(DATA_FILE, repo),
                    _chemin_pour_git(TARIFS_FILE, repo)]
    except ValueError:
        return False, ("Le dossier des données n'est pas dans le dépôt git : "
                       "sauvegarde cloud impossible.")
    # Évite l'apparition d'une fenêtre de console noire quand on est en .exe
    sans_fenetre = getattr(subprocess, "CREATE_NO_WINDOW", 0)

    def git(*args, timeout=15):
        return subprocess.run(
            ["git", *args], cwd=str(repo), capture_output=True,
            text=True, encoding="utf-8", errors="replace",
            timeout=timeout, creationflags=sans_fenetre)

    try:
        if not (repo / ".git").exists():
            return False, "Pas de dépôt git : sauvegarde cloud non configurée."

        # 1. Les fichiers de données ont-ils changé depuis le dernier commit ?
        st = git("status", "--porcelain", "--", *fichiers)
        if st.returncode != 0:
            return False, ("Git n'a pas pu lire le dossier des données."
                           + _message_de_git(st))
        a_committer = bool(st.stdout.strip())

        # 2. Si oui : commit avec le nombre de recharges dans le message
        if a_committer:
            ajout = git("add", "--", *fichiers)
            if ajout.returncode != 0:
                return False, ("Git n'a pas pu préparer les fichiers de "
                               "données." + _message_de_git(ajout))
            try:
                n = len(charger_donnees()["recharges"])
                message = f"Sauvegarde auto : {n} recharges"
            except Exception:
                message = "Sauvegarde auto des données"
            # Les chemins après « -- » limitent le commit aux seules données :
            # un fichier étranger déjà préparé dans le dépôt (git add) partait
            # avec elles vers GitHub (audit du 14/10/2026). Il reste préparé,
            # tel que l'utilisateur l'avait laissé.
            c = git("commit", "-m", message, "--", *fichiers)
            if c.returncode != 0:
                return False, ("L'enregistrement des données dans le dépôt "
                               "git (commit) a échoué." + _message_de_git(c))

        # 3. Des commits locaux attendent-ils d'être envoyés (push raté avant) ?
        #    Cette commande échoue s'il n'existe aucune branche distante
        #    configurée. Ce n'est PAS « rien en attente », c'est « on ne sait
        #    pas où envoyer » : confondre les deux faisait annoncer « déjà
        #    sauvegardées sur GitHub » alors que rien n'était jamais parti.
        ahead = git("rev-list", "--count", "@{u}..HEAD")
        if ahead.returncode != 0:
            return False, (
                "Aucune branche distante n'est configurée pour ce dépôt : vos "
                "données ne sont envoyées nulle part. À régler une seule fois, "
                "dans un terminal ouvert sur le dossier du projet :\n\n"
                "    git push -u origin main")
        en_attente = ahead.stdout.strip() not in ("", "0")

        if not a_committer and not en_attente:
            return True, "Données déjà sauvegardées sur GitHub."

        # 4. Push (nécessite une connexion internet)
        p = git("push", timeout=60)
        if p.returncode != 0:
            # Rien ne part plus vers GitHub a la fermeture (24/09/2026) : le
            # message promettait a tort un nouvel essai a ce moment-la.
            return False, ("Vos données sont enregistrées dans le dépôt git "
                           "de ce PC, mais l'envoi vers GitHub a échoué (pas "
                           "de connexion ?). Elles partiront au prochain clic "
                           "sur « Sauvegarder » (Ctrl+S)." + _message_de_git(p))
        return True, "Données sauvegardées sur GitHub."
    except FileNotFoundError:
        return False, "git n'est pas installé (ou introuvable dans le PATH)."
    except subprocess.TimeoutExpired:
        return False, "La sauvegarde GitHub a mis trop de temps (abandon)."
    except Exception as e:
        return False, f"Sauvegarde GitHub impossible. {erreur_en_clair(e)}"


def _message_de_git(resultat: subprocess.CompletedProcess) -> str:
    """Le message d'origine de git, à la suite de l'explication en français.

    Git répond en anglais, et ses messages sont trop variés pour être
    traduits un à un ; ils restent utiles pour un dépannage. On les présente
    donc comme tels, après la phrase qui dit ce qui s'est passé."""
    texte = (resultat.stderr or resultat.stdout or "").strip()[:300]
    return f"\n\nMessage de git (en anglais) :\n{texte}" if texte else ""


# ---------- moteur de calcul tarifaire ----------

def _parse_dt(s: str) -> datetime:
    """Accepte 'YYYY-MM-DDTHH:MM' ou 'YYYY-MM-DD HH:MM[:SS]'."""
    return datetime.fromisoformat(s.replace(" ", "T"))


def _a_la_minute(dt: datetime) -> datetime:
    """Arrondit a la minute la plus proche.

    Les recharges sont enregistrees a la minute (les secondes ne sont pas
    conservees). Si le calcul du cout, lui, tenait compte des secondes du
    CSV, le montant enregistre ne correspondait plus a ce que donnait un
    « Recalculer tous les couts » a partir des heures affichees. On arrondit
    donc des l'import, une bonne fois pour toutes.
    """
    if dt.second >= 30:
        dt += timedelta(minutes=1)
    return dt.replace(second=0, microsecond=0)


def _trouver_tarif(date_debut: datetime, tarifs: list[dict]) -> dict | None:
    d = date_debut.date()
    for t in tarifs:
        t_debut = datetime.fromisoformat(t["debut"]).date()
        t_fin = datetime.fromisoformat(t["fin"]).date() if t.get("fin") else None
        if d >= t_debut and (t_fin is None or d <= t_fin):
            return t
    return None


MINUTES_PAR_JOUR = 24 * 60


def _plages_en_morceaux(plages: list[list[str]]) -> list[tuple[int, int]]:
    """Traduit les plages horaires en morceaux (debut, fin) exprimes en
    minutes depuis minuit, tries.

    Une plage a cheval sur minuit (22:00-06:00) est coupee en deux morceaux
    (1320-1440 et 0-360) : tous les morceaux se traitent alors de la meme
    facon, ce qui supprime le cas particulier « heure de fin avant l'heure
    de debut ». Les morceaux vides (22:00-22:00) sont ecartes.
    """
    morceaux: list[tuple[int, int]] = []
    for heure_debut, heure_fin in plages:
        h1, m1 = map(int, heure_debut.split(":"))
        h2, m2 = map(int, heure_fin.split(":"))
        d, f = h1 * 60 + m1, h2 * 60 + m2
        candidats = [(d, MINUTES_PAR_JOUR), (0, f)] if f < d else [(d, f)]
        morceaux += [(a, b) for a, b in candidats if b > a]
    morceaux.sort()
    return morceaux


def _fusionner_plages(plages: list[list[str]]) -> list[tuple[int, int]]:
    """Fusionne les morceaux qui se recouvrent ou se touchent.

    Sans cette fusion, deux plages qui se recouvrent (22:00-06:00 et
    23:00-02:00) faisaient compter DEUX FOIS les secondes communes : la part
    d'heures creuses depassait 100 % de la session, le min(..., 1.0) de
    calculer_cout l'ecrasait silencieusement a 1, et toute l'energie etait
    facturee en heures creuses.
    """
    fusionnees: list[tuple[int, int]] = []
    for d, f in _plages_en_morceaux(plages):
        if fusionnees and d <= fusionnees[-1][1]:
            fusionnees[-1] = (fusionnees[-1][0], max(fusionnees[-1][1], f))
        else:
            fusionnees.append((d, f))
    return fusionnees


def _minutes_en_heure(minutes: int) -> str:
    """1320 -> « 22:00 ». Sert uniquement aux messages d'erreur."""
    return f"{minutes // 60 % 24:02d}:{minutes % 60:02d}"


def _chevauchement_plages(plages: list[list[str]]) -> tuple[str, str] | None:
    """Renvoie l'intervalle couvert deux fois par deux plages, sinon None.

    Des plages simplement jointives (22:00-00:00 puis 00:00-06:00) ne sont
    pas un chevauchement : elles se touchent sans se recouvrir.
    """
    morceaux = _plages_en_morceaux(plages)
    for (_, fin_prec), (debut, fin) in zip(morceaux, morceaux[1:]):
        if debut < fin_prec:
            return _minutes_en_heure(debut), _minutes_en_heure(min(fin_prec, fin))
    return None


def _secondes_en_hc(debut: datetime, fin: datetime,
                    plages: list[list[str]]) -> float:
    """Secondes de l'intervalle [debut, fin] tombant dans les plages HC (appliquées chaque jour).

    Le décompte se fait en secondes et non en minutes entières : arrondir
    chaque morceau à la minute inférieure faisait perdre jusqu'à une minute
    par morceau, et cette minute était facturée en heures pleines alors que
    la voiture chargeait bien en heures creuses.

    Les plages sont d'abord fusionnees (voir _fusionner_plages) : sinon des
    plages qui se recouvrent comptaient deux fois les memes secondes.
    """
    total = 0.0
    morceaux = _fusionner_plages(plages)
    jour = debut.replace(hour=0, minute=0, second=0, microsecond=0)
    while jour < fin:
        for depuis_minuit, jusqua_minuit in morceaux:
            seg_start = jour + timedelta(minutes=depuis_minuit)
            seg_end = jour + timedelta(minutes=jusqua_minuit)
            ov_start = max(debut, seg_start)
            ov_end = min(fin, seg_end)
            if ov_end > ov_start:
                # Plages lues a l'horloge, duree mesuree en temps reel.
                total += _secondes_reelles(ov_start, ov_end)
        jour += timedelta(days=1)
    return total


def _tarif_ou_erreur(instant: datetime, tarifs: list[dict]) -> dict:
    """Le tarif applicable a cet instant, ou une erreur explicite.

    Deux situations tres differentes derriere le meme refus : une grille
    encore vide (premiere utilisation) et une grille qui ne couvre pas cette
    date. La premiere appelle une consigne — allez saisir vos prix —, pas un
    reproche sur la date saisie.
    """
    tarif = _trouver_tarif(instant, tarifs)
    if tarif is None:
        if not tarifs:
            raise ValueError(
                "Votre grille tarifaire est encore vide : l'application ne "
                "peut pas calculer ce que vous coûte cette recharge.\n\n"
                "Ouvrez la page « Tarifs » et ajoutez une période avec le "
                "prix du kWh de votre contrat d'électricité."
            )
        raise ValueError(
            f"Aucun tarif défini pour le {instant:%d/%m/%Y}. "
            "Vérifiez la date saisie, ou complétez la grille dans la page "
            "« Tarifs »."
        )
    return tarif


def _morceaux_par_tarif(debut: datetime, fin: datetime,
                        tarifs: list[dict]) -> list[tuple[datetime, datetime, dict]]:
    """Découpe la session [debut, fin] à chaque changement de tarif.

    Sans ce découpage, le tarif était choisi d'après la seule date de début :
    une charge du 10/06 au soir jusqu'au 11/06 au matin était facturée en
    entier à l'ancien prix, alors que le nouveau s'appliquait dès minuit.
    Un quart des recharges à la maison passent minuit — le jour où les prix
    changent, il y a donc une chance sur quatre que ce soit le cas.

    Cas courant (la session tient dans une seule période tarifaire) : un
    unique morceau, et le calcul est exactement celui d'avant.
    """
    if fin <= debut:
        # Duree nulle ou negative : un seul morceau, celui du tarif du debut.
        # Peut arriver sur une donnee ancienne saisie de travers.
        return [(debut, fin, _tarif_ou_erreur(debut, tarifs))]

    morceaux = []
    curseur = debut
    while curseur < fin:
        tarif = _tarif_ou_erreur(curseur, tarifs)
        if tarif.get("fin"):
            # Le tarif couvre sa date de fin en entier : sa frontiere est donc
            # minuit au lendemain de cette date.
            lendemain = datetime.fromisoformat(tarif["fin"]) + timedelta(days=1)
            borne = lendemain.replace(hour=0, minute=0, second=0, microsecond=0)
        else:
            borne = fin          # tarif en cours : il va jusqu'au bout
        prochain = min(borne, fin)
        if prochain <= curseur:  # securite : evite une boucle infinie si la
            raise ValueError(    # grille est incoherente (fin avant debut)
                "Grille tarifaire incohérente : impossible de découper la "
                f"recharge du {debut:%d/%m/%Y}. Vérifiez les dates dans la "
                "page Tarifs.")
        morceaux.append((curseur, prochain, tarif))
        curseur = prochain
    return morceaux


def _cout_morceau(debut: datetime, fin: datetime, kwh: float,
                  tarif: dict) -> tuple[float, float, float]:
    """Coût d'un morceau de session couvert par un seul tarif.

    Renvoie (coût, kWh en heures pleines, kWh en heures creuses) SANS
    arrondir : c'est calculer_cout qui arrondit une seule fois, à la fin,
    pour ne pas empiler les arrondis d'un morceau à l'autre.
    """
    if tarif["type"] == "simple":
        return kwh * tarif["prix_kwh"], kwh, 0.0

    if tarif["type"] == "hp_hc":
        duree_s = max(_secondes_reelles(debut, fin), 1.0)
        hc_s = _secondes_en_hc(debut, fin, tarif["plages_hc"])
        # la part d'energie en heures creuses = la part du temps passe en HC
        # (hypothese de puissance constante rappelee plus haut)
        frac_hc = min(hc_s / duree_s, 1.0)
        kwh_hc = kwh * frac_hc
        kwh_hp = kwh - kwh_hc
        cout = kwh_hp * tarif["prix_hp"] + kwh_hc * tarif["prix_hc"]
        return cout, kwh_hp, kwh_hc

    raise ValueError(f"Type de tarif inconnu : {tarif['type']}")


def _fin_de_charge(debut: datetime, fin: datetime, kwh: float,
                   puissance_kw: float) -> datetime:
    """L'heure où la borne a fini de charger.

    Sans puissance connue (0) : la fin de la session, l'énergie est répartie
    uniformément. Avec la puissance de la borne (23/10/2026) : la borne
    charge à pleine puissance dès le début, puis s'arrête quand les kWh sont
    livrés ; la voiture reste ensuite branchée sans charger. Jamais après la
    fin de la session : une puissance trop faible pour livrer les kWh à
    temps revient à la répartition uniforme.
    """
    if puissance_kw <= 0:
        return fin
    return min(fin, debut + timedelta(hours=kwh / puissance_kw))


def calculer_cout(debut: datetime, fin: datetime, kwh: float,
                  tarifs: list[dict] | None = None,
                  puissance_kw: float = 0.0) -> dict:
    """Calcule le coût d'une session (hypothèse : puissance constante).

    La session est découpée aux changements de tarif ; chaque morceau reçoit
    l'énergie au prorata de sa durée, et se voit appliquer les prix et les
    plages d'heures creuses de SON tarif.

    `puissance_kw` : la puissance de charge de la borne, si l'utilisateur
    l'a réglée. L'énergie est alors comptée de `debut` jusqu'à la fin de la
    charge (voir _fin_de_charge), et non jusqu'à `fin`.

    Lève ValueError si aucun tarif ne couvre la date : mieux vaut refuser
    que d'enregistrer silencieusement un coût de 0 € (faute de frappe
    sur l'année, grille tarifaire incomplète...).
    """
    if tarifs is None:
        tarifs = charger_tarifs()
    fin = _fin_de_charge(debut, fin, kwh, puissance_kw)
    morceaux = _morceaux_par_tarif(debut, fin, tarifs)
    duree_totale = _secondes_reelles(debut, fin)

    cout = kwh_hp = kwh_hc = 0.0
    for m_debut, m_fin, tarif in morceaux:
        if len(morceaux) == 1 or duree_totale <= 0:
            part = kwh                      # tout pour l'unique morceau
        else:
            part = kwh * _secondes_reelles(m_debut, m_fin) / duree_totale
        m_cout, m_hp, m_hc = _cout_morceau(m_debut, m_fin, part, tarif)
        cout += m_cout
        kwh_hp += m_hp
        kwh_hc += m_hc

    # Le tarif retenu pour l'historique est celui du morceau le plus long.
    # Les noms sont accoles quand ils diffèrent vraiment : un changement de
    # prix qui garde le meme nom (« Mon contrat HP/HC » -> « Mon contrat HP/HC »)
    # n'a pas a produire un libelle doublonne.
    principal = max(morceaux, key=lambda m: _secondes_reelles(m[0], m[1]))
    noms = list(dict.fromkeys(tarif["nom"] for _, _, tarif in morceaux))
    return {
        "cout": round(cout, 4),
        "kwh_hp": round(kwh_hp, 3),
        "kwh_hc": round(kwh_hc, 3),
        "tarif_id": principal[2]["id"],
        "tarif_nom": " + ".join(noms),
    }


def calculer_cout_sans_duree(debut: datetime, kwh: float,
                             tarifs: list[dict] | None = None) -> dict:
    """Le cout d'une recharge dont on ignore l'heure de fin.

    Ce n'est possible qu'avec un tarif a prix unique : le prix ne depend
    alors que du jour, pas de l'heure, et la duree ne change rien au
    resultat. Avec un tarif heures pleines / heures creuses, elle commande
    tout — il faut alors bien l'heure de fin, et on le dit.
    """
    if tarifs is None:
        tarifs = charger_tarifs()
    tarif = _tarif_ou_erreur(debut, tarifs)
    if tarif.get("type") != "simple":
        raise ValueError(
            "L'heure de fin est nécessaire : votre tarif "
            f"« {tarif['nom']} » distingue les heures pleines des heures "
            "creuses, et c'est la durée de la charge qui répartit l'énergie "
            "entre les deux."
        )
    return {
        "cout": round(kwh * float(tarif["prix_kwh"]), 4),
        "kwh_hp": round(kwh, 3),
        "kwh_hc": 0.0,
        "tarif_id": tarif["id"],
        "tarif_nom": tarif["nom"],
    }


# ---------- ajout de recharges ----------

def _nouvel_id() -> str:
    return uuid.uuid4().hex[:12]


def energie_invraisemblable(kwh: float) -> str:
    """Explique pourquoi une energie saisie est impossible, sinon chaine vide.

    Une batterie ne peut pas absorber plus que sa capacite en une seule
    charge : au-dela, c'est une faute de frappe (85 au lieu de 35...). On se
    contente d'avertir, l'utilisateur reste libre de confirmer — la capacite
    peut ne pas etre renseignee correctement, ou la voiture changer.
    """
    config = charger_config()
    capacite = config["capacite_batterie"]
    rendement = config["rendement_charge"]
    if capacite <= 0 or not 0 < rendement <= 1 or kwh <= 0:
        return ""          # capacite inconnue : on ne peut rien affirmer
    maximum = capacite / rendement
    if kwh <= maximum:
        return ""
    return (f"{fmt_kwh(kwh)} dépasse ce que votre batterie peut absorber en "
            f"une seule charge : {fmt_nombre(capacite, 1)}\xa0kWh, soit "
            f"{fmt_nombre(maximum, 1)}\xa0kWh pris à la prise (rendement de "
            f"charge {100 * rendement:.0f}\xa0%).")


def _prix_unitaire(cout_arrondi: float, kwh: float) -> float:
    """Prix au kWh, calcule sur le cout REELLEMENT enregistre.

    Le cout est arrondi au centime avant d'etre stocke : si le prix unitaire
    etait calcule sur le montant complet, l'historique affichait un prix qui
    ne correspondait pas tout a fait au montant de la ligne (0,2051 au lieu
    de 0,2049 par exemple).
    """
    return round(cout_arrondi / kwh, 4) if kwh else 0


def ajouter_recharge_maison(debut: datetime, fin: datetime | None, kwh: float,
                            cout_wallbox: float | None = None) -> dict:
    """Enregistre une recharge faite a la maison.

    `fin` peut etre None : avec un tarif a prix unique, l'heure de fin ne
    change rien au cout, et l'exiger n'etait qu'une corvee de plus pour qui
    saisit une recharge le lendemain. Elle reste indispensable en heures
    pleines / heures creuses, ou la duree commande la repartition.
    """
    if kwh <= 0:
        raise ValueError("L'énergie (kWh) doit être supérieure à zéro.")
    if fin is not None and fin <= debut:
        raise ValueError("La fin doit être après le début.")
    calc = (calculer_cout(debut, fin, kwh,
                          puissance_kw=charger_config()["puissance_borne_kw"])
            if fin is not None else calculer_cout_sans_duree(debut, kwh))
    recharge = {
        "id": _nouvel_id(),
        "date": debut.isoformat(timespec="minutes"),
        "lieu": "maison",
        "kwh": round(kwh, 3),
        "kwh_hp": calc["kwh_hp"],
        "kwh_hc": calc["kwh_hc"],
        "cout_eur": round(calc["cout"], 2),
        "prix_kwh": _prix_unitaire(round(calc["cout"], 2), kwh),
        "tarif_id": calc["tarif_id"],
        "tarif_nom": calc["tarif_nom"],
    }
    # Pas d'heure de fin inventee : le champ est simplement absent, et tout
    # ce qui a besoin d'une duree (le controle kilometrique, le recalcul)
    # sait deja composer avec.
    if fin is not None:
        recharge["fin"] = fin.isoformat(timespec="minutes")
    if cout_wallbox is not None:
        recharge["cout_wallbox"] = round(cout_wallbox, 2)
    data = charger_donnees(pour_modification=True)
    data["recharges"].append(recharge)
    sauvegarder_donnees(data)
    return recharge


def dernier_choix_exterieur() -> tuple[str, str]:
    """L'operateur et la carte de la derniere recharge exterieure saisie.

    Sert a pre-remplir le formulaire. Auparavant les valeurs par defaut
    etaient ecrites en dur (« Ionity » et « Chargemap ») : c'etaient celles
    d'un utilisateur en particulier, et n'importe qui d'autre devait les
    corriger a chaque saisie. Deux chaines vides si rien n'a encore ete
    saisi : mieux vaut un champ a remplir qu'une reponse toute faite et
    fausse.
    """
    for r in reversed(charger_donnees()["recharges"]):
        if r.get("lieu") == "exterieur":
            return r.get("operateur", ""), r.get("carte", "")
    return "", ""


def _cle_lieu(texte: str) -> str:
    """La forme sur laquelle deux ecritures d'un meme lieu se rejoignent.

    Sans casse, sans accents, espaces ramenes a un seul : « AIRE DU LAC »,
    « Aire du Lac » et « aire du lac  » donnent la meme cle.
    """
    sans_accents = "".join(
        c for c in unicodedata.normalize("NFD", texte)
        if unicodedata.category(c) != "Mn")
    return " ".join(sans_accents.lower().split())


def lieux_deja_saisis() -> list[str]:
    """Les lieux deja employes, les plus frequents en tete.

    Remplit la liste deroulante du formulaire. On recharge presque toujours
    aux memes endroits : les proposer evite d'en reecrire un a chaque fois,
    et surtout de l'ecrire chaque fois un peu autrement — « Tilleuls (A7) »,
    « Tilleuls - Aire des Tilleuls (A7) »... qui comptent ensuite pour deux
    lieux distincts.

    Une seule orthographe par lieu est proposee : la plus employee, et a
    egalite la plus recente.
    """
    recharges = charger_donnees()["recharges"]
    # {cle: {orthographe: [nombre, rang de la derniere vue]}}
    familles: dict[str, dict[str, list]] = {}
    for rang, r in enumerate(recharges):
        if r.get("lieu") != "exterieur":
            continue
        texte = (r.get("lieu_detail") or "").strip()
        if not texte:
            continue
        compte = familles.setdefault(_cle_lieu(texte), {})
        vu = compte.setdefault(texte, [0, rang])
        vu[0] += 1
        vu[1] = rang

    retenus = []
    for orthographes in familles.values():
        # la plus employee ; a egalite, la plus recente
        meilleure = max(orthographes.items(), key=lambda kv: (kv[1][0], kv[1][1]))
        total = sum(v[0] for v in orthographes.values())
        dernier = max(v[1] for v in orthographes.values())
        retenus.append((total, dernier, meilleure[0]))
    retenus.sort(key=lambda x: (-x[0], -x[1]))
    return [nom for _, _, nom in retenus]


def lieu_canonique(texte: str) -> str:
    """Rend l'orthographe deja en service quand le lieu est deja connu.

    Taper « aire du lac » alors que « AIRE DU LAC » existe deja ne doit pas
    creer un second lieu dans les statistiques. Un lieu inconnu est rendu
    tel quel, simplement debarrasse de ses espaces en trop.
    """
    propre = " ".join(texte.split())
    if not propre:
        return ""
    cle = _cle_lieu(propre)
    for connu in lieux_deja_saisis():
        if _cle_lieu(connu) == cle:
            return connu
    return propre


def ajouter_recharge_exterieur(kwh: float, cout: float, operateur: str = "",
                               lieu_detail: str = "", date: str | None = None,
                               carte: str = "") -> dict:
    if kwh <= 0:
        raise ValueError("L'énergie (kWh) doit être supérieure à zéro.")
    if cout < 0:
        raise ValueError("Le coût ne peut pas être négatif.")
    recharge = {
        "id": _nouvel_id(),
        "date": date or datetime.now().isoformat(timespec="minutes"),
        "lieu": "exterieur",
        "operateur": operateur,
        "carte": carte,
        # Orthographe deja en service si le lieu est connu : sans quoi
        # « aire du lac » et « AIRE DU LAC » comptent pour deux.
        "lieu_detail": lieu_canonique(lieu_detail),
        "kwh": round(kwh, 3),
        "cout_eur": round(cout, 2),
        "prix_kwh": _prix_unitaire(round(cout, 2), kwh),
    }
    data = charger_donnees(pour_modification=True)
    data["recharges"].append(recharge)
    sauvegarder_donnees(data)
    return recharge


TARIFS_DEMO = [
    {"id": "demo_simple", "nom": "Demo Bleu", "type": "simple",
     "debut": "2025-01-01", "fin": "2025-12-31",
     "prix_kwh": 0.2516, "abonnement_mensuel": 13.47},
    {"id": "demo_hphc", "nom": "Demo HP/HC", "type": "hp_hc",
     "debut": "2026-01-01", "fin": None,
     "prix_hp": 0.27, "prix_hc": 0.13,
     "plages_hc": [["22:00", "06:00"]], "abonnement_mensuel": 15.90},
]

# (debut, fin, kWh) — deux d'entre elles passent minuit, une est anterieure
# au passage en heures creuses et releve donc du tarif simple.
RECHARGES_DEMO_MAISON = [
    ("2025-03-10T09:00", "2025-03-10T12:30", 25.0),
    ("2025-06-15T14:00", "2025-06-15T18:00", 30.0),
    ("2026-02-03T23:00", "2026-02-04T05:00", 35.0),
    ("2026-03-12T22:30", "2026-03-13T04:30", 32.0),
    ("2026-04-02T10:00", "2026-04-02T13:00", 18.0),
    ("2026-05-20T23:45", "2026-05-21T06:15", 40.0),
    ("2026-07-08T22:00", "2026-07-09T02:00", 22.0),
]

# (date, operateur, lieu, kWh, cout)
RECHARGES_DEMO_EXTERIEUR = [
    ("2026-04-15T12:30", "Ionity", "Aire de demonstration", 37.5, 22.50),
    ("2026-04-15T18:45", "Tesla", "Halte de demonstration", 28.0, 12.60),
    ("2026-06-01T09:15", "Fastned", "Station de demonstration", 30.0, 17.40),
]


def ecrire_jeu_demo(dossier: str | Path) -> Path:
    """Écrit un jeu de données de démonstration figé, et renvoie le dossier.

    Sert à la vérification automatique. Sur une machine neuve, ou juste
    après une restauration, celle-ci tournerait sinon sur zéro recharge :
    la plupart des pages afficheraient « aucune donnée » sans jamais
    exercer le code d'affichage, et ne prouveraient donc plus grand-chose.

    Ces dix recharges couvrent les deux lieux, les deux types de tarif, et
    deux charges qui passent minuit. Les montants ne sont pas écrits en
    dur : ils sont calculés par calculer_cout, ce qui garantit qu'ils
    restent cohérents avec le moteur, quoi qu'il arrive à celui-ci.
    """
    dossier = Path(dossier)
    dossier.mkdir(parents=True, exist_ok=True)

    recharges = []
    for i, (debut, fin, kwh) in enumerate(RECHARGES_DEMO_MAISON):
        d, f = _parse_dt(debut), _parse_dt(fin)
        calc = calculer_cout(d, f, kwh, TARIFS_DEMO)
        recharges.append({
            "id": f"demo_m{i:02d}", "date": debut, "fin": fin,
            "lieu": "maison", "kwh": kwh,
            "kwh_hp": calc["kwh_hp"], "kwh_hc": calc["kwh_hc"],
            "cout_eur": round(calc["cout"], 2),
            "prix_kwh": _prix_unitaire(round(calc["cout"], 2), kwh),
            "tarif_id": calc["tarif_id"], "tarif_nom": calc["tarif_nom"],
            "duree": f"{int((f - d).total_seconds() // 3600):02d}h"
                     f"{int((f - d).total_seconds() % 3600 // 60):02d}min",
            "source": "demo",
        })
    for i, (date_iso, operateur, lieu, kwh, cout) in enumerate(
            RECHARGES_DEMO_EXTERIEUR):
        recharges.append({
            "id": f"demo_e{i:02d}", "date": date_iso, "lieu": "exterieur",
            "operateur": operateur, "carte": "Chargemap", "lieu_detail": lieu,
            "kwh": kwh, "cout_eur": cout,
            "prix_kwh": _prix_unitaire(cout, kwh),
        })

    contenu = {
        "recharges": sorted(recharges, key=lambda r: r["date"]),
        "releves_km": [
            {"id": "demo_k0", "date": "2026-01-05T10:00", "km": 42000,
             "conso": 16.5},
            {"id": "demo_k1", "date": "2026-04-10T10:00", "km": 45200,
             "conso": 16.8},
            {"id": "demo_k2", "date": "2026-07-20T10:00", "km": 48600,
             "conso": 16.2},
        ],
    }
    (dossier / "recharges.json").write_text(
        json.dumps(contenu, indent=2, ensure_ascii=False), encoding="utf-8")
    (dossier / "tarifs.json").write_text(
        json.dumps({"tarifs": TARIFS_DEMO, "correction_csv_minutes": 0,
                    "rendement_charge": 0.90,
                    "capacite_batterie": 52.0},
                   indent=2, ensure_ascii=False), encoding="utf-8")
    return dossier


def horodatage_deja_utilise(date_iso: str | None,
                            sauf_id: str | None = None) -> dict | None:
    """La recharge déjà enregistrée à cette date ET cette heure, sinon None.

    Ce n'est pas un doublon : deux recharges le même jour sur deux bornes
    différentes sont parfaitement normales sur un trajet. Mais quand l'heure
    reste à sa valeur par défaut au lieu d'être précisée, leur ordre dans la
    journée devient arbitraire — or c'est cet ordre qui décide à quel
    intervalle kilométrique chacune est rattachée.
    """
    if not date_iso:
        return None
    for r in charger_donnees()["recharges"]:
        if r.get("id") != sauf_id and r.get("date") == date_iso:
            return r
    return None


def modifier_recharge(id_recharge: str, modifs: dict) -> dict:
    """Modifie une recharge existante par son id. Recalcule les coûts si maison."""
    data = charger_donnees(pour_modification=True)
    if "lieu_detail" in modifs:
        modifs = dict(modifs)
        modifs["lieu_detail"] = lieu_canonique(modifs["lieu_detail"])
    for r in data["recharges"]:
        if r.get("id") != id_recharge:
            continue
        r.update(modifs)
        # « fin » a None : l'heure de fin a ete videe dans « Modifier ». Le
        # champ disparait, comme pour une recharge saisie sans fin.
        if "fin" in modifs and modifs["fin"] is None:
            r.pop("fin")
        # validations : on refuse avant de sauvegarder (le fichier n'est
        # pas touché si une valeur est incohérente)
        if r.get("kwh", 0) <= 0:
            raise ValueError("L'énergie (kWh) doit être supérieure à zéro.")
        if r.get("cout_eur", 0) < 0:
            raise ValueError("Le coût ne peut pas être négatif.")
        # recalculer si maison — avec ou sans heure de fin. Sans fin, le
        # cout n'etait pas recalcule jusqu'a la v2.0.0 : passer de 30 a
        # 10 kWh laissait le montant des 30 kWh.
        if r.get("lieu") == "maison":
            debut = _parse_dt(r["date"])
            if r.get("fin"):
                fin = _parse_dt(r["fin"])
                if fin <= debut:
                    raise ValueError("La fin doit être après le début.")
                calc = calculer_cout(
                    debut, fin, r["kwh"],
                    puissance_kw=charger_config()["puissance_borne_kw"])
            else:
                # Tarif heures pleines / creuses : refuse, avec un message
                # qui demande l'heure de fin (rien n'est enregistre).
                calc = calculer_cout_sans_duree(debut, r["kwh"])
            r["kwh_hp"] = calc["kwh_hp"]
            r["kwh_hc"] = calc["kwh_hc"]
            r["cout_eur"] = round(calc["cout"], 2)
            r["prix_kwh"] = _prix_unitaire(r["cout_eur"], r["kwh"])
            r["tarif_id"] = calc["tarif_id"]
            r["tarif_nom"] = calc["tarif_nom"]
        elif r.get("lieu") == "exterieur" and r.get("kwh"):
            r["prix_kwh"] = _prix_unitaire(round(r.get("cout_eur", 0), 2),
                                           r["kwh"])
        sauvegarder_donnees(data)
        return r
    raise ValueError("Recharge introuvable")


def supprimer_recharge(id_recharge: str) -> bool:
    data = charger_donnees(pour_modification=True)
    avant = len(data["recharges"])
    data["recharges"] = [r for r in data["recharges"] if r.get("id") != id_recharge]
    if len(data["recharges"]) < avant:
        sauvegarder_donnees(data)
        return True
    return False


def _tarif_du_jour(jour: date, tarifs: list[dict]) -> tuple[dict | None, date]:
    """Le tarif applicable ce jour-là, et son dernier jour d'application.

    Un tarif sans date de fin est celui en cours : il court jusqu'à nouvel
    ordre (date.max). L'arrêter à aujourd'hui ferait disparaître les jours
    restants du mois quand on demande le mois entier.
    """
    for t in tarifs:
        t_debut = datetime.fromisoformat(t["debut"]).date()
        t_fin = (datetime.fromisoformat(t["fin"]).date()
                 if t.get("fin") else date.max)
        if t_debut <= jour <= t_fin:
            return t, t_fin
    return None, date.max


def calculer_abonnement(date_debut: date, date_fin: date,
                        tarifs: list[dict] | None = None) -> dict:
    """Calcule le coût d'abonnement entre deux dates (proratisé par jour).

    L'abonnement mensuel est divisé par le nombre de jours du mois en cours,
    puis sommé sur la période. Permet de gérer correctement les changements
    de tarif au milieu d'un mois.

    Le parcours se fait par TRANCHES et non jour par jour : une tranche
    couvre les jours consécutifs qui partagent le même mois et le même
    tarif. Sur « Tout » (quatre ans), cela fait une soixantaine de tours de
    boucle au lieu de 1 585, chacun reparcourant la grille tarifaire.
    """
    if tarifs is None:
        tarifs = charger_tarifs()
    total = 0.0
    par_tarif: dict[str, float] = {}
    jour = date_debut
    while jour <= date_fin:
        tarif, tarif_fin = _tarif_du_jour(jour, tarifs)
        if tarif is None:
            jour += timedelta(days=1)   # jour non couvert : il ne coute rien
            continue
        n_jours_mois = calendar.monthrange(jour.year, jour.month)[1]
        fin_du_mois = date(jour.year, jour.month, n_jours_mois)
        # La tranche s'arrete au premier des trois : fin du mois (le diviseur
        # change), fin du tarif, ou fin de la periode demandee.
        borne = min(fin_du_mois, tarif_fin, date_fin)
        n_jours = (borne - jour).days + 1
        cout_jour = float(tarif.get("abonnement_mensuel", 0)) / n_jours_mois
        # L'addition reste faite jour par jour, volontairement. Remplacer les
        # n additions par une multiplication donne un resultat different au
        # quinzieme chiffre apres la virgule — assez pour faire basculer un
        # arrondi et afficher 6,74 EUR au lieu de 6,73. Ce qui coutait cher,
        # ce n'etait pas l'addition, c'etait de reparcourir la grille
        # tarifaire et de refaire le calendrier a chaque jour.
        nom = tarif["nom"]
        for _ in range(n_jours):
            total += cout_jour
            par_tarif[nom] = par_tarif.get(nom, 0.0) + cout_jour
        jour = borne + timedelta(days=1)
    return {
        "total": round(total, 2),
        "par_tarif": {k: round(v, 2) for k, v in par_tarif.items()},
        "jours": (date_fin - date_debut).days + 1,
    }


# ---------- frais des cartes de recharge (28/09/2026) ----------
# L'achat d'une carte (une fois) ou un abonnement, mensuel ou annuel, a un
# reseau de bornes. Comptes a part, comme l'abonnement de la maison : jamais dans le
# cout des recharges ni dans le prix du kWh. Ranges dans tarifs.json, sous la
# cle « frais_cartes » ; un fichier plus ancien, sans cette cle, n'a aucun
# frais. Toutes les ecritures de tarifs.json relisent le fichier en entier :
# la cle survit donc a l'enregistrement d'un tarif ou d'un reglage.

TYPES_FRAIS_CARTE = {"unique": "Achat unique",
                     "mensuel": "Abonnement mensuel",
                     "annuel": "Abonnement annuel"}


def charger_frais_cartes() -> list[dict]:
    """Les frais de cartes, du plus ancien au plus recent."""
    return list(_lire_tarifs_json().get("frais_cartes", []))


def valider_frais_carte(frais: dict) -> dict:
    """Controle des frais avant de les enregistrer, et les rend propres.

    Leve ValueError, en francais, si quelque chose ne va pas. La fenetre
    controle deja la saisie (saisie.lire_frais_carte) : ceci est le filet du
    moteur, pour qui l'appellerait autrement."""
    carte = str(frais.get("carte", "")).strip()
    if not carte:
        raise ValueError("Indiquez le nom de la carte.")
    type_ = frais.get("type")
    if type_ not in TYPES_FRAIS_CARTE:
        raise ValueError("Type de frais inconnu : achat unique, "
                         "abonnement mensuel ou abonnement annuel.")
    try:
        debut = date.fromisoformat(str(frais.get("date")))
        fin = (date.fromisoformat(str(frais["fin"]))
               if type_ != "unique" and frais.get("fin") else None)
        montant = float(frais.get("montant", 0))
    except (TypeError, ValueError):
        raise ValueError("Date ou montant illisible.") from None
    if not montant > 0:
        raise ValueError("Le montant doit être supérieur à zéro.")
    if fin is not None and fin < debut:
        raise ValueError("La fin de l'abonnement vient avant son début.")
    propre = {"carte": carte, "type": type_, "date": debut.isoformat(),
              "fin": fin.isoformat() if fin else None,
              "montant": round(montant, 2)}
    if frais.get("id"):
        propre["id"] = frais["id"]
    return propre


def ajouter_frais_carte(frais: dict) -> dict:
    """Ajoute des frais de carte dans tarifs.json et les rend, avec leur
    identifiant."""
    propre = valider_frais_carte(frais)
    propre.setdefault("id", f"carte_{_nouvel_id()[:8]}")
    contenu = _lire_tarifs_json()
    liste = contenu.get("frais_cartes", []) + [propre]
    contenu["frais_cartes"] = sorted(liste, key=lambda f: f["date"])
    _ecrire_tarifs(contenu)
    return propre


def modifier_frais_carte(id_frais: str, frais: dict) -> dict:
    """Remplace des frais de carte existants, sans changer leur identifiant
    (analyse du 16/10/2026 : on devait supprimer puis recréer). Mêmes
    contrôles qu'à l'ajout."""
    propre = valider_frais_carte(frais)
    contenu = _lire_tarifs_json()
    liste = contenu.get("frais_cartes", [])
    rang = next((i for i, f in enumerate(liste) if f.get("id") == id_frais),
                None)
    if rang is None:
        raise ValueError("Ces frais sont introuvables : rien n'a été modifié.")
    propre["id"] = id_frais
    liste[rang] = propre
    contenu["frais_cartes"] = sorted(liste, key=lambda f: f["date"])
    _ecrire_tarifs(contenu)
    return propre


def supprimer_frais_carte(id_frais: str) -> bool:
    contenu = _lire_tarifs_json()
    avant = contenu.get("frais_cartes", [])
    reste = [f for f in avant if f.get("id") != id_frais]
    if len(reste) == len(avant):
        return False
    contenu["frais_cartes"] = reste
    _ecrire_tarifs(contenu)
    return True


def calculer_frais_cartes(date_debut: date, date_fin: date,
                          frais: list[dict] | None = None) -> dict:
    """Les frais de cartes tombes entre deux dates (incluses).

    Un achat compte le jour ou il est fait. Un abonnement mensuel compte
    chaque mois au prorata des jours, comme l'abonnement de la maison
    (calculer_abonnement) : la moitie de juin = la moitie du prix mensuel.
    Un abonnement annuel compte le prix de l'annee en entier le jour du
    debut, puis a chaque date anniversaire : ce qui sort du compte. Sans
    date de fin, un abonnement court jusqu'a la fin demandee."""
    if frais is None:
        frais = charger_frais_cartes()
    total = 0.0
    par_carte: dict[str, float] = {}
    for f in frais:
        debut_f = date.fromisoformat(f["date"])
        if f["type"] == "unique":
            montant = f["montant"] if date_debut <= debut_f <= date_fin else 0
        elif f["type"] == "annuel":
            montant = 0.0
            fin_f = date.fromisoformat(f["fin"]) if f.get("fin") else None
            for echeance in _anniversaires(debut_f, date_fin):
                if fin_f is not None and echeance > fin_f:
                    break
                if echeance >= date_debut:
                    montant += f["montant"]
        else:
            montant = 0.0
            jour = max(date_debut, debut_f)
            dernier = min(date_fin, date.fromisoformat(f["fin"])
                          if f.get("fin") else date_fin)
            while jour <= dernier:
                n_mois = calendar.monthrange(jour.year, jour.month)[1]
                borne = min(date(jour.year, jour.month, n_mois), dernier)
                montant += f["montant"] * ((borne - jour).days + 1) / n_mois
                jour = borne + timedelta(days=1)
        if montant:
            total += montant
            par_carte[f["carte"]] = par_carte.get(f["carte"], 0.0) + montant
    return {"total": round(total, 2),
            "par_carte": {k: round(v, 2) for k, v in par_carte.items()}}


def _anniversaires(debut: date, jusqu_a: date):
    """Le jour du debut, puis chaque date anniversaire jusqu'a `jusqu_a`
    inclus. Un 29 fevrier tombe le 28 les annees non bissextiles."""
    annee = debut.year
    while True:
        dernier_jour = calendar.monthrange(annee, debut.month)[1]
        echeance = date(annee, debut.month, min(debut.day, dernier_jour))
        if echeance > jusqu_a:
            return
        yield echeance
        annee += 1


def assurer_ids() -> int:
    """Migration : ajoute un id aux recharges qui n'en ont pas."""
    data = charger_donnees(pour_modification=True)
    n = 0
    for r in data["recharges"]:
        if "id" not in r:
            r["id"] = _nouvel_id()
            n += 1
    if n:
        sauvegarder_donnees(data)
    return n


# ---------- releves du compteur kilometrique ----------

def _date_fr(iso: str) -> str:
    try:
        return datetime.fromisoformat(iso).strftime("%d/%m/%Y")
    except ValueError:
        return iso


def charger_releves_km() -> list[dict]:
    """Relevés du compteur, du plus ancien au plus récent."""
    data = charger_donnees()
    return sorted(data.get("releves_km", []), key=lambda r: r.get("date", ""))


def rappel_prix_essence(seuil_jours: int = 90,
                        config: dict | None = None,
                        aujourd_hui: datetime | None = None) -> str | None:
    """Une phrase a afficher quand le prix du litre de la comparaison
    essence n'a pas ete mis a jour depuis `seuil_jours`, ou None.

    Un prix saisi a la main vieillit sans prevenir : c'est la raison meme
    pour laquelle aucun prix n'est ecrit dans le code. Rien sans
    comparaison, et rien quand la date de mise a jour est inconnue (fichier
    d'avant ce rappel) : mieux vaut se taire que relancer a tort.
    `config` et `aujourd_hui` ne sont renseignes que par les tests."""
    if config is None:
        config = charger_config()
    if not (config.get("conso_essence") and config.get("prix_essence")):
        return None
    try:
        maj = date.fromisoformat(str(config.get("prix_essence_maj")))
    except ValueError:
        return None
    maintenant = (aujourd_hui or datetime.now()).date()
    jours = (maintenant - maj).days
    if jours < seuil_jours:
        return None
    annee = str(maintenant.year)
    prix = ((config.get("prix_essence_annees") or {}).get(annee)
            or config["prix_essence"])
    return (f"Prix de l'essence mis à jour il y a {jours} jours "
            + f"({prix:.2f}\xa0€/L".replace(".", ",") + f" en {annee}) : "
            "revoyez-le dans « ⚙️ Paramètres », la comparaison avec une "
            "voiture essence en dépend.")


def rappel_releve_km(seuil_jours: int = 30,
                     aujourd_hui: datetime | None = None) -> str | None:
    """Une phrase a afficher quand le compteur n'a pas ete releve depuis
    longtemps, ou None s'il n'y a rien a dire.

    Le tableau de bord l'affiche discretement. Le but n'est pas de harceler :
    l'oubli coute cher, parce que les recharges faites APRES le dernier releve
    ne sont rattachees a aucune distance et ne comptent donc ni dans la
    consommation ni dans le cout aux 100 km.

    Deux precautions pour que le rappel reste doux :

    * rien tant qu'aucun releve n'existe. Quelqu'un qui ne se sert pas du
      kilometrage n'a pas a etre relance a chaque ouverture ; la page
      Kilometrage, elle, l'invite a commencer.
    * rien non plus s'il n'y a eu aucune recharge depuis : sans recharge a
      rattacher, l'oubli ne fausse rien.

    `aujourd_hui` n'est renseigne que par les tests.
    """
    releves = charger_releves_km()
    if not releves:
        return None
    maintenant = aujourd_hui or datetime.now()
    try:
        dernier = _parse_dt(releves[-1]["date"])
    except (KeyError, ValueError):
        return None
    jours = (maintenant - dernier).days
    if jours < seuil_jours:
        return None

    depuis = sum(1 for r in charger_donnees()["recharges"]
                 if r.get("date", "") > releves[-1]["date"])
    if not depuis:
        return None

    phrase = f"Dernier relevé kilométrique il y a {jours} jours."
    if len(releves) == 1:
        return (phrase + " Un deuxième relevé, et votre consommation réelle "
                "apparaîtra.")
    # Accord ecrit en clair : la phrase se relit mieux qu'avec des
    # conditions imbriquees dans le texte.
    if depuis > 1:
        suite = f"Depuis, {depuis} recharges ne sont rattachées"
    else:
        suite = "Depuis, 1 recharge n'est rattachée"
    return f"{phrase} {suite} à aucune distance."


def ajouter_releve_km(km: float, date: str | None = None,
                      conso: float | None = None) -> dict:
    """Enregistre un relevé du compteur kilométrique.

    `conso` est la consommation moyenne affichée par la voiture au même
    moment (kWh/100 km), facultative : elle sert de référence pour repérer
    les recharges qui n'ont pas été saisies.

    Le kilométrage doit rester croissant dans le temps : un compteur ne
    recule pas, donc une valeur qui diminue est forcément une faute de
    frappe et on la refuse plutôt que de fausser les calculs.
    """
    quand = date or datetime.now().isoformat(timespec="minutes")
    data = charger_donnees(pour_modification=True)
    releves = data.setdefault("releves_km", [])
    _controler_releve(releves, km, quand, conso)
    releve = {"id": _nouvel_id(), "date": quand, "km": round(float(km), 1)}
    if conso:
        releve["conso"] = round(float(conso), 1)
    releves.append(releve)
    sauvegarder_donnees(data)
    return releve


def modifier_releve_km(id_releve: str, km: float, date: str,
                       conso: float | None = None) -> dict:
    """Corrige un relevé existant, sans changer son identifiant.

    Mêmes contrôles qu'à l'ajout, le relevé corrigé étant comparé aux
    AUTRES (analyse du 16/10/2026 : jusque-là, corriger une faute imposait
    de supprimer puis de recréer le relevé). Une consommation vide retire
    celle qui était notée."""
    data = charger_donnees(pour_modification=True)
    releves = data.setdefault("releves_km", [])
    releve = next((r for r in releves if r.get("id") == id_releve), None)
    if releve is None:
        raise ValueError("Ce relevé est introuvable : rien n'a été modifié.")
    autres = [r for r in releves if r is not releve]
    _controler_releve(autres, km, date, conso)
    releve["date"] = date
    releve["km"] = round(float(km), 1)
    if conso:
        releve["conso"] = round(float(conso), 1)
    else:
        releve.pop("conso", None)
    sauvegarder_donnees(data)
    return releve


def _controler_releve(releves: list[dict], km: float, quand: str,
                      conso: float | None) -> None:
    """Lève ValueError, en français, si le relevé (km, quand, conso) ne
    peut pas prendre place parmi `releves`."""
    # 0 est permis (28/09/2026) : c'est le compteur d'une voiture neuve le
    # jour de la livraison, un point de depart utile.
    if km < 0:
        raise ValueError("Le kilométrage ne peut pas être négatif.")
    if conso is not None and conso and not 5 <= conso <= 50:
        raise ValueError(
            "La consommation d'une voiture électrique se situe entre 5 et "
            "50\xa0kWh/100\xa0km. Vérifiez la valeur saisie.")
    for r in releves:
        # relevé déjà saisi (double clic, ressaisie) : inutile de l'empiler,
        # il créerait un intervalle de 0 km sans intérêt
        if r["date"] == quand and abs(r["km"] - km) < 0.05:
            raise ValueError(
                f"Ce relevé existe déjà : {fmt_nombre(r['km'])}\xa0km au "
                f"{_date_fr(r['date'])}.")
        if r["date"] <= quand and r["km"] > km:
            raise ValueError(
                f"Le relevé du {_date_fr(r['date'])} indique déjà "
                f"{fmt_nombre(r['km'])}\xa0km : le kilométrage ne peut pas diminuer.")
        if r["date"] >= quand and r["km"] < km:
            raise ValueError(
                f"Le relevé du {_date_fr(r['date'])} indique {fmt_nombre(r['km'])}\xa0km : "
                "un relevé plus ancien ne peut pas être plus élevé.")


def conso_reference(releves: list[dict] | None = None) -> float:
    """Dernière consommation relevée sur le tableau de bord de la voiture.

    C'est une moyenne depuis l'origine du véhicule : elle évolue très
    lentement, donc la valeur la plus récente est la meilleure référence
    disponible. Retourne 0 si aucun relevé n'en comporte.
    """
    if releves is None:
        releves = charger_releves_km()
    for r in reversed(releves):
        if r.get("conso"):
            return float(r["conso"])
    return 0.0


def supprimer_releve_km(id_releve: str) -> bool:
    data = charger_donnees(pour_modification=True)
    releves = data.get("releves_km", [])
    avant = len(releves)
    data["releves_km"] = [r for r in releves if r.get("id") != id_releve]
    if len(data["releves_km"]) < avant:
        sauvegarder_donnees(data)
        return True
    return False


def calculer_consommation() -> dict:
    """Consommation réelle déduite des relevés du compteur.

    Pour chaque couple de relevés consécutifs : les kilomètres parcourus et
    l'énergie rechargée dans l'intervalle (les recharges datées après le
    premier relevé et jusqu'au second inclus). Le tout premier relevé ne
    sert que de point de départ, d'où le calcul à partir du deuxième.
    """
    releves = charger_releves_km()
    recharges = charger_donnees()["recharges"]
    vide = {"intervalles": [], "km": 0.0, "kwh": 0.0, "cout": 0.0,
            "kwh_100": 0.0, "cout_100": 0.0, "n_releves": len(releves)}
    if len(releves) < 2:
        return vide

    intervalles = []
    # Les totaux s'additionnent sur les valeurs exactes, arrondies une seule
    # fois à la fin : additionner les intervalles déjà arrondis donnait
    # 1 005,00 kWh au lieu de 1 005,40 pour 100 intervalles de 10,054
    # (audit du 14/10/2026).
    kwh_tot = cout_tot = 0.0
    for precedent, suivant in zip(releves, releves[1:]):
        km = suivant["km"] - precedent["km"]
        dedans = [r for r in recharges
                  if precedent["date"] < r.get("date", "") <= suivant["date"]]
        kwh = sum(r.get("kwh", 0) for r in dedans)
        cout = sum(r.get("cout_eur", 0) for r in dedans)
        kwh_tot += kwh
        cout_tot += cout
        intervalles.append({
            "debut": precedent["date"], "fin": suivant["date"],
            "km": round(km, 1), "kwh": round(kwh, 2), "cout": round(cout, 2),
            "n_recharges": len(dedans),
            "kwh_100": round(100 * kwh / km, 2) if km else 0.0,
            "cout_100": round(100 * cout / km, 2) if km else 0.0,
        })

    km_tot = releves[-1]["km"] - releves[0]["km"]
    marge = marge_batterie(charger_config(), recharges)
    return {
        "intervalles": intervalles,
        "km": round(km_tot, 1),
        "kwh": round(kwh_tot, 2),
        "cout": round(cout_tot, 2),
        "kwh_100": round(100 * kwh_tot / km_tot, 2) if km_tot else 0.0,
        "cout_100": round(100 * cout_tot / km_tot, 2) if km_tot else 0.0,
        "n_releves": len(releves),
        "controle": controler_energie(km_tot, kwh_tot,
                                      conso_reference(releves), marge),
    }


def marge_batterie(config: dict, recharges: list[dict]) -> float:
    """Marge d'incertitude du controle d'energie : une charge complete.

    Entre deux releves, la voiture peut partir batterie pleine et arriver
    batterie vide (ou l'inverse). On la compte en energie PRISE A LA PRISE
    (donc capacite / rendement), puisque c'est ce que l'application
    enregistre. Si la capacite n'est pas renseignee, la plus grosse recharge
    vue en donne une idee. Partagee par le Kilometrage et la comparaison
    essence : ils doivent tirer la meme conclusion (audit du 14/10/2026)."""
    capacite = config.get("capacite_batterie", 0) or 0
    rendement = config.get("rendement_charge", 0.90) or 0.90
    if capacite > 0 and 0 < rendement <= 1:
        return capacite / rendement
    return max((r.get("kwh", 0) for r in recharges), default=0.0)


# Au-dela de cet ecart relatif, on considere qu'il y a vraiment quelque chose
# a signaler. En dessous, l'imprecision de la methode suffit a l'expliquer.
SEUIL_ECART = 0.10


def controler_energie(km: float, kwh_enregistres: float,
                      conso_ref: float, marge_kwh: float = 0.0,
                      config: dict | None = None) -> dict:
    """Compare l'énergie enregistrée à celle que la voiture a réellement dû
    consommer, pour repérer les recharges qui n'ont pas été saisies.

    `conso_ref` est la consommation affichée par la voiture (énergie arrivée
    à la batterie) : elle tient compte de toutes les charges, y compris
    celles que l'application ignore. On la ramène à l'énergie prise à la
    prise en divisant par le rendement de charge, puis on compare.

    `marge_kwh` est l'incertitude incompressible de la méthode : entre deux
    relevés, la voiture peut partir batterie pleine et arriver batterie vide
    (ou l'inverse). L'écart que cela produit ne dépasse jamais une charge
    complète. En dessous de cette marge, on ne peut donc rien conclure —
    c'est le cas quand les relevés sont trop rapprochés.

    `config` : les réglages à utiliser ; à défaut, ceux de tarifs.json.
    """
    if config is None:
        config = charger_config()
    rendement = config.get("rendement_charge", 0.90)
    base = {"conso_reference": conso_ref, "rendement": rendement,
            "kwh_batterie": 0.0, "kwh_attendu": 0.0, "ecart_kwh": 0.0,
            "ecart_pct": 0.0, "marge_kwh": round(marge_kwh, 1),
            "conso_enregistree": 0.0,
            "capacite_batterie": config.get("capacite_batterie", 0),
            "verdict": "non_configure"}
    if conso_ref <= 0 or km <= 0 or not 0 < rendement <= 1:
        return base

    kwh_batterie = km * conso_ref / 100
    kwh_attendu = kwh_batterie / rendement
    ecart = kwh_enregistres - kwh_attendu
    ecart_pct = ecart / kwh_attendu

    if abs(ecart_pct) <= SEUIL_ECART:
        verdict = "coherent"
    elif abs(ecart) <= marge_kwh:
        # l'ecart s'explique entierement par l'etat de charge aux deux bouts :
        # il faut plus de recul (plus de kilometres, plus de recharges)
        verdict = "trop_court"
    elif ecart < 0:
        # Il manque de l'energie. Ce n'est PAS forcement un oubli de saisie :
        # les recharges faites chez des proches ou sur des bornes gratuites
        # ne sont pas mesurables. On l'annonce donc comme une information
        # (« voila la part qui vient d'ailleurs ») et non comme une anomalie.
        verdict = "energie_exterieure"
    else:
        verdict = "excedent"      # trop d'energie : kilometrage ou reference a revoir
    base.update({"kwh_batterie": round(kwh_batterie, 1),
                 "kwh_attendu": round(kwh_attendu, 1),
                 "ecart_kwh": round(ecart, 1),
                 "ecart_pct": round(100 * ecart_pct, 1),
                 # consommation que l'application est capable de voir, a
                 # comparer a celle affichee par la voiture
                 "conso_enregistree": round(100 * kwh_enregistres * rendement / km, 1),
                 "verdict": verdict})
    return base


# ---------- import CSV wallbox ----------

# En dessous de cette energie, une ligne du CSV n'est pas une recharge mais un
# branchement de quelques secondes (test de la prise, cable remis en place...).
# Une vraie recharge fait au minimum plusieurs kWh, la marge est large.
KWH_MINIMUM = 0.05

# Formats de date rencontres dans les exports de bornes : la norme
# internationale, et la forme francaise que produisent certains modeles.
_FORMATS_DATE_CSV = (
    "%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M",
    "%d/%m/%Y %H:%M:%S", "%d/%m/%Y %H:%M",
    # Ajouts du 28/09/2026, pour les exports d'autres bornes : le « T » de
    # la norme, et les formes 01.03.2026 et 01-03-2026.
    "%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M",
    "%d.%m.%Y %H:%M:%S", "%d.%m.%Y %H:%M",
    "%d-%m-%Y %H:%M:%S", "%d-%m-%Y %H:%M",
)

# Une date reconnaissable a l'oeil : sert a distinguer la ligne de titres de
# colonnes d'une vraie ligne de donnees.
_DATE_VISIBLE = re.compile(
    r"\d{4}-\d{2}-\d{2}|\d{2}[/.-]\d{2}[/.-]\d{4}")


def _nombre_csv(texte: str) -> float | None:
    """Lit « 37.249kWh », « 4,84 € », « 12.80 »... ou renvoie None.

    Les exports collent l'unite au nombre ou l'en separent, et emploient le
    point ou la virgule decimale selon la langue de la borne.
    """
    net = texte.strip().replace("\u00a0", "").replace(" ", "")
    net = re.sub(r"(?i)kwh|kw|eur|€", "", net)
    net = net.replace(",", ".")
    try:
        valeur = float(net)
    except ValueError:
        return None
    return valeur if math.isfinite(valeur) else None


def _date_csv(texte: str) -> datetime | None:
    """Lit une date d'export dans l'un des formats connus, ou renvoie None.

    En dernier recours, la norme internationale complete, fuseau horaire
    compris (« 2026-03-01T21:00:00Z », « …+01:00 ») : la date est alors
    ramenee a l'heure de ce PC, celle de toutes les autres recharges."""
    net = texte.strip()
    for fmt in _FORMATS_DATE_CSV:
        try:
            return datetime.strptime(net, fmt)
        except ValueError:
            continue
    if not _DATE_VISIBLE.match(net):
        return None
    try:
        lue = datetime.fromisoformat(net)
    except ValueError:
        return None
    if lue.tzinfo is not None:
        lue = lue.astimezone().replace(tzinfo=None)
    return lue


def _analyser_ligne_csv(ligne: str, facteur_kwh: float = 1.0) -> tuple | None:
    """Reconnait une ligne d'export de borne, ou renvoie None.

    `facteur_kwh` convertit l'energie lue en kWh (0,001 pour des Wh).

    Les colonnes attendues sont, dans cet ordre : identifiant du chargeur,
    debut, fin, energie, duree, cout — la disposition qu'emploient les
    exports de wallbox domestiques.

    La reconnaissance ne se fait plus par un motif fige, qui exigeait le
    numero de serie d'UNE borne precise, la virgule comme separateur et le
    point decimal. Elle se fait par le contenu : deux dates, deux nombres.
    Une autre marque de borne, une autre langue, ou une mise a jour de
    firmware qui change le separateur passent desormais sans rien casser —
    et une ligne vraiment incomprehensible reste signalee.
    """
    # Separateur : le point-virgule est la convention des tableurs francais,
    # et il leve l'ambiguite avec la virgule decimale.
    sep = ";" if ligne.count(";") >= 5 else ","
    try:
        champs = next(csv.reader([ligne], delimiter=sep))
    except (csv.Error, StopIteration):
        return None
    if len(champs) < 6:
        return None

    debut = _date_csv(champs[1])
    fin = _date_csv(champs[2])
    kwh = _nombre_csv(champs[3])
    cout = _nombre_csv(champs[5])
    if debut is None or fin is None or kwh is None or cout is None:
        return None
    kwh *= facteur_kwh

    # Les dates repartent en texte : la suite de l'import les relit apres
    # avoir applique la correction d'horloge.
    return (champs[0].strip(),
            debut.isoformat(sep=" "),
            fin.isoformat(sep=" "),
            f"{kwh:.6f}",
            champs[4].strip(),
            f"{cout:.6f}")


def _facteur_kwh_du_titre(ligne_de_titres: str) -> float:
    """0,001 si le titre de la colonne d'energie (la 4e) annonce des Wh,
    sinon 1. Avant le 08/10/2026, un export en Wh etait lu en kWh : 12 500 Wh
    devenaient 12 500 kWh, sans avertissement."""
    sep = ";" if ligne_de_titres.count(";") >= 5 else ","
    try:
        titres = next(csv.reader([ligne_de_titres], delimiter=sep))
    except (csv.Error, StopIteration):
        return 1.0
    if len(titres) < 4:
        return 1.0
    titre = _sans_accents(titres[3])
    return 0.001 if "wh" in titre and "kwh" not in titre else 1.0


def _depouiller_csv(contenu: str) -> tuple[list[tuple], int, int]:
    """Depouille un export de borne.

    Renvoie (recharges lues, lignes non reconnues, lignes de donnees vues).
    La premiere ligne est ecartee si elle ne porte aucune date : c'est la
    ligne de titres de colonnes, pas une recharge perdue.
    """
    lignes = [ligne for ligne in contenu.splitlines() if ligne.strip()]
    facteur_kwh = 1.0
    if lignes and not _DATE_VISIBLE.search(lignes[0]):
        facteur_kwh = _facteur_kwh_du_titre(lignes[0])
        lignes = lignes[1:]

    records, non_reconnues = [], 0
    for ligne in lignes:
        champs = _analyser_ligne_csv(ligne, facteur_kwh)
        if champs is not None:
            records.append(champs)
        else:
            non_reconnues += 1
    return records, non_reconnues, len(lignes)


# Écart d'énergie toléré entre une saisie manuelle et la ligne du CSV qui
# décrit la même session : 0,1 kWh, ou 1 % pour les grosses charges. On
# recopie souvent l'énergie arrondie (30,5 pour 30,497) : exiger les trois
# décimales faisait compter la même nuit deux fois (jusqu'à la v2.0.0).
TOLERANCE_KWH = 0.1
TOLERANCE_RELATIVE = 0.01


def _meme_session(debut: datetime, kwh: float,
                  deja: list[tuple[datetime, dict]],
                  fin: datetime | None = None,
                  chargeur: str | None = None,
                  debut_borne: datetime | None = None) -> dict | None:
    """La recharge déjà enregistrée qui décrit la même session, sinon None.

    D'abord, une recharge importée qui a gardé l'heure de début écrite par
    la borne (« debut_borne », avant correction d'horloge) : même heure de
    borne, même énergie à trois décimales et même chargeur, c'est la même
    ligne du CSV, quel que soit le réglage de la correction. Avant l'analyse
    du 16/10/2026, une recharge courte réimportée après un changement de
    correction (15 min, décalée de 20 min) ne recouvrait plus la première :
    elle était ajoutée une seconde fois.

    Sinon (saisie manuelle, ou recharge importée avant ce correctif),
    même session = début à moins de 2 h d'écart, et même énergie :
    - pour une recharge déjà importée d'un CSV : même énergie à trois
      décimales près (la wallbox donne toujours le même chiffre), horaires
      qui se chevauchent, et même chargeur. Avant l'audit du 14/10/2026, deux
      sessions distinctes du même CSV (10 h-10 h 15 et 11 h-11 h 15, 1 kWh
      chacune) étaient prises pour une seule. Le chevauchement, et non
      l'heure exacte, reconnaît encore la même session quand la correction
      d'horloge a changé entre deux imports ;
    - pour une saisie manuelle : même énergie à la tolérance ci-dessus, dans
      les 2 h (l'heure saisie peut être celle, décalée, de la wallbox).
    S'il y en a plusieurs, la plus proche dans le temps l'emporte.
    """
    if debut_borne is not None:
        for _debut_exist, r_exist in deja:
            if (r_exist.get("source") == "csv_import"
                    and _heure_borne(r_exist) == debut_borne
                    and _meme_energie_csv(r_exist, kwh)
                    and _memes_chargeurs(chargeur, r_exist.get("chargeur"))):
                return r_exist

    ecart_admis = max(TOLERANCE_KWH, TOLERANCE_RELATIVE * kwh)
    retenue, meilleur = None, None
    for debut_exist, r_exist in deja:
        # Une recharge qui a son heure de borne a déjà été comparée
        # ci-dessus, à coup sûr : la règle approchée ne doit pas la
        # rapprocher d'une autre ligne (deux vraies sessions distinctes).
        if (debut_borne is not None and r_exist.get("source") == "csv_import"
                and _heure_borne(r_exist) is not None):
            continue
        secondes = abs((debut - debut_exist).total_seconds())
        if secondes > 2 * 3600:
            continue
        try:
            kwh_exist = float(r_exist["kwh"])
        except (ValueError, TypeError, KeyError):
            continue
        if r_exist.get("source") == "csv_import":
            identique = (round(kwh_exist, 3) == round(kwh, 3)
                         and _horaires_compatibles(debut, fin, debut_exist,
                                                   r_exist)
                         and _memes_chargeurs(chargeur,
                                              r_exist.get("chargeur")))
        else:
            identique = abs(kwh_exist - kwh) <= ecart_admis + 1e-9
        if identique and (meilleur is None or secondes < meilleur):
            retenue, meilleur = r_exist, secondes
    return retenue


def _heure_borne(r_exist: dict) -> datetime | None:
    """L'heure de début écrite par la borne, si la recharge l'a gardée."""
    try:
        return _parse_dt(r_exist["debut_borne"])
    except (ValueError, TypeError, KeyError):
        return None


def _meme_energie_csv(r_exist: dict, kwh: float) -> bool:
    """Même énergie à trois décimales : la borne donne toujours le même
    chiffre pour la même ligne."""
    try:
        return round(float(r_exist["kwh"]), 3) == round(kwh, 3)
    except (ValueError, TypeError, KeyError):
        return False


def _horaires_compatibles(debut: datetime, fin: datetime | None,
                          debut_exist: datetime, r_exist: dict) -> bool:
    """Vrai si les deux sessions se chevauchent dans le temps.

    Sans heure de fin d'un côté ou de l'autre, on ne peut pas trancher :
    on garde l'ancienne règle (vrai)."""
    if fin is None or not r_exist.get("fin"):
        return True
    try:
        fin_exist = _parse_dt(r_exist["fin"])
    except (ValueError, TypeError):
        return True
    return debut < fin_exist and debut_exist < fin


def _memes_chargeurs(chargeur: str | None, chargeur_exist) -> bool:
    """Deux chargeurs différents = deux sessions différentes. Un chargeur
    inconnu d'un côté (ancienne recharge, autre format de CSV) ne départage
    rien."""
    if not chargeur or not chargeur_exist:
        return True
    return str(chargeur).strip() == str(chargeur_exist).strip()


def _lire_texte_csv(chemin: Path) -> str:
    """Le contenu d'un export, quel que soit l'encodage où il a été enregistré.

    - UTF-8 (avec ou sans marque de début) : ce que produisent les bornes ;
    - UTF-16 (reconnu à sa marque de début) : « Texte Unicode » d'Excel ;
    - sinon l'encodage Windows (cp1252) : un CSV ouvert puis réenregistré
      par Excel en France. Jusqu'à la v2.0.0, ce dernier cas refusait le
      fichier entier, avec un message en anglais.
    """
    brut = chemin.read_bytes()
    if brut.startswith((b"\xff\xfe", b"\xfe\xff")):
        return brut.decode("utf-16")
    try:
        texte = brut.decode("utf-8-sig")
    except UnicodeDecodeError:
        texte = brut.decode("cp1252", errors="replace")
    # Même traitement des fins de ligne qu'une lecture en mode texte : un
    # export aux lignes terminées par un CR seul doit être lu ligne à ligne.
    return texte.replace("\r\n", "\n").replace("\r", "\n")


# ---------- import CSV d'autres bornes (28/09/2026) ----------
# Un export qui n'a pas les six colonnes attendues n'est plus refuse : la
# page Importer montre ses premieres lignes, l'utilisateur dit quelle colonne
# porte quoi (une « correspondance »), et ce choix est retenu dans
# tarifs.json (cle « correspondances_csv ») pour les fichiers suivants du
# meme modele, reconnus a leur ligne de titres.


class FormatCsvInconnu(ValueError):
    """Le fichier n'a pas le format d'origine, et aucun choix de colonnes
    n'est retenu pour son modele : la page Importer demande les colonnes."""


_SEPARATEURS = (";", "\t", ",")      # par ordre de preference


def _separateur(lignes: list[str]) -> str:
    """Le separateur qui decoupe le mieux les premieres lignes : le meme
    nombre de colonnes sur chacune, et le plus grand."""
    def note(sep):
        comptes = [len(next(csv.reader([x], delimiter=sep)))
                   for x in lignes[:6]]
        reguliers = sum(1 for n in comptes if n == comptes[0] and n > 1)
        return (reguliers, comptes[0] if comptes else 0)
    return max(_SEPARATEURS, key=lambda sep: (*note(sep),
                                              -_SEPARATEURS.index(sep)))


def apercu_csv(chemin: str | Path) -> dict:
    """Les premieres lignes d'un export, decoupees en colonnes.

    Rend {"separateur", "entetes" (les titres, ou « Colonne 1 »... s'il n'y
    en a pas), "lignes" (cinq lignes au plus), "signature" (ce qui
    reconnait le modele du fichier : son separateur et ses titres ; None
    sans ligne de titres)}."""
    contenu = _lire_texte_csv(Path(chemin))
    lignes = [x for x in contenu.splitlines() if x.strip()]
    if not lignes:
        raise ValueError(f"« {Path(chemin).name} » est vide.")
    sep = _separateur(lignes)
    decoupees = [[c.strip() for c in champs]
                 for champs in csv.reader(lignes, delimiter=sep)]
    if _DATE_VISIBLE.search(lignes[0]):
        entetes = [f"Colonne {i + 1}" for i in range(len(decoupees[0]))]
        signature = None
    else:
        entetes, decoupees = decoupees[0], decoupees[1:]
        signature = sep + "|" + "|".join(entetes)
    return {"separateur": sep, "entetes": entetes, "lignes": decoupees[:5],
            "signature": signature}


def _sans_accents(texte: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", texte.lower())
                   if unicodedata.category(c) != "Mn")


# Mots qui trahissent le contenu d'une colonne, en francais et en anglais.
_MOTS_COLONNES = {
    "fin": ("fin", "end", "stop", "arret"),
    "debut": ("debut", "start", "begin", "depart", "date"),
    "duree": ("duree", "duration", "temps", "time"),
    "kwh": ("kwh", "energ", "wh", "conso"),
    "cout": ("cout", "cost", "prix", "price", "montant", "amount", "eur",
             "€"),
}


def deviner_correspondance(apercu: dict) -> dict:
    """Ce qu'on peut deviner des titres de colonnes. Chaque colonne ne sert
    qu'une fois ; la fin est cherchee avant le debut, pour que « Date de
    fin » ne soit pas prise pour le debut."""
    titres = [_sans_accents(t) for t in apercu["entetes"]]
    prises: set[int] = set()
    choix: dict = {"debut": None, "fin": None, "duree": None, "kwh": None,
                   "unite": "kWh", "cout": None}
    for champ in ("fin", "duree", "kwh", "cout", "debut"):
        for i, titre in enumerate(titres):
            if i not in prises and any(m in titre
                                       for m in _MOTS_COLONNES[champ]):
                choix[champ] = i
                prises.add(i)
                break
    if choix["kwh"] is not None:
        titre = titres[choix["kwh"]]
        if "wh" in titre and "kwh" not in titre:
            choix["unite"] = "Wh"
    # Une fin trouvee rend la duree inutile, et inversement la duree ne sert
    # que faute de fin.
    if choix["fin"] is not None:
        choix["duree"] = None
    return choix


def verifier_correspondance(c: dict) -> None:
    """Leve ValueError, en francais, s'il manque une colonne indispensable."""
    if c.get("debut") is None:
        raise ValueError("Indiquez la colonne du début de la recharge.")
    if c.get("kwh") is None:
        raise ValueError("Indiquez la colonne de l'énergie.")
    if c.get("fin") is None and c.get("duree") is None:
        raise ValueError("Indiquez la colonne de la fin ou la durée de la "
                         "recharge.")


def _duree_csv(texte: str) -> timedelta | None:
    """« 8:00 », « 8:00:00 », « 1h30 », ou un nombre de minutes."""
    net = texte.strip().lower().replace(" ", "")
    m = re.fullmatch(r"(\d+):(\d{2})(?::(\d{2}))?", net)
    if m:
        return timedelta(hours=int(m.group(1)), minutes=int(m.group(2)),
                         seconds=int(m.group(3) or 0))
    m = re.fullmatch(r"(\d+)h(\d{1,2})?(?:min)?", net)
    if m:
        return timedelta(hours=int(m.group(1)), minutes=int(m.group(2) or 0))
    minutes = _nombre_csv(net.replace("min", ""))
    return timedelta(minutes=minutes) if minutes is not None else None


def _depouiller_avec(contenu: str, c: dict) -> tuple[list[tuple], int, int]:
    """Comme _depouiller_csv, mais avec les colonnes choisies par
    l'utilisateur. Rend les memes tuples, pour que la suite de l'import
    soit la meme : pas de doublon, saisies manuelles remplacees..."""
    lignes = [x for x in contenu.splitlines() if x.strip()]
    if not lignes:
        return [], 0, 0
    sep = _separateur(lignes)
    if not _DATE_VISIBLE.search(lignes[0]):
        lignes = lignes[1:]
    records, non_reconnues = [], 0
    for champs in csv.reader(lignes, delimiter=sep):
        try:
            debut = _date_csv(champs[c["debut"]])
            if c.get("fin") is not None:
                fin = _date_csv(champs[c["fin"]])
            else:
                duree = _duree_csv(champs[c["duree"]])
                fin = (apres_duree(debut, duree)
                       if debut and duree is not None else None)
            kwh = _nombre_csv(champs[c["kwh"]])
            cout = (_nombre_csv(champs[c["cout"]])
                    if c.get("cout") is not None else None)
        except IndexError:
            debut = None
        if debut is None or fin is None or kwh is None:
            non_reconnues += 1
            continue
        if c.get("unite") == "Wh":
            kwh /= 1000
        records.append(("", debut.isoformat(sep=" "), fin.isoformat(sep=" "),
                        f"{kwh:.6f}", "",
                        f"{cout:.6f}" if cout is not None else None))
    return records, non_reconnues, len(lignes)


def charger_correspondances() -> dict:
    """Les choix de colonnes retenus : {signature du modele: choix}."""
    return dict(_lire_tarifs_json().get("correspondances_csv") or {})


def retenir_correspondance(apercu: dict, c: dict) -> None:
    """Retient le choix de colonnes pour ce modele de fichier. Sans ligne
    de titres, rien : le modele ne se reconnaitrait pas a coup sur."""
    if not apercu.get("signature"):
        return
    contenu = _lire_tarifs_json()
    retenues = dict(contenu.get("correspondances_csv") or {})
    retenues[apercu["signature"]] = {k: c.get(k) for k in (
        "debut", "fin", "duree", "kwh", "unite", "cout")}
    contenu["correspondances_csv"] = retenues
    _ecrire_tarifs(contenu)


def _n_lignes(n: int) -> str:
    """« 1 ligne », « 2 lignes » (audit du 08/10/2026 : « 1 lignes »)."""
    return f"{n} ligne{'s' if n > 1 else ''}"


def importer_csv_maison(chemin: str | Path, ignorer_zero: bool = True,
                        correspondance: dict | None = None) -> dict:
    """Importe l'export d'une borne. Sans `correspondance`, le format
    d'origine (six colonnes) est reconnu seul ; a defaut, un choix de
    colonnes retenu pour ce modele de fichier ; a defaut encore,
    FormatCsvInconnu : la page Importer demande alors les colonnes."""
    chemin = Path(chemin)
    contenu = _lire_texte_csv(chemin)

    # Une ligne que le lecteur ne comprend pas est COMPTEE, jamais ignoree en
    # silence : sinon l'import annoncait « 0 ajoutees, rien de nouveau », et
    # l'utilisateur, croyant le fichier deja traite, pouvait le supprimer et
    # perdre les recharges qu'il contenait.
    # À noter : certains exports terminent leurs lignes par un CR seul.
    # _lire_texte_csv les traduit à la lecture, splitlines() les compte
    # donc bien.
    if correspondance is not None:
        verifier_correspondance(correspondance)
        records, non_reconnues, n_lignes = _depouiller_avec(contenu,
                                                            correspondance)
    else:
        records, non_reconnues, n_lignes = _depouiller_csv(contenu)
        if not records and n_lignes:
            retenue = charger_correspondances().get(
                apercu_csv(chemin)["signature"] or "")
            if retenue:
                records, non_reconnues, n_lignes = _depouiller_avec(contenu,
                                                                    retenue)
            else:
                raise FormatCsvInconnu(
                    f"Aucune recharge reconnue dans « {chemin.name} », alors "
                    f"qu'il contient {_n_lignes(n_lignes)} de données.\n\n"
                    "Ce fichier n'a pas les six colonnes de l'export d'origine "
                    "(chargeur, début, fin, énergie, durée, coût) : "
                    "indiquez quelle colonne contient quoi.\n\n"
                    "NE LE SUPPRIMEZ PAS : les recharges qu'il contient ne "
                    "sont pas enregistrées."
                )
    if not records:
        if not n_lignes:
            raise ValueError(
                f"« {chemin.name} » ne contient aucune recharge : le fichier "
                "est vide, ou réduit à sa ligne d'en-tête."
            )
        raise ValueError(
            f"Aucune recharge reconnue dans « {chemin.name} », alors qu'il "
            f"contient {_n_lignes(n_lignes)} de données.\n\n"
            "Vérifiez les colonnes choisies (début, fin ou durée, énergie) : "
            "aucune ligne n'a pu être lue avec elles.\n\n"
            "NE LE SUPPRIMEZ PAS : les recharges qu'il contient ne sont pas "
            "enregistrées."
        )

    data = charger_donnees(pour_modification=True)
    tarifs = charger_tarifs()
    config = charger_config()
    correction = timedelta(minutes=config["correction_csv_minutes"])

    # Les recharges maison déjà enregistrées, avec leur début : pour repérer
    # une MÊME session, que l'heure soit identique ou décalée — typiquement
    # une saisie manuelle faite à l'heure de la wallbox, sans la correction
    # d'horloge (et donc avec une heure de fin fausse).
    deja: list[tuple[datetime, dict]] = []
    for r in data["recharges"]:
        if r.get("lieu") != "maison":
            continue
        try:
            deja.append((_parse_dt(r["date"]), r))
        except (ValueError, TypeError, KeyError):
            pass

    ajoutes = 0
    doublons = 0
    remplaces = 0
    zero_kwh = 0
    parasites = 0
    completees = 0      # anciennes recharges qui reçoivent l'heure de borne
    hors_grille: list[datetime] = []   # débuts qu'aucun tarif ne couvre

    for serial, s_debut, s_fin, kwh_str, duree, cout_str in records:
        kwh = float(kwh_str)
        # Une autre borne peut ne donner aucun cout (colonne « aucune »).
        cout_wb = float(cout_str) if cout_str is not None else None
        if ignorer_zero and kwh == 0:
            zero_kwh += 1
            continue

        # L'heure telle que la borne l'a écrite, avant correction : c'est
        # elle qui reconnaît la même ligne d'un import à l'autre.
        debut_borne = _parse_dt(s_debut)
        debut = _a_la_minute(debut_borne + correction)
        fin = _a_la_minute(_parse_dt(s_fin) + correction)

        # Branchement parasite : la prise a ete connectee une poignee de
        # secondes, ou n'a laisse passer qu'une bricole d'energie. Ce n'est
        # pas une recharge ; l'enregistrer gonflerait le compteur et, faute
        # de duree, tout serait classe en heures pleines.
        if fin <= debut or kwh < KWH_MINIMUM:
            parasites += 1
            continue

        proche = _meme_session(debut, kwh, deja, fin=fin, chargeur=serial,
                               debut_borne=debut_borne)
        # Déjà issue d'un import CSV : rien de neuf à en tirer, on passe.
        # Sinon (saisie manuelle), on la remplace plus bas par les données
        # exactes du CSV, même si l'heure de début coïncide déjà.
        if proche is not None and proche.get("source") == "csv_import":
            doublons += 1
            # Recharge importée avant le 16/10/2026 : elle reçoit l'heure de
            # la borne, pour être reconnue même si la correction change.
            if _heure_borne(proche) is None:
                proche["debut_borne"] = debut_borne.isoformat(
                    timespec="seconds")
                completees += 1
            continue

        # Une recharge qu'aucun tarif ne couvre (typiquement : un historique
        # de borne plus ancien que le premier tarif) est NOTEE, et l'import
        # continue pour les reperer toutes : le message final dit la periode
        # en cause et quoi faire (analyse « nouvel utilisateur » du
        # 19/10/2026 ; avant, l'import s'arretait a la premiere avec la
        # formule de la saisie a la main, « Vérifiez la date saisie »).
        if tarifs and (_trouver_tarif(debut, tarifs) is None
                       or _trouver_tarif(fin, tarifs) is None):
            hors_grille.append(debut)
            continue
        calc = calculer_cout(debut, fin, kwh, tarifs,
                             puissance_kw=config["puissance_borne_kw"])
        champs = {
            "date": debut.isoformat(timespec="minutes"),
            "fin": fin.isoformat(timespec="minutes"),
            "lieu": "maison",
            "kwh": round(kwh, 3),
            "kwh_hp": calc["kwh_hp"],
            "kwh_hc": calc["kwh_hc"],
            "cout_eur": round(calc["cout"], 2),
            "prix_kwh": _prix_unitaire(round(calc["cout"], 2), kwh),
            "tarif_id": calc["tarif_id"],
            "tarif_nom": calc["tarif_nom"],
            "duree": duree,
            "source": "csv_import",
            "chargeur": serial,
            "debut_borne": debut_borne.isoformat(timespec="seconds"),
        }
        if cout_wb is not None:
            champs["cout_wallbox"] = round(cout_wb, 2)
        if proche is not None:
            # Saisie manuelle de la même session : remplacée par les données
            # précises du CSV (heure corrigée, durée, coût wallbox). L'id
            # d'origine est conservé.
            proche.update(champs)
            remplaces += 1
        else:
            nouvelle = {"id": _nouvel_id(), **champs}
            data["recharges"].append(nouvelle)
            # Retenue aussitôt : si la même session figure deux fois dans le
            # CSV, la seconde sera vue comme un doublon (source csv_import).
            deja.append((debut, nouvelle))
            ajoutes += 1

    # Tout ou rien : tant qu'une recharge du fichier n'a pas de tarif, rien
    # n'est enregistre. Sinon le second import, apres correction du tarif,
    # melangerait des recharges deja la et des neuves.
    if hors_grille:
        raise ValueError(_message_hors_grille(hors_grille, tarifs))

    # N'ecrire (et donc ne creer un backup) que si quelque chose a change :
    # reimporter un CSV deja traite ne doit pas consommer une des 15 places
    # de la rotation des sauvegardes pour rien.
    if ajoutes or remplaces or completees:
        sauvegarder_donnees(data)
    return {"total_lus": len(records), "ajoutes": ajoutes, "doublons": doublons,
            "remplaces": remplaces, "zero_kwh": zero_kwh,
            "parasites": parasites, "non_reconnues": non_reconnues}


def _message_hors_grille(debuts: list[datetime], tarifs: list[dict]) -> str:
    """Le message d'un import refuse parce que des recharges du fichier
    tombent hors de la grille tarifaire : combien, de quand a quand, et
    quoi faire. Ecrit pour quelqu'un qui n'a rien saisi a la main."""
    premiere, derniere = min(debuts), max(debuts)
    n = fmt_nb_recharges(len(debuts))
    if premiere.date() == derniere.date():
        quand = f"le {premiere:%d/%m/%Y}"
    else:
        quand = f"du {premiere:%d/%m/%Y} au {derniere:%d/%m/%Y}"
    texte = (f"Rien n'a été importé : {n} de ce fichier, {quand}, "
             f"{'tombent' if len(debuts) > 1 else 'tombe'} à des dates "
             "qu'aucun tarif ne couvre.\n\n")
    debut_grille = min(datetime.fromisoformat(t["debut"]) for t in tarifs)
    if premiere < debut_grille:
        texte += (f"Votre grille tarifaire commence le "
                  f"{debut_grille:%d/%m/%Y}. Ouvrez la page « Tarifs », "
                  "modifiez votre tarif pour qu'il commence le "
                  f"{premiere:%d/%m/%Y} ou avant (ou ajoutez une période "
                  "pour ces dates), puis importez de nouveau ce fichier.")
    else:
        texte += ("Ouvrez la page « Tarifs » et ajoutez une période qui "
                  "couvre ces dates, puis importez de nouveau ce fichier.")
    return texte + ("\n\nNE LE SUPPRIMEZ PAS : les recharges qu'il contient "
                    "ne sont pas enregistrées.")


def recalculer_tout() -> tuple[int, list[str]]:
    """Recalcule le coût de toutes les recharges maison à partir des tarifs courants.

    Rend (nombre de recharges recalculées, dates de celles laissées telles
    quelles). Ces dernières étaient passées sous silence jusqu'à la v2.0.0 :
    le message n'annonçait que les recalculées."""
    data = charger_donnees(pour_modification=True)
    tarifs = charger_tarifs()
    puissance = charger_config()["puissance_borne_kw"]
    n = 0
    laissees: list[str] = []
    for r in data["recharges"]:
        if r.get("lieu") != "maison":
            continue
        debut = _parse_dt(r["date"])
        # Une recharge saisie sans heure de fin doit suivre les changements
        # de prix comme les autres : sans cela, elle gardait indefiniment le
        # cout calcule le jour de sa saisie.
        try:
            calc = (calculer_cout(debut, _parse_dt(r["fin"]), r["kwh"], tarifs,
                                  puissance_kw=puissance)
                    if r.get("fin")
                    else calculer_cout_sans_duree(debut, r["kwh"], tarifs))
        except ValueError:
            # Plus de tarif pour cette date, ou passage en heures creuses
            # d'une recharge sans duree : on la laisse telle quelle plutot
            # que d'interrompre le recalcul de toutes les autres — et on le
            # dit.
            laissees.append(r["date"])
            continue
        r["kwh_hp"] = calc["kwh_hp"]
        r["kwh_hc"] = calc["kwh_hc"]
        r["cout_eur"] = round(calc["cout"], 2)
        r["prix_kwh"] = _prix_unitaire(r["cout_eur"], r["kwh"])
        r["tarif_id"] = calc["tarif_id"]
        r["tarif_nom"] = calc["tarif_nom"]
        n += 1
    sauvegarder_donnees(data)
    return n, laissees


def enregistrer_reglages_borne(reglages: dict) -> dict:
    """Enregistre les réglages de la page Paramètres et, si la correction
    d'horloge change, replace les recharges déjà importées d'un CSV.

    Avant le 23/10/2026, changer la correction ne valait que pour les
    imports suivants : les recharges déjà importées gardaient les heures
    et le partage heures pleines / heures creuses de l'ancien réglage. Une
    recharge lue 0 h -> 5 h 30 dans le CSV et importée avec -60 restait
    à 23 h -> 4 h 30, toute en heures creuses (exemple), même une fois le
    réglage remis à 0.

    Chaque recharge importée est décalée puis son coût recalculé :
    - si elle a gardé l'heure de la borne (« debut_borne »), son début
      repart de cette heure plus la nouvelle correction ;
    - sinon (importée avant le 16/10/2026), elle est décalée de la
      différence entre l'ancienne et la nouvelle correction. On ne lui
      invente pas d'heure de borne : sans les secondes du CSV, la ligne ne
      serait plus reconnue au réimport.
    La fin suit le même décalage que le début. Les saisies à la main ne
    bougent pas : leur heure est celle que l'utilisateur a tapée.

    Si la puissance de charge de la borne change (23/10/2026), le coût de
    toutes les recharges à la maison est recalculé avec elle.

    Rend {"decalees": nombre de recharges replacées, "recalculees": nombre
    de recharges recalculées pour la nouvelle puissance, "laissees": dates
    de celles dont le coût n'a pas pu être recalculé (aucun tarif), qui
    sont tout de même replacées}.
    """
    config = charger_config()
    ancienne = config["correction_csv_minutes"]
    nouvelle = int(reglages.get("correction_csv_minutes", ancienne))
    puissance = float(reglages.get("puissance_borne_kw",
                                   config["puissance_borne_kw"]))
    decalees = recalculees = 0
    laissees: list[str] = []
    if nouvelle != ancienne:
        data = charger_donnees(pour_modification=True)
        tarifs = charger_tarifs()
        for rec in data["recharges"]:
            if (rec.get("source") != "csv_import"
                    or rec.get("lieu") != "maison"):
                continue
            debut = _parse_dt(rec["date"])
            borne = _heure_borne(rec)
            if borne is not None:
                nouveau_debut = _a_la_minute(
                    borne + timedelta(minutes=nouvelle))
            else:
                nouveau_debut = debut + timedelta(minutes=nouvelle - ancienne)
            ecart = nouveau_debut - debut
            if not ecart:
                continue
            rec["date"] = nouveau_debut.isoformat(timespec="minutes")
            fin = None
            if rec.get("fin"):
                fin = _parse_dt(rec["fin"]) + ecart
                rec["fin"] = fin.isoformat(timespec="minutes")
            decalees += 1
            try:
                calc = (calculer_cout(nouveau_debut, fin, rec["kwh"], tarifs,
                                      puissance_kw=puissance)
                        if fin is not None
                        else calculer_cout_sans_duree(nouveau_debut,
                                                      rec["kwh"], tarifs))
            except ValueError:
                # Plus de tarif pour la nouvelle heure : l'heure est
                # replacée, le coût reste l'ancien, et on le dit.
                laissees.append(rec["date"])
                continue
            rec["kwh_hp"] = calc["kwh_hp"]
            rec["kwh_hc"] = calc["kwh_hc"]
            rec["cout_eur"] = round(calc["cout"], 2)
            rec["prix_kwh"] = _prix_unitaire(rec["cout_eur"], rec["kwh"])
            rec["tarif_id"] = calc["tarif_id"]
            rec["tarif_nom"] = calc["tarif_nom"]
        # Les recharges d'abord : si leur écriture échoue, l'ancien réglage
        # reste en place et décrit toujours les heures enregistrées.
        if decalees:
            sauvegarder_donnees(data)
    enregistrer_config(reglages)
    # La puissance d'abord enregistrée : recalculer_tout() la relit.
    if puissance != config["puissance_borne_kw"]:
        recalculees, sans_tarif = recalculer_tout()
        laissees = list(dict.fromkeys(laissees + sans_tarif))
    return {"decalees": decalees, "recalculees": recalculees,
            "laissees": laissees}
