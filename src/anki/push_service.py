"""
Anki push service for notion-learning-sync.

Pushes clean atoms from PostgreSQL to Anki via AnkiConnect.
Handles:
- Quality filtering (only push atoms meeting threshold)
- Atom type filtering (only flashcard/cloze go to Anki)
- Batched operations for ~50x speedup
- Upsert logic (create or update)
- Module-based deck organization (CCNA::ITN::M01 Networking Today, etc.)
- Proper tag generation (cortex, curriculum, type, section)
- Note type routing (LearningOS-v2 vs LearningOS-v2 Cloze)
- 6-field metadata support
- Progress tracking
"""

from __future__ import annotations

import json
import re
from typing import Any

from loguru import logger
from sqlalchemy import text
from sqlalchemy.orm import Session

from src.anki.anki_client import AnkiClient
from src.anki.config import (
    ANKI_ATOM_TYPES,
    ANKI_QUALITY_THRESHOLDS,
    BASE_DECK,
    CCNA_ITN_MODULE_NAMES,
    CURRICULUM_ID,
    DEFAULT_QUALITY_THRESHOLD,
    SOURCE_TAG,
    get_module_deck_name,
    get_note_type,
)
from src.db.database import get_session

BATCH_SIZE = 100  # Process 100 atoms per batch


def _ensure_decks_exist(client: AnkiClient) -> None:
    """Create all module decks in Anki if they don't exist."""
    for module_num in CCNA_ITN_MODULE_NAMES:
        deck_name = get_module_deck_name(module_num)
        try:
            client._invoke("createDeck", {"deck": deck_name})
            logger.debug("Ensured deck exists: {}", deck_name)
        except Exception as exc:
            # Deck might already exist, that's fine
            logger.debug("Deck creation result for {}: {}", deck_name, exc)


