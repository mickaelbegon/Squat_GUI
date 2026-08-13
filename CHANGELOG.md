# Journal des changements

## 0.2.0 — 2026-08-12

### Interface et pédagogie

- Parcours progressif Observation → Cinématique → Dynamique, avec révélation contrôlée.
- Base géométrique d'appui alignée sur toute la longueur du pied; zone fonctionnelle
  redéfinie de la cheville à la tête des métatarsiens.
- Presets temporels, pas physique constant de 0,05 s et curseur synchronisé.
- Échelle de durée harmonisée : descente/montée `0,5/1/2/4 s`; isométrique `0/0,5/1/2 s`, sans option `1,5 s`.
- Le sélecteur temporel affiche désormais chaque preset directement sous la forme `descente | isométrique | montée`.
- Comparaison de conditions, duplication contrôlée et inspecteur des variables modifiées.
- Menu d’affichage unifié : CoM global/segmentaires, coordonnées articulaires au survol,
  orientations, angles, anthropométrie, appuis, forces et capacités.
- Tutoriel intégré et guide étudiant mis à jour jusqu’aux fonctionnalités F01–F41.

### Calculs et traçabilité scientifique

- Deux modes anthropométriques explicites et table effective exportée.
- Backend biorbd vérifié, cache `.bioMod` sans collision entre valeurs CLI distinctes.
- Décomposition canonique du couple, résidu de reconstruction et distinction entre
  base géométrique et zone d’appui fonctionnelle.
- Capacité active angle-vitesse avec amplitude de base et provenance exportées.

### Exports et distribution

- Schéma CSV/Excel 1.4.0 et classeur à 11 onglets.
- Export Excel autonome grâce au fallback `openpyxl` inclus dans le bundle; Artifact
  Tool reste utilisé automatiquement lorsqu'un runtime compatible est disponible.
- Export MP4 à 20 fps dont la durée du conteneur correspond à la trajectoire.
- Bundle PyInstaller enrichi des dépendances vidéo et de son binaire ffmpeg.
- Métadonnées Windows 0.2.0 et protocoles de recette externe reproductibles pour
  macOS et Windows.
- Scénarios publics recalés à 0,05 s et analyse de laboratoire migrée vers les champs
  canoniques.
- Protocole de pilote pédagogique préparé avec tâches et critères d'acceptation.

### Limites connues

- Le bundle Windows reste à construire et smoke-tester sur une machine Windows.
- Le bundle macOS n'est pas encore signé ni notarisé.
