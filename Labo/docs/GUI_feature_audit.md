# Audit fonctionnel et scientifique de Squat_GUI

Date de l'audit : 2026-08-10

Dépôt audité : `/Users/mickaelbegon/Documents/Squat_GUI`

Révision de base : `f046c34` (`main`, identique à `origin/main`)

Périmètre : audit LOT A, puis première tranche validable du LOT B (`F01` à `F04`). Les changements du LOT B ne sont pas commités.

## 1. Conclusion générale

Le dépôt contient déjà un noyau cohérent : cinématique plane, anthropométrie, dynamique inverse analytique, backend biorbd optionnel, animation Tkinter, courbes, comparaison de conditions, CLI et export CSV/JSON. Il ne faut donc pas recréer ces fonctions.

En revanche, la majorité des grandeurs scientifiques calculées ne sont pas encore inspectables pédagogiquement dans le GUI, et plusieurs sorties nécessaires ne sont pas exportées. L'interface actuelle révèle aussi les résultats mécaniques dès l'animation : CoM, projection, ZMP/CoP, GRF, bras de levier, anneaux de capacité et couples. Elle ne satisfait donc pas encore la séquence `PRÉDIRE → SIMULER → LIRE → COMPARER → EXPLIQUER`.

Répartition actuelle des 47 features après la tranche `F01`–`F04` :

| Statut | Nombre |
|---|---:|
| PRESENT | 13 |
| PARTIEL | 14 |
| ABSENT | 17 |
| PRESENT_MAIS_INADAPTE | 3 |

Une feature n'est pas marquée `PRESENT` au seul motif que la grandeur existe en mémoire. Elle doit aussi être accessible, compréhensible, documentée et suffisamment testée selon sa définition.

## 2. Décisions de conception enregistrées

Les demandes ajoutées pendant le cadrage sont intégrées aux actions proposées :

1. **F02 — coordonnées par infobulle** : dans la figure de droite (`animation_canvas`), le survol d'une articulation ou du centre de la barre doit afficher son nom et ses coordonnées `x, y` en mètres pour la frame courante. Les infobulles doivent pouvoir être désactivées dans le mode `OBSERVATION`.
2. **Export Excel global** : ajouter un classeur `.xlsx` reposant sur le même schéma canonique que le CSV, avec un onglet par famille de métriques et un onglet contenant la table anthropométrique effectivement utilisée. Le CSV existant reste disponible pour le CLI et les scripts afin de préserver la compatibilité.
3. **Menu d'affichage centralisé** : créer un menu `Affichage` contrôlant, sans recalcul, les coordonnées articulaires, orientations et angles segmentaires, angles articulaires, CoM global, projection du CoM, CoM segmentaires, barre, CoP/ZMP, GRF, base géométrique et limites fonctionnelles. Les presets `OBSERVATION`, `CINÉMATIQUE` et `DYNAMIQUE` doivent configurer ces mêmes couches plutôt que créer trois interfaces.

Architecture recommandée pour l'export Excel :

| Onglet | Contenu prévu |
|---|---|
| `conditions` | paramètres, backend, durées, frame count, pose basse |
| `temps` | condition, frame, temps absolu, temps normalisé, Δt, phase |
| `coordonnees` | articulations et barre, coordonnées x/y |
| `orientations` | pied, jambe, cuisse, tronc et conventions |
| `cinematique_articulaire` | angles, vitesses et accélérations |
| `anthropometrie` | masse, longueur, fraction de CoM, offsets, inertie et source |
| `com_segmentaires` | coordonnées et contributions pondérées de chaque segment et de la barre |
| `com_global` | position, vitesse et accélération du CoM global |
| `forces_equilibre` | GRF, poids, CoP/ZMP, bases et marges |
| `dynamique` | demande, composantes validées, capacité, utilisation et puissance |
| `definitions` | nom canonique, définition, unité, signe, repère et provenance |

Cette structure ne doit pas dupliquer les calculs : un module d'export dédié doit transformer les objets scientifiques existants en tables partagées par le GUI, le CLI, le CSV et Excel.

## 3. Architecture existante

| Domaine | Source de vérité actuelle | Observation |
|---|---|---|
| Anthropométrie | `src/squat_gui/anthropometry.py` — `SegmentSpec`, `Anthropometry` | Masses, longueurs, fractions de CoM, inerties et offsets centralisés, y compris l'offset transverse du CoM du pied. |
| Cinématique | `src/squat_gui/kinematics.py` — `Pose`, `MotionState`, `pose_from_angles`, `motion_state` | Positions, CoM segmentaires/global, trajectoire et phases centralisés. |
| Loi temporelle | `src/squat_gui/yeadon.py` — `QuinticBoundaryTrajectory` | Quintique à vitesse et accélération nulles aux bornes; aucun plateau constant. |
| Dynamique | `src/squat_gui/dynamics.py` — `inverse_dynamics`, `simulate` | Backend analytique et adaptateur biorbd; décomposition avancée incomplète. |
| Backend biorbd | `src/squat_gui/backend.py` — `biomod_text`, `BiorbdModelCache` | Modèle `.bioMod` généré selon anthropométrie, barre et wedge. |
| GUI | `src/squat_gui/app.py` — `SquatGui` | Le bouton-menu `Affichage`, l'inspecteur temporel et les infobulles F02 sont intégrés; le fichier mélange encore orchestration, rendu, comparaison et logique de présentation. |
| CLI/export | `src/squat_gui/cli.py` — `simulate_condition`, `write_csv`, `write_json` | Export riche mais incomplet et sans dictionnaire de données canonique. |
| Batch laboratoire | `Labo/scripts/run_squat_batch.py`, `analyse_squat_results.py` | Réutilise le CLI; analyse de synthèse sans dépendance externe. |
| Packaging | `packaging/squat_gui.spec`, scripts Windows/macOS | Pillow inclus; aucune dépendance vidéo ou Excel prévue. |

## 4. Conventions identifiées

