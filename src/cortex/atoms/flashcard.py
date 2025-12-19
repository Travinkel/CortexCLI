"""
Flashcard atom handler.

Simple front/back recall cards. User sees front, presses enter to flip,
then self-evaluates whether they recalled correctly.
"""

import time
from typing import Any

from rich import box
from rich.align import Align
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm, Prompt
from rich.text import Text

from src.delivery.cortex_visuals import CORTEX_THEME, cortex_result_panel
from . import AtomType, register
from .base import AnswerResult, is_dont_know


@register(AtomType.FLASHCARD)
class FlashcardHandler:
    """Handler for flashcard atoms."""

    def validate(self, atom: dict) -> bool:
        """Check if atom has required flashcard fields."""
        return bool(atom.get("front") and atom.get("back"))

    def present(self, atom: dict, console: Console) -> None:
        """Display the front of the flashcard."""
        front = atom.get("front", "No question")
        panel = Panel(
            front,
            title="[bold cyan]RECALL CHALLENGE[/bold cyan]",
            border_style="cyan",
            box=box.HEAVY,
            padding=(1, 2),
        )
        console.print(panel)

    def get_input(self, atom: dict, console: Console) -> dict:
        """Wait for flip, show back, get self-evaluation. '?' = I don't know."""
        # Wait for user to flip
        Prompt.ask("\nPress Enter to flip", default="", show_default=False)

        # Flip animation
        self._flip_animation(atom.get("front", ""), console)

        # Show back
        console.print(
            Panel(
                atom.get("back", "No answer"),
                title="[bold green]ANSWER[/bold green]",
                border_style="green",
                box=box.HEAVY,
                padding=(1, 2),
            )
        )

        # Self-evaluation with "I don't know" option
        console.print("[dim]y=yes, n=no, ?=I didn't know this[/dim]")
        while True:
            response = Prompt.ask(
                "Did you recall correctly? [y/n/?]",
                default="y",
            ).strip().lower()

            if is_dont_know(response):
                return {"recalled": False, "dont_know": True}
            elif response in ("y", "yes"):
                return {"recalled": True, "dont_know": False}
            elif response in ("n", "no"):
                return {"recalled": False, "dont_know": False}
            else:
                console.print("[yellow]Please enter y, n, or ?[/yellow]")

    def check(self, atom: dict, answer: Any, console: Console | None = None) -> AnswerResult:
        """Check self-reported answer."""
        # Handle dict input (from updated get_input)
        if isinstance(answer, dict):
            if answer.get("dont_know"):
                return AnswerResult(
                    correct=False,
                    feedback="Let's learn this one!",
                    user_answer="I don't know",
                    correct_answer=atom.get("back", ""),
                    explanation=atom.get("explanation", ""),
                    dont_know=True,
                )
            is_correct = answer.get("recalled", False)
        else:
            is_correct = bool(answer)

        return AnswerResult(
            correct=is_correct,
            feedback="Good recall!" if is_correct else "Keep practicing",
            user_answer="yes" if is_correct else "no",
            correct_answer=atom.get("back", ""),
        )

    def hint(self, atom: dict, attempt: int) -> str | None:
        """No hints for flashcards - it's pure recall."""
        return None

    def _flip_animation(self, front: str, console: Console) -> None:
        """Minimal flip effect."""
        for dots in [".", "..", "..."]:
            console.clear()
            console.print(
                Panel(
                    Align.center(Text(f"Flipping{dots}", style="cyan")),
                    border_style="cyan",
                    box=box.HEAVY,
                )
            )
            time.sleep(0.1)
        console.clear()
