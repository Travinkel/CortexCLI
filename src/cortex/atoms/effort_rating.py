"""
Effort rating atom handler.

Captures post-answer cognitive load rating (1-5 scale).
Tracks how hard the user found a question for adaptive difficulty.
"""

from typing import Any

from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt

from . import AtomType, register
from .base import AnswerResult, is_dont_know


EFFORT_LABELS = {
    1: "Very Easy - No effort required",
    2: "Easy - Minimal thinking",
    3: "Medium - Some effort required",
    4: "Hard - Significant effort",
    5: "Very Hard - Maximum mental effort",
}


@register(AtomType.EFFORT_RATING)
class EffortRatingHandler:
    """Handler for effort rating atoms - cognitive load tracking."""

    def validate(self, atom: dict) -> bool:
        """Check if atom has required fields."""
        return bool(atom.get("front") and atom.get("back"))

    def present(self, atom: dict, console: Console) -> None:
        """Display the question."""
        front = atom.get("front", "No question")
        panel = Panel(
            front,
            title="[bold cyan]COGNITIVE LOAD ASSESSMENT[/bold cyan]",
            border_style="cyan",
            box=box.HEAVY,
            padding=(1, 2),
        )
        console.print(panel)

    def get_input(self, atom: dict, console: Console) -> dict:
        """Get user answer, then effort rating."""
        # Step 1: Get the answer
        answer = Prompt.ask("Your answer")

        if is_dont_know(answer):
            return {"dont_know": True, "effort": 5}  # Max effort if gave up

        # Step 2: Get effort rating AFTER answering
        console.print()
        console.print("[bold yellow]EFFORT RATING[/bold yellow]")
        for level, label in EFFORT_LABELS.items():
            console.print(f"  [{level}] {label}")

        while True:
            try:
                effort_input = Prompt.ask("How hard was this? (1-5)", default="3")
                effort = int(effort_input)
                if 1 <= effort <= 5:
                    break
                console.print("[yellow]Please enter 1-5[/yellow]")
            except ValueError:
                console.print("[yellow]Please enter a valid number[/yellow]")

        return {"answer": answer, "effort": effort}

    def check(self, atom: dict, answer: Any, console: Console | None = None) -> AnswerResult:
        """Check answer and record effort level."""
        correct_answer = atom.get("back", "")
        effort = answer.get("effort", 3)
        effort_label = EFFORT_LABELS.get(effort, "Unknown")

        if answer.get("dont_know"):
            return AnswerResult(
                correct=False,
                feedback=f"Effort: {effort}/5 - {effort_label}",
                user_answer="I don't know",
                correct_answer=correct_answer,
                partial_score=0.0,
                explanation=f"Cognitive load: {effort}/5",
                dont_know=True,
            )

        user_answer = answer.get("answer", "").strip().lower()

        # Simple correctness check
        is_correct = user_answer == correct_answer.strip().lower()

        feedback = f"{'Correct!' if is_correct else 'Incorrect.'} Effort: {effort}/5"

        return AnswerResult(
            correct=is_correct,
            feedback=feedback,
            user_answer=user_answer,
            correct_answer=correct_answer,
            partial_score=1.0 if is_correct else 0.0,
            explanation=f"Cognitive load: {effort}/5 - {effort_label}",
        )

    def hint(self, atom: dict, attempt: int) -> str | None:
        """Provide hints for the question."""
        back = atom.get("back", "")
        if attempt == 1 and len(back) > 0:
            return f"The answer starts with '{back[0]}'"
        return None
