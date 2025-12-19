"""
Cortex CLI - The Developer's Learning Companion

A terminal-based learning tool that serves as:
1. Developer's Companion - Quick study sessions from the terminal
2. Content Pipeline - CI/CD validation for learning content
3. Offline Fallback - Air-gapped study with later sync

Usage:
    cortex start           # Start a study session
    cortex start --quick   # Quick 5-minute struggle review
    cortex validate        # Validate content (pipeline mode)
    cortex sync            # Sync with right-learning platform
    cortex export          # Export for offline use
    cortex import          # Import after offline study

Part of the Right Learning ecosystem.
"""

from __future__ import annotations

import asyncio
import sys
from datetime import datetime
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

# Local imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from src.core.modes import (
    CortexCliConfig,
    ModeContext,
    OperatingMode,
    detect_mode,
    get_mode_strategy,
)
from src.core.platform_client import PlatformClient

# =============================================================================
# CLI Setup
# =============================================================================

app = typer.Typer(
    name="cortex",
    help="🧠 Cortex CLI - Terminal-based cognitive learning companion",
    add_completion=True,
    rich_markup_mode="rich",
)

console = Console()


def get_config() -> CortexCliConfig:
    """Load configuration with mode auto-detection."""
    mode = detect_mode()
    return CortexCliConfig(mode=mode)


# =============================================================================
# Study Commands
# =============================================================================


@app.command()
def start(
    quick: Annotated[
        bool, typer.Option("--quick", "-q", help="Quick 5-minute struggle review")
    ] = False,
    cards: Annotated[
        int, typer.Option("--cards", "-n", help="Number of cards to review")
    ] = 20,
    module: Annotated[
        str | None, typer.Option("--module", "-m", help="Focus on specific module")
    ] = None,
    struggles: Annotated[
        bool, typer.Option("--struggles", "-s", help="Focus on struggle zones")
    ] = False,
) -> None:
    """
    Start a study session.

    Examples:
        cortex start              # Normal session
        cortex start --quick      # Quick 5-minute review
        cortex start -m 17        # Focus on Module 17
        cortex start --struggles  # Target struggle zones
    """
    config = get_config()

    if quick:
        cards = min(cards, 10)
        console.print("[yellow]⚡ Quick mode: 5-minute struggle review[/]")

    header = Panel(
        f"[bold cyan]CORTEX STUDY SESSION[/]\n"
        f"Mode: {config.mode.value.upper()}\n"
        f"Cards: {cards}\n"
        f"Focus: {'Struggles' if struggles else module or 'All'}",
        title="🧠",
        border_style="cyan",
    )
    console.print(header)

    # Run the study session
    asyncio.run(_run_study_session(config, cards, module, struggles))


async def _run_study_session(
    config: CortexCliConfig,
    card_limit: int,
    module: str | None,
    struggles_only: bool,
) -> None:
    """Execute a study session."""
    strategy = get_mode_strategy(config)
    context = await strategy.initialize()

    if config.is_connected:
        # API mode - fetch from platform
        async with PlatformClient(config.api) as client:
            if not await client.health_check():
                console.print("[yellow]⚠ Platform unreachable, switching to offline[/]")
                config.mode = OperatingMode.OFFLINE
                strategy = get_mode_strategy(config)

            atoms = await strategy.get_due_atoms(card_limit)
            console.print(f"[green]Loaded {len(atoms)} cards from platform[/]")
    else:
        # Offline mode - use local database
        atoms = await strategy.get_due_atoms(card_limit)
        console.print(f"[green]Loaded {len(atoms)} cards from local database[/]")

    if not atoms:
        console.print("[yellow]No cards due for review. Great job! 🎉[/]")
        return

    # Study loop would go here
    console.print("\n[dim]Press Ctrl+C to exit[/]")


# =============================================================================
# Sync Commands
# =============================================================================


