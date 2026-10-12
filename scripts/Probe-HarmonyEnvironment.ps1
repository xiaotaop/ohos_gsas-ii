param(
    [string]$SdkHome = $env:DEVECO_SDK_HOME,
    [string]$Output = "poc/results/harmony-environment.json"
)

$ErrorActionPreference = "Stop"

if ([string]::IsNullOrWhiteSpace($SdkHome)) {
    throw "DEVECO_SDK_HOME is not set. Pass -SdkHome or set the environment variable."
}

$sdkRoot = [System.IO.Path]::GetFullPath($SdkHome)
$sdkPackage = Join-Path $sdkRoot "default\sdk-pkg.json"
$nativeRoot = Join-Path $sdkRoot "default\openharmony\native"
$clang = Join-Path $nativeRoot "llvm\bin\clang.exe"
$cmake = Join-Path $nativeRoot "build-tools\cmake\bin\cmake.exe"
$ninja = Join-Path $nativeRoot "build-tools\cmake\bin\ninja.exe"
$hdc = Join-Path $sdkRoot "default\openharmony\toolchains\hdc.exe"

foreach ($required in @($sdkPackage, $clang, $cmake, $ninja, $hdc)) {
    if (-not (Test-Path -LiteralPath $required -PathType Leaf)) {
        throw "Required SDK file not found: $required"
    }
}

$sdkMetadata = Get-Content -LiteralPath $sdkPackage -Raw | ConvertFrom-Json
$clangVersion = (& $clang --version 2>&1 | Out-String).Trim()
$targetTriple = (& $clang --target=aarch64-linux-ohos -dumpmachine 2>&1 | Out-String).Trim()
$hdcOutput = (& $hdc list targets 2>&1 | Out-String).Trim()

$deviceTargets = @()
if ($hdcOutput -and $hdcOutput -ne "[Empty]") {
    $deviceTargets = @(
        $hdcOutput -split "`r?`n" |
            ForEach-Object { $_.Trim() } |
            Where-Object { $_ -and $_ -ne "[Empty]" -and $_ -notmatch '^\[' }
    )
}

$fortranCompilers = @(
    Get-ChildItem -LiteralPath $sdkRoot -Recurse -File -ErrorAction SilentlyContinue |
        Where-Object { $_.Name -match '^(gfortran|flang|flang-new)(\.exe)?$' } |
        ForEach-Object { $_.FullName }
)

$blockers = @()
if ($deviceTargets.Count -eq 0) {
    $blockers += "No HarmonyOS target is visible to hdc."
}
if ($fortranCompilers.Count -eq 0) {
    $blockers += "The installed HarmonyOS SDK contains no Fortran compiler."
}

$result = [ordered]@{
    schema_version = 1
    generated_at = [DateTime]::UtcNow.ToString("o")
    sdk = [ordered]@{
        root = $sdkRoot
        display_name = $sdkMetadata.data.displayName
        api_version = $sdkMetadata.data.apiVersion
        platform_version = $sdkMetadata.data.platformVersion
        package_version = $sdkMetadata.data.version
    }
    native_toolchain = [ordered]@{
        clang = $clang
        clang_version = $clangVersion
        target_triple = $targetTriple
        cmake = $cmake
        ninja = $ninja
        c_cross_compile_ready = ($targetTriple -match 'aarch64.*linux-ohos')
        fortran_compilers = $fortranCompilers
        fortran_cross_compile_ready = ($fortranCompilers.Count -gt 0)
    }
    device = [ordered]@{
        hdc = $hdc
        raw_output = $hdcOutput
        targets = $deviceTargets
        connected = ($deviceTargets.Count -gt 0)
    }
    blockers = $blockers
    ready_for_harmony_core_poc = ($blockers.Count -eq 0)
}

$outputPath = [System.IO.Path]::GetFullPath((Join-Path (Get-Location) $Output))
$outputDirectory = Split-Path -Parent $outputPath
[System.IO.Directory]::CreateDirectory($outputDirectory) | Out-Null
$json = $result | ConvertTo-Json -Depth 8
[System.IO.File]::WriteAllText($outputPath, $json + [Environment]::NewLine, [System.Text.UTF8Encoding]::new($false))

Write-Host "HarmonyOS environment probe written to $outputPath"
if ($blockers.Count -gt 0) {
    Write-Host "Current blockers:"
    $blockers | ForEach-Object { Write-Host "- $_" }
}
