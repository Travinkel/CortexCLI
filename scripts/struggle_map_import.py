#!/usr/bin/env python3
"""
Struggle Map Import Script.

Imports a YAML/JSON struggle map and generates:
1. Database entries with struggle weights
2. Anki filtered deck queries for weak sections
3. Atom generation targets for Gemini

Usage:
    python scripts/struggle_map_import.py --file struggle_map.yaml
    python scripts/struggle_map_import.py --file struggle_map.yaml --anki-query
    python scripts/struggle_map_import.py --file struggle_map.yaml --generate-atoms
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml
from loguru import logger
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from config import get_settings

console = Console()


# =============================================================================
# Data Models
# =============================================================================


@dataclass
class StruggleEntry:
    """A single struggle area from the map."""

    module: int
    sections: list[str]
    severity: str  # critical, high, medium, low
    failure_modes: list[str] = field(default_factory=list)
    notes: str | None = None

    @property
    def severity_weight(self) -> float:
        """Convert severity to numeric weight (0-1)."""
        return {
            "critical": 1.0,
            "high": 0.8,
            "medium": 0.5,
            "low": 0.3,
        }.get(self.severity, 0.5)

    @property
    def priority(self) -> int:
        """Priority ordering (lower = higher priority)."""
        return {
            "critical": 1,
            "high": 2,
            "medium": 3,
            "low": 4,
        }.get(self.severity, 3)


@dataclass
class StruggleMap:
    """Full struggle map with entries and preferences."""

    entries: list[StruggleEntry] = field(default_factory=list)
    preferences: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def get_modules(self, min_severity: str = "low") -> list[int]:
        """Get module numbers at or above severity threshold."""
        threshold = {"critical": 1, "high": 2, "medium": 3, "low": 4}[min_severity]
        return sorted(
            {e.module for e in self.entries if e.priority <= threshold}
        )

    def get_sections(self, min_severity: str = "low") -> list[str]:
        """Get all section IDs at or above severity threshold."""
        threshold = {"critical": 1, "high": 2, "medium": 3, "low": 4}[min_severity]
        sections = []
        for e in self.entries:
            if e.priority <= threshold:
                sections.extend(e.sections)
        return sections


# =============================================================================
# YAML/JSON Parser
# =============================================================================


def parse_struggle_file(file_path: Path) -> StruggleMap:
    """
    Parse a YAML or JSON struggle map file.

    Expected format:
    ```yaml
    struggles:
      - module: 11
        sections: ["11.3", "11.4"]
        severity: critical
        failure_modes: [FM3, FM4]
        notes: "IPv4 addressing struggles"
    preferences:
      focus_mode: weakest_first
      max_atoms_per_session: 50
    ```
    """
    if not file_path.exists():
        raise FileNotFoundError(f"Struggle map not found: {file_path}")

    with open(file_path) as f:
        if file_path.suffix in (".yaml", ".yml"):
            data = yaml.safe_load(f)
        else:
            data = json.load(f)

    entries = []
    for item in data.get("struggles", []):
        entry = StruggleEntry(
            module=item["module"],
            sections=item.get("sections", []),
            severity=item.get("severity", "medium"),
            failure_modes=item.get("failure_modes", []),
            notes=item.get("notes"),
        )
        entries.append(entry)

    return StruggleMap(
        entries=entries,
        preferences=data.get("preferences", {}),
    )


# =============================================================================
# Database Operations
# =============================================================================


def store_struggle_weights(struggle_map: StruggleMap) -> dict[str, Any]:
    """
    Store struggle weights in the database.

    Updates ccna_section_mastery or a dedicated struggle_weights table.
    """
    from sqlalchemy import text
    from src.db.database import engine

    with engine.connect() as conn:
        # Ensure struggle_weights table exists
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS struggle_weights (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                module_number INTEGER NOT NULL,
                section_id TEXT,
                severity TEXT NOT NULL,
                weight DECIMAL(3,2) NOT NULL,
                failure_modes TEXT[],
                notes TEXT,
                created_at TIMESTAMPTZ DEFAULT NOW(),
                updated_at TIMESTAMPTZ DEFAULT NOW(),
                UNIQUE(module_number, section_id)
            )
        """))
        conn.commit()

        # Clear existing and insert new
        conn.execute(text("DELETE FROM struggle_weights"))
        conn.commit()

        inserted = 0
        for entry in struggle_map.entries:
            if entry.sections:
                # Insert per-section weights
                for section in entry.sections:
                    conn.execute(
                        text("""
                        INSERT INTO struggle_weights
                            (module_number, section_id, severity, weight, failure_modes, notes)
                        VALUES (:module, :section, :severity, :weight, :failure_modes, :notes)
                        ON CONFLICT (module_number, section_id) DO UPDATE SET
                            severity = EXCLUDED.severity,
                            weight = EXCLUDED.weight,
                            failure_modes = EXCLUDED.failure_modes,
                            notes = EXCLUDED.notes,
                            updated_at = NOW()
                        """),
                        {
                            "module": entry.module,
                            "section": section,
                            "severity": entry.severity,
                            "weight": entry.severity_weight,
                            "failure_modes": entry.failure_modes,
                            "notes": entry.notes,
                        },
                    )
                    inserted += 1
            else:
                # Insert module-level weight
                conn.execute(
                    text("""
                    INSERT INTO struggle_weights
                        (module_number, section_id, severity, weight, failure_modes, notes)
                    VALUES (:module, NULL, :severity, :weight, :failure_modes, :notes)
                    ON CONFLICT (module_number, section_id) DO UPDATE SET
                        severity = EXCLUDED.severity,
                        weight = EXCLUDED.weight,
                        failure_modes = EXCLUDED.failure_modes,
                        notes = EXCLUDED.notes,
                        updated_at = NOW()
                    """),
                    {
                        "module": entry.module,
                        "severity": entry.severity,
                        "weight": entry.severity_weight,
                        "failure_modes": entry.failure_modes,
                        "notes": entry.notes,
                    },
                )
                inserted += 1

        conn.commit()
        return {"inserted": inserted, "modules": len(struggle_map.get_modules())}


