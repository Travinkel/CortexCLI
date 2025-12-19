#!/usr/bin/env python3
"""Find BYOD-related flashcards to investigate quality issues."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import create_engine, text

from config import get_settings

settings = get_settings()
engine = create_engine(settings.database_url)

with engine.connect() as conn:
    # Search for BYOD-related flashcards
    result = conn.execute(
        text("""
        SELECT ca.id, ca.front, ca.back, ca.quality_score, ca.atomicity_status, cs.title
        FROM clean_atoms ca
        JOIN ccna_sections cs ON ca.ccna_section_id = cs.section_id
        WHERE ca.atom_type IN ('flashcard', 'cloze')
        AND (cs.title ILIKE '%byod%' OR cs.title ILIKE '%bring your own%'
             OR ca.front ILIKE '%byod%' OR ca.back ILIKE '%byod%')
        ORDER BY ca.quality_score ASC
        LIMIT 30
    """)
    )
    print("=== BYOD-RELATED FLASHCARDS (SORTED BY LOWEST QUALITY) ===")
    for row in result:
        print(f"\n--- Score: {row.quality_score:.2f} | Status: {row.atomicity_status} ---")
        print(f"Section: {row.title}")
        print(f"Q: {row.front[:200]}")
        print(f"A: {row.back[:200]}")

    # Also search for the specific garbage pattern the user mentioned
    print('\n\n=== SEARCHING FOR "any manner" GARBAGE PATTERN ===')
    result = conn.execute(
        text("""
        SELECT ca.id, ca.front, ca.back, ca.quality_score, cs.title
        FROM clean_atoms ca
        JOIN ccna_sections cs ON ca.ccna_section_id = cs.section_id
        WHERE ca.atom_type IN ('flashcard', 'cloze')
        AND (ca.front ILIKE '%any manner%' OR ca.back ILIKE '%any manner%'
             OR ca.front ILIKE '%concept of any%' OR ca.back ILIKE '%concept of any%')
        LIMIT 10
    """)
    )
    found = False
    for row in result:
        found = True
        print(f"\nScore: {row.quality_score:.2f} | Section: {row.title}")
        print(f"Q: {row.front}")
        print(f"A: {row.back}")
    if not found:
        print("No matches found in database")

    # Check for cards with very short or broken content
    print("\n\n=== POTENTIAL GARBAGE CARDS (very short or broken) ===")
    result = conn.execute(
        text("""
        SELECT ca.id, ca.front, ca.back, ca.quality_score, cs.title
        FROM clean_atoms ca
        JOIN ccna_sections cs ON ca.ccna_section_id = cs.section_id
        WHERE ca.atom_type IN ('flashcard', 'cloze')
        AND (LENGTH(ca.front) < 20 OR LENGTH(ca.back) < 10
             OR ca.front LIKE '%,,,% ' OR ca.back LIKE '%,,,%'
             OR ca.front LIKE '%...%...%' OR ca.back LIKE '%...%...%')
        ORDER BY ca.quality_score ASC
        LIMIT 20
    """)
    )
    for row in result:
        print(f"\nScore: {row.quality_score:.2f} | Section: {row.title}")
        print(f"Q: {row.front}")
        print(f"A: {row.back}")
