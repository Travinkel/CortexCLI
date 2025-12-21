"""
SQL Query Builder atom handler.

User drags SQL clause blocks (SELECT, FROM, WHERE, etc.) to form a query.
Supports partial credit based on clause ordering and completeness.
"""

import random
from typing import Any

from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt
from rich.style import Style
from rich.syntax import Syntax
from rich.table import Table
from rich.text import Text

from src.delivery.cortex_visuals import (
    CORTEX_THEME,
    STYLES,
    get_asi_prompt,
)

from . import AtomType, register
from .base import AnswerResult, is_dont_know


@register(AtomType.SQL_QUERY_BUILDER)
class SqlQueryBuilderHandler:
    """Handler for SQL query builder atoms (clause ordering)."""

    # Standard SQL clause order
    CLAUSE_ORDER = [
        "SELECT", "FROM", "JOIN", "LEFT JOIN", "RIGHT JOIN", "INNER JOIN",
        "WHERE", "GROUP BY", "HAVING", "ORDER BY", "LIMIT", "OFFSET"
    ]

    def validate(self, atom: dict) -> bool:
        """Check if atom has required SQL builder fields."""
        clauses = atom.get("clauses", [])

        # Need at least SELECT and FROM
        if len(clauses) < 2:
            return False

        # Should have clause content
        for clause in clauses:
            if not isinstance(clause, dict):
                return False
            if "type" not in clause or "content" not in clause:
                return False

        return True

    def present(self, atom: dict, console: Console) -> None:
        """Display the SQL query builder context."""
        front = atom.get("front", "Build the SQL query by ordering these clauses:")

        panel = Panel(
            front,
            title="[bold cyan]SQL QUERY BUILDER[/bold cyan]",
            border_style="cyan",
            box=box.HEAVY,
            padding=(1, 2),
        )
        console.print(panel)

    def get_input(self, atom: dict, console: Console) -> dict:
        """Display scrambled SQL clauses and get user ordering."""
        clauses = atom.get("clauses", [])

        if not clauses:
            console.print("[yellow]No clauses found[/yellow]")
            return {"skipped": True}

        # Get correct order based on SQL syntax
        correct_order = self._sort_clauses(clauses)

        # Preserve scrambled order across retries
        if "_scrambled" not in atom:
            scrambled = clauses.copy()
            random.shuffle(scrambled)
            atom["_scrambled"] = scrambled
            atom["_correct_order"] = correct_order
        scrambled = atom["_scrambled"]

        # Display scrambled clauses with syntax highlighting
        clause_content = Text()
        for i, clause in enumerate(scrambled):
            clause_type = clause.get("type", "")
            content = clause.get("content", "")
            clause_content.append(f"  [{i + 1}] ", style=STYLES["cortex_warning"])
            clause_content.append(f"{clause_type} ", style="bold blue")
            clause_content.append(f"{content}\n", style=Style(color=CORTEX_THEME["white"]))

        clause_panel = Panel(
            clause_content,
            title="[bold yellow][*] SQL CLAUSE BLOCKS[/bold yellow]",
            border_style=Style(color=CORTEX_THEME["warning"]),
            box=box.HEAVY,
            padding=(1, 2),
        )
        console.print(clause_panel)
        console.print("[dim]'h'=hint, '?'=I don't know, or enter sequence (e.g., 2 1 3)[/dim]")
        console.print("[dim italic]Order clauses to form a valid SQL query[/dim italic]")

        hint_count = 0

        while True:
            seq = Prompt.ask(
                get_asi_prompt("sql_builder", "Enter clause order"),
            )

            if not seq or not seq.strip():
                console.print("[yellow]Please enter a sequence[/yellow]")
                continue

            if is_dont_know(seq):
                return {
                    "dont_know": True,
                    "correct_order": correct_order,
                    "hints_used": hint_count,
                }

            if seq.lower() == "h":
                hint_count += 1
                hint_text = self.hint(atom, hint_count)
                if hint_text:
                    console.print(f"[yellow]Hint {hint_count}:[/yellow] {hint_text}")
                else:
                    console.print("[dim]No more hints available[/dim]")
                continue

            try:
                indices = [int(x) - 1 for x in seq.replace(",", " ").split()]
                user_order = [scrambled[i] for i in indices if 0 <= i < len(scrambled)]
            except (ValueError, IndexError):
                console.print("[red]Invalid sequence. Use numbers corresponding to the clauses.[/red]")
                continue

            break

        return {
            "user_order": user_order,
            "correct_order": correct_order,
            "scrambled": scrambled,
            "user_input": seq,
            "hints_used": hint_count,
        }

    def check(self, atom: dict, answer: Any, console: Console | None = None) -> AnswerResult:
        """Check if user ordering forms valid SQL."""
        if answer.get("skipped"):
            return AnswerResult(
                correct=True,
                feedback="Skipped - no clauses available",
                user_answer="skipped",
                correct_answer="",
            )

        if answer.get("dont_know"):
            correct_order = answer.get("correct_order", [])
            correct_str = self._format_query(correct_order)
            return AnswerResult(
                correct=False,
                feedback="Let's learn this one!",
                user_answer="I don't know",
                correct_answer=correct_str,
                dont_know=True,
            )

        user_order = answer.get("user_order", [])
        correct_order = answer.get("correct_order", [])
        user_input = answer.get("user_input", "")

        # Compare clause types and content
        user_query = self._format_query(user_order)
        correct_query = self._format_query(correct_order)

        is_correct = user_query.upper() == correct_query.upper()

        # Calculate partial credit based on clause positions
        correct_positions = 0
        for i, clause in enumerate(user_order):
            if i < len(correct_order):
                if (clause.get("type") == correct_order[i].get("type") and
                    clause.get("content") == correct_order[i].get("content")):
                    correct_positions += 1

        partial_score = correct_positions / len(correct_order) if correct_order else 0

        if not is_correct and console:
            self._render_diff(user_order, correct_order, console)

        return AnswerResult(
            correct=is_correct,
            feedback="Valid SQL query!" if is_correct else f"Incorrect ordering. {correct_positions}/{len(correct_order)} clauses in position.",
            user_answer=user_input,
            correct_answer=correct_query,
            partial_score=partial_score,
        )

    def hint(self, atom: dict, attempt: int) -> str | None:
        """Progressive hints for SQL query building."""
        clauses = atom.get("clauses", [])
        if not clauses:
            return None

        correct_order = self._sort_clauses(clauses)

        if attempt == 1:
            return "SQL queries always start with SELECT"
        elif attempt == 2:
            return "SELECT is followed by FROM to specify the table"
        elif attempt == 3:
            first_clause = correct_order[0]
            return f"First clause: {first_clause['type']} {first_clause['content'][:30]}..."
        elif attempt == 4 and len(correct_order) > 2:
            last_clause = correct_order[-1]
            return f"Last clause: {last_clause['type']} {last_clause['content'][:30]}..."

        return None

    def _sort_clauses(self, clauses: list) -> list:
        """Sort clauses into correct SQL order."""
        def clause_priority(clause):
            clause_type = clause.get("type", "").upper()
            for i, known_type in enumerate(self.CLAUSE_ORDER):
                if clause_type.startswith(known_type):
                    return i
            return len(self.CLAUSE_ORDER)  # Unknown clauses go last

        return sorted(clauses, key=clause_priority)

    def _format_query(self, clauses: list) -> str:
        """Format clauses into a SQL query string."""
        parts = []
        for clause in clauses:
            clause_type = clause.get("type", "")
            content = clause.get("content", "")
            parts.append(f"{clause_type} {content}")
        return "\n".join(parts)

    def _render_diff(
        self,
        user_order: list,
        correct_order: list,
        console: Console,
    ) -> None:
        """Render visual diff between user and correct SQL."""
        # Show user's query
        user_query = self._format_query(user_order)
        user_syntax = Syntax(user_query, "sql", theme="monokai", line_numbers=False)

        console.print(Panel(
            user_syntax,
            title="[bold red]YOUR QUERY[/bold red]",
            border_style=Style(color=CORTEX_THEME["error"]),
            box=box.HEAVY,
        ))

        # Show correct query
        correct_query = self._format_query(correct_order)
        correct_syntax = Syntax(correct_query, "sql", theme="monokai", line_numbers=False)

        console.print(Panel(
            correct_syntax,
            title="[bold green]CORRECT QUERY[/bold green]",
            border_style=Style(color=CORTEX_THEME["success"]),
            box=box.HEAVY,
        ))

        # Show clause comparison
        diff_table = Table(box=box.SIMPLE, show_header=True)
        diff_table.add_column("")
        diff_table.add_column("Position")
        diff_table.add_column("Your Clause")
        diff_table.add_column("Should Be")

        max_len = max(len(user_order), len(correct_order))
        for i in range(max_len):
            user_clause = user_order[i] if i < len(user_order) else {}
            correct_clause = correct_order[i] if i < len(correct_order) else {}

            user_str = f"{user_clause.get('type', '')} {user_clause.get('content', '')}"
            correct_str = f"{correct_clause.get('type', '')} {correct_clause.get('content', '')}"

            if user_str.strip() == correct_str.strip():
                icon = "✓"
                style = STYLES["cortex_success"]
            else:
                icon = "✗"
                style = STYLES["cortex_error"]

            diff_table.add_row(
                Text(icon, style=style),
                str(i + 1),
                Text(user_str[:35], style=style),
                correct_str[:35],
            )

        console.print(Panel(
            diff_table,
            title="[bold yellow]CLAUSE ANALYSIS[/bold yellow]",
            border_style="yellow",
            box=box.ROUNDED,
        ))
