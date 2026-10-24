"""Captures du site de Recharges VE, sur un jeu de demonstration INVENTE.

Aucune donnee reelle : un dossier temporaire, un contrat fictif, des lieux
inventes. Les couts sont calcules par le moteur de l'application (comme de
vraies saisies). Les captures (1280 x 800) sont ecrites dans le dossier donne
en argument ; on les regarde, puis on les copie dans docs/media.

    py captures_site.py dossier_de_sortie

La fenetre s'affiche quelques secondes a l'ecran pendant les captures. Les
dates du jeu sont ecrites pour finir le 24/09/2026, puis avancees toutes
ensemble jusqu'a la veille du jour ou l'on lance le script : le mois en cours
a ainsi toujours des recharges, sans rien retoucher (14/10/2026).
"""

import os
import random
import sys
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

DEMO = Path(tempfile.mkdtemp(prefix="captures_rve_"))
os.environ["RECHARGES_DATA_DIR"] = str(DEMO)
SORTIE = Path(sys.argv[1])
SORTIE.mkdir(parents=True, exist_ok=True)
PROJET = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJET))
os.chdir(PROJET)

import recharges as r  # noqa: E402

hasard = random.Random(2026)

# Tout le jeu avance d'un bloc : son dernier releve tombe la veille au matin.
DECALAGE = timedelta(days=(datetime.now().date() - timedelta(days=1)
                           - datetime(2026, 9, 24).date()).days)


def avancer(iso: str) -> str:
    """Une date du jeu, avancee comme tout le jeu."""
    quand = datetime.fromisoformat(iso) + DECALAGE
    if "T" in iso:                       # date et heure : « 2026-10-13T08:30 »
        return quand.isoformat(timespec="minutes")
    return quand.date().isoformat()      # date seule : « 2025-10-29 »


# --- reglages et contrat fictifs ---
r.enregistrer_config(r.valider_reglages("64", "90", "0"))
r.enregistrer_tarif({
    "nom": "Mon contrat HP/HC", "debut": "2025-01-01", "fin": None,
    "type": "hp_hc", "abonnement_mensuel": 17.5,
    "prix_hp": 0.2146, "prix_hc": 0.1696,
    "plages_hc": [["22:00", "06:00"]]})

# --- recharges a la maison : tous les 4 a 6 jours, surtout la nuit ---
jour = datetime(2025, 10, 2, 22, 30) + DECALAGE
fin_du_jeu = datetime(2026, 9, 23, 23, 0) + DECALAGE
while jour < fin_du_jeu:
    kwh = round(hasard.uniform(14, 38), 2)
    debut = jour.replace(hour=hasard.choice([21, 22, 22, 23]),
                         minute=hasard.choice([0, 15, 30, 45]))
    duree = timedelta(hours=kwh / 7.2)          # borne de 7,4 kW
    r.ajouter_recharge_maison(debut, debut + duree, kwh)
    jour += timedelta(days=hasard.choice([4, 5, 5, 6]))

# --- recharges exterieures : lieux et montants inventes ---
EXTERIEUR = [
    ("2025-10-18T11:40", "Ionity", "Chargemap", "Aire des Tilleuls (A7)", 42.3, 0.49),
    ("2025-12-21T15:10", "TotalEnergies", "Direct (CB)", "Station du Pont-Neuf", 28.6, 0.59),
    ("2026-02-14T10:25", "Fastned", "Chargemap", "Aire du Lac (A43)", 36.1, 0.59),
    ("2026-04-05T13:50", "Tesla Supercharger", "Tesla", "Centre commercial Les Vergers", 33.4, 0.45),
    ("2026-05-29T16:30", "Ionity", "Chargemap", "Aire des Tilleuls (A7)", 45.0, 0.49),
    ("2026-07-12T09:45", "Electra", "Direct (CB)", "Parking de la Gare", 31.2, 0.55),
    ("2026-07-26T14:05", "Fastned", "Chargemap", "Aire du Lac (A43)", 38.7, 0.59),
    ("2026-08-16T12:20", "Izivia", "Chargemap", "Aire de la Forêt (A6)", 26.9, 0.52),
    ("2026-09-12T17:35", "TotalEnergies", "Direct (CB)", "Station du Pont-Neuf", 24.5, 0.59),
]
for date, operateur, carte, lieu, kwh, prix in EXTERIEUR:
    r.ajouter_recharge_exterieur(kwh, round(kwh * prix, 2), operateur=operateur,
                                 lieu_detail=lieu, date=avancer(date),
                                 carte=carte)

# --- releves du compteur : un par mois ---
km = 18240.0
for mois in range(10, 22):
    annee, m = 2025 + (mois - 1) // 12, (mois - 1) % 12 + 1
    km += hasard.uniform(980, 1350)
    r.ajouter_releve_km(round(km), avancer(f"{annee}-{m:02d}-24T08:30"),
                        round(hasard.uniform(15.2, 16.4), 1))

# --- comparaison essence et frais de carte : valeurs inventees et rondes ---
r.enregistrer_config({"conso_essence": 5.5, "prix_essence": 1.8,
                      "prix_essence_annees": {}})
# Une sauvegarde externe faite hier : sans elle, le tableau de bord du site
# s'ouvrait sur le bandeau « jamais copiees hors de cet ordinateur ».
r.enregistrer_config({"sauvegarde_externe_derniere":
                      (datetime.now().date() - timedelta(days=1)).isoformat()})
r.ajouter_frais_carte({"carte": "Chargemap", "type": "unique",
                       "date": avancer("2025-10-10"), "fin": None,
                       "montant": 20.0})

print("jeu :", len(r.charger_donnees()["recharges"]), "recharges,",
      len(r.charger_releves_km()), "releves")

# --- captures ---
from PySide6.QtWidgets import QApplication  # noqa: E402

import fenetre  # noqa: E402
import theme_qt  # noqa: E402

application = QApplication(sys.argv)
theme_qt.appliquer_theme(application)
theme_qt.installer_traduction_qt(application)
w = fenetre.FenetrePrincipale(accueil=False)
w.resize(1280, 800)
w.show()


def attendre():
    for _ in range(15):
        application.processEvents()


attendre()
w.filtre_periode = "Tout"      # l'Historique montre un tableau bien rempli
for nom, vue in (("capture_1_tableau_de_bord", "dashboard"),
                 ("capture_2_historique", "historique"),
                 ("capture_3_statistiques", "stats"),
                 ("capture_4_kilometrage", "km"),
                 ("capture_5_essence", "essence")):
    w.afficher_vue(vue)
    attendre()
    w.grab().save(str(SORTIE / f"{nom}.png"))
    print(nom, "OK")
w.close()
