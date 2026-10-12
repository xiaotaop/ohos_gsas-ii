param(
    [Parameter(Mandatory = $true)]
    [string]$Python,

    [string]$DllDirectory,

    [string]$Output = "poc/results/local-result.json"
)

$ErrorActionPreference = 'Stop'
$repoRoot = Split-Path $PSScriptRoot -Parent
$runner = Join-Path $repoRoot 'poc\core_refinement.py'
$fixtures = Join-Path $repoRoot 'tests\fixtures'
$outputPath = Join-Path $repoRoot $Output

$pocArguments = @($runner, '--fixtures', $fixtures, '--output', $outputPath)
if ($DllDirectory) {
    $pocArguments += @('--dll-dir', $DllDirectory)
}

& $Python @pocArguments
if ($LASTEXITCODE -ne 0) {
    throw "GSAS-II core PoC failed with exit code $LASTEXITCODE"
}
