# Junction every skills/<category>/<name>/ into ~/.claude/skills/<name>. Idempotent.
# Existing junctions are recreated; a real directory with the same name is left alone.
# (Comments kept ASCII: Windows PowerShell 5.1 reads BOM-less UTF-8 as ANSI.)
$dest = Join-Path $HOME '.claude\skills'
Get-ChildItem (Join-Path $PSScriptRoot '..\skills') -Filter SKILL.md -Recurse -Depth 2 | ForEach-Object {
    $src = $_.Directory.FullName
    $link = Join-Path $dest $_.Directory.Name
    $item = Get-Item $link -Force -ErrorAction SilentlyContinue
    if ($item -and $item.LinkType -ne 'Junction') { Write-Warning "skip ${link}: real directory"; return }
    if ($item) { $item.Delete() }
    New-Item -ItemType Junction -Path $link -Target $src | Out-Null
    "$($_.Directory.Name) -> $src"
}
