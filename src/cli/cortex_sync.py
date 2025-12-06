"""
Cortex 2.0 CLI Commands for Sync and Graph Operations.

These commands manage the Notion <-> Neo4j synchronization and
the Z-Score/Force Z algorithms for the Cortex 2.0 architecture.

Commands:
- nls sync pull      : Pull from Notion to Shadow Graph
- nls sync push      : Push Z-Scores back to Notion
- nls sync status    : Show sync status
- nls graph stats    : Show Shadow Graph statistics
- nls graph centrality : Compute and display centrality rankings
- nls zscore compute : Compute Z-Scores for all atoms
- nls zscore activate : Activate Focus Stream based on Z-Scores
- nls forcez analyze : Analyze prerequisite gaps
- nls forcez backtrack : Get Force Z remediation queue

Author: Cortex System
Version: 2.0.0 (Notion-Centric Architecture)
"""
from __future__ import annotations

import time
from datetime import datetime
from typing import Optional

import typer
from rich import box
from rich.align import Align
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn
from rich.style import Style
from rich.table import Table
from rich.text import Text

from config import get_settings

# Import Cortex 2.0 components
from src.graph.shadow_graph import get_shadow_graph, ShadowGraphService, NodeType
from src.graph.zscore_engine import (
    get_zscore_engine,
    get_forcez_engine,
    ZScoreEngine,
    AtomMetrics,
)
from src.sync.notion_client import NotionClient
from src.sync.notion_cortex import get_notion_cortex, CortexPropertyUpdate

# Theme constants (consistent with cortex.py)
CORTEX_THEME = {
    "primary": "#00D4FF",
    "secondary": "#7B68EE",
    "accent": "#FFD700",
    "success": "#00FF88",
    "warning": "#FFA500",
    "error": "#FF4444",
    "dim": "#666666",
    "white": "#FFFFFF",
}

console = Console()

# ============================================================================
# TYPER APPS
# ============================================================================

sync_app = typer.Typer(
    name="sync",
    help="Notion <-> Neo4j synchronization commands",
    no_args_is_help=True,
)

graph_app = typer.Typer(
    name="graph",
    help="Shadow Graph (Neo4j) commands",
    no_args_is_help=True,
)

zscore_app = typer.Typer(
    name="zscore",
    help="Z-Score computation and Focus Stream management",
    no_args_is_help=True,
)

forcez_app = typer.Typer(
    name="forcez",
    help="Force Z prerequisite backtracking commands",
    no_args_is_help=True,
)


# ============================================================================
# SYNC COMMANDS
# ============================================================================

