"""
The Cortex: Main CLI for CCNA Learning.

A Rich terminal interface for interleaved spaced repetition study
using the generated CCNA learning atoms.

Commands:
- cortex study    - Start a study session
- cortex stats    - Show learning statistics
- cortex reset    - Clear review state
- cortex sync     - Reload atom files
"""
from __future__ import annotations

import sys
import time
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.prompt import Prompt, IntPrompt, Confirm
from rich.table import Table
from rich.text import Text
from rich.markdown import Markdown

from loguru import logger

from .atom_deck import AtomDeck, Atom
from .state_store import StateStore
from .scheduler import InterleaveScheduler, SM2Scheduler
from .telemetry import SessionTelemetry, FatigueDetector, FatigueLevel


# =============================================================================
# CLI Setup
# =============================================================================

app = typer.Typer(
    name="cortex",
    help="The Cortex: CCNA Learning CLI",
    no_args_is_help=True,
)
console = Console()


# =============================================================================
# Styling
# =============================================================================

STYLES = {
    "correct": "bold green",
    "incorrect": "bold red",
    "info": "bold cyan",
    "warning": "bold yellow",
    "dim": "dim",
    "atom_type": {
        "flashcard": "blue",
        "cloze": "magenta",
        "mcq": "green",
        "true_false": "yellow",
        "matching": "cyan",
        "parsons": "red",
        "numeric": "bright_blue",
    },
}


def style_atom_type(atom_type: str) -> str:
    """Get styled atom type string."""
    color = STYLES["atom_type"].get(atom_type, "white")
    return f"[{color}]{atom_type}[/{color}]"


# =============================================================================
# Display Helpers
# =============================================================================

def display_atom_front(atom: Atom, index: int, total: int) -> None:
    """Display the front of a card."""
    type_styled = style_atom_type(atom.atom_type)
    header = f"Card {index}/{total}  |  {type_styled}  |  Module {atom.module_number}"

    # Build front content
    content = atom.front

    # For MCQ, show options
    if atom.atom_type == "mcq" and atom.content_json:
        options = atom.content_json.get("options", [])
        if options:
            content += "\n\n"
            for i, opt in enumerate(options):
                content += f"  {chr(65 + i)}. {opt.get('text', '')}\n"

    panel = Panel(
        content,
        title=header,
        title_align="left",
        border_style="cyan",
        padding=(1, 2),
    )
    console.print(panel)


def display_atom_back(atom: Atom, is_correct: bool) -> None:
    """Display the back of a card with feedback."""
    style = STYLES["correct"] if is_correct else STYLES["incorrect"]
    icon = "[green]✓[/green]" if is_correct else "[red]✗[/red]"

    content = f"{icon} {atom.back}"

    # Show source reference
    if atom.source_refs:
        ref = atom.source_refs[0]
        section = ref.get("section_id", "")
        content += f"\n\n[dim]Source: Section {section}[/dim]"

    panel = Panel(
        content,
        border_style=style,
        padding=(1, 2),
    )
    console.print(panel)


def display_fatigue_warning(signal) -> bool:
    """
    Display fatigue warning and ask if user wants to continue.

    Returns:
        True to continue, False to end session
    """
    color = "yellow" if signal.level == FatigueLevel.MILD else "red"

    console.print()
    console.print(Panel(
        f"[{color}]{signal.recommendation}[/{color}]",
        title="[bold]Fatigue Detected[/bold]",
        border_style=color,
    ))

    if signal.should_end:
        console.print("\n[bold red]Consider ending this session.[/bold red]")
        return Confirm.ask("Continue anyway?", default=False)

    if signal.should_break:
        return Confirm.ask("Take a short break?", default=True)

    return True  # Mild fatigue - just inform


# =============================================================================
# Commands
# =============================================================================

