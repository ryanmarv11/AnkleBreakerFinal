[Setup]
AppName=AnkleBreaker
AppVersion=1.0.0
DefaultDirName={autopf}\AnkleBreaker
ArchitecturesInstallIn64BitMode=x64
DefaultGroupName=AnkleBreaker
OutputDir=dist_installer
OutputBaseFilename=AnkleBreakerSetup
Compression=lzma2
SolidCompression=yes

[Files]
Source: "dist\AnkleBreaker.exe"; DestDir: "{app}"; Flags: ignoreversion

; ⬇️  If you bundle extra stuff (icons, default metadata.json, etc.) add more lines:
; Source: "resources\*"; DestDir: "{app}\resources"; Flags: recursesubdirs ignoreversion

[Icons]
Name: "{commondesktop}\AnkleBreaker"; Filename: "{app}\AnkleBreaker.exe"
Name: "{group}\AnkleBreaker";   Filename: "{app}\AnkleBreaker.exe"

[Run]
; Launch right after install (optional)
; Filename: "{app}\AnkleBreaker.exe"; Description: "Launch now"; Flags: nowait postinstall skipifsilent
