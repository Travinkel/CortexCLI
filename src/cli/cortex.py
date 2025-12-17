"""
The Cortex CLI: ASI-themed neural study interface for CCNA mastery.

Visual Identity: "Digital Neocortex"
- Cyan/Electric Blue color scheme
- Pulsing brain ASCII art animations
- Futuristic ">_ INPUT VECTOR:" prompts
- Google Calendar integration for scheduling

Modes:
- nls cortex start --mode adaptive (default)  -> adaptive interleaved session
- nls cortex start --mode war                 -> cram mode (modules 11-17, immediate retries)
- nls cortex schedule --time "tomorrow 9am"   -> schedule on Google Calendar
- nls cortex agenda                            -> show upcoming sessions
"""
from __future__ import annotations

import os
import sys

# Fix Windows encoding issues for Unicode characters (ASCII art, box drawing)
if sys.platform == "win32":
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    if hasattr(sys.stderr, 'reconfigure'):
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')

import random
import re
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Iterable, List, Optional

import typer
import yaml
from dateutil import parser as date_parser
from rich import box
from rich.align import Align
from rich.console import Console
from rich.layout import Layout
from rich.live import Live
from rich.panel import Panel
from rich.prompt import Confirm, Prompt
from rich.status import Status
from rich.style import Style
from rich.table import Table
from rich.text import Text
from sqlalchemy import text

from config import get_settings
from src.db.database import engine
from src.study.quiz_engine import QuizEngine, AtomType as QuizAtomType
from src.study.study_service import StudyService

# ASI Visual Components
from src.delivery.cortex_visuals import (
    CORTEX_THEME,
    STYLES,
    cortex_boot_sequence,
    cortex_question_panel,
    cortex_result_panel,
    get_asi_prompt,
    CortexSpinner,
    create_neurolink_panel,
    create_compact_neurolink,
    create_struggle_heatmap,
    render_signals_dashboard,
    # 3D ASCII Art Engine
    create_3d_panel,
    create_holographic_header,
    create_3d_status_card,
    create_neural_border,
    render_3d_menu,
)

# Google Calendar Integration
from src.integrations.google_calendar import CortexCalendar

# Neuro-Cognitive Diagnosis Engine (NCDE)
from src.adaptive.ncde_pipeline import (
    NCDEPipeline,
    SessionContext,
    RawInteractionEvent,
    create_raw_event,
    FatigueVector,
    RemediationType,
)
from src.adaptive.neuro_model import (
    CognitiveDiagnosis,
    FailMode,
    SuccessMode,
    CognitiveState,
)


# Atom handlers (modular question type system)
from src.cortex.atoms import get_handler as get_atom_handler
from src.cortex import CORTEX_SUPPORTED_TYPES
from src.cortex.session import CortexSession
cortex_app = typer.Typer(
    help="The Cortex: ASI-themed neural study interface with calendar scheduling",
    no_args_is_help=True,
)

console = Console()


def _normalize_numeric(raw: str) -> int | float | str:
    """
    Normalize numeric answers for comparison (supports hex/binary/decimal).

    Returns:
        - int for binary/hex values (preserves precision for large numbers)
        - float for decimal values
        - str for non-numeric values (e.g., IP addresses like "192.168.1.0")

    Hardening:
    - Uses int instead of float for binary/hex to avoid precision loss
    - Handles IP addresses as strings for exact matching
    - Returns original string for complex values (subnet masks, etc.)
    """
    value = raw.strip().lower().replace("_", "").replace(" ", "")

    # Handle IP addresses (dotted decimal notation)
    if "." in value and all(
        part.isdigit() and 0 <= int(part) <= 255
        for part in value.split(".")
        if part
    ):
        # Return as normalized IP string for exact comparison
        try:
            parts = value.split(".")
            if len(parts) == 4:
                return ".".join(str(int(p)) for p in parts)
        except ValueError:
            pass

    # Hex with 0x prefix - use int for precision
    if value.startswith("0x"):
        try:
            return int(value, 16)
        except ValueError:
            pass

    # Binary with 0b prefix - use int for precision
    if value.startswith("0b"):
        try:
            return int(value, 2)
        except ValueError:
            pass

    # Binary without prefix (string of 0s and 1s, at least 4 chars)
    # Must be all 0s and 1s to be considered binary
    if len(value) >= 4 and set(value).issubset({"0", "1"}):
        try:
            return int(value, 2)
        except ValueError:
            pass

    # Hex with h suffix (e.g., "FFh")
    if value.endswith("h") and len(value) > 1:
        try:
            return int(value[:-1], 16)
        except ValueError:
            pass

    # CIDR notation (e.g., "/24") - return as string
    if value.startswith("/") and value[1:].isdigit():
        return value

    # Regular decimal number
    try:
        # Try int first for whole numbers
        if "." not in value and "e" not in value:
            return int(value)
        return float(value)
    except ValueError:
        # Return as string for non-numeric (allows string comparison)
        return raw.strip()


def _compare_numeric_answers(user_answer: int | float | str, correct_answer: int | float | str, tolerance: float = 0) -> bool:
    """
    Compare numeric answers with type-aware logic.

    Args:
        user_answer: Normalized user answer
        correct_answer: Normalized correct answer
        tolerance: Fractional tolerance for float comparison (0 = exact)

    Returns:
        True if answers match within tolerance
    """
    # String comparison for IP addresses, CIDR, etc.
    if isinstance(user_answer, str) or isinstance(correct_answer, str):
        return str(user_answer).strip().lower() == str(correct_answer).strip().lower()

    # Integer comparison (exact match for binary/hex)
    if isinstance(user_answer, int) and isinstance(correct_answer, int):
        return user_answer == correct_answer

    # Float comparison with tolerance
    try:
        user_float = float(user_answer)
        correct_float = float(correct_answer)

        if tolerance > 0 and correct_float != 0:
            return abs(user_float - correct_float) <= abs(correct_float * tolerance)
        return user_float == correct_float
    except (ValueError, TypeError):
        return False


def _split_parsons_steps(back: str) -> list[str]:
    """Split a Parsons back field into ordered steps."""
    # Common delimiters: arrow (unicode or ASCII), newline, numbered list
    # Use alternation instead of character class to avoid range interpretation
    parts = re.split(r"\s*(?:->|→)+\s*|\n+", back.strip())
    steps = [p.strip() for p in parts if p.strip()]
    return steps


# Cortex only supports quiz-style atom types (not flashcards/cloze - those are for Anki)
def _parse_module_list(raw: Optional[str], default: Iterable[int]) -> list[int]:
    if not raw:
        return list(default)
    return [int(part.strip()) for part in raw.split(",") if part.strip().isdigit()]


def _ensure_struggles_imported() -> bool:
    """Check if struggles are imported, auto-import if struggles.yaml exists and DB is empty."""
    try:
        with engine.connect() as conn:
            result = conn.execute(text("SELECT COUNT(*) FROM struggle_weights"))
            count = result.scalar() or 0
            if count > 0:
                return True  # Already imported

        # Check if struggles.yaml exists
        project_root = Path(__file__).parent.parent.parent
        yaml_path = project_root / "struggles.yaml"
        if yaml_path.exists():
            console.print("[dim]Auto-importing struggles from struggles.yaml...[/dim]")
            result = _import_struggles_to_db()
            console.print(f"[green][OK][/green] Imported {result['imported']} struggle weights\n")
            return True
        return False
    except Exception:
        return False


def _get_pre_session_stats() -> dict:
    """Get pre-session statistics for the dashboard."""
    try:
        with engine.connect() as conn:
            # Get overall mastery
            result = conn.execute(text("""
                SELECT
                    COUNT(*) as total,
                    SUM(CASE WHEN nls_correct_count > nls_incorrect_count THEN 1 ELSE 0 END) as mastered
                FROM learning_atoms
                WHERE atom_type IN ('mcq', 'true_false', 'numeric', 'parsons')
            """))
            row = result.fetchone()
            total = row[0] or 1
            mastered = row[1] or 0
            overall_mastery = int((mastered / total) * 100) if total > 0 else 0

            # Get streak (placeholder)
            streak_days = 0

            # Get struggle zones
            result = conn.execute(text("""
                SELECT module_number, weight
                FROM struggle_weights
                WHERE weight > 0.5
                ORDER BY weight DESC
                LIMIT 5
            """))
            struggle_zones = [
                {"module_number": row[0], "weight": float(row[1]) if row[1] else 0.0, "avg_priority": float(row[1]) if row[1] else 0.0}
                for row in result.fetchall()
            ]

            return {
                "overall_mastery": overall_mastery,
                "sections_total": total,
                "sections_complete": mastered,
                "streak_days": streak_days,
                "struggle_zones": struggle_zones,
                "struggle_count": len(struggle_zones),
                "due_count": 0,
                "new_count": 0,
            }
    except Exception as e:
        logger.warning(f"Failed to get pre-session stats: {e}")
        return {
            "overall_mastery": 0, "sections_total": 0, "sections_complete": 0,
            "streak_days": 0, "struggle_zones": [], "struggle_count": 0,
            "due_count": 0, "new_count": 0,
        }


def _get_struggle_stats() -> list[dict]:
    """Get struggle weight statistics by module."""
    try:
        with engine.connect() as conn:
            result = conn.execute(text("""
                SELECT module_number, section_id, weight
                FROM struggle_weights
                ORDER BY module_number, section_id
            """))
            return [
                {
                    "module_number": row[0],
                    "section_id": row[1],
                    "weight": float(row[2]) if row[2] else 0.0,
                }
                for row in result.fetchall()
            ]
    except Exception as e:
        console.print(f"[yellow]Warning: Failed to get struggle stats: {e}[/yellow]")
        return []


def _show_interactive_dashboard() -> str:
    """
    Show the interactive dashboard hub.

    Returns the user's menu choice.
    """
    from src.anki.background_sync import get_background_sync

    # Auto-import struggles if needed
    _ensure_struggles_imported()

    try:
        stats = _get_pre_session_stats()
    except Exception as e:
        console.print(f"[yellow]Could not load stats: {e}[/yellow]")
        stats = {
            "overall_mastery": 0, "sections_total": 0, "sections_complete": 0,
            "streak_days": 0, "struggle_zones": [], "struggle_count": 0,
            "due_count": 0, "new_count": 0,
        }

    module_names = {
        1: "Networking Today", 2: "Switch Config", 3: "Protocols",
        4: "Physical Layer", 5: "Number Systems", 6: "Data Link",
        7: "Ethernet", 8: "Network Layer", 9: "Address Resolution",
        10: "Router Config", 11: "IPv4", 12: "IPv6", 13: "ICMP",
        14: "Transport", 15: "Application", 16: "Security", 17: "Small Network",
    }

    # =========================================================================
    # 3D HOLOGRAPHIC DASHBOARD
    # =========================================================================

    # Holographic header with neural pattern
    console.print(create_holographic_header("CORTEX - NEURAL STUDY HUB", width=90, style="neural"))

    # Anki sync status line
    sync = get_background_sync()
    if sync:
        sync_line = sync.get_status_line()
        if "synced" in sync_line.lower():
            console.print(f"  {sync_line}", style=Style(color=CORTEX_THEME["success"]))
        elif "syncing" in sync_line.lower():
            console.print(f"  {sync_line}", style=Style(color=CORTEX_THEME["accent"]))
        elif "disconnected" in sync_line.lower() or "offline" in sync_line.lower():
            console.print(f"  Anki: offline", style=Style(color=CORTEX_THEME["dim"]))
        else:
            console.print(f"  {sync_line}", style=Style(color=CORTEX_THEME["warning"]))

    console.print()

    # Build main dashboard content for 3D panel
    dashboard_content = []

    # Overall stats row
    mastery_pct = stats["overall_mastery"]
    dashboard_content.append(f"Overall Mastery: {mastery_pct:.0f}%  |  Streak: {stats['streak_days']} days")
    dashboard_content.append("")

    # Struggle zones
    if stats["struggle_zones"]:
        dashboard_content.append("STRUGGLE ZONES")
        for zone in stats["struggle_zones"][:5]:
            mod = zone["module_number"]
            name = module_names.get(mod, f"Module {mod}")
            priority = zone["avg_priority"]
            indicator = "[!]" if priority > 2.0 else "[*]"
            dashboard_content.append(f"  {indicator} Module {mod}: {name[:20]}")
        dashboard_content.append("")
    else:
        dashboard_content.append("No struggle zones configured yet.")
        dashboard_content.append("")

    # Session preview
    dashboard_content.append("READY TO STUDY")
    if stats["struggle_count"] > 0:
        dashboard_content.append(f"  {stats['struggle_count']} atoms from struggle zones")
    if stats["due_count"] > 0:
        dashboard_content.append(f"  {stats['due_count']} due for review")
    # Show progress: learned / total
    learned = stats.get("learned_count", 0)
    total_atoms = stats.get("total_count", 0)
    if total_atoms > 0:
        pct = (learned / total_atoms) * 100
        dashboard_content.append(f"  {learned}/{total_atoms} atoms learned ({pct:.0f}%)")

    # Render with 3D panel effect
    console.print(create_3d_panel(
        content="\n".join(dashboard_content),
        title="NEURAL STATUS",
        width=90,
        border_color=CORTEX_THEME["primary"],
        shadow_depth=2,
        glow=True,
    ))

    # Neural border separator
    console.print(create_neural_border(width=90))
    console.print()

    # 3D Action Menu
    menu_text = Text()
    menu_text.append("ACTIONS\n\n", style=STYLES["cortex_accent"])

    # Menu items with 3D-style formatting
    menu_items = [
        ("1", "Start adaptive session", "struggle-prioritized", CORTEX_THEME["success"]),
        ("2", "Start war mode", "cram session", CORTEX_THEME["error"]),
        ("3", "View struggle map", "details", CORTEX_THEME["warning"]),
        ("4", "Import struggles", "from YAML", CORTEX_THEME["secondary"]),
        ("5", "Configure modules", "", CORTEX_THEME["dim"]),
        ("6", "Resume session", "", CORTEX_THEME["dim"]),
        ("7", "Browse study notes", "", CORTEX_THEME["dim"]),
        ("8", "Learning signals", "dashboard", CORTEX_THEME["accent"]),
        ("9", "Sync with Anki", "", CORTEX_THEME["secondary"]),
        ("q", "Quit", "", CORTEX_THEME["dim"]),
    ]

    for key, label, sublabel, color in menu_items:
        # 3D button effect for first two options
        if key in ("1", "2"):
            menu_text.append("  ╔═", style=Style(color=color))
            menu_text.append(f" {key} ", style=Style(color=CORTEX_THEME["white"], bold=True))
            menu_text.append("═╗ ", style=Style(color=color))
            menu_text.append(f"{label}", style=Style(color=CORTEX_THEME["white"], bold=True))
            if sublabel:
                menu_text.append(f" ({sublabel})", style=Style(color=CORTEX_THEME["dim"]))
            menu_text.append("\n")
            menu_text.append("  ╚═══╝▓\n", style=Style(color=CORTEX_THEME["dim"]))
        else:
            # Flat style for other options
            menu_text.append(f"    [{key}] ", style=Style(color=color))
            menu_text.append(f"{label}", style=Style(color=CORTEX_THEME["white"]))
            if sublabel:
                menu_text.append(f" ({sublabel})", style=Style(color=CORTEX_THEME["dim"]))
            menu_text.append("\n")

    console.print(menu_text)
    console.print()

    return Prompt.ask(
        "[cyan]>_ SELECT ACTION[/cyan]",
        choices=["1", "2", "3", "4", "5", "6", "7", "8", "9", "q"],
        default="1",
    )


