"""
JSON Telemetry Logger for ML/LLM Analysis.

Provides structured JSON file logging alongside database telemetry,
enabling offline ML analysis and LLM-based learning insights.

File Structure:
    ~/.cortex/telemetry/
        sessions/
            2025-12-07_session_abc123.jsonl  # One event per line
        summaries/
            2025-12-07_daily.json            # Daily aggregations

Event Types:
    - session_start: Session initialization with mode/config
    - interaction: Individual atom response
    - diagnosis: NCDE cognitive diagnosis
    - state_change: Session state transitions
    - session_end: Session summary with statistics
"""

from __future__ import annotations

import json
import os
import uuid
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from loguru import logger


# =============================================================================
# Event Schemas
# =============================================================================


@dataclass
class InteractionEvent:
    """Captures a single atom interaction."""

    atom_id: str
    atom_type: str
    module_number: int | None
    section_id: str | None
    is_correct: bool
    response_time_ms: int
    user_answer: str
    correct_answer: str
    confidence: int | None = None
    session_index: int = 0
    queue_position: int = 0
    retry_attempt: int = 0
    hints_used: int = 0

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)


@dataclass
class DiagnosisEvent:
    """Captures NCDE cognitive diagnosis."""

    atom_id: str
    fail_mode: str | None  # encoding, retrieval, discrimination, integration, executive, fatigue
    success_mode: str | None  # recall, recognition, inference
    cognitive_state: str  # encoding, integration, focus, fatigue
    confidence: float
    remediation_type: str | None = None  # continue, micro_break, force_z
    remediation_target: str | None = None
    evidence: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)


@dataclass
class SessionStateEvent:
    """Captures session state at a point in time."""

    correct_count: int
    incorrect_count: int
    error_streak: int
    correct_streak: int
    fatigue_level: float
    elapsed_seconds: int
    atoms_remaining: int
    accuracy_percent: float
    avg_response_time_ms: float

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)


@dataclass
class SessionSummary:
    """End-of-session summary."""

    session_id: str
    learner_id: str
    mode: str
    started_at: str
    ended_at: str
    duration_seconds: int
    total_atoms: int
    correct_count: int
    incorrect_count: int
    accuracy_percent: float
    avg_response_time_ms: float
    error_streaks: list[int]
    modules_touched: list[int]
    sections_touched: list[str]
    failure_modes_detected: dict[str, int]
    remediations_triggered: dict[str, int]
    fatigue_detected: bool
    config: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)


# =============================================================================
# JSON Telemetry Logger
# =============================================================================


