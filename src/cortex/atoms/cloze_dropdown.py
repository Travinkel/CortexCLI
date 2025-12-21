"""
Cloze dropdown atom handler.

Cloze deletion with dropdown selection - presents a fill-in-the-blank
question with multiple choice options instead of free-form input.
"""

import re
from typing import Any

from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt
from rich.table import Table
from rich.text import Text

from src.delivery.cortex_visuals import (
    STYLES,
    get_asi_prompt,
)

from . import AtomType, register
from .base import AnswerResult, is_dont_know


@register(AtomType.CLOZE_DROPDOWN)
class ClozeDropdownHandler:
    """Handler for cloze dropdown atoms (cloze with multiple choice options)."""

    def validate(self, atom: dict) -> bool:
        """Check if atom has required cloze_dropdown fields."""
        # Requires cloze text with blank and options list
        cloze_text = atom.get("cloze_text") or atom.get("front", "")
        options = atom.get("options", [])
        correct = atom.get("correct_answer") or atom.get("back")

        has_blank = "{{" in cloze_text or "___" in cloze_text
        has_options = len(options) >= 2
        has_correct = bool(correct)

        return has_blank and has_options and has_correct

    def present(self, atom: dict, console: Console) -> None:
        """Display the cloze question with blank highlighted."""
        cloze_text = atom.get("cloze_text") or atom.get("front", "No question")

        # Format the blank for display
        display_text = self._format_blanks(cloze_text)

        panel = Panel(
            display_text,
            title="[bold cyan]SELECT THE CORRECT OPTION[/bold cyan]",
            border_style="cyan",
            box=box.HEAVY,
            padding=(1, 2),
        )
        console.print(panel)

    def get_input(self, atom: dict, console: Console) -> dict:
        """Display options and get user's selection."""
        options = atom.get("options", [])

        if not options:
            console.print("[yellow]No options found[/yellow]")
            return {"skipped": True}

        # Display options in a table
        table = Table(box=box.MINIMAL, show_header=False)
        table.add_column("Index", style="cyan", justify="right", width=4)
        table.add_column("Option", style="white")

        for i, option in enumerate(options):
            table.add_row(f"[{i + 1}]", str(option))

        panel = Panel(
            table,
            title="[bold yellow]OPTIONS[/bold yellow]",
            border_style="yellow",
            box=box.HEAVY,
            padding=(1, 2),
        )
        console.print(panel)

        console.print(f"[dim]Enter choice [1-{len(options)}]. 'h'=hint, '?'=I don't know[/dim]")

        hint_count = 0
        while True:
            choice = Prompt.ask(get_asi_prompt("cloze_dropdown", f"[1-{len(options)}]"))

            if is_dont_know(choice):
                return {"dont_know": True, "hints_used": hint_count}

            if choice.lower() == "h":
                hint_count += 1
                hint_text = self.hint(atom, hint_count)
                if hint_text:
                    console.print(f"[yellow]Hint {hint_count}:[/yellow] {hint_text}")
                else:
                    console.print("[dim]No more hints available[/dim]")
                continue

            if choice.isdigit():
                idx = int(choice)
                if 1 <= idx <= len(options):
                    return {
                        "choice": idx,
                        "selected": options[idx - 1],
                        "hints_used": hint_count,
                        "dont_know": False,
                    }

            console.print(f"[yellow]Please enter a number between 1 and {len(options)}[/yellow]")

    def check(self, atom: dict, answer: Any, console: Console | None = None) -> AnswerResult:
        """Check if the selected option is correct."""
        correct_answer = atom.get("correct_answer") or atom.get("back", "")

        if isinstance(answer, dict):
            if answer.get("skipped"):
                return AnswerResult(
                    correct=True,
                    feedback="Skipped",
                    user_answer="skipped",
                    correct_answer=correct_answer,
                )

            if answer.get("dont_know"):
                return AnswerResult(
                    correct=False,
                    feedback="Let's learn this one!",
                    user_answer="I don't know",
                    correct_answer=correct_answer,
                    explanation=atom.get("explanation", ""),
                    dont_know=True,
                )

            selected = str(answer.get("selected", "")).strip().lower()
        else:
            selected = str(answer).strip().lower()

        correct_lower = correct_answer.strip().lower()
        is_correct = selected == correct_lower

        return AnswerResult(
            correct=is_correct,
            feedback="Correct!" if is_correct else f"Expected: {correct_answer}",
            user_answer=str(answer.get("selected", answer) if isinstance(answer, dict) else answer),
            correct_answer=correct_answer,
            explanation=atom.get("explanation") if not is_correct else None,
        )

    def hint(self, atom: dict, attempt: int) -> str | None:
        """Progressive hints - eliminate wrong options."""
        options = atom.get("options", [])
        correct = (atom.get("correct_answer") or atom.get("back", "")).strip().lower()

        # Get incorrect options
        incorrect = [o for o in options if str(o).strip().lower() != correct]

        if attempt == 1 and incorrect:
            # Eliminate one wrong option
            return f"'{incorrect[0]}' is NOT the answer"
        elif attempt == 2 and len(incorrect) > 1:
            # Eliminate another wrong option
            return f"'{incorrect[1]}' is also NOT the answer"
        elif attempt == 3:
            # Give first letter hint
            if correct:
                return f"The answer starts with '{correct[0].upper()}'"

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
