"""
Anki pull service for notion-learning-sync.

Pulls FSRS stats FROM Anki INTO PostgreSQL.
This is the primary sync direction - we TRUST Anki's scheduling data.

Handles:
- Fetching card stats from Anki via AnkiConnect
- Mapping Anki cards to learning_atoms via card_id/concept_id
- Updating FSRS stats (interval, ease, stability, difficulty, etc.)
- Progress tracking
"""

from __future__ import annotations

from typing import Any

from loguru import logger
from sqlalchemy import text
from sqlalchemy.orm import Session

from src.anki.anki_client import AnkiClient
from src.anki.config import BASE_DECK
from src.db.database import get_session


def pull_review_stats(
    anki_client: AnkiClient | None = None,
    db_session: Session | None = None,
    dry_run: bool = False,
    query: str | None = None,
    sections: list[str] | None = None,
) -> dict[str, Any]:
    """
    Pull FSRS stats FROM Anki INTO PostgreSQL.

    This syncs Anki's scheduling data (interval, ease, reviews, lapses)
    back to our database so we can use it for analytics and adaptive learning.

    Args:
        anki_client: AnkiConnect client (default: create new)
        db_session: Database session (default: create new)
        dry_run: If True, log actions but don't execute
        query: Custom Anki search query (overrides default deck search)
               Example: "deck:CCNA::ITN::* (tag:section:2.1 OR tag:section:2.2)"
        sections: List of section IDs to filter by (e.g., ["2.1", "2.2", "3.*"])
                  Supports wildcards. Combined with OR logic.

    Returns:
        Dictionary with pull statistics
    """
    client = anki_client or AnkiClient()
    session = db_session or next(get_session())

    stats = {
        "cards_found": 0,
        "atoms_updated": 0,
        "atoms_not_found": 0,
        "query_used": "",
        "errors": [],
    }

    # Check Anki connection
    if not client.check_connection():
        raise RuntimeError(
            "Cannot connect to Anki. Ensure Anki is running with AnkiConnect addon."
        )

    # Build the query
    if query:
        # Use custom query directly
        anki_query = query
    elif sections:
        # Build query from section list
        # Format: deck:CCNA::ITN::* (tag:section:X.Y OR tag:section:X.Z)
        tag_conditions = [f"tag:section:{s}" for s in sections]
        anki_query = f"deck:{BASE_DECK}* ({' OR '.join(tag_conditions)})"
    else:
        # Default: all notes in deck
        anki_query = f"deck:{BASE_DECK}*"

    stats["query_used"] = anki_query
    logger.debug("Pulling FSRS stats from Anki with query: {}", anki_query)

    # Find all notes in our deck hierarchy (notes-first approach)
    # This is more reliable than findCards which doesn't return noteId properly
    try:
        note_ids = client._invoke("findNotes", {"query": anki_query})
    except Exception as exc:
        logger.error("Failed to find notes: {}", exc)
        stats["errors"].append(f"Find notes failed: {exc}")
        return stats

    logger.debug("Found {} notes in Anki", len(note_ids))

    if not note_ids:
        return stats

    # Get note info (includes concept_id and card IDs)
    try:
        notes_info = client._invoke("notesInfo", {"notes": note_ids})
    except Exception as exc:
        logger.error("Failed to get note info: {}", exc)
        stats["errors"].append(f"Note info failed: {exc}")
        return stats

    # Collect all card IDs for batch card info lookup
    all_card_ids = []
    note_to_cards = {}
    for note in notes_info:
        note_id = note.get("noteId")
        card_ids = note.get("cards", [])
        if note_id and card_ids:
            note_to_cards[note_id] = card_ids
            all_card_ids.extend(card_ids)

    stats["cards_found"] = len(all_card_ids)
    logger.debug("Found {} cards across {} notes", len(all_card_ids), len(notes_info))

    # Get card info (scheduling data) for all cards
    cards_by_id = {}
    if all_card_ids:
        try:
            cards_info = client._invoke("cardsInfo", {"cards": all_card_ids})
            cards_by_id = {c.get("cardId"): c for c in cards_info if c.get("cardId")}
        except Exception as exc:
            logger.error("Failed to get card info: {}", exc)
            stats["errors"].append(f"Card info failed: {exc}")
            return stats

    # Process each note
    updates = []
    for note in notes_info:
        note_id = note.get("noteId")
        fields = note.get("fields", {})

        # Get card_id from concept_id field (our primary identifier)
        card_id = (
            fields.get("concept_id", {}).get("value", "")
            or fields.get("Card ID", {}).get("value", "")
            or fields.get("CardID", {}).get("value", "")
        )

        if not card_id:
            continue

        # Get card scheduling data (use first card for this note)
        card_ids_for_note = note_to_cards.get(note_id, [])
        card = cards_by_id.get(card_ids_for_note[0]) if card_ids_for_note else {}

        # Extract FSRS stats from Anki
        interval = card.get("interval", 0)
        ease_factor = card.get("factor", 2500) / 1000  # Stored as int * 1000
        reps = card.get("reps", 0)
        lapses = card.get("lapses", 0)
        queue = card.get("queue", 0)
        due = card.get("due", 0)

        # Calculate stability (approximate from interval)
        # FSRS stability ≈ interval for mature cards
        stability = max(interval, 1)

        # Calculate difficulty from ease factor (0-1 scale, inverted)
        # Ease 2.5 = difficulty 0.5, Ease 1.3 = difficulty ~0.9
        difficulty = max(0.0, min(1.0, (3.0 - ease_factor) / 2.0))

        updates.append({
            "card_id": card_id,
            "note_id": card.get("noteId"),
            "interval": interval,
            "ease_factor": ease_factor,
            "reps": reps,
            "lapses": lapses,
            "stability": stability,
            "difficulty": difficulty,
            "queue": queue,
            "due": due,
        })

    logger.debug("Processing {} cards with valid card_ids", len(updates))

    if dry_run:
        logger.info("[DRY RUN] Would update {} atoms", len(updates))
        stats["atoms_updated"] = len(updates)
        return stats

    # Batch update database
    for update in updates:
        try:
            result = session.execute(
                text("""
                    UPDATE learning_atoms SET
                        anki_note_id = :note_id,
                        anki_interval = :interval,
                        anki_ease_factor = :ease_factor,
                        anki_review_count = :reps,
                        anki_lapses = :lapses,
                        anki_stability = :stability,
                        anki_difficulty = :difficulty,
                        anki_queue = :queue,
                        anki_synced_at = NOW()
                    WHERE card_id = :card_id
                """),
                update,
            )

            if result.rowcount > 0:
                stats["atoms_updated"] += 1
            else:
                stats["atoms_not_found"] += 1

        except Exception as exc:
            logger.warning("Failed to update atom {}: {}", update["card_id"], exc)
            stats["errors"].append(f"Update {update['card_id']} failed: {exc}")

    try:
        session.commit()
    except Exception as exc:
        logger.error("Failed to commit updates: {}", exc)
        session.rollback()
        stats["errors"].append(f"Commit failed: {exc}")

    logger.debug(
        "Pull complete: updated={}, not_found={}, errors={}",
        stats["atoms_updated"],
        stats["atoms_not_found"],
        len(stats["errors"]),
    )

    return stats


def sync_bidirectional(
    anki_client: AnkiClient | None = None,
    db_session: Session | None = None,
    min_quality: str = "B",
    dry_run: bool = False,
) -> dict[str, Any]:
    """
    Perform bidirectional sync: push atoms TO Anki, then pull stats FROM Anki.

    Args:
        anki_client: AnkiConnect client (default: create new)
        db_session: Database session (default: create new)
        min_quality: Minimum quality grade for push (A, B, C, D, F)
        dry_run: If True, log actions but don't execute

    Returns:
        Dictionary with combined push and pull statistics
    """
    from src.anki.push_service import push_clean_atoms

    client = anki_client or AnkiClient()
    session = db_session or next(get_session())

    logger.info("Starting bidirectional Anki sync...")

    # Push first (create/update cards in Anki)
    push_stats = push_clean_atoms(
        anki_client=client,
        db_session=session,
        min_quality=min_quality,
        dry_run=dry_run,
    )

    # Pull second (get scheduling data back)
    pull_stats = pull_review_stats(
        anki_client=client,
        db_session=session,
        dry_run=dry_run,
    )

    return {
        "push": push_stats,
        "pull": pull_stats,
    }
