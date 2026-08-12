# Squat GUI

Interface graphique 2D pour explorer un squat avec:

- modele pied, jambe, cuisse, tronc/tete/bras et barre, en prise `front`, `back` ou `over-head`;
- sujet homme ou femme enceinte de reference, 70 kg pour 1.70 m, inerties gauche/droite combinees en 2D;
- charge exprimee en `%BW` (pour le sujet de 70 kg) avec 11 choix de `0` a `100 %BW`, longueurs discretes et wedge de 20 deg;
- mouvement en trois phases reglables: excentrique et concentrique entre 2 et 6 s, isometrique entre 0 et 2 s;
- cinematique d'ordre 5 type Yeadon, issue du profil `6x^5 - 15x^4 + 10x^3`;
- dynamique inverse analytique 2D de demarrage;
- calcul de la reaction au sol, du centre de pression, du CoM et de sa projection;
- animation avec CoM, projection au sol, force de contact et bras de levier pointilles;
- contraintes de couples max avec feedback vert/rouge;
- relation couple max-angle optionnelle;
- images `refined` par sujet et prise de barre, avec retour `low quality`.

Le code contient aussi un backend optionnel `biorbd`; la présence éventuelle de `biobuddy` est diagnostiquée mais n'est pas requise par les calculs actuels. Si `biorbd` n'est pas installé, l'application reste exécutable avec le solveur analytique pur Python.

## Utilisation pedagogique

Le switch dans `Parcours didactique` affiche une consigne a la fois et pilote une révélation progressive. Le contrôle ou la figure à regarder est surligné dans la couleur du mot clé de l'étape:

1. choisir `homme` ou `femme enceinte`;
2. choisir la prise de barre;
3. augmenter progressivement la charge, initialement a `0 %BW`;
4. choisir un preset temporel ou régler indépendamment les trois durées de phase;
5. definir la position basse en glissant genou, hanche et epaules;
6. observer l'animation seule et formuler une hypothèse, sans valeur ni courbe révélée;
7. passer en `CINÉMATIQUE`, choisir la vue synchronisée et le repère temporel, déplacer le curseur et lire l'inspecteur numérique;
8. passer en `DYNAMIQUE` pour les forces, le CoP/ZMP, les couples et les capacités;
9. cliquer sur `Ajouter`;
10. sélectionner la référence, cliquer sur `Dupliquer`, changer un seul paramètre puis ajouter le nouvel essai;
11. sélectionner deux conditions et lire l'onglet `Variables contrôlées` pour vérifier les différences.

Les longueurs segmentaires, les couples max et les couples detailles sont des outils avances. `Sauver conditions` et `Charger conditions` ecrivent/lisent un fichier JSON comprenant les widgets et, si demande, les conditions ajoutees au tableau.

Les six presets temporels sont `Référence` (4/2/4 s), `Lent` (6/2/6 s), `Rapide` (2/0,5/2 s), `Sans pause` (4/0/4 s), `Descente lente / remontée rapide` (6/1/2 s) et son inverse (2/1/6 s). Les trois contrôles numériques restent disponibles; une combinaison qui ne correspond à aucun preset est indiquée `Personnalisé`.

La simulation utilise par défaut un pas temporel constant `Δt=0,05 s`. Le nombre de frames inclut les deux extrémités et s'adapte donc à la durée totale : `N = durée/0,05 + 1` (201 frames pour 10 s, 281 pour le preset lent de 14 s). La lecture avance à 20 images/s et respecte le temps physique.

Le sélecteur à côté du curseur propose `LIBRE`, `OBSERVATION`, `CINÉMATIQUE` et `DYNAMIQUE`. `OBSERVATION` masque courbes, temps, phases, valeurs, alertes et grandeurs mécaniques. `CINÉMATIQUE` limite les courbes aux articulations et au CoM, avec le choix position/vitesse/accélération. `DYNAMIQUE` ajoute forces, CoP/ZMP, poids, bases d'appui, couples et capacité. Le parcours didactique impose ces états dans cet ordre; hors parcours, le sélecteur reste directement contrôlable.

En mode `LIBRE`, le menu `Affichage` centralise les couches de la figure de droite. Il permet notamment d'activer les coordonnées articulaires au survol, les orientations segmentaires, les angles articulaires, l'anthropométrie utilisée, le CoM global ou segmentaire, le point d'appui CoP/ZMP, la GRF, le poids, les bases géométrique/fonctionnelle et le bilan d'équilibre. Changer un état de révélation ou une couche ne relance pas la simulation et ne remplace pas les choix libres mémorisés. La ligne sous le curseur donne la frame, le temps absolu, le pas temporel `Δt`, le temps normalisé et la phase, sauf en `OBSERVATION` où elle reste masquée.

La courbe `cinématique synchronisée` affiche simultanément position, vitesse et accélération sur trois axes empilés partageant exactement la même abscisse. La source peut être les angles articulaires ou le CoM; les unités et les lignes de zéro sont indiquées séparément sur chaque axe. Cliquer ou glisser dans n'importe lequel des trois axes déplace le même curseur rouge, l'animation et l'onglet `Valeurs au curseur`. Cet onglet donne, pour chaque courbe visible et chaque condition, la valeur échantillonnée à six décimales, son unité, son temps réel sur la courbe et sa phase.

Le menu `Phases` des résultats contrôle séparément les deux limites de phase et les noms `excentrique`, `isométrique` et `concentrique`. Masquer les noms masque aussi la phase dans l'inspecteur numérique, sans modifier les calculs ni les données exportées.

Le repère temporel offre trois lectures distinctes : `absolu` de 0 à la durée totale, `centré` sur le milieu de la pause basse et `normalisé` de 0 à 100 %. Le mode normalisé affiche un avertissement, car il rend comparables les événements relatifs mais masque les différences de durée. L'ancien repère normalisé `−100…+100` est remplacé par la convention `0…100 %`.

Le menu `Affichage` est le point central de toutes les sélections visuelles : courbes articulaires, composantes horizontale/verticale, axes, limites de couple, phases et couches de l'animation. Ces choix déclenchent uniquement un nouveau rendu; aucune simulation n'est relancée.

Pour une comparaison contrôlée, sélectionner une condition puis cliquer sur `Dupliquer`. La condition est copiée dans l'éditeur sans créer immédiatement une nouvelle ligne. Après modification d'un paramètre et `Ajouter`, la colonne `modifications contrôlées` et l'onglet `Variables contrôlées` listent les différences scientifiques; les réglages purement visuels sont volontairement exclus.