- Repère global 2D : `x` horizontal antérieur, `y` vertical vers le haut, `z` hors du plan (`backend.biomod_text`).
- Les longueurs et positions sont en mètres, les masses en kilogrammes et le temps en secondes.
- Les calculs angulaires internes utilisent les radians; le GUI et le CSV affichent/exportent principalement des degrés.
- Pour la jambe, la cuisse et le tronc, `unit_from_vertical(angle) = (sin(angle), cos(angle))` : zéro est vertical et un angle positif incline vers `+x`, donc dans le sens horaire dans la vue `x-y` actuelle.
- Les orientations absolues sont maintenant reconstruites depuis les extrémités géométriques et exportées pour le pied, la jambe, la cuisse et le tronc. Les anciennes colonnes internes `q_*` sont conservées pour compatibilité.
- Le pied est défini du talon vers les orteils. Un wedge positif relève le talon et oriente le pied de `-wedge_angle` depuis `+x`.
- Angles articulaires : cheville reconstruite relativement au pied, genou `q_thigh - q_shank`, hanche `q_trunk - q_thigh`. La reconstruction depuis les orientations tient compte du wedge et fait l'objet de tests.
- Conversion vers biorbd : `[-q0, -(q1-q0), -(q2-q1)]`; les signes sont inversés dans `_biorbd_coordinates` et `_joint_dict_from_biorbd_tau`.
- GRF : `x` positif vers l'avant, `y` positif vers le haut. La convention de signe des couples et puissances n'est pas documentée de façon suffisante pour l'enseignement.
- Le point d'appui est exprimé sur le plan horizontal `y=0` avec une provenance explicite : `CoP` pour le bilan analytique, `ZMP` pour `biorbd.CalcZeroMomentPoint` ou son fallback dynamique. La base géométrique projetée couvre toute la longueur du pied, du talon aux orteils. La zone fonctionnelle va de la projection de la cheville à la tête des métatarsiens, modélisée à 85 % du segment talon–orteils; les orteils distaux restent hors de cette zone.
- Les forces suivent `+x` vers l'avant et `+y` vers le haut. Le poids vaut `(0, -m*g)` avec `g=9,80665 m/s²`; l'identité vérifiée est `GRF + poids = m*a_COM`.
- Le modèle représente les deux membres inférieurs combinés. La masse corporelle de référence est 70 kg. La barre est ponctuelle dans le modèle analytique et reçoit une très petite inertie régularisée dans le `.bioMod`.
- Les contributions segmentaires au CoM sont définies par `m_i*x_i` et `m_i*y_i`; leur somme divisée par la masse totale reconstruit exactement le CoM global calculé dans `pose_from_angles`.
- Le temps scientifique va de `0` à la durée totale. Les courbes GUI utilisent actuellement un temps centré sur le squat et peuvent être normalisées; l'animation avance toutefois d'une frame toutes les 30 ms, indépendamment des durées physiques.

## 5. Tableau d'audit des features

