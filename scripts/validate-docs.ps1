# Read-only validation of generated documentation, relative Markdown links and hashes.
$ErrorActionPreference = 'Stop'
$docRoot = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$issues = [System.Collections.Generic.List[string]]::new()
$specText = [System.IO.File]::ReadAllText((Join-Path $docRoot 'docs/full-specification.md'))
$sections = [regex]::Matches($specText, '(?s)<!-- source: ([^\r\n]+) -->\r?\n(.*?)(?=\r?\n---\r?\n\r?\n<!-- source:|\z)')
$modulePaths = @(Get-ChildItem -LiteralPath (Join-Path $docRoot 'docs') -Recurse -File -Filter '*.md' | Where-Object Name -ne 'full-specification.md' | ForEach-Object { [System.IO.Path]::GetRelativePath($docRoot, $_.FullName).Replace('\','/') })
$includedPaths = @()
foreach ($section in $sections) {
    $relativePath = $section.Groups[1].Value
    $includedPaths += $relativePath
    if ($relativePath -notin $modulePaths) { $issues.Add("Missing/invalid source: $relativePath"); continue }
    $expected = [System.IO.File]::ReadAllText((Join-Path $docRoot $relativePath)).Replace("`r`n","`n").Trim()
    if ($expected -cne $section.Groups[2].Value.Replace("`r`n","`n").Trim()) { $issues.Add("Consolidated content mismatch: $relativePath") }
}
foreach ($relativePath in $modulePaths) { if ($relativePath -notin $includedPaths) { $issues.Add("Unconsolidated module: $relativePath") } }
if (@($includedPaths | Select-Object -Unique).Count -ne $includedPaths.Count) { $issues.Add('Duplicate consolidated sources') }

$markdownFiles = @(Get-ChildItem -LiteralPath $docRoot -Recurse -File -Filter '*.md')
foreach ($docFile in $markdownFiles) {
    # Consolidated modules retain their source-relative links; validate those in original modules.
    if ($docFile.FullName -eq (Join-Path $docRoot 'docs/full-specification.md')) { continue }
    $body = [System.IO.File]::ReadAllText($docFile.FullName)
    $links = [regex]::Matches($body, '\[[^\]\r\n]+\]\(([^)\r\n]+)\)')
    foreach ($link in $links) {
        $target = $link.Groups[1].Value.Trim().Trim('<','>')
        if ($target -match '^[a-zA-Z][a-zA-Z0-9+.-]*:' -or $target.StartsWith('#')) { continue }
        $fileTarget = [uri]::UnescapeDataString(($target -split '#',2)[0])
        if ($fileTarget -and !(Test-Path -LiteralPath (Join-Path $docFile.DirectoryName $fileTarget))) { $issues.Add("Broken file link in $($docFile.Name): $target") }
    }
}
$entries = [System.IO.File]::ReadAllText((Join-Path $docRoot 'docs-manifest.json')) | ConvertFrom-Json
$hashLines = @(Get-Content -LiteralPath (Join-Path $docRoot 'MANIFEST_SHA256.txt'))
$manifestPaths = @($entries | ForEach-Object { $_.path })
if (@($manifestPaths | Select-Object -Unique).Count -ne $manifestPaths.Count) { $issues.Add('Duplicate manifest paths') }
foreach ($entry in $entries) {
    $entryPath = Join-Path $docRoot $entry.path
    if (!(Test-Path -LiteralPath $entryPath -PathType Leaf)) { $issues.Add("Missing manifest file: $($entry.path)"); continue }
    $actualHash = (Get-FileHash -LiteralPath $entryPath -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($actualHash -cne $entry.sha256 -or (Get-Item -LiteralPath $entryPath).Length -ne $entry.bytes) { $issues.Add("Hash/size mismatch: $($entry.path)") }
    if (($entry.sha256 + '  ' + $entry.path) -notin $hashLines) { $issues.Add("Text manifest mismatch: $($entry.path)") }
}
foreach ($docFile in $markdownFiles) {
    $relativePath = [System.IO.Path]::GetRelativePath($docRoot, $docFile.FullName).Replace('\','/')
    if ($relativePath -notin $manifestPaths) { $issues.Add("Unhashed document: $relativePath") }
}
if ($hashLines.Count -ne $entries.Count) { $issues.Add('Text manifest entry count mismatch') }
if ($issues.Count) { $issues | ForEach-Object { Write-Output $_ }; exit 1 }
Write-Output ('PASS: ' + $sections.Count + ' consolidated modules; ' + $markdownFiles.Count + ' documents; links and both hash manifests consistent.')
