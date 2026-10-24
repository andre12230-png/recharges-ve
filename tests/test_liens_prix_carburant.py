"""Liens vers le prix des carburants, dans Parametres (19/10/2026).

Demande de l'auteur : que les utilisateurs trouvent ou mettre a jour le prix
du litre de la voiture essence de comparaison. Deux sites officiels de
l'Etat, aucun site prive :
- prix-carburants.gouv.fr : le prix station par station, pres de chez soi ;
- la page « Prix des produits pétroliers » du ministere : les moyennes
  nationales, pour le prix par annee.

Comme « Mise à jour » et « Votre avis », l'application confie l'adresse au
navigateur et ne se connecte elle-meme a aucun serveur. Si Windows n'ouvre
pas le navigateur, elle le dit et copie l'adresse. Aucun navigateur n'est
lance ici : l'ouverture est simulee.

    py -m pytest tests/test_liens_prix_carburant.py
"""

from __future__ import annotations

from pathlib import Path

import pytest
from PySide6.QtGui import QGuiApplication

import fenetre as module_fenetre
import liens
from pages import parametres as pa
from theme_qt import ROUGE

PROJET = Path(__file__).resolve().parent.parent


@pytest.fixture
def fenetre(qapp, monkeypatch):
    monkeypatch.setattr(module_fenetre, "charger_donnees",
                        lambda: {"recharges": []})
    f = module_fenetre.FenetrePrincipale(accueil=False)
    yield f
    f.deleteLater()


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
    faux.adresses = []
    monkeypatch.setattr(pa.QDesktopServices, "openUrl", faux)
    return faux


def test_les_deux_adresses_sont_officielles():
    assert liens.PRIX_CARBURANTS_STATIONS_URL == \
        "https://www.prix-carburants.gouv.fr/"
    assert liens.PRIX_CARBURANTS_MOYENNES_URL == (
        "https://www.ecologie.gouv.fr/politiques-publiques/"
        "prix-produits-petroliers")


def test_la_carte_essence_propose_les_deux_liens(fenetre, navigateur):
    page = pa.construire(fenetre)
    page.boutons_prix_carburant["stations"].click()
    page.boutons_prix_carburant["moyennes"].click()
    assert navigateur.adresses == [liens.PRIX_CARBURANTS_STATIONS_URL,
                                   liens.PRIX_CARBURANTS_MOYENNES_URL]
    assert page.message_essence.text().startswith("✓")


def test_navigateur_qui_ne_s_ouvre_pas_le_dit_et_copie_l_adresse(
        fenetre, navigateur):
    navigateur.resultat = False
    page = pa.construire(fenetre)
    page.boutons_prix_carburant["stations"].click()
    texte = page.message_essence.text()
    assert "pas pu" in texte
    assert liens.PRIX_CARBURANTS_STATIONS_URL in texte
    assert ROUGE in page.message_essence.styleSheet()
    assert QGuiApplication.clipboard().text() == \
        liens.PRIX_CARBURANTS_STATIONS_URL


def test_parametres_ne_se_connecte_a_rien():
    source = (PROJET / "pages" / "parametres.py").read_text(encoding="utf-8")
    for interdit in ("import urllib", "import http", "import socket",
                     "import requests", "import ssl"):
        assert interdit not in source, interdit
