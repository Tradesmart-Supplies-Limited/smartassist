@echo off
rem Copyright (c) 2026 Tradesmart Supplies Limited. All rights reserved. Developed by Maurille Khonde.
rem Installs SmartAssist on this computer. Run it once, with internet. Needs Python 3.12.
cd /d "%~dp0"

rem Find Python: the "py" launcher first, then plain "python".
set PY=py -3.12
%PY% --version >nul 2>&1
if errorlevel 1 set PY=python
%PY% --version >nul 2>&1
if errorlevel 1 (
    echo Python was not found on this computer.
    echo Install Python 3.12 from https://www.python.org/downloads/ first,
    echo tick "Add python.exe to PATH" in its installer, then run this file again.
    pause
    exit /b 1
)

echo Creating the SmartAssist environment (.venv)...
if not exist ".venv\Scripts\python.exe" %PY% -m venv .venv
if errorlevel 1 (
    echo The environment could not be created.
    pause
    exit /b 1
)

echo Downloading the packages SmartAssist needs. This takes a few minutes...
".venv\Scripts\python.exe" -m pip install --disable-pip-version-check streamlit==1.65.0 pandas==3.0.6 openpyxl==3.1.5 pymupdf==1.28.2 fonttools==4.66.1 pytest==9.1.1
if errorlevel 1 (
    echo.
    echo The download failed. Check the internet connection and run this file again.
    echo If the message above says "filename or extension is too long", move the SmartAssist
    echo folder to a short place such as C:\SmartAssist and run this file again.
    pause
    exit /b 1
)

echo.
echo SmartAssist is installed. Double-click start_smartassist.bat to open it.
pause