def push_clean_atoms(
    anki_client: AnkiClient | None = None,
    db_session: Session | None = None,
    min_quality: str = "B",
    dry_run: bool = False,
    incremental: bool = True,
) -> dict[str, Any]:
    """
    Push clean atoms from database to Anki using batched operations.

    ~50x faster than sequential push by using AnkiConnect's multi action.
    Cards are organized into module subdecks (ITN::01 Networking Today, etc.)

    Args:
        anki_client: AnkiConnect client (default: create new)
        db_session: Database session (default: create new)
        min_quality: Minimum quality grade to push (A, B, C, D, F)
        dry_run: If True, log actions but don't execute
        incremental: If True, only push atoms that are new or changed (default)
                     If False, push all atoms (full sync)

    Returns:
        Dictionary with push statistics
    """
    client = anki_client or AnkiClient()
    session = db_session or next(get_session())

    # Check Anki connection
    if not dry_run and not client.check_connection():
        raise RuntimeError(
            "Cannot connect to Anki. Ensure Anki is running with AnkiConnect addon."
        )

    # Ensure all module decks exist
    if not dry_run:
        logger.debug("Creating module decks in Anki...")
        _ensure_decks_exist(client)

    # Quality grade to numeric threshold (legacy support)
    # Per-type thresholds are now in ANKI_QUALITY_THRESHOLDS config
    quality_grades = {"A": 0.9, "B": 0.7, "C": 0.5, "D": 0.3, "F": 0.0}
    legacy_min_score = quality_grades.get(min_quality.upper(), 0.7)

    # Use per-type thresholds from config
    flashcard_threshold = ANKI_QUALITY_THRESHOLDS.get("flashcard", DEFAULT_QUALITY_THRESHOLD)
    cloze_threshold = ANKI_QUALITY_THRESHOLDS.get("cloze", DEFAULT_QUALITY_THRESHOLD)

    logger.info(
        "Pushing atoms to Anki (BATCHED): flashcard threshold={}, cloze threshold={}, dry_run={}, incremental={}",
        flashcard_threshold,
        cloze_threshold,
        dry_run,
        incremental,
    )

    # Fetch atoms - only flashcard/cloze types, with section info for tags
    # Per-type quality thresholds: flashcards need 0.85+, cloze needs 0.80+
    # NULL quality_score atoms are EXCLUDED (no more loophole)
    # Incremental mode: only atoms without anki_note_id or with updated_at > anki_synced_at
    if incremental:
        query = text("""
            SELECT
                la.id,
                la.card_id,
                la.front,
                la.back,
                la.atom_type,
                la.quality_score,
                la.anki_note_id,
                la.ccna_section_id,
                la.concept_id,
                cs.module_number
            FROM learning_atoms la
            LEFT JOIN ccna_sections cs ON la.ccna_section_id = cs.section_id
            WHERE la.quality_score IS NOT NULL
              AND (
                  (la.atom_type = 'flashcard' AND la.quality_score >= :flashcard_threshold)
                  OR (la.atom_type = 'cloze' AND la.quality_score >= :cloze_threshold)
              )
              AND (
                  la.anki_note_id IS NULL
                  OR la.anki_synced_at IS NULL
                  OR la.updated_at > la.anki_synced_at
              )
        """)
    else:
        query = text("""
            SELECT
                la.id,
                la.card_id,
                la.front,
                la.back,
                la.atom_type,
                la.quality_score,
                la.anki_note_id,
                la.ccna_section_id,
                la.concept_id,
                cs.module_number
            FROM learning_atoms la
            LEFT JOIN ccna_sections cs ON la.ccna_section_id = cs.section_id
            WHERE la.quality_score IS NOT NULL
              AND (
                  (la.atom_type = 'flashcard' AND la.quality_score >= :flashcard_threshold)
                  OR (la.atom_type = 'cloze' AND la.quality_score >= :cloze_threshold)
              )
        """)

    result = session.execute(
        query,
        {"flashcard_threshold": flashcard_threshold, "cloze_threshold": cloze_threshold}
    ).fetchall()

    mode_str = "incremental" if incremental else "full"
    logger.info("Found {} atoms to sync ({} mode)", len(result), mode_str)

    stats = {"created": 0, "updated": 0, "skipped": 0, "errors": []}

    # Process in batches
    atoms = list(result)
    total_batches = (len(atoms) + BATCH_SIZE - 1) // BATCH_SIZE

    for batch_idx in range(total_batches):
        start = batch_idx * BATCH_SIZE
        end = min(start + BATCH_SIZE, len(atoms))
        batch = atoms[start:end]

        logger.info(
            "Processing batch {}/{} ({} atoms)",
            batch_idx + 1,
            total_batches,
            len(batch),
        )

        if dry_run:
            stats["updated"] += len(batch)
            continue

        # Force create when doing full sync (not incremental) - skip finding existing notes
        batch_stats = _process_batch(client, session, batch, force_create=not incremental)
        stats["created"] += batch_stats["created"]
        stats["updated"] += batch_stats["updated"]
        stats["skipped"] += batch_stats["skipped"]
        stats["errors"].extend(batch_stats["errors"])

    logger.info(
        "Push complete: created={}, updated={}, skipped={}",
        stats["created"],
        stats["updated"],
        stats["skipped"],
    )

    return stats


