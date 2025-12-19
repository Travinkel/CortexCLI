"""
Fix NULL quality_score atoms.

Sets default quality scores for atoms that have NULL values.
Uses conservative defaults based on atom type.
"""

import sys
from pathlib import Path

from sqlalchemy import text

# Path setup
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.db.database import get_db

# Default quality scores by atom type
# Conservative defaults - these atoms haven't been validated
DEFAULT_QUALITY_SCORES = {
    "flashcard": 0.75,   # Below threshold (0.85) - won't sync to Anki
    "cloze": 0.75,       # Below threshold (0.80) - won't sync to Anki
    "mcq": 0.75,         # Default for quiz atoms
    "true_false": 0.75,  # Default for quiz atoms
    "parsons": 0.80,     # Slightly higher - harder to generate bad parsons
    "matching": 0.75,    # Default for quiz atoms
    "numeric": 0.75,     # Default for quiz atoms
}


def main():
    """Fix NULL quality_score atoms."""
    print("=" * 60)
    print("FIX NULL QUALITY SCORES")
    print("=" * 60)

    db = next(get_db())

    # Check current NULL counts
    print("\n[1] CURRENT NULL COUNTS BY TYPE")
    print("-" * 50)
    result = db.execute(text("""
        SELECT atom_type, COUNT(*) as cnt
        FROM learning_atoms
        WHERE quality_score IS NULL
        GROUP BY atom_type
        ORDER BY cnt DESC
    """)).fetchall()

    total_null = 0
    for row in result:
        print(f"  {row.atom_type}: {row.cnt}")
        total_null += row.cnt

    if total_null == 0:
        print("\n[OK] No NULL quality scores found!")
        return 0

    print(f"\n  Total: {total_null} atoms with NULL quality")

    # Apply defaults
    print("\n[2] APPLYING DEFAULT QUALITY SCORES")
    print("-" * 50)

    updated_total = 0
    for atom_type, default_score in DEFAULT_QUALITY_SCORES.items():
        result = db.execute(text("""
            UPDATE learning_atoms
            SET quality_score = :score
            WHERE atom_type = :type AND quality_score IS NULL
        """), {"score": default_score, "type": atom_type})
        count = result.rowcount
        if count > 0:
            print(f"  {atom_type}: {count} atoms set to {default_score}")
            updated_total += count

    db.commit()

    # Verify
    print("\n[3] VERIFICATION")
    print("-" * 50)
    result = db.execute(text("""
        SELECT COUNT(*) as cnt FROM learning_atoms WHERE quality_score IS NULL
    """)).fetchone()

    remaining = result.cnt
    print(f"  Updated: {updated_total} atoms")
    print(f"  Remaining NULL: {remaining} atoms")

    if remaining == 0:
        print("\n[SUCCESS] All NULL quality scores fixed!")
        return 0
    else:
        print(f"\n[WARNING] {remaining} atoms still have NULL quality")
        return 1


if __name__ == "__main__":
    sys.exit(main())
