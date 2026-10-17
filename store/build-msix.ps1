#requires -Version 5.1
# Offline build. Never install, sign, overwrite other products, or submit to Store.
[CmdletBinding()]
param([switch]$PreflightOnly)
$ErrorActionPreference="Stop"
$root=(Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$cfg=Get-Content (Join-Path $PSScriptRoot "product.json") -Raw -Encoding UTF8 | ConvertFrom-Json
if([Environment]::OSVersion.Platform -ne [PlatformID]::Win32NT -or -not [Environment]::Is64BitOperatingSystem){throw "Windows x64 required"}
if($cfg.exeName -notmatch '^[A-Za-z][A-Za-z0-9_-]{2,50}$' -or $cfg.appId -notmatch '^[A-Za-z][A-Za-z0-9]{2,48}$'){throw "Invalid product config"}
foreach($key in @("STORE_IDENTITY_NAME","STORE_PUBLISHER","STORE_PUBLISHER_DISPLAY_NAME","STORE_VERSION")){
 if([string]::IsNullOrWhiteSpace([Environment]::GetEnvironmentVariable($key))){throw "Partner Center field missing: $key"}
}
if($env:STORE_IDENTITY_CONFIRMED -cne "YES" -or $env:STORE_BRAND_APPROVED -cne "YES"){throw "Formal identity and approved logo required"}
if($env:STORE_IDENTITY_NAME -notmatch '^[A-Za-z0-9.-]{3,50}$' -or $env:STORE_PUBLISHER -notmatch '^CN=.' -or $env:STORE_VERSION -notmatch '^\d+\.\d+\.\d+\.0$'){throw "Invalid identity/publisher/version"}
$v=@($env:STORE_VERSION.Split(".")|ForEach-Object{[int]$_})
if($v[0] -lt 1 -or @($v|Where-Object{$_ -gt 65535}).Count){throw "Version out of range"}
$assets=@(@("StoreLogo.png",50,50),@("Square44x44Logo.png",44,44),@("Square150x150Logo.png",150,150),@("Wide310x150Logo.png",310,150))
Add-Type -AssemblyName System.Drawing
foreach($a in $assets){
 $file=Join-Path $PSScriptRoot ("assets\"+$a[0])
 if(-not(Test-Path $file)){throw "Missing approved logo: $file"}
 $bmp=[Drawing.Image]::FromFile($file)
 try{if($bmp.Width -ne $a[1] -or $bmp.Height -ne $a[2]){throw "Wrong image size $file"}}finally{$bmp.Dispose()}
}
if($cfg.needsBundledBrowser){throw "Playwright Chromium offline bundle is unverified; packaging HOLD"}
$python=Join-Path $root ".venv\Scripts\python.exe"
if(-not(Test-Path $python)){throw "Dedicated venv with dependencies and PyInstaller required; no auto-install"}
Push-Location $root
try{
 & $python -m unittest discover -s tests -p "test*.py" -v
 if($LASTEXITCODE -ne 0){throw "Python regression failed"}
 & $python -m compileall -q app.py
 if($LASTEXITCODE -ne 0){throw "Python syntax failure"}
 & $python -m PyInstaller --version | Out-Host
 if($LASTEXITCODE -ne 0){throw "PyInstaller missing"}
 if($PreflightOnly){Write-Host "MSIX_PREFLIGHT_PASS_NO_PACKAGE";return}
 $sdk=Join-Path ([Environment]::GetFolderPath("ProgramFilesX86")) "Windows Kits\10\bin"
 $makeappx=Get-ChildItem $sdk -Recurse -Filter makeappx.exe -File -ErrorAction SilentlyContinue | Where-Object {$_.DirectoryName -match '\\x64$'} | Sort-Object FullName -Descending | Select-Object -First 1
 if(-not $makeappx){throw "Windows SDK x64 MakeAppx missing"}
 $out=Join-Path $root ("store-output\"+(Get-Date -Format "yyyyMMdd-HHmmss")+"-"+[Guid]::NewGuid().ToString("N").Substring(0,8))
 $dist=Join-Path $out "dist";$work=Join-Path $out "work";$spec=Join-Path $out "spec";$stage=Join-Path $out "stage"
 New-Item -ItemType Directory -Path $dist,$work,$spec,$stage -Force | Out-Null
 & $python -m PyInstaller --clean --noconfirm --windowed --onedir --name $cfg.exeName --distpath $dist --workpath $work --specpath $spec (Join-Path $root "app.py")
 if($LASTEXITCODE -ne 0){throw "PyInstaller build failed"}
 $exe=Join-Path $dist ($cfg.exeName+"\"+$cfg.exeName+".exe")
 if(-not(Test-Path $exe)){throw "Expected app EXE missing"}
 $app=Join-Path $stage "App";$resource=Join-Path $stage "Assets"
 New-Item -ItemType Directory -Path $app,$resource | Out-Null
 Copy-Item -Path (Join-Path $dist ($cfg.exeName+"\*")) -Destination $app -Recurse
 foreach($a in $assets){Copy-Item -LiteralPath (Join-Path $PSScriptRoot ("assets\"+$a[0])) -Destination $resource}
 $esc={param([string]$t)[Security.SecurityElement]::Escape($t)}
 $name=& $esc $env:STORE_IDENTITY_NAME;$publisher=& $esc $env:STORE_PUBLISHER
 $pubDisplay=& $esc $env:STORE_PUBLISHER_DISPLAY_NAME;$display=& $esc $cfg.displayName
 $exeName=& $esc $cfg.exeName;$appId=& $esc $cfg.appId;$ver=$env:STORE_VERSION
 $manifest=@"
<?xml version="1.0" encoding="utf-8"?>
<Package xmlns="http://schemas.microsoft.com/appx/manifest/foundation/windows10" xmlns:uap="http://schemas.microsoft.com/appx/manifest/uap/windows10" xmlns:rescap="http://schemas.microsoft.com/appx/manifest/foundation/windows10/restrictedcapabilities" IgnorableNamespaces="uap rescap">
<Identity Name="$name" Publisher="$publisher" Version="$ver" ProcessorArchitecture="x64"/>
<Properties><DisplayName>$display</DisplayName><PublisherDisplayName>$pubDisplay</PublisherDisplayName><Logo>Assets\StoreLogo.png</Logo></Properties>
<Dependencies><TargetDeviceFamily Name="Windows.Desktop" MinVersion="10.0.19041.0" MaxVersionTested="10.0.26100.0"/></Dependencies>
<Resources><Resource Language="ja-jp"/></Resources>
<Applications><Application Id="$appId" Executable="App\$exeName.exe" EntryPoint="Windows.FullTrustApplication"><uap:VisualElements DisplayName="$display" Description="$display" BackgroundColor="transparent" Square150x150Logo="Assets\Square150x150Logo.png" Square44x44Logo="Assets\Square44x44Logo.png"><uap:DefaultTile Wide310x150Logo="Assets\Wide310x150Logo.png"/></uap:VisualElements></Application></Applications>
<Capabilities><rescap:Capability Name="runFullTrust"/></Capabilities>
</Package>
"@
 $file=Join-Path $stage "AppxManifest.xml"
 [IO.File]::WriteAllText($file,$manifest,(New-Object Text.UTF8Encoding($false)))
 [xml]$parsed=Get-Content $file -Raw -Encoding UTF8
 if($parsed.Package.Identity.Name -cne $env:STORE_IDENTITY_NAME){throw "Manifest Identity mismatch"}
 $msix=Join-Path $out ($cfg.exeName+"_"+$ver+"_x64.msix")
 & $makeappx.FullName pack /d $stage /p $msix
 if($LASTEXITCODE -ne 0 -or -not(Test-Path $msix)){throw "MakeAppx failed"}
 Add-Type -AssemblyName System.IO.Compression
 Add-Type -AssemblyName System.IO.Compression.FileSystem
 $zip=[IO.Compression.ZipFile]::OpenRead($msix)
 try{if($null -eq $zip.GetEntry("AppxManifest.xml") -or $null -eq $zip.GetEntry("App/$($cfg.exeName).exe")){throw "MSIX content incomplete"}}finally{$zip.Dispose()}
 $audit=[ordered]@{product=$cfg.displayName;identity=$env:STORE_IDENTITY_NAME;publisher=$env:STORE_PUBLISHER;version=$ver;msix=$msix;sha256=(Get-FileHash $msix -Algorithm SHA256).Hash;status="UNSIGNED_CANDIDATE_STORE_HOLD";next="WACK, installed GUI, update, uninstall, Store approval"}
 $audit|ConvertTo-Json -Depth 4|Set-Content (Join-Path $out "MSIX_AUDIT.json") -Encoding UTF8
 Write-Host "MSIX_CANDIDATE_BUILT: $msix"
}finally{Pop-Location}
