# Prompt Codex — construire et valider le ZIP Windows

Copier-coller tout le bloc ci-dessous dans une nouvelle tâche Codex ouverte sur le PC
Windows qui servira au build.

---

Tu travailles sur un PC Windows 10 ou 11 64 bits. Ton objectif est de produire et
valider la release candidate Windows de Squat GUI 0.2.0 depuis la branche GitHub
`codex/release-0.2.0-rc` du dépôt
`https://github.com/mickaelbegon/Squat_GUI.git`.

Communique en français. Avance de manière autonome jusqu'à un résultat vérifié. Ne
fusionne pas la PR, ne modifie pas `main`, ne crée pas de tag et ne publie pas de
release. Ne commit ni ne push aucune modification sans me demander explicitement
l'autorisation. Si le build révèle un défaut de code ou de packaging, diagnostique-le,
conserve les logs utiles et propose la correction minimale sans l'appliquer tant que je
ne l'ai pas autorisée.

## 1. Préparer le dépôt et l'environnement

1. Localise une copie existante du dépôt ou clone-la si elle n'existe pas.
2. Lis complètement les fichiers `AGENTS.md` applicables avant d'agir.
3. Vérifie le remote canonique, l'état Git et les éventuels changements locaux.
4. Récupère les branches distantes et place-toi exactement sur
   `codex/release-0.2.0-rc`.
5. Vérifie que la branche contient au minimum les fichiers suivants :
   - `packaging/build_windows.ps1`;
   - `packaging/validate_windows_release.ps1`;
   - `packaging/windows_version_info.txt`;
   - `packaging/squat_gui.spec`.
6. Utilise de préférence un environnement conda propre nommé `squat-gui` avec Python
   3.11. Si cet environnement existe déjà, vérifie sa version et réutilise-le seulement
   s'il est cohérent.
7. Installe le projet et les dépendances nécessaires au build :

   ```powershell
   python -m pip install --upgrade pip
   python -m pip install -e ".[dev,video,packaging]"
   ```

8. Exécute d'abord la suite de tests :

   ```powershell
   python -m pytest -q
   ```

Rapporte le nombre de tests réussis, ignorés et échoués. Les tests biorbd peuvent être
ignorés si biorbd n'est pas installé; tout autre échec doit être diagnostiqué avant le
build.

## 2. Choisir et documenter le backend du bundle

Le build préféré inclut biorbd. Vérifie d'abord :

```powershell
python -c "import biorbd; print(biorbd.__version__)"
```

- Si cet import réussit, construis le bundle complet avec
  `SQUAT_GUI_INCLUDE_OPTIONAL_BACKENDS=1`.
- Si l'import échoue, n'installe pas au hasard une variante incompatible. Construis le
  bundle analytique sans biorbd et indique très clairement cette limite dans le rapport
  final et dans le nom du ZIP.

## 3. Construire le bundle

Depuis la racine du dépôt, dans PowerShell :

```powershell
$env:PYTHON_BIN = (Get-Command python).Source
$env:SQUAT_GUI_INCLUDE_OPTIONAL_BACKENDS = "1"  # seulement si biorbd fonctionne
powershell -ExecutionPolicy Bypass -File packaging\build_windows.ps1
```

Pour le build analytique, supprime plutôt la variable avant d'appeler le script :

```powershell
Remove-Item Env:SQUAT_GUI_INCLUDE_OPTIONAL_BACKENDS -ErrorAction SilentlyContinue
powershell -ExecutionPolicy Bypass -File packaging\build_windows.ps1
```

Le script doit terminer sans erreur et son smoke test figé doit réussir. Vérifie ensuite :

- présence de `dist\Squat GUI\Squat GUI.exe`;
- architecture 64 bits;
- `ProductVersion` commençant par `0.2.0`;
- absence de console visible lors d'un lancement normal;
- présence des assets et bibliothèques dans le dossier `dist\Squat GUI`.

Affiche les métadonnées de version avec :

```powershell
(Get-Item "dist\Squat GUI\Squat GUI.exe").VersionInfo |
  Select-Object ProductName, ProductVersion, FileVersion
```

