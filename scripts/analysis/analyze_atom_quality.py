#!/usr/bin/env python3
"""
Analyze and Update Atom Quality Scores

Runs the quality analyzer on all flashcards and updates their quality scores.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from loguru import logger
from sqlalchemy import create_engine, text

from config import get_settings
from src.content.cleaning.atomicity import CardQualityAnalyzer

settings = get_settings()
engine = create_engine(settings.database_url)
analyzer = CardQualityAnalyzer()


def analyze_and_update_flashcards(limit: int = None, dry_run: bool = False):
    """Analyze flashcards and update their quality scores."""
    with engine.connect() as conn:
        # Get flashcards
        query = """
            SELECT id, front, back
            FROM clean_atoms
            WHERE atom_type = 'flashcard'
        """
        if limit:
            query += f" LIMIT {limit}"

        result = conn.execute(text(query))
        rows = result.fetchall()

        logger.info(f"Analyzing {len(rows)} flashcards...")

        # Track quality distribution
        grade_counts = {"A": 0, "B": 0, "C": 0, "D": 0, "F": 0}
        updated = 0

        for row in rows:
            # Analyze the card
            report = analyzer.analyze(row.front, row.back)

            # Count grades
            grade_counts[report.grade.value] += 1

            if not dry_run:
                # Update the database (only columns that exist)
                # Scale score to 0-1 range if column is DECIMAL(3,2), otherwise 0-100
                # Most DB columns use 0-100, but some use 0-1 scale
                scaled_score = report.score / 100.0  # Convert to 0-1 for DECIMAL(3,2)
                conn.execute(
                    text("""
                    UPDATE clean_atoms
                    SET quality_score = :score,
                        is_atomic = :is_atomic,
                        atomicity_status = :status
                    WHERE id = :id
                """),
                    {
                        "id": str(row.id),
                        "score": scaled_score,
                        "is_atomic": report.is_atomic,
                        "status": "atomic"
                        if report.is_atomic
                        else ("verbose" if report.is_verbose else "needs_split"),
                    },
                )
                updated += 1

                if updated % 500 == 0:
                    conn.commit()
                    logger.info(f"  Updated {updated}/{len(rows)} flashcards...")

        if not dry_run:
            conn.commit()

        # Print summary
        print("\n=== QUALITY ANALYSIS RESULTS ===")
        print(f"Total analyzed: {len(rows)}")
        print("\nGrade Distribution:")
        for grade, count in sorted(grade_counts.items()):
            pct = count / len(rows) * 100 if rows else 0
            print(f"  {grade}: {count:5} ({pct:5.1f}%)")

        good = grade_counts["A"] + grade_counts["B"]
        print(f"\nStudy-ready (A+B): {good} ({good / len(rows) * 100:.1f}%)")

        if dry_run:
            print("\n[DRY RUN - No changes saved]")
        else:
            print(f"\n[Updated {updated} flashcards in database]")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, help="Limit to N flashcards")
    parser.add_argument("--dry-run", action="store_true", help="Don't save changes")
    args = parser.parse_args()

    analyze_and_update_flashcards(limit=args.limit, dry_run=args.dry_run)