def _run_interactive_hub(initial_limit: int = 20):
    """Run the interactive Cortex hub loop."""
    from src.anki.background_sync import start_background_sync, stop_background_sync, get_background_sync

    limit = initial_limit
    module_list = list(range(1, 18))  # Default: all modules

    # Start background Anki sync
    sync_manager = start_background_sync(interval_seconds=300, min_quality="B")
    if sync_manager.status.anki_connected:
        console.print("[dim]Background Anki sync started[/dim]")

    try:
        while True:
            console.clear()
            cortex_boot_sequence(console, skip_animation=True)

            choice = _show_interactive_dashboard()

            if choice == "1":
                # Adaptive session
                console.print("\n[cyan]Starting adaptive session...[/cyan]\n")
                session = CortexSession(modules=module_list, limit=limit, war_mode=False)
                session.run()
                # After session ends, return to hub
                console.print("\n[dim]Press Enter to return to hub...[/dim]")
                input()

            elif choice == "2":
                # War mode
                console.print("\n[cyan]Starting war mode...[/cyan]\n")
                war_modules = list(range(11, 18))
                session = CortexSession(modules=war_modules, limit=25, war_mode=True)
                session.run()
                console.print("\n[dim]Press Enter to return to hub...[/dim]")
                input()

            elif choice == "3":
                # View struggles with sub-menu
                console.print()
                struggles = _get_struggle_stats()
                if struggles:
                    struggle_schema = {s["module_number"]: s["weight"] for s in struggles}
                    console.print(create_struggle_heatmap(struggle_schema))

                    # Detailed table
                    table = Table(
                        title="[bold cyan]STRUGGLE DETAILS[/bold cyan]",
                        box=box.ROUNDED,
                        border_style=Style(color=CORTEX_THEME["secondary"]),
                    )
                    table.add_column("Module", style="cyan", justify="center")
                    table.add_column("Severity", justify="center")
                    table.add_column("Weight", justify="right")
                    table.add_column("Mastery", justify="right")
                    table.add_column("Notes", max_width=40)

                    severity_colors = {
                        "critical": CORTEX_THEME["error"],
                        "high": CORTEX_THEME["warning"],
                        "medium": CORTEX_THEME["accent"],
                        "low": CORTEX_THEME["dim"],
                    }

                    for s in struggles:
                        severity_style = Style(color=severity_colors.get(s["severity"], CORTEX_THEME["dim"]))
                        mastery_pct = s["avg_mastery"]
                        mastery_style = Style(
                            color=CORTEX_THEME["success"] if mastery_pct >= 70 else (
                                CORTEX_THEME["warning"] if mastery_pct >= 40 else CORTEX_THEME["error"]
                            )
                        )
                        table.add_row(
                            f"M{s['module_number']:02d}",
                            Text(s["severity"].upper(), style=severity_style),
                            f"{s['weight']:.2f}",
                            Text(f"{mastery_pct:.0f}%", style=mastery_style),
                            s["notes"][:40] if s["notes"] else "",
                        )
                    console.print(table)

                    # Sub-menu for struggle actions
                    console.print("\n[bold cyan]STRUGGLE ACTIONS[/bold cyan]")
                    console.print("  [cyan]1[/cyan] - Generate study notes for all struggles")
                    console.print("  [cyan]2[/cyan] - Create filtered Anki deck for struggles")
                    console.print("  [cyan]b[/cyan] - Back to hub")

                    sub_choice = Prompt.ask(
                        "\n>_ [cyan]ACTION[/cyan]",
                        choices=["1", "2", "b"],
                        default="b",
                    )

                    if sub_choice == "1":
                        _generate_struggle_notes(struggles)
                    elif sub_choice == "2":
                        _create_struggle_deck(struggles)
                else:
                    console.print("[yellow]No struggles configured. Select option 4 to import.[/yellow]")
                    console.print("\n[dim]Press Enter to return to hub...[/dim]")
                    input()

            elif choice == "4":
                # Import struggles
                console.print("\n[cyan]Importing struggles from struggles.yaml...[/cyan]")
                result = _import_struggles_to_db()
                if result.get("errors"):
                    for err in result["errors"]:
                        console.print(f"[yellow]Warning: {err}[/yellow]")
                console.print(f"[green][OK][/green] Imported {result['imported']} struggle weights")
                console.print("\n[dim]Press Enter to return to hub...[/dim]")
                input()

            elif choice == "5":
                # Configure modules
                console.print("\n[bold cyan]MODULE CONFIGURATION[/bold cyan]\n")
                console.print("[dim]Available modules: 1-17[/dim]")
                console.print("  [cyan]1-10[/cyan]: Fundamentals (OSI, TCP/IP, Addressing)")
                console.print("  [cyan]11-17[/cyan]: Advanced (Routing, Switching, Security)")
                console.print()
                console.print(f"[dim]Current selection: {module_list}[/dim]\n")

                modules_input = Prompt.ask(
                    "[cyan]>_ MODULES (e.g., 1-17 or 5,8,9)[/cyan]",
                    default=",".join(str(m) for m in module_list),
                )

                # Parse range notation
                new_modules = []
                for part in modules_input.split(","):
                    part = part.strip()
                    if "-" in part:
                        try:
                            start_m, end_m = part.split("-")
                            new_modules.extend(range(int(start_m), int(end_m) + 1))
                        except ValueError:
                            pass
                    elif part.isdigit():
                        new_modules.append(int(part))

                if new_modules:
                    module_list = sorted(set(new_modules))
                    console.print(f"[green][OK][/green] Modules set to: {module_list}")
                else:
                    console.print("[yellow]Invalid input, keeping current selection[/yellow]")

                # Also configure limit
                limit_input = Prompt.ask(
                    "[cyan]>_ ATOMS PER SESSION[/cyan]",
                    default=str(limit),
                )
                if limit_input.isdigit():
                    limit = int(limit_input)
                    console.print(f"[green][OK][/green] Limit set to: {limit}")

                console.print("\n[dim]Press Enter to return to hub...[/dim]")
                input()

            elif choice == "6":
                # Resume session
                session = CortexSession.resume_latest()
                if session:
                    state = session._session_state
                    console.print(
                        Panel(
                            f"[cyan]Found saved session[/cyan]\n\n"
                            f"Mode: [bold]{state.mode.upper()}[/bold]\n"
                            f"Started: {state.started_at[:19]}\n"
                            f"Progress: {state.correct + state.incorrect} completed, "
                            f"{len(state.atoms_remaining)} remaining\n"
                            f"Score: {state.correct} correct, {state.incorrect} incorrect",
                            border_style=Style(color=CORTEX_THEME["accent"]),
                            box=box.ROUNDED,
                        )
                    )
                    if Confirm.ask("Resume this session?", default=True):
                        session.run()
                else:
                    console.print("[yellow]No saved session found.[/yellow]")

                console.print("\n[dim]Press Enter to return to hub...[/dim]")
                input()

            elif choice == "7":
                # Browse study notes
                _browse_study_notes()
                console.print("\n[dim]Press Enter to return to hub...[/dim]")
                input()

            elif choice == "8":
                # Learning signals dashboard
                _show_signals_dashboard()
                console.print("\n[dim]Press Enter to return to hub...[/dim]")
                input()

            elif choice == "9":
                # Manual Anki sync
                sync = get_background_sync()
                if sync and sync.status.anki_connected:
                    console.print("\n[cyan]Syncing with Anki...[/cyan]")
                    result = sync.sync_now()
                    if result.get("error"):
                        console.print(f"[red]Sync failed: {result['error']}[/red]")
                    else:
                        push_count = sync.status.last_push_count
                        pull_count = sync.status.last_pull_count
                        console.print(f"[green]Sync complete![/green] Pushed: {push_count}, Pulled: {pull_count}")
                else:
                    console.print("[yellow]Anki not connected. Start Anki with AnkiConnect addon.[/yellow]")
                console.print("\n[dim]Press Enter to return to hub...[/dim]")
                input()

            elif choice == "q":
                console.print("\n[dim]Exiting Cortex...[/dim]")
                break

    finally:
        # Stop background sync on exit
        stop_background_sync()


def _show_note_actions_menu(note: dict) -> None:
    """Display and handle the note actions menu after viewing a note."""
    import asyncio
    from rich.markdown import Markdown
    from rich.syntax import Syntax
    from src.learning.note_generator import mark_note_read

    while True:
        console.print("\n[bold cyan]Note Actions[/bold cyan]")
        console.print("[dim]What would you like to do?[/dim]\n")
        console.print("  [yellow]1[/yellow] Generate comparison table")
        console.print("  [yellow]2[/yellow] Generate diagram (Mermaid)")
        console.print("  [yellow]3[/yellow] Generate flashcards + cloze")
        console.print("  [yellow]4[/yellow] Create Anki filtered deck")
        console.print("  [yellow]5[/yellow] Rate this note")
        console.print("  [yellow]b[/yellow] Return to notes list")
        console.print()

        choice = Prompt.ask("[cyan]>_[/cyan]", choices=["1", "2", "3", "4", "5", "b"], default="b")

        if choice == "1":
            _handle_generate_table(note)
        elif choice == "2":
            _handle_generate_diagram(note)
        elif choice == "3":
            _handle_generate_atoms(note)
        elif choice == "4":
            _handle_create_anki_deck(note)
        elif choice == "5":
            _handle_rate_note(note)
        elif choice == "b":
            break


def _handle_generate_table(note: dict) -> None:
    """Handle comparison table generation action."""
    from src.db.database import session_scope
    from src.learning.note_actions import NoteActionsService
    from rich.markdown import Markdown

    console.print("\n[cyan]Generating comparison table...[/cyan]")

    with session_scope() as session:
        service = NoteActionsService(session)
        success, result = service.generate_comparison_table(note)

    if success:
        console.print()
        console.print(Markdown(result))
    else:
        console.print(f"[red]{result}[/red]")


def _handle_generate_diagram(note: dict) -> None:
    """Handle Mermaid diagram generation action."""
    from src.db.database import session_scope
    from src.learning.note_actions import NoteActionsService
    from rich.syntax import Syntax

    # Ask for diagram type
    console.print("\n[dim]Diagram type:[/dim]")
    console.print("  [yellow]1[/yellow] Flowchart (default)")
    console.print("  [yellow]2[/yellow] Sequence diagram")
    console.print("  [yellow]3[/yellow] State diagram")

    type_choice = Prompt.ask("[cyan]>_[/cyan]", choices=["1", "2", "3"], default="1")
    diagram_types = {"1": "flowchart", "2": "sequence", "3": "stateDiagram-v2"}
    diagram_type = diagram_types.get(type_choice, "flowchart")

    console.print(f"\n[cyan]Generating {diagram_type} diagram...[/cyan]")

    with session_scope() as session:
        service = NoteActionsService(session)
        success, result = service.generate_mermaid_diagram(note, diagram_type)

    if success:
        console.print()
        # Display Mermaid code with syntax highlighting
        syntax = Syntax(result.strip(), "mermaid", theme="monokai", line_numbers=False)
        console.print(syntax)
        console.print("\n[dim]Copy to https://mermaid.live to render[/dim]")
    else:
        console.print(f"[red]{result}[/red]")


