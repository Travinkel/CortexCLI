#!/usr/bin/env python3
"""
Anki → PostgreSQL Review Sync

Pulls review data from Anki back to PostgreSQL to:
1. Preserve mastery metadata across atom deletions/regenerations
2. Transfer FSRS scheduling state to concepts
3. Enable semantic similarity matching for metadata inheritance

Uses semantic embeddings to match atoms when card_id changes during regeneration.
"""

import json
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Optional
from urllib.request import urlopen, Request
from urllib.error import URLError

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import create_engine, text
from config import get_settings
from loguru import logger

# Sentence transformer for semantic matching
try:
    from sentence_transformers import SentenceTransformer
    import numpy as np
    HAS_EMBEDDINGS = True
except ImportError:
    HAS_EMBEDDINGS = False
    logger.warning("sentence-transformers not installed - semantic matching disabled")


def anki_invoke(action: str, params: dict = None, timeout: int = 30) -> dict:
    """Call AnkiConnect API."""
    settings = get_settings()
    request_json = json.dumps({
        "action": action,
        "version": 6,
        "params": params or {}
    }).encode('utf-8')

    try:
        req = Request(settings.anki_connect_url, data=request_json)
        req.add_header('Content-Type', 'application/json')
        with urlopen(req, timeout=timeout) as response:
            result = json.loads(response.read().decode('utf-8'))
            if result.get('error'):
                raise Exception(result['error'])
            return result.get('result')
    except URLError as e:
        logger.error(f"AnkiConnect error: {e}")
        raise


def get_anki_review_data() -> list[dict]:
    """Get all card review data from Anki."""
    # Find all notes in CCNA decks
    note_ids = anki_invoke("findNotes", {"query": "deck:CCNA*"})
    logger.info(f"Found {len(note_ids)} notes in Anki")

    if not note_ids:
        return []

    # Get note info in batches
    notes_info = anki_invoke("notesInfo", {"notes": note_ids})

    # Get card IDs for each note
    cards_data = []
    for note in notes_info:
        note_id = note['noteId']
        fields = note.get('fields', {})

        # Extract our card_id from fields
        card_id = fields.get('Card ID', {}).get('value', '')
        front = fields.get('Front', {}).get('value', '') or fields.get('front', {}).get('value', '')
        concept_id = fields.get('concept_id', {}).get('value', '')
        tags = note.get('tags', [])

        # Get card scheduling info
        card_ids = note.get('cards', [])
        for cid in card_ids:
            try:
                card_info = anki_invoke("cardsInfo", {"cards": [cid]})[0]
                cards_data.append({
                    'anki_note_id': note_id,
                    'anki_card_id': cid,
                    'card_id': card_id,
                    'front': front,
                    'concept_id': concept_id,
                    'tags': tags,
                    # FSRS/Anki scheduling state
                    'due': card_info.get('due'),
                    'interval': card_info.get('interval'),
                    'ease_factor': card_info.get('factor', 2500) / 1000.0,  # Convert to decimal
                    'reps': card_info.get('reps', 0),
                    'lapses': card_info.get('lapses', 0),
                    'queue': card_info.get('queue'),
                    'type': card_info.get('type'),
                })
            except Exception as e:
                logger.warning(f"Could not get card info for {cid}: {e}")

    return cards_data


