; ============================================================================
; Nabil Video Studio Pro - Inno Setup Installer Script
; ============================================================================
; This creates a professional Windows installer
;
; Requirements:
;   - Install Inno Setup from: https://jrsoftware.org/isinfo.php
;   - Open this file in Inno Setup Compiler
;   - Click Build > Compile to create the installer
; ============================================================================

#define MyAppName "Nabil Video Studio Pro"
#define MyAppVersion "1.7.6"
#define MyAppPublisher "Nabil Software"
#define MyAppURL "https://nabilsoftware.com"
#define MyAppExeName "NVS_Pro.exe"
#define MySourceDir "D:\DEV-SCRIPT\ALL-SCRIPT\3-NVS-PRO"

[Setup]
; Basic Info
AppId={{8F5E3C2A-1B4D-4E6F-9A8C-7D2B1E0F3A5C}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} {#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}

; Install Location
DefaultDirName={localappdata}\Programs\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes

; Output
OutputDir={#MySourceDir}\installer_output
OutputBaseFilename=NVS_Pro_v{#MyAppVersion}_Setup
SetupIconFile={#MySourceDir}\assets\logo.ico
UninstallDisplayIcon={app}\assets\logo.ico

; Compression
Compression=lzma2/ultra64
SolidCompression=yes
LZMAUseSeparateProcess=yes

; UI
WizardStyle=modern
WizardSizePercent=120

; Privileges (install to user folder, no admin needed)
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog

; Misc
AllowNoIcons=yes
DisableWelcomePage=no
DisableDirPage=no

; Close applications using files during install (for updates)
CloseApplications=force
CloseApplicationsFilter=*.exe,*.dll,*.py,*.pyd
RestartApplications=no

; Wait for app to close before starting file operations
SetupMutex=NabilVideoStudioProSetup

; Uninstall restart settings
UninstallRestartComputer=no

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Messages]
WelcomeLabel1=Welcome to {#MyAppName} Setup
WelcomeLabel2=This will install {#MyAppName} {#MyAppVersion} on your computer.%n%nNote: After installation, a First Time Setup will run to download AI components (3-4 GB). This requires an internet connection.

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"
Name: "startmenuicon"; Description: "Create Start Menu shortcut"; GroupDescription: "{cm:AdditionalIcons}"

[Files]
; Obfuscated Python scripts (protected with PyArmor)
Source: "{#MySourceDir}\pyarmor_dist\*.py"; DestDir: "{app}"; Excludes: "test_*"; Flags: ignoreversion
; PyArmor runtime (required to run obfuscated scripts)
Source: "{#MySourceDir}\pyarmor_dist\pyarmor_runtime_009860\*"; DestDir: "{app}\pyarmor_runtime_009860"; Flags: ignoreversion recursesubdirs createallsubdirs
; Text files (exclude PyArmor license files)
Source: "{#MySourceDir}\*.txt"; DestDir: "{app}"; Excludes: "pyarmor-*"; Flags: ignoreversion skipifsourcedoesntexist
; MP3 converter (not obfuscated - subfolder)
Source: "{#MySourceDir}\mp3\*"; DestDir: "{app}\mp3"; Flags: ignoreversion recursesubdirs createallsubdirs skipifsourcedoesntexist

; Standalone yt-dlp.exe (doesn't require Python - works on all systems)
Source: "{#MySourceDir}\yt-dlp.exe"; DestDir: "{app}"; Flags: ignoreversion

; Notification sound
Source: "{#MySourceDir}\notifications.mp3"; DestDir: "{app}"; Flags: ignoreversion

; Embedded Python (without site-packages - will be installed on first run)
Source: "{#MySourceDir}\python\*.exe"; DestDir: "{app}\python"; Flags: ignoreversion
Source: "{#MySourceDir}\python\*.dll"; DestDir: "{app}\python"; Flags: ignoreversion
Source: "{#MySourceDir}\python\*.pyd"; DestDir: "{app}\python"; Flags: ignoreversion
Source: "{#MySourceDir}\python\*.zip"; DestDir: "{app}\python"; Flags: ignoreversion skipifsourcedoesntexist
Source: "{#MySourceDir}\python\*.py"; DestDir: "{app}\python"; Flags: ignoreversion skipifsourcedoesntexist
Source: "{#MySourceDir}\python\*._pth"; DestDir: "{app}\python"; Flags: ignoreversion skipifsourcedoesntexist
Source: "{#MySourceDir}\python\Lib\*"; DestDir: "{app}\python\Lib"; Excludes: "torch,torchvision,torchaudio,nvidia,triton,torch-*,torchvision-*,torchaudio-*,nvidia-*"; Flags: ignoreversion recursesubdirs createallsubdirs skipifsourcedoesntexist
Source: "{#MySourceDir}\python\Scripts\*"; DestDir: "{app}\python\Scripts"; Flags: ignoreversion recursesubdirs createallsubdirs skipifsourcedoesntexist
Source: "{#MySourceDir}\python\DLLs\*"; DestDir: "{app}\python\DLLs"; Flags: ignoreversion recursesubdirs createallsubdirs skipifsourcedoesntexist

; Assets
Source: "{#MySourceDir}\assets\*"; DestDir: "{app}\assets"; Flags: ignoreversion recursesubdirs createallsubdirs skipifsourcedoesntexist

; Prompts
Source: "{#MySourceDir}\prompts\*"; DestDir: "{app}\prompts"; Flags: ignoreversion recursesubdirs createallsubdirs skipifsourcedoesntexist
Source: "{#MySourceDir}\prompts_content_creator\*"; DestDir: "{app}\prompts_content_creator"; Flags: ignoreversion recursesubdirs createallsubdirs skipifsourcedoesntexist

; Node.js (required for yt-dlp YouTube downloads)
Source: "{#MySourceDir}\node\node.exe"; DestDir: "{app}\node"; Flags: ignoreversion

; Launcher exe (proper executable - can be pinned to taskbar)
Source: "{#MySourceDir}\NVS_Pro.exe"; DestDir: "{app}"; Flags: ignoreversion

[Dirs]
; Create necessary directories
Name: "{app}\cache"
Name: "{app}\logs"
Name: "{localappdata}\NabilVideoStudioPro"

[Icons]
; Desktop shortcut with logo (autodesktop = user desktop when not admin)
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\NVS_Pro.exe"; IconFilename: "{app}\assets\logo.ico"; Tasks: desktopicon

; Start Menu shortcuts with logo (autoappdata picks user-level Start Menu)
Name: "{autoprograms}\{#MyAppName}"; Filename: "{app}\NVS_Pro.exe"; IconFilename: "{app}\assets\logo.ico"; Tasks: startmenuicon
Name: "{autoprograms}\{#MyAppName}\First Time Setup"; Filename: "{app}\python\python.exe"; Parameters: """{app}\first_run_setup.py"""; IconFilename: "{app}\assets\logo.ico"
Name: "{autoprograms}\{#MyAppName}\Uninstall {#MyAppName}"; Filename: "{uninstallexe}"

[Run]
; Run First Time Setup after install (waits for it to finish before launching app)
Filename: "{app}\python\python.exe"; Parameters: """{app}\first_run_setup.py"""; Description: "Run First Time Setup (download AI components - RECOMMENDED)"; Flags: postinstall skipifsilent unchecked
; Launch app after install
Filename: "{app}\NVS_Pro.exe"; Description: "Launch {#MyAppName}"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
; Clean up on uninstall
Type: filesandordirs; Name: "{app}\cache"
Type: filesandordirs; Name: "{app}\logs"
Type: filesandordirs; Name: "{app}\python\Lib\site-packages"
Type: filesandordirs; Name: "{app}\__pycache__"
Type: filesandordirs; Name: "{app}\pyarmor_runtime_009860"

[Code]
// Kill any running NVS Pro processes before installing
procedure KillRunningProcesses();
var
  ResultCode: Integer;
begin
  // Kill the main app
  Exec('taskkill.exe', '/F /IM NVS_Pro.exe', '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
  // Kill any Python processes from our app folder
  Exec('taskkill.exe', '/F /IM pythonw.exe', '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
  // Small delay to let files unlock
  Sleep(1000);
end;

function InitializeSetup(): Boolean;
begin
  Result := True;
  // Kill any running instances before install
  KillRunningProcesses();
end;

// Wait for the main application to close before proceeding
function PrepareToInstall(var NeedsRestart: Boolean): String;
var
  WaitCount: Integer;
begin
  Result := '';
  NeedsRestart := False;

  // Kill running processes again in case they restarted
  KillRunningProcesses();

  // Wait up to 10 seconds for files to unlock
  WaitCount := 0;
  while WaitCount < 10 do
  begin
    if not FileExists(ExpandConstant('{app}\NVS_Pro.exe')) then
      Break;

    if SaveStringToFile(ExpandConstant('{app}\update_check.tmp'), 'test', False) then
    begin
      DeleteFile(ExpandConstant('{app}\update_check.tmp'));
      Break;
    end;

    Sleep(1000);
    WaitCount := WaitCount + 1;
  end;
end;

procedure CurStepChanged(CurStep: TSetupStep);
begin
  if CurStep = ssPostInstall then
  begin
    // Create config directory in AppData
    ForceDirectories(ExpandConstant('{localappdata}\NabilVideoStudioPro'));
  end;
end;
