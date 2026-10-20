@echo off
rem Copyright (c) 2026 Tradesmart Supplies Limited. All rights reserved. Developed by Maurille Khonde.
rem Add, remove or reset DocuLoop users. Double-click this file.
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
    echo DocuLoop is not installed yet: the .venv folder is missing.
    pause
    exit /b 1
)
".venv\Scripts\python.exe" manage_users.py
