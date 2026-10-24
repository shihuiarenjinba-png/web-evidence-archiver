#requires -Version 5.1
# Web Evidence Archiver technical QA package only.
# Never signs, installs, uploads to Partner Center, submits, certifies, or authorizes sales.
[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)][string]$Version,
    [Parameter(Mandatory=$true)][string]$AssetsDirectory,
    [string]$PythonExe = 'python'
)
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$Root = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path
$BranchExpected = 'codex/store-p0-web-evidence-20261023'
Set-Location -LiteralPath $Root

function Call-Checked([string]$Program, [string[]]$Parameters) {
    & $Program @Parameters
    if ($LASTEXITCODE -ne 0) { throw "Command failed ($LASTEXITCODE): $Program" }
}
function Git-Value([string[]]$Parameters) {
    $r = & git @Parameters 2>&1
    if ($LASTEXITCODE -ne 0) { throw "Git command failed: git $($Parameters -join ' '): $r" }
    return ($r | Out-String).Trim()
}
function Escape-Xml([string]$s) { return [Security.SecurityElement]::Escape($s) }

$RemoteUrl = Git-Value -Parameters @('remote','get-url','origin')
if ($RemoteUrl -notmatch '(?i)github[.]com[:/]shihuiarenjinba-png/web-evidence-archiver(?:[.]git)?$') { throw 'Wrong origin repository.' }
Git-Value -Parameters @('fetch','origin') | Out-Null
$Branch = Git-Value -Parameters @('branch','--show-current')
$Commit = Git-Value -Parameters @('rev-parse','HEAD')
$RemoteCommit = Git-Value -Parameters @('rev-parse',('origin/' + $BranchExpected))
$Dirty = Git-Value -Parameters @('status','--porcelain')
if ($Branch -cne $BranchExpected) { throw "Wrong branch: $Branch" }
if ($Commit -notmatch '^[0-9a-f]{40}$') { throw 'Source SHA is invalid.' }
if ($RemoteCommit -cne $Commit) { throw 'Local HEAD and origin target branch do not match.' }
if ($Dirty) { throw 'Uncommitted changes exist; stopped without packaging.' }
if ($env:PROCESSOR_ARCHITECTURE -ne 'AMD64') { throw 'Windows x64 is required.' }

$VersionParts = $Version.Split('.')
if ($VersionParts.Count -ne 4 -or [int]$VersionParts[0] -lt 1 -or [int]$VersionParts[3] -ne 0 -or
    @($VersionParts | Where-Object { $_ -notmatch '^[0-9]+$' -or [long]$_ -gt 65535 }).Count -gt 0) {
    throw 'QA version must be a valid N.N.N.0 package version.'
}
if (-not (Test-Path -LiteralPath $AssetsDirectory -PathType Container)) { throw 'QA package assets directory is missing.' }
$AssetsDirectory = (Resolve-Path -LiteralPath $AssetsDirectory).Path

$Reg = Get-Content -LiteralPath (Join-Path $PSScriptRoot 'partner_center_registration.json') -Raw -Encoding UTF8 | ConvertFrom-Json
$Prod = Get-Content -LiteralPath (Join-Path $PSScriptRoot 'product.json') -Raw -Encoding UTF8 | ConvertFrom-Json
if ($Reg.storeIdVerificationStatus -cne 'PARTNER_CENTER_VERIFIED' -or $Reg.displayNameVerificationStatus -cne 'PARTNER_CENTER_VERIFIED') {
    throw 'QA packaging requires verified Store ID and reserved DisplayName.'
}
foreach ($Field in @('storeId','packageIdentityName','packageIdentityPublisher','publisherDisplayName','packageFamilyName')) {
    if ([string]::IsNullOrWhiteSpace([string]$Reg.storeIdentity.$Field)) { throw "Missing verified Store identity value: $Field" }
    if ($Reg.identityFieldVerification.$Field -cne 'PARTNER_CENTER_VERIFIED') { throw "Store identity field not verified: $Field" }
}
$Name = [string]$Prod.exeName
$AppId = [string]$Prod.appId
if ($Name -notmatch '^[A-Za-z][A-Za-z0-9_-]{2,50}$' -or $AppId -notmatch '^[A-Za-z][A-Za-z0-9]{2,48}$') { throw 'Invalid application metadata.' }

