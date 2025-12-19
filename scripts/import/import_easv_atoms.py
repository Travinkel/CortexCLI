"""Import EASV course atoms into the database."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from sqlalchemy import text
from src.db.database import engine

DATA_FILE = Path(__file__).parent.parent.parent / "data" / "generated" / "easv_course_atoms.json"


def import_easv_atoms(dry_run: bool = False):
    """Import EASV course atoms."""
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        atoms = json.load(f)

    print(f"Importing {len(atoms)} EASV course atoms")

    imported = 0
    skipped = 0

    with engine.begin() as conn:
        for atom in atoms:
            # Check if exists
            exists = conn.execute(
                text("SELECT 1 FROM learning_atoms WHERE card_id = :card_id"),
                {"card_id": atom["card_id"]}
            ).fetchone()

            if exists:
                print(f"  SKIP {atom['card_id']} (exists)")
                skipped += 1
                continue

            # Prepare back field
            back = atom["back"]
            if isinstance(back, dict):
                back = json.dumps(back)

            # Build source from course + topic
            source = f"easv_{atom.get('course', 'unknown')}_{atom.get('topic', 'general')}"

            if dry_run:
                print(f"  [DRY] {atom['card_id']}: {atom['front'][:50]}...")
                continue

            conn.execute(
                text("""
                    INSERT INTO learning_atoms (
                        card_id, front, back, atom_type, source, created_at
                    ) VALUES (
                        :card_id, :front, :back, :atom_type, :source, NOW()
                    )
                """),
                {
                    "card_id": atom["card_id"],
                    "front": atom["front"],
                    "back": back,
                    "atom_type": atom["atom_type"],
                    "source": source.lower().replace(".", "_"),
                }
            )
            print(f"  OK {atom['card_id']}")
            imported += 1

    print(f"\nComplete: {imported} imported, {skipped} skipped")
    return imported, skipped


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    import_easv_atoms(dry_run=args.dry_run)
