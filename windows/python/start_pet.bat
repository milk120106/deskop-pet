@echo off
rem Starts the pet without a console window.
cd /d "%~dp0"
if not exist .venv\Scripts\pythonw.exe (
  echo .venv missing - run setup_venv.bat first.
  pause
  exit /b 1
)
start "" ".venv\Scripts\pythonw.exe" main.py
