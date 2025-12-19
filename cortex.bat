@echo off
REM Cortex CLI Launcher for Windows
REM Usage: cortex              - Interactive menu
REM        cortex [command]    - Run specific command
REM
REM Examples:
REM        cortex              - Launch interactive menu
REM        cortex start        - Start study session (auto-syncs Anki)
REM        cortex sync         - Manual Anki sync (pull stats)
REM        cortex sync --push  - Bidirectional sync
REM        cortex stats        - Show progress
REM        cortex --help       - Show all commands

cd /d "%~dp0"

if "%~1"=="" (
    python -m src.cli.main cortex menu
) else (
    python -m src.cli.main cortex %*
)
