"""
Short answer exact match handler.

Exact string match grading for short answer questions.
Supports case-insensitive matching by default.
"""

from typing import Any

from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt

from src.delivery.cortex_visuals import get_asi_prompt

from . import AtomType, register
from .base import AnswerResult, is_dont_know


@register(AtomType.SHORT_ANSWER_EXACT)
class ShortAnswerExactHandler:
    """Handler for short answer exact match atoms."""

    def validate(self, atom: dict) -> bool:
        """Check if atom has required short answer fields."""
        question = atom.get("front") or atom.get("question", "")
        answer = atom.get("back") or atom.get("correct_answer", "")
        return bool(question and answer)

    def present(self, atom: dict, console: Console) -> None:
        """Display the short answer question."""
        question = atom.get("front") or atom.get("question", "No question")

        panel = Panel(
            question,
            title="[bold cyan]SHORT ANSWER[/bold cyan]",
            border_style="cyan",
            box=box.HEAVY,
            padding=(1, 2),
        )
        console.print(panel)

    def get_input(self, atom: dict, console: Console) -> dict:
        """Get user's answer. 'h'=hint, '?'=I don't know."""
        console.print("[dim]Type your answer. 'h'=hint, '?'=I don't know[/dim]")

        hint_count = 0
        while True:
            user_input = Prompt.ask(get_asi_prompt("short_answer", "[answer]"))

            if is_dont_know(user_input):
                return {"dont_know": True, "hints_used": hint_count}

            if user_input.lower() == "h":
                hint_count += 1
                hint_text = self.hint(atom, hint_count)
                if hint_text:
                    console.print(f"[yellow]Hint {hint_count}:[/yellow] {hint_text}")
                else:
                    console.print("[dim]No more hints available[/dim]")
                continue

            return {"answer": user_input, "hints_used": hint_count, "dont_know": False}

    def check(self, atom: dict, answer: Any, console: Console | None = None) -> AnswerResult:
        """Check if answer matches exactly (case-insensitive by default)."""
        correct_answer = atom.get("back") or atom.get("correct_answer", "")
        case_sensitive = atom.get("case_sensitive", False)

        if isinstance(answer, dict):
            if answer.get("dont_know"):
                return AnswerResult(
                    correct=False,
                    feedback="Let's learn this one!",
                    user_answer="I don't know",
                    correct_answer=correct_answer,
                    explanation=atom.get("explanation", ""),
                    dont_know=True,
                )
            user_answer = str(answer.get("answer", "")).strip()
        else:
            user_answer = str(answer).strip()

        # Exact match logic
        is_correct = self._grade(user_answer, correct_answer, case_sensitive)

        return AnswerResult(
            correct=is_correct,
            feedback="Correct!" if is_correct else f"Expected: {correct_answer}",
            user_answer=user_answer,
            correct_answer=correct_answer,
            explanation=atom.get("explanation") if not is_correct else None,
        )

    def hint(self, atom: dict, attempt: int) -> str | None:
        """Progressive hints for short answer."""
        answer = atom.get("back") or atom.get("correct_answer", "")
        if not answer:
            return None

        if attempt == 1:
            # First letter
            return f"Starts with: {answer[0]}..."
        elif attempt == 2:
            # Length hint
            return f"The answer has {len(answer)} characters"
        elif attempt == 3:
            # First and last letter
            if len(answer) > 2:
                return f"Starts with '{answer[0]}', ends with '{answer[-1]}'"

        return None

    def _grade(self, user_answer: str, correct: str, case_sensitive: bool) -> bool:
        """Exact string match grading."""
        if not case_sensitive:
            return user_answer.lower().strip() == correct.lower().strip()
        return user_answer.strip() == correct.strip()
