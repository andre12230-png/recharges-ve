"""Rappel de sauvegarde externe dans Recharges VE (28/09/2026).

La date de la derniere sauvegarde externe reussie est retenue dans
tarifs.json ; le tableau de bord rappelle doucement de recommencer au-dela
de 30 jours. Sans sauvegarde jamais faite, on compte depuis la premiere
recharge. Le texte vient de sauvegarde_externe.rappel_sauvegarde_externe,
commun aux trois applications. Donnees inventees, dossier jetable.

    py -m pytest tests/test_rappel_sauvegarde.py
"""

from __future__ import annotations

from datetime import date, datetime, timedelta

import recharges

from pages import tableau_de_bord as tb

AUJOURD_HUI = date(2026, 9, 30)


def _recharges(depuis_jours: int) -> list[dict]:
    jour = (datetime(2026, 9, 30) - timedelta(days=depuis_jours))
    return [{"id": "a", "date": jour.isoformat(timespec="minutes"),
             "lieu": "maison", "kwh": 10.0, "cout_eur": 2.0}]


def test_rien_juste_apres_une_sauvegarde():
    config = {"sauvegarde_externe_derniere": "2026-09-20"}
    assert tb.rappel_de_sauvegarde(_recharges(400), config,
                                   AUJOURD_HUI) is None


def test_rappel_au_dela_de_30_jours():
    config = {"sauvegarde_externe_derniere": "2026-08-01"}
    assert "depuis 60 jours" in tb.rappel_de_sauvegarde(
        _recharges(400), config, AUJOURD_HUI)


def test_jamais_faite_on_compte_depuis_la_premiere_recharge():
    assert tb.rappel_de_sauvegarde(_recharges(10), {}, AUJOURD_HUI) is None
    assert "jamais" in tb.rappel_de_sauvegarde(_recharges(45), {},
                                               AUJOURD_HUI)
    assert tb.rappel_de_sauvegarde([], {}, AUJOURD_HUI) is None


def test_le_bouton_retient_la_date(monkeypatch, tmp_path):
    import fenetre
    dossier = tmp_path / "donnees"
    recharges.ecrire_jeu_demo(dossier)
    cle = tmp_path / "cle"
    cle.mkdir()
    monkeypatch.setattr(fenetre.QFileDialog, "getExistingDirectory",
                        lambda *a: str(cle))
    monkeypatch.setattr(fenetre.QMessageBox, "information", lambda *a: None)
    faux = type("Faux", (), {"_destination_sauvegarde": ""})()
    ancien = recharges.dossier_donnees()
    recharges.rediriger_donnees(dossier)
    try:
        fenetre.FenetrePrincipale._sauvegarder_externe(faux)
        derniere = recharges.charger_config()["sauvegarde_externe_derniere"]
    finally:
        recharges.rediriger_donnees(ancien)
    assert derniere == date.today().isoformat()


def test_le_tableau_de_bord_montre_le_rappel(qapp, monkeypatch):
    import fenetre as module_fenetre
    from PySide6.QtWidgets import QLabel
    monkeypatch.setattr(module_fenetre, "charger_donnees",
                        lambda: {"recharges": []})
    monkeypatch.setattr(tb, "rappel_de_sauvegarde",
                        lambda *a: "Sauvegarde externe à refaire.")
    f = module_fenetre.FenetrePrincipale()
    page = tb.construire(f)
    assert any("Sauvegarde externe à refaire." in e.text()
               for e in page.findChildren(QLabel))
    f.deleteLater()


def test_le_rappel_est_un_bandeau_d_alerte_orange(qapp, monkeypatch):
    """29/09/2026 : le rappel etait un bandeau d'information jaune ; Pecule
    et le Photovoltaique le montrent en orange d'alerte. Meme couleur dans
    les trois applis."""
    import fenetre as module_fenetre
    from PySide6.QtWidgets import QFrame, QLabel
    monkeypatch.setattr(module_fenetre, "charger_donnees",
                        lambda: {"recharges": []})
    monkeypatch.setattr(tb, "rappel_de_sauvegarde",
                        lambda *a: "Sauvegarde externe à refaire.")
    f = module_fenetre.FenetrePrincipale()
    page = tb.construire(f)
    etiquette = next(e for e in page.findChildren(QLabel)
                     if "Sauvegarde externe à refaire." in e.text())
    parent = etiquette.parent()
    while parent is not None and not (isinstance(parent, QFrame)
                                      and parent.objectName().startswith("Bandeau")):
        parent = parent.parent()
    assert parent is not None and parent.objectName() == "BandeauAlerte"
    f.deleteLater()


def test_le_rappel_est_juste_avant_dernieres_recharges(qapp, monkeypatch):
    """17/10/2026 : le bandeau de sauvegarde quitte le haut de la page pour
    se placer juste avant la carte « Dernières recharges » (demande
    d'Andre) : les chiffres de la periode restent en tete."""
    import fenetre as module_fenetre
    from PySide6.QtWidgets import QLabel
    monkeypatch.setattr(module_fenetre, "charger_donnees",
                        lambda: {"recharges": []})
    monkeypatch.setattr(tb, "rappel_de_sauvegarde",
                        lambda *a: "Sauvegarde externe à refaire.")
    f = module_fenetre.FenetrePrincipale()
    page = tb.construire(f)
    colonne = page.layout()

    def rang(texte):
        # Remonte du texte jusqu'au bloc pose directement dans la page,
        # puis donne sa place dans la colonne.
        etiquette = next(e for e in page.findChildren(QLabel)
                         if texte in e.text())
        bloc = etiquette
        while bloc.parent() is not page:
            bloc = bloc.parent()
        return colonne.indexOf(bloc)

    assert rang("Sauvegarde externe à refaire.") + 1 == rang(
        "DERNIÈRES RECHARGES")              # titre de carte en capitales
    f.deleteLater()


def test_le_bandeau_d_alerte_a_les_couleurs_de_pecule():
    from theme_qt import (ALERTE_CADRE, ALERTE_FOND, ALERTE_TEXTE,
                          feuille_de_style)
    import re
    qss = feuille_de_style()
    bloc = re.search(r"QFrame#BandeauAlerte\s*\{([^}]*)\}", qss)
    assert bloc, "le style du bandeau d'alerte manque"
    assert ALERTE_FOND in bloc.group(1) and ALERTE_CADRE in bloc.group(1)
    texte = re.search(r"QFrame#BandeauAlerte QLabel\s*\{([^}]*)\}", qss)
    assert texte and ALERTE_TEXTE in texte.group(1)
