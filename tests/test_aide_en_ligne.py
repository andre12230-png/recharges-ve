"""Boutons « Mise à jour » et « Votre avis », repris de Pecule et du
Photovoltaique (15/09/2026).

Les deux passent par le navigateur : l'application elle-meme ne se connecte
a aucun serveur pour eux.
"""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

import pytest

os.environ.setdefault("RECHARGES_DATA_DIR",
                      tempfile.mkdtemp(prefix="recharges_aide_"))
PROJET = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJET))

import liens  # noqa: E402
from constantes import APP_VERSION  # noqa: E402


def test_les_liens_visent_la_derniere_version_publiee():
    racine = "https://github.com/andre12230-png/recharges-ve/releases/latest"
    assert liens.PAGE_VERSIONS_URL == racine
    # Nom FIXE de l'installeur : un nom numerote casserait le lien a chaque
    # version (voir le Photovoltaique).
    assert liens.INSTALLEUR_URL == racine + "/download/Recharges-VE-Setup.exe"


def test_la_version_copiee_nomme_l_application():
    assert liens.description_systeme().startswith(f"Recharges VE {APP_VERSION} — ")


def test_le_questionnaire_a_un_lien():
    """Le questionnaire existe depuis le 15/09/2026 : sans lien, le bouton
    « Ouvrir le questionnaire » serait grise."""
    assert liens.FORMULAIRE_AVIS_URL.startswith("https://forms.cloud.microsoft/")


@pytest.mark.parametrize("module", ["liens.py", "fenetres_aide.py"])
def test_aucun_acces_reseau(module):
    source = (PROJET / module).read_text(encoding="utf-8")
    for interdit in ("import urllib", "import http", "import socket",
                     "import requests", "import ssl"):
        assert interdit not in source, f"{module} : {interdit}"


def test_les_deux_boutons_sont_dans_le_menu():
    """Ils ne sont pas des pages (pas dans menu.SECTIONS) : on verifie qu'ils
    sont bien crees avec le menu, dans la section AIDE."""
    source = (PROJET / "fenetre.py").read_text(encoding="utf-8")
    assert "🔄 Mise à jour" in source
    assert "💬 Votre avis" in source
