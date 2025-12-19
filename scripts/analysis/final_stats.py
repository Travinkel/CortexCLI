#!/usr/bin/env python3
"""Final atom statistics report."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import create_engine, text

from config import get_settings

settings = get_settings()
engine = create_engine(settings.database_url)

with engine.connect() as conn:
    # Total by type
    result = conn.execute(
        text("""
        SELECT atom_type, COUNT(*) as count
        FROM clean_atoms
        GROUP BY atom_type
        ORDER BY count DESC
    """)
    )
    print("\n=== ATOM DISTRIBUTION ===")
    total = 0
    for row in result:
        print(f"  {row.atom_type:15} {row.count:5}")
        total += row.count
    print(f"  {'TOTAL':15} {total:5}")

    # Quality grades using actual score values (scaled 0-1)
    result = conn.execute(
        text("""
        SELECT
            CASE
                WHEN quality_score >= 0.90 THEN 'A (90+)'
                WHEN quality_score >= 0.75 THEN 'B (75-89)'
                WHEN quality_score >= 0.60 THEN 'C (60-74)'
                WHEN quality_score >= 0.40 THEN 'D (40-59)'
                ELSE 'F (<40)'
            END as grade,
            COUNT(*) as count
        FROM clean_atoms
        WHERE atom_type = 'flashcard'
        GROUP BY 1
        ORDER BY 1
    """)
    )
    print("\n=== FLASHCARD QUALITY GRADES (0-1 scale) ===")
    fc_total = 0
    a_b_count = 0
    for row in result:
        print(f"  {row.grade:15} {row.count:5}")
        fc_total += row.count
        if "A" in row.grade or "B" in row.grade:
            a_b_count += row.count
    print(f"\n  Study-ready (A+B): {a_b_count} ({a_b_count / fc_total * 100:.1f}%)")

    # Check actual score distribution
    result = conn.execute(
        text("""
        SELECT
            MIN(quality_score) as min_score,
            MAX(quality_score) as max_score,
            AVG(quality_score) as avg_score
        FROM clean_atoms
        WHERE atom_type = 'flashcard' AND quality_score IS NOT NULL
    """)
    )
    row = result.fetchone()
    print("\n=== SCORE RANGE ===")
    print(f"  Min: {row.min_score:.3f}")
    print(f"  Max: {row.max_score:.3f}")
    print(f"  Avg: {row.avg_score:.3f}")

    # Sample some high quality flashcards
    result = conn.execute(
        text("""
        SELECT front, back, quality_score, is_atomic, atomicity_status
        FROM clean_atoms
        WHERE atom_type = 'flashcard'
        ORDER BY quality_score DESC
        LIMIT 3
    """)
    )
    print("\n=== SAMPLE HIGH-QUALITY FLASHCARDS ===")
    for row in result:
        print(
            f"\nScore: {row.quality_score:.2f} | Atomic: {row.is_atomic} | Status: {row.atomicity_status}"
        )
        print(f"Q: {row.front[:80]}...")
        print(f"A: {row.back[:100]}...")
