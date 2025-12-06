"""
CLI Study Commands for CCNA Learning Path.

Commands:
    nls study today       - Daily study session summary
    nls study path        - Full learning path overview
    nls study module <n>  - Detailed view of module n
    nls study stats       - Personal learning statistics
    nls study sync        - Sync mastery from Anki
    nls study remediation - Show areas needing remediation
"""
from __future__ import annotations

from datetime import date

import typer
from rich import print as rprint
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

console = Console()

# Create the study app
study_app = typer.Typer(
    name="study",
    help="CCNA Study Path commands - daily sessions, progress tracking, remediation",
    no_args_is_help=True,
)


def _get_study_service():
    """Lazy load study service to avoid import errors."""
    from src.study.study_service import StudyService
    return StudyService()


def _format_progress_bar(score: float, width: int = 10) -> str:
    """Format a progress bar."""
    filled = int(score / 100 * width)
    empty = width - filled
    return "#" * filled + "-" * empty


def _get_status_indicator(is_mastered: bool, needs_remediation: bool) -> str:
    """Get status indicator."""
    if is_mastered:
        return "[green][OK][/green]"
    elif needs_remediation:
        return "[red][!][/red]"
    return ""


@study_app.command("today")
def study_today() -> None:
    """
    Show today's study session summary.

    Displays due reviews, new content recommendations, and remediation needs.
    """
    try:
        service = _get_study_service()
        summary = service.get_daily_summary()
    except Exception as e:
        rprint(f"[red]Error:[/red] {e}")
        rprint("\n[yellow]Make sure to run migrations first:[/yellow]")
        rprint("  nls db migrate --migration 008")
        rprint("  python scripts/populate_ccna_sections.py")
        return

    # Build the panel content
    content = Text()

    # Date header
    content.append(f"[DATE] {summary.date.strftime('%B %d, %Y')}\n\n", style="bold")

    # Due reviews
    content.append(f"[REVIEW] Due Reviews: ", style="cyan")
    content.append(f"{summary.due_reviews} cards", style="bold")
    if summary.due_reviews > 0:
        content.append(f" (est. {summary.due_reviews // 2} min)\n")
    else:
        content.append(" - All caught up!\n")

    # New content
    content.append(f"[NEW] New Content: ", style="green")
    content.append(f"{summary.new_atoms_available} atoms available\n", style="bold")

    # Remediation
    if summary.remediation_sections > 0:
        content.append(f"[!] Remediation: ", style="yellow")
        content.append(f"{summary.remediation_atoms} cards ", style="bold")
        content.append(f"from {summary.remediation_sections} sections\n")
    else:
        content.append("[OK] No remediation needed\n", style="green")

    content.append("\n")

    # Current focus
    content.append(f"[>] Current: Module {summary.current_module} - Section {summary.current_section}\n")

    # Overall progress
    content.append(f"[MASTERY] Overall: ")
    bar = _format_progress_bar(summary.overall_mastery)
    content.append(f"{bar} {summary.overall_mastery:.0f}%\n")

    # Streak
    if summary.streak_days > 0:
        content.append(f"[STREAK] {summary.streak_days} days\n", style="bold yellow")

    # Estimated time
    content.append(f"\n[TIME] Estimated session: {summary.estimated_minutes} minutes")

    panel = Panel(
        content,
        title="[bold]CCNA Study Session[/bold]",
        border_style="blue",
    )
    console.print(panel)

    rprint("\n[dim]Run [cyan]nls study path[/cyan] to see full learning path[/dim]")


