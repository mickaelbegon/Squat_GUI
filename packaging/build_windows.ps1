$ErrorActionPreference = "Stop"

$RootDir = Resolve-Path (Join-Path $PSScriptRoot "..")
Set-Location $RootDir

# Keep all PyInstaller scratch data off the repository/OneDrive tree.  This
# avoids sync-client locks and ensures an unsuccessful build cannot alter dist.
$StagingRoot = Join-Path $env:LOCALAPPDATA "SquatGUI\pyinstaller"
$env:PYINSTALLER_CONFIG_DIR = $StagingRoot

$PythonBin = if ($env:PYTHON_BIN) { $env:PYTHON_BIN } else { "python" }

function Invoke-PythonChecked {
    param(
        [string]$Description,
        [string[]]$Arguments
    )
    & $PythonBin @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "$Description a échoué avec le code $LASTEXITCODE"
    }
}

function Invoke-PyInstallerChecked {
    param([string[]]$Arguments)

    $PyInstallerProcess = Start-Process -FilePath $PythonBin -ArgumentList $Arguments -Wait -PassThru -NoNewWindow
    if ($PyInstallerProcess.ExitCode -ne 0) {
        throw "PyInstaller a échoué avec le code $($PyInstallerProcess.ExitCode)"
    }
}

function Publish-Bundle {
    param(
        [string]$SourceDir,
        [string]$DestinationDir
    )

    $DestinationParent = Split-Path -Parent $DestinationDir
    $IncomingDir = Join-Path $DestinationParent (".Squat GUI-incoming-" + [guid]::NewGuid())
    $PreviousDir = Join-Path $DestinationParent (".Squat GUI-previous-" + [guid]::NewGuid())
    New-Item -ItemType Directory -Force -Path $DestinationParent | Out-Null
    try {
        # Finish copying the already-smoke-tested candidate before it acquires
        # the public name. The final renames are on the destination volume.
        Copy-Item -LiteralPath $SourceDir -Destination $IncomingDir -Recurse -Force
        if (Test-Path -LiteralPath $DestinationDir) {
            Move-Item -LiteralPath $DestinationDir -Destination $PreviousDir
        }
        Move-Item -LiteralPath $IncomingDir -Destination $DestinationDir
    }
    catch {
        if (-not (Test-Path -LiteralPath $DestinationDir) -and (Test-Path -LiteralPath $PreviousDir)) {
            Move-Item -LiteralPath $PreviousDir -Destination $DestinationDir
        }
        throw
    }
    finally {
        if (Test-Path -LiteralPath $IncomingDir) {
            Remove-Item -Recurse -Force -LiteralPath $IncomingDir
        }
        if (Test-Path -LiteralPath $PreviousDir) {
            Remove-Item -Recurse -Force -LiteralPath $PreviousDir
        }
    }
}

function Ensure-PythonModule {
    param(
        [string]$ModuleName,
        [string]$PackageName
    )
    & $PythonBin -c "import $ModuleName" 2>$null
    if ($LASTEXITCODE -ne 0) {
        Write-Host "Module $ModuleName absent; installation de $PackageName..."
        Invoke-PythonChecked -Description "L'installation de $PackageName" -Arguments @(
            "-m", "pip", "install", "--no-build-isolation", $PackageName
        )
        Invoke-PythonChecked -Description "La vérification de $ModuleName" -Arguments @(
            "-c", "import $ModuleName"
        )
    }
}

Ensure-PythonModule -ModuleName "PyInstaller" -PackageName "pyinstaller"
Ensure-PythonModule -ModuleName "PIL" -PackageName "pillow"
Ensure-PythonModule -ModuleName "numpy" -PackageName "numpy"
Ensure-PythonModule -ModuleName "imageio" -PackageName "imageio"
Ensure-PythonModule -ModuleName "imageio_ffmpeg" -PackageName "imageio-ffmpeg"
Ensure-PythonModule -ModuleName "openpyxl" -PackageName "openpyxl"
& $PythonBin -c "import scipy, sys; parts = tuple(int(item) for item in scipy.__version__.split('.')[:2]); sys.exit(0 if (1, 10) <= parts < (1, 17) else 1)" 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Host "Version SciPy absente ou incompatible; installation de scipy>=1.10,<1.17..."
    Invoke-PythonChecked -Description "L'installation de SciPy" -Arguments @(
        "-m", "pip", "install", "--no-build-isolation", "scipy>=1.10,<1.17"
    )
    Invoke-PythonChecked -Description "La vérification de SciPy" -Arguments @(
        "-c", "import scipy, sys; parts = tuple(int(item) for item in scipy.__version__.split('.')[:2]); sys.exit(0 if (1, 10) <= parts < (1, 17) else 1)"
    )
}

$BuildRoot = Join-Path $StagingRoot ("build-" + [guid]::NewGuid())
$BuildWorkDir = Join-Path $BuildRoot "work"
$BuildDistDir = Join-Path $BuildRoot "dist"
New-Item -ItemType Directory -Force -Path $BuildWorkDir, $BuildDistDir | Out-Null
try {
    Invoke-PyInstallerChecked -Arguments @(
        "-m", "PyInstaller", "--clean", "--noconfirm",
        "--workpath", $BuildWorkDir,
        "--distpath", $BuildDistDir,
        "packaging\squat_gui.spec"
    )

    $BundleDir = Join-Path $BuildDistDir "Squat GUI"
    $Executable = Join-Path $BundleDir "Squat GUI.exe"
    $RequiredBundleFiles = @(
        (Join-Path $BundleDir "_internal\assets\raster_segments\pied.png"),
        (Join-Path $BundleDir "_internal\squat_gui\build_workbook.mjs")
    )
    foreach ($RequiredFile in $RequiredBundleFiles) {
        if (-not (Test-Path $RequiredFile -PathType Leaf)) {
            throw "Ressource attendue absente du bundle Windows: $RequiredFile"
        }
    }

    $PreviousSmoke = $env:SQUAT_GUI_SMOKE_TEST
    $PreviousSmokeLog = $env:SQUAT_GUI_SMOKE_LOG
    $SmokeLog = Join-Path $BuildRoot "smoke-error.log"
    try {
        $env:SQUAT_GUI_SMOKE_TEST = "1"
        $env:SQUAT_GUI_SMOKE_LOG = $SmokeLog
        $SmokeProcess = Start-Process -FilePath $Executable -Wait -PassThru -WindowStyle Hidden
        if ($SmokeProcess.ExitCode -ne 0) {
            $SmokeDetails = if (Test-Path -LiteralPath $SmokeLog) {
                Get-Content -LiteralPath $SmokeLog -Raw
            } else {
                "Aucune traceback n'a été produite."
            }
            throw "Le smoke test figé a échoué avec le code $($SmokeProcess.ExitCode).`n$SmokeDetails"
        }
    }
    finally {
        $env:SQUAT_GUI_SMOKE_TEST = $PreviousSmoke
        $env:SQUAT_GUI_SMOKE_LOG = $PreviousSmokeLog
    }

    # Do not touch the published bundle until build validation and the frozen
    # smoke test have both succeeded.
    $PublishedBundleDir = Join-Path $RootDir "dist\Squat GUI"
    Publish-Bundle -SourceDir $BundleDir -DestinationDir $PublishedBundleDir
}
finally {
    if (Test-Path -LiteralPath $BuildRoot) {
        Remove-Item -Recurse -Force -LiteralPath $BuildRoot
    }
}

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
