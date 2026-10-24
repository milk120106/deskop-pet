@echo off
rem Desktop Pet - Build Option B (Portable Onedir Folder)
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

echo Building DesktopPet_Portable (Onedir mode)...
"%PY_EXE%" -m PyInstaller --noconfirm deskpet_portable.spec

if %ERRORLEVEL% equ 0 (
    echo Setting up user directories in portable folder...
    if not exist "dist\DesktopPet_Portable\custom_characters" mkdir "dist\DesktopPet_Portable\custom_characters"
    if not exist "dist\DesktopPet_Portable\custom_sounds" mkdir "dist\DesktopPet_Portable\custom_sounds"
    if not exist "dist\DesktopPet_Portable\logs" mkdir "dist\DesktopPet_Portable\logs"

    echo.
    echo Build completed successfully!
    echo Output directory: dist\DesktopPet_Portable\
    echo Executable: dist\DesktopPet_Portable\DesktopPet.exe
) else (
    echo.
    echo Build failed. Please check the error log above.
)

pause