def _handle_generate_atoms(note: dict) -> None:
    """Handle flashcard/cloze generation with dedup feedback."""
    import asyncio
    from src.db.database import session_scope
    from src.learning.note_actions import NoteActionsService, DuplicationPolicy

    console.print("\n[cyan]Generating flashcards and cloze cards...[/cyan]")
    console.print("[dim]Checking for duplicates (allows same concept in different formats)[/dim]\n")

    with session_scope() as session:
        service = NoteActionsService(session)
        result = asyncio.run(service.generate_atoms_for_note(note, atom_types=["flashcard", "cloze"]))

    # Display results
    console.print(f"[green]Inserted: {len(result.inserted)} new atoms[/green]")

    if result.skipped_exact:
        console.print(f"[yellow]Skipped: {len(result.skipped_exact)} exact duplicates[/yellow]")

    if result.allowed_cross_format:
        console.print(f"[cyan]Cross-format: {len(result.allowed_cross_format)} (multiple retention paths)[/cyan]")

    if result.prompted_borderline:
        console.print(f"\n[yellow]Borderline duplicates: {len(result.prompted_borderline)}[/yellow]")
        console.print("[dim]These have 70-85% similarity to existing atoms:[/dim]\n")

        for i, (atom, dedup) in enumerate(result.prompted_borderline[:3], 1):
            console.print(f"  {i}. [dim]New:[/dim] {atom.front[:60]}...")
            console.print(f"     [dim]Existing ({dedup.similarity_score:.0%}):[/dim] {dedup.existing_front[:60]}...")
            console.print()

        # Ask user if they want to insert borderline atoms
        if Confirm.ask("[yellow]Insert borderline atoms anyway?[/yellow]", default=False):
            with session_scope() as session:
                service = NoteActionsService(session)
                inserted = service.insert_borderline_atoms(
                    result.prompted_borderline, note.get("section_id", "")
                )
                console.print(f"[green]Inserted {inserted} borderline atoms[/green]")

    if result.errors:
        for error in result.errors:
            console.print(f"[red]Error: {error}[/red]")


def _handle_create_anki_deck(note: dict) -> None:
    """Handle Anki filtered deck creation."""
    from src.db.database import session_scope
    from src.learning.note_actions import NoteActionsService

    console.print("\n[cyan]Creating Anki filtered deck...[/cyan]")

    with session_scope() as session:
        service = NoteActionsService(session)
        success, message = service.create_anki_filtered_deck(note)
        search_query = service.get_anki_search_query(note)

    if success:
        console.print(f"[green]{message}[/green]")
        console.print("[dim]Open Anki to study the filtered deck[/dim]")
    else:
        console.print(f"[red]{message}[/red]")
        # Show manual search query
        console.print(f"\n[dim]Manual search query: {search_query}[/dim]")


def _handle_rate_note(note: dict) -> None:
    """Handle note rating."""
    from src.learning.note_generator import mark_note_read

    console.print("\n[dim]Rate this note (1-5):[/dim]")
    rating = Prompt.ask("[cyan]Rating[/cyan]", default="")

    if rating.isdigit() and 1 <= int(rating) <= 5:
        try:
            mark_note_read(str(note.get("id")), rating=int(rating))
            console.print("[green]Rating saved![/green]")
        except Exception as e:
            console.print(f"[red]Failed to save rating: {e}[/red]")
    else:
        console.print("[yellow]Skipped rating[/yellow]")


def _browse_study_notes():
    """Browse and manage study notes."""
    from rich.markdown import Markdown
    from rich.table import Table
    from src.learning.note_generator import (
        get_qualified_notes,
        get_sections_needing_notes,
        mark_note_read,
        NoteGenerator,
    )

    console.print("\n[bold cyan]STUDY NOTES[/bold cyan]\n")

    # Get existing notes
    try:
        notes = get_qualified_notes()
        sections_needing = get_sections_needing_notes(min_errors=2)
    except Exception as e:
        console.print(f"[red]Error loading notes: {e}[/red]")
        return

    # Show stats
    console.print(f"[dim]Available notes: {len(notes)}[/dim]")
    console.print(f"[dim]Sections needing notes: {len(sections_needing)}[/dim]\n")

    # Sub-menu
    console.print("[cyan]1[/cyan] - View all notes")
    console.print("[cyan]2[/cyan] - View unread notes")
    console.print("[cyan]3[/cyan] - Generate notes for weak sections")
    console.print("[cyan]b[/cyan] - Back to hub")
    console.print()

    choice = Prompt.ask("[cyan]>_[/cyan]", choices=["1", "2", "3", "b"], default="b")

    if choice == "1":
        _view_notes_list(notes, all_notes=True)
    elif choice == "2":
        unread = [n for n in notes if n.get("read_count", 0) == 0]
        if unread:
            _view_notes_list(unread, all_notes=False)
        else:
            console.print("[green]No unread notes![/green]")
    elif choice == "3":
        _generate_notes_for_weak_sections(sections_needing)


def _view_notes_list(notes: list[dict], all_notes: bool = True):
    """View and navigate through notes."""
    from rich.markdown import Markdown
    from rich.table import Table
    from src.learning.note_generator import mark_note_read

    if not notes:
        console.print("[yellow]No notes available.[/yellow]")
        return

    # Show list
    table = Table(title="Study Notes", box=box.ROUNDED)
    table.add_column("#", style="cyan", width=4)
    table.add_column("Section", style="white", width=10)
    table.add_column("Title", style="white")
    table.add_column("Read", style="dim", width=6)

    for i, note in enumerate(notes, 1):
        read_status = "[green]✓[/green]" if note.get("read_count", 0) > 0 else "[yellow]○[/yellow]"
        table.add_row(
            str(i),
            str(note.get("section_id", "")),
            note.get("title", "")[:40],
            read_status,
        )

    console.print(table)
    console.print()

    # Allow selection
    console.print("[dim]Enter note number to read, or 'b' to go back[/dim]")
    selection = Prompt.ask("[cyan]>_[/cyan]", default="b")

    if selection.isdigit():
        idx = int(selection) - 1
        if 0 <= idx < len(notes):
            note = notes[idx]
            console.clear()

            # Display note
            panel = Panel(
                Markdown(note.get("content", "")),
                title=f"[bold cyan]{note.get('title', 'Study Note')}[/bold cyan]",
                subtitle=f"[dim]Section {note.get('section_id', '')}[/dim]",
                border_style="cyan",
                box=box.HEAVY,
                padding=(1, 2),
            )
            console.print(panel)

            # Mark as read
            try:
                mark_note_read(str(note.get("id")))
            except Exception:
                pass

            # Show actions menu
            _show_note_actions_menu(note)


def _show_signals_dashboard():
    """
    Show the learning signals dashboard.

    Displays:
    - Per-section accuracy by format (T/F vs MCQ vs Parsons)
    - Memorization suspects (high recognition, low transfer)
    - Note effectiveness (pre/post error rates)
    - Recommended actions per module
    """
    from src.learning.note_generator import get_note_quality_report

    console.print("\n[bold cyan]LOADING LEARNING SIGNALS...[/bold cyan]\n")

    transfer_data = []
    memorization_suspects = []
    note_effectiveness = []
    recommendations = []

    try:
        with engine.connect() as conn:
            # Get transfer testing data from the view we created
            try:
                result = conn.execute(text("""
                    SELECT
                        ccna_section_id as section_id,
                        avg_transfer_score as transfer_score,
                        avg_tf_accuracy as tf_accuracy,
                        avg_mcq_accuracy as mcq_accuracy,
                        avg_parsons_accuracy as parsons_accuracy,
                        total_atoms,
                        suspect_atoms
                    FROM v_section_transfer_analysis
                    WHERE avg_transfer_score IS NOT NULL
                    ORDER BY avg_transfer_score ASC NULLS LAST
                    LIMIT 10
                """))
                for row in result.fetchall():
                    transfer_data.append({
                        "section_id": row.section_id,
                        "transfer_score": float(row.transfer_score) if row.transfer_score else None,
                        "tf_accuracy": float(row.tf_accuracy) if row.tf_accuracy else None,
                        "mcq_accuracy": float(row.mcq_accuracy) if row.mcq_accuracy else None,
                        "parsons_accuracy": float(row.parsons_accuracy) if row.parsons_accuracy else None,
                    })
            except Exception as e:
                console.print(f"[dim]Transfer view not available: {e}[/dim]")

            # Get memorization suspects
            try:
                result = conn.execute(text("""
                    SELECT
                        la.ccna_section_id as section_id,
                        la.accuracy_by_type,
                        la.transfer_score
                    FROM learning_atoms la
                    WHERE la.memorization_suspect = TRUE
                    AND la.ccna_section_id IS NOT NULL
                    ORDER BY la.transfer_score ASC NULLS LAST
                    LIMIT 10
                """))
                for row in result.fetchall():
                    accuracy = row.accuracy_by_type or {}
                    tf_data = accuracy.get("true_false", {})
                    parsons_data = accuracy.get("parsons", {})

                    tf_acc = 0.0
                    if tf_data.get("total", 0) > 0:
                        tf_acc = tf_data.get("correct", 0) / tf_data["total"]

                    proc_acc = 0.0
                    if parsons_data.get("total", 0) > 0:
                        proc_acc = parsons_data.get("correct", 0) / parsons_data["total"]

                    memorization_suspects.append({
                        "section_id": row.section_id,
                        "tf_accuracy": tf_acc,
                        "procedural_accuracy": proc_acc,
                    })
            except Exception as e:
                console.print(f"[dim]Memorization suspects not available: {e}[/dim]")

            # Get note effectiveness from note quality report
            try:
                note_report = get_note_quality_report()
                for note in note_report[:10]:
                    if note.get("read_count", 0) > 0:
                        note_effectiveness.append({
                            "title": note.get("title", "Unknown"),
                            "improvement": note.get("improvement"),
                            "read_count": note.get("read_count", 0),
                        })
            except Exception as e:
                console.print(f"[dim]Note effectiveness not available: {e}[/dim]")

            # Generate recommendations based on signals
            try:
                # Sections with memorization suspects get high priority
                seen_modules = set()
                for suspect in memorization_suspects[:3]:
                    section_id = suspect.get("section_id", "")
                    if section_id and "." in section_id:
                        module = int(section_id.split(".")[0])
                        if module not in seen_modules:
                            seen_modules.add(module)
                            recommendations.append({
                                "module": module,
                                "action": "Deep practice needed",
                                "reason": "Recognition without understanding",
                                "priority": "high",
                            })

                # Sections with low transfer scores get medium priority
                for section in transfer_data[:3]:
                    if section.get("transfer_score") and section["transfer_score"] < 0.5:
                        section_id = section.get("section_id", "")
                        if section_id and "." in section_id:
                            module = int(section_id.split(".")[0])
                            if module not in seen_modules:
                                seen_modules.add(module)
                                recommendations.append({
                                    "module": module,
                                    "action": "Vary question types",
                                    "reason": "Low transfer score",
                                    "priority": "medium",
                                })

                # Get struggle zones for additional recommendations
                result = conn.execute(text("""
                    SELECT module_number, weight
                    FROM struggle_weights
                    WHERE weight > 0.5
                    ORDER BY weight DESC
                    LIMIT 5
                """))
                for row in result.fetchall():
                    if row.module_number not in seen_modules:
                        seen_modules.add(row.module_number)
                        recommendations.append({
                            "module": row.module_number,
                            "action": "Focus session",
                            "reason": f"Struggle weight: {row.weight:.1f}",
                            "priority": "medium" if row.weight > 0.7 else "low",
                        })
            except Exception as e:
                console.print(f"[dim]Could not generate recommendations: {e}[/dim]")

    except Exception as e:
        console.print(f"[red]Error loading signals: {e}[/red]")
        return

    # Render the dashboard
    dashboard = render_signals_dashboard(
        transfer_data=transfer_data,
        memorization_suspects=memorization_suspects,
        note_effectiveness=note_effectiveness,
        recommendations=recommendations,
    )
    console.print(dashboard)


def _generate_notes_for_weak_sections(sections: list[dict]):
    """Generate notes for sections that need them."""
    from src.learning.note_generator import NoteGenerator

    if not sections:
        console.print("[green]No sections need notes right now![/green]")
        return

    console.print(f"\n[yellow]Found {len(sections)} sections needing notes:[/yellow]\n")

    for s in sections[:5]:
        existing = "[green]has note[/green]" if s.get("existing_note_id") else "[yellow]needs note[/yellow]"
        console.print(f"  • {s.get('section_id')}: {s.get('section_title', '')[:30]} - {existing}")

    console.print()

    if Confirm.ask("Generate notes for these sections?", default=True):
        generator = NoteGenerator()

        for s in sections[:5]:
            if s.get("existing_note_id"):
                continue  # Skip sections with existing notes

            console.print(f"\n[cyan]Generating note for {s.get('section_id')}...[/cyan]")

            result = generator.generate_note(section_id=s.get("section_id", ""))

            if result.success:
                console.print(f"[green]✓ Generated: {result.title}[/green]")
            else:
                console.print(f"[yellow]⚠ {result.error}[/yellow]")

        console.print("\n[green]Done generating notes![/green]")