@sync_app.command("pull")
def sync_pull(
    entity: str = typer.Option(
        "all",
        "--entity", "-e",
        help="Entity type to sync (flashcards, concepts, all)",
    ),
    dry_run: bool = typer.Option(
        False,
        "--dry-run", "-n",
        help="Show what would be synced without syncing",
    ),
):
    """
    Pull data from Notion to Shadow Graph.

    Syncs Notion database pages to Neo4j nodes for graph algorithm support.

    Examples:
        nls sync pull                    # Sync all entities
        nls sync pull -e flashcards      # Sync only flashcards
        nls sync pull --dry-run          # Preview sync
    """
    settings = get_settings()
    notion = NotionClient()
    graph = get_shadow_graph()

    if not notion.ready:
        console.print(Panel(
            "[bold red]Notion client not ready.[/bold red]\n"
            "Check NOTION_API_KEY in .env",
            border_style=Style(color=CORTEX_THEME["error"]),
        ))
        raise typer.Exit(1)

    if not graph.is_available:
        console.print(Panel(
            "[bold red]Shadow Graph not available.[/bold red]\n"
            "Start Neo4j with: neo4j start\n"
            "Or install with: pip install neo4j",
            border_style=Style(color=CORTEX_THEME["error"]),
        ))
        raise typer.Exit(1)

    # Initialize schema
    console.print("[cyan]Initializing Shadow Graph schema...[/cyan]")
    graph.init_schema()

    entities_to_sync = []
    if entity == "all":
        entities_to_sync = ["flashcards", "concepts", "modules"]
    else:
        entities_to_sync = [entity]

    total_synced = 0

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        console=console,
    ) as progress:
        for ent in entities_to_sync:
            task = progress.add_task(f"Syncing {ent}...", total=100)

            # Fetch from Notion
            if ent == "flashcards":
                pages = notion.fetch_flashcards()
                node_type = NodeType.LEARNING_ATOM
            elif ent == "concepts":
                pages = notion.fetch_concepts()
                node_type = NodeType.CONCEPT
            elif ent == "modules":
                pages = notion.fetch_modules()
                node_type = NodeType.MODULE
            else:
                console.print(f"[yellow]Unknown entity: {ent}[/yellow]")
                continue

            progress.update(task, advance=30)

            if dry_run:
                console.print(f"[dim]DRY RUN: Would sync {len(pages)} {ent}[/dim]")
                progress.update(task, advance=70)
                continue

            # Sync to Neo4j
            result = graph.sync_from_notion_pages(pages, node_type)
            total_synced += result.nodes_created

            progress.update(task, advance=70)

            if result.errors:
                for error in result.errors[:5]:
                    console.print(f"[red]Error: {error}[/red]")

    # Summary
    summary = Text()
    summary.append("[*] SYNC COMPLETE [*]\n\n", style=Style(color=CORTEX_THEME["primary"], bold=True))
    summary.append(f"Nodes synced: ", style=Style(color=CORTEX_THEME["dim"]))
    summary.append(f"{total_synced}\n", style=Style(color=CORTEX_THEME["success"]))
    summary.append(f"Entities: ", style=Style(color=CORTEX_THEME["dim"]))
    summary.append(f"{', '.join(entities_to_sync)}", style=Style(color=CORTEX_THEME["accent"]))

    console.print(Panel(
        Align.center(summary),
        border_style=Style(color=CORTEX_THEME["success"]),
        box=box.DOUBLE,
    ))


@sync_app.command("push")
def sync_push(
    dry_run: bool = typer.Option(
        False,
        "--dry-run", "-n",
        help="Show what would be pushed without pushing",
    ),
):
    """
    Push computed properties back to Notion.

    Updates Z_Score, Z_Activation, and other computed fields.

    Examples:
        nls sync push           # Push all computed properties
        nls sync push --dry-run # Preview changes
    """
    settings = get_settings()

    if settings.protect_notion:
        console.print(Panel(
            "[bold yellow]PROTECT_NOTION is enabled.[/bold yellow]\n"
            "Set PROTECT_NOTION=false in .env to enable writes.",
            border_style=Style(color=CORTEX_THEME["warning"]),
        ))
        if not dry_run:
            raise typer.Exit(1)

    cortex = get_notion_cortex()
    notion = NotionClient()

    if not cortex.is_ready:
        console.print(Panel(
            "[bold red]Notion client not ready.[/bold red]",
            border_style=Style(color=CORTEX_THEME["error"]),
        ))
        raise typer.Exit(1)

    # Compute Z-Scores
    console.print("[cyan]Computing Z-Scores...[/cyan]")
    engine = get_zscore_engine()

    # Fetch flashcards and compute Z-Scores
    pages = notion.fetch_flashcards()

    metrics_list = []
    for page in pages:
        props = page.get("properties", {})

        # Extract last edited time
        last_edited = page.get("last_edited_time")
        last_touched = None
        if last_edited:
            try:
                last_touched = datetime.fromisoformat(last_edited.replace("Z", "+00:00"))
            except (ValueError, TypeError):
                pass

        # Extract review count (if available)
        review_count = 0
        if "Review_Count" in props:
            rc = props["Review_Count"].get("number")
            if rc:
                review_count = int(rc)

        # Extract memory state
        memory_state = "NEW"
        state_prop = props.get(settings.notion_prop_memory_state, {})
        if "status" in state_prop and state_prop["status"]:
            memory_state = state_prop["status"].get("name", "NEW")
        elif "select" in state_prop and state_prop["select"]:
            memory_state = state_prop["select"].get("name", "NEW")

        metrics_list.append(AtomMetrics(
            atom_id=page["id"],
            last_touched=last_touched,
            review_count=review_count,
            memory_state=memory_state,
        ))

    # Compute Z-Scores
    results = engine.compute_batch(metrics_list)

    # Mark all as needing update
    for result in results:
        result.needs_update = True

    console.print(f"[cyan]Computed {len(results)} Z-Scores[/cyan]")

    if dry_run:
        # Show preview
        table = Table(title="Z-Score Preview (Top 10)", box=box.ROUNDED)
        table.add_column("Atom ID", style=Style(color=CORTEX_THEME["dim"]))
        table.add_column("Z-Score", justify="right")
        table.add_column("Activated", justify="center")
        table.add_column("Decay", justify="right")
        table.add_column("Centrality", justify="right")
        table.add_column("Novelty", justify="right")

        for result in sorted(results, key=lambda r: -r.z_score)[:10]:
            table.add_row(
                result.atom_id[:8] + "...",
                f"{result.z_score:.3f}",
                "[green]Yes[/green]" if result.z_activation else "[dim]No[/dim]",
                f"{result.components.decay:.2f}",
                f"{result.components.centrality:.2f}",
                f"{result.components.novelty:.2f}",
            )

        console.print(table)
        console.print("\n[yellow]DRY RUN: No changes made[/yellow]")
        return

    # Push to Notion
    console.print("[cyan]Pushing to Notion...[/cyan]")
    update_result = cortex.update_zscores(results)

    # Summary
    summary = Text()
    summary.append("[*] PUSH COMPLETE [*]\n\n", style=Style(color=CORTEX_THEME["primary"], bold=True))
    summary.append(f"Success: ", style=Style(color=CORTEX_THEME["dim"]))
    summary.append(f"{update_result.success}\n", style=Style(color=CORTEX_THEME["success"]))
    summary.append(f"Failed: ", style=Style(color=CORTEX_THEME["dim"]))
    summary.append(f"{update_result.failed}\n", style=Style(color=CORTEX_THEME["error"]))
    summary.append(f"Skipped: ", style=Style(color=CORTEX_THEME["dim"]))
    summary.append(f"{update_result.skipped}", style=Style(color=CORTEX_THEME["warning"]))

    console.print(Panel(
        Align.center(summary),
        border_style=Style(color=CORTEX_THEME["success"]),
        box=box.DOUBLE,
    ))