def _process_batch(
    client: AnkiClient,
    session: Session,
    batch: list[tuple],
    force_create: bool = False,
) -> dict[str, Any]:
    """
    Process a batch of atoms with batched AnkiConnect calls.

    Strategy:
    1. Batch find existing notes by concept_id (unless force_create)
    2. Separate into updates vs creates
    3. Batch update existing notes
    4. Batch create new notes (with correct note type for cloze)
    5. Batch update database with new note IDs

    Args:
        client: AnkiConnect client
        session: Database session
        batch: List of atom tuples from query
        force_create: If True, skip find and create all notes fresh

    Row format from query:
    (id, card_id, front, back, atom_type, quality_score, anki_note_id, ccna_section_id, concept_id, module_number)
    """
    stats = {"created": 0, "updated": 0, "skipped": 0, "errors": []}

    # Separate into updates and creates
    updates = []  # (atom_id, note_id, fields)
    creates = []  # (atom_id, card_id, note_payload)

    # Only search for existing notes if not force_create
    find_results = []
    if not force_create:
        card_ids = [row[1] for row in batch]  # card_id is index 1
        queries = [f'concept_id:"{cid}"' for cid in card_ids]
        try:
            find_results = client.batch_find_notes(queries)
        except Exception as exc:
            logger.error("Batch find failed: {}", exc)
            stats["skipped"] += len(batch)
            stats["errors"].append(f"Batch find failed: {exc}")
            return stats

    for idx, row in enumerate(batch):
        # Unpack all fields from query
        (
            atom_id,
            card_id,
            front,
            back,
            atom_type,
            quality_score,
            existing_anki_id,
            section_id,
            concept_id,
            module_number,
        ) = row

        # Extract module number from card_id if not from join
        if not module_number:
            module_number = _extract_module_number(card_id)

        # Build fields with 6-field structure and metadata
        tags = _build_tags(card_id, atom_type, section_id, module_number)
        fields = _build_fields(card_id, front, back, tags, atom_type, section_id, module_number)

        # Get module-specific deck name
        deck_name = get_module_deck_name(module_number) if module_number else f"{BASE_DECK}::M00 Unknown"

        # Get correct note type based on atom type (cloze vs flashcard)
        note_type = get_note_type(atom_type)

        # Check for existing note (only if we did a find)
        found_ids = find_results[idx] if idx < len(find_results) else []

        if not force_create and found_ids:
            # Update existing note found in Anki
            note_id = found_ids[0]
            updates.append((atom_id, note_id, {"id": note_id, "fields": fields}, tags))
        elif not force_create and existing_anki_id:
            # Use existing ID from database
            updates.append((atom_id, existing_anki_id, {"id": existing_anki_id, "fields": fields}, tags))
        else:
            # Create new note in module-specific deck with correct note type
            note_payload = {
                "deckName": deck_name,
                "modelName": note_type,  # LearningOS-v2 or LearningOS-v2 Cloze
                "fields": fields,
                "tags": tags,
                "options": {"allowDuplicate": False, "duplicateScope": "deck"},
            }
            creates.append((atom_id, card_id, note_payload))

    # Batch update existing notes
    if updates:
        try:
            update_payloads = [u[2] for u in updates]
            client.batch_update_notes(update_payloads)
            stats["updated"] += len(updates)
            logger.debug("Batch updated {} notes", len(updates))

            # Also update tags for existing notes
            # Build tag update actions: addTags for each note
            tag_actions = []
            for atom_id, note_id, _, tags in updates:
                tag_actions.append({
                    "action": "addTags",
                    "params": {"notes": [note_id], "tags": " ".join(tags)}
                })
            if tag_actions:
                try:
                    client._invoke_multi(tag_actions)
                    logger.debug("Updated tags for {} notes", len(tag_actions))
                except Exception as tag_exc:
                    logger.warning("Tag update failed (non-fatal): {}", tag_exc)

            # Update sync timestamp in database for updated notes
            _batch_update_sync_time(session, [u[0] for u in updates])
        except Exception as exc:
            logger.error("Batch update failed: {}", exc)
            stats["errors"].append(f"Batch update failed: {exc}")
            stats["skipped"] += len(updates)

    # Batch create new notes
    if creates:
        try:
            create_payloads = [c[2] for c in creates]
            new_ids = client.batch_add_notes(create_payloads)

            # Update database with new note IDs
            db_updates = []
            for idx, (atom_id, card_id, _) in enumerate(creates):
                new_id = new_ids[idx] if idx < len(new_ids) else None
                # Handle various response types - can be int, None, or error dict
                if new_id and isinstance(new_id, int):
                    db_updates.append((atom_id, new_id))
                    stats["created"] += 1
                elif new_id and isinstance(new_id, dict):
                    # Error response from AnkiConnect
                    err = new_id.get("error", "Unknown error")
                    stats["skipped"] += 1
                    stats["errors"].append(f"Failed to create {card_id}: {err}")
                else:
                    stats["skipped"] += 1
                    stats["errors"].append(f"Failed to create: {card_id}")

            # Batch update database
            if db_updates:
                _batch_update_db(session, db_updates)

            logger.debug("Batch created {} notes", stats["created"])
        except Exception as exc:
            logger.error("Batch create failed: {}", exc)
            stats["errors"].append(f"Batch create failed: {exc}")
            stats["skipped"] += len(creates)

    return stats


