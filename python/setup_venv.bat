@echo off
setlocal

cd /d "%~dp0"

set PYTHON_CMD=

where py >nul 2>nul
if not errorlevel 1 (
    py -3.13 -c "import sys; print(sys.executable)" >nul 2>nul
    if not errorlevel 1 set PYTHON_CMD=py -3.13
)

if "%PYTHON_CMD%"=="" (
    where python >nul 2>nul
    if errorlevel 1 (
        echo Python was not found. Install Python 3.12 or 3.13, then run this script again.
        exit /b 1
    )
    set PYTHON_CMD=python
)

for /f %%v in ('%PYTHON_CMD% -c "import sys; print(1 if (3, 12) <= sys.version_info[:2] ^< (3, 14) else 0)"') do set PYTHON_OK=%%v
if not "%PYTHON_OK%"=="1" (
    echo Use Python 3.12 or 3.13. Python 3.14 is too new for this dependency stack right now.
    exit /b 1
)

%PYTHON_CMD% -m venv --clear .venv
if errorlevel 1 exit /b 1

call .venv\Scripts\activate.bat
python -m pip install --upgrade pip
if errorlevel 1 exit /b 1

python -m pip install -r requirements.txt
if errorlevel 1 exit /b 1

echo.
echo Python environment is ready.
echo Activate it with:
echo   .venv\Scripts\activate.bat
echo.
echo Next:
echo   python scripts\download_checkpoint.py