La couche `Anthropometrie utilisee` montre le mode, les longueurs et masses effectives. Lorsque `CoM segmentaires + barre` est active, le survol d'un CoM donne sa position, sa masse, sa fraction/son offset, son inertie et ses contributions ponderees `m*x` et `m*y`. La couche `Echantillons i-1 / i / i+1` affiche trois frames distinctes avec temps absolu, phase, CoM, angles articulaires et les deux pas temporels disponibles.

Limites de pose imposees par l'interface:

- cheville: -30 deg en flexion plantaire a +40 deg en flexion dorsale;
- genou: -140 a 0 deg;
- hanche: -15 a +120 deg.

## Hypotheses des nouvelles conditions

La barre est un segment ponctuel ajoute au modele `.bioMod`; sa masse est `70 * Charge %BW / 100`. Dans l'interface, la charge prend 11 valeurs discretes: `0, 10, ..., 100 %BW`. Sa position locale par rapport aux epaules est modifiee selon la prise: en avant pour `front`, en arriere pour `back`, et au milieu des mains au-dessus des epaules pour `over-head`. Le CoM du segment regroupe `tronc-tete-bras` est aussi deplace pour representer le changement de posture des bras. Les trois prises modifient donc géométrie, CoM, dynamique, cache `.bioMod`, export et comparaison, mais ni la masse de barre ni l'inertie propre du tronc à sujet/morphotype identiques. La barre reste ponctuelle: son orientation, sa longueur et son inertie propre ne sont pas modélisées.

La version `femme enceinte` est actuellement un scenario didactique initial, pas un modele clinique valide: elle conserve une masse corporelle totale de 70 kg pour permettre des comparaisons controlees, deplace le CoM du segment tronc de `+0.060 m` vers l'avant et multiplie son moment d'inertie par `1.18`. Ces deux coefficients sont centralises dans [anthropometry.py](src/squat_gui/anthropometry.py) et devront etre remplaces ou calibres a partir d'un jeu anthropometrique de grossesse choisi pour le cours.

### Parametres anthropometriques des membres inferieurs

Les masses, positions de CoM et rayons de giration du pied, de la jambe et de la cuisse reposent sur les parametres Dempster/Winter pour un modele combine gauche-droite: Winter, D. A. (2009), *Biomechanics and Motor Control of Human Movement*, 4th edition, Wiley. Les fractions de masse bilaterales du modele sont `2.9 %` pour les pieds, `9.3 %` pour les jambes et `20.0 %` pour les cuisses.

La convention d'origine est importante dans ce GUI:

- le pied est defini du talon vers les orteils; sa fraction de CoM est donc appliquee depuis le talon;
- la jambe est definie de la cheville vers le genou, alors que la table donne le CoM depuis le genou: la fraction utilisee est `1 - 0.433 = 0.567`;
- la cuisse est definie du genou vers la hanche, alors que la table donne le CoM depuis la hanche: la fraction utilisee est `1 - 0.433 = 0.567`.

Le profil `femme enceinte` conserve les parametres de membres inferieurs de la reference de base puis ajoute la modification didactique de grossesse au segment superieur. Le segment `tronc-tete-bras` n'est pas un segment anatomique isole de la table: il regroupe le reste du corps et la posture des bras autour de la barre. Sa position de CoM et son ajustement d'inertie restent donc des hypotheses pedagogiques explicites.

Deux modes rendent les variations de longueur interprétables :

- `longueur seule` isole la géométrie en conservant les masses et les inerties de référence; le facteur interne d'inertie compense exactement le changement de longueur;
- `morphotype recalibre` est une sensibilité didactique à densité linéique constante: chaque fraction massique de référence est multipliée par l'échelle de longueur du segment, les quatre masses sont renormalisées à la masse corporelle, puis les inerties sont recalculées par `I = m(kL)^2`.

Le second mode n'est pas une régression anthropométrique populationnelle. Le mode, la règle, les fractions massiques, masses, longueurs et inerties effectivement utilisées sont affichés et exportés.

Le wedge fait tourner le pied de 20 deg en surelevant le talon dans la geometrie 2D et dans le `.bioMod` genere. La pose debout de reference applique simultanement `-20 deg` a la cheville, afin de conserver la jambe et le tronc verticaux hors de la position basse. Le contact reste represente sur le plan du sol horizontal; il s'agit donc d'une exploration du changement de configuration, et non d'un modele de contact complet du wedge.

### Repere et conventions cinematiques

- Le repere global est plan : `x` est horizontal vers l'avant, `y` vertical vers le haut; les coordonnees sont en metres.
- Les orientations segmentaires absolues sont mesurees depuis l'axe global `+x`, dans le sens anti-horaire positif. Elles sont exportees pour le pied, la jambe, la cuisse et le tronc.
- L'angle de cheville est la dorsiflexion signee de la jambe relativement au pied. Cette reconstruction tient compte du wedge.
- L'angle de genou conserve la convention historique du modele : la flexion de squat est negative.
- L'angle de hanche est positif lorsque le tronc est oriente vers l'avant relativement a la cuisse dans la convention du squat.
- Les calculs utilisent les radians; le GUI et les exports pedagogiques utilisent les degres.

Le CoM global est reconstruit sans approximation supplementaire depuis les points segmentaires affiches :

```text
x_COM = somme(m_i * x_i) / somme(m_i)
y_COM = somme(m_i * y_i) / somme(m_i)
```

La barre est un point materiel dans le backend analytique. Sa masse contribue au CoM global; sa longueur, sa fraction de CoM et son inertie analytique sont nulles. Ses offsets d'attache relativement au tronc sont exportes separement.

### Derivees du centre de masse

Le backend analytique calcule les vitesses et accelerations de chaque CoM segmentaire par derivation de la geometrie, puis applique la meme ponderation massique que pour la position globale. La vitesse du CoM exportee n'est donc plus une valeur nulle de remplacement. Les tests comparent ces derivees analytiques aux differences centrees des positions et vitesses.

Le panneau trois echantillons fournit les donnees pour refaire manuellement, a une frame interieure:

```text
v_i ≈ (x_(i+1) - x_(i-1)) / (t_(i+1) - t_(i-1))
a_i ≈ (v_(i+1) - v_(i-1)) / (t_(i+1) - t_(i-1))
```

Aux premieres et dernieres frames, l'echantillon absent est indique comme indisponible plutot que dupliquer une frame. Le CSV conserve une ligne par frame avec le temps, `Δt` et toutes les coordonnees necessaires a ces calculs.

## Version locale "un clic" pour les etudiants

L'objectif de cette option est que l'etudiant n'installe pas Python, ne cree pas d'environnement conda et ne tape aucune commande. Il recoit une application deja empaquetee.

Ce que recoit l'etudiant:

- Windows: un fichier `.zip` contenant le dossier `Squat GUI`, puis double-clic sur `Squat GUI.exe`;
- macOS: un fichier `.zip` contenant `Squat GUI.app`, puis double-clic sur l'application.

