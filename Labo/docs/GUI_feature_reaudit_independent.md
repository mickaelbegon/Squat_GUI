# Réaudit indépendant des fonctionnalités F01–F41

Date : 2026-08-11
Référence examinée : worktree de `main` au-dessus de `f046c34`
Source des exigences : `Objectif général.md`

## Méthode

Ce réaudit a été reconstruit depuis les exigences, le code courant, les tests et les supports de laboratoire. Les verdicts du fichier `GUI_feature_audit.md` n'ont pas été utilisés comme preuve. Une fonctionnalité n'est déclarée `PRESENT` que si son calcul, sa présentation/export et une preuve vérifiable sont cohérents.

Contrôles frais réalisés avant toute correction issue de ce réaudit :

- inspection des modules scientifiques, du GUI, du CLI, des exports, du packaging et de `Labo/`;
- exécution avec `/Users/mickaelbegon/miniconda3/envs/squat-gui/bin/python` : biorbd 1.12.2 et NumPy 2.4.6 importent correctement;
- `python -m unittest discover -s tests -v` : 113 tests exécutés, 112 réussis, dont les 3 tests biorbd natifs; 1 erreur d'environnement sur l'export MP4, car `imageio` est absent;
- contrôle indépendant des scénarios : les 17 conditions de 9 s utilisent 101 frames (`Δt=0,09 s`) et la condition rapide de 4 s utilise 101 frames (`Δt=0,04 s`), au lieu de `Δt=0,05 s`;
- contrôle du cache biorbd : deux conditions CLI distinctes peuvent partager la même clé à cause de l'arrondi de la charge et des longueurs.

Statuts autorisés : `PRESENT`, `PARTIEL`, `ABSENT`, `PRESENT_MAIS_INADAPTE`.

## Matrice indépendante

