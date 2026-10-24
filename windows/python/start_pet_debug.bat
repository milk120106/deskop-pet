@echo off
rem Starts the pet with a console so errors stay visible (also see pet.log).
cd /d "%~dp0"
.venv\Scripts\python.exe main.py
pause
