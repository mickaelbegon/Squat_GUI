$ErrorActionPreference = "Stop"

$RootDir = Resolve-Path (Join-Path $PSScriptRoot "..")
Set-Location $RootDir

if (-not $env:PYINSTALLER_CONFIG_DIR) {
    $env:PYINSTALLER_CONFIG_DIR = Join-Path $env:TEMP "squat_gui_pyinstaller"
}

$PythonBin = if ($env:PYTHON_BIN) { $env:PYTHON_BIN } else { "python" }

function Ensure-PythonModule {
    param(
        [string]$ModuleName,
        [string]$PackageName
    )
    & $PythonBin -c "import $ModuleName" 2>$null
    if ($LASTEXITCODE -ne 0) {
        Write-Host "Module $ModuleName absent; installation de $PackageName..."
        & $PythonBin -m pip install --no-build-isolation $PackageName
    }
}

Ensure-PythonModule -ModuleName "PyInstaller" -PackageName "pyinstaller"
Ensure-PythonModule -ModuleName "PIL" -PackageName "pillow"

& $PythonBin -m PyInstaller --clean --noconfirm packaging\squat_gui.spec
$env:SQUAT_GUI_SMOKE_TEST = "1"
& "dist\Squat GUI\Squat GUI.exe"
$env:SQUAT_GUI_SMOKE_TEST = $null

Write-Host ""
Write-Host "Build termine."
Write-Host ""
Write-Host "Sortie principale:"
Write-Host "- dist\Squat GUI\Squat GUI.exe"
Write-Host ""
Write-Host "Pour distribuer aux etudiants sur Windows:"
Write-Host "1. compresser le dossier dist\Squat GUI en .zip;"
Write-Host "2. envoyer le .zip;"
Write-Host "3. l'etudiant dezippe le dossier;"
Write-Host "4. il double-clique sur Squat GUI.exe."
Write-Host ""
Write-Host "Important: garder le .exe avec tout le contenu du dossier dist\Squat GUI."
