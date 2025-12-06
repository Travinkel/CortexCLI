"""
⚠️  DEPRECATED - Use `nls cortex start --mode war` instead.

The War Room: Aggressive Mastery Study Interface.

This module is DEPRECATED. All functionality has been consolidated into
the Cortex CLI with the unified StudyService backend.

Migration:
    OLD: nls war study --modules 11,12,13
    NEW: nls cortex start --mode war --modules 11,12,13

    OLD: nls war study --cram
    NEW: nls cortex start --mode war

    OLD: nls war stats
    NEW: nls cortex stats

The new Cortex CLI provides:
- Unified StudyService backend (all interactions update FSRS)
- ASI-themed "Digital Neocortex" visual style
- Google Calendar integration
- Same War Mode aggressive mastery logic

This file will be removed in a future release.
"""
from __future__ import annotations

import warnings
warnings.warn(
    "war_room.py is deprecated. Use 'nls cortex start --mode war' instead.",
    DeprecationWarning,
    stacklevel=2
)

import json
import random
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, List, Dict, Any, Set
from uuid import UUID

import typer
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt, IntPrompt
from rich.table import Table
from rich.text import Text
from rich.rule import Rule
from loguru import logger
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from config import get_settings
from src.db.database import session_scope
from src.db.models import CleanAtom, CleanModule
from src.db.models.quiz import QuizQuestion


# =============================================================================
# CLI Setup
# =============================================================================

app = typer.Typer(
    name="war",
    help="The War Room: Aggressive mastery study interface",
    no_args_is_help=True,
)
console = Console()

# Session log file (decoupled from DB for speed)
SESSION_LOG_PATH = Path("session_logs.jsonl")

# High priority modules for cram mode
CRAM_MODULES = [11, 12, 13, 14, 15, 16, 17]

# Session duration in minutes
DEFAULT_SESSION_MINUTES = 60


# =============================================================================
# Color Styles
# =============================================================================

STYLES = {
    "correct": "bold green",
    "incorrect": "bold red",
    "question": "bold cyan",
    "answer": "bold white",
    "timer": "bold yellow",
    "escalation": "bold magenta",
    "dim": "dim",
    "type_flashcard": "blue",
    "type_mcq": "green",
    "type_parsons": "magenta",
    "type_numeric": "bright_blue",
    "type_cloze": "cyan",
    "type_true_false": "bright_yellow",
    "type_matching": "bright_cyan",
    "type_calculation": "bright_blue",
}


def get_type_style(atom_type: str) -> str:
    """Get color style for atom type."""
    return STYLES.get(f"type_{atom_type}", "white")


# =============================================================================
# Data Models
# =============================================================================

@dataclass
class StudyAtom:
    """Lightweight wrapper for study atoms."""
    atom_id: UUID
    atom_type: str
    front: str
    back: str
    module_number: Optional[int]
    quiz_content: Dict[str, Any] = field(default_factory=dict)
    source_fact_basis: Optional[str] = None
    card_id: Optional[str] = None
    fail_count: int = 0

    @property
    def is_mcq(self) -> bool:
        return self.atom_type == "mcq"

    @property
    def is_parsons(self) -> bool:
        return self.atom_type == "parsons"

    @property
    def is_numeric(self) -> bool:
        return self.atom_type in ("numeric", "calculation")

    @property
    def is_matching(self) -> bool:
        return self.atom_type == "matching"

    @property
    def is_flashcard(self) -> bool:
        return self.atom_type in ("flashcard", "cloze", "true_false")


