@echo off
cd /d "%~dp0"

echo ===================================================
echo Auto-detecting Python Environment...
echo ===================================================

python -c "import sys; exit(0 if sys.version_info.major==3 and sys.version_info.minor in (12,13) else 1)" >nul 2>nul
if %errorlevel% equ 0 set PY=python& goto start_venv

py -3.13 -c "import sys" >nul 2>nul
if %errorlevel% equ 0 set PY=py -3.13& goto start_venv

py -3.12 -c "import sys" >nul 2>nul
if %errorlevel% equ 0 set PY=py -3.12& goto start_venv

echo [ERROR] Compatible Python version not found.
echo This project requires Python 3.12 or 3.13.
echo Please install Python and check 'Add python.exe to PATH' during setup.
pause
exit /b 1

:start_venv
echo Using Python: %PY%

if not exist ".venv\Scripts\python.exe" (
    %PY% -m venv .venv
)

if exist update_python_security.bat (
    call update_python_security.bat
)

echo 安全修補：正在強制更新虛擬環境的 pip 與憑證依賴...
.venv\Scripts\python.exe -m pip install --upgrade --no-cache-dir pip>=26.2.2 certifi>=2026.10.19

echo 正在安裝其餘專案套件 (requirements.txt)...
.venv\Scripts\python.exe -m pip install --upgrade --no-cache-dir -r requirements.txt

echo ===================================================
echo Setup complete. .venv is ready.
echo ===================================================
pause
