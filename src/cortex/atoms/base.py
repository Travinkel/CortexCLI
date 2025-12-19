"""
Base protocol and types for atom handlers.
"""

from dataclasses import dataclass
from typing import Any, Protocol

from rich.console import Console


@dataclass
class AnswerResult:
    """Result of checking an answer."""
    correct: bool
    feedback: str
    user_answer: str
    correct_answer: str
    partial_score: float = 1.0  # 0.0-1.0 for partial credit
    explanation: str | None = None
    dont_know: bool = False  # True if user selected "I don't know"


# Constants for special inputs
DONT_KNOW_INPUTS = {"?", "idk", "dk", "don't know", "dont know"}


def is_dont_know(user_input: str) -> bool:
    """Check if input indicates 'I don't know'."""
    return user_input.strip().lower() in DONT_KNOW_INPUTS


class AtomHandler(Protocol):
    """Protocol for atom type handlers."""

    def validate(self, atom: dict) -> bool:
        """Check if atom has required fields for this type. Returns True if valid."""
        ...

    def present(self, atom: dict, console: Console) -> None:
        """Display the atom to the user."""
        ...

    def get_input(self, atom: dict, console: Console) -> Any:
        """Get user's answer. Returns the raw input."""
        ...

    def check(self, atom: dict, answer: Any, console: Console | None = None) -> AnswerResult:
        """Validate the answer and return result."""
        ...

    def hint(self, atom: dict, attempt: int) -> str | None:
        """Get progressive hint for attempt N. Returns None if no hint available."""
        ...
