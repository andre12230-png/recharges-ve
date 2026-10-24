"""La bascule vers PySide6 (etape 7) : l'autotest de l'exe, et les messages
du demarrage de la nouvelle fenetre.

Les messages du demarrage sont neutralises dans tous les autres tests
(conftest.py), puisqu'ils attendraient un clic. Ici, ils sont appeles pour
de bon, avec des boites de message remplacees par des doublures.

    py -m pytest tests/test_qt_bascule.py
"""

from __future__ import annotations

from datetime import datetime

import pytest

import fenetre as module_fenetre
import recharges

# La vraie methode, gardee AVANT que conftest.py ne la neutralise : pytest
# lit ce fichier avant de lancer le moindre test.
AVERTIR = module_fenetre.FenetrePrincipale._avertir_etat_donnees


@pytest.fixture
def donnees_rendues():
    """L'autotest redirige les donnees vers son jeu de demonstration : on
    les remet ou elles etaient pour la suite des tests."""
    ancien = recharges.dossier_donnees()
    yield
    recharges.rediriger_donnees(ancien)


# ---------- autotest ----------

def test_autotest_tout_va_bien(qapp, donnees_rendues, tmp_path):
    rapport = tmp_path / "rapport.txt"
    assert module_fenetre.autotest(str(rapport)) == 0
    lignes = rapport.read_text(encoding="utf-8").splitlines()
    assert lignes[0] == "données        : jeu de démonstration"
    import menu
    for vue in menu.pages():
        assert f"vue {vue:<11} : OK" in lignes
    assert "fichiers joints: OK" in lignes
    assert "thème          : clair (Pécule)" in lignes
    assert "recharges lues : 10" in lignes
    assert any(ligne.startswith("export PDF     : OK") for ligne in lignes)


def test_autotest_signale_une_page_cassee(qapp, donnees_rendues, tmp_path,
                                          monkeypatch):
    def cassee(fenetre):
        raise RuntimeError("page en panne")
    monkeypatch.setitem(module_fenetre.CONSTRUCTEURS, "km", cassee)
    rapport = tmp_path / "rapport.txt"
    assert module_fenetre.autotest(str(rapport)) == 1
    texte = rapport.read_text(encoding="utf-8")
    assert "vue km          : RuntimeError: page en panne" in texte
    assert "vue stats       : OK" in texte


# ---------- messages du demarrage ----------

@pytest.fixture
def boites(monkeypatch):
    """Les boites de message sont notees au lieu d'etre affichees.

    L'indicateur « tarifs disparus » repart aussi de zero : un test
    precedent qui a efface tarifs.json a pu le laisser allume en memoire."""
    monkeypatch.setattr(recharges, "INCIDENT_TARIFS", None)
    vues = []
    for genre in ("information", "warning", "critical"):
        monkeypatch.setattr(
            module_fenetre.QMessageBox, genre,
            lambda parent, titre, texte, g=genre: vues.append((g, titre, texte)))
    return vues


@pytest.fixture
def fenetre(qapp):
    f = module_fenetre.FenetrePrincipale(accueil=False)
    yield f
    f.deleteLater()


def test_premier_demarrage_accueille_puis_ouvre_les_tarifs(
        fenetre, boites, monkeypatch):
    monkeypatch.setattr(recharges, "PREMIER_DEMARRAGE", True)
    AVERTIR(fenetre)
    assert [(g, t) for g, t, _ in boites] == [
        ("information", "Bienvenue dans Recharges VE")]
    assert fenetre.vue_courante == "tarifs"


def test_donnees_reparees(fenetre, boites, monkeypatch):
    monkeypatch.setattr(recharges, "PREMIER_DEMARRAGE", False)
    monkeypatch.setattr(recharges, "DERNIERE_RESTAURATION", {
        "date_backup": datetime(2026, 9, 20, 8, 30), "n_recharges": 250,
        "mis_de_cote": "recharges.illisible.json"})
    remis = []
    monkeypatch.setattr(module_fenetre, "sauvegarder_donnees", remis.append)
    AVERTIR(fenetre)
    (genre, titre, texte), = boites
    assert (genre, titre) == ("warning", "Données réparées")
    assert "sauvegarde du 20/09/2026 à 08:30" in texte
    assert "recharges.illisible.json" in texte
    assert "remis en état" in texte and remis


def test_donnees_illisibles(fenetre, boites, monkeypatch):
    monkeypatch.setattr(recharges, "PREMIER_DEMARRAGE", False)
    monkeypatch.setattr(recharges, "DERNIERE_RESTAURATION", None)
    fenetre._erreur_chargement = "JSON invalide"
    AVERTIR(fenetre)
    (genre, titre, texte), = boites
    assert (genre, titre) == ("critical", "Données illisibles")
    assert "N'enregistrez rien" in texte


