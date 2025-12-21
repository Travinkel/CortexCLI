"""
Faded Parsons Problem atom handler.

Hybrid of Parsons (reordering) + Cloze (fill-in-blanks).
User reorders scrambled lines AND fills in 1-2 blanks per line.
Supports partial credit for ordering and blank accuracy.
"""

import random
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

# Pattern to match blanks: ___ or ___1___ or {blank} or {1}
BLANK_PATTERN = re.compile(r"(___\d*___?|___|\{(?:blank|\d+)\})")


@register(AtomType.FADED_PARSONS)
class FadedParsonsHandler:
    """Handler for faded Parsons problem atoms (ordering + fill-in-blanks)."""

    def validate(self, atom: dict) -> bool:
        """Check if atom has required faded Parsons fields."""
        lines = atom.get("lines", [])
        blanks = atom.get("blanks", {})

        # Need at least 2 lines and at least 1 blank
        if len(lines) < 2:
            return False
        if not blanks:
            return False

        # Verify blanks reference valid positions
        return True

    def present(self, atom: dict, console: Console) -> None:
        """Display the faded Parsons problem context."""
        front = atom.get("front", "Arrange in correct order AND fill in the blanks:")

        panel = Panel(
            front,
            title="[bold cyan]FADED SEQUENCE CHALLENGE[/bold cyan]",
            border_style="cyan",
            box=box.HEAVY,
            padding=(1, 2),
        )
        console.print(panel)

    def get_input(self, atom: dict, console: Console) -> dict:
        """Display scrambled lines with blanks, get user ordering and blank fills."""
        lines = atom.get("lines", [])
        blanks = atom.get("blanks", {})

        if not lines:
            console.print("[yellow]No lines found[/yellow]")
            return {"skipped": True}

        # Preserve scrambled order across retries
        if "_scrambled" not in atom:
            scrambled = list(enumerate(lines))  # Keep original indices
            random.shuffle(scrambled)
            atom["_scrambled"] = scrambled
        scrambled = atom["_scrambled"]

        # Display scrambled blocks with blanks highlighted
        line_content = Text()
        for display_idx, (orig_idx, line) in enumerate(scrambled):
            line_content.append(f"  [{display_idx + 1}] ", style=STYLES["cortex_warning"])
            # Highlight blanks in the line
            highlighted = self._highlight_blanks(line)
            line_content.append(highlighted)
            line_content.append("\n")

        line_panel = Panel(
            line_content,
            title="[bold yellow][*] FADED SEQUENCE BLOCKS[/bold yellow]",
            border_style=Style(color=CORTEX_THEME["warning"]),
            box=box.HEAVY,
            padding=(1, 2),
        )
        console.print(line_panel)

        # Show blank hints
        blank_count = len(blanks)
        console.print(f"[dim]This problem has {blank_count} blank(s) to fill.[/dim]")
        console.print("[dim]'h'=hint, '?'=I don't know[/dim]")
        console.print("[dim italic]First enter the correct sequence, then fill in blanks.[/dim italic]")

        hint_count = 0

        # Step 1: Get ordering
        while True:
            seq = Prompt.ask(
                get_asi_prompt("faded_parsons", "Enter sequence (e.g., 3 1 2 4)"),
            )

            if not seq or not seq.strip():
                console.print("[yellow]Please enter a sequence[/yellow]")
                continue

            if is_dont_know(seq):
                return {
                    "dont_know": True,
                    "correct_order": lines,
                    "blanks": blanks,
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
                if len(indices) != len(lines):
                    console.print(f"[yellow]Please provide {len(lines)} numbers[/yellow]")
                    continue
                user_order = [scrambled[i][1] for i in indices if 0 <= i < len(scrambled)]
                user_orig_indices = [scrambled[i][0] for i in indices if 0 <= i < len(scrambled)]
            except (ValueError, IndexError):
                console.print("[red]Invalid sequence. Use numbers corresponding to the blocks.[/red]")
                continue

            break

        # Step 2: Get blank fills
        user_blanks = {}
        for blank_id, correct_value in blanks.items():
            while True:
                answer = Prompt.ask(
                    get_asi_prompt("faded_parsons", f"Fill blank {blank_id}"),
                )

                if is_dont_know(answer):
                    user_blanks[blank_id] = ""
                    break

                if answer.lower() == "h":
                    hint_count += 1
                    # Give a letter hint for this blank
                    if correct_value:
                        console.print(f"[yellow]Hint:[/yellow] Starts with '{correct_value[0]}'")
                    continue

                user_blanks[blank_id] = answer.strip()
                break

        return {
            "user_order": user_order,
            "correct_order": lines,
            "user_blanks": user_blanks,
            "correct_blanks": blanks,
            "user_input": seq,
            "hints_used": hint_count,
        }

    def check(self, atom: dict, answer: Any, console: Console | None = None) -> AnswerResult:
        """Check if user ordering and blanks are correct."""
        if answer.get("skipped"):
            return AnswerResult(
                correct=True,
                feedback="Skipped - no lines available",
                user_answer="skipped",
                correct_answer="",
            )

        if answer.get("dont_know"):
            correct_order = answer.get("correct_order", [])
            blanks = answer.get("blanks", {})
            correct_str = self._format_solution(correct_order, blanks)
            return AnswerResult(
                correct=False,
                feedback="Let's learn this one!",
                user_answer="I don't know",
                correct_answer=correct_str,
                dont_know=True,
            )

        user_order = answer.get("user_order", [])
        correct_order = answer.get("correct_order", [])
        user_blanks = answer.get("user_blanks", {})
        correct_blanks = answer.get("correct_blanks", {})
        user_input = answer.get("user_input", "")

        # Calculate ordering score
        order_correct = user_order == correct_order
        correct_positions = sum(
            1 for i, line in enumerate(user_order)
            if i < len(correct_order) and line == correct_order[i]
        )
        order_score = correct_positions / len(correct_order) if correct_order else 0

        # Calculate blanks score
        blanks_correct = 0
        for blank_id, correct_val in correct_blanks.items():
            user_val = user_blanks.get(blank_id, "")
            if user_val.lower().strip() == correct_val.lower().strip():
                blanks_correct += 1
        blanks_score = blanks_correct / len(correct_blanks) if correct_blanks else 1.0

        # Combined score: 60% ordering, 40% blanks
        partial_score = (order_score * 0.6) + (blanks_score * 0.4)
        is_correct = order_correct and blanks_correct == len(correct_blanks)

        if not is_correct and console:
            self._render_diff(user_order, correct_order, user_blanks, correct_blanks, console)

        correct_str = self._format_solution(correct_order, correct_blanks)

        feedback_parts = []
        if order_correct:
            feedback_parts.append("Sequence correct!")
        else:
            feedback_parts.append(f"Sequence: {correct_positions}/{len(correct_order)} in position")

        feedback_parts.append(f"Blanks: {blanks_correct}/{len(correct_blanks)} correct")

        return AnswerResult(
            correct=is_correct,
            feedback=" | ".join(feedback_parts) if not is_correct else "Perfect! Sequence and blanks all correct!",
            user_answer=user_input,
            correct_answer=correct_str,
            partial_score=partial_score,
        )

    def hint(self, atom: dict, attempt: int) -> str | None:
        """Progressive hints for faded Parsons problems."""
        lines = atom.get("lines", [])
        blanks = atom.get("blanks", {})

        if not lines:
            return None

        if attempt == 1:
            return f"The first line is: {self._mask_blanks(lines[0][:50])}..."
        elif attempt == 2:
            return f"The last line is: {self._mask_blanks(lines[-1][:50])}..."
        elif attempt == 3 and blanks:
            # Give first letter of first blank
            first_blank = list(blanks.values())[0]
            return f"The first blank starts with '{first_blank[0]}'"
        elif attempt == 4 and len(lines) > 2:
            mid = len(lines) // 2
            return f"Line {mid + 1} should be: {self._mask_blanks(lines[mid][:40])}..."

        return None

    def _highlight_blanks(self, line: str) -> Text:
        """Return a Text object with blanks highlighted."""
        text = Text()
        parts = BLANK_PATTERN.split(line)
        for part in parts:
            if BLANK_PATTERN.match(part):
                text.append(part, style="bold magenta")
            else:
                text.append(part, style=Style(color=CORTEX_THEME["white"]))
        return text

    def _mask_blanks(self, line: str) -> str:
        """Keep blanks visible but mask them as ___."""
        return BLANK_PATTERN.sub("___", line)

    def _format_solution(self, lines: list[str], blanks: dict) -> str:
        """Format the complete solution with blanks filled in."""
        result_lines = []
        # Sort blank IDs for consistent replacement order
        sorted_blanks = list(sorted(blanks.items(), key=lambda x: x[0]))
        blank_index = 0

        for line in lines:
            filled_line = line

            # First try to replace numbered blanks (___1___, ___2___, etc)
            for blank_id, value in sorted_blanks:
                filled_line = filled_line.replace(f"___{blank_id}___", f"[{value}]")

            # Replace remaining generic ___ with blanks in sequential order
            while "___" in filled_line and blank_index < len(sorted_blanks):
                _, value = sorted_blanks[blank_index]
                filled_line = filled_line.replace("___", f"[{value}]", 1)
                blank_index += 1

            result_lines.append(filled_line)
        return " -> ".join(result_lines)

    def _render_diff(
        self,
        user_order: list,
        correct_order: list,
        user_blanks: dict,
        correct_blanks: dict,
        console: Console,
    ) -> None:
        """Render visual diff for ordering and blanks."""
        diff_table = Table(
            box=box.MINIMAL_HEAVY_HEAD,
            border_style=Style(color=CORTEX_THEME["error"]),
            show_header=True,
        )
        diff_table.add_column("", width=2)
        diff_table.add_column("Your Sequence", overflow="fold")
        diff_table.add_column("Correct", overflow="fold")

        correct_set = set(correct_order)

        for i, user_line in enumerate(user_order):
            correct_line = correct_order[i] if i < len(correct_order) else ""

            if user_line == correct_line:
                icon = "✓"
                style = STYLES["cortex_success"]
            elif user_line in correct_set:
                icon = "•"
                style = STYLES["cortex_warning"]
            else:
                icon = "✗"
                style = STYLES["cortex_error"]

            diff_table.add_row(
                Text(icon, style=style),
                Text(user_line[:40] + "..." if len(user_line) > 40 else user_line, style=style),
                Text(correct_line[:40] + "..." if len(correct_line) > 40 else correct_line),
            )

        console.print(Panel(
            diff_table,
            title="[bold red]SEQUENCE ANALYSIS[/bold red]",
            border_style=Style(color=CORTEX_THEME["error"]),
            box=box.HEAVY,
        ))

        # Show blank analysis
        if correct_blanks:
            blank_table = Table(box=box.SIMPLE, show_header=True)
            blank_table.add_column("Blank")
            blank_table.add_column("Your Answer")
            blank_table.add_column("Correct")

            for blank_id, correct_val in correct_blanks.items():
                user_val = user_blanks.get(blank_id, "")
                is_match = user_val.lower().strip() == correct_val.lower().strip()
                style = STYLES["cortex_success"] if is_match else STYLES["cortex_error"]
                icon = "✓" if is_match else "✗"

                blank_table.add_row(
                    f"{icon} {blank_id}",
                    Text(user_val or "(empty)", style=style),
                    correct_val,
                )

            console.print(Panel(
                blank_table,
                title="[bold yellow]BLANK ANALYSIS[/bold yellow]",
                border_style="yellow",
                box=box.ROUNDED,
            ))
