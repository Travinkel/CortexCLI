"""
Confidence slider atom handler.

Captures pre-answer confidence (0-100%) for calibration tracking.
Measures the gap between confidence and correctness to identify
overconfidence or underconfidence patterns.
"""

from typing import Any

from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt

from . import AtomType, register
from .base import AnswerResult, is_dont_know


@register(AtomType.CONFIDENCE_SLIDER)
class ConfidenceSliderHandler:
    """Handler for confidence slider atoms - metacognitive calibration."""

    def validate(self, atom: dict) -> bool:
        """Check if atom has required fields."""
        return bool(atom.get("front") and atom.get("back"))

    def present(self, atom: dict, console: Console) -> None:
        """Display the question."""
        front = atom.get("front", "No question")
        panel = Panel(
            front,
            title="[bold cyan]CALIBRATION CHECK[/bold cyan]",
            border_style="cyan",
            box=box.HEAVY,
            padding=(1, 2),
        )
        console.print(panel)

    def get_input(self, atom: dict, console: Console) -> dict:
        """Get pre-confidence rating, then user answer."""
        # Step 1: Get confidence BEFORE showing answer
        console.print("[dim]Rate your confidence before answering (0-100%)[/dim]")
        console.print("[dim]0 = guessing, 50 = unsure, 100 = certain[/dim]")

        while True:
            try:
                confidence_input = Prompt.ask("Confidence", default="50")
                if is_dont_know(confidence_input):
                    return {"dont_know": True, "confidence": 0}
                confidence = int(confidence_input)
                if 0 <= confidence <= 100:
                    break
                console.print("[yellow]Please enter a number 0-100[/yellow]")
            except ValueError:
                console.print("[yellow]Please enter a valid number[/yellow]")

        # Step 2: Get the actual answer
        console.print()
        answer = Prompt.ask("Your answer")

        if is_dont_know(answer):
            return {"dont_know": True, "confidence": confidence}

        return {"answer": answer, "confidence": confidence}

    def check(self, atom: dict, answer: Any, console: Console | None = None) -> AnswerResult:
        """Check answer and calculate calibration error."""
        correct_answer = atom.get("back", "")

        if answer.get("dont_know"):
            confidence = answer.get("confidence", 0)
            calibration_error = confidence  # High confidence + don't know = bad calibration
            return AnswerResult(
                correct=False,
                feedback=f"Calibration: {calibration_error}% error (confidence was {confidence}%)",
                user_answer="I don't know",
                correct_answer=correct_answer,
                partial_score=0.0,
                dont_know=True,
            )

        user_answer = answer.get("answer", "").strip().lower()
        confidence = answer.get("confidence", 50)

        # Simple correctness check (case-insensitive, stripped)
        is_correct = user_answer == correct_answer.strip().lower()

        # Calculate calibration error: |confidence - correctness * 100|
        correctness_pct = 100 if is_correct else 0
        calibration_error = abs(confidence - correctness_pct)

        # Good calibration feedback
        if calibration_error <= 20:
            calibration_msg = "Well calibrated!"
        elif calibration_error <= 40:
            calibration_msg = "Reasonably calibrated"
        elif confidence > correctness_pct:
            calibration_msg = "Overconfident"
        else:
            calibration_msg = "Underconfident"

        feedback = f"{'Correct!' if is_correct else 'Incorrect.'} {calibration_msg} (error: {calibration_error}%)"

        return AnswerResult(
            correct=is_correct,
            feedback=feedback,
            user_answer=user_answer,
            correct_answer=correct_answer,
            partial_score=1.0 if is_correct else 0.0,
            explanation=f"Calibration error: {calibration_error}% | Confidence: {confidence}%",
        )

    def hint(self, atom: dict, attempt: int) -> str | None:
        """Provide hints for the question."""
        back = atom.get("back", "")
        if attempt == 1 and len(back) > 0:
            return f"The answer starts with '{back[0]}'"
        elif attempt == 2 and len(back) > 2:
            return f"The answer has {len(back)} characters"
        return None