| ID | Feature | Compétence | Statut | Preuve dans le code | Limite actuelle | Action proposée | Priorité |
|---|---|---|---|---|---|---|---|
| F01 | Temps et frames | C3–C5 | PARTIEL | `observables.frame_info`; ligne d'état et curseur dans `SquatGui`; `test_frame_info_*` | Le GUI respecte 0,05 s, mais les 18 scénarios publics imposent un nombre de frames incompatible. | Recalculer les frames des scénarios et tester le contrat `Δt=0,05 s`. | P0 bloquant release |
| F02 | Coordonnées articulaires | C1 | PRESENT | `observables.joint_coordinates`; infobulles `register_animation_hover_targets`; colonnes `*_x_m`, `*_y_m`; `test_joint_coordinates_*` | Aucune limite bloquante identifiée. | Conserver la source de vérité dans `observables`. | P0 |
| F03 | Orientations segmentaires | C1 | PRESENT | `kinematics.segment_orientations`; labels GUI; table `orientations`; `test_absolute_orientations_*` | Le pied est fixe mais reste exporté, ce qui est cohérent. | Conserver la convention +x/antihoraire. | P0 |
| F04 | Angles articulaires | C1 | PRESENT | `joint_angles_from_orientations`, conversions segment/articulation; GUI et export; tests de round-trip et wedge | Deux conventions coexistent volontairement : flexion du genou négative dans Squat_GUI, positive pour Anderson. | Maintenir la conversion explicite et ses tests. | P0 |
| F05 | Longueurs segmentaires | C2, C10 | PRESENT | `segment_anthropometry`; couche anthropométrie; table Excel dédiée | Aucune limite bloquante identifiée. | Conserver l'affichage du mode associé. | P0 |
| F06 | CoM segmentaires | C2 | PRESENT | `Pose.segment_coms`, `com_contributions`, infobulles et export par segment/barre | La barre est ponctuelle; fraction, longueur et inertie analytique sont nulles. | Conserver cette limite visible. | P0 |
| F07 | CoM multicorps | C2 | PRESENT | `pose_from_angles`, `reconstruct_global_com`; contributions `m*x`, `m*y`; tests de reconstruction | Aucune divergence numérique détectée. | Conserver l'identité testée à tolérance stricte. | P0 |
| F08 | Position, vitesse, accélération | C3–C6 | PRESENT | dérivées analytiques dans `kinematics`; séries articulaires/CoM; tests par différences centrées | Aucune limite bloquante identifiée. | Conserver les tests analytiques et discrets. | P0 |
| F09 | Dérivation manuelle | C5 | PRESENT | `neighbor_samples`; couche i−1/i/i+1; export ligne par frame; tests aux bornes | Les échantillons absents aux extrémités sont volontairement indisponibles. | Conserver ce comportement. | P0 |
| F10 | GRF et poids | C3, C9 | PRESENT | `ground_reaction_and_cop`, `force_balance`; courbes et référence BW; tests d'équilibre des forces | Le backend analytique donne un CoP, biorbd un ZMP natif ou reconstruit; la provenance est exportée. | Conserver le libellé de provenance. | P0 |
| F11 | Équilibre | C7, C12 | PRESENT | base géométrique sur toute la longueur du pied; zone fonctionnelle cheville–tête des métatarsiens dans `kinematics`; marges dans `observables`; GUI/export/tests wedge | La tête des métatarsiens est modélisée à 85 % du segment talon–orteils faute de joint dédié; c'est une convention pédagogique, pas une loi clinique. | Conserver cette qualification didactique et le repère explicite. | P0 |
| F12 | Export canonique | C4, C8 | PARTIEL | schéma 1.3.0, dictionnaire et 11 tables dans `export_schema`; tests CSV/XLSX | Le CSV est exploitable, mais plusieurs définitions sont générées depuis le nom plutôt que rédigées précisément; l'Excel dépend d'un runtime Node/@oai non distribuable et absent du bundle PyInstaller. | Ajouter un writer Python autonome de secours, rédiger les définitions canoniques et tester un environnement sans runtime Codex. | P0 bloquant release |
| F13 | Tests scientifiques | C1–C12 | PRESENT | identités CoM, forces, dérivées, conventions, décomposition et backend biorbd couvertes | L'environnement `squat-gui` n'inclut pas `pytest`; `unittest` exécute néanmoins toute la suite. | Installer/figer les dépendances de test et conserver l'exécution biorbd réelle. | P0 |
| F14 | Export vidéo | C3, C4 | PRESENT_MAIS_INADAPTE | `video_export.export_mp4`; rendu offscreen; métadonnées; test dédié | Une trajectoire endpoint-inclusive de N frames est encodée avec N images : la vidéo dure `T+Δt`. `imageio` est absent de l'environnement canonique et du build étudiant. | Encoder les N−1 intervalles, ajouter les dépendances et tester la durée du conteneur. | P1 bloquant release |
| F15 | Couches vidéo | C2, C3, C7 | PARTIEL | `RenderLayers`, sélections GUI et rendu offscreen partagé | La sélection est correcte, mais l'export effectif échoue dans l'environnement canonique sans extra vidéo; le packaging ne collecte pas ces dépendances. | Intégrer/tester les dépendances vidéo dans le build. | P1 bloquant release |
| F16 | Durées indépendantes | C6, C10 | PARTIEL | `PhaseDurations`, quintiques séparées, GUI, courbes et exports; tests ciblés | Les scénarios publics cassent le pas de 0,05 s et la vidéo ajoute un intervalle à la durée. | Corriger scénarios et vidéo, puis tester GUI/CLI/MP4 de bout en bout. | P1 bloquant release |
| F17 | Presets temporels | C6 | PRESENT | six presets dans `didactics.TEMPORAL_PRESETS`; triplets affichés directement dans le sélecteur et sous les menus de durée; contrôles numériques conservés; échelle commune descente/montée 0,5/1/2/4 s et isométrique 0/0,5/1/2 s; scénarios `duration_slow/fast` alignés | Les valeurs restent des choix pédagogiques explicites, non des normes biomécaniques; la littérature ne définit pas une cadence universelle. | Aucun correctif restant sur l'affichage ou l'échelle des durées. | P1 |
| F18 | Mode OBSERVATION | C3, pédagogie | PRESENT | `RevealMode.OBSERVATION`, `layers_for_reveal`, masquage des valeurs/courbes/alertes; tests | Aucune réponse mécanique directe n'est révélée. | Conserver le garde. | P1 |
| F19 | Mode CINÉMATIQUE | C1–C6 | PRESENT | mode et choix des séries synchronisées; tests de révélation | Le CoM/projection sont visibles, conformément au parcours retenu. | Conserver. | P1 |
| F20 | Mode DYNAMIQUE | C7, C9–C11 | PRESENT | forces, support, couples, puissances et capacité révélés; tests | Aucune limite bloquante identifiée. | Conserver. | P1 |
| F21 | P/V/A synchronisées | C3–C6 | PRESENT | `draw_synchronized_kinematics`; trois panneaux et unités; tests | Pas d'interpolation entre conditions; lecture au voisin le plus proche. | Documenter l'échantillonnage exact. | P1 |
| F22 | Curseur synchronisé | C4 | PRESENT | `current_plot_time`, `sample_dataset_at_time`, événements de tracé et animation | En comparaison, les valeurs sont prises au sample le plus proche, ce qui est visible dans l'inspecteur. | Conserver le temps réel de l'échantillon affiché. | P1 |
| F23 | Lecture numérique | C4 | PRESENT | onglet `Valeurs au curseur`, six décimales, phase et temps; tests exacts | Aucune limite bloquante identifiée. | Conserver. | P1 |
| F24 | Limites de phases | C4 | PRESENT | `phase_windows`, marqueurs GUI; tests | Aucune limite bloquante identifiée. | Conserver. | P1 |
| F25 | Masquage des phases | C4 | PRESENT | contrôles séparés noms/limites; inspecteur cohérent | Le masquage est visuel seulement, comme demandé. | Conserver. | P1 |
| F26 | Affichage sélectif | C4 | PRESENT | menu central, variables de couches/composantes; test d'absence de resimulation | `app.py` porte encore beaucoup d'orchestration et de rendu. | Extraire progressivement des contrôleurs sans changer le comportement. | P1 dette architecture |
| F27 | Temps absolu/normalisé | C4, C6 | PRESENT | `timeline.TimeMode`, avertissement normalisé, axes/tests | Un mode centré supplémentaire est présent et documenté. | Conserver l'avertissement. | P1 |
| F28 | Comparaison de conditions | C8 | PRESENT | sauvegarde, sélection, animation/courbes synchronisées et légendes | Comparaison par sample le plus proche, sans interpolation. | Conserver les temps échantillonnés dans l'inspecteur. | P1 |
| F29 | Variables contrôlées | C8 | PRESENT | `comparison.parameter_differences`, duplication GUI, onglet dédié; tests | Les réglages visuels sont correctement exclus. | Conserver la liste sémantique centralisée. | P1 |
| F30 | Terme M(q)q̈ | C9 | PRESENT | analytique par évaluation contrôlée; biorbd par `massMatrix(q) @ qddot`; tests de reconstruction | Aucune confusion avec `total-contact` dans le code canonique. | Supprimer l'usage pédagogique des colonnes legacy dans les scripts de labo. | P2 |
| F31 | Termes dépendant de q̇ | C9 | PRESENT | évaluation à q̈=0 moins gravité; tests de mise à zéro | Une valeur legacy `inertial_nonlinear` subsiste pour compatibilité. | Ne plus l'utiliser dans les nouveaux résumés. | P2 |
| F32 | Gravité | C9 | PRESENT | évaluation à q̇=q̈=0; export/GUI/tests | Aucune limite bloquante identifiée. | Conserver. | P2 |
| F33 | Contact externe | C9, C12 | PRESENT | diagnostic signé séparé, provenance biorbd/fallback et total contrefactuel | Le contact n'appartient pas à la reconstruction du total contraint; certains supports Studium emploient encore une formulation antérieure ambiguë. | Corriger les supports et conserver la provenance. | P2 contenu pédagogique |
| F34 | Couple résultant | C9 | PRESENT | total de dynamique inverse à pied fixé, puissance et U fondés sur ce total | Le modèle ne prédit pas les forces musculaires individuelles. | Conserver la limite. | P2 |
| F35 | Reconstruction/labels | C9 | PRESENT | résidu strict, cinq courbes masquables, noms alignés; tests analytique/biorbd | Le script `analyse_squat_results.py` recalcule encore `total-contact` comme composante legacy. | Migrer le script vers les colonnes 1.3.0. | P2 correction release |
| F36 | Couple-angle | C11, C12 | PRESENT | équation active Anderson, paramètres 18–25 ans hommes, conventions et domaine testés | Seule la composante active extension/PF est modélisée; pas de couple passif. | Conserver cette qualification. | P2 |
| F37 | Couple-vitesse | C11, C12 | PARTIEL | équation Anderson et régime dérivé de la puissance; points C4/C5 testés | Le preset de base `Sportifs` est combiné aux facteurs Anderson, mais l'objet `TorqueCapacity` exporte toujours Anderson comme source unique; la provenance réelle est donc incomplète. | Propager le preset et sa source dans chaque capacité/export, ou interdire le mélange non documenté. | P2 correction scientifique |
| F38 | U(t) demande/capacité | C11 | PRESENT | `effort_ratios`, export U/%, gestion capacité nulle | U compare la valeur absolue au groupe extenseur/PF choisi; interprétation limitée au squat et au modèle actif. | Rendre cette direction musculaire explicite dans le GUI/export. | P2 |
| F39 | Maximum/limitation | C11, C12 | PRESENT | résumé GUI/JSON avec articulation, frame, temps, phase, dépassement | Les événements à capacité nulle sont marqués non définis plutôt que chiffrés artificiellement. | Conserver. | P2 |
| F40 | Anthropométrie | C10, C12 | PRESENT | modes `longueur seule` et `morphotype recalibre`; masses/inerties/table effective; tests | Le morphotype recalibré est une hypothèse de densité linéique constante, pas une régression populationnelle. | Conserver la qualification. | P2 |
| F41 | Position de barre | C10 | PARTIEL | positions front/back/over-head dans géométrie, CoM, dynamique, export, comparaison et tests | La barre reste ponctuelle; biorbd lui donne une petite inertie numérique locale absente de l'analytique. Surtout, la clé de cache arrondie peut confondre deux conditions CLI distinctes. | Rendre la clé sans collision pour toutes les entrées autorisées et tester la cohérence backend. | P2 correction release |

