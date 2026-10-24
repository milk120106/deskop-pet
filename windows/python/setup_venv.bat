@echo off
rem Create the virtual environment and install PySide6 (run once).
cd /d "%~dp0"
where python >nul 2>nul || (echo Python 3.10+ not found. & pause & exit /b 1)
if not exist .venv\Scripts\python.exe python -m venv .venv
.venv\Scripts\python.exe -m pip install --upgrade pip
.venv\Scripts\python.exe -m pip install -r requirements.txt
echo Done. Start the pet with start_pet.bat
pause
