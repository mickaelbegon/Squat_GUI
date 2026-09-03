# Guide de développement

## Environnement local

Prérequis : Git et Python 3.9 ou plus avec Tk. Un environnement dédié est
recommandé.

```bash
conda create -n squat-gui python=3.11 tk -y
conda activate squat-gui
conda install -c conda-forge "openpyxl>=3.1" "scipy>=1.10,<1.17" "libblas=*=*openblas" -y
python -m pip install -e ".[dev,video,packaging]"
python -m squat_gui
```

`openpyxl` est requis pour l'export Excel (`.xlsx`). Il est déclaré dans les
dépendances Python du projet et installé explicitement ici afin que l'export soit
disponible dès la création d'un environnement Conda.

`scipy` fournit le solveur SLSQP de l'option expérimentale de stabilisation de
la barre. La borne `<1.17` et le backend OpenBLAS évitent une défaillance native
constatée avec SciPy 1.17.1 et la variante MKL de Conda sous Windows. Si SciPy
manque dans une ancienne installation, cette option conserve la trajectoire
demandée et affiche un diagnostic explicite.

Le solveur analytique pur Python est toujours disponible. `biorbd` est une
dépendance facultative et ne doit pas bloquer le lancement du GUI.

## Organisation du dépôt

- `src/squat_gui/` : application, cinématique, dynamique, exports et backends ;
- `assets/` : silhouettes raster et formes vectorielles ;
- `tests/` : tests unitaires et tests Tkinter ;
- `packaging/` : spécification PyInstaller, scripts et recette de distribution ;
- `.github/workflows/` : intégration continue et publication des releases.

## Architecture en couches

Le projet sépare volontairement l'interface, les données de session, le calcul
et les sorties. Une couche ne doit pas contourner les contrats de la couche
voisine : cela permet notamment d'obtenir les mêmes résultats depuis le GUI,
la CLI et les tests.

```text
Tkinter (app.py) ─┐
                  ├─ modèles de condition/session ─ simulation_service ─ cinématique/dynamique
CLI (cli.py) ─────┘                  │                         │                    │
                                     │                         └─ backend analytique / biorbd optionnel
                                     ├─ rendu Tk / export vidéo
                                     └─ CSV / Excel / JSON
```

| Couche | Modules principaux | Responsabilité et règle de dépendance |
|---|---|---|
| Interface | `app.py`, `didactics.py`, `timeline.py`, `plot_data.py` | Widgets Tkinter, interactions, parcours pédagogique et orchestration visuelle. Elle transforme les réglages en `Condition`, mais ne porte pas les règles de simulation ou de persistance. |
| Modèles et session | `simulation_service.py`, `session_persistence.py`, `condition_store.py`, `comparison.py` | `Condition` est l'entrée immuable d'un calcul ; `GuiSettings` et `SavedCondition` forment le contrat JSON de session. Ces modules restent indépendants de Tkinter. |
| Simulation | `anthropometry.py`, `kinematics.py`, `dynamics.py`, `observables.py`, `bar_path_optimization.py` | Construction du sujet, trajectoires, dynamique inverse, observables et optimisation expérimentale de trajectoire de barre. Le service `simulate_condition` est le point de passage partagé par le GUI et la CLI. |
| Rendu | `rendering.py`, `scene_model.py`, `raster_segments.py`, `segment_shapes.py`, `resources.py`, `video_export.py` | Géométrie de scène, couches visuelles, sprites et rendu hors écran. Le rendu consomme des états/résultats ; il ne modifie ni la condition ni le calcul. |
| Exports | `export_io.py`, `export_schema.py`, `workbook_model.py`, `xlsx_writers.py` | Contrats de colonnes et de feuilles, écriture CSV atomique et writers Excel. Les formats étudiants restent séparés des données diagnostiques complètes. |
| Backends optionnels | `backend.py`, `yeadon.py` | Détection, cache et intégration `biorbd`/`biobuddy`. Le backend analytique reste disponible quand ces dépendances natives sont absentes. |

Lorsqu'une fonctionnalité traverse plusieurs couches, commencer par le modèle
ou contrat partagé, ajouter un test sans GUI, puis relier l'interface et les
exports. Éviter de faire passer une structure Tkinter, un widget ou un chemin
de fichier directement dans les modules de simulation.

### Points d'entrée

| Commande | Usage |
|---|---|
| `python -m squat_gui` | Lance le GUI sans argument ; délègue à la CLI si des arguments suivent. |
| `squat-gui` | Lance explicitement l'interface Tkinter. |
| `squat-gui-cli` | Lance explicitement la CLI (`run`, `batch`, etc.). |
| `squat-bar-com-editor` | Ouvre l'éditeur de calibration du centre de barre. |

Les scripts sont déclarés dans `pyproject.toml`. Toute nouvelle entrée doit
être documentée ici et pouvoir s'exécuter dans l'environnement minimal indiqué
plus haut.

## Vérifications

Avant un commit ou une pull request, exécuter depuis la racine du dépôt :

```bash
python -m ruff check src tests packaging
python -m compileall -q src tests packaging/squat_gui_launcher.py
git diff --check
python -m pytest -q
```

Certains tests `biorbd` sont ignorés lorsque ses extensions natives ne sont pas
installées. Les tests Tkinter qui vérifient la géométrie peuvent aussi être
ignorés sans session graphique ; les exécuter sur un poste disposant de Tk pour
valider une modification de layout. Les autres tests doivent rester
indépendants de ces backends et de l'affichage.

