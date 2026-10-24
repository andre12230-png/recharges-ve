"""Historique et fenetre « Modifier la recharge » de la version PySide6
(etape 4).

Donnees inventees, injectees a la place des fonctions de lecture ; la
suppression et la modification sont remplacees par des doublures : jamais
les vraies recharges.

    py -m pytest tests/test_qt_historique.py
"""

from __future__ import annotations

from datetime import datetime

import pytest
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QDialog

import dialogue_modifier
import fenetre as module_fenetre
import formulaire
from pages import historique as hist

MAINTENANT = datetime.now()
CE_MOIS = f"{MAINTENANT.year}-{MAINTENANT.month:02d}"

RECHARGES = [
    {"id": "a", "date": f"{CE_MOIS}-01T23:00", "fin": f"{CE_MOIS}-02T05:00",
     "lieu": "maison", "kwh": 20.0, "kwh_hc": 15.0, "cout_eur": 3.0,
     "prix_kwh": 0.15, "tarif_nom": "Mon contrat HP/HC"},
    {"id": "b", "date": f"{CE_MOIS}-02T12:00", "lieu": "exterieur",
     "kwh": 10.0, "cout_eur": 5.0, "prix_kwh": 0.5, "operateur": "Ionity",
     "carte": "Chargemap", "lieu_detail": "Aire de repos"},
    {"id": "c", "date": f"{CE_MOIS}-03T09:00", "lieu": "exterieur",
     "kwh": 30.0, "cout_eur": 18.0, "prix_kwh": 0.6,
     "operateur": "E.Leclerc", "carte": ""},
    {"id": "d", "date": "2020-01-05T10:00", "lieu": "maison", "kwh": 7.0,
     "cout_eur": 1.0, "prix_kwh": 0.1429, "tarif_nom": "Ancien"},
]


# ---------- calculs (sans interface) ----------

def test_selection_dans_l_ordre_lieu_periode_recherche_tri():
    ids = lambda rs: [r["id"] for r in rs]   # noqa: E731
    assert ids(hist.selection(RECHARGES, "Tout", "Tout", "",
                              ("date", True))) == ["c", "b", "a", "d"]
    assert ids(hist.selection(RECHARGES, "Maison", "Tout", "",
                              ("date", True))) == ["a", "d"]
    assert ids(hist.selection(RECHARGES, "Extérieur", "Tout", "ionity",
                              ("date", True))) == ["b"]
    assert ids(hist.selection(RECHARGES, "Tout", "Tout", "",
                              ("kwh", False))) == ["d", "b", "a", "c"]


def test_tri_apres_clic():
    assert hist.tri_apres_clic(("date", True), "date") == ("date", False)
    # Nouvelle colonne : les nombres partent du plus gros, le texte de A.
    assert hist.tri_apres_clic(("date", True), "kwh") == ("kwh", True)
    assert hist.tri_apres_clic(("date", True), "info") == ("info", False)


def test_cellules():
    assert hist.cellules(RECHARGES[1])[1:] == (
        "Extérieur", "10,00", "5,00", "0,5000", "Ionity (Chargemap)")
    # Sans carte : l'operateur seul, sans parentheses vides.
    assert hist.cellules(RECHARGES[2])[-1] == "E.Leclerc"
    assert hist.cellules(RECHARGES[0])[-1] == "Mon contrat HP/HC"


def test_message_si_vide():
    assert hist.message_si_vide("Tout", "zzz") == "Aucun résultat pour « zzz »."
    assert hist.message_si_vide("Maison", "").startswith(
        "Aucune recharge à la maison sur cette période.")


def test_message_si_vide_dit_comment_continuer():
    """Charte : un etat vide dit pourquoi ET comment commencer (audit du
    08/10/2026)."""
    from filtres import conseil_si_vide
    # Rien du tout : ajouter ou importer.
    debut = hist.message_si_vide("Tout", "", aucune_recharge=True)
    assert debut == "Aucune recharge pour l'instant.\n" + conseil_si_vide(True)
    assert "📝 Ajouter une recharge" in debut and "📥 Importer un CSV" in debut
    # Des recharges, mais pas sur cette periode : changer de periode.
    periode = hist.message_si_vide("Tout", "")
    assert periode.endswith(conseil_si_vide(False))
    assert "Toute la période" in periode


