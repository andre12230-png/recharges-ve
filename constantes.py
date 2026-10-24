"""Valeurs fixes de l'application : nom, version, listes de reference.

Ce module ne depend de rien d'autre — ni de l'interface, ni des donnees. Il
peut donc etre importe de partout sans risque d'import circulaire, ce qui est
exactement le role qu'on attend de lui.
"""

import importlib.util
import sys
from pathlib import Path

APP_NAME = "Recharges VE"
APP_VERSION = "v2.2.22"

# Saisie depuis le telephone : reservee a la version privee (decision du
# 24/10/2026). L'exe public est construit sans telephone.py (option
# --exclude-module, voir build.bat) : l'application le constate ici, et n'en
# montre alors ni le bouton ni le paragraphe de la notice.
SAISIE_TELEPHONE = importlib.util.find_spec("telephone") is not None


def chemin_ressource(nom: str) -> Path:
    """Trouve un fichier de ressource (icone...) qu'on soit en .py ou bundle PyInstaller."""
    if hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS) / nom
    return Path(__file__).parent / nom


# Principaux operateurs de recharge (France/Europe), accessibles via Chargemap notamment
OPERATEURS = [
    "Allego", "Atlante", "BP Pulse", "Bump", "Carrefour Energies",
    "Driveco", "E.Leclerc", "Electra", "Engie Vianeo", "Fastned",
    "Freshmile", "IECharge", "Intermarche", "Ionity", "Izivia",
    "Lidl", "Power Dot", "Shell Recharge", "Tesla Supercharger",
    "TotalEnergies", "Autre",
]
CARTES = ["Chargemap", "Ionity", "Tesla", "Plugsurfing", "ChargeMyHyundai",
          "Direct (CB)", "Autre"]


# Nombre de recharges affichees d'un coup dans l'Historique. Chaque ligne coute
# une dizaine d'elements graphiques a construire : au-dela d'une trentaine,
# l'affichage devient tres lent (plus de 12 s pour 250 lignes). On decoupe donc
# la liste en pages.
LIGNES_PAR_PAGE = 25


# Colonnes de l'Historique : (cle de tri, intitule). L'ordre commande a la
# fois l'entete et les cellules de chaque ligne.
COLONNES_HISTORIQUE = [
    ("date", "Date"),
    ("lieu", "Lieu"),
    ("kwh", "kWh"),
    ("cout_eur", "Coût"),
    ("prix_kwh", "€/kWh"),
    ("info", "Tarif / Opérateur"),
]


# Plages d'heures creuses les plus repandues en France. Ce sont des
# HORAIRES, pas des prix : ils dependent du reseau, pas du contrat, et ne
# se periment donc pas comme un tarif. On ne propose AUCUN prix tout fait —
# un prix invente qui vieillit fausse tous les calculs en silence.
PLAGES_COURANTES = {
    "Choisir une plage courante…": "",
    "22:00-06:00  (la plus répandue)": "22:00-06:00",
    "23:00-07:00": "23:00-07:00",
    "21:30-05:30": "21:30-05:30",
    "00:00-06:00 + 12:00-14:00  (coupée)": "00:00-06:00, 12:00-14:00",
    "02:00-07:00 + 14:00-17:00  (coupée)": "02:00-07:00, 14:00-17:00",
}
