#requires -Version 5.1
# Builds an identity-matched MSIX candidate. Never installs, uploads, or submits.
[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)] [ValidatePattern('^\d+\.\d+\.\d+\.0$')] [string]$StoreVersion,
    [switch]$ApprovedArtwork,
    [switch]$Build
)
$ErrorActionPreference = "Stop"
$repo = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$registration = Get-Content -LiteralPath (Join-Path $PSScriptRoot "partner_center_registration.json") -Raw -Encoding UTF8 | ConvertFrom-Json
$product = Get-Content -LiteralPath (Join-Path $PSScriptRoot "product.json") -Raw -Encoding UTF8 | ConvertFrom-Json
if ($registration.repository -cne (Split-Path $repo -Leaf) -or $registration.displayName -cne $product.displayName) {
    throw "Store registration and product.json do not match."
}
if ($registration.partnerCenterState -notin @('EXISTING_CONFIRMED', 'RESERVED_CONFIRMED', 'SUBMISSION_DRAFT_CONFIRMED')) {
    throw "Official Partner Center identity has not been confirmed for $($product.displayName)."
}
$i = $registration.storeIdentity
foreach ($field in @('storeId', 'packageIdentityName', 'packageIdentityPublisher', 'publisherDisplayName', 'packageFamilyName')) {
    if ([string]::IsNullOrWhiteSpace($i.$field)) {
        throw "Missing official $field; copy its real value from Partner Center."
    }
}
if (-not $i.packageFamilyName.StartsWith(($i.packageIdentityName + "_"), [StringComparison]::Ordinal)) {
    throw "Official PFN does not start with the package Identity Name."
}
if (-not $ApprovedArtwork) {
    throw "Artwork owner approval not acknowledged. Review copyright and 4 approved PNGs and rerun with -ApprovedArtwork."
}
$version = @($StoreVersion.Split('.') | ForEach-Object { [int]$_ })
if ($version[0] -lt 1 -or @($version | Where-Object { $_ -gt 65535 }).Count -gt 0) {
    throw "MSIX StoreVersion must begin above 0 and every component must be 0..65535."
}
$names = @('STORE_IDENTITY_NAME','STORE_PUBLISHER','STORE_PUBLISHER_DISPLAY_NAME', 'STORE_VERSION', 'STORE_IDENTITY_CONFIRMED', 'STORE_BRAND_APPROVED')
$saved = @{}
foreach ($name in $names) { $saved[$name] = [Environment]::GetEnvironmentVariable($name,'Process') }
try {
    $env:STORE_IDENTITY_NAME = [string]$i.packageIdentityName
    $env:STORE_PUBLISHER = [string]$i.packageIdentityPublisher
    $env:STORE_PUBLISHER_DISPLAY_NAME = [string]$i.publisherDisplayName
    $env:STORE_VERSION = $StoreVersion
    $env:STORE_IDENTITY_CONFIRMED = 'YES'
    $env:STORE_BRAND_APPROVED = 'YES'
    $builder = Join-Path $PSScriptRoot 'build-msix.ps1'
    if (-not (Test-Path -LiteralPath $builder)) { throw "Missing store/build-msix.ps1" }
    if ($Build) {
        & $builder
    } else {
        & $builder -PreflightOnly
    }
    if (-not $?) { throw 'MSIX builder failed.' }
    Write-Host ("PARTNER_CENTER_IDENTITY_MATCHED: " + $i.packageIdentityName)
    Write-Host ("STORE_ID: " + $i.storeId)
    if (-not $Build) { Write-Host "PRECHECK_ONLY: no package generated" }
} finally {
    foreach ($name in $names) {
        [Environment]::SetEnvironmentVariable($name,$saved[$name],'Process')
    }
}
