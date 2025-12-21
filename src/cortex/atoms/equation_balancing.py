"""
Equation Balancing atom handler.

User adjusts coefficients to balance chemical/mathematical equations.
Supports partial credit based on coefficient accuracy.
"""

import re
from typing import Any

from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt
from rich.style import Style
from rich.table import Table
from rich.text import Text

from src.delivery.cortex_visuals import (
    CORTEX_THEME,
    STYLES,
    get_asi_prompt,
)

from . import AtomType, register
from .base import AnswerResult, is_dont_know


@register(AtomType.EQUATION_BALANCING)
class EquationBalancingHandler:
    """Handler for equation balancing atoms (coefficient adjustment)."""

    def validate(self, atom: dict) -> bool:
        """Check if atom has required equation balancing fields."""
        # Check for equation string with coefficients (minimal form)
        equation = atom.get("equation", "")
        coefficients = atom.get("coefficients", {})

        if equation and coefficients:
            return True

        # Check for equation components
        reactants = atom.get("reactants", [])
        products = atom.get("products", [])

        # Need at least 1 reactant and 1 product
        return len(reactants) >= 1 and len(products) >= 1

    def present(self, atom: dict, console: Console) -> None:
        """Display the equation balancing context."""
        front = atom.get("front", "Balance the following equation:")

        panel = Panel(
            front,
            title="[bold cyan]EQUATION BALANCING[/bold cyan]",
            border_style="cyan",
            box=box.HEAVY,
            padding=(1, 2),
        )
        console.print(panel)

    def get_input(self, atom: dict, console: Console) -> dict:
        """Display equation and get user coefficients."""
        equation = atom.get("equation", "")
        reactants = atom.get("reactants", [])
        products = atom.get("products", [])
        coefficients = atom.get("coefficients", {})

        if not equation and (not reactants or not products):
            console.print("[yellow]No equation found[/yellow]")
            return {"skipped": True}

        # Build equation display from components if not provided
        if not equation:
            equation = self._build_equation(reactants, products)

        # Show the unbalanced equation
        eq_text = Text()
        eq_text.append("  ", style="dim")
        eq_text.append(equation, style="bold white")

        eq_panel = Panel(
            eq_text,
            title="[bold yellow][*] UNBALANCED EQUATION[/bold yellow]",
            border_style=Style(color=CORTEX_THEME["warning"]),
            box=box.HEAVY,
            padding=(1, 2),
        )
        console.print(eq_panel)

        # Show format instructions
        console.print("[dim]Enter coefficients for each compound in order, space-separated.[/dim]")
        console.print("[dim]Use 1 for no coefficient change.[/dim]")
        console.print("[dim]'h'=hint, '?'=I don't know[/dim]")

        # List compounds in order
        compounds = reactants + products
        for i, compound in enumerate(compounds):
            console.print(f"[dim]  {i + 1}. {compound}[/dim]")

        hint_count = 0

        while True:
            answer = Prompt.ask(
                get_asi_prompt("equation", f"Enter {len(compounds)} coefficients"),
            )

            if not answer or not answer.strip():
                console.print("[yellow]Please enter coefficients[/yellow]")
                continue

            if is_dont_know(answer):
                return {
                    "dont_know": True,
                    "correct_coefficients": coefficients,
                    "compounds": compounds,
                    "hints_used": hint_count,
                }

            if answer.lower() == "h":
                hint_count += 1
                hint_text = self.hint(atom, hint_count)
                if hint_text:
                    console.print(f"[yellow]Hint {hint_count}:[/yellow] {hint_text}")
                else:
                    console.print("[dim]No more hints available[/dim]")
                continue

            try:
                user_coeffs = [int(x) for x in answer.replace(",", " ").split()]
                if len(user_coeffs) != len(compounds):
                    console.print(f"[yellow]Please enter exactly {len(compounds)} numbers[/yellow]")
                    continue
            except ValueError:
                console.print("[red]Invalid input. Use numbers only.[/red]")
                continue

            break

        # Map coefficients to compounds
        user_coefficients = {}
        for i, compound in enumerate(compounds):
            user_coefficients[compound] = user_coeffs[i]

        return {
            "user_coefficients": user_coefficients,
            "correct_coefficients": coefficients,
            "compounds": compounds,
            "user_input": answer,
            "hints_used": hint_count,
        }

    def check(self, atom: dict, answer: Any, console: Console | None = None) -> AnswerResult:
        """Check if user coefficients balance the equation."""
        if answer.get("skipped"):
            return AnswerResult(
                correct=True,
                feedback="Skipped - no equation available",
                user_answer="skipped",
                correct_answer="",
            )

        if answer.get("dont_know"):
            correct_coeffs = answer.get("correct_coefficients", {})
            compounds = answer.get("compounds", [])
            correct_str = self._format_balanced(compounds, correct_coeffs)
            return AnswerResult(
                correct=False,
                feedback="Let's learn this one!",
                user_answer="I don't know",
                correct_answer=correct_str,
                dont_know=True,
            )

        user_coefficients = answer.get("user_coefficients", {})
        correct_coefficients = answer.get("correct_coefficients", {})
        compounds = answer.get("compounds", [])
        user_input = answer.get("user_input", "")

        # Check each coefficient
        correct_count = 0
        for compound in compounds:
            user_val = user_coefficients.get(compound, 0)
            correct_val = correct_coefficients.get(compound, 1)
            if user_val == correct_val:
                correct_count += 1

        is_correct = correct_count == len(compounds)
        partial_score = correct_count / len(compounds) if compounds else 0

        if not is_correct and console:
            self._render_diff(compounds, user_coefficients, correct_coefficients, console)

        correct_str = self._format_balanced(compounds, correct_coefficients)

        return AnswerResult(
            correct=is_correct,
            feedback="Equation balanced!" if is_correct else f"Incorrect. {correct_count}/{len(compounds)} coefficients correct.",
            user_answer=user_input,
            correct_answer=correct_str,
            partial_score=partial_score,
        )

    def hint(self, atom: dict, attempt: int) -> str | None:
        """Progressive hints for equation balancing."""
        coefficients = atom.get("coefficients", {})
        reactants = atom.get("reactants", [])
        products = atom.get("products", [])
        compounds = reactants + products

        if not coefficients or not compounds:
            return None

        if attempt == 1:
            return "Start by counting atoms of each element on both sides"
        elif attempt == 2:
            return "Balance one element at a time, starting with metals if present"
        elif attempt == 3 and compounds:
            # Reveal first coefficient
            first = compounds[0]
            coeff = coefficients.get(first, 1)
            return f"The coefficient for {first} is {coeff}"
        elif attempt == 4 and len(compounds) > 1:
            # Reveal second coefficient
            second = compounds[1]
            coeff = coefficients.get(second, 1)
            return f"The coefficient for {second} is {coeff}"

        return None

    def _build_equation(self, reactants: list, products: list) -> str:
        """Build equation string from components."""
        left = " + ".join(reactants)
        right = " + ".join(products)
        return f"{left} → {right}"

    def _format_balanced(self, compounds: list, coefficients: dict) -> str:
        """Format the balanced equation."""
        parts = []
        for compound in compounds:
            coeff = coefficients.get(compound, 1)
            if coeff == 1:
                parts.append(compound)
            else:
                parts.append(f"{coeff}{compound}")
        return ", ".join(parts)

    def _render_diff(
        self,
        compounds: list,
        user_coefficients: dict,
        correct_coefficients: dict,
        console: Console,
    ) -> None:
        """Render visual diff between user and correct coefficients."""
        diff_table = Table(
            box=box.MINIMAL_HEAVY_HEAD,
            border_style=Style(color=CORTEX_THEME["error"]),
            show_header=True,
        )
        diff_table.add_column("")
        diff_table.add_column("Compound")
        diff_table.add_column("Your Coeff")
        diff_table.add_column("Correct")

        for compound in compounds:
            user_val = user_coefficients.get(compound, 0)
            correct_val = correct_coefficients.get(compound, 1)

            if user_val == correct_val:
                icon = "✓"
                style = STYLES["cortex_success"]
            else:
                icon = "✗"
                style = STYLES["cortex_error"]

            diff_table.add_row(
                Text(icon, style=style),
                compound,
                Text(str(user_val), style=style),
                str(correct_val),
            )

        console.print(Panel(
            diff_table,
            title="[bold red]COEFFICIENT ANALYSIS[/bold red]",
            border_style=Style(color=CORTEX_THEME["error"]),
            box=box.HEAVY,
        ))
