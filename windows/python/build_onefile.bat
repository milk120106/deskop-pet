@echo off
rem Desktop Pet - Build Option A (Standalone Onefile EXE)
cd /d "%~dp0"

echo Checking Python environment...
set "PY_EXE=.venv\Scripts\python.exe"
if not exist "%PY_EXE%" (
    set "PY_EXE=python"
)

"%PY_EXE%" -c "import PyInstaller" >nul 2>nul
if %ERRORLEVEL% neq 0 (
    echo PyInstaller not found. Installing PyInstaller...
    "%PY_EXE%" -m pip install pyinstaller
    if %ERRORLEVEL% neq 0 (
        echo Failed to install PyInstaller.
        pause
        exit /b 1
    )
)

echo Building DesktopPet_Standalone.exe (Onefile mode)...
"%PY_EXE%" -m PyInstaller --noconfirm deskpet_onefile.spec

if %ERRORLEVEL% equ 0 (
    echo.
    echo Build completed successfully!
    echo Output: dist\DesktopPet_Standalone.exe
) else (
    echo.
    echo Build failed. Please check the error log above.
)

pause
