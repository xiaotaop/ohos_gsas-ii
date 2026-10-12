param(
    [string]$SdkHome = $env:DEVECO_SDK_HOME,
    [string]$OutputDirectory = "..\..\work\phase2-ohos"
)

$ErrorActionPreference = "Stop"

if ([string]::IsNullOrWhiteSpace($SdkHome)) {
    throw "DEVECO_SDK_HOME is not set. Pass -SdkHome or set the environment variable."
}

$repoRoot = Split-Path -Parent $PSScriptRoot
$source = Join-Path $repoRoot "poc\harmony\toolchain_smoke.c"
$nativeRoot = Join-Path ([System.IO.Path]::GetFullPath($SdkHome)) "default\openharmony\native"
$clang = Join-Path $nativeRoot "llvm\bin\clang.exe"
$readObject = Join-Path $nativeRoot "llvm\bin\llvm-readobj.exe"
$sysroot = Join-Path $nativeRoot "sysroot"

foreach ($required in @($source, $clang, $readObject, $sysroot)) {
    if (-not (Test-Path -LiteralPath $required)) {
        throw "Required input not found: $required"
    }
}

$buildDirectory = [System.IO.Path]::GetFullPath((Join-Path $repoRoot $OutputDirectory))
[System.IO.Directory]::CreateDirectory($buildDirectory) | Out-Null
$output = Join-Path $buildDirectory "libohos_gsas_toolchain_probe.so"

& $clang `
    --target=aarch64-linux-ohos `
    --sysroot=$sysroot `
    -fPIC `
    -shared `
    "-Wl,--no-undefined" `
    $source `
    -o $output

if ($LASTEXITCODE -ne 0) {
    throw "HarmonyOS C probe compilation failed with exit code $LASTEXITCODE"
}

$header = (& $readObject --file-headers $output 2>&1 | Out-String)
if ($LASTEXITCODE -ne 0 -or $header -notmatch 'Machine:\s+EM_AARCH64') {
    throw "Output is not an AArch64 ELF shared object.`n$header"
}

Write-Host "Built HarmonyOS AArch64 ELF shared object: $output"
Write-Host $header.Trim()
