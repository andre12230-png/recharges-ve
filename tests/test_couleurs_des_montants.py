"""Une couleur dit un sens (choix de l'auteur du 08/10/2026, audit de design).

Couts, prix et energie sont neutres, en bleu nuit : ni le vert d'une
bonne nouvelle, ni l'orange d'une alerte. Le vert est garde a ce qui est
favorable (l'economie face a l'essence), le rouge a ce qui ne l'est pas (un
surcout). Avant : cout Maison en vert, Exterieur en orange, energie en vert,
economie en brun. Donnees inventees.

    py -m pytest tests/test_couleurs_des_montants.py
"""

from __future__ import annotations

from PySide6.QtWidgets import QFrame, QLabel

import fenetre as module_fenetre
from pages import kilometrage as km
from pages import tableau_de_bord as tdb
from theme_qt import BLEU_NUIT, ROUGE, VERT

RECHARGES = [
    {"id": "a", "date": "2026-01-10T23:00", "fin": "2026-01-11T03:00",
     "lieu": "maison", "kwh": 20.0, "kwh_hc": 20.0, "cout_eur": 3.0,
     "prix_kwh": 0.15},
    {"id": "b", "date": "2026-01-12T12:00", "lieu": "exterieur",
     "kwh": 10.0, "cout_eur": 5.0, "prix_kwh": 0.5},
]


def couleurs_des_tuiles(widget) -> dict[str, str]:
    return {t.findChildren(QLabel)[0].text(): t._valeur.styleSheet()
            for t in widget.findChildren(QFrame)
            if t.objectName() == "TuileKpi"}


def test_tableau_de_bord_neutre(qapp, monkeypatch):
    monkeypatch.setattr(tdb, "charger_donnees", lambda: {"recharges": RECHARGES})
    monkeypatch.setattr(module_fenetre, "charger_donnees",
                        lambda: {"recharges": RECHARGES})
    f = module_fenetre.FenetrePrincipale()
    try:
        f.filtre_periode_dashboard = "Tout"
        page = tdb.construire(f)
        for libelle, style in couleurs_des_tuiles(page).items():
            assert BLEU_NUIT in style, libelle
        grands = [e for e in page.findChildren(QLabel)
                  if e.objectName() == "GrandeValeur"]
        assert grands and all(BLEU_NUIT in e.styleSheet() for e in grands)
    finally:
        f.deleteLater()


def test_economie_en_vert_surcout_en_rouge(qapp):
    base = {"km": 1000.0, "litres": 55.0, "cout_essence": 99.0,
            "cout_electrique": 30.0, "economie": 69.0, "debut": "2026-01-01",
            "fin": "2026-03-01", "conso_essence": 5.5, "prix_essence": 1.8,
            "cout_100_essence": 9.9, "cout_100_electrique": 3.0,
            "part_non_enregistree": 0.0, "par_annee": []}
    couleurs = couleurs_des_tuiles(km._carte_essence(base))
    assert BLEU_NUIT in couleurs["EN ÉLECTRICITÉ"]
    assert VERT in couleurs["ÉCONOMIE"]
    couleurs = couleurs_des_tuiles(km._carte_essence(
        dict(base, cout_electrique=120.0, economie=-21.0)))
    assert ROUGE in couleurs["SURCOÛT"]
