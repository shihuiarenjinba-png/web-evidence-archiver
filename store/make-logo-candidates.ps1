#requires -Version 5.1
# Candidate art only: never overwrite a designer-approved logo without explicit request.
[CmdletBinding()]
param([switch]$ReplaceCandidate)
$ErrorActionPreference="Stop"
$root=(Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$cfg=Get-Content (Join-Path $PSScriptRoot "product.json") -Raw -Encoding UTF8 | ConvertFrom-Json
if([Environment]::OSVersion.Platform -ne [PlatformID]::Win32NT){throw "Windows GDI+ required"}
Add-Type -AssemblyName System.Drawing
$dest=Join-Path $PSScriptRoot "assets"
New-Item -ItemType Directory -Force -Path $dest | Out-Null
$spec=@(
 @("StoreLogo.png",50,50),@("Square44x44Logo.png",44,44),
 @("Square150x150Logo.png",150,150),@("Wide310x150Logo.png",310,150)
)
foreach($item in $spec){
 $name=$item[0];[int]$w=$item[1];[int]$h=$item[2]
 $target=Join-Path $dest $name
 if((Test-Path $target) -and -not $ReplaceCandidate){Write-Host "KEEP_EXISTING $target";continue}
 $bmp=[Drawing.Bitmap]::new($w,$h)
 $g=[Drawing.Graphics]::FromImage($bmp)
 $dark=[Drawing.SolidBrush]::new([Drawing.Color]::FromArgb(18,31,49))
 $gold=[Drawing.SolidBrush]::new([Drawing.Color]::FromArgb(206,168,98))
 $light=[Drawing.SolidBrush]::new([Drawing.Color]::FromArgb(235,239,243))
 $pen=[Drawing.Pen]::new([Drawing.Color]::FromArgb(206,168,98),[float]([Math]::Max(1.4,$h*0.025)))
 try{
  $g.SmoothingMode=[Drawing.Drawing2D.SmoothingMode]::AntiAlias
  $g.TextRenderingHint=[Drawing.Text.TextRenderingHint]::AntiAliasGridFit
  $g.FillRectangle($dark,0,0,$w,$h)
  [int]$x=[Math]::Round($h*0.20);[int]$y=[Math]::Round($h*0.16)
  [int]$boxW=[Math]::Round($h*0.57);[int]$boxH=[Math]::Round($h*0.68)
  $g.FillRectangle($gold,$x,$y,$boxW,$boxH)
  $g.FillRectangle($dark,($x+[int]($h*0.075)),($y+[int]($h*0.07)),($boxW-[int]($h*0.14)),($boxH-[int]($h*0.14)))
  for($k=0;$k -lt 3;$k++){
   [int]$sy=$y+[int]($boxH*(0.28+$k*0.19))
   $g.FillRectangle($light,$x+[int]($h*0.13),$sy,[int]($h*0.27),[int]([Math]::Max(1,$h*0.018)))
  }
  if($w -gt $h){
   $f=[Drawing.Font]::new("Segoe UI",[float]($h*0.26),[Drawing.FontStyle]::Bold,[Drawing.GraphicsUnit]::Pixel)
   try{$g.DrawString([string]$cfg.brandAbbreviation,$f,$light,[float]($h*0.90),[float]($h*0.32))}finally{$f.Dispose()}
  }
  $bmp.Save($target,[Drawing.Imaging.ImageFormat]::Png)
  Write-Host "BRAND_CANDIDATE $name $w x $h"
 }finally{$g.Dispose();$bmp.Dispose();$dark.Dispose();$gold.Dispose();$light.Dispose();$pen.Dispose()}
}
Write-Host "Generated graphics are candidates. Real commercial brand approval remains required."
