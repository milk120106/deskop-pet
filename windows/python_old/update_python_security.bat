@echo off
setlocal EnableExtensions
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (echo .venv not found. Run setup_venv.bat first.& exit /b 1)
set PY=.venv\Scripts\python.exe
%PY% -m pip install --no-cache-dir --upgrade "pip>=26.2.2" "certifi>=2026.10.19"
if errorlevel 1 goto :error
%PY% -m pip --version
%PY% -c "import certifi; print('certifi', certifi.__version__); print(certifi.where())"
echo Python TLS dependencies are updated inside .venv.
exit /b 0
:error
echo Security dependency update failed. Do not run the application until it succeeds.
pause
exit /b 1
