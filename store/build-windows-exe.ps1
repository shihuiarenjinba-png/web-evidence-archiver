# Windows-only one-file EXE candidate, INCLUDING Chromium. Never publish or replace release artifacts.
[CmdletBinding()]
param([string]$PythonLauncher = 'py')
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
$Root = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path
if (git -C $Root status --porcelain) { throw 'Uncommitted changes exist; do not build from a dirty tree.' }
$Head = (git -C $Root rev-parse HEAD).Trim()
if ($LASTEXITCODE -ne 0 -or $Head.Length -ne 40) { throw 'Source SHA unavailable.' }
$Branch = (git -C $Root branch --show-current).Trim()
if ($Branch -ne 'ui/simple-product-flow-20261019') { throw "Wrong branch: $Branch" }
$Output = Join-Path $Root ('dist-candidate-' + $Head.Substring(0,12))
if (Test-Path -LiteralPath $Output) { throw 'This candidate already exists; never overwrite.' }
$Isolation = Join-Path $env:TEMP ('evidence-browser-build-' + [guid]::NewGuid().ToString('N'))
$PriorBrowserPath = [Environment]::GetEnvironmentVariable('PLAYWRIGHT_BROWSERS_PATH','Process')
try {
    New-Item -ItemType Directory -Path $Isolation | Out-Null
    $Venv = Join-Path $Isolation 'venv'
    & $PythonLauncher -3.12 -m venv $Venv
    if ($LASTEXITCODE -ne 0) { throw 'Python 3.12 is required.' }
    $Py = Join-Path $Venv 'Scripts\python.exe'
    & $Py -m pip install -r (Join-Path $Root 'requirements.txt') 'pyinstaller>=6,<7'
    if ($LASTEXITCODE -ne 0) { throw 'Cannot install pinned build dependencies.' }
    $env:PLAYWRIGHT_BROWSERS_PATH = '0'
    & $Py -m playwright install chromium
    if ($LASTEXITCODE -ne 0) { throw 'Unable to install isolated Chromium; do not reuse global cache.' }
    $BrowserPath = (& $Py -c "from pathlib import Path; import playwright; print(Path(playwright.__file__).parent / 'driver' / 'package' / '.local-browsers')").Trim()
    if (-not (Test-Path -LiteralPath $BrowserPath -PathType Container)) {
        throw 'Playwright Chromium bundle missing from the isolated package.'
    }
    Push-Location $Root
    try {
        & $Py -m compileall -q app.py archiver.py gui_capture_plan.py tests
        if ($LASTEXITCODE -ne 0) { throw 'Source syntax regression failed.' }
        & $Py -m unittest discover -s tests -p 'test*.py' -v
        if ($LASTEXITCODE -ne 0) { throw 'Browser-mock regression failed; EXE build blocked.' }
        & $Py -m PyInstaller --noconfirm --clean --onefile --windowed --name WebEvidenceArchiver --collect-all playwright --add-data "$BrowserPath;playwright/driver/package/.local-browsers" --distpath $Output --workpath (Join-Path $Isolation 'work') --specpath (Join-Path $Isolation 'spec') app.py
        if ($LASTEXITCODE -ne 0) { throw 'PyInstaller browser build failed.' }
    } finally { Pop-Location }
    $Exe = Join-Path $Output 'WebEvidenceArchiver.exe'
    if (-not (Test-Path -LiteralPath $Exe -PathType Leaf)) { throw 'No offline-capable EXE was built.' }
    $Digest = (Get-FileHash -LiteralPath $Exe -Algorithm SHA256).Hash
    Write-Host "BUILT FOR QA ONLY: $Exe / SHA256 $Digest / Source $Head"
    Write-Host 'MANDATORY: disconnected Windows launch and actual offline Chromium test; MakeAppx alone does not prove browser presence.'
} finally {
    [Environment]::SetEnvironmentVariable('PLAYWRIGHT_BROWSERS_PATH',$PriorBrowserPath,'Process')
    if (Test-Path -LiteralPath $Isolation) { Remove-Item -LiteralPath $Isolation -Recurse -Force }
}
