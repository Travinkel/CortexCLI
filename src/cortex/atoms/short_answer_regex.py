"""
Short answer regex match handler.

Regex pattern match for typo tolerance and flexible answer matching.
Supports case-insensitive matching by default.
"""

import re
from typing import Any

from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt

from src.delivery.cortex_visuals import get_asi_prompt

from . import AtomType, register
from .base import AnswerResult, is_dont_know


@register(AtomType.SHORT_ANSWER_REGEX)
class ShortAnswerRegexHandler:
    """Handler for short answer regex match atoms."""

    def validate(self, atom: dict) -> bool:
        """Check if atom has required regex answer fields."""
        question = atom.get("front") or atom.get("question", "")
        pattern = atom.get("pattern") or atom.get("regex", "")
        # Also need a display answer for feedback
        display_answer = atom.get("back") or atom.get("correct_answer", "")

        if not question:
            return False

        # Must have either a pattern or a display answer
        if not pattern and not display_answer:
            return False

        # Validate regex pattern if provided
        if pattern:
            try:
                re.compile(pattern)
            except re.error:
                return False

        return True

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
        """Check if answer matches the regex pattern."""
        pattern = atom.get("pattern") or atom.get("regex", "")
        display_answer = atom.get("back") or atom.get("correct_answer", "")
        case_sensitive = atom.get("case_sensitive", False)

        if isinstance(answer, dict):
            if answer.get("dont_know"):
                return AnswerResult(
                    correct=False,
                    feedback="Let's learn this one!",
                    user_answer="I don't know",
                    correct_answer=display_answer,
                    explanation=atom.get("explanation", ""),
                    dont_know=True,
                )
            user_answer = str(answer.get("answer", "")).strip()
        else:
            user_answer = str(answer).strip()

        # Grade using regex or fallback to exact match
        if pattern:
            is_correct = self._grade(user_answer, pattern, case_sensitive)
        else:
            # Fallback to exact match if no pattern
            if case_sensitive:
                is_correct = user_answer == display_answer
            else:
                is_correct = user_answer.lower() == display_answer.lower()

        return AnswerResult(
            correct=is_correct,
            feedback="Correct!" if is_correct else f"Expected: {display_answer}",
            user_answer=user_answer,
            correct_answer=display_answer,
            explanation=atom.get("explanation") if not is_correct else None,
        )

    def hint(self, atom: dict, attempt: int) -> str | None:
        """Progressive hints for regex answer."""
        answer = atom.get("back") or atom.get("correct_answer", "")
        if not answer:
            return None

        if attempt == 1:
            # First letter
            return f"Starts with: {answer[0]}..."
        elif attempt == 2:
            # Show accepted format example
            pattern = atom.get("pattern") or atom.get("regex", "")
            if pattern:
                return f"Answer should match format like: {answer}"
            return f"The answer has {len(answer)} characters"
        elif attempt == 3:
            # First and last letter
            if len(answer) > 2:
                return f"Starts with '{answer[0]}', ends with '{answer[-1]}'"

        return None

    def _grade(self, user_answer: str, pattern: str, case_sensitive: bool = False) -> bool:
        """Regex pattern match grading."""
        try:
            flags = 0 if case_sensitive else re.IGNORECASE
            return bool(re.fullmatch(pattern, user_answer, flags))
        except re.error:
            # Invalid regex - fall back to exact match
            return user_answer.lower() == pattern.lower()
