"""Les erreurs techniques dites en francais, et la phrase fausse sur GitHub.

Demande de l'auteur du 26/09/2026 : les boites de message recopiaient tel
quel le texte d'erreur de Python ou de git, en anglais (« Expecting value:
line 1 column 1 (char 0) », « [Errno 13] Permission denied »). erreurs.py
les traduit en phrases simples ; ces tests le verifient, puis verifient que
les messages de l'application passent bien par lui.

Et : un envoi rate vers GitHub annoncait « Il sera retente a la prochaine
fermeture ». Faux depuis le 24/09/2026 : rien ne part plus a la fermeture.

    py -m pytest tests/test_erreurs_en_clair.py
"""

import ast
import errno
import json
import os
import shutil
import stat
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

os.environ.setdefault("RECHARGES_DATA_DIR",
                      tempfile.mkdtemp(prefix="recharges_erreurs_"))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import recharges as r  # noqa: E402
from erreurs import erreur_en_clair  # noqa: E402

RACINE = Path(__file__).resolve().parent.parent
ANGLAIS = ("Expecting", "Permission denied", "No such file", "codec",
           "No space", "delimiter")


def sans_anglais(texte: str) -> bool:
    return not any(mot in texte for mot in ANGLAIS)


# ---------- la traduction elle-meme ----------

def test_json_abime_dit_ou():
    try:
        json.loads('{ "recharges": [,] }')
    except json.JSONDecodeError as e:
        texte = erreur_en_clair(e)
    assert "ligne 1, colonne" in texte and sans_anglais(texte)


def test_caracteres_mal_codes():
    try:
        "Prés".encode("cp1252").decode("utf-8")
    except UnicodeDecodeError as e:
        texte = erreur_en_clair(e)
    assert "mal codés" in texte and sans_anglais(texte)


def test_acces_refuse_nomme_le_fichier():
    e = PermissionError(errno.EACCES, "Permission denied",
                        r"C:\Donnees\recharges.json")
    texte = erreur_en_clair(e)
    assert "« recharges.json »" in texte
    assert "autre programme" in texte and sans_anglais(texte)


def test_fichier_introuvable():
    e = FileNotFoundError(errno.ENOENT, "No such file or directory",
                          r"C:\Donnees\export.csv")
    texte = erreur_en_clair(e)
    assert "« export.csv » introuvable" in texte and sans_anglais(texte)


def test_disque_plein():
    texte = erreur_en_clair(OSError(errno.ENOSPC, "No space left on device"))
    assert "disque est plein" in texte and sans_anglais(texte)


def test_autre_erreur_de_fichier_commence_en_francais():
    texte = erreur_en_clair(OSError(errno.EIO, "Input/output error"))
    assert texte.startswith("Le fichier n'a pas pu être lu ou écrit")


def test_message_deja_en_francais_inchange():
    assert erreur_en_clair(ValueError("La fin doit être après le début.")) \
        == "La fin doit être après le début."


# ---------- les messages de l'application ----------

@pytest.fixture
def dossier(tmp_path):
    ancien = r.BASE
    r.rediriger_donnees(tmp_path)
    yield tmp_path
    r.rediriger_donnees(ancien)


def test_ecriture_refusee_nomme_le_vrai_fichier(dossier, monkeypatch):
    """Audit du 08/10/2026 : un recharges.json en lecture seule donnait
    « Accès refusé au fichier « tmpo85oyjiz.tmp » », un nom que
    l'utilisateur ne voit jamais. Le message nomme recharges.json."""
    def refuse(source, cible):
        raise PermissionError(errno.EACCES, "Accès refusé", str(source),
                              None, str(cible))
    monkeypatch.setattr(r.os, "replace", refuse)
    with pytest.raises(PermissionError) as erreur:
        r.sauvegarder_donnees({"recharges": []})
    texte = erreur_en_clair(erreur.value)
    assert "« recharges.json »" in texte and ".tmp" not in texte
    assert not list(dossier.glob("*.tmp"))          # rien ne traine
    with pytest.raises(PermissionError) as erreur:
        r._ecrire_tarifs({"tarifs": []})
    assert "« tarifs.json »" in erreur_en_clair(erreur.value)


def test_tarifs_abimes(dossier):
    (dossier / "tarifs.json").write_text('{"tarifs": [,]}', encoding="utf-8")
    with pytest.raises(ValueError) as erreur:
        r.charger_tarifs()
    texte = str(erreur.value)
    assert "tarifs.json est invalide" in texte
    assert "ligne 1, colonne" in texte and sans_anglais(texte)


def test_restaurer_une_sauvegarde_abimee(dossier):
    abimee = dossier / "recharges_20260301_100000.json"
    abimee.write_text("{ abime", encoding="utf-8")
    with pytest.raises(ValueError) as erreur:
        r.restaurer_backup(abimee)
    assert sans_anglais(str(erreur.value))


def test_fichier_illisible_au_demarrage(dossier, qapp):
    """Sans sauvegarde pour le reparer : le detail du message d'alerte."""
    import fenetre as module_fenetre
    (dossier / "recharges.json").write_text("{ abime", encoding="utf-8")
    r.vider_cache()
    f = module_fenetre.FenetrePrincipale(accueil=False)
    try:
        assert f._erreur_chargement and sans_anglais(f._erreur_chargement)
    finally:
        f.deleteLater()
        (dossier / "recharges.json").unlink()
        r.vider_cache()