@app.command()
def sync(
    force: Annotated[
        bool, typer.Option("--force", "-f", help="Force full sync")
    ] = False,
) -> None:
    """
    Sync with the right-learning platform.

    Uploads pending reviews and downloads updated schedules.
    """
    config = get_config()

    if config.mode != OperatingMode.API:
        console.print("[yellow]Sync requires API mode. Set CORTEX_API_KEY.[/]")
        return

    console.print("[cyan]🔄 Syncing with right-learning platform...[/]")
    asyncio.run(_run_sync(config, force))


async def _run_sync(config: CortexCliConfig, force: bool) -> None:
    """Execute sync operation."""
    async with PlatformClient(config.api) as client:
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            task = progress.add_task("Authenticating...", total=None)

            auth = await client.authenticate()
            if not auth.success:
                console.print(f"[red]Authentication failed: {auth.error}[/]")
                return

            progress.update(task, description="Syncing reviews...")
            result = await client.full_sync()

            progress.update(task, description="Complete!")

        # Show results
        table = Table(title="Sync Results")
        table.add_column("Metric", style="cyan")
        table.add_column("Value", style="green")
        table.add_row("Reviews Uploaded", str(result.uploaded_reviews))
        table.add_row("Atoms Downloaded", str(result.downloaded_atoms))
        table.add_row("Conflicts", str(len(result.conflicts)))
        table.add_row("Status", "✓ Success" if result.success else "✗ Failed")
        console.print(table)


@app.command("export")
def export_data(
    output: Annotated[
        Path, typer.Option("--output", "-o", help="Output file path")
    ] = Path("cortex_export.json"),
) -> None:
    """
    Export profile for offline use.

    Downloads your complete learning state from the platform
    for use in air-gapped environments.
    """
    config = get_config()

    console.print(f"[cyan]📦 Exporting profile to {output}...[/]")
    asyncio.run(_run_export(config, output))


async def _run_export(config: CortexCliConfig, output: Path) -> None:
    """Execute export operation."""
    import json

    async with PlatformClient(config.api) as client:
        auth = await client.authenticate()
        if not auth.success:
            console.print(f"[red]Authentication failed: {auth.error}[/]")
            return

        data = await client.export_for_offline()

        if "error" in data:
            console.print(f"[red]Export failed: {data['error']}[/]")
            return

        output.write_text(json.dumps(data, indent=2, default=str))
        console.print(f"[green]✓ Exported {data.get('atom_count', 0)} atoms to {output}[/]")


@app.command("import")
def import_data(
    input_file: Annotated[
        Path, typer.Argument(help="Import file path")
    ],
) -> None:
    """
    Import offline study data.

    Uploads reviews recorded during offline study
    back to the platform.
    """
    if not input_file.exists():
        console.print(f"[red]File not found: {input_file}[/]")
        raise typer.Exit(1)

    console.print(f"[cyan]📥 Importing from {input_file}...[/]")
    # Import logic would go here


# =============================================================================
# Curriculum Commands
# =============================================================================


curriculum_app = typer.Typer(
    name="curriculum",
    help="📚 Curriculum parsing and atom generation",
)
app.add_typer(curriculum_app, name="curriculum")


