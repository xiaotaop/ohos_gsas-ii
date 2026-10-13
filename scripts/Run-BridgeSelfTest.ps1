param(
    [string]$Python,
    [string]$DllDirectory
)

# Member B bridge self-test (docs/TEAM_ASSIGNMENT.md §5.3).
#   Without -Python: stdlib-only fake-core scenarios (real GSAS test skips).
#   With -Python:    point at an interpreter that has GSAS-II/NumPy/SciPy to
#                    include the real five-stage PbSO4 run; pass the MinGW
#                    bin directory via -DllDirectory on Windows.

$ErrorActionPreference = 'Stop'
$repoRoot = Split-Path $PSScriptRoot -Parent

if ($Python) {
    $exe = $Python
    if ($DllDirectory) { $env:GSAS_DLL_DIRS = $DllDirectory }
} else {
    $exe = "py"
}

Push-Location $repoRoot
try {
    & $exe -m unittest discover -s bridge/tests -t . -v
} finally {
    Pop-Location
}
if ($LASTEXITCODE -ne 0) {
    throw "Bridge self-test failed with exit code $LASTEXITCODE"
}
