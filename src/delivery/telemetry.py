"""
Session Telemetry and Fatigue Detection.

Tracks real-time performance metrics during study sessions:
- Response time trends
- Accuracy over time
- Confidence patterns
- Fatigue signal detection
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

# =============================================================================
# Fatigue Signals
# =============================================================================


class FatigueLevel(Enum):
    """Severity of detected fatigue."""

    NONE = "none"
    MILD = "mild"  # Suggest a short break
    MODERATE = "moderate"  # Strongly suggest break
    SEVERE = "severe"  # Recommend ending session


@dataclass
class FatigueSignal:
    """A detected fatigue indicator."""

    level: FatigueLevel
    reason: str
    metric_value: float
    threshold: float
    recommendation: str

    @property
    def should_break(self) -> bool:
        """Whether to suggest a break."""
        return self.level in {FatigueLevel.MODERATE, FatigueLevel.SEVERE}

    @property
    def should_end(self) -> bool:
        """Whether to recommend ending the session."""
        return self.level == FatigueLevel.SEVERE


# =============================================================================
# Fatigue Detector
# =============================================================================


@dataclass
class FatigueConfig:
    """Configuration for fatigue detection."""

    # Accuracy thresholds
    accuracy_drop_threshold: float = 0.15  # 15% drop triggers alert
    min_samples_for_accuracy: int = 10  # Need this many before checking

    # Response time thresholds
    response_time_increase: float = 0.30  # 30% increase triggers alert
    min_samples_for_timing: int = 5

    # Streak thresholds
    incorrect_streak_threshold: int = 4  # 4 wrong in a row

    # Session limits
    max_session_minutes: int = 45  # Recommend break after this


class FatigueDetector:
    """
    Detects cognitive fatigue during study sessions.

    Monitors:
    1. Accuracy degradation - rolling average vs. initial
    2. Response time increase - getting slower
    3. Incorrect streaks - consecutive failures
    4. Session duration - time-based limits
    """

    def __init__(self, config: FatigueConfig | None = None):
        """
        Initialize fatigue detector.

        Args:
            config: Custom thresholds (uses defaults if None)
        """
        self.config = config or FatigueConfig()

    def detect(
        self,
        telemetry: SessionTelemetry,
    ) -> FatigueSignal | None:
        """
        Check for fatigue signals.

        Args:
            telemetry: Current session telemetry

        Returns:
            FatigueSignal if fatigue detected, None otherwise
        """
        # Check session duration first
        signal = self._check_duration(telemetry)
        if signal:
            return signal

        # Check incorrect streak
        signal = self._check_incorrect_streak(telemetry)
        if signal:
            return signal

        # Check accuracy drop
        signal = self._check_accuracy_drop(telemetry)
        if signal:
            return signal

        # Check response time increase
        signal = self._check_response_time(telemetry)
        if signal:
            return signal

        return None

    def _check_duration(self, telemetry: SessionTelemetry) -> FatigueSignal | None:
        """Check if session has exceeded time limit."""
        duration_minutes = telemetry.duration_minutes

        if duration_minutes >= self.config.max_session_minutes:
            return FatigueSignal(
                level=FatigueLevel.MODERATE,
                reason="Session duration exceeded",
                metric_value=duration_minutes,
                threshold=self.config.max_session_minutes,
                recommendation=f"You've been studying for {duration_minutes:.0f} minutes. "
                "Consider taking a 5-10 minute break.",
            )
        return None

    def _check_incorrect_streak(self, telemetry: SessionTelemetry) -> FatigueSignal | None:
        """Check for consecutive incorrect answers."""
        streak = telemetry.current_incorrect_streak

        if streak >= self.config.incorrect_streak_threshold:
            return FatigueSignal(
                level=FatigueLevel.SEVERE if streak >= 6 else FatigueLevel.MODERATE,
                reason="Incorrect answer streak",
                metric_value=streak,
                threshold=self.config.incorrect_streak_threshold,
                recommendation=f"You've had {streak} incorrect answers in a row. "
                "This might be a good time for a break or to review the material.",
            )
        return None

    def _check_accuracy_drop(self, telemetry: SessionTelemetry) -> FatigueSignal | None:
        """Check for significant accuracy degradation."""
        if telemetry.total_reviews < self.config.min_samples_for_accuracy:
            return None

        initial_accuracy = telemetry.initial_accuracy
        recent_accuracy = telemetry.recent_accuracy

        if initial_accuracy == 0:
            return None

        drop = (initial_accuracy - recent_accuracy) / initial_accuracy

        if drop >= self.config.accuracy_drop_threshold:
            return FatigueSignal(
                level=FatigueLevel.MODERATE if drop < 0.25 else FatigueLevel.SEVERE,
                reason="Accuracy degradation",
                metric_value=drop,
                threshold=self.config.accuracy_drop_threshold,
                recommendation=f"Your accuracy has dropped by {drop:.0%} since the session started. "
                "A short break might help restore focus.",
            )
        return None

    def _check_response_time(self, telemetry: SessionTelemetry) -> FatigueSignal | None:
        """Check for increasing response times."""
        if telemetry.total_reviews < self.config.min_samples_for_timing:
            return None

        initial_avg = telemetry.initial_response_time
        recent_avg = telemetry.recent_response_time

        if initial_avg == 0:
            return None

        increase = (recent_avg - initial_avg) / initial_avg

        if increase >= self.config.response_time_increase:
            return FatigueSignal(
                level=FatigueLevel.MILD,
                reason="Response time increase",
                metric_value=increase,
                threshold=self.config.response_time_increase,
                recommendation=f"You're taking {increase:.0%} longer to respond than at the start. "
                "This is a normal sign of mental fatigue.",
            )
        return None


# =============================================================================
# Session Telemetry
# =============================================================================


@dataclass
class ReviewEvent:
    """A single review event in the session."""

    atom_id: str
    grade: int
    response_ms: int
    is_correct: bool
    timestamp: datetime = field(default_factory=datetime.now)
    confidence: int | None = None


class SessionTelemetry:
    """
    Tracks metrics for a single study session.

    Provides rolling statistics for fatigue detection:
    - Accuracy (initial vs. recent windows)
    - Response times (initial vs. recent windows)
    - Streaks and patterns
    """

    WINDOW_SIZE = 10  # Size of "recent" window for comparisons

    def __init__(self):
        """Initialize session telemetry."""
        self.started_at = datetime.now()
        self.events: list[ReviewEvent] = []
        self._current_incorrect_streak = 0

    def record(
        self,
        atom_id: str,
        grade: int,
        response_ms: int,
        confidence: int | None = None,
    ) -> None:
        """
        Record a review event.

        Args:
            atom_id: The reviewed atom
            grade: SM-2 grade (0-5)
            response_ms: Time to answer
            confidence: Self-reported confidence
        """
        is_correct = grade >= 3

        event = ReviewEvent(
            atom_id=atom_id,
            grade=grade,
            response_ms=response_ms,
            is_correct=is_correct,
            confidence=confidence,
        )
        self.events.append(event)

        # Update streak
        if is_correct:
            self._current_incorrect_streak = 0
        else:
            self._current_incorrect_streak += 1

    # =========================================================================
    # Basic Metrics
    # =========================================================================

    @property
    def total_reviews(self) -> int:
        """Total reviews in session."""
        return len(self.events)

    @property
    def correct_count(self) -> int:
        """Number of correct answers."""
        return sum(1 for e in self.events if e.is_correct)

    @property
    def overall_accuracy(self) -> float:
        """Overall accuracy for the session."""
        if not self.events:
            return 0.0
        return self.correct_count / len(self.events)

    @property
    def average_response_ms(self) -> float:
        """Average response time in milliseconds."""
        if not self.events:
            return 0.0
        return sum(e.response_ms for e in self.events) / len(self.events)

    @property
    def duration_minutes(self) -> float:
        """Session duration in minutes."""
        delta = datetime.now() - self.started_at
        return delta.total_seconds() / 60

    @property
    def current_incorrect_streak(self) -> int:
        """Current consecutive incorrect answers."""
        return self._current_incorrect_streak

    # =========================================================================
    # Windowed Metrics (for fatigue detection)
    # =========================================================================

    @property
    def initial_accuracy(self) -> float:
        """Accuracy of first N reviews."""
        initial = self.events[: self.WINDOW_SIZE]
        if not initial:
            return 0.0
        return sum(1 for e in initial if e.is_correct) / len(initial)

    @property
    def recent_accuracy(self) -> float:
        """Accuracy of last N reviews."""
        recent = self.events[-self.WINDOW_SIZE :]
        if not recent:
            return 0.0
        return sum(1 for e in recent if e.is_correct) / len(recent)

    @property
    def initial_response_time(self) -> float:
        """Average response time of first N reviews (ms)."""
        initial = self.events[: self.WINDOW_SIZE]
        if not initial:
            return 0.0
        return sum(e.response_ms for e in initial) / len(initial)

    @property
    def recent_response_time(self) -> float:
        """Average response time of last N reviews (ms)."""
        recent = self.events[-self.WINDOW_SIZE :]
        if not recent:
            return 0.0
        return sum(e.response_ms for e in recent) / len(recent)

    # =========================================================================
    # Analysis
    # =========================================================================

    def get_stats(self) -> dict:
        """
        Get session statistics.

        Returns:
            Dictionary of session metrics
        """
        return {
            "duration_minutes": round(self.duration_minutes, 1),
            "total_reviews": self.total_reviews,
            "correct_count": self.correct_count,
            "accuracy_percent": round(self.overall_accuracy * 100, 1),
            "avg_response_ms": round(self.average_response_ms),
            "current_streak": self._current_incorrect_streak,
            "grade_distribution": self._grade_distribution(),
        }

    def _grade_distribution(self) -> dict[int, int]:
        """Get distribution of grades."""
        dist = {i: 0 for i in range(6)}
        for event in self.events:
            dist[event.grade] += 1
        return dist

    def get_struggling_atoms(self, min_failures: int = 2) -> list[str]:
        """
        Get atom IDs that have been failed multiple times.

        Args:
            min_failures: Minimum failures to be considered "struggling"

        Returns:
            List of atom IDs
        """
        failure_counts: dict[str, int] = {}

        for event in self.events:
            if not event.is_correct:
                failure_counts[event.atom_id] = failure_counts.get(event.atom_id, 0) + 1

        return [atom_id for atom_id, count in failure_counts.items() if count >= min_failures]
