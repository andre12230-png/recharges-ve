"""Sauvegarde des donnees sur un support externe (cle USB, disque).

Les sauvegardes automatiques (backups/) restent sur le meme disque que les
donnees : si ce disque lache, ou si le PC est vole, tout part ensemble. Ce
module copie les fichiers de donnees vers un dossier choisi par
l'utilisateur, dans un sous-dossier date, puis VERIFIE chaque copie octet
pour octet avant d'annoncer que c'est fait.

Il ne depend pas de l'interface : la fenetre choisit le dossier, ce module
fait la copie. Il se teste donc sans ouvrir de fenetre, et peut etre repris
tel quel par une autre application.
"""
from __future__ import annotations

import hashlib
import re
import shutil
import sys
from datetime import date, datetime
from pathlib import Path


class SauvegardeImpossible(Exception):
    """Echec explique en francais, a montrer tel quel a l'utilisateur."""


def _empreinte(chemin: Path) -> str:
    return hashlib.sha256(chemin.read_bytes()).hexdigest()


def texte_lisezmoi(nom_appli: str, version: str, quand: datetime,
                   fichiers: list[str], dossier_donnees: Path) -> str:
    """Le mode d'emploi depose a cote des copies : sans lui, une sauvegarde
    retrouvee dans deux ans sur une cle ne dit pas quoi en faire. C'est un
    texte a lire, pas du code : il est accentue."""
    liste = "\n".join(f"  - {nom}" for nom in fichiers)
    return (
        f"Sauvegarde faite par {nom_appli} {version}\n"
        f"le {quand:%d/%m/%Y à %H:%M}.\n"
        "\n"
        "Fichiers sauvegardés :\n"
        f"{liste}\n"
        "\n"
        "POUR LA REMETTRE EN SERVICE\n"
        "\n"
        f"1. Fermez {nom_appli}.\n"
        "2. Ouvrez le dossier de vos données. Sur l'ordinateur où cette\n"
        "   sauvegarde a été faite, c'était :\n"
        f"   {dossier_donnees}\n"
        "3. Recopiez-y les fichiers ci-dessus, en acceptant de remplacer\n"
        "   ceux qui s'y trouvent.\n"
        f"4. Relancez {nom_appli}.\n"
    )


def sauvegarder(fichiers: list[Path | None], destination: Path,
                dossier_donnees: Path, nom_appli: str, version: str,
                maintenant: datetime | None = None,
                hors_des_donnees: bool = True) -> tuple[Path, list[str]]:
    """Copie les fichiers existants dans un sous-dossier date de
    `destination`, et verifie chaque copie.

    `hors_des_donnees=False` n'est utilise que par la sauvegarde de
    fermeture, qui va volontairement dans le dossier des donnees.

    Renvoie le dossier cree et la liste des fichiers copies. Leve
    SauvegardeImpossible, avec un message comprehensible, si la sauvegarde
    ne peut pas etre faite ou ne peut pas etre garantie.
    """
    quand = maintenant or datetime.now()
    destination = Path(destination)
    if not destination.is_dir():
        raise SauvegardeImpossible(
            "Le dossier choisi est introuvable. La clé USB a-t-elle été "
            "retirée ?")
    # Sauvegarder dans le dossier des donnees lui-meme ne protege de rien.
    if hors_des_donnees and destination.resolve().is_relative_to(
            Path(dossier_donnees).resolve()):
        raise SauvegardeImpossible(
            "Ce dossier est celui de vos données : une copie à cet endroit "
            "disparaîtrait avec elles. Choisissez une clé USB ou un disque "
            "externe.")

    presents = [Path(f) for f in fichiers if f and Path(f).is_file()]
    if not presents:
        raise SauvegardeImpossible(
            "Il n'y a encore aucune donnée à sauvegarder.")

    base = f"Sauvegarde {nom_appli} {quand:%Y-%m-%d %Hh%M}"
    cible = destination / base
    n = 2
    while cible.exists():            # deux sauvegardes dans la meme minute
        cible = destination / f"{base} ({n})"
        n += 1

    # La copie se fait dans un dossier « (en cours) », qui ne prend le nom
    # habituel qu'une fois TOUT copie et verifie. Avant l'analyse du
    # 16/10/2026, une panne au milieu laissait un dossier au nom d'une
    # sauvegarde complete, avec une partie des fichiers seulement.
    en_cours = cible.with_name(cible.name + MARQUE_EN_COURS)
    noms = [f.name for f in presents]
    try:
        en_cours.mkdir(parents=True)
        for f in presents:
            shutil.copy2(f, en_cours / f.name)
        (en_cours / "LISEZMOI.txt").write_text(
            texte_lisezmoi(nom_appli, version, quand, noms, dossier_donnees),
            encoding="utf-8")
    except OSError as e:
        _marquer_inachevee(en_cours)
        raise SauvegardeImpossible(
            f"La copie a échoué ({e.strerror or e}). La clé est-elle pleine, "
            "retirée ou protégée en écriture ? Le dossier commencé porte la "
            "mention « INACHEVÉE » : ne vous en servez pas.") from e

    # Une copie n'est une sauvegarde que si elle est identique a l'original.
    for f in presents:
        if _empreinte(f) != _empreinte(en_cours / f.name):
            _marquer_inachevee(en_cours)
            raise SauvegardeImpossible(
                f"La copie de {f.name} ne correspond pas à l'original : ne "
                "comptez pas sur cette sauvegarde, et réessayez sur un autre "
                "support. Le dossier porte la mention « INACHEVÉE ».")
    try:
        en_cours.rename(cible)
    except OSError as e:
        raise SauvegardeImpossible(
            f"Les fichiers sont copiés et vérifiés, mais le dossier n'a pas pu "
            f"prendre son nom définitif ({e.strerror or e}) : il s'appelle "
            f"encore « {en_cours.name} ».") from e
    return cible, noms


