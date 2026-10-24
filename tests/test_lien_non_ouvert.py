"""Un lien que Windows n'a pas pu ouvrir n'est plus annonce comme ouvert
(second audit du 16/10/2026, constat A8).

Defaut d'origine : « Mise à jour » et « Votre avis » affichaient « ✓ Page
ouverte dans votre navigateur » sans regarder si Windows avait vraiment
ouvert le navigateur. Desormais, en cas d'echec, la fenetre le dit et donne
l'adresse, copiee pour etre collee dans le navigateur. Meme chose pour
« Ouvrir le dossier » dans Parametres.

Aucun navigateur n'est lance : l'ouverture est simulee.

    py -m pytest tests/test_lien_non_ouvert.py
"""

from __future__ import annotations

import pytest
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QPushButton

import fenetres_aide as fa
from liens import PAGE_VERSIONS_URL


def _bouton(fenetre, debut: str) -> QPushButton:
    return next(b for b in fenetre.findChildren(QPushButton)
                if b.text().startswith(debut))


@pytest.fixture
def navigateur(monkeypatch):
    """Ouverture simulee : `resultat` dit si Windows a reussi."""
    class Faux:
        resultat = True
        adresses: list[str] = []

        def __call__(self, url):
            self.adresses.append(url.toString())
            return self.resultat
    faux = Faux()
    monkeypatch.setattr(fa.QDesktopServices, "openUrl", faux)
    return faux


def test_echec_d_ouverture_dit_l_echec_et_donne_l_adresse(qapp, navigateur):
    navigateur.resultat = False
    f = fa.FenetreMiseAJour()
    _bouton(f, "🌐").click()
    texte = f.confirmation.text()
    assert "ouverte" not in texte.lower()
    assert "pas pu" in texte
    assert PAGE_VERSIONS_URL in texte
    # L'adresse est copiee, prete a coller dans le navigateur.
    assert QGuiApplication.clipboard().text() == PAGE_VERSIONS_URL


def test_ouverture_reussie_confirme_comme_avant(qapp, navigateur):
    navigateur.resultat = True
    f = fa.FenetreMiseAJour()
    _bouton(f, "🌐").click()
    assert f.confirmation.text().startswith("✓")
    assert navigateur.adresses[-1] == PAGE_VERSIONS_URL


def test_dossier_des_donnees_qui_ne_s_ouvre_pas_le_dit(
        qapp, monkeypatch, tmp_path):
    from pages import parametres as pa
    import fenetre as module_fenetre
    monkeypatch.setattr(pa, "dossier_donnees", lambda: tmp_path)
    monkeypatch.setattr(pa.QDesktopServices, "openUrl", lambda url: False)
    avertissements = []
    monkeypatch.setattr(pa.QMessageBox, "warning",
                        lambda parent, titre, texte, *a, **k:
                        avertissements.append(texte))
    f = module_fenetre.FenetrePrincipale(accueil=False)
    page = pa.construire(f)
    page.bouton_ouvrir_dossier.click()
    assert len(avertissements) == 1
    assert str(tmp_path) in avertissements[0]
    f.deleteLater()
