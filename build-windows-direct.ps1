param(
    [string]$ProductName = "Web-Evidence-Archiver",
    [string]$Version = "1.0.0"
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $Root
$BuildRoot = Join-Path $Root ".rc-build"
$Venv = Join-Path $BuildRoot "venv"
$Artifacts = Join-Path $Root "artifacts"
$Dist = Join-Path $Root "dist"
$BuildDir = Join-Path $Root "build"

function Remove-IfExists([string]$Path) {
    if (Test-Path $Path) { Remove-Item -LiteralPath $Path -Recurse -Force }
}

function Assert-NoCredentialMaterial {
    $excluded = @(".git", ".venv", ".rc-build", "dist", "build", "artifacts", "__pycache__")
    $extensions = @(".py", ".json", ".yaml", ".yml", ".toml", ".ini", ".cfg", ".txt", ".md", ".ps1", ".cmd")
    $patterns = @(
        'AIza[0-9A-Za-z_\-]{25,}',
        '-----BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY-----',
        '"private_key"\s*:\s*"',
        '"client_secret"\s*:\s*"[^"$]',
        '"refresh_token"\s*:\s*"[^"$]'
    )
    $files = Get-ChildItem -Path $Root -Recurse -File | Where-Object {
        $full = $_.FullName
        $blocked = $false
        foreach ($name in $excluded) {
            $needle = [IO.Path]::DirectorySeparatorChar + $name + [IO.Path]::DirectorySeparatorChar
            if ($full.Contains($needle)) { $blocked = $true; break }
        }
        (-not $blocked) -and ($extensions -contains $_.Extension.ToLowerInvariant())
    }
    foreach ($file in $files) {
        $text = Get-Content -LiteralPath $file.FullName -Raw -ErrorAction SilentlyContinue
        if ($null -eq $text) { continue }
        foreach ($pattern in $patterns) {
            if ($text -match $pattern) {
                throw "Potential credential material detected in $($file.FullName)."
            }
        }
    }
}

Write-Host "== RC preflight =="
Assert-NoCredentialMaterial

Remove-IfExists $BuildRoot
Remove-IfExists $Dist
Remove-IfExists $BuildDir
Remove-IfExists $Artifacts
New-Item -ItemType Directory -Path $BuildRoot, $Artifacts | Out-Null

Write-Host "== Python environment =="
py -3.12 -m venv $Venv
$Python = Join-Path $Venv "Scripts\python.exe"
& $Python -m pip install --upgrade pip
& $Python -m pip install -r (Join-Path $Root "requirements.txt")

Write-Host "== Source tests =="
& $Python -m unittest discover -s tests -v
if ($LASTEXITCODE -ne 0) { throw "Source tests failed." }

Write-Host "== Dependency snapshot =="
& $Python -m pip freeze | Set-Content -LiteralPath (Join-Path $Artifacts "runtime-requirements-lock.txt") -Encoding UTF8

Write-Host "== One-file Windows EXE build =="
& $Python -m pip install "pyinstaller>=6,<7"
$Args = @(
    "--noconfirm",
    "--clean",
    "--onefile",
    "--windowed",
    "--collect-all", "playwright",
    "--name", $ProductName,
    (Join-Path $Root "app.py")
)
& $Python -m PyInstaller @Args
if ($LASTEXITCODE -ne 0) { throw "PyInstaller build failed." }

$Exe = Join-Path $Dist "$ProductName.exe"
if (-not (Test-Path $Exe)) { throw "Built executable was not found: $Exe" }

Write-Host "== Release dependency evidence =="
& $Python "$Root\release_metadata.py" --output $Artifacts --product $ProductName --version $Version
if ($LASTEXITCODE -ne 0) { throw "Release metadata generation failed." }
Copy-Item -LiteralPath (Join-Path $Root "LICENSE_PENDING_APPROVAL.txt") -Destination (Join-Path $Artifacts "LICENSE_PENDING_APPROVAL.txt") -Force
Copy-Item -LiteralPath (Join-Path $Root "LICENSE_CANDIDATE_FOR_OWNER_APPROVAL.txt") -Destination (Join-Path $Artifacts "LICENSE_CANDIDATE_FOR_OWNER_APPROVAL.txt") -Force
$SourceCommit = (& git -C $Root rev-parse HEAD).Trim()
@(
    "Product=$ProductName"
    "Version=$Version"
    "SourceCommit=$SourceCommit"
    "SalesRelease=NO"
    "LicenseStatus=OWNER_APPROVAL_REQUIRED"
) | Set-Content -LiteralPath (Join-Path $Artifacts "VERSION.txt") -Encoding UTF8

Write-Host "== Packaged Playwright / Edge runtime self-test =="
$SelfTest = Start-Process -FilePath $Exe -ArgumentList "--self-test-browser" -PassThru -WindowStyle Hidden
if (-not $SelfTest.WaitForExit(60000)) {
    Stop-Process -Id $SelfTest.Id -Force -ErrorAction SilentlyContinue
    throw "Packaged browser runtime self-test timed out."
}
if ($SelfTest.ExitCode -ne 0) {
    throw "Packaged browser runtime self-test failed with code $($SelfTest.ExitCode)."
}

Write-Host "== Packaged GUI startup smoke test =="
$Process = Start-Process -FilePath $Exe -PassThru -WindowStyle Hidden
try {
    Start-Sleep -Seconds 5
    if ($Process.HasExited) {
        throw "Packaged executable exited during startup with code $($Process.ExitCode)."
    }
}
finally {
    if ($Process -and -not $Process.HasExited) {
        Stop-Process -Id $Process.Id -Force -ErrorAction SilentlyContinue
        $Process.WaitForExit()
    }
    Get-CimInstance Win32_Process | Where-Object { $_.ExecutablePath -eq $Exe } | ForEach-Object {
        Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue
    }
}

$TargetExe = Join-Path $Artifacts "$ProductName-RC.exe"
Copy-Item -LiteralPath $Exe -Destination $TargetExe -Force
Copy-Item -LiteralPath (Join-Path $Root "README.md") -Destination (Join-Path $Artifacts "$ProductName-README.md") -Force
Copy-Item -LiteralPath (Join-Path $Root "START_HERE.html") -Destination (Join-Path $Artifacts "START_HERE.html") -Force
Copy-Item -LiteralPath (Join-Path $Root "config.example.json") -Destination (Join-Path $Artifacts "config.example.json") -Force
$Hash = (Get-FileHash -Algorithm SHA256 -LiteralPath $TargetExe).Hash.ToLowerInvariant()
"$Hash  $([IO.Path]::GetFileName($TargetExe))" | Set-Content -LiteralPath "$TargetExe.sha256" -Encoding ASCII

Write-Host "== Final artifact checks =="
if ((Get-Item $TargetExe).Length -le 0) { throw "EXE artifact is empty." }
Assert-NoCredentialMaterial

Write-Host ""
Write-Host "RC_BUILD_PASS"
Write-Host "EXE: $TargetExe"
Write-Host "SHA256: $Hash"