# Ce qui s'ajoute au nom d'une sauvegarde tant qu'elle n'est pas finie, et
# quand elle a echoue. Aucun de ces noms n'est reconnu par copies_a_retirer
# ni pris pour la derniere copie de fermeture.
MARQUE_EN_COURS = " (en cours)"
MARQUE_INACHEVEE = " INACHEVÉE - ne pas utiliser"


def _marquer_inachevee(en_cours: Path) -> None:
    """Renomme un dossier de copie rate. Rien n'est efface : le dossier
    reste, avec un nom qui dit de ne pas s'en servir. Si meme le renommage
    echoue, il garde la mention « (en cours) », tout aussi parlante."""
    if not en_cours.exists():
        return
    base = en_cours.name[:-len(MARQUE_EN_COURS)]
    rate = en_cours.with_name(base + MARQUE_INACHEVEE)
    n = 2
    while rate.exists():
        rate = en_cours.with_name(f"{base}{MARQUE_INACHEVEE} ({n})")
        n += 1
    try:
        en_cours.rename(rate)
    except OSError:
        pass


def _copie_complete(nom: str) -> bool:
    """Faux pour un dossier de copie en cours ou ratee."""
    return MARQUE_EN_COURS not in nom and "INACHEVÉE" not in nom


# Le sous-dossier du dossier des donnees ou va la copie faite a chaque
# fermeture (demande de l'auteur du 24/09/2026, a la place de l'envoi GitHub).
DOSSIER_FERMETURE = "Sauvegardes"

# Nombre de copies de fermeture gardees telles quelles. Au-dela, on ne garde
# que la derniere copie de chaque mois (28/09/2026 : avant, aucune n'etait
# jamais retiree et le dossier grossissait sans fin).
GARDER_RECENTES = 10


