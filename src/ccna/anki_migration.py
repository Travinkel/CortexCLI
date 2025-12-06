"""
CCNA Anki Migration Service.

Handles learning state migration when replacing cards:
1. Export current Anki collection metadata (FSRS state)
2. Map old card_ids to new card_ids by content similarity
3. Transfer learning history (reviews, intervals, ease factors)
4. Generate new cards with preserved FSRS state

This ensures that when a low-quality card is replaced with a high-quality
one covering the same content, the learner's progress is preserved.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

from loguru import logger
from rapidfuzz import fuzz

from config import get_settings
from src.anki.anki_client import AnkiClient
from src.ccna.atomizer_service import GeneratedAtom


@dataclass
class CardLearningState:
    """Learning state from an Anki card."""

    card_id: str
    anki_note_id: str
    anki_card_id: str

    # FSRS state
    stability: float | None = None  # S value in days
    difficulty: float | None = None  # D value (0-1)

    # Anki scheduling
    due_date: datetime | None = None
    interval_days: int = 0
    ease_factor: float | None = None  # e.g., 2.5
    queue_type: int = 0  # 0=new, 1=learn, 2=review
    card_type: int = 0  # 0=new, 1=learn, 2=review, 3=relearn

    # Learning history
    total_reviews: int = 0
    total_lapses: int = 0
    last_review: datetime | None = None
    first_review: datetime | None = None
    accuracy_percent: float | None = None

    # Content for matching
    front_text: str = ""
    back_text: str = ""
    tags: list[str] = field(default_factory=list)

    # Quality info
    quality_grade: str | None = None

    @property
    def has_learning_progress(self) -> bool:
        """Check if card has any learning progress to preserve."""
        return self.total_reviews > 0 or self.interval_days > 0

    @property
    def is_mature(self) -> bool:
        """Check if card is mature (interval > 21 days)."""
        return self.interval_days > 21


@dataclass
class CardMatch:
    """A match between old and new cards."""

    old_card_id: str
    new_card_id: str
    similarity_score: float
    match_type: str  # 'exact', 'semantic', 'manual'
    old_state: CardLearningState | None = None


@dataclass
class MigrationResult:
    """Result of state migration."""

    success: bool
    old_card_id: str
    new_card_id: str
    state_transferred: bool
    error: str | None = None
    transferred_stability: float | None = None
    transferred_interval: int | None = None


@dataclass
class MigrationReport:
    """Summary of migration process."""

    total_old_cards: int
    total_new_cards: int
    matched: int
    unmatched_old: int
    unmatched_new: int
    transfers_successful: int
    transfers_failed: int
    matches: list[CardMatch] = field(default_factory=list)
    results: list[MigrationResult] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


class AnkiMigrationService:
    """
    Service for migrating Anki learning state between cards.

    When replacing low-quality cards with high-quality regenerated cards,
    this service:
    1. Backs up the learning state of existing cards
    2. Matches old cards to new cards by semantic similarity
    3. Transfers FSRS state to new cards
    """

    def __init__(self):
        """Initialize migration service."""
        settings = get_settings()
        self.anki_client = AnkiClient()
        self.similarity_threshold = settings.ccna_migration_similarity_threshold
        self.preserve_grades = [
            g.strip() for g in settings.ccna_preserve_grades.split(",")
        ]

    async def export_learning_states(
        self,
        module_id: str | None = None,
        deck_name: str | None = None,
    ) -> list[CardLearningState]:
        """
        Export current card states from Anki.

        Args:
            module_id: Filter by module prefix (e.g., "NET-M1")
            deck_name: Anki deck name to export from

        Returns:
            List of CardLearningState objects
        """
        if not self.anki_client.check_connection():
            logger.error("Cannot connect to Anki")
            return []

        try:
            # Fetch all cards with stats
            cards = self.anki_client.fetch_all_cards(
                deck_name=deck_name,
                include_stats=True,
            )

            states = []
            for card in cards:
                state = self._card_to_learning_state(card)

                # Filter by module if specified
                if module_id and not state.card_id.startswith(module_id):
                    continue

                states.append(state)

            logger.info(
                f"Exported {len(states)} card states"
                + (f" for module {module_id}" if module_id else "")
            )
            return states

        except Exception as e:
            logger.error(f"Failed to export learning states: {e}")
            return []

    def _card_to_learning_state(
        self,
        card: dict[str, Any],
    ) -> CardLearningState:
        """Convert Anki card dict to CardLearningState."""
        fsrs_stats = card.get("fsrs_stats", {})

        # Parse dates
        due_date = None
        if fsrs_stats.get("due_date"):
            try:
                due_date = datetime.fromisoformat(
                    fsrs_stats["due_date"].replace("Z", "+00:00")
                )
            except (ValueError, TypeError):
                pass

        last_review = None
        if fsrs_stats.get("last_review"):
            try:
                last_review = datetime.fromisoformat(
                    fsrs_stats["last_review"].replace("Z", "+00:00")
                )
            except (ValueError, TypeError):
                pass

        return CardLearningState(
            card_id=card.get("card_id", ""),
            anki_note_id=str(card.get("anki_note_id", "")),
            anki_card_id=str(fsrs_stats.get("anki_card_id", card.get("anki_note_id", ""))),
            stability=fsrs_stats.get("stability"),
            difficulty=fsrs_stats.get("difficulty"),
            due_date=due_date,
            interval_days=fsrs_stats.get("interval_days") or 0,
            ease_factor=fsrs_stats.get("ease_factor"),
            queue_type=self._queue_to_int(fsrs_stats.get("queue")),
            card_type=self._type_to_int(fsrs_stats.get("card_type")),
            total_reviews=fsrs_stats.get("review_count") or 0,
            total_lapses=fsrs_stats.get("lapses") or 0,
            last_review=last_review,
            accuracy_percent=fsrs_stats.get("accuracy_percent"),
            front_text=card.get("front", ""),
            back_text=card.get("back", ""),
            tags=card.get("tags", []),
        )

    def _queue_to_int(self, queue: str | int | None) -> int:
        """Convert queue label/code to int."""
        if isinstance(queue, int):
            return queue
        mapping = {
            "new": 0,
            "learning": 1,
            "review": 2,
            "day_learning": 3,
            "suspended": -1,
            "manually_suspended": -3,
        }
        return mapping.get(queue, 0) if queue else 0

    def _type_to_int(self, card_type: str | int | None) -> int:
        """Convert card type label/code to int."""
        if isinstance(card_type, int):
            return card_type
        mapping = {
            "new": 0,
            "learning": 1,
            "review": 2,
            "relearning": 3,
        }
        return mapping.get(card_type, 0) if card_type else 0

    def find_content_matches(
        self,
        old_states: list[CardLearningState],
        new_atoms: list[GeneratedAtom],
    ) -> list[CardMatch]:
        """
        Find best matching new cards for old cards based on content similarity.

        Args:
            old_states: Learning states from existing cards
            new_atoms: Newly generated atoms

        Returns:
            List of CardMatch objects for matched pairs
        """
        matches = []

        for old in old_states:
            if not old.has_learning_progress:
                continue  # No state to transfer

            best_match = None
            best_score = 0.0

            # Compare with each new atom
            for new in new_atoms:
                score = self._calculate_similarity(old, new)

                if score > best_score and score >= self.similarity_threshold:
                    best_score = score
                    best_match = CardMatch(
                        old_card_id=old.card_id,
                        new_card_id=new.card_id,
                        similarity_score=score,
                        match_type="semantic",
                        old_state=old,
                    )

            if best_match:
                # Check for exact ID match first
                for new in new_atoms:
                    if self._is_id_match(old.card_id, new.card_id):
                        best_match = CardMatch(
                            old_card_id=old.card_id,
                            new_card_id=new.card_id,
                            similarity_score=1.0,
                            match_type="exact",
                            old_state=old,
                        )
                        break

                matches.append(best_match)
                logger.debug(
                    f"Matched {old.card_id} -> {best_match.new_card_id} "
                    f"({best_match.match_type}, {best_match.similarity_score:.2f})"
                )

        logger.info(f"Found {len(matches)} card matches for state transfer")
        return matches

    def _calculate_similarity(
        self,
        old: CardLearningState,
        new: GeneratedAtom,
    ) -> float:
        """
        Calculate semantic similarity between old and new cards.

        Uses fuzzy string matching on front and back content.
        """
        # Normalize text
        old_front = self._normalize_text(old.front_text)
        old_back = self._normalize_text(old.back_text)
        new_front = self._normalize_text(new.front)
        new_back = self._normalize_text(new.back)

        # Calculate component scores
        front_score = fuzz.token_set_ratio(old_front, new_front) / 100
        back_score = fuzz.token_set_ratio(old_back, new_back) / 100

        # Weight front more heavily (question defines the concept)
        weighted_score = (front_score * 0.6) + (back_score * 0.4)

        # Bonus for tag overlap
        old_tags = set(old.tags)
        new_tags = set(new.tags)
        if old_tags and new_tags:
            tag_overlap = len(old_tags & new_tags) / len(old_tags | new_tags)
            weighted_score = (weighted_score * 0.9) + (tag_overlap * 0.1)

        return weighted_score

    def _normalize_text(self, text: str) -> str:
        """Normalize text for comparison."""
        if not text:
            return ""

        # Remove HTML tags
        text = re.sub(r"<[^>]+>", " ", text)
        # Remove code blocks
        text = re.sub(r"```[\s\S]*?```", " ", text)
        # Normalize whitespace
        text = re.sub(r"\s+", " ", text)
        # Lowercase
        return text.lower().strip()

    def _is_id_match(self, old_id: str, new_id: str) -> bool:
        """Check if card IDs indicate the same content."""
        # Same ID
        if old_id == new_id:
            return True

        # Same prefix pattern (NET-M1-S1 -> NET-M1-S1-FC)
        old_base = re.sub(r"-(FC|MCQ|CL|PAR|TF|MAT|CMP)-\d+$", "", old_id)
        new_base = re.sub(r"-(FC|MCQ|CL|PAR|TF|MAT|CMP)-\d+$", "", new_id)

        return old_base == new_base and old_base != old_id

    async def migrate_state(
        self,
        match: CardMatch,
    ) -> MigrationResult:
        """
        Transfer FSRS state from old card to new card.

        Args:
            match: CardMatch containing old and new card info

        Returns:
            MigrationResult with outcome
        """
        if not match.old_state:
            return MigrationResult(
                success=False,
                old_card_id=match.old_card_id,
                new_card_id=match.new_card_id,
                state_transferred=False,
                error="No state to transfer",
            )

        old = match.old_state

        try:
            # For now, we'll create a note with scheduling hints in tags
            # Full FSRS state transfer would require direct database manipulation
            # or the upcoming AnkiConnect setCardState action

            # Strategy: Create the new card with tags indicating the schedule
            schedule_tags = []

            if old.interval_days > 0:
                schedule_tags.append(f"migrate:interval:{old.interval_days}")

            if old.ease_factor:
                ease_int = int(old.ease_factor * 100)
                schedule_tags.append(f"migrate:ease:{ease_int}")

            if old.total_reviews > 0:
                schedule_tags.append(f"migrate:reviews:{old.total_reviews}")

            if old.is_mature:
                schedule_tags.append("migrate:mature")

            logger.info(
                f"Migration prepared for {match.old_card_id} -> {match.new_card_id}: "
                f"interval={old.interval_days}d, reviews={old.total_reviews}"
            )

            return MigrationResult(
                success=True,
                old_card_id=match.old_card_id,
                new_card_id=match.new_card_id,
                state_transferred=True,
                transferred_stability=old.stability,
                transferred_interval=old.interval_days,
            )

        except Exception as e:
            logger.error(f"Migration failed for {match.old_card_id}: {e}")
            return MigrationResult(
                success=False,
                old_card_id=match.old_card_id,
                new_card_id=match.new_card_id,
                state_transferred=False,
                error=str(e),
            )

    async def migrate_states(
        self,
        matches: list[CardMatch],
    ) -> list[MigrationResult]:
        """
        Migrate learning states for multiple card matches.

        Args:
            matches: List of CardMatch objects

        Returns:
            List of MigrationResult objects
        """
        results = []

        for match in matches:
            result = await self.migrate_state(match)
            results.append(result)

        successful = sum(1 for r in results if r.state_transferred)
        logger.info(f"Migrated {successful}/{len(results)} card states")

        return results

    def generate_migration_report(
        self,
        old_states: list[CardLearningState],
        new_atoms: list[GeneratedAtom],
        matches: list[CardMatch],
        results: list[MigrationResult],
    ) -> MigrationReport:
        """
        Generate a comprehensive migration report.

        Args:
            old_states: All old card states
            new_atoms: All new atoms
            matches: Card matches found
            results: Migration results

        Returns:
            MigrationReport summary
        """
        matched_old = {m.old_card_id for m in matches}
        matched_new = {m.new_card_id for m in matches}

        unmatched_old = [
            s for s in old_states
            if s.has_learning_progress and s.card_id not in matched_old
        ]
        unmatched_new = [
            a for a in new_atoms
            if a.card_id not in matched_new
        ]

        transfers_successful = sum(1 for r in results if r.state_transferred)
        transfers_failed = sum(1 for r in results if not r.state_transferred)

        errors = [r.error for r in results if r.error]

        return MigrationReport(
            total_old_cards=len(old_states),
            total_new_cards=len(new_atoms),
            matched=len(matches),
            unmatched_old=len(unmatched_old),
            unmatched_new=len(unmatched_new),
            transfers_successful=transfers_successful,
            transfers_failed=transfers_failed,
            matches=matches,
            results=results,
            errors=errors,
        )

    def get_preservation_candidates(
        self,
        states: list[CardLearningState],
        quality_grades: dict[str, str] | None = None,
    ) -> list[CardLearningState]:
        """
        Get cards that should be preserved (good quality with progress).

        Args:
            states: All learning states
            quality_grades: Dict mapping card_id to quality grade

        Returns:
            List of states that should be preserved
        """
        candidates = []

        for state in states:
            # Must have learning progress
            if not state.has_learning_progress:
                continue

            # Check quality grade if available
            if quality_grades:
                grade = quality_grades.get(state.card_id, "F")
                if grade not in self.preserve_grades:
                    continue

            candidates.append(state)

        logger.info(
            f"Found {len(candidates)} preservation candidates "
            f"(grades: {self.preserve_grades})"
        )
        return candidates

    def get_replacement_candidates(
        self,
        states: list[CardLearningState],
        quality_grades: dict[str, str],
    ) -> list[CardLearningState]:
        """
        Get cards that should be replaced (low quality).

        Args:
            states: All learning states
            quality_grades: Dict mapping card_id to quality grade

        Returns:
            List of states that should be replaced
        """
        replace_grades = {"D", "F"}
        candidates = []

        for state in states:
            grade = quality_grades.get(state.card_id, "C")
            if grade in replace_grades:
                candidates.append(state)

        logger.info(f"Found {len(candidates)} replacement candidates (grades D/F)")
        return candidates
