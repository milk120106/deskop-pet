@echo off
setlocal
cd /d "%~dp0"
if exist "dist\PythonPetV4\PythonPetV4.exe" ("dist\PythonPetV4\PythonPetV4.exe" & pause & exit /b 0)
if not exist ".venv\Scripts\python.exe" call setup_venv.bat
if errorlevel 1 exit /b 1
.venv\Scripts\python.exe main.py
pause
