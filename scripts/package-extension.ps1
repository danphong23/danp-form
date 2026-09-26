# Compatibility entry point for the canonical release builder (Python 3.11+).
param([string]$Python = 'python')

$ErrorActionPreference = 'Stop'
& $Python (Join-Path $PSScriptRoot 'release_package.py')
if ($LASTEXITCODE -ne 0) { throw "Release builder failed with exit code $LASTEXITCODE" }