@app.command()
def study(
    output_dir: Optional[Path] = typer.Option(
        None,
        "--dir", "-d",
        help="Directory with atom JSON files",
    ),
    new_limit: int = typer.Option(
        30,
        "--new", "-n",
        help="Maximum new cards per session",
    ),
    quality_threshold: float = typer.Option(
        85.0,
        "--quality", "-q",
        help="Minimum quality score for atoms",
    ),
) -> None:
    """
    Start an interactive study session.

    Loads atoms from JSON files and presents them using interleaved
    spaced repetition. Tracks progress in local SQLite database.
    """
    console.print("\n[bold cyan]The Cortex[/bold cyan] - CCNA Learning", style="bold")
    console.print("=" * 40)

    # Initialize components
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("Loading atoms...", total=None)

        deck = AtomDeck(
            output_dir=output_dir or Path("outputs"),
            quality_threshold=quality_threshold,
        )
        loaded = deck.load()

        if loaded == 0:
            console.print("\n[red]No atoms found![/red]")
            console.print(f"Looking in: {deck.output_dir.absolute()}")
            console.print("Run the atom factory first to generate atoms.")
            raise typer.Exit(1)

        progress.update(task, description=f"Loaded {loaded} atoms")

        store = StateStore()
        sm2 = SM2Scheduler()
        scheduler = InterleaveScheduler(deck, store, sm2)
        telemetry = SessionTelemetry()
        fatigue = FatigueDetector()

    # Show session preview
    session = scheduler.build_session()

    if session.total_cards == 0:
        console.print("\n[green]Nothing due for review![/green]")
        console.print("All caught up. Check back tomorrow.")
        raise typer.Exit(0)

    console.print(f"\n[bold]Session: {session.total_cards} cards[/bold]")
    console.print(f"  Due reviews: {len(session.due_atoms)}")
    console.print(f"  New cards: {len(session.new_atoms)}")
    console.print(f"  Estimated time: ~{session.estimated_minutes} min")
    console.print()

    if not Confirm.ask("Start session?", default=True):
        raise typer.Exit(0)

    # Start session
    session_id = store.start_session()
    queue = session.interleaved_queue
    completed = 0

    try:
        for i, atom in enumerate(queue, 1):
            console.clear()
            display_atom_front(atom, i, len(queue))

            # Wait for reveal
            start_time = time.time()
            Prompt.ask("\n[dim]Press Enter to reveal[/dim]")
            response_ms = int((time.time() - start_time) * 1000)

            # Show answer
            display_atom_back(atom, True)  # Placeholder, actual grading below

            # Get grade
            if atom.is_interactive:
                grade = _grade_interactive(atom)
            else:
                grade = _grade_recall()

            is_correct = grade >= 3

            # Update display with actual result
            console.print()
            if is_correct:
                console.print("[green]Correct![/green]")
            else:
                console.print("[red]Incorrect[/red]")

            # Record review
            scheduler.record_review(atom, grade, response_ms)
            telemetry.record(atom.id, grade, response_ms)
            completed += 1

            # Check fatigue
            signal = fatigue.detect(telemetry)
            if signal:
                if not display_fatigue_warning(signal):
                    console.print("\n[yellow]Ending session early.[/yellow]")
                    break

            # Next card prompt
            if i < len(queue):
                console.print()
                Prompt.ask("[dim]Press Enter for next card[/dim]")

    except KeyboardInterrupt:
        console.print("\n\n[yellow]Session interrupted.[/yellow]")

    # End session
    stats = telemetry.get_stats()
    store.end_session(
        session_id,
        atoms_reviewed=completed,
        accuracy=stats["accuracy_percent"] / 100,
    )

    # Show summary
    _display_session_summary(stats)


def _grade_interactive(atom: Atom) -> int:
    """Grade an interactive card (MCQ, true/false)."""
    if atom.atom_type == "mcq":
        correct_answer = atom.get_correct_answer()
        options = atom.get_options()

        user_input = Prompt.ask(
            "Your answer (A/B/C/D)",
            choices=["A", "B", "C", "D", "a", "b", "c", "d"][:len(options) * 2],
        ).upper()

        user_idx = ord(user_input) - ord("A")
        if user_idx < len(options):
            user_answer = options[user_idx].get("text", "")
            is_correct = user_answer == correct_answer
            return 5 if is_correct else 1

    elif atom.atom_type == "true_false":
        correct = atom.get_correct_answer()
        user_input = Prompt.ask("True or False?", choices=["t", "f", "true", "false"]).lower()
        user_answer = "true" if user_input in ["t", "true"] else "false"
        is_correct = user_answer == correct
        return 5 if is_correct else 1

    # Fallback to recall grading
    return _grade_recall()


def _grade_recall() -> int:
    """Grade a recall-based card."""
    console.print("\n[dim]Rate your recall:[/dim]")
    console.print("  5 = Perfect recall")
    console.print("  4 = Correct with hesitation")
    console.print("  3 = Correct with difficulty")
    console.print("  2 = Incorrect, but knew it")
    console.print("  1 = Incorrect, vaguely familiar")
    console.print("  0 = Complete blackout")

    return IntPrompt.ask("Grade", choices=["0", "1", "2", "3", "4", "5"])


