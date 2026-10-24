@echo off
setlocal
cd /d "%~dp0"
call build_windows.bat
if errorlevel 1 exit /b 1
if not exist release mkdir release
powershell -NoProfile -ExecutionPolicy Bypass -Command "if (Test-Path 'release\PythonPetV4-portable.zip') { Remove-Item 'release\PythonPetV4-portable.zip' -Force }; Compress-Archive -Path 'dist\PythonPetV4' -DestinationPath 'release\PythonPetV4-portable.zip' -CompressionLevel Optimal"
if errorlevel 1 (echo Portable ZIP failed.& pause& exit /b 1)
echo Portable ZIP: release\PythonPetV4-portable.zip
pause
