@echo off
rem Desktop Pet - Build Option C (Inno Setup Installer Wizard)
cd /d "%~dp0"

if not exist "dist\DesktopPet_Portable\DesktopPet.exe" (
    echo Portable build not found. Running build_portable.bat first...
    call build_portable.bat
    if not exist "dist\DesktopPet_Portable\DesktopPet.exe" (
        echo Portable build failed. Cannot build installer.
        pause
        exit /b 1
    )
)

echo Searching for Inno Setup compiler (ISCC.exe)...
set "ISCC="

if exist "%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe" (
    set "ISCC=%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe"
) else if exist "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" (
    set "ISCC=C:\Program Files (x86)\Inno Setup 6\ISCC.exe"
) else if exist "C:\Program Files\Inno Setup 6\ISCC.exe" (
    set "ISCC=C:\Program Files\Inno Setup 6\ISCC.exe"
) else (
    where iscc >nul 2>nul
    if %ERRORLEVEL% equ 0 set "ISCC=iscc"
)

if "%ISCC%"=="" (
    echo Inno Setup 6 compiler (ISCC.exe) was not found.
    echo Please install Inno Setup 6 or run: winget install JRSoftware.InnoSetup
    pause
    exit /b 1
)

echo Using Inno Setup compiler: "%ISCC%"
echo Compiling installer...
"%ISCC%" "installer.iss"

if %ERRORLEVEL% equ 0 (
    echo.
    echo Installer built successfully!
    echo Output: dist\DesktopPet_Setup_v2.1.0.exe
) else (
    echo.
    echo Installer compilation failed.
)

pause
