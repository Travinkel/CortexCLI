"""
⚠️  DEPRECATED - Use `nls cortex` commands instead.

Interactive CLI Session for CCNA Learning Path.

This module is DEPRECATED. All functionality has been consolidated into
the Cortex CLI with the unified StudyService backend.

Migration Guide:
    OLD: nls (interactive shell)
    NEW: nls cortex <command>

    OLD: today
    NEW: nls cortex today

    OLD: stats
    NEW: nls cortex stats

    OLD: path
    NEW: nls cortex path

    OLD: module <n>
    NEW: nls cortex module <n>

    OLD: remediation
    NEW: nls cortex remediation

    OLD: quiz [count] [type]
    NEW: nls cortex start --mode adaptive

The new Cortex CLI provides:
- Unified StudyService backend (all interactions update FSRS)
- ASI-themed "Digital Neocortex" visual style
- Google Calendar integration
- Same core functionality with better UX

This file will be removed in a future release.
"""
from __future__ import annotations

import warnings
warnings.warn(
    "interactive.py is deprecated. Use 'nls cortex <command>' instead.",
    DeprecationWarning,
    stacklevel=2
)

import cmd
import sys
import threading
import time
from datetime import datetime
from typing import Optional

from rich import print as rprint
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt, Confirm, IntPrompt
from rich.table import Table
from rich.text import Text

console = Console()


