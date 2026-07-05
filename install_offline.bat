@echo off
setlocal EnableDelayedExpansion
cd /d "%~dp0"

rem --- Must match download_packages.bat ---
set PYTHON_VERSION=3.14.6
set PYTHON_INSTALLER=python-%PYTHON_VERSION%-amd64.exe
set PYTHON_DIR=%LOCALAPPDATA%\Programs\Python\Python314
set PYEXE=

echo ============================================================
echo  MACS VAC - OFFLINE install (no internet needed)
echo ============================================================
echo.

if not exist "offline_packages" (
    echo ERROR: offline_packages\ not found.
    echo Run download_packages.bat on a PC with internet first.
    exit /b 1
)

rem --- Find or install Python ---
where python >nul 2>&1
if not errorlevel 1 (
    for /f "delims=" %%v in ('python -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}')"') do set FOUND_PY=%%v
    echo Found Python: !FOUND_PY!
    set "PYEXE=python"
)

if not defined PYEXE (
    if exist "%PYTHON_DIR%\python.exe" (
        echo Found Python at: %PYTHON_DIR%\python.exe
        set "PYEXE=%PYTHON_DIR%\python.exe"
    )
)

if not defined PYEXE (
    if exist "offline_installers\%PYTHON_INSTALLER%" (
        echo Python not found. Installing from local installer...
        echo   offline_installers\%PYTHON_INSTALLER%
        "offline_installers\%PYTHON_INSTALLER%" /quiet InstallAllUsers=0 PrependPath=1 Include_test=0 Include_pip=1
        if errorlevel 1 (
            echo ERROR: Python installer failed.
            exit /b 1
        )
        echo Waiting for install to finish...
        timeout /t 8 /nobreak >nul
        if exist "%PYTHON_DIR%\python.exe" (
            set "PYEXE=%PYTHON_DIR%\python.exe"
        )
    )
)

if not defined PYEXE (
    echo.
    echo ERROR: Python is not installed.
    echo Copy offline_installers\%PYTHON_INSTALLER% from the online PC,
    echo or run download_packages.bat there first.
    exit /b 1
)

echo Using: %PYEXE%
"%PYEXE%" --version
echo.

rem --- Optional: Tesseract OCR ---
set TESSERACT_INSTALLER=tesseract-ocr-w64-setup-5.5.0.20241111.exe
where tesseract >nul 2>&1
if errorlevel 1 (
    if exist "C:\Program Files\Tesseract-OCR\tesseract.exe" (
        echo Tesseract: already installed
    ) else if exist "offline_installers\%TESSERACT_INSTALLER%" (
        echo Installing Tesseract OCR from local installer...
        "offline_installers\%TESSERACT_INSTALLER%" /S
        echo Tesseract install launched. OCR steps need tesseract.exe in PATH.
    ) else (
        echo NOTE: Tesseract not installed. OCR steps will not work until you install it.
    )
) else (
    echo Tesseract: already in PATH
)
echo.

rem --- Virtual environment + pip packages ---
echo Installing Python packages from offline_packages\ ...
if not exist "venv\Scripts\python.exe" (
    echo Creating virtual environment...
    "%PYEXE%" -m venv venv
)

call venv\Scripts\activate.bat

python -m pip install --no-index --find-links=offline_packages pip setuptools wheel
python -m pip install --no-index --find-links=offline_packages -r requirements.txt

if errorlevel 1 (
    echo.
    echo INSTALL FAILED.
    echo Python version on this PC must match %PYTHON_VERSION% ^(same as download PC^).
    exit /b 1
)

echo.
echo ============================================================
echo  SUCCESS
echo.
echo  Run the app:
echo    venv\Scripts\python.exe MACS_Visual_Automation.py
echo.
echo  Or double-click run_app.bat
echo ============================================================
endlocal
