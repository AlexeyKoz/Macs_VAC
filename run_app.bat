@echo off
cd /d "%~dp0"
if not exist "venv\Scripts\python.exe" (
    echo Virtual environment not found. Run install_offline.bat first.
    pause
    exit /b 1
)
venv\Scripts\python.exe MACS_Visual_Automation.py
if errorlevel 1 (
    echo.
    echo The app exited with an error. See the message above.
    pause
)