def copies_a_retirer(noms: list[str], nom_appli: str,
                     garder: int = GARDER_RECENTES) -> list[str]:
    """Parmi les noms de dossiers de <donnees>\\Sauvegardes, ceux qu'on peut
    retirer : tout sauf les `garder` copies les plus recentes et la derniere
    copie de chaque mois.

    Seuls les dossiers crees par l'application sont concernes, reconnus a
    leur nom exact « Sauvegarde <appli> AAAA-MM-JJ HHhMM » (suivi de « (2) »
    pour une deuxieme copie dans la meme minute). Tout autre dossier range
    la par l'utilisateur est ignore. Rend les noms du plus ancien au plus
    recent.
    """
    motif = re.compile(
        rf"Sauvegarde {re.escape(nom_appli)} "
        r"(\d{4}-\d{2})-\d{2} \d{2}h\d{2}(?: \((\d+)\))?")

    copies = []                         # (cle de tri, mois, nom)
    for nom in noms:
        m = motif.fullmatch(nom)
        if m:
            # « (2) » vient apres la copie sans numero de la meme minute, et
            # « (10) » apres « (9) » : on trie sur le numero, pas sur le texte.
            date = nom[len(f"Sauvegarde {nom_appli} "):][:16]
            copies.append(((date, int(m.group(2) or 1)), m.group(1), nom))
    copies.sort()

    gardees = {nom for _, _, nom in copies[-garder:]} if garder > 0 else set()
    derniere_du_mois = {}
    for _, mois, nom in copies:         # du plus ancien au plus recent :
        derniere_du_mois[mois] = nom    # la derniere ecriture l'emporte
    gardees |= set(derniere_du_mois.values())
    return [nom for _, _, nom in copies if nom not in gardees]


def _disque_local(chemin: Path) -> bool:
    """Vrai si `chemin` est sur un disque fixe de ce PC.

    Sur une cle USB ou un lecteur reseau, il n'y a pas de Corbeille : Windows
    effacerait le dossier pour de bon au lieu de l'y mettre."""
    import ctypes
    racine = Path(chemin).resolve().anchor          # « F:\ »
    DRIVE_FIXED = 3
    return ctypes.windll.kernel32.GetDriveTypeW(racine) == DRIVE_FIXED


def mettre_a_la_corbeille(chemin: Path) -> bool:
    """Met un dossier a la Corbeille de Windows, d'ou il peut etre recupere.

    Rend True si le dossier est parti, False si ce n'etait pas possible (pas
    sous Windows, pas sur un disque fixe, refus de Windows) : le dossier reste
    alors en place. Jamais de suppression definitive."""
    if sys.platform != "win32" or not _disque_local(chemin):
        return False
    import ctypes
    from ctypes import wintypes

    class SHFILEOPSTRUCTW(ctypes.Structure):
        _fields_ = [("hwnd", wintypes.HWND), ("wFunc", wintypes.UINT),
                    ("pFrom", wintypes.LPCWSTR), ("pTo", wintypes.LPCWSTR),
                    ("fFlags", ctypes.c_ushort),
                    ("fAnyOperationsAborted", wintypes.BOOL),
                    ("hNameMappings", ctypes.c_void_p),
                    ("lpszProgressTitle", wintypes.LPCWSTR)]

    FO_DELETE = 3
    FOF_SILENT = 0x0004                 # pas de barre de progression
    FOF_NOCONFIRMATION = 0x0010         # pas de question « Voulez-vous... »
    FOF_ALLOWUNDO = 0x0040              # A LA CORBEILLE, et non effacer
    FOF_NOERRORUI = 0x0400              # pas de boite d'erreur de Windows
    operation = SHFILEOPSTRUCTW(
        wFunc=FO_DELETE,
        # Windows attend une liste terminee par deux caracteres nuls.
        pFrom=str(Path(chemin).resolve()) + "\0",
        fFlags=FOF_ALLOWUNDO | FOF_NOCONFIRMATION | FOF_SILENT | FOF_NOERRORUI)
    code = ctypes.windll.shell32.SHFileOperationW(ctypes.byref(operation))
    return code == 0 and not operation.fAnyOperationsAborted \
        and not Path(chemin).exists()


def _retirer_copies_en_trop(destination: Path, nom_appli: str,
                            corbeille) -> None:
    """Envoie a la Corbeille les copies de fermeture en trop. Ne leve jamais
    d'exception : un tri qui echoue laisse simplement les copies en place,
    il ne doit pas gener la fermeture."""
    try:
        noms = [d.name for d in destination.iterdir() if d.is_dir()]
        for nom in copies_a_retirer(noms, nom_appli):
            if not corbeille(destination / nom):
                return          # Corbeille indisponible : inutile d'insister
    except Exception:
        return


