# Laboratoire — Squat 2D, dynamique inverse et interprétation pratique

## Contexte

Ce laboratoire utilise le logiciel `Squat_GUI` et son interface CLI `python -m squat_gui` pour relier des consignes pratiques de squat à des variables biomécaniques : cinématique, dynamique inverse, CoM, CoP/ZMP, forces de réaction au sol, couples, puissances et ratios d’effort. Il introduit également la notion d’équilibre postural : une même pose basse peut ne plus être acceptable lorsque la morphologie ou la position de la barre change.

Le laboratoire est construit pour être associé à des questions dans Studium/Moodle. Les questions numériques doivent être calculées à partir des sorties produites localement avec le GUI ou la ligne de commande.

## Objectifs pédagogiques

À la fin du laboratoire, l’étudiant devrait pouvoir :

1. expliquer comment la posture modifie la distribution des moments entre hanche, genou et cheville;
2. interpréter le CoM, le CoP/ZMP et la zone d’appui fonctionnelle dans une tâche de squat;
3. distinguer couple brut et ratio d’effort normalisé par capacité articulaire;
4. analyser l’effet de la morphologie et de la position de barre sur l’équilibre, puis proposer une compensation posturale;
5. analyser l’effet de la charge, de la vitesse et des longueurs segmentaires;
6. décomposer un moment articulaire en `M(q)q̈`, termes dépendant de `q̇` et gravité, puis distinguer l'effet externe du contact;
7. relier les résultats simulés à des résultats expérimentaux publiés;
8. formuler une recommandation pratique nuancée plutôt qu’une règle universelle.

## Préparation

Avant la séance, lire les résumés de littérature dans `docs/references_litterature.md` et répondre aux QCM de préparation.

Commande de base depuis la racine du projet :

```bash
python -m squat_gui run --backend biorbd --out exports/condition_demo.csv --summary exports/condition_demo_summary.json
```

Si les scripts de ce dossier sont utilisés :

```bash
cd Labo
python scripts/run_squat_batch.py --conditions scenarios/scenarios_labo_squat.csv --out results_labo_squat
python scripts/analyse_squat_results.py --results results_labo_squat/results.csv --out results_labo_squat/summary_metrics.csv
```

## Tutoriel de prise en main du GUI

Lancer l'interface depuis la racine du projet :

```bash
python -m squat_gui
```

Le tutoriel intégré suit une progression volontairement graduelle. Les résultats et les alertes restent masqués pendant l'étape **Observation**, afin de formuler une hypothèse avant de consulter les métriques.

### 1. Préparer la condition

1. Renseigner le sujet, la position de la barre, la charge et la posture basse.
2. Pour une variation de longueur, choisir `longueur seule` afin d'isoler la géométrie, ou `morphotype recalibre` pour appliquer la sensibilité didactique documentée aux masses et inerties.
3. Choisir un profil temporel : `Référence 4/2/4`, `Lent 6/2/6`, `Rapide 2/0,5/2`, `Sans pause 4/0/4`, `Descente lente / montée rapide 6/1/2` ou `Descente rapide / montée lente 2/1/6`.
4. Vérifier les durées de descente, de pause et de remontée. Le pas temporel est fixé à `Δt = 0,05 s`; une modification manuelle des durées active le profil `Personnalisé`.
5. Lancer la simulation, puis démarrer l'animation.

### 2. Observer avant de mesurer

Pendant **Observation**, décrire qualitativement la stratégie : déplacement du tronc et du bassin, progression des genoux, position apparente du centre de masse et phase qui semble la plus exigeante. Noter une prédiction sur l'articulation limitante et sur le risque de sortie de la zone d'appui.

### 3. Examiner la cinématique

Passer à **Cinématique**, puis utiliser le menu `Affichage` pour choisir les couches visibles : articulations, centre de masse global ou segmentaire, angles segmentaires et coordonnées articulaires. Survoler une articulation dans l'animation pour afficher ses coordonnées dans une infobulle.

Dans la vue synchronisée :

- choisir une articulation ou le CoM comme source;
- comparer position, vitesse et accélération sur les trois graphiques alignés;
- cliquer ou faire glisser le curseur vertical pour déplacer simultanément l'animation et les trois graphiques;
- ouvrir l'inspecteur numérique pour lire les valeurs exactes de la frame courante;
- masquer indépendamment les noms de phases ou leurs limites si elles gênent la lecture.
- choisir le repère `absolu`, `centré` ou `normalisé`; en mode normalisé, tenir compte de l'avertissement indiquant que les différences de durée sont masquées.

