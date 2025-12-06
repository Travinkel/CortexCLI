"""
Adaptive Interleaver for CCNA Study Path.

Implements adaptive interleaving algorithm that mixes:
- Due Anki reviews (highest priority)
- New content from next section in path
- Remediation cards from struggling sections

Default ratio when struggling areas exist:
- 70% new content
- 30% remediation

Ratio increases with more struggling sections (capped at 50% remediation).
"""
from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Optional

from loguru import logger


@dataclass
class StudyCard:
    """A card in the study queue."""
    atom_id: str
    card_id: str
    front: str
    back: str
    atom_type: str
    section_id: str
    source: str  # 'due', 'new', 'remediation'
    priority: int = 0


@dataclass
class StudyQueue:
    """Complete study queue for a session."""
    due_reviews: list[StudyCard] = field(default_factory=list)
    new_cards: list[StudyCard] = field(default_factory=list)
    remediation_cards: list[StudyCard] = field(default_factory=list)

    @property
    def total_cards(self) -> int:
        return len(self.due_reviews) + len(self.new_cards) + len(self.remediation_cards)

    @property
    def estimated_minutes(self) -> int:
        """Estimate study time (30 seconds per card average)."""
        return max(1, self.total_cards // 2)


@dataclass
class InterleaveConfig:
    """Configuration for interleaving algorithm."""
    base_remediation_ratio: float = 0.30
    max_remediation_ratio: float = 0.50
    sections_for_max_ratio: int = 5
    new_cards_per_session: int = 30
    max_remediation_cards: int = 15


class AdaptiveInterleaver:
    """
    Implements adaptive interleaving for study sessions.

    The algorithm:
    1. Always include all due Anki reviews
    2. Calculate remediation ratio based on struggling sections
    3. Mix new content and remediation cards
    4. Interleave (not blocked) for better retention
    """

    def __init__(self, config: Optional[InterleaveConfig] = None):
        """
        Initialize interleaver with configuration.

        Args:
            config: InterleaveConfig or None for defaults
        """
        self.config = config or InterleaveConfig()

    def calculate_remediation_ratio(
        self,
        struggling_sections: int,
    ) -> float:
        """
        Calculate remediation ratio based on struggling sections.

        Args:
            struggling_sections: Number of sections needing remediation

        Returns:
            Ratio of remediation cards (0.0 to max_ratio)
        """
        if struggling_sections == 0:
            return 0.0

        if struggling_sections >= self.config.sections_for_max_ratio:
            return self.config.max_remediation_ratio

        # Linear interpolation
        ratio = (
            self.config.base_remediation_ratio +
            (self.config.max_remediation_ratio - self.config.base_remediation_ratio) *
            (struggling_sections / self.config.sections_for_max_ratio)
        )

        return min(ratio, self.config.max_remediation_ratio)

    def build_queue(
        self,
        due_reviews: list[StudyCard],
        available_new: list[StudyCard],
        remediation_pool: list[StudyCard],
        struggling_section_count: int,
    ) -> StudyQueue:
        """
        Build a study queue with adaptive interleaving.

        Args:
            due_reviews: Cards due for review today
            available_new: New cards from next section(s)
            remediation_pool: Cards from struggling sections
            struggling_section_count: Number of sections needing remediation

        Returns:
            StudyQueue with interleaved cards
        """
        queue = StudyQueue()

        # 1. Due reviews always included
        queue.due_reviews = due_reviews.copy()

        # 2. Calculate remediation ratio
        ratio = self.calculate_remediation_ratio(struggling_section_count)

        # 3. Calculate card counts
        total_non_due = self.config.new_cards_per_session
        remediation_count = int(total_non_due * ratio)
        new_count = total_non_due - remediation_count

        # Cap remediation
        remediation_count = min(
            remediation_count,
            self.config.max_remediation_cards,
            len(remediation_pool)
        )

        # Adjust new count if we have fewer remediation cards
        if remediation_count < int(total_non_due * ratio):
            new_count = total_non_due - remediation_count

        new_count = min(new_count, len(available_new))

        # 4. Select cards
        queue.new_cards = available_new[:new_count]

        # Select remediation cards (prioritize by section priority)
        sorted_remediation = sorted(
            remediation_pool,
            key=lambda c: c.priority,
            reverse=True
        )
        queue.remediation_cards = sorted_remediation[:remediation_count]

        logger.info(
            f"Built study queue: {len(queue.due_reviews)} due, "
            f"{len(queue.new_cards)} new, {len(queue.remediation_cards)} remediation "
            f"(ratio: {ratio:.0%})"
        )

        return queue

    def interleave(self, queue: StudyQueue) -> list[StudyCard]:
        """
        Interleave cards from the queue for optimal learning.

        Due reviews come first, then new/remediation are mixed.

        Args:
            queue: StudyQueue to interleave

        Returns:
            List of cards in study order
        """
        result = []

        # Due reviews first (in their original order)
        result.extend(queue.due_reviews)

        # Mix new and remediation
        mixed = queue.new_cards + queue.remediation_cards
        random.shuffle(mixed)

        result.extend(mixed)

        return result

    def get_session_summary(self, queue: StudyQueue) -> dict:
        """
        Get summary of study session.

        Args:
            queue: StudyQueue to summarize

        Returns:
            Dictionary with session stats
        """
        return {
            "total_cards": queue.total_cards,
            "due_reviews": len(queue.due_reviews),
            "new_cards": len(queue.new_cards),
            "remediation_cards": len(queue.remediation_cards),
            "estimated_minutes": queue.estimated_minutes,
            "remediation_ratio": (
                len(queue.remediation_cards) /
                (len(queue.new_cards) + len(queue.remediation_cards))
                if (len(queue.new_cards) + len(queue.remediation_cards)) > 0
                else 0
            ),
        }
