#Requires -Version 5.1
<#
  Скачивает официальный Windows CUDA runtime с PyPI и кладёт DLL отдельно от
  приложения. Вызывается установщиком только на компьютере с драйвером NVIDIA.
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$AppDir
)

Set-StrictMode -Version 2.0
$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"
[Net.ServicePointManager]::SecurityProtocol =
    [Net.ServicePointManager]::SecurityProtocol -bor [Net.SecurityProtocolType]::Tls12

$packages = @(
    "nvidia-cublas-cu12",
    "nvidia-cudnn-cu12",
    "nvidia-cuda-runtime-cu12",
    "nvidia-cuda-nvrtc-cu12"
)
$requiredDlls = @(
    "cublas64_12.dll",
    "cublasLt64_12.dll",
    "cudnn64_9.dll",
    "cudart64_12.dll",
    "nvrtc64_*.dll"
)
$runtimeDir = Join-Path $AppDir "gpu-runtime"
$tempRoot = Join-Path ([IO.Path]::GetTempPath()) ("voice-input-gpu-" + [Guid]::NewGuid().ToString("N"))
$stageDir = Join-Path $tempRoot "gpu-runtime"
$versions = New-Object System.Collections.Generic.List[string]

try {
    New-Item -ItemType Directory -Path $stageDir -Force | Out-Null

    foreach ($package in $packages) {
        $metadataUrl = "https://pypi.org/pypi/$package/json"
        $metadata = Invoke-RestMethod -Uri $metadataUrl -Method Get
        $wheels = @($metadata.urls | Where-Object {
            $_.packagetype -eq "bdist_wheel" -and $_.filename -like "*-win_amd64.whl"
        })
        if ($wheels.Count -eq 0) {
            throw "Для $package нет Windows x64 wheel."
        }

        $wheel = $wheels | Sort-Object filename | Select-Object -First 1
        $archive = Join-Path $tempRoot ($package + ".zip")
        Write-Host "[gpu] $package $($metadata.info.version)"
        Invoke-WebRequest -UseBasicParsing -Uri $wheel.url -OutFile $archive

        $expectedHash = ([string]$wheel.digests.sha256).ToLowerInvariant()
        $actualHash = (Get-FileHash -LiteralPath $archive -Algorithm SHA256).Hash.ToLowerInvariant()
        if ($actualHash -ne $expectedHash) {
            throw "SHA-256 не совпал для $package."
        }

        $extractDir = Join-Path $tempRoot $package
        Expand-Archive -LiteralPath $archive -DestinationPath $extractDir -Force
        $dlls = @(Get-ChildItem -LiteralPath $extractDir -Recurse -File -Filter "*.dll")
        if ($dlls.Count -eq 0) {
            throw "В wheel $package не найдены DLL."
        }
        foreach ($dll in $dlls) {
            Copy-Item -LiteralPath $dll.FullName -Destination (Join-Path $stageDir $dll.Name) -Force
        }
        $versions.Add("$package $($metadata.info.version)")

        Remove-Item -LiteralPath $archive -Force
        Remove-Item -LiteralPath $extractDir -Recurse -Force
    }

    foreach ($pattern in $requiredDlls) {
        if (-not (Get-ChildItem -LiteralPath $stageDir -File -Filter $pattern | Select-Object -First 1)) {
            throw "После распаковки не найден $pattern."
        }
    }

    if (Test-Path -LiteralPath $runtimeDir) {
        Remove-Item -LiteralPath $runtimeDir -Recurse -Force
    }
    Move-Item -LiteralPath $stageDir -Destination $runtimeDir
    @(
        "Downloaded from official PyPI packages:",
        $versions,
        "https://pypi.org/"
    ) | Set-Content -LiteralPath (Join-Path $runtimeDir "versions.txt") -Encoding UTF8
} catch {
    [Console]::Error.WriteLine("[gpu] " + $_.Exception.Message)
    exit 1
} finally {
    if (Test-Path -LiteralPath $tempRoot) {
        Remove-Item -LiteralPath $tempRoot -Recurse -Force -ErrorAction SilentlyContinue
    }
}
