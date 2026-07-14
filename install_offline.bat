@echo off
setlocal EnableDelayedExpansion
cd /d "%~dp0"

rem --- Must match download_packages.bat ---
set PYTHON_VERSION=3.14.6
set PYTHON_MM=3.14
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

rem ============================================================
rem  Find a Python whose version EXACTLY matches %PYTHON_MM%.
rem  The offline wheels (numpy/pillow are cp314) only work on the
rem  matching Python. A different Python on PATH (e.g. conda 3.12)
rem  is deliberately IGNORED here.
rem ============================================================

rem 1) Our pinned per-user install location
if exist "%PYTHON_DIR%\python.exe" (
    call :check_ver "%PYTHON_DIR%\python.exe"
    if not errorlevel 1 set "PYEXE=%PYTHON_DIR%\python.exe"
)

rem 2) The py launcher, asking for the exact minor version
if not defined PYEXE (
    py -%PYTHON_MM% -c "import sys" >nul 2>&1
    if not errorlevel 1 set "PYEXE=py -%PYTHON_MM%"
)

rem 3) python on PATH, but ONLY if its version matches
if not defined PYEXE (
    where python >nul 2>&1
    if not errorlevel 1 (
        call :check_ver "python"
        if not errorlevel 1 (
            set "PYEXE=python"
        ) else (
            for /f "delims=" %%v in ('python -c "import sys;print(sys.version.split()[0])" 2^>nul') do echo Ignoring Python on PATH ^(%%v^) - need %PYTHON_MM%.x
        )
    )
)

rem 4) Nothing suitable found - install our bundled Python
if not defined PYEXE (
    if exist "offline_installers\%PYTHON_INSTALLER%" (
        echo No Python %PYTHON_MM%.x found. Installing from local installer...
        echo   offline_installers\%PYTHON_INSTALLER%
        "offline_installers\%PYTHON_INSTALLER%" /quiet InstallAllUsers=0 PrependPath=1 Include_test=0 Include_pip=1
        if errorlevel 1 (
            echo ERROR: Python installer failed.
            exit /b 1
        )
        echo Waiting for install to finish...
        timeout /t 8 /nobreak >nul
        if exist "%PYTHON_DIR%\python.exe" set "PYEXE=%PYTHON_DIR%\python.exe"
    )
)

if not defined PYEXE (
    echo.
    echo ERROR: A matching Python %PYTHON_MM%.x is required but was not found.
    echo Copy offline_installers\%PYTHON_INSTALLER% from the online PC and
    echo run it, then re-run this script.
    exit /b 1
)

echo Using Python: %PYEXE%
%PYEXE% --version
echo.

rem --- Microsoft Visual C++ Redistributable (required by PySide6/Qt6) ---
rem Fixes: "DLL load failed while importing QtWidgets: The specified
rem procedure could not be found."
set VCREDIST=vc_redist.x64.exe
reg query "HKLM\SOFTWARE\Microsoft\VisualStudio\14.0\VC\Runtimes\X64" /v Installed >nul 2>&1
if errorlevel 1 (
    if exist "offline_installers\%VCREDIST%" (
        echo Installing Microsoft Visual C++ Redistributable ^(needed by Qt^)...
        "offline_installers\%VCREDIST%" /install /quiet /norestart
        echo VC++ Redistributable install finished.
    ) else (
        echo WARNING: offline_installers\%VCREDIST% not found.
        echo          PySide6 will fail to import without the VC++ runtime.
    )
) else (
    echo Visual C++ Redistributable: already installed
)
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

rem If an existing venv was built with the wrong Python, rebuild it.
if exist "venv\Scripts\python.exe" (
    call :check_ver "venv\Scripts\python.exe"
    if errorlevel 1 (
        echo Existing venv uses the wrong Python version - rebuilding it...
        rmdir /s /q venv
    )
)

if not exist "venv\Scripts\python.exe" (
    echo Creating virtual environment with %PYEXE% ...
    %PYEXE% -m venv venv
)

call venv\Scripts\activate.bat

rem Bootstrap tools first (all from local wheels, no internet).
python -m pip install --no-index --find-links=offline_packages pip setuptools wheel

rem Install the app requirements from local wheels only.
python -m pip install --no-index --find-links=offline_packages -r requirements.txt
if errorlevel 1 (
    echo.
    echo First attempt failed - retrying with build isolation disabled
    echo ^(uses the local setuptools/wheel, still no internet^)...
    python -m pip install --no-index --no-build-isolation --find-links=offline_packages -r requirements.txt
)

if errorlevel 1 (
    echo.
    echo INSTALL FAILED.
    echo   * This PC's Python version MUST match %PYTHON_VERSION%
    echo     ^(the version used on the download PC^) so the .whl files fit.
    echo     Check with:  "%PYEXE%" --version
    echo   * Make sure the whole offline_packages\ folder was copied over.
    echo   * numpy/pillow wheels are tagged cp314 - a different Python minor
    echo     version ^(3.12, 3.13, ...^) will be rejected. Re-download on a PC
    echo     running Python %PYTHON_VERSION%.
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
exit /b 0

rem ------------------------------------------------------------
rem  :check_ver  "<python exe>"
rem  Returns errorlevel 0 if major.minor == %PYTHON_MM%, else 1.
rem ------------------------------------------------------------
:check_ver
"%~1" -c "import sys; want=tuple(int(x) for x in '%PYTHON_MM%'.split('.')); sys.exit(0 if sys.version_info[:2]==want else 1)" >nul 2>&1
exit /b %errorlevel%
