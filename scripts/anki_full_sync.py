#!/usr/bin/env python3
"""
Anki Sync for Flashcard and Cloze atoms ONLY.

This script:
1. Syncs ONLY flashcard and cloze atoms to Anki (other types stay in NLS)
2. Creates hierarchical deck structure (CCNA::Module X::Section)
3. Pulls FSRS stats FROM Anki back to PostgreSQL
4. Supports full 6-field note structure with metadata

Learning Atom Philosophy:
- flashcard, cloze → Anki (FSRS scheduling)
- mcq, true_false, matching, parsons → NLS CLI (in-app quizzes)

Required Anki Note Fields (6):
1. Front - Question or cloze text
2. Back - Answer or explanation
3. Card ID - Unique identifier for sync
4. Tags - Space-separated tags
5. concept_id - UUID of concept
6. source - Origin (notion, module, etc.)
7. metadata_json - JSON blob with Bloom level, CLT load, etc.

Usage:
    python scripts/anki_full_sync.py [--dry-run] [--pull-only] [--push-only] [--delete-all]
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Optional

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import requests
from loguru import logger
from sqlalchemy import text

from config import get_settings
from src.db.database import session_scope
from src.cleaning.thresholds import (
    ANKI_MIN_QUALITY_SCORE,
    ANKI_MIN_FRONT_LENGTH,
    ANKI_MIN_BACK_LENGTH,
    ANKI_EXCLUDE_PATTERNS,
)

settings = get_settings()

ANKI_CONNECT_URL = settings.anki_connect_url

# Deck hierarchy for scalability:
#   CCNA (certification root)
#   └── ITN (Introduction to Networks - course 1 of 3)
#   └── SRWE (future: Switching, Routing, Wireless Essentials)
#   └── ENSA (future: Enterprise Networking, Security, Automation)
#
# Full path: CCNA::ITN::Module 1::Section Title
CERT_DECK = "CCNA"
COURSE_DECK = "ITN"  # Introduction to Networks
BASE_DECK = f"{CERT_DECK}::{COURSE_DECK}"

# Curriculum identifier for globally unique tags
# Format: <cert>-<course> e.g., ccna-itn, ccna-srwe, ccna-ensa
CURRICULUM_ID = "ccna-itn"

# Note types - different for flashcard vs cloze
FLASHCARD_NOTE_TYPE = "LearningOS-v2"
CLOZE_NOTE_TYPE = "LearningOS-v2 Cloze"

# ONLY these atom types go to Anki
ANKI_ATOM_TYPES = ("flashcard", "cloze")

# CCNA ITN Module Names (hardcoded for consistency)
# Per user's guidance: "hardcoding for CCNA is perfectly acceptable"
CCNA_ITN_MODULE_NAMES = {
    1: "Networking Today",
    2: "Basic Switch and End Device Configuration",
    3: "Protocols and Models",
    4: "Physical Layer",
    5: "Number Systems",
    6: "Data Link Layer",
    7: "Ethernet Switching",
    8: "Network Layer",
    9: "Address Resolution",
    10: "Basic Router Configuration",
    11: "IPv4 Addressing",
    12: "IPv6 Addressing",
    13: "ICMP",
    14: "Transport Layer",
    15: "Application Layer",
    16: "Network Security Fundamentals",
    17: "Build a Small Network",
}


def get_module_deck_name(module_num: int) -> str:
    """Get the deck name for a module number."""
    name = CCNA_ITN_MODULE_NAMES.get(module_num, f"Module {module_num}")
    return f"{BASE_DECK}::M{module_num:02d} {name}"


def anki_invoke(action: str, params: dict = None) -> dict:
    """Invoke AnkiConnect API."""
    payload = {"action": action, "version": 6}
    if params:
        payload["params"] = params

    try:
        response = requests.post(ANKI_CONNECT_URL, json=payload, timeout=30)
        result = response.json()
        if result.get("error"):
            raise Exception(result["error"])
        return result.get("result")
    except requests.exceptions.ConnectionError:
        logger.error("Cannot connect to Anki. Is Anki running with AnkiConnect?")
        raise


def ensure_deck_exists(deck_name: str) -> int:
    """Create deck if it doesn't exist, return deck ID."""
    try:
        deck_id = anki_invoke("createDeck", {"deck": deck_name})
        return deck_id
    except Exception as e:
        logger.warning(f"Could not create deck {deck_name}: {e}")
        return None