| ID | Feature | Compétence | Statut | Preuve dans le code | Limite actuelle | Action proposée | Priorité |
|---|---|---|---|---|---|---|---|
| F01 | Temps et frames | C4, C5 | PRESENT | `observables.FrameInfo/frame_info`; inspecteur sous le curseur dans `app.redraw`; export `frame/time_s/delta_time_s/normalized_time_percent/phase`; tests `test_frame_info_*` | Le titre de l'animation nomme explicitement le temps centré afin de le distinguer du temps absolu de l'inspecteur. | Conserver cette source commune lors de F09/F22/F27. | P0 |
| F02 | Coordonnées articulaires | C1, C5 | PRESENT | `observables.joint_coordinates`; cibles et infobulles `register_animation_hover_targets/on_animation_motion`; couche `Coordonnées articulaires (survol)`; export `ankle/knee/hip/shoulder/bar_{x,y}_m`; tests de coordonnées et longueurs | L'export Excel regroupé reste prévu dans F12, mais les valeurs sont déjà exportables en CSV. | Réutiliser ces colonnes canoniques dans l'onglet Excel `coordonnees`. | P0 |
| F03 | Orientations segmentaires | C1 | PRESENT | `kinematics.segment_orientations`; couche `Orientations segmentaires`; export `*_orientation_deg`; conventions README; tests avec wedge | Affichage volontairement compact; les définitions tabulaires détaillées viendront avec F12. | Réutiliser ces valeurs sans recalcul dans le schéma Excel. | P0 |
| F04 | Angles articulaires | C1, C4 | PRESENT | `joint_angles_from_orientations`, `joint_angles_from_pose`, conversions segment↔articulation centralisées; GUI, courbes, limites et CLI réutilisent la même convention; tests de reconstruction avec wedge | Les signes pédagogiques sont documentés; ils devront rester cohérents avec la décomposition dynamique F30–F35. | Verrouiller ces conventions dans le dictionnaire de données F12. | P0 |
| F05 | Longueurs segmentaires | C1, C2, C10 | PRESENT | `observables.segment_anthropometry`; couche `Anthropométrie utilisée` avec longueurs effectives; export `*_length_m`; tests des échelles réellement appliquées | L'onglet Excel anthropométrique reste à assembler dans F12 à partir de cette table canonique. | Réutiliser directement la table dans l'export XLSX. | P0 |
| F06 | CoM segmentaires | C2 | PRESENT | `Pose.segment_coms`; `SegmentAnthropometry`; couche `CoM segmentaires + barre`; infobulles avec coordonnées, masse, fraction/offset, inertie et contributions; export complet par segment | La barre reste ponctuelle dans l'analytique; l'inertie numérique régularisée propre à biorbd devra être explicitée dans le dictionnaire F12. | Produire l'onglet `anthropometrie` sans recalcul. | P0 |
| F07 | CoM multicorps | C2, C7 | PRESENT | `com_contributions` et `reconstruct_global_com`; export masse totale, `m*x`, `m*y` et CoM global; tests avec wedge, grossesse et barre overhead à 12 décimales | Aucune limite fonctionnelle restante pour le backend analytique; la validation biorbd demeure bloquée par l'environnement. | Conserver l'identité comme test de contrat de l'export Excel. | P0 |
| F08 | Position, vitesse, accélération | C3, C4, C5, C6 | PRESENT | `com_velocities` et `com_accelerations`; pondération analytique dans `total_com_velocity/acceleration`; courbes et export `com_*`; tests analytiques et différences centrées | La vue simultanée des trois ordres reste volontairement séparée dans F21; les trois quantités sont correctes et sélectionnables ici. | Réutiliser ces séries validées dans la vue synchronisée F21. | P0 |
| F09 | Données pour dérivation manuelle | C5 | PRESENT | `NeighborSample/neighbor_samples`; couche `Échantillons i−1 / i / i+1`; temps, phase, CoM, angles et Δt affichés; coordonnées complètes disponibles frame par frame dans le CSV; tests de frontières | Aux frontières, la donnée absente est explicitement indiquée plutôt que dupliquée. | Conserver ce comportement dans le futur snapshot numérique F45. | P0 |
| F10 | Forces de réaction et poids | C3, C4, C6 | PRESENT | `ForceBalance/force_balance`; couches GRF et poids; ligne `m·g` calculée depuis la masse; export poids/résidu; tests `GRF_x=m*a_x` et `GRF_y-mg=m*a_y` à 11 décimales | La validation numérique biorbd reste indisponible dans l'environnement local, mais les conventions et la provenance sont explicites. | Réutiliser le bilan dans le dictionnaire et l'onglet `forces_equilibre` de F12. | P0 |
| F11 | Équilibre | C7 | PRESENT | `geometric_support_limits`, `functional_support_limits`, `SupportMargins`; couches base/zone/CoP-ZMP; panneau d'équilibre; provenance dans `DynamicsResult`; exports des bornes, marges et appartenances | Le backend biorbd natif/fallback est distingué dans le code mais ne peut pas être exécuté avec l'ABI NumPy locale. | Conserver les anciens champs `cop_*`/`zmp_*` uniquement comme compatibilité documentée dans F12. | P0 |
| F12 | Export canonique | C4, C8 | PRESENT | Schéma courant `1.2.0` dans `export_schema`; CSV large versionné; 11 onglets Excel issus des mêmes lignes; dictionnaire unité/définition/signe/statut; bouton GUI et option CLI `--xlsx`; tests de contrat et rendu de chaque feuille | Le runtime Excel dépend de Node.js et `@oai/artifact-tool`; il est détecté automatiquement dans Codex et configurable par variables d'environnement ailleurs. | Stabiliser le schéma en ajoutant une migration explicite lors d'une future version majeure. | P0 |
| F13 | Tests scientifiques | C1–C7 | PRESENT | Tests anthropométrie, cinématique, CoM, dérivées, forces, équilibre, dynamique, CLI et contrat Excel; reconstruction du CoM à `1e-12`; détection biorbd par import fonctionnel; assertions explicites `backend == biorbd` | Les 3 tests biorbd sont correctement ignorés dans l'environnement local non supporté (ABI NumPy 1.x/2.x); ils ne valident plus silencieusement l'analytique. | Exécuter ces mêmes tests dans un environnement biorbd compatible avant toute revendication numérique biorbd. | P0 |
| F14 | Export vidéo | C3, C4 | PRESENT | Renderer Pillow hors écran; MP4 H.264 `900×720` via imageio-ffmpeg; bouton `Exporter MP4`; 20 fps; JSON de reproductibilité; test d'encodage et inspection frame centrale | L'installation légère doit inclure l'extra `[video]`; la durée encodée inclut l'affichage de la frame terminale (`10,05 s` pour une trajectoire de `10,00 s`). | Conserver séparément durée de trajectoire et durée encodée dans tous les consommateurs. | P1 |
| F15 | Couches vidéo | C3, C7 | PRESENT | `RenderLayers` partagé par GUI et vidéo; CoM, projection, CoM segmentaires, CoP/ZMP, GRF, poids, bases, bilan, coordonnées, orientations, angles, anthropométrie, bras de levier, anneaux, marqueurs et alertes; état sérialisé dans le JSON | L'overlay `i-1/i/i+1` reste propre à l'inspection interactive et n'est pas rendu dans la vidéo. | Ajouter des presets nommés enseignant/étudiant lors du bloc pédagogique correspondant. | P1 |
| F16 | Durées indépendantes | C6, C10 | PRESENT | `frame_count_for_duration`; contrat `Δt=0,05 s`; 201 frames pour 10 s et 141 pour 7 s; playback et vidéo à 20 fps; temps centré corrigé exactement à zéro; tests durée/discrétisation | La CLI permet toujours un `--frames` explicite, qui peut volontairement déroger au pas par défaut. | Afficher éventuellement un contrôle avancé `Δt/FPS` si un usage de ralenti devient nécessaire. | P1 |
| F17 | Presets temporels | C6, C8 | PRESENT | Six `TemporalPreset` nommés; sélecteur dédié; contrôles indépendants conservés; `Personnalisé` détecté; descente/montée limitées à 0,5/1/2/4 s, isométrique à 0/0,5/1/2 s; 161 frames pour le preset lent de 8 s | Les valeurs sont des choix pédagogiques explicites, pas des normes biomécaniques. | Conserver cette échelle discrète dans les supports de cours. | P1 |
| F18 | Mode OBSERVATION | C3, C4 | PRESENT | `RevealMode.OBSERVATION`; toutes les couches scientifiques, courbes, valeurs, temps, phases et alertes sont masqués; sujet et barre restent animés | Les poignées demeurent visibles dans l'éditeur de pose afin de conserver l'interaction demandée. | Conserver ce masque lors des futures vues numériques F21–F25. | P1 |
| F19 | Mode CINÉMATIQUE | C3, C4, C5 | PRESENT | `RevealMode.KINEMATICS`; CoM, géométrie et coordonnées au survol; menu limité aux courbes articulaires/CoM et aux trois ordres position-vitesse-accélération | L'affichage simultané des trois ordres appartient toujours explicitement à F21. | Réutiliser ce niveau comme garde de révélation dans la vue F21. | P1 |
| F20 | Mode DYNAMIQUE | C9, C11 | PRESENT | `RevealMode.DYNAMICS`; complète la cinématique par GRF, poids, CoP/ZMP, bases, bras de levier, couples, ratios de capacité et alertes; parcours didactique OBSERVATION→CINÉMATIQUE→DYNAMIQUE | Le panneau de bilan détaillé reste une couche libre pour éviter de surcharger le preset. | Appliquer le même garde aux sorties avancées F30–F41. | P1 |
| F21 | Position/vitesse/accélération synchronisées | C3, C4, C5, C6 | PRESENT | Vue `cinematique synchronisee`; trois axes temporels empilés pour angles articulaires ou CoM; unités et zéros propres à chaque ordre; tests des séries et unités | Les trois ordres partagent l'abscisse mais conservent volontairement des ordonnées distinctes. | Réutiliser ce renderer lors de l'ajout des modes temporels F27. | P1 |
| F22 | Curseur temporel synchronisé | C4 | PRESENT | `frame_var` canonique; curseur rouge commun; clic/glissement sur chacun des axes; animation, courbes et inspecteur mis à jour ensemble; échantillon le plus proche explicite par condition | En comparaison de durées différentes, chaque condition indique son propre temps effectivement échantillonné. | Formaliser l'alignement absolu/centré/normalisé dans F27. | P1 |
| F23 | Lecture numérique des courbes | C4, C5 | PRESENT | Onglet `Valeurs au curseur`; une ligne par condition et courbe visible; valeur à six décimales, unité, temps de courbe et phase; 9 lignes pour trois angles×trois ordres, 6 pour CoM | Les extrema et passages par zéro ne sont pas calculés automatiquement : ils restent des questions explorables avec le curseur, conformément à l'objectif pédagogique. | Ajouter éventuellement des outils enseignant d'événements après F27. | P1 |
| F24 | Limites et noms de phases | C4 | PRESENT | `timeline.phase_windows`; limites issues exactement des trois durées configurées; noms sur chaque axe; tests symétriques et asymétriques | En comparaison, les limites sont tracées pour chaque condition et peuvent se superposer. | Coupler leur interprétation aux trois représentations temporelles de F27. | P1 |
| F25 | Masquage des phases | C4 | PRESENT | Menu `Phases` toujours visible dans les résultats; contrôles indépendants noms/limites; phase masquée simultanément dans l'inspecteur | Les données exportées conservent toujours la phase, seul l'affichage pédagogique est masqué. | Conserver cette séparation affichage/données dans les futures vues. | P1 |
| F26 | Affichage sélectif | C4, C8 | PRESENT | Menu `Affichage` centralisant courbes, composantes, axes, limites, phases, qualité des sprites et toutes les couches de l'animation; `on_display_changed` ne déclenche que le rendu | Les contrôles contextuels de courbe et le menu `Phases` restent aussi disponibles comme raccourcis synchronisés. | Conserver une seule variable Tk par choix visuel afin d'éviter toute divergence entre raccourcis. | P1 |
| F27 | Temps absolu et normalisé | C4, C6, C8 | PRESENT | `TimeMode` offre `absolu`, `centré` et `normalisé`; axes, curseur, animation, inspecteur et phases partagent le même repère; avertissement explicite en normalisé | La normalisation est désormais conventionnelle `0…100 %`, changement observable par rapport à l'ancien `−100…+100`. | Conserver le temps absolu dans les exports et rappeler que la normalisation masque la durée. | P1 |
| F28 | Comparaison de conditions | C8, C10 | PRESENT | comparaison multi-condition, légende, échantillonnage partagé, colonne de résumé et onglet `Variables contrôlées`; smoke test complet de sélection de deux lignes | Les sorties biomécaniques ne sont pas résumées automatiquement dans cet onglet, qui reste centré sur le plan expérimental. | Ajouter les résumés scientifiques lors de F39 sans mélanger paramètres contrôlés et résultats. | P1 |
| F29 | Variables contrôlées | C8 | PRESENT | bouton `Dupliquer`, copie vers l'éditeur, `comparison.parameter_differences`, valeurs avec unités, exclusion des réglages d'affichage et persistance JSON de la référence | La duplication prépare une variante éditable; elle ne crée une nouvelle ligne qu'après `Ajouter`, afin d'éviter les doublons identiques. | Conserver ce workflow explicite dans le tutoriel et les futurs bundles enseignants. | P1 |
| F30 | Couple total de dynamique inverse | C9, C12 | PRESENT | `inverse_dynamics`; biorbd `InverseDynamics`; courbe `total ID`; export `*_inverse_dynamics_total_Nm`; README | Le total appartient au modèle contraint à pied fixé; il n'inclut donc pas une seconde fois la GRF comme force généralisée. | Conserver cette convention explicite dans tous les supports. | P2 |
| F31 | Terme `M(q)qddot` | C9 | PRESENT | `_analytical_inverse_dynamics_decomposition`; `_biorbd_inverse_dynamics_decomposition` appelle `massMatrix(q) @ qddot`; courbe/export dédiés; test fake-biorbd de l'appel | Les coordonnées analytiques internes sont des orientations segmentaires absolues puis les moments sont projetés aux articulations; biorbd utilise ses coordonnées articulaires relatives. | Comparer numériquement les deux backends dans un environnement biorbd compatible. | P2 |
| F32 | Termes dépendant de `qdot` | C9 | PRESENT | analytique isolé à `qddot=0`, gravité coupée; biorbd `InverseDynamics(q,qdot,0)-InverseDynamics(q,0,0)`; courbe/export `velocity_dependent` | Le terme agrège Coriolis et centrifuge; aucune séparation artificielle entre les deux n'est revendiquée. | Conserver le libellé collectif « termes dépendant de qdot ». | P2 |
| F33 | Gravité | C9 | PRESENT | analytique avec vitesse/accélération nulles; biorbd `InverseDynamics(q,0,0)`; courbe/export `gravity_Nm` | Dépend du repère, du signe articulaire et de la gravité configurée dans le moteur. | Vérifier toute future modification de repère contre le test de reconstruction. | P2 |
| F34 | Contact/forces externes | C9 | PRESENT | `_contact_moments`; `_biorbd_contact_torques` via `ExternalForceSet`; composante canonique signée `external_contact`; `contact_source` dans le GUI/export | Sur le modèle à pied fixé, le contact est un diagnostic/cas contrefactuel et non un quatrième terme du total contraint; la validation biorbd réelle reste bloquée par l'ABI locale. | Ne pas additionner la GRF au total contraint; revalider `ExternalForceSet` dans l'environnement biorbd cible. | P2 |
| F35 | Reconstruction du couple | C9, C12 | PRESENT | `total = mass_acceleration + velocity + gravity`; résidu par articulation; tests analytiques à 11 décimales et biorbd prévu à 8; export du résidu | Le champ historique `inertiels_non_lineaires = total-contact` demeure uniquement pour compatibilité de schéma et est masqué dans le GUI. | Supprimer ce champ lors d'une future version majeure du schéma. | P2 |
| F36 | Relation couple-angle | C11, C12 | PRESENT | angle signé converti vers la convention Anderson; domaine `C3 ± pi/(2*C2)`; lobe actif tronqué à zéro sans plancher arbitraire; facteurs/domaine exportés | Le modèle ne comprend pas le couple passif; hors lobe actif, `U` est non défini si une demande subsiste. | Conserver la distinction capacité active/couple total humain. | P2 |
| F37 | Relation couple-vitesse | C11, C12 | PRESENT | paramètres publiés C4–C6; vitesse réelle en rad/s; régime raccordé au signe de `tau*omega`; contrôles angle/vitesse séparés; régime/facteur/source exportés | Le preset Sportifs est un hybride d'amplitude sportive et de forme Anderson; aucune personnalisation individuelle. | Ne pas présenter les valeurs moyennes comme une norme individuelle. | P2 |
| F38 | Utilisation demande/capacité `U(t)` | C11, C12 | PRESENT | `U=abs(torque)/capacité active`; courbe `%`; ratio/pourcentage/état exportés; alerte reformulée sous hypothèses | `U` n'est pas calculable si la capacité active vaut zéro; ce cas est signalé au lieu d'être masqué par un plancher. | Employer systématiquement « faisabilité mécanique dans les hypothèses du modèle ». | P2 |
| F39 | Résumé demande/capacité | C11, C12 | PRESENT | JSON canonique et tableau GUI: maximum, articulation limitante, frame, temps, phase, dépassement et événements de capacité nulle | Le maximum dépend du preset et des relations actives choisies. | Comparer uniquement des conditions dont les hypothèses de capacité sont contrôlées. | P2 |
| F40 | Anthropométrie cohérente | C10, C12 | PRESENT | modes `longueur seule` et `morphotype recalibre`; masses/inerties isolées dans le premier, recalibrage didactique explicite dans le second; mode/règle/table effective GUI-export | Le morphotype recalibré repose sur une hypothèse de densité linéique constante, pas sur une régression populationnelle. | Conserver cette qualification et remplacer la règle si une base anthropométrique populationnelle est retenue. | P2 |
| F41 | Positions de barre | C10 | PRESENT | matrice front/back/over-head couvrant géométrie, invariants masse/inertie, dynamique, export, cache `.bioMod` et comparaison | La barre reste ponctuelle, sans orientation, longueur ni inertie propre. | Passer à un segment de barre seulement si cette fidélité devient nécessaire. | P2 |
| F42 | Plusieurs lois temporelles | C6, C10 | ABSENT | Une seule `QuinticBoundaryTrajectory` | Aucun choix de loi. | Auditer les besoins après P2; garder la quintique par défaut. | P3 |
| F43 | Intervalle à vitesse approximativement constante | C6 | ABSENT | Profil quintique `10s³-15s⁴+6s⁵` | Aucun plateau et il ne doit pas être décrit comme tel. | Ajouter seulement si pédagogiquement retenu, avec profil et tests dédiés. | P3 |
| F44 | Export automatique d'images | C4, C8 | ABSENT | Aucun export du canvas/courbes | Figures générées manuellement seulement. | Ajouter renderer de courbes réutilisable et export PNG/SVG après stabilisation des vues. | P3 |
| F45 | Snapshot numérique | C1–C7 | ABSENT | Valeurs de couples à l'animation seulement | Pas de fiche complète d'une frame. | Exporter un snapshot depuis le même inspecteur scientifique que F01–F11. | P3 |
| F46 | Variantes reproductibles | C8, C10 | PARTIEL | CLI `run/batch`, JSON de conditions, CSV de scénarios `Labo/` | Pas de générateur de variantes ni de provenance/seed; le YAML non suivi utilise une ancienne CLI incompatible. | Définir un format de scénario canonique et une génération déterministe. | P3 |
| F47 | Ensemble enseignant cohérent | C8, C12 | PARTIEL | Batch CSV + résumé JSON/CSV et script de génération de questions | Vidéo, figures et snapshot cohérents absents; exemples non suivis potentiellement obsolètes. | Construire un bundle seulement après stabilisation vidéo/export/snapshot et validation pédagogique. | P3 |

