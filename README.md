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
