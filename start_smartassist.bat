@echo off
rem Copyright (c) 2026 Tradesmart Supplies Limited. All rights reserved. Developed by Maurille Khonde.
rem Opens the SmartAssist window from the project folder. Double-click this file.
rem (Colleagues use the installed SmartAssist program instead: see "Desktop version" in README.md.)
cd /d "%~dp0"

if not exist ".venv\Scripts\pythonw.exe" (
    echo SmartAssist is not installed yet: the .venv folder is missing.
    echo See "First-time setup" in README.md.
    pause
    exit /b 1
)

rem pythonw opens only the SmartAssist window, without a black command window.
start "" ".venv\Scripts\pythonw.exe" desktop_app.py