def create_decks_batch(deck_names: list) -> int:
    """
    Create multiple decks using AnkiConnect's multi action.

    This is much faster than creating decks one-by-one.
    Returns the number of decks created.
    """
    if not deck_names:
        return 0

    # Build multi-action payload
    actions = [
        {"action": "createDeck", "params": {"deck": name}}
        for name in deck_names
    ]

    try:
        results = anki_invoke("multi", {"actions": actions})
        return len([r for r in results if r is not None])
    except Exception as e:
        logger.warning(f"Batch deck creation failed: {e}, falling back to sequential")
        # Fall back to sequential
        created = 0
        for name in deck_names:
            if ensure_deck_exists(name):
                created += 1
        return created


def get_all_anki_notes() -> dict:
    """Get all CCNA notes from Anki, mapped by Card ID field."""
    note_ids = anki_invoke("findNotes", {"query": f"deck:{BASE_DECK}*"})

    if not note_ids:
        return {}

    notes_info = anki_invoke("notesInfo", {"notes": note_ids})

    # Map by card_id field
    notes_map = {}
    for note in notes_info:
        fields = note.get("fields", {})
        # Try both "Card ID" (with space) and "CardID" (without space)
        card_id = fields.get("Card ID", {}).get("value", "") or fields.get("CardID", {}).get("value", "")
        if card_id:
            notes_map[card_id] = note

    return notes_map


def sanitize_deck_name(name: str) -> str:
    """Sanitize name for use as Anki deck name."""
    if not name:
        return "Unknown"
    name = re.sub(r'[<>:"/\\|?*]', '', name)
    name = name.replace('::', '-')
    return name[:50]


def delete_ccna_decks() -> int:
    """
    Delete ALL CCNA decks from Anki (including empty ones).

    Use this to clean up incorrectly structured deck hierarchy.
    """
    logger.info("Deleting all CCNA decks from Anki...")

    try:
        version = anki_invoke("version")
        logger.info(f"Connected to AnkiConnect v{version}")
    except Exception as e:
        logger.error(f"Cannot connect to Anki: {e}")
        return 0

    # Get all deck names
    all_decks = anki_invoke("deckNames")
    ccna_decks = [d for d in all_decks if d.startswith("CCNA")]

    if not ccna_decks:
        logger.info("No CCNA decks found")
        return 0

    logger.info(f"Found {len(ccna_decks)} CCNA decks to delete...")

    # Delete decks in batches (cardsToo=True removes cards as well)
    # Sort deepest first so children are deleted before parents
    sorted_decks = sorted(ccna_decks, key=len, reverse=True)
    batch_size = 10  # Delete 10 decks at a time
    deleted = 0

    for i in range(0, len(sorted_decks), batch_size):
        batch = sorted_decks[i:i+batch_size]
        try:
            anki_invoke("deleteDecks", {"decks": batch, "cardsToo": True})
            deleted += len(batch)
            if deleted % 50 == 0 or deleted == len(sorted_decks):
                logger.info(f"  Deleted {deleted}/{len(ccna_decks)} decks...")
        except Exception as e:
            # Fall back to one-by-one if batch fails
            for deck in batch:
                try:
                    anki_invoke("deleteDecks", {"decks": [deck], "cardsToo": True})
                    deleted += 1
                except Exception as e2:
                    logger.debug(f"Could not delete deck {deck}: {e2}")

    logger.info(f"Deletion complete: {deleted} decks removed")
    return deleted


def delete_all_ccna_cards() -> int:
    """
    Delete ALL existing CCNA cards from Anki.

    Use this before a fresh sync to ensure clean state with new 6-field structure.
    Returns the number of notes deleted.
    """
    logger.info("Deleting all existing CCNA notes from Anki...")

    try:
        version = anki_invoke("version")
        logger.info(f"Connected to AnkiConnect v{version}")
    except Exception as e:
        logger.error(f"Cannot connect to Anki: {e}")
        return 0

    # Find all notes in CCNA decks
    note_ids = anki_invoke("findNotes", {"query": f"deck:{BASE_DECK}*"})

    if not note_ids:
        logger.info("No existing CCNA notes found")
        return 0

    logger.info(f"Found {len(note_ids)} notes to delete...")

    # Delete in batches to avoid timeouts
    batch_size = 100
    deleted = 0
    for i in range(0, len(note_ids), batch_size):
        batch = note_ids[i:i+batch_size]
        try:
            anki_invoke("deleteNotes", {"notes": batch})
            deleted += len(batch)
            logger.info(f"  Deleted {deleted}/{len(note_ids)} notes...")
        except Exception as e:
            logger.warning(f"Batch delete failed: {e}")

    logger.info(f"Deletion complete: {deleted} notes removed")
    return deleted


