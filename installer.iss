; installer.iss — Inno Setup script for Claude Usage Tray
; Build with: iscc installer.iss
; Or run: python build.py  (handles both steps automatically)

#define AppName "Claude Usage Tray"
#define AppVersion "1.0.0"
#define AppPublisher "brunopatuleia"
#define AppURL "https://github.com/brunopatuleia/claude-usage"
#define AppExeName "ClaudeUsageTray.exe"
#define AppDescription "Displays your Claude Code usage on the Windows system tray"

[Setup]
AppId={{A3F2C1D0-8B4E-4F7A-9C6B-2E5D1F0A3B8C}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} {#AppVersion}
AppPublisher={#AppPublisher}
AppPublisherURL={#AppURL}
AppSupportURL={#AppURL}/issues
AppUpdatesURL={#AppURL}/releases
DefaultDirName={autopf}\{#AppName}
DefaultGroupName={#AppName}
AllowNoIcons=yes
; Output installer to dist\ folder
OutputDir=dist
OutputBaseFilename=ClaudeUsageTray-Setup-{#AppVersion}
; Compression
Compression=lzma2/ultra64
SolidCompression=yes
; Require Windows 10+
MinVersion=10.0
; Show nice wizard
WizardStyle=modern
; Icon (optional — comment out if you don't have one)
; SetupIconFile=assets\icon.ico
; UninstallDisplayIcon={app}\{#AppExeName}
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon";     Description: "Create a &desktop shortcut";          GroupDescription: "Shortcuts:"; Flags: unchecked
Name: "startupentry";   Description: "Start automatically &with Windows";    GroupDescription: "Options:";   Flags: unchecked

[Files]
; Main executable (built by PyInstaller)
Source: "dist\{#AppExeName}"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
; Start Menu
Name: "{group}\{#AppName}";         Filename: "{app}\{#AppExeName}"
Name: "{group}\Uninstall {#AppName}"; Filename: "{uninstallexe}"
; Desktop (optional task)
Name: "{autodesktop}\{#AppName}";   Filename: "{app}\{#AppExeName}"; Tasks: desktopicon

[Registry]
; "Start with Windows" — adds to HKCU Run (no admin needed)
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; \
    ValueType: string; ValueName: "{#AppName}"; \
    ValueData: """{app}\{#AppExeName}"""; \
    Flags: uninsdeletevalue; Tasks: startupentry

[Run]
; Offer to launch after install
Filename: "{app}\{#AppExeName}"; \
    Description: "Launch {#AppName} now"; \
    Flags: nowait postinstall skipifsilent

[UninstallRun]
; Kill the running process before uninstalling
Filename: "taskkill"; Parameters: "/F /IM {#AppExeName}"; Flags: runhidden; RunOnceId: "KillApp"

[Code]
// Show a friendly message if the PyInstaller EXE is missing
function PrepareToInstall(var NeedsRestart: Boolean): String;
var
  ExePath: String;
begin
  ExePath := ExpandConstant('{src}\dist\{#AppExeName}');
  if not FileExists(ExePath) then
    Result := 'ClaudeUsageTray.exe not found in dist\.' + #13#10 +
              'Please run "python build.py" first to build the application.'
  else
    Result := '';
end;
