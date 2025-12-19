#!/usr/bin/env python3
"""
Quality Audit Script for Learning Atoms.

Analyzes existing generated cards to find quality issues and collect
negative examples for improving LLM prompts.

Usage:
    python scripts/quality_audit.py --report          # Generate quality report
    python scripts/quality_audit.py --find-garbage    # Find garbage cards
    python scripts/quality_audit.py --export-negatives # Export negative examples
    python scripts/quality_audit.py --all             # Run all audits
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from loguru import logger
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

try:
    from sqlalchemy import text

    from src.db.database import engine

    HAS_DB = True
except Exception:
    HAS_DB = False
    logger.warning("Database not available, will analyze from files")

console = Console()


# =============================================================================
# Quality Issue Patterns (Evidence-Based)
# =============================================================================


@dataclass
class QualityPattern:
    """A pattern that indicates a quality issue."""

    name: str
    pattern: re.Pattern
    severity: str  # error, warning, info
    description: str
    affects: list[str] = field(default_factory=lambda: ["all"])  # atom types affected


# Malformed question patterns
MALFORMED_PATTERNS = [
    QualityPattern(
        name="garbled_what_the",
        pattern=re.compile(r"what\s+\w+\s+The\s+\w+", re.IGNORECASE),
        severity="error",
        description="Garbled question: 'what X The Y' pattern",
    ),
    QualityPattern(
        name="vague_what_is_this",
        pattern=re.compile(r"what\s+is\s+This\b", re.IGNORECASE),
        severity="error",
        description="Vague question: 'What is This'",
    ),
    QualityPattern(
        name="bare_definition",
        pattern=re.compile(r"^What\s+is\s+\w+\?\s*$"),
        severity="warning",
        description="Bare definition question without context",
    ),
    QualityPattern(
        name="garbled_however",
        pattern=re.compile(r"what\s+\w+\s+However", re.IGNORECASE),
        severity="error",
        description="Garbled question with 'However' fragment",
    ),
    QualityPattern(
        name="garbled_if",
        pattern=re.compile(r"what\s+\w+\s+If\s+", re.IGNORECASE),
        severity="error",
        description="Garbled question with 'If' fragment",
    ),
    QualityPattern(
        name="garbled_some",
        pattern=re.compile(r"what\s+\w+\s+Some\s+", re.IGNORECASE),
        severity="error",
        description="Garbled question with 'Some' fragment",
    ),
    QualityPattern(
        name="what_is_note",
        pattern=re.compile(r"what\s+is\s+Note:\?", re.IGNORECASE),
        severity="error",
        description="Question about markdown formatting",
    ),
    QualityPattern(
        name="what_is_step",
        pattern=re.compile(r"what\s+is\s+Step\s+\d", re.IGNORECASE),
        severity="error",
        description="Question about step number",
    ),
    QualityPattern(
        name="what_type_this_type",
        pattern=re.compile(r"what\s+type\s+This\s+type", re.IGNORECASE),
        severity="error",
        description="Garbled type question",
    ),
    QualityPattern(
        name="term_describes_layer",
        pattern=re.compile(r"networking\s+term\s+describes:\s*[A-Z][a-z]+\s+layer", re.IGNORECASE),
        severity="warning",
        description="Question answer is just OSI layer name",
    ),
    QualityPattern(
        name="repeated_word",
        pattern=re.compile(r"\b(\w{4,})\s+\1\b", re.IGNORECASE),
        severity="warning",
        description="Repeated word indicates garbled text",
    ),
]

# Truncation patterns
TRUNCATION_PATTERNS = [
    QualityPattern(
        name="ends_with_article",
        pattern=re.compile(r"\s+(a|an|the)\s*$", re.IGNORECASE),
        severity="error",
        description="Answer ends with article (truncated)",
    ),
    QualityPattern(
        name="ends_with_preposition",
        pattern=re.compile(r"\s+(of|to|for|with|by|at|in|on|from|or|and)\s*$", re.IGNORECASE),
        severity="error",
        description="Answer ends with preposition (truncated)",
    ),
    QualityPattern(
        name="ends_with_comma",
        pattern=re.compile(r",\s*$"),
        severity="error",
        description="Answer ends with comma (truncated)",
    ),
    QualityPattern(
        name="no_ending_punctuation",
        pattern=re.compile(r"[a-zA-Z]{3,}$"),  # Ends with word, no punctuation
        severity="warning",
        description="Answer missing ending punctuation",
    ),
]

# Incoherent text patterns
INCOHERENT_PATTERNS = [
    QualityPattern(
        name="repeated_commas",
        pattern=re.compile(r",{2,}"),
        severity="error",
        description="Multiple consecutive commas",
    ),
    QualityPattern(
        name="double_question",
        pattern=re.compile(r"\?\s*\?"),
        severity="error",
        description="Double question marks",
    ),
    QualityPattern(
        name="empty_bold",
        pattern=re.compile(r"\*\*\s*\*\*"),
        severity="error",
        description="Empty bold markers",
    ),
    QualityPattern(
        name="dash_sequence",
        pattern=re.compile(r"—{2,}|–{2,}|-{3,}"),
        severity="warning",
        description="Multiple consecutive dashes",
    ),
]

# MCQ-specific patterns
MCQ_PATTERNS = [
    QualityPattern(
        name="all_of_above",
        pattern=re.compile(r"all\s+of\s+the\s+above", re.IGNORECASE),
        severity="warning",
        description="'All of the above' is a weak distractor",
        affects=["mcq"],
    ),
    QualityPattern(
        name="none_of_above",
        pattern=re.compile(r"none\s+of\s+the\s+above", re.IGNORECASE),
        severity="warning",
        description="'None of the above' is a weak distractor",
        affects=["mcq"],
    ),
    QualityPattern(
        name="both_a_and_b",
        pattern=re.compile(r"both\s+[A-D]\s+and\s+[A-D]", re.IGNORECASE),
        severity="warning",
        description="'Both A and B' indicates poor question design",
        affects=["mcq"],
    ),
]

# Parsons-specific patterns
PARSONS_PATTERNS = [
    QualityPattern(
        name="incomplete_command",
        pattern=re.compile(r"^[a-z]+\s*$"),  # Single word without punctuation
        severity="warning",
        description="Incomplete CLI command",
        affects=["parsons"],
    ),
]

ALL_PATTERNS = (
    MALFORMED_PATTERNS + TRUNCATION_PATTERNS + INCOHERENT_PATTERNS + MCQ_PATTERNS + PARSONS_PATTERNS
)


@dataclass
class AuditResult:
    """Result of auditing a single atom."""

    atom_id: str
    atom_type: str
    front: str
    back: str
    issues: list[str] = field(default_factory=list)
    severity: str = "ok"  # ok, warning, error
    patterns_matched: list[str] = field(default_factory=list)


@dataclass
class AuditReport:
    """Complete audit report."""

    total_atoms: int = 0
    clean_atoms: int = 0
    warning_atoms: int = 0
    error_atoms: int = 0
    by_pattern: dict = field(default_factory=dict)
    by_type: dict = field(default_factory=dict)
    examples: list[AuditResult] = field(default_factory=list)


def audit_atom(
    atom_id: str,
    atom_type: str,
    front: str,
    back: str,
    content_json: dict | None = None,
) -> AuditResult:
    """Audit a single atom for quality issues."""
    result = AuditResult(
        atom_id=atom_id,
        atom_type=atom_type,
        front=front or "",
        back=back or "",
    )

    text_to_check = f"{front or ''} ||| {back or ''}"

    for pattern in ALL_PATTERNS:
        # Skip patterns that don't apply to this atom type
        if "all" not in pattern.affects and atom_type not in pattern.affects:
            continue

        if pattern.pattern.search(text_to_check):
            result.issues.append(pattern.description)
            result.patterns_matched.append(pattern.name)

            if pattern.severity == "error":
                result.severity = "error"
            elif pattern.severity == "warning" and result.severity != "error":
                result.severity = "warning"

    # Additional checks

    # Check for very short answers (not meaningful)
    if back and len(back.strip()) < 10:
        result.issues.append("Answer too short (<10 chars)")
        if result.severity != "error":
            result.severity = "warning"

    # Check for very long questions (cognitive overload)
    if front and len(front.split()) > 30:
        result.issues.append("Question too long (>30 words)")
        if result.severity != "error":
            result.severity = "warning"

    # Check for missing question mark in questions
    if front and atom_type in ["flashcard", "mcq", "true_false"]:
        if not front.strip().endswith("?") and "{{c1::" not in front:
            result.issues.append("Question missing question mark")
            if result.severity != "error":
                result.severity = "warning"

    # Check for content duplication (question repeats in answer)
    if front and back:
        front_words = set(front.lower().split())
        back_words = set(back.lower().split())
        overlap = len(front_words & back_words) / max(len(front_words), 1)
        if overlap > 0.7:
            result.issues.append("High overlap between question and answer")
            if result.severity != "error":
                result.severity = "warning"

    # MCQ-specific checks
    if atom_type == "mcq" and content_json:
        options = content_json.get("options", [])
        if len(options) < 3:
            result.issues.append(f"MCQ has only {len(options)} options")
            result.severity = "error"
        elif len(options) > 6:
            result.issues.append(f"MCQ has {len(options)} options (too many)")
            if result.severity != "error":
                result.severity = "warning"

    # Matching-specific checks
    if atom_type == "matching" and content_json:
        pairs = content_json.get("pairs", [])
        if len(pairs) > 6:
            result.issues.append(f"Matching has {len(pairs)} pairs (max 6)")
            if result.severity != "error":
                result.severity = "warning"

    # Parsons-specific checks
    if atom_type == "parsons" and content_json:
        blocks = content_json.get("blocks", [])
        if len(blocks) < 3:
            result.issues.append(f"Parsons has only {len(blocks)} blocks")
            result.severity = "error"
        elif len(blocks) > 12:
            result.issues.append(f"Parsons has {len(blocks)} blocks (too many)")
            if result.severity != "error":
                result.severity = "warning"

    return result


def audit_from_database() -> AuditReport:
    """Audit atoms from database."""
    report = AuditReport()

    if not HAS_DB:
        console.print("[red]Database not available[/red]")
        return report

    with engine.connect() as conn:
        # Get atoms from ccna_generated_atoms
        result = conn.execute(
            text("""
            SELECT card_id, atom_type, front, back, content_json
            FROM ccna_generated_atoms
            ORDER BY generated_at DESC
        """)
        )

        rows = list(result)
        report.total_atoms = len(rows)

        console.print(f"Auditing {report.total_atoms} atoms from database...")

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            task = progress.add_task("Auditing...", total=len(rows))

            for card_id, atom_type, front, back, content_json in rows:
                audit_result = audit_atom(
                    atom_id=card_id,
                    atom_type=atom_type or "flashcard",
                    front=front or "",
                    back=back or "",
                    content_json=content_json if isinstance(content_json, dict) else None,
                )

                # Update counts
                if audit_result.severity == "ok":
                    report.clean_atoms += 1
                elif audit_result.severity == "warning":
                    report.warning_atoms += 1
                elif audit_result.severity == "error":
                    report.error_atoms += 1

                # Track by pattern
                for pattern_name in audit_result.patterns_matched:
                    if pattern_name not in report.by_pattern:
                        report.by_pattern[pattern_name] = 0
                    report.by_pattern[pattern_name] += 1

                # Track by type
                if atom_type not in report.by_type:
                    report.by_type[atom_type] = {"total": 0, "errors": 0, "warnings": 0}
                report.by_type[atom_type]["total"] += 1
                if audit_result.severity == "error":
                    report.by_type[atom_type]["errors"] += 1
                elif audit_result.severity == "warning":
                    report.by_type[atom_type]["warnings"] += 1

                # Collect examples (first 5 of each pattern)
                if audit_result.severity == "error":
                    for pattern_name in audit_result.patterns_matched:
                        existing = [
                            e for e in report.examples if pattern_name in e.patterns_matched
                        ]
                        if len(existing) < 5:
                            report.examples.append(audit_result)
                            break

                progress.advance(task)

    return report


def audit_from_files(ccna_dir: Path) -> AuditReport:
    """Audit by re-generating from source files and checking patterns."""
    report = AuditReport()

    # This would need the generator to run - skip for now
    console.print("[yellow]File-based audit requires generation - use database audit[/yellow]")

    return report


def print_report(report: AuditReport):
    """Print formatted audit report."""
    console.print("\n[bold cyan]═══ Quality Audit Report ═══[/bold cyan]\n")

    # Summary table
    summary = Table(title="Summary")
    summary.add_column("Metric", style="cyan")
    summary.add_column("Count", justify="right", style="green")
    summary.add_column("Percentage", justify="right")

    summary.add_row("Total Atoms", str(report.total_atoms), "100%")
    summary.add_row(
        "Clean (no issues)",
        str(report.clean_atoms),
        f"{report.clean_atoms / max(report.total_atoms, 1) * 100:.1f}%",
    )
    summary.add_row(
        "Warnings",
        str(report.warning_atoms),
        f"{report.warning_atoms / max(report.total_atoms, 1) * 100:.1f}%",
    )
    summary.add_row(
        "Errors",
        str(report.error_atoms),
        f"{report.error_atoms / max(report.total_atoms, 1) * 100:.1f}%",
    )

    console.print(summary)

    # Issues by pattern
    if report.by_pattern:
        console.print("\n[bold]Issues by Pattern:[/bold]")
        pattern_table = Table()
        pattern_table.add_column("Pattern", style="yellow")
        pattern_table.add_column("Count", justify="right", style="red")

        for pattern, count in sorted(report.by_pattern.items(), key=lambda x: -x[1]):
            pattern_table.add_row(pattern, str(count))

        console.print(pattern_table)

    # Issues by atom type
    if report.by_type:
        console.print("\n[bold]Issues by Atom Type:[/bold]")
        type_table = Table()
        type_table.add_column("Type", style="cyan")
        type_table.add_column("Total", justify="right")
        type_table.add_column("Errors", justify="right", style="red")
        type_table.add_column("Warnings", justify="right", style="yellow")
        type_table.add_column("Error %", justify="right")

        for atype, counts in sorted(report.by_type.items()):
            error_pct = counts["errors"] / max(counts["total"], 1) * 100
            type_table.add_row(
                atype,
                str(counts["total"]),
                str(counts["errors"]),
                str(counts["warnings"]),
                f"{error_pct:.1f}%",
            )

        console.print(type_table)


def print_garbage_examples(report: AuditReport):
    """Print garbage card examples for LLM prompt improvement."""
    console.print("\n[bold red]═══ Garbage Card Examples ═══[/bold red]\n")
    console.print("Use these as negative examples in LLM prompts:\n")

    for i, example in enumerate(report.examples[:20], 1):
        console.print(f"[red]❌ Example {i}:[/red]")
        console.print(f"   [dim]ID:[/dim] {example.atom_id}")
        console.print(f"   [dim]Type:[/dim] {example.atom_type}")
        console.print(f"   [dim]Q:[/dim] {example.front[:100]}...")
        console.print(f"   [dim]A:[/dim] {example.back[:100]}...")
        console.print(f"   [dim]Issues:[/dim] {', '.join(example.issues)}")
        console.print()


def export_negative_examples(report: AuditReport, output_path: Path):
    """Export negative examples to JSON for prompt engineering."""
    examples = []

    for ex in report.examples:
        examples.append(
            {
                "id": ex.atom_id,
                "type": ex.atom_type,
                "front": ex.front,
                "back": ex.back,
                "issues": ex.issues,
                "patterns": ex.patterns_matched,
            }
        )

    output = {
        "generated_at": datetime.now().isoformat(),
        "total_audited": report.total_atoms,
        "error_count": report.error_atoms,
        "warning_count": report.warning_atoms,
        "pattern_counts": report.by_pattern,
        "negative_examples": examples,
    }

    output_path.write_text(json.dumps(output, indent=2))
    console.print(f"\n[green]Exported {len(examples)} negative examples to {output_path}[/green]")


def main():
    parser = argparse.ArgumentParser(description="Quality Audit for Learning Atoms")
    parser.add_argument("--report", action="store_true", help="Generate quality report")
    parser.add_argument(
        "--find-garbage", action="store_true", help="Find and display garbage cards"
    )
    parser.add_argument(
        "--export-negatives", action="store_true", help="Export negative examples to JSON"
    )
    parser.add_argument("--all", action="store_true", help="Run all audits")
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("quality_audit_results.json"),
        help="Output file for exports",
    )
    args = parser.parse_args()

    if not any([args.report, args.find_garbage, args.export_negatives, args.all]):
        parser.print_help()
        return 1

    # Run audit
    report = audit_from_database()

    if args.report or args.all:
        print_report(report)

    if args.find_garbage or args.all:
        print_garbage_examples(report)

    if args.export_negatives or args.all:
        export_negative_examples(report, args.output)

    return 0


if __name__ == "__main__":
    sys.exit(main())
