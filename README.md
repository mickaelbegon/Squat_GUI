# Squat GUI

Interface graphique 2D pour explorer un squat avec:

- modele pied, jambe, cuisse, tronc/tete/bras et barre, en prise `front`, `back` ou `over-head`;
- sujet homme ou femme enceinte de reference, 70 kg pour 1.70 m, inerties gauche/droite combinees en 2D;
- charge exprimee en `%BW` (pour le sujet de 70 kg), longueurs discretes et wedge de 20 deg;
- mouvement en trois phases reglables: excentrique, isometrique et concentrique;
- cinematique d'ordre 5 type Yeadon, issue du profil `6x^5 - 15x^4 + 10x^3`;
- dynamique inverse analytique 2D de demarrage;
- calcul de la reaction au sol, du centre de pression, du CoM et de sa projection;
- animation avec CoM, projection au sol, force de contact et bras de levier pointilles;
- contraintes de couples max avec feedback vert/rouge;
- relation couple max-angle optionnelle;
- images `refined` par sujet et prise de barre, avec retour `low quality`.

Le code contient aussi un backend optionnel pour brancher `biobuddy` et `biorbd`. Si ces paquets ne sont pas installes, l'application reste executable avec le solveur analytique pur Python.

## Utilisation pedagogique

Le checkbox `activer` dans `Parcours didactique` affiche une consigne a la fois:

1. choisir `homme` ou `femme enceinte`;
2. choisir la prise de barre;
3. augmenter progressivement la charge, initialement a `0 %BW`;
4. regler les trois durees de phase;
5. definir la position basse en glissant genou, hanche et epaules;
6. observer l'animation, le CoM, le CoP et les alertes;
7. parcourir cinematique, centre de masse puis couples;
8. cliquer sur `Ajouter`;
9. construire une deuxieme condition;
10. selectionner plusieurs conditions dans le tableau pour les comparer.

Les longueurs segmentaires, les couples max et les couples detailles sont des outils avances. `Sauver conditions` et `Charger conditions` ecrivent/lisent un fichier JSON comprenant les widgets et, si demande, les conditions ajoutees au tableau.

Limites de pose imposees par l'interface:

- cheville: -30 deg en flexion plantaire a +40 deg en flexion dorsale;
- genou: -140 a 0 deg;
- hanche: -15 a +120 deg.

## Hypotheses des nouvelles conditions

La barre est un segment ponctuel ajoute au modele `.bioMod`; sa masse est `70 * Charge %BW / 100`. Sa position locale par rapport aux epaules est modifiee selon la prise: en avant pour `front`, en arriere pour `back`, et au-dessus des bras pour `over-head`. Le CoM du segment regroupe `tronc-tete-bras` est aussi deplace pour representer le changement de posture des bras.

La version `femme enceinte` est actuellement un scenario didactique initial, pas un modele clinique valide: elle conserve une masse corporelle totale de 70 kg pour permettre des comparaisons controlees, deplace le CoM du segment tronc de `+0.060 m` vers l'avant et multiplie son moment d'inertie par `1.18`. Ces deux coefficients sont centralises dans [anthropometry.py](src/squat_gui/anthropometry.py) et devront etre remplaces ou calibres a partir d'un jeu anthropometrique de grossesse choisi pour le cours.

Le wedge ajoute une orientation initiale de 20 deg a la cheville dans le `.bioMod` genere et dans la geometrie 2D. Le contact reste represente sur le plan du sol horizontal; il s'agit donc d'une exploration du changement de configuration, et non d'un modele de contact complet du wedge.

## Installation de A a Z

Cette section est volontairement tres detaillee. L'objectif est qu'une personne qui n'a jamais installe Python puisse lancer le GUI.

Il y a deux niveaux possibles:

- installation simple: le GUI se lance, avec le solveur analytique Python et les images de segments;
- installation complete biorbd: le GUI utilise `biorbd` pour la dynamique inverse, le CoM, et le ZMP si la version installee expose `CalcZeroMomentPoint`.

### 0. Vocabulaire minimal

