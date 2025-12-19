"""
Compatibility shim for relocated section-linking utilities.

Tests and older tooling import `scripts.fix_atom_section_links`.
The implementation now lives under `scripts/setup/fix_atom_section_links.py`.
This module re-exports the public symbols to maintain backwards compatibility.
"""

from scripts.setup.fix_atom_section_links import (
    SECTION_PRIMARY_KEYWORDS,
    find_best_section_for_atom,
    score_section_match,
)

__all__ = [
    "SECTION_PRIMARY_KEYWORDS",
    "find_best_section_for_atom",
    "score_section_match",
]