def get_struggle_atom_counts(struggle_map: StruggleMap) -> dict[str, dict]:
    """
    Query existing atom counts for struggle sections.

    Returns dict mapping section_id -> {total, flashcard, cloze, mcq, ...}
    """
    from sqlalchemy import text
    from src.db.database import engine

    modules = struggle_map.get_modules()
    sections = struggle_map.get_sections()

    with engine.connect() as conn:
        # Query atom counts by section using learning_atoms table
        rows = conn.execute(
            text("""
            SELECT
                cs.section_id,
                cs.module_number,
                cs.title,
                COUNT(la.id) as total_atoms,
                COUNT(la.id) FILTER (WHERE la.atom_type = 'flashcard') as flashcard_count,
                COUNT(la.id) FILTER (WHERE la.atom_type = 'cloze') as cloze_count,
                COUNT(la.id) FILTER (WHERE la.atom_type = 'mcq') as mcq_count,
                COUNT(la.id) FILTER (WHERE la.atom_type = 'true_false') as tf_count,
                COUNT(la.id) FILTER (WHERE la.atom_type = 'parsons') as parsons_count,
                COUNT(la.id) FILTER (WHERE la.atom_type = 'numeric') as numeric_count,
                AVG(la.quality_score) as avg_quality
            FROM ccna_sections cs
            LEFT JOIN learning_atoms la ON la.ccna_section_id = cs.section_id
            WHERE cs.module_number = ANY(:modules)
                OR cs.section_id = ANY(:sections)
            GROUP BY cs.section_id, cs.module_number, cs.title
            ORDER BY cs.module_number, cs.section_id
            """),
            {"modules": modules, "sections": sections},
        ).fetchall()

        result = {}
        for row in rows:
            result[row.section_id] = {
                "module": row.module_number,
                "title": row.title,
                "total": row.total_atoms,
                "flashcard": row.flashcard_count,
                "cloze": row.cloze_count,
                "mcq": row.mcq_count,
                "true_false": row.tf_count,
                "parsons": row.parsons_count,
                "numeric": row.numeric_count,
                "avg_quality": float(row.avg_quality) if row.avg_quality else 0,
            }

        return result