@cortex_app.command("start")
def cortex_start(
    limit: int = typer.Option(20, help="Atoms per session"),
    quick: bool = typer.Option(
        False,
        "--quick", "-q",
        help="Skip hub, start adaptive session immediately",
    ),
):
    """
    Launch the Cortex study hub.

    The hub shows your progress, struggle zones, and lets you:
    - Start adaptive or war mode sessions
    - View and manage struggle weights
    - Configure modules and session size
    - Resume previous sessions

    Use --quick to skip the hub and start immediately.

    Examples:
        nls cortex start           # Open interactive hub
        nls cortex start --quick   # Start session immediately
    """
    if quick:
        # Quick mode: skip hub, start adaptive session immediately
        _ensure_struggles_imported()
        module_list = list(range(1, 18))
        session = CortexSession(modules=module_list, limit=limit, war_mode=False)
        session.run()
    else:
        # Interactive hub
        _run_interactive_hub(initial_limit=limit)


@cortex_app.command("war")
def cortex_war(
    limit: int = typer.Option(25, help="Notes to pull into the cram deck"),
):
    """Quick war mode (cram) session - skips hub."""
    _ensure_struggles_imported()
    module_list = list(range(11, 18))
    session = CortexSession(modules=module_list, limit=limit, war_mode=True)
    session.run()


@cortex_app.command("sync")
def cortex_sync(
    push: bool = typer.Option(False, "--push", "-p", help="Push atoms TO Anki"),
    pull: bool = typer.Option(True, "--pull/--no-pull", help="Pull stats FROM Anki"),
    dry_run: bool = typer.Option(False, "--dry-run", "-n", help="Preview without changes"),
):
    """
    Sync with Anki (bidirectional).

    Default: Pull FSRS stats FROM Anki to update mastery scores.
    --push: Also push new/updated atoms TO Anki.

    Examples:
        cortex sync              # Pull stats from Anki
        cortex sync --push       # Full bidirectional sync
        cortex sync --dry-run    # Preview what would sync
    """
    from src.anki.anki_client import AnkiClient
    from src.anki.pull_service import pull_review_stats
    from src.delivery.cortex_visuals import CortexSpinner

    client = AnkiClient()

    if not client.check_connection():
        console.print("[red]Cannot connect to Anki.[/red]")
        console.print("[dim]Ensure Anki is running with AnkiConnect addon.[/dim]")
        raise typer.Exit(1)

    results = {}

    # Push first if requested
    if push:
        from src.anki.push_service import push_clean_atoms

        with CortexSpinner(console, "Pushing atoms to Anki..."):
            push_result = push_clean_atoms(anki_client=client, dry_run=dry_run)
        results["push"] = push_result
        console.print(f"[green]✓[/green] Push: {push_result.get('created', 0)} created, {push_result.get('updated', 0)} updated")

    # Pull stats
    if pull:
        with CortexSpinner(console, "Pulling FSRS stats from Anki..."):
            pull_result = pull_review_stats(anki_client=client, dry_run=dry_run)
        results["pull"] = pull_result
        console.print(f"[green]✓[/green] Pull: {pull_result.get('atoms_updated', 0)} atoms updated")

    if dry_run:
        console.print("[dim](Dry run - no changes made)[/dim]")

    console.print("\n[bold green]Sync complete![/bold green]")


@cortex_app.command("resume")
def cortex_resume():
    """
    Resume a previously saved study session.

    Sessions are auto-saved every 5 questions and when you press Ctrl+C.
    Sessions expire after 24 hours.
    """
    session = CortexSession.resume_latest()

    if not session:
        console.print(
            Panel(
                "[yellow]No saved session found[/yellow]\n\n"
                "Start a new session with: [cyan]nls cortex start[/cyan]",
                border_style=Style(color=CORTEX_THEME["warning"]),
                box=box.ROUNDED,
            )
        )
        return

    # Show session info
    state = session._session_state
    console.print(
        Panel(
            f"[cyan]Found saved session[/cyan]\n\n"
            f"Mode: [bold]{state.mode.upper()}[/bold]\n"
            f"Started: {state.started_at[:19]}\n"
            f"Progress: {state.correct + state.incorrect} completed, "
            f"{len(state.atoms_remaining)} remaining\n"
            f"Score: {state.correct} correct, {state.incorrect} incorrect",
            border_style=Style(color=CORTEX_THEME["accent"]),
            box=box.ROUNDED,
        )
    )

    if Confirm.ask("Resume this session?", default=True):
        session.run()
    else:
        if Confirm.ask("Delete the saved session?", default=False):
            session.delete_session()
            console.print("[dim]Session deleted[/dim]")


# =============================================================================
# PREFLIGHT / SYSTEM CHECK
# =============================================================================

@cortex_app.command("check")
def cortex_check():
    """
    Preflight check - verify system readiness before study session.

    Checks:
    - Database connection
    - Atom counts by type
    - Anki connection (if configured)
    - FSRS stats freshness
    - Struggle map configuration
    """
    from collections import Counter

    console.print()
    console.print(
        Panel(
            "[bold cyan]CORTEX PREFLIGHT CHECK[/bold cyan]",
            border_style=Style(color=CORTEX_THEME["primary"]),
            box=box.DOUBLE,
        )
    )
    console.print()

    all_ok = True
    warnings = []

    # 1. Database connection
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        console.print("[green][OK][/green] Database connection")
    except Exception as e:
        console.print(f"[red][FAIL][/red] Database connection: {e}")
        all_ok = False

    # 2. Atom counts by type
    try:
        with engine.connect() as conn:
            result = conn.execute(text("""
                SELECT atom_type, COUNT(*) as count
                FROM learning_atoms
                WHERE front IS NOT NULL
                GROUP BY atom_type
                ORDER BY count DESC
            """))
            rows = result.fetchall()

            total = sum(r[1] for r in rows)
            console.print(f"[green][OK][/green] {total:,} atoms available")

            # Show breakdown
            type_table = Table(box=box.SIMPLE, show_header=False, padding=(0, 2))
            type_table.add_column("Type", style="dim")
            type_table.add_column("Count", justify="right", style="cyan")

            for atom_type, count in rows:
                type_table.add_row(f"    {atom_type}", str(count))

            console.print(type_table)

            # Check minimum threshold
            if total < 100:
                warnings.append("Low atom count - consider generating more atoms")

    except Exception as e:
        console.print(f"[red][FAIL][/red] Atom count check: {e}")
        all_ok = False

    # 3. Anki sync status
    try:
        with engine.connect() as conn:
            result = conn.execute(text("""
                SELECT
                    COUNT(*) FILTER (WHERE anki_note_id IS NOT NULL) as synced,
                    COUNT(*) as total
                FROM learning_atoms
                WHERE atom_type IN ('flashcard', 'cloze')
            """))
            row = result.fetchone()
            synced, total_anki = row[0], row[1]

            if synced > 0:
                console.print(f"[green][OK][/green] Anki synced: {synced:,}/{total_anki:,} cards")
            else:
                console.print("[yellow][WARN][/yellow] No cards synced to Anki")
                warnings.append("Run 'nls sync anki-push' to sync cards to Anki")

    except Exception as e:
        console.print(f"[yellow][WARN][/yellow] Anki check skipped: {e}")

    # 4. FSRS stats freshness
    try:
        with engine.connect() as conn:
            result = conn.execute(text("""
                SELECT MAX(anki_last_review) FROM learning_atoms
                WHERE anki_last_review IS NOT NULL
            """))
            row = result.fetchone()
            last_review = row[0] if row else None

            if last_review:
                from datetime import datetime, timezone
                if isinstance(last_review, str):
                    last_review = datetime.fromisoformat(last_review.replace("Z", "+00:00"))

                now = datetime.now(timezone.utc)
                age = now - last_review.replace(tzinfo=timezone.utc) if last_review.tzinfo is None else now - last_review
                days_old = age.days

                if days_old <= 1:
                    console.print(f"[green][OK][/green] FSRS stats current (last sync: {days_old}d ago)")
                elif days_old <= 3:
                    console.print(f"[yellow][WARN][/yellow] FSRS stats {days_old} days old")
                    warnings.append(f"Run 'nls sync anki-pull' to update FSRS stats")
                else:
                    console.print(f"[yellow][WARN][/yellow] FSRS stats {days_old} days old")
                    warnings.append(f"FSRS stats are stale - run 'nls sync anki-pull'")
            else:
                console.print("[dim][--][/dim] No FSRS stats available")

    except Exception as e:
        console.print(f"[dim][--][/dim] FSRS check skipped: {e}")

    # 5. Struggle map
    try:
        settings = get_settings()
        struggle_modules = getattr(settings, "struggle_modules", None)
        if struggle_modules:
            modules_list = [int(m) for m in str(struggle_modules).split(",") if m.strip()]
            if modules_list:
                console.print(f"[green][OK][/green] Struggle map: modules {modules_list}")
            else:
                console.print("[dim][--][/dim] No struggle modules configured")
        else:
            console.print("[dim][--][/dim] No struggle modules configured")
    except Exception as e:
        console.print(f"[dim][--][/dim] Struggle map check skipped: {e}")

    # 6. Handler registration
    try:
        from src.cortex.atoms import HANDLERS
        handler_count = len(HANDLERS)
        console.print(f"[green][OK][/green] {handler_count} atom handlers registered")
    except Exception as e:
        console.print(f"[red][FAIL][/red] Handler check: {e}")
        all_ok = False

    # Summary
    console.print()
    if all_ok and not warnings:
        console.print(
            Panel(
                "[bold green]Ready to study![/bold green]\n\n"
                "Run [cyan]nls cortex start[/cyan] to begin",
                border_style=Style(color=CORTEX_THEME["success"]),
                box=box.ROUNDED,
            )
        )
    elif all_ok:
        warning_text = "\n".join(f"  - {w}" for w in warnings)
        console.print(
            Panel(
                f"[bold yellow]Ready with warnings:[/bold yellow]\n\n{warning_text}",
                border_style=Style(color=CORTEX_THEME["warning"]),
                box=box.ROUNDED,
            )
        )
    else:
        console.print(
            Panel(
                "[bold red]System check failed[/bold red]\n\n"
                "Fix the issues above before studying",
                border_style=Style(color=CORTEX_THEME["error"]),
                box=box.ROUNDED,
            )
        )
        raise typer.Exit(1)


# =============================================================================
# RETENTION-OPTIMIZED STUDY
# =============================================================================