@dataclass
class WarSession:
    """
    Session state for War Room study.

    Tracks:
    - 60-minute countdown timer
    - Escalation Queue (items failed > 1 time)
    - Session statistics
    """
    start_time: datetime = field(default_factory=datetime.now)
    duration_minutes: int = DEFAULT_SESSION_MINUTES

    # Queues
    main_queue: List[StudyAtom] = field(default_factory=list)
    escalation_queue: List[StudyAtom] = field(default_factory=list)

    # Stats
    total_reviewed: int = 0
    correct_count: int = 0
    incorrect_count: int = 0
    escalated_count: int = 0

    # Tracking
    seen_atoms: Set[UUID] = field(default_factory=set)
    session_id: str = field(default_factory=lambda: datetime.now().strftime("%Y%m%d_%H%M%S"))

    @property
    def elapsed_seconds(self) -> float:
        return (datetime.now() - self.start_time).total_seconds()

    @property
    def elapsed_minutes(self) -> float:
        return self.elapsed_seconds / 60

    @property
    def remaining_seconds(self) -> float:
        return max(0, (self.duration_minutes * 60) - self.elapsed_seconds)

    @property
    def remaining_minutes(self) -> float:
        return self.remaining_seconds / 60

    @property
    def is_expired(self) -> bool:
        return self.remaining_seconds <= 0

    @property
    def accuracy(self) -> float:
        if self.total_reviewed == 0:
            return 0.0
        return (self.correct_count / self.total_reviewed) * 100

    def format_remaining(self) -> str:
        """Format remaining time as MM:SS."""
        mins = int(self.remaining_minutes)
        secs = int(self.remaining_seconds % 60)
        return f"{mins:02d}:{secs:02d}"

    def get_next_atom(self) -> Optional[StudyAtom]:
        """
        Get next atom to study.

        Priority:
        1. Escalation queue items (failed > 1 time)
        2. Main queue items
        """
        # Check escalation queue first (50% chance if both have items)
        if self.escalation_queue and (not self.main_queue or random.random() < 0.5):
            return self.escalation_queue.pop(0)

        if self.main_queue:
            return self.main_queue.pop(0)

        # If main queue empty, drain escalation queue
        if self.escalation_queue:
            return self.escalation_queue.pop(0)

        return None

    def record_result(self, atom: StudyAtom, passed: bool) -> None:
        """Record study result and handle escalation."""
        self.total_reviewed += 1
        self.seen_atoms.add(atom.atom_id)

        if passed:
            self.correct_count += 1
        else:
            self.incorrect_count += 1
            atom.fail_count += 1

            # Escalate if failed more than once
            if atom.fail_count > 1:
                self.escalation_queue.append(atom)
                self.escalated_count += 1
            elif atom.fail_count == 1:
                # Re-add to main queue for one more try
                self.main_queue.append(atom)


# =============================================================================
# Telemetry Logger
# =============================================================================

class TelemetryLogger:
    """Fast, file-based telemetry logger."""

    def __init__(self, log_path: Path = SESSION_LOG_PATH, session_id: Optional[str] = None):
        self.log_path = log_path
        self.session_id = session_id or datetime.now().strftime("%Y%m%d_%H%M%S")
        self.records: List[dict] = []

    def record(
        self,
        atom_id: UUID,
        atom_type: str,
        module: Optional[int],
        passed: bool,
        response_ms: int,
        fail_count: int = 0,
        escalated: bool = False,
    ) -> None:
        """Record a single interaction."""
        entry = {
            "session_id": self.session_id,
            "timestamp": datetime.now().isoformat(),
            "atom_id": str(atom_id),
            "atom_type": atom_type,
            "module": module,
            "passed": passed,
            "response_ms": response_ms,
            "fail_count": fail_count,
            "escalated": escalated,
        }
        self.records.append(entry)

        # Append to file immediately (for crash safety)
        with self.log_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")

    def get_session_stats(self) -> dict:
        """Get stats for current session."""
        if not self.records:
            return {"total": 0, "passed": 0, "failed": 0, "accuracy": 0.0, "escalated": 0}

        total = len(self.records)
        passed = sum(1 for r in self.records if r["passed"])
        failed = total - passed
        escalated = sum(1 for r in self.records if r.get("escalated", False))

        return {
            "total": total,
            "passed": passed,
            "failed": failed,
            "accuracy": (passed / total * 100) if total > 0 else 0.0,
            "escalated": escalated,
        }


# =============================================================================
# Database Queries
# =============================================================================

def parse_modules(modules_str: str) -> List[int]:
    """Parse comma-separated module numbers."""
    modules = []
    for part in modules_str.split(","):
        try:
            mod = int(part.strip())
            if 1 <= mod <= 17:
                modules.append(mod)
        except ValueError:
            pass
    return modules