## Verdict indépendant initial

Le périmètre F01–F41 est fonctionnellement très avancé, mais il n'est pas encore prêt pour une release étudiante reproductible.

- `PRESENT` : 34 fonctionnalités;
- `PARTIEL` : F01, F12, F15, F16, F37 et F41;
- `PRESENT_MAIS_INADAPTE` : F14;
- `ABSENT` : aucune.

Les bloqueurs de release sont : pas temporel des scénarios, durée/dépendances vidéo, export Excel dépendant d'un runtime Codex, provenance du preset de capacité, collisions du cache biorbd et supports de laboratoire encore fondés sur des colonnes/noms legacy.

## Risques transversaux hors matrice

1. `src/squat_gui/app.py` dépasse 5 000 lignes et concentre interface, rendu, comparaison, export et orchestration. Cette dette ne bloque pas à elle seule la release, mais augmente fortement le risque de régression.
2. `pyproject.toml` ne déclare aucune dépendance de base; l'environnement `squat-gui` ne contient ni `pytest` ni `imageio`.
3. Le bundle PyInstaller ne collecte ni le constructeur Excel `.mjs`, ni Node/@oai, ni explicitement les dépendances vidéo; les boutons Excel/MP4 ne sont donc pas garantis dans l'application distribuée.
4. Des artifacts enseignant non suivis (`corrigé`, données résolues, banques Studium et YAML avec réponses attendues) se trouvent dans le dépôt public local et ne doivent pas être ajoutés accidentellement.
5. Le fichier YAML non suivi décrit une ancienne CLI et des scénarios différents du CSV canonique; il ne doit pas être publié comme source active.

