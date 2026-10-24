"""Fenetre principale de la version PySide6 de Recharges VE.

Depuis la 2.0.0 (25/09/2026), elle remplace l'ancienne fenetre customtkinter
dont elle reprend tout le comportement — memes pages, memes titres, meme total
de la periode, memes raccourcis, memes messages au demarrage, meme copie des
donnees a la fermeture — avec l'apparence de Pecule (theme_qt.py). Les pages
sont dans pages/. Elle se lance par app.py :

    py app.py
"""

from __future__ import annotations

import hashlib
import queue
import sys
import tempfile
import threading
import traceback
from datetime import date
from pathlib import Path

from PySide6.QtCore import QLockFile, Qt, QTimer
from PySide6.QtGui import (QAction, QGuiApplication, QIcon, QKeySequence,
                           QShortcut)
from PySide6.QtWidgets import (QApplication, QButtonGroup, QFileDialog,
                               QFrame, QHBoxLayout, QLabel, QMainWindow,
                               QMenu, QMessageBox, QProgressDialog, QPushButton,
                               QScrollArea, QVBoxLayout, QWidget)

import liens              # liens.AIDE_EN_LIGNE : « Votre avis », « Mise à jour »
import menu
import recharges          # pour lire recharges.DERNIERE_RESTAURATION
from constantes import SAISIE_TELEPHONE
if SAISIE_TELEPHONE:      # absent de l'exe public (voir constantes.py)
    import telephone      # bouton « 📱 Téléphone » (serveur mobile)
import sauvegarde_externe
import suivi_saisie
from composants import confirmer
from constantes import APP_NAME, APP_VERSION, chemin_ressource
from erreurs import erreur_en_clair
from filtres import annee_en_cours, filtrer_par_periode, mois_en_cours
from pages import CONSTRUCTEURS
from recharges import (assurer_ids, charger_donnees, dossier_donnees,
                       sauvegarder_donnees, synchroniser_github)
from formats import fmt_eur, fmt_nb_recharges
from theme_qt import (CREME, LARGEUR_BANDEAU, appliquer_theme,
                      installer_traduction_qt, theme_actif)