def fetch_atoms_by_modules(
    db: Session,
    module_numbers: List[int],
    limit: int = 200,
) -> List[StudyAtom]:
    """Fetch atoms for multiple modules."""
    # Find modules
    modules = db.query(CleanModule).filter(
        CleanModule.week_order.in_(module_numbers)
    ).all()

    if not modules:
        return []

    module_ids = [m.id for m in modules]
    module_map = {m.id: m.week_order for m in modules}

    # Fetch atoms with quiz questions
    stmt = (
        select(CleanAtom)
        .where(CleanAtom.module_id.in_(module_ids))
        .options(joinedload(CleanAtom.quiz_question))
    )

    all_atoms = db.execute(stmt).scalars().unique().all()

    # Random sample if too many
    if len(all_atoms) > limit:
        all_atoms = random.sample(list(all_atoms), limit)

    result = []
    for a in all_atoms:
        quiz_content = {}
        source_fact_basis = None

        if a.quiz_question:
            quiz_content = a.quiz_question.question_content or {}
            # Extract source_fact_basis from explanations if available
            explanations = quiz_content.get("explanations", {})
            if explanations:
                # Get explanation for correct answer
                correct_idx = quiz_content.get("correct_index", 0)
                source_fact_basis = explanations.get(str(correct_idx), "")

        result.append(StudyAtom(
            atom_id=a.id,
            atom_type=a.atom_type,
            front=a.front,
            back=a.back or "",
            module_number=module_map.get(a.module_id),
            quiz_content=quiz_content,
            source_fact_basis=source_fact_basis,
            card_id=a.card_id,
        ))

    return result


def fetch_cram_atoms(db: Session, limit: int = 200) -> List[StudyAtom]:
    """Fetch random atoms from high-priority modules (11-17)."""
    return fetch_atoms_by_modules(db, CRAM_MODULES, limit)


# =============================================================================
# Display Functions
# =============================================================================

def display_timer_bar(session: WarSession) -> None:
    """Display session timer and stats bar."""
    remaining = session.format_remaining()
    accuracy = session.accuracy
    escalated = len(session.escalation_queue)

    # Color based on time remaining
    if session.remaining_minutes < 5:
        time_color = "red"
    elif session.remaining_minutes < 15:
        time_color = "yellow"
    else:
        time_color = "green"

    # Build status line
    status = (
        f"[{time_color}]TIME: {remaining}[/{time_color}] | "
        f"Done: {session.total_reviewed} | "
        f"Accuracy: {accuracy:.0f}% | "
    )

    if escalated > 0:
        status += f"[magenta]ESCALATED: {escalated}[/magenta]"
    else:
        status += "[dim]Escalation: 0[/dim]"

    console.print(status)


def display_flashcard_front(atom: StudyAtom, session: WarSession) -> None:
    """Display flashcard front with timer."""
    display_timer_bar(session)
    console.print()

    type_color = get_type_style(atom.atom_type)
    header = f"[{type_color}]{atom.atom_type.upper()}[/{type_color}]"

    if atom.module_number:
        header += f" | Module {atom.module_number}"

    if atom.fail_count > 0:
        header += f" | [magenta]RETRY #{atom.fail_count}[/magenta]"

    panel = Panel(
        atom.front,
        title=header,
        title_align="left",
        border_style="cyan",
        padding=(0, 1),
    )
    console.print(panel)


def display_feedback(atom: StudyAtom, passed: bool) -> None:
    """Display immediate feedback with explanation."""
    style = STYLES["correct"] if passed else STYLES["incorrect"]
    icon = "[green]PASS[/green]" if passed else "[red]FAIL[/red]"

    content = Text()
    content.append(f"{icon}\n\n")

    # Show the answer
    if atom.back:
        content.append(atom.back)

    # Show source_fact_basis if available and failed
    if not passed and atom.source_fact_basis:
        content.append(f"\n\n[bold yellow]Why?[/bold yellow]\n")
        content.append(atom.source_fact_basis)

    # Show explanations for MCQ
    if atom.is_mcq and atom.quiz_content.get("explanations"):
        content.append(f"\n\n[bold]Explanation:[/bold]\n")
        correct_idx = atom.quiz_content.get("correct_index", 0)
        explanation = atom.quiz_content["explanations"].get(str(correct_idx), "")
        if explanation:
            content.append(explanation)

    panel = Panel(
        content,
        border_style=style,
        padding=(0, 1),
    )
    console.print(panel)


