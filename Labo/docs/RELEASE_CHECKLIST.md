# Checklist de release Squat GUI 0.2.0

## Qualité logicielle

- [x] CI GitHub Actions ajoutée pour Python 3.11, installation propre et suite complète.
- [x] Tests ciblés des corrections d’audit.
- [x] Suite complète avec le backend biorbd réel.
- [x] Smoke test GUI natif : navigation, curseur, JSON, condition et export Excel.
- [x] Export MP4 réel : cadence, nombre de frames et durée du conteneur.
- [x] Contrôle de cohérence des versions Python/PyInstaller.

## Qualité scientifique

- [x] Unités, conventions, masses et pas temporel contrôlés.
- [x] 18 scénarios publics exécutés avec biorbd et Δt=0,05 s.
- [x] Aucune valeur non finie dans le lot de recette.
- [x] Résidus de forces et de reconstruction des couples au niveau de la précision machine.
- [x] Provenance des capacités et anthropométrie effective exportées.

## Livrables pédagogiques

- [x] Analyse du lot fondée sur les champs canoniques du schéma 1.4.0.
- [x] Guide Markdown mis à jour.
- [x] Guide DOCX régénéré et inspecté sur ses 7 pages.
- [x] Matériel enseignant local exclu du périmètre de distribution publique.

## Distribution

- [x] Protocoles reproductibles ajoutés pour la recette externe macOS et Windows.
- [x] Bundle macOS arm64 0.2.0 construit (222 Mo) et smoke-testé sur la machine de release.
- [x] ZIP macOS arm64 candidat créé (92 Mo), contrôlé par SHA-256, extrait puis smoke-testé avec un profil utilisateur vierge et sans Node.js.
- [ ] ZIP testé sur une seconde machine Apple Silicon représentative d’un poste étudiant.
- [ ] Bundle Windows construit et smoke-testé sur une machine Windows.
- [x] Export MP4 encodé et relu depuis l’application figée.
- [x] Export Excel rendu autonome dans l’application figée.
- [ ] Application signée/notarisée ou procédure d’ouverture non signée acceptée.

## Pilote pédagogique

- [x] Protocole pilote, tâches et critères d’acceptation préparés.
- [ ] Pilote réalisé avec 3 à 5 étudiants représentatifs.
- [ ] Observations classées P0–P3 et décisions reportées vers 0.2.1.

## Git et publication

- [x] Diff final relu et `git diff --check` sans erreur.
- [ ] Commit ciblé autorisé par le propriétaire du dépôt.
- [ ] Tag, push et publication autorisés explicitement.
