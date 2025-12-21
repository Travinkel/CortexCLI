"""
Categorization atom handler.

Bucket sorting where users assign items to categories.
Example: Sort network protocols into OSI layers.
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


def _parse_categorization(back: str) -> tuple[dict[str, list[str]], list[str]]:
    """
    Parse categorization data from the 'back' field.

    Returns: (correct_mapping, items)

    Expected JSON format:
    {
        "categories": {"Physical": ["Cable", "Hub"], "Network": ["IP", "Router"]},
        "items": ["Cable", "Hub", "IP", "Router"]  # optional, derived if missing
    }
    """
    try:
        data = json.loads(back)
        if isinstance(data, dict) and "categories" in data:
            categories = data["categories"]
            # Flatten all items if not provided
            items = data.get("items")
            if not items:
                items = []
                for cat_items in categories.values():
                    items.extend(cat_items)
            return categories, items
    except (json.JSONDecodeError, TypeError):
        pass

    return {}, []


@register(AtomType.CATEGORIZATION)
class CategorizationHandler:
    """Handler for categorization atoms - bucket sorting."""

    def validate(self, atom: dict) -> bool:
        """Check if atom has valid categorization data."""
        back = atom.get("back", "")
        categories, items = _parse_categorization(back)
        return bool(categories and items)

    def present(self, atom: dict, console: Console) -> None:
        """Display the categorization prompt and items."""
        front = atom.get("front", "Sort items into categories")
        panel = Panel(
            front,
            title="[bold cyan]CATEGORIZATION[/bold cyan]",
            border_style="cyan",
            box=box.HEAVY,
            padding=(1, 2),
        )
        console.print(panel)

    def get_input(self, atom: dict, console: Console) -> dict:
        """Get user's categorization of items."""
        categories, items = _parse_categorization(atom.get("back", ""))

        if not categories or not items:
            return {"skipped": True}

        # Store for later reference
        atom["_categories"] = categories
        atom["_items"] = items

        # Display available categories
        category_names = list(categories.keys())
        console.print("\n[bold yellow]CATEGORIES[/bold yellow]")
        for i, cat in enumerate(category_names, 1):
            console.print(f"  [{i}] {cat}")

        # Display items to categorize
        console.print("\n[bold yellow]ITEMS TO SORT[/bold yellow]")
        for i, item in enumerate(items, 1):
            console.print(f"  [{i}] {item}")

        console.print("\n[dim]For each item, enter the category number[/dim]")
        console.print("[dim]Format: item_num:category_num (e.g., 1:2 2:1 3:3)[/dim]")
        console.print("[dim]Or enter '?' if you don't know[/dim]")

        user_input = Prompt.ask("Assignments")

        if is_dont_know(user_input):
            return {"dont_know": True}

        # Parse assignments: "1:2 2:1 3:3" means item1->cat2, item2->cat1, etc.
        user_mapping: dict[str, list[str]] = {cat: [] for cat in category_names}
        assignments = user_input.replace(",", " ").split()

        for assignment in assignments:
            if ":" in assignment:
                parts = assignment.split(":")
                if len(parts) == 2 and parts[0].isdigit() and parts[1].isdigit():
                    item_idx = int(parts[0]) - 1
                    cat_idx = int(parts[1]) - 1
                    if 0 <= item_idx < len(items) and 0 <= cat_idx < len(category_names):
                        item = items[item_idx]
                        cat = category_names[cat_idx]
                        user_mapping[cat].append(item)

        return {"mapping": user_mapping, "user_input": user_input}

    def check(self, atom: dict, answer: Any, console: Console | None = None) -> AnswerResult:
        """Check categorization and calculate partial credit."""
        categories = atom.get("_categories", {})
        items = atom.get("_items", [])

        if not categories:
            categories, items = _parse_categorization(atom.get("back", ""))

        if answer.get("skipped"):
            return AnswerResult(
                correct=True,
                feedback="Skipped",
                user_answer="skipped",
                correct_answer=json.dumps(categories),
            )

        if answer.get("dont_know"):
            return AnswerResult(
                correct=False,
                feedback="Let's learn the categories!",
                user_answer="I don't know",
                correct_answer=json.dumps(categories),
                dont_know=True,
            )

        user_mapping = answer.get("mapping", {})

        # Calculate score: correct items / total items
        correct_count = 0
        total_items = len(items)

        for cat, correct_items in categories.items():
            user_items = set(user_mapping.get(cat, []))
            correct_set = set(correct_items)
            # Count items correctly placed in this category
            correct_count += len(user_items & correct_set)

        partial_score = correct_count / total_items if total_items > 0 else 0.0
        is_correct = partial_score == 1.0

        # Build feedback
        if is_correct:
            feedback = "Perfect categorization!"
        elif partial_score >= 0.8:
            feedback = f"Almost there! {correct_count}/{total_items} correct"
        elif partial_score >= 0.5:
            feedback = f"Partial credit: {correct_count}/{total_items} correct"
        else:
            feedback = f"Keep practicing: {correct_count}/{total_items} correct"

        # Format user answer for display
        user_answer_str = "; ".join(
            f"{cat}: {', '.join(items) if items else 'none'}"
            for cat, items in user_mapping.items()
        )

        correct_answer_str = "; ".join(
            f"{cat}: {', '.join(items)}"
            for cat, items in categories.items()
        )

        return AnswerResult(
            correct=is_correct,
            feedback=feedback,
            user_answer=user_answer_str or answer.get("user_input", ""),
            correct_answer=correct_answer_str,
            partial_score=partial_score,
        )

    def hint(self, atom: dict, attempt: int) -> str | None:
        """Provide progressive hints."""
        categories = atom.get("_categories", {})
        if not categories:
            categories, _ = _parse_categorization(atom.get("back", ""))

        if not categories:
            return None

        category_names = list(categories.keys())

        if attempt == 1:
            # Hint: show one correct item per category
            hints = []
            for cat, items in categories.items():
                if items:
                    hints.append(f"'{items[0]}' belongs in {cat}")
                    break
            return hints[0] if hints else None

        elif attempt == 2:
            # Hint: show number of items per category
            return "Items per category: " + ", ".join(
                f"{cat}: {len(items)}" for cat, items in categories.items()
            )

        return None