def display_mcq(atom: StudyAtom, session: WarSession) -> Optional[str]:
    """Display MCQ question and get user input."""
    display_timer_bar(session)
    console.print()

    type_color = get_type_style("mcq")
    header = f"[{type_color}]MCQ[/{type_color}]"

    if atom.module_number:
        header += f" | Module {atom.module_number}"

    if atom.fail_count > 0:
        header += f" | [magenta]RETRY #{atom.fail_count}[/magenta]"

    content = Text()
    content.append(atom.front + "\n\n")

    options = atom.quiz_content.get("options", [])

    for i, opt in enumerate(options):
        letter = chr(65 + i)  # A, B, C, D...
        if isinstance(opt, dict):
            opt_text = opt.get("text", str(opt))
        else:
            opt_text = str(opt)
        content.append(f"  {letter}. {opt_text}\n")

    panel = Panel(
        content,
        title=header,
        title_align="left",
        border_style="cyan",
        padding=(0, 1),
    )
    console.print(panel)

    # Get user input
    valid_choices = [chr(65 + i) for i in range(len(options))]

    user_input = Prompt.ask(
        "Your answer",
        default="",
    ).strip().upper()

    if user_input and user_input in valid_choices:
        return user_input
    return None


def check_mcq_answer(atom: StudyAtom, user_answer: str) -> bool:
    """Check if MCQ answer is correct."""
    correct_index = atom.quiz_content.get("correct_index", 0)
    user_index = ord(user_answer) - ord("A")
    return user_index == correct_index


def display_mcq_result(atom: StudyAtom, passed: bool, user_answer: str) -> None:
    """Display MCQ result with correct answer and explanation."""
    style = STYLES["correct"] if passed else STYLES["incorrect"]
    icon = "[green]CORRECT[/green]" if passed else "[red]INCORRECT[/red]"

    correct_index = atom.quiz_content.get("correct_index", 0)
    correct_letter = chr(65 + correct_index)

    options = atom.quiz_content.get("options", [])
    if correct_index < len(options):
        opt = options[correct_index]
        if isinstance(opt, dict):
            correct_text = opt.get("text", "")
        else:
            correct_text = str(opt)
    else:
        correct_text = ""

    content = Text()
    content.append(f"{icon}\n\n")
    content.append(f"Correct Answer: [bold]{correct_letter}. {correct_text}[/bold]\n")

    # Show explanation
    explanations = atom.quiz_content.get("explanations", {})
    if explanations:
        exp = explanations.get(str(correct_index), "")
        if exp:
            content.append(f"\n[yellow]Explanation:[/yellow]\n{exp}")

    # Show source_fact_basis if failed
    if not passed and atom.source_fact_basis:
        content.append(f"\n\n[bold yellow]Source:[/bold yellow]\n{atom.source_fact_basis}")

    panel = Panel(
        content,
        border_style=style,
        padding=(0, 1),
    )
    console.print(panel)


def display_parsons(atom: StudyAtom, session: WarSession) -> Optional[str]:
    """
    Display Parsons problem with block sorting interaction.

    Shows scrambled blocks and asks user to enter correct order.
    """
    display_timer_bar(session)
    console.print()

    type_color = get_type_style("parsons")
    header = f"[{type_color}]PARSONS[/{type_color}] - Arrange in correct order"

    if atom.module_number:
        header += f" | Module {atom.module_number}"

    if atom.fail_count > 0:
        header += f" | [magenta]RETRY #{atom.fail_count}[/magenta]"

    content = Text()
    content.append(atom.front + "\n\n")
    content.append("[dim]Arrange these blocks in the correct order:[/dim]\n\n")

    # Get blocks from quiz content or parse from back
    blocks = atom.quiz_content.get("items", [])

    if not blocks and atom.back:
        # Parse blocks from back (split by newline)
        blocks = [b.strip() for b in atom.back.split("\n") if b.strip()]

    # Create scrambled mapping
    original_indices = list(range(len(blocks)))
    scrambled_indices = original_indices.copy()
    random.shuffle(scrambled_indices)

    # Store for verification
    atom.quiz_content["_scrambled_map"] = scrambled_indices

    for i, scrambled_idx in enumerate(scrambled_indices, 1):
        if scrambled_idx < len(blocks):
            content.append(f"  [{i}] {blocks[scrambled_idx]}\n")

    panel = Panel(
        content,
        title=header,
        title_align="left",
        border_style="cyan",
        padding=(0, 1),
    )
    console.print(panel)

    # Get user input (e.g., "3,1,2,4" or "3 1 2 4")
    console.print("\n[dim]Enter the correct order (e.g., 1,3,2,4 or 1 3 2 4):[/dim]")
    user_input = Prompt.ask("Order", default="").strip()

    return user_input


