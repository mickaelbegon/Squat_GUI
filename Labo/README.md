# Laboratoire Squat_GUI

Ce dossier contient les fichiers publics du laboratoire de biomecanique du squat. Le protocole inclut une comparaison clinique cheville–talonnette et un volet d'equilibre postural : les etudiants analysent comment une restriction de dorsiflexion, les proportions segmentaires, le profil du sujet et la prise de barre deplacent le CoM et le CoP/ZMP. Les corriges, banques de questions avec reponses et jeux de valeurs numeriques resolues ne doivent pas etre distribues aux etudiants.

## Contenu versionne

- `Guide_etudiant_labo_squat.docx` : guide étudiant prêt à distribuer, incluant le tutoriel GUI F17-F41.
- `docs/Guide_etudiant_labo_squat.md` : source Markdown du guide etudiant et de son tutoriel.
- `docs/references_litterature.md` : references de depart.
- `scenarios/scenarios_labo_squat.csv` : les 11 conditions publiques sans resultats attendus, incluant la serie clinique `baseline` / `limited_ankle_flexion` / `wedge_20_deg` et les paires d'equilibre `balance_*`.
- `scripts/run_squat_batch.py` : lance les scenarios avec `python -m squat_gui batch`.
- `scripts/analyse_squat_results.py` : extrait les metriques de synthese depuis les CSV exportes, dont CoM/CoP au squat et les trois composantes de couples affichees par le GUI.
- `docs/PILOTE_PEDAGOGIQUE.md` : protocole de pilote avec tâches, mesures et critères d'acceptation avant déploiement en laboratoire.

Les deux scripts de laboratoire utilisent uniquement la bibliotheque standard Python; aucun paquet d'analyse supplementaire n'est requis.

## Utilisation rapide

Depuis la racine du projet:

```bash
cd Labo
python scripts/run_squat_batch.py --conditions scenarios/scenarios_labo_squat.csv --out results_labo_squat
python scripts/analyse_squat_results.py --results results_labo_squat/results.csv --out results_labo_squat/summary_metrics.csv
```

Les scenarios publics demandent le backend `biorbd`, afin que les couples de dynamique inverse et le CoP/ZMP soient ceux du modele utilise dans le GUI.

Les angles du CSV suivent directement la convention positive affichée par le GUI : `ankle_deg`, `knee_flexion_deg` et `hip_flexion_deg`. Le parseur conserve la lecture des anciens fichiers qui utilisaient les orientations segmentaires ou la flexion du genou signée.

Le scenario `duration_fast` suit le preset GUI rapide `0,5/0,5/0,5 s` (31 frames). Les phases de descente et de montée utilisent uniquement `0,5`, `1`, `2` ou `4 s`; la pause isométrique ne propose plus `1,5 s`.

Pour lancer seulement la comparaison clinique de cheville :

```bash
python scripts/run_squat_batch.py --conditions scenarios/scenarios_labo_squat.csv --out results_cheville --only baseline limited_ankle_flexion wedge_20_deg
python scripts/analyse_squat_results.py --results results_cheville/results.csv --out results_cheville/summary_metrics.csv
```

Le fichier `results_labo_squat/results.csv` contient toutes les frames, y compris le mode et la table anthropométriques effectifs, la capacité active angle-vitesse et l'utilisation `U`. Le résumé JSON canonique identifie `U max`, l'articulation limitante, le temps, la phase et le dépassement éventuel. Ces sorties décrivent une faisabilité mécanique dans les hypothèses du modèle. Le fichier `summary_metrics.csv` conserve les indicateurs historiques du script de laboratoire.

## Principe des comparaisons

1. Comparer `baseline` (25/90/120°), `limited_ankle_flexion` (10/90/120°) et `wedge_20_deg` (10/90/120° avec talonnette). Avec le backend analytique de référence, le point d'appui reste dans la zone fonctionnelle pour `baseline` et `wedge_20_deg`, tandis que la restriction seule produit des sorties de zone pendant une partie du mouvement.
2. Comparer une modification morphologique (`balance_long_thigh_back/front`) ou du profil du sujet (`balance_pregnant_back/front`) à prise identique.
3. Comparer enfin `load_100bw` et `duration_fast` aux conditions de référence pertinentes.
4. Observer `squat_com_x_m`, `squat_support_point_x_m` et `zmp_outside_support_frames`, puis interpréter les résultats dans les hypothèses du backend utilisé.

Le CSV public donne uniquement les conditions de depart; il ne contient ni la posture corrigee ni les reponses numeriques.

Dans le GUI, la base géométrique du ZMP couvre toute la longueur projetée du pied, du talon aux orteils. La zone fonctionnelle va de la projection de la cheville à la tête des métatarsiens; le modèle place cette tête à 85 % du segment talon–orteils, les orteils distaux restant hors de la zone fonctionnelle. Cette convention explicite évite de confondre la longueur anatomique du pied avec la zone d'appui fonctionnelle.