@cortex_app.command("optimize")
def cortex_optimize(
    modules: Optional[str] = typer.Option(
        None,
        "--modules", "-m",
        help="Comma-separated modules to focus on",
    ),
    limit: int = typer.Option(20, help="Maximum atoms per session"),
    show_plan: bool = typer.Option(
        False,
        "--plan", "-p",
        help="Show study plan without starting session",
    ),
):
    """
    Start a retention-optimized study session.

    Uses FSRS-4 algorithm with:
    - Desirable difficulty calibration
    - Concept-aware interleaving
    - Struggle area prioritization
    - Reading suggestions for weak areas

    Examples:
        nls cortex optimize                    # Full adaptive session
        nls cortex optimize -m 11,14,15        # Focus on specific modules
        nls cortex optimize --plan             # Preview study plan
    """
    import json
    from pathlib import Path
    from src.study.retention_engine import RetentionEngine, estimate_study_time

    # Load struggle modules
    struggle_modules: set[int] = set()
    struggle_file = Path.home() / ".cortex" / "struggle_schema.json"
    if struggle_file.exists():
        try:
            with open(struggle_file, "r") as f:
                data = json.load(f)
                struggle_modules = {int(k) for k, v in data.items() if float(v) >= 0.5}
        except (FileNotFoundError, json.JSONDecodeError, KeyError, ValueError, TypeError):
            pass  # No struggle file or invalid format

    # Parse modules
    module_list = None
    if modules:
        module_list = [int(m.strip()) for m in modules.split(",") if m.strip().isdigit()]

    # Initialize retention engine
    engine_retention = RetentionEngine()

    # Get reading suggestions
    console.print()
    console.print(
        Panel(
            "[bold cyan]RETENTION-OPTIMIZED SESSION[/bold cyan]",
            border_style=Style(color=CORTEX_THEME["primary"]),
            box=box.DOUBLE,
        )
    )

    # Show reading suggestions
    suggestions = engine_retention.suggest_reading(module_list, struggle_modules)
    if suggestions:
        console.print("\n[bold yellow]Pre-Study Reading Suggestions:[/bold yellow]")
        console.print("[dim]Reading before testing improves encoding[/dim]\n")

        for s in suggestions[:3]:
            priority_color = {
                "critical": CORTEX_THEME["error"],
                "high": CORTEX_THEME["warning"],
                "medium": CORTEX_THEME["accent"],
            }.get(s["priority"], CORTEX_THEME["dim"])

            console.print(
                f"  [{s['priority'].upper()}] ",
                style=Style(color=priority_color),
                end="",
            )
            console.print(
                f"Module {s['module_number']}: {s['title'][:40]}",
                style=Style(color=CORTEX_THEME["white"]),
            )
            console.print(f"        {s['reason']}", style=STYLES["cortex_dim"])
            console.print(f"        [cyan]{s['command']}[/cyan]")
            console.print()

    # Get optimized atoms
    atoms = engine_retention.get_optimized_session(
        limit=limit,
        modules=module_list,
        struggle_modules=struggle_modules,
    )

    if not atoms:
        console.print(Panel(
            "[yellow]No atoms available for study[/yellow]\n\n"
            "[dim]Try running: nls sync all[/dim]",
            border_style=Style(color=CORTEX_THEME["warning"]),
        ))
        return

    # Show session summary
    overdue = sum(1 for a in atoms if a.get("source") == "overdue")
    due = sum(1 for a in atoms if a.get("source") == "due")
    new = sum(1 for a in atoms if a.get("source") == "new")
    avg_difficulty = sum(a.get("difficulty", 0.5) for a in atoms) / len(atoms)
    est_time = estimate_study_time(len(atoms), avg_difficulty)

    console.print("\n[bold]Session Plan:[/bold]")
    console.print(f"  Atoms: {len(atoms)} ({overdue} overdue, {due} due, {new} new)")
    console.print(f"  Est. Time: {est_time} minutes")
    console.print(f"  Avg. Difficulty: {avg_difficulty:.1%}")

    if struggle_modules:
        struggle_in_session = sum(
            1 for a in atoms if a.get("module_number") in struggle_modules
        )
        console.print(f"  Struggle Focus: {struggle_in_session}/{len(atoms)} atoms")

    console.print()

    if show_plan:
        # Show detailed plan
        console.print("[bold]Atom Queue:[/bold]\n")
        for i, atom in enumerate(atoms[:10], 1):
            source_color = {
                "overdue": CORTEX_THEME["error"],
                "due": CORTEX_THEME["warning"],
                "new": CORTEX_THEME["accent"],
            }.get(atom.get("source"), CORTEX_THEME["dim"])

            console.print(
                f"  {i:2}. [{atom['source']:7}] ",
                style=Style(color=source_color),
                end="",
            )
            console.print(
                f"[{atom['atom_type']:10}] ",
                style=STYLES["cortex_dim"],
                end="",
            )
            console.print(
                f"M{atom['module_number']:02} ",
                style=STYLES["cortex_accent"],
                end="",
            )
            console.print(
                f"{atom['front'][:40]}...",
                style=Style(color=CORTEX_THEME["white"]),
            )

        if len(atoms) > 10:
            console.print(f"\n  ... and {len(atoms) - 10} more atoms")

        console.print("\n[dim]Run without --plan to start the session[/dim]")
        return

    # Start session
    if not Confirm.ask("\n[cyan]Start optimized session?[/cyan]", default=True):
        return

    # Run study session with retention engine
    session = CortexSession(
        modules=module_list or list(range(1, 18)),
        limit=limit,
        war_mode=False,
        atoms_override=atoms,  # Use pre-optimized atoms
    )
    session.run()


@cortex_app.command("suggest")
def cortex_suggest():
    """
    Get personalized study suggestions based on your performance.

    Shows:
    - Sections to re-read (high lapse rate)
    - Topics for immediate review (overdue)
    - Optimal next study focus
    """
    import json
    from pathlib import Path
    from src.study.retention_engine import RetentionEngine

    # Load struggle modules
    struggle_modules: set[int] = set()
    struggle_file = Path.home() / ".cortex" / "struggle_schema.json"
    if struggle_file.exists():
        try:
            with open(struggle_file, "r") as f:
                data = json.load(f)
                struggle_modules = {int(k) for k, v in data.items() if float(v) >= 0.5}
        except (FileNotFoundError, json.JSONDecodeError, KeyError, ValueError, TypeError):
            pass  # No struggle file or invalid format

    engine_retention = RetentionEngine()

    console.print()
    console.print(
        Panel(
            "[bold cyan]PERSONALIZED STUDY SUGGESTIONS[/bold cyan]",
            border_style=Style(color=CORTEX_THEME["primary"]),
            box=box.DOUBLE,
        )
    )

    # Reading suggestions
    suggestions = engine_retention.suggest_reading(None, struggle_modules)

    if suggestions:
        console.print("\n[bold]Recommended Reading:[/bold]")
        console.print("[dim]These sections have high error rates - re-read to strengthen encoding[/dim]\n")

        for s in suggestions:
            priority_color = {
                "critical": CORTEX_THEME["error"],
                "high": CORTEX_THEME["warning"],
                "medium": CORTEX_THEME["accent"],
            }.get(s["priority"], CORTEX_THEME["dim"])

            console.print(Panel(
                f"[bold]Module {s['module_number']}: {s['title']}[/bold]\n\n"
                f"Priority: [{s['priority'].upper()}]\n"
                f"Reason: {s['reason']}\n\n"
                f"[cyan]{s['command']}[/cyan]",
                border_style=Style(color=priority_color),
                box=box.ROUNDED,
            ))
    else:
        console.print("\n[green]No urgent reading suggestions - your encoding is solid![/green]")

    # Check for overdue reviews
    with engine.connect() as conn:
        result = conn.execute(text("""
            SELECT COUNT(*) as overdue_count
            FROM learning_atoms
            WHERE atom_type IN ('mcq', 'true_false', 'parsons', 'numeric')
              AND anki_due_date < CURRENT_DATE
        """))
        overdue_count = result.fetchone()[0]

    if overdue_count > 0:
        console.print(f"\n[bold yellow]Overdue Reviews: {overdue_count} atoms[/bold yellow]")
        console.print("[dim]Run 'nls cortex optimize' to prioritize these[/dim]")

    # Struggle area focus
    if struggle_modules:
        console.print(f"\n[bold]Your Struggle Areas:[/bold] Modules {sorted(struggle_modules)}")
        console.print("[dim]These modules get extra priority in adaptive sessions[/dim]")

    console.print("\n[bold]Recommended Actions:[/bold]")
    console.print("  1. Read suggested sections above")
    console.print("  2. Run: [cyan]nls cortex optimize[/cyan]")
    console.print("  3. Review progress: [cyan]nls cortex stats[/cyan]")


# =============================================================================
# GOOGLE CALENDAR COMMANDS
# =============================================================================

@cortex_app.command("schedule")
def cortex_schedule(
    time_str: str = typer.Option(
        ...,
        "--time", "-t",
        help="When to schedule (e.g., 'tomorrow 9am', '2025-12-06 14:00')",
    ),
    duration: int = typer.Option(
        60,
        "--duration", "-d",
        help="Session duration in minutes",
    ),
    modules: Optional[str] = typer.Option(
        None,
        "--modules", "-m",
        help="Comma-separated modules (default: 11-17)",
    ),
    cram: bool = typer.Option(
        False,
        "--cram",
        help="Use cram mode modules (11-17)",
    ),
):
    """
    Schedule a study session on Google Calendar.

    Examples:
        nls cortex schedule --time "tomorrow 9am" --duration 60
        nls cortex schedule -t "2025-12-06 14:00" -d 90 --modules 11,12,13
        nls cortex schedule -t "saturday 10am" --cram
    """
    # Parse the time string
    try:
        start_time = date_parser.parse(time_str, fuzzy=True)
        # If time is in the past today, assume tomorrow
        if start_time < datetime.now():
            start_time += timedelta(days=1)
    except Exception as e:
        console.print(Panel(
            f"[bold red]Could not parse time:[/bold red] {time_str}\n\n"
            "Try formats like:\n"
            "  - 'tomorrow 9am'\n"
            "  - 'saturday 14:00'\n"
            "  - '2025-12-06 10:00'",
            border_style=Style(color=CORTEX_THEME["error"]),
            box=box.HEAVY,
        ))
        raise typer.Exit(code=1)

    # Determine modules
    if cram:
        module_list = list(range(11, 18))
    elif modules:
        module_list = _parse_module_list(modules, default=range(11, 18))
    else:
        module_list = list(range(11, 18))

    # Initialize calendar
    calendar = CortexCalendar()

    if not calendar.is_available:
        console.print(Panel(
            "[bold red]Google Calendar libraries not installed.[/bold red]\n\n"
            "Run: pip install google-auth google-auth-oauthlib google-api-python-client",
            border_style=Style(color=CORTEX_THEME["error"]),
            box=box.HEAVY,
        ))
        raise typer.Exit(code=1)

    if not calendar.has_credentials:
        console.print(calendar.get_setup_instructions())
        raise typer.Exit(code=1)

    # Authenticate
    console.print(Panel(
        "[cyan]Connecting to Google Calendar...[/cyan]",
        border_style=Style(color=CORTEX_THEME["primary"]),
    ))

    if not calendar.authenticate():
        console.print(Panel(
            "[bold red]Authentication failed.[/bold red]\n\n"
            "Check that credentials.json is valid and try again.",
            border_style=Style(color=CORTEX_THEME["error"]),
            box=box.HEAVY,
        ))
        raise typer.Exit(code=1)

    # Book the session
    event_id = calendar.book_study_session(
        start_time=start_time,
        duration_minutes=duration,
        modules=module_list,
        title="Cortex War Room",
    )

    if event_id:
        modules_str = ", ".join(str(m) for m in module_list)
        end_time = start_time + timedelta(minutes=duration)

        result_text = Text()
        result_text.append("[*] SESSION SCHEDULED [*]\n\n", style=STYLES["cortex_primary"])
        result_text.append("Start: ", style=STYLES["cortex_dim"])
        result_text.append(f"{start_time.strftime('%A, %B %d at %I:%M %p')}\n", style=STYLES["cortex_accent"])
        result_text.append("Duration: ", style=STYLES["cortex_dim"])
        result_text.append(f"{duration} minutes\n", style=STYLES["cortex_accent"])
        result_text.append("Modules: ", style=STYLES["cortex_dim"])
        result_text.append(f"{modules_str}\n\n", style=STYLES["cortex_accent"])
        result_text.append("Command to start:\n", style=STYLES["cortex_dim"])
        result_text.append(f"  nls cortex start --mode war --modules {modules_str}", style=STYLES["cortex_success"])

        console.print(Panel(
            Align.center(result_text),
            border_style=Style(color=CORTEX_THEME["success"]),
            box=box.DOUBLE,
            padding=(1, 2),
        ))
    else:
        console.print(Panel(
            "[bold red]Failed to create calendar event.[/bold red]",
            border_style=Style(color=CORTEX_THEME["error"]),
            box=box.HEAVY,
        ))
        raise typer.Exit(code=1)


@cortex_app.command("agenda")
def cortex_agenda(
    days: int = typer.Option(7, "--days", "-d", help="Days to look ahead"),
):
    """
    Show upcoming scheduled Cortex sessions.

    Examples:
        nls cortex agenda
        nls cortex agenda --days 14
    """
    calendar = CortexCalendar()

    if not calendar.is_available:
        console.print(Panel(
            "[bold yellow]Google Calendar not configured.[/bold yellow]\n\n"
            "Run: nls cortex schedule --help",
            border_style=Style(color=CORTEX_THEME["warning"]),
        ))
        return

    if not calendar.has_credentials:
        console.print(calendar.get_setup_instructions())
        return

    if not calendar.authenticate():
        console.print(Panel(
            "[bold red]Authentication failed.[/bold red]",
            border_style=Style(color=CORTEX_THEME["error"]),
        ))
        return

    sessions = calendar.get_upcoming_sessions(days=days)

    if not sessions:
        console.print(Panel(
            f"[dim]No Cortex sessions scheduled in the next {days} days.[/dim]\n\n"
            "Schedule one with:\n"
            "  nls cortex schedule --time 'tomorrow 9am' --duration 60",
            title="[bold cyan][*] CORTEX AGENDA[/bold cyan]",
            border_style=Style(color=CORTEX_THEME["secondary"]),
            box=box.HEAVY,
        ))
        return

    # Build agenda table
    table = Table(
        title=f"[bold cyan][*] CORTEX SESSIONS (Next {days} days)[/bold cyan]",
        box=box.HEAVY,
        border_style=Style(color=CORTEX_THEME["primary"]),
    )
    table.add_column("DATE", style=Style(color=CORTEX_THEME["accent"]))
    table.add_column("TIME", style=Style(color=CORTEX_THEME["white"]))
    table.add_column("DURATION", justify="right", style=Style(color=CORTEX_THEME["secondary"]))
    table.add_column("TITLE", style=Style(color=CORTEX_THEME["warning"]))

    for session in sessions:
        start = session.get("start")
        end = session.get("end")
        title = session.get("title", "Cortex Session")

        if start:
            try:
                start_dt = date_parser.parse(start)
                end_dt = date_parser.parse(end) if end else start_dt + timedelta(hours=1)
                duration = int((end_dt - start_dt).total_seconds() / 60)

                table.add_row(
                    start_dt.strftime("%a %b %d"),
                    start_dt.strftime("%I:%M %p"),
                    f"{duration} min",
                    title.replace("[*] ", ""),
                )
            except (ValueError, TypeError, AttributeError):
                table.add_row("?", "?", "?", title)  # Date parsing failed

    console.print(table)


# =============================================================================
# PROGRESS & STATS COMMANDS
# =============================================================================

