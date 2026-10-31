"""Une valeur tapee et pas encore enregistree ne se perd plus sans un mot.

Defaut d'origine (verifie le 28/09/2026 par un essai) : chaque page etait
reconstruite a chaque clic du bandeau, et l'ancienne detruite. Aller voir une
autre page puis revenir, recliquer sur la page ouverte ou appuyer sur F5
effacait la recharge, le releve ou le reglage tape. La fermeture ne demandait
rien, et Ctrl+S (envoi vers GitHub) laissait croire que tout etait enregistre.

Donnees inventees, dossier jetable : jamais les vraies donnees.

    py -m pytest tests/test_saisie_conservee.py
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

# Redirection AVANT tout import du projet (voir conftest.py) : filet de
# secours si ce fichier est lance autrement que par pytest.
os.environ.setdefault("RECHARGES_DATA_DIR",
                      tempfile.mkdtemp(prefix="recharges_saisie_"))

import pytest  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402
from PySide6.QtWidgets import QLineEdit, QMessageBox, QPushButton  # noqa: E402

import fenetre as module_fenetre  # noqa: E402
from pages import parametres as pa  # noqa: E402

MARQUE = "12,5"


@pytest.fixture
def fenetre(qapp, monkeypatch):
    monkeypatch.setattr(module_fenetre, "charger_donnees",
                        lambda: {"recharges": []})
    # Aucune ecriture de reglages pendant ces tests.
    monkeypatch.setattr(pa, "enregistrer_config", lambda reglage: None)
    f = module_fenetre.FenetrePrincipale()
    qapp.processEvents()                  # le tableau de bord du demarrage
    yield f
    f._pages_gardees.clear()
    f.afficher_vue("dashboard", forcer=True)
    f.deleteLater()


def _page(f):
    return f.zone_page.widget()


def _taper(qapp, f, rang: int = 0) -> None:
    """Tape au clavier dans une case de la page, comme l'utilisateur."""
    qapp.processEvents()
    cases = [c for c in _page(f).findChildren(QLineEdit)
             if c.isEnabled() and not c.isReadOnly()]
    cases[rang].clear()
    QTest.keyClicks(cases[rang], MARQUE)


def _present(qapp, f) -> bool:
    qapp.processEvents()
    return any(c.text() == MARQUE for c in _page(f).findChildren(QLineEdit))


class _FauxMessages:
    """Remplace les boites de dialogue : repond sans attendre un clic."""
    Discard = QMessageBox.Discard
    Cancel = QMessageBox.Cancel
    Yes = QMessageBox.Yes
    No = QMessageBox.No
    reponse = QMessageBox.Cancel

    def __init__(self):
        self.questions: list[str] = []
        self.informations: list[str] = []
        # Titres des boites d'information (19/10/2026 : Ctrl+S ne doit
        # parler de git ni dans le titre ni dans le texte).
        self.titres: list[str] = []

    def question(self, parent, titre, texte, *a, **k):
        self.questions.append(texte)
        return self.reponse

    def information(self, parent, titre, texte, *a, **k):
        self.titres.append(titre)
        self.informations.append(texte)

    def warning(self, parent, titre, texte, *a, **k):
        self.titres.append(titre)
        self.informations.append(texte)

    def confirmer(self, parent, titre, texte, action, garder="Annuler",
                  *a, **k):
        # Les boites a boutons nommes (fermeture) : « Discard » vaut le
        # bouton d'action, tout le reste le bouton qui garde.
        self.questions.append(texte)
        self.boutons.append((titre, action, garder))
        return self.reponse == QMessageBox.Discard


@pytest.fixture
def messages(monkeypatch):
    faux = _FauxMessages()
    faux.boutons = []
    monkeypatch.setattr(module_fenetre, "QMessageBox", faux)
    monkeypatch.setattr(module_fenetre, "confirmer", faux.confirmer)
    return faux


# --- Changer de page ---------------------------------------------------------

@pytest.mark.parametrize("page, autre", [
    ("ajouter", "historique"), ("km", "historique"),
    ("parametres", "essence")])
def test_aller_voir_une_autre_page_puis_revenir_garde_la_saisie(
        qapp, fenetre, page, autre):
    fenetre.afficher_vue(page)
    _taper(qapp, fenetre)
    fenetre.afficher_vue(autre)
    fenetre.afficher_vue(page)
    assert _present(qapp, fenetre)


def test_recliquer_sur_la_page_ou_f5_garde_la_saisie(qapp, fenetre):
    fenetre.afficher_vue("ajouter")
    _taper(qapp, fenetre)
    fenetre.afficher_vue("ajouter")            # clic du bandeau, ou F5
    assert _present(qapp, fenetre)


