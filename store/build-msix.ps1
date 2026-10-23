#requires -Version 5.1
# Web Evidence Archiver: unsigned MSIX candidate only. Never signs, uploads, or publishes.
[CmdletBinding()]
param([switch]$PreflightOnly, [string]$PythonExe = 'python')
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

# Required clean-source check, before even writing a preflight report.
$Branch = Git-Value -Parameters @('branch','--show-current')
$Commit = Git-Value -Parameters @('rev-parse','HEAD')
$RemoteCommit = Git-Value -Parameters @('rev-parse',('origin/' + $BranchExpected))
$Dirty = Git-Value -Parameters @('status','--porcelain')
if ($Branch -cne $BranchExpected) { throw "Wrong branch: $Branch" }
if ($Commit -notmatch '^[0-9a-f]{40}if ($Dirty) { throw "Uncommitted changes exist; stopped without packaging." }
if ($env:PROCESSOR_ARCHITECTURE -ne 'AMD64') { throw 'Windows x64 is required.' }

$OutputRoot = Join-Path $Root 'store-output'
$Unique = (Get-Date -Format 'yyyyMMdd-HHmmss') + '-' + [Guid]::NewGuid().ToString('N').Substring(0,8)
$Output = Join-Path $OutputRoot $Unique
if (Test-Path -LiteralPath $Output) { throw "Output already exists: $Output" }
New-Item -ItemType Directory -Path $Output -Force | Out-Null
$ReportPath = Join-Path $Output 'PREFLIGHT.json'
Call-Checked -Program $PythonExe -Parameters @((Join-Path $PSScriptRoot 'msix_preflight.py'),'--json-out',$ReportPath)
$Report = Get-Content -LiteralPath $ReportPath -Raw -Encoding UTF8 | ConvertFrom-Json
$ReadyText = if ($Report.ready) { 'true' } else { 'false' }
if ($env:GITHUB_OUTPUT) { Add-Content -LiteralPath $env:GITHUB_OUTPUT -Value "ready=$ReadyText" }
Write-Host "SOURCE_SHA=$Commit"
Write-Host "MSIX_PREFLIGHT_READY=$ReadyText"
foreach ($Reason in @($Report.blockers)) { Write-Host "MSIX_BLOCKER=$Reason" }
if ($PreflightOnly) { Write-Host 'No EXE or MSIX created (preflight only).'; return }
if (-not $Report.ready) { throw 'MSIX blocked: exact Store identity, version, approved logos, or Chromium evidence missing.' }

$Reg = Get-Content -LiteralPath (Join-Path $PSScriptRoot 'partner_center_registration.json') -Raw | ConvertFrom-Json
$Prod = Get-Content -LiteralPath (Join-Path $PSScriptRoot 'product.json') -Raw | ConvertFrom-Json
$BrowserApproval = Get-Content -LiteralPath (Join-Path $PSScriptRoot 'browser_bundle_approval.json') -Raw | ConvertFrom-Json
$Name = [string]$Prod.exeName
$AppId = [string]$Prod.appId
$Version = [string]$Reg.approvedStoreVersion
if ($Name -notmatch '^[A-Za-z][A-Za-z0-9_-]{2,50}$' -or $AppId -notmatch '^[A-Za-z][A-Za-z0-9]{2,48}$') {
    throw 'Invalid application metadata.'
}
$ScratchRoot = if ($env:RUNNER_TEMP) { $env:RUNNER_TEMP } elseif ($env:TEMP) { $env:TEMP } else { [IO.Path]::GetTempPath() }
$Scratch = Join-Path $ScratchRoot ("wea-msix-" + $Unique)
if (Test-Path -LiteralPath $Scratch) { throw 'Refusing to reuse temporary build directory.' }
$Venv = Join-Path $Scratch 'venv'
$Dist = Join-Path $Scratch 'dist'
$Work = Join-Path $Scratch 'work'
$Spec = Join-Path $Scratch 'spec'
$Stage = Join-Path $Scratch 'stage'
$Unpack = Join-Path $Scratch 'unpack'
New-Item -ItemType Directory -Path $Scratch,$Dist,$Work,$Spec,$Stage,$Unpack | Out-Null
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
    if ($LASTEXITCODE -ne 0 -or $PlaywrightVersion -cne [string]$BrowserApproval.playwright_version) {
        throw 'Installed Playwright does not match owner-approved version.'
    }
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
    $_.Name -match '^(chrome|chrome-headless-shell|headless_shell)\.exe$'
})
if ($ChromiumExes.Count -eq 0) { throw 'Frozen Chromium executable is missing.' }
# Browser fingerprint: SHA256 of UTF-8 lines "relative/path|file_sha256" sorted by path.
$BrowserLines = @(Get-ChildItem -LiteralPath $BrowserRoot -File -Recurse | Sort-Object FullName | ForEach-Object {
    $rel = $_.FullName.Substring($BrowserRoot.Length).TrimStart('\').Replace('\','/')
    $hash = (Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256).Hash.ToLowerInvariant()
    "$rel|$hash"
})
$BrowserData = [Text.Encoding]::UTF8.GetBytes(($BrowserLines -join [char]10) + [char]10)
$Hasher = [Security.Cryptography.SHA256]::Create()
try { $BrowserHash = ([BitConverter]::ToString($Hasher.ComputeHash($BrowserData))).Replace('-','').ToLowerInvariant() }
finally { $Hasher.Dispose() }
if ($BrowserHash -cne ([string]$BrowserApproval.browser_payload_sha256).ToLowerInvariant()) {
    throw 'Packaged Chromium file-tree fingerprint does not match approved input.'
}
$StageApp = Join-Path $Stage 'App'
$StageAssets = Join-Path $Stage 'Assets'
New-Item -ItemType Directory -Path $StageApp,$StageAssets | Out-Null
Get-ChildItem -LiteralPath $FrozenApp | ForEach-Object {
    Copy-Item -LiteralPath $_.FullName -Destination $StageApp -Recurse -ErrorAction Stop
}
foreach ($Logo in @('StoreLogo.png','Square44x44Logo.png','Square150x150Logo.png')) {
    Copy-Item -LiteralPath (Join-Path (Join-Path $PSScriptRoot 'assets') $Logo) -Destination $StageAssets -ErrorAction Stop
}
Set-Content -LiteralPath (Join-Path $Stage 'SOURCE_GIT_COMMIT.txt') -Value $Commit -Encoding ASCII

$IdentityName = Escape-Xml ([string]$Reg.storeIdentity.packageIdentityName)
$Publisher = Escape-Xml ([string]$Reg.storeIdentity.packageIdentityPublisher)
$PublisherName = Escape-Xml ([string]$Reg.storeIdentity.publisherDisplayName)
$Display = Escape-Xml ([string]$Reg.displayName)
$Resources = (@($Reg.manifestResources) | ForEach-Object {
    '<Resource Language="' + (Escape-Xml ([string]$_)) + '"/>'
}) -join [Environment]::NewLine
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
$MakeAppx = Get-ChildItem -LiteralPath $Sdk -Recurse -File -Filter 'MakeAppx.exe' -ErrorAction SilentlyContinue |
    Where-Object { $_.DirectoryName -match '\\x64$' } | Sort-Object FullName -Descending | Select-Object -First 1
if (-not $MakeAppx) { throw 'Windows SDK x64 MakeAppx missing.' }
$Msix = Join-Path $Output ('WebEvidenceArchiver_' + $Version + '_x64.msix')
if (Test-Path -LiteralPath $Msix) { throw 'Refusing to overwrite existing candidate.' }
Call-Checked -Program $MakeAppx.FullName -Parameters @('pack','/d',$Stage,'/p',$Msix)
Call-Checked -Program $MakeAppx.FullName -Parameters @('unpack','/p',$Msix,'/d',$Unpack)
$RoundtripExe = Join-Path (Join-Path $Unpack 'App') ($Name + '.exe')
if (-not (Test-Path -LiteralPath $RoundtripExe -PathType Leaf)) { throw 'MSIX unpacked EXE missing.' }
$ExeSha = (Get-FileHash -LiteralPath $Exe -Algorithm SHA256).Hash.ToLowerInvariant()
if ((Get-FileHash -LiteralPath $RoundtripExe -Algorithm SHA256).Hash.ToLowerInvariant() -cne $ExeSha) {
    throw 'Unpacked executable checksum differs.'
}
[xml]$Doc = Get-Content -LiteralPath (Join-Path $Unpack 'AppxManifest.xml') -Raw
$Ns = New-Object Xml.XmlNamespaceManager($Doc.NameTable)
$Ns.AddNamespace('m','http://schemas.microsoft.com/appx/manifest/foundation/windows10')
$Ns.AddNamespace('u','http://schemas.microsoft.com/appx/manifest/uap/windows10')
$id = $Doc.SelectSingleNode('/m:Package/m:Identity',$Ns)
$dn = $Doc.SelectSingleNode('/m:Package/m:Properties/m:DisplayName',$Ns)
$pd = $Doc.SelectSingleNode('/m:Package/m:Properties/m:PublisherDisplayName',$Ns)
$an = $Doc.SelectSingleNode('/m:Package/m:Applications/m:Application',$Ns)
$vn = $Doc.SelectSingleNode('/m:Package/m:Applications/m:Application/u:VisualElements',$Ns)
if (-not $id -or -not $dn -or -not $pd -or -not $an -or -not $vn) { throw 'MSIX manifest identity/display nodes missing.' }
if ($id.GetAttribute('Name') -cne [string]$Reg.storeIdentity.packageIdentityName -or
    $id.GetAttribute('Publisher') -cne [string]$Reg.storeIdentity.packageIdentityPublisher -or
    $id.GetAttribute('Version') -cne $Version -or $id.GetAttribute('ProcessorArchitecture') -cne 'x64' -or
    $dn.InnerText -cne [string]$Reg.displayName -or
    $pd.InnerText -cne [string]$Reg.storeIdentity.publisherDisplayName -or
    $vn.GetAttribute('DisplayName') -cne [string]$Reg.displayName -or
    $an.GetAttribute('Id') -cne $AppId -or $an.GetAttribute('Executable') -cne "App\$Name.exe") {
    throw 'Unpacked MSIX manifest does not match the approved Store identity.'
}
$MsixSha = (Get-FileHash -LiteralPath $Msix -Algorithm SHA256).Hash.ToLowerInvariant()
$Evidence = [ordered]@{ source_commit=$Commit; source_branch=$Branch; store_id=$Reg.storeIdentity.storeId;
    msix=$Msix; msix_sha256=$MsixSha; exe_sha256=$ExeSha; browser_tree_sha256=$BrowserHash;
    signature='UNSIGNED'; install_qa='NOT_VERIFIED'; certification='NOT_AUTHORIZED'; sales='HOLD' }
$Evidence | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath (Join-Path $Output 'BUILD_EVIDENCE.json')
Write-Host "MSIX_CANDIDATE_CREATED=$Msix"
Write-Host "MSIX_SHA256=$MsixSha"
Write-Host 'STORE_SUBMISSION=NOT_AUTHORIZED; SALES=HOLD'
) { throw 'Source SHA is invalid.' }
if ($RemoteCommit -cne $Commit) { throw 'Local HEAD and origin target branch do not match.' }
if ($Dirty) { throw "Uncommitted changes exist; stopped without packaging." }
if ($env:PROCESSOR_ARCHITECTURE -ne 'AMD64') { throw 'Windows x64 is required.' }

