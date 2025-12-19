#!/usr/bin/env python3
"""
Regenerate all flashcards using LLM (Gemini) with quality validation.

This script:
1. Reads CCNA module TXT files directly
2. Extracts sections using regex parsing
3. Generates flashcards using Gemini with strict grammar instructions
4. Validates each card with perplexity scoring (GPT-2) + grammar (spaCy)
5. Saves validated cards to database

Usage:
    python scripts/regenerate_llm_atoms.py --module 1
    python scripts/regenerate_llm_atoms.py --all
    python scripts/regenerate_llm_atoms.py --all --dry-run
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
from src.db.database import engine
from src.content.generation.llm_generator import (
    GeneratedCard,
    LLMFlashcardGenerator,
    extract_sections_from_txt,
)

console = Console()
settings = get_settings()


def clear_llm_atoms(source: str = "llm-generated") -> int:
    """Clear existing LLM-generated atoms from database."""
    with engine.connect() as conn:
        result = conn.execute(
            text("""
            DELETE FROM learning_atoms WHERE source = :source
        """),
            {"source": source},
        )
        conn.commit()
        return result.rowcount


def save_cards_to_db(
    cards: list[GeneratedCard],
    section_id: str,
    dry_run: bool = False,
) -> int:
    """Save generated cards to database."""
    if dry_run or not cards:
        return len(cards)

    inserted = 0
    with engine.connect() as conn:
        for card in cards:
            try:
                # Calculate a basic quality score based on perplexity
                quality_score = 1.0
                if card.perplexity:
                    # Lower perplexity = higher quality
                    if card.perplexity < 50:
                        quality_score = 1.0
                    elif card.perplexity < 100:
                        quality_score = 0.9
                    elif card.perplexity < 200:
                        quality_score = 0.8
                    elif card.perplexity < 500:
                        quality_score = 0.7
                    else:
                        quality_score = 0.6

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


def main():
    parser = argparse.ArgumentParser(
        description="Regenerate flashcards using LLM with quality validation"
    )
    parser.add_argument("--module", type=int, help="Generate for specific module (1-17)")
    parser.add_argument("--all", action="store_true", help="Generate for all modules")
    parser.add_argument("--dry-run", action="store_true", help="Preview without saving")
    parser.add_argument(
        "--max-per-section", type=int, default=8, help="Max cards per section (default: 8)"
    )
    parser.add_argument(
        "--clear",
        action="store_true",
        help="Clear existing LLM-generated atoms before regenerating",
    )
    parser.add_argument(
        "--no-validation",
        action="store_true",
        help="Skip perplexity + grammar validation (faster but lower quality)",
    )
    args = parser.parse_args()

    if not (args.module or args.all):
        console.print("[yellow]Specify --module N or --all[/yellow]")
        return 1

    # Check API key
    if not settings.gemini_api_key:
        console.print("[red]GEMINI_API_KEY not configured in .env[/red]")
        return 1

    # Find CCNA TXT files
    modules_dir = Path(__file__).parent.parent / "docs" / "CCNA"
    if not modules_dir.exists():
        console.print(f"[red]CCNA modules directory not found: {modules_dir}[/red]")
        return 1

    if args.module:
        txt_files = [modules_dir / f"CCNA Module {args.module}.txt"]
        txt_files = [f for f in txt_files if f.exists()]
    else:
        txt_files = sorted(modules_dir.glob("CCNA Module *.txt"))

    if not txt_files:
        console.print("[yellow]No CCNA module files found[/yellow]")
        return 1

    console.print("\n[bold]LLM Flashcard Regeneration[/bold]")
    console.print(f"  Model: {settings.ai_model}")
    console.print(f"  Modules: {len(txt_files)}")
    console.print(f"  Max per section: {args.max_per_section}")
    console.print(f"  Quality validation: {'disabled' if args.no_validation else 'enabled'}")
    console.print()

    # Clear existing if requested
    if args.clear and not args.dry_run:
        cleared = clear_llm_atoms()
        console.print(f"[yellow]Cleared {cleared} existing LLM-generated atoms[/yellow]")

    # Initialize generator
    generator = LLMFlashcardGenerator(use_quality_validation=not args.no_validation)

    total_sections = 0
    total_generated = 0
    total_saved = 0
    stats = {"flashcard": 0, "cloze": 0}

    # Count total sections first
    all_sections = []
    for txt_file in txt_files:
        sections = extract_sections_from_txt(txt_file)
        for section in sections:
            section["file"] = txt_file
        all_sections.extend(sections)

    console.print(f"Found {len(all_sections)} sections across {len(txt_files)} modules")

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        console=console,
    ) as progress:
        task = progress.add_task("Generating...", total=len(all_sections))

        for section in all_sections:
            section_id = section["section_id"]
            title = section["title"]
            content = section["content"]
            module_num = section["module_number"]

            progress.update(task, description=f"Module {module_num}: {section_id} {title[:30]}...")

            # Generate cards
            try:
                cards = generator.generate_from_section(
                    section_title=f"{section_id} {title}",
                    section_content=content,
                    section_id=section_id,
                    module_number=module_num,
                    max_cards=args.max_per_section,
                )
            except Exception as e:
                logger.error(f"Error generating for {section_id}: {e}")
                cards = []

            total_sections += 1
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

    table.add_row("Modules processed", str(len(txt_files)))
    table.add_row("Sections processed", str(total_sections))
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