- `Terminal` sur macOS et `Anaconda Prompt` sur Windows sont les fenetres ou on tape les commandes.
- `conda` sert a creer un environnement Python propre, separe du reste de l'ordinateur.
- `squat-gui` sera le nom de l'environnement conda.
- Quand une commande commence par `conda activate squat-gui`, il faut voir quelque chose comme `(squat-gui)` au debut de la ligne suivante.
- Ne pas taper les signes `$` ou `>` si vous les voyez dans un tutoriel; ici les blocs de code contiennent seulement les commandes a copier.

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

### 3. Creer l'environnement conda

Dans `Anaconda Prompt` sur Windows, ou dans `Terminal` sur macOS:

```bash
conda create -n squat-gui python=3.11 -y
conda activate squat-gui
```

Verifier que le debut de la ligne contient `(squat-gui)`.

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
  --frames 101 \
  --out exports/front_80bw.csv \
  --summary exports/front_80bw_summary.json
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
- `--duration-excentrique`, `--duration-isometrique`, `--duration-concentrique`: durees entre 2 et 4 s;
- `--joint-angles-deg ANKLE KNEE HIP`: angles articulaires finaux en degres;
- `--q-segment-deg SHANK THIGH TRUNK`: angles segmentaires finaux en degres, convention interne du modele;
- `--torque-preset anderson` ou `--torque-preset sportifs`;
- `--max-cheville`, `--max-genou`, `--max-hanche`: surcharge manuelle des couples max;
- `--angle-adapt true/false`: active/desactive la relation couple-angle;
- `--frames`: nombre de frames exportees.

Le CSV exporte contient une ligne par frame avec:

- temps, phase, backend;
- parametres de condition;
- angles, vitesses et accelerations articulaires;
- CoM position/vitesse/acceleration;
- CoP, reaction au sol et moment dynamique;
- couples articulaires;
- couple max disponible;
- effort normalise en pourcentage;
- puissance;
- composantes `total`, `contact` et `inertiels_non_lineaires`, avec la convention `inertiels_non_lineaires = total - contact`.

Le JSON de resume contient les pics par articulation, le nombre de frames ou le CoP sort du pied et le nombre de frames ou un couple depasse 100%.

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
  --summary exports/batch_summary.json
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
- calculer `NonLinearEffect(...)`;
- calculer `CoM(...)`, `CoMdot(...)`, `CoMddot(...)`;
- calculer `CalcAngularMomentum(...)` pour le moment dynamique.

La decomposition simplifiee des couples suit la convention dynamique:

```text
total = inverse_dynamics(q, qdot, qddot)
inertiels_non_lineaires = total - contact
```

Dans le GUI, `total` vient de `biorbd_model.InverseDynamics(q, qdot, qddot)` quand `biorbd` est disponible. C'est ce `total` qui est utilise pour les courbes de couples articulaires, les puissances, les ratios d'effort et le tableau des conditions. Le terme `contact` represente l'effet de la reaction au sol estimee au CoP. La courbe `inertiels_non_lineaires` est simplement `total - contact`, ce qui evite d'afficher separement `Mqddot` et `NLeffects`. Pour l'instant, le terme de contact reste calcule dans le code du GUI, car le `.bioMod` actuel garde le pied fixe au sol; une integration encore plus propre consisterait a passer un `ExternalForceSet` a `InverseDynamics(..., externalForces)` dans un modele avec base/contacts compatibles.

Pour utiliser directement le centre de pression/ZMP depuis `biorbd`, il faut une version de `biorbd` qui expose `Model.CalcZeroMomentPoint(...)`. Une PR locale a ete preparee pour cela:

- branche: `/Users/mickaelbegon/Documents/GIT/biorbd`, `codex/calc-zero-moment-point`;
- PR: <https://github.com/pyomeca/biorbd/pull/383>.

Dernieres etapes:

1. compiler et installer cette branche de `biorbd` dans l'environnement Python utilise par le GUI, par exemple `vitpose-ekf`;
2. verifier que la fonction est exposee:

```bash
PYTHONPATH=src /Users/mickaelbegon/miniconda3/envs/vitpose-ekf/bin/python -c "from squat_gui.anthropometry import Anthropometry; from squat_gui.backend import write_biomod_file; import biorbd; p=write_biomod_file('/tmp/squat_check.bioMod', Anthropometry()); m=biorbd.Model(str(p)); print(hasattr(m, 'CalcZeroMomentPoint'))"
```

3. relancer le GUI avec ce meme Python.

