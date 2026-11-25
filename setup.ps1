[CmdletBinding()]
param(
    [string]$PythonExecutable,
    [switch]$AllowExperimentalPython314,
    [string]$ReportPath
)

$ErrorActionPreference = 'Stop'
$RepoRoot = [System.IO.Path]::GetFullPath($PSScriptRoot)
$OriginalSystemDirectory = [System.Environment]::CurrentDirectory
[System.Environment]::CurrentDirectory = $RepoRoot
$VenvDirectory = Join-Path $RepoRoot '.venv'
$VenvPython = Join-Path $RepoRoot '.venv\Scripts\python.exe'
$BrowserDirectory = Join-Path $RepoRoot '.pw-browsers'
$env:PLAYWRIGHT_BROWSERS_PATH = $BrowserDirectory
$RequiredFiles = @('app.py', 'archiver.py', 'requirements.txt', 'config.example.json')
$Step = 'repository validation'
$SelectedPython = $null
$VersionText = $null
$Report = [ordered]@{
    status = 'RUNNING'
    repository = $RepoRoot
    started_at = (Get-Date).ToString('o')
    python = $null
    version = $null
    steps = [ordered]@{}
}

function Save-Report {
    if (-not $script:ReportPath) { return }
    $parent = Split-Path -Parent $script:ReportPath
    if ($parent -and -not (Test-Path -LiteralPath $parent)) {
        New-Item -ItemType Directory -Path $parent -Force | Out-Null
    }
    $script:Report | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $script:ReportPath -Encoding utf8
}

function Get-PythonVersion([string]$Path) {
    $raw = & $Path -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}')" 2>&1
    if ($LASTEXITCODE -ne 0) { throw "Pythonを起動できません: $raw" }
    return [string]$raw
}

function Test-AllowedPython([string]$Path, [switch]$Explicit) {
    $version = Get-PythonVersion $Path
    $parts = $version.Split('.')
    $minor = [int]$parts[1]
    if ($parts[0] -ne '3' -or $minor -lt 12 -or $minor -gt 13) {
        if (-not ($minor -eq 14 -and $AllowExperimentalPython314)) {
            throw "Python $version はこの起動手順の検証対象外です。Python 3.13を優先し、次に3.12を使用します。Python 3.14を試す場合だけ -AllowExperimentalPython314 を指定し、テスト・Chromium起動が全て成功する必要があります。既存環境は変更していません。"
        }
    }
    return $version
}

