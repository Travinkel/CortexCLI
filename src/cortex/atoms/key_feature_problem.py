"""
Key Feature Problem (KFP) atom handler.

Critical decision-making: Select the N most important steps/actions
from a list. Tests prioritization and triage skills.

Example: "A network is down. Select the 3 most critical first steps."
"""

import json
from typing import Any

from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt
from rich.table import Table

from . import AtomType, register
from .base import AnswerResult, is_dont_know


def _parse_kfp(back: str) -> dict:
    """
    Parse KFP data from the 'back' field.

    Expected JSON format:
    {
        "scenario": "Network outage affecting 500 users",
        "options": [
            "Check cable connections",
            "Restart all switches",
            "Verify power to network closet",
            "Update firmware",
            "Check spanning tree logs",
            "Notify management"
        ],
        "key_features": [0, 2, 4],  # indices of critical steps
        "required_count": 3,
        "explanation": "Power and physical layer first, then L2 diagnostics"
    }
    """
    try:
        data = json.loads(back)
        if isinstance(data, dict) and "options" in data and "key_features" in data:
            return data
    except (json.JSONDecodeError, TypeError):
        pass

    return {}


@register(AtomType.KEY_FEATURE_PROBLEM)
class KeyFeatureProblemHandler:
    """Handler for Key Feature Problem atoms - critical step selection."""

    def validate(self, atom: dict) -> bool:
        """Check if atom has valid KFP data."""
        back = atom.get("back", "")
        kfp_data = _parse_kfp(back)
        return bool(
            kfp_data.get("options")
            and kfp_data.get("key_features")
            and len(kfp_data["options"]) >= 3
        )

    def present(self, atom: dict, console: Console) -> None:
        """Display the KFP scenario and options."""
        kfp_data = _parse_kfp(atom.get("back", ""))

        if not kfp_data:
            front = atom.get("front", "Select critical steps")
            console.print(Panel(front, title="[bold cyan]KEY FEATURE PROBLEM[/bold cyan]"))
            return

        # Store parsed data
        atom["_kfp_data"] = kfp_data

        scenario = kfp_data.get("scenario", atom.get("front", "Critical scenario"))
        required_count = kfp_data.get("required_count", 3)

        # Scenario panel
        console.print(Panel(
            scenario,
            title=f"[bold cyan]KEY FEATURE PROBLEM (Select {required_count})[/bold cyan]",
            border_style="cyan",
            box=box.HEAVY,
            padding=(1, 2),
        ))

    def get_input(self, atom: dict, console: Console) -> dict:
        """Get user's selection of key features."""
        kfp_data = atom.get("_kfp_data") or _parse_kfp(atom.get("back", ""))
        options = kfp_data.get("options", [])
        required_count = kfp_data.get("required_count", 3)

        if not options:
            return {"skipped": True}

        # Display options
        console.print("\n[bold yellow]AVAILABLE ACTIONS[/bold yellow]")
        table = Table(box=box.SIMPLE, show_header=False)
        table.add_column("#", style="cyan", width=4)
        table.add_column("Action", style="white")

        for i, option in enumerate(options, 1):
            table.add_row(f"[{i}]", option)

        console.print(table)

        console.print(f"\n[dim]Select {required_count} most critical steps[/dim]")
        console.print("[dim]Enter numbers separated by spaces (e.g., 1 3 5)[/dim]")
        console.print("[dim]'?' = I don't know[/dim]")

        while True:
            response = Prompt.ask(f"Select {required_count} critical steps")

            if is_dont_know(response):
                return {"dont_know": True}

            # Parse selections
            parts = response.replace(",", " ").split()
            selections = []
            for p in parts:
                if p.isdigit():
                    idx = int(p) - 1
                    if 0 <= idx < len(options):
                        selections.append(idx)

            if len(selections) == required_count:
                return {"selections": selections, "user_input": response}
            elif len(selections) > required_count:
                console.print(f"[yellow]Please select exactly {required_count} (you selected {len(selections)})[/yellow]")
            else:
                console.print(f"[yellow]Please select {required_count} valid options[/yellow]")

    def check(self, atom: dict, answer: Any, console: Console | None = None) -> AnswerResult:
        """Check selected key features."""
        kfp_data = atom.get("_kfp_data") or _parse_kfp(atom.get("back", ""))
        options = kfp_data.get("options", [])
        key_features = set(kfp_data.get("key_features", []))
        required_count = kfp_data.get("required_count", 3)
        explanation = kfp_data.get("explanation", "")

        # Build correct answer string
        correct_options = [options[i] for i in key_features if i < len(options)]
        correct_answer_str = "; ".join(correct_options)

        if answer.get("skipped"):
            return AnswerResult(
                correct=True,
                feedback="Skipped",
                user_answer="skipped",
                correct_answer=correct_answer_str,
            )

        if answer.get("dont_know"):
            return AnswerResult(
                correct=False,
                feedback="Let's learn critical decision-making!",
                user_answer="I don't know",
                correct_answer=correct_answer_str,
                explanation=explanation,
                dont_know=True,
            )

        user_selections = set(answer.get("selections", []))

        # Calculate score: correct selections / required count
        correct_count = len(user_selections & key_features)
        partial_score = correct_count / required_count if required_count > 0 else 0.0

        is_correct = user_selections == key_features

        # Build user answer string
        user_options = [options[i] for i in sorted(user_selections) if i < len(options)]
        user_answer_str = "; ".join(user_options)

        # Build feedback
        if is_correct:
            feedback = "Perfect! All key features identified."
        elif correct_count == required_count - 1:
            feedback = f"Almost! {correct_count}/{required_count} correct"
        elif correct_count > 0:
            feedback = f"Partial credit: {correct_count}/{required_count} correct"
        else:
            feedback = f"None of the key features selected"

        return AnswerResult(
            correct=is_correct,
            feedback=feedback,
            user_answer=user_answer_str,
            correct_answer=correct_answer_str,
            partial_score=partial_score,
            explanation=explanation,
        )

    def hint(self, atom: dict, attempt: int) -> str | None:
        """Provide hints for key feature selection."""
        kfp_data = atom.get("_kfp_data") or _parse_kfp(atom.get("back", ""))
        options = kfp_data.get("options", [])
        key_features = kfp_data.get("key_features", [])

        if not key_features or not options:
            return None

        if attempt == 1:
            # Hint: reveal one key feature
            if key_features:
                idx = key_features[0]
                if idx < len(options):
                    return f"One critical step is: '{options[idx]}'"

        elif attempt == 2:
            # Hint: general guidance
            explanation = kfp_data.get("explanation", "")
            if explanation:
                return f"Consider: {explanation}"
            return "Focus on immediate impact and dependencies"

        return None
