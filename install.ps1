#Requires -Version 5.1
<#
.SYNOPSIS
    NextDNS Blocker installation script for Windows.

.DESCRIPTION
    This script installs NextDNS Blocker on Windows systems. It:
    - Checks for Python installation
    - Installs the package via pip
    - Runs the interactive setup wizard
    - Configures Windows Task Scheduler for automatic sync

.PARAMETER SkipScheduler
    Skip Task Scheduler setup after installation.

.PARAMETER NonInteractive
    Run in non-interactive mode using environment variables.

.PARAMETER Upgrade
    Upgrade an existing installation.

.EXAMPLE
    .\install.ps1
    Standard interactive installation.

.EXAMPLE
    .\install.ps1 -SkipScheduler
    Install without setting up Task Scheduler.

.EXAMPLE
    $env:NEXTDNS_API_KEY = "your-key"; $env:NEXTDNS_PROFILE_ID = "abc123"; .\install.ps1 -NonInteractive
    Non-interactive installation using environment variables.

.NOTES
    Requires Python 3.9 or higher.
    Run in PowerShell as regular user (not elevated).
#>

[CmdletBinding()]
param(
    [switch]$SkipScheduler,
    [switch]$NonInteractive,
    [switch]$Upgrade
)

$ErrorActionPreference = "Stop"

# Configuration
$MinPythonVersion = [Version]"3.9"
$PackageName = "nextdns-blocker"

function Write-Header {
    param([string]$Message)
    Write-Host ""
    Write-Host "  $Message" -ForegroundColor Cyan
    Write-Host "  $('=' * $Message.Length)" -ForegroundColor Cyan
    Write-Host ""
}

function Write-Step {
    param([string]$Message)
    Write-Host "  $Message" -ForegroundColor White
}

function Write-Success {
    param([string]$Message)
    Write-Host "  $Message" -ForegroundColor Green
}

function Write-Warning {
    param([string]$Message)
    Write-Host "  Warning: $Message" -ForegroundColor Yellow
}

function Write-Error {
    param([string]$Message)
    Write-Host "  Error: $Message" -ForegroundColor Red
}

function Test-PythonInstallation {
    <#
    .SYNOPSIS
        Check if Python is installed and meets minimum version requirement.
    #>

    $pythonCommands = @("python", "python3", "py")

    foreach ($cmd in $pythonCommands) {
        try {
            $versionOutput = & $cmd --version 2>&1
            if ($LASTEXITCODE -eq 0 -and $versionOutput -match "Python (\d+\.\d+\.\d+)") {
                $installedVersion = [Version]$Matches[1]
                if ($installedVersion -ge $MinPythonVersion) {
                    return @{
                        Command = $cmd
                        Version = $installedVersion
                    }
                }
            }
        }
        catch {
            # Command not found, try next
            continue
        }
    }

    return $null
}

function Install-Package {
    param(
        [string]$PythonCommand,
        [switch]$Upgrade
    )

    $pipArgs = @("-m", "pip", "install")

    if ($Upgrade) {
        $pipArgs += "--upgrade"
    }

    $pipArgs += $PackageName

    Write-Step "Installing $PackageName..."
    & $PythonCommand @pipArgs

    if ($LASTEXITCODE -ne 0) {
        throw "Failed to install $PackageName"
    }

    Write-Success "$PackageName installed successfully"
}

function Test-PackageInstalled {
    param([string]$PythonCommand)

    try {
        & $PythonCommand -m nextdns_blocker --version 2>&1 | Out-Null
        return $LASTEXITCODE -eq 0
    }
    catch {
        return $false
    }
}

function Invoke-Setup {
    param(
        [string]$PythonCommand,
        [switch]$NonInteractive
    )

    Write-Step "Running setup wizard..."
    Write-Host ""

    $initArgs = @("-m", "nextdns_blocker", "init")

    if ($NonInteractive) {
        $initArgs += "--non-interactive"
    }

    & $PythonCommand @initArgs

    if ($LASTEXITCODE -ne 0) {
        throw "Setup wizard failed"
    }
}

function Install-TaskScheduler {
    param([string]$PythonCommand)

    Write-Step "Installing Task Scheduler jobs..."

    & $PythonCommand -m nextdns_blocker watchdog install

    if ($LASTEXITCODE -ne 0) {
        Write-Warning "Failed to install Task Scheduler jobs"
        Write-Host "  You can install manually with: nextdns-blocker watchdog install"
        return $false
    }

    return $true
}

function Show-PostInstallInfo {
    Write-Host ""
    Write-Success "Installation complete!"
    Write-Host ""
    Write-Host "  Commands:" -ForegroundColor Cyan
    Write-Host "    nextdns-blocker status    - Show blocking status"
    Write-Host "    nextdns-blocker sync      - Manual sync"
    Write-Host "    nextdns-blocker pause 30  - Pause for 30 min"
    Write-Host "    nextdns-blocker health    - Health check"
    Write-Host ""
    Write-Host "  Task Scheduler:" -ForegroundColor Cyan
    Write-Host "    taskschd.msc              - Open Task Scheduler"
    Write-Host "    schtasks /query /tn NextDNS-Blocker-Sync"
    Write-Host ""
    Write-Host "  Logs:" -ForegroundColor Cyan
    Write-Host "    $env:LOCALAPPDATA\nextdns-blocker\logs\"
    Write-Host ""
}

# =============================================================================
# Main Script
# =============================================================================

Write-Header "NextDNS Blocker Installer"

# Check Python installation
Write-Step "Checking Python installation..."
$python = Test-PythonInstallation

if (-not $python) {
    Write-Error "Python $MinPythonVersion or higher is required."
    Write-Host ""
    Write-Host "  Please install Python from: https://www.python.org/downloads/" -ForegroundColor Yellow
    Write-Host "  Make sure to check 'Add Python to PATH' during installation." -ForegroundColor Yellow
    Write-Host ""
    exit 1
}

Write-Success "Found Python $($python.Version)"

# Check if already installed
$alreadyInstalled = Test-PackageInstalled -PythonCommand $python.Command

if ($alreadyInstalled -and -not $Upgrade) {
    Write-Host ""
    $response = Read-Host "  $PackageName is already installed. Upgrade? [y/N]"
    if ($response -match "^[Yy]") {
        $Upgrade = $true
    }
    else {
        Write-Host ""
        Write-Host "  Run with -Upgrade to upgrade the existing installation." -ForegroundColor Yellow
        Write-Host ""
        exit 0
    }
}

# Install/upgrade package
try {
    Install-Package -PythonCommand $python.Command -Upgrade:$Upgrade
}
catch {
    Write-Error $_.Exception.Message
    exit 1
}

# Run setup wizard (skip if upgrading)
if (-not $Upgrade) {
    try {
        Invoke-Setup -PythonCommand $python.Command -NonInteractive:$NonInteractive
    }
    catch {
        Write-Error $_.Exception.Message
        exit 1
    }
}

# Install Task Scheduler (unless skipped)
if (-not $SkipScheduler -and -not $Upgrade) {
    Install-TaskScheduler -PythonCommand $python.Command | Out-Null
}

# Show post-install info
Show-PostInstallInfo
