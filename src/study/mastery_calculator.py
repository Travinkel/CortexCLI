"""
Mastery Calculator for CCNA Study Path.

Calculates mastery scores based on multiple signals:
- Anki FSRS metrics (retrievability, stability, lapses)
- MCQ performance
- Quiz results (True/False, Matching, Parsons)

Mastery threshold: 90% retrievability + <2 average lapses
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class MasteryMetrics:
    """Mastery metrics for a section or atom."""

    avg_retrievability: float
    avg_stability_days: float
    avg_lapses: float
    mcq_score: float | None
    atoms_total: int
    atoms_mastered: int
    atoms_learning: int
    atoms_struggling: int
    atoms_new: int


@dataclass
class MasteryResult:
    """Result of mastery calculation."""

    mastery_score: float  # 0-100
    is_mastered: bool
    needs_remediation: bool
    remediation_reason: str | None
    remediation_priority: int


class MasteryCalculator:
    """
    Calculates mastery scores and remediation needs.

    Evidence-based thresholds:
    - Mastery: 90% retrievability + <2 lapses average
    - Remediation trigger: <70% retrievability OR >3 lapses OR <80% MCQ
    """

    # Mastery thresholds
    MASTERY_RETRIEVABILITY = 0.90
    MASTERY_MAX_LAPSES = 2.0

    # Remediation thresholds
    REMEDIATION_MIN_RETRIEVABILITY = 0.70
    REMEDIATION_MAX_LAPSES = 3.0
    REMEDIATION_MIN_MCQ = 0.80

    # Score weights
    WEIGHT_RETRIEVABILITY = 0.40
    WEIGHT_LAPSE_RATE = 0.25
    WEIGHT_MCQ = 0.25
    WEIGHT_BUFFER = 0.10

    def __init__(
        self,
        mastery_retrievability: float = 0.90,
        mastery_max_lapses: float = 2.0,
        remediation_min_retrievability: float = 0.70,
        remediation_max_lapses: float = 3.0,
        remediation_min_mcq: float = 0.80,
    ):
        """
        Initialize calculator with configurable thresholds.

        Args:
            mastery_retrievability: Min retrievability for mastery (default 90%)
            mastery_max_lapses: Max average lapses for mastery (default 2)
            remediation_min_retrievability: Below this triggers remediation (default 70%)
            remediation_max_lapses: Above this triggers remediation (default 3)
            remediation_min_mcq: Below this MCQ score triggers remediation (default 80%)
        """
        self.mastery_retrievability = mastery_retrievability
        self.mastery_max_lapses = mastery_max_lapses
        self.remediation_min_retrievability = remediation_min_retrievability
        self.remediation_max_lapses = remediation_max_lapses
        self.remediation_min_mcq = remediation_min_mcq

    def calculate_mastery_score(
        self,
        avg_retrievability: float | None,
        avg_lapses: float | None,
        mcq_score: float | None,
    ) -> float:
        """
        Calculate composite mastery score (0-100).

        Formula:
            40% × retrievability +
            25% × (1 - lapse_rate) +
            25% × MCQ_score +
            10% buffer

        Args:
            avg_retrievability: Average FSRS retrievability (0-1)
            avg_lapses: Average lapses per atom
            mcq_score: MCQ performance percentage (0-100)

        Returns:
            Mastery score 0-100
        """
        # Convert retrievability to percentage
        ret_score = (avg_retrievability or 0.5) * 100

        # Convert lapses to inverse rate (fewer lapses = higher score)
        # Cap at 5 lapses = 0 score
        lapse_rate = min((avg_lapses or 0) / 5.0, 1.0)
        lapse_score = (1 - lapse_rate) * 100

        # MCQ score (default to 50% if not available)
        mcq = mcq_score or 50

        # Weighted composite
        score = (
            ret_score * self.WEIGHT_RETRIEVABILITY
            + lapse_score * self.WEIGHT_LAPSE_RATE
            + mcq * self.WEIGHT_MCQ
            + 10  # Buffer
        )

        return min(max(score, 0), 100)

    def check_mastery(
        self,
        avg_retrievability: float | None,
        avg_lapses: float | None,
    ) -> bool:
        """
        Check if section meets mastery threshold.

        Mastery requires:
        - 90%+ average retrievability
        - <2 average lapses per atom

        Args:
            avg_retrievability: Average FSRS retrievability (0-1)
            avg_lapses: Average lapses per atom

        Returns:
            True if mastered
        """
        ret = avg_retrievability or 0
        lapses = avg_lapses or 0

        return ret >= self.mastery_retrievability and lapses < self.mastery_max_lapses

    def check_remediation(
        self,
        avg_retrievability: float | None,
        avg_lapses: float | None,
        mcq_score: float | None,
    ) -> tuple[bool, str | None, int]:
        """
        Check if section needs remediation.

        Remediation triggers:
        - Retrievability <70%
        - Lapses >3 average
        - MCQ score <80%

        Args:
            avg_retrievability: Average FSRS retrievability (0-1)
            avg_lapses: Average lapses per atom
            mcq_score: MCQ performance percentage (0-100)

        Returns:
            Tuple of (needs_remediation, reason, priority)
        """
        needs_remediation = False
        reasons = []
        priority = 0

        ret = avg_retrievability if avg_retrievability is not None else 1.0
        lapses = avg_lapses if avg_lapses is not None else 0
        mcq = mcq_score if mcq_score is not None else 100

        # Check retrievability
        if ret < self.remediation_min_retrievability:
            needs_remediation = True
            reasons.append("low_retrievability")
            priority += 3

        # Check lapses
        if lapses > self.remediation_max_lapses:
            needs_remediation = True
            reasons.append("high_lapses")
            priority += 2

        # Check MCQ
        if mcq < self.remediation_min_mcq * 100:
            needs_remediation = True
            reasons.append("low_mcq")
            priority += 1

        # Determine final reason
        if len(reasons) > 1:
            reason = "combined"
        elif len(reasons) == 1:
            reason = reasons[0]
        else:
            reason = None

        return needs_remediation, reason, priority

    def calculate(self, metrics: MasteryMetrics) -> MasteryResult:
        """
        Calculate complete mastery result from metrics.

        Args:
            metrics: MasteryMetrics with all available data

        Returns:
            MasteryResult with score, status, and recommendations
        """
        # Calculate mastery score
        mastery_score = self.calculate_mastery_score(
            metrics.avg_retrievability,
            metrics.avg_lapses,
            metrics.mcq_score,
        )

        # Check mastery status
        is_mastered = self.check_mastery(
            metrics.avg_retrievability,
            metrics.avg_lapses,
        )

        # Check remediation need
        needs_remediation, reason, priority = self.check_remediation(
            metrics.avg_retrievability,
            metrics.avg_lapses,
            metrics.mcq_score,
        )

        return MasteryResult(
            mastery_score=round(mastery_score, 2),
            is_mastered=is_mastered,
            needs_remediation=needs_remediation,
            remediation_reason=reason,
            remediation_priority=priority,
        )

    def get_status_emoji(self, result: MasteryResult) -> str:
        """Get status emoji for display."""
        if result.is_mastered:
            return "✓"  # Mastered
        elif result.needs_remediation:
            return "⚠️"  # Needs remediation
        else:
            return ""  # Learning

    def get_status_color(self, result: MasteryResult) -> str:
        """Get Rich color for status display."""
        if result.is_mastered:
            return "green"
        elif result.needs_remediation:
            return "red"
        elif result.mastery_score >= 70:
            return "yellow"
        else:
            return "dim"

    def format_progress_bar(
        self,
        mastery_score: float,
        width: int = 10,
    ) -> str:
        """
        Format a text-based progress bar.

        Args:
            mastery_score: Score 0-100
            width: Character width of bar

        Returns:
            String like "████████░░" (80%)
        """
        filled = int(mastery_score / 100 * width)
        empty = width - filled
        return "█" * filled + "░" * empty
