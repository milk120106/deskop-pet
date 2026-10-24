@echo off
cd /d "%~dp0"
rem Debug launcher: keeps this window open so errors are visible.
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0dsh_pet.ps1"
pause
