#Requires -Version 5.1
<#
.SYNOPSIS
    Log rotation script for NextDNS Blocker on Windows.

.DESCRIPTION
    This script manages log files for NextDNS Blocker by:
    - Removing logs older than the retention period
    - Keeping only a specified number of recent log files
    - Optionally compressing old logs before deletion

.PARAMETER RetentionDays
    Number of days to retain logs. Default: 7

.PARAMETER MaxFiles
    Maximum number of log files to keep per type. Default: 5

.PARAMETER Compress
    Compress old logs before deletion (not implemented yet).

.PARAMETER DryRun
    Show what would be deleted without actually deleting.

.PARAMETER Install
    Install this script as a scheduled task to run daily.

.PARAMETER Uninstall
    Remove the scheduled task.

.EXAMPLE
    .\setup-logrotate.ps1
    Run log rotation with default settings.

.EXAMPLE
    .\setup-logrotate.ps1 -RetentionDays 14 -MaxFiles 10
    Keep logs for 14 days and maintain up to 10 files per type.

.EXAMPLE
    .\setup-logrotate.ps1 -DryRun
    Show what would be deleted without actually deleting.

.EXAMPLE
    .\setup-logrotate.ps1 -Install
    Install as a daily scheduled task.

.NOTES
    Log files are stored in: %LOCALAPPDATA%\nextdns-blocker\logs\
#>

[CmdletBinding()]
param(
    [int]$RetentionDays = 7,
    [int]$MaxFiles = 5,
    [switch]$Compress,
    [switch]$DryRun,
    [switch]$Install,
    [switch]$Uninstall
)

$ErrorActionPreference = "Stop"

# Configuration
$AppName = "nextdns-blocker"
$TaskName = "NextDNS-Blocker-LogRotate"
$LogDir = Join-Path $env:LOCALAPPDATA "$AppName\logs"

function Write-Step {
    param([string]$Message)
    Write-Host "  $Message" -ForegroundColor White
}

function Write-Success {
    param([string]$Message)
    Write-Host "  $Message" -ForegroundColor Green
}

function Write-DryRun {
    param([string]$Message)
    Write-Host "  [DRY-RUN] $Message" -ForegroundColor Yellow
}

function Get-LogFiles {
    <#
    .SYNOPSIS
        Get all log files in the log directory.
    #>

    if (-not (Test-Path $LogDir)) {
        return @()
    }

    Get-ChildItem -Path $LogDir -Filter "*.log" -File -ErrorAction SilentlyContinue
}

function Remove-OldLogs {
    <#
    .SYNOPSIS
        Remove logs older than retention period.
    #>
    param(
        [int]$Days,
        [switch]$DryRun
    )

    $cutoffDate = (Get-Date).AddDays(-$Days)
    $oldLogs = Get-LogFiles | Where-Object { $_.LastWriteTime -lt $cutoffDate }

    if ($oldLogs.Count -eq 0) {
        Write-Step "No logs older than $Days days found"
        return 0
    }

    $removed = 0
    foreach ($log in $oldLogs) {
        if ($DryRun) {
            Write-DryRun "Would remove: $($log.Name) (Last modified: $($log.LastWriteTime))"
        }
        else {
            try {
                Remove-Item $log.FullName -Force
                Write-Step "Removed: $($log.Name)"
                $removed++
            }
            catch {
                Write-Warning "Failed to remove $($log.Name): $_"
            }
        }
    }

    return $removed
}

function Limit-LogFiles {
    <#
    .SYNOPSIS
        Keep only the most recent N log files.
    #>
    param(
        [int]$MaxCount,
        [switch]$DryRun
    )

    # Group logs by base name (without date suffix if any)
    $allLogs = Get-LogFiles | Sort-Object LastWriteTime -Descending

    if ($allLogs.Count -le $MaxCount) {
        Write-Step "Log count ($($allLogs.Count)) is within limit ($MaxCount)"
        return 0
    }

    $logsToRemove = $allLogs | Select-Object -Skip $MaxCount
    $removed = 0

    foreach ($log in $logsToRemove) {
        if ($DryRun) {
            Write-DryRun "Would remove: $($log.Name) (keeping newest $MaxCount)"
        }
        else {
            try {
                Remove-Item $log.FullName -Force
                Write-Step "Removed: $($log.Name)"
                $removed++
            }
            catch {
                Write-Warning "Failed to remove $($log.Name): $_"
            }
        }
    }

    return $removed
}