class FenetrePrincipale(QMainWindow):
    def __init__(self, accueil: bool = True):
        """`accueil=False` : ni message de bienvenue, ni avertissement sur
        les donnees au demarrage. Pour l'autotest, qui tourne sans personne
        devant l'ecran : une boite de message l'attendrait indefiniment."""
        super().__init__()
        self.setWindowTitle(f"{APP_NAME} — {APP_VERSION}")
        self.resize(1280, 800)
        # 1000x640 et non plus : la hauteur doit tenir sur un portable
        # 1366x768, une fois la barre des taches deduite.
        self.setMinimumSize(1000, 640)
        icone = chemin_ressource("icone_voiture.ico")
        if Path(icone).exists():
            self.setWindowIcon(QIcon(str(icone)))

        # Migration : ajouter des ids aux anciennes recharges. C'est aussi la
        # premiere lecture du fichier : si elle echoue, on le signale
        # clairement plutot que de laisser l'appli s'ouvrir a vide.
        self._erreur_chargement: str = ""
        try:
            n = assurer_ids()
            if n:
                print(f"[migration] {n} recharges ont reçu un id")
        except Exception as e:
            self._erreur_chargement = erreur_en_clair(e)
            print(f"[migration] erreur : {e}")

        self.vue_courante: str | None = None
        self._derniere_erreur: str = ""   # renseigne par _afficher_erreur
        # La page affichee, et la vue qu'elle montre (None : page d'erreur).
        self._page_affichee: QWidget | None = None
        self._vue_posee: str | None = None
        # Pages quittees avec une saisie en cours : gardees telles quelles
        # au lieu d'etre detruites, et remises en place au retour.
        self._pages_gardees: dict[str, QWidget] = {}
        # Une page = un bouton du bandeau, ou une ligne (QAction) du petit
        # menu « Comparer et exporter… » : les deux se cochent pareil.
        self.boutons_nav: dict[str, QPushButton | QAction] = {}
        # Dossier choisi pour la derniere sauvegarde externe, repropose tant
        # que l'application reste ouverte.
        self._destination_sauvegarde: str = ""
        # Filtres des pages. Periode a l'ouverture : le mois en cours, ou
        # l'annee pour les Statistiques (leur graphique compare les mois).
        # Rien n'est memorise d'un lancement a l'autre : impossible de
        # rouvrir sur un mois passe en le prenant pour le mois courant.
        self.filtre_historique: str = "Tout"
        # Sans recharge ce mois-ci (un 1er du mois, un nouvel utilisateur) :
        # « Toute la periode » plutot qu'un ecran vide (charte, 08/10/2026).
        ouverture = self._periode_d_ouverture()
        self.filtre_periode: str = ouverture
        self.recherche_historique: str = ""
        self.tri_historique: tuple[str, bool] = ("date", True)
        # La recharge a remettre en evidence quand l'Historique se reconstruit
        # (apres une modification ou une suppression).
        self.selection_historique: str | None = None
        # Le message « Relevé enregistré » du Kilometrage, affiche une fois
        # la page reconstruite.
        self.message_km: str = ""
        # De meme pour « Frais enregistrés » de la page Tarifs.
        self.message_frais: str = ""
        self.filtre_periode_stats: str = annee_en_cours()
        # La comparaison essence s'ouvre sur l'etat global (28/09/2026).
        self.filtre_periode_essence: str = "Tout"
        self.filtre_periode_dashboard: str = ouverture
        self.filtre_periode_export: str = "Tout"
        self.filtre_lieu_export: str = "Tout"

        centre = QWidget()
        disposition = QHBoxLayout(centre)
        disposition.setContentsMargins(0, 0, 0, 0)
        disposition.setSpacing(0)
        disposition.addWidget(self._construire_bandeau())
        disposition.addWidget(self._construire_principale(), 1)
        self.setCentralWidget(centre)

        self._installer_raccourcis()
        # La fenetre s'affiche tout de suite ; le tableau de bord est bati au
        # premier instant libre. Chaque action differee est ATTACHEE a la
        # fenetre (deuxieme argument) : si la fenetre disparait avant, l'action
        # est annulee au lieu de s'executer sur une fenetre detruite (ce qui
        # faisait planter Python dans les tests, 25/09/2026).
        QTimer.singleShot(0, self, lambda: self.afficher_vue("dashboard"))
        # Une fois la fenetre affichee : accueillir au premier demarrage, ou
        # prevenir si le fichier de donnees a du etre repare.
        if accueil:
            QTimer.singleShot(700, self, lambda: self._avertir_etat_donnees())

    # ---------- bandeau de gauche ----------

    def _construire_bandeau(self) -> QScrollArea:
        """Le bandeau de Pecule : nom de l'application, sections annoncees par
        un petit titre souligne, un bouton par page, les actions sous leur
        section, la version en pied.

        Place dans une zone qui defile, comme dans Pecule : sur un petit
        ecran, les derniers boutons restent atteignables au lieu d'etre
        ecrases."""
        bandeau = QFrame()
        bandeau.setObjectName("Bandeau")
        colonne = QVBoxLayout(bandeau)
        # 6 px au-dessus du nom, 4 sous la version, comme Pecule et le
        # Photovoltaique (11/10/2026 ; c'etait 2 en bas).
        colonne.setContentsMargins(10, 6, 10, 4)
        # 4 px entre deux boutons, comme Pecule et le Photovoltaique
        # (29/09/2026 ; c'etait 1 px, les boutons paraissaient colles).
        colonne.setSpacing(4)

        marque = QLabel(APP_NAME)
        marque.setObjectName("Marque")
        colonne.addWidget(marque)
        sous_marque = QLabel("Coût réel de vos recharges")
        sous_marque.setObjectName("SousMarque")
        colonne.addWidget(sous_marque)

        # Les pages : un seul bouton coche a la fois, celui de la page
        # affichee.
        self._groupe_nav = QButtonGroup(self)
        self._groupe_nav.setExclusive(True)

        # Le bouton qui ouvre le petit menu des pages occasionnelles. Il ne
        # mene a aucune page lui-meme : un clic deroule le menu. Il est
        # surligne quand l'une de ses pages est affichee.
        self.bouton_comparer = QPushButton("🗂️ Comparer et exporter…")
        self.bouton_comparer.setObjectName("EntreeMenu")
        # Moins de retrait a droite (theme_qt) : en gras, son libelle etait
        # coupe.
        self.bouton_comparer.setProperty("avecMenu", True)
        self.bouton_comparer.setCheckable(True)
        self.bouton_comparer.setCursor(Qt.PointingHandCursor)
        self.bouton_comparer.setToolTip(
            "Ce que vos kilomètres vous auraient coûté en essence, et "
            "l'export Excel ou PDF de vos recharges")
        self.menu_comparer = QMenu(self.bouton_comparer)
        self.menu_comparer.setToolTipsVisible(True)
        self.bouton_comparer.setMenu(self.menu_comparer)
        self._groupe_nav.addButton(self.bouton_comparer)

        for n, (nom_section, items) in enumerate(menu.SECTIONS):
            # Un peu d'air avant chaque titre : 6 px, 4 sous le nom de
            # l'appli, comme dans Pecule (11/10/2026 ; c'etait 1 px, faute de
            # place avant le regroupement « Comparer et exporter… »). Le
            # bandeau doit tenir sans defiler sur un portable 1366 x 768
            # (~689 px utiles) : a remesurer apres tout ajout au menu.
            colonne.addSpacing(4 if n == 0 else 6)
            titre = QLabel(nom_section)
            titre.setObjectName("TitreSection")
            colonne.addWidget(titre)
            # Des actions, pas des pages : hors de menu.SECTIONS, qui ne
            # decrit que des pages (tests/test_menu.py). Jamais cochees.
            # On sauvegarde avant de restaurer : l'action vient en tete.
            if nom_section == "MES DONNÉES":
                colonne.addWidget(self._bouton_action(
                    "💾 Sauvegarde externe", self._sauvegarder_externe,
                    "Copie vos recharges et vos réglages sur une clé USB ou "
                    "un disque externe, dans un dossier daté, et vérifie la "
                    "copie"))
            for vue_id, texte, picto in items:
                if vue_id in menu.COMPARER_ET_EXPORTER:
                    # Une ligne du petit menu ; son bouton prend place dans
                    # le bandeau a la premiere ligne.
                    if not self.menu_comparer.actions():
                        colonne.addWidget(self.bouton_comparer)
                    action = self.menu_comparer.addAction(f"{picto} {texte}")
                    action.setCheckable(True)
                    action.setToolTip(menu.TITRES[vue_id][1])
                    action.triggered.connect(
                        lambda _=False, v=vue_id: self.afficher_vue(v))
                    self.boutons_nav[vue_id] = action
                    continue
                # Une espace apres l'emoji, comme les deux autres applis.
                bouton = QPushButton(f"{picto} {texte}")
                bouton.setObjectName("EntreeMenu")
                # L'infobulle d'une page : le sous-titre qu'elle affiche en
                # tete (11/10/2026, comme les lignes du petit menu).
                bouton.setToolTip(menu.TITRES[vue_id][1])
                bouton.setCheckable(True)
                bouton.setCursor(Qt.PointingHandCursor)
                bouton.clicked.connect(
                    lambda _=False, v=vue_id: self.afficher_vue(v))
                self._groupe_nav.addButton(bouton)
                self.boutons_nav[vue_id] = bouton
                colonne.addWidget(bouton)
            if (nom_section == "RÉGLAGES" and SAISIE_TELEPHONE
                    and telephone.jeton_mobile(dossier_donnees())):
                # Seulement si le serveur mobile a deja tourne sur ces
                # donnees (22/10/2026) : sans lui, le bouton n'aurait rien a
                # montrer. Un utilisateur sans serveur mobile ne le voit pas.
                colonne.addWidget(self._bouton_action(
                    "📱 Téléphone", self._ouvrir_telephone,
                    "Le QR code à scanner pour saisir une recharge depuis le "
                    "téléphone, et l'état du serveur (le relancer s'il est "
                    "arrêté)"))
            if nom_section == "AIDE" and liens.AIDE_EN_LIGNE:
                # L'ordre de Pecule : Notice, Votre avis, Mise a jour.
                # Masques tant que l'application n'est pas publiee (liens.py).
                # Infobulles des trois actions : les mêmes que dans Pécule
                # (ménage du bandeau, 11/10/2026 ; elles manquaient ici).
                colonne.addWidget(self._bouton_action(
                    "💬 Votre avis", self._ouvrir_avis,
                    "Signaler un problème ou proposer une idée "
                    "(questionnaire en ligne, dans votre navigateur)"))
                colonne.addWidget(self._bouton_action(
                    "🔄 Mise à jour", self._ouvrir_mise_a_jour,
                    "Voir s'il existe une version plus récente (la page "
                    "s'ouvre dans votre navigateur ; rien n'est vérifié "
                    "automatiquement)"))

        colonne.addStretch(1)
        # La version en pied : utile pour une capture d'ecran ou un rapport
        # de bug, mais on ne la lit pas tous les jours.
        version = QLabel(APP_VERSION)
        version.setObjectName("Version")
        colonne.addWidget(version)

        defilement = QScrollArea()
        defilement.setWidget(bandeau)
        defilement.setWidgetResizable(True)
        defilement.setFrameShape(QFrame.NoFrame)
        defilement.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        defilement.setFixedWidth(LARGEUR_BANDEAU)
        return defilement

    def _bouton_action(self, texte: str, commande,
                       infobulle: str) -> QPushButton:
        """Un bouton du menu qui lance une action au lieu d'ouvrir une page :
        meme allure que les autres, mais il ne reste jamais coche. Son
        libelle ne dit pas tout : l'infobulle le complete."""
        bouton = QPushButton(texte)
        bouton.setObjectName("ActionMenu")
        bouton.setToolTip(infobulle)
        bouton.setCursor(Qt.PointingHandCursor)
        bouton.clicked.connect(commande)
        return bouton

    # ---------- zone principale ----------

    def _construire_principale(self) -> QWidget:
        zone = QWidget()
        zone.setObjectName("ZonePrincipale")
        # Sans cela, un QWidget simple ignore le fond donne par la feuille
        # de style.
        zone.setAttribute(Qt.WA_StyledBackground, True)
        colonne = QVBoxLayout(zone)
        colonne.setContentsMargins(24, 18, 24, 0)
        colonne.setSpacing(10)

        # En-tete : titre et sous-titre a gauche, puis le bouton
        # « Sauvegarder » et la tuile du total a droite.
        entete = QHBoxLayout()
        titres = QVBoxLayout()
        titres.setSpacing(0)
        self.titre_vue = QLabel("")
        self.titre_vue.setObjectName("TitrePage")
        self.sous_titre_vue = QLabel("")
        self.sous_titre_vue.setObjectName("SousTitrePage")
        titres.addWidget(self.titre_vue)
        titres.addWidget(self.sous_titre_vue)
        entete.addLayout(titres, 1)

        # Envoi manuel vers GitHub, sans attendre la fermeture. Le bouton
        # n'existe que si les donnees vivent dans un depot git : proposer une
        # « sauvegarde GitHub » a qui n'en a pas ne fait qu'inquieter.
        self.bouton_sauver = None
        if recharges.sauvegarde_cloud_configuree():
            self.bouton_sauver = QPushButton("Sauvegarder")
            self.bouton_sauver.setToolTip(
                "Envoyer maintenant une copie de vos données vers GitHub "
                "(Ctrl+S)")
            self.bouton_sauver.clicked.connect(self._sauvegarder_maintenant)
            entete.addWidget(self.bouton_sauver, 0, Qt.AlignVCenter)

        tuile = QFrame()
        tuile.setObjectName("TuileTotal")
        tuile.setMinimumWidth(190)
        dans_tuile = QVBoxLayout(tuile)
        dans_tuile.setContentsMargins(12, 6, 12, 8)
        dans_tuile.setSpacing(0)
        # Le titre change selon la periode choisie (voir _maj_bilan).
        self.bilan_titre = QLabel("DÉPENSE · DEPUIS LE DÉBUT")
        self.bilan_titre.setObjectName("TotalLibelle")
        self.bilan_valeur = QLabel("0,00\xa0€")
        self.bilan_valeur.setObjectName("TotalValeur")
        dans_tuile.addWidget(self.bilan_titre)
        dans_tuile.addWidget(self.bilan_valeur)
        entete.addWidget(tuile)
        colonne.addLayout(entete)

        # Les pages defilent dans cette zone.
        self.zone_page = QScrollArea()
        self.zone_page.setObjectName("ZonePage")
        self.zone_page.setWidgetResizable(True)
        self.zone_page.setFrameShape(QFrame.NoFrame)
        colonne.addWidget(self.zone_page, 1)
        return zone

    # ---------- navigation ----------

    def _poser_page(self, contenu: QWidget, vue: str | None = None) -> None:
        """Met `contenu` dans la zone qui defile, a la place de l'ancienne
        page (voir _installer)."""
        enveloppe = QWidget()
        enveloppe.setObjectName("ContenuPage")
        enveloppe.setAttribute(Qt.WA_StyledBackground, True)
        disposition = QVBoxLayout(enveloppe)
        disposition.setContentsMargins(0, 4, 4, 20)
        disposition.addWidget(contenu)
        # Seules les pages de saisie sont suivies : une recherche dans
        # l'Historique n'est pas une donnee a enregistrer.
        if vue in menu.PAGES_DE_SAISIE:
            suivi_saisie.suivre(contenu)
        self._installer(enveloppe, vue)
        self.zone_page.verticalScrollBar().setValue(0)

    def _installer(self, enveloppe: QWidget, vue: str | None) -> None:
        """Remplace la page affichee par `enveloppe`.

        Qt detruit l'ancienne page au passage (setWidget) -- sauf si on
        quitte une page qui porte une saisie non enregistree : elle est
        alors retiree intacte et gardee, pour etre remise au retour. Avant,
        aller voir une autre page effacait la recharge ou le reglage tape."""
        ancienne = self.zone_page.widget()
        if (ancienne is not None and self._vue_posee is not None
                and self._vue_posee != vue
                and suivi_saisie.a_des_saisies(ancienne)):
            self._pages_gardees[self._vue_posee] = self.zone_page.takeWidget()
        self.zone_page.setWidget(enveloppe)
        self._page_affichee = enveloppe
        self._vue_posee = vue

    def saisies_en_attente(self) -> list[str]:
        """Les vues qui portent des valeurs tapees et non enregistrees."""
        vues = []
        if (self._vue_posee is not None
                and suivi_saisie.a_des_saisies(self.zone_page.widget())):
            vues.append(self._vue_posee)
        vues += [v for v, page in self._pages_gardees.items()
                 if v not in vues and suivi_saisie.a_des_saisies(page)]
        return vues

    def recharger_page(self, vue: str, garder_saisie: bool = False) -> None:
        """Reconstruit la page apres une action qui en change le contenu
        (releve enregistre ou supprime, frais ajoutes...), meme si une
        saisie y est en cours : c'est la page qui le demande.

        `garder_saisie` : l'action ne venait pas du formulaire (une ligne
        corrigee ou supprimee avec ses boutons). Ce qui etait tape dans le
        formulaire, pas encore enregistre, est alors remis dans la page
        reconstruite ; avant, il etait efface sans un mot (second audit du
        16/10/2026). Apres l'enregistrement du formulaire lui-meme, il doit
        au contraire repartir vide : `garder_saisie` reste a False."""
        releve = {}
        if garder_saisie and vue == self._vue_posee:
            releve = suivi_saisie.relever(self.zone_page.widget())
        self.afficher_vue(vue, forcer=True)
        if releve and vue == self._vue_posee:
            suivi_saisie.remettre(self.zone_page.widget(), releve)

    @staticmethod
    def _periode_d_ouverture() -> str:
        """Le mois en cours s'il a des recharges, sinon « Tout »."""
        try:
            toutes = charger_donnees()["recharges"]
        except Exception:
            return mois_en_cours()
        return mois_en_cours() if filtrer_par_periode(
            toutes, mois_en_cours()) else "Tout"

    def afficher_vue(self, vue: str, forcer: bool = False) -> None:
        """Affiche la page `vue`, reconstruite depuis les fichiers.

        Sans `forcer`, une page qui porte une saisie non enregistree n'est
        pas reconstruite : recliquer sur la page ouverte ou F5 la laisse
        telle quelle, et une page gardee au depart est remise au retour."""
        self.vue_courante = vue
        # La page affichee : bouton coche (fond bleu pale, texte gras).
        bouton = self.boutons_nav.get(vue)
        if bouton is not None:
            bouton.setChecked(True)
        # Le petit menu « Comparer et exporter… » : sa ligne cochee, et son
        # bouton surligne, seulement pour l'une de ses pages. Une autre page
        # cochee ci-dessus a deja libere le bouton (groupe exclusif).
        for v in menu.COMPARER_ET_EXPORTER:
            self.boutons_nav[v].setChecked(v == vue)
        if vue in menu.COMPARER_ET_EXPORTER:
            self.bouton_comparer.setChecked(True)

        try:
            self._maj_bilan()
        except Exception as e:
            print(f"[bilan] {e}")
        # Apres une saisie, la page est reaffichee : c'est le moment de dire
        # si l'enregistrement s'est fait sans copie de secours.
        if recharges.ECHEC_BACKUP:
            QTimer.singleShot(0, self, self._signaler_echec_backup)

        titre, sous_titre = menu.TITRES.get(vue, (vue, ""))
        self.titre_vue.setText(titre)
        self.sous_titre_vue.setText(sous_titre)

        if forcer:
            gardee = self._pages_gardees.pop(vue, None)
            if gardee is not None:
                gardee.deleteLater()
        else:
            if (vue == self._vue_posee
                    and suivi_saisie.a_des_saisies(self.zone_page.widget())):
                return
            gardee = self._pages_gardees.pop(vue, None)
            if gardee is not None:
                self._installer(gardee, vue)
                return

        constructeur = CONSTRUCTEURS.get(vue)
        if constructeur is None:
            return
        try:
            # La page recoit la fenetre.
            self._poser_page(constructeur(self), vue)
        except Exception as e:
            self._afficher_erreur(e)

    def changer_periode(self, attribut: str, valeur: str) -> None:
        """Une page a change de periode : on range la valeur dans le filtre
        de cette page (`filtre_periode_dashboard`...), puis on la
        reconstruit.

        La reconstruction attend le prochain instant libre : elle detruit la
        barre de periode qui vient d'annoncer le changement, et detruire un
        objet pendant qu'il emet son signal peut faire planter le programme."""
        setattr(self, attribut, valeur)
        vue = self.vue_courante
        QTimer.singleShot(0, self, lambda: self.afficher_vue(vue))

    def _afficher_erreur(self, e: Exception) -> None:
        """Affiche une erreur a la place de la page, sans noyer l'utilisateur.

        Le detail technique (la « pile d'appels » de Python) est
        indispensable pour diagnostiquer, mais il n'a aucun sens pour qui se
        sert simplement de l'application : il est donc replie par defaut, et
        copiable en un clic pour etre transmis tel quel."""
        # Pour le diagnostic (autotest) : le nom technique de l'erreur.
        self._derniere_erreur = traceback.format_exception_only(e)[-1].strip()
        detail = traceback.format_exc()

        bloc = QFrame()
        bloc.setObjectName("BlocErreur")
        colonne = QVBoxLayout(bloc)
        colonne.setContentsMargins(18, 14, 18, 14)
        titre = QLabel("CETTE PAGE N'A PAS PU S'AFFICHER")
        titre.setObjectName("TitreErreur")
        colonne.addWidget(titre)
        # erreur_en_clair : une erreur de Python (en anglais) devient une
        # phrase en français ; le détail technique reste replié plus bas.
        for texte in (erreur_en_clair(e),
                      "Vos données ne sont pas en cause : rien n'a été "
                      "modifié. Essayez une autre page, ou redémarrez "
                      "l'application."):
            etiquette = QLabel(texte)
            etiquette.setObjectName("TexteErreur")
            etiquette.setWordWrap(True)
            colonne.addWidget(etiquette)

        # Cree mais cache : c'est le bouton ci-dessous qui le deplie.
        trace = QLabel(detail)
        trace.setObjectName("Trace")
        trace.setWordWrap(True)
        trace.setTextInteractionFlags(Qt.TextSelectableByMouse)
        trace.setVisible(False)

        rangee = QHBoxLayout()
        bouton_detail = QPushButton("Afficher le détail technique")
        bouton_copier = QPushButton("Copier le détail technique")

        def basculer():
            trace.setVisible(not trace.isVisible())
            bouton_detail.setText("Masquer le détail technique"
                                  if trace.isVisible()
                                  else "Afficher le détail technique")

        def copier():
            QGuiApplication.clipboard().setText(detail)
            bouton_copier.setText("Copié !")
            QTimer.singleShot(1500, bouton_copier, lambda: bouton_copier.setText(
                "Copier le détail technique"))

        bouton_detail.clicked.connect(basculer)
        bouton_copier.clicked.connect(copier)
        rangee.addWidget(bouton_detail)
        rangee.addWidget(bouton_copier)
        rangee.addStretch(1)
        colonne.addLayout(rangee)
        colonne.addWidget(trace)

        page = QWidget()
        disposition = QVBoxLayout(page)
        disposition.setContentsMargins(0, 0, 0, 0)
        disposition.addWidget(bloc)
        disposition.addStretch(1)
        self._poser_page(page)

    def _maj_bilan(self) -> None:
        """Affiche dans la tuile du total la depense de la periode choisie
        dans la page affichee (tableau de bord, historique ou statistiques).
        Sur les autres pages, on retombe sur le total general."""
        data = charger_donnees()
        periodes_par_vue = {
            "dashboard": self.filtre_periode_dashboard,
            "historique": self.filtre_periode,
            "stats": self.filtre_periode_stats,
            "essence": self.filtre_periode_essence,
        }
        periode = periodes_par_vue.get(self.vue_courante, "Tout")
        selection = filtrer_par_periode(data["recharges"], periode)
        total = sum(r.get("cout_eur", 0) for r in selection)
        # La tuile dit toujours sur quelle periode porte son chiffre :
        # « Total dépense » ne disait pas qu'il changeait d'une page a
        # l'autre (audit de design du 03/10/2026).
        quand = "depuis le début" if periode == "Tout" else periode
        self.bilan_titre.setText(f"DÉPENSE · {quand.upper()}")
        self.bilan_valeur.setText(fmt_eur(total))

    # ---------- raccourcis ----------

    def _installer_raccourcis(self) -> None:
        """Raccourcis valables partout dans la fenetre, quel que soit le
        champ qui a le curseur."""
        for touches, action in (
                ("Ctrl+S", self._sauvegarder_maintenant),
                ("Ctrl+F", self._aller_a_la_recherche),
                # Les touches de fonction evitent d'entrer en conflit avec
                # la saisie.
                ("F5", lambda: self.afficher_vue(self.vue_courante
                                                 or "dashboard"))):
            raccourci = QShortcut(QKeySequence(touches), self)
            raccourci.activated.connect(action)

    def _aller_a_la_recherche(self) -> None:
        """Ctrl+F : ouvre l'Historique et place le curseur dans la recherche."""
        if self.vue_courante != "historique":
            self.afficher_vue("historique")
        champ = getattr(self, "champ_recherche", None)
        if champ is not None:
            champ.setFocus()

    # ---------- demarrage ----------

    def _accueillir(self) -> None:
        """Premier demarrage : dire l'essentiel, puis ouvrir la page Tarifs.

        Sans grille tarifaire, l'application ne sait rien calculer : autant
        y conduire l'utilisateur plutot que de le laisser buter dessus a sa
        premiere recharge."""
        QMessageBox.information(
            self, f"Bienvenue dans {APP_NAME}",
            "Cette application suit ce que vous coûtent réellement les "
            "recharges de votre voiture électrique.\n\n"
            "Avant tout, elle a besoin de connaître VOS prix : la page "
            "« Tarifs » va s'ouvrir, ajoutez-y une période avec le prix du "
            "kWh de votre contrat d'électricité (et vos heures creuses si "
            "vous en avez). Sans cela, aucun coût ne peut être calculé.\n\n"
            "Vos données seront enregistrées sur ce PC, dans :\n"
            f"{dossier_donnees()}\n\n"
            "La page « Notice », en bas du menu, explique le reste.")
        self.afficher_vue("tarifs")

    def _avertir_etat_donnees(self) -> None:
        """Accueille au premier demarrage, ou signale un probleme de donnees."""
        # Un tarifs.json disparu a ete decouvert par le tableau de bord, qui
        # lit la grille des l'ouverture (premier demarrage, ou fichier perdu).
        if recharges.PREMIER_DEMARRAGE:
            self._accueillir()
            return
        self._avertir_tarifs_disparus()

        info = recharges.DERNIERE_RESTAURATION
        if info:
            quand = info["date_backup"].strftime("%d/%m/%Y à %H:%M")
            # Deux causes : un fichier abime, ou un fichier disparu d'un
            # dossier deja utilise (audit du 14/10/2026).
            if info.get("cause") == "absent":
                constat = ("Le fichier de vos recharges avait disparu du "
                           "dossier des données (déplacé ou supprimé par "
                           "erreur ?).\n\n")
            else:
                constat = (
                    "Le fichier de vos recharges était illisible au démarrage "
                    "(coupure de courant pendant une sauvegarde, disque "
                    "plein...).\n\n")
            texte = (
                constat +
                f"Il a été remplacé par la sauvegarde du {quand}, "
                f"qui contient {fmt_nb_recharges(info['n_recharges'])}.\n\n"
                "Les recharges saisies APRÈS cette date sont peut-être à "
                "ressaisir : vérifiez vos dernières lignes dans l'Historique.")
            if info["mis_de_cote"]:
                texte += ("\n\nLe fichier abîmé a été conservé sous le nom "
                          f"{info['mis_de_cote']}, dans le dossier des données.")
            # Remettre tout de suite le fichier d'aplomb : sans cela il reste
            # illisible tant qu'on n'enregistre rien, et la reparation
            # recommencerait a chaque demarrage.
            try:
                sauvegarder_donnees(charger_donnees())
                texte += "\n\nLe fichier de travail a été remis en état."
            except Exception as e:
                texte += ("\n\nLe fichier n'a pas pu être remis en état. "
                          + erreur_en_clair(e))
            QMessageBox.warning(self, "Données réparées", texte)
            return

        if self._erreur_chargement:
            QMessageBox.critical(
                self, "Données illisibles",
                "Le fichier de vos recharges n'a pas pu être lu, et aucune "
                "sauvegarde n'a pu le remplacer.\n\n"
                f"Détail : {self._erreur_chargement}\n\n"
                "Vos sauvegardes se trouvent dans :\n"
                f"{dossier_donnees() / 'backups'}\n\n"
                "N'enregistrez rien avant d'avoir restauré une sauvegarde "
                "(page « Restaurer une sauvegarde », à gauche), sinon le fichier sera écrasé.")

    def _signaler_echec_backup(self) -> None:
        """La copie de secours d'avant un enregistrement a echoue : le dire
        une fois (audit du 14/10/2026 ; l'echec n'allait qu'a la console,
        invisible dans la version .exe)."""
        detail = recharges.ECHEC_BACKUP
        if not detail:
            return
        recharges.ECHEC_BACKUP = None
        QMessageBox.warning(
            self, "Copie de secours impossible",
            "Votre saisie est bien enregistrée, mais la copie de secours "
            "faite juste avant n'a pas pu être créée dans le dossier :\n"
            f"{dossier_donnees() / 'backups'}\n\n{detail}\n\n"
            "Tant que ce problème dure, une erreur ne pourra pas être "
            "annulée par « Restaurer une sauvegarde ». Vérifiez que le "
            "disque n'est pas plein et que ce dossier n'est pas protégé.")

    def _avertir_tarifs_disparus(self) -> None:
        """tarifs.json avait disparu : dire ce qui a ete remis en place, ou
        qu'il faut ressaisir ses prix. Ce n'est pas un premier demarrage."""
        incident = recharges.INCIDENT_TARIFS
        if not incident:
            return
        if incident["copie"]:
            quand = incident["date"].strftime("%d/%m/%Y à %H:%M")
            QMessageBox.warning(
                self, "Tarifs remis en place",
                "Le fichier de vos tarifs (tarifs.json) avait disparu.\n\n"
                f"Il a été remplacé par sa copie du {quand} "
                f"({incident['copie']}).\n\n"
                "Vérifiez vos prix dans la page « Tarifs » : une modification "
                "faite après cette date est peut-être à refaire.")
        else:
            QMessageBox.warning(
                self, "Tarifs introuvables",
                "Le fichier de vos tarifs (tarifs.json) a disparu, et aucune "
                "copie n'a été trouvée.\n\n"
                "Vos recharges sont intactes, avec leurs montants. Ressaisissez "
                "vos prix dans la page « Tarifs » avant d'en ajouter de "
                "nouvelles.")
        self.afficher_vue("tarifs")

    # ---------- sauvegardes ----------

    def _noms_des_pages(self, vues: list[str]) -> str:
        """« Ajouter une recharge », « Paramètres » : pour les messages."""
        return ", ".join(f"« {menu.TITRES.get(v, (v, ''))[0]} »" for v in vues)

    def _sauvegarder_maintenant(self) -> None:
        """Ctrl+S ou bouton « Sauvegarder » : envoie les donnees vers GitHub
        sans attendre la fermeture."""
        # Ctrl+S n'enregistre pas le formulaire affiche : il envoie ce qui est
        # deja enregistre. Avant, il laissait croire que la recharge tapee
        # l'etait ; elle se perdait ensuite au changement de page.
        # Sans depot git (le cas de presque tous les utilisateurs), Ctrl+S
        # ne parle ni de git ni de depot : c'est un reflexe de beaucoup de
        # gens, on lui repond avec leurs mots (analyse « nouvel
        # utilisateur » du 19/10/2026).
        avec_depot = recharges.sauvegarde_cloud_configuree()
        attente = self.saisies_en_attente()
        if attente:
            if avec_depot:
                debut = ("Ctrl+S n'enregistre pas ce que vous venez de "
                         "taper : il envoie vers votre dépôt les données "
                         "déjà enregistrées.\n\n")
                fin = ", puis refaites Ctrl+S si vous voulez les envoyer."
            else:
                debut = ("Ctrl+S n'enregistre pas ce que vous venez de "
                         "taper.\n\n")
                fin = "."
            QMessageBox.information(
                self, "Pas encore enregistré",
                debut + "Des valeurs tapées dans "
                f"{self._noms_des_pages(attente)} ne sont pas encore "
                "enregistrées. Cliquez sur le bouton « Enregistrer… » de la "
                "page (ou appuyez sur Entrée dans une case)" + fin)
            self.afficher_vue(attente[0])
            return
        if not avec_depot:
            QMessageBox.information(
                self, "Rien d'autre à faire",
                "Tout ce que vous avez enregistré avec les boutons de "
                "l'application est déjà gardé sur ce PC : Ctrl+S n'est pas "
                "nécessaire.\n\n"
                "Une copie de secours est faite toute seule avant chaque "
                "modification. Pour garder aussi une copie ailleurs (clé "
                "USB, disque externe), utilisez « 💾 Sauvegarde externe » "
                "dans le menu de gauche.")
            return

        def fini(ok: bool, msg: str) -> None:
            if ok:
                QMessageBox.information(self, "Sauvegarde GitHub", msg)
            else:
                QMessageBox.warning(
                    self, "Sauvegarde GitHub",
                    f"{msg}\n\nVos données restent enregistrées sur ce PC.")

        self._lancer_sync_github("Sauvegarde des données vers GitHub...", fini)

    def _lancer_sync_github(self, texte_attente: str, quand_fini) -> None:
        """Envoie les donnees vers GitHub dans un fil d'execution separe.

        Le « git push » peut durer jusqu'a 60 secondes : lance sur le fil de
        l'interface, il figerait la fenetre (« Ne repond pas »). Le travail
        se fait a cote ; le resultat revient par une file d'attente, lue
        toutes les 100 ms sur le fil de l'interface — le seul qui ait le
        droit de toucher aux fenetres."""
        attente = QProgressDialog(texte_attente, "", 0, 0, self)
        attente.setWindowTitle("Sauvegarde")
        attente.setCancelButton(None)        # on ne peut pas l'interrompre
        attente.setWindowModality(Qt.WindowModal)
        attente.setMinimumDuration(0)
        attente.show()
        resultat: queue.Queue = queue.Queue()

        def travail():
            # synchroniser_github() ne leve jamais d'exception, mais on ne
            # laisse rien passer : sans reponse, la surveillance tournerait
            # indefiniment.
            try:
                resultat.put(synchroniser_github())
            except Exception as e:
                resultat.put((False, erreur_en_clair(e)))

        threading.Thread(target=travail, daemon=True).start()

        def surveiller():
            try:
                ok, msg = resultat.get_nowait()
            except queue.Empty:
                QTimer.singleShot(100, self, surveiller)
                return
            attente.close()
            quand_fini(ok, msg)

        surveiller()

    def _sauvegarder_externe(self) -> None:
        """Copie les donnees sur une cle USB ou un disque choisi par
        l'utilisateur. La copie et sa verification : sauvegarde_externe.py."""
        choisi = QFileDialog.getExistingDirectory(
            self, "Choisissez la clé USB ou le disque où sauvegarder",
            self._destination_sauvegarde)
        if not choisi:
            return                      # l'utilisateur a renonce
        dossier = dossier_donnees()
        fichiers = [dossier / "recharges.json", dossier / "tarifs.json"]
        try:
            cible, copies = sauvegarde_externe.sauvegarder(
                fichiers, Path(choisi), dossier, APP_NAME, APP_VERSION)
        except sauvegarde_externe.SauvegardeImpossible as e:
            QMessageBox.warning(self, "Sauvegarde impossible",
                                erreur_en_clair(e))
            return
        self._destination_sauvegarde = choisi
        # Retenue pour le rappel du tableau de bord (28/09/2026). Apres la
        # copie : la sauvegarde elle-meme porte l'etat d'avant. Un echec
        # d'ecriture ne gache pas la sauvegarde, qui est faite et verifiee.
        try:
            recharges.enregistrer_config({"sauvegarde_externe_derniere":
                                          date.today().isoformat()})
        except (OSError, ValueError):
            pass
        liste = "\n".join(f"  • {nom}" for nom in copies)
        QMessageBox.information(
            self, "Sauvegarde terminée",
            (f"{len(copies)} fichiers copiés et vérifiés"
             if len(copies) > 1 else "1 fichier copié et vérifié")
            + f" dans :\n{cible}\n\n"
            f"{liste}\n\nPour la remettre en service un jour, suivez le "
            "fichier LISEZMOI.txt placé à côté.")

    def closeEvent(self, evenement) -> None:
        """A la fermeture : copie des donnees dans le sous-dossier
        « Sauvegardes » du dossier des donnees (si elles ont change).

        Rien ne part vers GitHub a la fermeture (decision du 24/09/2026) :
        seul le bouton « Sauvegarder » (Ctrl+S) le fait, a la demande. En cas
        d'echec, un avertissement s'affiche ; cet echec ne bloque pas la
        fermeture.

        Des valeurs tapees et non enregistrees : on pose d'abord la question
        (« Annuler » par defaut, qui ramene a la page). Avant, elles se
        perdaient sans un mot."""
        attente = self.saisies_en_attente()
        if attente:
            # Boutons nommes (audit du 08/10/2026) : Qt traduit « Discard »
            # par « Ne pas tenir compte », qui ne dit pas ce qu'on perd.
            if not confirmer(
                    self, "Saisie non enregistrée",
                    f"Des valeurs tapées dans {self._noms_des_pages(attente)} "
                    "ne sont pas encore enregistrées.\n\n"
                    "Fermer quand même ? Elles seront perdues.",
                    action="Fermer sans enregistrer",
                    garder="Revenir à la saisie"):
                evenement.ignore()
                self.afficher_vue(attente[0])
                return
        dossier = dossier_donnees()
        try:
            sauvegarde_externe.sauvegarder_a_la_fermeture(
                [dossier / "recharges.json", dossier / "tarifs.json"],
                dossier, APP_NAME, APP_VERSION)
        except Exception as e:
            QMessageBox.warning(
                self, "Sauvegarde à la fermeture",
                "La copie dans le dossier « Sauvegardes » a échoué.\n"
                f"{erreur_en_clair(e)}\n\n"
                "Vos données restent enregistrées sur ce PC.")
        evenement.accept()

    def _ouvrir_telephone(self) -> None:
        from fenetre_telephone import FenetreTelephone
        FenetreTelephone(self, dossier_donnees()).exec()

    # ---------- aide ----------

    def _ouvrir_mise_a_jour(self) -> None:
        from fenetres_aide import FenetreMiseAJour
        FenetreMiseAJour(self).exec()

    def _ouvrir_avis(self) -> None:
        from fenetres_aide import FenetreAvis
        FenetreAvis(self).exec()


