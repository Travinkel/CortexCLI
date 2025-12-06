# Cortex CLI Launcher for PowerShell
# Usage: .\cortex [command] [options]
#        .\cortex           - Interactive menu
#        .\cortex study     - Start study session
#        .\cortex stats     - Show progress

$scriptPath = Split-Path -Parent $MyInvocation.MyCommand.Path
Push-Location $scriptPath
try {
    python cortex.py @args
} finally {
    Pop-Location
}