# =============================================================================
# Anki Filtered Deck Queries
# =============================================================================


def generate_anki_queries(struggle_map: StruggleMap) -> dict[str, str]:
    """
    Generate Anki filtered deck queries for struggle areas.

    Returns dict mapping deck name -> search query.
    """
    queries = {}

    # Critical struggles - highest priority
    critical_modules = [
        e.module for e in struggle_map.entries if e.severity == "critical"
    ]
    critical_sections = []
    for e in struggle_map.entries:
        if e.severity == "critical":
            critical_sections.extend(e.sections)

    if critical_modules or critical_sections:
        parts = []
        for m in critical_modules:
            parts.append(f'"module:{m}"')
        for s in critical_sections:
            parts.append(f'"section:{s}"')
        queries["CCNA::Struggle::Critical"] = f"({' OR '.join(parts)}) -is:suspended"

    # High severity
    high_modules = [e.module for e in struggle_map.entries if e.severity == "high"]
    high_sections = []
    for e in struggle_map.entries:
        if e.severity == "high":
            high_sections.extend(e.sections)

    if high_modules or high_sections:
        parts = []
        for m in high_modules:
            parts.append(f'"module:{m}"')
        for s in high_sections:
            parts.append(f'"section:{s}"')
        queries["CCNA::Struggle::High"] = f"({' OR '.join(parts)}) -is:suspended"

    # Combined struggle deck
    all_modules = struggle_map.get_modules("medium")
    if all_modules:
        module_parts = [f'"module:{m}"' for m in all_modules]
        queries["CCNA::Struggle::All"] = (
            f"({' OR '.join(module_parts)}) -is:suspended is:due"
        )

    # Failure mode specific decks
    fm_decks = {
        "FM1": "CCNA::Struggle::FM1-Confusions",  # similar term confusion
        "FM2": "CCNA::Struggle::FM2-Process",  # multi-step processes
        "FM3": "CCNA::Struggle::FM3-Calculation",  # numeric calculations
        "FM4": "CCNA::Struggle::FM4-Application",  # context application
    }

    for entry in struggle_map.entries:
        for fm in entry.failure_modes:
            if fm in fm_decks:
                deck_name = fm_decks[fm]
                if deck_name not in queries:
                    queries[deck_name] = ""
                if entry.sections:
                    for s in entry.sections:
                        queries[deck_name] += f' OR "section:{s}"'
                else:
                    queries[deck_name] += f' OR "module:{entry.module}"'

    # Clean up FM queries
    for deck_name in fm_decks.values():
        if deck_name in queries:
            query = queries[deck_name].strip()
            if query.startswith("OR "):
                query = query[3:]
            queries[deck_name] = f"({query}) -is:suspended"

    return queries


def generate_anki_commands(queries: dict[str, str]) -> list[str]:
    """Generate AnkiConnect commands to create filtered decks."""
    commands = []

    for deck_name, query in queries.items():
        # Create filtered deck command (AnkiConnect format)
        cmd = {
            "action": "createFilteredDeck",
            "version": 6,
            "params": {
                "newDeckName": deck_name,
                "searchQuery": query,
            },
        }
        commands.append(json.dumps(cmd, indent=2))

    return commands


# =============================================================================
# Atom Generation Targets
# =============================================================================