## 6. Audit des tests et de l'environnement

Baseline exécutée avec Python 3.11 de l'environnement `vitpose-ekf`, `PYTHONPATH=src` et les caches Python redirigés vers `/tmp`.

| Groupe | Résultat |
|---|---|
| `test_app_plot.py` | 11/11 réussis |
| `test_cli.py` | 2/2 réussis |
| `test_dynamics.py` | 15/15 réussis |
| `test_raster_segments.py` | 12/12 réussis (45,5 s) |
| `test_resources.py` | 2/2 réussis |
| `test_yeadon.py` | 2/2 réussis |
| Sous-ensemble sans biorbd | 44/44 réussis |
| `test_biorbd_backend.py` | 3 exécutés, 1 échec; les 2 autres retombent silencieusement sur l'analytique et ne constituent donc pas une validation biorbd fiable |
| Smoke test Tkinter | Fenêtre 1480×920 créée, 81 états/résultats, redraw à la frame 40; backend analytique après échec biorbd |

Cause de l'échec biorbd : l'extension installée a été compilée avec NumPy 1.x, tandis que l'environnement contient NumPy 2.4.4 (`ImportError: numpy.core.multiarray failed to import`, `_ARRAY_API not found`). `detect_optional_backends` et le décorateur de test utilisent `find_spec`, qui détecte le paquet sans vérifier que son extension native est importable.