Ce que fait la personne qui prepare le cours:

1. construire l'application une fois sur Windows pour les etudiants Windows;
2. construire l'application une fois sur macOS pour les etudiants macOS;
3. tester les deux fichiers obtenus sur un ordinateur propre;
4. distribuer les `.zip`.

Les fichiers de packaging sont dans `packaging/`:

- `packaging/squat_gui.spec`: configuration PyInstaller;
- `packaging/build_windows.ps1`: build Windows;
- `packaging/build_macos.sh`: build macOS;
- `packaging/squat_gui_launcher.py`: point d'entree GUI pour l'application empaquetee.

### Construire la version macOS

Sur un Mac, ouvrir `Terminal`, aller dans le dossier du projet, activer l'environnement qui contient les dependances voulues, puis lancer:

```bash
conda activate squat-gui
bash packaging/build_macos.sh
```

Sorties attendues:

- `dist/Squat GUI.app`;
- `dist/Squat GUI/`.

Distribuer de preference `dist/Squat GUI.app` compresse en `.zip`. Si macOS bloque l'application parce qu'elle n'est pas signee, faire clic droit sur `Squat GUI.app`, puis `Ouvrir`, puis confirmer `Ouvrir`.

### Construire la version Windows

Sur Windows, ouvrir `Anaconda Prompt` ou PowerShell dans le dossier du projet, activer l'environnement qui contient les dependances voulues, puis lancer:

```powershell
conda activate squat-gui
powershell -ExecutionPolicy Bypass -File packaging\build_windows.ps1
```

Sortie attendue:

```text
dist\Squat GUI\Squat GUI.exe
```

Distribuer le dossier complet `dist\Squat GUI` compresse en `.zip`. Il ne faut pas sortir le `.exe` de son dossier, car les bibliotheques et les assets sont a cote.

### Inclure ou non biorbd dans l'application

Par défaut, les scripts créent un build simple qui n'embarque pas `biorbd`. C'est le choix recommandé pour une première distribution étudiante : le fichier est plus léger et moins sensible aux bibliothèques natives.

Pour produire un build complet qui tente d'embarquer les backends optionnels, activer explicitement:

macOS:

```bash
conda activate squat-gui
SQUAT_GUI_INCLUDE_OPTIONAL_BACKENDS=1 bash packaging/build_macos.sh
```

Windows PowerShell:

```powershell
conda activate squat-gui
$env:SQUAT_GUI_INCLUDE_OPTIONAL_BACKENDS = "1"
powershell -ExecutionPolicy Bypass -File packaging\build_windows.ps1
```

Pour un deploiement etudiant, le plus prudent est de produire deux builds propres:

- build simple, sans `biorbd`, plus leger et plus facile a distribuer;
- build complet, avec `biorbd`, a tester sur une machine Windows/macOS comparable a celles des etudiants.

Important: le build complet doit etre fait depuis un environnement ou `import biorbd` et les fonctions utilisees par le GUI fonctionnent reellement. Si un paquet `biorbd` est present mais incompatible avec la version de Python, rester sur le build simple ou corriger l'environnement avant de construire.

### Verification minimale avant distribution

La recette reproductible complète, y compris les validateurs d'archive avec profil
utilisateur vierge, est décrite dans
[`packaging/RECETTE_DISTRIBUTION.md`](packaging/RECETTE_DISTRIBUTION.md).

Avant d'envoyer le `.zip`, tester:

1. ouvrir l'application par double-clic;
2. verifier que les images refined s'affichent;
3. changer sujet, prise de barre, wedge et charge;
4. cliquer sur `Ajouter`;
5. creer une deuxieme condition et comparer;
6. sauvegarder puis recharger un JSON de conditions.

## Installation de A a Z

Cette section est volontairement tres detaillee. L'objectif est qu'une personne qui n'a jamais installe Python puisse lancer le GUI.

Il y a deux niveaux possibles:

- installation simple: le GUI se lance, avec le solveur analytique Python et les images de segments;
- installation complete biorbd: le GUI utilise `biorbd` pour la dynamique inverse, le CoM, et le ZMP si la version installee expose `CalcZeroMomentPoint`.

Pour une premiere installation, suivre uniquement les sections 0 a 5. Les sections 6 et 7 sur `biorbd` peuvent etre faites plus tard.

### 0. Vocabulaire minimal

- `Terminal` sur macOS et `Anaconda Prompt` sur Windows sont les fenetres ou on tape les commandes.
- `conda` sert a creer un environnement Python propre, separe du reste de l'ordinateur.
- `squat-gui` sera le nom de l'environnement conda.
- Quand une commande commence par `conda activate squat-gui`, il faut voir quelque chose comme `(squat-gui)` au debut de la ligne suivante.
- Ne pas taper les signes `$` ou `>` si vous les voyez dans un tutoriel; ici les blocs de code contiennent seulement les commandes a copier.

### 0.5. Les trois verifications qui evitent presque toutes les erreurs

Avant de copier les commandes d'installation, verifier ces trois points.

1. Vous etes dans le bon dossier du projet.

Le dossier courant doit contenir au minimum:

- `README.md`;
- `pyproject.toml`;
- le dossier `src`;
- le dossier `assets`.

Pour verifier sur Windows:

```bat
dir
```

Pour verifier sur macOS:

```bash
ls
```

Si ces fichiers n'apparaissent pas, vous n'etes pas dans le bon dossier. C'est frequent apres extraction d'un `.zip`: il peut y avoir un dossier dans un dossier, par exemple `Squat_GUI-main\Squat_GUI-main`, ou vous pouvez etre reste dans `Downloads`.

2. L'environnement conda doit etre cree avant d'etre active.

La commande:

```bash
conda activate squat-gui
```

ne fonctionne que si cette commande a deja reussi au moins une fois:

```bash
conda create -n squat-gui python=3.11 -y
```

Si vous voyez `EnvironmentNameNotFound: Could not find conda environment: squat-gui`, ce n'est pas grave: cela veut simplement dire que l'environnement n'a pas encore ete cree. Revenir a la section 3 et commencer par `conda create`.

3. Si conda bloque sur des conditions d'utilisation, les accepter.

Sur certaines installations recentes de conda/Anaconda, `conda create` peut s'arreter avec un message du type `Terms of Service have not been accepted`. Dans ce cas, executer:

```bash
conda tos accept --override-channels --channel https://repo.anaconda.com/pkgs/main
conda tos accept --override-channels --channel https://repo.anaconda.com/pkgs/r
```

Puis relancer:

```bash
conda create -n squat-gui python=3.11 -y
```

Si `conda tos` n'existe pas, mettre conda a jour puis reessayer:

```bash
conda update -n base conda -y
```

### 1. Installer Conda

Le plus simple est d'installer Miniconda. C'est la version legere de conda, recommandee pour ce type de projet. Documentation officielle: <https://www.anaconda.com/docs/getting-started/miniconda/install>.

#### Windows

1. Aller sur <https://www.anaconda.com/docs/getting-started/miniconda/install>.
2. Telecharger l'installateur Miniconda Windows 64-bit.
3. Double-cliquer sur le fichier `.exe`.
4. Choisir `Install Just for Me` si l'installateur pose la question.
5. Garder le dossier propose par defaut, par exemple `C:\Users\votre_nom\miniconda3`.
6. Laisser coche `Register Miniconda3 as my default Python`.
7. Finir l'installation.
8. Ouvrir le menu Demarrer et chercher `Anaconda Prompt`.
9. Dans `Anaconda Prompt`, verifier:

```bat
conda --version
```

Si une version s'affiche, conda est installe.

#### macOS / OS X

Sur macOS recent, ouvrir `Terminal` avec `Cmd + Espace`, taper `Terminal`, puis `Entree`.

Pour Mac Apple Silicon (M1/M2/M3/M4), copier ces commandes une par une:

```bash
mkdir -p ~/miniconda3
curl https://repo.anaconda.com/miniconda/Miniconda3-latest-MacOSX-arm64.sh -o ~/miniconda3/miniconda.sh
bash ~/miniconda3/miniconda.sh -b -u -p ~/miniconda3
rm ~/miniconda3/miniconda.sh
~/miniconda3/bin/conda init zsh
```

Fermer puis rouvrir `Terminal`, puis verifier:

```bash
conda --version
```

Pour Mac Intel ancien, utiliser plutot Miniforge ou un installateur Intel disponible dans les archives Miniconda, car Anaconda a arrete les nouveaux builds Intel macOS apres 2025. La documentation conda mentionne Miniforge comme distribution conda compatible conda-forge: <https://docs.conda.io/en/main/>.

### 2. Recuperer le dossier du projet

Si le projet est fourni en dossier ou en `.zip`, placer le dossier `Squat_GUI` dans `Documents`.

Cas le plus frequent avec un ZIP:

1. Telecharger le `.zip`.
2. L'extraire.
3. Renommer le dossier extrait en `Squat_GUI` si necessaire.
4. Deplacer ce dossier dans `Documents`.
5. Ouvrir `Anaconda Prompt` sur Windows ou `Terminal` sur macOS.
6. Aller dans le dossier du projet.

Si le projet est disponible via Git, installer Git puis cloner le depot. Exemple, a adapter avec la vraie URL du depot:

Windows:

```bat
cd /d %USERPROFILE%\Documents
git clone URL_DU_DEPOT Squat_GUI
cd Squat_GUI
```

macOS:

```bash
cd ~/Documents
git clone URL_DU_DEPOT Squat_GUI
cd Squat_GUI
```

Si le dossier existe deja:

Windows:

```bat
cd /d %USERPROFILE%\Documents\Squat_GUI
```

macOS:

```bash
cd ~/Documents/Squat_GUI
```

Verifier ensuite que le dossier est complet.

Windows:

```bat
dir README.md pyproject.toml src assets
```

macOS:

```bash
ls README.md pyproject.toml src assets
```

Si une erreur indique qu'un fichier ou dossier est introuvable, ne pas continuer l'installation. Rechercher le vrai dossier qui contient `pyproject.toml`, puis refaire le `cd`.

### 3. Creer l'environnement conda

Dans `Anaconda Prompt` sur Windows, ou dans `Terminal` sur macOS:

```bash
conda create -n squat-gui python=3.11 -y
```

Si conda affiche une erreur sur des conditions d'utilisation non acceptees (`Terms of Service`), executer les deux commandes suivantes, puis relancer le `conda create`:

```bash
conda tos accept --override-channels --channel https://repo.anaconda.com/pkgs/main
conda tos accept --override-channels --channel https://repo.anaconda.com/pkgs/r
```

Quand `conda create` est termine, activer l'environnement:

```bash
conda activate squat-gui
```

Verifier que le debut de la ligne contient `(squat-gui)`. Si ce n'est pas le cas, ne pas installer les paquets tout de suite: reessayer `conda activate squat-gui`.

Installer les paquets de base:

```bash
conda install -c conda-forge numpy pillow tk git -y
python -m pip install -e .
```

`pillow` sert a afficher les images de segments. Si Pillow manque, le GUI peut revenir aux formes vectorielles, mais l'animation est moins jolie.

### 4. Lancer le GUI en mode simple

Toujours depuis le dossier `Squat_GUI`, avec l'environnement active:

```bash
python -m squat_gui
```

Le GUI doit s'ouvrir. Si la barre du bas indique que `biorbd` manque, ce n'est pas bloquant: l'application utilise alors le backend analytique Python.

Pour relancer plus tard:

Windows:

```bat
cd /d %USERPROFILE%\Documents\Squat_GUI
conda activate squat-gui
python -m squat_gui
```

macOS:

```bash
cd ~/Documents/Squat_GUI
conda activate squat-gui
python -m squat_gui
```

### 5. Tester que l'installation simple est correcte

```bash
python -m unittest discover -s tests
```

On veut voir `OK` a la fin. Certains warnings SWIG peuvent apparaitre si `biorbd` est installe; ce n'est pas grave.

### 6. Installer biorbd sans compiler

Cette etape donne le backend `biorbd` standard depuis conda-forge. Documentation du paquet: <https://anaconda.org/conda-forge/biorbd>.

```bash
conda activate squat-gui
conda install -c conda-forge biorbd -y
```

Relancer:

```bash
python -m squat_gui
```

Si tout va bien, la barre du bas indique `biorbd actif`. Si elle indique encore le backend analytique, verifier que vous avez bien lance le GUI dans l'environnement `(squat-gui)`.

Important: selon la version installee, `biorbd` peut ne pas encore exposer `CalcZeroMomentPoint`. Dans ce cas, le GUI utilise quand meme `biorbd` pour la dynamique, mais garde un fallback analytique pour le centre de pression.

### 7. Installation complete avec ZMP biorbd

Pour que la barre du bas indique `biorbd actif (ZMP biorbd)`, il faut une version de `biorbd` qui expose `Model.CalcZeroMomentPoint(...)`. Une PR a ete preparee ici: <https://github.com/pyomeca/biorbd/pull/383>.

Si cette PR a ete fusionnee et publiee sur conda-forge, refaire simplement:

```bash
conda install -c conda-forge biorbd -y
```

Puis verifier:

```bash
python -c "import biorbd; m=biorbd.Model(); print(hasattr(m, 'CalcZeroMomentPoint'))"
```