$OutputRoot = Join-Path $Root 'store-output'
$Unique = (Get-Date -Format 'yyyyMMdd-HHmmss') + '-' + [Guid]::NewGuid().ToString('N').Substring(0,8)
$Output = Join-Path $OutputRoot $Unique
if (Test-Path -LiteralPath $Output) { throw "Output already exists: $Output" }
New-Item -ItemType Directory -Path $Output -Force | Out-Null
$ReportPath = Join-Path $Output 'PREFLIGHT.json'
Call-Checked -Program $PythonExe -Parameters @((Join-Path $PSScriptRoot 'msix_preflight.py'),'--json-out',$ReportPath)
$Report = Get-Content -LiteralPath $ReportPath -Raw -Encoding UTF8 | ConvertFrom-Json
$ReadyText = if ($Report.ready) { 'true' } else { 'false' }
if ($env:GITHUB_OUTPUT) { Add-Content -LiteralPath $env:GITHUB_OUTPUT -Value "ready=$ReadyText" }
Write-Host "SOURCE_SHA=$Commit"
Write-Host "MSIX_PREFLIGHT_READY=$ReadyText"
foreach ($Reason in @($Report.blockers)) { Write-Host "MSIX_BLOCKER=$Reason" }
if ($PreflightOnly) { Write-Host 'No EXE or MSIX created (preflight only).'; return }
if (-not $Report.ready) { throw 'MSIX blocked: exact Store identity, version, approved logos, or Chromium evidence missing.' }