@sync_app.command("status")
def sync_status():
    """
    Show current sync status.

    Displays connection status for Notion and Neo4j, and sync statistics.
    """
    settings = get_settings()
    notion = NotionClient()
    graph = get_shadow_graph()

    # Build status display
    content = Text()
    content.append("[*] SYNC STATUS [*]\n\n", style=Style(color=CORTEX_THEME["primary"], bold=True))

    # Notion status
    content.append("NOTION: ", style=Style(color=CORTEX_THEME["dim"]))
    if notion.ready:
        content.append("Connected\n", style=Style(color=CORTEX_THEME["success"]))
        content.append(f"  Databases configured: {notion.get_configured_database_count()}\n",
                       style=Style(color=CORTEX_THEME["dim"]))
    else:
        content.append("Not Connected\n", style=Style(color=CORTEX_THEME["error"]))

    # Neo4j status
    content.append("\nNEO4J: ", style=Style(color=CORTEX_THEME["dim"]))
    if graph.is_available:
        content.append("Connected\n", style=Style(color=CORTEX_THEME["success"]))
        stats = graph.get_stats()
        content.append(f"  URI: {stats.get('uri', 'N/A')}\n", style=Style(color=CORTEX_THEME["dim"]))
        content.append(f"  Total nodes: {stats.get('total_nodes', 0)}\n", style=Style(color=CORTEX_THEME["dim"]))
        content.append(f"  Total edges: {stats.get('total_edges', 0)}\n", style=Style(color=CORTEX_THEME["dim"]))
    else:
        content.append("Not Connected\n", style=Style(color=CORTEX_THEME["error"]))
        content.append("  Install with: pip install neo4j\n", style=Style(color=CORTEX_THEME["dim"]))
        content.append("  Start with: neo4j start\n", style=Style(color=CORTEX_THEME["dim"]))

    # Protection status
    content.append("\nPROTECTION: ", style=Style(color=CORTEX_THEME["dim"]))
    if settings.protect_notion:
        content.append("ENABLED (read-only)\n", style=Style(color=CORTEX_THEME["warning"]))
    else:
        content.append("DISABLED (writes allowed)\n", style=Style(color=CORTEX_THEME["success"]))

    console.print(Panel(
        content,
        border_style=Style(color=CORTEX_THEME["primary"]),
        box=box.HEAVY,
    ))


