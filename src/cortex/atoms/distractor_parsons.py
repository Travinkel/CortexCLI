"""
Distractor Parsons Problem atom handler.

Parsons problem with distractor lines that must be discarded.
User reorders correct lines AND identifies/discards fake lines.
Supports partial credit for ordering and distractor identification.
"""

import random
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


@register(AtomType.DISTRACTOR_PARSONS)
class DistractorParsonsHandler:
    """Handler for distractor Parsons problem atoms (ordering + discard fakes)."""

    def validate(self, atom: dict) -> bool:
        """Check if atom has required distractor Parsons fields."""
        correct_lines = atom.get("correct_lines", [])
        distractors = atom.get("distractors", [])

        # Need at least 2 correct lines and at least 1 distractor
        if len(correct_lines) < 2:
            return False
        if len(distractors) < 1:
            return False

        return True

    def present(self, atom: dict, console: Console) -> None:
        """Display the distractor Parsons problem context."""
        front = atom.get("front", "Arrange in correct order, but DISCARD the fake lines:")

        panel = Panel(
            front,
            title="[bold cyan]DISTRACTOR CHALLENGE[/bold cyan]",
            border_style="cyan",
            box=box.HEAVY,
            padding=(1, 2),
        )
        console.print(panel)

    def get_input(self, atom: dict, console: Console) -> dict:
        """Display all lines (shuffled) and get user selection/ordering."""
        correct_lines = atom.get("correct_lines", [])
        distractors = atom.get("distractors", [])

        if not correct_lines:
            console.print("[yellow]No lines found[/yellow]")
            return {"skipped": True}

        # Combine and shuffle all lines, preserving origin
        if "_scrambled" not in atom:
            all_lines = [(line, True) for line in correct_lines] + [
                (line, False) for line in distractors
            ]
            random.shuffle(all_lines)
            atom["_scrambled"] = all_lines
        scrambled = atom["_scrambled"]

        # Display all blocks
        line_content = Text()
        for i, (line, _is_correct) in enumerate(scrambled):
            line_content.append(f"  [{i + 1}] ", style=STYLES["cortex_warning"])
            line_content.append(f"{line}\n", style=Style(color=CORTEX_THEME["white"]))

        line_panel = Panel(
            line_content,
            title="[bold yellow][*] SEQUENCE BLOCKS (some are FAKE!)[/bold yellow]",
            border_style=Style(color=CORTEX_THEME["warning"]),
            box=box.HEAVY,
            padding=(1, 2),
        )
        console.print(line_panel)

        distractor_count = len(distractors)
        correct_count = len(correct_lines)
        console.print(f"[dim]{distractor_count} line(s) are FAKE and should be discarded.[/dim]")
        console.print(f"[dim]Select only the {correct_count} correct lines in the right order.[/dim]")
        console.print("[dim]'h'=hint, '?'=I don't know[/dim]")

        hint_count = 0

        while True:
            seq = Prompt.ask(
                get_asi_prompt("distractor_parsons", f"Enter {correct_count} numbers (e.g., 3 1 4)"),
            )

            if not seq or not seq.strip():
                console.print("[yellow]Please enter a sequence[/yellow]")
                continue

            if is_dont_know(seq):
                return {
                    "dont_know": True,
                    "correct_order": correct_lines,
                    "distractors": distractors,
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
                selected_lines = [scrambled[i][0] for i in indices if 0 <= i < len(scrambled)]
                selected_origins = [scrambled[i][1] for i in indices if 0 <= i < len(scrambled)]
            except (ValueError, IndexError):
                console.print("[red]Invalid sequence. Use numbers corresponding to the blocks.[/red]")
                continue

            break

        # Calculate which distractors were correctly discarded
        selected_set = set(indices)
        all_indices = set(range(len(scrambled)))
        discarded_indices = all_indices - selected_set
        discarded_lines = [scrambled[i][0] for i in discarded_indices]

        return {
            "user_order": selected_lines,
            "correct_order": correct_lines,
            "selected_origins": selected_origins,
            "discarded_lines": discarded_lines,
            "distractors": distractors,
            "scrambled": scrambled,
            "user_input": seq,
            "hints_used": hint_count,
        }

    def check(self, atom: dict, answer: Any, console: Console | None = None) -> AnswerResult:
        """Check if user correctly ordered valid lines and discarded distractors."""
        if answer.get("skipped"):
            return AnswerResult(
                correct=True,
                feedback="Skipped - no lines available",
                user_answer="skipped",
                correct_answer="",
            )

        if answer.get("dont_know"):
            correct_order = answer.get("correct_order", [])
            distractors = answer.get("distractors", [])
            correct_str = " -> ".join(correct_order)
            distractor_str = ", ".join(distractors)
            return AnswerResult(
                correct=False,
                feedback="Let's learn this one!",
                user_answer="I don't know",
                correct_answer=f"Order: {correct_str}\nDiscard: {distractor_str}",
                dont_know=True,
            )

        user_order = answer.get("user_order", [])
        correct_order = answer.get("correct_order", [])
        discarded_lines = answer.get("discarded_lines", [])
        distractors = answer.get("distractors", [])
        user_input = answer.get("user_input", "")

        # Check ordering accuracy
        order_correct = user_order == correct_order
        correct_positions = sum(
            1 for i, line in enumerate(user_order)
            if i < len(correct_order) and line == correct_order[i]
        )
        order_score = correct_positions / len(correct_order) if correct_order else 0

        # Check distractor identification
        correctly_discarded = sum(1 for d in discarded_lines if d in distractors)
        wrongly_discarded = sum(1 for d in discarded_lines if d in correct_order)
        distractors_included = sum(1 for line in user_order if line in distractors)

        distractor_score = 0.0
        if distractors:
            # Reward for correctly discarding distractors, penalize for wrong discards
            distractor_score = (correctly_discarded - wrongly_discarded) / len(distractors)
            distractor_score = max(0.0, distractor_score)

        # Combined score: 60% ordering, 40% distractor handling
        partial_score = (order_score * 0.6) + (distractor_score * 0.4)
        is_correct = order_correct and distractors_included == 0 and correctly_discarded == len(distractors)

        if not is_correct and console:
            self._render_diff(user_order, correct_order, discarded_lines, distractors, console)

        correct_str = " -> ".join(correct_order)

        feedback_parts = []
        if order_correct:
            feedback_parts.append("Sequence correct!")
        else:
            feedback_parts.append(f"Sequence: {correct_positions}/{len(correct_order)} in position")

        if distractors_included > 0:
            feedback_parts.append(f"Included {distractors_included} fake line(s)")
        if wrongly_discarded > 0:
            feedback_parts.append(f"Discarded {wrongly_discarded} valid line(s)")
        if correctly_discarded == len(distractors):
            feedback_parts.append("All fakes discarded!")

        return AnswerResult(
            correct=is_correct,
            feedback=" | ".join(feedback_parts) if not is_correct else "Perfect! Correct sequence with all fakes discarded!",
            user_answer=user_input,
            correct_answer=correct_str,
            partial_score=partial_score,
        )

    def hint(self, atom: dict, attempt: int) -> str | None:
        """Progressive hints for distractor Parsons problems."""
        correct_lines = atom.get("correct_lines", [])
        distractors = atom.get("distractors", [])

        if not correct_lines:
            return None

        if attempt == 1:
            return f"The first correct step is: {correct_lines[0][:40]}..."
        elif attempt == 2:
            return f"The last correct step is: {correct_lines[-1][:40]}..."
        elif attempt == 3 and distractors:
            # Reveal one distractor
            return f"One fake line to discard: '{distractors[0][:40]}...'"
        elif attempt == 4 and len(distractors) > 1:
            return f"Another fake line: '{distractors[1][:40]}...'"
        elif attempt == 5 and len(correct_lines) > 2:
            mid = len(correct_lines) // 2
            return f"Step {mid + 1} should be: {correct_lines[mid][:35]}..."

        return None

    def _render_diff(
        self,
        user_order: list,
        correct_order: list,
        discarded_lines: list,
        distractors: list,
        console: Console,
    ) -> None:
        """Render visual diff for ordering and distractor handling."""
        # Ordering analysis
        diff_table = Table(
            box=box.MINIMAL_HEAVY_HEAD,
            border_style=Style(color=CORTEX_THEME["error"]),
            show_header=True,
        )
        diff_table.add_column("", width=2)
        diff_table.add_column("Your Selection", overflow="fold")
        diff_table.add_column("Status", overflow="fold")

        correct_set = set(correct_order)
        distractor_set = set(distractors)

        for i, line in enumerate(user_order):
            if line in distractor_set:
                icon = "✗"
                style = STYLES["cortex_error"]
                status = "FAKE (should discard)"
            elif i < len(correct_order) and line == correct_order[i]:
                icon = "✓"
                style = STYLES["cortex_success"]
                status = "Correct position"
            elif line in correct_set:
                icon = "•"
                style = STYLES["cortex_warning"]
                status = "Wrong position"
            else:
                icon = "?"
                style = STYLES["cortex_error"]
                status = "Unknown"

            diff_table.add_row(
                Text(icon, style=style),
                Text(line[:45] + "..." if len(line) > 45 else line, style=style),
                status,
            )

        console.print(Panel(
            diff_table,
            title="[bold red]SELECTION ANALYSIS[/bold red]",
            border_style=Style(color=CORTEX_THEME["error"]),
            box=box.HEAVY,
        ))

        # Discarded lines analysis
        if discarded_lines:
            discard_table = Table(box=box.SIMPLE, show_header=True)
            discard_table.add_column("")
            discard_table.add_column("Discarded Line")
            discard_table.add_column("Verdict")

            for line in discarded_lines:
                if line in distractor_set:
                    icon = "✓"
                    style = STYLES["cortex_success"]
                    verdict = "Correctly discarded (was fake)"
                else:
                    icon = "✗"
                    style = STYLES["cortex_error"]
                    verdict = "Should NOT have discarded!"

                discard_table.add_row(
                    Text(icon, style=style),
                    Text(line[:40] + "..." if len(line) > 40 else line, style=style),
                    verdict,
                )

            console.print(Panel(
                discard_table,
                title="[bold yellow]DISCARDED LINES[/bold yellow]",
                border_style="yellow",
                box=box.ROUNDED,
            ))
