@echo off
rem Lance le panneau de controle (installe les dependances au premier lancement).
cd /d "%~dp0"

where python >nul 2>nul
if errorlevel 1 (
    echo Python 3 est introuvable.
    echo Installez-le depuis https://www.python.org/downloads/ en cochant "Add python.exe to PATH".
    pause
    exit /b 1
)

python -c "import pygame, numpy, imageio_ffmpeg" >nul 2>nul
if errorlevel 1 (
    echo Installation des dependances, patientez...
    python -m pip install -r requirements.txt
    if errorlevel 1 (
        echo L'installation a echoue.
        pause
        exit /b 1
    )
)

where pythonw >nul 2>nul
if errorlevel 1 (
    python main.py
) else (
    start "" pythonw main.py
)
