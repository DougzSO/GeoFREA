# Sleep and wake events of the Windows System log, for parse_logs.py --power (COMMAND 76).
# usage: powershell -File scripts/profiling/export_power_events.ps1 -Since 2026-10-13 -Out power_events.json
param([string]$Since = '2026-10-13', [string]$Out = 'power_events.json')
$start = [datetime]$Since
$sleep = Get-WinEvent -FilterHashtable @{LogName = 'System'; ProviderName = 'Microsoft-Windows-Kernel-Power'; Id = 42; StartTime = $start} -ErrorAction SilentlyContinue
$wake = Get-WinEvent -FilterHashtable @{LogName = 'System'; ProviderName = 'Microsoft-Windows-Power-Troubleshooter'; Id = 1; StartTime = $start} -ErrorAction SilentlyContinue
$f = { param($e) [pscustomobject]@{ t = $e.TimeCreated.ToString('yyyy-MM-dd HH:mm:ss'); id = $e.Id } }
@{ sleep_wake = @($sleep | ForEach-Object { & $f $_ }); resume = @($wake | ForEach-Object { & $f $_ }) } | ConvertTo-Json -Depth 4 | Set-Content -Encoding utf8 $Out
