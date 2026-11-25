[CmdletBinding()]
param(
    [switch]$CheckOnly,
    [string]$PythonPath,
    [string]$ConfigPath
)

$ErrorActionPreference = 'Stop'
$RepoRoot = [System.IO.Path]::GetFullPath($PSScriptRoot)
$env:PLAYWRIGHT_BROWSERS_PATH = Join-Path $RepoRoot '.pw-browsers'
$AppPath = Join-Path $RepoRoot 'app.py'
$DefaultPython = Join-Path $RepoRoot '.venv\Scripts\python.exe'
$Python = if ($PythonPath) { $PythonPath } else { $DefaultPython }

function Stop-Run([string]$Message) {
    Write-Error "$Message`n`n準備がまだの場合は次を実行してください: & `"$(Join-Path $RepoRoot 'setup.ps1')`""
    exit 1
}

foreach ($file in @($AppPath, (Join-Path $RepoRoot 'archiver.py'), (Join-Path $RepoRoot 'requirements.txt'))) {
    if (-not (Test-Path -LiteralPath $file -PathType Leaf)) { Stop-Run "製品ファイルが見つかりません: $file" }
}
if (-not (Test-Path -LiteralPath $Python -PathType Leaf)) {
    Stop-Run "専用Python環境がありません: $Python"
}

Push-Location $RepoRoot
Write-Host "確認中: リポジトリ=$RepoRoot" -ForegroundColor Cyan
$probe = @'
import json, os
from pathlib import Path
import playwright
browser_root = Path(os.environ["PLAYWRIGHT_BROWSERS_PATH"])
metadata = Path(playwright.__file__).parent / "driver" / "package" / "browsers.json"
browsers = json.loads(metadata.read_text(encoding="utf-8"))["browsers"]
revision = next(item["revision"] for item in browsers if item["name"] == "chromium")
chrome = browser_root / f"chromium-{revision}" / "chrome-win64" / "chrome.exe"
headless = browser_root / f"chromium_headless_shell-{revision}" / "chrome-headless-shell-win64" / "chrome-headless-shell.exe"
if not chrome.is_file() or not headless.is_file():
    raise SystemExit(f"Chromium binaries missing: {chrome}; {headless}")
print("READY")
'@
$probeOutput = $probe | & $Python -
$probeExitCode = $LASTEXITCODE
Pop-Location
Write-Host "確認結果: Playwright/Chromium probe exit=$probeExitCode" -ForegroundColor Cyan
if ($probeExitCode -ne 0 -or (($probeOutput -join "`n") -notmatch 'READY')) {
    Stop-Run 'PlaywrightまたはChromiumを確認できません。setup.ps1を実行してください。'
}
if ($CheckOnly) {
    Write-Host "PATH CHECK PASS: repo=$RepoRoot python=$Python app=$AppPath"
    return
}

Push-Location $RepoRoot
try {
    Write-Host "Web Evidence Archiverを起動します: $AppPath"
    if ($ConfigPath) {
        $ResolvedConfigPath = if ([System.IO.Path]::IsPathRooted($ConfigPath)) { $ConfigPath } else { Join-Path $RepoRoot $ConfigPath }
        if (-not (Test-Path -LiteralPath $ResolvedConfigPath -PathType Leaf)) { throw "設定JSONが見つかりません: $ResolvedConfigPath" }
        & $Python $AppPath --config $ResolvedConfigPath
    } else {
        & $Python $AppPath
    }
    if ($LASTEXITCODE -ne 0) { throw "GUIが異常終了しました (exit=$LASTEXITCODE)。doctor.ps1で依存関係を確認してください。" }
} catch {
    Write-Error $_.Exception.Message
    exit 1
} finally {
    Pop-Location
}