def _display_session_summary(stats: dict) -> None:
    """Display end-of-session summary."""
    console.print("\n")
    console.print(Panel(
        f"[bold]Session Complete![/bold]\n\n"
        f"Duration: {stats['duration_minutes']:.1f} minutes\n"
        f"Cards reviewed: {stats['total_reviews']}\n"
        f"Accuracy: {stats['accuracy_percent']:.1f}%",
        title="Summary",
        border_style="green",
    ))


@app.command()
def stats() -> None:
    """Show learning statistics and progress."""
    store = StateStore()
    db_stats = store.get_stats()

    console.print("\n[bold cyan]Learning Statistics[/bold cyan]")
    console.print("=" * 40)

    table = Table(show_header=False, box=None)
    table.add_column("Metric", style="dim")
    table.add_column("Value", style="bold")

    table.add_row("Total atoms tracked", str(db_stats["total_atoms_tracked"]))
    table.add_row("Atoms due today", str(db_stats["atoms_due"]))
    table.add_row("Total reviews", str(db_stats["total_reviews"]))
    table.add_row("Avg grade (recent)", f"{db_stats['avg_grade_recent']:.2f}")
    table.add_row("Retention rate", f"{db_stats['retention_rate_percent']:.1f}%")
    table.add_row("Sessions completed", str(db_stats["sessions_completed"]))

    console.print(table)

    # Recent sessions
    sessions = store.get_session_history(limit=5)
    if sessions:
        console.print("\n[bold]Recent Sessions[/bold]")
        session_table = Table()
        session_table.add_column("Date")
        session_table.add_column("Cards")
        session_table.add_column("Accuracy")
        session_table.add_column("Fatigue")

        for s in sessions:
            date_str = s.started_at.strftime("%Y-%m-%d %H:%M") if s.started_at else "?"
            fatigue_icon = "[red]![/red]" if s.fatigue_detected else "[green]OK[/green]"
            session_table.add_row(
                date_str,
                str(s.atoms_reviewed),
                f"{s.accuracy * 100:.0f}%",
                fatigue_icon,
            )

        console.print(session_table)


@app.command()
def reset(
    module: Optional[int] = typer.Option(
        None,
        "--module", "-m",
        help="Reset only specific module",
    ),
    confirm: bool = typer.Option(
        False,
        "--yes", "-y",
        help="Skip confirmation",
    ),
) -> None:
    """Clear review state for a fresh start."""
    if module:
        msg = f"Reset review state for Module {module}?"
    else:
        msg = "Reset ALL review state? This cannot be undone!"

    if not confirm and not Confirm.ask(msg, default=False):
        raise typer.Exit(0)

    store = StateStore()
    count = store.reset(module_filter=module)

    if module:
        console.print(f"[green]Reset {count} atoms from Module {module}[/green]")
    else:
        console.print("[green]All review state has been reset.[/green]")


@app.command()
def sync(
    output_dir: Optional[Path] = typer.Option(
        None,
        "--dir", "-d",
        help="Directory with atom JSON files",
    ),
) -> None:
    """Reload atoms from JSON files."""
    deck = AtomDeck(output_dir=output_dir or Path("outputs"))
    count = deck.sync()

    console.print(f"[green]Synced {count} atoms from {len(deck._files_loaded)} files[/green]")

    # Show deck stats
    stats = deck.get_stats()
    console.print(f"\nModules: {list(stats['modules'].keys())}")
    console.print(f"Types: {list(stats['by_type'].keys())}")


@app.command()
def preview(
    limit: int = typer.Option(10, "--limit", "-l", help="Number of cards to preview"),
) -> None:
    """Preview upcoming study cards."""
    deck = AtomDeck(output_dir=Path("outputs"))
    deck.load()

    store = StateStore()
    scheduler = InterleaveScheduler(deck, store)

    preview_list = scheduler.get_queue_preview(limit=limit)

    console.print("\n[bold]Upcoming Cards[/bold]\n")

    table = Table()
    table.add_column("ID")
    table.add_column("Type")
    table.add_column("Status")

    for atom_id, atom_type, status in preview_list:
        type_styled = style_atom_type(atom_type)
        status_styled = "[yellow]due[/yellow]" if status == "due" else "[green]new[/green]"
        table.add_row(atom_id, type_styled, status_styled)

    console.print(table)


# =============================================================================
# Entry Point
# =============================================================================

def main() -> None:
    """CLI entry point."""
    # Configure logging
    logger.remove()
    logger.add(
        sys.stderr,
        level="WARNING",
        format="<level>{message}</level>",
    )

    app()


if __name__ == "__main__":
    main()