try {
    Push-Location $RepoRoot
    foreach ($name in $RequiredFiles) {
        if (-not (Test-Path -LiteralPath (Join-Path $RepoRoot $name) -PathType Leaf)) {
            throw "必須ファイルがありません: $name。このsetup.ps1をWeb Evidence Archiverのリポジトリから実行してください。"
        }
    }
    $Report.steps.repository = 'PASS'

    $Step = 'Python selection'
    if (Test-Path -LiteralPath $VenvPython -PathType Leaf) {
        $SelectedPython = $VenvPython
        $VersionText = Test-AllowedPython $SelectedPython
    } else {
        $candidates = [System.Collections.Generic.List[string]]::new()
        if ($PythonExecutable) { $candidates.Add((Resolve-Path -LiteralPath $PythonExecutable).Path) }
        $launcher = Get-Command py -ErrorAction SilentlyContinue
        if ($launcher) {
            foreach ($minor in @(13, 12)) {
                try {
                    & $launcher.Source "-3.$minor" -c "import sys; raise SystemExit(0 if sys.version_info[:2] == (3, $minor) else 1)" 2>$null
                    if ($LASTEXITCODE -eq 0) { $candidates.Add("py -3.$minor") }
                } catch { }
            }
        }
        foreach ($minor in @(13, 12)) {
            $local = Join-Path $env:LOCALAPPDATA "Programs\Python\Python$minor\python.exe"
            if (Test-Path -LiteralPath $local -PathType Leaf) { $candidates.Add($local) }
        }
        if ($AllowExperimentalPython314) {
            if ($launcher) {
                try {
                    & $launcher.Source -3.14 -c "import sys; raise SystemExit(0 if sys.version_info[:2] == (3, 14) else 1)" 2>$null
                    if ($LASTEXITCODE -eq 0) { $candidates.Add('py -3.14') }
                } catch { }
            }
            if (Test-Path -LiteralPath 'C:\Python314\python.exe') { $candidates.Add('C:\Python314\python.exe') }
        }
        if (-not $candidates.Count) {
            throw 'Python 3.13/3.12が見つかりません。Python 3.14は初期設定では使用しません。必要なら -AllowExperimentalPython314 を指定して動作検証してください。'
        }
        $chosen = $candidates[0]
        if ($chosen.StartsWith('py ')) {
            $spec = $chosen.Substring(3)
            $VersionText = (& $launcher.Source $spec -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}')").Trim()
            & $launcher.Source $spec -m venv $VenvDirectory
        } else {
            $VersionText = Test-AllowedPython $chosen
            & $chosen -m venv $VenvDirectory
        }
        if ($LASTEXITCODE -ne 0 -or -not (Test-Path -LiteralPath $VenvPython -PathType Leaf)) {
            throw '仮想環境を作成できませんでした。Pythonのインストールを修復してから再実行してください。'
        }
        $SelectedPython = $VenvPython
        $VersionText = Test-AllowedPython $SelectedPython
    }
    $Report.python = $SelectedPython
    $Report.version = $VersionText
    $Report.steps.python = 'PASS'

    $Step = 'dependency install'
    & $VenvPython -m pip --version
    if ($LASTEXITCODE -ne 0) { throw 'venv内pipを起動できません。setup.ps1を再実行するか、Python venv機能を修復してください。' }
    & $VenvPython -m pip install -r (Join-Path $RepoRoot 'requirements.txt')
    if ($LASTEXITCODE -ne 0) { throw 'requirements.txtの依存関係を導入できません。ネットワーク接続とpipの出力を確認してください。' }
    $Report.steps.dependencies = 'PASS'

    $Step = 'Chromium install and launch'
    $browserPathProbe = @'
from pathlib import Path
from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    print(p.chromium.executable_path)
'@
    $browserPath = [string](($browserPathProbe | & $VenvPython -) | Select-Object -Last 1)
    if (-not (Test-Path -LiteralPath $browserPath -PathType Leaf)) {
        & $VenvPython -m playwright install chromium
        if ($LASTEXITCODE -ne 0) { throw 'Playwright Chromiumを導入できません。空き容量・ネットワーク・アクセス権を確認してください。' }
    }
    $probe = @'
from pathlib import Path
from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    executable = Path(p.chromium.executable_path)
    if not executable.is_file():
        raise SystemExit(f"Chromium executable missing: {executable}")
    browser = p.chromium.launch(headless=True)
    page = browser.new_page()
    page.set_content("<title>setup check</title><p>ready</p>")
    assert page.title() == "setup check"
    browser.close()
print(f"Chromium PASS: {executable}")
'@
    $probe | & $VenvPython -
    if ($LASTEXITCODE -ne 0) { throw 'Chromiumを起動できません。doctor.ps1で診断し、Chromiumを再導入してください。' }
    $Report.steps.chromium = 'PASS'

    $Step = 'application tests'
    & $VenvPython -m unittest discover -s (Join-Path $RepoRoot 'tests') -v
    if ($LASTEXITCODE -ne 0) { throw '自動テストに失敗しました。ログの失敗テストを確認してください。' }
    & $VenvPython -m compileall -q (Join-Path $RepoRoot 'app.py') (Join-Path $RepoRoot 'archiver.py')
    if ($LASTEXITCODE -ne 0) { throw 'アプリのcompileチェックに失敗しました。' }
    $Report.steps.tests = 'PASS'
    $Report.status = 'PASS'
    $Report.completed_at = (Get-Date).ToString('o')
    Save-Report
    Write-Host "セットアップ完了: $RepoRoot" -ForegroundColor Green
    Write-Host "Python: $VersionText ($SelectedPython)"
    Write-Host "起動: & `"$(Join-Path $RepoRoot 'run.ps1')`""
    if ($ReportPath) { Write-Host "レポート: $ReportPath" }
} catch {
    $Report.status = 'FAIL'
    $Report.failed_step = $Step
    $Report.error = $_.Exception.Message
    $Report.completed_at = (Get-Date).ToString('o')
    Save-Report
    Write-Error "セットアップ失敗 [$Step]。$($_.Exception.Message)"
    exit 1
} finally {
    if ((Get-Location).Path -eq $RepoRoot) { Pop-Location }
    [System.Environment]::CurrentDirectory = $OriginalSystemDirectory
}
