"""Fabrique l'installeur Windows : distribution/Recharges-VE-Setup-vX.Y.Z.exe.

A lancer APRES la construction de l'exe (commande PyInstaller de build.bat),
qui produit dist/Recharges-VE/. Necessite Inno Setup 6 (gratuit) :
winget install JRSoftware.InnoSetup

Ce script :

  * verifie qu'aucune donnee personnelle ne traine dans le dossier construit
    (les vraies donnees vivent juste a cote, dans dist\\ : voir
    preparer_distribution.py) ;
  * lance le compilateur d'Inno Setup sur installeur/recharges-ve.iss en lui
    passant le numero de version (APP_VERSION de constantes.py, sans le v) ;
  * affiche la taille et l'empreinte SHA-256 de l'installeur produit.

L'installeur est un complement de l'archive .zip, pas son remplacant.

    py faire_installeur.py
"""

import hashlib
import os
import shutil
import subprocess
import sys
from pathlib import Path

from constantes import APP_VERSION

RACINE = Path(__file__).parent
CONSTRUIT = RACINE / "dist" / "Recharges-VE"
RECETTE = RACINE / "installeur" / "recharges-ve.iss"
SORTIE = RACINE / "distribution"

# Donnees personnelles : si l'une d'elles se trouvait dans le dossier
# construit, a n'importe quelle profondeur, elle partirait chez un inconnu.
# La recette les exclut deja a la racine ; ce controle double la ceinture de
# bretelles et fouille aussi les sous-dossiers (_internal compris).
INTERDITS = ("recharges.json", "tarifs.json", "tarifs.json.avant", "backups")

# Les seuls .csv admis : les trois fichiers d'exemple que matplotlib embarque.
# Tout autre .csv, ou qu'il soit, peut etre un releve de borne.
EXEMPLES_CSV = "_internal/matplotlib/mpl-data/sample_data/"


def est_donnee_personnelle(relatif: str) -> bool:
    """Vrai si ce chemin (relatif au dossier de l'application, avec des /)
    designe une donnee personnelle. Sans tenir compte des majuscules, comme
    Windows. Sert aussi a relire l'archive (preparer_distribution.py)."""
    minuscule = relatif.lower()
    morceaux = minuscule.split("/")
    interdits = {nom.lower() for nom in INTERDITS}
    if any(m in interdits for m in morceaux):
        return True
    return minuscule.endswith(".csv") and not minuscule.startswith(EXEMPLES_CSV)


def chercher_donnees_personnelles(dossier: Path) -> list[str]:
    """Chemins (relatifs, avec des /) des donnees personnelles trouvees dans
    `dossier`, a toutes les profondeurs, tries. Un dossier interdit
    (backups) est signale une seule fois, sans son contenu."""
    trouves = []
    for chemin in sorted(dossier.rglob("*")):
        relatif = chemin.relative_to(dossier).as_posix()
        # Deja couvert par un dossier interdit signale plus haut ?
        if any(relatif.startswith(t + "/") for t in trouves):
            continue
        if est_donnee_personnelle(relatif):
            trouves.append(relatif)
    return sorted(trouves)


# Saisie depuis le telephone : reservee a la version privee (24/10/2026),
# jamais dans un exe distribue. Les noms des modules embarques se lisent en
# clair dans l'exe : leur presence trahit un exe construit sans les
# --exclude-module de la version publique (voir build.bat).
MODULES_PRIVES = (b"fenetre_telephone", b"telephone")


def contient_saisie_telephone(dossier: Path) -> bool:
    """Vrai si l'exe de `dossier` embarque la saisie depuis le telephone."""
    exe = dossier / "Recharges-VE.exe"
    if not exe.is_file():
        return False
    contenu = exe.read_bytes()
    return any(nom in contenu for nom in MODULES_PRIVES)


def trouver_iscc() -> str:
    """Cherche le compilateur d'Inno Setup aux endroits habituels.

    La variable d'environnement ISCC permet d'en imposer un autre."""
    candidats = [os.environ.get("ISCC", "")]
    for base in (os.environ.get("LOCALAPPDATA", "") + r"\Programs",
                 os.environ.get("ProgramFiles(x86)", ""),
                 os.environ.get("ProgramFiles", "")):
        candidats.append(os.path.join(base, "Inno Setup 6", "ISCC.exe"))
    for chemin in candidats:
        if chemin and os.path.isfile(chemin):
            return chemin
    raise SystemExit(
        "ECHEC : Inno Setup 6 est introuvable.\n"
        "Installez-le avec : winget install JRSoftware.InnoSetup")


def main() -> int:
    if not (CONSTRUIT / "Recharges-VE.exe").is_file():
        raise SystemExit(
            f"ECHEC : {CONSTRUIT}\\Recharges-VE.exe est introuvable.\n"
            "Construisez d'abord l'exe (commande de build.bat).")

    # Inno Setup veut un numero pur (1.23.0) : le « v » est remis par la
    # recette dans le nom du fichier et dans l'assistant.
    version = APP_VERSION.lstrip("v")
    print(f"Version : {APP_VERSION}")

    trouves = chercher_donnees_personnelles(CONSTRUIT)
    if trouves:
        raise SystemExit(
            "ECHEC : donnees personnelles dans le dossier construit : "
            + ", ".join(trouves))
    if contient_saisie_telephone(CONSTRUIT):
        raise SystemExit(
            "ECHEC : cet exe contient la saisie depuis le telephone, reservee "
            "a la version privee. Reconstruisez-le en version publique "
            "(build.bat public).")

    iscc = trouver_iscc()
    print(f"Inno Setup : {iscc}")
    # /Q : n'affiche que les erreurs. /D : definit AppVersion pour la recette.
    resultat = subprocess.run([iscc, "/Q", f"/DAppVersion={version}", str(RECETTE)])
    if resultat.returncode != 0:
        raise SystemExit("ECHEC : la compilation de l'installeur a echoue.")

    cible = SORTIE / f"Recharges-VE-Setup-v{version}.exe"
    if not cible.is_file():
        raise SystemExit(f"ECHEC : {cible} n'a pas ete produit.")
    # Copie a nom FIXE, celle qu'on joint a la release : le bouton « Mise a
    # jour » de l'application et le README visent
    # .../releases/latest/download/Recharges-VE-Setup.exe. Un nom numerote
    # casserait ce lien a chaque version (comme pour le Photovoltaique).
    fixe = SORTIE / "Recharges-VE-Setup.exe"
    shutil.copy2(cible, fixe)
    empreinte = hashlib.sha256(cible.read_bytes()).hexdigest()
    print()
    print(f"Installeur : {cible}")
    print(f"Nom fixe   : {fixe} (a joindre a la release)")
    print(f"Taille     : {cible.stat().st_size / (1024 * 1024):.1f} Mo")
    print(f"SHA-256    : {empreinte}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