Conséquences :

- le GUI affiche d'abord que biorbd est disponible, puis retombe sur l'analytique lors de la simulation;
- `simulate` masque toute exception de chargement biorbd en mode automatique;
- deux tests annotés biorbd peuvent réussir sur le backend analytique;
- aucun résultat scientifique biorbd ne doit être déclaré validé dans cet environnement avant correction de l'ABI et assertion explicite du backend.

## 7. Audit du matériel `Labo/`

### Matériel versionné

- `Labo/scenarios/scenarios_labo_squat.csv` utilise la CLI actuelle et couvre posture, équilibre, charge et durées.
- `Labo/scripts/run_squat_batch.py` appelle correctement `python -m squat_gui batch`.
- `Labo/scripts/analyse_squat_results.py` consomme les exports actuels, mais reconstruit encore `total-contact` sous le nom inertiel/non-linéaire.
- Le guide Markdown inclut désormais un tutoriel de prise en main couvrant F17–F29; il demande parfois des grandeurs qui devront changer après F30–F35.
- `Labo/scripts/build_student_guide_docx.py` régénère le guide Word depuis cette source Markdown avec listes, code, tableau et pagination natifs.

### Matériel non suivi, préservé sans modification

- Le YAML `Labo/scenarios/scenarios_labo_squat.yaml` utilise d'anciens flags absents de la CLI actuelle (`--output`, `--phase-duration`, `--trunk-angle`, etc.) et annonce `Mqddot` alors que cette composante n'existe pas.
- `Labo/data_exemple/valeurs_exemple_gui.csv` suit un ancien schéma et contient des valeurs de référence qui ne sont pas reliées par test à la version actuelle.
- `Labo/scripts/generate_questions_from_gui_summary.py` dépend de pandas, absent des dépendances déclarées dans `pyproject.toml`.
- Les corrigés et banques Studium sont présents dans le dépôt public local sous forme non suivie. Ils ne doivent pas être modifiés ni distribués avec le matériel étudiant.

### Inspection visuelle des DOCX

Les deux DOCX ont été rendus en PNG avec LibreOffice puis inspectés page par page. Le guide étudiant a été régénéré après l'audit initial.

- `Labo/Guide_etudiant_labo_squat.docx` : sept pages inspectées à 100 %; aucun marqueur Markdown visible, listes correctement espacées, livrables renumérotés 1–5, en-têtes/pieds de page cohérents et grille d'évaluation complète sur une page autonome. Le tutoriel couvre les presets temporels, les trois étapes didactiques, les couches d'affichage, l'infobulle articulaire, les courbes synchronisées, l'inspecteur, les phases, les repères temporels, la duplication contrôlée et les exports.
- `Labo/Corrige_enseignant_labo_squat.docx` : deux pages, lisible et sans chevauchement manifeste. Son contenu mentionne toutefois `Mqddot/couple total`, grandeur non produite par le code actuel.

Le corrigé enseignant reste volontairement inchangé et devra être synchronisé avec F30–F35 dans le dépôt enseignant avant distribution.

## 8. Risques et décisions requises avant le LOT B

1. **Convention des angles** : décider et documenter si l'angle de cheville est relatif au pied ou conserve la convention interne actuelle, particulièrement avec wedge.
2. **Terminologie CoP/ZMP** : choisir les termes exacts par backend et ne pas présenter deux méthodes différentes comme strictement identiques sans explication.
3. **Backend de référence** : rétablir un environnement biorbd importable et rendre les tests incapables de valider silencieusement le backend analytique.
4. **Export** : garder le CSV comme contrat machine compatible et ajouter Excel comme conteneur pédagogique fondé sur le même schéma.
5. **Affichage** : centraliser les couches avant d'ajouter les presets, infobulles et vidéo; `app.py` doit rester orchestration/présentation.
6. **Vitesse du CoM analytique** : corriger avant d'exposer davantage cette grandeur aux étudiants.
7. **Supports Labo** : ne pas utiliser le YAML et les valeurs d'exemple non suivis comme vérité scientifique tant qu'ils ne sont pas régénérés et testés.

## 9. Critères proposés de validation du LOT B (P0)

Le LOT B pourra être considéré validé lorsque :

- chaque grandeur F01–F11 est inspectable dans le GUI et exportable avec unités/conventions;
- les infobulles F02 fonctionnent sur la figure d'animation sans révéler de données en mode observation;
- le CSV et le classeur Excel proviennent du même schéma versionné;
- l'onglet anthropométrique permet de reconstruire les CoM segmentaires et global;
- les tests pédagogiques demandés reconstruisent orientations, angles, CoM, vitesse, accélération, GRF et phases;
- les tests analytiques et biorbd identifient explicitement leur backend et passent dans leurs environnements supportés;
- la suite complète, le CLI, un smoke test GUI et le packaging pertinent sont vérifiés;
- l'audit est mis à jour avec les fichiers, fonctions et tests finaux.

## 10. Validation de la tranche LOT B — F01 à F04

Implémentation contrôlée le 2026-08-10 :

- `tests/test_observables.py` ajoute six tests sur le temps, les coordonnées, les longueurs, les orientations absolues, le wedge et les conversions angulaires;
- `tests/test_cli.py` vérifie la présence du pas temporel, du temps normalisé, des coordonnées et des orientations dans l'export;
- sous-ensemble ciblé F01–F04/CLI/GUI : `19 passed`;
- suite complète hors backend biorbd : `50 passed, 36 subtests passed`;
- smoke test Tkinter réel : `81` états, `10` entrées dans `Affichage`, `5` cibles de survol et `2` objets canvas composant l'infobulle;
- inspection visuelle effectuée à la frame 40 : inspecteur temporel lisible, bouton `Affichage` accessible, coordonnées en mètres affichées au survol, orientations et angles activables séparément.

