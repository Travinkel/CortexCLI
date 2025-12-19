#!/usr/bin/env python3
"""
Generate Atoms for Struggle Sections.

Uses the AtomizerService with Gemini to generate targeted atoms
for sections identified in the struggle map.

Usage:
    python scripts/atoms/generate_struggle_atoms.py --struggle-map data/ccna_struggle_map.yaml
    python scripts/atoms/generate_struggle_atoms.py --sections 11.3,11.4,11.5 --types mcq,parsons
    python scripts/atoms/generate_struggle_atoms.py --module 11 --severity critical
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path
from typing import Any

from loguru import logger
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from config import get_settings

console = Console()


# =============================================================================
# Struggle Map Integration
# =============================================================================


def load_struggle_map(file_path: Path) -> dict[str, Any]:
    """Load struggle map from YAML/JSON file."""
    import json

    import yaml

    if not file_path.exists():
        raise FileNotFoundError(f"Struggle map not found: {file_path}")

    with open(file_path) as f:
        if file_path.suffix in (".yaml", ".yml"):
            return yaml.safe_load(f)
        return json.load(f)


def expand_wildcard_section(section_pattern: str, module_num: int) -> list[str]:
    """
    Expand wildcard patterns like '5.x' or '3.2.x' to actual section IDs.

    For now, returns the pattern as-is since the atomizer will handle it.
    In production, this would query the database for matching sections.
    """
    # If it's a wildcard, keep it as-is (the loader will handle expansion)
    if section_pattern.endswith(".x") or section_pattern.endswith(".*"):
        return [section_pattern]
    return [section_pattern]


def get_sections_from_struggle_map(
    struggle_map: dict,
    min_severity: str = "high",
) -> list[dict]:
    """
    Extract sections to generate atoms for based on severity.

    Supports v2.0 struggle map format with:
    - Wildcard patterns (5.x, 3.2.x)
    - Structured failure_modes (primary/secondary)

    Returns list of dicts with section info and recommended atom types.
    """
    severity_priority = {"critical": 1, "high": 2, "medium": 3, "low": 4}
    threshold = severity_priority.get(min_severity, 3)

    # Get failure mode -> atom type mapping from preferences
    fm_types = struggle_map.get("preferences", {}).get("preferred_atom_types", {})

    sections = []
    for entry in struggle_map.get("struggles", []):
        entry_severity = entry.get("severity", "medium")
        if severity_priority.get(entry_severity, 3) > threshold:
            continue

        # Handle v2.0 format: failure_modes can be dict with primary/secondary
        failure_modes_raw = entry.get("failure_modes", [])
        failure_modes = []

        if isinstance(failure_modes_raw, dict):
            # v2.0 format: {"primary": "FM3", "secondary": ["FM4"]}
            primary = failure_modes_raw.get("primary")
            secondary = failure_modes_raw.get("secondary", [])
            if primary:
                failure_modes.append(primary)
            if isinstance(secondary, list):
                failure_modes.extend(secondary)
            elif secondary:
                failure_modes.append(secondary)
        elif isinstance(failure_modes_raw, list):
            # v1.0 format: ["FM1", "FM3"]
            failure_modes = failure_modes_raw

        # Determine atom types based on failure modes
        recommended_types = set()
        for fm in failure_modes:
            types = fm_types.get(fm, ["flashcard", "mcq"])
            recommended_types.update(types)

        # Default types if no specific recommendations
        if not recommended_types:
            recommended_types = {"flashcard", "mcq", "cloze"}

        module_num = entry["module"]
        for section_pattern in entry.get("sections", []):
            # Expand wildcards
            expanded = expand_wildcard_section(section_pattern, module_num)
            for section_id in expanded:
                sections.append({
                    "module": module_num,
                    "section_id": section_id,
                    "severity": entry_severity,
                    "failure_modes": failure_modes,
                    "recommended_types": list(recommended_types),
                    "notes": entry.get("notes"),
                })

    return sections


# =============================================================================
# Content Loading
# =============================================================================


async def load_section_content(section_id: str) -> dict | None:
    """
    Load section content from database or file system.

    Handles wildcard patterns like '5.x' by loading all matching sections.
    Returns dict with section metadata and raw content for atomization.
    """
    from sqlalchemy import text

    from src.db.database import engine

    # Get section metadata from database
    section_meta = None
    with engine.connect() as conn:
        # Handle wildcard patterns - get all matching section IDs
        if section_id.endswith(".x") or section_id.endswith(".*"):
            prefix = section_id[:-2]  # Remove '.x' or '.*'
            result = conn.execute(
                text("""
                SELECT section_id, module_number, title, level, word_count
                FROM ccna_sections
                WHERE section_id LIKE :prefix
                ORDER BY section_id
                """),
                {"prefix": f"{prefix}.%"},
            )
            rows = result.fetchall()
            if rows:
                section_meta = {
                    "id": section_id,
                    "module": rows[0].module_number,
                    "title": f"Sections {prefix}.*",
                    "level": 1,
                    "expanded_sections": [r.section_id for r in rows],
                }
        else:
            # Exact match
            result = conn.execute(
                text("""
                SELECT section_id, module_number, title, level, word_count
                FROM ccna_sections
                WHERE section_id = :section_id
                """),
                {"section_id": section_id},
            )
            row = result.fetchone()
            if row:
                section_meta = {
                    "id": row.section_id,
                    "module": row.module_number,
                    "title": row.title,
                    "level": row.level,
                }

    # Load content from CCNA docs directory
    docs_dir = Path(__file__).parent.parent.parent / "docs" / "source-materials" / "CCNA"

    # Handle wildcards - extract prefix for file loading
    if section_id.endswith(".x") or section_id.endswith(".*"):
        prefix = section_id[:-2]  # e.g., "5.x" -> "5"
        try:
            module_num = int(prefix.split(".")[0])
        except ValueError:
            logger.warning(f"Invalid section_id format: {section_id}")
            return None
    else:
        try:
            module_num = int(section_id.split(".")[0])
        except ValueError:
            logger.warning(f"Invalid section_id format: {section_id}")
            return None

    # Look for matching file - try multiple patterns
    patterns = [
        f"*Module {module_num}.txt",  # "CCNA Module 5.txt"
        f"*Module{module_num:02d}*.txt",  # "Module05..."
        f"*Module {module_num:02d}*.txt",  # "Module 05..."
    ]
    file_content = None
    for pattern in patterns:
        for txt_file in docs_dir.glob(pattern):
            with open(txt_file, encoding="utf-8") as f:
                file_content = f.read()
            break
        if file_content:
            break

    if not file_content:
        logger.warning(f"Could not find module file for section {section_id}")
        return None

    # Handle wildcards - load all sections matching prefix
    if section_id.endswith(".x") or section_id.endswith(".*"):
        prefix = section_id[:-2]
        # Find all sections starting with this prefix
        import re

        # Look for section headers like "## 5.1" or "### 5.1.1" in markdown
        section_pattern = rf"^#+\s*({re.escape(prefix)}\.\d+(?:\.\d+)*)\s+"
        matches = list(re.finditer(section_pattern, file_content, re.MULTILINE))

        if not matches:
            # Try without markdown - just section numbers at line start
            section_pattern = rf"^({re.escape(prefix)}\.\d+(?:\.\d+)*)\s+"
            matches = list(re.finditer(section_pattern, file_content, re.MULTILINE))

        if matches:
            combined_content = []
            for i, match in enumerate(matches):
                start = match.start()
                end = matches[i + 1].start() if i + 1 < len(matches) else len(file_content)
                section_text = file_content[start:end].strip()
                if section_text:
                    combined_content.append(section_text)

            if combined_content:
                return {
                    "id": section_id,
                    "module": module_num,
                    "title": section_meta.get("title", f"Sections {prefix}.*") if section_meta else f"Sections {prefix}.*",
                    "level": 1,
                    "word_count": sum(len(c.split()) for c in combined_content),
                    "raw_content": "\n\n".join(combined_content),
                    "expanded_sections": section_meta.get("expanded_sections", []) if section_meta else [],
                }

        # If no regex matches, return the entire file content (it's all relevant)
        logger.info(f"No section markers found for {section_id}, using entire file content")
        return {
            "id": section_id,
            "module": module_num,
            "title": section_meta.get("title", f"Module {module_num}") if section_meta else f"Module {module_num}",
            "level": 1,
            "word_count": len(file_content.split()),
            "raw_content": file_content,
            "expanded_sections": section_meta.get("expanded_sections", []) if section_meta else [],
        }

    # Single section - extract just that section
    section_marker = f"{section_id}"
    if section_marker in file_content:
        start = file_content.find(section_marker)
        # Find next section at same or higher level
        next_section = file_content.find(f"\n{module_num}.", start + len(section_marker))
        if next_section == -1:
            next_section = len(file_content)

        section_content = file_content[start:next_section].strip()
        return {
            "id": section_id,
            "module": module_num,
            "title": section_meta.get("title", f"Section {section_id}") if section_meta else f"Section {section_id}",
            "level": len(section_id.split(".")),
            "word_count": len(section_content.split()),
            "raw_content": section_content,
        }

    logger.warning(f"Could not find content for section {section_id}")
    return None


# =============================================================================
# Atom Generation
# =============================================================================


async def generate_atoms_for_section(
    section_info: dict,
    atom_types: list[str] | None = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    """
    Generate atoms for a single section using AtomizerService.

    Args:
        section_info: Dict with section_id, content, recommended_types
        atom_types: Override atom types to generate
        dry_run: If True, don't save to database

    Returns:
        Dict with generation results. If not a dry run, includes a serializable
        list of atoms under key "atoms" suitable for export or saving.
    """
    from src.ccna.atomizer_service import AtomizerService, AtomType
    from src.ccna.content_parser import Section

    # Determine types to generate
    types_to_generate = atom_types or section_info.get("recommended_types", ["flashcard", "mcq"])

    # Map string types to AtomType enum
    type_map = {
        "flashcard": AtomType.FLASHCARD,
        "cloze": AtomType.CLOZE,
        "mcq": AtomType.MCQ,
        "true_false": AtomType.TRUE_FALSE,
        "parsons": AtomType.PARSONS,
        "matching": AtomType.MATCHING,
        "numeric": AtomType.NUMERIC,
        "compare": AtomType.COMPARE,
    }

    target_types = [type_map[t] for t in types_to_generate if t in type_map]

    if not target_types:
        return {"error": "No valid atom types specified"}

    # Load section content
    content = await load_section_content(section_info["section_id"])
    if not content or not content.get("raw_content"):
        return {"error": f"No content found for section {section_info['section_id']}"}

    # Create Section object for atomizer
    section = Section(
        id=content["id"],
        title=content.get("title", ""),
        level=content.get("level", 2),
        content=content["raw_content"],  # Use raw_content for both
        raw_content=content["raw_content"],
    )

    if dry_run:
        return {
            "section_id": section_info["section_id"],
            "content_words": content.get("word_count", 0),
            "target_types": [t.value for t in target_types],
            "status": "dry_run",
        }

    # Initialize atomizer
    atomizer = AtomizerService()

    try:
        result = await atomizer.atomize_section(section, target_types)

        # Build serializable atoms for export/save
        atoms_serializable = []
        for a in getattr(result, "atoms", []) or []:
            try:
                atoms_serializable.append({
                    "card_id": getattr(a, "card_id", None),
                    "atom_type": getattr(getattr(a, "atom_type", None), "value", getattr(a, "atom_type", None)),
                    "front": getattr(a, "front", None),
                    "back": getattr(a, "back", None),
                    "quality_score": getattr(a, "quality_score", None),
                    "content_json": getattr(a, "content_json", None),
                    "is_hydrated": getattr(a, "is_hydrated", None),
                    "fidelity_type": getattr(a, "fidelity_type", None),
                    "source_fact_basis": getattr(a, "source_fact_basis", None),
                })
            except Exception as _:
                # Best-effort serialization; skip problematic atom
                continue

        return {
            "section_id": section_info["section_id"],
            "atoms_generated": len(getattr(result, "atoms", []) or []),
            "by_type": {t.value: len([a for a in getattr(result, "atoms", []) or [] if getattr(a, "atom_type", None) == t]) for t in target_types},
            "errors": getattr(result, "errors", []),
            "warnings": getattr(result, "warnings", []),
            "atoms": atoms_serializable,
        }

    except Exception as e:
        logger.error(f"Generation failed for {section_info['section_id']}: {e}")
        return {
            "section_id": section_info["section_id"],
            "error": str(e),
        }


async def save_generated_atoms(atoms: list, section_id: str) -> int:
    """
    Save generated atoms to the database.

    Supports both atom objects and plain dicts as produced by
    `generate_atoms_for_section`.

    Returns number of atoms saved. If asyncpg is unavailable, logs a warning
    and returns 0.
    """
    try:
        import asyncpg  # type: ignore
    except Exception:
        logger.warning("asyncpg not installed. Skipping DB save. Use --export to write atoms to file.")
        return 0

    settings = get_settings()
    conn = await asyncpg.connect(settings.database_url)

    def _get(val, attr):
        # Helper to access from object or dict
        if isinstance(val, dict):
            return val.get(attr)
        return getattr(val, attr, None)

    saved = 0
    try:
        for atom in atoms:
            try:
                await conn.execute(
                    """
                    INSERT INTO learning_atoms (
                        card_id, atom_type, front, back, quality_score,
                        ccna_section_id, source, content_json,
                        is_hydrated, fidelity_type, source_fact_basis
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
                    ON CONFLICT (card_id) DO UPDATE SET
                        front = EXCLUDED.front,
                        back = EXCLUDED.back,
                        updated_at = NOW()
                    """,
                    _get(atom, "card_id"),
                    _get(atom, "atom_type") if isinstance(_get(atom, "atom_type"), str) else _get(_get(atom, "atom_type"), "value"),
                    _get(atom, "front"),
                    _get(atom, "back"),
                    _get(atom, "quality_score"),
                    section_id,
                    "struggle_generation",
                    _get(atom, "content_json"),
                    _get(atom, "is_hydrated"),
                    _get(atom, "fidelity_type"),
                    _get(atom, "source_fact_basis"),
                )
                saved += 1
            except Exception as e:
                logger.error(f"Failed to save atom {_get(atom, 'card_id')}: {e}")

        return saved

    finally:
        await conn.close()


# =============================================================================
# Export Helpers
# =============================================================================


def export_atoms_to_file(atoms: list, section_id: str, export_dir: Path) -> int:
    """
    Export atoms to JSONL file per section. Accepts dict or object atoms.
    Returns number of atoms written.
    """
    import json

    export_dir.mkdir(parents=True, exist_ok=True)
    out_path = export_dir / f"{section_id.replace('.', '_')}.jsonl"

    def _to_dict(a):
        if isinstance(a, dict):
            return a
        # object fallback
        return {
            "card_id": getattr(a, "card_id", None),
            "atom_type": getattr(getattr(a, "atom_type", None), "value", getattr(a, "atom_type", None)),
            "front": getattr(a, "front", None),
            "back": getattr(a, "back", None),
            "quality_score": getattr(a, "quality_score", None),
            "content_json": getattr(a, "content_json", None),
            "is_hydrated": getattr(a, "is_hydrated", None),
            "fidelity_type": getattr(a, "fidelity_type", None),
            "source_fact_basis": getattr(a, "source_fact_basis", None),
        }

    written = 0
    with open(out_path, "w", encoding="utf-8") as f:
        for a in atoms or []:
            try:
                f.write(json.dumps(_to_dict(a), ensure_ascii=False) + "\n")
                written += 1
            except Exception as e:
                logger.error(f"Failed to export atom: {e}")

    return written


# =============================================================================
# Main Entry Point
# =============================================================================


async def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Generate atoms for CCNA struggle sections using Gemini"
    )
    parser.add_argument(
        "--struggle-map",
        type=Path,
        help="Path to struggle map YAML file",
    )
    parser.add_argument(
        "--sections",
        help="Comma-separated section IDs (e.g., 11.3,11.4)",
    )
    parser.add_argument(
        "--module",
        type=int,
        help="Generate for all sections in a module",
    )
    parser.add_argument(
        "--severity",
        choices=["critical", "high", "medium", "low"],
        default="high",
        help="Minimum severity threshold (default: high)",
    )
    parser.add_argument(
        "--types",
        help="Comma-separated atom types (flashcard,mcq,cloze,parsons,numeric)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be generated without calling API",
    )
    parser.add_argument(
        "--save",
        action="store_true",
        help="Save generated atoms to database",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=10,
        help="Max sections to process (default: 10)",
    )
    parser.add_argument(
        "--export",
        action="store_true",
        help="Export generated atoms to JSONL files (data/exports/atoms by default)",
    )
    parser.add_argument(
        "--export-dir",
        type=Path,
        default=Path("data/exports/atoms"),
        help="Directory to write JSONL export files",
    )

    args = parser.parse_args()

    # Determine sections to process
    sections = []

    if args.struggle_map:
        console.print(f"[cyan]Loading struggle map:[/cyan] {args.struggle_map}")
        struggle_data = load_struggle_map(args.struggle_map)
        sections = get_sections_from_struggle_map(struggle_data, args.severity)
        console.print(f"[green]Found {len(sections)} sections at severity >= {args.severity}[/green]")

    elif args.sections:
        section_ids = [s.strip() for s in args.sections.split(",")]
        default_types = args.types.split(",") if args.types else ["flashcard", "mcq"]
        sections = [
            {"section_id": sid, "recommended_types": default_types}
            for sid in section_ids
        ]

    elif args.module:
        # Query all sections for the module using SQLAlchemy
        from sqlalchemy import text
        from src.db.database import engine

        with engine.connect() as conn:
            result = conn.execute(
                text("SELECT section_id FROM ccna_sections WHERE module_number = :module_num ORDER BY section_id"),
                {"module_num": args.module},
            )
            rows = result.fetchall()

        default_types = args.types.split(",") if args.types else ["flashcard", "mcq"]
        sections = [
            {"section_id": row.section_id, "recommended_types": default_types}
            for row in rows
        ]
        console.print(f"[green]Found {len(sections)} sections in module {args.module}[/green]")

    else:
        console.print("[red]Specify --struggle-map, --sections, or --module[/red]")
        sys.exit(1)

    # Limit sections
    sections = sections[:args.limit]

    # Override types if specified
    atom_types = args.types.split(",") if args.types else None

    # Display plan
    console.print(
        Panel(
            f"[bold]ATOM GENERATION PLAN[/bold]\n\n"
            f"Sections: {len(sections)}\n"
            f"Types: {atom_types or 'per-section recommendations'}\n"
            f"Dry run: {args.dry_run}\n"
            f"Save to DB: {args.save}\n"
            f"Export: {args.export} -> {args.export_dir if args.export else ''}",
            border_style="cyan",
        )
    )

    # Process sections
    results = []
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("Generating atoms...", total=len(sections))

        total_saved = 0
        total_exported = 0
        for section in sections:
            progress.update(task, description=f"Processing {section['section_id']}...")

            result = await generate_atoms_for_section(
                section,
                atom_types=atom_types,
                dry_run=args.dry_run,
            )

            # Persist or export if requested and not a dry run
            if not args.dry_run and isinstance(result, dict) and not result.get("error"):
                atoms_for_io = result.get("atoms") or []
                if args.save and atoms_for_io:
                    try:
                        saved = await save_generated_atoms(atoms_for_io, section["section_id"])
                        total_saved += saved
                    except Exception as e:
                        logger.error(f"Save failed for {section['section_id']}: {e}")
                if args.export and atoms_for_io:
                    try:
                        exported = export_atoms_to_file(atoms_for_io, section["section_id"], args.export_dir)
                        total_exported += exported
                    except Exception as e:
                        logger.error(f"Export failed for {section['section_id']}: {e}")

            results.append(result)

            progress.advance(task)

        # Attach IO totals to results for footer display
        results.append({"__totals__": {"saved": total_saved, "exported": total_exported}})

    # Display results
    table = Table(show_header=True, header_style="bold")
    table.add_column("Section", style="cyan")
    table.add_column("Atoms", justify="right")
    table.add_column("Types", style="dim")
    table.add_column("Status")

    total_atoms = 0
    total_words = 0
    for r in results:
        if "error" in r:
            table.add_row(
                r.get("section_id", "?"),
                "-",
                "-",
                f"[red]{r['error'][:30]}[/red]",
            )
        else:
            count = r.get("atoms_generated", 0)
            total_atoms += count
            words = r.get("content_words", 0)
            total_words += words
            by_type = r.get("by_type", {})
            target_types = r.get("target_types", [])

            # For dry run, show target types; for real run, show generated counts
            if r.get("status") == "dry_run":
                type_str = ", ".join(target_types) if target_types else "-"
                status = f"[blue]{words} words[/blue]"
            else:
                type_str = ", ".join(f"{k}:{v}" for k, v in by_type.items() if v > 0) or "-"
                status = "[green]OK[/green]" if count > 0 else "[yellow]Empty[/yellow]"

            table.add_row(
                r.get("section_id", "?"),
                str(count) if not r.get("status") == "dry_run" else "-",
                type_str,
                status,
            )

    console.print("\n")
    console.print(table)

    # Footer totals (including persisted/exported if attached)
    totals = next((r.get("__totals__") for r in results if isinstance(r, dict) and r.get("__totals__")), {"saved": 0, "exported": 0})

    if args.dry_run:
        console.print(f"\n[bold cyan]Total content:[/bold cyan] {total_words:,} words across {len(results)-1 if totals else len(results)} sections")
        console.print("\n[yellow]This was a dry run. Run without --dry-run to generate atoms.[/yellow]")
    else:
        console.print(f"\n[bold green]Total atoms generated:[/bold green] {total_atoms}")
        if args.save:
            console.print(f"[bold green]Saved to DB:[/bold green] {totals.get('saved', 0)}")
        if args.export:
            console.print(f"[bold green]Exported to files:[/bold green] {totals.get('exported', 0)} -> {args.export_dir}")


if __name__ == "__main__":
    asyncio.run(main())
