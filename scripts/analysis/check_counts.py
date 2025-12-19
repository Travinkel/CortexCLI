"""Quick script to verify atom counts."""

import sys

from sqlalchemy import create_engine, text

sys.path.insert(0, ".")
from config import get_settings

settings = get_settings()
engine = create_engine(settings.database_url)
with engine.connect() as conn:
    # First show columns
    result = conn.execute(
        text(
            "SELECT column_name FROM information_schema.columns WHERE table_name = 'clean_atoms' ORDER BY ordinal_position"
        )
    )
    print("=== COLUMNS IN clean_atoms ===")
    for row in result:
        print(f"  {row[0]}")
    print()
    # Total counts by atom type
    result = conn.execute(
        text("""
        SELECT atom_type, COUNT(*) as count
        FROM clean_atoms
        WHERE front IS NOT NULL AND front != ''
        GROUP BY atom_type
        ORDER BY count DESC
    """)
    )
    print("=== TOTAL COUNTS BY ATOM TYPE ===")
    for row in result:
        print(f"  {row.atom_type}: {row.count}")

    # Module breakdown for Anki types
    result = conn.execute(
        text("""
        SELECT cs.module_number, ca.atom_type, COUNT(*) as count
        FROM clean_atoms ca
        JOIN ccna_sections cs ON ca.ccna_section_id = cs.section_id
        WHERE ca.atom_type IN ('flashcard', 'cloze')
          AND ca.front IS NOT NULL AND ca.front != ''
        GROUP BY cs.module_number, ca.atom_type
        ORDER BY cs.module_number, ca.atom_type
    """)
    )
    print()
    print("=== ANKI CARDS PER MODULE ===")
    totals = {"flashcard": 0, "cloze": 0}
    current_module = None
    for row in result:
        if current_module != row.module_number:
            current_module = row.module_number
            print(f"  Module {row.module_number}:")
        print(f"    {row.atom_type}: {row.count}")
        totals[row.atom_type] += row.count
    print()
    print("=== TOTALS ===")
    print(f"  Flashcards: {totals['flashcard']}")
    print(f"  Cloze: {totals['cloze']}")
    print(f"  Combined Anki: {totals['flashcard'] + totals['cloze']}")
