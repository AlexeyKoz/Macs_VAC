@echo off
setlocal EnableDelayedExpansion
cd /d "%~dp0"

echo ============================================================
echo  MACS VAC - OFFLINE DIAGNOSTIC
echo  Run this on the offline PC and send the full output.
echo ============================================================
echo.

if not exist "venv\Scripts\python.exe" (
    echo ERROR: venv not found. Run install_offline.bat first.
    pause
    exit /b 1
)

set PY=venv\Scripts\python.exe

echo ---- 1) Python ----
"%PY%" -c "import sys,platform;print('exe   :',sys.executable);print('ver   :',sys.version);print('bits  :',platform.architecture()[0]);print('win   :',platform.platform())"
echo.

echo ---- 2) Installed Qt packages ----
"%PY%" -m pip list 2>nul | findstr /I "PySide6 shiboken"
echo.

echo ---- 3) PySide6 location + Qt DLL folder ----
"%PY%" -c "import PySide6,os;d=os.path.dirname(PySide6.__file__);print('pkg   :',d);print('has bin:',os.path.isdir(d));print('files :',len([f for f in os.listdir(d) if f.lower().endswith(('.dll','.pyd')) ]),'dll/pyd in package')"
echo.

echo ---- 4) Import shiboken6 ----
"%PY%" -c "import shiboken6;print('shiboken6 OK',shiboken6.__version__)"
echo.

echo ---- 5) Import PySide6.QtCore ----
"%PY%" -c "from PySide6 import QtCore;print('QtCore OK',QtCore.__version__)"
echo.

echo ---- 6) Import PySide6.QtGui ----
"%PY%" -c "from PySide6 import QtGui;print('QtGui OK')"
echo.

echo ---- 7) Import PySide6.QtWidgets (the failing one) ----
"%PY%" -c "from PySide6 import QtWidgets;print('QtWidgets OK')"
echo.

echo ---- 8) VC++ runtime DLLs on system ----
if exist "%SystemRoot%\System32\msvcp140.dll" (
    echo msvcp140.dll   : FOUND in System32
) else (
    echo msvcp140.dll   : MISSING
)
if exist "%SystemRoot%\System32\vcruntime140.dll" (
    echo vcruntime140.dll : FOUND in System32
) else (
    echo vcruntime140.dll : MISSING
)
if exist "%SystemRoot%\System32\vcruntime140_1.dll" (
    echo vcruntime140_1.dll : FOUND in System32
) else (
    echo vcruntime140_1.dll : MISSING  ^(this one is often the culprit^)
)
echo.

echo ---- 9) Conflicting Qt DLLs on PATH ----
where Qt6Core.dll 2>nul
where Qt6Widgets.dll 2>nul
echo (blank above = none on PATH, which is good)
echo.

echo ============================================================
echo  Diagnostic complete. Copy ALL text above and send it back.
echo ============================================================
pause
endlocal
