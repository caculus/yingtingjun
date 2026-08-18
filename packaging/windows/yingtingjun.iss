#define MyAppName "英聽君"
#define MyAppVersion "1.1.0"
#define MyAppPublisher "yingtingjun"
#define DistDir "..\..\dist\Yingtingjun"

[Setup]
AppId={{8F3C2A91-6B47-4E0D-9C1A-2D5E7B8F4A10}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={localappdata}\Yingtingjun
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
OutputDir=..\..\dist
OutputBaseFilename=Yingtingjun-Setup-x64
Compression=lzma
SolidCompression=yes
WizardStyle=modern
UninstallDisplayName={#MyAppName}
SetupLogging=yes

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Files]
Source: "{#DistDir}\*"; DestDir: "{app}"; Flags: recursesubdirs ignoreversion; Excludes: "__pycache__\*,*.pyc,.deps-ok"

[Icons]
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\Yingtingjun.bat"; WorkingDir: "{app}"; Comment: "英聽君 — 本機英文聽力播放器"
Name: "{autoprograms}\{#MyAppName}"; Filename: "{app}\Yingtingjun.bat"; WorkingDir: "{app}"; Comment: "英聽君 — 本機英文聽力播放器"

[Run]
Filename: "{app}\Yingtingjun.bat"; Description: "啟動英聽君"; Flags: nowait postinstall skipifsilent unchecked

[UninstallDelete]
; Do not list data\ — user transcripts and notes should survive uninstall.

[Code]
procedure CurStepChanged(CurStep: TSetupStep);
var
  ResultCode: Integer;
begin
  if CurStep = ssPostInstall then
  begin
    WizardForm.StatusLabel.Caption := '正在下載 Python、ffmpeg、詞典與模型（請看進度視窗）…';
    WizardForm.StatusLabel.Update;
    if not Exec(
      ExpandConstant('{sys}\WindowsPowerShell\v1.0\powershell.exe'),
      '-NoProfile -ExecutionPolicy Bypass -NoLogo -File "' + ExpandConstant('{app}\Install-PythonDeps.ps1') + '"',
      ExpandConstant('{app}'),
      SW_SHOWNORMAL,
      ewWaitUntilTerminated,
      ResultCode) then
    begin
      MsgBox('無法啟動下載程式。之後開啟英聽君會再試一次。', mbError, MB_OK);
    end
    else if ResultCode <> 0 then
    begin
      MsgBox('執行階段下載失敗（代碼 ' + IntToStr(ResultCode) + '）。之後開啟英聽君會再試一次。', mbError, MB_OK);
    end;
  end;
end;