def test_tarifs_remis_depuis_une_copie(fenetre, boites, monkeypatch):
    """Diagnostic du 26/09/2026 : un tarifs.json disparu n'est plus pris
    pour un premier demarrage."""
    monkeypatch.setattr(recharges, "PREMIER_DEMARRAGE", False)
    monkeypatch.setattr(recharges, "DERNIERE_RESTAURATION", None)
    monkeypatch.setattr(recharges, "INCIDENT_TARIFS", {
        "copie": "tarifs_20260920_083000.json",
        "date": datetime(2026, 9, 20, 8, 30)})
    AVERTIR(fenetre)
    (genre, titre, texte), = boites
    assert (genre, titre) == ("warning", "Tarifs remis en place")
    assert "copie du 20/09/2026 à 08:30" in texte
    assert fenetre.vue_courante == "tarifs"


def test_tarifs_perdus_sans_copie(fenetre, boites, monkeypatch):
    monkeypatch.setattr(recharges, "PREMIER_DEMARRAGE", False)
    monkeypatch.setattr(recharges, "DERNIERE_RESTAURATION", None)
    monkeypatch.setattr(recharges, "INCIDENT_TARIFS",
                        {"copie": None, "date": None})
    AVERTIR(fenetre)
    (genre, titre, texte), = boites
    assert (genre, titre) == ("warning", "Tarifs introuvables")
    assert "Ressaisissez vos prix" in texte


def test_demarrage_ordinaire_silencieux(fenetre, boites, monkeypatch):
    monkeypatch.setattr(recharges, "PREMIER_DEMARRAGE", False)
    monkeypatch.setattr(recharges, "DERNIERE_RESTAURATION", None)
    AVERTIR(fenetre)
    assert boites == []


def test_sans_accueil_rien_n_est_programme(qapp, monkeypatch):
    """accueil=False (l'autotest) : aucune boite ne doit pouvoir s'ouvrir,
    meme plus tard."""
    appels = []
    monkeypatch.setattr(module_fenetre.QTimer, "singleShot",
                        lambda delai, *a: appels.append(delai))
    f = module_fenetre.FenetrePrincipale(accueil=False)
    assert 700 not in appels
    f.deleteLater()


def test_donnees_reparees_accorde_une_seule_recharge(fenetre, boites,
                                                     monkeypatch):
    """« qui contient 1 recharge », pas « 1 recharges » (07/10/2026)."""
    monkeypatch.setattr(recharges, "PREMIER_DEMARRAGE", False)
    monkeypatch.setattr(recharges, "DERNIERE_RESTAURATION", {
        "date_backup": datetime(2026, 9, 20, 8, 30), "n_recharges": 1,
        "mis_de_cote": None})
    monkeypatch.setattr(module_fenetre, "sauvegarder_donnees", lambda d: None)
    AVERTIR(fenetre)
    (_, _, texte), = boites
    assert "qui contient 1 recharge." in texte


def test_donnees_reprises_apres_disparition(fenetre, boites, monkeypatch):
    """Audit du 14/10/2026 (A01) : un fichier disparu n'est pas un fichier
    abime ; le message dit ce qui s'est vraiment passe."""
    monkeypatch.setattr(recharges, "PREMIER_DEMARRAGE", False)
    monkeypatch.setattr(recharges, "DERNIERE_RESTAURATION", {
        "cause": "absent", "date_backup": datetime(2026, 9, 20, 8, 30),
        "n_recharges": 250, "mis_de_cote": None})
    remis = []
    monkeypatch.setattr(module_fenetre, "sauvegarder_donnees", remis.append)
    AVERTIR(fenetre)
    (genre, titre, texte), = boites
    assert (genre, titre) == ("warning", "Données réparées")
    assert "avait disparu" in texte and "illisible" not in texte
    assert "sauvegarde du 20/09/2026 à 08:30" in texte
    assert remis


def test_copie_de_secours_ratee_signalee_une_fois(fenetre, boites,
                                                  monkeypatch):
    """Audit du 14/10/2026 (A02) : l'echec de la copie de secours d'un
    enregistrement ordinaire est dit a l'utilisateur, une seule fois."""
    monkeypatch.setattr(recharges, "ECHEC_BACKUP", "Le disque est plein.")
    fenetre._signaler_echec_backup()
    fenetre._signaler_echec_backup()
    (genre, titre, texte), = boites
    assert (genre, titre) == ("warning", "Copie de secours impossible")
    assert "Le disque est plein." in texte
    assert recharges.ECHEC_BACKUP is None
