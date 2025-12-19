"""
Cloze deletion atom handler.

Fill-in-the-blank style questions. The front contains {{blanks}}
that the user must fill in.
"""

import re
from typing import Any

from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt
from rich.text import Text

from src.delivery.cortex_visuals import (
    CORTEX_THEME,
    STYLES,
    cortex_result_panel,
    get_asi_prompt,
)
from . import AtomType, register
from .base import AnswerResult, is_dont_know


@register(AtomType.CLOZE)
class ClozeHandler:
    """Handler for cloze deletion atoms."""

    def validate(self, atom: dict) -> bool:
        """Check if atom has required cloze fields (front with blanks)."""
        front = atom.get("front", "")
        return bool(front and ("{{" in front or "cloze" in front.lower()))

    def present(self, atom: dict, console: Console) -> None:
        """Display the cloze question with blanks highlighted."""
        front = atom.get("front", "No question")

        # Highlight blanks
        display_text = self._format_blanks(front)

        panel = Panel(
            display_text,
            title="[bold cyan]FILL THE BLANK[/bold cyan]",
            border_style="cyan",
            box=box.HEAVY,
            padding=(1, 2),
        )
        console.print(panel)

    def get_input(self, atom: dict, console: Console) -> dict:
        """Get user's answer for the blank. Press 'h' for hints, '?' for I don't know."""
        console.print("[dim]'h'=hint, '?'=I don't know, or enter your answer[/dim]")

        hint_count = 0
        while True:
            user_input = Prompt.ask(get_asi_prompt("default", "[answer]"))

            # Check for "I don't know"
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
        """Check if answer matches the cloze deletion."""
        # Handle "I don't know"
        if isinstance(answer, dict) and answer.get("dont_know"):
            correct_answer = self._extract_answer(atom)
            return AnswerResult(
                correct=False,
                feedback="Let's learn this one!",
                user_answer="I don't know",
                correct_answer=correct_answer,
                explanation=atom.get("explanation", ""),
                dont_know=True,
            )

        # Handle both dict (with hints) and str (direct) input
        if isinstance(answer, dict):
            user_answer = str(answer.get("answer", "")).strip().lower()
        else:
            user_answer = str(answer).strip().lower()

        # Extract expected answer from back or cloze markers
        correct_answer = self._extract_answer(atom)
        correct_lower = correct_answer.strip().lower()

        # Flexible matching - exact or close enough
        is_correct = (
            user_answer == correct_lower
            or user_answer in correct_lower
            or correct_lower in user_answer
        )

        return AnswerResult(
            correct=is_correct,
            feedback="Correct!" if is_correct else f"Expected: {correct_answer}",
            user_answer=str(answer),
            correct_answer=correct_answer,
        )

    def hint(self, atom: dict, attempt: int) -> str | None:
        """Progressive hints for cloze."""
        answer = self._extract_answer(atom)
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

    def _format_blanks(self, text: str) -> Text:
        """Format text with highlighted blanks."""
        result = Text()

        # Pattern for {{cloze}} or {{c1::answer}} format
        pattern = r"\{\{(?:c\d+::)?([^}]+)\}\}"

        last_end = 0
        for match in re.finditer(pattern, text):
            # Add text before the blank
            result.append(text[last_end : match.start()])
            # Add highlighted blank
            result.append(" [____] ", style=STYLES["cortex_warning"])
            last_end = match.end()

        # Add remaining text
        result.append(text[last_end:])

        # If no cloze markers found, look for underscores
        if "{{" not in text and "___" in text:
            return Text(text.replace("___", " [____] "), style=STYLES["cortex_accent"])

        return result

    def _extract_answer(self, atom: dict) -> str:
        """Extract the expected answer from the atom."""
        # Check for pre-parsed answer
        if atom.get("cloze_answer"):
            return atom["cloze_answer"]

        # Try to extract from front (Anki-style cloze)
        front = atom.get("front", "")
        pattern = r"\{\{(?:c\d+::)?([^}]+)\}\}"
        match = re.search(pattern, front)
        if match:
            return match.group(1)

        # Fall back to back field
        return atom.get("back", "")
