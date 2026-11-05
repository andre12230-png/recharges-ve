"""Contrôle du français du 05/11/2026 (écarts I1 à I3, R1 à R6, O1).

I1 : la fenêtre « Recharges à vérifier » disait « Choisissez pour chacune »
     même pour une seule recharge.
I2 : le compte rendu d'import parlait toujours de « ces recharges », même
     pour une seule.
I3 : la même fenêtre disait « Votre saisie », puis « Remplacer ma saisie ».
R1 à R6 : le README (règle d'import d'avant la 2.2.32, « wallbox » au lieu
     de « borne », « au 100 km », « + », « thème clair », nombre de tests).
O1 : les messages des outils de construction sans accents.

Données inventées.

    py -m pytest tests/test_francais_2026_11_05.py
"""

from __future__ import annotations

import re
from pathlib import Path

from PySide6.QtWidgets import QLabel

RACINE = Path(__file__).resolve().parent.parent


def _cas(n_cas: int, n_saisies: int = 1) -> list[dict]:
    """`n_cas` lignes du fichier douteuses, chacune avec `n_saisies`
    saisies à la main qui lui ressemblent (valeurs inventées)."""
    cas = []
    for i in range(n_cas):
        jour = f"2026-03-{i + 1:02d}"
        cas.append({
            "cle": f"k{i}",
            "fichier": {"date": f"{jour}T11:30", "fin": f"{jour}T11:45",
                        "kwh": 1.05},
            "saisies": [{"id": f"s{i}-{j}", "date": f"{jour}T1{j}:00",
                         "fin": f"{jour}T1{j}:15", "kwh": 1.0}
                        for j in range(n_saisies)]})
    return cas


def _textes_fenetre(cas) -> str:
    from dialogue_rapprochements import DialogueRapprochements
    fenetre = DialogueRapprochements(None, cas)
    return " ".join(e.text() for e in fenetre.findChildren(QLabel))


def _choix_fenetre(cas) -> list[str]:
    from dialogue_rapprochements import DialogueRapprochements
    fenetre = DialogueRapprochements(None, cas)
    return [liste.itemText(i) for liste in fenetre.choix
            for i in range(liste.count())]


# ---------- I1 : « pour chacune » seulement s'il y en a plusieurs ----------

def test_une_seule_recharge_pas_de_pour_chacune(qapp):
    textes = _textes_fenetre(_cas(1))
    assert "pour chacune" not in textes
    assert "Choisissez ce qu'il faut en faire" in textes


def test_plusieurs_recharges_pour_chacune(qapp):
    textes = _textes_fenetre(_cas(2))
    assert "Choisissez pour chacune" in textes
    assert "supprimer les doublons ensuite" in textes


def test_une_seule_recharge_le_doublon(qapp):
    assert "supprimer le doublon ensuite" in _textes_fenetre(_cas(1))


# ---------- I2 : compte rendu accordé ----------

def _bilan(cas) -> dict:
    return {"ajoutes": len(cas), "remplaces": 0, "doublons": 0,
            "zero_kwh": 0, "total_lus": len(cas), "a_verifier": cas}


def test_compte_rendu_d_un_seul_doublon_possible():
    from pages.importer import texte_resultat
    texte, alerte = texte_resultat(_bilan(_cas(1)))
    assert alerte
    assert ("cette recharge du fichier ressemble à une saisie à la main ; "
            "les deux sont gardées") in texte
    assert "ces recharges" not in texte
    assert "• 01/03/2026 11:30" in texte          # la ligne reste listée


def test_compte_rendu_de_plusieurs_doublons_possibles():
    from pages.importer import texte_resultat
    texte, _alerte = texte_resultat(_bilan(_cas(2)))
    assert ("ces recharges du fichier ressemblent à des saisies à la "
            "main") in texte
    assert "les deux sont gardées" not in texte
    assert "Supprimez les doublons" in texte
    assert "• 01/03/2026 11:30" in texte and "• 02/03/2026 11:30" in texte


# ---------- I3 : une seule personne dans la fenêtre ----------

def test_la_fenetre_ne_dit_pas_ma_saisie(qapp):
    choix = _choix_fenetre(_cas(1)) + _choix_fenetre(_cas(1, n_saisies=2))
    assert not any("ma saisie" in c for c in choix)
    assert "Remplacer la saisie par la ligne du fichier" in choix
    assert any(c.startswith("Remplacer la saisie du 01/03/2026 10:00")
               for c in choix)


# ---------- R1 à R6 : le README ----------

def _readme() -> str:
    return (RACINE / "README.md").read_text(encoding="utf-8")


def test_readme_decrit_la_regle_d_import_actuelle():
    texte = _readme()
    assert "moins de 2 h d'écart" not in texte
    assert "Recharges à vérifier" in texte


def test_readme_dit_borne_et_non_wallbox():
    # Seule exception : « (wallbox) », pour qui connaît ce mot.
    restes = re.findall(r"wallbox", _readme().replace("(wallbox)", ""))
    assert restes == []


def test_readme_cout_aux_100_km():
    assert "au 100 km" not in _readme()


def test_readme_sans_plus_dans_une_phrase():
    assert "tableau détaillé + synthèse" not in _readme()


def test_readme_le_theme_controle_n_est_pas_forcement_clair():
    assert "le thème clair et la traduction" not in _readme()


def test_readme_sans_nombre_de_tests_perime():
    assert "Plus de 800 tests" not in _readme()


# ---------- O1 : outils de construction accentués ----------

def test_outils_de_construction_accentues():
    for nom in ("faire_installeur.py", "preparer_distribution.py"):
        source = (RACINE / nom).read_text(encoding="utf-8")
        # Les messages affichés seulement (les commentaires du code
        # restent sans accents, comme ailleurs dans ces fichiers).
        for faute in ('"ECHEC', 'f"ECHEC', "Mo — aucune donnee",
                      "a ete supprimee", "Archive prete"):
            assert faute not in source, (nom, faute)