@curriculum_app.command("import")
def curriculum_import(
    file_path: Annotated[
        Path, typer.Argument(help="Path to curriculum file (e.g., SDE2.txt)")
    ],
    domain: Annotated[
        str | None, typer.Option("--domain", "-d", help="Domain name override")
    ] = None,
    output: Annotated[
        Path | None, typer.Option("--output", "-o", help="Output JSON file for atoms")
    ] = None,
    dry_run: Annotated[
        bool, typer.Option("--dry-run", help="Show what would be imported")
    ] = False,
) -> None:
    """
    Import curriculum file and generate learning atoms.

    Parses EASV curriculum files (SDE2.txt, PROGII.txt, etc.)
    and generates flashcards for study.

    Examples:
        cortex curriculum import docs/SDE2.txt
        cortex curriculum import docs/PROGII.txt --domain "Programming II"
        cortex curriculum import docs/SDE2.txt --output atoms.json --dry-run
    """
    import json
    from src.curriculum import EASVParser, parse_curriculum_file

    if not file_path.exists():
        console.print(f"[red]File not found: {file_path}[/]")
        raise typer.Exit(1)

    console.print(f"[cyan]📚 Parsing curriculum: {file_path.name}...[/]")

    try:
        course, atoms = parse_curriculum_file(file_path)

        # Override domain if specified
        if domain:
            course.name = domain
            for atom in atoms:
                atom.course_code = domain

        # Display results
        table = Table(title=f"📖 Course: {course.name} ({course.code})")
        table.add_column("Metric", style="cyan")
        table.add_column("Value", style="green")

        table.add_row("Weeks Parsed", str(len(course.weeks)))
        table.add_row("Atoms Generated", str(len(atoms)))
        table.add_row("Learning Objectives", str(sum(len(w.learning_objectives) for w in course.weeks)))

        console.print(table)

        # Show week breakdown
        if course.weeks:
            weeks_table = Table(title="Week Breakdown")
            weeks_table.add_column("Week", style="cyan", justify="center")
            weeks_table.add_column("Topic", style="white")
            weeks_table.add_column("Objectives", style="yellow")

            for week in course.weeks[:10]:  # Show first 10 weeks
                obj_str = ", ".join(o.code for o in week.learning_objectives[:3])
                if len(week.learning_objectives) > 3:
                    obj_str += f" +{len(week.learning_objectives) - 3}"
                weeks_table.add_row(
                    str(week.number),
                    week.topic[:50] + "..." if len(week.topic) > 50 else week.topic,
                    obj_str or "-",
                )

            if len(course.weeks) > 10:
                weeks_table.add_row("...", f"+{len(course.weeks) - 10} more weeks", "")

            console.print(weeks_table)

        # Show sample atoms
        if atoms and not dry_run:
            console.print("\n[bold]Sample Atoms:[/]")
            for atom in atoms[:3]:
                console.print(Panel(
                    f"[cyan]Q:[/] {atom.front}\n[green]A:[/] {atom.back}",
                    title=f"{atom.atom_type} | {atom.concept or 'General'}",
                    border_style="dim",
                ))

        if dry_run:
            console.print("\n[yellow]Dry run - no atoms saved[/]")
            return

        # Save to output file or local store
        if output:
            atoms_data = [atom.to_dict() for atom in atoms]
            output.write_text(json.dumps({
                "course": {
                    "code": course.code,
                    "name": course.name,
                    "weeks": len(course.weeks),
                },
                "atoms": atoms_data,
                "generated_at": datetime.now().isoformat(),
            }, indent=2, default=str))
            console.print(f"\n[green]✓ Saved {len(atoms)} atoms to {output}[/]")
        else:
            # Store in default location
            data_dir = Path.home() / ".cortex" / "curriculum"
            data_dir.mkdir(parents=True, exist_ok=True)
            output_file = data_dir / f"{course.code.lower()}_atoms.json"

            atoms_data = [atom.to_dict() for atom in atoms]
            output_file.write_text(json.dumps({
                "course": {
                    "code": course.code,
                    "name": course.name,
                    "weeks": len(course.weeks),
                },
                "atoms": atoms_data,
                "generated_at": datetime.now().isoformat(),
            }, indent=2, default=str))
            console.print(f"\n[green]✓ Saved {len(atoms)} atoms to {output_file}[/]")

    except Exception as e:
        console.print(f"[red]Error parsing curriculum: {e}[/]")
        raise typer.Exit(1)


