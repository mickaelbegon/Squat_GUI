# Squat GUI

Premiere interface graphique 2D pour explorer un squat avec:

- modele pied, jambe, cuisse, tronc/reste du corps et barre sur les epaules;
- homme initial de 70 kg pour 1.70 m, inerties gauche/droite combinees en 2D;
- sliders pour la charge, les longueurs tibia/cuisse/tronc et la duree;
- cinematique d'ordre 5 type Yeadon, issue du profil `6x^5 - 15x^4 + 10x^3`;
- dynamique inverse analytique 2D de demarrage;
- calcul de la reaction au sol, du centre de pression, du CoM et de sa projection;
- animation avec CoM, projection au sol, force de contact et bras de levier pointilles;
- contraintes de couples max avec feedback vert/rouge;
- relation couple max-angle optionnelle.

Le code contient aussi un backend optionnel pour brancher `biobuddy` et `biorbd`. Si ces paquets ne sont pas installes, l'application reste executable avec le solveur analytique pur Python.

## Lancer

```bash
PYTHONPATH=src python3 -m squat_gui
```

Avec l'environnement biomecanique local qui contient `biobuddy` et `biorbd`:

```bash
PYTHONPATH=src /Users/mickaelbegon/miniconda3/envs/vitpose-ekf/bin/python -m squat_gui
```

## Tests

```bash
PYTHONPATH=src python3 -m unittest discover -s tests
```

## Backend biorbd et centre de pression

Le backend `biorbd` est deja utilise, quand il est disponible, pour:

- generer/mettre en cache un modele `.bioMod` selon la charge et les longueurs;
- calculer `InverseDynamics(...)`;
- calculer `NonLinearEffect(...)`;
- calculer `CoM(...)`, `CoMdot(...)`, `CoMddot(...)`;
- calculer `CalcAngularMomentum(...)` pour le moment dynamique.

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

## Modifier les images de segments

Les sprites PNG utilises par l'animation sont dans `assets/raster_segments/`.
Ils sont ancres par les cibles dessinees dans les images:

- `pied.png`: cible de cheville et pointe du pied detectee sur la silhouette;
- `jambe.png`: cibles cheville et genou;
- `cuisse.png`: cibles genou et hanche;
- `tronc.png`: cibles hanche et epaule.

Pour remplacer une image, garder un fond blanc ou transparent, garder le segment en vue de profil, et dessiner les cibles comme un rond noir/blanc avec un point noir central. Le renderer detecte automatiquement ces points. Si Pillow n'est pas disponible, l'application revient automatiquement aux formes vectorielles JSON.
