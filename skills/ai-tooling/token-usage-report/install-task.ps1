# Registers the weekly snapshot as a Windows scheduled task. Needs elevation —
# run via: Start-Process powershell -Verb RunAs -ArgumentList '-File', <this>
$ErrorActionPreference = 'Stop'
$home_ = $env:USERPROFILE
$log = Join-Path $home_ '.claude\task-install-result.txt'
try {
    $ps1 = Join-Path $home_ '.claude\skills\token-usage-report\weekly.ps1'
    $act = New-ScheduledTaskAction -Execute 'powershell.exe' `
        -Argument "-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File `"$ps1`""
    $trg = New-ScheduledTaskTrigger -Weekly -DaysOfWeek Monday -At 09:07
    # Run as the logged-in user so it reads that user's ~/.claude logs, not SYSTEM's.
    $prc = New-ScheduledTaskPrincipal -UserId "$env:USERDOMAIN\$env:USERNAME" -RunLevel Limited
    Register-ScheduledTask -TaskName 'ClaudeTokenReport' -Action $act -Trigger $trg `
        -Principal $prc -Description 'Weekly Claude Code token usage snapshot' -Force | Out-Null
    $next = (Get-ScheduledTaskInfo -TaskName 'ClaudeTokenReport').NextRunTime
    "OK  registered ClaudeTokenReport, next run: $next" | Out-File $log -Encoding utf8
} catch {
    "FAIL $($_.Exception.Message)" | Out-File $log -Encoding utf8
}
