<#
.SYNOPSIS
  Unattended round of GeoFREA (COMMAND 78): the countries one after the other, every phase to potential_maps, and a check of every artifact
  against the manifest saved before the round.

.DESCRIPTION
  Run it from a PowerShell window with Claude Code, VS Code and the browser closed (the round needs about 4 GB free for IND and BRA):

      powershell -ExecutionPolicy Bypass -File D:\Douglas\DOUTORADO\GeoFREA_77\scripts\run_unattended.ps1

  For each country, in order:
    1. the available memory and the other GeoFREA processes are checked; the manifest of the country is copied to
       <data>\outputs\<ISO>\unattended\<stamp>\manifest_before.json;
    2. the aligned layers made by the revision in -AdoptRevision are adopted under the current code (scripts\adopt_aligned_cache_keys.py, D-core-044:
       it stops unless the equivalence proof in -AdoptProof says "equal" for these two code versions; without it F2a of BRA would be about 42,000 s);
    3. `main.py <ISO> --phases <all> --rerun <all>` runs in the worktree, with the computer kept awake, its output in the log of the run, and the available memory
       sampled every -PollSeconds into memory.csv. Under -MinFreeMb the process tree is stopped, the country is marked ABORTADO and the round goes on to the next
       one: the manifest is written after each phase, so it keeps the phases that finished;
    4. scripts\unattended_check.py compares the content hash of every artifact of the phases that ran with the manifest saved in step 1 and writes
       <data>\outputs\<ISO>\unattended_check.json (IDENTICO or DIFERENTE per artifact, and the wall, awake and CPU time and the peak memory of each phase).
  The exit code is 0 only when every country is IDENTICO.

  The round is done when the window prints "ROUND FINISHED" and the file <data>\unattended_round_<stamp>.json exists.

.PARAMETER Countries      Countries to run, in order (default IND, BRA).
.PARAMETER Worktree       The tree to run (default: the one this script is in; it must be the branch perf/77).
.PARAMETER Python         python.exe to use (default: the .venv of the main checkout of the repository).
.PARAMETER Phases         Comma list of the phases (default: the twelve phases to potential_maps).
.PARAMETER MinFreeMb      Available memory under which the current country is stopped (default 400).
.PARAMETER MinStartMb     Available memory that a round needs to start (default 2000, the rule of CONVENTIONS "Memory before a cold round").
.PARAMETER AdoptRevision  The revision under which the aligned layers of the countries were made (default perf/75-performance).
.PARAMETER AdoptProof     The equivalence proof the adoption needs, relative to the worktree.
.PARAMETER SkipAdopt      Do not adopt (the layers are computed again if their key changed).
.PARAMETER DryRun         Do the checks of the start and print what would run.
#>
[CmdletBinding()]
param(
    [string[]]$Countries = @('IND', 'BRA'),
    [string]$Worktree = (Split-Path -Parent $PSScriptRoot),
    [string]$Python = '',
    [string]$Phases = 'data_acquisition,data_quality_audit,grid_alignment,siting_layers,land_eligibility,external_inputs,climate_forcing,hazard_context,climate_maps,overview,technical_potential,potential_maps',
    [int]$MinFreeMb = 400,
    [int]$MinStartMb = 2000,
    [int]$PollSeconds = 15,
    [string]$AdoptRevision = 'perf/75-performance',
    [string]$AdoptProof = 'docs/_audit/cumulative_equivalence_77_PRT.json',
    [switch]$SkipAdopt,
    [switch]$DryRun
)

$ErrorActionPreference = 'Stop'
$Stamp = Get-Date -Format 'yyyyMMdd_HHmmss'

function Write-Log([string]$Message) {
    $line = '{0} {1}' -f (Get-Date -Format 'yyyy-MM-dd HH:mm:ss'), $Message
    Write-Host $line
    if ($script:RoundLog) { Add-Content -Path $script:RoundLog -Value $line -Encoding utf8 }
}

function Get-AvailableMb {
    try {
        if (-not $script:MemCounter) { $script:MemCounter = New-Object System.Diagnostics.PerformanceCounter('Memory', 'Available MBytes') }
        return [int]$script:MemCounter.NextValue()
    } catch {
        return [int]((Get-CimInstance Win32_OperatingSystem).FreePhysicalMemory / 1024)
    }
}

function Get-OtherGeoFreaProcesses {
    Get-CimInstance Win32_Process -Filter "Name = 'python.exe' OR Name = 'pythonw.exe'" |
        Where-Object { $_.CommandLine -match 'main\.py|run_unattended|check_aligned|adopt_aligned|bench_guard|bench_phase|prof_phase' -and $_.ProcessId -ne $PID }
}

function Read-EnvValue([string]$File, [string]$Name) {
    foreach ($line in Get-Content $File) {
        if ($line -match ('^\s*' + [regex]::Escape($Name) + '\s*=\s*(.+?)\s*$')) { return $Matches[1].Trim('"').Trim("'") }
    }
    return $null
}