# ============================================================================
# GRAPH COMMANDS
# ============================================================================

@graph_app.command("stats")
def graph_stats():
    """
    Show Shadow Graph statistics.

    Displays node and edge counts by type.
    """
    graph = get_shadow_graph()

    if not graph.is_available:
        console.print(Panel(
            "[bold red]Shadow Graph not available.[/bold red]",
            border_style=Style(color=CORTEX_THEME["error"]),
        ))
        raise typer.Exit(1)

    stats = graph.get_stats()

    # Build display
    content = Text()
    content.append("[*] SHADOW GRAPH STATS [*]\n\n", style=Style(color=CORTEX_THEME["primary"], bold=True))

    content.append(f"URI: {stats.get('uri', 'N/A')}\n", style=Style(color=CORTEX_THEME["dim"]))
    content.append(f"Database: {stats.get('database', 'N/A')}\n\n", style=Style(color=CORTEX_THEME["dim"]))

    # Nodes table
    content.append("NODES:\n", style=Style(color=CORTEX_THEME["secondary"]))
    nodes = stats.get("nodes", {})
    for label, count in sorted(nodes.items(), key=lambda x: -x[1]):
        content.append(f"  {label:20s} ", style=Style(color=CORTEX_THEME["dim"]))
        content.append(f"{count:,}\n", style=Style(color=CORTEX_THEME["white"]))

    # Edges table
    content.append("\nEDGES:\n", style=Style(color=CORTEX_THEME["secondary"]))
    edges = stats.get("edges", {})
    for edge_type, count in sorted(edges.items(), key=lambda x: -x[1]):
        content.append(f"  {edge_type:20s} ", style=Style(color=CORTEX_THEME["dim"]))
        content.append(f"{count:,}\n", style=Style(color=CORTEX_THEME["white"]))

    # Totals
    content.append(f"\nTOTAL NODES: ", style=Style(color=CORTEX_THEME["dim"]))
    content.append(f"{stats.get('total_nodes', 0):,}\n", style=Style(color=CORTEX_THEME["accent"]))
    content.append(f"TOTAL EDGES: ", style=Style(color=CORTEX_THEME["dim"]))
    content.append(f"{stats.get('total_edges', 0):,}", style=Style(color=CORTEX_THEME["accent"]))

    console.print(Panel(
        content,
        border_style=Style(color=CORTEX_THEME["secondary"]),
        box=box.HEAVY,
    ))


@graph_app.command("centrality")
def graph_centrality(
    limit: int = typer.Option(20, "--limit", "-l", help="Number of top nodes to show"),
):
    """
    Compute and display PageRank centrality.

    Shows the most important/central atoms in the knowledge graph.
    """
    graph = get_shadow_graph()

    if not graph.is_available:
        console.print(Panel(
            "[bold red]Shadow Graph not available.[/bold red]",
            border_style=Style(color=CORTEX_THEME["error"]),
        ))
        raise typer.Exit(1)

    console.print("[cyan]Computing PageRank centrality...[/cyan]")
    rankings = graph.compute_pagerank()

    if not rankings:
        console.print("[yellow]No nodes found in graph.[/yellow]")
        return

    # Normalize and sort
    max_rank = max(rankings.values()) if rankings else 1.0
    normalized = {k: v / max_rank for k, v in rankings.items()}
    sorted_rankings = sorted(normalized.items(), key=lambda x: -x[1])

    # Display table
    table = Table(
        title=f"[bold cyan]Top {limit} Atoms by Centrality[/bold cyan]",
        box=box.HEAVY,
        border_style=Style(color=CORTEX_THEME["primary"]),
    )
    table.add_column("Rank", justify="right", style=Style(color=CORTEX_THEME["dim"]))
    table.add_column("Atom ID", style=Style(color=CORTEX_THEME["white"]))
    table.add_column("Centrality", justify="right")

    for i, (atom_id, score) in enumerate(sorted_rankings[:limit], 1):
        # Color based on score
        if score > 0.8:
            score_style = Style(color=CORTEX_THEME["success"])
        elif score > 0.5:
            score_style = Style(color=CORTEX_THEME["warning"])
        else:
            score_style = Style(color=CORTEX_THEME["dim"])

        table.add_row(
            str(i),
            atom_id[:12] + "...",
            Text(f"{score:.3f}", style=score_style),
        )

    console.print(table)


