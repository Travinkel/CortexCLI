#!/usr/bin/env python
"""
Populate CCNA Sections Table.

Extracts all sections from CCNA module files and inserts them into
the ccna_sections table for study path tracking.

Usage:
    python scripts/populate_ccna_sections.py
    python scripts/populate_ccna_sections.py --dry-run
"""
from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from loguru import logger
from rich import print as rprint
from rich.console import Console
from rich.table import Table

console = Console()


@dataclass
class Section:
    """A CCNA section extracted from content."""
    module_number: int
    section_id: str
    title: str
    level: int  # 2 = main (X.Y), 3 = sub (X.Y.Z)
    parent_section_id: str | None
    word_count: int
    display_order: int


def extract_sections(modules_dir: Path) -> list[Section]:
    """Extract all sections from CCNA module files."""
    sections = []
    display_order = 0

    # Pattern for section numbers like 1.2, 1.4.1, 10.1.3
    section_pattern = re.compile(
        r'^#*\s*\**(\d+\.\d+(?:\.\d+)?)\s+(.+?)(?:\*\*)?$',
        re.MULTILINE
    )

    for module_file in sorted(modules_dir.glob('CCNA Module *.txt')):
        module_num = int(re.search(r'Module\s*(\d+)', module_file.stem).group(1))
        content = module_file.read_text(encoding='utf-8')

        # Track positions for word count estimation
        matches = list(section_pattern.finditer(content))

        for i, match in enumerate(matches):
            section_id = match.group(1)
            title = match.group(2).strip().rstrip('*').strip()

            # Skip intro sections (X.0.X)
            if '.0.' in section_id or section_id.endswith('.0'):
                continue

            # Determine level from section ID depth
            parts = section_id.split('.')
            level = len(parts)  # 2 for X.Y, 3 for X.Y.Z

            # Determine parent section ID
            parent_id = None
            if level == 3:
                parent_id = f"{parts[0]}.{parts[1]}"

            # Estimate word count (content until next section)
            start_pos = match.end()
            end_pos = matches[i + 1].start() if i + 1 < len(matches) else len(content)
            section_content = content[start_pos:end_pos]
            word_count = len(section_content.split())

            display_order += 1

            sections.append(Section(
                module_number=module_num,
                section_id=section_id,
                title=title,
                level=level,
                parent_section_id=parent_id,
                word_count=word_count,
                display_order=display_order,
            ))

    return sections


def display_summary(sections: list[Section]) -> None:
    """Display summary of extracted sections."""
    table = Table(title="CCNA Sections Extraction Summary")
    table.add_column("Module", justify="right", style="cyan")
    table.add_column("Main (X.Y)", justify="right", style="green")
    table.add_column("Sub (X.Y.Z)", justify="right", style="yellow")
    table.add_column("Total", justify="right", style="bold")

    module_stats = {}
    for s in sections:
        if s.module_number not in module_stats:
            module_stats[s.module_number] = {'main': 0, 'sub': 0}
        if s.level == 2:
            module_stats[s.module_number]['main'] += 1
        else:
            module_stats[s.module_number]['sub'] += 1

    total_main = 0
    total_sub = 0

    for mod in sorted(module_stats.keys()):
        stats = module_stats[mod]
        total_main += stats['main']
        total_sub += stats['sub']
        table.add_row(
            str(mod),
            str(stats['main']),
            str(stats['sub']),
            str(stats['main'] + stats['sub'])
        )

    table.add_section()
    table.add_row("TOTAL", str(total_main), str(total_sub), str(total_main + total_sub), style="bold")

    console.print(table)


def insert_sections(sections: list[Section], dry_run: bool = False) -> int:
    """Insert sections into database."""
    if dry_run:
        rprint(f"\n[yellow]DRY RUN[/yellow]: Would insert {len(sections)} sections")
        return len(sections)

    from sqlalchemy import text
    from src.db.database import engine

    inserted = 0
    skipped = 0
    errors = 0

    # Sort sections: level 2 first (parents), then level 3 (children)
    sorted_sections = sorted(sections, key=lambda s: (s.level, s.display_order))

    with engine.connect() as conn:
        for section in sorted_sections:
            try:
                # Check if already exists
                result = conn.execute(
                    text("SELECT 1 FROM ccna_sections WHERE section_id = :id"),
                    {"id": section.section_id}
                )
                if result.fetchone():
                    skipped += 1
                    continue

                # Insert section
                conn.execute(
                    text("""
                        INSERT INTO ccna_sections
                        (module_number, section_id, title, level, parent_section_id,
                         word_count, display_order)
                        VALUES
                        (:module_number, :section_id, :title, :level, :parent_section_id,
                         :word_count, :display_order)
                    """),
                    {
                        "module_number": section.module_number,
                        "section_id": section.section_id,
                        "title": section.title,
                        "level": section.level,
                        "parent_section_id": section.parent_section_id,
                        "word_count": section.word_count,
                        "display_order": section.display_order,
                    }
                )
                inserted += 1
                conn.commit()  # Commit each insert individually

            except Exception as e:
                logger.error(f"Error inserting section {section.section_id}: {e}")
                errors += 1
                conn.rollback()

    rprint(f"\n[OK] Inserted {inserted} sections, skipped {skipped} existing, {errors} errors")
    return inserted


def main():
    parser = argparse.ArgumentParser(description="Populate CCNA sections table")
    parser.add_argument("--dry-run", action="store_true", help="Preview without database changes")
    parser.add_argument("--modules-dir", default="docs/CCNA", help="Path to CCNA modules directory")
    args = parser.parse_args()

    modules_dir = Path(args.modules_dir)
    if not modules_dir.exists():
        # Try relative to project root
        modules_dir = Path(__file__).parent.parent / args.modules_dir

    if not modules_dir.exists():
        rprint(f"[red]Error:[/red] Modules directory not found: {modules_dir}")
        return 1

    rprint(f"\n[bold]CCNA Sections Population[/bold]")
    rprint(f"Source: {modules_dir}")
    rprint("")

    # Extract sections
    sections = extract_sections(modules_dir)

    if not sections:
        rprint("[red]No sections extracted![/red]")
        return 1

    # Display summary
    display_summary(sections)

    # Insert into database
    insert_sections(sections, dry_run=args.dry_run)

    return 0


if __name__ == "__main__":
    sys.exit(main())