Limite d'environnement inchangée : le paquet biorbd local reste non importable à cause de son ABI NumPy 1.x face à NumPy 2.4.4. Le smoke test retombe donc explicitement sur le backend analytique. Aucun résultat biorbd n'est déclaré validé.

## 11. Validation de la tranche LOT B — F05 à F07

Implémentation contrôlée le 2026-08-10 :

- `SegmentAnthropometry` expose la table effective pied/jambe/cuisse/tronc/barre, incluant longueurs, masses, fractions/offsets, rayons de giration, inerties et offsets d'attache de la barre;
- l'offset transverse de `0,025 m` du CoM du pied est désormais centralisé dans `Anthropometry` et partagé par la géométrie analytique, le `.bioMod` et la table inspectable;
- `ComContribution` expose les coordonnées et produits `m*x`, `m*y` de chaque segment;
- le test de reconstruction retrouve le CoM global à 12 décimales avec wedge, profil grossesse et barre overhead;
- sous-ensemble ciblé incluant GUI, CLI et dynamique : `37 passed, 11 subtests passed`;
- suite complète hors backend biorbd : `53 passed, 41 subtests passed`;
- smoke test Tkinter réel : `11` entrées dans `Affichage`, `5` cibles de CoM segmentaire, une infobulle et un panneau anthropométrique effectivement rendus;
- inspection visuelle : longueurs et masses lisibles dans le panneau, CoM segmentaires identifiés en français et détail pondéré accessible au survol.

Limite inchangée : biorbd ne s'importe pas dans l'environnement NumPy 2.4.4; le contrôle GUI utilise explicitement le backend analytique.

## 12. Validation de la tranche LOT B — F08 à F09

Implémentation contrôlée le 2026-08-10 :

- `com_velocities` dérive analytiquement les positions des CoM pied/jambe/cuisse/tronc/barre, wedge compris;
- le backend analytique pondère ces vitesses par les masses et renseigne désormais `DynamicsResult.com_velocity` au lieu de retourner systématiquement zéro;
- les vitesses segmentaires concordent avec une différence centrée des positions à 8 décimales et les accélérations avec une différence centrée des vitesses à 7 décimales sur le cas de test;
- sur une simulation échantillonnée à `Δt=0,01 s`, les tolérances explicites sont `1e-5 m/s` pour la vitesse globale et `2e-4 m/s²` pour l'accélération globale;
- `neighbor_samples` fournit exactement `i−1`, `i`, `i+1` et ne duplique pas les frontières;
- sous-ensemble ciblé incluant GUI, CLI et dynamique : `42 passed, 21 subtests passed`;
- suite complète hors backend biorbd : `58 passed, 51 subtests passed`;
- smoke test Tkinter réel à la frame 20 : vitesse analytique `(-0,0161; -0,1147) m/s`, panneau trois-échantillons rendu et inspecteur `t=2,500 s`, `Δt=0,125 s`, phase excentrique;
- inspection visuelle : courbes horizontale/verticale de vitesse non nulles, curseur synchronisé et panneau manuel lisible.

Limite inchangée : la suite biorbd reste bloquée par l'ABI NumPy locale; aucun résultat biorbd supplémentaire n'est revendiqué.

## 13. Validation de la tranche LOT B — F10 à F11

Implémentation contrôlée le 2026-08-10 :

- `ForceBalance` expose le poids positif, son vecteur `(0,-m*g)`, la résultante externe, `m*a_COM` et le résidu du bilan;
- la ligne de référence des courbes de GRF utilise désormais explicitement `total_mass * 9,80665` et non la première GRF verticale;
- les identités `GRF_x=m*a_COM_x` et `GRF_y-m*g=m*a_COM_y` passent à 11 décimales sur 31 frames avec charge, wedge et profil grossesse;
- le backend analytique étiquette son point `CoP` avec la source `bilan dynamique analytique`; le chemin biorbd étiquette `ZMP` et distingue l'appel natif du fallback;
- `SupportMargins` sépare base géométrique et zone fonctionnelle, avec quatre marges signées et deux booléens d'appartenance;
- les champs legacy sont maintenus : `cop_in_foot` signifie maintenant réellement l'appartenance géométrique et `zmp_in_support` l'appartenance fonctionnelle;
- sous-ensemble ciblé F10–F11/GUI/CLI : `44 passed, 11 subtests passed`;
- suite complète hors backend biorbd : `63 passed, 51 subtests passed`;
- smoke test Tkinter réel à la frame 20 : `CoP`, poids `686,4655 N`, résidu `(0; 1,09e-13) N`, panneau de bilan rendu;
- inspection visuelle : flèches GRF/poids, bases étiquetées, alerte `CoP hors zone fonctionnelle d'appui` et ligne `m·g` lisibles.

Limite inchangée : la provenance biorbd est couverte structurellement, mais son exécution reste bloquée par l'ABI NumPy locale.

## 14. Validation de la tranche LOT B — F12 à F13

Implémentation contrôlée le 2026-08-10 :

- le contrat d'export, initialement `1.0.0`, est désormais versionné `1.1.0`; la première colonne du CSV et de chaque table Excel porte cette version;
- le CSV large reste rétrocompatible, notamment pour `cop_x_m`, `cop_in_foot` et les alias `zmp_*`, tous marqués `compatibilité legacy` dans le dictionnaire;
- le classeur sépare `conditions`, `temps`, `coordonnees`, `orientations`, `cinematique_articulaire`, `anthropometrie`, `com_segmentaires`, `com_global`, `forces_equilibre`, `dynamique` et `definitions`;
- la table anthropométrique contient cinq lignes par condition et reprend les masses, longueurs, fractions/offsets de CoM, rayons de giration, inerties et offsets de barre réellement utilisés;
- le test de contrat vérifie que toute colonne CSV et Excel possède une définition, une unité et une convention de signe, et que le CoM global se reconstruit depuis les contributions segmentaires à `1e-12`;
- l'export est accessible par le bouton `Exporter Excel` et par `--xlsx` pour les commandes `run` et `batch`;
- chaque onglet du classeur de référence a été rendu en PNG et inspecté; aucune valeur n'est mélangée à son unité et aucune erreur de formule n'a été détectée;
- la détection optionnelle importe réellement les extensions natives; le GUI ne tente plus de charger biorbd lorsqu'il est installé mais incompatible;
- les trois tests biorbd exigent désormais explicitement des résultats `backend == "biorbd"`;
- suite complète : `68 passed, 3 skipped, 51 subtests passed` en `33,95 s`;
- smoke test Tkinter réel : fenêtre `1480×920`, export de `81` frames et statut `classeur Excel écrit` visibles.

Limite d'environnement : les 3 skips correspondent à biorbd compilé avec NumPy 1.x face à NumPy 2.4.4. Ce blocage est maintenant détecté correctement et ne produit plus de faux succès analytiques; une validation numérique biorbd reste à exécuter dans un environnement ABI compatible.

## 15. Validation de la tranche LOT C — F14 à F16

Implémentation contrôlée le 2026-08-10 :