def sauvegarder_a_la_fermeture(fichiers: list[Path | None],
                               dossier_donnees: Path, nom_appli: str,
                               version: str,
                               maintenant: datetime | None = None,
                               corbeille=mettre_a_la_corbeille
                               ) -> Path | None:
    """Copie les donnees dans <dossier des donnees>\\Sauvegardes, dans un
    sous-dossier date, a la fermeture de l'application.

    Si rien n'a change depuis la derniere copie, rien n'est fait et la
    fonction rend None : fermer dix fois l'appli sans rien saisir ne cree
    pas dix dossiers identiques. Apres une nouvelle copie, celles en trop
    (voir copies_a_retirer) partent a la Corbeille ; `corbeille` n'est
    remplacee que par les tests.
    Leve SauvegardeImpossible si la copie echoue.
    """
    destination = Path(dossier_donnees) / DOSSIER_FERMETURE
    try:
        destination.mkdir(exist_ok=True)
    except OSError as e:
        raise SauvegardeImpossible(
            f"Le dossier {destination} n'a pas pu être créé "
            f"({e.strerror or e}).") from e

    presents = [Path(f) for f in fichiers if f and Path(f).is_file()]
    # La copie la plus recente : les noms commencent par la date au format
    # AAAA-MM-JJ HHhMM, l'ordre alphabetique est donc l'ordre chronologique.
    # Une copie inachevee ne compte pas : elle ferait croire les donnees
    # deja sauvegardees.
    precedentes = sorted(d for d in destination.iterdir()
                         if d.is_dir() and _copie_complete(d.name))
    if presents and precedentes:
        derniere = precedentes[-1]
        if all((derniere / f.name).is_file()
               and _empreinte(derniere / f.name) == _empreinte(f)
               for f in presents):
            return None                 # deja sauvegarde tel quel

    cible, _ = sauvegarder(fichiers, destination, dossier_donnees, nom_appli,
                           version, maintenant, hors_des_donnees=False)
    # Le tri vient APRES la nouvelle copie verifiee : on ne retire jamais une
    # ancienne copie tant que la nouvelle n'est pas sure.
    _retirer_copies_en_trop(destination, nom_appli, corbeille)
    return cible


# ---------- rappel de sauvegarde externe (28/09/2026) ----------
# Commun aux trois applications. Chacune retient la date de sa derniere
# sauvegarde externe reussie (dans ses propres reglages) et montre ce rappel
# sur sa page d'accueil. Le texte est le meme partout.

SEUIL_RAPPEL_JOURS = 30


def rappel_sauvegarde_externe(derniere: str | None, depuis: str | None,
                              aujourd_hui: date | None = None,
                              seuil_jours: int = SEUIL_RAPPEL_JOURS
                              ) -> str | None:
    """Une phrase a afficher quand la derniere sauvegarde externe date de
    `seuil_jours` ou plus, ou None s'il n'y a rien a dire.

    `derniere` : date (AAAA-MM-JJ) de la derniere sauvegarde externe
    reussie, None s'il n'y en a jamais eu. `depuis` : date a partir de
    laquelle compter quand il n'y en a jamais eu (premiere utilisation de
    l'application) ; sans elle, on se tait plutot que de relancer un
    utilisateur qui vient d'installer l'application."""
    aujourd_hui = aujourd_hui or date.today()
    if derniere:
        try:
            jours = (aujourd_hui - date.fromisoformat(derniere[:10])).days
        except ValueError:
            return None
        if jours < seuil_jours:
            return None
        return (f"Aucune sauvegarde externe depuis {jours} jours : le bouton "
                "« 💾 Sauvegarde externe » copie vos données sur une clé USB "
                "ou un disque, à l'abri d'une panne de cet ordinateur.")
    if not depuis:
        return None
    try:
        jours = (aujourd_hui - date.fromisoformat(depuis[:10])).days
    except ValueError:
        return None
    if jours < seuil_jours:
        return None
    return ("Vos données n'ont encore jamais été copiées hors de cet "
            "ordinateur : le bouton « 💾 Sauvegarde externe » les met sur une "
            "clé USB ou un disque, à l'abri d'une panne.")
