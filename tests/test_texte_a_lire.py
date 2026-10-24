"""Longs textes : pas plus de ~110 signes par ligne (780 px), charte des
applis. Audit de design du 03/10/2026 : la Notice et la page Importer
couraient sur toute la largeur, jusqu'a 165 signes par ligne."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QWidget

from composants import LARGEUR_TEXTE


def _paragraphes(page):
    return [e for e in page.findChildren(QLabel)
            if e.wordWrap() and len(e.text()) > 150]


def _afficher(page, largeur=1200):
    """Comme dans l'appli : la page dans une zone qui defile (sinon Qt la
    tasse dans la hauteur de la fenetre, et le test croirait a un texte
    coupe)."""
    from PySide6.QtWidgets import QApplication, QScrollArea
    zone = QScrollArea()
    zone.setWidgetResizable(True)
    zone.setWidget(page)
    zone.setAttribute(Qt.WA_DontShowOnScreen, True)
    zone.resize(largeur, 800)
    zone.show()
    for _ in range(5):
        QApplication.processEvents()
    page._zone = zone


def test_la_notice_garde_des_lignes_courtes(qapp):
    from pages import notice
    page = notice.construire(None)
    _afficher(page)
    longs = _paragraphes(page)
    assert longs
    for lbl in longs:
        assert lbl.width() <= LARGEUR_TEXTE
        # Et rien n'est coupe (piege de setMaximumWidth, charte section 6).
        assert lbl.height() >= lbl.heightForWidth(lbl.width())
    page._zone.deleteLater()


def test_la_page_importer_garde_des_lignes_courtes(qapp, monkeypatch):
    from pages import importer

    class Fenetre(QWidget):
        pass
    page = importer.construire(Fenetre())
    _afficher(page)
    longs = _paragraphes(page)
    assert longs
    assert all(lbl.width() <= LARGEUR_TEXTE for lbl in longs)
    page._zone.deleteLater()
