@echo off
cd /d "%~dp0"
if exist "dist\PythonPetV4\PythonPetV4.exe" (start "" "dist\PythonPetV4\PythonPetV4.exe") else (pythonw main.py)
