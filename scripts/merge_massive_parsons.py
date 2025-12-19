"""Merge 150 Parsons atoms into cortex_master.json."""
import json
import uuid
from pathlib import Path

def main():
    atoms_file = Path("outputs/generated_atoms/massive_parsons.json")
    if not atoms_file.exists():
        print("ERROR: massive_parsons.json not found")
        return

    with open(atoms_file, "r", encoding="utf-8") as f:
        new_atoms = json.load(f)

    print(f"Loaded {len(new_atoms)} Parsons atoms")

    deck_file = Path("outputs/cortex_master.json")
    with open(deck_file, "r", encoding="utf-8") as f:
        deck = json.load(f)

    existing_atoms = deck.get("atoms", [])
    print(f"Existing deck has {len(existing_atoms)} atoms")

    existing_ids = {a.get("card_id") for a in existing_atoms}
    added = 0

    for atom in new_atoms:
        card_id = atom.get("card_id", f"PAR-{uuid.uuid4().hex[:8].upper()}")

        if card_id in existing_ids:
            card_id = f"{card_id}-{uuid.uuid4().hex[:4].upper()}"

        new_atom = {
            "id": str(uuid.uuid4()),
            "card_id": card_id,
            "atom_type": "parsons",
            "front": atom.get("scenario", atom.get("front", "")),
            "back": atom.get("explanation", ""),
            "quality_score": 0.9,
            "difficulty": 3,
            "knowledge_type": "procedural",
            "source_refs": [],
            "content_json": {
                "correct_sequence": atom.get("correct_sequence", []),
                "distractors": atom.get("distractors", [])
            },
            "media_type": None,
            "media_code": None,
        }

        existing_atoms.append(new_atom)
        existing_ids.add(card_id)
        added += 1

    deck["atoms"] = existing_atoms

    with open(deck_file, "w", encoding="utf-8") as f:
        json.dump(deck, f, indent=2, ensure_ascii=False)

    print(f"\nAdded {added} new Parsons atoms")
    print(f"Total deck size: {len(existing_atoms)} atoms")

    parsons_count = sum(1 for a in existing_atoms if a.get("atom_type") == "parsons")
    print(f"\nTOTAL PARSONS ATOMS: {parsons_count}")

    by_type = {}
    for a in existing_atoms:
        t = a.get("atom_type", "unknown")
        by_type[t] = by_type.get(t, 0) + 1

    print("\nFinal breakdown:")
    for t, c in sorted(by_type.items()):
        print(f"  {t}: {c}")


if __name__ == "__main__":
    main()
