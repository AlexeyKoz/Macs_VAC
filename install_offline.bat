@echo off
setlocal EnableDelayedExpansion
cd /d "%~dp0"

rem --- Must match download_packages.bat ---
set PYTHON_VERSION=3.14.6
set PYTHON_MM=3.14
set PYTHON_INSTALLER=python-%PYTHON_VERSION%-amd64.exe
set PYTHON_DIR=%LOCALAPPDATA%\Programs\Python\Python314
set PYEXE=

rem Modules the app actually imports at startup - used to VERIFY a working
rem install, not just trust that "pip said OK".
set VERIFY_IMPORTS=import PySide6.QtCore, PySide6.QtGui, PySide6.QtWidgets, cv2, numpy, PIL.Image, pyautogui, pytesseract, mss, pygetwindow, pyperclip

echo ============================================================
echo  MACS VAC - OFFLINE install (no internet needed)
echo  Anything already installed is skipped; only what's missing
echo  gets installed, so this is safe to re-run at any time.
echo ============================================================
echo.

rem ============================================================
rem  Fast path: if a working venv already exists, do nothing else.
rem ============================================================
if exist "venv\Scripts\python.exe" (
    call :check_ver "venv\Scripts\python.exe"
    if not errorlevel 1 (
        "venv\Scripts\python.exe" -c "%VERIFY_IMPORTS%" >nul 2>nul
        if not errorlevel 1 (
            echo Everything is already installed and working - nothing to do.
            goto :success
        )
    )
)

set HAVE_PACKAGES=0
if exist "offline_packages" set HAVE_PACKAGES=1
if "%HAVE_PACKAGES%"=="0" (
    echo NOTE: offline_packages\ not found here. Steps that need it will be
    echo       skipped for now; the script still installs everything else it
    echo       can, and checks at the end whether the app is fully working.
    echo.
)

rem ============================================================
rem [1/5] Find a Python whose version EXACTLY matches %PYTHON_MM%.
rem  The offline wheels (numpy/pillow etc.) are built for one specific
rem  Python version. A different Python on PATH (e.g. conda 3.12) is
rem  deliberately IGNORED here.
rem ============================================================
echo [1/5] Python %PYTHON_MM%.x
echo -------------------------------------------

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
            for /f "delims=" %%v in ('python -c "import sys;print(sys.version.split()[0])" 2^>nul') do echo   Ignoring Python on PATH ^(%%v^) - need %PYTHON_MM%.x
        )
    )
)

rem 4) Nothing suitable found - install our bundled Python
if not defined PYEXE (
    if exist "offline_installers\%PYTHON_INSTALLER%" (
        echo   No Python %PYTHON_MM%.x found. Installing from local installer...
        echo     offline_installers\%PYTHON_INSTALLER%
        "offline_installers\%PYTHON_INSTALLER%" /quiet InstallAllUsers=0 PrependPath=1 Include_test=0 Include_pip=1
        if errorlevel 1 (
            echo ERROR: Python installer failed.
            exit /b 1
        )
        echo   Waiting for install to finish...
        timeout /t 8 /nobreak >nul
        if exist "%PYTHON_DIR%\python.exe" set "PYEXE=%PYTHON_DIR%\python.exe"
    )
)

if not defined PYEXE (
    echo.
    echo ERROR: A matching Python %PYTHON_MM%.x is required but was not found,
    echo        and no local installer is available to install it.
    echo        Copy offline_installers\%PYTHON_INSTALLER% from the online PC
    echo        into this folder ^(or install Python %PYTHON_MM%.x manually^),
    echo        then re-run this script.
    exit /b 1
)

echo   Using: %PYEXE%
%PYEXE% --version
echo.

rem ============================================================
rem [2/5] Microsoft Visual C++ Redistributable (required by PySide6/Qt6)
rem  Fixes: "DLL load failed while importing QtWidgets: The specified
rem  procedure could not be found."
rem ============================================================
echo [2/5] Visual C++ Redistributable (required by Qt)
echo -------------------------------------------
set VCREDIST=vc_redist.x64.exe
reg query "HKLM\SOFTWARE\Microsoft\VisualStudio\14.0\VC\Runtimes\X64" /v Installed >nul 2>&1
if errorlevel 1 (
    if exist "offline_installers\%VCREDIST%" (
        echo   Installing Microsoft Visual C++ Redistributable ^(needed by Qt^)...
        "offline_installers\%VCREDIST%" /install /quiet /norestart
        echo   VC++ Redistributable install finished.
    ) else (
        echo   WARNING: offline_installers\%VCREDIST% not found.
        echo            PySide6 will fail to import without the VC++ runtime.
    )
) else (
    echo   Already installed - skipping.
)
echo.

