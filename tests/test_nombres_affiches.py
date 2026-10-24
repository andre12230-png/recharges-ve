"""Nombres affiches : milliers separes, virgule decimale, accents, et
l'export PDF/Excel a espaces insecables (08/10/2026).

- Page Kilometrage : « environ 2105 kWh » s'ecrivait sans separateur.
- Energie invraisemblable : « 85.00 kWh depasse ... pris a la prise » —
  point decimal et mots sans accents.
- Releves du compteur : « 73000 km » sans separateur.
- Export : « 1 234,50 EUR » a l'espace ordinaire, coupable en fin de ligne.
"""

from __future__ import annotations

import pytest

import export
import recharges as r
from pages import kilometrage as km

NBSP = "\xa0"

CONTROLE = {"conso_reference": 15.9, "kwh_batterie": 2105.3,
            "kwh_attendu": 2339.2, "rendement": 0.9, "ecart_kwh": -1250.4,
            "ecart_pct": -33.5, "conso_enregistree": 10.6, "marge_kwh": 1071.0,
            "capacite_batterie": 64.0}


def test_le_controle_du_kilometrage_separe_les_milliers():
    t = km.textes_controle(dict(CONTROLE, verdict="energie_exterieure"))
    assert f"environ 2{NBSP}105{NBSP}kWh à la batterie" in t["detail"]
    assert f"environ 2{NBSP}339{NBSP}kWh pris à la prise" in t["detail"]
    assert t["verdict"].startswith(f"Environ 1{NBSP}250{NBSP}kWh")
    t = km.textes_controle(dict(CONTROLE, verdict="trop_court"))
    assert f"(-1{NBSP}250{NBSP}kWh)" in t["verdict"]
    assert f"soit 1{NBSP}071{NBSP}kWh pris à la prise" in t["verdict"]
    t = km.textes_controle(dict(CONTROLE, verdict="excedent",
                                ecart_kwh=1250.4, ecart_pct=33.5))
    assert f"dépassent de +1{NBSP}250{NBSP}kWh" in t["verdict"]


def test_energie_invraisemblable_en_francais(monkeypatch):
    monkeypatch.setattr(r, "charger_config", lambda: {
        "capacite_batterie": 64.0, "rendement_charge": 0.9})
    texte = r.energie_invraisemblable(1085.0)
    assert texte.startswith(f"1{NBSP}085,00{NBSP}kWh dépasse ce que")
    assert f"64,0{NBSP}kWh, soit 71,1{NBSP}kWh pris à la prise" in texte
    assert "." not in texte.rstrip(".")


def test_les_releves_du_compteur_separent_les_milliers():
    premier = r.ajouter_releve_km(73000, "2026-09-01T08:00")
    try:
        with pytest.raises(ValueError, match=f"73{NBSP}000{NBSP}km"):
            r.ajouter_releve_km(72000, "2026-09-10T08:00")
        with pytest.raises(ValueError, match=f"73{NBSP}000{NBSP}km"):
            r.ajouter_releve_km(73000, "2026-09-01T08:00")
    finally:
        r.supprimer_releve_km(premier["id"])


def test_l_export_ecrit_ses_nombres_a_l_espace_insecable():
    assert export._fr(1234.5) == f"1{NBSP}234,50"
    assert export._fr(13073, 0) == f"13{NBSP}073"


def test_le_pdf_ne_coupe_pas_un_montant():
    """ReportLab respecte l'espace insecable : une colonne trop etroite
    pour la phrase coupe ailleurs, jamais au milieu du montant."""
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.platypus import Paragraph
    texte = f"Abonnement : {export._fr(1234.5)}{NBSP}EUR sur la période."
    para = Paragraph(texte, getSampleStyleSheet()["Normal"])
    para.wrap(70, 500)
    lignes = [" ".join(mot for mot in ligne[1]) if isinstance(ligne, tuple)
              else str(ligne) for ligne in para.blPara.lines]
    assert any(f"1{NBSP}234,50{NBSP}EUR" in ligne for ligne in lignes), lignes


def test_l_en_tete_de_l_export_dit_toute_la_periode():
    """L'en-tete du PDF et de l'Excel reprend le nom affiche a l'ecran,
    pas la valeur interne « Tout » (08/10/2026)."""
    from pages import exporter as ex
    assert ex.libelle_export("Tout", "Tout") == "Tous les lieux · Toute la période"
    assert ex.libelle_export("Maison", "2025") == "Maison · 2025"
