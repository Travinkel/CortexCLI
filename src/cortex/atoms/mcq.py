"""
MCQ (Multiple Choice Question) atom handler.

- Presents a question with several options.
- User selects one or more options.
- Supports single-best-answer and multiple-correct-answers (multi-select).
"""

import json
import random
from typing import Any

from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt
from rich.table import Table
from rich.text import Text

from src.delivery.cortex_visuals import (
    CORTEX_THEME,
    STYLES,
    get_asi_prompt,
)

from . import AtomType, register
from .base import AnswerResult, is_dont_know


def _parse_mcq_options(back: str) -> tuple[list[dict], bool, int, str | None]:
    """
    Parse MCQ options from the 'back' field.

    Returns: (options, is_multi_select, required_count, explanation)

    Supports two formats:
    1. JSON: {"options": [...], "correct": 0 or [0,1], "multi_select": true/false}
    2. Legacy text: Lines starting with * are correct
    """
    explanation = None

    # Try JSON format first
    try:
        data = json.loads(back)
        if isinstance(data, dict) and "options" in data:
            options = []
            correct = data.get("correct")
            is_multi = data.get("multi_select", False)
            required_count = data.get("required_count", 1)
            explanation = data.get("explanation")

            # Handle correct as single index or list of indices
            if isinstance(correct, list):
                correct_indices = set(correct)
            elif isinstance(correct, int):
                correct_indices = {correct}
            else:
                # Correct is null/missing - don't try to infer, just mark as unknown
                # The check() method will use the explanation as the answer instead
                correct_indices = set()
                # Note: We intentionally leave correct_indices empty here
                # The check() method handles this by showing the explanation

            for i, opt_text in enumerate(data["options"]):
                options.append({
                    "text": opt_text,
                    "correct": i in correct_indices
                })

            return options, is_multi, required_count, explanation
    except (json.JSONDecodeError, TypeError):
        pass

    # Fall back to legacy text format
    options = []
    lines = back.strip().split("\n")
    for line in lines:
        line = line.strip()
        if not line:
            continue

        is_correct = line.startswith("*")
        text = line.lstrip("* ").strip()
        options.append({"text": text, "correct": is_correct})

    # Determine if multi-select based on correct count
    correct_count = sum(1 for o in options if o["correct"])
    is_multi = correct_count > 1

    return options, is_multi, correct_count if is_multi else 1, None


