# PR (brouillon) — Refactorisation de maintenabilité du GUI et du calcul

> **Statut : brouillon — ne pas fusionner.** Le build Windows de release reste
> bloqué par une incompatibilité PyInstaller/Tcl dans l'environnement Conda
> `squat-gui`, et non par l'absence de `tkinter`. Les améliorations sûres du
> build sont en cours de nettoyage ; une reconstruction dans un Python officiel
> ou un environnement Conda-forge propre est nécessaire avant une release. La
> compatibilité historique de `dynamics.py` est désormais corrigée et validée.
> La PR ne deviendra prête à relire qu'après build, smoke test et recette
> Windows réussis, ainsi que les validations GUI et biorbd ci-dessous.

## Titre proposé

`Refactoriser le GUI, le calcul et les exports sans modifier les façades publiques`

## Corps proposé

## Résumé

Cette PR réorganise l'application pour isoler les responsabilités du GUI, de
la CLI, du rendu, des calculs, des exports et de la persistance, sans changer
les points d'entrée publics ni les hypothèses biomécaniques.

Les façades `app.py`, `cli.py`, `dynamics.py` et `kinematics.py` restent les
points d'accès compatibles. Les implémentations sont désormais réparties dans
des modules spécialisés et testables (contrôleurs GUI, scène/graphes,
cinématique, dynamique inverse, optimisation de trajectoire de barre, exports
et workflow de session).

À la date de l'audit, `git diff main...HEAD` compte exactement **83 fichiers**,
**12 938 ajouts** et **7 726 suppressions** ; la branche est à **27 commits**
devant `main`.

## Points vérifiés automatiquement

Dans l'environnement Conda `squat-gui` :

```powershell
python -m ruff check src tests packaging
python -m compileall -q src tests packaging\squat_gui_launcher.py
git diff --check main...HEAD
python -m pytest -q
```

La dernière exécution documentée a réussi : `247 passed`, `23 skipped` et
`124 subtests passed`. Ces résultats doivent être rejoués après les correctifs
en cours. Les tests couvrent notamment les frontières
d'architecture, les délégations GUI/CLI, les contrôleurs, les exports, le
packaging, ainsi que les régressions numériques de cinématique, dynamique et
SLSQP.

## Portée et précautions

- Aucune modification intentionnelle des hypothèses biomécaniques ni de la
  version distribuée (`0.2.0`).
- La validation automatisée ne remplace pas la recette graphique Tkinter sous
  Windows ni l'essai d'un bundle PyInstaller sur une seconde machine.
- Cette recette GUI n'a pas encore été effectuée : le build de release est
  bloqué par l'incompatibilité PyInstaller/Tcl de Conda `squat-gui`, non par
  l'absence de `tkinter`. Les améliorations sûres du build sont en cours de
  nettoyage. La release exige une reconstruction dans un Python officiel ou un
  environnement Conda-forge propre; le smoke doit y être exécuté et son échec
  propagé par `build_windows.ps1`.
- La validation du backend optionnel biorbd, de même que celle du fallback
  analytique dans le bundle, n'a pas encore été effectuée.
- La compatibilité historique de la façade `dynamics.py` est corrigée et
  validée.
- Les itérations SLSQP peuvent varier selon SciPy/BLAS ; les références
  valident les résultats physiques avec des tolérances définies.

## Checklist de validation — Aurélie

- [ ] Préparer un Python officiel ou un environnement Conda-forge propre,
      reconstruire le bundle, puis vérifier l'exécution du smoke et la
      propagation de son échec par `build_windows.ps1`.
- [ ] Relire le diff, en priorité les façades `app.py`, `cli.py`,
      `dynamics.py`, `kinematics.py` et les contrats d'export.
- [ ] Dans un arbre propre, exécuter les quatre commandes de contrôle
      ci-dessus.
- [ ] Sous Windows/Tk, effectuer la checklist GUI de
      [DEVELOPMENT.md](DEVELOPMENT.md#checklist-manuelle-gui-windows) aux
      tailles 1480x920 et 1024x700 : pose et déplacement par glisser-déposer,
      dialogue d'angles, animation/survol, graphes, conditions, sauvegarde et
      rechargement JSON, exports CSV et XLSX.
- [ ] Vérifier dans le classeur XLSX `Synthèse`, `Données combinées`, une
      feuille par simulation et `Définitions`, puis confirmer que la
      comparaison de conditions indique la variable modifiée.
- [ ] Construire le bundle Windows depuis le Python officiel ou
      l'environnement Conda-forge propre préparé ci-dessus :

      ```powershell
      $env:SQUAT_GUI_INCLUDE_OPTIONAL_BACKENDS = "1"
      powershell -ExecutionPolicy Bypass -File packaging\build_windows.ps1
      Compress-Archive -Path "dist\Squat GUI" -DestinationPath "Squat_GUI-0.2.0-Windows-x64.zip"
      ```

- [ ] Tester ce ZIP sur une seconde machine Windows avec :

      ```powershell
      powershell -ExecutionPolicy Bypass -File packaging\validate_windows_release.ps1 `
        -ArchivePath "C:\chemin\Squat_GUI-0.2.0-Windows-x64.zip" -IncludeBiorbd
      ```

      Pour un bundle analytique, omettre `-IncludeBiorbd` et définir
      `SQUAT_GUI_INCLUDE_OPTIONAL_BACKENDS` à `"0"` avant le build.
- [ ] Consigner l'OS, les versions Python/SciPy/BLAS, le résultat, les erreurs
      éventuelles et les captures utiles avant l'accord de fusion.

## Procédure de repli après fusion

1. Isoler immédiatement la régression et conserver le rapport de recette,
   les captures et les fichiers d'export concernés.
2. Créer une branche de correctif depuis `main` pour diagnostiquer et corriger
   le problème.
3. Si un retrait est nécessaire, inverser uniquement le commit de merge :

   ```powershell
   git revert -m 1 <commit-de-merge>
   ```

4. Ne pas réécrire `main` et ne pas utiliser `git reset --hard`. Rejouer les
   contrôles automatisés et la recette Windows sur le commit de repli, puis
   préparer le correctif pour une réintégration séparée.

Voir aussi [REFACTOR_REVIEW.md](REFACTOR_REVIEW.md) pour le détail des
vérifications et de la procédure de fusion.
