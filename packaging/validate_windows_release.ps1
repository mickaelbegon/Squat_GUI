param(
    [Parameter(Mandatory = $true)]
    [string]$ArchivePath,
    [string]$ExpectedVersion = "0.2.0",
    [switch]$IncludeBiorbd
)

$ErrorActionPreference = "Stop"
$ArchivePath = (Resolve-Path $ArchivePath).Path
$WorkDir = Join-Path $env:TEMP ("squat-gui-windows-recette-" + [guid]::NewGuid())
$ExtractDir = Join-Path $WorkDir "extracted"
$CleanHome = Join-Path $WorkDir "home"

try {
    New-Item -ItemType Directory -Path $ExtractDir, $CleanHome | Out-Null
    Expand-Archive -Path $ArchivePath -DestinationPath $ExtractDir
    $Executable = Join-Path $ExtractDir "Squat GUI\Squat GUI.exe"
    if (-not (Test-Path $Executable -PathType Leaf)) {
        throw "Exécutable absent de l'archive: $Executable"
    }

    $ActualVersion = (Get-Item $Executable).VersionInfo.ProductVersion
    if (-not $ActualVersion.StartsWith($ExpectedVersion)) {
        throw "Version inattendue: $ActualVersion (attendu: $ExpectedVersion)"
    }

    $PreviousHome = $env:USERPROFILE
    $PreviousSmoke = $env:SQUAT_GUI_SMOKE_TEST
    $PreviousBackend = $env:SQUAT_GUI_INCLUDE_OPTIONAL_BACKENDS
    $PreviousNode = $env:SQUAT_GUI_NODE
    $PreviousNodeModules = $env:SQUAT_GUI_NODE_MODULES
    try {
        $env:USERPROFILE = $CleanHome
        $env:SQUAT_GUI_SMOKE_TEST = "1"
        $env:SQUAT_GUI_NODE = $null
        $env:SQUAT_GUI_NODE_MODULES = $null
        $env:SQUAT_GUI_INCLUDE_OPTIONAL_BACKENDS = if ($IncludeBiorbd) { "1" } else { "0" }
        & $Executable
        if ($LASTEXITCODE -ne 0) {
            throw "Le smoke test figé a échoué avec le code $LASTEXITCODE"
        }
    }
    finally {
        $env:USERPROFILE = $PreviousHome
        $env:SQUAT_GUI_SMOKE_TEST = $PreviousSmoke
        $env:SQUAT_GUI_INCLUDE_OPTIONAL_BACKENDS = $PreviousBackend
        $env:SQUAT_GUI_NODE = $PreviousNode
        $env:SQUAT_GUI_NODE_MODULES = $PreviousNodeModules
    }

    Write-Host "Recette Windows réussie: Squat GUI $ActualVersion, profil vierge."
}
finally {
    if (Test-Path $WorkDir) {
        Remove-Item -Recurse -Force $WorkDir
    }
}
