@echo off
rem Copyright (c) 2026 Tradesmart Supplies Limited. All rights reserved. Developed by Maurille Khonde.
rem Starts DocuLoop and opens it in the web browser. Double-click this file.
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo DocuLoop is not installed yet: the .venv folder is missing.
    echo See "First-time setup" in README.md.
    pause
    exit /b 1
)

echo Starting DocuLoop... the browser opens in a few seconds.
echo Keep this window open while you work. Close it to stop DocuLoop.

rem Use port 8501, or the next free one if another program already uses it.
set PORT=8501
:find_port
netstat -ano | findstr /r /c:":%PORT% .*LISTENING" >nul
if not errorlevel 1 (
    set /a PORT+=1
    goto find_port
)

rem Open the browser a few seconds after the app starts.
start "" /min cmd /c "timeout /t 5 /nobreak >nul & start http://localhost:%PORT%"

rem The app runs only on this computer and sends nothing to the internet.
".venv\Scripts\python.exe" -m streamlit run app.py --server.address localhost --server.port %PORT% --server.headless true --browser.gatherUsageStats false

pause
