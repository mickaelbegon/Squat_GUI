# Laboratoire Squat_GUI

Ce dossier contient les fichiers publics du laboratoire de biomecanique du squat. Les corriges, banques de questions avec reponses et jeux de valeurs numeriques resolues ne doivent pas etre distribues aux etudiants.

## Contenu versionne

- `Guide_etudiant_labo_squat.docx` : guide etudiant pret a distribuer.
- `docs/Guide_etudiant_labo_squat.md` : version Markdown du guide etudiant.
- `docs/references_litterature.md` : references de depart.
- `scenarios/scenarios_labo_squat.csv` : conditions de simulation sans resultats attendus.
- `scripts/run_squat_batch.py` : lance les scenarios avec `python -m squat_gui batch`.
- `scripts/analyse_squat_results.py` : extrait les metriques de synthese depuis les CSV exportes.

## Utilisation rapide

Depuis la racine du projet:

```bash
cd Labo
python scripts/run_squat_batch.py --conditions scenarios/scenarios_labo_squat.csv --out results_labo_squat
python scripts/analyse_squat_results.py --results results_labo_squat/results.csv --out results_labo_squat/summary_metrics.csv
```

Pour lancer seulement quelques scenarios:

```bash
python scripts/run_squat_batch.py --conditions scenarios/scenarios_labo_squat.csv --out results_labo_squat --only baseline load_50kg
```

Le fichier `results_labo_squat/results.csv` contient toutes les frames. Le fichier `summary_metrics.csv` contient une ligne par scenario avec les pics de couple, ratios d'effort, CoP, CoM, GRF et contributions dynamiques.
