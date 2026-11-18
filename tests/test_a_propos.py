"""Fenetre « À propos de Recharges VE » (18/11/2026).

Ouverte par un clic sur le numero de version, en bas du bandeau de gauche :
un lien discret, qui ne change pas la taille du bandeau. Meme fenetre que
dans Pecule et le Photovoltaique. Tout se passe hors ecran, sur le dossier de
donnees temporaire de tests/conftest.py.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from PySide6.QtCore import QEvent, QPoint, Qt
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import QLabel, QToolTip

import fenetre as module_fenetre
import liens
from constantes import APP_NAME, APP_VERSION, COPYRIGHT_TITULAIRE
from fenetres_aide import FenetreAPropos

RACINE = Path(__file__).resolve().parent.parent


def _texte(fen) -> str:
    return "\n".join(e.text() for e in fen.findChildren(QLabel))


@pytest.fixture
def fenetre(qapp):
    f = module_fenetre.FenetrePrincipale()
    f.afficher_vue("dashboard")
    yield f
    f.deleteLater()


def _etiquette_version(fenetre):
    trouvees = [e for e in fenetre.findChildren(QLabel)
                if e.objectName() == "Version"]
    assert len(trouvees) == 1
    return trouvees[0]


def test_la_fenetre_donne_version_licence_et_depot(qapp):
    texte = _texte(FenetreAPropos())
    assert APP_VERSION in texte
    assert "MIT" in texte
    assert "aucune garantie" in texte
    # L'application ne se connecte a rien : la fenetre le rappelle.
    assert "ne se connecte" in texte
    assert liens.DEPOT_URL.startswith("https://github.com/andre12230-png/")


def test_le_copyright_reprend_le_fichier_licence(qapp):
    """Une seule source : le nom affiche est celui du fichier LICENSE."""
    licence = (RACINE / "LICENSE").read_text(encoding="utf-8")
    ligne = next(x for x in licence.splitlines() if x.startswith("Copyright"))
    assert ligne.replace("Copyright (c)", "").strip() == COPYRIGHT_TITULAIRE
    assert COPYRIGHT_TITULAIRE in _texte(FenetreAPropos())


def test_le_bouton_du_depot_ouvre_la_page_du_projet(qapp, monkeypatch):
    import fenetres_aide
    ouvertes = []
    monkeypatch.setattr(fenetres_aide.QDesktopServices, "openUrl",
                        lambda url: ouvertes.append(url.toString()) or True)
    fen = FenetreAPropos()
    fen.btn_depot.click()
    assert ouvertes == [liens.DEPOT_URL]


def test_clic_sur_la_version_ouvre_a_propos(fenetre, monkeypatch):
    ouvertures = []
    monkeypatch.setattr(FenetreAPropos, "exec",
                        lambda self: ouvertures.append(self) or 0)
    etiquette = _etiquette_version(fenetre)
    assert etiquette.text() == APP_VERSION
    clic = QMouseEvent(QEvent.MouseButtonPress, QPoint(2, 2),
                       Qt.LeftButton, Qt.LeftButton, Qt.NoModifier)
    etiquette.mousePressEvent(clic)
    assert len(ouvertures) == 1
    assert f"{APP_NAME}" in ouvertures[0].windowTitle()


def test_la_version_annonce_son_role(fenetre):
    etiquette = _etiquette_version(fenetre)
    assert "propos" in etiquette.toolTip()
    assert etiquette.cursor().shape() == Qt.PointingHandCursor


def test_l_infobulle_du_numero_reste_lisible(qapp, fenetre):
    """Une infobulle recoit les regles de style du widget qui la montre : on
    la rend et on mesure son texte le plus fonce (sur le fond jaune pale)."""
    from collections import Counter

    etiquette = _etiquette_version(fenetre)
    fenetre.show()
    bulle = None
    for _ in range(20):
        QToolTip.showText(etiquette.mapToGlobal(QPoint(5, 5)),
                          etiquette.toolTip(), etiquette)
        qapp.processEvents()
        bulle = next((w for w in qapp.topLevelWidgets()
                      if w.metaObject().className() == "QTipLabel"
                      and w.isVisible()), None)
        if bulle is not None:
            break
    assert bulle is not None, "infobulle jamais affichee"
    image = bulle.grab().toImage()
    QToolTip.hideText()
    pixels = [image.pixelColor(x, y) for x in range(image.width())
              for y in range(image.height())]
    fond = Counter(c.name() for c in pixels).most_common(1)[0][0]
    assert fond == "#ffffdc", fond
    plus_fonce = min(max(c.red(), c.green(), c.blue()) for c in pixels)
    assert plus_fonce <= 60, plus_fonce
