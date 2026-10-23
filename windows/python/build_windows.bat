@echo off
setlocal
cd /d "%~dp0"
where py >nul 2>nul && set PY=py || set PY=python
call update_python_security.bat
if errorlevel 1 exit /b 1
%PY% -m pip install --upgrade --no-cache-dir -r requirements.txt
if exist "models\vosk-model-small-cn-0.22\conf\model.conf" set MODEL_DATA=--add-data "models;models"
%PY% -m PyInstaller --noconfirm --clean --windowed --onedir --name PythonPetV4 --collect-submodules PySide6.QtMultimedia --collect-submodules litellm --add-data "assets;assets" --add-data "custom_characters;custom_characters" %MODEL_DATA% main.py
if errorlevel 1 (
  echo Build failed.
  pause
  exit /b 1
)
echo.
echo Build complete: dist\PythonPetV4\PythonPetV4.exe
echo Copy the entire dist\PythonPetV4 folder when distributing.
pause