## Contre-audit après corrections

Les corrections ont ensuite été évaluées sans réutiliser les validations manuelles F01–F41 comme preuve. Les contrôles de release du 2026-08-11 donnent :

- 124 tests et 75 sous-tests réussis avec Python 3.11.15, NumPy 2.4.6 et biorbd 1.12.2;
- 18 scénarios publics exécutés avec biorbd, 3 158 lignes, `Δt=0,05 s` partout et aucune valeur non finie;
- erreur maximale de bilan des forces `2,92e-13 N` et résidu maximal de reconstruction des couples `3,27e-13 Nm`;
- MP4 réel : 20 frames à 20 fps pour une trajectoire de 1,00 s, durée du conteneur 1,00 s;
- smoke test GUI natif réussi : quatre modes de révélation, curseur, JSON, condition sauvegardée et export Excel;
- classeur 1.4.0 à 11 onglets, sans erreur de formule, rendu et inspecté onglet par onglet;
- bundle macOS arm64 0.2.0 de 220 Mo construit avec biorbd, ffmpeg et les assets; le smoke test figé encode/relit un MP4 et exécute réellement biorbd;
- guide étudiant DOCX régénéré et inspecté visuellement sur ses sept pages.

La clôture complémentaire du 2026-08-12 ajoute un writer `openpyxl` autonome : les
11 onglets ont été comparés au classeur Artifact Tool, rendus et inspectés; un test sans
Node.js et le smoke test du bundle macOS arm64 de 222 Mo ont tous deux créé puis relu le
classeur sans erreur.