### 4. Examiner la dynamique

Passer à **Dynamique** et comparer les forces de réaction au sol, le CoP/ZMP, les couples articulaires, les puissances et l'utilisation demande/capacité `U`. Les contrôles `max-angle (Anderson)` et `max-vitesse (Anderson)` modulent séparément la capacité active. Le régime est cohérent avec la puissance affichée : puissance positive en concentrique/génération, négative en excentrique/absorption et vitesse nulle en isométrique. Dans `couples détaillés`, utiliser `Affichage` pour masquer ou afficher séparément `M(q)q̈`, les termes dépendant de `q̇`, la gravité, le contact externe signé et le `total ID`.

Interpréter `U = |couple requis| / capacité active disponible` comme une **faisabilité mécanique dans les hypothèses du modèle**. `U > 1` signale une demande supérieure à cette capacité modélisée, mais ne constitue pas un verdict absolu sur la réussite d'une personne. Le tableau des conditions donne `U max`, l'articulation limitante, le temps, la phase et le dépassement éventuel.

Dans ce modèle à pied fixé, vérifier la reconstruction `total ID = M(q)q̈ + termes q̇ + gravité`. Le contact est présenté séparément : il ne doit pas être ajouté une seconde fois au total contraint. Revenir ensuite à l'hypothèse formulée en Observation et préciser ce qui est confirmé, infirmé ou reste ambigu.

### 5. Comparer en contrôlant les variables

Enregistrer d'abord une condition de référence. La sélectionner, cliquer sur `Dupliquer`, modifier un seul paramètre scientifique, puis cliquer sur `Ajouter`. Sélectionner ensuite les deux conditions et ouvrir l'onglet `Variables contrôlées` : il doit nommer le paramètre modifié et présenter les valeurs de référence et comparée avec leurs unités. Les différences de simple affichage ne sont pas comptées.

Le menu `Affichage` centralise les courbes, composantes, axes, limites et couches de l'animation. Changer une couche modifie uniquement le rendu et ne relance pas la simulation.

Lors d'une comparaison morphologique, vérifier dans la couche `Anthropométrie utilisée` que le mode est identique entre conditions, sauf si le mode lui-même constitue la variable étudiée. Les trois prises de barre modifient la géométrie et la dynamique, mais la barre est modélisée comme un point massique sans longueur ni inertie propre.

### 6. Conserver une trace reproductible

Enregistrer la condition lorsqu'elle doit être réutilisée. Pour une analyse complète, exporter le classeur Excel : chaque famille de métriques est placée dans un onglet dédié et la table anthropométrique effectivement utilisée est incluse. L'export vidéo MP4 permet de conserver l'animation et les couches d'affichage sélectionnées.

Avant de poursuivre, vérifier que vous savez : sélectionner un preset temporel, afficher une coordonnée par survol, déplacer le curseur synchronisé, lire l'inspecteur numérique, distinguer les trois repères temporels, dupliquer une référence, vérifier les variables contrôlées et produire un export.

## Déroulement proposé

### Bloc 1 — Référence et lecture des sorties

Lancer une simulation baseline en suivant le tutoriel intégré. Formuler d'abord une hypothèse en mode Observation, puis identifier les angles articulaires, les vitesses, les accélérations, les moments, les puissances, le CoM, le CoP/ZMP et les ratios d'effort.

Questions d’analyse :

- Le pic de couple au genou survient-il au point bas ou pendant la remontée?
- Le ZMP reste-t-il dans la zone d’appui fonctionnelle?
- Quelle articulation a le ratio d’effort le plus élevé?

### Bloc 2 — Posture : hanche vs genou

Comparer `posture_knee_dominant` et `posture_hip_dominant`.

Hypothèse : une posture plus verticale avec genoux avancés augmente la demande relative au genou; une posture avec tronc plus incliné augmente la demande à la hanche.

Variables à extraire : pics de couples, ratios d’effort, ratio hanche/genou, CoP min/max.

Lien littérature attendu : Fry et al. (2003), Straub & Powers (2024).