@study_app.command("path")
def study_path() -> None:
    """
    Show complete CCNA learning path with progress.

    Displays all 17 modules with completion percentage and mastery status.
    """
    try:
        service = _get_study_service()
        modules = service.get_module_summaries()
    except Exception as e:
        rprint(f"[red]Error:[/red] {e}")
        return

    if not modules:
        rprint("[yellow]No module data found.[/yellow]")
        rprint("Run: python scripts/populate_ccna_sections.py")
        return

    rprint("\n[bold]CCNA Learning Path Progress[/bold]")
    rprint("=" * 70)

    total_mastered = 0
    total_learning = 0
    total_struggling = 0
    total_new = 0
    total_remediation = 0

    for mod in modules:
        # Module header
        completion = (
            mod.sections_completed / mod.total_sections * 100
            if mod.total_sections > 0
            else 0
        )

        # Status indicator
        if mod.sections_needing_remediation > 0:
            status = "[red][!][/red]"
        elif completion >= 90:
            status = "[green][OK][/green]"
        else:
            status = ""

        rprint(f"\n[cyan]Module {mod.module_number}:[/cyan] {mod.title} {status}")

        # Progress bar
        bar = _format_progress_bar(mod.avg_mastery)
        color = "green" if mod.avg_mastery >= 90 else "yellow" if mod.avg_mastery >= 70 else "red"
        rprint(f"  [{color}]{bar}[/{color}] {mod.avg_mastery:.0f}%  ", end="")
        rprint(f"[dim]({mod.sections_completed}/{mod.total_sections} sections)[/dim]")

        # Atom breakdown (condensed)
        if mod.atoms_total > 0:
            rprint(
                f"  [dim]Atoms: "
                f"[green]{mod.atoms_mastered}[/green] mastered | "
                f"[yellow]{mod.atoms_learning}[/yellow] learning | "
                f"[red]{mod.atoms_struggling}[/red] struggling | "
                f"[dim]{mod.atoms_new}[/dim] new[/dim]"
            )

        # Track totals
        total_mastered += mod.atoms_mastered
        total_learning += mod.atoms_learning
        total_struggling += mod.atoms_struggling
        total_new += mod.atoms_new
        total_remediation += mod.sections_needing_remediation

    # Summary
    rprint("\n" + "=" * 70)
    total_atoms = total_mastered + total_learning + total_struggling + total_new
    overall_pct = (
        (total_mastered + total_learning * 0.5) / total_atoms * 100
        if total_atoms > 0
        else 0
    )

    rprint(f"[bold]Overall:[/bold] {overall_pct:.0f}% progress | {total_atoms} atoms total")
    rprint(
        f"[green]{total_mastered}[/green] mastered | "
        f"[yellow]{total_learning}[/yellow] learning | "
        f"[red]{total_struggling}[/red] struggling | "
        f"[dim]{total_new}[/dim] new"
    )

    if total_remediation > 0:
        rprint(f"\n[red][!] {total_remediation} sections need remediation[/red]")
        rprint("[dim]Run [cyan]nls study remediation[/cyan] for details[/dim]")


@study_app.command("module")
def study_module(
    module_number: int = typer.Argument(..., help="Module number (1-17)"),
) -> None:
    """
    Show detailed progress for a specific module.

    Displays all sections with individual mastery scores and atom breakdowns.
    """
    if module_number < 1 or module_number > 16:
        rprint(f"[red]Invalid module number:[/red] {module_number} (must be 1-16)")
        return

    try:
        service = _get_study_service()
        sections = service.get_section_details(module_number)
    except Exception as e:
        rprint(f"[red]Error:[/red] {e}")
        return

    if not sections:
        rprint(f"[yellow]No sections found for Module {module_number}[/yellow]")
        return

    # Module titles
    module_titles = {
        1: "Networking Today",
        2: "Basic Switch and End Device Configuration",
        3: "Protocols and Models",
        4: "Physical Layer",
        5: "Number Systems",
        6: "Data Link Layer",
        7: "Ethernet Switching",
        8: "Network Layer",
        9: "Address Resolution",
        10: "Basic Router Configuration",
        11: "IPv4 Addressing",
        12: "IPv6 Addressing",
        13: "ICMP",
        14: "Transport Layer",
        15: "Application Layer",
        16: "Network Security Fundamentals",
        17: "Build a Small Network",
    }

    title = module_titles.get(module_number, f"Module {module_number}")
    rprint(f"\n[bold cyan]Module {module_number}: {title}[/bold cyan]")
    rprint("=" * 70)

    for section in sections:
        # Main section
        bar = _format_progress_bar(section.mastery_score)
        status = _get_status_indicator(section.is_mastered, section.needs_remediation)

        rprint(f"\n  +-- [bold]{section.section_id}[/bold] {section.title} {status}")
        rprint(f"  |   {bar} {section.mastery_score:.0f}%")

        if section.atoms_total > 0:
            rprint(
                f"  |   [dim]"
                f"[green]{section.atoms_mastered}[/green]/"
                f"[yellow]{section.atoms_learning}[/yellow]/"
                f"[red]{section.atoms_struggling}[/red]/"
                f"{section.atoms_new} atoms"
                f"[/dim]"
            )

        if section.needs_remediation:
            rprint(f"  |   [red]Needs remediation: {section.remediation_reason}[/red]")

        # Subsections (indented)
        for sub in section.subsections:
            sub_bar = _format_progress_bar(sub.mastery_score, width=8)
            sub_status = _get_status_indicator(sub.is_mastered, sub.needs_remediation)

            rprint(f"  |   +-- {sub.section_id} {sub.title[:40]} {sub_status}")
            rprint(f"  |       {sub_bar} {sub.mastery_score:.0f}%")


