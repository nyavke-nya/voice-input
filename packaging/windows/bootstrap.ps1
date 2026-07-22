#Requires -Version 5
<#
  Полный bootstrap Voice Input под Windows одной командой: ставит Python 3.12 и
  Inno Setup (winget, per-user, без прав администратора), при необходимости качает
  проект (git не нужен) и собирает VoiceInputSetup.exe.

  Из любого места:
    irm https://raw.githubusercontent.com/nyavke/voice-input/main/packaging/windows/bootstrap.ps1 | iex

  Или локально из репозитория:
    powershell -ExecutionPolicy Bypass -File packaging\windows\bootstrap.ps1
    powershell -ExecutionPolicy Bypass -File packaging\windows\bootstrap.ps1 -Gpu:$false   # лёгкая CPU-сборка

  Требуется Windows 10 22H2+/11 (в них есть winget) и интернет.
#>
param([bool]$Gpu = $true)
$ErrorActionPreference = "Stop"

function Info($m) { Write-Host "[bootstrap] $m" -ForegroundColor Cyan }
function Have($c) { [bool](Get-Command $c -ErrorAction SilentlyContinue) }

function Find-Python312 {
    if (Have py) {
        try {
            $exe = & py -3.12 -c "import sys;print(sys.executable)" 2>$null
            if ($LASTEXITCODE -eq 0 -and $exe) { return $exe.Trim() }
        } catch {}
    }
    foreach ($p in @(
        "$env:LOCALAPPDATA\Programs\Python\Python312\python.exe",
        "$env:ProgramFiles\Python312\python.exe",
        "${env:ProgramFiles(x86)}\Python312\python.exe")) {
        if (Test-Path $p) { return $p }
    }
    return $null
}

function Find-ISCC {
    if (Have ISCC.exe) { return (Get-Command ISCC.exe).Source }
    foreach ($p in @(
        "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe",
        "$env:ProgramFiles\Inno Setup 6\ISCC.exe",
        "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe")) {
        if (Test-Path $p) { return $p }
    }
    return $null
}

function Winget-Install($id) {
    if (-not (Have winget)) {
        throw "winget не найден. Обнови «App Installer» из Microsoft Store и повтори."
    }
    # per-user, без UAC; ненулевой код (напр. «уже установлено») не валит — проверим наличием exe
    winget install -e --id $id --scope user --silent `
        --accept-package-agreements --accept-source-agreements 2>$null | Out-Null
}

# --- Python 3.12 ---
$python = Find-Python312
if (-not $python) {
    Info "ставлю Python 3.12 (winget, per-user)…"
    Winget-Install "Python.Python.3.12"
    $python = Find-Python312
}
if (-not $python) { throw "Python 3.12 не найден даже после установки." }
Info "Python: $python"

# --- Inno Setup 6 (нужен только для installer; без него соберём просто папку с exe) ---
$iscc = Find-ISCC
if (-not $iscc) {
    Info "ставлю Inno Setup 6 (winget)…"
    Winget-Install "JRSoftware.InnoSetup"
    $iscc = Find-ISCC
}

# python и ISCC ищутся build.ps1 по PATH — добавим их каталоги в начало
$env:PATH = (Split-Path $python) + ";" + $env:PATH
if ($iscc) { $env:PATH = (Split-Path $iscc) + ";" + $env:PATH }

# --- получить проект (если запущено через irm|iex — качаем zip, git не нужен) ---
if ($PSScriptRoot -and (Test-Path (Join-Path $PSScriptRoot "build.ps1"))) {
    $build = Join-Path $PSScriptRoot "build.ps1"
} else {
    $work = Join-Path $env:TEMP "voice-input-build"
    if (Test-Path $work) { Remove-Item -Recurse -Force $work }
    New-Item -ItemType Directory -Path $work | Out-Null
    $zip = Join-Path $work "src.zip"
    Info "скачиваю проект…"
    Invoke-WebRequest "https://github.com/nyavke/voice-input/archive/refs/heads/main.zip" -OutFile $zip
    Expand-Archive $zip -DestinationPath $work
    $build = Join-Path $work "voice-input-main\packaging\windows\build.ps1"
}

$skip = @()
if (-not $iscc) {
    Info "Inno Setup недоступен — соберу папку с VoiceInput.exe без installer."
    $skip = @("-SkipInstaller")
}
Info "сборка (GPU=$Gpu)…"
& powershell.exe -NoProfile -ExecutionPolicy Bypass -File $build -Gpu:$Gpu @skip
