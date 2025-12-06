#!/usr/bin/env python3
"""
Cleanup and Regenerate Flashcards

This script:
1. Deletes all broken flashcards (quality_score < 50 or quality_score = 0)
2. Regenerates fresh flashcards from CCNA source content using generate_all_atoms.py logic
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import create_engine, text
from config import get_settings
from loguru import logger

settings = get_settings()
engine = create_engine(settings.database_url)


def count_flashcards():
    """Count current flashcard distribution."""
    with engine.connect() as conn:
        result = conn.execute(text("""
            SELECT
                COUNT(*) as total,
                COUNT(*) FILTER (WHERE quality_score = 0) as score_zero,
                COUNT(*) FILTER (WHERE quality_score > 0 AND quality_score < 50) as low_quality,
                COUNT(*) FILTER (WHERE quality_score >= 50) as acceptable
            FROM clean_atoms
            WHERE atom_type = 'flashcard'
        """))
        row = result.fetchone()
        return {
            "total": row.total,
            "score_zero": row.score_zero,
            "low_quality": row.low_quality,
            "acceptable": row.acceptable
        }


def delete_broken_flashcards(dry_run=True):
    """Delete all flashcards with quality_score < 50."""
    with engine.connect() as conn:
        # First, count what we'll delete
        result = conn.execute(text("""
            SELECT COUNT(*) FROM clean_atoms
            WHERE atom_type = 'flashcard' AND (quality_score < 50 OR quality_score IS NULL)
        """))
        to_delete = result.scalar()

        logger.info(f"Found {to_delete} flashcards to delete (quality_score < 50)")

        if not dry_run:
            conn.execute(text("""
                DELETE FROM clean_atoms
                WHERE atom_type = 'flashcard' AND (quality_score < 50 OR quality_score IS NULL)
            """))
            conn.commit()
            logger.info(f"Deleted {to_delete} broken flashcards")
        else:
            logger.info("[DRY RUN] Would delete these flashcards")

        return to_delete


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Cleanup broken flashcards")
    parser.add_argument("--delete", action="store_true", help="Actually delete (not dry run)")
    parser.add_argument("--stats", action="store_true", help="Just show stats")
    args = parser.parse_args()

    print("\n=== CURRENT FLASHCARD STATUS ===")
    stats = count_flashcards()
    print(f"  Total flashcards: {stats['total']}")
    print(f"  Quality score = 0: {stats['score_zero']} (garbage)")
    print(f"  Quality score < 50: {stats['low_quality']} (low quality)")
    print(f"  Quality score >= 50: {stats['acceptable']} (acceptable)")

    if args.stats:
        sys.exit(0)

    print("\n=== DELETING BROKEN FLASHCARDS ===")
    deleted = delete_broken_flashcards(dry_run=not args.delete)

    if args.delete:
        print("\n=== AFTER CLEANUP ===")
        stats = count_flashcards()
        print(f"  Remaining flashcards: {stats['total']}")