def check_parsons_answer(atom: StudyAtom, user_input: str) -> bool:
    """Check if Parsons order is correct."""
    # Get correct order
    correct_order = atom.quiz_content.get("correct_order")
    scrambled_map = atom.quiz_content.get("_scrambled_map", [])

    if not scrambled_map:
        return False

    # Parse user input (accept comma or space separated)
    user_order = []
    for part in user_input.replace(",", " ").split():
        try:
            idx = int(part.strip()) - 1  # Convert to 0-indexed
            user_order.append(idx)
        except ValueError:
            continue

    if len(user_order) != len(scrambled_map):
        return False

    # Map user's display order back to original indices
    user_original_order = [scrambled_map[i] for i in user_order if i < len(scrambled_map)]

    # Check if user's order matches correct order (0, 1, 2, 3...)
    if correct_order:
        return user_original_order == correct_order
    else:
        # If no explicit correct_order, assume original order is correct
        return user_original_order == list(range(len(scrambled_map)))


def display_parsons_answer(atom: StudyAtom, passed: bool) -> None:
    """Display correct Parsons order with explanation."""
    style = STYLES["correct"] if passed else STYLES["incorrect"]
    icon = "[green]CORRECT[/green]" if passed else "[red]INCORRECT[/red]"

    content = Text()
    content.append(f"{icon}\n\n")
    content.append("[bold]Correct Order:[/bold]\n\n")

    blocks = atom.quiz_content.get("items", [])
    correct_order = atom.quiz_content.get("correct_order", list(range(len(blocks))))

    if blocks:
        for i, idx in enumerate(correct_order, 1):
            if idx < len(blocks):
                content.append(f"  {i}. {blocks[idx]}\n")
    else:
        # Fallback to back content
        for i, line in enumerate(atom.back.split("\n"), 1):
            if line.strip():
                content.append(f"  {i}. {line.strip()}\n")

    # Show source_fact_basis if failed
    if not passed and atom.source_fact_basis:
        content.append(f"\n\n[bold yellow]Why this order?[/bold yellow]\n{atom.source_fact_basis}")

    panel = Panel(
        content,
        border_style=style,
        padding=(0, 1),
    )
    console.print(panel)


def display_numeric(atom: StudyAtom, session: WarSession) -> Optional[str]:
    """
    Display numeric/calculation question with math input.
    """
    display_timer_bar(session)
    console.print()

    type_color = get_type_style("numeric")
    header = f"[{type_color}]NUMERIC[/{type_color}] - Calculate the answer"

    if atom.module_number:
        header += f" | Module {atom.module_number}"

    if atom.fail_count > 0:
        header += f" | [magenta]RETRY #{atom.fail_count}[/magenta]"

    panel = Panel(
        atom.front,
        title=header,
        title_align="left",
        border_style="cyan",
        padding=(0, 1),
    )
    console.print(panel)

    # Get numeric input
    console.print("\n[dim]Enter your answer (number or expression):[/dim]")
    user_input = Prompt.ask("Answer", default="").strip()

    return user_input


def check_numeric_answer(atom: StudyAtom, user_input: str) -> bool:
    """Check if numeric answer is correct (with tolerance)."""
    correct_answers = atom.quiz_content.get("correct_answers", [])

    if not correct_answers:
        # Try to extract from back
        try:
            # Look for numbers in the back
            import re
            numbers = re.findall(r"[-+]?\d*\.?\d+", atom.back)
            if numbers:
                correct_answers = numbers
        except:
            pass

    if not correct_answers:
        return False

    # Try to parse user input
    try:
        user_value = float(user_input.replace(",", ""))
    except ValueError:
        return False

    # Check against correct answers with tolerance
    for correct in correct_answers:
        try:
            correct_value = float(str(correct).replace(",", ""))
            # Allow 1% tolerance for floating point
            if abs(user_value - correct_value) <= abs(correct_value * 0.01) + 0.001:
                return True
        except ValueError:
            if str(correct).strip() == user_input.strip():
                return True

    return False