Si la commande affiche `True`, c'est bon.

Si la commande affiche `False`, il faut compiler la branche de la PR.

#### macOS: compiler biorbd avec la PR ZMP

Installer d'abord les outils Apple:

```bash
xcode-select --install
```

Si macOS repond que les outils sont deja installes, c'est bon.

Installer les outils de compilation dans l'environnement:

```bash
conda activate squat-gui
conda install -c conda-forge cmake ninja "swig=4.3.1" eigen tinyxml2 rbdl ipopt numpy scipy -y
```

Recuperer biorbd:

```bash
mkdir -p ~/Documents/GIT
cd ~/Documents/GIT
git clone https://github.com/pyomeca/biorbd.git
cd biorbd
git fetch origin pull/383/head:codex/calc-zero-moment-point
git checkout codex/calc-zero-moment-point
```

Configurer, compiler et installer dans l'environnement actif:

```bash
PATH="$CONDA_PREFIX/bin:$PATH" cmake -S . -B build-squat -G Ninja \
  -DCMAKE_PREFIX_PATH="$CONDA_PREFIX" \
  -DCMAKE_INSTALL_PREFIX="$CONDA_PREFIX" \
  -DMATH_LIBRARY_BACKEND=Eigen3 \
  -DBINDER_PYTHON3=ON \
  -DBUILD_EXAMPLE=OFF \
  -DBUILD_TESTS=OFF \
  -DSWIG_EXECUTABLE="$CONDA_PREFIX/bin/swig" \
  -DSWIG_DIR="$CONDA_PREFIX/share/swig/4.3.1" \
  -DPython3_EXECUTABLE="$CONDA_PREFIX/bin/python" \
  -DPython3_ROOT_DIR="$CONDA_PREFIX" \
  -DPython3_NumPy_INCLUDE_DIRS="$(python -c 'import numpy; print(numpy.get_include())')" \
  -DPython3_SITELIB_INSTALL="$CONDA_PREFIX/lib/python3.11/site-packages"

cmake --build build-squat --target install
```

Verifier:

```bash
python -c "import biorbd; m=biorbd.Model(); print(biorbd.__version__); print(hasattr(m, 'CalcZeroMomentPoint'))"
```

On veut `True` sur la deuxieme ligne.

Pour valider le calcul ZMP avant installation, il est aussi possible de compiler les tests avec `-DBUILD_TESTS=ON`, puis d'executer:

```bash
./build-squat/test/biorbd_eigen_tests --gtest_filter=CoM.zeroMomentPoint
```

Sur Mac Apple Silicon, utiliser la compilation CMake directe ci-dessus plutot que `pip install .` si `scikit-build` signale un melange de dossiers `arm64` et `x86_64`: l'emballage Python de la branche peut encore construire son chemin d'installation avec le mauvais nom d'architecture, alors que le module CMake arm64 et son test ZMP fonctionnent correctement.

#### Windows: compiler biorbd avec la PR ZMP

Installer d'abord:

1. Git for Windows: <https://git-scm.com/download/win>.
2. Visual Studio Build Tools 2022: <https://visualstudio.microsoft.com/visual-cpp-build-tools/>.
3. Dans l'installateur Visual Studio, cocher `Desktop development with C++`, puis installer.
4. Redemarrer Windows si l'installateur le demande.

Ouvrir `Anaconda Prompt`, puis:

```bat
conda activate squat-gui
conda install -c conda-forge cmake ninja swig=4.3.1 eigen tinyxml2 rbdl ipopt numpy scipy -y
```

Recuperer biorbd:

```bat
cd /d %USERPROFILE%\Documents
mkdir GIT
cd GIT
git clone https://github.com/pyomeca/biorbd.git
cd biorbd
git fetch origin pull/383/head:codex/calc-zero-moment-point
git checkout codex/calc-zero-moment-point
```

Configurer, compiler et installer:

```bat
cmake -S . -B build-squat -G Ninja ^
  -DCMAKE_PREFIX_PATH="%CONDA_PREFIX%" ^
  -DCMAKE_INSTALL_PREFIX="%CONDA_PREFIX%" ^
  -DMATH_LIBRARY_BACKEND=Eigen3 ^
  -DBINDER_PYTHON3=ON ^
  -DBUILD_EXAMPLE=OFF ^
  -DBUILD_TESTS=OFF ^
  -DSWIG_EXECUTABLE="%CONDA_PREFIX%\Library\bin\swig.exe" ^
  -DPython3_EXECUTABLE="%CONDA_PREFIX%\python.exe" ^
  -DPython3_ROOT_DIR="%CONDA_PREFIX%" ^
  -DPython3_SITELIB_INSTALL="%CONDA_PREFIX%\Lib\site-packages"

cmake --build build-squat --target install
```

Verifier:

```bat
python -c "import biorbd; m=biorbd.Model(); print(biorbd.__version__); print(hasattr(m, 'CalcZeroMomentPoint'))"
```

On veut `True` sur la deuxieme ligne.

### 8. Lancer apres installation complete

Retourner au projet:

Windows:

```bat
cd /d %USERPROFILE%\Documents\Squat_GUI
conda activate squat-gui
python -m squat_gui
```

macOS:

```bash
cd ~/Documents/Squat_GUI
conda activate squat-gui
python -m squat_gui
```

La barre du bas doit indiquer:

```text
biorbd actif (ZMP biorbd): ...
```

### 9. Problemes frequents

- `conda n'est pas reconnu`: fermer puis rouvrir `Anaconda Prompt` ou `Terminal`. Sur macOS, lancer `~/miniconda3/bin/conda init zsh`, fermer puis rouvrir.
- `EnvironmentNameNotFound: squat-gui`: l'environnement n'a pas encore ete cree. Lancer `conda create -n squat-gui python=3.11 -y`, attendre la fin, puis seulement ensuite `conda activate squat-gui`.
- `Terms of Service have not been accepted`: lancer `conda tos accept --override-channels --channel https://repo.anaconda.com/pkgs/main`, puis `conda tos accept --override-channels --channel https://repo.anaconda.com/pkgs/r`, et relancer la commande qui avait bloque.
- `DirectoryNotFoundError`, `No such file or directory`, ou `pyproject.toml` introuvable: vous n'etes pas dans le dossier racine du projet. Aller dans le dossier qui contient `README.md`, `pyproject.toml`, `src` et `assets`.
- `No module named squat_gui`: vous n'etes probablement pas dans le dossier `Squat_GUI`, ou `python -m pip install -e .` n'a pas ete lance.
- `No module named PIL`: lancer `conda install -c conda-forge pillow -y`.
- `No module named biorbd`: lancer `conda install -c conda-forge biorbd -y`, ou continuer avec le backend analytique.
- message `compiled using NumPy 1.x cannot be run in NumPy 2.x`: reinstaller/recompiler `biorbd` contre la version de NumPy de l'environnement, ou creer un environnement avec `numpy<2` compatible avec le binaire installe.
- `Could NOT find SWIG`: verifier `swig=4.3.1`, puis relancer la commande CMake avec `-DSWIG_EXECUTABLE=...`.
- `hasattr(m, 'CalcZeroMomentPoint')` affiche `False`: la version installee de `biorbd` ne contient pas encore la PR ZMP; compiler la branche PR ou attendre la release conda-forge.
- Le GUI s'ouvre mais les images sont moches ou absentes: installer Pillow, puis relancer.
- Le GUI ne s'ouvre pas sur macOS a cause de Tk: verifier que vous utilisez le Python de l'environnement conda et que `tk` est installe avec `conda install -c conda-forge tk -y`.

