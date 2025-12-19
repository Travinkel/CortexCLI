"""Merge Module 3 atoms into cortex_master.json."""
import json
import uuid
from pathlib import Path

def main():
    # Load Module 3 atoms
    module3_file = Path("outputs/generated_atoms/module3_atoms.json")
    if not module3_file.exists():
        print("ERROR: module3_atoms.json not found")
        return

    with open(module3_file, "r", encoding="utf-8") as f:
        module3_atoms = json.load(f)

    print(f"Loaded {len(module3_atoms)} Module 3 atoms")

    # Load existing deck
    deck_file = Path("outputs/cortex_master.json")
    if not deck_file.exists():
        print("ERROR: cortex_master.json not found")
        return

    with open(deck_file, "r", encoding="utf-8") as f:
        deck = json.load(f)

    existing_atoms = deck.get("atoms", [])
    print(f"Existing deck has {len(existing_atoms)} atoms")

    # Get existing card_ids to avoid duplicates
    existing_ids = {a.get("card_id") for a in existing_atoms}

    # Transform and add new atoms
    added = 0
    for atom in module3_atoms:
        card_id = atom.get("card_id", f"GEN-{uuid.uuid4().hex[:8].upper()}")

        if card_id in existing_ids:
            print(f"  Skipping duplicate: {card_id}")
            continue

        atom_type = atom.get("atom_type", "flashcard")

        # Build new atom in deck format
        new_atom = {
            "id": str(uuid.uuid4()),
            "card_id": card_id,
            "atom_type": atom_type,
            "front": atom.get("front", ""),
            "quality_score": 0.85,  # New atoms get slightly higher score
            "difficulty": atom.get("metadata", {}).get("difficulty", 2),
            "knowledge_type": atom.get("metadata", {}).get("knowledge_type", "conceptual"),
            "source_refs": atom.get("source_refs", []),
            "media_type": None,
            "media_code": None,
        }

        # Handle different atom types
        if atom_type == "flashcard":
            new_atom["back"] = atom.get("back", "")
            new_atom["content_json"] = {"tags": atom.get("tags", [])}

        elif atom_type == "mcq":
            correct = atom.get("correct_answer", "")
            distractors = atom.get("distractors", [])
            options = [correct] + distractors
            new_atom["back"] = json.dumps({
                "options": options,
                "correct": 0,
                "explanation": atom.get("explanation", "")
            })
            new_atom["content_json"] = {
                "options": options,
                "correct": 0,
                "explanation": atom.get("explanation", "")
            }

        elif atom_type == "matching":
            pairs = atom.get("pairs", [])
            new_atom["back"] = json.dumps({"pairs": pairs})
            new_atom["content_json"] = {"pairs": pairs}

        existing_atoms.append(new_atom)
        existing_ids.add(card_id)
        added += 1

    # Update deck
    deck["atoms"] = existing_atoms

    # Save
    with open(deck_file, "w", encoding="utf-8") as f:
        json.dump(deck, f, indent=2, ensure_ascii=False)

    print(f"\nAdded {added} new atoms")
    print(f"Total deck size: {len(existing_atoms)} atoms")

    # Count by type
    by_type = {}
    for a in existing_atoms:
        t = a.get("atom_type", "unknown")
        by_type[t] = by_type.get(t, 0) + 1

    print("\nDeck breakdown by type:")
    for t, c in sorted(by_type.items()):
        print(f"  {t}: {c}")


if __name__ == "__main__":
    main()