def sync_reviews_to_postgresql(cards_data: list[dict], conn) -> dict:
    """
    Sync Anki review data to PostgreSQL.

    Returns stats dict.
    """
    matched = 0
    unmatched = 0
    updated = 0

    for card in cards_data:
        card_id = card['card_id']
        if not card_id:
            unmatched += 1
            continue

        # Try to find atom by card_id
        result = conn.execute(text('''
            SELECT id, front, concept_id FROM learning_atoms
            WHERE card_id = :card_id
        '''), {'card_id': card_id})
        row = result.fetchone()

        if row:
            matched += 1
            atom_id = str(row.id)

            # Upsert into anki_sync_state table
            conn.execute(text('''
    -- Update FSRS fields directly on learning_atoms
                UPDATE learning_atoms SET
                    anki_stability = CASE
                        WHEN :interval > 0 THEN :interval
                        ELSE COALESCE(anki_stability, 1)
                    END,
                    anki_difficulty = :ease,
                    anki_review_count = COALESCE(anki_review_count, 0) + :reps,
                    anki_lapses = COALESCE(anki_lapses, 0) + :lapses,
                    anki_due_date = CASE
                        WHEN :due IS NOT NULL THEN to_timestamp(:due)::date
                        ELSE anki_due_date
                    END,
                    updated_at = NOW()
                WHERE id = :atom_id::uuid
            '''), {
                'atom_id': atom_id,
                'note_id': card['anki_note_id'],
                'card_id': card['anki_card_id'],
                'due': card['due'],
                'interval': card['interval'],
                'ease': card['ease_factor'],
                'reps': card['reps'],
                'lapses': card['lapses'],
            })
            updated += 1
        else:
            unmatched += 1

    return {
        'matched': matched,
        'unmatched': unmatched,
        'updated': updated
    }


def transfer_mastery_to_concepts(conn) -> int:
    """
    Aggregate atom-level Anki data to concept-level mastery.

    Returns number of concepts updated.
    """
    # Calculate concept mastery from atom FSRS data stored in learning_atoms
    result = conn.execute(text('''
        WITH atom_mastery AS (
            SELECT
                la.concept_id,
                COUNT(*) as atom_count,
                AVG(la.anki_difficulty) as avg_ease,
                AVG(la.anki_stability) as avg_interval,
                SUM(la.anki_review_count) as total_reps,
                SUM(la.anki_lapses) as total_lapses,
                -- Stability proxy: higher interval = more stable memory
                AVG(CASE WHEN la.anki_stability > 21 THEN 1.0
                         WHEN la.anki_stability > 7 THEN 0.7
                         WHEN la.anki_stability > 1 THEN 0.4
                         ELSE 0.2 END) as stability_score
            FROM learning_atoms la
            WHERE la.concept_id IS NOT NULL
              AND la.anki_review_count > 0
            GROUP BY la.concept_id
        )
        UPDATE concepts cc SET
            updated_at = NOW()
        FROM atom_mastery am
        WHERE cc.id = am.concept_id
        RETURNING cc.id
    '''))

    updated = len(result.fetchall())
    return updated


def find_semantic_matches(conn, unmatched_cards: list[dict]) -> list[dict]:
    """
    Use semantic embeddings to match Anki cards to atoms when card_id doesn't match.

    Returns list of suggested matches.
    """
    if not HAS_EMBEDDINGS or not unmatched_cards:
        return []

    settings = get_settings()
    model = SentenceTransformer(settings.embedding_model)

    # Get all atom fronts for comparison
    result = conn.execute(text('''
        SELECT id, card_id, front FROM learning_atoms
        WHERE front IS NOT NULL AND LENGTH(front) > 10
    '''))
    atoms = [{'id': str(r.id), 'card_id': r.card_id, 'front': r.front} for r in result]

    if not atoms:
        return []

    # Compute embeddings
    atom_texts = [a['front'] for a in atoms]
    atom_embeddings = model.encode(atom_texts, convert_to_numpy=True)

    matches = []
    for card in unmatched_cards:
        if not card['front']:
            continue

        card_embedding = model.encode([card['front']], convert_to_numpy=True)[0]

        # Compute cosine similarity
        similarities = np.dot(atom_embeddings, card_embedding) / (
            np.linalg.norm(atom_embeddings, axis=1) * np.linalg.norm(card_embedding)
        )

        best_idx = np.argmax(similarities)
        best_score = similarities[best_idx]

        if best_score >= settings.semantic_duplicate_threshold:
            matches.append({
                'anki_card_id': card['anki_card_id'],
                'anki_front': card['front'][:50],
                'matched_atom_id': atoms[best_idx]['id'],
                'matched_card_id': atoms[best_idx]['card_id'],
                'matched_front': atoms[best_idx]['front'][:50],
                'similarity': float(best_score),
                'review_data': {
                    'interval': card['interval'],
                    'ease_factor': card['ease_factor'],
                    'reps': card['reps'],
                    'lapses': card['lapses'],
                }
            })

    return matches


