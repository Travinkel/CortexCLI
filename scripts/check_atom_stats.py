#!/usr/bin/env python3
"""Quick atom stats check."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import create_engine, text
from config import get_settings

settings = get_settings()
engine = create_engine(settings.database_url)

with engine.connect() as conn:
    # Total by type
    result = conn.execute(text('''
        SELECT atom_type, COUNT(*) as count
        FROM clean_atoms
        GROUP BY atom_type
        ORDER BY count DESC
    '''))
    print('\n=== ATOM DISTRIBUTION ===')
    total = 0
    for row in result:
        print(f'  {row.atom_type:15} {row.count:5}')
        total += row.count
    print(f'  {"TOTAL":15} {total:5}')

    # Flashcards by quality score
    result = conn.execute(text('''
        SELECT
            CASE
                WHEN quality_score >= 80 THEN 'A (80+)'
                WHEN quality_score >= 60 THEN 'B (60-79)'
                WHEN quality_score >= 40 THEN 'C (40-59)'
                ELSE 'D (<40)'
            END as grade,
            COUNT(*) as count
        FROM clean_atoms
        WHERE atom_type = 'flashcard'
        GROUP BY 1
        ORDER BY 1
    '''))
    print('\n=== FLASHCARD QUALITY GRADES ===')
    for row in result:
        print(f'  {row.grade:15} {row.count:5}')

    # High quality atoms (quality_score >= 70, not flagged)
    result = conn.execute(text('''
        SELECT COUNT(*)
        FROM clean_atoms
        WHERE atom_type = 'flashcard'
          AND quality_score >= 70
          AND (source IS NULL OR source NOT LIKE '%flagged%')
    '''))
    good = result.scalar()
    print(f'\n=== STUDY-READY FLASHCARDS ===')
    print(f'  High quality (>=70, not flagged): {good}')

    # Cloze count
    result = conn.execute(text("SELECT COUNT(*) FROM clean_atoms WHERE atom_type = 'cloze'"))
    cloze = result.scalar()
    print(f'  Cloze atoms: {cloze}')

    # True/False count
    result = conn.execute(text("SELECT COUNT(*) FROM clean_atoms WHERE atom_type = 'true_false'"))
    tf = result.scalar()
    print(f'  True/False atoms: {tf}')

    # MCQ count
    result = conn.execute(text("SELECT COUNT(*) FROM clean_atoms WHERE atom_type = 'mcq'"))
    mcq = result.scalar()
    print(f'  MCQ atoms: {mcq}')

    print(f'\n=== TOTAL STUDY-READY ===')
    print(f'  {good + cloze + tf + mcq} atoms ready for study')
