"""Validate all Parsons atoms have proper step sequences."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from sqlalchemy import text
from src.db.database import engine


def validate_parsons():
    """Check Parsons atom format validity."""
    with engine.connect() as conn:
        # Total Parsons
        total = conn.execute(text(
            "SELECT COUNT(*) FROM learning_atoms WHERE atom_type = 'parsons'"
        )).scalar()

        # Check for atoms with proper format (arrow separators)
        valid = conn.execute(text("""
            SELECT COUNT(*) FROM learning_atoms
            WHERE atom_type = 'parsons'
            AND (back LIKE '% -> %' OR back LIKE '%→%')
        """)).scalar()

        # Check for atoms still with prose (no separators)
        invalid = conn.execute(text("""
            SELECT card_id, back FROM learning_atoms
            WHERE atom_type = 'parsons'
            AND back NOT LIKE '% -> %'
            AND back NOT LIKE '%→%'
        """)).fetchall()

        # Check step counts for valid atoms
        step_counts = conn.execute(text("""
            SELECT card_id, back,
                   LENGTH(back) - LENGTH(REPLACE(back, ' -> ', '')) + 1 as step_count
            FROM learning_atoms
            WHERE atom_type = 'parsons'
            AND back LIKE '% -> %'
            ORDER BY step_count DESC
            LIMIT 5
        """)).fetchall()

        # Check stats preservation on atoms with reviews
        reviewed_atoms = conn.execute(text("""
            SELECT card_id, anki_review_count, anki_lapses, back
            FROM learning_atoms
            WHERE atom_type = 'parsons'
            AND anki_review_count > 0
            LIMIT 5
        """)).fetchall()

        print("=" * 60)
        print("PARSONS VALIDATION REPORT")
        print("=" * 60)
        print(f"\nTotal Parsons atoms: {total}")
        print(f"Valid (with -> separators): {valid}")
        print(f"Invalid (prose format): {len(invalid)}")
        print(f"Validity rate: {valid/total*100:.1f}%")

        if invalid:
            print(f"\nSample invalid atoms ({min(5, len(invalid))} of {len(invalid)}):")
            for atom in invalid[:5]:
                print(f"  - {atom[0]}: {atom[1][:50]}...")

        if step_counts:
            print(f"\nStep count distribution (highest):")
            for atom in step_counts:
                print(f"  - {atom[0]}: {atom[2]} steps")

        if reviewed_atoms:
            print(f"\nReviewed atoms (stats preserved):")
            for atom in reviewed_atoms:
                print(f"  - {atom[0]}: {atom[1]} reviews, {atom[2]} lapses")
                print(f"    Back: {atom[3][:60]}...")

        return {
            "total": total,
            "valid": valid,
            "invalid": len(invalid),
            "validity_rate": valid / total * 100 if total > 0 else 0
        }


if __name__ == "__main__":
    validate_parsons()
