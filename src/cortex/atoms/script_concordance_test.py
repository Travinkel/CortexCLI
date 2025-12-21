"""
Script Concordance Test (SCT) atom handler.

Diagnostic reasoning assessment: Given a scenario and hypothesis,
how does new information affect the hypothesis's likelihood?

Used in medical/networking/troubleshooting domains to test
expert-like reasoning patterns.
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


# SCT response scale (Likert-like)
SCT_SCALE = {
    -2: "Much less likely",
    -1: "Somewhat less likely",
    0: "Unchanged",
    1: "Somewhat more likely",
    2: "Much more likely",
}


def _parse_sct(back: str) -> dict:
    """
    Parse SCT data from the 'back' field.

    Expected JSON format:
    {
        "scenario": "Network has intermittent connectivity",
        "hypothesis": "Spanning tree loop",
        "new_info": "MAC table shows port flapping",
        "expert_consensus": 2,  # -2 to +2 scale
        "expert_distribution": {"-2": 0, "-1": 1, "0": 2, "1": 5, "2": 12}
    }
    """
    try:
        data = json.loads(back)
        if isinstance(data, dict) and all(
            key in data for key in ["scenario", "hypothesis", "new_info"]
        ):
            return data
    except (json.JSONDecodeError, TypeError):
        pass

    return {}


def _calculate_sct_score(user_response: int, expert_distribution: dict) -> float:
    """
    Calculate SCT score based on expert panel distribution.

    The score is based on what percentage of experts agreed with the user.
    If 80% of experts said +2 and user said +2, score is 0.8.
    """
    if not expert_distribution:
        return 1.0 if user_response == 0 else 0.5  # Default if no distribution

    total_experts = sum(expert_distribution.values())
    if total_experts == 0:
        return 0.5

    user_key = str(user_response)
    matching_experts = expert_distribution.get(user_key, 0)

    return matching_experts / total_experts


@register(AtomType.SCRIPT_CONCORDANCE_TEST)
class ScriptConcordanceTestHandler:
    """Handler for Script Concordance Test atoms - diagnostic reasoning."""

    def validate(self, atom: dict) -> bool:
        """Check if atom has valid SCT data."""
        back = atom.get("back", "")
        sct_data = _parse_sct(back)
        return bool(
            sct_data.get("scenario")
            and sct_data.get("hypothesis")
            and sct_data.get("new_info")
        )

    def present(self, atom: dict, console: Console) -> None:
        """Display the SCT scenario."""
        sct_data = _parse_sct(atom.get("back", ""))

        if not sct_data:
            front = atom.get("front", "No scenario")
            console.print(Panel(front, title="[bold cyan]DIAGNOSTIC REASONING[/bold cyan]"))
            return

        # Store parsed data
        atom["_sct_data"] = sct_data

        # Build the presentation
        scenario = sct_data.get("scenario", "")
        hypothesis = sct_data.get("hypothesis", "")
        new_info = sct_data.get("new_info", "")

        # Scenario panel
        console.print(Panel(
            f"[bold]Scenario:[/bold] {scenario}",
            title="[bold cyan]SCRIPT CONCORDANCE TEST[/bold cyan]",
            border_style="cyan",
            box=box.HEAVY,
            padding=(1, 2),
        ))

        # Hypothesis
        console.print(Panel(
            f"[bold]Hypothesis:[/bold] {hypothesis}",
            title="[bold yellow]WORKING DIAGNOSIS[/bold yellow]",
            border_style="yellow",
            box=box.ROUNDED,
            padding=(0, 2),
        ))

        # New information
        console.print(Panel(
            f"[bold]New Information:[/bold] {new_info}",
            title="[bold magenta]NEW DATA[/bold magenta]",
            border_style="magenta",
            box=box.ROUNDED,
            padding=(0, 2),
        ))

    def get_input(self, atom: dict, console: Console) -> dict:
        """Get user's assessment of how new info affects hypothesis."""
        sct_data = atom.get("_sct_data") or _parse_sct(atom.get("back", ""))
        hypothesis = sct_data.get("hypothesis", "the hypothesis")

        # Display the scale
        console.print(f"\n[bold]Does this make '{hypothesis}':[/bold]")
        console.print()

        table = Table(box=box.SIMPLE, show_header=False)
        table.add_column("Value", style="cyan", width=6)
        table.add_column("Meaning", style="white")

        for value in [-2, -1, 0, 1, 2]:
            table.add_row(f"[{value:+d}]", SCT_SCALE[value])

        console.print(table)
        console.print("[dim]Enter -2, -1, 0, +1, or +2. '?' = I don't know[/dim]")

        while True:
            response = Prompt.ask("Your assessment")

            if is_dont_know(response):
                return {"dont_know": True}

            # Parse response
            response = response.replace("+", "").strip()
            try:
                value = int(response)
                if -2 <= value <= 2:
                    return {"response": value}
                console.print("[yellow]Please enter -2, -1, 0, 1, or 2[/yellow]")
            except ValueError:
                console.print("[yellow]Please enter a valid number[/yellow]")

    def check(self, atom: dict, answer: Any, console: Console | None = None) -> AnswerResult:
        """Check answer against expert consensus."""
        sct_data = atom.get("_sct_data") or _parse_sct(atom.get("back", ""))

        expert_consensus = sct_data.get("expert_consensus", 0)
        expert_distribution = sct_data.get("expert_distribution", {})

        if answer.get("dont_know"):
            return AnswerResult(
                correct=False,
                feedback="Let's learn diagnostic reasoning!",
                user_answer="I don't know",
                correct_answer=f"{expert_consensus:+d} ({SCT_SCALE.get(expert_consensus, 'Unknown')})",
                partial_score=0.0,
                dont_know=True,
            )

        user_response = answer.get("response", 0)

        # Calculate score based on expert distribution
        if expert_distribution:
            partial_score = _calculate_sct_score(user_response, expert_distribution)
        else:
            # Fall back to distance from consensus
            distance = abs(user_response - expert_consensus)
            partial_score = max(0.0, 1.0 - (distance * 0.25))

        # Determine correctness (within 1 of consensus = acceptable)
        is_correct = abs(user_response - expert_consensus) <= 1

        # Build feedback
        user_label = SCT_SCALE.get(user_response, "Unknown")
        expert_label = SCT_SCALE.get(expert_consensus, "Unknown")

        if user_response == expert_consensus:
            feedback = f"Expert match! ({expert_label})"
        elif is_correct:
            feedback = f"Close to experts. You: {user_label}, Experts: {expert_label}"
        else:
            feedback = f"Experts disagree. You: {user_label}, Experts: {expert_label}"

        # Add distribution info if available
        explanation = None
        if expert_distribution:
            dist_str = ", ".join(
                f"{k}: {v}" for k, v in sorted(expert_distribution.items())
            )
            explanation = f"Expert panel distribution: {dist_str}"

        return AnswerResult(
            correct=is_correct,
            feedback=feedback,
            user_answer=f"{user_response:+d} ({user_label})",
            correct_answer=f"{expert_consensus:+d} ({expert_label})",
            partial_score=partial_score,
            explanation=explanation,
        )

    def hint(self, atom: dict, attempt: int) -> str | None:
        """Provide hints for diagnostic reasoning."""
        sct_data = atom.get("_sct_data") or _parse_sct(atom.get("back", ""))

        if attempt == 1:
            # Hint: explain the relationship between info and hypothesis
            hypothesis = sct_data.get("hypothesis", "")
            new_info = sct_data.get("new_info", "")
            return f"Consider: Does '{new_info}' typically indicate or contradict '{hypothesis}'?"

        elif attempt == 2:
            # Hint: reveal direction (not magnitude)
            expert_consensus = sct_data.get("expert_consensus", 0)
            if expert_consensus > 0:
                return "Experts lean toward 'more likely'"
            elif expert_consensus < 0:
                return "Experts lean toward 'less likely'"
            else:
                return "Experts consider this unchanged"

        return None
