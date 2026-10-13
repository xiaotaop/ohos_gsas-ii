param([switch]$Check)
$ErrorActionPreference = 'Stop'
$root = Split-Path $PSScriptRoot -Parent
$destination = Join-Path $root 'ui-mock/entry/src/main/resources/rawfile'
$names = @('refinement-request.json', 'core-events-success.json', 'core-events-failed.json', 'core-events-cancelled.json')
function Get-NormalizedText([string]$Path) {
    return [System.IO.File]::ReadAllText($Path).Replace("`r`n", "`n")
}
if (-not $Check) { New-Item -ItemType Directory -Path $destination -Force | Out-Null }
foreach ($name in $names) {
    $source = Join-Path $root "contracts/examples/$name"
    $target = Join-Path $destination $name
    if (-not $Check) { Copy-Item -LiteralPath $source -Destination $target }
    if (-not (Test-Path -LiteralPath $target)) { throw "Missing mock resource: $name" }
    if (-not [string]::Equals(
        (Get-NormalizedText $source),
        (Get-NormalizedText $target),
        [System.StringComparison]::Ordinal
    )) {
        throw "Mock resource differs from contract: $name"
    }
    Write-Output "PASS mock resource $name"
}