### Bloc 3 — Équilibre postural : morphologie et prise de barre

Le principe de ce bloc est de tenir la pose basse constante au début de la comparaison. La charge est exprimée en pourcentage du poids de corps et vaut 40 % BW dans les essais fournis.

Comparer d’abord :

- `balance_bar_back`, `balance_bar_front` et `balance_bar_overhead`;
- `balance_long_thigh_back` et `balance_long_thigh_front`;
- `balance_pregnant_back` et `balance_pregnant_front`.

Questions d’analyse :

- À pose identique, comment la prise de barre déplace-t-elle le CoM au point bas et le CoP/ZMP pendant le mouvement?
- Une cuisse plus longue ou le profil `femme enceinte` rend-il la même stratégie posturale plus difficile à équilibrer?
- Dans quels cas le ZMP sort-il de la zone d’appui, et pendant combien de frames?
- La prise qui améliore l’équilibre réduit-elle nécessairement le ratio d’effort de toutes les articulations?

Étape de conception : ouvrir les conditions les plus critiques dans le GUI, ajuster les angles de la position de squat jusqu’à conserver le ZMP dans la zone d’appui, puis enregistrer la condition adaptée. La zone retenue exclut les 15 % postérieurs de la projection du pied : le bord du talon constitue une alerte, même si le point est encore sous la silhouette du pied. Avec le wedge, la limite postérieure est la projection verticale de la cheville pour écarter les appuis excessivement postérieurs sur le talon surélevé. Rapporter les changements d’angles nécessaires et leurs conséquences sur les couples.

Variables à extraire : `squat_com_x_m`, `squat_support_point_x_m`, `zmp_outside_support_frames`, excursion du point d’appui, pics de couples et ratios d’effort.

Lien littérature attendu : Chan & Sigward (2020), Kim et al. (2021), Schoenfeld (2010).

### Bloc 4 — Limites d’appui

Comparer `stability_forward` et `stability_backward`.

Hypothèse : une posture peut être biomécaniquement exigeante sans être acceptable si le ZMP sort de la zone d’appui fonctionnelle.

Variables à extraire : ZMP, CoM, couleur d’alerte du GUI, moments normalisés.

Lien littérature attendu : Chan & Sigward (2020), Kitamura et al. (2019).

### Bloc 5 — Charge externe

Comparer `baseline`, `load_30bw`, `load_60bw` et `load_100bw`. La charge de barre est exprimée en pourcentage du poids de corps du sujet de référence de 70 kg.

Hypothèse : la charge augmente les couples et les forces de réaction au sol, mais l’articulation limitante peut dépendre des capacités maximales.

Variables à extraire : pics de couples, GRF verticale, ratios d’effort, première articulation dépassant 1.0.

Lien littérature attendu : Pürzel et al. (2025), Schoenfeld (2010).

### Bloc 6 — Durée du mouvement

Comparer `duration_slow` et `duration_fast` avec posture, charge et prise de barre constantes. Dans le GUI, reproduire cette comparaison avec les presets `Lent 6/2/6` et `Rapide 2/0,5/2`, puis utiliser le curseur synchronisé pour comparer les mêmes événements du mouvement.

Hypothèse : réduire la durée augmente les accélérations et peut modifier les parts `M(q)q̈` et dépendante de `q̇` dans le couple total.

Variables à extraire : couple total de dynamique inverse, `M(q)q̈`, termes dépendant de `q̇`, gravité, effet externe signé du contact, résidu de reconstruction et puissance.

Lien littérature attendu : Hannan & King (2022).

### Bloc 7 — Mini-projet

Chaque équipe choisit un objectif :

- minimiser la demande relative au genou;
- maximiser la sollicitation du genou sans dépasser les capacités;
- garder le CoP au centre du pied;
- adapter la posture pour préserver l’équilibre après un changement de morphologie ou de prise de barre;
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
| Simulations reproductibles et bien comparées | 20 |
| Analyse des moments, CoP/ZMP et ratios d’effort | 20 |
| Équilibre morphologie / prise de barre et adaptation proposée | 15 |
| Analyse dynamique total, `M(q)q̈`, `q̇`, gravité, contact et durée | 10 |
| Utilisation pertinente de la littérature | 20 |
| Recommandation pratique nuancée | 10 |
| Clarté des figures et tableaux | 5 |
