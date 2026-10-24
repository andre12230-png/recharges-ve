"""Le graphique « Énergie et coût par mois » de la page Statistiques
(version PySide6).

matplotlib dessine dans un widget Qt (FigureCanvasQTAgg), comme dans le
Photovoltaique. Ce module n'est importe qu'a l'ouverture des Statistiques :
charger matplotlib coute environ 2 secondes, inutile de les payer au
demarrage.
"""

from __future__ import annotations

from datetime import date

from matplotlib import rcParams
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.figure import Figure
from matplotlib.lines import Line2D
from matplotlib.patches import Patch
from matplotlib.ticker import FuncFormatter, MaxNLocator
from PySide6.QtWidgets import QSizePolicy

from theme_qt import (BLEU_NUIT, CARTE_CADRE, ENCRE, FOND_CARTE,
                      GRAPHE_COUT, GRAPHE_ENERGIE, GRIS_SOUS)


# La police de l'application, comme le Photovoltaique (DejaVu Sans faute de
# Segoe UI, hors Windows).
rcParams["font.family"] = ["Segoe UI", "DejaVu Sans"]

# Le chiffre ecrit dans une barre : noir dans les deux themes (5,8 pour 1 sur
# le bleu clair des barres, 6,8 sur le bleu du theme sombre ; le texte clair
# du theme sombre n'y tiendrait pas).
TEXTE_SUR_BARRE = "#000000"

MOIS_ABREGES = ["janv.", "févr.", "mars", "avr.", "mai", "juin", "juil.",
                "août", "sept.", "oct.", "nov.", "déc."]


def etiquette_mois(mois: str) -> str:
    """« 2026-01 » devient « janv. 26 » : assez court pour tenir a plat sous
    sa barre (charte : raccourcir avant de tourner)."""
    return f"{MOIS_ABREGES[int(mois[5:7]) - 1]} {mois[2:4]}"


def _milliers(valeur: float) -> str:
    """Graduation ronde a la francaise, milliers separes (espace fine
    insecable : le nombre ne se coupe jamais)."""
    return f"{valeur:,.0f}".replace(",", " ")


def en_euros(valeur: float, _position) -> str:
    """Graduation de l'axe des couts : « 1 200 € »."""
    return f"{_milliers(valeur)} €"


def en_kwh(valeur: float, _position) -> str:
    """Graduation de l'axe de l'energie (l'unite est dans le titre de l'axe)."""
    return _milliers(valeur)


def chiffre_barre(kwh: float) -> str:
    """Le chiffre ecrit au-dessus d'une barre : « 84 » a partir de 10 kWh,
    « 7,3 » en dessous (un arrondi a l'unite y ferait perdre trop)."""
    if kwh >= 10:
        return _milliers(kwh)
    return f"{kwh:.1f}".replace(".", ",")


def mois_en_cours_affiche(mois: list[str]) -> str | None:
    """Le mois en cours (« 2026-10 ») s'il figure dans le graphique : il
    n'est pas fini, sa barre est hachuree (charte, audit du 08/10/2026)."""
    aujourd_hui = date.today()
    en_cours = f"{aujourd_hui.year}-{aujourd_hui.month:02d}"
    return en_cours if en_cours in mois else None


