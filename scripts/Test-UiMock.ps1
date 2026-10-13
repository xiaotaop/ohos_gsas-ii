param([Parameter(Mandatory = $true)][string]$DevEcoHome)
$ErrorActionPreference = 'Stop'
$root = Split-Path $PSScriptRoot -Parent
$node = Join-Path $DevEcoHome 'tools\node\node.exe'
$tsc = Join-Path $DevEcoHome 'sdk\default\openharmony\ets\build-tools\ets-loader\node_modules\typescript\bin\tsc'
$source = Join-Path $root 'ui-mock\entry\src\main\ets\model\Refinement.ts'
$output = Join-Path $root 'ui-mock\build\test-model'
& $node $tsc $source --target ES2020 --module commonjs --strict --skipLibCheck --outDir $output
if ($LASTEXITCODE -ne 0) { throw 'UI model type check failed' }
# node:test also runs directly, without the test runner spawning a child process.
& $node (Join-Path $root 'tests\ui-mock.test.cjs')
if ($LASTEXITCODE -ne 0) { throw 'UI mock behavior tests failed' }
& (Join-Path $PSScriptRoot 'Sync-UiMockFixtures.ps1') -Check
