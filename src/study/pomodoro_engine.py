"""
Pomodoro Session Engine for Interleaved Learning.

Orchestrates study sessions that alternate between:
- Anki reviews (flashcard + cloze via external app)
- In-app quizzes (MCQ, True/False, Matching, Parsons)

This creates a rich, multi-modal learning experience that builds
knowledge to expert level through varied practice types.

Session Flow:
1. Plan session (e.g., 2 hours = 4 pomodoros)
2. Each pomodoro:
   - Anki block (10-15 min): "Go do your due reviews in Anki"
   - Quiz block (10-15 min): In-app MCQ, T/F, Matching, Parsons
3. 5 min break between pomodoros
4. Summary and mastery update
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from uuid import UUID, uuid4

from loguru import logger
from rich import print as rprint
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm, Prompt
from rich.text import Text
from sqlalchemy import text

from src.db.database import session_scope
from src.study.quiz_engine import AtomType, QuizEngine

console = Console()


class BlockType(str, Enum):
    """Type of study block within a pomodoro."""

    ANKI = "anki"
    QUIZ = "quiz"
    BREAK = "break"


@dataclass
class PomodoroBlock:
    """A single block within a pomodoro session."""

    block_type: BlockType
    duration_minutes: int
    focus_section: str | None = None
    atom_types: list[AtomType] = field(default_factory=list)
    completed: bool = False
    cards_done: int = 0
    correct: int = 0
    incorrect: int = 0
    # Per-type quiz counts for accurate tracking
    quiz_type_counts: dict = field(
        default_factory=lambda: {
            "mcq": 0,
            "true_false": 0,
            "matching": 0,
            "parsons": 0,
        }
    )


@dataclass
class PomodoroSession:
    """A full pomodoro study session."""

    id: UUID = field(default_factory=uuid4)
    user_id: str = "default"
    planned_hours: float = 1.0
    pomodoros: list[list[PomodoroBlock]] = field(default_factory=list)
    current_pomodoro: int = 0
    current_block: int = 0
    started_at: datetime | None = None
    ended_at: datetime | None = None

    # Totals
    total_anki_cards: int = 0
    total_quiz_correct: int = 0
    total_quiz_incorrect: int = 0

    # Focus
    focus_module: int | None = None
    focus_section: str | None = None


class PomodoroEngine:
    """
    Engine for running interleaved Pomodoro study sessions.

    Alternates between:
    - Anki blocks: prompts user to do flashcard/cloze reviews
    - Quiz blocks: presents MCQ, T/F, Matching, Parsons in-app
    """

    def __init__(self):
        self.quiz_engine = QuizEngine()
        self.current_session: PomodoroSession | None = None

    def plan_session(
        self,
        hours: float,
        focus_module: int | None = None,
        focus_section: str | None = None,
    ) -> PomodoroSession:
        """
        Plan a new study session.

        Args:
            hours: Total study hours (e.g., 2.0)
            focus_module: Optional module number to focus on
            focus_section: Optional section to focus on

        Returns:
            PomodoroSession with planned blocks
        """
        session = PomodoroSession(
            planned_hours=hours,
            focus_module=focus_module,
            focus_section=focus_section,
        )

        # Calculate pomodoros (25 min work + 5 min break = 30 min)
        total_minutes = int(hours * 60)
        num_pomodoros = max(1, total_minutes // 30)

        for pomo_num in range(num_pomodoros):
            blocks = []

            # Anki block (12 min) - flashcard/cloze reviews
            blocks.append(
                PomodoroBlock(
                    block_type=BlockType.ANKI,
                    duration_minutes=12,
                    focus_section=focus_section,
                )
            )

            # Quiz block (13 min) - MCQ, T/F, Matching, Parsons
            # Vary the quiz types across pomodoros
            quiz_types = self._get_quiz_types_for_pomodoro(pomo_num)
            blocks.append(
                PomodoroBlock(
                    block_type=BlockType.QUIZ,
                    duration_minutes=13,
                    focus_section=focus_section,
                    atom_types=quiz_types,
                )
            )

            # Break (5 min) - except for last pomodoro
            if pomo_num < num_pomodoros - 1:
                blocks.append(
                    PomodoroBlock(
                        block_type=BlockType.BREAK,
                        duration_minutes=5,
                    )
                )

            session.pomodoros.append(blocks)

        self.current_session = session
        return session

    def _get_quiz_types_for_pomodoro(self, pomo_num: int) -> list[AtomType]:
        """Get quiz types for a specific pomodoro, rotating through types."""
        patterns = [
            [AtomType.MCQ, AtomType.TRUE_FALSE],  # Pomo 1: Quick recall
            [AtomType.TRUE_FALSE, AtomType.MCQ],  # Pomo 2: Mix it up
            [AtomType.MCQ, AtomType.MATCHING],  # Pomo 3: Connections
            [AtomType.TRUE_FALSE, AtomType.PARSONS],  # Pomo 4: Procedures
            [AtomType.MCQ, AtomType.TRUE_FALSE, AtomType.MATCHING],  # Pomo 5: Variety
            [AtomType.PARSONS, AtomType.MCQ],  # Pomo 6: Deeper
        ]
        return patterns[pomo_num % len(patterns)]

    def show_plan(self, session: PomodoroSession | None = None) -> None:
        """Display the session plan."""
        session = session or self.current_session
        if not session:
            rprint("[red]No session planned[/red]")
            return

        console.print()
        content = Text()
        content.append(f"Session Plan: {session.planned_hours} hours\n", style="bold cyan")
        content.append(f"Pomodoros: {len(session.pomodoros)}\n\n")

        if session.focus_module:
            content.append(f"Focus: Module {session.focus_module}\n")
        if session.focus_section:
            content.append(f"Section: {session.focus_section}\n")

        panel = Panel(content, title="[bold]Study Plan[/bold]", border_style="blue")
        console.print(panel)

        # Show blocks
        for i, pomo in enumerate(session.pomodoros, 1):
            console.print(f"\n[cyan]Pomodoro {i}[/cyan]")
            for block in pomo:
                if block.block_type == BlockType.ANKI:
                    console.print(
                        f"  [yellow]ANKI[/yellow] ({block.duration_minutes} min) - Flashcard/Cloze reviews"
                    )
                elif block.block_type == BlockType.QUIZ:
                    types = ", ".join(t.value for t in block.atom_types)
                    console.print(f"  [green]QUIZ[/green] ({block.duration_minutes} min) - {types}")
                elif block.block_type == BlockType.BREAK:
                    console.print(f"  [dim]BREAK[/dim] ({block.duration_minutes} min)")

        console.print()

    def run_session(self, session: PomodoroSession | None = None) -> PomodoroSession:
        """
        Run the full study session interactively.

        Returns:
            Completed PomodoroSession with stats
        """
        session = session or self.current_session
        if not session:
            raise ValueError("No session planned. Call plan_session() first.")

        session.started_at = datetime.now()
        console.clear()

        # Welcome
        self._show_session_start(session)

        try:
            for pomo_idx, pomo_blocks in enumerate(session.pomodoros):
                session.current_pomodoro = pomo_idx

                console.print(
                    f"\n[bold cyan]═══ POMODORO {pomo_idx + 1}/{len(session.pomodoros)} ═══[/bold cyan]\n"
                )

                for block_idx, block in enumerate(pomo_blocks):
                    session.current_block = block_idx

                    if block.block_type == BlockType.ANKI:
                        self._run_anki_block(session, block)
                    elif block.block_type == BlockType.QUIZ:
                        self._run_quiz_block(session, block)
                    elif block.block_type == BlockType.BREAK:
                        self._run_break(block)

                    block.completed = True

        except KeyboardInterrupt:
            console.print("\n[yellow]Session paused.[/yellow]")

        session.ended_at = datetime.now()

        # Save and show summary
        self._save_session(session)
        self._show_session_summary(session)

        return session

    def _show_session_start(self, session: PomodoroSession) -> None:
        """Show session start banner."""
        content = Text()
        content.append("Study Session Starting\n\n", style="bold")
        content.append(f"Duration: {session.planned_hours} hours\n")
        content.append(f"Pomodoros: {len(session.pomodoros)}\n\n")
        content.append("Structure per pomodoro:\n", style="dim")
        content.append("  1. Anki (12 min) - Flashcard/Cloze\n", style="yellow")
        content.append("  2. Quiz (13 min) - MCQ/T-F/Matching/Parsons\n", style="green")
        content.append("  3. Break (5 min)\n\n", style="dim")
        content.append("Press Ctrl+C anytime to pause.\n", style="dim")

        panel = Panel(
            content, title="[bold cyan]NLS Study Session[/bold cyan]", border_style="cyan"
        )
        console.print(panel)

        if not Confirm.ask("\n[bold]Ready to begin?[/bold]", default=True):
            raise KeyboardInterrupt()

    def _run_anki_block(self, session: PomodoroSession, block: PomodoroBlock) -> None:
        """Run an Anki review block."""
        console.print()
        panel_content = Text()
        panel_content.append("Time to review in Anki!\n\n", style="bold")
        panel_content.append("1. Open Anki\n")
        panel_content.append("2. Review due flashcards and cloze cards\n")
        panel_content.append(f"3. Aim for ~{block.duration_minutes} minutes\n\n")

        if session.focus_section:
            panel_content.append(f"Focus: Section {session.focus_section}\n", style="cyan")
            panel_content.append(
                f"Anki query: deck:CCNA* tag:section:{session.focus_section}*\n", style="dim"
            )
        else:
            panel_content.append("Focus: Due reviews first, then new cards\n", style="cyan")
            panel_content.append("Anki query: deck:CCNA* is:due\n", style="dim")

        panel = Panel(
            panel_content,
            title=f"[bold yellow]ANKI BLOCK[/bold yellow] ({block.duration_minutes} min)",
            border_style="yellow",
        )
        console.print(panel)

        # Timer with countdown
        console.print("\n[dim]Press Enter when done with Anki, or wait for timer...[/dim]")

        # Simple timer - could be enhanced with actual countdown
        start = datetime.now()
        target = start + timedelta(minutes=block.duration_minutes)

        try:
            # Wait for user input or timeout

            while datetime.now() < target:
                remaining = (target - datetime.now()).seconds // 60
                console.print(
                    f"\r[dim]~{remaining} min remaining... (press Enter when done)[/dim]", end=""
                )

                # Check for input (simplified - works better in interactive mode)
                try:
                    response = Prompt.ask(
                        "\n[bold]How many cards did you review?[/bold]",
                        default="20",
                    )
                    block.cards_done = int(response) if response.isdigit() else 20
                    break
                except (EOFError, KeyboardInterrupt):
                    block.cards_done = 15  # Estimate
                    break

        except Exception:
            block.cards_done = 15  # Estimate if timer fails

        session.total_anki_cards += block.cards_done
        console.print(f"\n[green]✓ Completed {block.cards_done} Anki cards[/green]\n")

    def _run_quiz_block(self, session: PomodoroSession, block: PomodoroBlock) -> None:
        """Run an in-app quiz block."""
        console.print()
        types_str = ", ".join(t.value.replace("_", "/") for t in block.atom_types)

        panel_content = Text()
        panel_content.append("Interactive Quiz Time!\n\n", style="bold")
        panel_content.append(f"Types: {types_str}\n")
        panel_content.append(f"Duration: ~{block.duration_minutes} minutes\n\n")
        panel_content.append("Answer each question to build mastery.\n", style="dim")

        panel = Panel(
            panel_content,
            title=f"[bold green]QUIZ BLOCK[/bold green] ({block.duration_minutes} min)",
            border_style="green",
        )
        console.print(panel)

        if not Confirm.ask("\n[bold]Start quiz?[/bold]", default=True):
            return

        # Fetch atoms for quiz
        atoms = self.quiz_engine.fetch_atoms(
            atom_types=block.atom_types,
            section_id=session.focus_section,
            limit=15,  # ~1 min per atom
            prioritize_weak=True,
        )

        if not atoms:
            console.print("[yellow]No quiz atoms available for these types/section[/yellow]")
            return

        console.print(f"\n[dim]Loaded {len(atoms)} questions[/dim]\n")

        # Present each atom
        start_time = datetime.now()
        max_duration = timedelta(minutes=block.duration_minutes)

        for i, atom in enumerate(atoms, 1):
            # Check time limit
            if datetime.now() - start_time > max_duration:
                console.print("\n[yellow]Time's up for this block![/yellow]")
                break

            console.print(f"\n[dim]Question {i}/{len(atoms)}[/dim]")

            result = self.quiz_engine.present_atom(atom)

            if result.is_correct:
                block.correct += 1
                session.total_quiz_correct += 1
            else:
                block.incorrect += 1
                session.total_quiz_incorrect += 1

            block.cards_done += 1

            # Track per-type count for accurate session reporting
            atom_type_key = atom.atom_type.value  # e.g., "mcq", "true_false"
            if atom_type_key in block.quiz_type_counts:
                block.quiz_type_counts[atom_type_key] += 1

            # Brief pause between questions
            time.sleep(0.5)

            # Option to continue or stop
            if i < len(atoms) and i % 5 == 0:
                if not Confirm.ask("\n[dim]Continue?[/dim]", default=True):
                    break

        # Block summary
        accuracy = (block.correct / block.cards_done * 100) if block.cards_done > 0 else 0
        console.print(
            f"\n[green]✓ Quiz block complete: {block.correct}/{block.cards_done} ({accuracy:.0f}%)[/green]"
        )

    def _run_break(self, block: PomodoroBlock) -> None:
        """Run a break period."""
        console.print()
        panel_content = Text()
        panel_content.append("Time for a break!\n\n", style="bold")
        panel_content.append("• Stand up and stretch\n")
        panel_content.append("• Rest your eyes\n")
        panel_content.append("• Get some water\n")
        panel_content.append(f"\n{block.duration_minutes} minutes\n", style="dim")

        panel = Panel(
            panel_content,
            title="[bold dim]BREAK[/bold dim]",
            border_style="dim",
        )
        console.print(panel)

        # Simple countdown
        console.print("\n[dim]Press Enter to skip break...[/dim]")

        try:
            for remaining in range(block.duration_minutes * 60, 0, -30):
                mins = remaining // 60
                console.print(f"\r[dim]Break: {mins}:{remaining % 60:02d} remaining[/dim]", end="")
                time.sleep(min(30, remaining))
        except (EOFError, KeyboardInterrupt):
            pass

        console.print("\n[green]✓ Break complete![/green]\n")

    def _save_session(self, session: PomodoroSession) -> None:
        """Save session to database with per-type quiz counts."""
        try:
            with session_scope() as db:
                duration_minutes = 0
                if session.started_at and session.ended_at:
                    duration_minutes = int(
                        (session.ended_at - session.started_at).total_seconds() / 60
                    )

                # Aggregate quiz type counts from all blocks
                quiz_counts = {"mcq": 0, "true_false": 0, "matching": 0, "parsons": 0}
                for pomo in session.pomodoros:
                    for block in pomo:
                        if block.block_type == BlockType.QUIZ:
                            for quiz_type, count in block.quiz_type_counts.items():
                                quiz_counts[quiz_type] += count

                db.execute(
                    text("""
                    INSERT INTO pomodoro_sessions (
                        id, user_id, started_at, ended_at, planned_hours, actual_minutes,
                        pomodoros_completed, pomodoros_planned,
                        anki_cards_reviewed, mcq_answered, true_false_answered,
                        matching_answered, parsons_answered,
                        total_correct, total_incorrect,
                        focus_module, focus_section_id
                    ) VALUES (
                        :id, :user_id, :started, :ended, :planned_hours, :actual_minutes,
                        :pomos_done, :pomos_planned,
                        :anki_cards, :mcq, :tf, :matching, :parsons,
                        :correct, :incorrect,
                        :focus_module, :focus_section
                    )
                """),
                    {
                        "id": str(session.id),
                        "user_id": session.user_id,
                        "started": session.started_at,
                        "ended": session.ended_at,
                        "planned_hours": session.planned_hours,
                        "actual_minutes": duration_minutes,
                        "pomos_done": session.current_pomodoro + 1,
                        "pomos_planned": len(session.pomodoros),
                        "anki_cards": session.total_anki_cards,
                        "mcq": quiz_counts["mcq"],
                        "tf": quiz_counts["true_false"],
                        "matching": quiz_counts["matching"],
                        "parsons": quiz_counts["parsons"],
                        "correct": session.total_quiz_correct,
                        "incorrect": session.total_quiz_incorrect,
                        "focus_module": session.focus_module,
                        "focus_section": session.focus_section,
                    },
                )
                db.commit()
                logger.info(
                    f"Session saved: {session.total_anki_cards} Anki, "
                    f"MCQ:{quiz_counts['mcq']} TF:{quiz_counts['true_false']} "
                    f"Match:{quiz_counts['matching']} Parsons:{quiz_counts['parsons']}"
                )
        except Exception as e:
            logger.warning(f"Could not save session: {e}")

    def _show_session_summary(self, session: PomodoroSession) -> None:
        """Show final session summary."""
        console.print()

        duration_str = "N/A"
        if session.started_at and session.ended_at:
            duration = session.ended_at - session.started_at
            mins = int(duration.total_seconds() / 60)
            duration_str = f"{mins} minutes"

        total_quiz = session.total_quiz_correct + session.total_quiz_incorrect
        quiz_accuracy = (session.total_quiz_correct / total_quiz * 100) if total_quiz > 0 else 0

        content = Text()
        content.append("Session Complete!\n\n", style="bold green")
        content.append(f"Duration: {duration_str}\n")
        content.append(f"Pomodoros: {session.current_pomodoro + 1}/{len(session.pomodoros)}\n\n")

        content.append("Anki Reviews:\n", style="yellow")
        content.append(f"  Cards reviewed: {session.total_anki_cards}\n\n")

        content.append("In-App Quizzes:\n", style="green")
        content.append(f"  Questions: {total_quiz}\n")
        content.append(f"  Correct: {session.total_quiz_correct}\n")
        content.append(f"  Accuracy: {quiz_accuracy:.0f}%\n")

        panel = Panel(
            content,
            title="[bold]Session Summary[/bold]",
            border_style="green",
        )
        console.print(panel)

    def quick_quiz(
        self,
        count: int = 10,
        atom_types: list[AtomType] | None = None,
        section_id: str | None = None,
    ) -> dict:
        """
        Run a quick quiz session without full Pomodoro structure.

        Args:
            count: Number of questions
            atom_types: Types to include (default: MCQ + T/F)
            section_id: Optional section filter

        Returns:
            Quiz stats dict
        """
        if atom_types is None:
            atom_types = [AtomType.MCQ, AtomType.TRUE_FALSE]

        self.quiz_engine.reset_session()

        atoms = self.quiz_engine.fetch_atoms(
            atom_types=atom_types,
            section_id=section_id,
            limit=count,
            prioritize_weak=True,
        )

        if not atoms:
            console.print("[yellow]No quiz atoms available[/yellow]")
            return {"total": 0, "correct": 0, "accuracy": 0}

        console.print(f"\n[bold]Quick Quiz: {len(atoms)} questions[/bold]\n")

        for i, atom in enumerate(atoms, 1):
            console.print(f"\n[dim]Question {i}/{len(atoms)}[/dim]")
            self.quiz_engine.present_atom(atom)

        return self.quiz_engine.get_session_summary()
