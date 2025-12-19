#!/usr/bin/env python3
"""Check quality distribution for Anki-bound cards."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import create_engine, text

from config import get_settings

settings = get_settings()
engine = create_engine(settings.database_url)

with engine.connect() as conn:
    result = conn.execute(
        text("""
        SELECT
            COUNT(*) as total,
            COUNT(*) FILTER (WHERE quality_score >= 0.75) as gte_75,
            COUNT(*) FILTER (WHERE quality_score >= 0.50) as gte_50,
            COUNT(*) FILTER (WHERE quality_score > 0 AND quality_score < 0.50) as lt_50,
            COUNT(*) FILTER (WHERE quality_score = 0 OR quality_score IS NULL) as zero_or_null
        FROM clean_atoms
        WHERE atom_type IN ('flashcard', 'cloze')
          AND ccna_section_id IS NOT NULL
    """)
    )
    row = result.fetchone()
    print("=== QUALITY DISTRIBUTION FOR ANKI-BOUND CARDS ===")
    print(f"  Total flashcard/cloze: {row.total}")
    print(f"  Quality >= 0.75 (B+):  {row.gte_75}")
    print(f"  Quality >= 0.50:       {row.gte_50}")
    print(f"  Quality < 0.50:        {row.lt_50}")
    print(f"  Quality = 0 or NULL:   {row.zero_or_null}")

    # Also check for text coherence issues
    print("\n=== MALFORMED CARD PATTERNS ===")

    # Check for repeated commas, truncated questions, etc.
    result = conn.execute(
        text("""
        SELECT COUNT(*) FROM clean_atoms
        WHERE atom_type IN ('flashcard', 'cloze')
          AND ccna_section_id IS NOT NULL
          AND (
            front LIKE '%,,,% '
            OR front LIKE '%what concept The concept%'
            OR front LIKE '%what is This%'
            OR front ~ '^[A-Za-z]+ [A-Za-z]+\\?$'  -- Very short questions like "What is This?"
            OR LENGTH(front) < 15
            OR LENGTH(back) < 5
          )
    """)
    )
    malformed = result.scalar()
    print(f"  Malformed cards detected: {malformed}")