$OutputRoot = Join-Path $Root 'store-output'
$Unique = (Get-Date -Format 'yyyyMMdd-HHmmss') + '-' + [Guid]::NewGuid().ToString('N').Substring(0,8)
$Output = Join-Path $OutputRoot ('qa-' + $Unique)
New-Item -ItemType Directory -Path $Output -Force | Out-Null
$ScratchRoot = if ($env:RUNNER_TEMP) { $env:RUNNER_TEMP } elseif ($env:TEMP) { $env:TEMP } else { [IO.Path]::GetTempPath() }
$Scratch = Join-Path $ScratchRoot ('wea-qa-msix-' + $Unique)
$Venv = Join-Path $Scratch 'venv'
$Dist = Join-Path $Scratch 'dist'
$Work = Join-Path $Scratch 'work'
$Spec = Join-Path $Scratch 'spec'
$Stage = Join-Path $Scratch 'stage'
$Unpack = Join-Path $Scratch 'unpack'
New-Item -ItemType Directory -Path $Scratch,$Dist,$Work,$Spec,$Stage,$Unpack -Force | Out-Null

Call-Checked -Program $PythonExe -Parameters @('-m','venv',$Venv)
$BuildPython = Join-Path $Venv 'Scripts\python.exe'
Call-Checked -Program $BuildPython -Parameters @('-m','pip','install','-r',(Join-Path $Root 'requirements.txt'))
Call-Checked -Program $BuildPython -Parameters @('-m','pip','install','pyinstaller==6.16.0')
Call-Checked -Program $BuildPython -Parameters @('-m','unittest','discover','-s','tests','-p','test*.py','-v')
Call-Checked -Program $BuildPython -Parameters @('-m','compileall','-q','app.py','archiver.py','store','tests')

$PriorBrowsersPath = $env:PLAYWRIGHT_BROWSERS_PATH
$env:PLAYWRIGHT_BROWSERS_PATH = '0'
try {
    Call-Checked -Program $BuildPython -Parameters @('-m','playwright','install','chromium')
    $PlaywrightVersion = (& $BuildPython -c 'import importlib.metadata; print(importlib.metadata.version("playwright"))').Trim()
    if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($PlaywrightVersion)) { throw 'Cannot determine installed Playwright version.' }
    Call-Checked -Program $BuildPython -Parameters @('-m','PyInstaller','--clean','--noconfirm','--windowed','--onedir','--name',$Name,
                                '--distpath',$Dist,'--workpath',$Work,'--specpath',$Spec,
                                '--collect-all','playwright',[string]$Prod.entryPoint)
} finally { $env:PLAYWRIGHT_BROWSERS_PATH = $PriorBrowsersPath }

