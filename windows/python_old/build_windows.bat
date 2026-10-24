@echo off
setlocal
cd /d "%~dp0"
call setup_venv.bat
if errorlevel 1 exit /b 1
set PY=.venv\Scripts\python.exe
if not exist custom_characters mkdir custom_characters
set MODEL_DATA=
if exist "models\vosk-model-small-cn-0.22\conf\model.conf" set MODEL_DATA=--add-data "models;models"
%PY% -m PyInstaller --noconfirm --clean --windowed --onedir --name PythonPetV4 --collect-submodules PySide6.QtMultimedia --collect-submodules litellm --collect-submodules google.genai --add-data "assets;assets" --add-data "custom_characters;custom_characters" %MODEL_DATA% main.py
if errorlevel 1 (echo Build failed.& pause& exit /b 1)
echo Build complete: dist\PythonPetV4\PythonPetV4.exe
pause