## Lancer rapidement sur cette machine

Depuis ce dossier, si l'environnement local `vitpose-ekf` existe deja:

```bash
PYTHONPATH=src /Users/mickaelbegon/miniconda3/envs/vitpose-ekf/bin/python -m squat_gui
```

Sinon, apres `python -m pip install -e .` dans l'environnement conda actif:

```bash
python -m squat_gui
```

## Ligne de commande pour generer des conditions

La ligne de commande permet de creer rapidement des conditions de squat sans ouvrir le GUI et d'exporter les resultats pour analyse dans Python, R, Matlab, Excel ou un notebook.

Deux entrees sont disponibles:

```bash
python -m squat_gui run ...
python -m squat_gui batch conditions.csv ...
```

Si le paquet a ete installe avec `python -m pip install -e .`, on peut aussi utiliser:

```bash
squat-gui-cli run ...
squat-gui-cli batch conditions.csv ...
```

### Exporter une condition unique

Exemple analytique, sans forcer biorbd:

```bash
python -m squat_gui run \
  --condition-id front_80bw \
  --subject-profile homme \
  --bar-position front \
  --load-percent-bw 80 \
  --duration-excentrique 3 \
  --duration-isometrique 2 \
  --duration-concentrique 3 \
  --joint-angles-deg 22 -80 78 \
  --torque-preset sportifs \
  --backend analytical \
  --frames 0 \
  --out exports/front_80bw.csv \
  --summary exports/front_80bw_summary.json \
  --xlsx exports/front_80bw.xlsx
```

Exemple avec biorbd obligatoire:

```bash
python -m squat_gui run \
  --condition-id squat_biorbd \
  --bar-position over-head \
  --load-percent-bw 30 \
  --wedge \
  --backend biorbd \
  --out exports/squat_biorbd.csv \
  --summary exports/squat_biorbd_summary.json
```

Si `--backend biorbd` est demande et que biorbd n'est pas disponible, la commande s'arrete avec une erreur. Avec `--backend auto`, la CLI essaie biorbd et retombe sur l'analytique si biorbd n'est pas utilisable.

Arguments utiles:

- `--subject-profile`: `homme` ou `femme enceinte`;
- `--bar-position`: `front`, `back` ou `over-head`;
- `--load-percent-bw`: charge de barre en pourcentage du poids du sujet de 70 kg;
- `--load KG`: compatibilite avec les scripts historiques, prioritaire sur `%BW`;
- `--wedge`: ajoute la talonnette de 20 deg;
- `--shank`, `--thigh`, `--trunk`: variations de longueur en pourcentage;
- `--anthropometry-mode "longueur seule"` ou `"morphotype recalibre"`;
- `--duration-excentrique`, `--duration-concentrique`: durees entre 2 et 6 s;
- `--duration-isometrique`: duree entre 0 et 2 s;
- `--joint-angles-deg ANKLE KNEE HIP`: angles articulaires finaux en degres;
- `--q-segment-deg SHANK THIGH TRUNK`: angles segmentaires finaux en degres, convention interne du modele;
- `--torque-preset anderson` ou `--torque-preset sportifs`;
- `--max-cheville`, `--max-genou`, `--max-hanche`: surcharge manuelle des couples max;
- `--angle-adapt true/false`: active/desactive la relation couple-angle;
- `--velocity-adapt true/false`: active/desactive la relation couple-vitesse;
- `--frames`: nombre de frames exportees.
- sans `--frames` (ou avec `--frames 0`), la CLI applique automatiquement `Δt=0,05 s`;
- `--xlsx`: classeur Excel global optionnel, construit depuis les memes lignes que le CSV.

Le CSV exporte utilise le schema versionne `1.4.0` et contient une ligne par frame avec:

- frame, temps absolu, `Δt`, temps normalise, phase et backend;
- parametres de condition;
- coordonnees `x/y` en metres de la cheville, du genou, de la hanche, de l'epaule et du centre de la barre;
- orientations absolues du pied, de la jambe, de la cuisse et du tronc;
- table anthropometrique effective repetee par condition : mode/règle, longueurs, masses et fractions massiques, fractions/offsets de CoM, rayons de giration et inerties;
- CoM de chaque segment et de la barre, avec les contributions `m*x` et `m*y` permettant de reconstruire le CoM global;
- angles, vitesses et accelerations articulaires;
- CoM position/vitesse/acceleration;
- poids, reaction au sol, residu du bilan des forces, point d'appui avec sa provenance, bases et marges d'equilibre;
- couples articulaires;
- capacité active disponible et ses facteurs angle/vitesse, angle de capacité, vitesse signée, régime, domaine, modèle et source;
- utilisation demande/capacité `U = |couple requis| / capacité disponible`, en ratio et en pourcentage;
- puissance;
- décomposition du couple de dynamique inverse en `M(q)qddot`, termes dépendant de `qdot`, gravité et résidu de reconstruction;
- effet signé du contact externe, séparé du total à pied fixé; les colonnes historiques `contact` et `inertial_nonlinear` restent exportées avec le statut `compatibilité legacy`.

Le JSON de resume contient les pics par articulation, le nombre de frames ou le point d'appui sort des bases geometrique/fonctionnelle et un bloc `mechanical_feasibility`: `U` maximal, articulation limitante, frame, temps, phase, dépassement de 1 et éventuelles capacités actives nulles. Il s'agit d'une **faisabilité mécanique dans les hypothèses du modèle**, pas d'un verdict absolu sur la réussite humaine.

Le bouton `Exporter Excel` du GUI regroupe la condition courante et toutes les conditions enregistrees. Le classeur contient les onglets `conditions`, `temps`, `coordonnees`, `orientations`, `cinematique_articulaire`, `anthropometrie`, `com_segmentaires`, `com_global`, `forces_equilibre`, `dynamique` et `definitions`. Les unites restent dans les en-tetes ou dans le dictionnaire; une cellule contient toujours une seule valeur numerique, sans unite concatenee.

