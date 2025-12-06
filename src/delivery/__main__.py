"""
Entry point for running The Cortex as a module.

Usage:
    python -m src.delivery study
    python -m src.delivery stats
    python -m src.delivery --help
"""
from .cortex_cli import main

if __name__ == "__main__":
    main()
