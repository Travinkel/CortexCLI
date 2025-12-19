"""Merge all subsection atoms into cortex_master.json."""
import json
import uuid
from pathlib import Path

def main():
    # Load subsection atoms
    atoms_file = Path("outputs/generated_atoms/all_subsections_atoms.json")
    if not atoms_file.exists():
        print("ERROR: all_subsections_atoms.json not found")
        return

    with open(atoms_file, "r", encoding="utf-8") as f:
        new_atoms = json.load(f)

    print(f"Loaded {len(new_atoms)} subsection atoms")

    # Load existing deck
    deck_file = Path("outputs/cortex_master.json")
    if not deck_file.exists():
        print("ERROR: cortex_master.json not found")
        return

    with open(deck_file, "r", encoding="utf-8") as f:
        deck = json.load(f)

    existing_atoms = deck.get("atoms", [])
    print(f"Existing deck has {len(existing_atoms)} atoms")

    existing_ids = {a.get("card_id") for a in existing_atoms}
    added = 0

    for atom in new_atoms:
        card_id = atom.get("card_id", f"SUB-{uuid.uuid4().hex[:8].upper()}")

        # Make unique if duplicate
        if card_id in existing_ids:
            card_id = f"{card_id}-{uuid.uuid4().hex[:4].upper()}"

        atom_type = atom.get("atom_type", "flashcard")

        new_atom = {
            "id": str(uuid.uuid4()),
            "card_id": card_id,
            "atom_type": atom_type,
            "front": atom.get("front", "") or atom.get("scenario", ""),
            "quality_score": 0.85,
            "difficulty": atom.get("metadata", {}).get("difficulty", 3) if isinstance(atom.get("metadata"), dict) else 3,
            "knowledge_type": atom.get("metadata", {}).get("knowledge_type", "conceptual") if isinstance(atom.get("metadata"), dict) else "conceptual",
            "source_refs": atom.get("source_refs", []),
            "media_type": None,
            "media_code": None,
        }

        if atom_type == "flashcard":
            new_atom["back"] = atom.get("back", "")
            new_atom["content_json"] = {"tags": atom.get("tags", [])}

        elif atom_type == "numeric":
            new_atom["back"] = atom.get("back", "")
            new_atom["content_json"] = {
                "tags": atom.get("tags", []),
                "calculation_type": atom.get("calculation_type", "")
            }

        elif atom_type == "parsons":
            new_atom["front"] = atom.get("scenario", atom.get("front", ""))
            new_atom["back"] = atom.get("explanation", "")
            new_atom["content_json"] = {
                "correct_sequence": atom.get("correct_sequence", []),
                "distractors": atom.get("distractors", [])
            }

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

    deck["atoms"] = existing_atoms

    with open(deck_file, "w", encoding="utf-8") as f:
        json.dump(deck, f, indent=2, ensure_ascii=False)

    print(f"\nAdded {added} new atoms from all subsections")
    print(f"Total deck size: {len(existing_atoms)} atoms")

    # Breakdown
    by_type = {}
    for a in existing_atoms:
        t = a.get("atom_type", "unknown")
        by_type[t] = by_type.get(t, 0) + 1

    print("\nFinal deck breakdown:")
    for t, c in sorted(by_type.items()):
        print(f"  {t}: {c}")


if __name__ == "__main__":
    main()
