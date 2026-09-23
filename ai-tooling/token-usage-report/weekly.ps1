# Weekly token-usage snapshot. Overwrites one file — the raw jsonl logs are the
# real archive, so any window can always be recomputed on demand.
$root = Join-Path $env:USERPROFILE '.claude'
$out  = Join-Path $root 'token-report-latest.txt'
$py   = Join-Path $root 'skills\token-usage-report\report.py'

& python $py --days 7 --by-tool --by-session --cost |
    Out-File -FilePath $out -Encoding utf8
