$ErrorActionPreference = "Stop"

$ProjectDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ProjectDir

$PythonCmd = $null

if (Get-Command py -ErrorAction SilentlyContinue) {
    $Py313 = py -3.13 -c "import sys; print(sys.executable)" 2>$null
    if ($LASTEXITCODE -eq 0 -and $Py313) {
        $PythonCmd = "py -3.13"
    }
}

if (-not $PythonCmd -and (Get-Command python -ErrorAction SilentlyContinue)) {
    $PythonCmd = "python"
}

if (-not $PythonCmd) {
    throw "Python was not found. Install Python 3.12 or 3.13, then run this script again."
}

$PythonOk = Invoke-Expression "$PythonCmd -c `"import sys; print('1' if (3, 12) <= sys.version_info[:2] < (3, 14) else '0')`""
if ($PythonOk -ne "1") {
    throw "Use Python 3.12 or 3.13. Python 3.14 is too new for this dependency stack right now."
}

Invoke-Expression "$PythonCmd -m venv --clear .venv"
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt

Write-Host ""
Write-Host "Python environment is ready."
Write-Host "Activate it with:"
Write-Host "  .\.venv\Scripts\activate"
Write-Host ""
Write-Host "Next:"
Write-Host "  .\.venv\Scripts\python.exe scripts\download_checkpoint.py"
