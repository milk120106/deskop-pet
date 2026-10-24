@echo off
rem Desktop Pet - Silent Background Launcher
cd /d "%~dp0"

if exist ".venv\Scripts\pythonw.exe" (
    start "" ".venv\Scripts\pythonw.exe" main.py
    exit /b 0
)

if exist ".venv\Scripts\python.exe" (
    start "" ".venv\Scripts\python.exe" main.py
    exit /b 0
)

where pythonw >nul 2>nul
if %ERRORLEVEL% equ 0 (
    start "" pythonw main.py
    exit /b 0
)

where python >nul 2>nul
if %ERRORLEVEL% equ 0 (
    start "" python main.py
    exit /b 0
)

echo Python environment not found. Please run setup_venv.bat first.
pause
exit /b 1