## 4. Créer le ZIP candidat

Crée un dossier de sortie ignoré par Git :

```powershell
$ReleaseDir = "outputs\release_candidate_windows_0.2.0"
New-Item -ItemType Directory -Force -Path $ReleaseDir | Out-Null
```

Nom du ZIP :

- avec biorbd : `Squat_GUI-0.2.0-Windows-x64.zip`;
- sans biorbd : `Squat_GUI-0.2.0-Windows-x64-analytical.zip`.

Compresse le dossier complet, jamais le `.exe` seul :

```powershell
$ZipPath = Join-Path $ReleaseDir "Squat_GUI-0.2.0-Windows-x64.zip"
Compress-Archive -Path "dist\Squat GUI" -DestinationPath $ZipPath -Force
```

Calcule ensuite le SHA-256 :

```powershell
$Hash = Get-FileHash $ZipPath -Algorithm SHA256
$Hash
"$($Hash.Hash.ToLower())  $([System.IO.Path]::GetFileName($ZipPath))" |
  Set-Content -Encoding ascii (Join-Path $ReleaseDir "SHA256SUMS.txt")
```

Rapporte la taille du ZIP et son SHA-256.

## 5. Valider exactement le ZIP livré

Utilise le validateur fourni, qui extrait l'archive dans un dossier temporaire, emploie
un profil utilisateur vierge, masque tout runtime Node.js et teste Excel/MP4 :

```powershell
powershell -ExecutionPolicy Bypass -File packaging\validate_windows_release.ps1 `
  -ArchivePath $ZipPath -ExpectedVersion "0.2.0" -IncludeBiorbd
```

Omet `-IncludeBiorbd` pour le build analytique. Le validateur doit afficher
`Recette Windows réussie` et sortir avec le code 0.

Vérifie aussi l'intégrité indépendamment :

```powershell
$Expected = (Get-Content (Join-Path $ReleaseDir "SHA256SUMS.txt")).Split()[0]
$Actual = (Get-FileHash $ZipPath -Algorithm SHA256).Hash.ToLower()
if ($Actual -ne $Expected) { throw "Checksum SHA-256 invalide" }
```

## 6. Effectuer une courte recette manuelle

Décompresse le ZIP avec l'Explorateur Windows dans un nouveau dossier, puis :

1. double-clique sur `Squat GUI.exe`;
2. vérifie les images des segments et le tutoriel Observation → Cinématique → Dynamique;
3. change sujet, prise de barre, wedge, charge et durée;
4. ajoute une condition, duplique-la, modifie un paramètre et compare;
5. sauvegarde puis recharge un JSON de conditions;
6. exporte un Excel, ouvre-le et confirme `Synthèse`, `Données combinées`, une
   feuille par simulation et `Définitions`;
7. exporte un MP4 et lis-le dans le lecteur Windows;
8. ferme puis rouvre l'application.

Ne considère pas la recette comme réussie si un export ne s'ouvre pas, si une image est
absente, si l'application affiche une console parasite, si Windows Defender bloque le
fichier sans que le message exact soit relevé, ou si le backend annoncé ne correspond
pas au build prévu.

## 7. Livrables et rapport final

À la fin, donne un rapport concis contenant :

- version exacte de Windows et architecture;
- version de Python et environnement utilisé;
- commit Git testé (`git rev-parse HEAD`);
- résultat de `git status --short`;
- résultat des tests Python;
- backend inclus : `biorbd` ou `analytical`;
- résultat du smoke test du build;
- résultat du validateur d'archive;
- résultat de chaque point de recette manuelle;
- chemin absolu du ZIP;
- taille du ZIP;
- SHA-256;
- avertissements Windows Defender/SmartScreen éventuels, avec le texte exact;
- tout risque ou contrôle non exécuté.

Le résultat attendu est un ZIP autonome dont le dossier interne `Squat GUI` contient
l'exécutable et toutes ses dépendances. N'envoie pas le `.exe` seul. Ne marque pas la
recette comme réussie sur la seule base de la construction PyInstaller.

---
