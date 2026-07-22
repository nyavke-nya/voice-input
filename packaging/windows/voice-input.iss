; Inno Setup 6.3+ — per-user установка Voice Input без UAC.
; Собирает dist\VoiceInput\ (результат PyInstaller) в один VoiceInputSetup.exe.

#define AppName "Voice Input"
#define AppVersion "1.1.0"
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
; Уже установлено → не переспрашивать папку: сразу обновляем на месте.
DisableDirPage=auto
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

[CustomMessages]
ru.NvidiaTask=Ускорение NVIDIA (скачать около 1,3 ГБ во время установки)
en.NvidiaTask=NVIDIA acceleration (download about 1.3 GB during setup)
ru.NvidiaGroup=Дополнительно:
en.NvidiaGroup=Optional components:
ru.NvidiaDownloading=Скачивание cuBLAS и cuDNN для NVIDIA (около 1,3 ГБ)...
en.NvidiaDownloading=Downloading cuBLAS and cuDNN for NVIDIA (about 1.3 GB)...
ru.NvidiaFailed=Компоненты NVIDIA скачать не удалось. Voice Input установлен и будет работать на процессоре. Позже можно снова запустить установщик.
en.NvidiaFailed=The NVIDIA components could not be downloaded. Voice Input is installed and will work on the CPU. You can run Setup again later.
ru.UpdateButton=&Обновить
en.UpdateButton=&Update
ru.ReadyUpdate=Программа готова обновить Voice Input. Установленная версия: %1.
en.ReadyUpdate=Setup is ready to update Voice Input. Installed version: %1.

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"
Name: "autostart"; Description: "Запускать Voice Input при входе в систему"; GroupDescription: "Автозапуск:"
Name: "nvidiagpu"; Description: "{cm:NvidiaTask}"; GroupDescription: "{cm:NvidiaGroup}"; Flags: checkedonce; Check: HasNvidiaDriver

[Files]
; Маленький загрузчик извлекается только на время установки. Ставим первым,
; чтобы SolidCompression не заставлял распаковывать весь onedir ради него.
Source: "install-gpu-runtime.ps1"; Flags: dontcopy noencryption
; Весь onedir-каталог PyInstaller.
Source: "..\..\dist\VoiceInput\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs ignoreversion

[InstallDelete]
; Удалить CUDA от старой 1,6-ГБ сборки и предыдущий отдельно скачанный runtime.
; Только когда задача NVIDIA выбрана: тихий auto-update идёт с /MERGETASKS=!nvidiagpu,
; и существующий CUDA-рантайм сохраняется (не удаляется и не перекачивается заново).
Type: filesandordirs; Name: "{app}\gpu-runtime"; Check: NvidiaSelected
Type: filesandordirs; Name: "{app}\nvidia"; Check: NvidiaSelected
Type: filesandordirs; Name: "{app}\_internal\nvidia"; Check: NvidiaSelected
Type: files; Name: "{app}\cublas*.dll"; Check: NvidiaSelected
Type: files; Name: "{app}\cudnn*.dll"; Check: NvidiaSelected
Type: files; Name: "{app}\cudart*.dll"; Check: NvidiaSelected
Type: files; Name: "{app}\nvrtc*.dll"; Check: NvidiaSelected
Type: files; Name: "{app}\nvJitLink*.dll"; Check: NvidiaSelected
Type: files; Name: "{app}\_internal\cublas*.dll"; Check: NvidiaSelected
Type: files; Name: "{app}\_internal\cudnn*.dll"; Check: NvidiaSelected
Type: files; Name: "{app}\_internal\cudart*.dll"; Check: NvidiaSelected
Type: files; Name: "{app}\_internal\nvrtc*.dll"; Check: NvidiaSelected
Type: files; Name: "{app}\_internal\nvJitLink*.dll"; Check: NvidiaSelected

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
; Без skipifsilent: тихий auto-update (app сам ставит installer /SILENT) должен
; перезапустить приложение после обновления.
Filename: "{app}\{#AppExe}"; Description: "Запустить Voice Input"; Flags: nowait postinstall