- la discrétisation par défaut est définie par `DEFAULT_SAMPLE_PERIOD_S=0,05`; le nombre de frames inclut les deux extrémités et s'adapte à la durée totale;
- le cas GUI par défaut produit `201` frames sur `10,00 s`, avec `Δt=0,050 s` à toutes les frames adjacentes;
- le classeur scientifique de référence a été régénéré avec `141` frames sur `7,00 s`; les 11 onglets ont été rendus et inspectés, et `temps!delta_time_s` vaut `0,050` sur toute la table;
- la lecture utilise un intervalle de `50 ms`, soit `20 fps`, et respecte donc le temps physique;
- le temps centré n'est plus estimé par la moyenne asymétrique des échantillons isométriques : la frame `100/200` affiche exactement `t_centré=0,00 s` et les courbes vont de `-5,00` à `+5,00 s`;
- `RenderLayers` est la configuration commune à la figure de droite et au renderer hors écran; les bras de levier, anneaux de capacité et marqueurs articulaires sont désormais eux aussi activables;
- l'export MP4 encode les silhouettes raffinées et les couches actives en H.264/YUV420p, `900×720`, `20 fps`;
- le JSON associé distingue la durée scientifique de la trajectoire (`10,00 s`) de la durée du flux incluant la dernière frame (`10,05 s`) et conserve backend, dimensions et couches;
- le MP4 complet de `201` frames a été relu avec ffmpeg; cadence `20,0 fps`, codec H.264, dimensions `900×720` et durée `10,05 s` confirmées;
- la frame centrale et la GUI ont été inspectées visuellement : boutons non tronqués, couches CoM/poids/bases lisibles, statut `201 frames · 20 fps`;
- suite complète : `74 passed, 3 skipped, 51 subtests passed` en `82,82 s`.

Limite inchangée : les trois skips biorbd correspondent exclusivement à l'ABI NumPy incompatible et ne concernent pas le renderer ou l'export vidéo.

## 16. Validation de la tranche LOT C — F17 à F20

Implémentation contrôlée le 2026-08-10 :

- les six presets temporels sont présents et distincts, avec leur triplet directement visible dans le sélecteur : `Référence` 4/2/4 s, `Lent` 4/2/2 s, `Rapide` 0,5/0,5/0,5 s, `Sans pause` 4/0/4 s, puis les deux profils asymétriques 4/1/0,5 s et 0,5/1/4 s;
- les contrôles numériques indépendants restent disponibles; toute combinaison différente est identifiée `Personnalisé`;
- tous les presets conservent exactement `Δt=0,05 s`; le preset lent produit 161 frames sur 8,00 s;
- `RevealMode` et `layers_for_reveal` forment un contrôle unique partagé par l'interface et l'export vidéo, sans nouvelle simulation ni écrasement des choix du mode `LIBRE`;
- `OBSERVATION` conserve uniquement le sujet et la barre animés; courbes, grandeurs, alertes, temps et noms de phase sont masqués;
- `CINÉMATIQUE` révèle CoM et coordonnées au survol, limite le menu aux articulations/CoM et conserve les trois choix position, vitesse et accélération;
- `DYNAMIQUE` ajoute GRF, poids, CoP/ZMP, bases d'appui, bras de levier, couples, ratios de capacité et alertes;
- le parcours en 11 étapes impose la séquence `OBSERVATION` jusqu'à l'hypothèse, puis `CINÉMATIQUE`, puis `DYNAMIQUE`; les contrôles incompatibles sont désactivés;
- smoke test Tkinter réel des trois états : fenêtre `1480×920`, panneau de résultats entièrement visible, aucune valeur mécanique en observation et transitions correctes aux étapes 6 et 7;
- suite complète : `83 passed, 3 skipped, 57 subtests passed` en `32,38 s`.

Limite assumée : les durées des presets sont des choix pédagogiques explicites et non des normes biomécaniques; elles peuvent être ajustées sans changer le contrat `Δt=0,05 s`.

## 17. Validation de la tranche LOT C — F21 à F25

Implémentation contrôlée le 2026-08-10 :

Validation fonctionnelle confirmée par l'enseignant avant le démarrage de F26–F29.

- la nouvelle vue `cinematique synchronisee` empile position, vitesse et accélération sur trois axes partageant strictement la même abscisse;
- la source est sélectionnable entre angles articulaires et CoM; les articulations ou composantes restent masquables individuellement sans resimulation;
- chaque axe possède son unité propre (`deg`, `deg/s`, `deg/s²` ou `m`, `m/s`, `m/s²`) et une ligne de zéro explicite incluse dans ses bornes;
- le curseur rouge peut être déplacé depuis le slider, par clic ou par glissement sur n'importe lequel des trois axes; il met à jour l'animation et les valeurs dans le même redraw;
- l'onglet `Valeurs au curseur` présente une ligne par condition et courbe visible, avec valeur à six décimales, unité, temps effectivement échantillonné et phase;
- l'inspecteur affiche 9 lignes pour trois angles×trois ordres et 6 lignes pour deux composantes du CoM×trois ordres;
- les limites de phases proviennent des durées configurées et non d'une estimation graphique; les noms et les limites sont deux contrôles indépendants;
- masquer les noms masque également la colonne phase de l'inspecteur, mais ne modifie ni les calculs ni les exports;
- la compatibilité des conditions sauvegardées a été révisée : les anciennes valeurs dynamiques à 6 s sont bornées à 4 s, tandis que l'échelle GUI/CLI officielle reste discrète;
- smoke tests Tkinter réels : transitions didactiques, neuf valeurs articulaires, six valeurs CoM, clic à 75 % donnant la frame 150/200, masquage de phase et panneau non tronqué;
- inspection visuelle `1480×920` : trois courbes lisibles, unités/zéros explicites, curseur commun, menu `Phases` accessible et sept lignes numériques visibles avec défilement;
- le tutoriel intégré nomme maintenant explicitement la vue synchronisée, le curseur, l'inspecteur et les phases; le guide étudiant Markdown/Word décrit le parcours F17–F25 et son DOCX de six pages a été inspecté intégralement;
- contrôle ciblé après synchronisation du tutoriel : `30 passed, 6 subtests passed`; smoke test Tkinter réel de l'étape 7 : mode `CINÉMATIQUE`, texte et surlignage du panneau de valeurs confirmés;
- suite complète : `92 passed, 3 skipped, 57 subtests passed` en `47,92 s`.

Limite inchangée : les trois skips proviennent exclusivement de l'ABI biorbd/NumPy locale; aucun ne concerne la timeline, les courbes ou l'inspecteur.

## 18. Validation de la tranche LOT C — F26 à F29

Implémentation contrôlée le 2026-08-11 :

- `Affichage` centralise les courbes, composantes, axes, limites, phases, sprites et couches scientifiques; une modification visuelle conserve les mêmes objets `states/results` et ne relance pas `simulate`;
- le repère temporel est visible à côté du curseur et propose `absolu` (`0…T` s), `centré` (milieu de la pause à `t=0`) et `normalisé` (`0…100 %`);
- axes, limites/noms de phases, curseur, animation et inspecteur numérique utilisent le même repère; un avertissement indique systématiquement que le mode normalisé masque la durée réelle, et devient plus explicite lorsque les conditions ont des durées différentes;
- le changement numérique de l'ancien `−100…+100` vers `0…100 %` est couvert par les tests de timeline et documenté dans le README;
- `Dupliquer` copie exactement une condition sélectionnée vers l'éditeur; la nouvelle ligne n'est créée qu'après modification puis `Ajouter`;
- la colonne `modifications contrôlées` fournit un résumé et l'onglet dédié donne paramètre, référence et valeur comparée avec unités;
- le diff sémantique inclut sujet, barre, charge, longueurs, durées, wedge, capacités et pose basse, mais exclut les couches, courbes et autres réglages purement visuels;
- la référence et son résumé sont conservés dans le JSON des conditions;
- tests ciblés : `36 passed, 6 subtests passed`; suite complète : `98 passed, 3 skipped, 57 subtests passed` en `107,06 s`;
- smoke test Tkinter réel : deux conditions, duplication puis changement de charge `0→30 % BW`, une seule différence `Charge` affichée, mode normalisé visible et absence de resimulation lors d'un changement d'affichage;
- inspection visuelle `1480×920` après correction : sélecteur temporel non tronqué, onglet `Variables contrôlées` lisible et comparaison des deux silhouettes/courbes cohérente.

