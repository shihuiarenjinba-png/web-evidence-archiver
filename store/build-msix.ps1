#requires -Version 5.1
# Candidate ONLY: no installation, certificate change, Store submission, or overwrite.
[CmdletBinding()]
param([switch]$PreflightOnly)
$ErrorActionPreference = "Stop"
$root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$cfg = Get-Content (Join-Path $PSScriptRoot "product.json") -Raw -Encoding UTF8 | ConvertFrom-Json
if ([Environment]::OSVersion.Platform -ne [PlatformID]::Win32NT -or -not [Environment]::Is64BitOperatingSystem) {throw "Windows x64 required"}
if ($cfg.exeName -notmatch '^[A-Za-z][A-Za-z0-9_-]{2,50}$' -or $cfg.appId -notmatch '^[A-Za-z][A-Za-z0-9]{2,48}$') {throw "Invalid store/product.json"}
foreach ($key in @("STORE_IDENTITY_NAME","STORE_PUBLISHER","STORE_PUBLISHER_DISPLAY_NAME","STORE_VERSION")) {
  if ([string]::IsNullOrWhiteSpace([Environment]::GetEnvironmentVariable($key))) {throw "Missing Partner Center field: $key"}
}
if ($env:STORE_IDENTITY_CONFIRMED -cne "YES" -or $env:STORE_BRAND_APPROVED -cne "YES") {throw "Formal Identity and logo approval required"}
if ($env:STORE_IDENTITY_NAME -notmatch '^[A-Za-z0-9.-]{3,50}$' -or $env:STORE_PUBLISHER -notmatch '^CN=.' -or $env:STORE_VERSION -notmatch '^\d+\.\d+\.\d+\.0$') {throw "Invalid Identity/Publisher/Store version"}
$parts = @($env:STORE_VERSION.Split(".") | ForEach-Object { [int]$_ })
if ($parts[0] -lt 1 -or @($parts | Where-Object {$_ -gt 65535}).Count -gt 0) {throw "Version outside Store range"}
$assets = @(@("StoreLogo.png",50,50),@("Square44x44Logo.png",44,44),@("Square150x150Logo.png",150,150),@("Wide310x150Logo.png",310,150))
Add-Type -AssemblyName System.Drawing
foreach ($item in $assets) {
  $file = Join-Path $PSScriptRoot ("assets\" + $item[0])
  if (-not (Test-Path $file)) {throw "Missing approved PNG: $file"}
  $bmp = [Drawing.Image]::FromFile($file)
  try {if ($bmp.Width -ne $item[1] -or $bmp.Height -ne $item[2]) {throw "Wrong dimensions: $file"}}
  finally {$bmp.Dispose()}
}
if ($cfg.needsBundledBrowser) {throw "HOLD: offline Chromium bundle and startup unverified"}
$python = Join-Path $root ".venv\Scripts\python.exe"
if (-not (Test-Path $python)) {throw "Dedicated .venv missing; nothing installed automatically"}
Push-Location $root
try {
  & $python -m unittest discover -s tests -p "test*.py" -v
  if ($LASTEXITCODE -ne 0) {throw "Regression test failed"}
  & $python -m compileall -q app.py
  if ($LASTEXITCODE -ne 0) {throw "Syntax check failed"}
  & $python -m PyInstaller --version | Out-Host
  if ($LASTEXITCODE -ne 0) {throw "PyInstaller not installed"}
  if ($PreflightOnly) {Write-Host "PREFLIGHT_PASS_NO_PACKAGE";return}
  $sdk = Join-Path ([Environment]::GetFolderPath("ProgramFilesX86")) "Windows Kits\10\bin"
  $tool = Get-ChildItem $sdk -Recurse -File -Filter makeappx.exe -ErrorAction SilentlyContinue | Where-Object {$_.DirectoryName -match '\\x64$'} | Sort-Object FullName -Descending | Select-Object -First 1
  if (-not $tool) {throw "Windows SDK x64 MakeAppx missing"}
  $tag = (Get-Date -Format "yyyyMMdd-HHmmss") + "-" + [Guid]::NewGuid().ToString("N").Substring(0,8)
  $out = Join-Path $root ("store-output\" + $tag)
  $dist = Join-Path $out "dist"
  $stage = Join-Path $out "stage"
  New-Item -ItemType Directory -Path $dist,$stage -Force | Out-Null
  & $python -m PyInstaller --noconfirm --clean --windowed --onedir --name $cfg.exeName --distpath $dist --workpath (Join-Path $out "work") --specpath (Join-Path $out "spec") (Join-Path $root "app.py")
  if ($LASTEXITCODE -ne 0) {throw "PyInstaller failed"}
  $built = Join-Path (Join-Path $dist $cfg.exeName) ($cfg.exeName + ".exe")
  if (-not (Test-Path $built)) {throw "Built EXE missing"}
  $app = Join-Path $stage "App"
  $assetDir = Join-Path $stage "Assets"
  New-Item -ItemType Directory -Path $app,$assetDir -Force | Out-Null
  Copy-Item (Join-Path (Join-Path $dist $cfg.exeName) "*") $app -Recurse
  foreach ($item in $assets) {Copy-Item (Join-Path $PSScriptRoot ("assets\" + $item[0])) $assetDir}
  $esc = {param([string]$t) [Security.SecurityElement]::Escape($t)}
  $tokens = @{
    "{{NAME}}"=(& $esc $env:STORE_IDENTITY_NAME)
    "{{PUBLISHER}}"=(& $esc $env:STORE_PUBLISHER)
    "{{PUBLISHER_NAME}}"=(& $esc $env:STORE_PUBLISHER_DISPLAY_NAME)
    "{{DISPLAY}}"=(& $esc $cfg.displayName)
    "{{EXE}}"=(& $esc $cfg.exeName)
    "{{APPID}}"=(& $esc $cfg.appId)
    "{{VERSION}}"=$env:STORE_VERSION
  }
  $xml = @'
<?xml version="1.0" encoding="utf-8"?>
<Package xmlns="http://schemas.microsoft.com/appx/manifest/foundation/windows10" xmlns:uap="http://schemas.microsoft.com/appx/manifest/uap/windows10" xmlns:rescap="http://schemas.microsoft.com/appx/manifest/foundation/windows10/restrictedcapabilities" IgnorableNamespaces="uap rescap">
<Identity Name="{{NAME}}" Publisher="{{PUBLISHER}}" Version="{{VERSION}}" ProcessorArchitecture="x64" />
<Properties><DisplayName>{{DISPLAY}}</DisplayName><PublisherDisplayName>{{PUBLISHER_NAME}}</PublisherDisplayName><Logo>Assets\StoreLogo.png</Logo></Properties>
<Dependencies><TargetDeviceFamily Name="Windows.Desktop" MinVersion="10.0.19041.0" MaxVersionTested="10.0.26100.0" /></Dependencies>
<Resources><Resource Language="ja-jp" /></Resources>
<Applications><Application Id="{{APPID}}" Executable="App\{{EXE}}.exe" EntryPoint="Windows.FullTrustApplication"><uap:VisualElements DisplayName="{{DISPLAY}}" Description="{{DISPLAY}}" BackgroundColor="transparent" Square150x150Logo="Assets\Square150x150Logo.png" Square44x44Logo="Assets\Square44x44Logo.png"><uap:DefaultTile Wide310x150Logo="Assets\Wide310x150Logo.png" /></uap:VisualElements></Application></Applications>
<Capabilities><rescap:Capability Name="runFullTrust" /></Capabilities>
</Package>
'@
  foreach ($token in $tokens.Keys) {$xml = $xml.Replace($token, [string]$tokens[$token])}
  $manifest = Join-Path $stage "AppxManifest.xml"
  [IO.File]::WriteAllText($manifest,$xml,(New-Object Text.UTF8Encoding($false)))
  [xml]$parsed = Get-Content $manifest -Raw -Encoding UTF8
  $identity = $parsed.SelectSingleNode("/*[local-name()='Package']/*[local-name()='Identity']")
  if ($identity.GetAttribute("Name") -cne $env:STORE_IDENTITY_NAME -or $identity.GetAttribute("Publisher") -cne $env:STORE_PUBLISHER) {throw "Manifest Identity mismatch"}
  $msix = Join-Path $out ($cfg.exeName + "_" + $env:STORE_VERSION + "_x64.msix")
  & $tool.FullName pack /d $stage /p $msix
  if ($LASTEXITCODE -ne 0 -or -not (Test-Path $msix)) {throw "MakeAppx failed"}
  Add-Type -AssemblyName System.IO.Compression.FileSystem
  $zip = [IO.Compression.ZipFile]::OpenRead($msix)
  try {if (-not $zip.GetEntry("AppxManifest.xml") -or -not $zip.GetEntry(("App/" + $cfg.exeName + ".exe"))) {throw "Incomplete MSIX"}} finally {$zip.Dispose()}
  $audit = @{status="UNSIGNED_MSIX_CANDIDATE_STORE_HOLD";path=$msix;sha256=(Get-FileHash $msix -Algorithm SHA256).Hash;identity=$env:STORE_IDENTITY_NAME;publisher=$env:STORE_PUBLISHER;version=$env:STORE_VERSION}
  $audit | ConvertTo-Json | Set-Content (Join-Path $out "MSIX_AUDIT.json") -Encoding UTF8
  Write-Host "UNSIGNED_MSIX_CANDIDATE: $msix"
} finally {Pop-Location}