def pull_anki_stats():
    """
    Pull FSRS stats FROM Anki INTO PostgreSQL.

    This is the primary sync direction - we TRUST Anki's scheduling data.
    """
    logger.info("Pulling FSRS stats from Anki...")

    try:
        version = anki_invoke("version")
        logger.info(f"Connected to AnkiConnect v{version}")
    except Exception as e:
        logger.error(f"Cannot connect to Anki: {e}")
        return

    # Get all CCNA cards with stats
    card_ids = anki_invoke("findCards", {"query": f"deck:{BASE_DECK}*"})
    logger.info(f"Found {len(card_ids)} cards in Anki")

    if not card_ids:
        return

    cards_info = anki_invoke("cardsInfo", {"cards": card_ids})

    # Get notes info for Card ID field
    note_ids = list(set(card.get("noteId") for card in cards_info))
    notes_info = anki_invoke("notesInfo", {"notes": note_ids})
    notes_by_id = {n["noteId"]: n for n in notes_info if n.get("noteId")}

    updated = 0
    with session_scope() as session:
        for card in cards_info:
            note = notes_by_id.get(card.get("noteId"), {})
            fields = note.get("fields", {})
            card_id_field = fields.get("Card ID", {}).get("value", "") or fields.get("CardID", {}).get("value", "")

            if not card_id_field:
                continue

            # Extract FSRS stats
            interval = card.get("interval", 0)
            ease_factor = card.get("factor", 2500) / 1000  # Stored as int * 1000
            reps = card.get("reps", 0)
            lapses = card.get("lapses", 0)
            queue = card.get("queue", 0)

            # Calculate stability (approximate from interval)
            # FSRS stability ≈ interval for mature cards
            stability = max(interval, 1)

            # Calculate difficulty from ease factor (0-1 scale, inverted)
            # Ease 2.5 = difficulty 0.5, Ease 1.3 = difficulty ~0.9
            difficulty = max(0, min(1, (3.0 - ease_factor) / 2.0))

            # Update atom in database
            result = session.execute(text("""
                UPDATE learning_atoms SET
                    anki_note_id = :note_id,
                    anki_interval = :interval,
                    anki_ease_factor = :ease,
                    anki_review_count = :reps,
                    anki_lapses = :lapses,
                    anki_stability = :stability,
                    anki_difficulty = :difficulty,
                    anki_queue = :queue,
                    anki_synced_at = NOW()
                WHERE card_id = :card_id
            """), {
                "note_id": card.get("noteId"),
                "interval": interval,
                "ease": ease_factor,
                "reps": reps,
                "lapses": lapses,
                "stability": stability,
                "difficulty": difficulty,
                "queue": queue,
                "card_id": card_id_field,
            })

            if result.rowcount > 0:
                updated += 1

        session.commit()

    logger.info(f"Updated FSRS stats for {updated} atoms")