function Install-ScheduledTask {
    <#
    .SYNOPSIS
        Install this script as a daily scheduled task.
    #>

    $scriptPath = $MyInvocation.ScriptName
    if (-not $scriptPath) {
        $scriptPath = $PSCommandPath
    }

    if (-not $scriptPath -or -not (Test-Path $scriptPath)) {
        Write-Error "Cannot determine script path for scheduled task"
        return $false
    }

    # Check if task already exists
    $existingTask = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue

    if ($existingTask) {
        Write-Step "Task '$TaskName' already exists. Updating..."
        Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
    }

    # Create task action
    $action = New-ScheduledTaskAction `
        -Execute "powershell.exe" `
        -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$scriptPath`" -RetentionDays $RetentionDays -MaxFiles $MaxFiles"

    # Create trigger (daily at 3 AM)
    $trigger = New-ScheduledTaskTrigger -Daily -At "3:00AM"

    # Create settings
    $settings = New-ScheduledTaskSettingsSet `
        -AllowStartIfOnBatteries `
        -DontStopIfGoingOnBatteries `
        -StartWhenAvailable

    # Register task
    try {
        Register-ScheduledTask `
            -TaskName $TaskName `
            -Action $action `
            -Trigger $trigger `
            -Settings $settings `
            -Description "Daily log rotation for NextDNS Blocker" `
            | Out-Null

        Write-Success "Scheduled task '$TaskName' installed successfully"
        Write-Step "Runs daily at 3:00 AM"
        return $true
    }
    catch {
        Write-Error "Failed to create scheduled task: $_"
        return $false
    }
}

function Uninstall-ScheduledTask {
    <#
    .SYNOPSIS
        Remove the scheduled task.
    #>

    $existingTask = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue

    if (-not $existingTask) {
        Write-Step "Task '$TaskName' not found"
        return $true
    }

    try {
        Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
        Write-Success "Scheduled task '$TaskName' removed"
        return $true
    }
    catch {
        Write-Error "Failed to remove scheduled task: $_"
        return $false
    }
}

function Show-Summary {
    param(
        [int]$RemovedByAge,
        [int]$RemovedByCount
    )

    Write-Host ""
    Write-Host "  Summary:" -ForegroundColor Cyan
    Write-Host "    Removed by age:   $RemovedByAge files"
    Write-Host "    Removed by count: $RemovedByCount files"
    Write-Host "    Total removed:    $($RemovedByAge + $RemovedByCount) files"
    Write-Host ""
}

# =============================================================================
# Main Script
# =============================================================================

Write-Host ""
Write-Host "  NextDNS Blocker Log Rotation" -ForegroundColor Cyan
Write-Host "  ============================" -ForegroundColor Cyan
Write-Host ""

# Handle install/uninstall
if ($Install) {
    if (Install-ScheduledTask) {
        exit 0
    }
    else {
        exit 1
    }
}

if ($Uninstall) {
    if (Uninstall-ScheduledTask) {
        exit 0
    }
    else {
        exit 1
    }
}

# Check if log directory exists
if (-not (Test-Path $LogDir)) {
    Write-Step "Log directory does not exist: $LogDir"
    Write-Step "Nothing to rotate."
    exit 0
}

Write-Step "Log directory: $LogDir"
Write-Step "Retention: $RetentionDays days"
Write-Step "Max files: $MaxFiles"

if ($DryRun) {
    Write-Host ""
    Write-Host "  [DRY-RUN MODE - No files will be deleted]" -ForegroundColor Yellow
}

Write-Host ""

# Remove old logs
Write-Step "Checking for logs older than $RetentionDays days..."
$removedByAge = Remove-OldLogs -Days $RetentionDays -DryRun:$DryRun

Write-Host ""

# Limit number of log files
Write-Step "Checking log file count (limit: $MaxFiles)..."
$removedByCount = Limit-LogFiles -MaxCount $MaxFiles -DryRun:$DryRun

# Show summary
Show-Summary -RemovedByAge $removedByAge -RemovedByCount $removedByCount

if ($DryRun) {
    Write-Host "  Run without -DryRun to actually delete files." -ForegroundColor Yellow
    Write-Host ""
}
