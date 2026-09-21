# Build the Blender Extension ZIP with __init__.py at the package root.
$ErrorActionPreference = 'Stop'
$addonRoot = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$stage = Join-Path ([System.IO.Path]::GetTempPath()) 'dan-form-package-stage'
$zipPath = Join-Path $addonRoot 'dan-form-extension.zip'
if (Test-Path -LiteralPath $stage) { Remove-Item -LiteralPath $stage -Recurse -Force }
if (Test-Path -LiteralPath $zipPath) { Remove-Item -LiteralPath $zipPath -Force }
New-Item -ItemType Directory -Path $stage | Out-Null
Copy-Item -LiteralPath (Join-Path $addonRoot 'blender_manifest.toml') -Destination $stage
# The extension archive has __init__.py at its root.  Copy the complete Python
# package contents beside it so relative imports (constants, runtime and future
# core/blender/ui packages) are present in the installed extension as well.
Copy-Item -Path (Join-Path $addonRoot 'dan_form/*') -Destination $stage -Recurse -Force
Get-ChildItem -LiteralPath $stage -Directory -Filter '__pycache__' -Recurse -Force |
    Remove-Item -Recurse -Force
Compress-Archive -Path (Join-Path $stage '*') -DestinationPath $zipPath
Write-Output "Packaged $zipPath"