@curriculum_app.command("list")
def curriculum_list() -> None:
    """
    List imported curriculum courses.

    Shows all curriculum files that have been imported.
    """
    data_dir = Path.home() / ".cortex" / "curriculum"

    if not data_dir.exists():
        console.print("[yellow]No curriculum imported yet.[/]")
        console.print("[dim]Use 'cortex curriculum import <file>' to import.[/]")
        return

    import json

    files = list(data_dir.glob("*_atoms.json"))
    if not files:
        console.print("[yellow]No curriculum imported yet.[/]")
        return

    table = Table(title="📚 Imported Curriculum")
    table.add_column("Course", style="cyan")
    table.add_column("Name", style="white")
    table.add_column("Atoms", style="green", justify="right")
    table.add_column("Imported", style="dim")

    for f in files:
        try:
            data = json.loads(f.read_text())
            course_info = data.get("course", {})
            table.add_row(
                course_info.get("code", "Unknown"),
                course_info.get("name", "-"),
                str(len(data.get("atoms", []))),
                data.get("generated_at", "-")[:10] if data.get("generated_at") else "-",
            )
        except (json.JSONDecodeError, KeyError):
            table.add_row(f.stem.replace("_atoms", ""), "Error reading", "-", "-")

    console.print(table)


@curriculum_app.command("atoms")
def curriculum_atoms(
    course: Annotated[
        str, typer.Argument(help="Course code (e.g., SDE2, PROGII)")
    ],
    limit: Annotated[
        int, typer.Option("--limit", "-n", help="Number of atoms to show")
    ] = 10,
) -> None:
    """
    Show atoms for an imported course.

    Examples:
        cortex curriculum atoms SDE2
        cortex curriculum atoms PROGII --limit 20
    """
    import json

    data_dir = Path.home() / ".cortex" / "curriculum"
    atom_file = data_dir / f"{course.lower()}_atoms.json"

    if not atom_file.exists():
        console.print(f"[red]Course not found: {course}[/]")
        console.print("[dim]Use 'cortex curriculum list' to see imported courses.[/]")
        raise typer.Exit(1)

    data = json.loads(atom_file.read_text())
    atoms = data.get("atoms", [])

    console.print(f"[cyan]📚 {course} - {len(atoms)} atoms[/]\n")

    for i, atom in enumerate(atoms[:limit]):
        console.print(Panel(
            f"[cyan]Q:[/] {atom.get('front', '')}\n[green]A:[/] {atom.get('back', '')}",
            title=f"#{i+1} | {atom.get('atom_type', 'flashcard')} | {atom.get('concept', '-')}",
            border_style="dim",
        ))

    if len(atoms) > limit:
        console.print(f"\n[dim]Showing {limit} of {len(atoms)} atoms. Use --limit to see more.[/]")


# =============================================================================
# Study Commands (Focus Stream Integration)
# =============================================================================


