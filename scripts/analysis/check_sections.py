#!/usr/bin/env python3
"""Check CCNA section content and atom distribution."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import create_engine, text

from config import get_settings

settings = get_settings()
engine = create_engine(settings.database_url)

with engine.connect() as conn:
    # Check sections with content
    result = conn.execute(
        text("""
        SELECT section_id, title,
               COALESCE(LENGTH(content), 0) as content_len,
               COALESCE(LENGTH(key_terms), 0) as terms_len
        FROM ccna_sections
        ORDER BY content_len DESC
        LIMIT 15
    """)
    )
    print("=== TOP SECTIONS BY CONTENT LENGTH ===")
    for row in result:
        print(
            f"  {row.section_id}: {row.title[:40]:40} content={row.content_len:6} terms={row.terms_len}"
        )

    # Check how many sections have content
    result = conn.execute(
        text("""
        SELECT
            COUNT(*) as total,
            COUNT(*) FILTER (WHERE content IS NOT NULL AND LENGTH(content) > 100) as with_content,
            COUNT(*) FILTER (WHERE key_terms IS NOT NULL) as with_terms
        FROM ccna_sections
    """)
    )
    row = result.fetchone()
    print("\n=== SECTION COVERAGE ===")
    print(f"  Total sections: {row.total}")
    print(f"  With content (>100 chars): {row.with_content}")
    print(f"  With key terms: {row.with_terms}")

    # Check atom distribution per section
    result = conn.execute(
        text("""
        SELECT
            cs.section_id,
            cs.title,
            COUNT(*) FILTER (WHERE ca.atom_type = 'flashcard') as flashcards,
            COUNT(*) FILTER (WHERE ca.atom_type = 'true_false') as tf,
            COUNT(*) FILTER (WHERE ca.atom_type = 'cloze') as cloze,
            COUNT(*) FILTER (WHERE ca.atom_type = 'mcq') as mcq,
            COUNT(*) as total
        FROM ccna_sections cs
        LEFT JOIN clean_atoms ca ON cs.section_id = ca.ccna_section_id
        GROUP BY cs.section_id, cs.title
        HAVING COUNT(*) > 0
        ORDER BY COUNT(*) DESC
        LIMIT 10
    """)
    )
    print("\n=== TOP SECTIONS BY ATOM COUNT ===")
    for row in result:
        print(
            f"  {row.section_id}: FC={row.flashcards} TF={row.tf} CL={row.cloze} MCQ={row.mcq} Total={row.total}"
        )
