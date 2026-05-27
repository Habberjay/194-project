param()

$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$PythonDir = Join-Path $Root "python"
$PythonExe = Join-Path $PythonDir ".venv\Scripts\python.exe"
$Checkpoint = Join-Path $PythonDir "checkpoints\depth_anything_v2_vits.pth"
$InputVideosDir = Join-Path $PythonDir "input_videos"
$UnityExportDir = Join-Path $PythonDir "output\unity_export"
$UnityTexturesDir = Join-Path $Root "unity\Assets\Textures"

$VideoExtensions = @("*.mp4", "*.mov", "*.avi", "*.mkv", "*.webm", "*.m4v")
$CriticalMissing = $false

function Write-Check {
    param(
        [string]$State,
        [string]$Label,
        [string]$Detail = ""
    )

    if ($Detail.Trim().Length -gt 0) {
        Write-Host "[$State] $Label - $Detail"
    }
    else {
        Write-Host "[$State] $Label"
    }
}

Write-Host ""
Write-Host "Project setup check"
Write-Host "Root: $Root"
Write-Host ""

if (Test-Path $PythonExe) {
    Write-Check "OK" "Python virtual environment" $PythonExe
}
else {
    Write-Check "WARN" "Python virtual environment missing" "run_unity_demo.ps1 can create it, or run python\setup_venv.ps1"
}

if (Test-Path $Checkpoint) {
    Write-Check "OK" "Depth Anything checkpoint" $Checkpoint
}
else {
    Write-Check "WARN" "Depth Anything checkpoint missing" "run_unity_demo.ps1 can download it, or run python\scripts\download_checkpoint.py"
}

$InputVideos = @()
if (Test-Path $InputVideosDir) {
    foreach ($Pattern in $VideoExtensions) {
        $InputVideos += Get-ChildItem -Path $InputVideosDir -Recurse -File -Include $Pattern -ErrorAction SilentlyContinue
    }
}

if ($InputVideos.Count -gt 0) {
    Write-Check "OK" "Input videos found" "$($InputVideos.Count) video file(s)"
}
else {
    Write-Check "MISSING" "No input videos found" "put a short site video in python\input_videos\"
    $CriticalMissing = $true
}

$Dotnet = Get-Command dotnet -ErrorAction SilentlyContinue
if ($null -eq $Dotnet) {
    Write-Check "WARN" ".NET SDK" "dotnet was not found; install the x64 .NET SDK for VS Code C# support"
}
else {
    $Sdks = @(& $Dotnet.Source --list-sdks 2>$null)
    if ($Sdks.Count -gt 0 -and ($Sdks -join "").Trim().Length -gt 0) {
        Write-Check "OK" ".NET SDK" ($Sdks -join "; ")
    }
    else {
        Write-Check "WARN" ".NET SDK missing" "install the x64 .NET SDK; runtimes alone are not enough for C# Dev Kit"
    }
}

$UnityExportFiles = @(
    (Join-Path $UnityExportDir "frame.png"),
    (Join-Path $UnityExportDir "depth.png"),
    (Join-Path $UnityExportDir "line_metadata.json")
)
$UnityExportReady = ($UnityExportFiles | Where-Object { Test-Path $_ }).Count -eq $UnityExportFiles.Count
if ($UnityExportReady) {
    Write-Check "OK" "Python Unity export assets" "python\output\unity_export\"
}
else {
    Write-Check "INFO" "Python Unity export assets not ready" "run .\run_unity_demo.ps1 to generate them"
}

$UnityCopyFiles = @(
    (Join-Path $UnityTexturesDir "Blueprints\frame.png"),
    (Join-Path $UnityTexturesDir "DepthMaps\depth.png"),
    (Join-Path $UnityTexturesDir "line_metadata.json")
)
$UnityCopiesReady = ($UnityCopyFiles | Where-Object { Test-Path $_ }).Count -eq $UnityCopyFiles.Count
if ($UnityCopiesReady) {
    Write-Check "OK" "Unity texture copies" "unity\Assets\Textures\"
}
else {
    Write-Check "INFO" "Unity texture copies not ready" "run .\run_unity_demo.ps1 without -NoCopyToUnity"
}

Write-Host ""
if ($CriticalMissing) {
    Write-Host "Setup check finished with missing required input."
    exit 1
}

Write-Host "Setup check finished."
exit 0