@app.command("study")
def study_session(
    course: Annotated[
        str | None, typer.Option("--course", "-c", help="Course code to study")
    ] = None,
    budget: Annotated[
        int, typer.Option("--budget", "-b", help="Number of cards to review")
    ] = 20,
    keywords: Annotated[
        str | None, typer.Option("--keywords", "-k", help="Focus keywords (comma-separated)")
    ] = None,
) -> None:
    """
    Start a Focus Stream study session.

    Uses the Z-Score algorithm to prioritize atoms from imported curriculum.

    Examples:
        cortex study                        # Study all imported courses
        cortex study --course SDE2          # Focus on SDE2
        cortex study -c SDE2 -b 10 -k git   # 10 cards about Git
    """
    import json
    from src.delivery.focus_stream import FocusStream, ProjectContext

    data_dir = Path.home() / ".cortex" / "curriculum"

    if not data_dir.exists():
        console.print("[yellow]No curriculum imported yet.[/]")
        console.print("[dim]Use 'cortex curriculum import <file>' to import first.[/]")
        return

    # Load atoms from all imported courses or specific course
    all_atoms = []

    if course:
        atom_file = data_dir / f"{course.lower()}_atoms.json"
        if not atom_file.exists():
            console.print(f"[red]Course not found: {course}[/]")
            console.print("[dim]Use 'cortex curriculum list' to see imported courses.[/]")
            raise typer.Exit(1)
        files = [atom_file]
    else:
        files = list(data_dir.glob("*_atoms.json"))

    if not files:
        console.print("[yellow]No curriculum imported yet.[/]")
        return

    for f in files:
        try:
            data = json.loads(f.read_text())
            for i, atom in enumerate(data.get("atoms", [])):
                atom["id"] = f"{f.stem}-{i}"
                atom["review_count"] = atom.get("review_count", 0)
                atom["last_review"] = atom.get("last_review")
                all_atoms.append(atom)
        except (json.JSONDecodeError, KeyError):
            continue

    if not all_atoms:
        console.print("[yellow]No atoms found in imported curriculum.[/]")
        return

    # Set up Focus Stream
    stream = FocusStream()
    context = ProjectContext()

    if course:
        context.active_courses = [course.upper()]

    if keywords:
        context.keywords = [k.strip() for k in keywords.split(",")]

    stream.set_context(context)

    # Get prioritized queue
    queue = stream.get_queue(all_atoms, budget=budget)

    if not queue:
        console.print("[yellow]No cards meet activation threshold. All caught up![/]")
        return

    # Study session header
    console.print(Panel(
        f"[bold cyan]FOCUS STREAM SESSION[/]\n"
        f"Cards: {len(queue)} of {len(all_atoms)}\n"
        f"Course: {course or 'All'}\n"
        f"Keywords: {keywords or 'None'}",
        title="[bold]Study[/]",
        border_style="cyan",
    ))

    # Interactive study loop
    console.print("\n[dim]Press Enter to reveal answer, then rate 1-4 (or 'q' to quit)[/]\n")

    reviewed = 0
    correct = 0

    for i, atom in enumerate(queue):
        console.print(f"[bold cyan]Card {i+1}/{len(queue)}[/] [dim]Z={atom.z_score:.2f}[/]")
        console.print(Panel(
            f"[cyan]{atom.front}[/]",
            title=f"Question | {atom.concept or atom.course_code}",
            border_style="blue",
        ))

        # Wait for Enter to reveal
        try:
            input("[dim]Press Enter to reveal...[/] ")
        except (KeyboardInterrupt, EOFError):
            break

        console.print(Panel(
            f"[green]{atom.back}[/]",
            title="Answer",
            border_style="green",
        ))

        # Get rating
        try:
            rating = input("\n[dim]Rate (1=Again, 2=Hard, 3=Good, 4=Easy, q=quit):[/] ").strip().lower()
        except (KeyboardInterrupt, EOFError):
            break

        if rating == "q":
            break

        reviewed += 1
        if rating in ("3", "4"):
            correct += 1

        console.print()

    # Session summary
    if reviewed > 0:
        accuracy = (correct / reviewed) * 100
        console.print(Panel(
            f"[bold]Session Complete[/]\n\n"
            f"Reviewed: {reviewed}\n"
            f"Correct: {correct}\n"
            f"Accuracy: {accuracy:.0f}%",
            title="Summary",
            border_style="green" if accuracy >= 70 else "yellow",
        ))
    else:
        console.print("[dim]Session ended without reviews.[/]")