[Code]
function HasNvidiaDriver: Boolean;
begin
  { nvcuda.dll ставится драйвером NVIDIA; без него CUDA-рантайм бесполезен. }
  Result := FileExists(ExpandConstant('{sys}\nvcuda.dll'));
end;

function NvidiaSelected: Boolean;
begin
  { CUDA удаляем/качаем только когда задача выбрана. Тихий auto-update идёт с
    /MERGETASKS=!nvidiagpu -> существующий CUDA-рантайм сохраняется как есть. }
  Result := WizardIsTaskSelected('nvidiagpu');
end;

function GetInstalledVersion: String;
begin
  { Inno хранит версию установленной сборки в ключе деинсталляции "<AppId>_is1".
    GUID продублирован из [Setup] намеренно — надёжнее ISPP-кавычек в строке. }
  Result := '';
  RegQueryStringValue(HKA,
    'Software\Microsoft\Windows\CurrentVersion\Uninstall\{7E660811-6038-47F1-838F-52AB5695DA2C}_is1',
    'DisplayVersion', Result);
end;

procedure CurPageChanged(CurPageID: Integer);
var
  Prev: String;
begin
  { Уже установлено → страница «Готово» говорит «обновить», кнопка тоже. }
  if CurPageID = wpReady then
  begin
    Prev := GetInstalledVersion;
    if Prev <> '' then
    begin
      WizardForm.NextButton.Caption := ExpandConstant('{cm:UpdateButton}');
      WizardForm.ReadyLabel.Caption := FmtMessage(ExpandConstant('{cm:ReadyUpdate}'), [Prev]);
    end;
  end;
end;

procedure InstallNvidiaRuntime;
var
  ResultCode: Integer;
  ScriptPath, Params: string;
  Started: Boolean;
begin
  if not WizardIsTaskSelected('nvidiagpu') then
    Exit;

  ExtractTemporaryFile('install-gpu-runtime.ps1');
  ScriptPath := ExpandConstant('{tmp}\install-gpu-runtime.ps1');
  Params := '-NoProfile -NonInteractive -ExecutionPolicy Bypass -File ' +
    AddQuotes(ScriptPath) + ' -AppDir ' + AddQuotes(ExpandConstant('{app}'));
  WizardForm.StatusLabel.Caption := ExpandConstant('{cm:NvidiaDownloading}');
  ResultCode := -1;
  Started := Exec(
    ExpandConstant('{sys}\WindowsPowerShell\v1.0\powershell.exe'),
    Params, '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
  if (not Started) or (ResultCode <> 0) then
  begin
    Log('NVIDIA runtime installer failed, exit=' + IntToStr(ResultCode));
    MsgBox(ExpandConstant('{cm:NvidiaFailed}'), mbError, MB_OK);
  end;
end;

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

procedure CurStepChanged(CurStep: TSetupStep);
begin
  if CurStep = ssPostInstall then
    InstallNvidiaRuntime;
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
begin
  if CurUninstallStep = usUninstall then
    StopRunning
  { Обычное удаление НЕ трогает настройки/модели. Отдельная опция (по умолчанию
    выключена, кнопка по умолчанию — «Нет»). }
  else if CurUninstallStep = usPostUninstall then
  begin
    { Файлы, скачанные во время установки, не входят в статический manifest. }
    DelTree(ExpandConstant('{app}\gpu-runtime'), True, True, True);
    if MsgBox('Удалить также настройки, статистику и скачанные модели Voice Input?' + #13#10 +
              '(по умолчанию они сохраняются)',
              mbConfirmation, MB_YESNO or MB_DEFBUTTON2) = IDYES then
    begin
      DelTree(ExpandConstant('{userappdata}\Voice Input'), True, True, True);
      DelTree(ExpandConstant('{localappdata}\Voice Input'), True, True, True);
    end;
  end;
end;
