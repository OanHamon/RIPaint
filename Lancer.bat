@echo off
rem Lance RIPaint dans le terminal (installe les dependances au premier lancement).
cd /d "%~dp0"
title RIPaint
chcp 65001 >nul

where python >nul 2>nul
if errorlevel 1 (
    echo Python 3 est introuvable.
    echo Installez-le depuis https://www.python.org/downloads/ en cochant "Add python.exe to PATH".
    pause
    exit /b 1
)

python -c "import pygame, numpy, imageio_ffmpeg, textual" >nul 2>nul
if errorlevel 1 (
    echo Installation des dependances, patientez...
    python -m pip install -r requirements.txt
    if errorlevel 1 (
        echo L'installation a echoue.
        pause
        exit /b 1
    )
)

python main.py
if errorlevel 1 pause