class NLSShell(cmd.Cmd):
    """Interactive CCNA Learning Path shell."""

    intro = None  # We'll show custom intro
    prompt = "[nls] > "

    def __init__(self):
        super().__init__()
        self.study_service = None
        self.anki_client = None
        self.quiz_engine = None
        self.pomodoro_engine = None
        self.sync_thread = None
        self.sync_running = False
        self.last_sync = None
        self.sync_interval = 60  # seconds
        self.current_session = None

    def preloop(self):
        """Initialize services and show welcome screen."""
        self._show_welcome()
        self._init_services()
        self._start_background_sync()

    def postloop(self):
        """Clean up on exit."""
        self._stop_background_sync()
        rprint("\n[dim]Goodbye! Keep learning.[/dim]\n")

    def _show_welcome(self):
        """Display welcome banner."""
        console.clear()

        banner = Text()
        banner.append("CCNA Learning Path\n", style="bold cyan")
        banner.append("Interactive Study Session\n\n", style="dim")
        banner.append(f"Started: {datetime.now().strftime('%B %d, %Y at %H:%M')}\n")

        panel = Panel(
            banner,
            title="[bold]NLS[/bold]",
            border_style="blue",
            padding=(1, 2),
        )
        console.print(panel)

    def _init_services(self):
        """Initialize study service and Anki client."""
        rprint("[dim]Initializing services...[/dim]")

        try:
            from src.study.study_service import StudyService
            self.study_service = StudyService()
            rprint("  [green][OK][/green] Study service ready")
        except Exception as e:
            rprint(f"  [yellow][!][/yellow] Study service: {e}")

        try:
            from src.anki.anki_client import AnkiClient
            self.anki_client = AnkiClient()
            if self.anki_client.check_connection():
                rprint("  [green][OK][/green] Anki connected (flashcard/cloze)")
            else:
                rprint("  [yellow][!][/yellow] Anki not running (sync disabled)")
                self.anki_client = None
        except Exception as e:
            rprint(f"  [yellow][!][/yellow] Anki: {e}")
            self.anki_client = None

        try:
            from src.study.quiz_engine import QuizEngine
            from src.study.pomodoro_engine import PomodoroEngine
            self.quiz_engine = QuizEngine()
            self.pomodoro_engine = PomodoroEngine()
            rprint("  [green][OK][/green] Quiz engine ready (mcq/tf/matching/parsons)")
        except Exception as e:
            rprint(f"  [yellow][!][/yellow] Quiz engine: {e}")

        rprint("")

    def _start_background_sync(self):
        """Start background Anki sync thread."""
        if self.anki_client is None:
            return

        self.sync_running = True
        self.sync_thread = threading.Thread(target=self._sync_loop, daemon=True)
        self.sync_thread.start()
        rprint("[dim]Background sync started (every 60s)[/dim]\n")

    def _stop_background_sync(self):
        """Stop background sync thread."""
        self.sync_running = False
        if self.sync_thread:
            self.sync_thread.join(timeout=2)

    def _sync_loop(self):
        """Background sync loop."""
        while self.sync_running:
            try:
                self._do_sync(quiet=True)
                self.last_sync = datetime.now()
            except Exception:
                pass  # Silently handle sync errors
            time.sleep(self.sync_interval)

    def _do_sync(self, quiet: bool = False):
        """Perform Anki sync."""
        if self.anki_client is None:
            if not quiet:
                rprint("[yellow]Anki not connected[/yellow]")
            return

        if self.study_service:
            try:
                count = self.study_service.refresh_mastery()
                if not quiet:
                    rprint(f"[green][OK][/green] Synced mastery for {count} sections")
            except Exception as e:
                if not quiet:
                    rprint(f"[red]Sync error:[/red] {e}")

    # ========================================
    # STUDY COMMANDS
    # ========================================

    def do_plan(self, arg):
        """Plan a study session. Usage: plan <hours>  Example: plan 8"""
        if not arg:
            rprint("[yellow]Usage: plan <hours>[/yellow]")
            rprint("Example: plan 8  (plan 8-hour study session)")
            return

        try:
            hours = float(arg)
        except ValueError:
            rprint(f"[red]Invalid hours:[/red] {arg}")
            return

        if hours < 0.5 or hours > 16:
            rprint("[yellow]Hours should be between 0.5 and 16[/yellow]")
            return

        # Calculate session plan
        minutes = int(hours * 60)
        cards_per_hour = 60  # ~1 card per minute with review
        total_cards = int(hours * cards_per_hour)

        # Break into sessions (25 min focus + 5 min break = Pomodoro)
        pomodoros = int(minutes / 30)
        cards_per_pomo = total_cards // max(pomodoros, 1)

        rprint(f"\n[bold]Study Plan: {hours} hours[/bold]")
        rprint("=" * 50)
        rprint(f"\n[cyan]Time Breakdown:[/cyan]")
        rprint(f"  Total time: {hours} hours ({minutes} minutes)")
        rprint(f"  Pomodoro sessions: {pomodoros} x 25 min")
        rprint(f"  Break time: {pomodoros * 5} min total")

        rprint(f"\n[cyan]Card Targets:[/cyan]")
        rprint(f"  Due reviews first: ~{min(total_cards // 2, 200)} cards")
        rprint(f"  New content: ~{total_cards // 3} cards")
        rprint(f"  Remediation interleaved: ~{total_cards // 6} cards")

        rprint(f"\n[cyan]FSRS-Optimized Schedule:[/cyan]")
        rprint("  1. Morning (high retention): Hard conceptual cards")
        rprint("  2. Midday: Application/procedural cards")
        rprint("  3. Afternoon: Review due cards (stability refresh)")
        rprint("  4. Evening: Light review + new cards")

        rprint(f"\n[cyan]Filtered Deck Queries:[/cyan]")
        rprint("  [dim]Create these in Anki as dynamic views:[/dim]")
        rprint(f"  - Weakest 40:     prop:due is:review rated:30:1")
        rprint(f"  - High Priority:  (stability<7 AND lapses>0)")
        rprint(f"  - New Learning:   is:new")
        rprint(f"  - Bloom Apply:    tag:bloom:apply")
        rprint(f"  - Due Today:      prop:due<=0")

        rprint("\n[green]Ready to start![/green]")
        rprint("Run [cyan]quiz[/cyan] to start a quiz or [cyan]session[/cyan] for full pomodoro\n")

    def do_today(self, arg):
        """Show today's study session summary."""
        if not self.study_service:
            rprint("[red]Study service not available[/red]")
            return

        try:
            summary = self.study_service.get_daily_summary()
        except Exception as e:
            rprint(f"[red]Error:[/red] {e}")
            return

        content = Text()
        content.append(f"[DATE] {summary.date.strftime('%B %d, %Y')}\n\n", style="bold")
        content.append(f"[REVIEW] Due Reviews: ", style="cyan")
        content.append(f"{summary.due_reviews} cards", style="bold")
        if summary.due_reviews > 0:
            content.append(f" (est. {summary.due_reviews // 2} min)\n")
        else:
            content.append(" - All caught up!\n")

        content.append(f"[NEW] New Content: ", style="green")
        content.append(f"{summary.new_atoms_available} atoms available\n", style="bold")

        if summary.remediation_sections > 0:
            content.append(f"[!] Remediation: ", style="yellow")
            content.append(f"{summary.remediation_atoms} cards ", style="bold")
            content.append(f"from {summary.remediation_sections} sections\n")
        else:
            content.append("[OK] No remediation needed\n", style="green")

        content.append("\n")
        content.append(f"[>] Current: Module {summary.current_module} - Section {summary.current_section}\n")

        bar = self._format_progress_bar(summary.overall_mastery)
        content.append(f"[MASTERY] Overall: {bar} {summary.overall_mastery:.0f}%\n")

        if summary.streak_days > 0:
            content.append(f"[STREAK] {summary.streak_days} days\n", style="bold yellow")

        content.append(f"\n[TIME] Estimated session: {summary.estimated_minutes} minutes")

        panel = Panel(content, title="[bold]Today's Study Session[/bold]", border_style="blue")
        console.print(panel)

    def do_path(self, arg):
        """Show full CCNA learning path with progress."""
        if not self.study_service:
            rprint("[red]Study service not available[/red]")
            return

        try:
            modules = self.study_service.get_module_summaries()
        except Exception as e:
            rprint(f"[red]Error:[/red] {e}")
            return

        if not modules:
            rprint("[yellow]No module data found.[/yellow]")
            return

        rprint("\n[bold]CCNA Learning Path Progress[/bold]")
        rprint("=" * 70)

        for mod in modules:
            completion = (
                mod.sections_completed / mod.total_sections * 100
                if mod.total_sections > 0
                else 0
            )

            if mod.sections_needing_remediation > 0:
                status = "[red][!][/red]"
            elif completion >= 90:
                status = "[green][OK][/green]"
            else:
                status = ""

            rprint(f"\n[cyan]Module {mod.module_number}:[/cyan] {mod.title} {status}")

            bar = self._format_progress_bar(mod.avg_mastery)
            color = "green" if mod.avg_mastery >= 90 else "yellow" if mod.avg_mastery >= 70 else "red"
            rprint(f"  [{color}]{bar}[/{color}] {mod.avg_mastery:.0f}%  ", end="")
            rprint(f"[dim]({mod.sections_completed}/{mod.total_sections} sections)[/dim]")

            if mod.atoms_total > 0:
                rprint(
                    f"  [dim]Atoms: "
                    f"[green]{mod.atoms_mastered}[/green] mastered | "
                    f"[yellow]{mod.atoms_learning}[/yellow] learning | "
                    f"[red]{mod.atoms_struggling}[/red] struggling | "
                    f"[dim]{mod.atoms_new}[/dim] new[/dim]"
                )

        rprint("\n" + "=" * 70)

    def do_module(self, arg):
        """
        Show detailed progress for a specific module or multiple modules.

        Usage:
            module <n>              Show module sections and progress
            module <n> --expand     Show cross-module expansion via prerequisite graph
            module 1 2 3            Show activity path for multiple modules
            module 1 2 3 --expand   Expand multiple modules with prerequisites
            module 1 2 3 --anki-learn  Force cards into Anki learning queue
        """
        if not arg:
            rprint("[yellow]Usage: module <number(s)> [--expand] [--anki-learn][/yellow]")
            rprint("Example: module 3")
            rprint("         module 3 --expand")
            rprint("         module 1 2 3          (checkpoint exam prep)")
            rprint("         module 1 2 3 --expand (with prerequisites)")
            return

        # Parse args for flags
        parts = arg.split()
        expand_mode = "--expand" in parts or "-e" in parts
        anki_learn_mode = "--anki-learn" in parts or "-a" in parts

        # Remove flags from parts
        module_parts = [p for p in parts if not p.startswith("-")]

        # Parse module numbers
        module_numbers = []
        for p in module_parts:
            try:
                mod = int(p)
                if 1 <= mod <= 17:
                    module_numbers.append(mod)
                else:
                    rprint(f"[yellow]Skipping invalid module {mod} (must be 1-17)[/yellow]")
            except ValueError:
                rprint(f"[red]Invalid module number:[/red] {p}")
                return

        if not module_numbers:
            rprint("[red]No valid module numbers provided[/red]")
            return

        if not self.study_service:
            rprint("[red]Study service not available[/red]")
            return

        # Multi-module mode (2+ modules)
        if len(module_numbers) > 1 or expand_mode:
            self._show_multi_module_path(module_numbers, expand_mode, anki_learn_mode)
            return

        # Single module without --expand: show sections
        module_number = module_numbers[0]

        try:
            sections = self.study_service.get_section_details(module_number)
        except Exception as e:
            rprint(f"[red]Error:[/red] {e}")
            return

        if not sections:
            rprint(f"[yellow]No sections found for Module {module_number}[/yellow]")
            return

        module_titles = {
            1: "Networking Today", 2: "Basic Switch and End Device Configuration",
            3: "Protocols and Models", 4: "Physical Layer", 5: "Number Systems",
            6: "Data Link Layer", 7: "Ethernet Switching", 8: "Network Layer",
            9: "Address Resolution", 10: "Basic Router Configuration",
            11: "IPv4 Addressing", 12: "IPv6 Addressing", 13: "ICMP",
            14: "Transport Layer", 15: "Application Layer",
            16: "Network Security Fundamentals",
        }

        title = module_titles.get(module_number, f"Module {module_number}")
        rprint(f"\n[bold cyan]Module {module_number}: {title}[/bold cyan]")
        rprint("=" * 70)

        for section in sections:
            bar = self._format_progress_bar(section.mastery_score)
            status = ""
            if section.is_mastered:
                status = "[green][OK][/green]"
            elif section.needs_remediation:
                status = "[red][!][/red]"

            rprint(f"\n  +-- [bold]{section.section_id}[/bold] {section.title} {status}")
            rprint(f"  |   {bar} {section.mastery_score:.0f}%")

            if section.atoms_total > 0:
                rprint(
                    f"  |   [dim]"
                    f"[green]{section.atoms_mastered}[/green]/"
                    f"[yellow]{section.atoms_learning}[/yellow]/"
                    f"[red]{section.atoms_struggling}[/red]/"
                    f"{section.atoms_new} atoms[/dim]"
                )

            if section.needs_remediation:
                rprint(f"  |   [red]Needs remediation: {section.remediation_reason}[/red]")

    def _show_module_expansion(self, module_number: int):
        """
        Show cross-module expansion for a module via prerequisite graph.

        This finds all related concepts across all modules (up to 3 hops)
        and groups them by destination (Anki vs NLS).
        """
        rprint(f"\n[bold cyan]Expanding Module {module_number}[/bold cyan] (prerequisite graph, max 3 hops)")
        rprint("-" * 70)

        try:
            expanded = self.study_service.get_expanded_module_atoms(module_number, max_depth=3)
        except Exception as e:
            rprint(f"[red]Error:[/red] {e}")
            return

        # Show summary
        rprint(f"\n[bold]Expansion Summary:[/bold]")
        rprint(f"  Target module: {expanded.target_module}")
        rprint(f"  Concepts found: {expanded.concept_count}")
        rprint(f"  Modules touched: {expanded.modules_touched}")
        rprint(f"  Max chain depth: {expanded.prerequisite_chain_depth}")

        # Show Anki atoms (flashcard + cloze)
        rprint(f"\n[bold yellow]ANKI JOBS[/bold yellow] (flashcard + cloze)")
        rprint(f"  Total: {len(expanded.anki_atoms)} atoms")
        if expanded.anki_atoms:
            # Group by module
            by_module = {}
            for atom in expanded.anki_atoms:
                mod = atom.get("module_number", 0)
                by_module.setdefault(mod, []).append(atom)

            for mod in sorted(by_module.keys()):
                atoms = by_module[mod]
                fc_count = sum(1 for a in atoms if a["atom_type"] == "flashcard")
                cl_count = sum(1 for a in atoms if a["atom_type"] == "cloze")
                marker = "[cyan]*[/cyan]" if mod == module_number else " "
                rprint(f"  {marker} Module {mod}: {fc_count} flashcard, {cl_count} cloze")

        # Show NLS atoms (MCQ, T/F, Matching, Parsons)
        rprint(f"\n[bold green]NLS QUIZ JOBS[/bold green] (mcq, true_false, matching, parsons)")
        rprint(f"  Total: {len(expanded.quiz_atoms)} atoms")
        if expanded.quiz_atoms:
            # Group by type
            by_type = {}
            for atom in expanded.quiz_atoms:
                t = atom.get("atom_type", "unknown")
                by_type.setdefault(t, 0)
                by_type[t] += 1

            for t, count in sorted(by_type.items()):
                rprint(f"    {t}: {count}")

        # Show priority atoms (low stability / high lapses)
        if expanded.priority_atoms:
            rprint(f"\n[bold red]PRIORITY ATOMS[/bold red] (low stability or high lapses)")
            rprint(f"  Total: {len(expanded.priority_atoms)} atoms needing attention")

        # Suggest Anki query
        if expanded.anki_atoms:
            modules_str = " OR ".join(f"tag:module:{m}" for m in expanded.modules_touched)
            rprint(f"\n[dim]Suggested Anki query:[/dim]")
            rprint(f"  [cyan]deck:CCNA* ({modules_str})[/cyan]")

        rprint("")

    def _show_multi_module_path(
        self, module_numbers: list, expand_mode: bool, anki_learn_mode: bool
    ):
        """
        Show activity path for multiple modules with learning suggestions.

        This is the core command for checkpoint exam prep:
            module 1 2 3 --expand
        """
        modules_str = ", ".join(str(m) for m in module_numbers)
        rprint(f"\n[bold cyan]Activity Path: Modules {modules_str}[/bold cyan]")
        if expand_mode:
            rprint("[dim](with prerequisite expansion, max 3 hops)[/dim]")
        rprint("-" * 70)

        try:
            # Get activity path with prerequisite expansion
            max_depth = 3 if expand_mode else 0
            activity_path = self.study_service.get_multi_module_activity_path(
                module_numbers, max_depth=max_depth
            )
        except Exception as e:
            rprint(f"[red]Error:[/red] {e}")
            return

        summary = activity_path.get("summary", {})

        # Show summary
        rprint(f"\n[bold]Summary:[/bold]")
        rprint(f"  Target modules: {summary.get('target_modules', module_numbers)}")
        rprint(f"  Total atoms: {summary.get('total_atoms', 0)}")
        rprint(f"  Concepts: {activity_path.get('concept_count', 0)}")

        if expand_mode:
            prereq_mods = summary.get("prerequisite_modules", [])
            if prereq_mods:
                rprint(f"  [yellow]Prerequisite modules found: {prereq_mods}[/yellow]")
            rprint(f"  Modules touched: {activity_path.get('modules_touched', [])}")

        # Show Anki jobs
        anki_jobs = activity_path.get("anki_jobs", [])
        if anki_jobs:
            total_anki = sum(j["total"] for j in anki_jobs)
            rprint(f"\n[bold yellow]ANKI JOBS[/bold yellow] ({total_anki} cards total)")
            rprint("  Destination: flashcard + cloze → Anki (FSRS scheduling)")

            for job in anki_jobs:
                marker = "[cyan]*[/cyan]" if job["is_target_module"] else " "
                prereq_tag = " [dim](prerequisite)[/dim]" if not job["is_target_module"] else ""
                rprint(
                    f"  {marker} Module {job['module']}: "
                    f"{job['flashcard_count']} flashcard, {job['cloze_count']} cloze"
                    f"{prereq_tag}"
                )

        # Show NLS quiz jobs
        nls_jobs = activity_path.get("nls_jobs", [])
        if nls_jobs:
            total_nls = sum(j["count"] for j in nls_jobs)
            rprint(f"\n[bold green]NLS QUIZ JOBS[/bold green] ({total_nls} questions total)")
            rprint("  Destination: mcq, true_false, matching, parsons → NLS (in-app)")

            for job in nls_jobs:
                clt_indicator = "●" * int(job["avg_clt_load"])
                rprint(
                    f"    {job['quiz_type']:12} {job['count']:4} questions  "
                    f"CLT: {clt_indicator} ({job['avg_clt_load']})"
                )

        # Generate and show learning suggestions
        suggestions = self.study_service.generate_learning_suggestions(activity_path)
        if suggestions:
            rprint(f"\n[bold]SUGGESTED LEARNING PATH:[/bold]")
            for i, suggestion in enumerate(suggestions, 1):
                icon = "📚" if suggestion["type"] == "anki" else "🎯"
                rprint(f"\n  {i}. {icon} [bold]{suggestion['action']}[/bold]")
                rprint(f"     [dim]{suggestion['reason']}[/dim]")
                if suggestion["type"] == "anki":
                    rprint(f"     [cyan]Anki query: {suggestion.get('query', '')}[/cyan]")
                elif suggestion["type"] == "nls_quiz":
                    qtype = suggestion.get("quiz_type", "mcq")
                    count = suggestion.get("count", 10)
                    rprint(f"     [green]NLS command: quiz {count} {qtype}[/green]")

        # Handle --anki-learn flag
        if anki_learn_mode:
            self._force_anki_learning(activity_path)

        # Show Anki query for all modules
        all_modules = activity_path.get("modules_touched", module_numbers)
        if all_modules:
            modules_query = " OR ".join(f"tag:module:{m}" for m in all_modules)
            rprint(f"\n[dim]Combined Anki query:[/dim]")
            rprint(f"  [cyan]deck:CCNA* ({modules_query})[/cyan]")

        rprint("")

    def _force_anki_learning(self, activity_path: dict):
        """
        Force Anki cards into learning queue via AnkiConnect.

        Per Master Prompt: --anki-learn flag should:
        1. Collect all flashcard/cloze note IDs
        2. Order by prerequisite depth
        3. Create filtered deck or use setLearning
        """
        if not self.anki_client:
            rprint("\n[yellow]Anki not connected - cannot force learning queue[/yellow]")
            return

        # Collect note IDs from activity path
        note_ids = []
        for job in activity_path.get("anki_jobs", []):
            note_ids.extend([nid for nid in job.get("note_ids", []) if nid])

        if not note_ids:
            rprint("\n[yellow]No Anki note IDs available for learning queue[/yellow]")
            return

        rprint(f"\n[bold cyan]ANKI LEARN NOW[/bold cyan]")
        rprint(f"  Preparing {len(note_ids)} cards for learning queue...")

        try:
            # Create filtered deck with prerequisite-ordered cards
            from src.anki.anki_client import AnkiClient

            modules = activity_path.get("modules_touched", [])
            deck_name = f"LearningOS::Checkpoint-{'-'.join(str(m) for m in modules)}"

            # Build query for filtered deck
            modules_query = " OR ".join(f"tag:module:{m}" for m in modules)
            query = f"deck:CCNA* ({modules_query}) is:new"

            # Try to create filtered deck via AnkiConnect
            if self.anki_client:
                try:
                    self.anki_client.invoke("createFilteredDeck", {
                        "newDeckName": deck_name,
                        "searchQuery": query,
                    })
                    rprint(f"  [green]Created filtered deck: {deck_name}[/green]")
                    rprint(f"  [dim]Query: {query}[/dim]")
                    rprint(f"\n  Open Anki and study the '{deck_name}' deck!")
                except Exception as e:
                    rprint(f"  [yellow]Could not create filtered deck: {e}[/yellow]")
                    rprint(f"  [dim]Manual query: {query}[/dim]")

        except Exception as e:
            rprint(f"  [red]Error: {e}[/red]")

    def do_stats(self, arg):
        """Show comprehensive study statistics."""
        if not self.study_service:
            rprint("[red]Study service not available[/red]")
            return

        try:
            stats = self.study_service.get_study_stats()
        except Exception as e:
            rprint(f"[red]Error:[/red] {e}")
            return

        rprint("\n[bold]CCNA Study Statistics[/bold]")
        rprint("=" * 50)

        table = Table(title="Section Progress", show_header=False)
        table.add_column("Metric", style="cyan")
        table.add_column("Value", justify="right")

        s = stats["sections"]
        table.add_row("Total Sections", str(s["total"]))
        table.add_row("Completed", f"{s['completed']} ({s['completion_rate']}%)")
        console.print(table)

        table = Table(title="Atom Mastery", show_header=False)
        table.add_column("Status", style="cyan")
        table.add_column("Count", justify="right")

        a = stats["atoms"]
        table.add_row("Total Atoms", str(a["total"]))
        table.add_row("[green]Mastered[/green]", str(a["mastered"]))
        table.add_row("[yellow]Learning[/yellow]", str(a["learning"]))
        table.add_row("[red]Struggling[/red]", str(a["struggling"]))
        table.add_row("[dim]New[/dim]", str(a["new"]))
        console.print(table)

        rprint(f"\n[bold]Overall Mastery:[/bold] {stats['mastery']['average']}%")

    def do_remediation(self, arg):
        """Show sections needing remediation."""
        if not self.study_service:
            rprint("[red]Study service not available[/red]")
            return

        try:
            sections = self.study_service.get_remediation_sections()
        except Exception as e:
            rprint(f"[red]Error:[/red] {e}")
            return

        if not sections:
            rprint("\n[green][OK] No sections need remediation![/green]")
            rprint("Great job keeping up with your studies!")
            return

        rprint(f"\n[bold red][!] {len(sections)} Sections Need Remediation[/bold red]")
        rprint("=" * 60)

        table = Table()
        table.add_column("Section", style="cyan")
        table.add_column("Title")
        table.add_column("Mastery", justify="right")
        table.add_column("Reason", style="yellow")

        for section in sections[:10]:
            table.add_row(
                section.section_id,
                section.title[:35] + "..." if len(section.title) > 35 else section.title,
                f"{section.mastery_score:.0f}%",
                section.remediation_reason or "combined",
            )

        console.print(table)

        if len(sections) > 10:
            rprint(f"\n[dim]... and {len(sections) - 10} more[/dim]")

    def do_sync(self, arg):
        """Sync mastery scores from Anki."""
        rprint("\n[bold]Syncing Mastery from Anki...[/bold]")
        self._do_sync(quiet=False)
        self.last_sync = datetime.now()
        rprint("")

    # ========================================
    # SESSION COMMANDS
    # ========================================

    def do_status(self, arg):
        """Show current session status."""
        rprint("\n[bold]Session Status[/bold]")
        rprint("-" * 40)

        if self.anki_client:
            rprint("[green][OK][/green] Anki connected")
            if self.last_sync:
                rprint(f"     Last sync: {self.last_sync.strftime('%H:%M:%S')}")
            rprint(f"     Sync interval: {self.sync_interval}s")
        else:
            rprint("[yellow][!][/yellow] Anki not connected")

        if self.study_service:
            rprint("[green][OK][/green] Study service active")
        else:
            rprint("[red][X][/red] Study service unavailable")

        rprint("")

    def do_clear(self, arg):
        """Clear the screen."""
        console.clear()
        self._show_welcome()

    def do_jobs(self, arg):
        """Generate learning jobs (filtered deck queries) for a session."""
        if not self.study_service:
            rprint("[red]Study service not available[/red]")
            return

        rprint("\n[bold]Generating Learning Jobs...[/bold]")
        rprint("=" * 60)

        # Get current state
        try:
            summary = self.study_service.get_daily_summary()
            remediation = self.study_service.get_remediation_sections()
        except Exception as e:
            rprint(f"[red]Error:[/red] {e}")
            return

        jobs = []

        # Job 1: Stability Repair (weakest items)
        if remediation:
            weak_sections = [s.section_id for s in remediation[:5]]
            jobs.append({
                "id": 1,
                "name": "Stability Repair",
                "type": "weakness",
                "query": f"(tag:ccna AND (rated:7:1 OR prop:lapses>1))",
                "cards": min(len(remediation) * 5, 40),
                "priority": "HIGH",
            })

        # Job 2: Due Reviews
        if summary.due_reviews > 0:
            jobs.append({
                "id": 2,
                "name": "Due Reviews",
                "type": "maintenance",
                "query": "is:due",
                "cards": summary.due_reviews,
                "priority": "HIGH",
            })

        # Job 3: New Learning
        if summary.new_atoms_available > 0:
            jobs.append({
                "id": 3,
                "name": "New Content",
                "type": "acquisition",
                "query": "is:new tag:ccna",
                "cards": min(30, summary.new_atoms_available),
                "priority": "MEDIUM",
            })

        # Job 4: Bloom Application
        jobs.append({
            "id": 4,
            "name": "Apply-Level Practice",
            "type": "application",
            "query": "(tag:bloom:apply OR tag:mcq OR tag:parsons)",
            "cards": 20,
            "priority": "MEDIUM",
        })

        # Job 5: Cluster Integration
        jobs.append({
            "id": 5,
            "name": "Concept Integration",
            "type": "integration",
            "query": f"tag:module:{summary.current_module}",
            "cards": 25,
            "priority": "LOW",
        })

        # Display jobs
        rprint("\n[cyan]Generated Learning Jobs:[/cyan]\n")

        table = Table(show_header=True)
        table.add_column("#", style="dim", width=3)
        table.add_column("Job", style="cyan")
        table.add_column("Type", style="dim")
        table.add_column("Cards", justify="right")
        table.add_column("Priority")
        table.add_column("Anki Query", style="dim")

        total_cards = 0
        for job in jobs:
            priority_style = {
                "HIGH": "[red]HIGH[/red]",
                "MEDIUM": "[yellow]MED[/yellow]",
                "LOW": "[dim]LOW[/dim]",
            }
            table.add_row(
                str(job["id"]),
                job["name"],
                job["type"],
                str(job["cards"]),
                priority_style.get(job["priority"], job["priority"]),
                job["query"][:30] + "..." if len(job["query"]) > 30 else job["query"],
            )
            total_cards += job["cards"]

        console.print(table)

        rprint(f"\n[bold]Total:[/bold] {total_cards} cards")
        rprint(f"[dim]Estimated time: {total_cards} minutes[/dim]")

        rprint("\n[cyan]To create filtered deck in Anki:[/cyan]")
        rprint("  Tools > Create Filtered Deck > paste query")
        rprint("\n[yellow]Remember:[/yellow] Delete filtered decks after use!")
        rprint("[dim]Filtered decks are ephemeral jobs, not permanent structure.[/dim]\n")

    # ========================================
    # QUIZ COMMANDS (In-App Learning)
    # ========================================

    def do_quiz(self, arg):
        """
        Start an interactive quiz. Usage: quiz [count] [type]

        Examples:
            quiz           - 10 random MCQ/T-F questions
            quiz 20        - 20 questions
            quiz 10 mcq    - 10 MCQ only
            quiz 15 tf     - 15 True/False only
            quiz 10 match  - 10 Matching problems
            quiz 5 parsons - 5 Parsons ordering problems
        """
        if not self.quiz_engine:
            rprint("[red]Quiz engine not available[/red]")
            return

        # Parse arguments
        parts = arg.split() if arg else []
        count = 10
        atom_types = None

        if parts:
            try:
                count = int(parts[0])
            except ValueError:
                pass

            if len(parts) > 1:
                type_map = {
                    "mcq": "mcq",
                    "tf": "true_false",
                    "truefalse": "true_false",
                    "true_false": "true_false",
                    "match": "matching",
                    "matching": "matching",
                    "parsons": "parsons",
                    "order": "parsons",
                }
                type_arg = parts[1].lower()
                if type_arg in type_map:
                    from src.study.quiz_engine import AtomType
                    atom_types = [AtomType(type_map[type_arg])]

        # Run quiz
        from src.study.quiz_engine import AtomType
        if atom_types is None:
            atom_types = [AtomType.MCQ, AtomType.TRUE_FALSE]

        stats = self.pomodoro_engine.quick_quiz(
            count=count,
            atom_types=atom_types,
        )

        rprint(f"\n[bold]Quiz Complete![/bold]")
        rprint(f"  Score: {stats['correct']}/{stats['total']} ({stats['accuracy']:.0f}%)")
        rprint(f"  Time: {stats['duration_minutes']} minutes\n")

    def do_session(self, arg):
        """
        Start a full Pomodoro study session. Usage: session [hours]

        A session alternates between:
        - Anki blocks (flashcard/cloze reviews)
        - Quiz blocks (MCQ, T/F, Matching, Parsons)

        Examples:
            session      - 1 hour session (2 pomodoros)
            session 2    - 2 hour session (4 pomodoros)
            session 0.5  - 30 min session (1 pomodoro)
        """
        if not self.pomodoro_engine:
            rprint("[red]Pomodoro engine not available[/red]")
            return

        hours = 1.0
        if arg:
            try:
                hours = float(arg)
            except ValueError:
                rprint(f"[red]Invalid hours:[/red] {arg}")
                return

        if hours < 0.5 or hours > 8:
            rprint("[yellow]Hours should be between 0.5 and 8[/yellow]")
            return

        # Plan and show session
        session = self.pomodoro_engine.plan_session(hours)
        self.pomodoro_engine.show_plan(session)

        if Confirm.ask("\n[bold]Start this session?[/bold]", default=True):
            self.current_session = self.pomodoro_engine.run_session(session)

    def do_mcq(self, arg):
        """Quick MCQ quiz. Usage: mcq [count]"""
        count = int(arg) if arg and arg.isdigit() else 10
        self.do_quiz(f"{count} mcq")

    def do_tf(self, arg):
        """Quick True/False quiz. Usage: tf [count]"""
        count = int(arg) if arg and arg.isdigit() else 10
        self.do_quiz(f"{count} tf")

    def do_matching(self, arg):
        """Quick Matching quiz. Usage: matching [count]"""
        count = int(arg) if arg and arg.isdigit() else 5
        self.do_quiz(f"{count} match")

    def do_parsons(self, arg):
        """Quick Parsons (ordering) quiz. Usage: parsons [count]"""
        count = int(arg) if arg and arg.isdigit() else 5
        self.do_quiz(f"{count} parsons")

    def do_struggle(self, arg):
        """
        Load a struggle-focused learning path from JSON file or inline.

        Usage:
            struggle --file my-struggles.json    Load from file
            struggle --add "module:7:high"       Quick add
            struggle --show                      Show current struggles

        JSON Schema Example:
        {
          "struggles": [
            {"type": "module", "id": 7, "name": "DHCPv4", "severity": "high"},
            {"type": "concept", "name": "Subnetting", "severity": "critical"},
            {"type": "topic", "keywords": ["STP"], "severity": "medium"}
          ],
          "preferences": {
            "focus_mode": "weakest_first",
            "max_atoms_per_session": 50,
            "include_prerequisites": true
          }
        }
        """
        import json
        from pathlib import Path

        if not self.study_service:
            rprint("[red]Study service not available[/red]")
            return

        parts = arg.split() if arg else []

        # Handle --show flag
        if "--show" in parts:
            self._show_current_struggles()
            return

        # Handle --file flag
        if "--file" in parts:
            try:
                file_idx = parts.index("--file")
                file_path = parts[file_idx + 1] if file_idx + 1 < len(parts) else None
                if not file_path:
                    rprint("[red]Usage: struggle --file <path>[/red]")
                    return
                self._load_struggles_from_file(file_path)
            except Exception as e:
                rprint(f"[red]Error loading file:[/red] {e}")
            return

        # Handle --add flag (quick add)
        if "--add" in parts:
            try:
                add_idx = parts.index("--add")
                spec = parts[add_idx + 1] if add_idx + 1 < len(parts) else None
                if not spec:
                    rprint("[red]Usage: struggle --add \"type:id:severity\"[/red]")
                    rprint("Example: struggle --add \"module:7:high\"")
                    return
                self._quick_add_struggle(spec)
            except Exception as e:
                rprint(f"[red]Error:[/red] {e}")
            return

        # No args - show usage
        rprint("\n[bold]Struggle-Focused Learning Path[/bold]")
        rprint("-" * 50)
        rprint("\n[cyan]Usage:[/cyan]")
        rprint("  struggle --file struggles.json   Load from JSON file")
        rprint("  struggle --add \"module:7:high\"   Quick add a struggle")
        rprint("  struggle --show                  Show current struggles")
        rprint("\n[cyan]JSON Schema:[/cyan]")
        rprint('''  {
    "struggles": [
      {"type": "module", "id": 7, "name": "DHCPv4", "severity": "high"},
      {"type": "concept", "name": "Subnetting", "severity": "critical"},
      {"type": "topic", "keywords": ["STP", "spanning tree"], "severity": "high"},
      {"type": "section", "module": 11, "section": "11.4", "severity": "medium"}
    ],
    "preferences": {
      "focus_mode": "weakest_first",
      "max_atoms_per_session": 50,
      "include_prerequisites": true,
      "prerequisite_depth": 2
    }
  }''')
        rprint("\n[cyan]Severity Levels:[/cyan]")
        rprint("  critical (4x) - Cannot proceed without mastering")
        rprint("  high (3x)     - Major gaps affecting progress")
        rprint("  medium (2x)   - Needs improvement")
        rprint("  low (1x)      - Minor weakness")
        rprint("\nSee docs/struggle-schema.md for full documentation.\n")

    def _load_struggles_from_file(self, file_path: str):
        """Load and process struggles from JSON file."""
        import json
        from pathlib import Path

        path = Path(file_path)
        if not path.exists():
            rprint(f"[red]File not found:[/red] {file_path}")
            return

        with open(path, "r") as f:
            data = json.load(f)

        struggles = data.get("struggles", [])
        prefs = data.get("preferences", {})

        if not struggles:
            rprint("[yellow]No struggles defined in file[/yellow]")
            return

        rprint(f"\n[bold cyan]Loading {len(struggles)} struggles...[/bold cyan]")

        # Build prioritized learning path
        severity_weights = {"critical": 4, "high": 3, "medium": 2, "low": 1}

        all_atoms = []
        modules_touched = set()

        for struggle in sorted(struggles, key=lambda s: -severity_weights.get(s.get("severity", "low"), 1)):
            stype = struggle.get("type")
            severity = struggle.get("severity", "medium")
            name = struggle.get("name", "Unknown")

            rprint(f"\n  [{severity.upper()}] {stype}: {name}")

            # Get atoms based on struggle type
            atoms = self._get_struggle_atoms(struggle, prefs)
            if atoms:
                all_atoms.extend(atoms)
                for a in atoms:
                    if a.get("module"):
                        modules_touched.add(a["module"])
                rprint(f"    → Found {len(atoms)} atoms")
            else:
                rprint(f"    → [dim]No atoms found[/dim]")

        # Show summary
        rprint(f"\n[bold]STRUGGLE-FOCUSED LEARNING PATH[/bold]")
        rprint("=" * 60)

        # Group by severity
        by_severity = {}
        for a in all_atoms:
            sev = a.get("severity", "medium")
            by_severity.setdefault(sev, []).append(a)

        for sev in ["critical", "high", "medium", "low"]:
            if sev in by_severity:
                count = len(by_severity[sev])
                rprint(f"  [{sev.upper():8}] {count:4} atoms")

        total = len(all_atoms)
        est_time = total * 1.5 / 60  # ~1.5 min per atom

        rprint(f"\n  TOTAL: {total} atoms")
        rprint(f"  Estimated time: {est_time:.1f} hours")
        rprint(f"  Modules touched: {sorted(modules_touched)}")

        # Generate Anki queries
        if modules_touched:
            rprint(f"\n[cyan]Anki Query:[/cyan]")
            modules_query = " OR ".join(f"tag:module:{m}" for m in sorted(modules_touched))
            rprint(f"  deck:CCNA* ({modules_query})")

        rprint("")

    def _get_struggle_atoms(self, struggle: dict, prefs: dict) -> list:
        """Get atoms for a specific struggle."""
        stype = struggle.get("type")
        severity = struggle.get("severity", "medium")
        include_prereqs = prefs.get("include_prerequisites", True)
        prereq_depth = prefs.get("prerequisite_depth", 2)

        atoms = []

        try:
            if stype == "module":
                mod_id = struggle.get("id")
                if mod_id:
                    if include_prereqs:
                        expanded = self.study_service.get_expanded_module_atoms(mod_id, prereq_depth)
                        atoms = expanded.anki_atoms + expanded.quiz_atoms
                    else:
                        sections = self.study_service.get_section_details(mod_id)
                        for s in sections:
                            atoms.extend(self.study_service.get_atoms_for_section(s.section_id))

            elif stype == "concept":
                concept_name = struggle.get("name")
                if concept_name:
                    atoms = self.study_service.get_atoms_by_concept_name(concept_name)

            elif stype == "topic":
                keywords = struggle.get("keywords", [])
                if keywords:
                    atoms = self.study_service.search_atoms_by_keywords(keywords)

            elif stype == "section":
                mod = struggle.get("module")
                sec = struggle.get("section")
                if mod and sec:
                    atoms = self.study_service.get_atoms_for_section(f"{mod}.{sec}")

        except Exception as e:
            rprint(f"    [yellow]Warning: {e}[/yellow]")

        # Tag with severity for prioritization
        for a in atoms:
            a["severity"] = severity

        return atoms

    def _quick_add_struggle(self, spec: str):
        """Quick add a struggle from spec string like 'module:7:high'"""
        parts = spec.replace('"', '').replace("'", "").split(":")
        if len(parts) < 3:
            rprint("[red]Format: type:id:severity[/red]")
            rprint("Examples:")
            rprint("  module:7:high")
            rprint("  concept:Subnetting:critical")
            return

        stype, identifier, severity = parts[0], parts[1], parts[2]

        if severity not in ["critical", "high", "medium", "low"]:
            rprint(f"[yellow]Invalid severity: {severity}. Using 'medium'[/yellow]")
            severity = "medium"

        struggle = {"type": stype, "severity": severity}
        if stype == "module":
            struggle["id"] = int(identifier)
            struggle["name"] = f"Module {identifier}"
        elif stype == "concept":
            struggle["name"] = identifier
        elif stype == "topic":
            struggle["keywords"] = [identifier]

        rprint(f"\n[bold]Adding struggle:[/bold] {stype} - {identifier} ({severity})")

        atoms = self._get_struggle_atoms(struggle, {"include_prerequisites": True, "prerequisite_depth": 2})

        if atoms:
            rprint(f"  Found {len(atoms)} atoms for this struggle")

            # Show breakdown
            by_type = {}
            for a in atoms:
                t = a.get("atom_type", "unknown")
                by_type.setdefault(t, 0)
                by_type[t] += 1

            for t, count in sorted(by_type.items()):
                rprint(f"    {t}: {count}")
        else:
            rprint("  [yellow]No atoms found for this struggle[/yellow]")

        rprint("")

    def _show_current_struggles(self):
        """Show currently tracked struggles from database."""
        rprint("\n[bold]Current Struggles[/bold]")
        rprint("-" * 50)

        if not self.study_service:
            rprint("[red]Study service not available[/red]")
            return

        try:
            # Get sections with low mastery as implicit struggles
            remediation = self.study_service.get_remediation_sections()

            if not remediation:
                rprint("\n[green]No struggles detected![/green]")
                rprint("All sections are at acceptable mastery levels.\n")
                return

            rprint(f"\n[yellow]{len(remediation)} sections need attention:[/yellow]\n")

            for section in remediation[:15]:
                bar = self._format_progress_bar(section.mastery_score)
                rprint(f"  [{section.mastery_score:3.0f}%] {bar} {section.section_id}: {section.title[:40]}")
                if section.remediation_reason:
                    rprint(f"         [dim]Reason: {section.remediation_reason}[/dim]")

            if len(remediation) > 15:
                rprint(f"\n  [dim]... and {len(remediation) - 15} more[/dim]")

            rprint("\n[cyan]Tip:[/cyan] Create a struggles.json file with these sections for focused study.")
            rprint("See: [dim]struggle --file struggles.json[/dim]\n")

        except Exception as e:
            rprint(f"[red]Error:[/red] {e}")

    def do_help(self, arg):
        """Show available commands."""
        rprint("\n[bold]Available Commands[/bold]")
        rprint("-" * 50)
        rprint("")
        rprint("[cyan]In-App Quizzes (MCQ, T/F, Matching, Parsons):[/cyan]")
        rprint("  quiz [n] [type]  - Start a quiz (e.g., quiz 10 mcq)")
        rprint("  mcq [n]          - Quick MCQ quiz")
        rprint("  tf [n]           - Quick True/False quiz")
        rprint("  matching [n]     - Quick Matching quiz")
        rprint("  parsons [n]      - Quick Parsons ordering quiz")
        rprint("  session [hrs]    - Full Pomodoro session (Anki + quizzes)")
        rprint("")
        rprint("[yellow]Anki Integration (flashcard + cloze only):[/yellow]")
        rprint("  sync        - Sync FSRS stats from Anki")
        rprint("  jobs        - Generate filtered deck queries for Anki")
        rprint("  plan <hrs>  - Plan a study session with time breakdown")
        rprint("")
        rprint("[cyan]Progress Tracking:[/cyan]")
        rprint("  today                - Today's study session summary")
        rprint("  path                 - Full learning path with progress")
        rprint("  module <n>           - Detailed view of module n (1-17)")
        rprint("  module <n> --expand  - Cross-module expansion (3 hop prereq graph)")
        rprint("  module 1 2 3         - Activity path for checkpoint exam prep")
        rprint("  module 1 2 3 --expand    (with prerequisites)")
        rprint("  module 1 2 3 --anki-learn  (force Anki learning queue)")
        rprint("  stats                - Comprehensive statistics")
        rprint("  remediation          - Sections needing remediation")
        rprint("")
        rprint("[red]Struggle-Focused Learning:[/red]")
        rprint("  struggle                     - Show usage and JSON schema")
        rprint("  struggle --show              - Show current struggles from mastery")
        rprint("  struggle --file FILE.json    - Load struggle path from JSON")
        rprint("  struggle --add \"module:7:high\" - Quick add a struggle")
        rprint("")
        rprint("[dim]Session:[/dim]")
        rprint("  status      - Show connection status")
        rprint("  clear       - Clear screen")
        rprint("  help        - Show this help")
        rprint("  quit/exit   - Exit the session")
        rprint("")
        rprint("[dim]Architecture:[/dim]")
        rprint("  Anki:  flashcard + cloze (FSRS scheduling)")
        rprint("  NLS:   mcq, true_false, matching, parsons (in-app)")
        rprint("")

    def do_quit(self, arg):
        """Exit the interactive session."""
        return True

    def do_exit(self, arg):
        """Exit the interactive session."""
        return True

    def do_EOF(self, arg):
        """Handle Ctrl+D."""
        rprint("")
        return True

    def emptyline(self):
        """Handle empty input (don't repeat last command)."""
        pass

    def default(self, line):
        """Handle unknown commands."""
        rprint(f"[yellow]Unknown command:[/yellow] {line}")
        rprint("Type [cyan]help[/cyan] for available commands.")

    # ========================================
    # UTILITIES
    # ========================================

    def _format_progress_bar(self, score: float, width: int = 10) -> str:
        """Format a progress bar."""
        filled = int(score / 100 * width)
        empty = width - filled
        return "#" * filled + "-" * empty


def main():
    """Entry point for interactive CLI."""
    try:
        shell = NLSShell()
        shell.cmdloop()
    except KeyboardInterrupt:
        rprint("\n\n[dim]Session interrupted. Goodbye![/dim]\n")
        sys.exit(0)


if __name__ == "__main__":
    main()