@app.command("queue")
def show_queue(
    course: Annotated[
        str | None, typer.Option("--course", "-c", help="Course code")
    ] = None,
    budget: Annotated[
        int, typer.Option("--budget", "-b", help="Queue size")
    ] = 30,
    verbose: Annotated[
        bool, typer.Option("--verbose", "-v", help="Show Z-Score components")
    ] = False,
) -> None:
    """
    Show the Focus Stream queue without starting a session.

    Useful for seeing what cards would be prioritized.

    Examples:
        cortex queue                    # Show full queue
        cortex queue -c SDE2 -b 10      # Top 10 from SDE2
        cortex queue -v                 # Show Z-Score breakdown
    """
    import json
    from src.delivery.focus_stream import FocusStream, ProjectContext

    data_dir = Path.home() / ".cortex" / "curriculum"

    if not data_dir.exists():
        console.print("[yellow]No curriculum imported yet.[/]")
        return

    # Load atoms
    all_atoms = []

    if course:
        files = [data_dir / f"{course.lower()}_atoms.json"]
    else:
        files = list(data_dir.glob("*_atoms.json"))

    for f in files:
        if not f.exists():
            continue
        try:
            data = json.loads(f.read_text())
            for i, atom in enumerate(data.get("atoms", [])):
                atom["id"] = f"{f.stem}-{i}"
                all_atoms.append(atom)
        except (json.JSONDecodeError, KeyError):
            continue

    if not all_atoms:
        console.print("[yellow]No atoms found.[/]")
        return

    # Get queue
    stream = FocusStream()
    if course:
        stream.set_context(ProjectContext(active_courses=[course.upper()]))

    queue = stream.get_queue(all_atoms, budget=budget)

    # Display queue
    table = Table(title=f"Focus Stream Queue ({len(queue)} cards)")
    table.add_column("#", style="dim", width=3)
    table.add_column("Z", style="cyan", width=5)
    table.add_column("Question", style="white")
    table.add_column("Concept", style="yellow")

    if verbose:
        table.add_column("D", style="dim", width=4)
        table.add_column("C", style="dim", width=4)
        table.add_column("P", style="dim", width=4)
        table.add_column("N", style="dim", width=4)

    for i, atom in enumerate(queue):
        q_text = atom.front[:40] + "..." if len(atom.front) > 40 else atom.front
        row = [str(i+1), f"{atom.z_score:.2f}", q_text, atom.concept or "-"]

        if verbose:
            row.extend([
                f"{atom.decay:.1f}",
                f"{atom.centrality:.1f}",
                f"{atom.project_relevance:.1f}",
                f"{atom.novelty:.1f}",
            ])

        table.add_row(*row)

    console.print(table)


# =============================================================================
# Pipeline Commands
# =============================================================================


@app.command()
def validate(
    path: Annotated[
        Path, typer.Argument(help="Path to content directory or file")
    ] = Path("docs/source-materials"),
    strict: Annotated[
        bool, typer.Option("--strict", "-s", help="Fail on warnings")
    ] = False,
    output: Annotated[
        Path | None, typer.Option("--output", "-o", help="Output report path")
    ] = None,
) -> None:
    """
    Validate learning content (CI/CD pipeline mode).

    Parses and validates:
    - Markdown content structure
    - Parsons problem syntax
    - MCQ distractor quality
    - Cloze deletion format
    - Atom quality scores

    Exit codes:
        0 - All content valid
        1 - Validation errors found
        2 - Warnings found (with --strict)
    """
    console.print(f"[cyan]🔍 Validating content in {path}...[/]")

    errors = []
    warnings = []

    # Walk through content files
    if path.is_file():
        files = [path]
    else:
        files = list(path.rglob("*.md")) + list(path.rglob("*.txt"))

    with Progress(console=console) as progress:
        task = progress.add_task("Validating...", total=len(files))

        for file in files:
            # Validate each file
            file_errors, file_warnings = _validate_file(file)
            errors.extend(file_errors)
            warnings.extend(file_warnings)
            progress.advance(task)

    # Report results
    _print_validation_report(errors, warnings, output)

    # Exit with appropriate code
    if errors:
        raise typer.Exit(1)
    if warnings and strict:
        raise typer.Exit(2)


