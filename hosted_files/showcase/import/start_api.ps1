# PowerShell script to start Flask API server with Administrator privileges
# This script checks if running as admin and re-launches if needed

param(
    [switch]$AsAdmin,
    [switch]$NoElevate  # Skip elevation check (useful when already running as admin)
)

# Function to check if running as administrator
function Test-Administrator {
    $currentUser = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = New-Object Security.Principal.WindowsPrincipal($currentUser)
    return $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

# If not running as admin and -NoElevate not specified, relaunch as admin
if (-not (Test-Administrator) -and -not $AsAdmin -and -not $NoElevate) {
    Write-Host "Not running as Administrator. Attempting to elevate..." -ForegroundColor Yellow
    
    # Relaunch this script as administrator
    $scriptPath = $MyInvocation.MyCommand.Path
    Start-Process powershell.exe -Verb RunAs -ArgumentList "-ExecutionPolicy Bypass -File `"$scriptPath`" -AsAdmin"
    exit
}

if (Test-Administrator) {
    Write-Host "Starting Flask server with Administrator privileges" -ForegroundColor Green
}
else {
    Write-Host "Warning: Starting Flask server WITHOUT Administrator privileges" -ForegroundColor Yellow
    Write-Host "Printer control operations may fail with 'Access Denied' errors" -ForegroundColor Yellow
}

# Change to API directory
Set-Location "C:\MenoAPI\API"

# Start Flask server in background
$pythonExe = "C:\MenoAPI\API\.venv\Scripts\python.exe"
$flaskApp = "C:\MenoAPI\API\src\Meno_Helper_Webhook.py"
$logFile = "C:\MenoAPI\API\logs\output.log"

Write-Host "Starting Flask application..." -ForegroundColor Cyan
Write-Host "Python: $pythonExe" -ForegroundColor Gray
Write-Host "App: $flaskApp" -ForegroundColor Gray
Write-Host "Log: $logFile" -ForegroundColor Gray

# Start process in background with output redirected to log
$processInfo = New-Object System.Diagnostics.ProcessStartInfo
$processInfo.FileName = $pythonExe
$processInfo.Arguments = $flaskApp
$processInfo.RedirectStandardOutput = $false
$processInfo.RedirectStandardError = $false
$processInfo.UseShellExecute = $false
$processInfo.CreateNoWindow = $true
$processInfo.WorkingDirectory = "C:\MenoAPI\API"

$process = New-Object System.Diagnostics.Process
$process.StartInfo = $processInfo

# Start the process
if ($process.Start()) {
    Write-Host "Flask server started successfully!" -ForegroundColor Green
    Write-Host "Process ID: $($process.Id)" -ForegroundColor Cyan
    Write-Host "Server is running in background. Check logs at: $logFile" -ForegroundColor Cyan
}
else {
    Write-Host "Failed to start Flask server!" -ForegroundColor Red
    exit 1
}
