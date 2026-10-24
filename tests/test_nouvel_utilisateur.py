"""Le parcours d'un nouvel utilisateur (analyse du 19/10/2026).

Import d'un historique plus ancien que le tarif : le premier tarif est
propose au 01/01 de l'annee en cours, et l'export d'une borne remonte
souvent plus loin. L'import s'arretait a la premiere recharge sans tarif
avec « Aucun tarif défini pour le … Vérifiez la date saisie », formule de
la saisie a la main : l'utilisateur ne savait ni quelles dates manquaient,
ni quoi changer. Il doit apprendre la periode en cause et la marche a
suivre ; rien n'est enregistre tant que tout le fichier n'est pas couvert.

Toutes les donnees sont inventees, dans un dossier temporaire.

    py -m pytest tests/test_nouvel_utilisateur.py
"""

import json
import os
import sys
import tempfile
from pathlib import Path

import pytest

os.environ.setdefault("RECHARGES_DATA_DIR",
                      tempfile.mkdtemp(prefix="recharges_nouvel_util_"))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import recharges as r  # noqa: E402

ENTETE_CSV = ("NS du chargeur,Heure de debut,Heure de fin,Consommation,"
              "Duree,Cout")


def ecrire(chemin: Path, contenu) -> None:
    chemin.parent.mkdir(parents=True, exist_ok=True)
    chemin.write_text(json.dumps(contenu, ensure_ascii=False),
                      encoding="utf-8")


@pytest.fixture
def dossier(tmp_path, monkeypatch):
    """Un dossier neuf, avec le tarif d'un nouvel utilisateur : il commence
    au 01/01/2026, la date proposee par la fenetre du premier tarif."""
    ancien = r.BASE
    r.rediriger_donnees(tmp_path)
    monkeypatch.setattr(r, "DERNIERE_RESTAURATION", None)
    monkeypatch.setattr(r, "ECHEC_BACKUP", None, raising=False)
    ecrire(tmp_path / "tarifs.json", {
        "correction_csv_minutes": 0,
        "tarifs": [{"id": "t", "nom": "Mon contrat", "type": "simple",
                    "debut": "2026-01-01", "fin": None, "prix_kwh": 0.20,
                    "abonnement_mensuel": 10.0}]})
    r.vider_cache()
    yield tmp_path
    r.rediriger_donnees(ancien)


def ecrire_csv(dossier: Path, lignes: list[str]) -> Path:
    chemin = dossier / "borne.csv"
    chemin.write_text(chr(13).join([ENTETE_CSV] + lignes), encoding="utf-8")
    return chemin


HISTORIQUE = [
    "WB-0001,2025-11-02 22:00:00,2025-11-03 04:00:00,30.000kWh,06h00min,6.00€",
    "WB-0001,2025-12-10 22:00:00,2025-12-11 02:00:00,20.000kWh,04h00min,4.00€",
    "WB-0001,2026-02-02 22:00:00,2026-02-03 04:00:00,30.000kWh,06h00min,6.00€",
]


def test_import_avant_le_tarif_dit_les_dates_et_quoi_faire(dossier):
    with pytest.raises(ValueError) as erreur:
        r.importer_csv_maison(ecrire_csv(dossier, HISTORIQUE))
    message = str(erreur.value)
    # Pas la formule de la saisie a la main : rien n'a ete « saisi ».
    assert "date saisie" not in message
    # Les deux recharges sans tarif, de la premiere a la derniere.
    assert "2 recharges" in message
    assert "02/11/2025" in message and "10/12/2025" in message
    # Ce qu'il faut faire : avancer le debut du tarif, puis reimporter.
    assert "01/01/2026" in message
    assert "« Tarifs »" in message
    assert "ou avant" in message
    assert "NE LE SUPPRIMEZ PAS" in message


def test_import_avant_le_tarif_n_enregistre_rien(dossier):
    """Tout ou rien : meme la recharge de 2026, couverte par le tarif,
    attend que tout le fichier le soit (sinon un second import, apres
    correction du tarif, melangerait des recharges deja la et des neuves)."""
    with pytest.raises(ValueError):
        r.importer_csv_maison(ecrire_csv(dossier, HISTORIQUE))
    assert not (dossier / "recharges.json").exists() \
        or r.charger_donnees()["recharges"] == []


def test_apres_avoir_avance_le_tarif_tout_s_importe(dossier):
    tarifs = json.loads((dossier / "tarifs.json").read_text("utf-8"))
    tarifs["tarifs"][0]["debut"] = "2025-11-01"
    ecrire(dossier / "tarifs.json", tarifs)
    r.vider_cache()
    bilan = r.importer_csv_maison(ecrire_csv(dossier, HISTORIQUE))
    assert bilan["ajoutes"] == 3


def test_avertissements_de_la_grille_accentues():
    """Messages affiches apres l'enregistrement d'un tarif : ils etaient
    ecrits sans accents (« Donnez une date de fin a », « imprevisible »,
    « refusees »)."""
    ouvert = {"nom": "A", "debut": "2025-01-01", "fin": None}
    suivant = {"nom": "B", "debut": "2026-01-01", "fin": None}
    chevauche = [{"nom": "A", "debut": "2025-01-01", "fin": "2025-12-31"},
                 {"nom": "B", "debut": "2025-06-01", "fin": None}]
    troue = [{"nom": "A", "debut": "2025-01-01", "fin": "2025-03-31"},
             {"nom": "B", "debut": "2025-06-01", "fin": None}]
    textes = " ".join(r._avertissements_grille([ouvert, suivant])
                      + r._avertissements_grille(chevauche)
                      + r._avertissements_grille(troue))
    assert "Donnez une date de fin à « A »" in textes
    assert "le tarif appliqué serait imprévisible" in textes
    assert "seront refusées" in textes


def test_fenetre_du_tarif_demande_des_prix_ttc(qapp):
    """La facture donne le HT et le TTC : sans precision, recopier le HT
    sous-estimait tous les couts sans que rien ne le signale (19/10/2026)."""
    from PySide6.QtWidgets import QLabel
    import dialogue_tarif as dt
    d = dt.DialogueTarif(None, None)
    textes = [w.text() for w in d.findChildren(QLabel)]
    for debut in ("Prix du kWh", "Prix en heures PLEINES",
                  "Prix en heures CREUSES", "Abonnement mensuel"):
        libelle = next(t for t in textes if t.startswith(debut))
        assert "TTC" in libelle, libelle
    assert any("taxes comprises" in t for t in textes)
    d.deleteLater()


def test_page_restaurer_zero_recharge_au_singulier(dossier):
    from pages.restaurer import recharges_actuelles
    assert recharges_actuelles() == "0 recharge"


def test_une_seule_recharge_sans_tarif_au_singulier(dossier):
    with pytest.raises(ValueError) as erreur:
        r.importer_csv_maison(ecrire_csv(dossier, HISTORIQUE[:1]))
    message = str(erreur.value)
    assert "1 recharge " in message and "1 recharges" not in message
    assert "02/11/2025" in message
