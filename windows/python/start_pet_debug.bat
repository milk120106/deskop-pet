@echo off
rem Desktop Pet - Debug Console Launcher
cd /d "%~dp0"

set "PY_EXE="

if exist ".venv\Scripts\python.exe" (
    set "PY_EXE=.venv\Scripts\python.exe"
) else (
    where python >nul 2>nul
    if %ERRORLEVEL% equ 0 (
        set "PY_EXE=python"
    )
)

if "%PY_EXE%"=="" (
    echo Python environment not found. Please run setup_venv.bat first.
    pause
    exit /b 1
)

echo Starting Desktop Pet in debug mode...
"%PY_EXE%" main.py
if %ERRORLEVEL% neq 0 (
    echo.
    echo Process exited with error code %ERRORLEVEL%
    pause
)