def display_numeric_answer(atom: StudyAtom, passed: bool) -> None:
    """Display numeric answer with calculation steps."""
    style = STYLES["correct"] if passed else STYLES["incorrect"]
    icon = "[green]CORRECT[/green]" if passed else "[red]INCORRECT[/red]"

    content = Text()
    content.append(f"{icon}\n\n")
    content.append("[bold]Solution:[/bold]\n\n")
    content.append(atom.back)

    # Show calculation steps if available
    steps = atom.quiz_content.get("calculation_steps", [])
    if steps:
        content.append("\n\n[bold yellow]Steps:[/bold yellow]\n")
        for i, step in enumerate(steps, 1):
            content.append(f"  {i}. {step}\n")

    # Show source_fact_basis if failed
    if not passed and atom.source_fact_basis:
        content.append(f"\n\n[bold yellow]Reference:[/bold yellow]\n{atom.source_fact_basis}")

    panel = Panel(
        content,
        border_style=style,
        padding=(0, 1),
    )
    console.print(panel)


def display_matching(atom: StudyAtom, session: WarSession) -> Optional[str]:
    """Display matching problem."""
    display_timer_bar(session)
    console.print()

    type_color = get_type_style("matching")
    header = f"[{type_color}]MATCHING[/{type_color}] - Match left to right"

    if atom.module_number:
        header += f" | Module {atom.module_number}"

    content = Text()
    content.append(atom.front + "\n\n")

    pairs = atom.quiz_content.get("pairs", [])

    # Scramble right side
    left_items = [p.get("left", "") for p in pairs]
    right_items = [p.get("right", "") for p in pairs]

    scrambled_right = right_items.copy()
    random.shuffle(scrambled_right)

    # Store for verification
    atom.quiz_content["_scrambled_right"] = scrambled_right

    console.print("[dim]Left Column:[/dim]")
    for i, item in enumerate(left_items, 1):
        content.append(f"  {i}. {item}\n")

    content.append("\n[dim]Right Column (scrambled):[/dim]\n")
    for i, item in enumerate(scrambled_right):
        letter = chr(65 + i)
        content.append(f"  {letter}. {item}\n")

    panel = Panel(
        content,
        title=header,
        title_align="left",
        border_style="cyan",
        padding=(0, 1),
    )
    console.print(panel)

    console.print("\n[dim]Enter matches (e.g., 1A,2C,3B or 1A 2C 3B):[/dim]")
    user_input = Prompt.ask("Matches", default="").strip()

    return user_input


# =============================================================================
# Study Loop
# =============================================================================

