"""Fabrique l'archive a donner : l'application, sans les donnees de personne.

Le dossier `dist\\` melange deux choses tres differentes :

- `dist\\Recharges-VE\\` : l'application elle-meme, fabriquee par build.bat ;
- `dist\\recharges.json`, `dist\\tarifs.json`, `dist\\backups\\`, `dist\\*.csv` :
  les donnees de celui qui s'en sert.

Copier `dist\\` en entier pour le donner a quelqu'un, c'est lui remettre son
historique de recharges, sa grille tarifaire, la capacite de sa batterie et
la derive d'horloge de SA wallbox. Ce script ne prend que l'application, et
y joint le mode d'emploi et la licence.

    py preparer_distribution.py

Le resultat : `distribution\\Recharges-VE-X.Y.Z-win64.zip`, pret a etre envoye.
Meme nom que les archives de Pecule et du Photovoltaique (numero sans le
« v », suivi de « -win64 ») : les trois pages de versions se ressemblent.
"""

import sys
import zipfile
from pathlib import Path

from constantes import APP_VERSION
from faire_installeur import (chercher_donnees_personnelles,
                              contient_saisie_telephone, est_donnee_personnelle)

RACINE = Path(__file__).parent
APPLICATION = RACINE / "dist" / "Recharges-VE"
SORTIE = RACINE / "distribution"

# Joints a l'archive, a cote de l'application.
DOCUMENTS = ["README.md", "LICENSE"]

# Ce qui ne doit JAMAIS partir : des donnees personnelles. La regle est
# dans faire_installeur.py (est_donnee_personnelle), commune a l'installeur
# et a l'archive. La verification finale relit l'archive pour s'en assurer —
# une faute d'inattention ici se paierait en donnees privees envoyees a un
# inconnu. Depuis le 15/10/2026, elle fouille aussi _internal : seuls les
# trois .csv d'exemple de matplotlib y sont admis.
DOSSIER = "Recharges-VE/"


def verifier_archive(archive: Path) -> list[str]:
    """Relit l'archive et renvoie la liste des fichiers suspects."""
    suspects = []
    with zipfile.ZipFile(archive) as z:
        for nom in z.namelist():
            chemin = nom.replace("\\", "/")
            # Chemin vu depuis le dossier de l'application ; README.md et
            # LICENSE, a cote, sont juges sur leur nom tel quel.
            relatif = chemin[len(DOSSIER):] if chemin.startswith(DOSSIER) else chemin
            if est_donnee_personnelle(relatif):
                suspects.append(nom)
    return suspects


def main() -> int:
    if not APPLICATION.is_dir():
        print(f"ECHEC : {APPLICATION} est introuvable.")
        print("Lancez build.bat d'abord.")
        return 1

    # Avant meme d'ecrire l'archive : le dossier de l'application, fouille
    # a toutes les profondeurs.
    trouves = chercher_donnees_personnelles(APPLICATION)
    if trouves:
        print("ECHEC : donnees personnelles dans le dossier construit :")
        for t in trouves:
            print(f"  {t}")
        return 1
    if contient_saisie_telephone(APPLICATION):
        print("ECHEC : cet exe contient la saisie depuis le telephone, reservee")
        print("a la version privee. Reconstruisez-le en version publique")
        print("(build.bat public).")
        return 1

    SORTIE.mkdir(exist_ok=True)
    archive = SORTIE / f"Recharges-VE-{APP_VERSION.lstrip('v')}-win64.zip"
    archive.unlink(missing_ok=True)

    n = 0
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as z:
        # L'application, telle quelle. Elle se retrouve a la racine de
        # l'archive : une fois decompressee, aucun fichier de donnees ne
        # l'entoure, et l'application ecrira donc dans le dossier personnel
        # de l'utilisateur (%LOCALAPPDATA%) plutot qu'a cote d'elle.
        for fichier in sorted(APPLICATION.rglob("*")):
            if fichier.is_file():
                z.write(fichier, Path("Recharges-VE") / fichier.relative_to(APPLICATION))
                n += 1
        for nom in DOCUMENTS:
            source = RACINE / nom
            if source.exists():
                z.write(source, nom)
                n += 1

    suspects = verifier_archive(archive)
    if suspects:
        archive.unlink(missing_ok=True)
        print("ECHEC : des donnees personnelles ont failli partir.")
        for s in suspects:
            print(f"  {s}")
        print("L'archive a ete supprimee.")
        return 1

    taille = archive.stat().st_size / (1024 * 1024)
    print(f"Archive prete : {archive}")
    print(f"{n} fichiers, {taille:.1f} Mo — aucune donnee personnelle.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
