@echo off
setlocal
cd /d "%~dp0"

if not exist "venv\Scripts\pyinstaller.exe" (
    echo Creating venv and installing dependencies...
    python -m venv venv
    call venv\Scripts\activate.bat
    pip install -r requirements.txt pyinstaller
) else (
    call venv\Scripts\activate.bat
)

echo Building MACS Visual Automation...
pyinstaller --noconfirm MACS_Visual_Automation.spec

if errorlevel 1 (
    echo Build FAILED.
    exit /b 1
)

echo.
echo Build complete.
echo Run: dist\MACS_VAC\MACS_Visual_Automation.exe
endlocal
