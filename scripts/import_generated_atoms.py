"""
Import generated atoms into the database.
"""
import json
import sys
import uuid
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import text
from src.db.database import engine


def import_atoms():
    """Import generated atoms into learning_atoms table."""
    atoms_file = Path("outputs/generated_atoms/all_generated_atoms.json")

    if not atoms_file.exists():
        print(f"No atoms file found at {atoms_file}")
        return

    with open(atoms_file, "r", encoding="utf-8") as f:
        atoms = json.load(f)

    print(f"Importing {len(atoms)} atoms...")
    imported = 0
    skipped = 0

    with engine.begin() as conn:
        for atom in atoms:
            try:
                # Generate unique card_id if not present
                card_id = atom.get("card_id") or f"GEN-{uuid.uuid4().hex[:8].upper()}"

                # Determine front/back based on atom type
                atom_type = atom.get("atom_type", "flashcard")

                if atom_type == "parsons":
                    front = atom.get("front", "")
                    # For parsons, back is the explanation
                    back = atom.get("explanation", "")
                    # Store sequence in content_json
                    content_json = json.dumps({
                        "correct_sequence": atom.get("correct_sequence", []),
                        "distractors": atom.get("distractors", [])
                    })
                elif atom_type == "matching":
                    front = atom.get("front", "")
                    # For matching, format pairs as back
                    pairs = atom.get("pairs", [])
                    back = "\n".join([f"{p['term']}: {p['definition']}" for p in pairs])
                    content_json = json.dumps({"pairs": pairs})
                else:
                    front = atom.get("front", "")
                    back = atom.get("back", "")
                    content_json = json.dumps(atom.get("metadata", {}))

                if not front:
                    skipped += 1
                    continue

                # Get section_id from source_refs or generate from module
                section_id = None
                if "source_refs" in atom and atom["source_refs"]:
                    section_id = atom["source_refs"][0].get("section_id")
                if not section_id:
                    section_id = f"{atom.get('module', 0)}.1"

                # Check if already exists
                existing = conn.execute(
                    text("SELECT 1 FROM learning_atoms WHERE card_id = :card_id"),
                    {"card_id": card_id}
                ).fetchone()

                if existing:
                    skipped += 1
                    continue

                # Insert
                conn.execute(
                    text("""
                        INSERT INTO learning_atoms (
                            card_id, atom_type, front, back,
                            ccna_section_id, source, content_json,
                            quality_score, created_at
                        ) VALUES (
                            :card_id, :atom_type, :front, :back,
                            :section_id, :source, :content_json,
                            :quality_score, :created_at
                        )
                    """),
                    {
                        "card_id": card_id,
                        "atom_type": atom_type,
                        "front": front,
                        "back": back,
                        "section_id": section_id,
                        "source": "targeted_generation",
                        "content_json": content_json,
                        "quality_score": 0.8,
                        "created_at": datetime.now()
                    }
                )
                imported += 1

            except Exception as e:
                print(f"  Error importing {atom.get('card_id', 'unknown')}: {e}")
                skipped += 1

    print(f"\nImported: {imported}")
    print(f"Skipped: {skipped}")
    return imported


def update_deck():
    """Re-export deck after import."""
    import subprocess
    result = subprocess.run(
        [sys.executable, "-X", "utf8", "scripts/db_to_deck.py"],
        capture_output=True,
        text=True
    )
    print(result.stdout)
    if result.stderr:
        print(result.stderr)


if __name__ == "__main__":
    count = import_atoms()
    if count and count > 0:
        print("\nUpdating CLI deck...")
        update_deck()