def _format_progress_bar(score: float, width: int = 10) -> str:
    """Format a progress bar (ASCII-safe for Windows console)."""
    filled = int(score / 100 * width)
    empty = width - filled
    return "#" * filled + "-" * empty


@cortex_app.command("stats")
def cortex_stats():
    """
    Show comprehensive study statistics with ASI styling.

    Displays:
    - Section progress (total, completed, completion rate)
    - Atom mastery breakdown (mastered, learning, struggling, new)
    - Overall mastery score and total reviews
    - Session history (if available)
    """
    study_service = StudyService()

    try:
        stats = study_service.get_study_stats()
    except Exception as e:
        console.print(Panel(
            f"[bold red]Error loading stats:[/bold red] {e}",
            border_style=Style(color=CORTEX_THEME["error"]),
        ))
        return

    # Header
    header = Text()
    header.append("[*] CORTEX TELEMETRY [*]", style=STYLES["cortex_primary"])

    console.print(Panel(
        Align.center(header),
        border_style=Style(color=CORTEX_THEME["primary"]),
        box=box.DOUBLE,
    ))

    # Section Progress Table
    s = stats["sections"]
    section_table = Table(
        title="[bold cyan]SECTION PROGRESS[/bold cyan]",
        box=box.HEAVY,
        border_style=Style(color=CORTEX_THEME["secondary"]),
        show_header=False,
    )
    section_table.add_column("Metric", style=Style(color=CORTEX_THEME["dim"]))
    section_table.add_column("Value", justify="right", style=Style(color=CORTEX_THEME["white"]))

    section_table.add_row("Total Sections", str(s["total"]))
    section_table.add_row("Completed", f"[green]{s['completed']}[/green]")
    section_table.add_row("Completion Rate", f"[cyan]{s['completion_rate']}%[/cyan]")

    console.print(section_table)

    # Atom Mastery Table
    a = stats["atoms"]
    atom_table = Table(
        title="[bold cyan]ATOM MASTERY[/bold cyan]",
        box=box.HEAVY,
        border_style=Style(color=CORTEX_THEME["secondary"]),
        show_header=False,
    )
    atom_table.add_column("Status", style=Style(color=CORTEX_THEME["dim"]))
    atom_table.add_column("Count", justify="right")

    atom_table.add_row("Total Atoms", str(a["total"]))
    atom_table.add_row("[green]Mastered[/green]", f"[green]{a['mastered']}[/green]")
    atom_table.add_row("[yellow]Learning[/yellow]", f"[yellow]{a['learning']}[/yellow]")
    atom_table.add_row("[red]Struggling[/red]", f"[red]{a['struggling']}[/red]")
    atom_table.add_row("[dim]New[/dim]", f"[dim]{a['new']}[/dim]")

    console.print(atom_table)

    # Overall Mastery
    mastery = stats["mastery"]["average"]
    bar = _format_progress_bar(mastery, 20)
    mastery_color = CORTEX_THEME["success"] if mastery >= 80 else CORTEX_THEME["warning"] if mastery >= 60 else CORTEX_THEME["error"]

    mastery_text = Text()
    mastery_text.append("OVERALL MASTERY: ", style=STYLES["cortex_dim"])
    mastery_text.append(f"{bar} ", style=Style(color=mastery_color))
    mastery_text.append(f"{mastery:.1f}%", style=Style(color=mastery_color, bold=True))
    mastery_text.append(f"\n\nTotal Reviews: ", style=STYLES["cortex_dim"])
    mastery_text.append(f"{stats['mastery']['total_reviews']}", style=Style(color=CORTEX_THEME["accent"]))

    console.print(Panel(
        Align.center(mastery_text),
        border_style=Style(color=mastery_color),
        box=box.HEAVY,
    ))


@cortex_app.command("today")
def cortex_today():
    """
    Show today's study session summary.

    Displays:
    - Due reviews count
    - New atoms available
    - Remediation needs
    - Current module/section progress
    - Study streak
    """
    study_service = StudyService()

    try:
        summary = study_service.get_daily_summary()
    except Exception as e:
        console.print(Panel(
            f"[bold red]Error loading summary:[/bold red] {e}",
            border_style=Style(color=CORTEX_THEME["error"]),
        ))
        return

    # Build content
    content = Text()
    content.append("[*] DAILY BRIEFING [*]\n\n", style=STYLES["cortex_primary"])

    content.append(f"DATE: ", style=STYLES["cortex_dim"])
    content.append(f"{summary.date.strftime('%B %d, %Y')}\n\n", style=Style(color=CORTEX_THEME["accent"]))

    # Due Reviews
    content.append("DUE REVIEWS: ", style=Style(color=CORTEX_THEME["warning"]))
    content.append(f"{summary.due_reviews} cards", style=Style(color=CORTEX_THEME["white"], bold=True))
    if summary.due_reviews > 0:
        content.append(f" (~{summary.due_reviews // 2} min)\n", style=STYLES["cortex_dim"])
    else:
        content.append(" - All caught up!\n", style=STYLES["cortex_success"])

    # Progress
    pct = (summary.learned_count / max(1, summary.total_count)) * 100
    content.append("PROGRESS: ", style=Style(color=CORTEX_THEME["success"]))
    content.append(f"{summary.learned_count}/{summary.total_count} learned ({pct:.0f}%)\n", style=Style(color=CORTEX_THEME["white"], bold=True))

    # Remediation
    if summary.remediation_sections > 0:
        content.append("REMEDIATION: ", style=Style(color=CORTEX_THEME["error"]))
        content.append(f"{summary.remediation_atoms} cards ", style=Style(color=CORTEX_THEME["white"], bold=True))
        content.append(f"from {summary.remediation_sections} sections\n", style=STYLES["cortex_dim"])
    else:
        content.append("REMEDIATION: ", style=Style(color=CORTEX_THEME["success"]))
        content.append("None needed\n", style=STYLES["cortex_success"])

    content.append("\n")

    # Current Progress
    content.append("CURRENT: ", style=STYLES["cortex_dim"])
    content.append(f"Module {summary.current_module} - Section {summary.current_section}\n", style=Style(color=CORTEX_THEME["accent"]))

    # Mastery Bar
    bar = _format_progress_bar(summary.overall_mastery, 15)
    mastery_color = CORTEX_THEME["success"] if summary.overall_mastery >= 80 else CORTEX_THEME["warning"]
    content.append("MASTERY: ", style=STYLES["cortex_dim"])
    content.append(f"{bar} {summary.overall_mastery:.0f}%\n", style=Style(color=mastery_color))

    # Streak
    if summary.streak_days > 0:
        content.append("\n")
        content.append(f"[FIRE] STREAK: {summary.streak_days} days", style=Style(color=CORTEX_THEME["warning"], bold=True))

    # Estimated Time
    content.append(f"\n\nESTIMATED SESSION: ", style=STYLES["cortex_dim"])
    content.append(f"{summary.estimated_minutes} minutes", style=Style(color=CORTEX_THEME["accent"]))

    console.print(Panel(
        content,
        title="[bold cyan][*] CORTEX[/bold cyan]",
        border_style=Style(color=CORTEX_THEME["primary"]),
        box=box.HEAVY,
        padding=(1, 2),
    ))


@cortex_app.command("path")
def cortex_path():
    """
    Show full CCNA learning path with progress.

    Displays all 17 modules with:
    - Mastery percentage and progress bar
    - Section completion counts
    - Atom breakdown (mastered/learning/struggling/new)
    - Remediation warnings
    """
    study_service = StudyService()

    try:
        modules = study_service.get_module_summaries()
    except Exception as e:
        console.print(Panel(
            f"[bold red]Error loading path:[/bold red] {e}",
            border_style=Style(color=CORTEX_THEME["error"]),
        ))
        return

    if not modules:
        console.print(Panel(
            "[yellow]No module data found.[/yellow]",
            border_style=Style(color=CORTEX_THEME["warning"]),
        ))
        return

    # Header
    console.print(Panel(
        Align.center(Text("[*] CCNA LEARNING PATH [*]", style=STYLES["cortex_primary"])),
        border_style=Style(color=CORTEX_THEME["primary"]),
        box=box.DOUBLE,
    ))

    for mod in modules:
        # Determine status
        if mod.sections_needing_remediation > 0:
            status_icon = "[red][*] REMEDIATION[/red]"
            border_color = CORTEX_THEME["error"]
        elif mod.avg_mastery >= 90:
            status_icon = "[green][*] MASTERED[/green]"
            border_color = CORTEX_THEME["success"]
        elif mod.avg_mastery >= 70:
            status_icon = "[yellow][*] LEARNING[/yellow]"
            border_color = CORTEX_THEME["warning"]
        else:
            status_icon = "[dim][*] NEW[/dim]"
            border_color = CORTEX_THEME["dim"]

        bar = _format_progress_bar(mod.avg_mastery, 15)

        content = Text()
        content.append(f"{bar} ", style=Style(color=border_color))
        content.append(f"{mod.avg_mastery:.0f}%  ", style=Style(color=border_color, bold=True))
        content.append(f"({mod.sections_completed}/{mod.total_sections} sections)\n", style=STYLES["cortex_dim"])

        if mod.atoms_total > 0:
            content.append(f"[green]{mod.atoms_mastered}[/green] mastered | ", style="")
            content.append(f"[yellow]{mod.atoms_learning}[/yellow] learning | ", style="")
            content.append(f"[red]{mod.atoms_struggling}[/red] struggling | ", style="")
            content.append(f"[dim]{mod.atoms_new}[/dim] new", style="")

        console.print(Panel(
            content,
            title=f"[bold cyan]Module {mod.module_number}:[/bold cyan] {mod.title}  {status_icon}",
            border_style=Style(color=border_color),
            box=box.ROUNDED,
            padding=(0, 1),
        ))


@cortex_app.command("remediation")
def cortex_remediation():
    """
    Show sections needing remediation.

    Lists all sections with low mastery scores that need
    focused review, sorted by priority.
    """
    study_service = StudyService()

    try:
        sections = study_service.get_remediation_sections()
    except Exception as e:
        console.print(Panel(
            f"[bold red]Error loading remediation:[/bold red] {e}",
            border_style=Style(color=CORTEX_THEME["error"]),
        ))
        return

    if not sections:
        console.print(Panel(
            Align.center(Text("[*] ALL CLEAR [*]\n\nNo sections need remediation!\nGreat job keeping up with your studies.", style=STYLES["cortex_success"])),
            border_style=Style(color=CORTEX_THEME["success"]),
            box=box.DOUBLE,
        ))
        return

    # Header
    header = Text()
    header.append(f"[*] REMEDIATION QUEUE: {len(sections)} sections [*]", style=STYLES["cortex_error"])

    console.print(Panel(
        Align.center(header),
        border_style=Style(color=CORTEX_THEME["error"]),
        box=box.DOUBLE,
    ))

    # Build table
    table = Table(
        box=box.HEAVY,
        border_style=Style(color=CORTEX_THEME["error"]),
    )
    table.add_column("SECTION", style=Style(color=CORTEX_THEME["accent"]))
    table.add_column("TITLE", max_width=40)
    table.add_column("MASTERY", justify="right")
    table.add_column("REASON", style=Style(color=CORTEX_THEME["warning"]))

    for section in sections[:15]:
        bar = _format_progress_bar(section.mastery_score, 8)
        table.add_row(
            section.section_id,
            section.title[:38] + "..." if len(section.title) > 38 else section.title,
            f"{bar} {section.mastery_score:.0f}%",
            section.remediation_reason or "combined",
        )

    console.print(table)

    if len(sections) > 15:
        console.print(f"\n[dim]... and {len(sections) - 15} more sections[/dim]")

    # Suggest action
    console.print(Panel(
        f"Run [cyan]nls cortex start --mode war[/cyan] to focus on weak areas",
        border_style=Style(color=CORTEX_THEME["secondary"]),
    ))


