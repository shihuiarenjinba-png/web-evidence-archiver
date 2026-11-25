[CmdletBinding()]
param(
    [string]$ReportPath,
    [string]$SetupReportPath
)

$ErrorActionPreference = 'Continue'
$RepoRoot = [System.IO.Path]::GetFullPath($PSScriptRoot)
$env:PLAYWRIGHT_BROWSERS_PATH = Join-Path $RepoRoot '.pw-browsers'
Push-Location $RepoRoot
$Python = Join-Path $RepoRoot '.venv\Scripts\python.exe'
$configPath = Join-Path $RepoRoot 'config.example.json'
$checks = [ordered]@{}
$Report = [ordered]@{
    repository = $RepoRoot
    checked_at = (Get-Date).ToString('o')
    python = $null
    checks = $checks
}

foreach ($name in @('app.py', 'archiver.py', 'requirements.txt', 'config.example.json')) {
    $checks[$name] = Test-Path -LiteralPath (Join-Path $RepoRoot $name) -PathType Leaf
}
$checks.venv = Test-Path -LiteralPath $Python -PathType Leaf
$checks.pip = $false
$checks.playwright = $false
$checks.chromium_file = $false
$checks.chromium_launch = 'NOT_TESTED'
$checks.setup_launch_receipt = $false
$checks.output_directory = 'NOT_TESTED'

if ($checks.venv) {
    $version = & $Python -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}')" 2>&1
    $Report.python = [string]$version
    & $Python -m pip --version *> $null
    $checks.pip = ($LASTEXITCODE -eq 0)
    $browserProbe = @'
import json, os
from pathlib import Path
import playwright
metadata = Path(playwright.__file__).parent / "driver" / "package" / "browsers.json"
browsers = json.loads(metadata.read_text(encoding="utf-8"))["browsers"]
revision = next(item["revision"] for item in browsers if item["name"] == "chromium")
root = Path(os.environ["PLAYWRIGHT_BROWSERS_PATH"])
chrome = root / f"chromium-{revision}" / "chrome-win64" / "chrome.exe"
headless = root / f"chromium_headless_shell-{revision}" / "chrome-headless-shell-win64" / "chrome-headless-shell.exe"
print(json.dumps({"chrome": str(chrome), "headless": str(headless)}))
'@
    $browserOutput = $browserProbe | & $Python - 2>&1
    if ($LASTEXITCODE -eq 0) {
        $checks.playwright = $true
        try {
            $browserInfo = (($browserOutput | Select-Object -Last 1) | ConvertFrom-Json)
            $chromePath = [string]$browserInfo.chrome
            $headlessPath = [string]$browserInfo.headless
            $Report.chromium_executable = $chromePath
            $checks.chromium_file = (Test-Path -LiteralPath $chromePath -PathType Leaf) -and (Test-Path -LiteralPath $headlessPath -PathType Leaf)
            if ($checks.chromium_file -and $SetupReportPath -and (Test-Path -LiteralPath $SetupReportPath -PathType Leaf)) {
                $setupReceipt = Get-Content -LiteralPath $SetupReportPath -Raw | ConvertFrom-Json
                $checks.setup_launch_receipt = ($setupReceipt.status -eq 'PASS' -and $setupReceipt.steps.chromium -eq 'PASS')
                $checks.chromium_launch = if ($checks.setup_launch_receipt) { "PASS_FROM_SETUP_REPORT: $($setupReceipt.completed_at)" } else { 'FAIL: setup report does not record Chromium launch PASS' }
            } elseif ($checks.chromium_file) {
                $checks.chromium_launch = 'NOT_VERIFIED: provide -SetupReportPath from setup.ps1; binary presence alone is insufficient.'
            } else { $checks.chromium_launch = 'NOT_RUN: Chromium executable missing' }
        } catch {
            $checks.chromium_file = $false
                    $checks.chromium_launch = "FAIL: $($_.Exception.Message)"
        }
    } elseif (($browserOutput -join "`n") -match 'No module named .playwright') {
        $checks.playwright = $false
        $checks.chromium_file = $false
    } else {
        $checks.playwright = $true
        $checks.chromium_file = $false
        $Report.browser_error = $browserOutput -join "`n"
    }
}

try {
    $config = Get-Content -LiteralPath $configPath -Raw | ConvertFrom-Json
    $outputDir = [string]$config.output_dir
    $resolvedOutput = if ([System.IO.Path]::IsPathRooted($outputDir)) { $outputDir } else { Join-Path $RepoRoot $outputDir }
    if (Test-Path -LiteralPath $resolvedOutput -PathType Container) {
        $probePath = Join-Path $resolvedOutput ('.doctor-' + [guid]::NewGuid().ToString('N') + '.tmp')
        try {
            [System.IO.File]::WriteAllText($probePath, 'write check')
            Remove-Item -LiteralPath $probePath -Force
            $checks.output_directory = 'WRITE_ACCESS_PASS'
        } catch {
            if (Test-Path -LiteralPath $probePath) { Remove-Item -LiteralPath $probePath -Force -ErrorAction SilentlyContinue }
            $checks.output_directory = "WRITE_ACCESS_FAIL: $($_.Exception.Message)"
        }
    } else {
        $checks.output_directory = "NOT_CREATED; parent exists=$(Test-Path -LiteralPath (Split-Path -Parent $resolvedOutput))"
    }
    $Report.output_directory = $resolvedOutput
} catch {
    $checks.config_validation = "FAIL: $($_.Exception.Message)"
}

$ready = ($checks['app.py'] -and $checks['archiver.py'] -and $checks['requirements.txt'] -and $checks['config.example.json'] -and $checks.venv -and $checks.pip -and $checks.playwright -and $checks.chromium_file -and $checks.setup_launch_receipt)
$Report.startup_ready = [bool]$ready
$Report.next_command = if ($ready) { "& `"$(Join-Path $RepoRoot 'run.ps1')`"" } else { "& `"$(Join-Path $RepoRoot 'setup.ps1')`"" }
$Report | ConvertTo-Json -Depth 8
if ($ReportPath) {
    $parent = Split-Path -Parent $ReportPath
    if ($parent -and -not (Test-Path -LiteralPath $parent)) { New-Item -ItemType Directory -Path $parent -Force | Out-Null }
    $Report | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $ReportPath -Encoding utf8
    Write-Host "診断レポート: $ReportPath"
}
if (-not $ready) {
    Write-Host "起動準備未完了です。次の手順: $($Report.next_command)" -ForegroundColor Yellow
    Pop-Location
    exit 1
}
Write-Host "起動準備完了です: $($Report.next_command)" -ForegroundColor Green
Pop-Location
