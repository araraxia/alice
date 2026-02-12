# PowerShell script to restart Flask server with Administrator privileges
# This script checks if running as admin and re-launches if needed

param(
    [switch]$AsAdmin
)

# Function to check if running as administrator
function Test-Administrator {
    $currentUser = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = New-Object Security.Principal.WindowsPrincipal($currentUser)
    return $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

# If not running as admin and -AsAdmin not specified, relaunch as admin
if (-not (Test-Administrator) -and -not $AsAdmin) {
    Write-Host "Not running as Administrator. Attempting to elevate..." -ForegroundColor Yellow
    
    # Relaunch this script as administrator
    $scriptPath = $MyInvocation.MyCommand.Path
    Start-Process powershell.exe -Verb RunAs -ArgumentList "-ExecutionPolicy Bypass -File `"$scriptPath`" -AsAdmin"
    exit
}

Write-Host "Running with Administrator privileges" -ForegroundColor Green

# Change to API directory
Set-Location "C:\MenoAPI\API"

# Call the Python webhook starter with restart flag
$pythonExe = "C:\MenoAPI\API\.venv\Scripts\python.exe"
$starterScript = "C:\MenoAPI\API\src\webhook_starter.py"

Write-Host "Restarting Flask server..." -ForegroundColor Cyan
& $pythonExe $starterScript --restart True

Write-Host "Restart command completed." -ForegroundColor Green
