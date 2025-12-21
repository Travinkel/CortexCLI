"""
List recall atom handler.

Order-independent set recall - user must recall all items in a list,
but order doesn't matter. Supports partial credit.
"""

from typing import Any

from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt

from src.delivery.cortex_visuals import get_asi_prompt

from . import AtomType, register
from .base import AnswerResult, is_dont_know


@register(AtomType.LIST_RECALL)
class ListRecallHandler:
    """Handler for order-independent list recall atoms."""

    def validate(self, atom: dict) -> bool:
        """Check if atom has required list recall fields."""
        prompt = atom.get("front") or atom.get("prompt", "")
        correct = atom.get("correct") or atom.get("items") or atom.get("back")

        # Correct can be a list or comma-separated string
        if isinstance(correct, str):
            correct = [x.strip() for x in correct.split(",") if x.strip()]

        return bool(prompt and correct and len(correct) >= 1)

    def present(self, atom: dict, console: Console) -> None:
        """Display the list recall prompt."""
        prompt = atom.get("front") or atom.get("prompt", "No question")
        correct = self._get_correct_list(atom)
        count = len(correct)

        panel = Panel(
            prompt,
            title=f"[bold cyan]LIST RECALL ({count} items)[/bold cyan]",
            border_style="cyan",
            box=box.HEAVY,
            padding=(1, 2),
        )
        console.print(panel)

    def get_input(self, atom: dict, console: Console) -> dict:
        """Get user's list of answers."""
        correct = self._get_correct_list(atom)
        count = len(correct)

        console.print(f"[dim]Enter {count} items (comma-separated or one per line).[/dim]")
        console.print("[dim]Type 'done' when finished. 'h'=hint, '?'=I don't know[/dim]")

        hint_count = 0
        answers: list[str] = []

        while True:
            prompt_text = get_asi_prompt("list_recall", f"[{len(answers) + 1}/{count}]")
            user_input = Prompt.ask(prompt_text)

            if is_dont_know(user_input):
                return {"dont_know": True, "answers": answers, "hints_used": hint_count}

            if user_input.lower() == "h":
                hint_count += 1
                hint_text = self.hint(atom, hint_count, answers)
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

            console.print(f"[dim]Added. {count - len(answers)} remaining.[/dim]")

            if len(answers) >= count:
                break

        return {"answers": answers, "hints_used": hint_count, "dont_know": False}

    def check(self, atom: dict, answer: Any, console: Console | None = None) -> AnswerResult:
        """Check if user's list matches (order-independent)."""
        correct = self._get_correct_list(atom)

        if isinstance(answer, dict):
            if answer.get("dont_know"):
                return AnswerResult(
                    correct=False,
                    feedback="Let's learn this one!",
                    user_answer="I don't know",
                    correct_answer=", ".join(correct),
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

        # Grade using set comparison
        result = self._grade(user_answers, correct)

        # Build feedback
        if result["is_correct"]:
            feedback = "Correct! All items recalled."
        else:
            missing = result.get("missing", [])
            extra = result.get("extra", [])
            feedback_parts = []
            if missing:
                feedback_parts.append(f"Missing: {', '.join(missing)}")
            if extra:
                feedback_parts.append(f"Extra: {', '.join(extra)}")
            feedback = "; ".join(feedback_parts) if feedback_parts else "Incorrect"

        return AnswerResult(
            correct=result["is_correct"],
            feedback=feedback,
            user_answer=", ".join(user_answers),
            correct_answer=", ".join(correct),
            partial_score=result["partial_score"],
            explanation=atom.get("explanation") if not result["is_correct"] else None,
        )

    def hint(
        self, atom: dict, attempt: int, current_answers: list[str] | None = None
    ) -> str | None:
        """Progressive hints for list recall."""
        correct = self._get_correct_list(atom)
        if not correct:
            return None

        current_answers = current_answers or []
        current_set = {a.lower().strip() for a in current_answers}

        # Find items not yet answered
        remaining = [c for c in correct if c.lower().strip() not in current_set]

        if not remaining:
            return "You've recalled all items!"

        if attempt == 1:
            # Show count remaining
            return f"{len(remaining)} items remaining to recall"
        elif attempt == 2 and remaining:
            # First letter of a missing item
            return f"One item starts with: {remaining[0][0].upper()}..."
        elif attempt == 3 and remaining:
            # More specific hint
            item = remaining[0]
            if len(item) > 2:
                return f"Missing item: {item[0]}...{item[-1]} ({len(item)} letters)"

        return None

    def _get_correct_list(self, atom: dict) -> list[str]:
        """Extract the correct list from atom."""
        correct = atom.get("correct") or atom.get("items") or atom.get("back")

        if isinstance(correct, str):
            return [x.strip() for x in correct.split(",") if x.strip()]
        elif isinstance(correct, list):
            return [str(x).strip() for x in correct]

        return []

    def _grade(self, user_answers: list[str], correct: list[str]) -> dict:
        """Set match grading (order doesn't matter)."""
        user_set = {a.lower().strip() for a in user_answers if a.strip()}
        correct_set = {c.lower().strip() for c in correct}

        matched = user_set & correct_set
        missing = correct_set - user_set
        extra = user_set - correct_set

        return {
            "is_correct": user_set == correct_set,
            "partial_score": len(matched) / len(correct_set) if correct_set else 0.0,
            "missing": [c for c in correct if c.lower().strip() in missing],
            "extra": list(extra),
            "matched": list(matched),
        }