def push_atoms_to_anki(dry_run: bool = False):
    """
    Push flashcard and cloze atoms TO Anki.

    ONLY these types go to Anki:
    - flashcard
    - cloze

    MCQ, true_false, matching, parsons stay in NLS for in-app quizzes.
    """
    logger.info("Pushing flashcard/cloze atoms to Anki...")

    try:
        version = anki_invoke("version")
        logger.info(f"Connected to AnkiConnect v{version}")
    except Exception as e:
        logger.error(f"Cannot connect to Anki: {e}")
        return

    # Create base deck
    if not dry_run:
        ensure_deck_exists(BASE_DECK)

    with session_scope() as session:
        # Get ONLY flashcard and cloze atoms with full metadata for 6-field structure
        # Per Master Prompt: CLT is NOT fetched for Anki cards
        # Note: difficulty and prerequisites columns may not exist in older schemas
        #
        # QUALITY FILTER (configurable via src/cleaning/thresholds.py):
        # - quality_score >= ANKI_MIN_QUALITY_SCORE (Grade C or better)
        # - front text >= ANKI_MIN_FRONT_LENGTH chars (avoid truncated questions)
        # - back text >= ANKI_MIN_BACK_LENGTH chars (avoid empty answers)
        # - Exclude malformed patterns from ANKI_EXCLUDE_PATTERNS

        # Build dynamic exclusion clauses from configurable patterns
        exclude_clauses = " ".join(
            f"AND ca.front NOT LIKE '{pattern}'" for pattern in ANKI_EXCLUDE_PATTERNS
        )

        query = f"""
            SELECT
                ca.id,
                ca.card_id,
                ca.front,
                ca.back,
                ca.atom_type,
                ca.concept_id,
                ca.source,
                ca.quality_score,
                ca.anki_stability,
                ca.anki_difficulty,
                ca.module_id,
                lm.name as module_name,
                lm.week_order as module_number,
                cc.name as concept_name
            FROM learning_atoms ca
            LEFT JOIN learning_modules lm ON ca.module_id = lm.id
            LEFT JOIN concepts cc ON ca.concept_id = cc.id
            WHERE ca.atom_type IN ('flashcard', 'cloze')
              AND ca.front IS NOT NULL
              AND ca.front != ''
              -- Quality filters (from thresholds.py)
              AND ca.quality_score IS NOT NULL
              AND ca.quality_score >= :min_quality
              AND LENGTH(ca.front) >= :min_front_length
              AND LENGTH(ca.back) >= :min_back_length
              -- Exclude malformed patterns (from thresholds.py)
              {exclude_clauses}
            ORDER BY lm.week_order, ca.card_id
        """

        logger.info(f"Quality filter: score >= {ANKI_MIN_QUALITY_SCORE}, front >= {ANKI_MIN_FRONT_LENGTH} chars, back >= {ANKI_MIN_BACK_LENGTH} chars")
        logger.info(f"Excluding {len(ANKI_EXCLUDE_PATTERNS)} malformed patterns")

        result = session.execute(text(query), {
            "min_quality": ANKI_MIN_QUALITY_SCORE,
            "min_front_length": ANKI_MIN_FRONT_LENGTH,
            "min_back_length": ANKI_MIN_BACK_LENGTH,
        })

        atoms = [dict(row._mapping) for row in result.fetchall()]
        logger.info(f"Found {len(atoms)} flashcard/cloze atoms to sync")

        # Count by type
        type_counts = {}
        for atom in atoms:
            t = atom["atom_type"]
            type_counts[t] = type_counts.get(t, 0) + 1
        logger.info(f"  By type: {type_counts}")

        # Get existing Anki notes
        existing_notes = get_all_anki_notes()
        existing_card_ids = set(existing_notes.keys())
        logger.info(f"Found {len(existing_card_ids)} existing notes in Anki")

        # Track what we're syncing
        db_card_ids = set()
        notes_to_add = []
        notes_to_update = []
        decks_created = set()

        # Pre-compute all deck names to create them upfront
        logger.info("Computing deck names...")
        deck_names_needed = set()
        for atom in atoms:
            module_num = atom.get("module_number") or 0
            deck_name = get_module_deck_name(module_num)
            deck_names_needed.add(deck_name)

        logger.info(f"Need to create/verify {len(deck_names_needed)} decks...")
        if not dry_run:
            # Create decks in batches using multi action (much faster)
            sorted_decks = sorted(deck_names_needed)
            batch_size = 50  # Create 50 decks per API call
            total_created = 0

            for i in range(0, len(sorted_decks), batch_size):
                batch = sorted_decks[i:i+batch_size]
                created = create_decks_batch(batch)
                total_created += created
                decks_created.update(batch)
                logger.info(f"  Created {min(i + batch_size, len(sorted_decks))}/{len(deck_names_needed)} decks...")

            logger.info(f"  All {len(decks_created)} decks ready")

        logger.info("Processing atoms...")
        for i, atom in enumerate(atoms):
            if (i + 1) % 1000 == 0:
                logger.info(f"  Processed {i + 1}/{len(atoms)} atoms...")
            card_id = atom["card_id"]
            if not card_id:
                # Generate card_id if missing
                atom_id_str = str(atom['id'])[:8]
                card_id = f"CCNA-M{atom.get('module_number', 0)}-{atom_id_str}"

            db_card_ids.add(card_id)

            # Build deck path using hardcoded CCNA module names
            module_num = atom.get("module_number") or 0
            deck_name = get_module_deck_name(module_num)

            # Build globally-unique tags with curriculum prefix
            # Format: <curriculum>:<module> e.g., ccna-itn:m1
            # This ensures module:1 from CCNA-ITN doesn't clash with module:1 from another course
            #
            # Tag hierarchy (searchable in Anki):
            #   ccna-itn:m1         - All atoms from CCNA ITN Module 1
            #   ccna-itn:1.1.1      - Specific section within module
            #   ccna-itn            - All atoms from CCNA ITN curriculum
            #   type:flashcard      - Cross-curriculum type filter
            #   concept:<slug>      - Cross-curriculum concept filter
            #
            # CLT tags are NOT used for Anki cards (per Master Prompt rule 1)
            tags = [
                CURRICULUM_ID,                              # Root curriculum tag: ccna-itn
                f"{CURRICULUM_ID}:m{module_num}",           # Module: ccna-itn:m1
                f"type:{atom['atom_type']}",                # Type: type:flashcard
            ]

            # Add concept tag if available (cross-curriculum searchable)
            if atom.get("concept_name"):
                concept_slug = atom["concept_name"].lower().replace(" ", "-")[:30]
                tags.append(f"concept:{concept_slug}")

            # Add difficulty tag if available (from FSRS anki_difficulty, scale 0-1 → map to 1-5)
            if atom.get("anki_difficulty"):
                # Map 0-1 scale to 1-5 difficulty bands
                # 0.0-0.2 → easy (1), 0.2-0.4 → (2), 0.4-0.6 → medium (3), 0.6-0.8 → (4), 0.8-1.0 → hard (5)
                diff_int = min(5, max(1, int(atom["anki_difficulty"] * 5) + 1))
                tags.append(f"difficulty:{diff_int}")

            # Choose note type based on atom type
            note_type = CLOZE_NOTE_TYPE if atom["atom_type"] == "cloze" else FLASHCARD_NOTE_TYPE

            # Build metadata JSON per Master Prompt structure
            # Note: CLT variables are null for Anki cards (per Master Prompt rule 5)
            # Convert Decimal types to float for JSON serialization
            def to_float(val):
                return float(val) if val is not None else None

            metadata = {
                "curriculum_id": CURRICULUM_ID,          # Globally unique curriculum identifier
                "concept_name": atom.get("concept_name"),
                "module_number": module_num,
                "module_name": atom.get("module_name"),
                "quality_score": to_float(atom.get("quality_score")),
                "difficulty": to_float(atom.get("anki_difficulty")),  # FSRS difficulty (0-1 scale)
                "stability": to_float(atom.get("anki_stability")),
                "atom_type": atom["atom_type"],
                # CLT is null for Anki cards per Master Prompt
                "clt_intrinsic": None,
                "clt_extraneous": None,
                "clt_germane": None,
                "prerequisites": [],  # Future: populate from prerequisite graph
            }

            # Build note with 6-field structure (field names are lowercase to match Anki)
            # LearningOS-v2 fields: concept_id, front, back, tags, source, metadata_json
            note = {
                "deckName": deck_name,
                "modelName": note_type,
                "fields": {
                    "concept_id": str(atom.get("concept_id") or ""),
                    "front": atom["front"],
                    "back": atom.get("back") or "",
                    "tags": " ".join(tags),
                    "source": atom.get("source") or "nls",
                    "metadata_json": json.dumps(metadata),
                },
                "tags": tags,
                # Allow duplicates since we track by card_id in our DB, not by content
                # Anki's duplicate check is too strict for learning atoms
                "options": {
                    "allowDuplicate": True,
                },
            }

            if card_id in existing_card_ids:
                notes_to_update.append((card_id, note, existing_notes[card_id]["noteId"]))
            else:
                notes_to_add.append(note)

        logger.info(f"\nSync Summary:")
        logger.info(f"  Flashcard/Cloze atoms in DB: {len(atoms)}")
        logger.info(f"  New notes to add: {len(notes_to_add)}")
        logger.info(f"  Notes to update: {len(notes_to_update)}")
        logger.info(f"  Decks to create: {len(decks_created)}")

        if dry_run:
            logger.info("\n[DRY RUN] No changes made")
            return

        # Add new notes
        if notes_to_add:
            logger.info(f"Adding {len(notes_to_add)} new notes...")

            # Debug: show first note structure
            if notes_to_add:
                sample = notes_to_add[0]
                logger.debug(f"Sample note structure:")
                logger.debug(f"  deckName: {sample.get('deckName')}")
                logger.debug(f"  modelName: {sample.get('modelName')}")
                logger.debug(f"  fields.front: {sample.get('fields', {}).get('front', 'MISSING')[:80]}...")
                logger.debug(f"  fields.back: {sample.get('fields', {}).get('back', 'MISSING')[:50]}...")
                logger.debug(f"  fields keys: {list(sample.get('fields', {}).keys())}")

            batch_size = 50
            added = 0
            for i in range(0, len(notes_to_add), batch_size):
                batch = notes_to_add[i:i+batch_size]
                try:
                    result = anki_invoke("addNotes", {"notes": batch})
                    added += len([r for r in result if r is not None])
                except Exception as e:
                    logger.warning(f"Batch add failed: {e}")
                    # Show first failing note
                    if batch:
                        logger.debug(f"First note in batch: {json.dumps(batch[0], indent=2, default=str)[:500]}")
                    # Try one by one
                    for note in batch:
                        try:
                            anki_invoke("addNote", {"note": note})
                            added += 1
                        except Exception as e2:
                            logger.debug(f"Failed to add note: {e2}")
            logger.info(f"  Added {added} notes")

        # Update existing notes
        if notes_to_update:
            logger.info(f"Updating {len(notes_to_update)} notes...")
            updated = 0
            for card_id, note, note_id in notes_to_update:
                try:
                    anki_invoke("updateNoteFields", {
                        "note": {
                            "id": note_id,
                            "fields": note["fields"],
                        }
                    })
                    updated += 1
                except Exception as e:
                    logger.debug(f"Failed to update {card_id}: {e}")
            logger.info(f"  Updated {updated} notes")

        logger.info("\nPush complete!")


