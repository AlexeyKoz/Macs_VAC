@echo off
setlocal EnableDelayedExpansion
cd /d "%~dp0"

rem --- Must match the Python version used for pip download ---
set PYTHON_VERSION=3.14.6
set PYTHON_INSTALLER=python-%PYTHON_VERSION%-amd64.exe
set PYTHON_URL=https://www.python.org/ftp/python/%PYTHON_VERSION%/%PYTHON_INSTALLER%

echo ============================================================
echo  MACS VAC - download everything for OFFLINE PC
echo  Run this on a PC WITH internet, then copy the whole folder.
echo ============================================================
echo.

if not exist "offline_packages" mkdir "offline_packages"
if not exist "offline_installers" mkdir "offline_installers"

rem --- 1) Python installer ---
echo [1/4] Python %PYTHON_VERSION% installer...
if exist "offline_installers\%PYTHON_INSTALLER%" (
    echo       Already downloaded: offline_installers\%PYTHON_INSTALLER%
) else (
    echo       Downloading from python.org ...
    curl -L -o "offline_installers\%PYTHON_INSTALLER%" "%PYTHON_URL%"
    if errorlevel 1 (
        echo ERROR: Failed to download Python. Check internet or download manually:
        echo   %PYTHON_URL%
        echo Save as: offline_installers\%PYTHON_INSTALLER%
        exit /b 1
    )
    echo       Saved: offline_installers\%PYTHON_INSTALLER%
)
echo.

rem --- 2) pip packages (needs Python already on THIS PC) ---
echo [2/4] Python packages from requirements.txt...
where python >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python is not installed on this PC.
    echo Install Python first, then run this script again.
    exit /b 1
)

for /f "delims=" %%v in ('python -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}')"') do set LOCAL_PY=%%v
echo       This PC Python: %LOCAL_PY%
echo       Target offline Python: %PYTHON_VERSION%
if /I not "%LOCAL_PY%"=="%PYTHON_VERSION%" (
    echo WARNING: Versions differ. Pip wheels may not work on the offline PC.
    echo          Install Python %PYTHON_VERSION% on this PC and re-run, or re-download
    echo          pip packages using: py -%PYTHON_VERSION% -m pip download ...
)

if not exist "venv\Scripts\pip.exe" (
    python -m venv venv
)
call venv\Scripts\activate.bat
python -m pip install --upgrade pip

rem Build/collect WHEELS for everything (converts source .tar.gz to .whl so the
rem offline PC never has to compile or reach the internet during install).
python -m pip wheel -r requirements.txt -w offline_packages
if errorlevel 1 (
    echo ERROR: Failed to build wheels for requirements.
    exit /b 1
)
rem Bootstrap tools as wheels too (needed to create the venv on the offline PC).
python -m pip download setuptools wheel pip -d offline_packages
echo.

rem --- 3) Microsoft Visual C++ Redistributable (REQUIRED by PySide6/Qt6) ---
echo [3/4] Visual C++ Redistributable (required by Qt)...
set VCREDIST=vc_redist.x64.exe
set VCREDIST_URL=https://aka.ms/vs/17/release/vc_redist.x64.exe
if exist "offline_installers\%VCREDIST%" (
    echo       Already downloaded: offline_installers\%VCREDIST%
) else (
    echo       Downloading VC++ Redistributable ...
    curl -L -o "offline_installers\%VCREDIST%" "%VCREDIST_URL%"
    if errorlevel 1 (
        echo WARNING: VC++ download failed. PySide6 will not import on the
        echo          offline PC without it. Download manually:
        echo          %VCREDIST_URL%
    ) else (
        echo       Saved: offline_installers\%VCREDIST%
    )
)
echo.

rem --- 4) optional Tesseract OCR (for OCR steps only) ---
echo [4/4] Tesseract OCR installer (optional, for OCR steps)...
set TESSERACT_INSTALLER=tesseract-ocr-w64-setup-5.5.0.20241111.exe
set TESSERACT_URL=https://digi.bib.uni-mannheim.de/tesseract/%TESSERACT_INSTALLER%
if exist "offline_installers\%TESSERACT_INSTALLER%" (
    echo       Already downloaded: offline_installers\%TESSERACT_INSTALLER%
) else (
    echo       Downloading Tesseract ...
    curl -L -o "offline_installers\%TESSERACT_INSTALLER%" "%TESSERACT_URL%"
    if errorlevel 1 (
        echo WARNING: Tesseract download failed. OCR steps will not work offline
        echo          until you install Tesseract manually on the other PC.
    ) else (
        echo       Saved: offline_installers\%TESSERACT_INSTALLER%
    )
)

echo.
echo ============================================================
echo  DONE. Copy the ENTIRE project folder to the offline PC:
echo    - offline_installers\   (Python + VC++ runtime + Tesseract installers)
echo    - offline_packages\     (pip wheels)
echo    - MACS_Visual_Automation.py
echo    - install_offline.bat
echo.
echo  On offline PC run:  install_offline.bat
echo ============================================================
endlocal
