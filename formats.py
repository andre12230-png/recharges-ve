"""Mise en forme des valeurs a l'ecran : euros, kWh, dates, a la francaise.

Venues de theme.py (ancienne interface, retiree en 2.0.0), ou elles
voisinaient avec la palette de couleurs customtkinter. Elles ne dependent
d'aucune interface : les pages, l'export et les filtres s'en servent.
"""

from datetime import datetime

# Espace insecable, entre les milliers et devant l'unite : un montant ne se
# coupe jamais en fin de ligne (charte des trois applis, 07/10/2026).
ESPACE = "\xa0"


def fmt_eur(v: float) -> str:
    return f"{v:,.2f}{ESPACE}€".replace(",", ESPACE).replace(".", ",")


def fmt_nombre(v: float, decimales: int = 0) -> str:
    """Un nombre a la francaise, milliers separes : « 70 781 », « 6 398,45 »."""
    return f"{v:,.{decimales}f}".replace(",", ESPACE).replace(".", ",")


def fmt_signe(v: float) -> str:
    """Un nombre entier signe, milliers separes : « +1 250 », « -126 », « 0 »."""
    return ("+" if round(v) > 0 else "") + fmt_nombre(v)


def fmt_prix_kwh(v: float) -> str:
    """Prix du kWh, a la francaise : « 0,2516 €/kWh »."""
    return f"{v:.4f}{ESPACE}€/kWh".replace(".", ",")


def fmt_nb_recharges(n: int) -> str:
    """« 1 recharge », « 2 recharges » : l'accord que l'ecran oubliait."""
    return f"{n} recharge{'s' if n > 1 else ''}"


def fmt_kwh(v: float) -> str:
    return f"{v:,.2f}{ESPACE}kWh".replace(",", ESPACE).replace(".", ",")


def fmt_date_fr(iso: str) -> str:
    """Convertit '2026-05-28T14:30' en '28/05/2026 14:30'."""
    try:
        dt = datetime.fromisoformat(iso)
        return dt.strftime("%d/%m/%Y %H:%M")
    except Exception:
        return iso