Le GUI detecte automatiquement `CalcZeroMomentPoint`. Si la fonction existe, le centre de pression est obtenu par `biorbd` avec la normale du sol `(0, 1, 0)` et un point du sol `(0, 0, 0)`. Si la fonction n'existe pas encore dans l'environnement installe, le GUI garde le calcul de fallback base sur le moment dynamique et la reaction verticale.

## Relation couple-angle max

Le checkbox `max-angle` applique une modulation normalisee du couple maximal disponible selon l'angle articulaire:

```text
max_angle = max_saisi * max(0.05, cos(C2 * (angle - C3)))
```

Cette courbe utilise les coefficients actifs moyens 18-25 ans homme de Anderson, Madigan et Nussbaum, "Maximum voluntary joint torque as a function of joint angle and angular velocity: model development and application to the lower limb", Journal of Biomechanics, 2007, doi: `10.1016/j.jbiomech.2007.03.022`, <https://pubmed.ncbi.nlm.nih.gov/17485097/>.

Les directions retenues sont celles utiles au squat: flexion plantaire cheville, extension genou et extension hanche. Les valeurs `C1` de l'article sont normalisees par poids du corps fois taille; elles servent a initialiser les couples max pour un homme de 70 kg et 1.70 m. Les valeurs `C2` et `C3` modulent ensuite le pic saisi par l'utilisateur selon l'angle. La vitesse angulaire et les couples passifs du modele complet d'Anderson ne sont pas encore utilises dans le GUI; le facteur excentrique reste celui demande dans l'interface.

Le GUI propose deux jeux de couples max. Comme le modele 2D regroupe les cotes gauche et droit, les valeurs issues de tests unilateraux sont sommees sur les deux membres:

- `Anderson actif x2`: coefficients Anderson 18-25 ans homme, multiplies par deux pour le modele combine. Pour 70 kg et 1.70 m: cheville 222 Nm, genou 380 Nm, hanche 376 Nm.
- `Sportifs`: proposition heterogene mais documentee a partir de donnees sportives. Pour 70 kg: cheville 229 Nm, genou 497 Nm, hanche 330 Nm.

La proposition `Sportifs` est volontairement un preset de travail, pas une norme unique. La cheville vient des plantarflexions de joueurs de soccer de So et al. 1994, `100.0 + 104.9 Nm` pour dominant + non-dominant, recalees de 62.6 kg a 70 kg, doi: `10.1136/bjsm.28.1.25`, <https://pmc.ncbi.nlm.nih.gov/articles/PMC1332153/>. Le genou vient des quadriceps de joueurs de soccer elite de Keytsman et al. 2024, environ `3.55 + 3.55 Nm/kg` sur dominant + non-dominant a 90 deg, doi: `10.1186/s13102-024-00961-y`, <https://link.springer.com/article/10.1186/s13102-024-00961-y>. La hanche vient de mesures d'extension de hanche chez des footballeuses, environ `2.36 + 2.35 Nm/kg` a 30 deg de flexion apres entrainement, doi: `10.1371/journal.pone.0342529`, <https://pmc.ncbi.nlm.nih.gov/articles/PMC12931786/>; cette valeur est moins directement comparable a un groupe masculin mais donne un ordre de grandeur sportif publie.

## Modifier les images de segments

Les sprites PNG utilises par l'animation sont dans `assets/raster_segments/`. Les images `refined` sont maintenant actives par defaut; le checkbox `low quality` revient aux premiers sprites.
Ils sont ancres par les cibles dessinees dans les images:

- `pied.png`: cible de cheville et pointe du pied detectee sur la silhouette;
- `jambe.png`: cibles cheville et genou;
- `cuisse.png`: cibles genou et hanche;
- `tronc.png`: cibles hanche et epaule pour le rendu simple;
- `trunk_homme_{front,back,over-head}.png` et `trunk_femme_enceinte_{front,back,over-head}.png`: torses refined adaptes a la prise.

Pour remplacer une image, garder un fond blanc ou transparent, garder le segment en vue de profil, et dessiner les cibles comme un rond noir/blanc avec un point noir central. Le renderer detecte automatiquement ces points. Si Pillow n'est pas disponible, l'application revient automatiquement aux formes vectorielles JSON.
