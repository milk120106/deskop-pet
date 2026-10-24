@echo off
rem Desktop Pet - Build Option D (MSI Package via WiX Toolset)
cd /d "%~dp0"

if not exist "dist\DesktopPet_Portable\DesktopPet.exe" (
    echo Portable build not found. Running build_portable.bat first...
    call build_portable.bat
    if not exist "dist\DesktopPet_Portable\DesktopPet.exe" (
        echo Portable build failed. Cannot build MSI.
        pause
        exit /b 1
    )
)

echo Searching for WiX Toolset...
set "WIX_EXE="

where wix >nul 2>nul
if %ERRORLEVEL% equ 0 (
    set "WIX_EXE=wix"
) else (
    where candle >nul 2>nul
    if %ERRORLEVEL% equ 0 set "WIX_EXE=candle"
)

if "%WIX_EXE%"=="" (
    echo WiX Toolset was not found.
    echo Please install WiX Toolset to compile MSI:
    echo   1. Via .NET: dotnet tool install --global wix
    echo   2. Or via Winget: winget install WiX.WiX
    pause
    exit /b 1
)

echo Compiling MSI package...
if "%WIX_EXE%"=="wix" (
    wix build installer.wxs -o dist\DesktopPet_v2.1.0.msi
) else (
    candle.exe installer.wxs -out build\installer.wixobj
    light.exe -ext WixUIExtension build\installer.wixobj -out dist\DesktopPet_v2.1.0.msi
)

if %ERRORLEVEL% equ 0 (
    echo.
    echo MSI package built successfully!
    echo Output: dist\DesktopPet_v2.1.0.msi
) else (
    echo.
    echo MSI build failed.
)

pause