class GraphiqueMois(FigureCanvasQTAgg):
    """Barres de l'energie par mois (axe de gauche, kWh) et courbe du cout
    (axe de droite, €)."""

    def __init__(self, mois: list[str], kwh: list[float], cout: list[float]):
        self.figure = Figure(figsize=(9, 3.4), dpi=100, facecolor=FOND_CARTE,
                             tight_layout=True)
        super().__init__(self.figure)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.setFixedHeight(320)
        self._dessiner(mois, kwh, cout)

    def _dessiner(self, mois, kwh, cout) -> None:
        ax1 = self.figure.add_subplot(111, facecolor=FOND_CARTE)
        # « janv. 26 », a plat tant qu'il y a au plus douze mois (une annee) ;
        # au-dela, ils se posent en biais plutot que de se chevaucher (audit
        # de design du 03/10/2026 : « 01/2026 » penche, alors qu'il tenait).
        etiquettes = [etiquette_mois(m) for m in mois]
        positions = list(range(len(mois)))
        # Barres pleines : transparentes a 15 %, elles tombaient a 2,8 pour 1
        # sur la carte claire, sous le seuil de 3 de la charte (audit du
        # 14/10/2026). Pleines : 3,4 en clair, 5,0 en sombre.
        barres = ax1.bar(positions, kwh, color=GRAPHE_ENERGIE,
                         label="Énergie (kWh)")
        debout = len(mois) > 12
        # De la place au-dessus de la plus haute barre pour son chiffre.
        haut = max(kwh, default=0)
        if haut > 0:
            ax1.set_ylim(0, haut * (1.25 if debout else 1.12))
        # Le mois en cours n'est pas fini : trace, mais hachure.
        en_cours = mois_en_cours_affiche(mois)
        if en_cours is not None:
            barre = barres[mois.index(en_cours)]
            barre.set_hatch("//")
            barre.set_edgecolor(FOND_CARTE)
        ax1.set_ylabel("kWh", color=BLEU_NUIT)
        if len(mois) <= 12:
            ax1.set_xticks(positions, etiquettes)
        else:
            ax1.set_xticks(positions, etiquettes, rotation=45, ha="right")
        # Graduations rondes (pas de 1, 2 ou 5 x 10^n), milliers separes.
        ax1.yaxis.set_major_locator(MaxNLocator(nbins=5, steps=[1, 2, 5, 10]))
        ax1.yaxis.set_major_formatter(FuncFormatter(en_kwh))
        ax1.tick_params(colors=GRIS_SOUS)
        for bord in ax1.spines.values():
            bord.set_color(CARTE_CADRE)
        ax2 = ax1.twinx()
        # La ligne passe SOUS les chiffres des barres (elle les barrait), et
        # ses points PAR-DESSUS (ils portent le cout de chaque mois) : deux
        # traces, l'un pour la ligne, l'autre pour les points.
        courbe, = ax2.plot(positions, cout, color=GRAPHE_COUT, marker="o",
                           label="Coût (€)", zorder=2)
        courbe.set_marker("None")
        ax2.plot(positions, cout, color=GRAPHE_COUT, marker="o",
                 linestyle="None", zorder=6)
        # Chaque graduation porte son « € » : plus besoin de titre d'axe.
        ax2.yaxis.set_major_locator(MaxNLocator(nbins=5, steps=[1, 2, 5, 10]))
        ax2.yaxis.set_major_formatter(FuncFormatter(en_euros))
        ax2.tick_params(colors=GRIS_SOUS)
        # Un coût nul (mois sans recharge) reste posé sur l'axe, pas en
        # dessous.
        ax2.set_ylim(bottom=0)
        for bord in ax2.spines.values():
            bord.set_color(CARTE_CADRE)
        # Une legende : les couleurs seules ne disent pas quel axe est lequel.
        # Posee AU-DESSUS du dessin, pour ne masquer ni barre ni point.
        # La legende garde un carre plein (Patch), sinon elle prendrait
        # l'allure de la premiere barre, peut-etre hachuree.
        carre = Patch(facecolor=GRAPHE_ENERGIE)
        repere_cout = Line2D([], [], color=GRAPHE_COUT, marker="o")
        ax1.legend([carre, repere_cout], ["Énergie (kWh)", "Coût (€)"],
                   loc="lower left", bbox_to_anchor=(0, 1.0), ncol=2,
                   frameon=False, fontsize=9,
                   # Le texte du theme : le noir par defaut de matplotlib
                   # disparaissait sur le fond sombre (12/10/2026).
                   labelcolor=ENCRE)
        self._ecrire_chiffres(ax1, ax2, positions, kwh, cout, debout)

    def _ecrire_chiffres(self, ax1, ax2, positions, kwh, cout,
                         debout) -> None:
        """Chaque barre porte son chiffre (audit du 14/10/2026) : la valeur
        exacte se lit sans survol, et la couleur ne porte pas seule
        l'information. A plat jusqu'a douze mois, debout au-dela (charte,
        section 5).

        Le chiffre se pose DANS le haut de la barre, en noir (5,8 pour 1 sur
        le bleu clair, 6,8 sur le bleu sombre) : au-dessus, il se disputait
        la place avec le point du cout du mois, souvent pose a la meme
        hauteur. Une barre trop courte pour le contenir le porte au-dessus
        d'elle, sur un petit fond de la carte. Les chiffres sont poses sur
        l'axe du cout, dessine en dernier : la ligne du cout passe dessous.
        """
        # La hauteur reelle du dessin, en pixels, pour savoir si un chiffre
        # tient dans sa barre (la hauteur du graphique est fixe : 320 px).
        self.figure.tight_layout()
        hauteur = ax1.get_window_extent().height
        pixels_par_kwh = hauteur / ax1.get_ylim()[1]
        points_par_pixel = 72 / self.figure.dpi
        for position, valeur, euros in zip(positions, kwh, cout):
            if valeur <= 0:
                continue
            texte = chiffre_barre(valeur)
            # Place qu'il faut : la hauteur d'une ligne a plat, la longueur
            # du texte debout (environ 6 px par signe en 8 pt), plus l'air.
            besoin = 7 * len(texte) + 12 if debout else 20
            dedans = valeur * pixels_par_kwh >= besoin
            fond = GRAPHE_ENERGIE if dedans else FOND_CARTE
            decalage = -6 if dedans else 6
            if not dedans:
                # Au-dessus de la barre, le point du cout peut tomber sur le
                # chiffre : on monte alors le chiffre au-dessus du point.
                haut_barre = ax1.transData.transform((position, valeur))[1]
                point = ax2.transData.transform((position, euros))[1]
                ecart = (point - haut_barre) * points_par_pixel
                if -6 <= ecart <= besoin * points_par_pixel + 6:
                    decalage = ecart + 7
            ax2.annotate(texte, (position, valeur), xycoords=ax1.transData,
                         xytext=(0, decalage),
                         textcoords="offset points", ha="center",
                         va="top" if dedans else "bottom", fontsize=8,
                         color=TEXTE_SUR_BARRE if dedans else ENCRE,
                         rotation=90 if debout else 0, zorder=5,
                         bbox={"boxstyle": "round,pad=0.15",
                               "facecolor": fond, "edgecolor": "none"})
