#!/usr/bin/env python3
"""Test the improved quality filter."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import create_engine, text

from config import get_settings
from src.content.cleaning.thresholds import (
    ANKI_EXCLUDE_PATTERNS,
    ANKI_MIN_BACK_LENGTH,
    ANKI_MIN_FRONT_LENGTH,
    ANKI_MIN_QUALITY_SCORE,
)

settings = get_settings()
engine = create_engine(settings.database_url)

# Build dynamic exclusion clauses
exclude_clauses = " ".join(
    f"AND ca.front NOT LIKE '{pattern}'" for pattern in ANKI_EXCLUDE_PATTERNS
)

with engine.connect() as conn:
    print("=== QUALITY FILTER SETTINGS ===")
    print(f"  Min quality score: {ANKI_MIN_QUALITY_SCORE}")
    print(f"  Min front length: {ANKI_MIN_FRONT_LENGTH}")
    print(f"  Min back length: {ANKI_MIN_BACK_LENGTH}")
    print(f"  Exclude patterns: {len(ANKI_EXCLUDE_PATTERNS)}")

    # Count all flashcard/cloze
    result = conn.execute(
        text("""
        SELECT COUNT(*) FROM clean_atoms
        WHERE atom_type IN ('flashcard', 'cloze')
          AND ccna_section_id IS NOT NULL
    """)
    )
    total = result.scalar()
    print(f"\n=== TOTAL FLASHCARD/CLOZE: {total} ===")

    # Count passing quality filter
    query = f"""
        SELECT COUNT(*) FROM clean_atoms ca
        WHERE ca.atom_type IN ('flashcard', 'cloze')
          AND ca.ccna_section_id IS NOT NULL
          AND ca.front IS NOT NULL
          AND ca.front != ''
          AND ca.quality_score IS NOT NULL
          AND ca.quality_score >= :min_quality
          AND LENGTH(ca.front) >= :min_front_length
          AND LENGTH(ca.back) >= :min_back_length
          {exclude_clauses}
    """
    result = conn.execute(
        text(query),
        {
            "min_quality": ANKI_MIN_QUALITY_SCORE,
            "min_front_length": ANKI_MIN_FRONT_LENGTH,
            "min_back_length": ANKI_MIN_BACK_LENGTH,
        },
    )
    passing = result.scalar()
    print(f"  Passing quality filter: {passing}")
    print(f"  Filtered out: {total - passing}")
    print(f"  Pass rate: {passing / total * 100:.1f}%")

    # Show some passing cards
    print("\n=== SAMPLE PASSING CARDS ===")
    query = f"""
        SELECT ca.front, ca.back, ca.quality_score
        FROM clean_atoms ca
        WHERE ca.atom_type IN ('flashcard', 'cloze')
          AND ca.ccna_section_id IS NOT NULL
          AND ca.front IS NOT NULL
          AND ca.front != ''
          AND ca.quality_score IS NOT NULL
          AND ca.quality_score >= :min_quality
          AND LENGTH(ca.front) >= :min_front_length
          AND LENGTH(ca.back) >= :min_back_length
          {exclude_clauses}
        ORDER BY ca.quality_score DESC
        LIMIT 5
    """
    result = conn.execute(
        text(query),
        {
            "min_quality": ANKI_MIN_QUALITY_SCORE,
            "min_front_length": ANKI_MIN_FRONT_LENGTH,
            "min_back_length": ANKI_MIN_BACK_LENGTH,
        },
    )
    for row in result:
        print(f"\nScore: {row.quality_score:.2f}")
        print(f"Q: {row.front[:100]}")
        print(f"A: {row.back[:80]}")

    # Show some filtered-out cards
    print("\n=== SAMPLE FILTERED-OUT CARDS ===")
    result = conn.execute(
        text("""
        SELECT front, back, quality_score
        FROM clean_atoms
        WHERE atom_type IN ('flashcard', 'cloze')
          AND ccna_section_id IS NOT NULL
          AND (quality_score IS NULL OR quality_score < :min_quality
               OR LENGTH(front) < :min_front OR LENGTH(back) < :min_back)
        ORDER BY quality_score DESC NULLS LAST
        LIMIT 5
    """),
        {
            "min_quality": ANKI_MIN_QUALITY_SCORE,
            "min_front": ANKI_MIN_FRONT_LENGTH,
            "min_back": ANKI_MIN_BACK_LENGTH,
        },
    )
    for row in result:
        score_str = f"{row.quality_score:.2f}" if row.quality_score else "NULL"
        print(f"\nScore: {score_str}")
        print(f"Q: {row.front[:100] if row.front else 'EMPTY'}")
        print(f"A: {row.back[:80] if row.back else 'EMPTY'}")
