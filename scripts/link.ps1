# Junction shared skills into Claude and Codex user skill directories. Idempotent.
# Existing junctions are recreated; a real directory with the same name is left alone.
# (Comments kept ASCII: Windows PowerShell 5.1 reads BOM-less UTF-8 as ANSI.)
$codexExcluded = @(
    'codex-imagegen',
    'funplay-cocos-mcp'
)
$targets = @(
    @{ Name = 'claude'; Path = (Join-Path $HOME '.claude\skills'); Excluded = @() },
    @{ Name = 'codex'; Path = (Join-Path $HOME '.agents\skills'); Excluded = $codexExcluded }
)
$skills = Get-ChildItem (Join-Path $PSScriptRoot '..\skills') -Filter SKILL.md -Recurse -Depth 2

foreach ($target in $targets) {
    New-Item -ItemType Directory -Path $target.Path -Force | Out-Null
    foreach ($skill in $skills) {
        $name = $skill.Directory.Name
        if ($target.Excluded -contains $name) {
            "[$($target.Name)] skip ${name}: platform-specific or pending adaptation"
            continue
        }

        $src = $skill.Directory.FullName
        $link = Join-Path $target.Path $name
        $item = Get-Item $link -Force -ErrorAction SilentlyContinue
        if ($item -and $item.LinkType -ne 'Junction') {
            Write-Warning "[$($target.Name)] skip ${link}: real directory"
            continue
        }
        if ($item) { $item.Delete() }
        New-Item -ItemType Junction -Path $link -Target $src | Out-Null
        "[$($target.Name)] $name -> $src"
    }
}
