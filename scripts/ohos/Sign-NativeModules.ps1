<#
.SYNOPSIS
Strip and self-sign HarmonyOS native modules on the host (Windows).

.DESCRIPTION
HarmonyOS rejects unsigned user ELF, and DevEco ships llvm-strip,
llvm-objcopy and binary-sign-tool.jar, so the normalization performed by
scripts/ohos/sign-native-modules.sh on the device can run before packaging.

Self-signing is for development HAPs only. Release signing uses the official
certificate chain and remains member C's build step.

.PARAMETER Path
Files or directories to process. Directories are searched recursively for
*.so.

.PARAMETER SdkRoot
OHOS SDK root. Defaults to $env:DEVECO_SDK_HOME when set, otherwise the
standard DevEco Studio location.

.EXAMPLE
powershell -NoProfile -File scripts/ohos/Sign-NativeModules.ps1 -Path D:\gsas-cross\build
#>
param(
    [Parameter(Mandatory = $true)]
    [string[]]$Path,

    [string]$SdkRoot = $(if ($env:DEVECO_SDK_HOME) { $env:DEVECO_SDK_HOME } else { 'D:\DevEco Studio\sdk' })
)

$ErrorActionPreference = 'Stop'

$native = Join-Path $SdkRoot 'default/openharmony/native'
$toolchains = Join-Path $SdkRoot 'default/openharmony/toolchains/lib'
$strip = Join-Path $native 'llvm/bin/llvm-strip.exe'
$objcopy = Join-Path $native 'llvm/bin/llvm-objcopy.exe'
$signJar = Join-Path $toolchains 'binary-sign-tool.jar'

foreach ($tool in @($strip, $objcopy, $signJar)) {
    if (-not (Test-Path $tool)) { throw "missing signing tool: $tool" }
}

$files = foreach ($item in $Path) {
    if (Test-Path $item -PathType Container) {
        Get-ChildItem $item -Recurse -Filter '*.so' -File
    } elseif (Test-Path $item) {
        Get-Item $item
    } else {
        throw "path not found: $item"
    }
}
if (-not $files) { throw 'no .so files to sign' }

foreach ($file in $files) {
    & $strip --strip-debug $file.FullName
    if ($LASTEXITCODE -ne 0) { throw "llvm-strip failed: $($file.FullName)" }
    # Drop a previous signature before signing, matching sign-native-modules.sh.
    & $objcopy --remove-section=.codesign $file.FullName
    if ($LASTEXITCODE -ne 0) { throw "llvm-objcopy failed: $($file.FullName)" }
    & java -jar $signJar sign -inFile $file.FullName -outFile $file.FullName -selfSign 1 | Out-Null
    if ($LASTEXITCODE -ne 0) { throw "binary-sign-tool failed: $($file.FullName)" }
    $hash = (Get-FileHash $file.FullName -Algorithm SHA256).Hash.ToLower()
    '{0}  {1}' -f $hash, $file.FullName
}