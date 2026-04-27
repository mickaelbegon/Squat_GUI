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

## Prochaine etape biomecanique

Installer l'environnement biomecanique puis remplacer le solveur analytique par un appel `biorbd.InverseDynamics(...)` dans `src/squat_gui/backend.py`. Le modele `.bioMod` est genere par `write_biomod_file(...)` a partir des parametres anthropometriques courants.

## Modifier les images de segments

Les sprites PNG utilises par l'animation sont dans `assets/raster_segments/`.
Ils sont ancres par deux points par image dans `src/squat_gui/raster_segments.py`:

- `pied.png`: articulation de cheville et pointe du pied;
- `jambe.png`: cheville et genou;
- `cuisse.png`: genou et hanche;
- `tronc.png`: hanche et epaule.

Pour remplacer une image, garder un fond blanc ou transparent, garder le segment en vue de profil, puis ajuster les coordonnees `distal_anchor` et `proximal_anchor` si les cercles articulaires changent de position. Si Pillow n'est pas disponible, l'application revient automatiquement aux formes vectorielles JSON.
