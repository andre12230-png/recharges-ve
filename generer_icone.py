"""Genere icone_voiture.ico (pour le .exe et la fenetre) et icone_voiture.png
a partir du dessin icone_voiture.svg.

Le dessin est un fichier SVG (vectoriel) : il se retouche dans un editeur de
texte ou un logiciel de dessin, et reste net a toutes les tailles. Chaque
taille de l'icone Windows est DESSINEE a sa taille a partir du SVG, et non
reduite depuis la grande image : en 16 et 24 pixels, une reduction rend
flous les traits fins (le cable, l'eclair).

Nouveau dessin le 25/09/2026 (medaillon vert -> bleu, voiture vue de face,
eclair, cable et prise), a la demande de l'auteur ; l'ancien (voiture sur disque
orange) etait dessine point par point ici meme.

    py generer_icone.py
"""

import sys
from pathlib import Path

from PIL import Image
from PySide6.QtCore import QBuffer, QByteArray, QIODevice, Qt
from PySide6.QtGui import QGuiApplication, QImage, QPainter
from PySide6.QtSvg import QSvgRenderer

DOSSIER = Path(__file__).resolve().parent
SOURCE = DOSSIER / "icone_voiture.svg"
TAILLES = (256, 128, 64, 48, 32, 24, 16)


def dessiner(rendu: QSvgRenderer, taille: int) -> Image.Image:
    """Le dessin a `taille` pixels de cote, fond transparent, en image PIL."""
    image = QImage(taille, taille, QImage.Format_ARGB32)
    image.fill(Qt.transparent)
    peintre = QPainter(image)
    peintre.setRenderHint(QPainter.Antialiasing)
    peintre.setRenderHint(QPainter.SmoothPixmapTransform)
    rendu.render(peintre)
    peintre.end()
    # Passage par un PNG en memoire : le moyen le plus simple et le plus sur
    # de donner l'image Qt a PIL, qui sait ecrire un .ico multi-tailles.
    octets = QByteArray()
    tampon = QBuffer(octets)
    tampon.open(QIODevice.WriteOnly)
    image.save(tampon, "PNG")
    tampon.close()
    from io import BytesIO
    return Image.open(BytesIO(bytes(octets))).convert("RGBA")


def main() -> int:
    application = QGuiApplication.instance() or QGuiApplication(sys.argv)
    rendu = QSvgRenderer(str(SOURCE))
    if not rendu.isValid():
        print(f"Dessin illisible : {SOURCE}")
        return 1
    images = [dessiner(rendu, t) for t in TAILLES]

    images[0].save(DOSSIER / "icone_voiture.png")
    print("icone_voiture.png genere (256 x 256)")

    # Le .ico porte chaque taille dessinee a part (append_images).
    images[0].save(DOSSIER / "icone_voiture.ico", format="ICO",
                   sizes=[(t, t) for t in TAILLES],
                   append_images=images[1:])
    print("icone_voiture.ico genere : " + ", ".join(str(t) for t in TAILLES))
    del application
    return 0


if __name__ == "__main__":
    sys.exit(main())
