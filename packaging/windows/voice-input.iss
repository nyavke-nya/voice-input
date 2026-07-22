; Inno Setup 6.3+ — per-user установка Voice Input без UAC.
; Собирает dist\VoiceInput\ (результат PyInstaller) в один VoiceInputSetup.exe.

#define AppName "Voice Input"
#define AppVersion "0.1.0"
#define AppExe "VoiceInput.exe"

[Setup]
; Постоянный AppId — обязателен для upgrades поверх старой версии.
AppId={{7E660811-6038-47F1-838F-52AB5695DA2C}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher=nyavke
VersionInfoVersion={#AppVersion}
WizardStyle=modern
; per-user: без прав администратора, без UAC
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
DefaultDirName={localappdata}\Programs\Voice Input
UsePreviousAppDir=yes
DisableProgramGroupPage=yes
DefaultGroupName={#AppName}
; x64, минимум Windows 10 22H2 (build 19045)
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0.19045
OutputDir=..\..\dist
OutputBaseFilename=VoiceInputSetup
SetupIconFile=voice-input.ico
UninstallDisplayIcon={app}\{#AppExe}
UninstallDisplayName={#AppName}
Compression=lzma2
SolidCompression=yes

[Languages]
Name: "ru"; MessagesFile: "compiler:Languages\Russian.isl"
Name: "en"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"
Name: "autostart"; Description: "Запускать Voice Input при входе в систему"; GroupDescription: "Автозапуск:"

[Files]
; Весь onedir-каталог PyInstaller.
Source: "..\..\dist\VoiceInput\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs ignoreversion

[Icons]
; Все ярлыки — только на установленный EXE (иконка вшита в него PyInstaller'ом,
; поэтому не зависим от onedir-раскладки _internal). Никакого python/.py/ps1.
Name: "{autoprograms}\{#AppName}"; Filename: "{app}\{#AppExe}"; Parameters: "--settings"
Name: "{autodesktop}\{#AppName}";  Filename: "{app}\{#AppExe}"; Parameters: "--settings"; Tasks: desktopicon

[Registry]
; Автозапуск демона без окна (по умолчанию включён).
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: string; \
  ValueName: "Voice Input"; ValueData: """{app}\{#AppExe}"""; Flags: uninsdeletevalue; Tasks: autostart

[Run]
Filename: "{app}\{#AppExe}"; Description: "Запустить Voice Input"; Flags: nowait postinstall skipifsilent

[Code]
{ Аккуратно завершить работающий экземпляр штатной командой (не убивая
  посторонние процессы) перед заменой файлов и перед удалением. }
procedure StopRunning;
var
  ResultCode: Integer;
  Exe: string;
begin
  Exe := ExpandConstant('{app}\{#AppExe}');
  if FileExists(Exe) then
  begin
    Exec(Exe, '--quit', '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
    Sleep(800);
  end;
end;

function PrepareToInstall(var NeedsRestart: Boolean): String;
begin
  StopRunning;   { upgrade: закрыть предыдущую версию }
  Result := '';
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
begin
  if CurUninstallStep = usUninstall then
    StopRunning
  { Обычное удаление НЕ трогает настройки/модели. Отдельная опция (по умолчанию
    выключена, кнопка по умолчанию — «Нет»). }
  else if CurUninstallStep = usPostUninstall then
  begin
    if MsgBox('Удалить также настройки, статистику и скачанные модели Voice Input?' + #13#10 +
              '(по умолчанию они сохраняются)',
              mbConfirmation, MB_YESNO or MB_DEFBUTTON2) = IDYES then
    begin
      DelTree(ExpandConstant('{userappdata}\Voice Input'), True, True, True);
      DelTree(ExpandConstant('{localappdata}\Voice Input'), True, True, True);
    end;
  end;
end;
