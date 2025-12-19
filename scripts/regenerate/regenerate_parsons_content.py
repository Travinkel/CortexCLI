"""
Regenerate Parsons atom back field content while preserving card_id and all stats.

Uses Gemini to convert prose descriptions to proper step sequences.
Preserves: card_id, anki_note_id, anki_card_id, anki_ease_factor, anki_interval_days,
           anki_review_count, anki_lapses, stability_days, retrievability, etc.
"""
import asyncio
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import google.generativeai as genai
from sqlalchemy import text
from config import get_settings
from src.db.database import engine

CONVERSION_PROMPT = """Convert this Cisco IOS Parsons problem description into a proper step sequence.

Current prose description:
{prose}

Scenario context:
{scenario}

Convert to a step sequence using this EXACT format:
step1 -> step2 -> step3 -> step4

Rules:
1. Use actual CLI commands (enable, configure terminal, interface g0/0, ip address, etc.)
2. Each step should be a single command or mode transition
3. Use " -> " (space-arrow-space) as the separator
4. Include mode transitions (enable, configure terminal, etc.) at the start
5. End with appropriate command (end, exit, copy run start, etc.) if needed
6. Use 3-6 steps total
7. Commands should be in exact Cisco IOS syntax

Examples:
- "enable -> configure terminal -> hostname R1 -> end"
- "enable -> configure terminal -> interface g0/0/0 -> ip address 192.168.1.1 255.255.255.0 -> no shutdown"
- "enable -> configure terminal -> line console 0 -> password cisco -> login"

Return ONLY the step sequence, nothing else. No explanation, just the commands with " -> " separators.
"""


async def regenerate_single(model, atom_id: str, card_id: str, front: str, back: str) -> tuple[bool, str]:
    """Regenerate a single Parsons atom."""
    try:
        prompt = CONVERSION_PROMPT.format(prose=back, scenario=front)
        response = await model.generate_content_async(prompt)
        new_back = response.text.strip()

        # Validate format
        if " -> " not in new_back:
            return False, f"Invalid format: no ' -> ' separator found"

        # Validate step count
        steps = new_back.split(" -> ")
        if len(steps) < 2:
            return False, f"Too few steps: {len(steps)}"
        if len(steps) > 8:
            return False, f"Too many steps: {len(steps)}"

        return True, new_back
    except Exception as e:
        return False, str(e)


async def regenerate_parsons(dry_run: bool = False, limit: int = None):
    """
    Regenerate all Parsons atoms with prose back fields.

    Args:
        dry_run: If True, don't actually update database
        limit: Max atoms to process (for testing)
    """
    settings = get_settings()
    genai.configure(api_key=settings.gemini_api_key)
    model = genai.GenerativeModel("gemini-2.0-flash-exp")

    with engine.begin() as conn:
        # Fetch all Parsons atoms with prose backs
        query = """
            SELECT id, card_id, front, back, ccna_section_id,
                   anki_review_count, anki_lapses
            FROM learning_atoms
            WHERE atom_type = 'parsons'
            AND back NOT LIKE '%->%'
            AND back NOT LIKE '%→%'
        """
        if limit:
            query += f" LIMIT {limit}"

        result = conn.execute(text(query))
        parsons_atoms = result.fetchall()

        print(f"Found {len(parsons_atoms)} Parsons atoms needing regeneration")
        if dry_run:
            print("DRY RUN - no changes will be made")
        print()

        updated = 0
        errors = []
        skipped = 0

        for i, atom in enumerate(parsons_atoms):
            atom_id = str(atom[0])
            card_id = atom[1]
            front = atom[2]
            back = atom[3]
            review_count = atom[5] or 0
            lapses = atom[6] or 0

            # Generate proper step sequence
            success, result_text = await regenerate_single(model, atom_id, card_id, front, back)

            if not success:
                errors.append(f"{card_id}: {result_text}")
                print(f"[{i+1}/{len(parsons_atoms)}] ERROR {card_id}: {result_text}")
                continue

            # Show what would be updated
            print(f"[{i+1}/{len(parsons_atoms)}] {card_id}")
            print(f"    Old: {back[:60]}...")
            print(f"    New: {result_text}")
            if review_count > 0 or lapses > 0:
                print(f"    Stats preserved: {review_count} reviews, {lapses} lapses")

            if not dry_run:
                # Update back field ONLY - preserve all stats
                conn.execute(
                    text("""
                        UPDATE learning_atoms
                        SET back = :new_back, updated_at = NOW()
                        WHERE id = :id
                    """),
                    {"new_back": result_text, "id": atom_id}
                )
                updated += 1
            else:
                skipped += 1

            # Rate limit - Gemini allows 10 requests/minute
            await asyncio.sleep(7)  # ~8.5 requests/minute to stay under limit

        print()
        print("=" * 60)
        print(f"Complete: {updated} updated, {skipped} skipped (dry run), {len(errors)} errors")

        if errors:
            print("\nErrors:")
            for err in errors[:10]:
                print(f"  - {err}")
            if len(errors) > 10:
                print(f"  ... and {len(errors) - 10} more")

        return {"updated": updated, "skipped": skipped, "errors": errors}


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Regenerate Parsons atom back fields")
    parser.add_argument("--dry-run", action="store_true", help="Don't actually update database")
    parser.add_argument("--limit", type=int, help="Max atoms to process")
    args = parser.parse_args()

    asyncio.run(regenerate_parsons(dry_run=args.dry_run, limit=args.limit))


if __name__ == "__main__":
    main()