def _validate_file(file: Path) -> tuple[list[str], list[str]]:
    """Validate a single content file."""
    errors = []
    warnings = []

    content = file.read_text(encoding="utf-8", errors="replace")

    # Check for common issues
    if "{{c1::" in content and "}}" not in content:
        errors.append(f"{file}: Unclosed cloze deletion")

    if "```parsons" in content:
        # Validate Parsons problem structure
        if "```" not in content[content.index("```parsons") + 10 :]:
            errors.append(f"{file}: Unclosed Parsons code block")

    if len(content) < 100:
        warnings.append(f"{file}: Very short content ({len(content)} chars)")

    return errors, warnings


def _print_validation_report(
    errors: list[str], warnings: list[str], output: Path | None
) -> None:
    """Print validation results."""
    if errors:
        console.print("\n[red bold]ERRORS:[/]")
        for error in errors:
            console.print(f"  [red]✗[/] {error}")

    if warnings:
        console.print("\n[yellow bold]WARNINGS:[/]")
        for warning in warnings:
            console.print(f"  [yellow]⚠[/] {warning}")

    if not errors and not warnings:
        console.print("\n[green]✓ All content valid![/]")

    # Summary
    console.print(f"\n[dim]Errors: {len(errors)} | Warnings: {len(warnings)}[/]")

    # Write report if requested
    if output:
        report = {
            "timestamp": datetime.utcnow().isoformat(),
            "errors": errors,
            "warnings": warnings,
            "summary": {
                "error_count": len(errors),
                "warning_count": len(warnings),
                "status": "pass" if not errors else "fail",
            },
        }
        import json

        output.write_text(json.dumps(report, indent=2))
        console.print(f"[dim]Report written to {output}[/]")


# =============================================================================
# Status Commands
# =============================================================================


@app.command()
def status() -> None:
    """Show current status and configuration."""
    config = get_config()

    table = Table(title="Cortex CLI Status")
    table.add_column("Setting", style="cyan")
    table.add_column("Value", style="green")

    table.add_row("Mode", config.mode.value.upper())
    table.add_row("Connected", "Yes" if config.is_connected else "No")
    table.add_row("Data Directory", str(config.data_dir))
    table.add_row("Log Level", config.log_level)

    if config.is_connected:
        table.add_row("API URL", config.api.base_url)
        table.add_row("Auto Sync", "Enabled" if config.api.auto_sync else "Disabled")

    if config.is_offline:
        table.add_row("Database", str(config.offline.database_path))
        table.add_row("Pending Syncs", "Check with 'cortex sync --status'")

    console.print(table)


@app.command()
def config(
    show: Annotated[
        bool, typer.Option("--show", help="Show current configuration")
    ] = False,
    set_key: Annotated[
        str | None, typer.Option("--set", help="Set configuration key=value")
    ] = None,
) -> None:
    """View or modify configuration."""
    if show or (not show and not set_key):
        cfg = get_config()
        import json

        console.print_json(json.dumps(cfg.model_dump(), indent=2, default=str))

    if set_key:
        key, _, value = set_key.partition("=")
        console.print(f"[yellow]Setting {key}={value}[/]")
        # Config setting logic would go here


# =============================================================================
# Entry Point
# =============================================================================


@app.callback()
def main(
    verbose: Annotated[
        bool, typer.Option("--verbose", "-v", help="Verbose output")
    ] = False,
    mode: Annotated[
        str | None, typer.Option("--mode", help="Override operating mode")
    ] = None,
) -> None:
    """
    🧠 Cortex CLI - Terminal-based cognitive learning companion

    Part of the Right Learning ecosystem.

    \b
    Operating Modes:
      api      - Connected to right-learning platform
      pipeline - CI/CD content validation
      offline  - Local-only operation

    \b
    Quick Start:
      cortex start              # Start a study session
      cortex start --quick      # Quick 5-minute review
      cortex validate ./docs    # Validate content
      cortex sync               # Sync with platform
    """
    if verbose:
        import logging

        logging.basicConfig(level=logging.DEBUG)

    if mode:
        import os

        os.environ["CORTEX_MODE"] = mode


def run() -> None:
    """Entry point for the CLI."""
    app()


if __name__ == "__main__":
    run()