`ruff` est inclus seulement dans l'extra de développement (`.[dev]`) : il n'est
pas requis pour lancer l'application ni pour les distributions étudiantes. La
première règle CI couvre exclusivement les erreurs certaines d'import, de
syntaxe et de structure. Le formatage automatique et les règles de style ne
sont pas encore bloquants, afin d'éviter d'imposer une remise en forme massive
du code existant. Pour normaliser ponctuellement un nouveau fichier ou un
fichier modifié, utiliser :

```bash
python -m ruff format chemin/du_fichier.py
python -m ruff check chemin/du_fichier.py
```

## Ligne de commande et exports

Une condition unique peut être générée sans ouvrir le GUI :

```bash
python -m squat_gui run \
  --condition-id front_50bw \
  --subject-profile homme \
  --bar-position front \
  --load-percent-bw 50 \
  --duration-excentrique 2 \
  --duration-isometrique 1 \
  --duration-concentrique 2 \
  --joint-angles-deg 22 -80 78 \
  --backend analytical \
  --out exports/front_50bw.csv \
  --xlsx exports/front_50bw.xlsx
```

Pour un lot, utiliser :

```bash
python -m squat_gui batch conditions.csv \
  --out exports/batch_results.csv \
  --xlsx exports/batch_results.xlsx
```

`--backend auto` essaie `biorbd` puis revient à l'analytique. `--backend biorbd`
échoue explicitement si le backend demandé est indisponible. `--frames 0` utilise
le pas temporel par défaut de 0,05 s.

Le CSV utilise par défaut le contrat `standard` : une ligne par frame avec les
paramètres de condition, la cinématique articulaire, les moments et puissances,
le CoM, le CoP/ZMP et la GRF verticale. `--csv-mode full` conserve l'ancien
niveau diagnostique avec les coordonnées segmentaires et les termes
intermédiaires. L'export Excel place en premier l'onglet `Synthèse`, qui fournit
une ligne par condition avec les pics, moments normalisés, position au squat,
excursion du CoP/ZMP, sorties de la base d'appui et faisabilité mécanique. Les
frames complètes sont ensuite disponibles dans `Données combinées` et dans une
feuille distincte par simulation; `Définitions` conserve le dictionnaire des
colonnes. Le JSON reste
disponible avec `--summary chemin.json`, mais n'est plus requis pour l'analyse
étudiante.

## Builds locaux

Les builds étudiants n'incluent pas `biorbd` par défaut. Ils contiennent le
solveur analytique, les assets, Excel et l'export vidéo.

Windows :

```powershell
conda activate squat-gui
powershell -ExecutionPolicy Bypass -File packaging\build_windows.ps1
```

La sortie est `dist\Squat GUI\Squat GUI.exe`. Distribuer le dossier complet,
jamais l'exécutable seul.

macOS :

```bash
conda activate squat-gui
bash packaging/build_macos.sh
```

La sortie principale est `dist/Squat GUI.app`. Le bundle doit être signé et
notarisé avec les identifiants Apple du diffuseur pour éviter l'avertissement
Gatekeeper en production.

Pour tenter d'embarquer le backend optionnel dans un build local :

```bash
SQUAT_GUI_INCLUDE_OPTIONAL_BACKENDS=1 bash packaging/build_macos.sh
```

Sous PowerShell, définir la même variable d'environnement à `1` avant le script.
Ne publier ce build que si `import biorbd` et les fonctions réellement utilisées
par Squat GUI passent dans l'environnement de construction.

## Releases GitHub

Le workflow `release.yml` se déclenche sur un tag `v*` et :

1. vérifie que la version du tag correspond à `pyproject.toml` ;
2. construit et teste les applications sur Windows et macOS ;
3. crée un ZIP par système ;
4. calcule `SHA256SUMS.txt` ;
5. crée la release GitHub ou y téléverse les artefacts.

Procédure de publication :

```bash
git tag v0.2.0
git push origin v0.2.0
```

Avant de taguer, mettre à jour ensemble `pyproject.toml`, `CHANGELOG.md`, les
métadonnées PyInstaller et les versions attendues par les validateurs. Tester les
ZIP obtenus sur une seconde machine avec
[`packaging/RECETTE_DISTRIBUTION.md`](../packaging/RECETTE_DISTRIBUTION.md).

## Backend biorbd

Quand il est disponible, `biorbd` sert à générer et mettre en cache un `.bioMod`,
calculer la dynamique inverse, le CoM et ses dérivées, ainsi que le moment
cinétique. Le GUI conserve un fallback analytique pour toute fonction absente.

Le support natif du ZMP dépend de `Model.CalcZeroMomentPoint`. Le travail amont
historique est suivi dans [pyomeca/biorbd#383](https://github.com/pyomeca/biorbd/pull/383).
Pour vérifier une installation :

```bash
python -c "import biorbd; print(hasattr(biorbd.Model, 'CalcZeroMomentPoint'))"
```

Ne pas présenter le CoP analytique et le ZMP `biorbd` comme des synonymes : les
champs `support_point_label` et `support_point_source` tracent la méthode utilisée.

## Sprites et calibration

Les PNG sont dans `assets/raster_segments/`; les variantes détaillées se trouvent
dans le sous-dossier `refined/`. Le renderer détecte les cibles articulaires dans
les images et revient aux formes JSON si Pillow est absent.

L'éditeur de centre de barre se lance avec :

```bash
squat-bar-com-editor
```

Sauvegarder dans `assets/raster_segments/bar_com_points.json`. Les annotations
détaillées constituent la référence physique pour chaque combinaison sujet/prise.
Changer uniquement la qualité d'image ne doit donc jamais modifier la cinématique
ou la dynamique.

## Contributions

Chaque correction fonctionnelle doit être accompagnée d'un test ciblé. Garder les
commits séparés par issue, ne pas inclure de fichiers de build locaux et documenter
toute nouvelle hypothèse scientifique dans `DOCS/BIOMECHANICS.md`.