def _recopies_brutes(fichier: Path) -> list[int]:
    """Lignes ou une erreur est recopiee telle quelle — f"{e}",
    f"{e or ...}" ou str(e) — ailleurs que dans un print().

    Meme methode que le Photovoltaique : on lit la structure du code (ast)
    plutot que son texte, pour ne pas se laisser tromper par un commentaire.
    « Une erreur » : le nom d'un « except ... as x », ou une variable
    nommee comme on nomme les erreurs (e, exc, err)."""
    arbre = ast.parse(fichier.read_text(encoding="utf-8"))
    noms = {"e", "exc", "err"}
    noms.update(n.name for n in ast.walk(arbre)
                if isinstance(n, ast.ExceptHandler) and n.name)
    dans_print = set()
    for noeud in ast.walk(arbre):
        if (isinstance(noeud, ast.Call) and isinstance(noeud.func, ast.Name)
                and noeud.func.id == "print"):
            dans_print.update(id(n) for n in ast.walk(noeud))

    def nomme_une_erreur(noeud) -> bool:
        return isinstance(noeud, ast.Name) and noeud.id in noms

    lignes = []
    for noeud in ast.walk(arbre):
        if id(noeud) in dans_print:
            continue
        if isinstance(noeud, ast.FormattedValue):
            valeur = noeud.value
            if nomme_une_erreur(valeur) or (
                    isinstance(valeur, ast.BoolOp)
                    and any(nomme_une_erreur(v) for v in valeur.values)):
                lignes.append(noeud.lineno)
        elif (isinstance(noeud, ast.Call) and isinstance(noeud.func, ast.Name)
              and noeud.func.id == "str" and len(noeud.args) == 1
              and nomme_une_erreur(noeud.args[0])):
            lignes.append(noeud.lineno)
    return sorted(lignes)


# Tout ce qui s'affiche a l'ecran. fenetre.py y manquait avant le 29/09/2026 :
# sa page « Cette page n'a pas pu s'afficher » recopiait str(e), en anglais
# pour une erreur de Python, sans que ce test le voie.
FICHIERS_A_L_ECRAN = sorted([
    *(RACINE / "pages").glob("*.py"), *RACINE.glob("dialogue_*.py"),
    RACINE / "fenetre.py", RACINE / "app.py", RACINE / "composants.py",
    RACINE / "fenetres_aide.py", RACINE / "formulaire.py",
    RACINE / "suivi_saisie.py", RACINE / "graphique.py", RACINE / "menu.py"])


@pytest.mark.parametrize("fichier", FICHIERS_A_L_ECRAN, ids=lambda f: f.name)
def test_l_ecran_ne_recopie_plus_l_erreur_brute(fichier):
    """Ce qui s'affiche passe par erreur_en_clair(e), jamais par str(e) ni
    « {e} » tel quel. Le detail technique voulu (diagnostic) s'ecrit avec
    traceback.format_exception_only(e)."""
    assert _recopies_brutes(fichier) == []


def test_la_detection_voit_une_recopie_brute(tmp_path):
    """Le detecteur lui-meme : il trouve str(e) et {e}, pas un print."""
    essai = tmp_path / "essai.py"
    essai.write_text(
        "try:\n    pass\nexcept Exception as e:\n"
        "    texte = str(e)\n    autre = f'{e}'\n    print(f'{e}')\n",
        encoding="utf-8")
    assert _recopies_brutes(essai) == [4, 5]


# ---------- l'envoi rate vers GitHub ----------

def _effacer(dossier: Path) -> None:
    """Efface un dossier, meme s'il contient un depot git (fichiers en
    lecture seule sous Windows)."""
    def insister(fonction, chemin, _exception):
        os.chmod(chemin, stat.S_IWRITE)
        fonction(chemin)
    shutil.rmtree(dossier, onexc=insister)


@pytest.mark.skipif(not shutil.which("git"), reason="git n'est pas installé")
def test_envoi_rate_ne_promet_plus_la_fermeture(tmp_path):
    def git(*args, cwd=tmp_path / "donnees"):
        return subprocess.run(["git", *args], cwd=str(cwd),
                              capture_output=True, text=True)

    donnees = tmp_path / "donnees"
    donnees.mkdir()
    (donnees / "recharges.json").write_text('{"recharges": []}',
                                            encoding="utf-8")
    (donnees / "tarifs.json").write_text('{"tarifs": []}', encoding="utf-8")
    distant = tmp_path / "distant.git"
    git("init", "--bare", str(distant), cwd=tmp_path)
    git("init")
    git("config", "user.name", "Test")
    git("config", "user.email", "test@example.invalid")
    git("add", "-A")
    git("commit", "-m", "depart")
    git("remote", "add", "origin", str(distant))
    assert git("push", "-u", "origin", "HEAD").returncode == 0
    # Le depot distant disparait : l'envoi suivant echouera.
    _effacer(distant)

    ancien = r.BASE
    r.rediriger_donnees(donnees)
    try:
        (donnees / "tarifs.json").write_text('{"tarifs": [], "x": 1}',
                                             encoding="utf-8")
        ok, message = r.synchroniser_github()
    finally:
        r.rediriger_donnees(ancien)
        _effacer(donnees)
    assert not ok
    assert "fermeture" not in message
    assert "Sauvegarder" in message
