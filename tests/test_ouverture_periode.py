"""Periode a l'ouverture (audit du 08/10/2026).

Charte : l'application s'ouvre sur le mois en cours ; sans donnees ce
mois-ci, sur « Toute la periode », pas sur un ecran vide (un 1er du mois, ou
pour un nouvel utilisateur). Donnees inventees.

    py -m pytest tests/test_ouverture_periode.py
"""

from __future__ import annotations

from datetime import datetime

import fenetre as module_fenetre
from filtres import mois_en_cours

MAINTENANT = datetime.now()
CE_MOIS = f"{MAINTENANT.year}-{MAINTENANT.month:02d}"
ANCIENNE = {"id": "a", "date": "2020-01-05T10:00", "lieu": "maison",
            "kwh": 7.0, "cout_eur": 1.0, "prix_kwh": 0.1429}
DU_MOIS = {"id": "b", "date": f"{CE_MOIS}-01T10:00", "lieu": "exterieur",
           "kwh": 10.0, "cout_eur": 5.0, "prix_kwh": 0.5}


def ouvrir(qapp, monkeypatch, recharges):
    monkeypatch.setattr(module_fenetre, "charger_donnees",
                        lambda: {"recharges": recharges})
    return module_fenetre.FenetrePrincipale(accueil=False)


def test_mois_en_cours_avec_des_recharges_ce_mois(qapp, monkeypatch):
    f = ouvrir(qapp, monkeypatch, [ANCIENNE, DU_MOIS])
    try:
        assert f.filtre_periode_dashboard == mois_en_cours()
        assert f.filtre_periode == mois_en_cours()
    finally:
        f.deleteLater()


def test_toute_la_periode_sans_recharge_ce_mois(qapp, monkeypatch):
    f = ouvrir(qapp, monkeypatch, [ANCIENNE])
    try:
        assert f.filtre_periode_dashboard == "Tout"
        assert f.filtre_periode == "Tout"
    finally:
        f.deleteLater()


def test_toute_la_periode_pour_un_nouvel_utilisateur(qapp, monkeypatch):
    f = ouvrir(qapp, monkeypatch, [])
    try:
        assert f.filtre_periode_dashboard == "Tout"
    finally:
        f.deleteLater()
