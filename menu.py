"""Le menu de gauche et le titre de chaque page, decrits une seule fois.

Donnees pures, sans interface : la fenetre (fenetre.py) en construit son
bandeau et ses titres, et l'autotest en tire la liste des pages a ouvrir.
Une page ajoutee ici apparait donc partout a la fois — voir
tests/test_menu.py.
"""

# Le menu, section par section : (identifiant, libelle, pictogramme).
# Les emoji sont ceux du Photovoltaique quand la page y a une equivalente
# (Tableau de bord, Statistiques, Notice) ; « Ajouter une recharge » garde
# 📝, la Saisie quotidienne du Photovoltaique a ✏️.
# Ordre de l'usage (28/09/2026, demande de l'auteur) : saisir — les deux
# facons d'entrer une recharge, puis l'Historique pour les corriger —,
# analyser et exporter ce qu'on analyse, sauvegarder puis restaurer, regler,
# se faire aider.
SECTIONS = [
    ("PRINCIPAL", [
        ("dashboard", "Tableau de bord", "🏠"),
        ("ajouter", "Ajouter une recharge", "📝"),
        ("import", "Importer un CSV", "📥"),
        ("historique", "Historique", "📋"),
    ]),
    ("ANALYSE", [
        ("stats", "Statistiques", "📊"),
        ("km", "Kilométrage", "🚗"),
        ("essence", "Essence ou électrique ?", "⛽"),
        ("export", "Exporter", "📤"),
    ]),
    # « 💾 Sauvegarde externe » (une action, pas une page) est pose par
    # fenetre.py EN TETE de cette section : on sauvegarde, puis on restaure.
    # « MES DONNÉES », comme dans Pecule (29/09/2026 ; c'etait « SAUVEGARDES »).
    ("MES DONNÉES", [
        # ♻ et non 🔄 : 🔄 est le bouton « Mise à jour », comme dans
        # Pécule. Libellé complet, celui du titre de la page (ménage du
        # bandeau, 11/10/2026 ; c'était « Restaurer »).
        ("restaurer", "Restaurer une sauvegarde", "♻"),
    ]),
    # Comme la rubrique « Réglages » de Pécule.
    ("RÉGLAGES", [
        # ⚡ et non 💶 (11/10/2026) : 💶 est « Synthèse financière » dans le
        # Photovoltaïque, de l'argent ; ici, ce sont vos prix de l'électricité.
        ("tarifs", "Tarifs", "⚡"),
        ("parametres", "Paramètres", "⚙️"),
    ]),
    ("AIDE", [
        ("notice", "Notice", "📖"),
    ]),
]

# Les pages qui servent de temps en temps : un seul bouton du bandeau,
# « 🗂️ Comparer et exporter… », les propose dans un petit menu, comme
# « Bilans et comparaisons… » dans le Photovoltaique (choix de l'auteur du
# 11/10/2026). Elles restent des pages, decrites ci-dessus a leur place.
COMPARER_ET_EXPORTER = ("essence", "export")

# Titre et sous-titre affiches en haut de chaque page.
TITRES = {
    "dashboard": ("Tableau de bord", "Vue d'ensemble de vos recharges"),
    # Comme la Saisie quotidienne du Photovoltaique, une phrase qui commence
    # par ce qu'on fait (11/10/2026 ; c'etait « Maison ou borne extérieure »).
    "ajouter": ("Ajouter une recharge",
                "Saisir une recharge, à la maison ou sur une borne extérieure"),
    # Des mots, pas de « / » entre deux mots (charte), et ce que la page
    # contient : ces sous-titres servent aussi d'infobulle (11/10/2026).
    "historique": ("Historique", "Toutes vos recharges, à modifier ou supprimer"),
    "stats": ("Statistiques",
              "Énergie et coût mois par mois, et par tarif, opérateur et carte"),
    "km": ("Kilométrage",
           "Relevés du compteur et consommation réelle de la voiture"),
    "essence": ("Essence ou électrique ?",
                "Ce que vos kilomètres vous auraient coûté en essence"),
    "import": ("Importer un CSV",
               "L'historique exporté par votre borne de recharge"),
    "export": ("Exporter", "Excel ou PDF, sur la période de votre choix"),
    # Le sous-titre ne redit pas le titre de la premiere carte, « Grille
    # tarifaire » (audit de design du 03/10/2026) : il dit ce que la page
    # contient.
    "tarifs": ("Tarifs",
               "Vos prix de l'électricité à la maison, et les frais de vos "
               "cartes de recharge"),
    # Les cartes de la page, au « vous » comme les Parametres du
    # Photovoltaique (11/10/2026).
    "parametres": ("Paramètres",
                   "Votre voiture, votre borne, l'abonnement de la maison et "
                   "vos données"),
    "restaurer": ("Restaurer une sauvegarde",
                  "Revenir à un état antérieur de vos recharges"),
    # Comme Pecule et le Photovoltaique, sans « glossaire » : cette notice
    # n'en a pas (11/10/2026).
    "notice": ("Notice", "Mode d'emploi"),
}


# Les pages ou l'on tape des donnees a enregistrer (et non de simples
# filtres) : la fenetre y suit les cases modifiees, pour ne pas les effacer
# en changeant de page ni fermer sans prevenir.
PAGES_DE_SAISIE = ("ajouter", "km", "parametres", "tarifs")


def pages() -> list[str]:
    """Les identifiants de toutes les pages, dans l'ordre du menu."""
    return [vue_id for _, items in SECTIONS for vue_id, _, _ in items]