def test_sans_saisie_la_page_est_reconstruite_comme_avant(qapp, fenetre):
    fenetre.afficher_vue("ajouter")
    avant = _page(fenetre)
    fenetre.afficher_vue("historique")
    fenetre.afficher_vue("ajouter")
    assert _page(fenetre) is not avant
    assert fenetre.saisies_en_attente() == []


def test_ce_que_l_application_ecrit_seule_ne_compte_pas(qapp, fenetre):
    # Ajouter pre-remplit la date du jour : ce n'est pas une saisie.
    fenetre.afficher_vue("ajouter")
    assert fenetre.saisies_en_attente() == []


def test_une_recherche_dans_l_historique_n_est_pas_une_saisie(qapp, fenetre):
    fenetre.afficher_vue("historique")
    _taper(qapp, fenetre)
    assert fenetre.saisies_en_attente() == []


def test_reglages_enregistres_plus_rien_en_attente(qapp, fenetre):
    fenetre.afficher_vue("parametres")
    page = fenetre._page_affichee
    cases = page.findChildren(QLineEdit)
    case = [c for c in cases if c.text()][0]    # un reglage deja rempli
    valeur = case.text()
    case.selectAll()
    QTest.keyClicks(case, valeur)              # retape : valeur acceptee
    assert fenetre.saisies_en_attente() == ["parametres"]
    # Chaque carte a son bouton : on enregistre les trois (la part de
    # l'abonnement liee a la voiture a sa carte depuis le 10/10/2026).
    boutons = [b for b in page.findChildren(QPushButton)
               if b.text().startswith("Enregistrer")]
    assert len(boutons) == 3
    for bouton in boutons:
        bouton.click()
    assert fenetre.saisies_en_attente() == []


# --- Fermer ------------------------------------------------------------------

def test_fermer_sans_saisie_ne_demande_rien(qapp, fenetre, messages):
    assert fenetre.close()
    assert messages.questions == []


def test_fermer_avec_saisie_annuler_ramene_a_la_page(qapp, fenetre, messages):
    fenetre.afficher_vue("ajouter")
    _taper(qapp, fenetre)
    fenetre.afficher_vue("historique")
    messages.reponse = QMessageBox.Cancel
    assert not fenetre.close()
    assert "pas encore enregistr" in messages.questions[0]
    assert "Ajouter une recharge" in messages.questions[0]
    assert fenetre.vue_courante == "ajouter"
    assert _present(qapp, fenetre)


def test_fermer_sans_enregistrer_ferme(qapp, fenetre, messages):
    fenetre.afficher_vue("ajouter")
    _taper(qapp, fenetre)
    messages.reponse = QMessageBox.Discard
    assert fenetre.close()
    # Audit du 08/10/2026 : Qt traduit « Discard » par « Ne pas tenir
    # compte ». Les boutons disent l'action, et la boite son sujet.
    assert messages.boutons == [("Saisie non enregistrée",
                                 "Fermer sans enregistrer",
                                 "Revenir à la saisie")]

# --- Ctrl+S ------------------------------------------------------------------
# L'envoi vers GitHub a ete retire le 31/10/2026 : Ctrl+S ne sauvegarde rien,
# il reste un rappel pour ceux qui ont ce reflexe.

def test_ctrl_s_avec_saisie_le_dit(qapp, fenetre, messages):
    fenetre.afficher_vue("ajouter")
    _taper(qapp, fenetre)
    fenetre._reflexe_ctrl_s()
    texte = messages.informations[0]
    assert "n'enregistre pas" in texte
    assert "Ajouter une recharge" in texte
    assert "dépôt" not in texte
    assert _present(qapp, fenetre)


def test_ctrl_s_sans_saisie_oriente_vers_la_sauvegarde_externe(
        qapp, fenetre, messages):
    """Analyse « nouvel utilisateur » du 19/10/2026 : ce reflexe recoit une
    reponse dans les mots de l'utilisateur, sans parler de git."""
    fenetre._reflexe_ctrl_s()
    texte = " ".join(messages.titres + messages.informations).lower()
    assert "git" not in texte and "dépôt" not in texte
    assert "sauvegarde externe" in texte
    assert "avec les boutons" in texte


def test_plus_aucun_envoi_vers_github(fenetre):
    """Rien dans l'application ne peut envoyer les donnees vers GitHub : ni
    bouton « Sauvegarder », ni fonction d'envoi, ni appel a git."""
    assert not hasattr(module_fenetre.recharges, "synchroniser_github")
    assert not hasattr(module_fenetre, "synchroniser_github")
    textes = [b.text() for b in fenetre.findChildren(QPushButton)]
    assert "Sauvegarder" not in textes
    racine = Path(module_fenetre.__file__).resolve().parent
    for nom in ("recharges.py", "fenetre.py"):
        assert "subprocess" not in (racine / nom).read_text(encoding="utf-8")
