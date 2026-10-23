@echo off
setlocal
cd /d "%~dp0"
python -m pip install -r requirements.txt
python -m PyInstaller --noconfirm --clean --windowed --name PythonPetV4 --add-data "assets;assets" --add-data "custom_characters;custom_characters" main.py
if errorlevel 1 pause & exit /b 1
echo.
echo Build complete: dist\PythonPetV4\PythonPetV4.exe
pause
