@echo off
title Creation du logiciel Facturation Yvan
cd /d "%~dp0"
py -m pip install --upgrade pip
py -m pip install pyinstaller reportlab
py -m PyInstaller --noconfirm --clean --onefile --windowed --name FacturationYvan facturation.py
echo.
echo Termine. Le logiciel se trouve dans le dossier dist.
pause