| ID corrigé | Statut après correction | Preuve de clôture |
|---|---|---|
| F01 | PRESENT | scénarios 161 frames/8 s et 31 frames/1,5 s; test systématique du pas de 0,05 s |
| F12 | PRESENT | schéma 1.4.0 et 11 onglets conservés; sélection `auto` Artifact Tool/`openpyxl`; fallback Python testé sans Node.js puis dans l'application figée |
| F13 | PRESENT | `pytest` figé dans l'extra dev; suite complète avec biorbd réel |
| F14 | PRESENT | N−1 intervalles encodés; durée du conteneur vérifiée; dépendances incluses dans le bundle |
| F15 | PRESENT | couches partagées par le renderer; ffmpeg/imageio présents et export figé réellement exécuté |
| F16 | PRESENT | pas public, trajectoire et vidéo cohérents de bout en bout |
| F30–F35 | PRESENT | script de laboratoire migré vers les champs canoniques et séparation géométrique/fonctionnelle |
| F37 | PRESENT | amplitude de base, preset et source propagés dans `TorqueCapacity`, CSV et Excel |
| F41 | PRESENT | clé à précision d'entrée et suffixe SHA-256; test de non-collision |

Verdict post-correction : **41 fonctionnalités PRESENT, aucune PARTIEL, ABSENT ni PRESENT_MAIS_INADAPTE**.

Le CSV, l'Excel autonome, le calcul, le MP4, le laboratoire et le bundle biorbd sont validés. Le support Windows, la signature/notarisation macOS et la dette d'architecture restent des risques de livraison, pas des échecs F01–F41.
