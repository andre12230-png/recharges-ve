"""Le texte de la notice d'utilisation, sans interface.

Lu par la page Notice (pages/notice.py). Une section par bloc, un
paragraphe par entree : ajouter une explication n'oblige a toucher a aucun
widget.

Ce texte-la est accentue, contrairement aux commentaires du code : c'est de
la lecture, pas du code.
"""

from constantes import SAISIE_TELEPHONE
from liens import AIDE_EN_LIGNE

# Intitule du paragraphe retire de la notice publique (voir la fin du fichier).
PARAGRAPHE_TELEPHONE = "Depuis le téléphone"

# (titre de section, [(intitule ou "", texte), ...])
# Un intitule vide donne un paragraphe simple, sans titre en gras.
SECTIONS: list[tuple[str, list[tuple[str, str]]]] = [
    ("À quoi sert cette application", [
        ("", "Elle suit le coût réel des recharges du véhicule électrique : "
             "celles faites à la maison, calculées d'après la grille "
             "tarifaire et l'heure de la charge, et celles faites à "
             "l'extérieur, saisies au montant payé."),
        ("", "De là, elle tire le prix moyen du kWh, le coût aux 100\xa0km, la "
             "part des heures creuses, et de quoi comparer un mois à l'autre."),
        ("Se repérer",
         "Le menu de gauche suit l'ordre de l'usage, en cinq sections : "
         "Principal (saisir, importer, retrouver ses recharges), Analyse "
         "(statistiques, kilométrage, essence ou électrique, export), "
         "Mes données (sauvegarde externe, restauration), Réglages (tarifs "
         "et paramètres), Aide. La page affichée est le bouton surligné en "
         "bleu. « Essence ou électrique ? » et « Exporter », qui servent de "
         "temps en temps, s'ouvrent par le bouton « 🗂️ Comparer et "
         "exporter… », qui les propose dans un petit menu : la page affichée "
         "y est cochée."),
    ]),
    ("Choisir la période", [
        ("La barre « Période »",
         "Elle porte deux menus — l'année, puis le mois — encadrés par deux "
         "flèches. Les flèches reculent ou avancent d'un cran : d'un mois "
         "quand un mois est affiché, d'une année quand c'est une année. "
         "Elles se grisent quand il n'y a plus rien de ce côté."),
        ("Ce mois-ci et le clavier",
         "Le bouton « Ce mois-ci » ramène au mois en cours en un clic ; il "
         "est grisé quand vous y êtes déjà. Au clavier : Ctrl+← période "
         "précédente, Ctrl+→ période suivante, Ctrl+Origine mois en cours. "
         "Dans une case de saisie, Ctrl+← et Ctrl+→ gardent leur rôle "
         "habituel (sauter d'un mot)."),
        ("Sur la page Statistiques",
         "Seule l'année se choisit : le graphique compare les mois d'une "
         "année entre eux, un mois seul n'y apprendrait rien. Les flèches et "
         "Ctrl+← / Ctrl+→ y avancent d'une année, et le bouton devient "
         "« Cette année » (Ctrl+Origine)."),
        ("Toute la période et 30 derniers jours",
         "Ces deux choix sont en tête du menu des années. Le menu des mois "
         "se grise alors : ces périodes-là ne se découpent pas en mois. "
         "« 30 derniers jours » compte 30 jours du calendrier, aujourd'hui "
         "compris, pour les recharges comme pour l'abonnement et les frais "
         "de cartes."),
        ("À l'ouverture",
         "Rien n'est mémorisé d'une fois sur l'autre : vous ne risquez pas "
         "de prendre les chiffres d'un mois passé pour ceux du mois en "
         "cours. Le tableau de bord et l'historique affichent le mois en "
         "cours, ou « Toute la période » s'il n'a encore aucune recharge "
         "(un 1er du mois, par exemple). Les statistiques partent de l'année : leur graphique "
         "compare les mois entre eux, et un seul mois n'y ferait qu'une "
         "barre. La page Exporter, elle, part de « Toute la période », puisqu'on y "
         "choisit sa période exprès."),
    ]),
    ("Ajouter une recharge", [
        ("Les cases à remplir",
         "Une case qu'il faut remplir et qui est encore vide est encadrée de "
         "bleu et affiche « à saisir ». Une fois remplie, elle reprend son "
         "cadre gris. Les autres cases sont facultatives. La page "
         "Kilométrage fait de même pour le kilométrage actuel."),
        ("À la maison",
         "Saisissez la date, l'heure de début, l'heure de fin et l'énergie "
         "en kWh. L'heure de fin peut rester vide si votre tarif est à prix "
         "unique : elle ne change alors rien au coût. En heures pleines / "
         "heures creuses elle est indispensable, c'est la durée qui répartit "
         "l'énergie entre les deux. "
         "Le coût est calculé tout seul d'après la grille tarifaire — vous "
         "n'avez rien à taper. Une charge qui passe minuit est découpée : "
         "chaque morceau est facturé au tarif de son heure. La nuit du "
         "changement d'heure, la durée est celle vraiment écoulée : de "
         "01:30 à 04:30 la nuit où l'on avance l'heure, la voiture n'a "
         "chargé que deux heures."),
        ("Donner la durée plutôt que l'heure de fin",
         "La borne affiche souvent la durée de la charge, pas l'heure à "
         "laquelle elle s'est terminée. Tapez-la dans la case de l'heure de "
         "fin avec un « + » devant : « +6h12 », « +6h », ou « +45min ». Le "
         "« + » est indispensable — sans lui, « 6h12 » serait compris comme "
         "six heures douze du matin. Laissez alors la case du jour vide : "
         "la durée se compte à partir du début."),
        ("À l'extérieur",
         "Trois cases sont proposées : l'énergie, le coût total et le prix "
         "du kWh. Remplissez-en deux, la troisième se calcule. Les reçus des "
         "opérateurs ne donnent pas tous les mêmes chiffres : l'un le total "
         "payé, l'autre le tarif au kWh — vous n'avez plus de division à "
         "faire. Si vous remplissez les trois, c'est le coût payé qui fait "
         "foi : c'est lui que vous retrouverez sur votre relevé bancaire. "
         "Une recharge gratuite se saisit avec 0\xa0€ et son énergie."),
        ("Le lieu se choisit dans une liste",
         "Le champ « Lieu » propose les endroits où vous avez déjà rechargé, "
         "les plus fréquents en tête : choisissez-y plutôt que de réécrire. "
         "Le même endroit écrit de deux façons — « Tilleuls (A7) » et "
         "« Tilleuls - Aire des Tilleuls » — compterait sinon pour deux lieux "
         "dans vos statistiques. Un endroit nouveau se tape librement dans la "
         "case, et rejoint la liste tout seul. Une écriture qui ne diffère "
         "que par les majuscules, les accents ou les espaces rejoint celle "
         "déjà en service. La même liste sert quand vous corrigez une "
         "recharge depuis l'Historique."),
        ("Noter le compteur au passage",
         "Une case « Kilométrage du compteur » termine les deux formulaires. "
         "Elle est facultative, mais c'est le moment le plus commode : vous "
         "êtes devant la voiture. Le relevé est daté de la recharge, et vous "
         "évitez un détour par la page Kilométrage. Plus vos relevés sont "
         "fréquents, plus votre coût aux 100\xa0km est juste. Si le relevé est "
         "refusé — un compteur ne recule pas — la recharge, elle, reste "
         "enregistrée, et le message vous le dit."),
        ("Le bouton « Maintenant »",
         "Il remplit les deux cases — le jour et l'heure — avec l'instant "
         "présent, pour éviter de les taper."),
        ("Les deux cases d'une date",
         "Le jour et l'heure ont chacun leur case : « 18/09/2026 » à "
         "« 22:30 ». Le jour est déjà rempli à l'ouverture, et le plus "
         "souvent vous n'avez que l'heure à corriger. "
         "Une case laissée vide ne bloque pas l'autre : sans jour, c'est "
         "aujourd'hui ; sans heure, minuit. Seule exception, l'heure de "
         "fin : sans jour, elle se place le jour du début de la recharge."),
        ("Écrire vite",
         "Dans la case du jour, « 18/09 » suffit : l'année en cours est "
         "devinée, et elle peut aussi s'écrire sur deux chiffres "
         "(« 18/09/26 »). Dans celle de l'heure, le « h » remplace les "
         "deux-points : « 22h30 », ou « 22h » pour l'heure pile. "
         "Pour une charge de nuit, laissez la case du jour de fin VIDE et ne "
         "donnez que l'heure : elle se place le jour du début, ou le "
         "lendemain si elle tombe avant l'heure du début. Après un début à "
         "22h30, « 6h » désigne le lendemain matin — même si vous saisissez "
         "la recharge plusieurs jours après. "
         "En janvier, un jour écrit sans année et qui tomberait loin dans "
         "l'avenir est rapporté à l'année précédente : le 2 janvier, "
         "« 30/12 » est bien le 30 décembre qui vient de s'écouler. "
         "Une recharge de plus de trois jours est refusée : c'est presque "
         "toujours une faute sur la date de fin. "
         "Les mêmes écritures valent pour le relevé kilométrique."),
        (PARAGRAPHE_TELEPHONE,
         "Si le serveur mobile est installé sur ce PC (il se trouve avec le "
         "code de l'application, dossier « mobile »), le bouton "
         "« 📱 Téléphone », sous Réglages, affiche le QR code à scanner avec "
         "le téléphone pour ouvrir la page de saisie. Il dit aussi si le "
         "serveur tourne, et le relance s'il a été arrêté. Sans serveur "
         "mobile, ce bouton n'apparaît pas."),
    ]),
    ("Retrouver et corriger une recharge", [
        ("L'historique",
         "Il liste les recharges du lieu et de la période choisis, dans un "
         "seul tableau qui défile. Au-dessus, une ligne résume ce qui est "
         "affiché : nombre de recharges, énergie, coût, prix moyen du kWh. "
         "Le lieu d'une recharge à l'extérieur s'affiche quand la souris "
         "passe sur sa ligne."),
        ("Chercher et trier",
         "Le champ de recherche accepte un opérateur, un lieu, un tarif, une "
         "date, un mois (« juillet ») ou un montant écrit comme à l'écran "
         "(« 30,24 »), et filtre le tableau pendant que vous tapez "
         "(Ctrl+F y place le curseur directement ; la petite croix l'efface). "
         "Un clic sur un titre de colonne trie le tableau ; un second clic "
         "inverse l'ordre."),
        ("Corriger ou supprimer",
         "Cliquez sur une ligne, puis sur « Modifier… » ou « Supprimer ». "
         "Le double-clic sur une ligne, ou la touche Entrée, ouvre aussi la "
         "modification ; la touche Suppr supprime, après confirmation. Le "
         "clic droit propose les deux. Dans la fenêtre de modification, les "
         "cases s'écrivent comme à la saisie (dates courtes, durée "
         "« +6h12 »), et une erreur s'affiche sous la case à corriger. "
         "Vider les deux cases de la fin retire l'heure de fin, comme pour "
         "une recharge saisie sans elle ; avec un tarif heures pleines / "
         "heures creuses, elle reste nécessaire et l'appli la redemande. "
         "Après coup, la recharge reste en évidence dans le tableau."),
        ("Les statistiques",
         "La page Statistiques donne l'énergie et le coût mois par mois (chaque "
         "barre porte son énergie en kWh, la courbe donne le coût), la "
         "répartition par tarif et par opérateur, et la carte « Votre borne face "
         "au tarif réel » : le coût calculé par l'application comparé à "
         "celui annoncé par votre borne — sur "
         "les seules recharges importées de son fichier, les seules qu'elle "
         "ait chiffrées."),
    ]),
    ("Les tarifs", [
        ("À faire en premier",
         "Tant que la grille est vide, aucun coût ne peut être calculé et "
         "l'enregistrement d'une recharge à la maison est refusé (une "
         "recharge extérieure, payée à la borne, n'en a pas besoin). "
         "Ajoutez une période "
         "avec le prix du kWh de votre contrat d'électricité, et vos plages "
         "d'heures creuses si vous en avez."),
        ("Où trouver les chiffres",
         "Tout se lit sur votre facture d'électricité ou dans votre espace "
         "client : le prix du kWh, l'abonnement mensuel, et vos plages "
         "d'heures creuses. Prenez les prix TTC (taxes comprises), ceux que "
         "vous payez, et non les prix HT. La fenêtre de saisie le rappelle, "
         "et signale une "
         "erreur sous la case à corriger. Aucun prix "
         "n'est proposé d'office : un tarif inventé, qui vieillit sans "
         "prévenir, fausserait tous vos calculs en silence."),
        ("Les plages d'heures creuses courantes",
         "Un menu propose les plages les plus répandues — 22:00-06:00, "
         "23:00-07:00, ou une plage coupée du type 00:00-06:00 + "
         "12:00-14:00. Le choisir remplit la case ; vous pouvez ensuite la "
         "corriger, ou tout écrire à la main si vos horaires sortent de "
         "l'ordinaire. Ces horaires dépendent de votre réseau, pas de votre "
         "contrat : ils ne changent pas avec les prix."),
        ("Une période par grille de prix",
         "La page Tarifs contient une entrée par période tarifaire, avec ses "
         "dates de validité, l'abonnement mensuel et les prix du kWh. Quand "
         "vos prix changent, n'écrasez pas l'ancienne période : ajoutez-en "
         "une nouvelle. Les recharges déjà saisies gardent ainsi le prix qui "
         "était le leur."),
        ("Recalculer les coûts",
         "Après un changement de grille, l'application propose de recalculer "
         "le coût des recharges maison ; le bouton « Recalculer tous les "
         "coûts » le fait aussi plus tard. Chaque recharge reprend le prix "
         "de la période où elle a eu lieu : corriger une erreur de saisie "
         "dans une grille corrige donc ses recharges, sans toucher aux "
         "autres périodes."),
        ("L'abonnement",
         "Il est affiché à part sur le tableau de bord, jamais mélangé au "
         "coût des recharges ni au prix du kWh. Il est compté pour le mois "
         "entier, même si le mois n'est pas fini : il est dû de toute façon. "
         "Si vous indiquez dans les Paramètres la part de l'abonnement liée "
         "à la voiture (en pour cent), le bloc Maison affiche en plus « dont "
         "part de la voiture », toujours à part du coût des recharges."),
        ("Les frais de vos cartes de recharge",
         "En bas de la page Tarifs. Saisissez l'achat d'une carte (une "
         "fois, à sa date) ou un abonnement à un réseau de bornes : mensuel "
         "(son prix par mois) ou annuel (son prix par an), avec sa date de "
         "début et, s'il est terminé, sa date de fin. Si votre carte n'est pas dans la liste, tapez son "
         "nom. Comme l'abonnement de la maison, ces frais sont affichés à "
         "part — dans le bloc Extérieur du tableau de bord et dans les "
         "exports — et jamais mélangés au coût des recharges, au prix du kWh "
         "ni au coût aux 100\xa0km. Un abonnement mensuel compte chaque mois "
         "au prorata des jours ; un abonnement annuel compte le prix de "
         "l'année le jour du début, puis à chaque date anniversaire. Le "
         "bouton « Modifier… » d'une ligne corrige des frais déjà saisis "
         "(par exemple pour ajouter la date de fin d'un abonnement "
         "résilié) ; « Supprimer » les retire."),
    ]),
    ("Importer les relevés de votre borne", [
        ("Comment",
         "Déposez le fichier exporté par la borne dans le dossier de vos "
         "données : il apparaît alors dans la page « Importer un CSV », avec "
         "un bouton Importer. Vous pouvez aussi aller le chercher ailleurs "
         "avec « Choisir le fichier de ma borne… ». L'import se fait "
         "aussitôt, sans "
         "confirmation : le compte rendu s'affiche juste après."),
        ("Ce qui est lu",
         "Six colonnes, dans cet ordre : chargeur, début, fin, énergie, "
         "durée, coût. Le séparateur peut être la virgule ou le "
         "point-virgule, les nombres s'écrire avec un point ou une virgule, "
         "et les dates 2026-03-02 23:00:00 comme 02/03/2026 23:00. Un fichier "
         "ouvert puis réenregistré par Excel se lit aussi."),
        ("Une autre borne",
         "Si le fichier n'a pas ces six colonnes, une fenêtre « Quelle "
         "colonne contient quoi ? » montre ses premières lignes : indiquez "
         "la colonne du début, celle de la fin (ou de la durée), celle de "
         "l'énergie (en kWh ou en Wh) et, si la borne en donne un, celle du "
         "coût. L'application devine déjà ce qu'elle peut d'après les titres "
         "des colonnes. Ce choix est retenu : les fichiers suivants du même "
         "modèle s'importent ensuite directement. Annuler n'enregistre "
         "rien. Une limite : la date et l'heure doivent être dans la même "
         "colonne. Si votre borne les sépare (« Date » puis « Heure »), "
         "réunissez-les dans un tableur avant l'import, ou saisissez vos "
         "recharges à la main."),
        ("Rien n'est perdu en silence",
         "Les recharges déjà enregistrées ne sont pas dupliquées, et deux "
         "recharges distinctes du fichier (horaires qui ne se chevauchent "
         "pas, ou deux bornes) restent deux recharges. Une "
         "recharge saisie à la main puis retrouvée dans le fichier (même "
         "heure à deux heures près, même énergie à 0,1\xa0kWh ou 1\xa0% près) est "
         "remplacée par la ligne de la borne, plus précise. Les "
         "branchements sans recharge sont écartés. Si des lignes ne sont pas "
         "comprises, leur nombre s'affiche en orange — elles n'ont PAS été "
         "enregistrées, ne supprimez pas le fichier. Si aucune ne l'est, "
         "l'import s'arrête sur une erreur plutôt que d'annoncer « rien de "
         "nouveau »."),
    ]),
    ("Le kilométrage", [
        ("", "Relevez le compteur de temps en temps, avec la consommation "
             "moyenne affichée par la voiture. L'application en tire le coût "
             "aux 100\xa0km et compare l'énergie que vous avez saisie à celle "
             "que la voiture dit avoir consommée."),
        ("L'écart n'est pas une faute",
         "Les recharges faites chez des proches ou sur des bornes gratuites "
         "ne sont pas mesurables : l'énergie qui en vient manquera toujours à "
         "l'appel. L'application estime seulement quelle part n'est pas "
         "enregistrée, d'après la consommation affichée par la voiture et le "
         "rendement de charge. Si vos recharges dépassent ce que la voiture "
         "semble avoir consommé, elle le signale comme un écart à vérifier : "
         "kilométrage, énergie saisie, consommation de référence ou "
         "rendement."),
        ("Le coût aux 100\xa0km sur le tableau de bord",
         "Dès que vous avez deux relevés et des recharges entre eux, le "
         "tableau de bord affiche le coût de vos recharges enregistrées aux "
         "100\xa0km, sans l'abonnement ni les frais de cartes. Attention, "
         "il ne suit pas la période choisie en haut de la page : il se "
         "calcule entre vos relevés du compteur, et la bande rappelle sur "
         "quelles dates il porte. La consommation en kWh n'y figure pas "
         "exprès — celle que l'application connaît ne compte que l'énergie "
         "saisie, et la page Kilométrage l'explique bien mieux, avec l'écart "
         "par rapport à ce qu'affiche votre voiture."),
        ("Comparaison avec une voiture essence",
         "Indiquez dans « ⚙️ Paramètres » la consommation d'une voiture "
         "essence comparable (en litres aux 100\xa0km) et le prix du litre. La "
         "page « ⛽ Essence ou électrique ? » montre alors ce que l'essence vous aurait coûté, ce que vous avez "
         "payé en électricité, et l'économie ; le tableau de bord ajoute le "
         "coût aux 100\xa0km en essence. En haut de la page, choisissez « Toute la période » "
         "(avec le détail année par année) ou une année. L'abonnement "
         "électrique et les frais de cartes ne sont pas comptés. Deux cases "
         "vides : pas de comparaison."),
        ("D'où viennent les kilomètres",
         "De vos relevés du compteur : sans deux relevés qui l'encadrent, une "
         "année ne peut pas être comparée. Pour une voiture achetée neuve, un "
         "relevé à 0\xa0km le jour de la livraison sert de point de départ. "
         "Quand deux relevés encadrent plusieurs années, les kilomètres entre "
         "eux sont partagés au prorata du temps passé dans chaque année. Si "
         "une partie de l'énergie de ces kilomètres manque dans vos recharges "
         "(chez des proches, sur des bornes gratuites, ou recharges non "
         "saisies), la comparaison en donne une estimation, quand l'écart "
         "dépasse ce qu'une batterie partie pleine ou vide peut expliquer. "
         "Son origine et son prix ne sont pas connus : le coût en électricité "
         "ne compte que vos recharges saisies."),
        ("Le prix du litre",
         "Un prix général, et, si vous le souhaitez, un prix par année "
         "(Paramètres) : l'essence ne coûtait pas le même prix d'une année à "
         "l'autre. Une année laissée vide prend le prix général. Pensez à le "
         "mettre à jour de temps en temps : le tableau de bord vous le "
         "rappelle quand il n'a pas été revu depuis trois mois. Pour trouver "
         "le prix, deux boutons de Paramètres ouvrent des sites officiels "
         "dans votre navigateur : « Prix près de chez vous » "
         "(prix-carburants.gouv.fr, le prix des stations) et « Moyennes "
         "nationales » (le ministère, une moyenne par mois : faites celle "
         "des mois d'une année pour son prix par année). L'application, "
         "elle, ne se connecte à rien."),
        ("Le rappel du tableau de bord",
         "Si le compteur n'a pas été relevé depuis un mois et que des "
         "recharges ont eu lieu entre-temps, une ligne discrète l'indique en "
         "haut du tableau de bord. Ce n'est pas un reproche : les recharges "
         "faites après le dernier relevé ne sont rattachées à aucune "
         "distance, et n'entrent donc ni dans la consommation ni dans le "
         "coût aux 100\xa0km. Un nouveau relevé les rattache toutes d'un coup. "
         "Tant que vous n'avez saisi aucun relevé, rien ne s'affiche : si "
         "vous ne vous servez pas de cette page, l'application ne vous en "
         "parle pas."),
        ("Corriger un relevé",
         "Le bouton « Modifier… » de sa ligne, dans « Mes relevés », ouvre le "
         "relevé pour corriger sa date, son kilométrage ou la consommation "
         "affichée. Les mêmes contrôles qu'à la saisie s'appliquent : le "
         "compteur ne peut pas reculer d'un relevé à l'autre. « Supprimer » "
         "le retire pour de bon."),
    ]),
    ("Vos données", [
        ("Où elles sont",
         "Dans le dossier indiqué en bas de cette page, et dans la page "
         "« ⚙️ Paramètres », dont le bouton « Ouvrir le dossier » l'affiche "
         "dans l'Explorateur. Vos recharges sont "
         "dans recharges.json, la grille tarifaire dans tarifs.json. "
         "L'application ne s'ouvre qu'une fois à la fois : deux fenêtres "
         "sur les mêmes données effaceraient l'une les saisies de l'autre."),
        ("Sauvegardes automatiques",
         "Une copie est faite avant chaque écriture, dans le sous-dossier "
         "backups. La page « ♻ Restaurer une sauvegarde » permet de revenir à l'une d'elles ; "
         "l'état actuel est mis de côté au passage, donc une restauration se "
         "défait ; si cette mise de côté échoue, la restauration est annulée "
         "et rien n'est remplacé. Si recharges.json est abîmé (illisible, ou "
         "retouché avec une date ou un nombre impossible) ou a disparu, "
         "l'application reprend d'elle-même la sauvegarde la plus récente "
         "au démarrage, et vous le dit. À chaque fermeture, si vos données ont changé, une copie "
         "datée est aussi faite dans le sous-dossier Sauvegardes : les 10 "
         "plus récentes y restent, plus la dernière de chaque mois ; les "
         "autres partent à la Corbeille de Windows."),
        ("Sauvegarde externe",
         "Les sauvegardes automatiques restent sur le même disque que vos "
         "données : si ce disque lâche, elles partent avec lui. Le bouton "
         "« 💾 Sauvegarde externe » (menu de gauche, section Mes données) copie "
         "vos recharges et vos tarifs sur la clé USB ou le disque de votre "
         "choix, dans un dossier daté, et vérifie chaque copie. Un fichier "
         "LISEZMOI.txt, déposé à côté, explique comment la remettre en "
         "service. Si la copie échoue (clé pleine ou retirée), le dossier "
         "commencé porte la mention « INACHEVÉE - ne pas utiliser » : ne "
         "vous en servez pas, et recommencez. "
         "Faites-le de temps en temps, par exemple une fois par "
         "mois : au-delà de 30 jours sans sauvegarde externe, le tableau de "
         "bord vous le rappelle."),
        ("Réglages de la voiture et de la borne",
         "Dans la page « ⚙️ Paramètres » (menu de gauche, section "
         "Réglages). La capacité de la batterie, en kWh : "
         "elle sert à repérer une énergie impossible à la saisie, et de "
         "marge au contrôle kilométrique. Le rendement de charge, en pour "
         "cent : la part de l'énergie qui arrive vraiment à la batterie, 90 "
         "convient à la plupart des voitures. La correction de l'horloge, en "
         "minutes : si les heures exportées par votre borne sont décalées "
         "(-60 recule d'une heure). Vérifiez-la d'abord, par exemple sur la "
         "courbe de charge de votre compteur : la plupart des bornes "
         "exportent déjà l'heure juste. Quand vous la changez, les "
         "recharges déjà importées sont replacées et leur coût recalculé. "
         "La puissance de charge de la borne, en kW (facultative, 7,4 pour "
         "une borne domestique courante) : une borne charge à pleine "
         "puissance dès le début, puis s'arrête quand la batterie est "
         "pleine, même si la voiture reste branchée. Indiquée, elle place "
         "l'énergie au début de la recharge, ce qui compte plus justement "
         "les heures creuses ; laissée vide, l'énergie est étalée jusqu'à "
         "l'heure de fin. Le coût de toutes vos recharges à la maison est "
         "recalculé quand vous la changez."),
        ("Apparence : clair ou sombre",
         "La question vous est posée au tout premier lancement. Pour "
         "changer d'avis ensuite : page « ⚙️ Paramètres », carte "
         "Apparence, thème Clair ou Sombre. Le choix s'applique au "
         "prochain démarrage de "
         "l'application, quel que soit le réglage de Windows. Il ne touche "
         "pas à vos données."),
        ("Le bouton « Sauvegarder »",
         "Il n'apparaît que si vos données sont suivies par un dépôt git : "
         "il en envoie alors une copie vers GitHub. Rien n'y part tout seul, "
         "pas même à la fermeture : seulement quand vous cliquez. Si l'envoi "
         "échoue (pas de connexion), cliquez de nouveau plus tard. C'est "
         "facultatif, et sans rapport avec "
         "les sauvegardes ci-dessus, qui, elles, sont toujours faites. Le "
         "raccourci est Ctrl+S."),
    ]),
    ("Exporter", [
        ("", "Excel ou PDF, sur le lieu et la période de votre choix. Le "
             "nombre de lignes concernées s'affiche avant que vous lanciez "
             "l'export."),
        ("Ce que contient le fichier",
         "Excel : la liste des recharges, puis une feuille de synthèse. "
         "PDF : la synthèse, puis la liste des recharges, prêt à imprimer. "
         "Les deux donnent aussi l'abonnement de la période (sauf pour "
         "l'extérieur seul) et, quand vous exportez tous les lieux, le coût "
         "aux 100\xa0km. Celui-ci se calcule entre vos relevés du compteur : "
         "seuls les intervalles compris en entier dans la période comptent."),
    ]),
    ("Nouvelles versions et avis", [
        ("Mise à jour",
         "L'application ne vérifie pas toute seule qu'une nouvelle version "
         "existe. Le bouton « 🔄 Mise à jour », en bas du menu, ouvre dans "
         "votre navigateur la page de la dernière version : si son numéro "
         "est plus grand que celui affiché en bas du menu, une mise à jour "
         "vous attend. Fermez l'application avant de lancer l'installeur : "
         "vos données ne sont pas touchées."),
        ("Votre avis",
         "Le bouton « 💬 Votre avis » ouvre un court questionnaire dans "
         "votre navigateur, pour signaler un problème ou proposer une idée. "
         "Aucune réponse n'est obligatoire."),
    ]),
    ("Raccourcis clavier", [
        ("Ctrl+S", "Envoyer vers un dépôt git, si vous en avez un, les "
                   "données déjà enregistrées. Ctrl+S n'enregistre pas le "
                   "formulaire affiché : s'il reste des valeurs tapées, "
                   "l'application le dit et n'envoie rien."),
        ("Ctrl+F", "Ouvrir l'Historique et aller dans la recherche."),
        ("F5", "Recharger la page affichée (sauf si vous y avez tapé des "
               "valeurs pas encore enregistrées : elles restent)."),
        ("Entrée", "Enregistrer le formulaire en cours, depuis n'importe "
                   "quelle case (ajout d'une recharge, relevé kilométrique, "
                   "fenêtres de modification et de tarif). Dans l'Historique, "
                   "ouvrir la recharge choisie."),
        ("Suppr", "Dans l'Historique, supprimer la recharge choisie, après "
                  "confirmation."),
        ("Échap", "Fermer une fenêtre de modification ou de tarif sans rien "
                  "changer."),
        ("Changer de page", "Des valeurs tapées et pas encore enregistrées "
                            "restent en place : vous les retrouvez en "
                            "revenant. À la fermeture, l'application demande "
                            "s'il faut les abandonner."),
    ]),
]

# Sans les boutons « Mise à jour » et « Votre avis » (application non
# publiee, liens.py), la notice n'en parle pas non plus.
if not AIDE_EN_LIGNE:
    SECTIONS = [s for s in SECTIONS if s[0] != "Nouvelles versions et avis"]

# Version publique, sans saisie depuis le telephone (constantes.py) : la
# notice n'en parle pas non plus.
if not SAISIE_TELEPHONE:
    SECTIONS = [(titre, [p for p in paragraphes if p[0] != PARAGRAPHE_TELEPHONE])
                for titre, paragraphes in SECTIONS]
