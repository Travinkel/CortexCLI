@echo off
REM ============================================
REM STUDY - One command to study your ITN cards
REM ============================================
REM Usage: study           - Open Anki (cards organized by module)
REM        study sync      - Sync to Anki first, then open
REM
REM Just double-click this file or run from PowerShell.

cd /d "%~dp0"

if "%~1"=="sync" (
    echo Syncing to Anki...
    python -m src.cli.main sync anki-push
    echo.
    echo Sync complete. Opening Anki...
    start "" "C:\Program Files\Anki\anki.exe"
    exit /b
)

echo.
echo ========================================
echo  Introduction to Networks - Study Time
echo ========================================
echo.
echo Your cards are organized in Anki by module:
echo.
echo   ITN::01 Networking Today
echo   ITN::02 Basic Switch and End Device Configuration
echo   ITN::03 Protocols and Models
echo   ITN::04 Physical Layer
echo   ITN::05 Number Systems
echo   ITN::06 Data Link Layer
echo   ITN::07 Ethernet Switching
echo   ITN::08 Network Layer
echo   ITN::09 Address Resolution
echo   ...and more
echo.
echo Just click a module deck in Anki to study it!
echo.
echo Opening Anki...
start "" "C:\Program Files\Anki\anki.exe"
