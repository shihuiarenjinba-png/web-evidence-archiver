#requires -Version 5.1
# Produce an UNSIGNED MSIX Store upload candidate. Never publish or install.
# All generated artifacts and Python environments are isolated by unique directory.
[CmdletBinding()]
param([switch]$PreflightOnly, [string]$PythonExe = "python")
$ErrorActionPreference = "Stop"
$root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$cfgPath = Join-Path $PSScriptRoot "product.json"
$identityPath = Join-Path $PSScriptRoot "partner_center_registration.json"
if (-not (Test-Path -LiteralPath $cfgPath) -or -not (Test-Path -LiteralPath $identityPath)) {
    throw "Missing store/product.json or partner_center_registration.json"
}
$cfg = Get-Content -LiteralPath $cfgPath -Raw -Encoding UTF8 | ConvertFrom-Json
$registration = Get-Content -LiteralPath $identityPath -Raw -Encoding UTF8 | ConvertFrom-Json
if ([Environment]::OSVersion.Platform -ne [PlatformID]::Win32NT -or -not [Environment]::Is64BitOperatingSystem) {
    throw "Windows x64 is required to generate a Windows MSIX."
}
if ($cfg.exeName -notmatch '^[A-Za-z][A-Za-z0-9_-]{2,50}$' -or
    $cfg.appId -notmatch '^[A-Za-z][A-Za-z0-9]{2,48}$' -or
    $cfg.entryPoint -notmatch '^[A-Za-z][A-Za-z0-9_-]*\.py$') {
    throw "Unsafe or missing store/product.json exeName, appId or entryPoint."
}
if ($registration.repository -cne (Split-Path $root -Leaf) -or $cfg.displayName -cne $registration.displayName) {
    throw "Store registration belongs to a different product/repository."
}
$entry = Join-Path $root $cfg.entryPoint
if (-not (Test-Path -LiteralPath $entry)) { throw "App entrypoint missing: $entry" }
$identity = $registration.storeIdentity
foreach ($key in @("storeId","packageIdentityName","packageIdentityPublisher","publisherDisplayName","packageFamilyName")) {
    if ([string]::IsNullOrWhiteSpace($identity.$key)) {
        throw "Official Partner Center Identity is not recorded: $key. No placeholder permitted."
    }
}
if ($registration.partnerCenterState -notin @("EXISTING_CONFIRMED","RESERVED_CONFIRMED","SUBMISSION_DRAFT_CONFIRMED")) {
    throw "Partner Center product state is not confirmed. Check for duplicate products first."
}
$envFields = @{
    "STORE_IDENTITY_NAME" = $identity.packageIdentityName
    "STORE_PUBLISHER" = $identity.packageIdentityPublisher
    "STORE_PUBLISHER_DISPLAY_NAME" = $identity.publisherDisplayName
}
foreach ($key in $envFields.Keys) {
    if ([Environment]::GetEnvironmentVariable($key) -cne [string]$envFields[$key]) {
        throw "Environment $key must exactly match the recorded official Identity."
    }
}
if ($env:STORE_IDENTITY_CONFIRMED -cne "YES" -or $env:STORE_BRAND_APPROVED -cne "YES") {
    throw "Identity and artwork must be explicitly verified and approved."
}
if ($env:STORE_IDENTITY_NAME -notmatch '^[A-Za-z0-9.-]{3,70}$' -or
    $env:STORE_PUBLISHER -notmatch '^CN=.' -or
    $env:STORE_VERSION -notmatch '^\d+\.\d+\.\d+\.0$') {
    throw "Invalid official identity or STORE_VERSION (expected x.y.z.0)."
}
$versionParts = @($env:STORE_VERSION.Split(".") | ForEach-Object { [int]$_ })
if ($versionParts[0] -lt 1 -or @($versionParts | Where-Object { $_ -gt 65535 }).Count -gt 0) {
    throw "Version component out of Store candidate range."
}
$assets = @(
    @("StoreLogo.png",50,50),
    @("Square44x44Logo.png",44,44),
    @("Square150x150Logo.png",150,150),
    @("Wide310x150Logo.png",310,150)
)
Add-Type -AssemblyName System.Drawing
foreach ($a in $assets) {
    $p = Join-Path $PSScriptRoot ("assets\" + $a[0])
    if (-not (Test-Path -LiteralPath $p)) { throw "Approved PNG missing: $p" }
    $img = [System.Drawing.Image]::FromFile($p)
    try {
        if ($img.Width -ne [int]$a[1] -or $img.Height -ne [int]$a[2]) {
            throw "Wrong logo dimensions: $p"
        }
    } finally { $img.Dispose() }
}
if ($cfg.needsBundledBrowser) {
    throw "HOLD: Playwright Chromium offline bundle and runtime discovery have not been verified. Do not create an incomplete Web Evidence Archiver MSIX."
}
$sdk = Join-Path ([Environment]::GetFolderPath("ProgramFilesX86")) "Windows Kits\10\bin"
$makeappx = Get-ChildItem -Path $sdk -Filter makeappx.exe -Recurse -File -ErrorAction SilentlyContinue |
    Where-Object { $_.DirectoryName -match '\\x64$' } | Sort-Object FullName -Descending | Select-Object -First 1
if (-not $makeappx) { throw "Windows SDK x64 makeappx.exe not found." }
if ($PreflightOnly) {
    Write-Host "MSIX_PREFLIGHT_PASS_NO_PACKAGE: $($cfg.displayName)"
    return
}
$tag = (Get-Date -Format "yyyyMMdd-HHmmss") + "-" + [Guid]::NewGuid().ToString("N").Substring(0,8)
$out = Join-Path $root ("store-output\" + $tag)
$venv = Join-Path $out "venv"
$dist = Join-Path $out "dist"
$work = Join-Path $out "work"
$spec = Join-Path $out "spec"
$stage = Join-Path $out "stage"
New-Item -ItemType Directory -Path $out,$dist,$work,$spec,$stage -Force | Out-Null
$oldPyc = $env:PYTHONPYCACHEPREFIX
$oldNoBytecode = $env:PYTHONDONTWRITEBYTECODE
$env:PYTHONPYCACHEPREFIX = Join-Path $out "pycache"
$env:PYTHONDONTWRITEBYTECODE = "1"
Push-Location -LiteralPath $root
try {
    $sha = (& git rev-parse HEAD | Out-String).Trim()
    if ($LASTEXITCODE -ne 0 -or $sha -notmatch '^[0-9a-f]{40}$') {
        throw "Git commit SHA not verified."
    }
    & $PythonExe -m venv $venv
    if ($LASTEXITCODE -ne 0) { throw "Isolated Python venv failed." }
    $python = Join-Path $venv "Scripts\python.exe"
    if (-not (Test-Path -LiteralPath $python)) { throw "Python venv executable missing." }
    $v = (& $python --version 2>&1 | Out-String).Trim()
    if ($v -notmatch '^Python 3\.11\.') { throw "Python 3.11 is required for baseline build: $v" }
    $requirements = Join-Path $root "requirements.txt"
    if (Test-Path -LiteralPath $requirements) {
        & $python -m pip install -r $requirements
        if ($LASTEXITCODE -ne 0) { throw "Python dependency installation failed." }
    }
    & $python -m pip install "pyinstaller==6.16.0"
    if ($LASTEXITCODE -ne 0) { throw "PyInstaller installation failed." }
    & $python -m unittest discover -s tests -p "test*.py" -v
    if ($LASTEXITCODE -ne 0) { throw "Full unit regression failed; MSIX not generated." }
    & $python -m compileall -q $cfg.entryPoint
    if ($LASTEXITCODE -ne 0) { throw "Python syntax check failed." }
    & $python -m PyInstaller --clean --noconfirm --windowed --onedir --name $cfg.exeName --distpath $dist --workpath $work --specpath $spec $entry
    if ($LASTEXITCODE -ne 0) { throw "PyInstaller failed." }
    $exe = Join-Path (Join-Path $dist $cfg.exeName) ($cfg.exeName + ".exe")
    if (-not (Test-Path -LiteralPath $exe)) { throw "Built GUI EXE is missing." }
    $app = Join-Path $stage "App"
    $assetDir = Join-Path $stage "Assets"
    New-Item -ItemType Directory -Path $app,$assetDir -Force | Out-Null
    Copy-Item -Path (Join-Path (Join-Path $dist $cfg.exeName) "*") -Destination $app -Recurse -Force
    foreach ($a in $assets) {
        Copy-Item -LiteralPath (Join-Path $PSScriptRoot ("assets\" + $a[0])) -Destination $assetDir
    }
    $xmlEscape = { param([string]$value) [Security.SecurityElement]::Escape($value) }
    $manifest = @'
<?xml version="1.0" encoding="utf-8"?>
<Package xmlns="http://schemas.microsoft.com/appx/manifest/foundation/windows10" xmlns:uap="http://schemas.microsoft.com/appx/manifest/uap/windows10" xmlns:rescap="http://schemas.microsoft.com/appx/manifest/foundation/windows10/restrictedcapabilities" IgnorableNamespaces="uap rescap">
<Identity Name="{{NAME}}" Publisher="{{PUBLISHER}}" Version="{{VERSION}}" ProcessorArchitecture="x64"/>
<Properties><DisplayName>{{DISPLAY}}</DisplayName><PublisherDisplayName>{{PUBLISHER_DISPLAY}}</PublisherDisplayName><Logo>Assets\StoreLogo.png</Logo></Properties>
<Dependencies><TargetDeviceFamily Name="Windows.Desktop" MinVersion="10.0.19041.0" MaxVersionTested="10.0.26100.0"/></Dependencies>
<Resources><Resource Language="ja-jp"/></Resources>
<Applications><Application Id="{{APPID}}" Executable="App\{{EXE}}.exe" EntryPoint="Windows.FullTrustApplication"><uap:VisualElements DisplayName="{{DISPLAY}}" Description="{{DISPLAY}}" BackgroundColor="transparent" Square150x150Logo="Assets\Square150x150Logo.png" Square44x44Logo="Assets\Square44x44Logo.png"><uap:DefaultTile Wide310x150Logo="Assets\Wide310x150Logo.png"/></uap:VisualElements></Application></Applications>
<Capabilities><rescap:Capability Name="runFullTrust"/></Capabilities>
</Package>
'@
    $tokens = @{
        "{{NAME}}" = (& $xmlEscape $identity.packageIdentityName)
        "{{PUBLISHER}}" = (& $xmlEscape $identity.packageIdentityPublisher)
        "{{PUBLISHER_DISPLAY}}" = (& $xmlEscape $identity.publisherDisplayName)
        "{{DISPLAY}}" = (& $xmlEscape $cfg.displayName)
        "{{VERSION}}" = $env:STORE_VERSION
        "{{APPID}}" = (& $xmlEscape $cfg.appId)
        "{{EXE}}" = (& $xmlEscape $cfg.exeName)
    }
    foreach ($token in $tokens.Keys) { $manifest = $manifest.Replace($token,[string]$tokens[$token]) }
    $manifestPath = Join-Path $stage "AppxManifest.xml"
    [IO.File]::WriteAllText($manifestPath,$manifest,(New-Object Text.UTF8Encoding($false)))
    [xml]$parsed = Get-Content -LiteralPath $manifestPath -Raw -Encoding UTF8
    $parsedIdentity = $parsed.SelectSingleNode("/*[local-name()='Package']/*[local-name()='Identity']")
    if ($parsedIdentity.GetAttribute("Name") -cne $identity.packageIdentityName -or
        $parsedIdentity.GetAttribute("Publisher") -cne $identity.packageIdentityPublisher -or
        $parsedIdentity.GetAttribute("Version") -cne $env:STORE_VERSION) {
        throw "Generated MSIX manifest Identity does not match Partner Center."
    }
    $msix = Join-Path $out ($cfg.exeName + "_" + $env:STORE_VERSION + "_x64.msix")
    & $makeappx.FullName pack /d $stage /p $msix
    if ($LASTEXITCODE -ne 0 -or -not (Test-Path -LiteralPath $msix)) { throw "MakeAppx failed." }
    Add-Type -AssemblyName System.IO.Compression.FileSystem
    $zip = [IO.Compression.ZipFile]::OpenRead($msix)
    try {
        if (-not $zip.GetEntry("AppxManifest.xml") -or -not $zip.GetEntry("App/" + $cfg.exeName + ".exe")) {
            throw "MSIX is missing required files."
        }
    } finally { $zip.Dispose() }
    $audit = [ordered]@{
        product = $cfg.displayName
        storeId = $identity.storeId
        identity = $identity.packageIdentityName
        publisher = $identity.packageIdentityPublisher
        version = $env:STORE_VERSION
        sourceCommit = $sha
        msixPath = $msix
        sha256 = (Get-FileHash -LiteralPath $msix -Algorithm SHA256).Hash
        status = "MSIX_CREATED_UNSIGNED_NOT_TESTED_DO_NOT_SUBMIT"
        windowsGuiE2E = "NOT_TESTED"
        storeCertification = "NOT_SUBMITTED"
    }
    $audit | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath (Join-Path $out "MSIX_AUDIT.json") -Encoding UTF8
    Write-Host ("MSIX_CANDIDATE_UNTESTED: " + $msix)
} finally {
    Pop-Location
    $env:PYTHONPYCACHEPREFIX = $oldPyc
    $env:PYTHONDONTWRITEBYTECODE = $oldNoBytecode
}