# ---------- la page ----------

@pytest.fixture
def fenetre(qapp, monkeypatch):
    monkeypatch.setattr(hist, "charger_donnees",
                        lambda: {"recharges": RECHARGES})
    monkeypatch.setattr(module_fenetre, "charger_donnees",
                        lambda: {"recharges": RECHARGES})
    f = module_fenetre.FenetrePrincipale()
    f.afficher_vue("historique")
    yield f
    f.deleteLater()


def page_de(f) -> hist.PageHistorique:
    return f.zone_page.widget().findChild(hist.PageHistorique)


def lignes(page) -> list[str]:
    return [r["id"] for r in page.modele.recharges]


def test_ouvre_sur_le_mois_en_cours(fenetre):
    page = page_de(fenetre)
    assert lignes(page) == ["c", "b", "a"]           # tout le mois, sans 2020
    assert page.resume.text().startswith("3 recharges · 60,00\xa0kWh · 26,00\xa0€")


def test_lieu_et_recherche_sans_reconstruire_la_page(fenetre):
    page = page_de(fenetre)
    page.choix_lieu.setCurrentText("Extérieur")
    assert lignes(page) == ["c", "b"]
    page.recherche.setText("ionity")             # filtre pendant la frappe
    assert lignes(page) == ["b"]
    assert page_de(fenetre) is page              # meme page : curseur garde
    assert fenetre.recherche_historique == "ionity"


def test_aucun_resultat(fenetre):
    page = page_de(fenetre)
    page.recherche.setText("zzz")
    assert page.tableau.isHidden()
    assert page.message_vide.text() == "Aucun résultat pour « zzz »."


def test_page_vide_garde_ses_controles_groupes(qapp, monkeypatch):
    """Audit du 08/10/2026 : sans aucune recharge, le tableau cache ne
    prenait plus la hauteur, et les rangees de controles s'etalaient sur
    toute la page (« Rechercher » a mi-hauteur, les boutons plus bas)."""
    monkeypatch.setattr(hist, "charger_donnees", lambda: {"recharges": []})
    monkeypatch.setattr(module_fenetre, "charger_donnees",
                        lambda: {"recharges": []})
    f = module_fenetre.FenetrePrincipale()
    try:
        f.resize(1280, 800)
        f.show()
        for _ in range(5):                 # minuteurs du demarrage
            qapp.processEvents()
        f.afficher_vue("historique")
        for _ in range(5):
            qapp.processEvents()
        page = page_de(f)
        assert page.tableau.isHidden()
        haut_lieu = page.choix_lieu.mapTo(page, page.choix_lieu.rect()
                                          .topLeft()).y()
        haut_recherche = page.recherche.mapTo(page, page.recherche.rect()
                                              .topLeft()).y()
        assert haut_recherche - haut_lieu < 60
    finally:
        f.close()
        f.deleteLater()


def test_menu_lieu_dit_tous_les_lieux(fenetre):
    """Audit du 08/10/2026 : « Tout » se lisait comme une periode. Le menu
    dit « Tous les lieux » ; la valeur gardee reste « Tout »."""
    page = page_de(fenetre)
    assert page.choix_lieu.itemText(0) == "Tous les lieux"
    page.choix_lieu.setCurrentText("Maison")
    page.choix_lieu.setCurrentText("Tous les lieux")
    assert fenetre.filtre_historique == "Tout"
    assert lignes(page) == ["c", "b", "a"]


def test_colonnes_a_la_largeur_de_leur_contenu(fenetre):
    """Charte : une colonne de date ou de nombre n'est jamais plus etroite
    que son contenu ; le libelle (Tarif / Operateur) prend le reste. Audit
    du 08/10/2026 : largeurs fixees a la main (80 px pour un montant)."""
    from PySide6.QtWidgets import QHeaderView
    entete = page_de(fenetre).tableau.horizontalHeader()
    derniere = entete.count() - 1
    for i in range(derniere):
        assert entete.sectionResizeMode(i) == QHeaderView.ResizeToContents, i
    assert entete.sectionResizeMode(derniere) == QHeaderView.Stretch