$FrozenApp = Join-Path $Dist $Name
$Exe = Join-Path $FrozenApp ($Name + '.exe')
if (-not (Test-Path -LiteralPath $Exe -PathType Leaf)) { throw 'Frozen EXE is missing.' }
$BrowserDirs = @(Get-ChildItem -LiteralPath $FrozenApp -Directory -Recurse -Filter '.local-browsers')
if ($BrowserDirs.Count -ne 1) { throw 'Frozen Playwright browser payload missing or ambiguous.' }
$BrowserRoot = $BrowserDirs[0].FullName
$ChromiumExes = @(Get-ChildItem -LiteralPath $BrowserRoot -File -Recurse | Where-Object {
    $_.Name -match '^(chrome|chrome-headless-shell|headless_shell)[.]exe$'
})
if ($ChromiumExes.Count -eq 0) { throw 'Frozen Chromium executable is missing.' }
$BrowserLines = @(Get-ChildItem -LiteralPath $BrowserRoot -File -Recurse | Sort-Object FullName | ForEach-Object {
    $rel = $_.FullName.Substring($BrowserRoot.Length).TrimStart('\').Replace('\','/')
    $hash = (Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256).Hash.ToLowerInvariant()
    "$rel|$hash"
})
$BrowserData = [Text.Encoding]::UTF8.GetBytes(($BrowserLines -join [char]10) + [char]10)
$Hasher = [Security.Cryptography.SHA256]::Create()
try { $BrowserHash = ([BitConverter]::ToString($Hasher.ComputeHash($BrowserData))).Replace('-','').ToLowerInvariant() }
finally { $Hasher.Dispose() }

$StageApp = Join-Path $Stage 'App'
$StageAssets = Join-Path $Stage 'Assets'
New-Item -ItemType Directory -Path $StageApp,$StageAssets -Force | Out-Null
Get-ChildItem -LiteralPath $FrozenApp | ForEach-Object { Copy-Item -LiteralPath $_.FullName -Destination $StageApp -Recurse -ErrorAction Stop }
foreach ($Logo in @('StoreLogo.png','Square44x44Logo.png','Square150x150Logo.png')) {
    $Source = Join-Path $AssetsDirectory $Logo
    if (-not (Test-Path -LiteralPath $Source -PathType Leaf)) { throw "Missing QA logo: $Logo" }
    Copy-Item -LiteralPath $Source -Destination $StageAssets -ErrorAction Stop
}
Set-Content -LiteralPath (Join-Path $Stage 'SOURCE_GIT_COMMIT.txt') -Value $Commit -Encoding ASCII

$IdentityName = Escape-Xml ([string]$Reg.storeIdentity.packageIdentityName)
$Publisher = Escape-Xml ([string]$Reg.storeIdentity.packageIdentityPublisher)
$PublisherName = Escape-Xml ([string]$Reg.storeIdentity.publisherDisplayName)
$Display = Escape-Xml ([string]$Reg.displayName)
$Resources = @('<Resource Language="en-US"/>','<Resource Language="ja-JP"/>') -join [Environment]::NewLine
$Manifest = @"
<?xml version="1.0" encoding="utf-8"?>
<Package xmlns="http://schemas.microsoft.com/appx/manifest/foundation/windows10" xmlns:uap="http://schemas.microsoft.com/appx/manifest/uap/windows10" xmlns:uap10="http://schemas.microsoft.com/appx/manifest/uap/windows10/10" xmlns:rescap="http://schemas.microsoft.com/appx/manifest/foundation/windows10/restrictedcapabilities" IgnorableNamespaces="uap uap10 rescap">
 <Identity Name="$IdentityName" Publisher="$Publisher" Version="$Version" ProcessorArchitecture="x64"/>
 <Properties><DisplayName>$Display</DisplayName><PublisherDisplayName>$PublisherName</PublisherDisplayName><Logo>Assets\StoreLogo.png</Logo></Properties>
 <Resources>$Resources</Resources>
 <Dependencies><TargetDeviceFamily Name="Windows.Desktop" MinVersion="10.0.19041.0" MaxVersionTested="10.0.26100.0"/></Dependencies>
 <Applications><Application Id="$AppId" Executable="App\$Name.exe" uap10:RuntimeBehavior="packagedClassicApp" uap10:TrustLevel="mediumIL"><uap:VisualElements DisplayName="$Display" Description="$Display" BackgroundColor="transparent" Square150x150Logo="Assets\Square150x150Logo.png" Square44x44Logo="Assets\Square44x44Logo.png"/></Application></Applications>
 <Capabilities><rescap:Capability Name="runFullTrust"/></Capabilities>
</Package>
"@
[IO.File]::WriteAllText((Join-Path $Stage 'AppxManifest.xml'), $Manifest, (New-Object Text.UTF8Encoding($false)))

$Sdk = Join-Path ([Environment]::GetFolderPath('ProgramFilesX86')) 'Windows Kits\10\bin'
$Found = @(Get-ChildItem -LiteralPath $Sdk -Recurse -File -Filter 'MakeAppx.exe' -ErrorAction SilentlyContinue |
    Where-Object { $_.FullName -like '*\x64\MakeAppx.exe' } | Sort-Object FullName -Descending)
if ($Found.Count -eq 0) { throw 'Windows SDK x64 MakeAppx missing.' }
$MakeAppxPath = $Found[0].FullName
$Msix = Join-Path $Output ('WebEvidenceArchiver_QA_UNSIGNED_' + $Version + '_x64.msix')
Call-Checked -Program $MakeAppxPath -Parameters @('pack','/d',$Stage,'/p',$Msix)
Call-Checked -Program $MakeAppxPath -Parameters @('unpack','/p',$Msix,'/d',$Unpack)

$RoundtripExe = Join-Path (Join-Path $Unpack 'App') ($Name + '.exe')
if (-not (Test-Path -LiteralPath $RoundtripExe -PathType Leaf)) { throw 'MSIX unpacked EXE missing.' }
$ExeSha = (Get-FileHash -LiteralPath $Exe -Algorithm SHA256).Hash.ToLowerInvariant()
if ((Get-FileHash -LiteralPath $RoundtripExe -Algorithm SHA256).Hash.ToLowerInvariant() -cne $ExeSha) { throw 'Unpacked executable checksum differs.' }
[xml]$Doc = Get-Content -LiteralPath (Join-Path $Unpack 'AppxManifest.xml') -Raw
$Ns = New-Object Xml.XmlNamespaceManager($Doc.NameTable)
$Ns.AddNamespace('m','http://schemas.microsoft.com/appx/manifest/foundation/windows10')
$Ns.AddNamespace('u','http://schemas.microsoft.com/appx/manifest/uap/windows10')
$Ns.AddNamespace('u10','http://schemas.microsoft.com/appx/manifest/uap/windows10/10')
$idNode = $Doc.SelectSingleNode('/m:Package/m:Identity',$Ns)
$dn = $Doc.SelectSingleNode('/m:Package/m:Properties/m:DisplayName',$Ns)
$pd = $Doc.SelectSingleNode('/m:Package/m:Properties/m:PublisherDisplayName',$Ns)
$an = $Doc.SelectSingleNode('/m:Package/m:Applications/m:Application',$Ns)
$vn = $Doc.SelectSingleNode('/m:Package/m:Applications/m:Application/u:VisualElements',$Ns)
if (-not $idNode -or -not $dn -or -not $pd -or -not $an -or -not $vn) { throw 'MSIX manifest identity/display nodes missing.' }
if ($idNode.GetAttribute('Name') -cne [string]$Reg.storeIdentity.packageIdentityName -or
    $idNode.GetAttribute('Publisher') -cne [string]$Reg.storeIdentity.packageIdentityPublisher -or
    $idNode.GetAttribute('Version') -cne $Version -or $idNode.GetAttribute('ProcessorArchitecture') -cne 'x64' -or
    $dn.InnerText -cne [string]$Reg.displayName -or
    $pd.InnerText -cne [string]$Reg.storeIdentity.publisherDisplayName -or
    $vn.GetAttribute('DisplayName') -cne [string]$Reg.displayName -or
    $an.GetAttribute('Id') -cne $AppId -or $an.GetAttribute('Executable') -cne "App\$Name.exe" -or
    $an.GetAttribute('RuntimeBehavior','http://schemas.microsoft.com/appx/manifest/uap/windows10/10') -cne 'packagedClassicApp' -or
    $an.GetAttribute('TrustLevel','http://schemas.microsoft.com/appx/manifest/uap/windows10/10') -cne 'mediumIL') {
    throw 'Unpacked MSIX manifest does not match the verified Store identity and desktop runtime contract.'
}
$MsixSha = (Get-FileHash -LiteralPath $Msix -Algorithm SHA256).Hash.ToLowerInvariant()
$Evidence = [ordered]@{
    source_commit=$Commit; source_branch=$Branch; store_id=$Reg.storeIdentity.storeId;
    qa_version=$Version; playwright_version=$PlaywrightVersion; browser_tree_sha256=$BrowserHash;
    chromium_executables=$ChromiumExes.Count; msix=$Msix; msix_sha256=$MsixSha; exe_sha256=$ExeSha;
    package_signature='QA_UNSIGNED'; browser_redistribution_approval='NOT_PROVIDED';
    install_qa='NOT_VERIFIED'; certification='NOT_AUTHORIZED'; sales='HOLD'
}
$Evidence | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath (Join-Path $Output 'BUILD_EVIDENCE.json') -Encoding UTF8
Write-Host "QA_UNSIGNED_MSIX_CREATED=$Msix"
Write-Host "MSIX_SHA256=$MsixSha"
Write-Host "EXE_SHA256=$ExeSha"
Write-Host "BROWSER_TREE_SHA256=$BrowserHash"
Write-Host "PLAYWRIGHT_VERSION=$PlaywrightVersion"
Write-Host 'BROWSER_QA_APPROVAL=NOT_PROVIDED'
Write-Host 'STORE_SUBMISSION_AUTHORIZED=FALSE'