def _identifiant_windows() -> None:
    """Donne a l'application sa propre entree dans la barre des taches :
    sans cela, Windows la range sous l'icone de Python."""
    try:
        import ctypes
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
            "andre12230.RechargesVE")
    except Exception:
        pass


def autotest(chemin_rapport: str) -> int:
    """Ouvre chaque page et teste les exports, sans intervention, puis ferme.

    Sert a verifier l'application RECONSTRUITE en .exe : un simple demarrage
    ne prouve pas que le graphique des statistiques (matplotlib), l'export
    Excel (openpyxl) ou le PDF (reportlab) fonctionnent encore, car ces
    morceaux ne sont charges qu'a l'usage. Le compte rendu est ecrit dans un
    fichier : l'exe n'a pas de console.

    Il tourne sur un JEU DE DEMONSTRATION fige, pas sur vos donnees : sur
    une machine neuve, un fichier vide ferait afficher « aucune donnee »
    partout sans rien prouver. Ajoutez --donnees-reelles pour le lancer sur
    vos vraies donnees.

        Recharges-VE.exe --autotest C:\\chemin\\rapport.txt

    Rend 0 si tout va bien, 1 sinon."""
    from export import exporter_excel, exporter_pdf

    lignes = []
    if "--donnees-reelles" in sys.argv:
        lignes.append("données        : les vôtres")
    else:
        demo = Path(tempfile.mkdtemp(prefix="autotest_demo_"))
        recharges.ecrire_jeu_demo(demo)
        recharges.rediriger_donnees(demo)
        lignes.append("données        : jeu de démonstration")

    application = QApplication.instance() or QApplication(sys.argv)
    traduit = installer_traduction_qt(application)
    appliquer_theme(application)
    fenetre = FenetrePrincipale(accueil=False)
    fenetre.show()
    application.processEvents()
    soucis = 0
    for vue in menu.pages():
        fenetre._derniere_erreur = ""
        try:
            fenetre.afficher_vue(vue)
            application.processEvents()
            souci = fenetre._derniere_erreur
        except Exception as e:
            souci = traceback.format_exception_only(e)[-1].strip()
        soucis += bool(souci)
        lignes.append(f"vue {vue:<11} : {souci or 'OK'}")

    dossier = Path(tempfile.mkdtemp(prefix="autotest_"))
    echantillon = charger_donnees()["recharges"][:30]
    for nom, fonction, extension in (("export Excel", exporter_excel, ".xlsx"),
                                     ("export PDF", exporter_pdf, ".pdf")):
        try:
            cible = fonction(echantillon, dossier / f"test{extension}",
                             "autotest")
            lignes.append(f"{nom:<15}: OK ({Path(cible).stat().st_size} "
                          "octets)")
        except Exception as e:
            soucis += 1
            detail = traceback.format_exception_only(e)[-1].strip()
            lignes.append(f"{nom:<15}: {detail}")

    # Les fichiers livres a cote du programme : sans eux, l'icone ou la
    # fleche des listes manquent sans aucune erreur.
    manquants = [nom for nom in ("icone_voiture.ico", "fleche_bas.svg",
                                 "fleche_bas_sombre.svg")
                 if not chemin_ressource(nom).is_file()]
    soucis += bool(manquants)
    lignes.append("fichiers joints: " + ("OK" if not manquants else
                                         "MANQUANTS " + ", ".join(manquants)))
    # Le thème choisi (clair de Pécule, ou sombre), quel que soit le
    # réglage de Windows.
    fond = application.palette().window().color().name().upper()
    attendu = fond == CREME.upper()
    soucis += not attendu
    nom_theme = ("clair (Pécule)" if theme_actif() == "clair"
                 else "sombre")
    lignes.append("thème          : " + (nom_theme if attendu
                                          else f"INATTENDU ({fond})"))
    lignes.append("boutons Qt     : "
                  + ("en français" if traduit else "EN ANGLAIS (qtbase_fr absent)"))
    lignes.append(f"recharges lues : {len(charger_donnees()['recharges'])}")
    Path(chemin_rapport).write_text("\n".join(lignes) + "\n",
                                    encoding="utf-8")
    fenetre.hide()
    fenetre.deleteLater()
    return 1 if soucis else 0