La generation `.xlsx` est autonome : elle utilise `@oai/artifact-tool` lorsqu'un runtime Node.js compatible est disponible, puis bascule automatiquement sur le writer Python `openpyxl` inclus dans l'application. Aucun runtime Node n'est donc requis dans le bundle étudiant. La variable `SQUAT_GUI_XLSX_WRITER` permet de forcer `auto` (défaut), `artifact-tool` ou `openpyxl`. Pour forcer Artifact Tool hors de Codex, définir aussi `SQUAT_GUI_NODE` vers l'exécutable Node et `SQUAT_GUI_NODE_MODULES` vers le dossier `node_modules` qui contient `@oai/artifact-tool`.

Le bouton `Exporter MP4` produit une animation H.264 `900×720` à 20 fps depuis un renderer hors écran. Les couches actives dans le menu `Affichage` sont reprises dans la vidéo, y compris CoM, CoP/ZMP, GRF, poids, bases d'appui, bras de levier, anneaux de capacité et annotations scientifiques. Un fichier `<video>.mp4.json` conserve la cadence, les dimensions, la durée de la trajectoire, la durée encodée, le backend et l'état exact des couches. Installer les dépendances hors runtime complet avec `python -m pip install -e ".[video]"`.

### Exporter un lot de conditions

Creer un fichier `conditions.csv`, par exemple:

```csv
condition_id,subject_profile,bar_position,load_percent_bw,wedge_20_deg,shank_percent,thigh_percent,trunk_percent,duration_excentrique_s,duration_isometrique_s,duration_concentrique_s,frames,backend,torque_preset,ankle_deg,knee_deg,hip_deg
back_libre,homme,back,0,false,0,0,0,4,2,4,81,analytical,anderson,22,-80,78
front_charge,homme,front,80,false,0,0,0,3,2,3,101,auto,sportifs,24,-85,75
enceinte_wedge,femme enceinte,back,30,true,5,0,0,4,3,4,101,auto,anderson,20,-75,70
```

Puis lancer:

```bash
python -m squat_gui batch conditions.csv \
  --out exports/batch_results.csv \
  --summary exports/batch_summary.json \
  --xlsx exports/batch_results.xlsx
```

Le fichier `batch_results.csv` regroupe toutes les frames de toutes les conditions, avec une colonne `condition_id` pour filtrer les analyses.

## Tests

```bash
python -m unittest discover -s tests
```

## Backend biorbd et centre de pression

Le backend `biorbd` est deja utilise, quand il est disponible, pour:

- generer/mettre en cache un modele `.bioMod` selon la charge, les longueurs, le profil, la prise de barre et le wedge;
- calculer `InverseDynamics(...)`;
- calculer `CoM(...)`, `CoMdot(...)`, `CoMddot(...)`;
- calculer `CalcAngularMomentum(...)` pour le moment dynamique.

La décomposition canonique suit la convention du modèle à pied fixé:

```text
total = inverse_dynamics(q, qdot, qddot)
total = M(q) qddot + termes_dependant_de_qdot + gravite
```

Dans le GUI, `total ID` vient de `biorbd_model.InverseDynamics(q, qdot, qddot)` quand `biorbd` est disponible. C'est ce total qui est utilisé pour les courbes de couples articulaires, les puissances, les ratios d'effort et le tableau des conditions. Comme le pied est fixé à la base du `.bioMod`, cette définition est volontairement conservée pour ne pas annuler artificiellement les moments de maintien du squat.

Pour biorbd, `M(q)qddot` est calculé explicitement par `massMatrix(q) @ qddot`. La gravité est obtenue par `InverseDynamics(q, 0, 0)`. Les termes dépendant de la vitesse sont isolés par `InverseDynamics(q, qdot, 0) - gravité`. Pour le backend analytique, les mêmes termes sont isolés en annulant séparément `qdot`, `qddot` et la gravité dans les équations segmentaires, puis projetés dans la convention cheville-genou-hanche. Le résidu `total - somme des trois termes` est exporté et testé à une tolérance stricte.

Le moment de contact reste un diagnostic distinct. Sa colonne canonique `external_contact_effect_Nm` est signée comme une contribution additive; elle est l'opposé de l'ancienne colonne soustractive `contact_Nm`. Elle n'entre pas dans la reconstruction du total contraint à pied fixé. Le calcul biorbd par `ExternalForceSet` fournit aussi le total contrefactuel avec cette force externe, mais ce dernier n'est pas utilisé pour la puissance ni pour le ratio demande/capacité. La colonne `contact_source` indique explicitement `biorbd.ExternalForceSet` ou le fallback géométrique réellement employé. L'ancienne colonne `inertial_nonlinear_Nm = total - contact` est conservée uniquement pour lire les exports antérieurs et ne doit recevoir aucune interprétation physique.

Pour utiliser directement le ZMP depuis `biorbd`, il faut une version de `biorbd` qui expose `Model.CalcZeroMomentPoint(...)`. Une PR locale a ete preparee pour cela:

- branche: `/Users/mickaelbegon/Documents/GIT/biorbd`, `codex/calc-zero-moment-point`;
- PR: <https://github.com/pyomeca/biorbd/pull/383>.

Dernieres etapes:

1. compiler et installer cette branche de `biorbd` dans l'environnement Python utilise par le GUI, par exemple `vitpose-ekf`;
2. verifier que la fonction est exposee:

```bash
PYTHONPATH=src /Users/mickaelbegon/miniconda3/envs/vitpose-ekf/bin/python -c "from squat_gui.anthropometry import Anthropometry; from squat_gui.backend import write_biomod_file; import biorbd; p=write_biomod_file('/tmp/squat_check.bioMod', Anthropometry()); m=biorbd.Model(str(p)); print(hasattr(m, 'CalcZeroMomentPoint'))"
```

3. relancer le GUI avec ce meme Python.

Le GUI et l'export conservent la provenance exacte du point d'appui:

- backend analytique : `CoP`, obtenu par le bilan du moment de la resultante de contact;
- biorbd avec `CalcZeroMomentPoint` : `ZMP`, obtenu directement avec la normale du sol `(0, 1, 0)` et un point du sol `(0, 0, 0)`;
- biorbd sans cette fonction : `ZMP`, obtenu par le bilan dynamique de fallback.

Les champs `support_point_label` et `support_point_source` evitent donc d'utiliser CoP et ZMP comme des synonymes silencieux.

