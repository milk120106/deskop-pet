@echo off
cd /d "%~dp0"
if exist "dist\PythonPetV4\PythonPetV4.exe" (dist\PythonPetV4\PythonPetV4.exe) else (python main.py)
pause