@study_app.command("stats")
def study_stats() -> None:
    """
    Show comprehensive study statistics.

    Displays atoms, sections, mastery, and session history.
    """
    try:
        service = _get_study_service()
        stats = service.get_study_stats()
    except Exception as e:
        rprint(f"[red]Error:[/red] {e}")
        return

    rprint("\n[bold]CCNA Study Statistics[/bold]")
    rprint("=" * 50)

    # Sections
    table = Table(title="Section Progress", show_header=False)
    table.add_column("Metric", style="cyan")
    table.add_column("Value", justify="right")

    s = stats["sections"]
    table.add_row("Total Sections", str(s["total"]))
    table.add_row("Completed", f"{s['completed']} ({s['completion_rate']}%)")

    console.print(table)

    # Atoms
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

    # Mastery
    rprint(f"\n[bold]Overall Mastery:[/bold] {stats['mastery']['average']}%")
    rprint(f"[dim]Total Reviews: {stats['mastery']['total_reviews']}[/dim]")

    # Sessions
    if stats["sessions"]["total"] > 0:
        sess = stats["sessions"]
        rprint(f"\n[bold]Study Sessions:[/bold]")
        rprint(f"  Sessions: {sess['total']}")
        rprint(f"  Total Time: {sess['total_minutes']} minutes")
        rprint(f"  Cards Reviewed: {sess['total_cards_reviewed']}")
        rprint(f"  Average Accuracy: {sess['avg_accuracy']}%")


@study_app.command("remediation")
def study_remediation() -> None:
    """
    Show sections needing remediation.

    Lists all struggling sections sorted by priority.
    """
    try:
        service = _get_study_service()
        sections = service.get_remediation_sections()
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
    table.add_column("Struggling", justify="right", style="red")

    for section in sections:
        table.add_row(
            section.section_id,
            section.title[:35] + "..." if len(section.title) > 35 else section.title,
            f"{section.mastery_score:.0f}%",
            section.remediation_reason or "combined",
            str(section.atoms_struggling),
        )

    console.print(table)

    rprint("\n[dim]These sections will be interleaved into your daily study sessions.[/dim]")


@study_app.command("sync")
def study_sync() -> None:
    """
    Sync mastery scores from Anki statistics.

    Updates all section mastery based on current Anki review data.
    """
    rprint("\n[bold]Syncing Mastery from Anki...[/bold]")

    try:
        service = _get_study_service()

        # First sync Anki stats
        rprint("  Pulling Anki statistics...")
        # TODO: Call anki pull service

        # Then refresh mastery calculations
        rprint("  Recalculating mastery scores...")
        count = service.refresh_mastery()

        rprint(f"\n[green][OK][/green] Updated mastery for {count} sections")

    except Exception as e:
        rprint(f"[red]Error:[/red] {e}")
        return

    rprint("\n[dim]Run [cyan]nls study today[/cyan] to see updated recommendations[/dim]")
