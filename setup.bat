@echo off
chcp 65001 >nul 2>&1
title Sentinela - Instalacao

echo ============================================
echo   Sentinela - Instalacao Automatica
echo ============================================
echo.

:: Check Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERRO] Python nao encontrado!
    echo Instale o Python em https://python.org
    echo Marque "Add to PATH" durante a instalacao.
    pause
    exit /b 1
)
echo [OK] Python encontrado

:: Check FFmpeg
ffmpeg -version >nul 2>&1
if errorlevel 1 (
    echo [ERRO] FFmpeg nao encontrado!
    echo Instale o FFmpeg em https://ffmpeg.org/download.html
    echo Adicione ao PATH do sistema.
    pause
    exit /b 1
)
echo [OK] FFmpeg encontrado

:: Install Python dependencies
echo.
echo Instalando dependencias Python...
pip install -r requirements.txt --quiet
if errorlevel 1 (
    echo [ERRO] Falha ao instalar dependencias Python
    pause
    exit /b 1
)
echo [OK] Dependencias Python instaladas

:: Create directories
if not exist recordings mkdir recordings
if not exist logs mkdir logs
if not exist tools\mediamtx mkdir tools\mediamtx
if not exist tools\rclone mkdir tools\rclone
if not exist tools\cloudflared mkdir tools\cloudflared

:: Download MediaMTX
if not exist tools\mediamtx\mediamtx.exe (
    echo.
    echo Baixando MediaMTX...
    powershell -Command "& { $ProgressPreference='SilentlyContinue'; Invoke-WebRequest -Uri 'https://github.com/bluenviron/mediamtx/releases/download/v1.9.3/mediamtx_v1.9.3_windows_amd64.zip' -OutFile 'tools\mediamtx\mediamtx.zip' }" 2>nul
    if exist tools\mediamtx\mediamtx.zip (
        powershell -Command "Expand-Archive -Path 'tools\mediamtx\mediamtx.zip' -DestinationPath 'tools\mediamtx' -Force"
        del tools\mediamtx\mediamtx.zip 2>nul
        echo [OK] MediaMTX baixado
    ) else (
        echo [AVISO] Nao foi possivel baixar MediaMTX. Streaming ao vivo nao funcionara.
        echo         Baixe manualmente de: https://github.com/bluenviron/mediamtx/releases
    )
) else (
    echo [OK] MediaMTX ja instalado
)

:: Download rclone
if not exist tools\rclone\rclone.exe (
    echo.
    echo Baixando rclone...
    powershell -Command "& { $ProgressPreference='SilentlyContinue'; Invoke-WebRequest -Uri 'https://downloads.rclone.org/rclone-current-windows-amd64.zip' -OutFile 'tools\rclone\rclone.zip' }" 2>nul
    if exist tools\rclone\rclone.zip (
        powershell -Command "Expand-Archive -Path 'tools\rclone\rclone.zip' -DestinationPath 'tools\rclone\temp' -Force"
        powershell -Command "Get-ChildItem 'tools\rclone\temp\rclone-*\rclone.exe' | Move-Item -Destination 'tools\rclone\rclone.exe' -Force"
        rmdir /s /q tools\rclone\temp 2>nul
        del tools\rclone\rclone.zip 2>nul
        echo [OK] rclone baixado
    ) else (
        echo [AVISO] Nao foi possivel baixar rclone. Sync com nuvem nao funcionara.
        echo         Baixe manualmente de: https://rclone.org/downloads/
    )
) else (
    echo [OK] rclone ja instalado
)

:: Download cloudflared
if not exist tools\cloudflared\cloudflared.exe (
    echo.
    echo Baixando cloudflared...
    powershell -Command "& { $ProgressPreference='SilentlyContinue'; Invoke-WebRequest -Uri 'https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-windows-amd64.exe' -OutFile 'tools\cloudflared\cloudflared.exe' }" 2>nul
    if exist tools\cloudflared\cloudflared.exe (
        echo [OK] cloudflared baixado
    ) else (
        echo [AVISO] Nao foi possivel baixar cloudflared. Acesso remoto nao funcionara.
        echo         Baixe manualmente de: https://github.com/cloudflare/cloudflared/releases
    )
) else (
    echo [OK] cloudflared ja instalado
)

echo.
echo ============================================
echo   Instalacao concluida!
echo ============================================
echo.
echo Para iniciar o Sentinela, execute:
echo   python main.py
echo.
echo Ou use o atalho: start.bat
echo.
pause
