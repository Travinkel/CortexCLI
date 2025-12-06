@echo off
REM Cortex CLI Launcher for Windows
REM Usage: cortex [command] [options]
REM        cortex           - Interactive menu
REM        cortex study     - Start study session
REM        cortex stats     - Show progress

cd /d "%~dp0"
python cortex.py %*