def show_summary():
    """Show current atom distribution."""
    with session_scope() as session:
        result = session.execute(text("""
            SELECT
                atom_type,
                COUNT(*) as count
            FROM learning_atoms
            GROUP BY atom_type
            ORDER BY count DESC
        """))

        print("\n" + "=" * 60)
        print("LEARNING ATOM DISTRIBUTION")
        print("=" * 60)

        anki_total = 0
        nls_total = 0

        rows = list(result)

        print("\n[TO ANKI - Spaced Repetition]")
        for row in rows:
            if row.atom_type in ANKI_ATOM_TYPES:
                print(f"  {row.atom_type:15} {row.count:5} atoms")
                anki_total += row.count

        print("\n[IN NLS - Interactive Quizzes]")
        for row in rows:
            if row.atom_type not in ANKI_ATOM_TYPES:
                print(f"  {row.atom_type:15} {row.count:5} atoms")
                nls_total += row.count

        print("\n" + "-" * 60)
        print(f"  Anki (flashcard+cloze): {anki_total}")
        print(f"  NLS (mcq+t/f+etc):      {nls_total}")
        print(f"  TOTAL:                  {anki_total + nls_total}")
        print("=" * 60)


def main():
    parser = argparse.ArgumentParser(
        description="Sync learning atoms with Anki (flashcard/cloze only)"
    )
    parser.add_argument("--dry-run", action="store_true", help="Show what would be done")
    parser.add_argument("--pull-only", action="store_true", help="Only pull stats FROM Anki")
    parser.add_argument("--push-only", action="store_true", help="Only push atoms TO Anki")
    parser.add_argument("--delete-all", action="store_true",
                        help="Delete ALL existing CCNA cards before sync (use for fresh start with new 6-field structure)")
    parser.add_argument("--delete-decks", action="store_true",
                        help="Delete ALL CCNA decks (including empty ones) - use to fix hierarchy issues")
    parser.add_argument("--summary", action="store_true", help="Show atom distribution")

    args = parser.parse_args()

    if args.summary:
        show_summary()
        return 0

    try:
        # Handle deck deletion first (to fix hierarchy issues)
        if args.delete_decks:
            if args.dry_run:
                logger.info("[DRY RUN] Would delete all CCNA decks")
            else:
                deleted = delete_ccna_decks()
                logger.info(f"Deleted {deleted} decks, ready for fresh sync")

        # Handle card deletion
        if args.delete_all:
            if args.dry_run:
                logger.info("[DRY RUN] Would delete all existing CCNA notes")
            else:
                deleted = delete_all_ccna_cards()
                logger.info(f"Deleted {deleted} notes, ready for fresh sync")

        if args.pull_only:
            pull_anki_stats()
        elif args.push_only:
            push_atoms_to_anki(dry_run=args.dry_run)
        elif not args.delete_all:
            # Default: bidirectional sync (skip if only --delete-all was specified)
            # 1. Pull stats from Anki first (trust FSRS)
            pull_anki_stats()
            # 2. Push new flashcard/cloze atoms to Anki
            push_atoms_to_anki(dry_run=args.dry_run)
        else:
            # --delete-all was specified alone, now push fresh content
            push_atoms_to_anki(dry_run=args.dry_run)

        if not args.dry_run:
            show_summary()

    except Exception as e:
        logger.exception(f"Sync failed: {e}")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
