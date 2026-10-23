@echo off
setlocal
cd /d "%~dp0"
where py >nul 2>nul && set PY=py || set PY=python
%PY% -m pip install -r requirements.txt
%PY% -m PyInstaller --noconfirm --clean --windowed --onedir --name PythonPetV4 --collect-submodules PySide6.QtMultimedia --collect-submodules litellm --add-data "assets;assets" --add-data "custom_characters;custom_characters" main.py
if errorlevel 1 (
  echo Build failed.
  pause
  exit /b 1
)
echo.
echo Build complete: dist\PythonPetV4\PythonPetV4.exe
echo Copy the entire dist\PythonPetV4 folder when distributing.
pause
