"""Le graphique des Statistiques (audit de design du 03/10/2026) : les mois
etaient penches alors qu'ils tenaient a plat, ecrits « 01/2026 », et l'axe
des couts n'avait pas d'euros sur ses graduations (charte, section 5)."""

import graphique


def test_mois_abreges_a_la_francaise():
    assert graphique.etiquette_mois("2026-01") == "janv. 26"
    assert graphique.etiquette_mois("2026-07") == "juil. 26"
    assert graphique.etiquette_mois("2025-12") == "déc. 25"


def test_graduations_en_euros():
    # Espaces insecables : la graduation ne se coupe jamais.
    assert graphique.en_euros(0, None) == "0 €"
    assert graphique.en_euros(1200, None) == "1 200 €"
    assert graphique.en_kwh(2500, None) == "2 500"


def test_douze_mois_tiennent_a_plat(qapp):
    mois = [f"2026-{m:02d}" for m in range(1, 13)]
    g = graphique.GraphiqueMois(mois, [100.0] * 12, [20.0] * 12)
    ax1 = g.figure.axes[0]
    textes = [t.get_text() for t in ax1.get_xticklabels()]
    assert textes[0] == "janv. 26"
    assert all(t.get_rotation() == 0 for t in ax1.get_xticklabels())
    g.deleteLater()


def test_le_mois_en_cours_est_hachure(qapp):
    """Charte : une periode incomplete reste tracee mais hachuree, et sa
    legende garde des carres pleins (audit du 08/10/2026)."""
    from datetime import date

    from matplotlib.patches import Patch
    aujourd_hui = date.today()
    en_cours = f"{aujourd_hui.year}-{aujourd_hui.month:02d}"
    mois = ["2020-01", en_cours]
    g = graphique.GraphiqueMois(mois, [100.0, 40.0], [20.0, 8.0])
    ax1 = g.figure.axes[0]
    barres = [p for p in ax1.patches]
    assert not barres[0].get_hatch()
    assert barres[1].get_hatch()
    poignees = ax1.get_legend().legend_handles
    assert isinstance(poignees[0], Patch) and not poignees[0].get_hatch()
    assert graphique.mois_en_cours_affiche(mois) == en_cours
    assert graphique.mois_en_cours_affiche(["2020-01"]) is None
    g.deleteLater()


def _contraste(c1, c2) -> float:
    """Rapport de contraste de deux couleurs RGB (0-1), formule WCAG."""
    def lum(c):
        def canal(v):
            return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4
        r, g, b = (canal(v) for v in c[:3])
        return 0.2126 * r + 0.7152 * g + 0.0722 * b
    clair, fonce = sorted((lum(c1), lum(c2)), reverse=True)
    return (clair + 0.05) / (fonce + 0.05)


def test_a14_barres_a_trois_pour_un_sur_la_carte(qapp):
    """Audit du 14/10/2026 (A14) : barres transparentes a 15 %, 2,8 pour 1
    seulement en clair. La couleur reellement vue (composee sur le fond de
    la carte) doit tenir 3 pour 1 (charte, section 1)."""
    from matplotlib.colors import to_rgb, to_rgba
    g = graphique.GraphiqueMois(["2020-01", "2020-02"], [100.0, 40.0],
                                [20.0, 8.0])
    ax1 = g.figure.axes[0]
    fond = to_rgb(graphique.FOND_CARTE)
    for barre in ax1.patches:
        r, v, b, a = to_rgba(barre.get_facecolor())
        vue = tuple(a * c + (1 - a) * f for c, f in zip((r, v, b), fond))
        assert _contraste(vue, fond) >= 3
    g.deleteLater()


def test_a14_chaque_barre_porte_son_chiffre(qapp):
    """La valeur de chaque barre est ecrite au-dessus : la couleur ne porte
    pas seule l'information, et le chiffre exact se lit sans survol."""
    g = graphique.GraphiqueMois(["2020-01", "2020-02", "2020-03"],
                                [83.5, 7.26, 0.0], [20.0, 2.0, 0.0])
    textes = [t.get_text() for ax in g.figure.axes for t in ax.texts]
    assert textes == ["84", "7,3"]
    g.deleteLater()


def test_a14_chiffre_dans_la_barre_lisible(qapp):
    """Un chiffre ecrit dans sa barre tient 4,5 pour 1 sur elle ; un
    chiffre pose au-dessus, sur la carte, aussi."""
    from matplotlib.colors import to_rgb
    g = graphique.GraphiqueMois(["2020-01", "2020-02"], [100.0, 3.0],
                                [20.0, 1.0])
    chiffres = [t for ax in g.figure.axes for t in ax.texts]
    assert len(chiffres) == 2
    for t in chiffres:
        fond = t.get_bbox_patch().get_facecolor()
        assert _contraste(to_rgb(t.get_color()), fond) >= 4.5
    # La grande barre porte son chiffre dedans, la petite au-dessus.
    fonds = [to_rgb(t.get_bbox_patch().get_facecolor()) for t in chiffres]
    assert fonds == [to_rgb(graphique.GRAPHE_ENERGIE),
                     to_rgb(graphique.FOND_CARTE)]
    g.deleteLater()


def test_a14_chiffres_debout_au_dela_de_douze_mois(qapp):
    mois = [f"2025-{m:02d}" for m in range(1, 13)] + ["2026-01"]
    g = graphique.GraphiqueMois(mois, [100.0] * 13, [20.0] * 13)
    chiffres = [t for ax in g.figure.axes for t in ax.texts]
    assert len(chiffres) == 13
    assert all(t.get_rotation() == 90 for t in chiffres)
    g.deleteLater()


def test_police_de_l_application():
    from matplotlib import rcParams
    assert rcParams["font.family"][0] == "Segoe UI"
