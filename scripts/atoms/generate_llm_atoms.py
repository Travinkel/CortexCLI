#!/usr/bin/env python3
"""
Generate flashcards using LLM (Gemini).

This replaces the regex-based generation with LLM-based generation
that produces grammatically correct cards by construction.

Usage:
    python scripts/generate_llm_atoms.py --module 1
    python scripts/generate_llm_atoms.py --all
    python scripts/generate_llm_atoms.py --section 1.1.1
"""

from __future__ import annotations

import argparse
import sys
import uuid
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from loguru import logger
from rich.console import Console
from rich.progress import BarColumn, Progress, SpinnerColumn, TextColumn
from rich.table import Table
from sqlalchemy import text

from config import get_settings
from src.content.cleaning.atomicity import CardQualityAnalyzer
from src.db.database import engine
from src.content.generation.llm_generator import GeneratedCard, LLMFlashcardGenerator

console = Console()
settings = get_settings()
quality_analyzer = CardQualityAnalyzer()


def get_sections(module: int = None, section_id: str = None, all_modules: bool = False):
    """Get sections to process from database."""
    with engine.connect() as conn:
        if section_id:
            result = conn.execute(
                text("""
                SELECT section_id, title, content, module_number
                FROM ccna_sections
                WHERE section_id = :id AND content IS NOT NULL
            """),
                {"id": section_id},
            )
        elif module:
            result = conn.execute(
                text("""
                SELECT section_id, title, content, module_number
                FROM ccna_sections
                WHERE module_number = :mod
                  AND content IS NOT NULL
                  AND LENGTH(content) > 100
                ORDER BY display_order
            """),
                {"mod": module},
            )
        elif all_modules:
            result = conn.execute(
                text("""
                SELECT section_id, title, content, module_number
                FROM ccna_sections
                WHERE content IS NOT NULL
                  AND LENGTH(content) > 100
                ORDER BY module_number, display_order
            """)
            )
        else:
            return []

        return list(result)


def save_cards_to_db(cards: list[GeneratedCard], section_id: str, dry_run: bool = False) -> int:
    """Save generated cards to database."""
    if dry_run or not cards:
        return len(cards)

    inserted = 0
    with engine.connect() as conn:
        for card in cards:
            # Calculate quality score
            report = quality_analyzer.analyze(card.question, card.answer, card.card_type)
            quality_score = report.score / 100.0

            try:
                conn.execute(
                    text("""
                    INSERT INTO learning_atoms
                    (id, atom_type, front, back, ccna_section_id, quality_score, source, created_at)
                    VALUES (:id, :type, :front, :back, :section, :quality, :source, :created)
                    ON CONFLICT (id) DO NOTHING
                """),
                    {
                        "id": str(uuid.uuid4()),
                        "type": card.card_type,
                        "front": card.question,
                        "back": card.answer,
                        "section": section_id,
                        "quality": quality_score,
                        "source": "llm-generated",
                        "created": datetime.now(),
                    },
                )
                inserted += 1
            except Exception as e:
                logger.error(f"Error inserting card: {e}")

        conn.commit()

    return inserted


def clear_section_atoms(section_id: str, source: str = "llm-generated"):
    """Clear existing LLM-generated atoms for a section."""
    with engine.connect() as conn:
        result = conn.execute(
            text("""
            DELETE FROM clean_atoms
            WHERE ccna_section_id = :section AND source = :source
        """),
            {"section": section_id, "source": source},
        )
        conn.commit()
        return result.rowcount


def main():
    parser = argparse.ArgumentParser(description="Generate flashcards using LLM")
    parser.add_argument("--module", type=int, help="Generate for specific module (1-16)")
    parser.add_argument("--section", type=str, help="Generate for specific section")
    parser.add_argument("--all", action="store_true", help="Generate for all modules")
    parser.add_argument("--dry-run", action="store_true", help="Preview without saving")
    parser.add_argument("--max-per-section", type=int, default=8, help="Max cards per section")
    parser.add_argument(
        "--replace", action="store_true", help="Replace existing LLM-generated cards"
    )
    args = parser.parse_args()

    if not (args.module or args.section or args.all):
        console.print("[yellow]Specify --module N, --section X.Y.Z, or --all[/yellow]")
        return 1

    # Check API key
    if not settings.gemini_api_key:
        console.print("[red]GEMINI_API_KEY not configured in .env[/red]")
        return 1

    sections = get_sections(
        module=args.module,
        section_id=args.section,
        all_modules=args.all,
    )

    if not sections:
        console.print("[yellow]No sections found[/yellow]")
        return 1

    console.print("\n[bold]LLM Flashcard Generation[/bold]")
    console.print(f"  Model: {settings.ai_model}")
    console.print(f"  Sections: {len(sections)}")
    console.print(f"  Max per section: {args.max_per_section}")
    console.print()

    generator = LLMFlashcardGenerator()
    total_generated = 0
    total_saved = 0
    stats = {"flashcard": 0, "cloze": 0}

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        console=console,
    ) as progress:
        task = progress.add_task("Generating...", total=len(sections))

        for section_id, title, content, module_num in sections:
            progress.update(task, description=f"Module {module_num}: {section_id}")

            # Clear existing if replacing
            if args.replace and not args.dry_run:
                cleared = clear_section_atoms(section_id)
                if cleared:
                    logger.debug(f"Cleared {cleared} existing cards for {section_id}")

            # Generate cards
            cards = generator.generate_from_section(
                section_title=f"{section_id} {title}",
                section_content=content,
                max_cards=args.max_per_section,
            )

            total_generated += len(cards)
            for card in cards:
                stats[card.card_type] = stats.get(card.card_type, 0) + 1

            # Save to database
            if not args.dry_run:
                saved = save_cards_to_db(cards, section_id, dry_run=args.dry_run)
                total_saved += saved

            progress.advance(task)

    # Summary table
    table = Table(title="Generation Summary")
    table.add_column("Metric", style="cyan")
    table.add_column("Value", justify="right", style="green")

    table.add_row("Sections processed", str(len(sections)))
    table.add_row("Cards generated", str(total_generated))
    for card_type, count in stats.items():
        table.add_row(f"  {card_type}", str(count))
    if not args.dry_run:
        table.add_row("Cards saved", str(total_saved))

    console.print(table)

    if args.dry_run:
        console.print("\n[yellow]DRY RUN - No cards saved[/yellow]")

    return 0


if __name__ == "__main__":
    sys.exit(main())
