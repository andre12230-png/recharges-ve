# Recharges VE

[![Version](https://badgen.net/github/release/andre12230-png/recharges-ve/stable?label=version&color=blue)](https://github.com/andre12230-png/recharges-ve/releases/latest)
[![Licence MIT](https://badgen.net/github/license/andre12230-png/recharges-ve)](LICENSE)

Application de bureau gratuite (Windows 10/11) pour savoir ce que vous
coûtent **vraiment** les recharges de votre voiture électrique : à la maison,
heures creuses comprises, et sur les bornes publiques, avec le coût aux
100 km. Données 100 % locales, open source (licence MIT).

Page de présentation : **[andre12230-png.github.io/recharges-ve](https://andre12230-png.github.io/recharges-ve/)**

[![Vidéo de présentation de Recharges VE (1 min 07) — cliquez pour la lancer](docs/media/video-apercu.jpg)](https://andre12230-png.github.io/recharges-ve/#video)
*▶ Vidéo de présentation (1 min 07), sur la page de présentation. Réalisée avec des données d'exemple.*

## Installer l'application

Pas besoin d'être informaticien, ni d'installer Python :

1. Téléchargez l'installeur
   **[Recharges-VE-Setup.exe](https://github.com/andre12230-png/recharges-ve/releases/latest/download/Recharges-VE-Setup.exe)**
   (il est aussi sur la [page des versions](https://github.com/andre12230-png/recharges-ve/releases/latest),
   rubrique *Assets*).
2. Lancez-le. Aucun mot de passe administrateur n'est demandé.
3. Windows peut afficher « Windows a protégé votre ordinateur » : le
   programme est encore peu téléchargé et n'est pas signé, ce qui ne veut
   pas dire qu'il est dangereux. Cliquez sur **Informations complémentaires**, puis
   **Exécuter quand même**.
4. Lancez **Recharges VE** depuis le menu Démarrer.

Vous préférez vérifier plutôt que me croire sur parole ? L'installeur de cette
version a été soumis à 68 antivirus, et
**[un seul le signale](https://www.virustotal.com/gui/file/f62524511fee4b705fceacf8b29cee2268292c01d7fddf87a018da749a02b427)** :
celui de Microsoft, par une détection automatique (« !ml ») qui se trompe souvent
sur les programmes écrits en Python. Ce faux positif a été signalé à Microsoft. Le
rapport est public, sur VirusTotal.

Vous pouvez aussi **[y déposer vous-même](https://www.virustotal.com/gui/home/upload)**
le fichier que vous venez de télécharger, pour vous assurer qu'il est bien arrivé
intact. Le site est en anglais, mais il n'y a rien à lire : cliquez sur
*Choose file* et désignez le fichier. C'est le réflexe à avoir pour n'importe
quel programme téléchargé, pas seulement celui-ci.

Vous préférez une version **portable**, sans installation ? Prenez le fichier
`.zip` sur la [page des versions](https://github.com/andre12230-png/recharges-ve/releases/latest)
(rubrique *Assets*) : décompressez-le où vous voulez (gardez tout le dossier
ensemble), puis double-cliquez `Recharges-VE\Recharges-VE.exe`. Vos données
vont, là aussi, dans votre dossier personnel.

Pour mettre à jour : fermez l'application et lancez le nouvel installeur (le
bouton **🔄 Mise à jour**, en bas du menu, ouvre la page de la dernière
version). Pour désinstaller : Paramètres Windows › Applications. Dans les
deux cas, vos données sont conservées.

## Premiers pas

1. **Vos tarifs d'abord.** Au premier lancement, l'application ouvre la page
   **Tarifs** : saisissez le prix du kWh de votre contrat d'électricité, et
   vos plages d'heures creuses si vous en avez. Sans eux, aucun coût ne peut
   être calculé : une recharge à la maison est refusée plutôt qu'inscrite à
   0 €.
2. **Vos recharges** : page **Ajouter une recharge** (à la maison : début,
   fin, énergie ; sur une borne : montant payé et énergie). Si votre borne
   domestique exporte l'historique de ses charges dans un fichier CSV, la
   page **Importer un CSV** le fait entrer d'un coup.
3. **Votre kilométrage**, de temps en temps (page **Kilométrage**) : il
   donne le coût réel aux 100 km.

La page **Notice**, en bas du menu, explique chaque écran.

## Vos données

Elles restent **sur votre ordinateur**, dans `%LOCALAPPDATA%\Recharges VE`
(raccourci **Dossier des données** du menu Démarrer), et sont sauvegardées
avant chaque modification. Le bouton **💾 Sauvegarde externe** en fait une
copie vérifiée sur une clé USB ou un disque. L'application ne crée aucun
compte et n'envoie rien en ligne.

## Un problème ? Une idée ?

Le bouton **💬 Votre avis** ouvre un
[court questionnaire](https://forms.cloud.microsoft/r/3EvSX9YEBP), sans compte
à créer. Vous avez un compte GitHub ? Vous pouvez aussi
[ouvrir un ticket](https://github.com/andre12230-png/recharges-ve/issues).

---

La suite de ce document s'adresse à qui veut comprendre les calculs ou
modifier le programme.

---

## Pour travailler sur le code

Python 3.14, la seule version testée :

```bash
py -m pip install -r requirements.txt
py app.py
```

Cette installation a été vérifiée dans un environnement neuf : les
bibliothèques s'installent et l'application passe sa vérification automatique.

Le code lui-même ne demande pas tant : la construction la plus récente qu'il
emploie est la notation `X | Y` des annotations, apparue en **Python 3.10**.
Mais rien en dessous de 3.14 n'a jamais été essayé, ni pour l'application ni
pour ses bibliothèques — d'où le chiffre annoncé. Si vous avez une version
plus ancienne, essayez : ça marchera probablement, sans garantie.

> **`py` plutôt que `python`.** Sur une machine où plusieurs Python
> cohabitent, avec des versions de bibliothèques différentes, `py` désigne
> sans ambiguïté celui qui lance l'application, exécute les tests **et**
> construit l'exécutable (voir `build.bat`) : l'exe embarque alors exactement
> ce que la vérification automatique a testé.

Lancée depuis les sources, l'application lit les données de `dist\` — les
mêmes que l'exécutable fabriqué à côté, pour éviter deux historiques
divergents.

---

## Les pages

| Page | À quoi elle sert |
|---|---|
| **Tableau de bord** | Vue d'ensemble sur la période choisie : nombre de recharges, énergie, coût, prix moyen, répartition maison / extérieur, abonnement, dernières recharges. |
| **Ajouter une recharge** | Saisie manuelle, à la maison ou sur une borne extérieure. L'heure de fin peut rester vide si votre tarif est à prix unique. Une énergie supérieure à ce que la batterie peut absorber (voir `capacite_batterie`) déclenche une demande de confirmation : c'est presque toujours une faute de frappe. |
| **Importer un CSV** | Import du fichier exporté par la wallbox. |
| **Historique** | Toutes les recharges dans un seul tableau qui défile : on choisit une ligne, puis **Modifier…** ou **Supprimer** (ou double-clic, Entrée, Suppr, clic droit). Filtres par lieu et par période, **recherche** pendant la frappe (opérateur, lieu, tarif, date, montant) et **tri en cliquant sur un titre de colonne**. Une ligne résume la sélection. |
| **Statistiques** | Graphique énergie et coût par mois, répartition par tarif et par opérateur, écart avec le coût annoncé par la wallbox. |
| **Kilométrage** | Relevés du compteur, consommation et coût au 100 km, et estimation de la **part d'énergie non enregistrée** (recharges chez des proches, bornes gratuites). Une phrase renvoie à la page « Essence ou électrique ? » pour la comparaison avec une voiture essence. |
| **⛽ Essence ou électrique ?** | La comparaison avec une voiture essence, sur « Tout » (avec le détail année par année) ou sur une année, à partir des kilomètres entre vos relevés du compteur : ce que l'essence vous aurait coûté, ce que vous avez payé en électricité, l'économie. Un bouton mène aux Paramètres pour changer la voiture de comparaison ou le prix du litre. |
| **Exporter** | Excel (tableau détaillé + synthèse) ou PDF (rapport imprimable), sur la sélection de votre choix. |
| **Restaurer** | Liste les sauvegardes disponibles avec leur date et leur nombre de recharges, et permet d'en remettre une en service. L'état actuel est mis de côté au passage : une restauration faite par erreur s'annule en restaurant la sauvegarde la plus récente. |
| **Tarifs** | Grille tarifaire : **modifier** une période, en **ajouter** une quand vos prix changent, la supprimer, et recalculer tous les coûts. Plus besoin d'éditer `tarifs.json` à la main. En bas de page, les **frais de vos cartes de recharge** (achat d'une carte, ou abonnement mensuel ou annuel à un réseau), comptés à part comme l'abonnement de la maison. |
| **⚙️ Paramètres** | Les réglages de la voiture et de la borne (capacité de la batterie, rendement de charge, correction de l'horloge du CSV, puissance de charge de la borne), la **voiture essence de comparaison** (consommation en L/100 km et prix du litre, à saisir vous-même), la **part de l'abonnement liée à la voiture**, l'**apparence** (thème clair ou sombre, appliqué au prochain démarrage) et l'emplacement de vos données, avec un bouton pour ouvrir ce dossier. |
| **Notice** | Le mode d'emploi, dans l'application : à quoi elle sert, comment choisir la période, saisir une recharge, tenir la grille tarifaire, où sont les données et comment revenir en arrière. |

Le menu de gauche range ces pages en cinq sections — **Principal**,
**Analyse**, **Mes données**, **Réglages**, **Aide** — dans l'ordre de
l'usage (saisir, analyser, sauvegarder, régler, se faire aider), sous forme de boutons précédés d'un
emoji, comme dans Pécule et dans Gestion Photovoltaïque. La page affichée est
le bouton surligné en bleu. **Essence ou électrique ?** et **Exporter**, qui
servent de temps en temps, sont réunies sous un seul bouton,
**🗂️ Comparer et exporter…**, qui les propose dans un petit menu : le menu
tient ainsi sans défiler sur un portable 1366 × 768. Le numéro de version est
en pied de menu.

### Raccourcis clavier

| Touche | Effet |
|---|---|
| `Ctrl+S` | Envoie vers un dépôt git, si vous en avez un, les données déjà enregistrées (voir plus bas) ; il n'enregistre pas le formulaire affiché et le dit s'il reste des valeurs tapées |
| `Ctrl+F` | Ouvre l'Historique, curseur dans la recherche |
| `F5` | Reconstruit la page affichée, sauf si elle porte des valeurs tapées pas encore enregistrées |
| `Entrée` | Enregistre le formulaire en cours, depuis n'importe quelle case ; dans l'Historique, ouvre la recharge choisie |
| `Suppr` | Dans l'Historique, supprime la recharge choisie (après confirmation) |
| `Échap` | Ferme une fenêtre de modification ou de tarif sans rien changer |

Les champs de date portent un bouton **Maintenant** : on saisit presque
toujours une recharge après coup, et retaper `jj/mm/aaaa hh:mm` est fastidieux.

---

## Choisir la période

Le tableau de bord, l'historique, les statistiques et l'export partagent la
même barre : **‹ année mois ›**. Les deux flèches reculent ou avancent d'un
cran — d'un mois quand un mois est affiché, d'une année quand c'est une année
— et se grisent quand il n'y a plus rien de ce côté. Le menu des mois ne
propose que les mois qui portent des recharges, plus le mois en cours.

Le bouton **Ce mois-ci** ramène au mois en cours en un clic (grisé quand on y
est déjà). Au clavier : **Ctrl+←** période précédente, **Ctrl+→** période
suivante, **Ctrl+Origine** mois en cours.

Sur la page **Statistiques**, seule l'année se choisit (**‹ année ›**) : son
graphique compare les mois d'une année entre eux. Le bouton y devient
**Cette année**, et flèches comme raccourcis avancent d'une année.

Le menu des années offre aussi deux raccourcis : **Tout** et **30 derniers
jours** ; le menu des mois est alors grisé, puisque ces deux-là ne se
découpent pas en mois. « 30 derniers jours » compte 30 jours du calendrier,
aujourd'hui compris, pour les recharges comme pour l'abonnement et les frais.

**L'application s'ouvre toujours sur le mois en cours** (l'export, lui, part
de « Tout »). Rien n'est mémorisé d'une utilisation sur l'autre : après avoir
consulté un mois passé, le lancement suivant revient au mois courant, sans
risque de prendre de vieux chiffres pour les chiffres du jour.

## Où sont mes données

Dans **votre dossier personnel** : `%LOCALAPPDATA%\Recharges VE`. C'est
l'emplacement d'une installation neuve — toujours accessible en écriture, où
que l'archive ait été décompressée. Le chemin exact est rappelé en bas de la
page **Notice**.

Deux exceptions :

- une installation qui tourne **déjà** avec ses données à côté de
  l'application (le dossier `dist\` de qui construit l'exécutable lui-même)
  les garde là : elles ne changent jamais de place sous vos pieds ;
- la variable d'environnement `RECHARGES_DATA_DIR` a toujours le dernier mot
  (voir « Lancer les tests »).

Quel que soit le dossier, il contient :

| Fichier | Contenu |
|---|---|
| `recharges.json` | Toutes les recharges et les relevés kilométriques. **C'est LE fichier à ne pas perdre.** |
| `tarifs.json` | Grille tarifaire et réglages (voir plus bas). |
| `tarifs.json.avant` | La copie de `tarifs.json` juste avant la dernière modification. C'est la sortie de secours que propose le message d'erreur si `tarifs.json` est illisible. |
| `backups\` | Les 15 dernières sauvegardes automatiques de `recharges.json` (`recharges_<date>_<heure>.json`) **et** de `tarifs.json` (`tarifs_<date>_<heure>.json`), plus la première sauvegarde de chaque journée, gardée un mois (`recharges_jour_<date>.json`, `tarifs_jour_<date>.json`). |
| `*.csv` | Les exports de la wallbox déposés là sont proposés directement à l'import. |

`tarifs.json` est créé au premier démarrage, avec une grille vide et des
réglages neutres. `recharges.json` apparaît à votre première recharge.

**Cinq protections** contre la perte de données :

1. Une sauvegarde est créée dans `backups\` **avant chaque écriture**.
2. La première sauvegarde de chaque journée est mise de côté et conservée
   **un mois** : les 15 sauvegardes tournantes ne couvrent que quelques jours
   si vous saisissez beaucoup, alors qu'un problème peut n'être remarqué que
   des semaines plus tard.
3. L'écriture est atomique : une coupure de courant ne peut pas laisser un
   fichier à moitié écrit.
4. **À chaque fermeture**, `recharges.json` et `tarifs.json` sont copiés dans
   le sous-dossier `Sauvegardes\` du dossier des données, dans un dossier
   daté — seulement s'ils ont changé depuis la copie précédente. Les 10
   copies les plus récentes sont gardées, plus la dernière de chaque mois ;
   les autres partent à la Corbeille de Windows (jamais effacées pour de
   bon : sur une clé USB ou un lecteur réseau, qui n'ont pas de Corbeille,
   elles restent en place).
   **Facultatif** : si vos données sont suivies par un dépôt git (un dépôt
   fait pour elles, jamais celui du code, qui les ignore), le bouton
   **Sauvegarder**, en haut de la fenêtre (ou Ctrl+S), envoie une
   copie sur GitHub. Rien ne part à la fermeture. Sans dépôt git, ce bouton
   n'apparaît pas et l'application n'en parle jamais.
5. **Sauvegarde externe** : le bouton **💾 Sauvegarde externe** du menu de
   gauche copie `recharges.json` et `tarifs.json` sur une clé USB ou un
   disque, dans un dossier daté, et vérifie chaque copie. Les protections
   précédentes (sauf l'envoi GitHub) restent sur le même disque que les données ;
   celle-ci survit à sa panne. Un `LISEZMOI.txt` déposé à côté explique
   comment la remettre en service.

Si le fichier devient malgré tout illisible (ou n'a plus la forme d'un
fichier de recharges), l'application le répare toute
seule au démarrage à partir de la dernière sauvegarde, **vous prévient par un
message** indiquant la date de cette sauvegarde, et met le fichier abîmé de
côté sous le nom `recharges_illisible_<date>.json`.

S'il a disparu alors que des sauvegardes existent, elle reprend de même la
plus récente, et vous le dit : elle ne repart pas d'un historique vide.
Une restauration est annulée si l'état actuel n'a pas pu être mis de
côté avant.

---

## Les réglages (`tarifs.json`)

Tout se modifie dans l'application, sans Bloc-notes : la grille tarifaire
dans la page **Tarifs** (elle vérifie les saisies, ferme la période précédente
quand vous en ajoutez une nouvelle, et propose de recalculer les coûts), et
les trois réglages de la voiture et de la borne ci-dessous dans la page
**⚙️ Paramètres**, contrôlés avant d'être enregistrés.

| Réglage | Rôle |
|---|---|
| `capacite_batterie` | Capacité de la batterie en kWh (0 = inconnue). Sert à repérer une énergie impossible à la saisie, et de marge au contrôle kilométrique. |
| `rendement_charge` | Part de l'énergie qui arrive réellement à la batterie (0.9 = 90 %, le reste part en chaleur). |
| `correction_csv_minutes` | Décalage appliqué aux heures du CSV de la wallbox (-60 = recule d'une heure). Corrige la dérive d'horloge du chargeur. La changer dans ⚙️ Paramètres replace aussi les recharges déjà importées et recalcule leur coût. |
| `puissance_borne_kw` | Puissance de charge de la borne, en kW (facultative ; 0 = inconnue). Renseignée, l'énergie d'une recharge est comptée à cette puissance dès le début, au lieu d'être étalée jusqu'à l'heure de fin : les heures creuses sont mieux comptées. La changer dans ⚙️ Paramètres recalcule le coût des recharges à la maison. |
| `tarifs` | La grille : une entrée par période tarifaire. |
| `frais_cartes` | Les frais des cartes de recharge : carte, type (`unique`, `mensuel` ou `annuel`), date (d'achat ou de début), fin (abonnement terminé, sinon `null`), montant (par mois ou par an pour un abonnement ; l'annuel compte en entier au début puis à chaque date anniversaire). Absente des fichiers d'avant la 2.0.5 : aucun frais. |
| `conso_essence` | Consommation de la voiture essence de comparaison, en L/100 km (0 ou absente = pas de comparaison). |
| `prix_essence` | Prix du litre d'essence pour la comparaison, en euros (0 ou absent = pas de comparaison). Aucun prix n'est proposé d'avance. |
| `prix_essence_annees` | Prix du litre par année, facultatifs : `{"2024": 1.8, ...}`. Une année absente prend `prix_essence`. |
| `sauvegarde_externe_derniere` | Jour (AAAA-MM-JJ) de la dernière sauvegarde externe réussie : au-delà de 30 jours, le tableau de bord le rappelle. Absente : jamais faite (le rappel compte alors depuis la première recharge). |
| `correspondances_csv` | Les choix de colonnes retenus pour importer les exports d'autres bornes, un par modèle de fichier (reconnu à sa ligne de titres). |
| `prix_essence_maj` | Jour (AAAA-MM-JJ) où la comparaison essence a été enregistrée pour la dernière fois : au-delà de trois mois, le tableau de bord rappelle de revoir le prix du litre. Absente : pas de rappel. |

Chaque période tarifaire contient ses dates de validité, l'abonnement mensuel,
et soit un prix unique (`"type": "simple"`), soit un prix heures pleines /
heures creuses avec les plages horaires (`"type": "hp_hc"`).

Une recharge dont la date ne tombe dans **aucune** période est refusée plutôt
qu'enregistrée à 0 € : c'est voulu, cela évite les erreurs silencieuses.

---

## Comment les coûts sont calculés

**À la maison**, l'application répartit l'énergie entre heures pleines et
heures creuses au prorata du **temps** passé dans chaque plage (hypothèse :
la voiture charge à puissance constante). Le décompte se fait à la seconde.

Deux plages d'heures creuses qui **se recouvrent** sont refusées à la saisie :
l'heure commune ne peut pas être creuse deux fois. Des plages simplement
jointives (`22:00-00:00` puis `00:00-06:00`) sont acceptées, elles se touchent
sans se recouvrir.

**Une recharge à cheval sur un changement de tarif** est découpée aux
frontières de période. Chaque morceau reçoit l'énergie au prorata de sa durée
et se voit appliquer les prix *et* les plages d'heures creuses de son propre
tarif. Une charge du 10 juin 21 h au 11 juin 5 h, quand les prix changent le
11, est donc facturée 3 heures à l'ancien tarif et 5 au nouveau — et non plus
8 heures à l'ancien. Quand les deux périodes portent des noms différents,
l'historique affiche les deux (`Ancien + Nouveau`).

**L'abonnement n'est jamais mélangé au coût des recharges.** Il est affiché à
part sur le tableau de bord, calculé au jour le jour sur toute la période
choisie — un mois entier quand vous affichez un mois, même s'il n'est pas
fini, puisqu'il est dû de toute façon.

**La part d'énergie non enregistrée** compare l'énergie que vous avez saisie à
celle que la voiture a réellement consommée d'après sa consommation affichée.
La différence n'est pas présentée comme une faute : les recharges faites chez
des proches ou sur des bornes gratuites ne sont pas mesurables, et l'énergie
qui en vient manquera toujours à l'appel. L'application indique donc quelle
part de votre énergie vient d'ailleurs.

Deux conséquences à garder en tête :

- la **consommation** affichée ne porte que sur l'énergie enregistrée : elle
  est donc plus basse que celle affichée par la voiture ;
- le **coût au 100 km ne compte que les recharges saisies** : si l'énergie
  non enregistrée a été payée (recharge oubliée), le coût réel est plus élevé.
  Son origine et son prix ne sont pas connus d'après les seuls relevés.

La comparaison avec une voiture essence reprend le même contrôle, marge de la
batterie comprise : elle n'annonce une part d'énergie non enregistrée que si
le Kilométrage la constate aussi.

Un seul cas est signalé comme un **écart inhabituel à vérifier** : un
**excédent**, c'est-à-dire plus d'énergie enregistrée que la voiture ne semble
en avoir consommé. Le calcul repose sur la consommation de référence du dernier
relevé et sur le rendement de charge réglé : l'écart peut venir d'un
kilométrage ou d'une énergie mal saisie, mais aussi de l'une de ces deux
valeurs. La part d'énergie non enregistrée, elle, reste une **estimation**.

Aucune conclusion n'est tirée tant que l'écart reste inférieur à une charge
complète de batterie : sur une période courte, il s'explique entièrement par
l'état de charge au début et à la fin.

---

## Import du CSV de la wallbox

Dans la page **Importer un CSV**, choisissez le fichier exporté par votre
borne (depuis son application ou son site : « exporter », « historique »).
Un fichier déposé dans le dossier de vos données y est aussi proposé
directement. L'application :

- applique la correction d'horloge et arrondit les heures à la minute ;
- ignore les lignes à 0 kWh et les branchements parasites (moins de 0,05 kWh
  ou durée nulle) ;
- reconnaît une session déjà importée (même énergie, même chargeur, horaires
  qui se chevauchent) et ne la compte pas deux fois ; deux sessions
  distinctes de même énergie restent deux sessions ;
- **remplace** une saisie manuelle par les données précises du CSV quand il
  s'agit de la même session (même énergie, début à moins de 2 h d'écart) ;
- n'écrit rien du tout s'il n'y a aucune nouveauté.

**Quel format ?** Six colonnes, dans cet ordre : identifiant du chargeur,
début, fin, énergie, durée, coût. C'est la disposition des exports de wallbox
domestiques. Le lecteur s'accommode du séparateur (virgule ou point-virgule),
de la virgule ou du point décimal, des unités collées ou non au nombre
(`30.000kWh` comme `30,000 kWh`), et des dates écrites `2026-03-02 23:00:00`
ou `02/03/2026 23:00`. Il ne dépend donc pas de la langue du micrologiciel,
et la plupart des autres bornes passent par la fenêtre décrite ci-dessous.
Limite connue : la date et l'heure doivent être dans la même colonne ; une
borne qui les sépare demande de les réunir dans un tableur avant l'import.

**Une autre borne ?** Un fichier présenté autrement ouvre la fenêtre
« Quelle colonne contient quoi ? » : ses premières lignes s'affichent, et
l'on indique la colonne du début, de la fin (ou de la durée), de l'énergie
(kWh ou Wh) et, facultatif, du coût annoncé par la borne. L'application
devine ce qu'elle peut d'après les titres, en français comme en anglais.
Le choix est retenu (clé `correspondances_csv` de `tarifs.json`) : le même
modèle de fichier s'importe ensuite sans rien demander. Sont aussi lues les
dates `2026-03-02T23:00:00`, `02.03.2026 23:00`, `02-03-2026 23:00` et
celles qui portent un fuseau horaire (`…Z`, `…+01:00`), ramenées à l'heure
du PC.

**Si le fichier reste incompréhensible**, l'import s'arrête sur une erreur
explicite au lieu d'annoncer « 0 ajoutées, rien de nouveau ». C'est important :
ce message rassurant laissait croire que le fichier était déjà importé, alors
qu'aucune de ses recharges n'avait été enregistrée. Quand seule une partie des
lignes est reconnue, le nombre de lignes laissées de côté est affiché en
orange.

---

## Donner l'application à quelqu'un

Ne copiez **pas** le dossier `dist\` : il mélange l'application et vos
données — votre historique, votre grille tarifaire, la capacité de votre
batterie, la dérive d'horloge de votre wallbox.

```bash
py preparer_distribution.py
```

Ce script fabrique `distribution\Recharges-VE-X.Y.Z-win64.zip` : l'application,
le mode d'emploi et la licence, rien d'autre. Il relit ensuite l'archive pour
vérifier qu'aucun fichier de données ne s'y est glissé, et la supprime si
c'était le cas.

Ou bien l'installeur, plus simple pour la personne qui le reçoit :

```bash
py faire_installeur.py
```

Il fabrique `distribution\Recharges-VE-Setup-vX.Y.Z.exe` à partir du seul
dossier `dist\Recharges-VE\`, après avoir vérifié qu'aucun fichier de données
n'y traîne (Inno Setup 6 requis). Une fois installée, l'application range ses
données dans `%LOCALAPPDATA%\Recharges VE`.

---

## Fabriquer l'exécutable

Après une modification du code :

```bash
build.bat
```

Le script reconstruit `dist\Recharges-VE\Recharges-VE.exe`, puis lance une
**vérification automatique** et affiche son compte rendu : toutes les pages du
menu sont ouvertes, les exports Excel et PDF testés, et les fichiers joints (icône,
flèche des listes), le thème clair et la traduction française des boutons de
Qt contrôlés. Tout doit être `OK` ; l'exécutable rend le code 1 sinon.

Cette vérification est lançable seule :

```bash
dist\Recharges-VE\Recharges-VE.exe --autotest rapport.txt
```

C'est indispensable après une modification du script de construction : sans
console en mode fenêtré, un exécutable amputé d'une bibliothèque démarre très
bien et ne casse qu'au moment d'ouvrir les Statistiques ou de lancer un export.

Elle tourne sur un **jeu de démonstration** de dix recharges, pas sur vos
données : sur une machine neuve, ou juste après une restauration, un fichier
vide ferait afficher « aucune donnée » partout sans rien prouver. Ces dix
recharges couvrent les deux lieux, les deux types de tarif et deux charges qui
passent minuit, et leurs montants sont calculés — jamais écrits en dur.

Pour la lancer sur vos vraies données :

```bash
dist\Recharges-VE\Recharges-VE.exe --autotest rapport.txt --donnees-reelles
```

---

## Organisation du code

| Fichier | Rôle |
|---|---|
| `app.py` | Le point d'entrée : lance la fenêtre (ou la vérification automatique avec `--autotest`). |
| `fenetre.py` | La fenêtre principale, en PySide6 (Qt) : menu de gauche, en-tête, aiguillage vers les pages, messages du démarrage, sauvegardes, vérification automatique. |
| `pages\` | Une page par fichier : `tableau_de_bord`, `ajouter`, `historique`, `statistiques`, `kilometrage`, `essence`, `importer`, `exporter`, `tarifs`, `parametres`, `restaurer`, `notice`, et `periode` (la barre « Période : ‹ année mois › »). Chacune expose `construire(fenetre)`, qui reçoit la fenêtre principale. |
| `dialogue_modifier.py`, `dialogue_tarif.py` | Les fenêtres de saisie : modifier une recharge, saisir un tarif. |
| `dialogue_km_frais.py` | Les fenêtres « Modifier le relevé » (page Kilométrage) et « Modifier les frais » (page Tarifs), pour corriger une faute sans supprimer puis recréer l'entrée. |
| `dialogue_colonnes.py` | La fenêtre « Colonnes du fichier » : importer l'export d'une borne qui n'a pas le format attendu. |
| `fenetres_aide.py` | Les fenêtres « Mise à jour » et « Votre avis » (elles passent par le navigateur : l'application ne se connecte à aucun serveur). |
| `suivi_saisie.py` | Repère ce qui a été tapé sans être enregistré, pour ne jamais le perdre sans prévenir. |
| `formulaire.py` | Les cases de saisie, avec leur message d'erreur sous la case fautive. |
| `composants.py`, `graphique.py` | Cartes, tuiles de chiffres ; le graphique des Statistiques (matplotlib). |
| `theme_qt.py` | L'apparence : les couleurs de Pécule, en thème clair ou sombre (Paramètres › Apparence), et la feuille de style. |
| `premier_theme.py` | La question « Clair ou Sombre ? » posée au tout premier lancement, avant l'ouverture de la fenêtre. |
| `menu.py`, `liens.py`, `notice_texte.py` | Le menu et les titres des pages ; les liens « Mise à jour » et « Votre avis » ; le texte de la notice. |
| `saisie.py` | La lecture de ce qui est tapé dans les formulaires, avec un message en français et le nom de la case fautive. Sans interface. |
| `erreurs.py` | Les erreurs techniques dites en français dans les messages. Module commun aux trois applications de l'auteur. |
| `sauvegarde_externe.py` | La copie vérifiée des données sur une clé USB ou un disque. Sans interface, commun aux trois applications. |
| `formats.py` | La mise en forme des valeurs (euros, kWh, dates). |
| `filtres.py` | Sélection par période, recherche, tri, regroupement. Fonctions pures, sans interface ni fichiers. |
| `constantes.py` | Nom, version, listes d'opérateurs et de cartes, colonnes du tableau. Ne dépend de rien. |
| `recharges.py` | Le cœur : lecture et écriture des données, calcul des coûts, import CSV, sauvegardes et sauvegarde GitHub. Ne dépend pas de l'interface. |
| `temps_reel.py` | Les durées vraies d'une recharge, y compris la nuit du changement d'heure (les heures sont rangées à l'heure de l'horloge). Ne dépend ni de Qt ni du reste de l'application. |
| `export.py` | Génération des fichiers Excel et PDF. À ne pas confondre avec `pages\exporter.py`, qui est la page : celui-ci fabrique les fichiers, celle-là affiche les boutons. |
| `build.bat` | Fabrication de l'exécutable et vérification. |
| `captures_site.py` | Les captures du site (`docs\media`), prises sur un jeu de démonstration inventé : aucune donnée réelle. |
| `preparer_distribution.py` | L'archive à donner : l'application sans les données de personne. |
| `faire_installeur.py` | L'installeur Windows à donner (`distribution\Recharges-VE-Setup-vX.Y.Z.exe`), après la construction de l'exe. Nécessite Inno Setup 6. |
| `installeur\recharges-ve.iss` | Recette de l'installeur, lue par Inno Setup. Son `AppId` ne doit jamais changer : c'est lui qui fait reconnaître une version déjà installée. |
| `fleche_bas.svg` | La flèche des listes déroulantes, redessinée par la feuille de style. |
| `icone_voiture.svg`, `generer_icone.py` | Le dessin de l'icône (vectoriel, à retoucher ici), et le script qui en tire `icone_voiture.ico` (sept tailles, chacune dessinée à sa taille) et `.png`. |
| `tests\test_recharges.py` | Tests du moteur de calcul et des données. |
| `tests\test_filtres.py` | Tests des filtres, du tri et des regroupements. |
| `tests\test_selecteur_periode.py` | Tests des deux menus et des deux flèches de la barre de période. |
| `tests\test_ce_mois.py` | Tests des raccourcis clavier de la barre de période. |
| `tests\test_qt_*.py` | Tests de l'interface, fenêtres construites hors écran (bouton « Ce mois-ci », pages, formulaires, vérification automatique). |
| `tests\test_menu.py` | Vérifie que chaque entrée du menu mène à une page qui existe et porte un titre. |
| `tests\test_isolation.py` | Le garde-fou : vérifie que les tests n'écrivent pas dans les vraies données. |
| `tests\conftest.py` | Redirige les données vers un dossier temporaire, avant tout le reste. |
| `requirements.txt` | Bibliothèques nécessaires pour faire tourner l'application. |
| `requirements-dev.txt` | En plus : les outils qui construisent et vérifient (pytest, pyinstaller, ruff). |
| `requirements.lock` | Les versions exactes du jour, pour refabriquer l'exe à l'identique. |
| `LICENSE` | Licence MIT. |

`recharges.py`, `saisie.py`, `formats.py`, `filtres.py` et `constantes.py` ne
dépendent pas de l'interface : tout ce qu'ils contiennent se teste sans ouvrir de fenêtre.

Le code est aussi vérifié par **ruff**, qui repère les imports devenus
inutiles et les variables jamais lues (configuration dans `ruff.toml`) :

```bash
py -m ruff check .
```

---

## Lancer les tests

```bash
py -m pytest
```

Toujours **pytest**, et non `py -m unittest discover` : unittest ne voit pas
les tests écrits au format pytest (une trentaine sont alors sautés sans
avertissement) et ne lit pas `tests/conftest.py`, qui détourne les données
vers un dossier temporaire pendant les tests.

Plus de 800 tests couvrent le calcul des coûts (tarif simple, heures pleines / heures
creuses, plage à cheval sur minuit, plages qui se chevauchent, recharge à
cheval sur un changement de tarif, session d'une minute, date sans tarif,
recharge sans heure de fin), la
proratisation de l'abonnement (mois de 28 et de 31 jours, changement de tarif
en cours de mois, tarif sans date de fin), la validation de la grille
tarifaire, la lecture de `tarifs.json`, l'import CSV, les sauvegardes et leur
restauration, le cache mémoire, et enfin les filtres, la recherche, le tri et
les regroupements.

**Les tests n'écrivent jamais dans vos données.** Ils posent la variable
d'environnement `RECHARGES_DATA_DIR` sur un dossier temporaire *avant*
d'importer `recharges.py` : `recharges.json`, `tarifs.json` et `backups\`
partent le temps de la séance dans ce dossier, effacé à la fin.

La même variable permet de faire tourner l'application entière sur une copie
de vos données, pour essayer une modification sans risque :

```bash
set RECHARGES_DATA_DIR=C:\essai
py app.py
```

(dans PowerShell : `$env:RECHARGES_DATA_DIR = "C:\essai"`)

Sans cette variable, rien ne change : les données restent dans `dist\`.

---

## Licence

MIT — voir `LICENSE`. Faites-en ce que vous voulez, sans garantie.
