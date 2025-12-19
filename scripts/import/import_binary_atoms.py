"""
Import generated binary training atoms into the database.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from sqlalchemy import text
from src.db.database import engine

DATA_DIR = Path(__file__).parent.parent.parent / "data" / "generated"


def import_atoms(json_file: Path, dry_run: bool = False):
    """Import atoms from JSON file into database."""
    with open(json_file, "r", encoding="utf-8") as f:
        atoms = json.load(f)

    print(f"Importing {len(atoms)} atoms from {json_file.name}")

    imported = 0
    skipped = 0

    with engine.begin() as conn:
        for atom in atoms:
            # Check if atom already exists
            exists = conn.execute(
                text("SELECT 1 FROM learning_atoms WHERE card_id = :card_id"),
                {"card_id": atom["card_id"]}
            ).fetchone()

            if exists:
                print(f"  SKIP {atom['card_id']} (already exists)")
                skipped += 1
                continue

            if dry_run:
                print(f"  [DRY] Would import {atom['card_id']}")
                continue

            # Handle back field - may need JSON encoding for MCQ
            back_val = atom["back"]
            if atom["atom_type"] == "mcq" and isinstance(back_val, str):
                # Already JSON encoded
                pass
            elif atom["atom_type"] == "mcq" and isinstance(back_val, dict):
                back_val = json.dumps(back_val)

            # Insert atom
            conn.execute(
                text("""
                    INSERT INTO learning_atoms (
                        card_id, front, back, atom_type, ccna_section_id,
                        source, created_at
                    ) VALUES (
                        :card_id, :front, :back, :atom_type, :section_id,
                        :source, NOW()
                    )
                """),
                {
                    "card_id": atom["card_id"],
                    "front": atom["front"],
                    "back": back_val,
                    "atom_type": atom["atom_type"],
                    "section_id": atom.get("ccna_section_id"),
                    "source": atom.get("source", "generated"),
                }
            )
            print(f"  OK {atom['card_id']}")
            imported += 1

    print(f"\nComplete: {imported} imported, {skipped} skipped")
    return imported, skipped


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Import binary training atoms")
    parser.add_argument("--dry-run", action="store_true", help="Don't actually import")
    args = parser.parse_args()

    plm_file = DATA_DIR / "binary_plm_drills.json"
    worked_file = DATA_DIR / "binary_worked_examples.json"

    total_imported = 0
    total_skipped = 0

    if plm_file.exists():
        i, s = import_atoms(plm_file, dry_run=args.dry_run)
        total_imported += i
        total_skipped += s

    if worked_file.exists():
        i, s = import_atoms(worked_file, dry_run=args.dry_run)
        total_imported += i
        total_skipped += s

    print(f"\n{'='*60}")
    print(f"TOTAL: {total_imported} imported, {total_skipped} skipped")


if __name__ == "__main__":
    main()
