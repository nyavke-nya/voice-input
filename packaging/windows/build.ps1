#Requires -Version 5
<#
  Одна команда для воспроизводимой локальной сборки Voice Input под Windows.

    powershell -ExecutionPolicy Bypass -File packaging\windows\build.ps1            # GPU (по умолчанию)
    powershell -ExecutionPolicy Bypass -File packaging\windows\build.ps1 -Gpu:$false # лёгкая CPU-сборка

  GPU-сборка вшивает CUDA-рантайм (~+1.5 ГБ) и включает NVIDIA при device: auto,
  иначе молча падает на CPU (универсально). CPU-сборка — компактная, без CUDA.

  Требуется: Python 3.12 x64 в PATH и Inno Setup 6.3+ (ISCC.exe в PATH).
  Подпись — опционально: задай $env:PILL_PFX (путь к .pfx) и $env:PILL_PFX_PASSWORD.
#>
param(
    [ValidateSet("true", "false", "1", "0")]
    [string]$Gpu = "true",
    [switch]$SkipInstaller,
    [switch]$ValidateOnly
)
$ErrorActionPreference = "Stop"
$gpuEnabled = $Gpu -in @("true", "1")
if ($ValidateOnly) {
    Write-Host "Parameters OK (GPU=$gpuEnabled)"
    return
}
function Assert-NativeSuccess([string]$Step) {
    if ($LASTEXITCODE -ne 0) { throw "$Step завершился с кодом $LASTEXITCODE." }
}
# PowerShell 7.4+: ненулевой код нативной команды (pip/PyInstaller/ISCC) — это ошибка.
if ($PSVersionTable.PSVersion.Major -ge 7) { $PSNativeCommandUseErrorActionPreference = $true }
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$root = (Resolve-Path (Join-Path $here "..\..")).Path
Set-Location $root

# 1. чистый venv
$venv = Join-Path $here ".venv-build"
if (Test-Path $venv) { Remove-Item -Recurse -Force $venv }
python -m venv $venv
Assert-NativeSuccess "Создание venv"
$py = Join-Path $venv "Scripts\python.exe"
& $py -m pip install --upgrade pip
Assert-NativeSuccess "Обновление pip"
$req = if ($gpuEnabled) { "requirements-windows-gpu.txt" } else { "requirements-windows.txt" }
Write-Host "Зависимости: $req  (GPU=$gpuEnabled)"
& $py -m pip install -r (Join-Path $here $req)
Assert-NativeSuccess "Установка зависимостей"

# 2/3. сборка onedir
foreach ($d in @("build", "dist")) {
    $p = Join-Path $root $d
    if (Test-Path $p) { Remove-Item -Recurse -Force $p }
}
& $py -m PyInstaller --noconfirm --clean (Join-Path $here "voice_input.spec")
Assert-NativeSuccess "PyInstaller"

# 4. smoke-test артефакта (тяжёлые DLL грузятся, ресурсы на месте)
$exe = Join-Path $root "dist\VoiceInput\VoiceInput.exe"
if (-not (Test-Path $exe)) { throw "PyInstaller не создал $exe" }
& $exe --self-test
Assert-NativeSuccess "Self-test"

if ($SkipInstaller) {
    Write-Host "Готово (без installer): $exe"
    return
}

# 5. Inno installer -> dist\VoiceInputSetup.exe
& ISCC.exe (Join-Path $here "voice-input.iss")
Assert-NativeSuccess "Inno Setup"
$setup = Join-Path $root "dist\VoiceInputSetup.exe"
if (-not (Test-Path $setup)) { throw "Inno Setup не создал $setup" }

# опциональная подпись EXE и installer
if ($env:PILL_PFX -and (Test-Path $env:PILL_PFX)) {
    $ts = "http://timestamp.digicert.com"
    & signtool.exe sign /f $env:PILL_PFX /p $env:PILL_PFX_PASSWORD /fd sha256 /tr $ts /td sha256 $exe
    Assert-NativeSuccess "Подпись EXE"
    & signtool.exe sign /f $env:PILL_PFX /p $env:PILL_PFX_PASSWORD /fd sha256 /tr $ts /td sha256 $setup
    Assert-NativeSuccess "Подпись installer"
    Write-Host "Подписано: $setup"
} else {
    Write-Host "Сертификат не задан — installer НЕ подписан (unsigned)."
}

Write-Host "Готово: $setup"
