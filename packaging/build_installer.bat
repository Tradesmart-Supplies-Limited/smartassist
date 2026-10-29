@echo off
rem Copyright (c) 2026 Tradesmart Supplies Limited. All rights reserved. Developed by Maurille Khonde.
rem Makes dist\SmartAssist_Setup_2.0.exe: the installer to give to colleagues. Run it from this folder.
rem Needs (on this PC only): PyInstaller in .venv and Inno Setup 6. Colleagues need nothing.
cd /d "%~dp0\.."

echo 1/4 Running the automatic checks...
".venv\Scripts\python.exe" -m pytest -q
if errorlevel 1 (echo The checks failed: no installer made. & pause & exit /b 1)

echo 2/4 Making the icon...
".venv\Scripts\python.exe" packaging\make_icon.py

echo 3/4 Packing SmartAssist with its own Python (a few minutes)...
".venv\Scripts\pyinstaller.exe" --noconfirm --clean --distpath dist --workpath build packaging\smartassist.spec
if errorlevel 1 (echo Packing failed. & pause & exit /b 1)
"dist\SmartAssist\SmartAssist.exe" --check
if errorlevel 1 (echo The packed program failed its self-check. & pause & exit /b 1)

echo 4/4 Making the installer...
set ISCC=%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe
if not exist "%ISCC%" set ISCC=%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe
if not exist "%ISCC%" (echo Inno Setup 6 is not installed. & pause & exit /b 1)
"%ISCC%" packaging\installer.iss
if errorlevel 1 (echo The installer could not be made. & pause & exit /b 1)

echo.
echo Done: dist\SmartAssist_Setup_2.0.exe
pause