# ============================================================================
# Z-SCORE COMMANDS
# ============================================================================

@zscore_app.command("compute")
def zscore_compute(
    atom_id: Optional[str] = typer.Argument(
        None,
        help="Specific atom ID to compute (or all if not provided)",
    ),
):
    """
    Compute Z-Scores for atoms.

    If no atom ID is provided, computes Z-Scores for all atoms.
    """
    engine = get_zscore_engine()
    notion = NotionClient()
    settings = get_settings()

    if atom_id:
        # Single atom
        result = engine.compute(AtomMetrics(atom_id=atom_id))

        content = Text()
        content.append("[*] Z-SCORE RESULT [*]\n\n", style=Style(color=CORTEX_THEME["primary"], bold=True))
        content.append(f"Atom: {atom_id}\n\n", style=Style(color=CORTEX_THEME["dim"]))

        content.append("COMPONENTS:\n", style=Style(color=CORTEX_THEME["secondary"]))
        content.append(f"  Decay (D):      {result.components.decay:.3f}\n",
                       style=Style(color=CORTEX_THEME["white"]))
        content.append(f"  Centrality (C): {result.components.centrality:.3f}\n",
                       style=Style(color=CORTEX_THEME["white"]))
        content.append(f"  Project (P):    {result.components.project:.3f}\n",
                       style=Style(color=CORTEX_THEME["white"]))
        content.append(f"  Novelty (N):    {result.components.novelty:.3f}\n",
                       style=Style(color=CORTEX_THEME["white"]))

        content.append(f"\nTOTAL Z-SCORE: ", style=Style(color=CORTEX_THEME["dim"]))
        content.append(f"{result.z_score:.3f}\n", style=Style(color=CORTEX_THEME["accent"], bold=True))

        content.append(f"ACTIVATED: ", style=Style(color=CORTEX_THEME["dim"]))
        if result.z_activation:
            content.append("Yes (Focus Stream)\n", style=Style(color=CORTEX_THEME["success"]))
        else:
            content.append("No\n", style=Style(color=CORTEX_THEME["warning"]))

        console.print(Panel(
            content,
            border_style=Style(color=CORTEX_THEME["primary"]),
            box=box.HEAVY,
        ))
    else:
        # All atoms
        console.print("[cyan]Fetching atoms from Notion...[/cyan]")
        pages = notion.fetch_flashcards()

        metrics_list = []
        for page in pages:
            last_edited = page.get("last_edited_time")
            last_touched = None
            if last_edited:
                try:
                    last_touched = datetime.fromisoformat(last_edited.replace("Z", "+00:00"))
                except (ValueError, TypeError):
                    pass

            metrics_list.append(AtomMetrics(
                atom_id=page["id"],
                last_touched=last_touched,
            ))

        console.print(f"[cyan]Computing Z-Scores for {len(metrics_list)} atoms...[/cyan]")
        results = engine.compute_batch(metrics_list)

        # Statistics
        activated = sum(1 for r in results if r.z_activation)
        avg_score = sum(r.z_score for r in results) / len(results) if results else 0

        content = Text()
        content.append("[*] Z-SCORE BATCH RESULTS [*]\n\n", style=Style(color=CORTEX_THEME["primary"], bold=True))
        content.append(f"Total atoms: {len(results)}\n", style=Style(color=CORTEX_THEME["dim"]))
        content.append(f"Activated: {activated}\n", style=Style(color=CORTEX_THEME["success"]))
        content.append(f"Average Z-Score: {avg_score:.3f}\n", style=Style(color=CORTEX_THEME["accent"]))

        console.print(Panel(
            content,
            border_style=Style(color=CORTEX_THEME["success"]),
            box=box.DOUBLE,
        ))


@zscore_app.command("activate")
def zscore_activate(
    dry_run: bool = typer.Option(
        False,
        "--dry-run", "-n",
        help="Preview without updating Notion",
    ),
):
    """
    Activate Focus Stream based on Z-Scores.

    Computes Z-Scores and updates Z_Activation property in Notion.
    """
    # Reuse sync push command
    sync_push(dry_run=dry_run)


