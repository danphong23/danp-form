# Build the Blender Extension ZIP with __init__.py at the package root.
$ErrorActionPreference = 'Stop'
$addonRoot = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$stage = Join-Path ([System.IO.Path]::GetTempPath()) 'dan-form-package-stage'
$zipPath = Join-Path $addonRoot 'dan-form-extension.zip'
if (Test-Path -LiteralPath $stage) { Remove-Item -LiteralPath $stage -Recurse -Force }
if (Test-Path -LiteralPath $zipPath) { Remove-Item -LiteralPath $zipPath -Force }
New-Item -ItemType Directory -Path $stage | Out-Null
Copy-Item -LiteralPath (Join-Path $addonRoot 'blender_manifest.toml') -Destination $stage
Copy-Item -LiteralPath (Join-Path $addonRoot 'dan_form/__init__.py') -Destination (Join-Path $stage '__init__.py')
Compress-Archive -Path (Join-Path $stage '*') -DestinationPath $zipPath
Write-Output "Packaged $zipPath"
