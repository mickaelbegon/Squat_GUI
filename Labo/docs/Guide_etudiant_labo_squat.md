# Laboratoire — Squat 2D, dynamique inverse et interprétation pratique

## Contexte

Ce laboratoire utilise le logiciel `Squat_GUI` et son interface CLI `squat-gui-cli run` pour relier des consignes pratiques de squat à des variables biomécaniques : cinématique, dynamique inverse, CoM, CoP/ZMP, forces de réaction au sol, couples, puissances et ratios d’effort.

Le laboratoire est construit pour être associé à des questions dans Studium/Moodle. Les questions numériques doivent être calculées à partir des sorties produites localement avec le GUI ou la ligne de commande.

## Objectifs pédagogiques

À la fin du laboratoire, l’étudiant devrait pouvoir :

1. expliquer comment la posture modifie la distribution des moments entre hanche, genou et cheville;
2. interpréter le CoM, le CoP/ZMP et le polygone d’appui dans une tâche de squat;
3. distinguer couple brut et ratio d’effort normalisé par capacité articulaire;
4. analyser l’effet de la charge, de la vitesse et des longueurs segmentaires;
5. décomposer un moment articulaire en contributions inertielle, effets non linéaires et contact;
6. relier les résultats simulés à des résultats expérimentaux publiés;
7. formuler une recommandation pratique nuancée plutôt qu’une règle universelle.

## Préparation

Avant la séance, lire les résumés de littérature dans `docs/references_litterature.md` et répondre aux QCM de préparation.

Commande de base depuis la racine du projet :

```bash
python -m squat_gui run --backend analytical --out exports/condition_demo.csv --summary exports/condition_demo_summary.json
```

Si les scripts de ce dossier sont utilisés :

```bash
cd Labo
python scripts/run_squat_batch.py --conditions scenarios/scenarios_labo_squat.csv --out results_labo_squat
python scripts/analyse_squat_results.py --results results_labo_squat/results.csv --out results_labo_squat/summary_metrics.csv
```

## Déroulement proposé

### Bloc 1 — Référence et lecture des sorties

Lancer une simulation baseline. Identifier les angles articulaires, les vitesses, les accélérations, les moments, les puissances, le CoM, le CoP/ZMP et les ratios d’effort.

Questions d’analyse :

- Le pic de couple au genou survient-il au point bas ou pendant la remontée?
- Le CoP reste-t-il dans le pied?
- Quelle articulation a le ratio d’effort le plus élevé?

### Bloc 2 — Posture : hanche vs genou

Comparer `posture_knee_dominant` et `posture_hip_dominant`.

Hypothèse : une posture plus verticale avec genoux avancés augmente la demande relative au genou; une posture avec tronc plus incliné augmente la demande à la hanche.

Variables à extraire : pics de couples, ratios d’effort, ratio hanche/genou, CoP min/max.

Lien littérature attendu : Fry et al. (2003), Straub & Powers (2024).

### Bloc 3 — Stabilité

Comparer `stability_forward` et `stability_backward`.

Hypothèse : une posture peut être biomécaniquement exigeante sans être acceptable si le CoP sort du pied.

Variables à extraire : CoP, CoM, couleur d’alerte du GUI, moments normalisés.

Lien littérature attendu : Chan & Sigward (2020), Kitamura et al. (2019).

### Bloc 4 — Charge externe

Comparer baseline, 25 kg, 50 kg et 75 kg.

Hypothèse : la charge augmente les couples et les forces de réaction au sol, mais l’articulation limitante peut dépendre des capacités maximales.

Variables à extraire : pics de couples, GRF verticale, ratios d’effort, première articulation dépassant 1.0.

Lien littérature attendu : Pürzel et al. (2025), Schoenfeld (2010).

### Bloc 5 — Vitesse

Comparer un squat lent et un squat rapide avec posture et charge constantes.

Hypothèse : la vitesse augmente la contribution inertielle `Mqddot`, ce qui peut modifier l’interprétation du mouvement.

Variables à extraire : `Mqddot`, `contact`, `NLeffects`, couple total, puissance.

Lien littérature attendu : Hannan & King (2022).

### Bloc 6 — Mini-projet

Chaque équipe choisit un objectif :

- minimiser la demande relative au genou;
- maximiser la sollicitation du genou sans dépasser les capacités;
- garder le CoP au centre du pied;
- augmenter la charge sans dépasser 80 % de capacité;
- augmenter la vitesse tout en limitant la part inertielle.

Le rapport doit inclure une hypothèse, un plan de simulations, une figure principale, un tableau de métriques, une interprétation pratique et au moins deux liens explicites avec la littérature.

## Livrables

1. fichier de résultats ou résumé `summary_metrics.csv`;
2. figures comparatives;
3. réponses au questionnaire ou aux questions remises par l’enseignant;
4. court rapport de 2 à 4 pages;
5. conclusion pratique : que peut-on recommander, et à quelles conditions?

## Critères d’évaluation

| Critère | Points |
|---|---:|
| Simulations reproductibles et bien comparées | 25 |
| Analyse des moments, CoP/ZMP et ratios d’effort | 25 |
| Analyse dynamique `Mqddot`, contact et vitesse | 15 |
| Utilisation pertinente de la littérature | 20 |
| Recommandation pratique nuancée | 10 |
| Clarté des figures et tableaux | 5 |