# ============================================================================
# FORCE Z COMMANDS
# ============================================================================

@forcez_app.command("analyze")
def forcez_analyze(
    atom_id: str = typer.Argument(..., help="Atom ID to analyze"),
):
    """
    Analyze prerequisite gaps for an atom.

    Checks if Force Z backtracking is needed.
    """
    engine = get_forcez_engine()
    result = engine.analyze(atom_id)

    content = Text()
    content.append("[*] FORCE Z ANALYSIS [*]\n\n", style=Style(color=CORTEX_THEME["primary"], bold=True))
    content.append(f"Target: {atom_id[:12]}...\n\n", style=Style(color=CORTEX_THEME["dim"]))

    if result.should_backtrack:
        content.append("RECOMMENDATION: ", style=Style(color=CORTEX_THEME["dim"]))
        content.append("BACKTRACK NEEDED\n\n", style=Style(color=CORTEX_THEME["error"], bold=True))

        content.append(f"Weak Prerequisites: {len(result.weak_prerequisites)}\n",
                       style=Style(color=CORTEX_THEME["warning"]))

        content.append("\nREMEDIATION PATH:\n", style=Style(color=CORTEX_THEME["secondary"]))
        for i, prereq_id in enumerate(result.recommended_path[:5], 1):
            content.append(f"  {i}. {prereq_id[:12]}...\n",
                           style=Style(color=CORTEX_THEME["white"]))

        content.append(f"\n{result.explanation}\n", style=Style(color=CORTEX_THEME["dim"]))
    else:
        content.append("RECOMMENDATION: ", style=Style(color=CORTEX_THEME["dim"]))
        content.append("NO BACKTRACKING NEEDED\n\n", style=Style(color=CORTEX_THEME["success"], bold=True))
        content.append(f"{result.explanation}\n", style=Style(color=CORTEX_THEME["dim"]))

    console.print(Panel(
        content,
        border_style=Style(color=CORTEX_THEME["error"] if result.should_backtrack else CORTEX_THEME["success"]),
        box=box.HEAVY,
    ))


@forcez_app.command("queue")
def forcez_queue(
    atom_id: str = typer.Argument(..., help="Atom ID to get remediation queue for"),
    limit: int = typer.Option(5, "--limit", "-l", help="Maximum queue size"),
):
    """
    Get Force Z remediation queue for an atom.

    Returns atoms that should be reviewed before the target.
    """
    engine = get_forcez_engine()
    queue = engine.get_remediation_queue(atom_id, limit=limit)

    if not queue:
        console.print(Panel(
            "[green]No remediation needed.[/green]\n"
            "All prerequisites are sufficiently mastered.",
            border_style=Style(color=CORTEX_THEME["success"]),
        ))
        return

    table = Table(
        title="[bold red]Force Z Remediation Queue[/bold red]",
        box=box.HEAVY,
        border_style=Style(color=CORTEX_THEME["error"]),
    )
    table.add_column("Priority", justify="right", style=Style(color=CORTEX_THEME["dim"]))
    table.add_column("Atom", style=Style(color=CORTEX_THEME["white"]))
    table.add_column("State", justify="center")
    table.add_column("Z-Score", justify="right")

    for i, item in enumerate(queue, 1):
        state = item.get("memory_state", "NEW")
        state_style = Style(color=CORTEX_THEME["warning"] if state == "LEARNING" else CORTEX_THEME["dim"])

        table.add_row(
            str(i),
            item.get("title", item["id"][:12]),
            Text(state, style=state_style),
            f"{item.get('z_score', 0):.3f}",
        )

    console.print(table)
    console.print(f"\n[cyan]Review these {len(queue)} atoms before proceeding.[/cyan]")


# ============================================================================
# MAIN REGISTRATION
# ============================================================================

def register_cortex_sync_commands(app: typer.Typer) -> None:
    """Register Cortex 2.0 sync commands with the main CLI app."""
    app.add_typer(sync_app, name="sync")
    app.add_typer(graph_app, name="graph")
    app.add_typer(zscore_app, name="zscore")
    app.add_typer(forcez_app, name="forcez")