def test_clic_sur_un_titre_trie(fenetre):
    page = page_de(fenetre)
    page.tableau.horizontalHeader().sectionClicked.emit(2)      # kWh
    assert fenetre.tri_historique == ("kwh", True)
    assert lignes(page) == ["c", "a", "b"]
    page.tableau.horizontalHeader().sectionClicked.emit(2)
    assert lignes(page) == ["b", "a", "c"]


def test_le_tri_garde_la_ligne_choisie(fenetre):
    page = page_de(fenetre)
    page.tableau.selectRow(lignes(page).index("a"))
    page.tableau.horizontalHeader().sectionClicked.emit(2)
    assert page.recharge_choisie()["id"] == "a"


def test_boutons_actifs_seulement_avec_une_ligne_choisie(fenetre):
    page = page_de(fenetre)
    assert not page.bouton_modifier.isEnabled()
    assert not page.bouton_supprimer.isEnabled()
    page.tableau.selectRow(0)
    assert page.bouton_modifier.isEnabled()
    assert page.bouton_supprimer.isEnabled()


def test_ctrl_f_va_dans_la_recherche(fenetre):
    assert fenetre.champ_recherche is page_de(fenetre).recherche


def test_la_recherche_dit_son_raccourci(fenetre):
    """Comme le bouton « 🔎 Rechercher » de Pécule : le raccourci est écrit
    dans l'infobulle, entre parenthèses (Ctrl+F harmonisé le 11/10/2026)."""
    assert "(Ctrl+F)" in page_de(fenetre).recherche.toolTip()


def test_nombres_cales_a_droite(fenetre):
    page = page_de(fenetre)
    alignement = page.modele.data(page.modele.index(0, 2), Qt.TextAlignmentRole)
    assert alignement & Qt.AlignRight
    # Le lieu d'une recharge exterieure s'affiche au survol.
    rang = lignes(page).index("b")
    assert page.modele.data(page.modele.index(rang, 5),
                            Qt.ToolTipRole) == "Aire de repos"


def test_supprimer_demande_puis_choisit_la_voisine(fenetre, monkeypatch):
    supprimees = []
    monkeypatch.setattr(hist, "supprimer_recharge",
                        lambda ident: supprimees.append(ident) or True)
    reponses = [False, True]
    monkeypatch.setattr(hist, "confirmer", lambda *a, **k: reponses.pop(0))
    page = page_de(fenetre)
    page.tableau.selectRow(lignes(page).index("b"))
    page.supprimer()                          # « Garder »
    assert supprimees == []
    page.supprimer()                          # « Supprimer la recharge »
    assert supprimees == ["b"]
    # Apres reconstruction, la ligne suivante sera choisie.
    assert fenetre.selection_historique == "a"


def test_suppression_introuvable_le_dit(fenetre, monkeypatch):
    monkeypatch.setattr(hist, "supprimer_recharge", lambda ident: False)
    monkeypatch.setattr(hist, "confirmer", lambda *a, **k: True)
    messages = []
    monkeypatch.setattr(hist.QMessageBox, "critical",
                        lambda parent, titre, texte: messages.append(texte))
    page = page_de(fenetre)
    page.tableau.selectRow(0)
    page.supprimer()
    assert messages == ["Cette recharge est introuvable : rien n'a été "
                        "supprimé."]


def test_modifier_puis_retrouver_la_ligne(fenetre, monkeypatch):
    class FausseFenetre:
        def __init__(self, parent, recharge):
            self.recharge = recharge

        def exec(self):
            return QDialog.Accepted
    monkeypatch.setattr(hist, "DialogueModifier", FausseFenetre)
    page = page_de(fenetre)
    page.tableau.selectRow(lignes(page).index("a"))
    page.modifier()
    assert fenetre.selection_historique == "a"
    # La page reconstruite retrouve la ligne, puis oublie la consigne.
    nouvelle = hist.PageHistorique(fenetre)
    assert nouvelle.recharge_choisie()["id"] == "a"
    assert fenetre.selection_historique is None


# ---------- la fenetre « Modifier la recharge » ----------

