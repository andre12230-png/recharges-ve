"""Durees vraies, meme la nuit du changement d'heure.

Les heures d'une recharge sont rangees « a l'heure de l'horloge », sans
fuseau (format des fichiers inchange). Soustraire ou ajouter des heures
d'horloge trompe deux nuits par an : la nuit ou l'on avance l'heure,
01:30 -> 04:30 ne dure que 2 h ; la nuit ou on la recule, 02:30 -> 03:30
en dure 2. Le cout HP/HC en etait faux (second audit du 16/10/2026,
constat A2). Les autres jours, ces fonctions donnent exactement le meme
resultat qu'une simple soustraction.

Aucune dependance a Qt ni au reste de l'application.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

# Le fuseau qui sert a mesurer les durees. None : celui de l'ordinateur
# (Windows), le bon pour chaque utilisateur, qu'il ait ou non un changement
# d'heure. Les tests le fixent a Paris pour donner partout le meme resultat.
FUSEAU_DES_DUREES = None


def en_temps_universel(instant: datetime) -> datetime:
    """L'instant `instant`, lu a l'heure de l'horloge, en temps universel.

    Une heure qui passe deux fois (la nuit du retour a l'heure d'hiver) est
    lue comme la premiere : sans fuseau rangé, on ne peut pas savoir mieux."""
    if instant.tzinfo is None:
        if FUSEAU_DES_DUREES is None:
            instant = instant.astimezone()
        else:
            instant = instant.replace(tzinfo=FUSEAU_DES_DUREES)
    return instant.astimezone(timezone.utc)


def a_l_horloge(instant: datetime) -> datetime:
    """L'inverse : un instant en temps universel, lu a l'heure de
    l'horloge, sans fuseau (comme dans les fichiers)."""
    if FUSEAU_DES_DUREES is None:
        local = instant.astimezone()
    else:
        local = instant.astimezone(FUSEAU_DES_DUREES)
    return local.replace(tzinfo=None)


def secondes_reelles(debut: datetime, fin: datetime) -> float:
    """Le temps vraiment ecoule de `debut` a `fin`, en secondes."""
    return (en_temps_universel(fin)
            - en_temps_universel(debut)).total_seconds()


def apres_duree(debut: datetime, duree: timedelta) -> datetime:
    """L'heure d'horloge atteinte `duree` apres `debut` : une charge de 2 h
    commencee a 01:30 la nuit du passage a l'heure d'ete finit a 04:30."""
    return a_l_horloge(en_temps_universel(debut) + duree)