function Stop-Tree([int]$ProcessId) { & taskkill.exe /PID $ProcessId /T /F | Out-Null }

# Runs a command in the worktree, sampling the available memory; returns @{ ExitCode; Aborted; MinFreeMb }.
function Invoke-Monitored([string[]]$Arguments, [string]$LogFile, [string]$MemoryCsv) {
    $err = [System.IO.Path]::ChangeExtension($LogFile, '.err.txt')
    $p = Start-Process -FilePath $Python -ArgumentList $Arguments -WorkingDirectory $Worktree -RedirectStandardOutput $LogFile `
        -RedirectStandardError $err -PassThru -NoNewWindow
    $null = $p.Handle   # keeps the exit code readable after the process ends
    $minFree = [int]::MaxValue
    $aborted = $null
    while (-not $p.WaitForExit($PollSeconds * 1000)) {
        $free = Get-AvailableMb
        if ($free -lt $minFree) { $minFree = $free }
        Add-Content -Path $MemoryCsv -Value ('{0},{1}' -f (Get-Date -Format 'yyyy-MM-dd HH:mm:ss'), $free)
        if ($free -lt $MinFreeMb) {
            $aborted = "available memory fell to $free MB (limit $MinFreeMb MB)"
            Write-Log "LOW MEMORY: $aborted; stopping the process tree $($p.Id)"
            Stop-Tree $p.Id
            $null = $p.WaitForExit(30000)
            break
        }
    }
    $code = if ($aborted) { -1 } else { $p.ExitCode }
    return @{ ExitCode = $code; Aborted = $aborted; MinFreeMb = $(if ($minFree -eq [int]::MaxValue) { $null } else { $minFree }) }
}

# ---- the start: resolve everything and check the machine ---------------------------------------------------------------------------------
$Worktree = (Resolve-Path $Worktree).Path
if (-not $Python) {
    $common = (& git -C $Worktree rev-parse --git-common-dir).Trim()
    $mainRepo = Split-Path -Parent (Resolve-Path (Join-Path $Worktree $common)).Path
    $Python = Join-Path $mainRepo '.venv\Scripts\python.exe'
}
if (-not (Test-Path $Python)) { throw "python.exe not found: $Python" }
$envFile = Join-Path $Worktree '.env'
if (-not (Test-Path $envFile)) { throw "no .env in $Worktree (it holds GEOFREA_DATA_DIR)" }
$Data = Read-EnvValue $envFile 'GEOFREA_DATA_DIR'
if (-not $Data -or -not (Test-Path $Data)) { throw "GEOFREA_DATA_DIR is not set or does not exist: $Data" }
$env:GEOFREA_DATA_DIR = $Data
$env:PYTHONPATH = Join-Path $Worktree 'src'   # the venv is installed from the main checkout; the round runs the code of this worktree
$env:PYTHONUNBUFFERED = '1'
$script:RoundLog = Join-Path $Data "unattended_round_$Stamp.log"

$branch = (& git -C $Worktree rev-parse --abbrev-ref HEAD).Trim()
$head = (& git -C $Worktree rev-parse HEAD).Trim()
$dirty = [bool](& git -C $Worktree status --porcelain -- src config main.py)
$startFree = Get-AvailableMb
Write-Log "round $Stamp: countries $($Countries -join ', '); worktree $Worktree ($branch @ $($head.Substring(0, 10))$(if ($dirty) { ', UNCOMMITTED CHANGES in src/config/main.py' }))"
Write-Log "available memory at the start: $startFree MB (total $([int]((Get-CimInstance Win32_ComputerSystem).TotalPhysicalMemory / 1MB)) MB)"
$others = @(Get-OtherGeoFreaProcesses)
if ($others.Count) {
    $others | ForEach-Object { Write-Log "another GeoFREA process is running: pid $($_.ProcessId) $($_.CommandLine)" }
    throw 'another GeoFREA python process is active; the round does not start'
}
if ($startFree -lt $MinStartMb) {
    throw "only $startFree MB are available (the round needs $MinStartMb MB): close Claude Code, VS Code and the browser and run again"
}
$settingsText = Get-Content (Join-Path $Worktree 'config\settings.yaml') -Raw
if ($settingsText -notmatch '(?m)^figures:\s*summary\s*$') { throw 'config\settings.yaml does not say "figures: summary": the round would draw every map' }
if ($settingsText -notmatch '(?m)^keep_awake:\s*true\s*$') { Write-Log 'WARNING: settings.yaml keep_awake is not true; this script asks the system to stay awake itself' }

if ($DryRun) {
    foreach ($iso in $Countries) { Write-Log "DRY RUN: would run $iso ($Phases), adopt from $AdoptRevision with $AdoptProof" }
    return
}

# keep the computer awake for the life of this script (the pipeline asks as well: main.py keep_awake)
Add-Type -Namespace Win32 -Name Power -MemberDefinition '[System.Runtime.InteropServices.DllImport("kernel32.dll")] public static extern uint SetThreadExecutionState(uint esFlags);'
[void][Win32.Power]::SetThreadExecutionState(0x80000001)   # ES_CONTINUOUS | ES_SYSTEM_REQUIRED

$roundStart = Get-Date
$results = @()
try {
    foreach ($iso in $Countries) {
        $iso = $iso.ToUpper()
        $outDir = Join-Path $Data "outputs\$iso"
        $manifest = Join-Path $outDir 'manifest.json'
        $runDir = Join-Path $outDir "unattended\$Stamp"
        New-Item -ItemType Directory -Force -Path $runDir | Out-Null
        $mem = Join-Path $runDir 'memory.csv'
        Set-Content -Path $mem -Value 'time,available_mb' -Encoding utf8
        if (-not (Test-Path $manifest)) { Write-Log "$iso: no manifest, skipped"; $results += @{ country = $iso; verdict = 'SEM_MANIFEST' }; continue }
        Copy-Item $manifest (Join-Path $runDir 'manifest_before.json') -Force
        $started = (Get-Date).ToUniversalTime().ToString('yyyy-MM-ddTHH:mm:ssZ')
        $aborted = $null
        $free = Get-AvailableMb
        Write-Log "$iso: start; available memory $free MB; manifest saved in $runDir"
        if ($free -lt $MinFreeMb) { $aborted = "available memory is $free MB at the start of $iso" }

        if (-not $aborted -and -not $SkipAdopt) {
            Write-Log "$iso: adopting the aligned layers made by $AdoptRevision"
            $adopt = Invoke-Monitored @('scripts\adopt_aligned_cache_keys.py', $iso, '--revision', $AdoptRevision, '--proof', $AdoptProof) (Join-Path $runDir 'adopt.log.txt') $mem
            if ($adopt.Aborted) { $aborted = $adopt.Aborted }
            elseif ($adopt.ExitCode -ne 0) {
                $aborted = "the adoption of the aligned layers failed (exit $($adopt.ExitCode), see $runDir\adopt.log.txt): F2a would be computed from the start, so $iso does not run"
                Write-Log "$iso: $aborted"
            }
        }
        if (-not $aborted) {
            Write-Log "$iso: running $Phases"
            $run = Invoke-Monitored @('main.py', $iso, '--phases', $Phases, '--rerun', $Phases) (Join-Path $runDir 'run.log.txt') $mem
            if ($run.Aborted) { $aborted = $run.Aborted }
            elseif ($run.ExitCode -eq 75) { $aborted = 'main.py did not start: less than 2 GB available for a cold phase (exit 75)' }
            elseif ($run.ExitCode -ne 0) { Write-Log "$iso: main.py ended with exit code $($run.ExitCode) (see $runDir\run.log.txt)" }
            Write-Log "$iso: main.py ended (exit $($run.ExitCode)); minimum available memory $($run.MinFreeMb) MB"
        }

        $power = Join-Path $runDir 'power_events.json'
        & powershell.exe -NoProfile -ExecutionPolicy Bypass -File (Join-Path $Worktree 'scripts\profiling\export_power_events.ps1') -Since ($roundStart.AddDays(-1).ToString('yyyy-MM-dd')) -Out $power | Out-Null
        $checkArgs = @('scripts\unattended_check.py', $iso, '--before', (Join-Path $runDir 'manifest_before.json'), '--after', $manifest,
            '--out', (Join-Path $outDir 'unattended_check.json'), '--phases', $Phases, '--power', $power, '--started', $started)
        if ($aborted) { $checkArgs += @('--aborted', $aborted) }
        $summaryLine = & $Python @checkArgs
        Write-Log "$iso: $summaryLine"
        $check = Get-Content (Join-Path $outDir 'unattended_check.json') -Raw | ConvertFrom-Json
        foreach ($row in $check.phases) {
            Write-Log ('  {0,-20} {1,-8} awake {2,8} s  cpu {3,8} s  peak {4,6} MB' -f $row.phase, $row.status, $row.awake_s, $row.cpu_s, $row.peak_rss_mb)
        }
        $results += @{ country = $iso; verdict = $check.verdict; aborted = $aborted; different = @($check.different); check = (Join-Path $outDir 'unattended_check.json'); run_dir = $runDir }
    }
} finally {
    [void][Win32.Power]::SetThreadExecutionState(0x80000000)   # ES_CONTINUOUS: release
}

$summaryFile = Join-Path $Data "unattended_round_$Stamp.json"
@{ stamp = $Stamp; branch = $branch; head = $head; dirty = $dirty; start_available_mb = $startFree; results = $results } | ConvertTo-Json -Depth 6 | Set-Content -Path $summaryFile -Encoding utf8
Write-Log "ROUND FINISHED: $(($results | ForEach-Object { '{0} {1}' -f $_.country, $_.verdict }) -join '; ')  (summary $summaryFile, log $script:RoundLog)"
if ($results | Where-Object { $_.verdict -ne 'IDENTICO' }) { exit 1 }
