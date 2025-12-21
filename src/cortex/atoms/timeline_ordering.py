"""
Timeline Ordering atom handler.

User orders historical events into chronological sequence.
Supports partial credit based on correctly positioned events.
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


@register(AtomType.TIMELINE_ORDERING)
class TimelineOrderingHandler:
    """Handler for timeline ordering atoms (chronological sequencing)."""

    def validate(self, atom: dict) -> bool:
        """Check if atom has required timeline fields."""
        events = atom.get("events", [])

        # Need at least 2 events with year/date info
        if len(events) < 2:
            return False

        # Each event should have a year or date field
        for event in events:
            if not isinstance(event, dict):
                return False
            if "year" not in event and "date" not in event:
                return False
            if "event" not in event and "name" not in event:
                return False

        return True

    def present(self, atom: dict, console: Console) -> None:
        """Display the timeline ordering context."""
        front = atom.get("front", "Arrange these events in chronological order:")

        panel = Panel(
            front,
            title="[bold cyan]TIMELINE CHALLENGE[/bold cyan]",
            border_style="cyan",
            box=box.HEAVY,
            padding=(1, 2),
        )
        console.print(panel)

    def get_input(self, atom: dict, console: Console) -> dict:
        """Display scrambled events and get user ordering."""
        events = atom.get("events", [])

        if not events:
            console.print("[yellow]No events found[/yellow]")
            return {"skipped": True}

        # Sort events by year/date to get correct order
        correct_order = sorted(events, key=lambda e: e.get("year", e.get("date", 0)))

        # Preserve scrambled order across retries
        if "_scrambled" not in atom:
            scrambled = events.copy()
            random.shuffle(scrambled)
            atom["_scrambled"] = scrambled
            atom["_correct_order"] = correct_order
        scrambled = atom["_scrambled"]

        # Display scrambled events (without showing years)
        event_content = Text()
        for i, event in enumerate(scrambled):
            event_name = event.get("event", event.get("name", "Unknown"))
            event_content.append(f"  [{i + 1}] ", style=STYLES["cortex_warning"])
            event_content.append(f"{event_name}\n", style=Style(color=CORTEX_THEME["white"]))

        event_panel = Panel(
            event_content,
            title="[bold yellow][*] HISTORICAL EVENTS[/bold yellow]",
            border_style=Style(color=CORTEX_THEME["warning"]),
            box=box.HEAVY,
            padding=(1, 2),
        )
        console.print(event_panel)
        console.print("[dim]'h'=hint, '?'=I don't know, or enter sequence (e.g., 3 1 2 4)[/dim]")
        console.print("[dim italic]Order from EARLIEST to MOST RECENT[/dim italic]")

        hint_count = 0

        while True:
            seq = Prompt.ask(
                get_asi_prompt("timeline", "(earliest to most recent)"),
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
                console.print("[red]Invalid sequence. Use numbers corresponding to the events.[/red]")
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
        """Check if user ordering matches chronological sequence."""
        if answer.get("skipped"):
            return AnswerResult(
                correct=True,
                feedback="Skipped - no events available",
                user_answer="skipped",
                correct_answer="",
            )

        if answer.get("dont_know"):
            correct_order = answer.get("correct_order", [])
            correct_str = self._format_timeline(correct_order)
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

        # Compare by event name/description
        user_events = [e.get("event", e.get("name")) for e in user_order]
        correct_events = [e.get("event", e.get("name")) for e in correct_order]

        is_correct = user_events == correct_events

        # Calculate partial credit
        correct_positions = sum(
            1 for i, e in enumerate(user_events)
            if i < len(correct_events) and e == correct_events[i]
        )
        partial_score = correct_positions / len(correct_events) if correct_events else 0

        if not is_correct and console:
            self._render_diff(user_order, correct_order, console)

        correct_str = self._format_timeline(correct_order)

        return AnswerResult(
            correct=is_correct,
            feedback="Correct chronological order!" if is_correct else f"Incorrect. {correct_positions}/{len(correct_events)} in correct position.",
            user_answer=user_input,
            correct_answer=correct_str,
            partial_score=partial_score,
        )

    def hint(self, atom: dict, attempt: int) -> str | None:
        """Progressive hints for timeline ordering."""
        events = atom.get("events", [])
        if not events:
            return None

        # Get correct chronological order
        correct_order = sorted(events, key=lambda e: e.get("year", e.get("date", 0)))

        if attempt == 1:
            first = correct_order[0]
            event_name = first.get("event", first.get("name"))
            year = first.get("year", first.get("date"))
            return f"The earliest event ({year}): {event_name[:40]}..."
        elif attempt == 2:
            last = correct_order[-1]
            event_name = last.get("event", last.get("name"))
            year = last.get("year", last.get("date"))
            return f"The most recent event ({year}): {event_name[:40]}..."
        elif attempt == 3 and len(correct_order) > 2:
            mid = len(correct_order) // 2
            middle = correct_order[mid]
            event_name = middle.get("event", middle.get("name"))
            year = middle.get("year", middle.get("date"))
            return f"Event #{mid + 1} ({year}): {event_name[:35]}..."

        return None

    def _format_timeline(self, events: list) -> str:
        """Format events as a timeline string."""
        parts = []
        for event in events:
            year = event.get("year", event.get("date", "?"))
            name = event.get("event", event.get("name"))
            parts.append(f"{year}: {name}")
        return " -> ".join(parts)

    def _render_diff(
        self,
        user_order: list,
        correct_order: list,
        console: Console,
    ) -> None:
        """Render visual diff between user and correct timeline."""
        diff_table = Table(
            box=box.MINIMAL_HEAVY_HEAD,
            border_style=Style(color=CORTEX_THEME["error"]),
            show_header=True,
        )
        diff_table.add_column("", width=2)
        diff_table.add_column("Your Order", overflow="fold")
        diff_table.add_column("Correct Order", overflow="fold")

        correct_events = [e.get("event", e.get("name")) for e in correct_order]
        correct_set = set(correct_events)

        max_len = max(len(user_order), len(correct_order))
        for i in range(max_len):
            user_event = user_order[i] if i < len(user_order) else {}
            correct_event = correct_order[i] if i < len(correct_order) else {}

            user_name = user_event.get("event", user_event.get("name", ""))
            correct_name = correct_event.get("event", correct_event.get("name", ""))
            correct_year = correct_event.get("year", correct_event.get("date", ""))

            if user_name == correct_name:
                icon = "✓"
                style = STYLES["cortex_success"]
            elif user_name in correct_set:
                icon = "•"
                style = STYLES["cortex_warning"]
            else:
                icon = "✗"
                style = STYLES["cortex_error"]

            diff_table.add_row(
                Text(icon, style=style),
                Text(user_name[:35] + "..." if len(user_name) > 35 else user_name, style=style),
                f"{correct_year}: {correct_name[:30]}..." if len(correct_name) > 30 else f"{correct_year}: {correct_name}",
            )

        console.print(Panel(
            diff_table,
            title="[bold red]TIMELINE ANALYSIS[/bold red]",
            border_style=Style(color=CORTEX_THEME["error"]),
            box=box.HEAVY,
        ))