def run_war_session(session: WarSession) -> dict:
    """Run the War Room study loop with timer and escalation."""
    if not session.main_queue:
        console.print("[yellow]No atoms to study![/yellow]")
        return {"total": 0, "passed": 0, "failed": 0}

    telemetry = TelemetryLogger(session_id=session.session_id)

    console.print(f"\n[bold cyan]WAR ROOM[/bold cyan] - {len(session.main_queue)} cards")
    console.print(f"[bold yellow]Session Timer: {session.duration_minutes} minutes[/bold yellow]")
    console.print("[dim]Items failed > 1x will ESCALATE for re-study[/dim]")
    console.print("[dim]P=Pass | F=Fail | Q=Quit[/dim]\n")

    time.sleep(1)  # Brief pause before starting

    try:
        while not session.is_expired:
            atom = session.get_next_atom()

            if atom is None:
                console.print("\n[green]All cards completed![/green]")
                break

            start_time = datetime.now()
            console.clear()

            # Handle by atom type
            if atom.is_mcq:
                user_answer = display_mcq(atom, session)

                if user_answer is None:
                    console.print("[yellow]Invalid input, marked as fail[/yellow]")
                    passed = False
                else:
                    passed = check_mcq_answer(atom, user_answer)

                response_ms = int((datetime.now() - start_time).total_seconds() * 1000)
                display_mcq_result(atom, passed, user_answer or "")

            elif atom.is_parsons:
                user_input = display_parsons(atom, session)

                if not user_input:
                    passed = False
                else:
                    passed = check_parsons_answer(atom, user_input)

                response_ms = int((datetime.now() - start_time).total_seconds() * 1000)
                display_parsons_answer(atom, passed)

            elif atom.is_numeric:
                user_input = display_numeric(atom, session)

                if not user_input:
                    passed = False
                else:
                    passed = check_numeric_answer(atom, user_input)

                response_ms = int((datetime.now() - start_time).total_seconds() * 1000)
                display_numeric_answer(atom, passed)

            elif atom.is_matching:
                user_input = display_matching(atom, session)
                # Matching is self-graded for now
                response_ms = int((datetime.now() - start_time).total_seconds() * 1000)
                result = Prompt.ask("Did you get it right? [P]ass/[F]ail", default="f")
                passed = result.lower().startswith("p")
                display_feedback(atom, passed)

            else:
                # Standard flashcard
                display_flashcard_front(atom, session)
                Prompt.ask("[dim]Press Enter to reveal[/dim]")
                response_ms = int((datetime.now() - start_time).total_seconds() * 1000)

                result = Prompt.ask("[P]ass/[F]ail/[Q]uit", default="f")

                if result.lower().startswith("q"):
                    console.print("\n[yellow]Session ended by user.[/yellow]")
                    break

                passed = result.lower().startswith("p")
                display_feedback(atom, passed)

            # Record result and handle escalation
            session.record_result(atom, passed)

            # Record telemetry
            telemetry.record(
                atom_id=atom.atom_id,
                atom_type=atom.atom_type,
                module=atom.module_number,
                passed=passed,
                response_ms=response_ms,
                fail_count=atom.fail_count,
                escalated=atom.fail_count > 1,
            )

            # Show escalation notice
            if not passed and atom.fail_count == 1:
                console.print("\n[yellow]Card will return for retry.[/yellow]")
            elif not passed and atom.fail_count > 1:
                console.print(f"\n[magenta]ESCALATED! Card added to priority queue.[/magenta]")

            # Brief pause between cards
            if not session.is_expired:
                Prompt.ask("[dim]Press Enter for next card[/dim]")

    except KeyboardInterrupt:
        console.print("\n\n[yellow]Session interrupted.[/yellow]")

    # Check if timer expired
    if session.is_expired:
        console.print("\n[bold yellow]TIME'S UP![/bold yellow]")

    return telemetry.get_session_stats()


def display_session_summary(session: WarSession, stats: dict) -> None:
    """Display comprehensive end-of-session summary."""
    total = stats.get("total", session.total_reviewed)
    if total == 0:
        return

    passed = stats.get("passed", session.correct_count)
    failed = stats.get("failed", session.incorrect_count)
    accuracy = stats.get("accuracy", session.accuracy)
    escalated = stats.get("escalated", session.escalated_count)

    # Color based on accuracy
    if accuracy >= 80:
        style = "green"
    elif accuracy >= 60:
        style = "yellow"
    else:
        style = "red"

    content = f"""[bold]Session Complete![/bold]

Duration: {session.elapsed_minutes:.1f} minutes
Cards Reviewed: {total}

[green]Passed: {passed}[/green]
[red]Failed: {failed}[/red]
[magenta]Escalated (failed 2+): {escalated}[/magenta]

Accuracy: [{style}]{accuracy:.1f}%[/{style}]"""

    # Add remaining escalation queue info
    remaining_escalated = len(session.escalation_queue)
    if remaining_escalated > 0:
        content += f"\n\n[yellow]Still in escalation queue: {remaining_escalated} cards[/yellow]"
        content += "\n[dim]Consider running another session![/dim]"

    panel = Panel(
        content,
        title="[bold]WAR ROOM SUMMARY[/bold]",
        border_style=style,
        padding=(1, 2),
    )
    console.print("\n")
    console.print(panel)


# =============================================================================
# Commands
# =============================================================================

