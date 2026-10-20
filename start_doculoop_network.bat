@echo off
rem Copyright (c) 2026 Tradesmart Supplies Limited. All rights reserved. Developed by Maurille Khonde.
rem Starts DocuLoop for the whole office network: colleagues open it in their browser with a login.
rem Use start_doculoop.bat instead to keep DocuLoop on this computer only.
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo DocuLoop is not installed yet: the .venv folder is missing.
    echo See "First-time setup" in README.md.
    pause
    exit /b 1
)

rem Never share DocuLoop without logins: it shows passports and invoices.
".venv\Scripts\python.exe" manage_users.py check
if errorlevel 1 (
    echo No users are set up yet, so DocuLoop will not be shared on the network.
    echo Double-click manage_users.bat, add the users, then start this file again.
    pause
    exit /b 1
)

rem Always port 8501, so colleagues keep the same address.
set PORT=8501
netstat -ano | findstr /r /c:":%PORT% .*LISTENING" >nul
if not errorlevel 1 (
    echo DocuLoop is already running ^(port %PORT% is in use^). Close the other DocuLoop window first.
    pause
    exit /b 1
)

".venv\Scripts\python.exe" brand_streamlit.py

echo.
echo DocuLoop is starting for the office network. Colleagues open one of these in their browser:
echo     http://%COMPUTERNAME%:%PORT%
".venv\Scripts\python.exe" -c "import socket; [print('    http://' + a + ':%PORT%') for a in sorted({i[4][0] for i in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET)}) if not a.startswith('127.')]"
echo.
echo The first time, Windows may ask whether Python may use the network: choose Private networks and Allow.
echo Keep this window open while people work. Close it to stop DocuLoop for everyone.
echo.

start "" /min cmd /c "timeout /t 5 /nobreak >nul & start http://localhost:%PORT%"

rem Nothing goes to the internet: DocuLoop only answers computers on the office network.
".venv\Scripts\python.exe" -m streamlit run app.py --server.address 0.0.0.0 --server.port %PORT% --server.headless true --browser.gatherUsageStats false

pause
