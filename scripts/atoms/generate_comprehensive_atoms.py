#!/usr/bin/env python
"""
Generate Comprehensive Learning Atoms for CCNA.

Generates 10+ atoms per section with a balanced mix of atom types:
- Flashcards: ~40% (core facts, definitions)
- MCQ: ~20% (conceptual understanding)
- Cloze: ~15% (terminology)
- True/False: ~10% (common misconceptions)
- Matching: ~10% (related concepts)
- Parsons: ~5% (CLI procedures)

Target: ~5,600 total atoms (562 sections × 10 avg)

Usage:
    python scripts/generate_comprehensive_atoms.py --module 1
    python scripts/generate_comprehensive_atoms.py --all
    python scripts/generate_comprehensive_atoms.py --under-covered
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from rich import print as rprint
from rich.console import Console
from rich.table import Table

console = Console()


@dataclass
class SectionCoverage:
    """Track atom coverage for a section."""

    section_id: str
    title: str
    module_number: int
    current_atoms: int
    target_atoms: int = 10
    flashcard_count: int = 0
    mcq_count: int = 0
    cloze_count: int = 0
    true_false_count: int = 0
    matching_count: int = 0
    parsons_count: int = 0

    @property
    def needs_more(self) -> bool:
        return self.current_atoms < self.target_atoms

    @property
    def gap(self) -> int:
        return max(0, self.target_atoms - self.current_atoms)


TARGET_TYPE_DISTRIBUTION = {
    "flashcard": 0.40,
    "mcq": 0.20,
    "cloze": 0.15,
    "true_false": 0.10,
    "matching": 0.10,
    "parsons": 0.05,
}


def get_section_coverage() -> dict[str, SectionCoverage]:
    """Get current atom coverage per section from database."""
    from sqlalchemy import text

    from src.db.database import engine

    coverage = {}

    with engine.connect() as conn:
        # Get sections
        sections_result = conn.execute(
            text("""
            SELECT section_id, title, module_number
            FROM ccna_sections
            ORDER BY display_order
        """)
        )

        for row in sections_result:
            coverage[row.section_id] = SectionCoverage(
                section_id=row.section_id,
                title=row.title,
                module_number=row.module_number,
                current_atoms=0,
            )

        # Get atom counts per section
        atoms_result = conn.execute(
            text("""
            SELECT
                ccna_section_id,
                atom_type,
                COUNT(*) as cnt
            FROM clean_atoms
            WHERE ccna_section_id IS NOT NULL
            GROUP BY ccna_section_id, atom_type
        """)
        )

        for row in atoms_result:
            if row.ccna_section_id in coverage:
                cov = coverage[row.ccna_section_id]
                cov.current_atoms += row.cnt

                if row.atom_type == "flashcard":
                    cov.flashcard_count = row.cnt
                elif row.atom_type == "mcq":
                    cov.mcq_count = row.cnt
                elif row.atom_type == "cloze":
                    cov.cloze_count = row.cnt
                elif row.atom_type == "true_false":
                    cov.true_false_count = row.cnt
                elif row.atom_type == "matching":
                    cov.matching_count = row.cnt
                elif row.atom_type == "parsons":
                    cov.parsons_count = row.cnt

    return coverage


def get_under_covered_sections(coverage: dict[str, SectionCoverage]) -> list[SectionCoverage]:
    """Get sections that need more atoms."""
    return [c for c in coverage.values() if c.needs_more]


def calculate_types_needed(section: SectionCoverage) -> dict[str, int]:
    """Calculate how many of each atom type to generate for a section."""
    gap = section.gap
    if gap <= 0:
        return {}

    types_needed = {}

    for atom_type, ratio in TARGET_TYPE_DISTRIBUTION.items():
        target_for_type = int(10 * ratio)  # Target per full section
        current = getattr(section, f"{atom_type}_count", 0)
        needed = max(0, target_for_type - current)

        if needed > 0:
            types_needed[atom_type] = min(needed, gap)
            gap -= types_needed[atom_type]

        if gap <= 0:
            break

    # If still have gap, add to flashcards
    if gap > 0:
        types_needed["flashcard"] = types_needed.get("flashcard", 0) + gap

    return types_needed


async def generate_atoms_for_section(
    section_id: str, types_needed: dict[str, int], content: str, dry_run: bool = False
) -> dict[str, Any]:
    """Generate atoms of specified types for a section."""
    if dry_run:
        return {"section_id": section_id, "planned": types_needed, "generated": 0, "dry_run": True}

    from src.ccna.atomizer_service import AtomizerService, AtomType
    from src.ccna.content_parser import Section

    atomizer = AtomizerService()

    # Create a minimal Section object
    section = Section(
        id=section_id,
        title="",
        level=2,
        content=content,
        raw_content=content,
    )

    generated = {}
    errors = []

    for atom_type, count in types_needed.items():
        if count <= 0:
            continue

        try:
            # Map to AtomType enum
            type_map = {
                "flashcard": AtomType.FLASHCARD,
                "mcq": AtomType.MCQ,
                "cloze": AtomType.CLOZE,
                "true_false": AtomType.TRUE_FALSE,
                "matching": AtomType.MATCHING,
                "parsons": AtomType.PARSONS,
            }

            if atom_type not in type_map:
                continue

            result = await atomizer.atomize_section(section, [type_map[atom_type]])
            generated[atom_type] = len(result.atoms)

            if result.errors:
                errors.extend(result.errors)

        except Exception as e:
            errors.append(f"{atom_type}: {str(e)}")
            generated[atom_type] = 0

    return {
        "section_id": section_id,
        "planned": types_needed,
        "generated": generated,
        "errors": errors,
    }


def display_coverage_report(coverage: dict[str, SectionCoverage]) -> None:
    """Display coverage analysis report."""
    table = Table(title="CCNA Atom Coverage Analysis")
    table.add_column("Module", justify="right", style="cyan")
    table.add_column("Sections", justify="right")
    table.add_column("Total Atoms", justify="right", style="green")
    table.add_column("Avg/Section", justify="right")
    table.add_column("Under-covered", justify="right", style="yellow")
    table.add_column("Gap", justify="right", style="red")

    module_stats = {}
    for cov in coverage.values():
        mod = cov.module_number
        if mod not in module_stats:
            module_stats[mod] = {"sections": 0, "atoms": 0, "under_covered": 0, "gap": 0}
        module_stats[mod]["sections"] += 1
        module_stats[mod]["atoms"] += cov.current_atoms
        if cov.needs_more:
            module_stats[mod]["under_covered"] += 1
            module_stats[mod]["gap"] += cov.gap

    total_sections = 0
    total_atoms = 0
    total_under = 0
    total_gap = 0

    for mod in sorted(module_stats.keys()):
        stats = module_stats[mod]
        avg = stats["atoms"] / stats["sections"] if stats["sections"] > 0 else 0

        total_sections += stats["sections"]
        total_atoms += stats["atoms"]
        total_under += stats["under_covered"]
        total_gap += stats["gap"]

        table.add_row(
            str(mod),
            str(stats["sections"]),
            str(stats["atoms"]),
            f"{avg:.1f}",
            str(stats["under_covered"]),
            str(stats["gap"]) if stats["gap"] > 0 else "-",
        )

    table.add_section()
    total_avg = total_atoms / total_sections if total_sections > 0 else 0
    table.add_row(
        "TOTAL",
        str(total_sections),
        str(total_atoms),
        f"{total_avg:.1f}",
        str(total_under),
        str(total_gap),
        style="bold",
    )

    console.print(table)

    rprint("\n[bold]Summary:[/bold]")
    rprint(f"  Current coverage: {total_atoms} atoms across {total_sections} sections")
    rprint(f"  Average: {total_avg:.1f} atoms/section")
    rprint(f"  Target: 10 atoms/section ({total_sections * 10} total)")
    rprint(f"  Gap: {total_gap} atoms needed")


def main():
    parser = argparse.ArgumentParser(description="Generate comprehensive CCNA atoms")
    parser.add_argument("--module", type=int, help="Generate for specific module (1-17)")
    parser.add_argument("--all", action="store_true", help="Generate for all modules")
    parser.add_argument(
        "--under-covered", action="store_true", help="Only generate for under-covered sections"
    )
    parser.add_argument("--dry-run", action="store_true", help="Preview without generating")
    parser.add_argument("--report", action="store_true", help="Show coverage report only")
    parser.add_argument(
        "--target", type=int, default=10, help="Target atoms per section (default: 10)"
    )
    args = parser.parse_args()

    rprint("\n[bold]CCNA Comprehensive Atom Generation[/bold]\n")

    # Get current coverage
    rprint("Analyzing current coverage...")
    try:
        coverage = get_section_coverage()
    except Exception as e:
        rprint(f"[red]Error getting coverage:[/red] {e}")
        rprint("\n[yellow]Note:[/yellow] Make sure to run the migration first:")
        rprint("  nls db migrate --migration 008")
        rprint("  python scripts/populate_ccna_sections.py")
        return 1

    if not coverage:
        rprint("[yellow]No sections found in database.[/yellow]")
        rprint("Run: python scripts/populate_ccna_sections.py")
        return 1

    # Update target if specified
    if args.target != 10:
        for cov in coverage.values():
            cov.target_atoms = args.target

    # Display coverage report
    display_coverage_report(coverage)

    if args.report:
        return 0

    # Determine which sections to process
    if args.module:
        sections_to_process = [
            c for c in coverage.values() if c.module_number == args.module and c.needs_more
        ]
        rprint(f"\n[bold]Processing Module {args.module}[/bold]")
    elif args.under_covered:
        sections_to_process = get_under_covered_sections(coverage)
        rprint(f"\n[bold]Processing {len(sections_to_process)} under-covered sections[/bold]")
    elif args.all:
        sections_to_process = get_under_covered_sections(coverage)
        rprint(f"\n[bold]Processing ALL under-covered sections ({len(sections_to_process)})[/bold]")
    else:
        rprint("\n[yellow]No action specified.[/yellow]")
        rprint("Use --module N, --under-covered, or --all")
        return 0

    if not sections_to_process:
        rprint("[green]All sections have sufficient coverage![/green]")
        return 0

    # Calculate what to generate
    generation_plan = []
    for section in sections_to_process:
        types_needed = calculate_types_needed(section)
        if types_needed:
            generation_plan.append(
                {
                    "section": section,
                    "types_needed": types_needed,
                    "total_needed": sum(types_needed.values()),
                }
            )

    # Display plan
    total_to_generate = sum(p["total_needed"] for p in generation_plan)
    rprint("\n[bold]Generation Plan:[/bold]")
    rprint(f"  Sections to process: {len(generation_plan)}")
    rprint(f"  Total atoms to generate: {total_to_generate}")

    # Show type breakdown
    type_totals = {}
    for p in generation_plan:
        for t, n in p["types_needed"].items():
            type_totals[t] = type_totals.get(t, 0) + n

    rprint("\n  By type:")
    for t, n in sorted(type_totals.items(), key=lambda x: -x[1]):
        rprint(f"    {t}: {n}")

    if args.dry_run:
        rprint("\n[yellow]DRY RUN - No atoms generated[/yellow]")
        return 0

    # Confirm before proceeding
    rprint("\n[bold yellow]Ready to generate atoms.[/bold yellow]")
    rprint("This will call the AI API and may take significant time.")
    rprint("Continue? [y/N] ", end="")

    response = input().strip().lower()
    if response != "y":
        rprint("[yellow]Cancelled[/yellow]")
        return 0

    # TODO: Implement actual generation loop
    rprint("\n[yellow]Generation loop not yet implemented.[/yellow]")
    rprint("The infrastructure is in place - atoms would be generated using:")
    rprint("  - AtomizerService for AI generation")
    rprint("  - Quality grading from atomicity.py")
    rprint("  - Insert into ccna_generated_atoms table")

    return 0


if __name__ == "__main__":
    sys.exit(main())