@app.command("study")
def study(
    modules: Optional[str] = typer.Option(
        None,
        "--modules", "-m",
        help="Comma-separated module numbers (e.g., 11,12,13)",
    ),
    cram: bool = typer.Option(
        False,
        "--cram", "-c",
        help="War Mode: modules 11-17 (high priority)",
    ),
    limit: int = typer.Option(
        100,
        "--limit", "-l",
        help="Maximum number of cards",
    ),
    duration: int = typer.Option(
        DEFAULT_SESSION_MINUTES,
        "--duration", "-d",
        help="Session duration in minutes",
    ),
) -> None:
    """
    Start an aggressive mastery study session.

    Features:
    - 60-minute countdown timer (configurable)
    - Escalation queue for items failed > 1 time
    - Immediate feedback with explanations
    - Specialized UI for Parsons and Numeric problems

    Examples:
        nls war study --modules 11,12,13    # Focus on modules 11-13
        nls war study --cram                # War Mode (modules 11-17)
        nls war study --cram -d 30          # 30-minute cram session
    """
    # Parse module numbers
    if modules:
        module_list = parse_modules(modules)
        if not module_list:
            console.print(f"[red]Invalid modules: {modules}[/red]")
            console.print("[dim]Format: 11,12,13 or 11 12 13[/dim]")
            raise typer.Exit(1)
        mode = f"Modules {','.join(str(m) for m in module_list)}"
    elif cram:
        module_list = CRAM_MODULES
        mode = "CRAM MODE (Modules 11-17)"
    else:
        # Default to cram mode
        module_list = CRAM_MODULES
        mode = "CRAM MODE (Modules 11-17)"

    # Fetch atoms
    console.print("[dim]Loading atoms from database...[/dim]")

    try:
        with session_scope() as db:
            atoms = fetch_atoms_by_modules(db, module_list, limit=limit)

            if not atoms:
                console.print("[yellow]No atoms found![/yellow]")
                console.print("[dim]Make sure the database is populated.[/dim]")
                raise typer.Exit(1)

            console.print(f"[green]Loaded {len(atoms)} atoms[/green] - {mode}")

            # Shuffle for variety
            random.shuffle(atoms)

            # Create session
            session = WarSession(
                duration_minutes=duration,
                main_queue=atoms,
            )

            # Run study session
            stats = run_war_session(session)

            # Show summary
            display_session_summary(session, stats)

    except Exception as e:
        logger.exception("Error in war room session")
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1)


@app.command("stats")
def show_stats() -> None:
    """Show War Room session statistics from logs."""
    if not SESSION_LOG_PATH.exists():
        console.print("[yellow]No session logs found.[/yellow]")
        console.print(f"[dim]Logs will be saved to: {SESSION_LOG_PATH}[/dim]")
        return

    # Parse log file
    sessions: Dict[str, List[dict]] = {}

    with SESSION_LOG_PATH.open("r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                try:
                    entry = json.loads(line)
                    session_id = entry.get("session_id", "unknown")
                    if session_id not in sessions:
                        sessions[session_id] = []
                    sessions[session_id].append(entry)
                except json.JSONDecodeError:
                    continue

    if not sessions:
        console.print("[yellow]No valid session data found.[/yellow]")
        return

    console.print(f"\n[bold]War Room Session History[/bold] ({len(sessions)} sessions)\n")

    # Create table
    table = Table()
    table.add_column("Session", style="dim")
    table.add_column("Date/Time", style="cyan")
    table.add_column("Cards", justify="right")
    table.add_column("Accuracy", justify="right")
    table.add_column("Escalated", justify="right", style="magenta")

    # Show recent sessions
    for session_id, records in sorted(sessions.items(), reverse=True)[:10]:
        total = len(records)
        passed = sum(1 for r in records if r.get("passed"))
        accuracy = (passed / total * 100) if total > 0 else 0
        escalated = sum(1 for r in records if r.get("escalated", False))

        # Get first timestamp
        first_ts = records[0].get("timestamp", "")[:16] if records else "?"

        color = "green" if accuracy >= 80 else "yellow" if accuracy >= 60 else "red"

        table.add_row(
            session_id[:8] + "...",
            first_ts,
            str(total),
            f"[{color}]{accuracy:.1f}%[/{color}]",
            str(escalated) if escalated > 0 else "-",
        )

    console.print(table)

    # Show overall stats
    all_records = [r for records in sessions.values() for r in records]
    total_all = len(all_records)
    passed_all = sum(1 for r in all_records if r.get("passed"))
    escalated_all = sum(1 for r in all_records if r.get("escalated", False))

    console.print(f"\n[bold]All-Time Stats:[/bold]")
    console.print(f"  Total cards reviewed: {total_all}")
    console.print(f"  Overall accuracy: {(passed_all/total_all*100) if total_all else 0:.1f}%")
    console.print(f"  Total escalations: {escalated_all}")


# =============================================================================
# Entry Point
# =============================================================================

def main() -> None:
    """CLI entry point."""
    # Configure logging (minimal for speed)
    logger.remove()
    logger.add(sys.stderr, level="ERROR")

    app()


if __name__ == "__main__":
    main()
