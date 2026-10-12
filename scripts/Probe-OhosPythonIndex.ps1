param(
    [string]$IndexUrl = "https://pypi.cnb.cool/OpenHarmonyPCDeveloper/pypi/-/packages/simple",
    [string[]]$Packages = @("gsas-ii", "pycifrw", "numpy", "scipy"),
    [string]$Output = "poc/results/ohos-python-index.json"
)

$ErrorActionPreference = "Stop"
$records = @()

foreach ($package in $Packages) {
    $packageUrl = "$($IndexUrl.TrimEnd('/'))/$package/"
    $statusCode = 0
    $filenames = @()
    $errorMessage = $null

    try {
        $response = Invoke-WebRequest -UseBasicParsing -Uri $packageUrl -TimeoutSec 30
        $statusCode = [int]$response.StatusCode
        $matches = [regex]::Matches($response.Content, 'href=["''](?<href>[^"'']+)["'']')
        $filenames = @(
            $matches |
                ForEach-Object { [System.Uri]::UnescapeDataString(($_.Groups['href'].Value -split '/')[-1].Split('#')[0]) } |
                Where-Object { $_ }
        )
    }
    catch {
        $errorMessage = $_.Exception.Message
        if ($_.Exception.Response -and $_.Exception.Response.StatusCode) {
            $statusCode = [int]$_.Exception.Response.StatusCode
        }
    }

    $ohosWheels = @($filenames | Where-Object { $_ -match '-ohos_aarch64\.whl$' })
    $records += [ordered]@{
        package = $package
        url = $packageUrl
        status_code = $statusCode
        project_present = ($statusCode -eq 200)
        ohos_aarch64_wheel_count = $ohosWheels.Count
        ohos_aarch64_wheels = $ohosWheels
        error = $errorMessage
    }
}

$result = [ordered]@{
    schema_version = 1
    generated_at = [DateTime]::UtcNow.ToString("o")
    index_url = $IndexUrl
    packages = $records
}

$outputPath = [System.IO.Path]::GetFullPath((Join-Path (Get-Location) $Output))
$outputDirectory = Split-Path -Parent $outputPath
[System.IO.Directory]::CreateDirectory($outputDirectory) | Out-Null
$json = $result | ConvertTo-Json -Depth 8
[System.IO.File]::WriteAllText($outputPath, $json + [Environment]::NewLine, [System.Text.UTF8Encoding]::new($false))
Write-Host "HarmonyOS Python index probe written to $outputPath"
