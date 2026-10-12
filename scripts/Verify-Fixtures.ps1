$ErrorActionPreference = 'Stop'
$fixtureDirectory = Join-Path $PSScriptRoot '..\tests\fixtures'
$expected = [ordered]@{
    'PBSO4.XRA' = 'CA2DA02FC7E17D2FC912DE22A979F8101BA6140F2E8104F9D3AA64F030CA58BB'
    'INST_XRY.PRM' = 'E59413059BC3B12A51F1C6EEBC5D581470320D05A31F11A41DBB32E16D1D16B9'
    'PBSO4.CWN' = '59462BA6D7C72C9800B0B6BF41903F9933ED5AC5ADAB101D27022D5D25CF18BA'
    'inst_d1a.prm' = 'A1031174A9B509F889377752F5C095A1DAD49A25FB0A72C057F184F7B321FCEA'
    'PbSO4-Wyckoff.cif' = '22CBA0B64FB6BF89178FE828FDF63570BFFEBED1485313E78C50C2918A47A970'
}

foreach ($name in $expected.Keys) {
    $path = Join-Path $fixtureDirectory $name
    if (-not (Test-Path -LiteralPath $path -PathType Leaf)) {
        throw "Missing fixture: $name"
    }
    $actual = (Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash
    if ($actual -ne $expected[$name]) {
        throw "Hash mismatch: $name; expected $($expected[$name]), got $actual"
    }
    Write-Output "PASS $name"
}
Write-Output 'All fixture SHA-256 checks passed.'

