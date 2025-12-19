"""
Import atoms from cortex_master.json into the learning_atoms database.
"""
import json
import uuid
from pathlib import Path
from datetime import datetime

from sqlalchemy import text
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.db.database import engine


def main():
    # Load JSON deck
    deck_file = Path("outputs/cortex_master.json")
    with open(deck_file, "r", encoding="utf-8") as f:
        deck = json.load(f)

    json_atoms = deck.get("atoms", [])
    print(f"JSON deck has {len(json_atoms)} atoms")

    # Get existing card_ids from database
    with engine.connect() as conn:
        result = conn.execute(text("SELECT card_id FROM learning_atoms"))
        existing_ids = {row.card_id for row in result}
        print(f"Database has {len(existing_ids)} existing atoms")

    # Find atoms to import (not already in DB)
    to_import = [a for a in json_atoms if a.get("card_id") not in existing_ids]
    print(f"Atoms to import: {len(to_import)}")

    if not to_import:
        print("Nothing to import!")
        return

    # Import new atoms
    imported = 0
    skipped = 0

    with engine.begin() as conn:
        for atom in to_import:
            try:
                card_id = atom.get("card_id", f"IMP-{uuid.uuid4().hex[:8].upper()}")
                atom_type = atom.get("atom_type", "flashcard")
                front = atom.get("front", "")
                back = atom.get("back", "")

                if not front:
                    skipped += 1
                    continue

                # Determine section_id from card_id if possible
                section_id = None
                cid = card_id
                if cid.startswith(("2.", "3.", "4.", "5.", "6.", "7.", "8.", "9.", "10.", "11.", "12.", "13.", "14.", "15.")):
                    parts = cid.split("-")
                    if parts:
                        section_id = parts[0]

                # Default section if none found
                if not section_id:
                    section_id = "1.1"

                # Insert into database
                conn.execute(
                    text("""
                        INSERT INTO learning_atoms (
                            id, card_id, atom_type, front, back,
                            ccna_section_id, source, quality_score, created_at
                        ) VALUES (
                            :id, :card_id, :atom_type, :front, :back,
                            :section_id, :source, :quality_score, :created_at
                        )
                    """),
                    {
                        "id": str(uuid.uuid4()),
                        "card_id": card_id,
                        "atom_type": atom_type,
                        "front": front,
                        "back": back if isinstance(back, str) else json.dumps(back),
                        "section_id": section_id,
                        "source": "json_import",
                        "quality_score": atom.get("quality_score", 0.85),
                        "created_at": datetime.now(),
                    }
                )
                imported += 1

            except Exception as e:
                print(f"  Error importing {atom.get('card_id', 'unknown')}: {e}")
                skipped += 1

    print(f"\nImported: {imported}")
    print(f"Skipped: {skipped}")

    # Verify
    with engine.connect() as conn:
        result = conn.execute(text("SELECT atom_type, COUNT(*) as cnt FROM learning_atoms GROUP BY atom_type ORDER BY cnt DESC"))
        print("\nNew database breakdown:")
        for row in result:
            print(f"  {row.atom_type}: {row.cnt}")

        total = conn.execute(text("SELECT COUNT(*) FROM learning_atoms")).scalar()
        print(f"\nTotal atoms in database: {total}")


if __name__ == "__main__":
    main()