@pytest.fixture
def modifiees(monkeypatch):
    appels = []
    monkeypatch.setattr(dialogue_modifier, "modifier_recharge",
                        lambda ident, modifs: appels.append((ident, modifs)))
    monkeypatch.setattr(dialogue_modifier, "lieux_deja_saisis",
                        lambda: ["Aire de repos"])
    monkeypatch.setattr(formulaire, "energie_invraisemblable", lambda kwh: "")
    return appels


def test_fenetre_pre_remplie_a_la_francaise(qapp, modifiees):
    d = dialogue_modifier.DialogueModifier(None, RECHARGES[1])
    f = d.formulaire
    assert f.texte("date_jour") == f"02/{CE_MOIS[5:]}/{CE_MOIS[:4]}"
    assert f.texte("date_heure") == "12:00"
    assert (f.texte("kwh"), f.texte("cout_eur")) == ("10,0", "5,0")
    assert f.texte("operateur") == "Ionity"
    assert f.texte("lieu_detail") == "Aire de repos"


def test_enregistrer_sans_rien_toucher(qapp, modifiees):
    d = dialogue_modifier.DialogueModifier(None, RECHARGES[0])
    d.enregistrer()
    assert modifiees == [("a", {"date": RECHARGES[0]["date"],
                                "fin": RECHARGES[0]["fin"], "kwh": 20.0})]
    assert d.result() == QDialog.Accepted


def test_erreur_sous_la_case(qapp, modifiees):
    d = dialogue_modifier.DialogueModifier(None, RECHARGES[0])
    d.formulaire.ecrire("kwh", "abc")
    d.enregistrer()
    assert d.formulaire.message("kwh").startswith("« abc »")
    assert modifiees == []


def test_refus_du_moteur_en_bas_de_la_fenetre(qapp, modifiees, monkeypatch):
    def refus(ident, modifs):
        raise ValueError("Aucune période tarifaire ne couvre cette date.")
    monkeypatch.setattr(dialogue_modifier, "modifier_recharge", refus)
    d = dialogue_modifier.DialogueModifier(None, RECHARGES[0])
    d.enregistrer()
    assert not d.message.isHidden()
    assert d.message.text() == "Aucune période tarifaire ne couvre cette date."
    assert d.result() != QDialog.Accepted


def test_energie_invraisemblable(qapp, modifiees, monkeypatch):
    monkeypatch.setattr(formulaire, "energie_invraisemblable",
                        lambda kwh: "Trop pour la batterie.")
    monkeypatch.setattr(formulaire, "_demander", lambda *a, **k: False)
    d = dialogue_modifier.DialogueModifier(None, RECHARGES[0])
    d.enregistrer()
    assert modifiees == []


def test_entree_enregistre_une_seule_fois(qapp, modifiees):
    """Dans une fenetre de dialogue, Entree declenche le bouton par defaut :
    si les cases l'ecoutaient aussi, la recharge serait enregistree deux
    fois."""
    for recharge, case in ((RECHARGES[0], "kwh"),
                           (RECHARGES[1], "lieu_detail")):
        modifiees.clear()
        d = dialogue_modifier.DialogueModifier(None, recharge)
        d.show()
        cible = d.formulaire.cases[case]
        cible = cible.lineEdit() if hasattr(cible, "lineEdit") else cible
        QTest.keyClick(cible, Qt.Key_Return)
        assert len(modifiees) == 1, case
        d.close()


def test_echap_ferme_sans_rien_changer(qapp, modifiees):
    d = dialogue_modifier.DialogueModifier(None, RECHARGES[0])
    d.show()
    QTest.keyClick(d.formulaire.cases["kwh"], Qt.Key_Escape)
    assert d.result() == QDialog.Rejected
    assert modifiees == []


def test_le_resume_passe_a_la_ligne_si_la_place_manque(fenetre):
    """Second audit du 16/10/2026, constat A7 : a la taille minimale de la
    fenetre (1 000 px), le resume colle a la recherche refusait de passer a
    la ligne et la page debordait de 140 px. La largeur se mesure hors des
    tests (polices absentes ici) : voir le JOURNAL du 17/10/2026."""
    page = page_de(fenetre)
    assert page.resume.wordWrap()