@cortex_app.command("module")
def cortex_module(
    module_num: int = typer.Argument(..., help="Module number (1-17)"),
    expand: bool = typer.Option(False, "--expand", "-e", help="Expand with prerequisite graph"),
):
    """
    Show detailed progress for a specific module.

    Examples:
        nls cortex module 11
        nls cortex module 11 --expand
    """
    if module_num < 1 or module_num > 17:
        console.print(Panel(
            "[bold red]Module must be between 1 and 17[/bold red]",
            border_style=Style(color=CORTEX_THEME["error"]),
        ))
        return

    study_service = StudyService()

    try:
        sections = study_service.get_section_details(module_num)
    except Exception as e:
        console.print(Panel(
            f"[bold red]Error loading module:[/bold red] {e}",
            border_style=Style(color=CORTEX_THEME["error"]),
        ))
        return

    if not sections:
        console.print(Panel(
            f"[yellow]No sections found for Module {module_num}[/yellow]",
            border_style=Style(color=CORTEX_THEME["warning"]),
        ))
        return

    module_titles = {
        1: "Networking Today", 2: "Basic Switch and End Device Configuration",
        3: "Protocols and Models", 4: "Physical Layer", 5: "Number Systems",
        6: "Data Link Layer", 7: "Ethernet Switching", 8: "Network Layer",
        9: "Address Resolution", 10: "Basic Router Configuration",
        11: "IPv4 Addressing", 12: "IPv6 Addressing", 13: "ICMP",
        14: "Transport Layer", 15: "Application Layer",
        16: "Network Security Fundamentals", 17: "Build a Small Network",
    }

    title = module_titles.get(module_num, f"Module {module_num}")

    # Header
    console.print(Panel(
        Align.center(Text(f"[*] MODULE {module_num}: {title} [*]", style=STYLES["cortex_primary"])),
        border_style=Style(color=CORTEX_THEME["primary"]),
        box=box.DOUBLE,
    ))

    # Show sections
    for section in sections:
        bar = _format_progress_bar(section.mastery_score, 10)

        if section.is_mastered:
            status = "[green][*] MASTERED[/green]"
            border_color = CORTEX_THEME["success"]
        elif section.needs_remediation:
            status = "[red][*] REMEDIATION[/red]"
            border_color = CORTEX_THEME["error"]
        else:
            status = ""
            border_color = CORTEX_THEME["secondary"]

        content = Text()
        content.append(f"{bar} {section.mastery_score:.0f}%\n", style=Style(color=border_color))

        if section.atoms_total > 0:
            content.append(f"[green]{section.atoms_mastered}[/green]/", style="")
            content.append(f"[yellow]{section.atoms_learning}[/yellow]/", style="")
            content.append(f"[red]{section.atoms_struggling}[/red]/", style="")
            content.append(f"[dim]{section.atoms_new}[/dim] atoms", style="")

        if section.needs_remediation and section.remediation_reason:
            content.append(f"\n[red]Reason: {section.remediation_reason}[/red]", style="")

        console.print(Panel(
            content,
            title=f"[cyan]{section.section_id}[/cyan] {section.title}  {status}",
            border_style=Style(color=border_color),
            box=box.ROUNDED,
            padding=(0, 1),
        ))

    # Show expansion if requested
    if expand:
        console.print(Panel(
            "[dim]Prerequisite expansion coming soon...[/dim]",
            border_style=Style(color=CORTEX_THEME["dim"]),
        ))


@cortex_app.command("read")
def cortex_read(
    module_num: int = typer.Argument(..., help="Module number (1-17)"),
    section: Optional[str] = typer.Option(None, "--section", "-s", help="Specific section ID (e.g., '11.2')"),
    toc: bool = typer.Option(False, "--toc", "-t", help="Show table of contents only"),
    search: Optional[str] = typer.Option(None, "--search", "-q", help="Search for keyword in module"),
    no_pager: bool = typer.Option(False, "--no-pager", help="Disable paging for long content"),
):
    """
    Read CCNA source material for a module.

    Re-read sections to reinforce learning before or after quiz sessions.

    Examples:
        nls cortex read 11                      # Read entire module 11
        nls cortex read 11 --toc                # Show table of contents
        nls cortex read 11 --section 11.2       # Read specific section
        nls cortex read 11 --search "subnet"    # Search within module
    """
    from pathlib import Path
    import json

    from src.content.reader import ContentReader
    from src.delivery.cortex_visuals import (
        render_module_header,
        render_section_header,
        render_section_content,
        render_toc,
        render_search_results,
        render_reading_nav,
    )

    # Validate module number
    if module_num < 1 or module_num > 17:
        console.print(Panel(
            "[bold red]Module must be between 1 and 17[/bold red]",
            border_style=Style(color=CORTEX_THEME["error"]),
        ))
        return

    # Initialize reader
    reader = ContentReader()

    # Check if module exists
    module = reader.get_module(module_num)
    if not module:
        console.print(Panel(
            f"[bold red]Module {module_num} source file not found[/bold red]\n\n"
            f"[dim]Expected: docs/source-materials/CCNA/CCNA Module {module_num}.txt[/dim]",
            border_style=Style(color=CORTEX_THEME["error"]),
        ))
        return

    # Load struggle modules for highlighting
    struggle_modules: set[int] = set()
    struggle_file = Path.home() / ".cortex" / "struggle_schema.json"
    if struggle_file.exists():
        try:
            with open(struggle_file, "r") as f:
                data = json.load(f)
                struggle_modules = {int(k) for k, v in data.items() if float(v) >= 0.5}
        except (FileNotFoundError, json.JSONDecodeError, KeyError, ValueError, TypeError):
            pass  # No struggle file or invalid format

    # Handle search mode
    if search:
        results = reader.search(module_num, search)
        if not results:
            console.print(Panel(
                f"[yellow]No results found for '{search}' in Module {module_num}[/yellow]",
                border_style=Style(color=CORTEX_THEME["warning"]),
            ))
            return
        console.print(render_search_results(search, results, module_num))
        return

    # Handle TOC mode
    if toc:
        entries = reader.get_toc(module_num)
        console.print(render_toc(module_num, module.title, entries, struggle_modules))
        return

    # Handle section-specific reading
    if section:
        target_section = reader.get_section(module_num, section)
        if not target_section:
            console.print(Panel(
                f"[bold red]Section '{section}' not found in Module {module_num}[/bold red]\n\n"
                f"[dim]Use --toc to see available sections[/dim]",
                border_style=Style(color=CORTEX_THEME["error"]),
            ))
            return

        # Display single section
        console.print(render_module_header(module_num, module.title))

        section_num = reader._extract_section_number(target_section.id) or section
        header = render_section_header(section_num, target_section.title, target_section.level)
        content = render_section_content(
            target_section.content,
            key_terms=target_section.key_terms if target_section.key_terms else None,
            commands=target_section.commands if target_section.commands else None,
            level=target_section.level,
        )

        if no_pager:
            console.print(header)
            console.print(content)
        else:
            with console.pager():
                console.print(header)
                console.print(content)
        return

    # Default: Read entire module with paging
    console.print(render_module_header(module_num, module.title, module.description))

    all_sections = reader.get_all_sections_flat(module_num)

    if no_pager:
        # Output all content without paging
        for sec in all_sections:
            section_num = reader._extract_section_number(sec.id) or sec.id
            console.print(render_section_header(section_num, sec.title, sec.level))
            console.print(render_section_content(
                sec.content,
                key_terms=sec.key_terms if sec.key_terms else None,
                commands=sec.commands if sec.commands else None,
                level=sec.level,
            ))
    else:
        # Interactive paged reading
        current_idx = 0
        while True:
            sec = all_sections[current_idx]
            section_num = reader._extract_section_number(sec.id) or sec.id

            console.clear()
            console.print(render_module_header(module_num, module.title))
            console.print(render_section_header(section_num, sec.title, sec.level))
            console.print(render_section_content(
                sec.content,
                key_terms=sec.key_terms if sec.key_terms else None,
                commands=sec.commands if sec.commands else None,
                level=sec.level,
            ))
            console.print(render_reading_nav(
                section_num,
                has_prev=current_idx > 0,
                has_next=current_idx < len(all_sections) - 1,
            ))

            # Get navigation input
            choice = Prompt.ask(
                "",
                choices=["n", "p", "t", "q", ""],
                default="n",
                show_choices=False,
            )

            if choice == "q":
                break
            elif choice == "t":
                console.clear()
                entries = reader.get_toc(module_num)
                console.print(render_toc(module_num, module.title, entries, struggle_modules))
                Prompt.ask("[dim]Press Enter to continue reading[/dim]", default="")
            elif choice == "p" and current_idx > 0:
                current_idx -= 1
            elif choice in ("n", "") and current_idx < len(all_sections) - 1:
                current_idx += 1
            elif current_idx >= len(all_sections) - 1:
                console.print(Panel(
                    "[cyan]End of module. Press 'q' to quit or 'p' to go back.[/cyan]",
                    border_style=Style(color=CORTEX_THEME["accent"]),
                ))
                Prompt.ask("", default="")


# =============================================================================
# CORTEX 2.0: NEUROMORPHIC COMMANDS
# =============================================================================

@cortex_app.command("persona")
def cortex_persona():
    """
    Show your learner persona profile.

    Displays the dynamic cognitive profile including:
    - Processing speed classification
    - Knowledge type strengths/weaknesses
    - Mechanism effectiveness
    - Chronotype and peak hours
    - Learning velocity and acceleration
    """
    from src.adaptive.persona_service import PersonaService

    service = PersonaService()
    persona = service.get_persona()

    # Build content
    content = Text()
    content.append("[*] LEARNER PERSONA [*]\n\n", style=STYLES["cortex_primary"])

    # Processing Speed
    content.append("PROCESSING: ", style=STYLES["cortex_dim"])
    speed_display = persona.processing_speed.value.replace("_", " ").title()
    content.append(f"{speed_display}\n", style=Style(color=CORTEX_THEME["accent"], bold=True))

    # Chronotype
    content.append("CHRONOTYPE: ", style=STYLES["cortex_dim"])
    chrono_display = persona.chronotype.value.replace("_", " ").title()
    content.append(f"{chrono_display} ", style=Style(color=CORTEX_THEME["white"]))
    content.append(f"(peak: {persona.peak_performance_hour}:00)\n\n", style=STYLES["cortex_dim"])

    # Knowledge Strengths
    content.append("KNOWLEDGE TYPE STRENGTHS:\n", style=Style(color=CORTEX_THEME["secondary"]))
    for ktype in ["factual", "conceptual", "procedural", "strategic"]:
        score = getattr(persona, f"strength_{ktype}")
        bar = _format_progress_bar(score * 100, 10)
        color = CORTEX_THEME["success"] if score > 0.7 else CORTEX_THEME["warning"] if score > 0.4 else CORTEX_THEME["error"]
        content.append(f"  {ktype.capitalize():12s} ", style=STYLES["cortex_dim"])
        content.append(f"{bar} {score:.0%}\n", style=Style(color=color))

    content.append("\n")

    # Mechanism Effectiveness
    content.append("MECHANISM EFFECTIVENESS:\n", style=Style(color=CORTEX_THEME["secondary"]))
    for mech in ["retrieval", "discrimination", "elaboration"]:
        score = getattr(persona, f"effectiveness_{mech}")
        bar = _format_progress_bar(score * 100, 10)
        color = CORTEX_THEME["success"] if score > 0.7 else CORTEX_THEME["warning"] if score > 0.4 else CORTEX_THEME["error"]
        content.append(f"  {mech.capitalize():12s} ", style=STYLES["cortex_dim"])
        content.append(f"{bar} {score:.0%}\n", style=Style(color=color))

    content.append("\n")

    # Calibration
    content.append("CALIBRATION: ", style=STYLES["cortex_dim"])
    if persona.calibration_score > 0.65:
        content.append("Overconfident ", style=Style(color=CORTEX_THEME["warning"]))
        content.append("(needs more challenge)\n", style=STYLES["cortex_dim"])
    elif persona.calibration_score < 0.35:
        content.append("Underconfident ", style=Style(color=CORTEX_THEME["accent"]))
        content.append("(needs encouragement)\n", style=STYLES["cortex_dim"])
    else:
        content.append("Well-calibrated\n", style=Style(color=CORTEX_THEME["success"]))

    # Velocity
    content.append("\nLEARNING VELOCITY: ", style=STYLES["cortex_dim"])
    content.append(f"{persona.current_velocity:.1f} atoms/hour ", style=Style(color=CORTEX_THEME["accent"], bold=True))
    trend_color = CORTEX_THEME["success"] if persona.velocity_trend == "improving" else CORTEX_THEME["warning"]
    content.append(f"({persona.velocity_trend})\n", style=Style(color=trend_color))

    # Stats
    content.append(f"\nTOTAL STUDY: ", style=STYLES["cortex_dim"])
    content.append(f"{persona.total_study_hours:.1f} hours  ", style=Style(color=CORTEX_THEME["white"]))
    content.append(f"STREAK: {persona.current_streak_days} days", style=Style(color=CORTEX_THEME["warning"]))

    console.print(Panel(
        content,
        title="[bold cyan][*] CORTEX PERSONA[/bold cyan]",
        border_style=Style(color=CORTEX_THEME["primary"]),
        box=box.HEAVY,
        padding=(1, 2),
    ))


@cortex_app.command("diagnose")
def cortex_diagnose(
    atom_id: str = typer.Argument(None, help="Atom ID to diagnose (optional)"),
):
    """
    Run cognitive diagnosis on recent performance.

    Analyzes your recent interactions to identify:
    - Cognitive patterns (encoding, retrieval, discrimination errors)
    - Struggle patterns requiring remediation
    - Cognitive load levels
    - Recommended actions
    """
    from src.adaptive.neuro_model import (
        detect_struggle_pattern,
        compute_cognitive_load,
        CognitiveState,
        FailMode,
    )
    from src.adaptive.cognitive_model import diagnose_error

    study_service = StudyService()

    # Get recent history (mock - would come from study_service)
    # For now, show the diagnostic framework
    content = Text()
    content.append("[*] COGNITIVE DIAGNOSIS [*]\n\n", style=STYLES["cortex_primary"])

    content.append("FAIL MODE DETECTION:\n", style=Style(color=CORTEX_THEME["secondary"]))
    fail_modes = [
        ("ENCODING", "Hippocampus", "Memory never formed - needs elaboration"),
        ("RETRIEVAL", "CA3/CA1", "Memory exists but weak pathway - needs practice"),
        ("DISCRIMINATION", "Dentate Gyrus", "Confusing similar items - needs contrast training"),
        ("INTEGRATION", "P-FIT Network", "Facts don't connect - needs worked examples"),
        ("EXECUTIVE", "Prefrontal Cortex", "Impulsive/careless - needs slow down"),
        ("FATIGUE", "Global", "Cognitive exhaustion - needs rest"),
    ]

    for mode, region, remedy in fail_modes:
        content.append(f"  {mode:14s} ", style=Style(color=CORTEX_THEME["accent"]))
        content.append(f"({region:16s}) ", style=STYLES["cortex_dim"])
        content.append(f"{remedy}\n", style=Style(color=CORTEX_THEME["white"]))

    content.append("\n")
    content.append("Run a study session to collect diagnostic data.\n", style=STYLES["cortex_dim"])
    content.append("Diagnosis happens automatically during learning.", style=STYLES["cortex_dim"])

    console.print(Panel(
        content,
        title="[bold cyan][*] NEUROMORPHIC DIAGNOSIS[/bold cyan]",
        border_style=Style(color=CORTEX_THEME["secondary"]),
        box=box.HEAVY,
        padding=(1, 2),
    ))