$Reg = Get-Content -LiteralPath (Join-Path $PSScriptRoot 'partner_center_registration.json') -Raw | ConvertFrom-Json
$Prod = Get-Content -LiteralPath (Join-Path $PSScriptRoot 'product.json') -Raw | ConvertFrom-Json
$BrowserApproval = Get-Content -LiteralPath (Join-Path $PSScriptRoot 'browser_bundle_approval.json') -Raw | ConvertFrom-Json
$Name = [string]$Prod.exeName
$AppId = [string]$Prod.appId
$Version = [string]$Reg.approvedStoreVersion
if ($Name -notmatch '^[A-Za-z][A-Za-z0-9_-]{2,50}$' -or $AppId -notmatch '^[A-Za-z][A-Za-z0-9]{2,48}$') {
    throw 'Invalid application metadata.'
}
$ScratchRoot = if ($env:RUNNER_TEMP) { $env:RUNNER_TEMP } elseif ($env:TEMP) { $env:TEMP } else { [IO.Path]::GetTempPath() }
$Scratch = Join-Path $ScratchRoot ("wea-msix-" + $Unique)
if (Test-Path -LiteralPath $Scratch) { throw 'Refusing to reuse temporary build directory.' }
$Venv = Join-Path $Scratch 'venv'
$Dist = Join-Path $Scratch 'dist'
$Work = Join-Path $Scratch 'work'
$Spec = Join-Path $Scratch 'spec'
$Stage = Join-Path $Scratch 'stage'
$Unpack = Join-Path $Scratch 'unpack'
New-Item -ItemType Directory -Path $Scratch,$Dist,$Work,$Spec,$Stage,$Unpack | Out-Null
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
    if ($LASTEXITCODE -ne 0 -or $PlaywrightVersion -cne [string]$BrowserApproval.playwright_version) {
        throw 'Installed Playwright does not match owner-approved version.'
    }
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
    $_.Name -match '^(chrome|chrome-headless-shell|headless_shell)\.exe$'
})
if ($ChromiumExes.Count -eq 0) { throw 'Frozen Chromium executable is missing.' }
# Browser fingerprint: SHA256 of UTF-8 lines "relative/path|file_sha256" sorted by path.
$BrowserLines = @(Get-ChildItem -LiteralPath $BrowserRoot -File -Recurse | Sort-Object FullName | ForEach-Object {
    $rel = $_.FullName.Substring($BrowserRoot.Length).TrimStart('\').Replace('\','/')
    $hash = (Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256).Hash.ToLowerInvariant()
    "$rel|$hash"
})
$BrowserData = [Text.Encoding]::UTF8.GetBytes(($BrowserLines -join [char]10) + [char]10)
$Hasher = [Security.Cryptography.SHA256]::Create()
try { $BrowserHash = ([BitConverter]::ToString($Hasher.ComputeHash($BrowserData))).Replace('-','').ToLowerInvariant() }
finally { $Hasher.Dispose() }
if ($BrowserHash -cne ([string]$BrowserApproval.browser_payload_sha256).ToLowerInvariant()) {
    throw 'Packaged Chromium file-tree fingerprint does not match approved input.'
}
$StageApp = Join-Path $Stage 'App'
$StageAssets = Join-Path $Stage 'Assets'
New-Item -ItemType Directory -Path $StageApp,$StageAssets | Out-Null
Get-ChildItem -LiteralPath $FrozenApp | ForEach-Object {
    Copy-Item -LiteralPath $_.FullName -Destination $StageApp -Recurse -ErrorAction Stop
}
foreach ($Logo in @('StoreLogo.png','Square44x44Logo.png','Square150x150Logo.png')) {
    Copy-Item -LiteralPath (Join-Path (Join-Path $PSScriptRoot 'assets') $Logo) -Destination $StageAssets -ErrorAction Stop
}
Set-Content -LiteralPath (Join-Path $Stage 'SOURCE_GIT_COMMIT.txt') -Value $Commit -Encoding ASCII

$IdentityName = Escape-Xml ([string]$Reg.storeIdentity.packageIdentityName)
$Publisher = Escape-Xml ([string]$Reg.storeIdentity.packageIdentityPublisher)
$PublisherName = Escape-Xml ([string]$Reg.storeIdentity.publisherDisplayName)
$Display = Escape-Xml ([string]$Reg.displayName)
$Resources = (@($Reg.manifestResources) | ForEach-Object {
    '<Resource Language="' + (Escape-Xml ([string]$_)) + '"/>'
}) -join [Environment]::NewLine
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
$MakeAppx = Get-ChildItem -LiteralPath $Sdk -Recurse -File -Filter 'MakeAppx.exe' -ErrorAction SilentlyContinue |
    Where-Object { $_.DirectoryName -match '\\x64$' } | Sort-Object FullName -Descending | Select-Object -First 1
if (-not $MakeAppx) { throw 'Windows SDK x64 MakeAppx missing.' }
$Msix = Join-Path $Output ('WebEvidenceArchiver_' + $Version + '_x64.msix')
if (Test-Path -LiteralPath $Msix) { throw 'Refusing to overwrite existing candidate.' }
Call-Checked -Program $MakeAppx.FullName -Parameters @('pack','/d',$Stage,'/p',$Msix)
Call-Checked -Program $MakeAppx.FullName -Parameters @('unpack','/p',$Msix,'/d',$Unpack)
$RoundtripExe = Join-Path (Join-Path $Unpack 'App') ($Name + '.exe')
if (-not (Test-Path -LiteralPath $RoundtripExe -PathType Leaf)) { throw 'MSIX unpacked EXE missing.' }
$ExeSha = (Get-FileHash -LiteralPath $Exe -Algorithm SHA256).Hash.ToLowerInvariant()
if ((Get-FileHash -LiteralPath $RoundtripExe -Algorithm SHA256).Hash.ToLowerInvariant() -cne $ExeSha) {
    throw 'Unpacked executable checksum differs.'
}
[xml]$Doc = Get-Content -LiteralPath (Join-Path $Unpack 'AppxManifest.xml') -Raw
$Ns = New-Object Xml.XmlNamespaceManager($Doc.NameTable)
$Ns.AddNamespace('m','http://schemas.microsoft.com/appx/manifest/foundation/windows10')
$Ns.AddNamespace('u','http://schemas.microsoft.com/appx/manifest/uap/windows10')
$id = $Doc.SelectSingleNode('/m:Package/m:Identity',$Ns)
$dn = $Doc.SelectSingleNode('/m:Package/m:Properties/m:DisplayName',$Ns)
$pd = $Doc.SelectSingleNode('/m:Package/m:Properties/m:PublisherDisplayName',$Ns)
$an = $Doc.SelectSingleNode('/m:Package/m:Applications/m:Application',$Ns)
$vn = $Doc.SelectSingleNode('/m:Package/m:Applications/m:Application/u:VisualElements',$Ns)
if (-not $id -or -not $dn -or -not $pd -or -not $an -or -not $vn) { throw 'MSIX manifest identity/display nodes missing.' }
if ($id.GetAttribute('Name') -cne [string]$Reg.storeIdentity.packageIdentityName -or
    $id.GetAttribute('Publisher') -cne [string]$Reg.storeIdentity.packageIdentityPublisher -or
    $id.GetAttribute('Version') -cne $Version -or $id.GetAttribute('ProcessorArchitecture') -cne 'x64' -or
    $dn.InnerText -cne [string]$Reg.displayName -or
    $pd.InnerText -cne [string]$Reg.storeIdentity.publisherDisplayName -or
    $vn.GetAttribute('DisplayName') -cne [string]$Reg.displayName -or
    $an.GetAttribute('Id') -cne $AppId -or $an.GetAttribute('Executable') -cne "App\$Name.exe") {
    throw 'Unpacked MSIX manifest does not match the approved Store identity.'
}
$MsixSha = (Get-FileHash -LiteralPath $Msix -Algorithm SHA256).Hash.ToLowerInvariant()
$Evidence = [ordered]@{ source_commit=$Commit; source_branch=$Branch; store_id=$Reg.storeIdentity.storeId;
    msix=$Msix; msix_sha256=$MsixSha; exe_sha256=$ExeSha; browser_tree_sha256=$BrowserHash;
    signature='UNSIGNED'; install_qa='NOT_VERIFIED'; certification='NOT_AUTHORIZED'; sales='HOLD' }
$Evidence | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath (Join-Path $Output 'BUILD_EVIDENCE.json')
Write-Host "MSIX_CANDIDATE_CREATED=$Msix"
Write-Host "MSIX_SHA256=$MsixSha"
Write-Host 'STORE_SUBMISSION=NOT_AUTHORIZED; SALES=HOLD'