Limite inchangée : les trois skips correspondent au backend biorbd non importable avec l'ABI NumPy locale; ils ne concernent pas F26–F29.

Validation fonctionnelle F26–F29 confirmée par l'enseignant le 2026-08-11; démarrage autorisé de F30–F35.

## 19. Implémentation de la tranche P2 — F30 à F35

Convention arrêtée le 2026-08-11 après audit des équations :

- les backends analytique et biorbd sont des modèles à pied fixé; le couple `total ID` reste donc le résultat contraint déjà utilisé par la puissance et la demande/capacité;
- la reconstruction canonique est `total ID = M(q)qddot + termes dépendant de qdot + gravité`;
- le moment de GRF est exposé séparément sous un signe additif `external_contact`; le total contrefactuel avec force externe est calculé mais ne remplace pas le total contraint;
- biorbd calcule explicitement `M(q)qddot` avec `massMatrix(q) @ qddot`; le backend analytique isole le même type de terme en annulant vitesse et gravité;
- les cinq courbes `M(q) qddot`, `termes qdot`, `gravité`, `contact externe (signé)` et `total ID` peuvent être masquées individuellement depuis `Affichage`;
- le schéma d'export passe à `1.1.0` et ajoute les quatre termes canoniques ainsi que le résidu de reconstruction; les colonnes ambiguës antérieures sont marquées `compatibilité legacy`.

Contrôles réalisés :

- reconstruction analytique testée à 11 décimales sur chaque frame; mesure indépendante sur 161 frames : résidu maximal exactement `0,0 N·m`;
- test biorbd isolé avec moteur contrôlé : appel explicite unique à `massMatrix`, puis reconstruction `M(q)qddot + vitesse + gravité` à 12 décimales;
- suite complète : `101 passed, 3 skipped, 57 subtests passed` en `309,41 s`; les trois skips restent les tests d'intégration biorbd indisponibles dans l'environnement local;
- smoke test Tkinter réel en mode DYNAMIQUE : 201 frames, 15 séries (cinq composantes × trois articulations), résidu inférieur à `1e-10 N·m`;
- inspection visuelle du panneau détaillé après correction du chevauchement de la légende : cinq composantes lisibles sur une bande supérieure et trois panneaux articulaires non tronqués;
- guide étudiant Markdown/Word synchronisé; DOCX de sept pages rendu sur format Letter et chaque page inspectée visuellement sans chevauchement, troncature ni table déformée.

Validation fonctionnelle F30–F35 confirmée par l'enseignant le 2026-08-11; démarrage autorisé de F36–F39.

## 20. Implémentation de la tranche P2 — F36 à F39

Implémentation contrôlée le 2026-08-11 :

- les six paramètres `C1…C6` des hommes actifs de 18–25 ans publiés par Anderson et al. (2007) sont associés aux fléchisseurs plantaires, extenseurs du genou et extenseurs de hanche;
- la relation couple-angle utilise l'angle signé dans la convention Anderson; la flexion de genou Squat_GUI est inversée, les autres angles sont conservés, et le plancher arbitraire de 5 % est supprimé;
- le domaine actif est explicite; la capacité vaut zéro hors du lobe positif, et une utilisation non calculable est signalée sans produire de valeur numérique artificielle;
- la relation couple-vitesse utilise la vitesse réelle en `rad/s`; le régime est dérivé de la puissance articulaire exportée (`tau*omega > 0` concentrique/générateur, `< 0` excentrique/absorbant), et le facteur fixe 1,35 dépendant du nom de phase est supprimé;
- angle et vitesse sont activables séparément dans le GUI, la CLI et les conditions sauvegardées;
- l'export `1.2.0` ajoute facteurs, angle, vitesse, régime, domaine, modèle, source, capacité, `U`, pourcentage et état de dépassement;
- le résumé JSON et le tableau GUI donnent `U max`, articulation limitante, frame/temps, phase et dépassement, avec la formulation « faisabilité mécanique dans les hypothèses du modèle »;
- tests ciblés : `50 passed, 6 subtests passed`;
- suite complète : `104 passed, 3 skipped, 57 subtests passed` en `55,15 s`; les trois skips restent limités à l'intégration biorbd indisponible dans l'environnement local;
- smoke test Tkinter réel : 201 frames, contrôles angle/vitesse actifs, colonne `U max = 43 %` et résumé `genou · 6,50 s · concentrique · non` pour la condition par défaut;
- guide étudiant Word reconstruit puis inspecté visuellement sur ses 7 pages, sans chevauchement, troncature ni tableau cassé.

Validation fonctionnelle F36–F39 confirmée par l'enseignant le 2026-08-11; démarrage autorisé de F40–F41.

## 21. Implémentation de la tranche P2 — F40 à F41

Implémentation contrôlée le 2026-08-11 :

- `longueur seule` conserve les masses et inerties de référence tout en modifiant la géométrie, ce qui isole strictement la sensibilité aux longueurs;
- `morphotype recalibre` multiplie les fractions massiques de référence par les échelles de longueur, les renormalise à la masse corporelle et recalcule `I=m(kL)^2`; la règle est étiquetée comme hypothèse didactique de densité linéique constante;
- le mode est sélectionnable dans le GUI et la CLI, sauvegardé, comparé, intégré à la clé de cache `.bioMod` et exporté avec la règle, les fractions massiques, masses, longueurs et inerties effectives;
- le schéma d'export passe à `1.3.0`;
- une matrice front/back/over-head vérifie trois géométries et trois réponses dynamiques distinctes, des masses/inerties invariantes à morphotype fixé, trois clés et modèles `.bioMod`, les positions exportées et le diff de variable contrôlée;
- la limite de barre ponctuelle est désormais explicite.
- tests ciblés : `69 passed, 3 skipped, 11 subtests passed`;
- suite complète : `110 passed, 3 skipped, 57 subtests passed` en `31,60 s`;
- smoke test Tkinter réel `1480×920` : bascule vers `morphotype recalibre`, 201 frames, masse segmentaire totale `70,0 kg` et mode détecté comme variable contrôlée.
- guide étudiant Word synchronisé, reconstruit puis inspecté visuellement sur ses 7 pages; la pagination du tableau d'évaluation a été corrigée et aucun chevauchement, troncature ni tableau déformé ne subsiste.

Validation fonctionnelle F40–F41 confirmée par l'enseignant le 2026-08-11. L'ensemble des fonctionnalités F01–F41 de l'audit est désormais validé.