def main():
    """Main sync pipeline."""
    import argparse

    parser = argparse.ArgumentParser(description="Pull Anki review data to PostgreSQL")
    parser.add_argument("--dry-run", action="store_true", help="Don't write to database")
    parser.add_argument("--semantic-match", action="store_true", help="Use semantic matching for unmatched cards")
    parser.add_argument("--transfer-mastery", action="store_true", help="Update concept mastery scores")
    args = parser.parse_args()

    logger.info("Starting Anki → PostgreSQL sync...")

    settings = get_settings()
    engine = create_engine(settings.database_url)

    # Get Anki data
    logger.info("Fetching review data from Anki...")
    cards_data = get_anki_review_data()
    logger.info(f"Retrieved {len(cards_data)} cards from Anki")

    with engine.connect() as conn:
        # Ensure anki_sync_state table exists
        conn.execute(text('''
            CREATE TABLE IF NOT EXISTS anki_sync_state (
                atom_id UUID PRIMARY KEY REFERENCES learning_atoms(id),
                anki_note_id BIGINT,
                anki_card_id BIGINT,
                due INTEGER,
                interval_days INTEGER,
                ease_factor REAL,
                reps INTEGER DEFAULT 0,
                lapses INTEGER DEFAULT 0,
                last_synced_at TIMESTAMP DEFAULT NOW(),
                created_at TIMESTAMP DEFAULT NOW()
            )
        '''))

        # Add columns to concepts if missing
        try:
            conn.execute(text('''
                ALTER TABLE concepts
                ADD COLUMN IF NOT EXISTS mastery_score REAL DEFAULT 0,
                ADD COLUMN IF NOT EXISTS total_reviews INTEGER DEFAULT 0,
                ADD COLUMN IF NOT EXISTS avg_ease REAL DEFAULT 2.5,
                ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP DEFAULT NOW()
            '''))
        except Exception:
            pass  # Columns may already exist

        if not args.dry_run:
            # Sync review data
            logger.info("Syncing review data to PostgreSQL...")
            stats = sync_reviews_to_postgresql(cards_data, conn)
            logger.info(f"Sync stats: {stats}")

            # Semantic matching for unmatched
            if args.semantic_match and stats['unmatched'] > 0:
                unmatched = [c for c in cards_data if not c['card_id']]
                logger.info(f"Running semantic matching on {len(unmatched)} unmatched cards...")
                matches = find_semantic_matches(conn, unmatched)
                logger.info(f"Found {len(matches)} semantic matches")

                for m in matches[:10]:  # Show first 10
                    logger.info(f"  Match ({m['similarity']:.2f}): '{m['anki_front']}...' → '{m['matched_front']}...'")

            # Transfer mastery to concepts
            if args.transfer_mastery:
                logger.info("Transferring mastery to concepts...")
                concepts_updated = transfer_mastery_to_concepts(conn)
                logger.info(f"Updated {concepts_updated} concept mastery scores")

            conn.commit()
        else:
            logger.info("[DRY RUN] Would sync review data")

        # Show summary
        logger.info("\n=== ANKI → POSTGRESQL SYNC SUMMARY ===")
        logger.info(f"  Cards in Anki: {len(cards_data)}")

        result = conn.execute(text("SELECT COUNT(*) FROM anki_sync_state"))
        synced = result.scalar()
        logger.info(f"  Cards synced: {synced}")

        if args.transfer_mastery:
            result = conn.execute(text('''
                SELECT COUNT(*) FROM concepts WHERE mastery_score > 0
            '''))
            mastered = result.scalar()
            logger.info(f"  Concepts with mastery: {mastered}")


if __name__ == "__main__":
    main()
