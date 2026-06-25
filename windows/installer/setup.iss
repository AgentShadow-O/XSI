; XSI Agent Inno Setup Script
#define MyAppName "XSI Security Agent"
#define MyAppVersion "0.4.0"
#define MyAppPublisher "XSI"
#define MyAppExeName "XSI-Agent-Tray.exe"
#define MyServiceExeName "XSI-Agent-Service.exe"

[Setup]
AppId={{XSI-AGENT-WINDOWS-SERVICE-1234}}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={commonpf}\XSI Agent
DefaultGroupName={#MyAppName}
OutputDir=.
OutputBaseFilename=XSI-Agent-Setup
Compression=lzma
SolidCompression=yes
PrivilegesRequired=admin

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Dirs]
Name: "{commonappdata}\XSI"; Permissions: admins-full
Name: "{commonappdata}\XSI\config"; Permissions: admins-full
Name: "{commonappdata}\XSI\logs"; Permissions: admins-full users-modify
Name: "{commonappdata}\XSI\data"; Permissions: admins-full users-modify
Name: "{commonappdata}\XSI\cache"; Permissions: admins-full users-modify
Name: "{commonappdata}\XSI\queue"; Permissions: admins-full users-modify
Name: "{commonappdata}\XSI\modules"; Permissions: admins-full users-modify
Name: "{commonappdata}\XSI\temp"; Permissions: admins-full users-modify

[Files]
Source: "{#SourcePath}\..\dist\{#MyServiceExeName}"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#SourcePath}\..\dist\{#MyAppExeName}"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#SourcePath}\..\assets\*"; DestDir: "{app}\assets"; Flags: ignoreversion recursesubdirs
; Config will be created by the code below

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{commondesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon
Name: "{commonstartup}\XSI Agent Tray"; Filename: "{app}\{#MyAppExeName}"

[Run]
; Install the service using standard pywin32 command
Filename: "{app}\{#MyServiceExeName}"; Parameters: "install"; Flags: runhidden
; Configure service recovery and automatic startup
Filename: "{sys}\sc.exe"; Parameters: "config ""XSI Agent"" start= auto"; Flags: runhidden
Filename: "{sys}\sc.exe"; Parameters: "failure ""XSI Agent"" actions= restart/60000/restart/60000/restart/60000 reset= 86400"; Flags: runhidden
; Start the service
Filename: "{app}\{#MyServiceExeName}"; Parameters: "start"; Flags: runhidden
; Start the tray app for the current user
Filename: "{app}\{#MyAppExeName}"; Flags: nowait postinstall skipifsilent

[UninstallRun]
Filename: "{app}\{#MyServiceExeName}"; Parameters: "stop"; Flags: runhidden; RunOnceId: "StopXSIService"
Filename: "{app}\{#MyServiceExeName}"; Parameters: "remove"; Flags: runhidden; RunOnceId: "RemoveXSIService"

[Code]
var
  ServerPage: TInputQueryWizardPage;

function InitializeSetup(): Boolean;
begin
  Result := True;
end;

function PrepareToInstall(var NeedsRestart: Boolean): String;
var
  ResultCode: Integer;
begin
  Exec(ExpandConstant('{sys}\sc.exe'), 'stop "XSI Agent"', '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
  Exec(ExpandConstant('{sys}\sc.exe'), 'delete "XSI Agent"', '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
  Result := '';
end;

procedure InitializeWizard;
begin
  ServerPage := CreateInputQueryPage(wpSelectDir,
    'XSI Controller Configuration', 'Connection Details',
    'Please enter the server URL and your agent token.');
  ServerPage.Add('Server URL (e.g. https://xsi-api.example.com):', False);
  ServerPage.Add('Agent Token:', False);
  ServerPage.Add('Device Name (Optional):', False);
  
  ServerPage.Values[0] := '';
  ServerPage.Values[1] := '';
end;

procedure CurStepChanged(CurStep: TSetupStep);
var
  ConfigContent: String;
  ConfigDir: String;
begin
  if CurStep = ssPostInstall then
  begin
    ConfigDir := ExpandConstant('{commonappdata}\XSI\config');
    ForceDirectories(ConfigDir);
    if not FileExists(ConfigDir + '\agent.json') then
    begin
      ConfigContent := '{' + #13#10 +
        '  "server": "' + ServerPage.Values[0] + '",' + #13#10 +
        '  "enrollment_token": "' + ServerPage.Values[1] + '",' + #13#10 +
        '  "device_name": "' + ServerPage.Values[2] + '",' + #13#10 +
        '  "has_initial_scan": false' + #13#10 +
        '}';
      SaveStringToFile(ConfigDir + '\agent.json', ConfigContent, False);
    end;
  end;
end;