class JSONTelemetryLogger:
    """
    JSON file logger for ML/LLM analysis.

    Writes structured JSONL (one event per line) to session files.
    Supports file rotation and daily summaries.
    """

    def __init__(
        self,
        log_dir: Path | None = None,
        rotation_size_mb: int = 10,
        learner_id: str | None = None,
    ):
        """
        Initialize the telemetry logger.

        Args:
            log_dir: Directory for telemetry files (default: ~/.cortex/telemetry)
            rotation_size_mb: Max file size before rotation (default: 10MB)
            learner_id: Unique learner identifier (default: auto-generated)
        """
        self.log_dir = log_dir or (Path.home() / ".cortex" / "telemetry")
        self.sessions_dir = self.log_dir / "sessions"
        self.summaries_dir = self.log_dir / "summaries"
        self.rotation_size_bytes = rotation_size_mb * 1024 * 1024
        self.learner_id = learner_id or self._get_or_create_learner_id()

        # Current session state
        self.session_id: str | None = None
        self.session_file: Path | None = None
        self.session_start: datetime | None = None
        self.mode: str | None = None
        self.config: dict[str, Any] = {}

        # Session statistics
        self.interaction_count = 0
        self.correct_count = 0
        self.incorrect_count = 0
        self.response_times: list[int] = []
        self.error_streaks: list[int] = []
        self.current_error_streak = 0
        self.modules_touched: set[int] = set()
        self.sections_touched: set[str] = set()
        self.failure_modes: dict[str, int] = {}
        self.remediations: dict[str, int] = {}
        self.fatigue_detected = False

        # Ensure directories exist
        self._ensure_directories()

    def _ensure_directories(self) -> None:
        """Create telemetry directories if they don't exist."""
        self.sessions_dir.mkdir(parents=True, exist_ok=True)
        self.summaries_dir.mkdir(parents=True, exist_ok=True)

    def _get_or_create_learner_id(self) -> str:
        """Get or create a persistent learner ID."""
        id_file = self.log_dir / ".learner_id"
        if id_file.exists():
            return id_file.read_text().strip()

        learner_id = str(uuid.uuid4())[:8]
        self.log_dir.mkdir(parents=True, exist_ok=True)
        id_file.write_text(learner_id)
        return learner_id

    def start_session(
        self,
        mode: str,
        config: dict[str, Any] | None = None,
    ) -> str:
        """
        Start a new telemetry session.

        Args:
            mode: Study mode (adaptive, war, manual)
            config: Session configuration (modules, types, limits, etc.)

        Returns:
            Session ID
        """
        self.session_id = str(uuid.uuid4())[:12]
        self.session_start = datetime.now(UTC)
        self.mode = mode
        self.config = config or {}

        # Reset statistics
        self.interaction_count = 0
        self.correct_count = 0
        self.incorrect_count = 0
        self.response_times = []
        self.error_streaks = []
        self.current_error_streak = 0
        self.modules_touched = set()
        self.sections_touched = set()
        self.failure_modes = {}
        self.remediations = {}
        self.fatigue_detected = False

        # Create session file
        date_str = self.session_start.strftime("%Y-%m-%d")
        filename = f"{date_str}_session_{self.session_id}.jsonl"
        self.session_file = self.sessions_dir / filename

        # Write session start event
        self._write_event(
            "session_start",
            {
                "learner_id": self.learner_id,
                "mode": mode,
                "config": config,
                "platform": os.name,
            },
        )

        logger.debug(f"Telemetry session started: {self.session_id}")
        return self.session_id

    def log_interaction(self, event: InteractionEvent) -> None:
        """
        Log a single atom interaction.

        Args:
            event: InteractionEvent with response details
        """
        if not self.session_id:
            logger.warning("log_interaction called without active session")
            return

        # Update statistics
        self.interaction_count += 1
        self.response_times.append(event.response_time_ms)

        if event.is_correct:
            self.correct_count += 1
            if self.current_error_streak > 0:
                self.error_streaks.append(self.current_error_streak)
                self.current_error_streak = 0
        else:
            self.incorrect_count += 1
            self.current_error_streak += 1

        if event.module_number:
            self.modules_touched.add(event.module_number)
        if event.section_id:
            self.sections_touched.add(event.section_id)

        # Write event
        self._write_event("interaction", event.to_dict())

    def log_diagnosis(self, event: DiagnosisEvent) -> None:
        """
        Log an NCDE cognitive diagnosis.

        Args:
            event: DiagnosisEvent with diagnosis details
        """
        if not self.session_id:
            logger.warning("log_diagnosis called without active session")
            return

        # Track failure modes
        if event.fail_mode:
            self.failure_modes[event.fail_mode] = (
                self.failure_modes.get(event.fail_mode, 0) + 1
            )

        # Track remediations
        if event.remediation_type:
            self.remediations[event.remediation_type] = (
                self.remediations.get(event.remediation_type, 0) + 1
            )

        # Track fatigue
        if event.cognitive_state == "fatigue" or event.fail_mode == "fatigue":
            self.fatigue_detected = True

        # Write event
        self._write_event("diagnosis", event.to_dict())

    def log_state_change(
        self,
        state_type: str,
        old_value: Any,
        new_value: Any,
        context: dict[str, Any] | None = None,
    ) -> None:
        """
        Log a session state change.

        Args:
            state_type: Type of state change (e.g., "mode", "fatigue_level")
            old_value: Previous value
            new_value: New value
            context: Additional context
        """
        if not self.session_id:
            return

        self._write_event(
            "state_change",
            {
                "state_type": state_type,
                "old_value": old_value,
                "new_value": new_value,
                "context": context or {},
            },
        )

    def log_state_snapshot(self, state: SessionStateEvent) -> None:
        """
        Log a full session state snapshot.

        Args:
            state: SessionStateEvent with current state
        """
        if not self.session_id:
            return

        self._write_event("state_snapshot", state.to_dict())

    def end_session(self) -> SessionSummary | None:
        """
        End the session and write summary.

        Returns:
            SessionSummary with final statistics
        """
        if not self.session_id or not self.session_start:
            logger.warning("end_session called without active session")
            return None

        ended_at = datetime.now(UTC)
        duration = int((ended_at - self.session_start).total_seconds())

        # Add any remaining error streak
        if self.current_error_streak > 0:
            self.error_streaks.append(self.current_error_streak)

        # Calculate averages
        accuracy = (
            (self.correct_count / self.interaction_count * 100)
            if self.interaction_count > 0
            else 0.0
        )
        avg_rt = (
            sum(self.response_times) / len(self.response_times)
            if self.response_times
            else 0.0
        )

        # Create summary
        summary = SessionSummary(
            session_id=self.session_id,
            learner_id=self.learner_id,
            mode=self.mode or "unknown",
            started_at=self.session_start.isoformat(),
            ended_at=ended_at.isoformat(),
            duration_seconds=duration,
            total_atoms=self.interaction_count,
            correct_count=self.correct_count,
            incorrect_count=self.incorrect_count,
            accuracy_percent=round(accuracy, 2),
            avg_response_time_ms=round(avg_rt, 2),
            error_streaks=self.error_streaks,
            modules_touched=sorted(self.modules_touched),
            sections_touched=sorted(self.sections_touched),
            failure_modes_detected=self.failure_modes,
            remediations_triggered=self.remediations,
            fatigue_detected=self.fatigue_detected,
            config=self.config,
        )

        # Write session end event
        self._write_event("session_end", summary.to_dict())

        # Update daily summary
        self._update_daily_summary(summary)

        logger.debug(
            f"Telemetry session ended: {self.session_id} "
            f"({self.interaction_count} interactions, {accuracy:.1f}% accuracy)"
        )

        # Reset session state
        self.session_id = None
        self.session_file = None
        self.session_start = None

        return summary

    def _write_event(self, event_type: str, payload: dict[str, Any]) -> None:
        """Write an event to the session file."""
        if not self.session_file:
            return

        event = {
            "ts": datetime.now(UTC).isoformat(),
            "session": self.session_id,
            "type": event_type,
            **payload,
        }

        try:
            with open(self.session_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(event, default=str) + "\n")

            # Check for rotation
            self._rotate_if_needed()

        except Exception as e:
            logger.error(f"Failed to write telemetry event: {e}")

    def _rotate_if_needed(self) -> None:
        """Rotate file if it exceeds size limit."""
        if not self.session_file or not self.session_file.exists():
            return

        if self.session_file.stat().st_size > self.rotation_size_bytes:
            # Rename current file with timestamp
            timestamp = datetime.now(UTC).strftime("%H%M%S")
            rotated = self.session_file.with_suffix(f".{timestamp}.jsonl")
            self.session_file.rename(rotated)

            # Create new file
            self.session_file.touch()
            logger.debug(f"Rotated telemetry file: {rotated.name}")

    def _update_daily_summary(self, session: SessionSummary) -> None:
        """Update daily aggregation file."""
        if not self.session_start:
            return

        date_str = self.session_start.strftime("%Y-%m-%d")
        summary_file = self.summaries_dir / f"{date_str}_daily.json"

        # Load or create daily summary
        daily: dict[str, Any]
        if summary_file.exists():
            try:
                daily = json.loads(summary_file.read_text())
            except json.JSONDecodeError:
                daily = self._create_empty_daily()
        else:
            daily = self._create_empty_daily()

        # Update aggregates
        daily["sessions"].append(session.session_id)
        daily["total_atoms"] += session.total_atoms
        daily["total_correct"] += session.correct_count
        daily["total_incorrect"] += session.incorrect_count
        daily["total_duration_seconds"] += session.duration_seconds

        # Update accuracy
        total = daily["total_correct"] + daily["total_incorrect"]
        daily["overall_accuracy"] = (
            round(daily["total_correct"] / total * 100, 2) if total > 0 else 0.0
        )

        # Update mode counts
        daily["mode_counts"][session.mode] = (
            daily["mode_counts"].get(session.mode, 0) + 1
        )

        # Merge failure modes
        for mode, count in session.failure_modes_detected.items():
            daily["failure_modes"][mode] = daily["failure_modes"].get(mode, 0) + count

        # Merge modules
        for mod in session.modules_touched:
            if mod not in daily["modules_studied"]:
                daily["modules_studied"].append(mod)
        daily["modules_studied"].sort()

        daily["last_updated"] = datetime.now(UTC).isoformat()

        # Write back
        try:
            summary_file.write_text(json.dumps(daily, indent=2))
        except Exception as e:
            logger.error(f"Failed to update daily summary: {e}")

    def _create_empty_daily(self) -> dict[str, Any]:
        """Create empty daily summary structure."""
        return {
            "date": datetime.now(UTC).strftime("%Y-%m-%d"),
            "sessions": [],
            "total_atoms": 0,
            "total_correct": 0,
            "total_incorrect": 0,
            "total_duration_seconds": 0,
            "overall_accuracy": 0.0,
            "mode_counts": {},
            "failure_modes": {},
            "modules_studied": [],
            "last_updated": datetime.now(UTC).isoformat(),
        }

    def get_session_file_path(self) -> Path | None:
        """Get the current session file path."""
        return self.session_file

    def get_daily_summary_path(self, date: datetime | None = None) -> Path:
        """Get the daily summary file path for a date."""
        d = date or datetime.now(UTC)
        date_str = d.strftime("%Y-%m-%d")
        return self.summaries_dir / f"{date_str}_daily.json"


# =============================================================================
# Global Instance
# =============================================================================

# Singleton for easy access across modules
_global_logger: JSONTelemetryLogger | None = None


def get_telemetry_logger() -> JSONTelemetryLogger:
    """Get or create the global telemetry logger."""
    global _global_logger
    if _global_logger is None:
        _global_logger = JSONTelemetryLogger()
    return _global_logger


def reset_telemetry_logger() -> None:
    """Reset the global telemetry logger (for testing)."""
    global _global_logger
    _global_logger = None
