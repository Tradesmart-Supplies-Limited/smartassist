; Copyright (c) 2026 Tradesmart Supplies Limited. All rights reserved. Developed by Maurille Khonde.
; Inno Setup recipe: turns dist\SmartAssist (made by PyInstaller) into one SmartAssist_Setup.exe.
; Run packaging\build_installer.bat, which does everything in the right order.

#define AppName "SmartAssist"
#define AppVersion "2.0"
#define Publisher "Tradesmart Supplies Limited"

[Setup]
AppId=TradesmartSupplies.SmartAssist
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher={#Publisher}
; Installed for the person only: no administrator needed, and an update simply installs over it.
PrivilegesRequired=lowest
DefaultDirName={localappdata}\Programs\{#AppName}
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
OutputDir=..\dist
OutputBaseFilename=SmartAssist_Setup_{#AppVersion}
SetupIconFile=smartassist.ico
UninstallDisplayIcon={app}\SmartAssist.exe
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible

[Tasks]
Name: "desktopicon"; Description: "Put a SmartAssist icon on the desktop"; GroupDescription: "Shortcuts:"

[Files]
Source: "..\dist\SmartAssist\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\SmartAssist.exe"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\SmartAssist.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\SmartAssist.exe"; Description: "Open SmartAssist now"; Flags: nowait postinstall skipifsilent

; The saved inspection reports live in %LOCALAPPDATA%\SmartAssist and are kept on uninstall and update.
