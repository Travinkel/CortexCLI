"""
Anki import service for notion-learning-sync.

Orchestrates the import of existing Anki decks into PostgreSQL staging tables.
Performs:
- Bulk card import via AnkiConnect
- Prerequisite tag parsing
- Basic quality analysis (word/char counts)
- FSRS stat extraction
- Progress tracking and error handling
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from loguru import logger
from psycopg2.extras import Json
from sqlalchemy import text
from sqlalchemy.orm import Session

from config import get_settings
from src.anki.anki_client import AnkiClient
from src.db.database import get_db


class AnkiImportService:
    """
    Service for importing Anki decks into PostgreSQL staging tables.

    Workflow:
    1. Fetch all cards from Anki via AnkiConnect
    2. Parse prerequisite tags (tag:prereq:domain:topic:subtopic)
    3. Calculate word/char counts for quality analysis
    4. Insert into stg_anki_cards
    5. Log import statistics
    """

    def __init__(
        self,
        anki_client: AnkiClient | None = None,
        db_session: Session | None = None,
    ) -> None:
        """
        Initialize import service.

        Args:
            anki_client: AnkiConnect client (default: create new)
            db_session: Database session (default: create new)
        """
        self.settings = get_settings()
        self.anki_client = anki_client or AnkiClient()
        self.db_session = db_session or next(get_db())
        self.import_batch_id = str(uuid.uuid4())

        logger.info(
            "Initialized AnkiImportService: batch_id={}",
            self.import_batch_id,
        )

    # ========================================
    # Main Import Methods
    # ========================================

    def import_deck(
        self,
        deck_name: str | None = None,
        query: str | None = None,
        dry_run: bool = False,
        quality_analysis: bool = True,
    ) -> dict[str, Any]:
        """
        Import all cards from an Anki deck.

        Args:
            deck_name: Deck to import (default from config)
            query: Anki search query to filter cards (default from config)
            dry_run: If True, fetch but don't insert
            quality_analysis: If True, calculate word counts and quality metrics

        Returns:
            Dictionary with import statistics:
                - cards_imported: Number of cards processed
                - cards_with_fsrs: Cards with FSRS stats
                - cards_with_prerequisites: Cards with prerequisite tags
                - cards_needing_split: Non-atomic cards
                - grade_distribution: Quality grade counts
                - errors: List of error messages
        """
        deck = deck_name or self.settings.anki_deck_name
        search_query = query or self.settings.anki_query

        logger.info("Starting Anki import: deck={}, query={}, dry_run={}", deck, search_query, dry_run)

        # Create import log entry
        if not dry_run:
            self._create_import_log(deck)

        # Check AnkiConnect connection
        if not self.anki_client.check_connection():
            error_msg = "Failed to connect to AnkiConnect. Is Anki running?"
            logger.error(error_msg)
            if not dry_run:
                self._update_import_log("failed", error_message=error_msg)
            return {
                "success": False,
                "error": error_msg,
                "cards_imported": 0,
            }

        # Fetch cards from Anki
        try:
            cards = self.anki_client.fetch_all_cards(
                deck_name=deck,
                query=search_query,
                include_stats=True,
            )

            if not cards:
                logger.warning("No cards found for query '{}'", search_query)
                if not dry_run:
                    self._update_import_log("completed", cards_imported=0)
                return {
                    "success": True,
                    "cards_imported": 0,
                    "message": f"No cards found for query '{search_query}'",
                }

            logger.info("Fetched {} cards from Anki", len(cards))

        except Exception as exc:
            error_msg = f"Failed to fetch cards from Anki: {exc}"
            logger.error(error_msg)
            if not dry_run:
                self._update_import_log("failed", error_message=error_msg)
            return {
                "success": False,
                "error": error_msg,
                "cards_imported": 0,
            }

        # Process cards
        stats = {
            "cards_imported": 0,
            "cards_with_fsrs": 0,
            "cards_with_prerequisites": 0,
            "cards_needing_split": 0,
            "grade_distribution": {"A": 0, "B": 0, "C": 0, "D": 0, "F": 0},
            "errors": [],
        }

        for card in cards:
            try:
                # Add quality analysis if requested
                if quality_analysis:
                    card = self._add_quality_metrics(card)

                # Insert into staging table (unless dry run)
                if not dry_run:
                    self._insert_staging_card(card)

                # Update statistics
                stats["cards_imported"] += 1

                if card.get("fsrs_stats"):
                    stats["cards_with_fsrs"] += 1

                if card.get("prerequisites", {}).get("has_prerequisites"):
                    stats["cards_with_prerequisites"] += 1

                if card.get("needs_split"):
                    stats["cards_needing_split"] += 1

                quality_grade = card.get("quality_grade")
                if quality_grade in stats["grade_distribution"]:
                    stats["grade_distribution"][quality_grade] += 1

            except Exception as exc:
                error_msg = f"Failed to process card {card.get('card_id')}: {exc}"
                logger.error(error_msg)
                stats["errors"].append(error_msg)

        # Commit transaction
        if not dry_run:
            try:
                self.db_session.commit()
                logger.info("Committed {} cards to database", stats["cards_imported"])
            except Exception as exc:
                self.db_session.rollback()
                error_msg = f"Database commit failed: {exc}"
                logger.error(error_msg)
                self._update_import_log("failed", error_message=error_msg)
                return {
                    "success": False,
                    "error": error_msg,
                    "cards_imported": 0,
                }

            # Update import log with final statistics
            self._update_import_log(
                status="completed",
                **{k: v for k, v in stats.items() if k != "errors"},
            )

        # Log summary
        logger.info(
            "Import complete: {} cards imported, {} with FSRS, {} with prerequisites, {} need splitting",
            stats["cards_imported"],
            stats["cards_with_fsrs"],
            stats["cards_with_prerequisites"],
            stats["cards_needing_split"],
        )

        logger.info(
            "Quality distribution: A={}, B={}, C={}, D={}, F={}",
            stats["grade_distribution"]["A"],
            stats["grade_distribution"]["B"],
            stats["grade_distribution"]["C"],
            stats["grade_distribution"]["D"],
            stats["grade_distribution"]["F"],
        )

        stats["success"] = True
        return stats

    # ========================================
    # Quality Analysis Methods
    # ========================================

    def _add_quality_metrics(self, card: dict[str, Any]) -> dict[str, Any]:
        """
        Add basic quality metrics to card data.

        Calculates:
        - Word counts (front/back)
        - Character counts (front/back)
        - Preliminary quality grade (simple heuristic)
        - Needs split flag
        """
        front = card.get("front", "")
        back = card.get("back", "")

        # Count words and characters
        front_words = len(front.split()) if front else 0
        back_words = len(back.split()) if back else 0
        front_chars = len(front) if front else 0
        back_chars = len(back) if back else 0

        # Simple quality grading heuristic
        # (Full quality analysis will be done by atomicity.py)
        quality_grade = self._calculate_preliminary_grade(
            front_words,
            back_words,
            back_chars,
        )

        # Determine if card needs splitting
        needs_split = self._needs_split_heuristic(back_words, back_chars, back)

        # Add metrics to card
        card["front_word_count"] = front_words
        card["back_word_count"] = back_words
        card["front_char_count"] = front_chars
        card["back_char_count"] = back_chars
        card["quality_grade"] = quality_grade
        card["needs_split"] = needs_split

        return card

    def _calculate_preliminary_grade(
        self,
        front_words: int,
        back_words: int,
        back_chars: int,
    ) -> str:
        """
        Calculate preliminary quality grade based on simple heuristics.

        Full analysis will be done by CardQualityAnalyzer.

        Grading:
        - A: Optimal atomicity (back 1-5 words, <100 chars)
        - B: Good atomicity (back 6-15 words, <120 chars)
        - C: Acceptable (back 16-25 words or 120-150 chars)
        - D: Verbose (back 26-40 words or 150-200 chars)
        - F: Requires split (back >40 words or >200 chars)
        """
        # Grade A: Optimal
        if back_words <= 5 and back_chars < 100:
            return "A"

        # Grade B: Good
        if back_words <= 15 and back_chars <= 120:
            return "B"

        # Grade C: Acceptable
        if back_words <= 25 and back_chars <= 150:
            return "C"

        # Grade D: Verbose
        if back_words <= 40 and back_chars <= 200:
            return "D"

        # Grade F: Requires split
        return "F"

    def _needs_split_heuristic(
        self,
        back_words: int,
        back_chars: int,
        back_text: str,
    ) -> bool:
        """
        Simple heuristic to detect cards likely needing splitting.

        Looks for:
        - Very long answers (>40 words or >200 chars)
        - Multiple sentences
        - Enumeration patterns (1., 2., 3. or bullet points)
        """
        # Very long answers
        if back_words > 40 or back_chars > 200:
            return True

        # Multiple sentences (rough heuristic)
        if back_text:
            sentence_count = back_text.count(". ") + back_text.count(".\n")
            if sentence_count > 3:
                return True

            # Enumeration patterns
            if any(pattern in back_text for pattern in ["1.", "2.", "3.", "•", "-", "*"]):
                return True

        return False

    # ========================================
    # Database Methods
    # ========================================

    def _insert_staging_card(self, card: dict[str, Any]) -> None:
        """
        Insert card into stg_anki_cards table.

        Args:
            card: Card dictionary from AnkiClient
        """
        # Extract FSRS stats if present
        fsrs_stats = card.get("fsrs_stats", {})

        # Extract prerequisite data
        prerequisites = card.get("prerequisites", {})

        # Build insert statement
        insert_sql = text("""
            INSERT INTO stg_anki_cards (
                anki_note_id,
                anki_card_id,
                card_id,
                front,
                back,
                deck_name,
                note_type,
                tags,
                raw_tags_json,
                has_prerequisites,
                prerequisite_tags,
                prerequisite_hierarchy,
                fsrs_stability_days,
                fsrs_difficulty,
                fsrs_retrievability,
                interval_days,
                ease_factor,
                review_count,
                lapses,
                last_review,
                due_date,
                queue,
                card_type,
                correct_count,
                accuracy_percent,
                quality_grade,
                front_word_count,
                back_word_count,
                front_char_count,
                back_char_count,
                needs_split,
                raw_anki_data,
                import_batch_id,
                imported_at
            ) VALUES (
                :anki_note_id,
                :anki_card_id,
                :card_id,
                :front,
                :back,
                :deck_name,
                :note_type,
                :tags,
                :raw_tags_json,
                :has_prerequisites,
                :prerequisite_tags,
                :prerequisite_hierarchy,
                :fsrs_stability_days,
                :fsrs_difficulty,
                :fsrs_retrievability,
                :interval_days,
                :ease_factor,
                :review_count,
                :lapses,
                :last_review,
                :due_date,
                :queue,
                :card_type,
                :correct_count,
                :accuracy_percent,
                :quality_grade,
                :front_word_count,
                :back_word_count,
                :front_char_count,
                :back_char_count,
                :needs_split,
                :raw_anki_data,
                :import_batch_id,
                :imported_at
            )
            ON CONFLICT (anki_note_id) DO UPDATE SET
                front = EXCLUDED.front,
                back = EXCLUDED.back,
                tags = EXCLUDED.tags,
                fsrs_stability_days = EXCLUDED.fsrs_stability_days,
                fsrs_difficulty = EXCLUDED.fsrs_difficulty,
                interval_days = EXCLUDED.interval_days,
                review_count = EXCLUDED.review_count,
                quality_grade = EXCLUDED.quality_grade,
                needs_split = EXCLUDED.needs_split,
                imported_at = EXCLUDED.imported_at
        """)

        # Execute insert
        self.db_session.execute(
            insert_sql,
            {
                "anki_note_id": int(card.get("anki_note_id", 0)),
                "anki_card_id": int(card.get("anki_card_id", 0))
                if card.get("anki_card_id")
                else None,
                "card_id": card.get("card_id"),
                "front": card.get("front"),
                "back": card.get("back"),
                "deck_name": card.get("deck_name"),
                "note_type": card.get("note_type"),
                "tags": card.get("tags", []),
                "raw_tags_json": Json(card.get("tags", [])),  # JSONB
                "has_prerequisites": prerequisites.get("has_prerequisites", False),
                "prerequisite_tags": prerequisites.get("prerequisite_tags", []),
                "prerequisite_hierarchy": Json(prerequisites.get("parsed_hierarchy", [])),  # JSONB
                "fsrs_stability_days": fsrs_stats.get("fsrs_stability_days"),
                "fsrs_difficulty": fsrs_stats.get("fsrs_difficulty"),
                "fsrs_retrievability": fsrs_stats.get("fsrs_retrievability"),
                "interval_days": fsrs_stats.get("interval_days"),
                "ease_factor": fsrs_stats.get("ease_factor"),
                "review_count": fsrs_stats.get("review_count", 0),
                "lapses": fsrs_stats.get("lapses", 0),
                "last_review": fsrs_stats.get("last_review"),
                "due_date": fsrs_stats.get("due_date"),
                "queue": fsrs_stats.get("queue"),
                "card_type": fsrs_stats.get("card_type"),
                "correct_count": fsrs_stats.get("correct_count"),
                "accuracy_percent": fsrs_stats.get("accuracy_percent"),
                "quality_grade": card.get("quality_grade"),
                "front_word_count": card.get("front_word_count"),
                "back_word_count": card.get("back_word_count"),
                "front_char_count": card.get("front_char_count"),
                "back_char_count": card.get("back_char_count"),
                "needs_split": card.get("needs_split", False),
                "raw_anki_data": Json(card),  # Wrap dict for PostgreSQL JSONB
                "import_batch_id": self.import_batch_id,
                "imported_at": datetime.utcnow(),
            },
        )

    def _create_import_log(self, deck_name: str) -> None:
        """Create import log entry in anki_import_log table."""
        insert_sql = text("""
            INSERT INTO anki_import_log (
                import_batch_id,
                deck_name,
                started_at,
                status
            ) VALUES (
                :import_batch_id,
                :deck_name,
                :started_at,
                :status
            )
        """)

        self.db_session.execute(
            insert_sql,
            {
                "import_batch_id": self.import_batch_id,
                "deck_name": deck_name,
                "started_at": datetime.utcnow(),
                "status": "running",
            },
        )
        self.db_session.commit()

    def _update_import_log(
        self,
        status: str,
        error_message: str | None = None,
        **kwargs: Any,
    ) -> None:
        """Update import log with completion status and statistics."""
        # Build SET clause dynamically
        set_fields = ["status = :status", "completed_at = :completed_at"]
        params = {
            "status": status,
            "completed_at": datetime.utcnow(),
            "import_batch_id": self.import_batch_id,
        }

        if error_message:
            set_fields.append("error_message = :error_message")
            params["error_message"] = error_message

        # Add statistics fields
        stat_fields = [
            "cards_imported",
            "cards_with_fsrs",
            "cards_with_prerequisites",
            "cards_needing_split",
            "grade_a_count",
            "grade_b_count",
            "grade_c_count",
            "grade_d_count",
            "grade_f_count",
        ]

        for field in stat_fields:
            if field in kwargs:
                set_fields.append(f"{field} = :{field}")
                if field.startswith("grade_") and "grade_distribution" in kwargs:
                    grade = field.split("_")[1].upper()
                    params[field] = kwargs["grade_distribution"].get(grade, 0)
                else:
                    params[field] = kwargs[field]

        update_sql = text(f"""
            UPDATE anki_import_log
            SET {", ".join(set_fields)}
            WHERE import_batch_id = :import_batch_id
        """)

        self.db_session.execute(update_sql, params)
        self.db_session.commit()

    # ========================================
    # Query Methods
    # ========================================

    def get_import_stats(self, batch_id: str | None = None) -> dict[str, Any] | None:
        """
        Get import statistics for a batch.

        Args:
            batch_id: Import batch ID (default: current batch)

        Returns:
            Dictionary with import statistics or None if not found
        """
        batch = batch_id or self.import_batch_id

        query_sql = text("""
            SELECT
                import_batch_id,
                deck_name,
                started_at,
                completed_at,
                status,
                cards_imported,
                cards_with_fsrs,
                cards_with_prerequisites,
                cards_needing_split,
                grade_a_count,
                grade_b_count,
                grade_c_count,
                grade_d_count,
                grade_f_count,
                error_message
            FROM anki_import_log
            WHERE import_batch_id = :batch_id
        """)

        result = self.db_session.execute(query_sql, {"batch_id": batch}).fetchone()

        if not result:
            return None

        return dict(result._mapping)
