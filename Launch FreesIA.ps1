# FreesIA GUI Launcher
# Starts the FreesIA GUI without showing a console window

# Get the directory where this script is located
$scriptDir = Split-Path -Parent -Path $MyInvocation.MyCommand.Definition

# Change to that directory
Set-Location $scriptDir

# Run the GUI with a hidden console window
$psi = New-Object System.Diagnostics.ProcessStartInfo
$psi.FileName = "python.exe"
$psi.Arguments = "FreesIA_GUI.py"
$psi.UseShellExecute = $false
$psi.CreateNoWindow = $true
$psi.RedirectStandardOutput = $true
$psi.RedirectStandardError = $true

# Start the process
$process = [System.Diagnostics.Process]::Start($psi)

# Optional: Wait a bit to ensure it started
Start-Sleep -Milliseconds 500

exit
