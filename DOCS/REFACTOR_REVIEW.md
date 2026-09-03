# Revue — `codex/maintainability-refactor`

## Décision attendue

Cette branche est une refactorisation de maintenabilité : elle préserve les
points d'entrée et les résultats métier tout en séparant les responsabilités
du GUI, de la CLI, du calcul, du rendu, des exports et de la persistance. Elle
ne doit être fusionnée qu'après la recette Windows ci-dessous ; elle ne change
ni les hypothèses biomécaniques, ni la version distribuée (`0.2.0`).

Écart vérifié le 3 septembre 2026 : `origin/main` est ancêtre de la branche ;
la branche contient 28 commits supplémentaires et aucun commit de `main` à
réintégrer. Le diff représente 87 fichiers (13 546 ajouts, 7 615 suppressions),
principalement dans `src/squat_gui/` et `tests/`.

## Architecture résultante

Les façades restent volontairement stables : `app.py` pour Tkinter, `cli.py`
pour la compatibilité CLI, et `dynamics.py`/`kinematics.py` pour les API de
calcul existantes. Les responsabilités ont été extraites dans des modules
testables :

- session et conditions : `condition_store`, `session_persistence`,
  `session_workflow`, `simulation_service` ;
- GUI : contrôleurs d'interaction, constructeur de layout, édition de pose et
  actions de conditions ;
- rendu : modèle de scène, pose, animation, overlays, canvas et primitives de
  graphes ;
- calcul : couches géométriques de cinématique, noyau de dynamique inverse,
  contraintes/problème/solveur de trajectoire de barre ;
- sorties : contrats/tableaux d'export, modèle de classeur et writers XLSX ;
- CLI : parser, conversions et handlers séparés.

`tests/test_architecture_boundaries.py` verrouille les dépendances descendantes
entre ces couches. Les références numériques couvrent la cinématique et la
dynamique analytiques de façon serrée, ainsi que SLSQP avec des tolérances
compatibles avec les variantes SciPy/BLAS.

## Vérifications automatisées

Exécutées dans l'environnement Conda `squat-gui` (Python 3.11.15) :

```powershell
python -m ruff check src tests packaging
python -m compileall -q src tests packaging\squat_gui_launcher.py
git diff --check origin/main...HEAD
```

Résultat : succès, sans erreur signalée. La suite complète a également été
exécutée :

```powershell
python -m pytest -q  # 247 passed, 23 skipped, 124 subtests passed (118,28 s)
```

Les tests ajoutés couvrent notamment les frontières d'architecture, les
délégations GUI/CLI, les contrôleurs de pose/conditions/scène/graphes, les
exports, le packaging, et les régressions numériques (`tests/test_numerical_regression.py`).

## Limites connues de validation

- Tkinter : les tests sans affichage ne valident pas les dimensions de widgets,
  polices, scroll, survol ni les gestes utilisateur. Une session graphique
  Windows reste obligatoire.
- biorbd : optionnel et natif. Son absence doit conserver le fallback
  analytique ; sa présence dans un bundle doit être validée dans le bundle, pas
  seulement dans l'environnement de développement.
- Packaging : les tests de contrat contrôlent scripts, imports et ressources,
  mais ne remplacent ni PyInstaller ni l'essai sur une seconde machine.
- SLSQP : les résultats sont validés au niveau biomécanique avec tolérances
  assumées ; ne pas exiger l'identité exacte des itérations entre versions de
  SciPy/BLAS.

## Checklist de revue d'Aurélie

- [ ] Lire le diff par commit, en priorité les façades `app.py`, `cli.py`,
      `dynamics.py`, `kinematics.py` et les nouveaux contrats d'export.
- [ ] Vérifier que GUI et CLI gardent leurs commandes, exports et fichiers JSON
      compatibles avec le comportement attendu.
- [ ] Lancer les quatre contrôles de la section précédente dans un arbre propre.
- [ ] Sous Windows/Tk, suivre la
      [checklist GUI](DEVELOPMENT.md#checklist-manuelle-gui-windows) : tailles
      1480×920 et 1024×700, pose/drag/dialogue, animation/survol, graphes,
      conditions, JSON, CSV et XLSX.
- [ ] Construire et tester un ZIP Windows sur une seconde machine selon la
      [recette de distribution](../packaging/RECETTE_DISTRIBUTION.md), avec et
      sans `-IncludeBiorbd` selon le bundle cible.
- [ ] Si biorbd est inclus, confirmer le backend réellement annoncé et les
      fonctions optionnelles dans le bundle extrait.
- [ ] Consigner OS, version Python/SciPy/BLAS, résultat et éventuelles captures
      avant l'accord de fusion.

## Procédure de fusion et de repli

1. Actualiser les références et vérifier que `origin/main` est toujours ancêtre
   de `origin/codex/maintainability-refactor` :

   ```powershell
   git fetch origin
   git log --oneline origin/codex/maintainability-refactor..origin/main
   git diff --check origin/main...origin/codex/maintainability-refactor
   ```

   La première commande de log doit rester vide. Si elle ne l'est plus,
   réactualiser la branche et refaire les contrôles avant toute fusion.

2. Après les validations, intégrer via la revue habituelle (merge commit ou
   fast-forward selon la politique du dépôt), puis relancer au minimum Ruff,
   pytest et la recette Windows sur le commit intégré.

3. En cas de régression après fusion, créer immédiatement une branche de
   correctif depuis `main`; si un retrait est nécessaire, inverser uniquement le
   commit de merge avec `git revert -m 1 <commit-de-merge>`. Ne pas réécrire
   `main` ni utiliser `reset --hard`. Conserver le rapport de recette et les
   exports fautifs pour corriger puis réintégrer.

Cette note n'ouvre pas de pull request, ne crée aucun tag et ne modifie pas la
configuration de livraison.