Le calcul du point et le critere d'acceptabilite sont distincts. La base geometrique est la projection talon-orteils. La zone fonctionnelle exclut les `15 %` posterieurs de cette projection : un point place au bord du talon reste dans la base geometrique mais est signale hors zone fonctionnelle. Avec le `wedge 20 deg`, la limite posterieure fonctionnelle est placee a la projection verticale de la cheville. Les deux intervalles, leurs marges anterieure/posterieure et l'appartenance du point sont affichables et exportes. Les anciens champs `zmp_*` et `cop_in_foot` restent presents pour compatibilite, avec `cop_in_foot` reserve desormais a la vraie base geometrique.

Le repere de forces utilise `+x` vers l'avant et `+y` vers le haut. Le poids est le vecteur `(0, -m*g)`, avec `g=9,80665 m/s2`. Le bilan verifie a chaque frame:

```text
GRF + poids = masse_totale * acceleration_COM
```

La ligne horizontale des courbes de GRF represente explicitement `m*g`; elle n'est plus estimee depuis la premiere valeur de GRF. La couche `Bilan forces et equilibre` affiche le residu numerique de l'identite, la provenance du CoP/ZMP, les deux bases et les marges signees.

## Relations couple-angle et couple-vitesse

Le checkbox `max-angle (Anderson)` applique la relation active couple-angle:

```text
facteur_angle = max(0, cos(C2 * (angle - C3)))
```

Cette courbe utilise les coefficients actifs moyens 18-25 ans homme de Anderson, Madigan et Nussbaum, "Maximum voluntary joint torque as a function of joint angle and angular velocity: model development and application to the lower limb", Journal of Biomechanics, 2007, doi: `10.1016/j.jbiomech.2007.03.022`, <https://pubmed.ncbi.nlm.nih.gov/17485097/>.

Les directions retenues sont celles utiles au squat: flexion plantaire cheville, extension genou et extension hanche. Anderson définit la flexion/dorsiflexion positive; seule la flexion de genou, historiquement négative dans Squat_GUI, est donc inversée avant l'évaluation. Le lobe actif vaut zéro hors de l'intervalle `C3 ± pi/(2*C2)`; aucun plancher physiologique arbitraire n'est appliqué.

Le checkbox `max-vitesse (Anderson)` applique les paramètres `C4`, `C5` et `C6` de la même publication. La vitesse est exprimée en `rad/s`, positive en concentrique et négative en excentrique. Le régime est raccordé à la puissance affichée: `couple × vitesse articulaire > 0` est générateur/concentrique, `< 0` est absorbant/excentrique et une vitesse nulle est isométrique. La surface vaut 75 % du maximum isométrique à `C4` et 50 % à `C5`; la branche excentrique est celle de l'équation publiée, et non un facteur fixe lié au nom de la phase. Les couples passifs d'Anderson ne sont pas ajoutés: la capacité affichée reste une capacité **active**.

La capacité utilisée est `max_saisi × facteur_angle × facteur_vitesse`. Le preset `Anderson actif x2` utilise `C1` pour initialiser l'amplitude; le preset `Sportifs` conserve son amplitude propre mais emprunte la forme angle-vitesse d'Anderson. Ce dernier cas est un hybride didactique explicitement traçable, pas une norme physiologique homogène.

Le GUI propose deux jeux de couples max. Comme le modele 2D regroupe les cotes gauche et droit, les valeurs issues de tests unilateraux sont sommees sur les deux membres:

- `Anderson actif x2`: coefficients Anderson 18-25 ans homme, multiplies par deux pour le modele combine. Pour 70 kg et 1.70 m: cheville 222 Nm, genou 380 Nm, hanche 376 Nm.
- `Sportifs`: proposition heterogene mais documentee a partir de donnees sportives. Pour 70 kg: cheville 229 Nm, genou 497 Nm, hanche 330 Nm.

La proposition `Sportifs` est volontairement un preset de travail, pas une norme unique. La cheville vient des plantarflexions de joueurs de soccer de So et al. 1994, `100.0 + 104.9 Nm` pour dominant + non-dominant, recalees de 62.6 kg a 70 kg, doi: `10.1136/bjsm.28.1.25`, <https://pmc.ncbi.nlm.nih.gov/articles/PMC1332153/>. Le genou vient des quadriceps de joueurs de soccer elite de Keytsman et al. 2024, environ `3.55 + 3.55 Nm/kg` sur dominant + non-dominant a 90 deg, doi: `10.1186/s13102-024-00961-y`, <https://link.springer.com/article/10.1186/s13102-024-00961-y>. La hanche vient de mesures d'extension de hanche chez des footballeuses, environ `2.36 + 2.35 Nm/kg` a 30 deg de flexion apres entrainement, doi: `10.1371/journal.pone.0342529`, <https://pmc.ncbi.nlm.nih.gov/articles/PMC12931786/>; cette valeur est moins directement comparable a un groupe masculin mais donne un ordre de grandeur sportif publie.

## Modifier les images de segments

Les sprites PNG utilises par l'animation sont dans `assets/raster_segments/`. Les images `refined` sont maintenant actives par defaut; le checkbox `low quality` utilise aussi une image propre a chaque sujet et prise de barre.
Ils sont ancres par les cibles dessinees dans les images:

- `pied.png`: cible de cheville et pointe du pied detectee sur la silhouette;
- `jambe.png`: cibles cheville et genou;
- `cuisse.png`: cibles genou et hanche;
- `tronc.png`: cibles hanche et epaule pour le rendu simple;
- `trunk_homme_{front,back,over-head}.png` et `trunk_femme_enceinte_{front,back,over-head}.png`: torses refined adaptes a la prise.

### Calibrer le CoM de la barre dans les images

Une petite interface permet de pointer manuellement le centre de la barre sur les six images `low quality` et les six images `refined`:

```bash
conda activate squat-gui
pip install -e .
squat-bar-com-editor
```

Selectionner chaque image, cliquer au centre de la barre dessinee, puis utiliser `Sauver JSON`. Par defaut, le fichier propose est `assets/raster_segments/bar_com_points.json`. Il conserve le point en pixels, sa position normalisee, ainsi que son deplacement anterieur/longitudinal par rapport a l'epaule exprime en longueurs de tronc.

Le fichier est maintenant utilise par la cinematique et par la generation des modeles `.bioMod`. Les six annotations `refined` constituent la reference physique de la barre pour chaque combinaison sujet/prise : changer uniquement le mode d'image `low quality` ne change donc pas les couples, le CoM ou le CoP. Les six annotations basse qualite sont conservees pour controler la correspondance visuelle des images de secours.

Pour remplacer une image, garder un fond blanc ou transparent, garder le segment en vue de profil, et dessiner les cibles comme un rond noir/blanc avec un point noir central. Le renderer detecte automatiquement ces points. Si Pillow n'est pas disponible, l'application revient automatiquement aux formes vectorielles JSON.
