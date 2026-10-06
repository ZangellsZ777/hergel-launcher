#include "version.iss"
[Setup]
AppId={{AB8F8537-8920-494D-978E-AF798087677A}
AppName=Hergel Launcher
AppVersion={#HergelVersion}
AppPublisher=Hergel Studio
DefaultDirName={localappdata}\Programs\HergelLauncher
DefaultGroupName=Hergel Launcher
PrivilegesRequired=lowest
OutputDir=..\dist
OutputBaseFilename=Hergel-Launcher-Instalador
SetupIconFile=..\assets\hergel.ico
UninstallDisplayIcon={app}\HergelLauncher.exe
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible

[Languages]
Name: "spanish"; MessagesFile: "compiler:Languages\Spanish.isl"

[Files]
Source: "..\dist\HergelLauncher\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\Hergel Launcher"; Filename: "{app}\HergelLauncher.exe"
Name: "{autodesktop}\Hergel Launcher"; Filename: "{app}\HergelLauncher.exe"

[Run]
Filename: "{app}\HergelLauncher.exe"; Description: "Abrir Hergel Launcher"; Flags: nowait postinstall skipifsilent
