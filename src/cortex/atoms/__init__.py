"""
Atom type handlers for Cortex study sessions.

Each atom type (flashcard, MCQ, parsons, etc.) has its own module with:
- present(): Display the atom to the user
- get_input(): Get user's answer
- check(): Validate the answer
- hint(): Provide progressive hints
"""

from enum import Enum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .base import AtomHandler

class AtomType(str, Enum):
    """Supported atom types in Cortex."""
    FLASHCARD = "flashcard"
    CLOZE = "cloze"
    MCQ = "mcq"
    TRUE_FALSE = "true_false"
    NUMERIC = "numeric"
    MATCHING = "matching"
    PARSONS = "parsons"
    # Batch 3a: Declarative memory handlers
    CLOZE_DROPDOWN = "cloze_dropdown"
    SHORT_ANSWER_EXACT = "short_answer_exact"
    SHORT_ANSWER_REGEX = "short_answer_regex"
    LIST_RECALL = "list_recall"
    ORDERED_LIST_RECALL = "ordered_list_recall"


# Handler registry - populated by @register decorator
HANDLERS: dict[AtomType, "AtomHandler"] = {}


def register(atom_type: AtomType):
    """Decorator to register an atom handler."""
    def decorator(cls):
        HANDLERS[atom_type] = cls()
        return cls
    return decorator


def get_handler(atom_type: str | AtomType) -> "AtomHandler | None":
    """Get the handler for an atom type."""
    if isinstance(atom_type, str):
        try:
            atom_type = AtomType(atom_type.lower())
        except ValueError:
            return None
    return HANDLERS.get(atom_type)


# Import handlers to trigger registration
from . import flashcard
from . import mcq
from . import true_false
from . import numeric
from . import cloze
from . import matching
from . import parsons
# Batch 3a: Declarative memory handlers
from . import cloze_dropdown
from . import short_answer_exact
from . import short_answer_regex
from . import list_recall
from . import ordered_list_recall

__all__ = [
    "AtomType",
    "HANDLERS",
    "get_handler",
    "register",
]
