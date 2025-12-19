#!/usr/bin/env python3
"""
Cortex CLI - Quick launcher for the interactive menu.

This is a convenience wrapper that launches the Cortex interactive menu.
For the full CLI with all commands, use: python -m src.cli.main cortex --help

Usage:
    python cortex.py           # Launch interactive menu
    python cortex.py --help    # Show this help

For direct command access:
    python -m src.cli.main cortex start      # Start study session
    python -m src.cli.main cortex stats      # Show progress stats
    python -m src.cli.main cortex --help     # All commands
"""

import subprocess
import sys


def main():
    """Launch the Cortex interactive menu."""
    if len(sys.argv) > 1 and sys.argv[1] in ("--help", "-h"):
        print(__doc__)
        return

    # Launch the menu command from the main CLI
    subprocess.run([sys.executable, "-m", "src.cli.main", "cortex", "menu"])


if __name__ == "__main__":
    main()
