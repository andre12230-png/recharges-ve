"""Journal des erreurs : erreurs.log, dans le dossier des données.

Avant les audits du 26/10/2026 (#22, #26), les erreurs n'étaient écrites
que par print() : dans l'exe, qui n'a pas de console, elles disparaissaient
sans laisser de trace. Elles sont désormais notées, datées, dans ce
fichier texte, qu'on peut lire avec le Bloc-notes.

Le fichier reste petit : au-delà de TAILLE_MAX, il est renommé en
erreurs.log.ancien (qui remplace le précédent) et un nouveau commence.
Il ne part jamais sur GitHub : la sauvegarde n'envoie que recharges.json
et tarifs.json.

Sans Qt, pour se tester sans fenêtre.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

NOM = "erreurs.log"
# Environ 200 Ko : des centaines d'erreurs, bien plus qu'il n'en faut.
TAILLE_MAX = 200_000


def ecrire(dossier: Path, texte: str) -> None:
    """Ajoute une ligne datée au journal du dossier. Ne lève jamais
    d'erreur : un journal impossible à écrire (dossier absent, disque
    plein) ne doit pas faire planter l'application qu'il surveille."""
    try:
        chemin = Path(dossier) / NOM
        if chemin.exists() and chemin.stat().st_size > TAILLE_MAX:
            chemin.replace(chemin.with_name(NOM + ".ancien"))
        horodatage = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
        with open(chemin, "a", encoding="utf-8") as fichier:
            fichier.write(f"{horodatage}  {texte.rstrip()}\n")
    except OSError:
        pass