@register(AtomType.MCQ)
class MCQHandler:
    """Handler for Multiple Choice Question atoms."""

    def validate(self, atom: dict) -> bool:
        """Validate that the atom has valid MCQ content."""
        if atom.get("options"):
            return len(atom["options"]) >= 2 and any(o.get("correct") for o in atom["options"])
        back = atom.get("back", "")
        if not back:
            return False
        # Try JSON parsing
        try:
            data = json.loads(back)
            if isinstance(data, dict) and "options" in data:
                if len(data["options"]) < 2:
                    return False
                # Require either a correct index OR an explanation
                correct = data.get("correct")
                explanation = data.get("explanation")
                if correct is None and not explanation:
                    # Can't validate or explain - skip this MCQ
                    return False
                return True
        except (json.JSONDecodeError, TypeError):
            pass
        # Legacy format
        return "*" in back

    def present(self, atom: dict, console: Console) -> None:
        """Display the MCQ question."""
        front = atom.get("front", "Select the correct option:")

        # Parse to detect multi-select
        _, is_multi, required_count, _ = _parse_mcq_options(atom.get("back", ""))

        if is_multi:
            title = f"[bold cyan]MULTIPLE CHOICE (Select {required_count})[/bold cyan]"
        else:
            title = "[bold cyan]MULTIPLE CHOICE[/bold cyan]"

        panel = Panel(
            front,
            title=title,
            border_style="cyan",
            box=box.HEAVY,
            padding=(1, 2),
        )
        console.print(panel)

    def get_input(self, atom: dict, console: Console) -> dict:
        """Display options and get user's choice(s)."""
        # Parse options with multi-select info
        if atom.get("options"):
            options = atom["options"]
            is_multi = atom.get("_is_multi", False)
            required_count = atom.get("_required_count", 1)
            explanation = atom.get("_explanation")
        else:
            options, is_multi, required_count, explanation = _parse_mcq_options(atom.get("back", ""))
            atom["_explanation"] = explanation  # Store for later use

        if not options:
            console.print("[yellow]No options found[/yellow]")
            return {"skipped": True}

        # Store multi-select state
        atom["_is_multi"] = is_multi
        atom["_required_count"] = required_count

        # Shuffle options for presentation (only on first attempt, not retry)
        if "_shuffled_options" not in atom:
            random.shuffle(options)
            atom["_shuffled_options"] = options
        else:
            # Use existing shuffled order on retry
            options = atom["_shuffled_options"]

        # Display options in a table
        table = Table(box=box.MINIMAL, show_header=False)
        table.add_column("Index", style="cyan", justify="right", width=4)
        table.add_column("Option", style="white")

        for i, option in enumerate(options):
            table.add_row(f"[{i + 1}]", option["text"])

        panel = Panel(
            table,
            title="[bold yellow]SELECT TARGET[/bold yellow]",
            border_style="yellow",
            box=box.HEAVY,
            padding=(1, 2),
        )
        console.print(panel)

        # Different prompts for single vs multi-select
        if is_multi:
            console.print(f"[dim]Enter {required_count} choices (e.g., 1 3). 'h'=hint, '?'=I don't know[/dim]")
            prompt_text = get_asi_prompt("mcq_multi", f"Select {required_count}")
        else:
            console.print("[dim]Enter choice (e.g., 1). 'h'=hint, '?'=I don't know[/dim]")
            prompt_text = get_asi_prompt("mcq", f"[1-{len(options)}]")

        # Get user input (free-form to support multiple choices)
        choice = Prompt.ask(prompt_text)

        if is_dont_know(choice):
            return {"dont_know": True}

        if choice.lower() == "h":
            # Basic hint: rule out one incorrect option
            incorrect_options = [o["text"] for o in options if not o["correct"]]
            if incorrect_options:
                hint = f"Hint: '{random.choice(incorrect_options)}' is NOT the answer"
                console.print(f"[yellow]{hint}[/yellow]")
                # Re-ask for input after hint
                choice = Prompt.ask(prompt_text)

        if is_dont_know(choice):
            return {"dont_know": True}

        # Parse choice(s)
        if is_multi:
            # Parse space/comma separated choices
            parts = choice.replace(",", " ").split()
            choices = []
            for p in parts:
                if p.isdigit():
                    choices.append(int(p))
            return {"choices": choices, "is_multi": True}
        else:
            return {"choice": choice, "is_multi": False}

    def check(self, atom: dict, answer: Any, console: Console | None = None) -> AnswerResult:
        """Check if the user's choice(s) are correct."""
        shuffled_options = atom.get("_shuffled_options", [])
        correct_answers = [o["text"] for o in shuffled_options if o["correct"]]

        # Check if we have a properly marked correct answer
        has_correct = len(correct_answers) > 0
        explanation = atom.get("_explanation")

        # Fallback: if no correct answer found, use explanation
        if not correct_answers:
            if explanation:
                correct_answers = [explanation]
            else:
                # This shouldn't happen if validation is working correctly
                correct_answers = ["See course materials for the correct answer"]

        if answer.get("skipped"):
            return AnswerResult(
                correct=True,
                feedback="Skipped",
                user_answer="skipped",
                correct_answer=", ".join(correct_answers),
            )

        if answer.get("dont_know"):
            return AnswerResult(
                correct=False,
                feedback="Let's learn this one!",
                user_answer="I don't know",
                correct_answer=", ".join(correct_answers),
                dont_know=True,
            )

        is_multi = answer.get("is_multi", False)

        if is_multi:
            # Multi-select: check all choices
            choices = answer.get("choices", [])
            required_count = atom.get("_required_count", 2)

            if len(choices) != required_count:
                return AnswerResult(
                    correct=False,
                    feedback=f"Please select exactly {required_count} options.",
                    user_answer=f"Selected {len(choices)} options",
                    correct_answer=", ".join(correct_answers),
                )

            # Get selected options
            selected_texts = []
            all_correct = True
            for idx in choices:
                if 1 <= idx <= len(shuffled_options):
                    opt = shuffled_options[idx - 1]
                    selected_texts.append(opt["text"])
                    if not opt["correct"]:
                        all_correct = False
                else:
                    all_correct = False

            # Also check that we got ALL correct answers
            correct_indices = {i + 1 for i, o in enumerate(shuffled_options) if o["correct"]}
            if set(choices) != correct_indices:
                all_correct = False

            return AnswerResult(
                correct=all_correct,
                feedback="Correct!" if all_correct else "Incorrect.",
                user_answer=", ".join(selected_texts),
                correct_answer=", ".join(correct_answers),
            )
        else:
            # Single select
            choice_str = answer.get("choice", "")
            if not choice_str.isdigit():
                # Empty or invalid input - treat as "don't know"
                return AnswerResult(
                    correct=False,
                    feedback="No answer provided.",
                    user_answer="",
                    correct_answer=", ".join(correct_answers),
                    dont_know=True,
                )

            choice_idx = int(choice_str) - 1

            if not (0 <= choice_idx < len(shuffled_options)):
                return AnswerResult(
                    correct=False,
                    feedback="Invalid choice.",
                    user_answer=choice_str,
                    correct_answer=", ".join(correct_answers),
                )

            selected_option = shuffled_options[choice_idx]
            is_correct = selected_option["correct"]

            # If we don't have a marked correct answer, we can't verify
            if not has_correct:
                return AnswerResult(
                    correct=False,  # Can't verify, treat as learning opportunity
                    feedback="Let's check the explanation:",
                    user_answer=selected_option["text"],
                    correct_answer=", ".join(correct_answers),
                    explanation=explanation if explanation else None,
                )

            return AnswerResult(
                correct=is_correct,
                feedback="Correct!" if is_correct else "Incorrect.",
                user_answer=selected_option["text"],
                correct_answer=", ".join(correct_answers),
            )

    def hint(self, atom: dict, attempt: int) -> str | None:
        """Provide a hint for MCQ questions."""
        options = atom.get("_shuffled_options") or atom.get("options")
        if not options:
            return None

        # Check if we have a properly marked correct answer
        has_correct = any(o.get("correct") for o in options)
        if not has_correct:
            # Can't give elimination hint without knowing correct answer
            explanation = atom.get("_explanation")
            if explanation:
                return f"Hint: {explanation}"
            return "Think about which answer best fits the question context."

        incorrect_options = [o["text"] for o in options if not o["correct"]]
        if incorrect_options:
            return f"'{random.choice(incorrect_options)}' is NOT the answer"

        return None
