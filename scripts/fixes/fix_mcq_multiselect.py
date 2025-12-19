"""
Update existing MCQ atoms to add multi_select flag based on question text.

Detects "Choose two", "Choose three", etc. in the front field and updates
the back JSON to include multi_select and required_count.
"""
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from sqlalchemy import text
from src.db.database import engine


def detect_multi_select(question_text: str) -> tuple[bool, int]:
    """Detect if a question requires multiple answers."""
    q_lower = question_text.lower()

    patterns = [
        (r'choose\s+two', 2),
        (r'choose\s+three', 3),
        (r'choose\s+four', 4),
        (r'select\s+two', 2),
        (r'select\s+three', 3),
        (r'\(choose\s+2\)', 2),
        (r'\(choose\s+3\)', 3),
        (r'two\s+(?:answers|options|choices)', 2),
        (r'three\s+(?:answers|options|choices)', 3),
    ]

    for pattern, count in patterns:
        if re.search(pattern, q_lower):
            return True, count

    return False, 1


def fix_multiselect(dry_run: bool = False):
    """Update MCQ atoms with multi_select flag."""
    with engine.begin() as conn:
        # Get all MCQ atoms
        result = conn.execute(text("""
            SELECT id, card_id, front, back
            FROM learning_atoms
            WHERE atom_type = 'mcq'
        """))
        mcqs = result.fetchall()

        print(f"Found {len(mcqs)} MCQ atoms")

        updated = 0
        already_correct = 0
        errors = 0

        for row in mcqs:
            atom_id, card_id, front, back = row

            # Detect multi-select from question text
            is_multi, required_count = detect_multi_select(front or "")

            if not is_multi:
                continue  # Skip single-select questions

            # Parse existing back JSON
            try:
                back_data = json.loads(back)
            except (json.JSONDecodeError, TypeError):
                # Not JSON format, skip
                continue

            # Check if already has multi_select flag
            if back_data.get("multi_select") == True and back_data.get("required_count") == required_count:
                already_correct += 1
                continue

            # Update the back data
            back_data["multi_select"] = True
            back_data["required_count"] = required_count

            # If correct is a single int, we may need to convert to list
            # But we don't know the other correct answers, so leave it
            # The needs_review flag should already be set for these

            new_back = json.dumps(back_data)

            print(f"[UPDATE] {card_id}: multi_select=True, required_count={required_count}")
            print(f"         Question: {front[:60]}...")

            if not dry_run:
                conn.execute(
                    text("UPDATE learning_atoms SET back = :back WHERE id = :id"),
                    {"back": new_back, "id": atom_id}
                )
                updated += 1

        print(f"\n{'='*60}")
        print(f"Updated: {updated}")
        print(f"Already correct: {already_correct}")
        print(f"Errors: {errors}")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    fix_multiselect(dry_run=args.dry_run)
