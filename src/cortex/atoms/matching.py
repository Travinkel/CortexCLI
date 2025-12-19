"""
Matching atom handler.

User matches terms to definitions. Definitions are shuffled,
user provides pairs like "1A 2B 3C".
"""

import random
from typing import Any

from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt
from rich.table import Table
from rich.style import Style

from src.delivery.cortex_visuals import (
    CORTEX_THEME,
    STYLES,
    cortex_result_panel,
    get_asi_prompt,
)
from . import AtomType, register
from .base import AnswerResult, is_dont_know


@register(AtomType.MATCHING)
class MatchingHandler:
    """Handler for matching atoms."""

    def validate(self, atom: dict) -> bool:
        """Check if atom has required matching fields (pairs)."""
        pairs = atom.get("pairs", [])
        return bool(pairs and len(pairs) >= 2)

    def present(self, atom: dict, console: Console) -> None:
        """Display the matching question."""
        front = atom.get("front", "Match the following:")
        panel = Panel(
            front,
            title="[bold cyan]MATCH PAIRS[/bold cyan]",
            border_style="cyan",
            box=box.HEAVY,
            padding=(1, 2),
        )
        console.print(panel)

    def get_input(self, atom: dict, console: Console) -> dict:
        """Display terms/definitions and get user matches."""
        pairs = atom.get("pairs", [])
        if not pairs:
            console.print("[yellow]No matching pairs available[/yellow]")
            return {"skipped": True}

        # Extract terms and definitions
        terms = [p.get("term", "") for p in pairs]
        definitions = [p.get("definition", "") for p in pairs]

        # Shuffle definitions
        shuffled_defs = definitions.copy()
        random.shuffle(shuffled_defs)

        # Display terms
        console.print("\n[bold cyan]TERMS:[/bold cyan]")
        for i, term in enumerate(terms, 1):
            console.print(f"  [{i}] {term}")

        # Display shuffled definitions
        console.print("\n[bold cyan]DEFINITIONS:[/bold cyan]")
        for i, defn in enumerate(shuffled_defs, 1):
            console.print(f"  ({chr(64 + i)}) {defn}")

        # Get matches
        console.print("\n[dim]Match terms to definitions (e.g., 1A 2B 3C). '?'=I don't know[/dim]")
        user_input = Prompt.ask(
            get_asi_prompt("matching"), default=""
        ).strip()

        # Check for "I don't know"
        if is_dont_know(user_input):
            return {
                "dont_know": True,
                "terms": terms,
                "definitions": definitions,
            }

        user_input = user_input.upper()

        # Parse matches
        user_matches = {}
        for match in user_input.split():
            if len(match) >= 2 and match[0].isdigit():
                term_idx = int(match[0]) - 1
                def_idx = ord(match[-1]) - ord("A")
                if 0 <= term_idx < len(terms) and 0 <= def_idx < len(shuffled_defs):
                    user_matches[term_idx] = def_idx

        return {
            "user_matches": user_matches,
            "terms": terms,
            "definitions": definitions,
            "shuffled_defs": shuffled_defs,
            "user_input": user_input,
            "dont_know": False,
        }

    def check(self, atom: dict, answer: Any, console: Console | None = None) -> AnswerResult:
        """Check matching pairs."""
        if answer.get("skipped"):
            return AnswerResult(
                correct=True,
                feedback="Skipped",
                user_answer="skipped",
                correct_answer="",
            )

        # Handle "I don't know"
        if answer.get("dont_know"):
            terms = answer.get("terms", [])
            definitions = answer.get("definitions", [])
            correct_answer = "\n".join(
                f"{i + 1}. {terms[i]} -> {definitions[i]}"
                for i in range(len(terms))
            )
            return AnswerResult(
                correct=False,
                feedback="Let's learn this one!",
                user_answer="I don't know",
                correct_answer=correct_answer,
                dont_know=True,
            )

        user_matches = answer.get("user_matches", {})
        terms = answer.get("terms", [])
        definitions = answer.get("definitions", [])
        shuffled_defs = answer.get("shuffled_defs", [])
        user_input = answer.get("user_input", "")

        # Count correct matches
        correct_count = 0
        for i, term in enumerate(terms):
            correct_def = definitions[i]
            shuffled_idx = shuffled_defs.index(correct_def)
            if user_matches.get(i) == shuffled_idx:
                correct_count += 1

        is_correct = correct_count == len(terms)
        partial_score = correct_count / len(terms) if terms else 0

        # Build correct answer string
        correct_answer = "\n".join(
            f"{i + 1}. {terms[i]} -> {definitions[i]}"
            for i in range(len(terms))
        )

        return AnswerResult(
            correct=is_correct,
            feedback=f"{correct_count}/{len(terms)} correct",
            user_answer=user_input,
            correct_answer=correct_answer,
            partial_score=partial_score,
        )

    def hint(self, atom: dict, attempt: int) -> str | None:
        """Progressive hints for matching."""
        pairs = atom.get("pairs", [])
        if not pairs:
            return None

        if attempt == 1 and len(pairs) > 0:
            # Give one correct pair
            first = pairs[0]
            return f"Hint: '{first.get('term', '')}' matches with something about '{first.get('definition', '')[:20]}...'"
        elif attempt == 2 and len(pairs) > 1:
            # Give another pair
            second = pairs[1]
            term = second.get("term", "")
            defn = second.get("definition", "")
            return f"Hint: '{term}' -> '{defn[:15]}...'"

        return None
