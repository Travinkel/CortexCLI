"""
Core Mastery Module.

Provides unified mastery calculation interfaces and implementations.
Both adaptive and study modules should use these base classes.

Design:
- MasteryLevel: Enum for categorizing mastery scores
- ConceptMastery: Dataclass for full mastery state
- MasteryCalculator: Base class with common FSRS formulas
- SimpleMasteryCalculator: Lightweight calculator without DB
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Protocol
from uuid import UUID


class MasteryLevel(str, Enum):
    """
    Mastery level categorization.

    Aligned with learning science research on skill acquisition stages.
    """

    NOT_STARTED = "not_started"  # 0%
    NOVICE = "novice"  # 1-39%
    DEVELOPING = "developing"  # 40-69%
    PROFICIENT = "proficient"  # 70-89%
    MASTERED = "mastered"  # 90-100%

    @classmethod
    def from_score(cls, score: float) -> MasteryLevel:
        """
        Convert a 0-1 mastery score to a level.

        Args:
            score: Mastery score between 0 and 1

        Returns:
            Corresponding MasteryLevel
        """
        if score <= 0:
            return cls.NOT_STARTED
        elif score < 0.4:
            return cls.NOVICE
        elif score < 0.7:
            return cls.DEVELOPING
        elif score < 0.9:
            return cls.PROFICIENT
        else:
            return cls.MASTERED

    @property
    def display_name(self) -> str:
        """Human-readable name."""
        return self.value.replace("_", " ").title()

    @property
    def emoji(self) -> str:
        """Status emoji for CLI/UI display."""
        return {
            MasteryLevel.NOT_STARTED: "○",
            MasteryLevel.NOVICE: "◔",
            MasteryLevel.DEVELOPING: "◑",
            MasteryLevel.PROFICIENT: "◕",
            MasteryLevel.MASTERED: "●",
        }[self]

    @property
    def color(self) -> str:
        """Rich color for CLI display."""
        return {
            MasteryLevel.NOT_STARTED: "dim",
            MasteryLevel.NOVICE: "red",
            MasteryLevel.DEVELOPING: "yellow",
            MasteryLevel.PROFICIENT: "cyan",
            MasteryLevel.MASTERED: "green",
        }[self]


@dataclass
class KnowledgeBreakdown:
    """
    Mastery breakdown by knowledge type.

    Based on Revised Bloom's Taxonomy mapped to learning activities.
    """

    declarative: float = 0.0  # Facts, terminology (Flashcards, T/F)
    procedural: float = 0.0  # How-to, commands (Parsons, CLI)
    conceptual: float = 0.0  # Relationships, principles (MCQ, Matching)

    @property
    def average(self) -> float:
        """Average across all knowledge types."""
        return (self.declarative + self.procedural + self.conceptual) / 3

    def to_dict(self) -> dict[str, float]:
        """Convert to dictionary."""
        return {
            "declarative": self.declarative,
            "procedural": self.procedural,
            "conceptual": self.conceptual,
        }


@dataclass
class ConceptMastery:
    """
    Full mastery state for a concept.

    This is the canonical representation used across the system.
    """

    concept_id: UUID | None = None
    concept_name: str = ""

    # Core mastery scores (0-1)
    review_mastery: float = 0.0  # From FSRS retrievability
    quiz_mastery: float = 0.0  # From quiz performance
    combined_mastery: float = 0.0  # Weighted combination

    # Knowledge type breakdown
    knowledge_breakdown: KnowledgeBreakdown = field(default_factory=KnowledgeBreakdown)

    # Status
    level: MasteryLevel = MasteryLevel.NOT_STARTED
    is_unlocked: bool = True
    unlock_reason: str | None = None

    # Activity counts
    review_count: int = 0
    quiz_attempt_count: int = 0
    last_review_at: datetime | None = None
    last_quiz_at: datetime | None = None

    def __post_init__(self):
        """Compute level from combined mastery."""
        self.level = MasteryLevel.from_score(self.combined_mastery)

    @property
    def is_mastered(self) -> bool:
        """Check if concept is mastered (90%+)."""
        return self.combined_mastery >= 0.9

    @property
    def needs_remediation(self) -> bool:
        """Check if concept needs remediation (<70%)."""
        return self.combined_mastery < 0.7

    @property
    def mastery_percentage(self) -> float:
        """Mastery as percentage (0-100)."""
        return self.combined_mastery * 100


# ============================================================================
# FSRS Formulas
# ============================================================================


def calculate_retrievability(stability_days: float, days_since_review: float) -> float:
    """
    Calculate FSRS retrievability.

    Formula: R = e^(-t/S)

    Where:
        R = retrievability (probability of recall)
        t = time since last review in days
        S = stability in days

    Args:
        stability_days: FSRS stability (days until 90% forgetting)
        days_since_review: Days elapsed since last review

    Returns:
        Retrievability between 0 and 1
    """
    if stability_days <= 0:
        return 0.0
    return math.exp(-days_since_review / stability_days)


def calculate_days_since(last_review: datetime | None, now: datetime | None = None) -> float:
    """
    Calculate days elapsed since a review.

    Args:
        last_review: Timestamp of last review (can be naive or aware)
        now: Current time (defaults to UTC now)

    Returns:
        Days elapsed as float
    """
    if last_review is None:
        return 30.0  # Default assumption for never-reviewed

    if now is None:
        now = datetime.now(UTC)

    # Handle timezone awareness
    if last_review.tzinfo is None:
        last_review = last_review.replace(tzinfo=UTC)
    if now.tzinfo is None:
        now = now.replace(tzinfo=UTC)

    delta = now - last_review
    return delta.total_seconds() / 86400.0


# ============================================================================
# Mastery Calculator Interface
# ============================================================================


class IMasteryCalculator(Protocol):
    """Interface for mastery calculators."""

    def calculate_mastery_score(
        self,
        retrievability: float,
        quiz_score: float | None = None,
        **kwargs,
    ) -> float:
        """Calculate combined mastery score."""
        ...


class MasteryCalculator:
    """
    Base mastery calculator with FSRS integration.

    Formula: combined = (review × weight_review) + (quiz × weight_quiz)

    Default weights based on learning science research:
    - 62.5% review (spaced repetition effectiveness)
    - 37.5% quiz (active recall + transfer testing)
    """

    # Default weights (can be overridden)
    WEIGHT_REVIEW = 0.625
    WEIGHT_QUIZ = 0.375

    def __init__(
        self,
        weight_review: float = 0.625,
        weight_quiz: float = 0.375,
    ):
        """
        Initialize calculator with weights.

        Args:
            weight_review: Weight for review mastery (default 62.5%)
            weight_quiz: Weight for quiz mastery (default 37.5%)
        """
        self.weight_review = weight_review
        self.weight_quiz = weight_quiz

    def calculate_combined_mastery(
        self,
        review_mastery: float,
        quiz_mastery: float,
    ) -> float:
        """
        Calculate weighted combined mastery.

        Args:
            review_mastery: Review mastery 0-1
            quiz_mastery: Quiz mastery 0-1

        Returns:
            Combined mastery 0-1
        """
        return review_mastery * self.weight_review + quiz_mastery * self.weight_quiz

    def calculate_review_mastery(
        self,
        atoms: list[dict],
    ) -> float:
        """
        Calculate review mastery from atom FSRS data.

        Uses weighted average where weight = min(review_count, 20).

        Args:
            atoms: List of dicts with keys:
                - stability_days: FSRS stability
                - last_review: datetime of last review
                - review_count: number of reviews

        Returns:
            Review mastery 0-1
        """
        if not atoms:
            return 0.0

        total_weight = 0.0
        weighted_sum = 0.0
        now = datetime.now(UTC)

        for atom in atoms:
            stability = atom.get("stability_days", 0)
            if stability <= 0:
                continue

            days_since = calculate_days_since(atom.get("last_review"), now)
            retrievability = calculate_retrievability(stability, days_since)

            # Weight by review count (capped at 20)
            review_count = atom.get("review_count", 1)
            weight = min(review_count, 20) if review_count > 0 else 1

            weighted_sum += retrievability * weight
            total_weight += weight

        if total_weight > 0:
            return weighted_sum / total_weight
        return 0.0

    def calculate_quiz_mastery(
        self,
        scores: list[float],
        method: str = "best_of_3",
    ) -> float:
        """
        Calculate quiz mastery from quiz scores.

        Args:
            scores: List of quiz scores (0-1), most recent first
            method: Aggregation method:
                - "best_of_3": Best score from last 3 attempts
                - "average": Simple average of all scores
                - "weighted_recent": More weight to recent scores

        Returns:
            Quiz mastery 0-1
        """
        if not scores:
            return 0.0

        if method == "best_of_3":
            return max(scores[:3])
        elif method == "average":
            return sum(scores) / len(scores)
        elif method == "weighted_recent":
            # Exponential decay: most recent gets weight 1, older gets less
            total_weight = 0.0
            weighted_sum = 0.0
            for i, score in enumerate(scores):
                weight = 0.5**i  # 1, 0.5, 0.25, 0.125, ...
                weighted_sum += score * weight
                total_weight += weight
            return weighted_sum / total_weight if total_weight > 0 else 0.0
        else:
            return max(scores[:3])  # Default to best_of_3


class SimpleMasteryCalculator(MasteryCalculator):
    """
    Simplified mastery calculator without database access.

    Uses a different formula optimized for quick calculations:
    - 40% retrievability
    - 25% lapse rate (inverted)
    - 25% MCQ score
    - 10% buffer

    Suitable for CLI displays and quick assessments.
    """

    # Thresholds
    MASTERY_THRESHOLD = 0.90
    MASTERY_MAX_LAPSES = 2.0
    REMEDIATION_THRESHOLD = 0.70
    REMEDIATION_MAX_LAPSES = 3.0

    def __init__(self):
        """Initialize with simplified weights."""
        super().__init__(weight_review=0.4, weight_quiz=0.25)

    def calculate_mastery_score(
        self,
        retrievability: float | None = None,
        lapses: float | None = None,
        mcq_score: float | None = None,
    ) -> float:
        """
        Calculate simplified mastery score (0-100).

        Formula:
            40% × retrievability +
            25% × (1 - lapse_rate) +
            25% × MCQ_score +
            10% buffer

        Args:
            retrievability: Average FSRS retrievability (0-1)
            lapses: Average lapses per atom
            mcq_score: MCQ performance (0-100)

        Returns:
            Mastery score 0-100
        """
        # Retrievability component (0-40 points)
        ret = (retrievability or 0.5) * 100 * 0.40

        # Lapse component - fewer lapses = higher score (0-25 points)
        lapse_rate = min((lapses or 0) / 5.0, 1.0)
        lapse_score = (1 - lapse_rate) * 100 * 0.25

        # MCQ component (0-25 points)
        mcq = (mcq_score or 50) * 0.25

        # Buffer (10 points)
        buffer = 10

        return min(max(ret + lapse_score + mcq + buffer, 0), 100)

    def check_mastery(
        self,
        retrievability: float | None,
        lapses: float | None,
    ) -> bool:
        """
        Check if content is mastered.

        Requires:
        - 90%+ retrievability
        - <2 average lapses
        """
        ret = retrievability or 0
        lap = lapses or 0
        return ret >= self.MASTERY_THRESHOLD and lap < self.MASTERY_MAX_LAPSES

    def check_remediation(
        self,
        retrievability: float | None,
        lapses: float | None,
        mcq_score: float | None = None,
    ) -> tuple[bool, str | None]:
        """
        Check if content needs remediation.

        Triggers:
        - Retrievability <70%
        - Lapses >3 average
        - MCQ <80%

        Returns:
            Tuple of (needs_remediation, reason)
        """
        reasons = []

        if (retrievability or 1.0) < self.REMEDIATION_THRESHOLD:
            reasons.append("low_retrievability")

        if (lapses or 0) > self.REMEDIATION_MAX_LAPSES:
            reasons.append("high_lapses")

        if mcq_score is not None and mcq_score < 80:
            reasons.append("low_mcq")

        if reasons:
            return True, "_".join(reasons) if len(reasons) > 1 else reasons[0]
        return False, None

    def get_level(self, score: float) -> MasteryLevel:
        """Get mastery level from score (0-100)."""
        return MasteryLevel.from_score(score / 100)

    def format_progress_bar(self, score: float, width: int = 10) -> str:
        """
        Format a text progress bar.

        Args:
            score: Score 0-100
            width: Character width

        Returns:
            String like "████████░░"
        """
        filled = int(score / 100 * width)
        empty = width - filled
        return "█" * filled + "░" * empty