rem ============================================================
rem [3/5] Optional: Tesseract OCR (only needed for OCR check / Verify text)
rem ============================================================
echo [3/5] Tesseract OCR ^(optional - only needed for OCR steps^)
echo -------------------------------------------
set TESSERACT_INSTALLER=tesseract-ocr-w64-setup-5.5.0.20241111.exe
where tesseract >nul 2>&1
if errorlevel 1 (
    if exist "C:\Program Files\Tesseract-OCR\tesseract.exe" (
        echo   Already installed - skipping.
    ) else if exist "offline_installers\%TESSERACT_INSTALLER%" (
        echo   Installing Tesseract OCR from local installer...
        "offline_installers\%TESSERACT_INSTALLER%" /S
        echo   Waiting for install to finish...
        timeout /t 5 /nobreak >nul
        echo   Tesseract install launched. OCR steps need tesseract.exe in PATH.
    ) else (
        echo   NOTE: Tesseract not found and no local installer available.
        echo         OCR check / Verify text steps won't work until you install
        echo         it - all other actions work fine without it.
    )
) else (
    echo   Already installed - skipping.
)
echo.

rem ============================================================
rem [4/5] Virtual environment
rem ============================================================
echo [4/5] Virtual environment ^(venv\^)
echo -------------------------------------------

rem If an existing venv was built with the wrong Python, rebuild it.
if exist "venv\Scripts\python.exe" (
    call :check_ver "venv\Scripts\python.exe"
    if errorlevel 1 (
        echo   Existing venv uses the wrong Python version - rebuilding it...
        rmdir /s /q venv
    )
)

if not exist "venv\Scripts\python.exe" (
    echo   Creating virtual environment with %PYEXE% ...
    %PYEXE% -m venv venv
    if errorlevel 1 (
        echo ERROR: Failed to create the virtual environment.
        exit /b 1
    )
) else (
    echo   Already exists - skipping.
)
echo.

rem ============================================================
rem [5/5] Python packages (PySide6, OpenCV, numpy, Pillow, etc.)
rem ============================================================
echo [5/5] Python packages
echo -------------------------------------------

if "%HAVE_PACKAGES%"=="1" (
    call venv\Scripts\activate.bat

    rem Bootstrap tools first - all from local wheels, no internet.
    python -m pip install --no-index --find-links=offline_packages pip setuptools wheel

    rem Install the app requirements from local wheels only. pip skips
    rem anything that's already satisfied, so partially-installed venvs
    rem just get the missing pieces filled in.
    python -m pip install --no-index --find-links=offline_packages -r requirements.txt
    if errorlevel 1 (
        echo.
        echo   First attempt failed - retrying with build isolation disabled
        echo   ^(uses the local setuptools/wheel, still no internet^)...
        python -m pip install --no-index --no-build-isolation --find-links=offline_packages -r requirements.txt
    )

    if errorlevel 1 (
        echo.
        echo WARNING: pip reported errors installing from offline_packages\.
        echo   * This PC's Python version MUST match %PYTHON_VERSION%
        echo     ^(the version used on the download PC^) so the .whl files fit.
        echo   * numpy/pillow wheels are tagged cp314 - a different Python minor
        echo     version ^(3.12, 3.13, ...^) will be rejected.
        echo   Continuing to the final check to see what actually still works...
    )
    call venv\Scripts\deactivate.bat >nul 2>nul
) else (
    echo   offline_packages\ not found - skipped. Checking below whether the
    echo   required packages are already present in venv\ anyway.
)
echo.

rem ============================================================
rem Final check: verify the app can actually import everything it needs.
rem This is the real pass/fail - not just "pip returned 0".
rem ============================================================
echo Verifying the installation...
"venv\Scripts\python.exe" -c "%VERIFY_IMPORTS%" 2>"%TEMP%\macs_vac_verify_err.txt"
if errorlevel 1 (
    echo.
    echo ============================================================
    echo  INSTALL INCOMPLETE - some required modules still fail to import:
    echo ============================================================
    type "%TEMP%\macs_vac_verify_err.txt"
    del "%TEMP%\macs_vac_verify_err.txt" >nul 2>nul
    echo.
    if "%HAVE_PACKAGES%"=="0" (
        echo   offline_packages\ was not found. Run download_packages.bat on a
        echo   PC with internet, copy the offline_packages\ folder here, and
        echo   re-run this script.
    ) else (
        echo   Make sure offline_packages\ was copied completely and matches
        echo   Python %PYTHON_VERSION%, then re-run this script.
    )
    exit /b 1
)
del "%TEMP%\macs_vac_verify_err.txt" >nul 2>nul
echo   All required modules import OK.
echo.

:success
echo ============================================================
echo  SUCCESS - MACS Visual Automation is ready to run.
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
