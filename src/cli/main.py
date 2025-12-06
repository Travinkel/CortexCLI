"""
Typer CLI for notion-learning-sync service.

Commands:
    nls sync notion         - Sync all Notion databases to PostgreSQL
    nls sync anki-push      - Push clean atoms to Anki
    nls sync anki-pull      - Pull FSRS stats from Anki
    nls sync all            - Full sync pipeline
    nls db init             - Initialize database tables
    nls db migrate          - Run SQL migrations
    nls clean run           - Run atomicity cleaning pipeline
    nls clean check         - Check quality without modifications
    nls export cards        - Export cards to CSV
    nls export stats        - Export Anki stats to CSV
    nls study today         - Show daily study session summary
    nls study path          - Show full CCNA learning path
    nls study module <n>    - Show module details
    nls study stats         - Show study statistics
    nls study sync          - Sync mastery from Anki
    nls study remediation   - Show sections needing remediation
    nls war study --modules 11,12,13 - War Room: Focus on specific modules
    nls war study --cram             - War Room: Cram mode (Modules 11-17)
    nls war study -d 30              - War Room: 30-minute session
    nls war stats                    - War Room: Show session statistics

Usage:
    nls --help
    nls sync notion
    nls sync all --dry-run
    nls db migrate --migration 014
    nls war study --cram
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

import json
from pathlib import Path
from typing import Optional

import typer
from loguru import logger
from rich import print as rprint
from rich.console import Console
from rich.table import Table

from config import get_settings

app = typer.Typer(
    help="notion-learning-sync CLI: Notion -> PostgreSQL -> Anki cognitive pipeline",
    no_args_is_help=False,  # Allow running without args for interactive mode
    invoke_without_command=True,
)

# Import and register study commands
from src.cli.study_commands import study_app
app.add_typer(study_app, name="study")

# Import and register war room commands
from src.cli.war_room import app as war_app
app.add_typer(war_app, name="war")

# Cortex (rich dashboard CLI)
from src.cli.cortex import cortex_app
app.add_typer(cortex_app, name="cortex")

# Cortex 2.0 Sync Commands (Notion <-> Neo4j)
from src.cli.cortex_sync import (
    sync_app as cortex_sync_app,
    graph_app,
    zscore_app,
    forcez_app,
)
# Note: We register these under the cortex namespace for organization
# Usage: nls cortex sync pull, nls cortex graph stats, etc.
cortex_app.add_typer(cortex_sync_app, name="sync2")  # sync2 to avoid conflict with existing sync
cortex_app.add_typer(graph_app, name="graph")
cortex_app.add_typer(zscore_app, name="zscore")
cortex_app.add_typer(forcez_app, name="forcez")

console = Console()


@app.callback()
def main_callback(ctx: typer.Context):
    """
    CCNA Learning Path CLI.

    Run without arguments to start an interactive study session with
    continuous Anki sync. Or use subcommands for specific operations.
    """
    # If no subcommand is provided, launch interactive mode
    if ctx.invoked_subcommand is None:
        from src.cli.interactive import main as interactive_main
        interactive_main()


# ========================================
# Context Builder (Dependency Injection)
# ========================================


class CLIContext:
    """
    Dependency injection container for CLI commands.

    Lazily initializes services to avoid import errors during development.
    """

    def __init__(self, dry_run: bool = False):
        self.settings = get_settings()
        self.dry_run = dry_run or self.settings.dry_run
        self._notion_adapter = None
        self._sync_service = None
        self._anki_client = None
        self._cleaning_pipeline = None

    @property
    def notion_adapter(self):
        """Lazy load NotionAdapter."""
        if self._notion_adapter is None:
            from src.sync.notion_adapter import NotionAdapter

            self._notion_adapter = NotionAdapter(settings=self.settings)
        return self._notion_adapter

    @property
    def sync_service(self):
        """Lazy load SyncService (Phase 2)."""
        if self._sync_service is None:
            try:
                from src.sync.sync_service import SyncService
                from src.sync.notion_client import NotionClient

                # Create progress callback for CLI
                def progress_callback(entity_type: str, current: int, total: int):
                    if current % 100 == 0 or current == total:
                        rprint(f"  [{entity_type}] {current}/{total} pages processed...")

                self._sync_service = SyncService(
                    notion_client=NotionClient(),
                    progress_callback=progress_callback,
                )
            except ImportError:
                logger.error("SyncService not yet implemented (Phase 2)")
                raise typer.Exit(code=1)
        return self._sync_service

    @property
    def anki_client(self):
        """Lazy load AnkiClient (Phase 4)."""
        if self._anki_client is None:
            try:
                from src.anki.anki_client import AnkiClient

                self._anki_client = AnkiClient(settings=self.settings)
            except ImportError:
                logger.error("AnkiClient not yet implemented (Phase 4)")
                raise typer.Exit(code=1)
        return self._anki_client

    @property
    def cleaning_pipeline(self):
        """Lazy load CleaningPipeline (Phase 3)."""
        if self._cleaning_pipeline is None:
            try:
                from src.cleaning.pipeline import CleaningPipeline

                self._cleaning_pipeline = CleaningPipeline(settings=self.settings)
            except ImportError:
                logger.error("CleaningPipeline not yet implemented (Phase 3)")
                raise typer.Exit(code=1)
        return self._cleaning_pipeline


def _build_context(dry_run: bool = False) -> CLIContext:
    """Build CLI context with dependency injection."""
    return CLIContext(dry_run=dry_run)


# ========================================
# SYNC COMMANDS
# ========================================

sync_app = typer.Typer(help="Sync operations (Notion <-> PostgreSQL <-> Anki)")
app.add_typer(sync_app, name="sync")


@sync_app.command("notion")
def sync_notion(
    dry_run: bool = typer.Option(
        False, "--dry-run", help="Preview changes without writing to database"
    ),
    incremental: bool = typer.Option(
        True, "--incremental/--full", help="Use incremental sync (last_edited_time)"
    ),
    parallel: bool = typer.Option(
        False, "--parallel", help="Sync databases concurrently (faster, higher API load)"
    ),
) -> None:
    """
    Sync all configured Notion databases to PostgreSQL.

    Fetches from all 18 Notion databases (if configured) and upserts to
    staging tables. Run with --dry-run to preview changes.

    Examples:
        nls sync notion                    # Incremental sync (changed pages only)
        nls sync notion --full             # Full sync (all pages)
        nls sync notion --dry-run          # Preview without writing
        nls sync notion --parallel         # Faster concurrent fetching
    """
    ctx = _build_context(dry_run=dry_run)

    rprint("\n[bold cyan]Notion -> PostgreSQL Sync[/bold cyan]")
    rprint(f"  Mode: {'Incremental' if incremental else 'Full'}")
    rprint(f"  Dry run: {ctx.dry_run}")
    rprint(f"  Parallel: {parallel}\n")

    # Phase 2 implementation
    results = ctx.sync_service.sync_all_databases(
        incremental=incremental,
        dry_run=ctx.dry_run,
        parallel=parallel,
    )

    # Display results
    table = Table(title="Sync Results", show_header=True)
    table.add_column("Entity Type", style="cyan")
    table.add_column("Added", justify="right", style="green")
    table.add_column("Updated", justify="right", style="yellow")
    table.add_column("Skipped", justify="right", style="dim")
    table.add_column("Errors", justify="right", style="red")

    total_added = 0
    total_updated = 0
    total_skipped = 0
    total_errors = 0

    for entity_type, counts in results.items():
        added = counts.get("added", 0)
        updated = counts.get("updated", 0)
        skipped = counts.get("skipped", 0)
        errors = counts.get("errors", 0)

        total_added += added
        total_updated += updated
        total_skipped += skipped
        total_errors += errors

        table.add_row(
            entity_type,
            str(added),
            str(updated),
            str(skipped),
            str(errors) if errors > 0 else "-",
        )

    table.add_section()
    table.add_row(
        "TOTAL",
        str(total_added),
        str(total_updated),
        str(total_skipped),
        str(total_errors) if total_errors > 0 else "-",
        style="bold",
    )

    console.print(table)

    if total_errors > 0:
        rprint(f"\n[yellow]⚠[/yellow] {total_errors} errors occurred during sync")
        rprint("  Check logs for details")
    else:
        rprint(f"\n[bold green]✓ Sync complete![/bold green]")

    logger.info("Notion sync complete!")


@sync_app.command("anki-push")
def sync_anki_push(
    dry_run: bool = typer.Option(False, "--dry-run", help="Preview without pushing to Anki"),
    quality_filter: str = typer.Option(
        "B", "--min-quality", help="Minimum quality grade to push (A/B/C/D/F)"
    ),
) -> None:
    """
    Push clean atoms from PostgreSQL to Anki.

    Only pushes cards with quality grade >= min-quality.
    Updates existing cards and creates new ones via AnkiConnect.
    """
    ctx = _build_context(dry_run=dry_run)

    logger.info(f"Pushing clean atoms to Anki (min quality: {quality_filter})...")

    # Phase 4 implementation
    from src.anki.push_service import push_clean_atoms

    result = push_clean_atoms(
        anki_client=ctx.anki_client,
        min_quality=quality_filter,
        dry_run=ctx.dry_run,
    )

    rprint(f"\n[green]✓[/green] Pushed {result['updated']} cards to Anki")
    rprint(f"  Created: {result['created']}")
    rprint(f"  Updated: {result['updated']}")
    rprint(f"  Skipped: {result['skipped']}")


@sync_app.command("anki-pull")
def sync_anki_pull(
    dry_run: bool = typer.Option(False, "--dry-run", help="Preview without writing to DB"),
    deck: Optional[str] = typer.Option(None, "--deck", help="Deck name (default: from config)"),
) -> None:
    """
    Pull FSRS stats from Anki to PostgreSQL.

    Fetches ease_factor, interval, stability, retrievability, etc.
    Updates clean_atoms table with latest Anki metadata.
    """
    ctx = _build_context(dry_run=dry_run)

    deck_name = deck or ctx.settings.anki_deck_name
    logger.info(f"Pulling FSRS stats from Anki deck: {deck_name}...")

    # Phase 4 implementation
    from src.anki.pull_service import pull_review_stats

    result = pull_review_stats(
        anki_client=ctx.anki_client,
        deck_name=deck_name,
        dry_run=ctx.dry_run,
    )

    rprint(f"\n[green]✓[/green] Pulled stats for {result['updated']} cards")
    rprint(f"  New cards: {result['new']}")
    rprint(f"  Updated: {result['updated']}")
    rprint(f"  Missing in DB: {result['missing']}")


@sync_app.command("all")
def sync_all(
    dry_run: bool = typer.Option(False, "--dry-run", help="Preview without changes"),
) -> None:
    """
    Run full sync pipeline: Notion -> PostgreSQL -> Clean -> Anki.

    This is the primary sync command. It orchestrates:
    1. Notion -> PostgreSQL (staging)
    2. Cleaning pipeline (staging -> canonical)
    3. Push to Anki (canonical -> AnkiConnect)
    4. Pull FSRS stats (Anki -> canonical)
    """
    ctx = _build_context(dry_run=dry_run)

    logger.info("Starting FULL sync pipeline...")

    # Phase 2-4 implementation
    result = ctx.sync_service.sync_full()

    rprint("\n[bold green]✓ Full sync complete![/bold green]")
    rprint(f"  Notion -> PostgreSQL: {result['notion']['total']} items")
    rprint(f"  Cleaning: {result['cleaning']['processed']} atoms")
    rprint(f"  Anki push: {result['anki_push']['updated']} cards")
    rprint(f"  Anki pull: {result['anki_pull']['updated']} stats")


# ========================================
# ANKI COMMANDS
# ========================================

anki_app = typer.Typer(help="Anki deck import and management")
app.add_typer(anki_app, name="anki")


@anki_app.command("import")
def anki_import(
    deck: Optional[str] = typer.Option(
        None, "--deck", help="Deck name to import (default: from config)"
    ),
    dry_run: bool = typer.Option(
        False, "--dry-run", help="Preview import without writing to database"
    ),
    quality_analysis: bool = typer.Option(
        True, "--quality/--no-quality", help="Run quality analysis during import"
    ),
) -> None:
    """
    Import existing Anki deck into PostgreSQL staging table.

    Workflow:
    1. Fetch all cards from Anki via AnkiConnect
    2. Extract FSRS stats (stability, difficulty, retrievability)
    3. Parse prerequisite tags (tag:prereq:domain:topic:subtopic)
    4. Run quality analysis (word counts, atomicity check)
    5. Insert into stg_anki_cards table

    The imported cards can then be analyzed for quality, split if non-atomic,
    and have prerequisites extracted for the prerequisite system.

    Examples:
        nls anki import
        nls anki import --deck "CCNA Study"
        nls anki import --dry-run
        nls anki import --no-quality
    """
    settings = get_settings()
    deck_name = deck or settings.anki_deck_name

    logger.info("=" * 60)
    logger.info("ANKI DECK IMPORT")
    logger.info("=" * 60)
    logger.info(f"  Deck: {deck_name}")
    logger.info(f"  Dry run: {dry_run}")
    logger.info(f"  Quality analysis: {quality_analysis}")
    logger.info("")

    # Import service
    try:
        from src.anki.import_service import AnkiImportService

        service = AnkiImportService()
    except ImportError as exc:
        logger.error(f"Failed to import AnkiImportService: {exc}")
        raise typer.Exit(code=1)

    # Check AnkiConnect connection first
    rprint("[yellow]Checking AnkiConnect connection...[/yellow]")
    if not service.anki_client.check_connection():
        rprint("[red]✗[/red] Failed to connect to AnkiConnect")
        rprint("")
        rprint("Please ensure:")
        rprint("  1. Anki is running")
        rprint("  2. AnkiConnect add-on is installed")
        rprint("  3. AnkiConnect is accessible at http://localhost:8765")
        raise typer.Exit(code=1)

    rprint("[green]✓[/green] Connected to AnkiConnect\n")

    # Run import
    try:
        rprint(f"[yellow]Importing cards from deck: {deck_name}...[/yellow]\n")

        result = service.import_deck(
            deck_name=deck_name,
            dry_run=dry_run,
            quality_analysis=quality_analysis,
        )

        if not result.get("success"):
            rprint(f"[red]✗[/red] Import failed: {result.get('error', 'Unknown error')}")
            raise typer.Exit(code=1)

        # Display results
        rprint(f"\n[bold green]✓ Import {'preview' if dry_run else 'complete'}![/bold green]\n")

        # Create summary table
        table = Table(title="Import Summary", show_header=True)
        table.add_column("Metric", style="cyan")
        table.add_column("Count", justify="right", style="green")

        table.add_row("Cards imported", str(result["cards_imported"]))
        table.add_row("Cards with FSRS stats", str(result["cards_with_fsrs"]))
        table.add_row(
            "Cards with prerequisites",
            str(result["cards_with_prerequisites"]),
        )
        table.add_row(
            "Cards needing split",
            str(result["cards_needing_split"]),
            style="yellow" if result["cards_needing_split"] > 0 else None,
        )

        console.print(table)

        # Display quality distribution
        if quality_analysis:
            grade_dist = result.get("grade_distribution", {})

            rprint("\n[bold]Quality Distribution:[/bold]")
            rprint(f"  Grade A (excellent):  {grade_dist.get('A', 0)}")
            rprint(f"  Grade B (good):       {grade_dist.get('B', 0)}")
            rprint(f"  Grade C (acceptable): {grade_dist.get('C', 0)}")
            rprint(f"  Grade D (needs work): [yellow]{grade_dist.get('D', 0)}[/yellow]")
            rprint(f"  Grade F (split/fix):  [red]{grade_dist.get('F', 0)}[/red]")

        # Display errors if any
        errors = result.get("errors", [])
        if errors:
            rprint(f"\n[yellow]Warnings ({len(errors)}):[/yellow]")
            for error in errors[:5]:  # Show first 5 errors
                rprint(f"  - {error}")
            if len(errors) > 5:
                rprint(f"  ... and {len(errors) - 5} more")

        # Next steps
        if not dry_run:
            rprint("\n[bold]Next Steps:[/bold]")

            needs_split = result["cards_needing_split"]
            if needs_split > 0:
                rprint(f"  1. Review {needs_split} cards flagged for splitting")
                rprint("     Run: [cyan]nls clean split --batch[/cyan]")

            if result["cards_with_prerequisites"] > 0:
                rprint("  2. Analyze prerequisite hierarchy")
                rprint("     Run: [cyan]nls prereq analyze[/cyan]")

            rprint("  3. Run full quality analysis")
            rprint("     Run: [cyan]nls clean check[/cyan]")

        logger.info("Anki import completed successfully!")

    except Exception as exc:
        logger.exception("Unexpected error during import")
        rprint(f"\n[red]✗[/red] Import failed: {exc}")
        raise typer.Exit(code=1)


# ========================================
# DATABASE COMMANDS
# ========================================

db_app = typer.Typer(help="Database management (init, migrate)")
app.add_typer(db_app, name="db")


@db_app.command("init")
def db_init() -> None:
    """
    Initialize database tables from SQLAlchemy models.

    Creates all tables defined in src/db/models.py if they don't exist.
    Safe to run multiple times (idempotent).
    """
    logger.info("Initializing database tables...")

    try:
        from src.db.database import engine, init_db
        from src.db.models import Base

        Base.metadata.create_all(engine)
        rprint("[green]✓[/green] Database initialized!")
    except ImportError:
        logger.error("Database models not yet implemented")
        raise typer.Exit(code=1)


@db_app.command("migrate")
def db_migrate(
    migration: str = typer.Option(
        "014",
        "--migration",
        "-m",
        help="Migration number (e.g., '014' for 014_learning_atoms_quality.sql)",
    ),
    force: bool = typer.Option(
        False, "--force", help="Run migration even if already applied"
    ),
) -> None:
    """
    Run raw SQL migration files.

    Migrations are located in src/db/migrations/.
    Skips statements that already exist (idempotent).
    """
    from pathlib import Path
    from sqlalchemy import text

    logger.info(f"Running migration: {migration}")

    # Find migration file
    migrations_dir = Path(__file__).parent.parent / "db" / "migrations"
    migration_files = sorted(migrations_dir.glob(f"{migration}*.sql"))

    if not migration_files:
        logger.error(f"No migration found matching: {migration}")
        logger.info(f"Available migrations in {migrations_dir}:")
        for f in sorted(migrations_dir.glob("*.sql")):
            logger.info(f"  - {f.name}")
        raise typer.Exit(code=1)

    migration_file = migration_files[0]
    logger.info(f"Found: {migration_file.name}")

    sql_content = migration_file.read_text(encoding="utf-8")

    # Execute migration
    from src.db.database import engine

    with engine.connect() as conn:
        # Split by semicolons (handle DO $$ blocks)
        statements = []
        current = []
        in_block = False

        for line in sql_content.split("\n"):
            stripped = line.strip()

            if stripped.startswith("DO $$"):
                in_block = True
            if in_block and stripped.endswith("$$;"):
                in_block = False

            current.append(line)

            if stripped.endswith(";") and not in_block:
                stmt = "\n".join(current).strip()
                if stmt and not stmt.startswith("--"):
                    statements.append(stmt)
                current = []

        # Execute each statement
        executed = 0
        skipped = 0
        errors = 0

        for i, stmt in enumerate(statements, 1):
            if stmt.strip():
                try:
                    conn.execute(text(stmt))
                    conn.commit()
                    executed += 1
                except Exception as e:
                    if "already exists" in str(e) or "duplicate" in str(e).lower():
                        skipped += 1
                        logger.debug(f"Statement {i}: Already exists (skipped)")
                    else:
                        errors += 1
                        logger.error(f"Statement {i} failed: {e}")

        rprint(f"\n[green]✓[/green] Migration complete!")
        rprint(f"  Executed: {executed}")
        rprint(f"  Skipped: {skipped}")
        if errors > 0:
            rprint(f"  [red]Errors: {errors}[/red]")


# ========================================
# CLEANING COMMANDS
# ========================================

clean_app = typer.Typer(help="Quality cleaning pipeline")
app.add_typer(clean_app, name="clean")


@clean_app.command("run")
def clean_run(
    dry_run: bool = typer.Option(False, "--dry-run", help="Preview without changes"),
    rewrite: bool = typer.Option(False, "--rewrite", help="Enable AI rewriting for grade D/F"),
) -> None:
    """
    Run atomicity cleaning pipeline on staging tables.

    Transforms staging -> canonical with quality analysis, duplicate detection,
    and optional AI rewriting.
    """
    ctx = _build_context(dry_run=dry_run)

    logger.info("Running cleaning pipeline...")

    # Phase 3 implementation
    result = ctx.cleaning_pipeline.process_all(enable_rewrite=rewrite)

    rprint(f"\n[green]✓[/green] Cleaning complete!")
    rprint(f"  Processed: {result['processed']}")
    rprint(f"  Grade A: {result['grade_a']}")
    rprint(f"  Grade B: {result['grade_b']}")
    rprint(f"  Grade C: {result['grade_c']}")
    rprint(f"  Grade D: {result['grade_d']}")
    rprint(f"  Grade F: {result['grade_f']}")
    if rewrite:
        rprint(f"  Rewritten: {result['rewritten']}")


@clean_app.command("check")
def clean_check(
    limit: int = typer.Option(100, "--limit", "-l", help="Max atoms to check"),
) -> None:
    """
    Check atomicity quality without modifications.

    Analyzes clean_atoms table and reports quality distribution.
    """
    logger.info(f"Checking quality for up to {limit} atoms...")

    # Phase 3 implementation
    from src.cleaning.atomicity import CardQualityAnalyzer

    analyzer = CardQualityAnalyzer()

    # Fetch atoms from DB
    from src.db.database import session_scope

    with session_scope() as session:
        from src.db.models import CleanAtom

        atoms = session.query(CleanAtom).limit(limit).all()

        grade_counts = {"A": 0, "B": 0, "C": 0, "D": 0, "F": 0}

        for atom in atoms:
            result = analyzer.analyze_card(atom.front, atom.back)
            grade_counts[result.grade.value] += 1

        table = Table(title=f"Quality Check ({len(atoms)} atoms)")
        table.add_column("Grade", style="cyan")
        table.add_column("Count", justify="right")
        table.add_column("Percentage", justify="right")

        for grade in ["A", "B", "C", "D", "F"]:
            count = grade_counts[grade]
            pct = (count / len(atoms) * 100) if atoms else 0
            table.add_row(grade, str(count), f"{pct:.1f}%")

        console.print(table)


# ========================================
# EXPORT COMMANDS
# ========================================

export_app = typer.Typer(help="Export data to CSV/JSON")
app.add_typer(export_app, name="export")


@export_app.command("cards")
def export_cards(
    output: Path = typer.Option(Path("cards_export.csv"), "--output", "-o"),
    source: str = typer.Option(
        "postgresql", "--source", "-s", help="Source: notion or postgresql"
    ),
) -> None:
    """Export flashcards to CSV."""
    logger.info(f"Exporting cards from {source} to {output}...")

    # Phase 2 implementation
    from src.export.csv_exporter import export_cards_to_csv

    count = export_cards_to_csv(source=source, output=output)

    rprint(f"[green]✓[/green] Exported {count} cards to {output}")


@export_app.command("stats")
def export_stats(
    output: Path = typer.Option(Path("anki_stats.csv"), "--output", "-o"),
    deck: Optional[str] = typer.Option(None, "--deck", help="Deck name filter"),
) -> None:
    """Export Anki FSRS stats to CSV."""
    ctx = _build_context()

    deck_name = deck or ctx.settings.anki_deck_name
    logger.info(f"Exporting Anki stats for deck: {deck_name}...")

    # Phase 4 implementation
    from src.export.csv_exporter import export_anki_stats_to_csv

    count = export_anki_stats_to_csv(deck=deck_name, output=output)

    rprint(f"[green]✓[/green] Exported {count} stats to {output}")


# ========================================
# INFO COMMANDS
# ========================================


@app.command("info")
def show_info() -> None:
    """Show configuration and database status."""
    settings = get_settings()

    table = Table(title="notion-learning-sync Configuration")
    table.add_column("Setting", style="cyan")
    table.add_column("Value", style="green")

    table.add_row("Database URL", settings.database_url)
    table.add_row("Notion API Key", "***" if settings.notion_api_key else "Not set")
    table.add_row("PROTECT_NOTION", str(settings.protect_notion))
    table.add_row("DRY_RUN", str(settings.dry_run))
    table.add_row("Anki Connect URL", settings.anki_connect_url)
    table.add_row("Anki Deck", settings.anki_deck_name)
    table.add_row("AI Model", settings.ai_model)
    table.add_row("Log Level", settings.log_level)

    console.print(table)

    # Show configured databases
    configured = settings.get_configured_notion_databases()
    if configured:
        db_table = Table(title=f"Configured Notion Databases ({len(configured)})")
        db_table.add_column("Database", style="cyan")
        db_table.add_column("ID", style="dim")

        for name, db_id in configured.items():
            db_table.add_row(name, db_id[:8] + "...")

        console.print(db_table)
    else:
        rprint("[yellow]⚠[/yellow] No Notion databases configured")


@app.command("version")
def show_version() -> None:
    """Show version information."""
    rprint("[bold]notion-learning-sync[/bold] v0.1.0 (Phase 1: Foundation)")
    rprint("  Cognitive diagnostic content pipeline")
    rprint("  Notion -> PostgreSQL -> Anki")


def main() -> None:
    """Entry point for the CLI."""
    app()


if __name__ == "__main__":
    main()