def verrou_instance_unique(dossier: Path) -> QLockFile | None:
    """Le verrou « une seule fenetre sur ces donnees », ou None s'il est pris.

    Sans lui, rien n'empechait d'ouvrir l'application deux fois (double-clic
    repete sur l'icone). Chaque fenetre gardait sa propre copie des donnees
    en memoire et reecrivait le fichier entier a partir d'elle : la recharge
    ajoutee dans l'une disparaissait des que l'autre enregistrait (v2.0.0 et
    avant).

    Le verrou est un petit fichier du dossier temporaire de Windows, nomme
    d'apres le dossier des donnees : deux dossiers differents (l'autotest sur
    son jeu de demonstration) restent independants. Il se libere a la
    fermeture ; apres un plantage, Qt le reconnait comme perime (le
    programme qui l'avait pose n'existe plus) et le reprend."""
    empreinte = hashlib.sha1(
        str(Path(dossier).resolve()).lower().encode("utf-8")).hexdigest()[:12]
    verrou = QLockFile(str(Path(tempfile.gettempdir())
                           / f"recharges-ve-{empreinte}.verrou"))
    # 0 : jamais perime par anciennete, seulement si son programme a disparu.
    # L'application reste ouverte des heures : l'anciennete ne prouve rien.
    verrou.setStaleLockTime(0)
    return verrou if verrou.tryLock(0) else None


def main() -> int:
    if "--autotest" in sys.argv:
        return autotest(sys.argv[sys.argv.index("--autotest") + 1])
    _identifiant_windows()
    # Deja creee si la question Clair / Sombre du premier lancement a ete
    # posee (premier_theme.py) : on la reprend, Qt n'en accepte qu'une.
    application = QApplication.instance() or QApplication(sys.argv)
    application.setApplicationName(APP_NAME)
    installer_traduction_qt(application)
    appliquer_theme(application)
    # Garde en vie jusqu'a la fin de main() : le verrou tombe avec lui.
    verrou = verrou_instance_unique(dossier_donnees())
    if verrou is None:
        QMessageBox.information(
            None, APP_NAME,
            f"{APP_NAME} est déjà ouverte.\n\n"
            "Utilisez la fenêtre déjà ouverte (voyez la barre des tâches). "
            "Deux fenêtres sur les mêmes données effaceraient l'une les "
            "saisies de l'autre.")
        return 0
    fenetre = FenetrePrincipale()
    fenetre.show()
    code = application.exec()
    verrou.unlock()
    return code


if __name__ == "__main__":
    sys.exit(main())