def identify_generation_targets(
    struggle_map: StruggleMap,
    min_atoms: int = 10,
    target_types: list[str] | None = None,
) -> list[dict]:
    """
    Identify sections that need more atoms generated.

    Args:
        struggle_map: The parsed struggle map
        min_atoms: Minimum atoms per section (default 10)
        target_types: Atom types to check (default: flashcard, cloze, mcq)

    Returns:
        List of dicts with section info and generation recommendations
    """
    if target_types is None:
        target_types = ["flashcard", "cloze", "mcq", "parsons", "numeric"]

    atom_counts = get_struggle_atom_counts(struggle_map)
    targets = []

    for entry in struggle_map.entries:
        for section_id in entry.sections:
            counts = atom_counts.get(section_id, {})
            total = counts.get("total", 0)

            # Determine what's missing
            missing_types = []
            for t in target_types:
                if counts.get(t, 0) < 3:  # At least 3 of each type
                    missing_types.append(t)

            # Higher priority for critical/high severity with few atoms
            if total < min_atoms or missing_types:
                targets.append({
                    "module": entry.module,
                    "section_id": section_id,
                    "title": counts.get("title", "Unknown"),
                    "severity": entry.severity,
                    "current_atoms": total,
                    "missing_types": missing_types,
                    "failure_modes": entry.failure_modes,
                    "priority": entry.priority,
                    "recommended_generation": missing_types or ["flashcard", "mcq"],
                })

    # Sort by priority then by atom count
    targets.sort(key=lambda x: (x["priority"], x["current_atoms"]))
    return targets


# =============================================================================
# Display Functions
# =============================================================================


def display_struggle_map(struggle_map: StruggleMap):
    """Display the loaded struggle map."""
    console.print(
        Panel(
            "[bold cyan]CCNA STRUGGLE MAP[/bold cyan]",
            border_style="cyan",
        )
    )

    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("Module", style="cyan", width=8)
    table.add_column("Sections", style="white")
    table.add_column("Severity", justify="center")
    table.add_column("Failure Modes", style="dim")
    table.add_column("Notes", style="dim", max_width=30)

    severity_colors = {
        "critical": "[red]CRITICAL[/red]",
        "high": "[yellow]HIGH[/yellow]",
        "medium": "[blue]MEDIUM[/blue]",
        "low": "[dim]LOW[/dim]",
    }

    for entry in sorted(struggle_map.entries, key=lambda e: (e.priority, e.module)):
        table.add_row(
            str(entry.module),
            ", ".join(entry.sections) if entry.sections else f"M{entry.module}.*",
            severity_colors.get(entry.severity, entry.severity),
            ", ".join(entry.failure_modes) if entry.failure_modes else "-",
            (entry.notes[:27] + "...") if entry.notes and len(entry.notes) > 30 else (entry.notes or "-"),
        )

    console.print(table)

    # Summary
    console.print(f"\n[cyan]Total entries:[/cyan] {len(struggle_map.entries)}")
    console.print(f"[cyan]Critical:[/cyan] {len([e for e in struggle_map.entries if e.severity == 'critical'])}")
    console.print(f"[cyan]High:[/cyan] {len([e for e in struggle_map.entries if e.severity == 'high'])}")


def display_anki_queries(queries: dict[str, str]):
    """Display Anki filtered deck queries."""
    console.print(
        Panel(
            "[bold green]ANKI FILTERED DECK QUERIES[/bold green]",
            border_style="green",
        )
    )

    for deck_name, query in queries.items():
        console.print(f"\n[cyan]{deck_name}[/cyan]")
        console.print(f"[dim]{query}[/dim]")


