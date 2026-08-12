# Recette de distribution Squat GUI 0.2.0

Ces contrôles s'exécutent sur une machine différente de celle du build. Ils ne
remplacent pas la recette manuelle par double-clic, mais vérifient l'intégrité du
bundle et les fonctions qui échouent le plus souvent après packaging.

## Second Mac Apple Silicon

1. Copier le ZIP candidat et le fichier `SHA256SUMS.txt` sur le Mac de recette.
2. Vérifier le checksum avec `shasum -a 256 -c SHA256SUMS.txt`.
3. Depuis une copie du dépôt contenant le validateur, lancer :

   ```bash
   bash packaging/validate_macos_release.sh /chemin/Squat_GUI-0.2.0-macOS-arm64.zip
   ```

4. Décompresser à nouveau le ZIP avec Finder, puis ouvrir l'application par
   double-clic. Si Gatekeeper la bloque, noter le message exact, puis essayer
   clic droit → `Ouvrir` → `Ouvrir`.
5. Exécuter la recette manuelle commune ci-dessous.

Le validateur exige la version 0.2.0, l'architecture arm64 et une signature interne
cohérente. Il lance le bundle avec un profil vierge, sans Node.js, puis vérifie Excel,
MP4, assets et biorbd.

## Windows 10/11 64 bits

Construire sur Windows dans l'environnement canonique :

```powershell
conda activate squat-gui
$env:SQUAT_GUI_INCLUDE_OPTIONAL_BACKENDS = "1"
powershell -ExecutionPolicy Bypass -File packaging\build_windows.ps1
Compress-Archive -Path "dist\Squat GUI" -DestinationPath "Squat_GUI-0.2.0-Windows-x64.zip"
Get-FileHash "Squat_GUI-0.2.0-Windows-x64.zip" -Algorithm SHA256
```

Copier ensuite le ZIP sur une seconde machine Windows et lancer :

```powershell
powershell -ExecutionPolicy Bypass -File packaging\validate_windows_release.ps1 `
  -ArchivePath "C:\chemin\Squat_GUI-0.2.0-Windows-x64.zip" -IncludeBiorbd
```

Sans biorbd dans le build, omettre `-IncludeBiorbd`. Le validateur contrôle les
métadonnées de version, extrait dans un dossier temporaire, utilise un profil vierge
et teste Excel/MP4 sans Node.js.

## Recette manuelle commune

- Ouvrir l'application par double-clic, sans terminal visible.
- Vérifier les images des segments et le tutoriel Observation → Cinématique → Dynamique.
- Changer sujet, prise de barre, wedge, charge et durées.
- Déplacer la posture basse puis parcourir le mouvement avec le curseur.
- Activer les coordonnées articulaires au survol, CoM, appuis et forces.
- Ajouter une condition, la dupliquer, modifier un paramètre et comparer les deux.
- Sauvegarder puis recharger les conditions JSON.
- Exporter un Excel et vérifier ses 11 onglets.
- Exporter un MP4 et le lire dans le lecteur système.
- Fermer puis rouvrir l'application.

La recette est acceptée si aucun crash ou blocage n'apparaît, si les deux exports
s'ouvrent, si la comparaison indique la variable modifiée et si le backend annoncé
correspond au build attendu. Conserver OS, architecture, résultat, message d'erreur
exact et captures utiles dans le rapport de recette.
