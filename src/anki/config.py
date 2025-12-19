"""
Anki configuration constants and note type definitions.

Centralizes all Anki-related configuration to avoid duplication
and ensure consistency across push/pull operations.
"""

from __future__ import annotations

# =============================================================================
# Note Types - must match your Anki note type names exactly
# =============================================================================
FLASHCARD_NOTE_TYPE = "LearningOS-v2"
CLOZE_NOTE_TYPE = "LearningOS-v2 Cloze-NEW"

# =============================================================================
# Deck Structure
# =============================================================================
CERT_DECK = "CCNA"
COURSE_DECK = "ITN"
BASE_DECK = f"{CERT_DECK}::{COURSE_DECK}"

# =============================================================================
# Tags
# =============================================================================
# Curriculum identifier for globally unique tags
# Format: <cert>-<course> e.g., ccna-itn, ccna-srwe, ccna-ensa
CURRICULUM_ID = "ccna-itn"

# Source tag to identify cards created by this system
SOURCE_TAG = "cortex"

# =============================================================================
# Atom Type Filtering
# =============================================================================
# Only these atom types go to Anki (FSRS scheduling)
# Other types (mcq, true_false, matching, parsons) stay in NLS for CLI quizzes
ANKI_ATOM_TYPES = ("flashcard", "cloze")

# =============================================================================
# Quality Thresholds per Atom Type
# =============================================================================
# Per-type minimum quality scores for Anki sync
# Flashcards are stricter because passive recall needs high quality
# Cloze is moderately strict as active completion
ANKI_QUALITY_THRESHOLDS: dict[str, float] = {
    "flashcard": 0.85,  # Stricter - passive recall needs quality
    "cloze": 0.80,      # Moderate - active completion
}

# Default threshold for atom types not in the above dict
DEFAULT_QUALITY_THRESHOLD = 0.75

# =============================================================================
# CCNA ITN Module Names
# =============================================================================
# Maps module number to display name for Anki deck organization
# Per user guidance: "hardcoding for CCNA is perfectly acceptable"
CCNA_ITN_MODULE_NAMES = {
    1: "Networking Today",
    2: "Basic Switch and End Device Configuration",
    3: "Protocols and Models",
    4: "Physical Layer",
    5: "Number Systems",
    6: "Data Link Layer",
    7: "Ethernet Switching",
    8: "Network Layer",
    9: "Address Resolution",
    10: "Basic Router Configuration",
    11: "IPv4 Addressing",
    12: "IPv6 Addressing",
    13: "ICMP",
    14: "Transport Layer",
    15: "Application Layer",
    16: "Network Security Fundamentals",
    17: "Build a Small Network",
}


def get_note_type(atom_type: str) -> str:
    """
    Get Anki note type for atom type.

    Args:
        atom_type: The atom type (flashcard, cloze, mcq, etc.)

    Returns:
        Note type name for Anki (LearningOS-v2 or LearningOS-v2 Cloze)
    """
    return CLOZE_NOTE_TYPE if atom_type == "cloze" else FLASHCARD_NOTE_TYPE


def get_module_deck_name(module_num: int) -> str:
    """
    Get full deck path for module number.

    Args:
        module_num: Module number (1-17 for CCNA ITN)

    Returns:
        Full deck path like "CCNA::ITN::M01 Networking Today"
    """
    name = CCNA_ITN_MODULE_NAMES.get(module_num, f"Module {module_num}")
    return f"{BASE_DECK}::M{module_num:02d} {name}"


def is_anki_atom_type(atom_type: str) -> bool:
    """
    Check if atom type should be synced to Anki.

    Args:
        atom_type: The atom type to check

    Returns:
        True if atom should go to Anki, False if it stays in NLS CLI
    """
    return atom_type in ANKI_ATOM_TYPES
