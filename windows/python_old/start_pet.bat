@echo off
setlocal
cd /d "%~dp0"
if exist "dist\PythonPetV4\PythonPetV4.exe" (start "" "dist\PythonPetV4\PythonPetV4.exe" & exit /b 0)
if not exist ".venv\Scripts\pythonw.exe" call setup_venv.bat
if errorlevel 1 exit /b 1
start "" ".venv\Scripts\pythonw.exe" main.py