def _build_fields(
    card_id: str,
    front: str,
    back: str | None,
    tags: list[str],
    atom_type: str,
    section_id: str | None,
    module_number: int | None,
) -> dict[str, str]:
    """
    Build Anki note fields with 6-field structure.

    Fields match LearningOS-v2 note type:
    - front: Question or cloze text
    - back: Answer or explanation
    - concept_id: Unique card identifier
    - tags: Space-separated tags (stored in field for display)
    - source: Origin system (cortex)
    - metadata_json: JSON blob with additional metadata
    """
    # Build metadata JSON
    metadata = {
        "curriculum_id": CURRICULUM_ID,
        "module_number": module_number,
        "section_id": section_id,
        "atom_type": atom_type,
    }

    return {
        "front": front or "",
        "back": back or "",
        "concept_id": card_id or "",
        "tags": " ".join(tags),
        "source": SOURCE_TAG,
        "metadata_json": json.dumps(metadata),
    }


def _build_tags(
    card_id: str,
    atom_type: str,
    section_id: str | None,
    module_number: int | None,
) -> list[str]:
    """
    Build Anki tags with proper curriculum hierarchy.

    Tag structure:
    - cortex: Source identifier
    - ccna-itn: Curriculum root
    - ccna-itn:m{N}: Module tag
    - type:{atom_type}: flashcard or cloze
    - section:{id}: Section ID for filtering
    """
    tags = [SOURCE_TAG, CURRICULUM_ID]

    # Module tag
    if module_number:
        tags.append(f"{CURRICULUM_ID}:m{module_number}")

    # Type tag
    if atom_type:
        tags.append(f"type:{atom_type}")

    # Section tag
    if section_id:
        tags.append(f"section:{section_id}")

    return tags


def _extract_module_number(card_id: str) -> int | None:
    """
    Extract module number from card_id.

    Card IDs are formatted as NET-M{module}-S{section}-...
    Returns module number or None if not found.
    """
    if not card_id:
        return None

    match = re.match(r"NET-M(\d+)", card_id)
    if match:
        return int(match.group(1))

    return None


def _batch_update_db(session: Session, updates: list[tuple[int, int]]) -> None:
    """Batch update database with anki_note_ids and sync timestamp."""
    try:
        for atom_id, note_id in updates:
            session.execute(
                text("""
                    UPDATE learning_atoms
                    SET anki_note_id = :note_id, anki_synced_at = NOW()
                    WHERE id = :atom_id
                """),
                {"note_id": int(note_id), "atom_id": atom_id}
            )
        session.commit()
    except Exception as exc:
        logger.error("Database batch update failed: {}", exc)
        session.rollback()


def _batch_update_sync_time(session: Session, atom_ids: list[int]) -> None:
    """Update sync timestamp for atoms that were updated in Anki."""
    if not atom_ids:
        return
    try:
        for atom_id in atom_ids:
            session.execute(
                text("UPDATE learning_atoms SET anki_synced_at = NOW() WHERE id = :atom_id"),
                {"atom_id": atom_id}
            )
        session.commit()
    except Exception as exc:
        logger.error("Sync time update failed: {}", exc)
        session.rollback()
