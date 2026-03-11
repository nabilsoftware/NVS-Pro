; ============================================================================
; Nabil Video Studio Pro - UPDATE ONLY Installer
; ============================================================================
; Lightweight installer that only updates scripts and prompts.
; Does NOT include Python, node, ffmpeg, or other large dependencies.
; For fresh installs, use NVS_Pro_Setup.iss instead.
; ============================================================================

#define MyAppName "Nabil Video Studio Pro"
#define MyAppVersion "1.7.16"
#define MyAppPublisher "Nabil Software"
#define MyAppURL "https://nabilsoftware.com"
#define MyAppExeName "NVS_Pro.exe"
#define MySourceDir "D:\DEV-SCRIPT\ALL-SCRIPT\3-NVS-PRO"

[Setup]
; Same AppId as full installer so Inno Setup knows it's the same app
AppId={{8F5E3C2A-1B4D-4E6F-9A8C-7D2B1E0F3A5C}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} {#MyAppVersion} Update
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}

; Install to same location as full installer
DefaultDirName={localappdata}\Programs\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes

; Output
OutputDir={#MySourceDir}\installer_output
OutputBaseFilename=NVS_Pro_v{#MyAppVersion}_Update
SetupIconFile={#MySourceDir}\assets\logo.ico
UninstallDisplayIcon={app}\assets\logo.ico

; Compression (fast — small files don't need ultra)
Compression=lzma2/fast
SolidCompression=yes

; UI
WizardStyle=modern
WizardSizePercent=120

; Privileges (same as full installer)
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog

; Misc
AllowNoIcons=yes
DisableWelcomePage=no
DisableDirPage=yes

; Close applications using files during install
CloseApplications=force
CloseApplicationsFilter=*.exe,*.dll,*.py,*.pyd
RestartApplications=no

; Same mutex as full installer
SetupMutex=NabilVideoStudioProSetup

; Don't create a new uninstaller — keep the one from full install
UpdateUninstallLogAppName=no
CreateUninstallRegKey=no

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Messages]
WelcomeLabel1={#MyAppName} Update
WelcomeLabel2=This will update {#MyAppName} to v{#MyAppVersion}.%n%nThis is a lightweight update that only updates the application scripts.

[Files]
; Obfuscated Python scripts (the main thing that changes)
Source: "{#MySourceDir}\pyarmor_dist\*.py"; DestDir: "{app}"; Excludes: "test_*"; Flags: ignoreversion
; PyArmor runtime
Source: "{#MySourceDir}\pyarmor_dist\pyarmor_runtime_009860\*"; DestDir: "{app}\pyarmor_runtime_009860"; Flags: ignoreversion recursesubdirs createallsubdirs

; Prompts (may change between versions)
Source: "{#MySourceDir}\prompts\*"; DestDir: "{app}\prompts"; Flags: ignoreversion recursesubdirs createallsubdirs skipifsourcedoesntexist
Source: "{#MySourceDir}\prompts_content_creator\*"; DestDir: "{app}\prompts_content_creator"; Flags: ignoreversion recursesubdirs createallsubdirs skipifsourcedoesntexist

; Assets (logo, defaults — small files)
Source: "{#MySourceDir}\assets\logo.ico"; DestDir: "{app}\assets"; Flags: ignoreversion skipifsourcedoesntexist
Source: "{#MySourceDir}\assets\defaults\*"; DestDir: "{app}\assets\defaults"; Flags: ignoreversion recursesubdirs createallsubdirs skipifsourcedoesntexist

[Run]
; Launch app after update
Filename: "{app}\NVS_Pro.exe"; Description: "Launch {#MyAppName}"; Flags: nowait postinstall skipifsilent

[Code]
// Kill any running NVS Pro processes before installing
procedure KillRunningProcesses();
var
  ResultCode: Integer;
begin
  Exec('taskkill.exe', '/F /IM NVS_Pro.exe', '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
  Exec('taskkill.exe', '/F /IM pythonw.exe', '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
  Sleep(1000);
end;

function InitializeSetup(): Boolean;
begin
  Result := True;
  KillRunningProcesses();
end;

function PrepareToInstall(var NeedsRestart: Boolean): String;
var
  WaitCount: Integer;
begin
  Result := '';
  NeedsRestart := False;
  KillRunningProcesses();

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
