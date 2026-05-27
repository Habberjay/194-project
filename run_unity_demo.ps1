param(
    [string]$Preset = "site_line_1",
    [double]$SampleFps = 5,
    [int]$MaxFrames = 1,
    [string]$Video = "",
    [switch]$SkipLineSelector,
    [switch]$NoClean,
    [switch]$NoCopyToUnity
)

$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$PythonDir = Join-Path $Root "python"
$PythonExe = Join-Path $PythonDir ".venv\Scripts\python.exe"
$Checkpoint = Join-Path $PythonDir "checkpoints\depth_anything_v2_vits.pth"
$UnityExportDir = Join-Path $PythonDir "output\unity_export"
$UnityTexturesDir = Join-Path $Root "unity\Assets\Textures"
$UnityDepthDir = Join-Path $UnityTexturesDir "DepthMaps"
$UnityBlueprintDir = Join-Path $UnityTexturesDir "Blueprints"

function Run-Step {
    param(
        [string]$Label,
        [string]$FilePath,
        [string[]]$Arguments
    )

    Write-Host ""
    Write-Host "== $Label =="
    & $FilePath @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "$Label failed with exit code $LASTEXITCODE."
    }
}

try {
    Set-Location $PythonDir

    if (!(Test-Path $PythonExe)) {
        Run-Step "Create Python venv" "powershell" @("-ExecutionPolicy", "Bypass", "-File", ".\setup_venv.ps1")
        if (!(Test-Path $PythonExe)) {
            throw "Python venv setup finished, but $PythonExe was not found."
        }
    }

    if (!(Test-Path $Checkpoint)) {
        Run-Step "Download Depth Anything checkpoint" $PythonExe @("scripts\download_checkpoint.py")
    }

    if (!$NoClean) {
        Run-Step "Clean generated output" $PythonExe @("scripts\clean_outputs.py", "--yes")
    }

    $extractArgs = @("scripts\extract_frames.py", "--sample-fps", "$SampleFps", "--max-frames", "$MaxFrames", "--clear")
    if ($Video.Trim().Length -gt 0) {
        $videoPath = $Video.Trim()
        if (![System.IO.Path]::IsPathRooted($videoPath)) {
            $rootRelativeVideo = Join-Path $Root $videoPath
            $pythonRelativeVideo = Join-Path $PythonDir $videoPath
            if (Test-Path $rootRelativeVideo) {
                $videoPath = (Resolve-Path $rootRelativeVideo).Path
            }
            elseif (Test-Path $pythonRelativeVideo) {
                $videoPath = (Resolve-Path $pythonRelativeVideo).Path
            }
        }
        $extractArgs += @("--video", $videoPath)
    }
    Run-Step "Extract frames" $PythonExe $extractArgs

    Run-Step "Generate depth maps" $PythonExe @("scripts\run_depth.py", "--max-images", "$MaxFrames", "--clear")

    if (!$SkipLineSelector) {
        Write-Host ""
        Write-Host "== Select line =="
        Write-Host "Click point A, click point B, press S to save, then press Q or Esc."
        & $PythonExe "-B" "scripts\line_selector.py" "--preset" $Preset
        if ($LASTEXITCODE -ne 0) {
            throw "Line selector failed with exit code $LASTEXITCODE."
        }
    }
    else {
        Write-Host ""
        Write-Host "== Select line =="
        Write-Host "Skipping line selector. Reusing preset '$Preset'."
    }

    Run-Step "Export Unity bundle" $PythonExe @("-B", "scripts\export_unity_demo.py", "--preset", $Preset, "--clear")

    if (!$NoCopyToUnity) {
        Write-Host ""
        Write-Host "== Copy Unity export assets =="
        New-Item -ItemType Directory -Force -Path $UnityDepthDir | Out-Null
        New-Item -ItemType Directory -Force -Path $UnityBlueprintDir | Out-Null

        Copy-Item -Force (Join-Path $UnityExportDir "depth.png") (Join-Path $UnityDepthDir "depth.png")
        Copy-Item -Force (Join-Path $UnityExportDir "frame.png") (Join-Path $UnityBlueprintDir "frame.png")
        Copy-Item -Force (Join-Path $UnityExportDir "line_metadata.json") (Join-Path $UnityTexturesDir "line_metadata.json")

        Write-Host "Copied Unity assets into unity\Assets\Textures."
    }

    Write-Host ""
    Write-Host "DONE."
    Write-Host "Unity export bundle:"
    Write-Host "  python\output\unity_export\frame.png"
    Write-Host "  python\output\unity_export\depth.png"
    Write-Host "  python\output\unity_export\line_metadata.json"
    if (!$NoCopyToUnity) {
        Write-Host "Unity-ready copies:"
        Write-Host "  unity\Assets\Textures\Blueprints\frame.png"
        Write-Host "  unity\Assets\Textures\DepthMaps\depth.png"
        Write-Host "  unity\Assets\Textures\line_metadata.json"
    }
    Write-Host ""
    Write-Host "In Unity: assign depth.png, frame.png, and line_metadata.json, then use Load Metadata and Rebuild Surface Line."
}
finally {
    Set-Location $Root
}