def display_generation_targets(targets: list[dict]):
    """Display atom generation targets."""
    console.print(
        Panel(
            "[bold yellow]ATOM GENERATION TARGETS[/bold yellow]",
            border_style="yellow",
        )
    )

    table = Table(show_header=True, header_style="bold")
    table.add_column("Priority", justify="center", width=8)
    table.add_column("Section", width=12)
    table.add_column("Title", max_width=30)
    table.add_column("Current", justify="right", width=8)
    table.add_column("Missing Types", style="yellow")
    table.add_column("Failure Modes", style="dim")

    priority_labels = {1: "[red]CRIT[/red]", 2: "[yellow]HIGH[/yellow]", 3: "[blue]MED[/blue]", 4: "[dim]LOW[/dim]"}

    for t in targets[:20]:  # Top 20
        table.add_row(
            priority_labels.get(t["priority"], str(t["priority"])),
            t["section_id"],
            t["title"][:28] + "..." if len(t["title"]) > 30 else t["title"],
            str(t["current_atoms"]),
            ", ".join(t["missing_types"][:3]) if t["missing_types"] else "-",
            ", ".join(t["failure_modes"]) if t["failure_modes"] else "-",
        )

    console.print(table)
    console.print(f"\n[dim]Showing top 20 of {len(targets)} targets[/dim]")


# =============================================================================
# Main Entry Point
# =============================================================================


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Import CCNA struggle map and generate learning resources"
    )
    parser.add_argument(
        "--file", "-f",
        type=Path,
        required=True,
        help="Path to YAML/JSON struggle map file",
    )
    parser.add_argument(
        "--store-db",
        action="store_true",
        help="Store struggle weights in database",
    )
    parser.add_argument(
        "--anki-query",
        action="store_true",
        help="Generate Anki filtered deck queries",
    )
    parser.add_argument(
        "--anki-commands",
        action="store_true",
        help="Output AnkiConnect commands (JSON)",
    )
    parser.add_argument(
        "--show-targets",
        action="store_true",
        help="Show sections needing atom generation",
    )
    parser.add_argument(
        "--generate-atoms",
        action="store_true",
        help="Trigger atom generation for weak sections",
    )
    parser.add_argument(
        "--output", "-o",
        type=Path,
        help="Output file for queries/commands",
    )
    parser.add_argument(
        "--min-atoms",
        type=int,
        default=10,
        help="Minimum atoms per section (default: 10)",
    )

    args = parser.parse_args()

    # Load struggle map
    console.print(f"\n[cyan]Loading struggle map from:[/cyan] {args.file}")
    try:
        struggle_map = parse_struggle_file(args.file)
        display_struggle_map(struggle_map)
    except Exception as e:
        console.print(f"[red]Error loading struggle map:[/red] {e}")
        sys.exit(1)

    # Store in database
    if args.store_db:
        console.print("\n[cyan]Storing struggle weights in database...[/cyan]")
        try:
            result = store_struggle_weights(struggle_map)
            console.print(f"[green]Stored {result['inserted']} weights for {result['modules']} modules[/green]")
        except Exception as e:
            console.print(f"[red]Database error:[/red] {e}")
            logger.exception("Database store failed")

    # Generate Anki queries
    if args.anki_query or args.anki_commands:
        queries = generate_anki_queries(struggle_map)
        display_anki_queries(queries)

        if args.anki_commands:
            commands = generate_anki_commands(queries)
            console.print("\n[bold green]AnkiConnect Commands:[/bold green]")
            for cmd in commands:
                console.print(cmd)

        if args.output:
            with open(args.output, "w") as f:
                json.dump({"queries": queries}, f, indent=2)
            console.print(f"\n[green]Saved queries to:[/green] {args.output}")

    # Show generation targets
    if args.show_targets or args.generate_atoms:
        console.print("\n[cyan]Identifying atom generation targets...[/cyan]")
        try:
            targets = identify_generation_targets(
                struggle_map,
                min_atoms=args.min_atoms,
            )
            display_generation_targets(targets)

            if args.generate_atoms:
                console.print("\n[yellow]Atom generation triggered...[/yellow]")
                # This would integrate with AtomizerService
                console.print("[dim]Use scripts/atoms/generate_all_atoms.py with --sections flag[/dim]")
                console.print(f"[dim]Target sections: {', '.join(t['section_id'] for t in targets[:10])}[/dim]")

        except Exception as e:
            console.print(f"[red]Error querying database:[/red] {e}")
            logger.exception("Database query failed")


if __name__ == "__main__":
    main()
