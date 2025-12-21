"""
Ordered list recall atom handler.

Order-dependent sequence recall - user must recall all items in a list
in the correct order. Supports partial credit based on position matching.
"""

from typing import Any

from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt

from src.delivery.cortex_visuals import get_asi_prompt

from . import AtomType, register
from .base import AnswerResult, is_dont_know


@register(AtomType.ORDERED_LIST_RECALL)
class OrderedListRecallHandler:
    """Handler for order-dependent list recall atoms."""

    def validate(self, atom: dict) -> bool:
        """Check if atom has required ordered list recall fields."""
        prompt = atom.get("front") or atom.get("prompt", "")
        correct = atom.get("correct") or atom.get("sequence") or atom.get("back")

        # Correct can be a list or comma-separated string
        if isinstance(correct, str):
            correct = [x.strip() for x in correct.split(",") if x.strip()]

        return bool(prompt and correct and len(correct) >= 2)

    def present(self, atom: dict, console: Console) -> None:
        """Display the ordered list recall prompt."""
        prompt = atom.get("front") or atom.get("prompt", "No question")
        correct = self._get_correct_list(atom)
        count = len(correct)

        panel = Panel(
            prompt,
            title=f"[bold cyan]SEQUENCE RECALL ({count} items, order matters)[/bold cyan]",
            border_style="cyan",
            box=box.HEAVY,
            padding=(1, 2),
        )
        console.print(panel)

    def get_input(self, atom: dict, console: Console) -> dict:
        """Get user's ordered list of answers."""
        correct = self._get_correct_list(atom)
        count = len(correct)

        console.print(f"[dim]Enter {count} items in order (comma-separated or one per line).[/dim]")
        console.print("[dim]Type 'done' when finished. 'h'=hint, '?'=I don't know[/dim]")

        hint_count = 0
        answers: list[str] = []

        while True:
            position = len(answers) + 1
            prompt_text = get_asi_prompt("ordered_list", f"[{position}/{count}]")
            user_input = Prompt.ask(prompt_text)

            if is_dont_know(user_input):
                return {"dont_know": True, "answers": answers, "hints_used": hint_count}

            if user_input.lower() == "h":
                hint_count += 1
                hint_text = self.hint(atom, hint_count, len(answers))
                if hint_text:
                    console.print(f"[yellow]Hint {hint_count}:[/yellow] {hint_text}")
                else:
                    console.print("[dim]No more hints available[/dim]")
                continue

            if user_input.lower() == "done":
                break

            # Handle comma-separated input
            if "," in user_input:
                items = [x.strip() for x in user_input.split(",") if x.strip()]
                answers.extend(items)
            else:
                answers.append(user_input.strip())

            console.print(
                f"[dim]Position {len(answers)} recorded. {count - len(answers)} remaining.[/dim]"
            )

            if len(answers) >= count:
                break

        return {"answers": answers, "hints_used": hint_count, "dont_know": False}

    def check(self, atom: dict, answer: Any, console: Console | None = None) -> AnswerResult:
        """Check if user's list matches in order."""
        correct = self._get_correct_list(atom)

        if isinstance(answer, dict):
            if answer.get("dont_know"):
                return AnswerResult(
                    correct=False,
                    feedback="Let's learn this one!",
                    user_answer="I don't know",
                    correct_answer=" → ".join(correct),
                    explanation=atom.get("explanation", ""),
                    dont_know=True,
                )
            user_answers = answer.get("answers", [])
        else:
            # Handle string or list input
            if isinstance(answer, str):
                user_answers = [x.strip() for x in answer.split(",") if x.strip()]
            else:
                user_answers = list(answer) if answer else []

        # Grade using sequence comparison
        result = self._grade(user_answers, correct)

        # Build feedback
        if result["is_correct"]:
            feedback = "Correct! Perfect sequence."
        else:
            correct_positions = result.get("correct_positions", [])
            total = len(correct)
            feedback = f"{len(correct_positions)}/{total} positions correct."

            # Show first wrong position
            wrong_positions = result.get("wrong_positions", [])
            if wrong_positions:
                first_wrong = wrong_positions[0]
                if first_wrong < len(user_answers):
                    feedback += f" Position {first_wrong + 1} should be '{correct[first_wrong]}'"

        return AnswerResult(
            correct=result["is_correct"],
            feedback=feedback,
            user_answer=" → ".join(user_answers),
            correct_answer=" → ".join(correct),
            partial_score=result["partial_score"],
            explanation=atom.get("explanation") if not result["is_correct"] else None,
        )

    def hint(self, atom: dict, attempt: int, current_position: int = 0) -> str | None:
        """Progressive hints for ordered list recall."""
        correct = self._get_correct_list(atom)
        if not correct:
            return None

        if attempt == 1:
            # Reveal first item
            return f"First item: {correct[0]}"
        elif attempt == 2:
            # Reveal last item
            return f"Last item: {correct[-1]}"
        elif attempt == 3 and current_position < len(correct):
            # Reveal next expected item
            return f"Position {current_position + 1} should be: {correct[current_position]}"

        return None

    def _get_correct_list(self, atom: dict) -> list[str]:
        """Extract the correct sequence from atom."""
        correct = atom.get("correct") or atom.get("sequence") or atom.get("back")

        if isinstance(correct, str):
            return [x.strip() for x in correct.split(",") if x.strip()]
        elif isinstance(correct, list):
            return [str(x).strip() for x in correct]

        return []

    def _grade(self, user_answers: list[str], correct: list[str]) -> dict:
        """Sequence match grading (order matters)."""
        # Normalize for comparison
        user_normalized = [a.lower().strip() for a in user_answers]
        correct_normalized = [c.lower().strip() for c in correct]

        # Count correct positions
        correct_positions = []
        wrong_positions = []

        for i, (u, c) in enumerate(zip(user_normalized, correct_normalized)):
            if u == c:
                correct_positions.append(i)
            else:
                wrong_positions.append(i)

        # Also track missing positions (if user provided fewer items)
        for i in range(len(user_normalized), len(correct_normalized)):
            wrong_positions.append(i)

        # Calculate partial score
        if not correct:
            partial_score = 0.0
        else:
            partial_score = len(correct_positions) / len(correct)

        # Perfect match requires same length and all positions correct
        is_correct = len(user_normalized) == len(correct_normalized) and len(
            correct_positions
        ) == len(correct)

        return {
            "is_correct": is_correct,
            "partial_score": partial_score,
            "correct_positions": correct_positions,
            "wrong_positions": wrong_positions,
        }
