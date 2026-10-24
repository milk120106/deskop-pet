@echo off
setlocal
cd /d "%~dp0"
if exist "models\vosk-model-small-cn-0.22\conf\model.conf" (
    echo Vosk Chinese model already exists.
    exit /b 0
)
if not exist models mkdir models
powershell -NoProfile -ExecutionPolicy Bypass -Command "$u='https://alphacephei.com/vosk/models/vosk-model-small-cn-0.22.zip'; Invoke-WebRequest -UseBasicParsing -Uri $u -OutFile 'models\vosk-cn.zip'; Expand-Archive -Force 'models\vosk-cn.zip' 'models'; Remove-Item 'models\vosk-cn.zip'"
if errorlevel 1 (
    echo Failed to download Vosk model.
    pause
    exit /b 1
)
echo Vosk model installed.