@cortex_app.command("plm")
def cortex_plm(
    category: str = typer.Argument(None, help="Category to train on"),
    duration: int = typer.Option(5, "--duration", "-d", help="Training duration in minutes"),
):
    """
    Start a Perceptual Learning Module (PLM) drill.

    PLM trains rapid pattern recognition (<1000ms response times):
    - Classification: "Is this X or Y?"
    - Discrimination: "What type is this?"
    - Builds automatic recognition, not conscious recall

    Examples:
        nls cortex plm "chain rule"
        nls cortex plm --duration 10
    """
    from src.adaptive.perceptual_learning import PLMEngine, PLM_TARGET_MS

    content = Text()
    content.append("[*] PERCEPTUAL LEARNING MODULE [*]\n\n", style=STYLES["cortex_primary"])

    content.append("GOAL: ", style=STYLES["cortex_dim"])
    content.append(f"Response time < {PLM_TARGET_MS}ms with 90%+ accuracy\n\n", style=Style(color=CORTEX_THEME["accent"]))

    content.append("This mode trains AUTOMATIC pattern recognition:\n", style=Style(color=CORTEX_THEME["white"]))
    content.append("- Visual cortex processing, not frontal deliberation\n", style=STYLES["cortex_dim"])
    content.append("- High volume, rapid presentation\n", style=STYLES["cortex_dim"])
    content.append("- Interleaved confusable pairs\n", style=STYLES["cortex_dim"])

    if category:
        content.append(f"\nCategory: {category}\n", style=Style(color=CORTEX_THEME["accent"]))

    content.append(f"\nDuration: {duration} minutes\n", style=STYLES["cortex_dim"])
    content.append("\n[PLM session implementation coming soon]", style=Style(color=CORTEX_THEME["warning"]))

    console.print(Panel(
        content,
        title="[bold cyan][*] PLM DRILL[/bold cyan]",
        border_style=Style(color=CORTEX_THEME["primary"]),
        box=box.HEAVY,
        padding=(1, 2),
    ))


@cortex_app.command("tutor")
def cortex_tutor(
    topic: str = typer.Argument(None, help="Topic to discuss"),
):
    """
    Start a Socratic tutoring session with AI.

    Uses Gemini AI for personalized tutoring:
    - Guides you to answers, doesn't give them
    - Adapts to your learner persona
    - Scaffolding that fades over time

    Examples:
        nls cortex tutor "limits"
        nls cortex tutor "why does integration by parts work"
    """
    from src.integrations.vertex_tutor import VertexTutor, get_quick_hint
    from src.adaptive.neuro_model import FailMode

    content = Text()
    content.append("[*] SOCRATIC TUTOR [*]\n\n", style=STYLES["cortex_primary"])

    content.append("The AI tutor uses your persona to personalize explanations.\n\n", style=Style(color=CORTEX_THEME["white"]))

    content.append("TUTORING MODES:\n", style=Style(color=CORTEX_THEME["secondary"]))
    content.append("  SOCRATIC     - Guides with questions\n", style=STYLES["cortex_dim"])
    content.append("  ELABORATIVE  - Explains differently\n", style=STYLES["cortex_dim"])
    content.append("  CONTRASTIVE  - Compares similar concepts\n", style=STYLES["cortex_dim"])
    content.append("  PROCEDURAL   - Step-by-step walkthrough\n", style=STYLES["cortex_dim"])

    if topic:
        content.append(f"\nTopic: {topic}\n", style=Style(color=CORTEX_THEME["accent"]))

    content.append("\n[AI tutor integration coming soon]", style=Style(color=CORTEX_THEME["warning"]))
    content.append("\nRequires: GOOGLE_API_KEY environment variable", style=STYLES["cortex_dim"])

    console.print(Panel(
        content,
        title="[bold cyan][*] AI TUTOR[/bold cyan]",
        border_style=Style(color=CORTEX_THEME["primary"]),
        box=box.HEAVY,
        padding=(1, 2),
    ))


@cortex_app.command("smart-schedule")
def cortex_smart_schedule(
    days: int = typer.Option(7, "--days", "-d", help="Days to schedule"),
    hours: int = typer.Option(1, "--hours", "-h", help="Study hours per day"),
):
    """
    Generate an optimal study schedule based on your persona.

    Uses your chronotype and peak hours to:
    - Block optimal cognitive windows
    - Avoid low-energy periods
    - Balance deep work and review
    - Integrate with Google Calendar

    Examples:
        nls cortex smart-schedule --days 7 --hours 2
    """
    from src.adaptive.persona_service import PersonaService
    from src.integrations.google_calendar import CortexCalendar, StudyBlockType

    service = PersonaService()
    persona = service.get_persona()
    calendar = CortexCalendar()

    content = Text()
    content.append("[*] SMART SCHEDULING [*]\n\n", style=STYLES["cortex_primary"])

    content.append("PERSONA-BASED OPTIMIZATION:\n", style=Style(color=CORTEX_THEME["secondary"]))
    content.append(f"  Chronotype: {persona.chronotype.value.replace('_', ' ').title()}\n", style=STYLES["cortex_dim"])
    content.append(f"  Peak Hour: {persona.peak_performance_hour}:00\n", style=STYLES["cortex_dim"])
    content.append(f"  Low Energy: {persona.low_energy_hours}\n\n", style=STYLES["cortex_dim"])

    content.append("RECOMMENDED SCHEDULE:\n", style=Style(color=CORTEX_THEME["secondary"]))

    # Generate recommendations
    peak = persona.peak_performance_hour
    for day in range(min(days, 3)):  # Show first 3 days
        day_name = ["Today", "Tomorrow", "Day 3"][day]
        content.append(f"\n{day_name}:\n", style=Style(color=CORTEX_THEME["accent"]))
        content.append(f"  {peak}:00-{peak+1}:00  ", style=Style(color=CORTEX_THEME["white"]))
        content.append("DEEP WORK (new material)\n", style=Style(color=CORTEX_THEME["success"]))
        if hours > 1:
            review_hour = peak + 4 if peak + 4 < 22 else peak - 3
            content.append(f"  {review_hour}:00-{review_hour+1}:00  ", style=Style(color=CORTEX_THEME["white"]))
            content.append("REVIEW (spaced repetition)\n", style=Style(color=CORTEX_THEME["warning"]))

    content.append("\n")

    if calendar.is_available and calendar.has_credentials:
        content.append("Google Calendar: ", style=STYLES["cortex_dim"])
        content.append("Connected\n", style=Style(color=CORTEX_THEME["success"]))
        content.append("Run with --book to add events to calendar", style=STYLES["cortex_dim"])
    else:
        content.append("Google Calendar: ", style=STYLES["cortex_dim"])
        content.append("Not configured\n", style=Style(color=CORTEX_THEME["warning"]))
        content.append("Run: nls cortex schedule --help for setup", style=STYLES["cortex_dim"])

    console.print(Panel(
        content,
        title="[bold cyan][*] SMART SCHEDULE[/bold cyan]",
        border_style=Style(color=CORTEX_THEME["primary"]),
        box=box.HEAVY,
        padding=(1, 2),
    ))


@cortex_app.command("force-z")
def cortex_force_z():
    """
    Check for prerequisite gaps (Force Z analysis).

    Analyzes your knowledge graph to find:
    - Concepts you're trying to learn (X)
    - Prerequisites you're missing (Z)
    - Backtracking recommendations

    The "Force Z" algorithm ensures foundational knowledge
    is solid before building on it.
    """
    from src.adaptive.scheduler_rl import should_force_z, PREREQUISITE_THRESHOLD

    content = Text()
    content.append("[*] FORCE Z ANALYSIS [*]\n\n", style=STYLES["cortex_primary"])

    content.append("ALGORITHM:\n", style=Style(color=CORTEX_THEME["secondary"]))
    content.append("If trying to learn X but prerequisite Z has\n", style=STYLES["cortex_dim"])
    content.append(f"mastery < {PREREQUISITE_THRESHOLD:.0%}, FORCE BACKTRACK to Z.\n\n", style=STYLES["cortex_dim"])

    content.append("WHY THIS MATTERS:\n", style=Style(color=CORTEX_THEME["secondary"]))
    content.append("Building on weak foundations leads to:\n", style=Style(color=CORTEX_THEME["white"]))
    content.append("  - Integration errors (P-FIT failure)\n", style=STYLES["cortex_dim"])
    content.append("  - Increased cognitive load\n", style=STYLES["cortex_dim"])
    content.append("  - Frustration and abandonment\n\n", style=STYLES["cortex_dim"])

    content.append("During sessions, Force Z activates automatically.\n", style=Style(color=CORTEX_THEME["accent"]))
    content.append("The scheduler will backtrack when needed.", style=STYLES["cortex_dim"])

    console.print(Panel(
        content,
        title="[bold cyan][*] FORCE Z[/bold cyan]",
        border_style=Style(color=CORTEX_THEME["primary"]),
        box=box.HEAVY,
        padding=(1, 2),
    ))


@cortex_app.command("struggles")
def cortex_struggles(
    import_yaml: bool = typer.Option(
        False,
        "--import-yaml",
        help="Import struggles from struggles.yaml into database",
    ),
    show: bool = typer.Option(
        True,
        "--show", "-s",
        help="Show current struggle weights",
    ),
):
    """
    Manage struggle weights for prioritized study.

    Struggle zones are weak areas that need extra focus.
    They are defined in struggles.yaml and imported to the database.

    Examples:
        nls cortex struggles                   # Show current struggles
        nls cortex struggles --import-yaml     # Import from struggles.yaml
    """
    console.print()

    if import_yaml:
        console.print(
            Panel(
                "[bold cyan]IMPORTING STRUGGLE MAP[/bold cyan]",
                border_style=Style(color=CORTEX_THEME["primary"]),
                box=box.DOUBLE,
            )
        )
        console.print()

        result = _import_struggles_to_db()

        if result.get("errors"):
            for err in result["errors"]:
                console.print(f"[yellow]Warning: {err}[/yellow]")

        console.print(f"[green][OK][/green] Imported {result['imported']} struggle weights")
        console.print()

    if show:
        struggles = _get_struggle_stats()

        if not struggles:
            console.print(
                Panel(
                    "[yellow]No struggle weights in database[/yellow]\n\n"
                    "Run: [cyan]nls cortex struggles --import-yaml[/cyan]\n"
                    "to import from struggles.yaml",
                    border_style=Style(color=CORTEX_THEME["warning"]),
                    box=box.ROUNDED,
                )
            )
            return

        # Create heatmap data
        struggle_schema = {s["module_number"]: s["weight"] for s in struggles}
        console.print(create_struggle_heatmap(struggle_schema))

        # Detailed table
        table = Table(
            title="[bold cyan]STRUGGLE DETAILS[/bold cyan]",
            box=box.ROUNDED,
            border_style=Style(color=CORTEX_THEME["secondary"]),
        )
        table.add_column("Module", style="cyan", justify="center")
        table.add_column("Severity", justify="center")
        table.add_column("Weight", justify="right")
        table.add_column("Mastery", justify="right")
        table.add_column("Atoms", justify="right")
        table.add_column("Notes", max_width=30)

        severity_colors = {
            "critical": CORTEX_THEME["error"],
            "high": CORTEX_THEME["warning"],
            "medium": CORTEX_THEME["accent"],
            "low": CORTEX_THEME["dim"],
        }

        for s in struggles:
            severity_style = Style(color=severity_colors.get(s["severity"], CORTEX_THEME["dim"]))
            mastery_pct = s["avg_mastery"]
            mastery_style = Style(
                color=CORTEX_THEME["success"] if mastery_pct >= 70 else (
                    CORTEX_THEME["warning"] if mastery_pct >= 40 else CORTEX_THEME["error"]
                )
            )

            table.add_row(
                f"M{s['module_number']:02d}",
                Text(s["severity"].upper(), style=severity_style),
                f"{s['weight']:.2f}",
                Text(f"{mastery_pct:.0f}%", style=mastery_style),
                str(s["atom_count"]),
                s["notes"][:30] if s["notes"] else "",
            )

        console.print(table)


def main() -> None:
    cortex_app()


if __name__ == "__main__":
    main()
