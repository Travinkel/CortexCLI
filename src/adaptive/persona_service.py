"""
Learner Persona Service for Cortex.

Builds and maintains a dynamic cognitive profile that evolves with every interaction.
This profile is the "Learner Persona Vector" injected into all LLM prompts for
personalized tutoring.

Key Features:
- Processing characteristics (speed, accuracy patterns)
- Chronotype detection (morning lark, night owl, neutral)
- Knowledge type strengths (factual, conceptual, procedural, strategic)
- Mechanism effectiveness (retrieval, discrimination, integration, etc.)
- Interference patterns (which concepts get confused)
- Calibration tracking (confidence vs. actual performance)
- Acceleration indicators (pace of mastery acquisition)

The persona evolves using Exponential Moving Averages (EMA) to balance
recent performance with historical stability.

Based on research from:
- Jung & Haier (2007): P-FIT theory
- Roenneberg (2007): Chronotype and performance
- Koriat (2008): Metacognitive calibration
- Kruger & Dunning (1999): Calibration biases

Author: Cortex System
Version: 2.0.0 (Neuromorphic Architecture)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

from loguru import logger

try:
    from sqlalchemy import text

    from src.db.database import engine

    HAS_DATABASE = True
except ImportError:
    HAS_DATABASE = False
    logger.warning("Database not available - persona will use in-memory storage")


# =============================================================================
# ENUMERATIONS
# =============================================================================


class ProcessingSpeed(str, Enum):
    """Classification of learner's processing speed."""

    FAST_ACCURATE = "fast_accurate"  # <3s, >80% accuracy
    FAST_INACCURATE = "fast_inaccurate"  # <3s, ≤80% accuracy
    SLOW_ACCURATE = "slow_accurate"  # ≥3s, >80% accuracy
    SLOW_INACCURATE = "slow_inaccurate"  # ≥3s, ≤80% accuracy
    MODERATE = "moderate"  # Default/balanced


class Chronotype(str, Enum):
    """Learner's chronotype (biological clock preference)."""

    MORNING_LARK = "morning_lark"  # Peak 6-10am
    NEUTRAL = "neutral"  # Peak 10am-2pm
    NIGHT_OWL = "night_owl"  # Peak 8pm-12am


class PreferredModality(str, Enum):
    """Learning modality preference."""

    VISUAL = "visual"  # Diagrams, graphs, spatial
    SYMBOLIC = "symbolic"  # Formulas, equations, proofs
    PROCEDURAL = "procedural"  # Step-by-step, algorithms
    NARRATIVE = "narrative"  # Stories, analogies, context
    MIXED = "mixed"  # No strong preference


# =============================================================================
# LEARNER PERSONA DATACLASS
# =============================================================================


@dataclass
class LearnerPersona:
    """
    Dynamic cognitive profile of a learner.

    Updated after every session based on performance patterns.
    This is the core "vector" that personalizes all AI interactions.

    Attributes:
        user_id: Unique identifier for the learner
        processing_speed: Speed/accuracy classification
        attention_span_minutes: Before accuracy drops significantly
        preferred_session_length: Optimal study duration
        chronotype: Biological clock preference
        peak_performance_hour: Best hour for deep work (0-23)
        low_energy_hours: Hours to avoid difficult material
        strength_*: Knowledge type proficiencies (0-1)
        effectiveness_*: Mechanism effectiveness (0-1)
        interference_prone_topics: Concepts often confused
        conceptual_weaknesses: Fundamental gaps identified
        calibration_score: Confidence calibration (0.5 = perfect)
        preferred_modality: Learning style preference
        acceleration_rate: Mastery acquisition rate (atoms/hour)
        total_study_hours: Cumulative study time
        current_streak_days: Consecutive days studied
    """

    user_id: str = "default"

    # Processing characteristics
    processing_speed: ProcessingSpeed = ProcessingSpeed.MODERATE
    attention_span_minutes: int = 25
    preferred_session_length: int = 25

    # Chronotype
    chronotype: Chronotype = Chronotype.NEUTRAL
    peak_performance_hour: int = 10  # 0-23
    low_energy_hours: list[int] = field(default_factory=lambda: [14, 15, 16])

    # Knowledge type strengths (0-1)
    strength_factual: float = 0.5  # Memorizing facts, definitions
    strength_conceptual: float = 0.5  # Understanding relationships
    strength_procedural: float = 0.5  # Following multi-step processes
    strength_strategic: float = 0.5  # Problem-solving, metacognition

    # Mechanism effectiveness (0-1)
    effectiveness_retrieval: float = 0.5  # Free recall
    effectiveness_generation: float = 0.5  # Producing answers
    effectiveness_elaboration: float = 0.5  # Connecting to prior knowledge
    effectiveness_application: float = 0.5  # Using in new contexts
    effectiveness_discrimination: float = 0.5  # Distinguishing similar items

    # Struggle patterns
    interference_prone_topics: list[str] = field(default_factory=list)
    conceptual_weaknesses: list[str] = field(default_factory=list)

    # Metacognitive calibration (0.5 = perfectly calibrated)
    # <0.5 = underconfident, >0.5 = overconfident
    calibration_score: float = 0.5

    # Learning modality preference
    preferred_modality: PreferredModality = PreferredModality.MIXED

    # Acceleration metrics
    acceleration_rate: float = 0.0  # Atoms mastered per hour
    current_velocity: float = 0.0  # Recent learning rate
    velocity_trend: str = "stable"  # "improving", "stable", "declining"

    # Cumulative metrics
    total_study_hours: float = 0.0
    total_atoms_seen: int = 0
    total_atoms_mastered: int = 0
    current_streak_days: int = 0
    longest_streak_days: int = 0

    # P-FIT and Hippocampal indices (derived from performance)
    pfit_efficiency: float = 0.5  # Integration ability
    hippocampal_efficiency: float = 0.5  # Pattern separation ability

    # Timestamps
    created_at: datetime | None = None
    updated_at: datetime | None = None
    last_session_at: datetime | None = None

    def to_prompt_context(self) -> str:
        """
        Generate context string for LLM prompts.

        This is injected into every AI tutoring prompt so the LLM
        understands how to communicate with this specific learner.
        Returns a structured context that personalizes AI responses.
        """
        # Identify strengths
        strengths = []
        if self.strength_factual > 0.7:
            strengths.append("factual recall")
        if self.strength_procedural > 0.7:
            strengths.append("step-by-step procedures")
        if self.strength_conceptual > 0.7:
            strengths.append("abstract concept understanding")
        if self.strength_strategic > 0.7:
            strengths.append("problem-solving strategies")

        # Identify weaknesses
        weaknesses = []
        if self.strength_factual < 0.4:
            weaknesses.append("memorizing specific facts")
        if self.strength_procedural < 0.4:
            weaknesses.append("following multi-step procedures")
        if self.strength_conceptual < 0.4:
            weaknesses.append("grasping abstract concepts")
        if self.strength_strategic < 0.4:
            weaknesses.append("strategic problem-solving")

        # Calibration guidance
        if self.calibration_score > 0.65:
            calibration_note = "tends to be overconfident - challenge assumptions"
        elif self.calibration_score < 0.35:
            calibration_note = "tends to be underconfident - provide encouragement"
        else:
            calibration_note = "well-calibrated"

        # Processing style guidance
        processing_guide = {
            ProcessingSpeed.FAST_ACCURATE: "Quick thinker, efficient processor",
            ProcessingSpeed.FAST_INACCURATE: "Impulsive - needs prompts to slow down",
            ProcessingSpeed.SLOW_ACCURATE: "Deliberate thinker - appreciates depth",
            ProcessingSpeed.SLOW_INACCURATE: "May be struggling - simplify explanations",
            ProcessingSpeed.MODERATE: "Balanced processor",
        }

        # Modality guidance
        modality_guide = {
            PreferredModality.VISUAL: "Use diagrams and visualizations when possible",
            PreferredModality.SYMBOLIC: "Comfortable with formal notation and equations",
            PreferredModality.PROCEDURAL: "Break down into numbered steps",
            PreferredModality.NARRATIVE: "Use analogies and real-world examples",
            PreferredModality.MIXED: "Vary explanatory approaches",
        }

        context = f"""
LEARNER PROFILE:
- Processing Style: {processing_guide.get(self.processing_speed, "Unknown")}
- Attention Span: ~{self.attention_span_minutes} minutes before fatigue
- Peak Performance: {self.peak_performance_hour}:00 (chronotype: {self.chronotype.value})
- Strengths: {", ".join(strengths) if strengths else "Balanced across domains"}
- Areas for Growth: {", ".join(weaknesses) if weaknesses else "None identified"}
- Topics Often Confused: {", ".join(self.interference_prone_topics[:3]) if self.interference_prone_topics else "None tracked"}
- Preferred Explanation Style: {modality_guide.get(self.preferred_modality, "Mixed")}
- Calibration: {calibration_note}
- Learning Velocity: {self.current_velocity:.1f} atoms/hour ({self.velocity_trend})
- Study Streak: {self.current_streak_days} days

COMMUNICATION GUIDELINES:
- {"Use concrete examples and analogies" if self.strength_conceptual < 0.5 else "Can handle abstract explanations"}
- {"Break down into small numbered steps" if self.strength_procedural < 0.5 else "Can follow complex procedures"}
- {"Include visual representations when possible" if self.preferred_modality == PreferredModality.VISUAL else "Text-based explanations work well"}
- {"Challenge overconfidence with Socratic questions" if self.calibration_score > 0.6 else "Build confidence with positive reinforcement" if self.calibration_score < 0.4 else "Balance challenge and support"}
- {"Suggest slowing down before answering" if self.processing_speed == ProcessingSpeed.FAST_INACCURATE else "Maintain current pacing"}

P-FIT EFFICIENCY: {self.pfit_efficiency:.2f} (integration ability)
HIPPOCAMPAL EFFICIENCY: {self.hippocampal_efficiency:.2f} (pattern separation ability)
"""
        return context.strip()

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "user_id": self.user_id,
            "processing_speed": self.processing_speed.value,
            "attention_span_minutes": self.attention_span_minutes,
            "preferred_session_length": self.preferred_session_length,
            "chronotype": self.chronotype.value,
            "peak_performance_hour": self.peak_performance_hour,
            "low_energy_hours": self.low_energy_hours,
            "strength_factual": round(self.strength_factual, 3),
            "strength_conceptual": round(self.strength_conceptual, 3),
            "strength_procedural": round(self.strength_procedural, 3),
            "strength_strategic": round(self.strength_strategic, 3),
            "effectiveness_retrieval": round(self.effectiveness_retrieval, 3),
            "effectiveness_generation": round(self.effectiveness_generation, 3),
            "effectiveness_elaboration": round(self.effectiveness_elaboration, 3),
            "effectiveness_application": round(self.effectiveness_application, 3),
            "effectiveness_discrimination": round(self.effectiveness_discrimination, 3),
            "interference_prone_topics": self.interference_prone_topics[:10],
            "conceptual_weaknesses": self.conceptual_weaknesses[:10],
            "calibration_score": round(self.calibration_score, 3),
            "preferred_modality": self.preferred_modality.value,
            "acceleration_rate": round(self.acceleration_rate, 2),
            "current_velocity": round(self.current_velocity, 2),
            "velocity_trend": self.velocity_trend,
            "total_study_hours": round(self.total_study_hours, 1),
            "total_atoms_seen": self.total_atoms_seen,
            "total_atoms_mastered": self.total_atoms_mastered,
            "current_streak_days": self.current_streak_days,
            "longest_streak_days": self.longest_streak_days,
            "pfit_efficiency": round(self.pfit_efficiency, 3),
            "hippocampal_efficiency": round(self.hippocampal_efficiency, 3),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> LearnerPersona:
        """Create persona from dictionary."""
        return cls(
            user_id=data.get("user_id", "default"),
            processing_speed=ProcessingSpeed(data.get("processing_speed", "moderate")),
            attention_span_minutes=data.get("attention_span_minutes", 25),
            preferred_session_length=data.get("preferred_session_length", 25),
            chronotype=Chronotype(data.get("chronotype", "neutral")),
            peak_performance_hour=data.get("peak_performance_hour", 10),
            low_energy_hours=data.get("low_energy_hours", [14, 15, 16]),
            strength_factual=data.get("strength_factual", 0.5),
            strength_conceptual=data.get("strength_conceptual", 0.5),
            strength_procedural=data.get("strength_procedural", 0.5),
            strength_strategic=data.get("strength_strategic", 0.5),
            effectiveness_retrieval=data.get("effectiveness_retrieval", 0.5),
            effectiveness_generation=data.get("effectiveness_generation", 0.5),
            effectiveness_elaboration=data.get("effectiveness_elaboration", 0.5),
            effectiveness_application=data.get("effectiveness_application", 0.5),
            effectiveness_discrimination=data.get("effectiveness_discrimination", 0.5),
            interference_prone_topics=data.get("interference_prone_topics", []),
            conceptual_weaknesses=data.get("conceptual_weaknesses", []),
            calibration_score=data.get("calibration_score", 0.5),
            preferred_modality=PreferredModality(data.get("preferred_modality", "mixed")),
            acceleration_rate=data.get("acceleration_rate", 0.0),
            current_velocity=data.get("current_velocity", 0.0),
            velocity_trend=data.get("velocity_trend", "stable"),
            total_study_hours=data.get("total_study_hours", 0.0),
            total_atoms_seen=data.get("total_atoms_seen", 0),
            total_atoms_mastered=data.get("total_atoms_mastered", 0),
            current_streak_days=data.get("current_streak_days", 0),
            longest_streak_days=data.get("longest_streak_days", 0),
            pfit_efficiency=data.get("pfit_efficiency", 0.5),
            hippocampal_efficiency=data.get("hippocampal_efficiency", 0.5),
        )


# =============================================================================
# SESSION STATISTICS
# =============================================================================


@dataclass
class SessionStatistics:
    """
    Statistics from a learning session for persona updates.

    Collected during a study session and passed to PersonaService.update_from_session().
    """

    # By knowledge type
    correct_by_type: dict[str, int] = field(default_factory=dict)
    incorrect_by_type: dict[str, int] = field(default_factory=dict)

    # By mechanism (atom type)
    correct_by_mechanism: dict[str, int] = field(default_factory=dict)
    incorrect_by_mechanism: dict[str, int] = field(default_factory=dict)

    # Timing
    avg_response_time_ms: int = 0
    session_duration_minutes: int = 0

    # Overall
    total_correct: int = 0
    total_incorrect: int = 0

    # Interference detected
    confusion_pairs: list[tuple[str, str]] = field(default_factory=list)

    # Calibration (if confidence was tracked)
    high_confidence_correct: int = 0
    high_confidence_incorrect: int = 0
    low_confidence_correct: int = 0
    low_confidence_incorrect: int = 0

    # Timestamps
    session_hour: int = 10  # Hour of day (0-23)
    session_date: datetime | None = None

    @property
    def overall_accuracy(self) -> float:
        """Calculate overall accuracy."""
        total = self.total_correct + self.total_incorrect
        return self.total_correct / total if total > 0 else 0.5

    @property
    def atoms_per_minute(self) -> float:
        """Calculate processing rate."""
        if self.session_duration_minutes <= 0:
            return 0.0
        total = self.total_correct + self.total_incorrect
        return total / self.session_duration_minutes


# =============================================================================
# PERSONA SERVICE
# =============================================================================

# In-memory cache for personas (fallback when DB unavailable)
_persona_cache: dict[str, LearnerPersona] = {}


class PersonaService:
    """
    Service for building and updating learner personas.

    Handles:
    - Loading/saving personas from database
    - Updating personas from session statistics
    - Inferring chronotype from performance patterns
    - Detecting interference patterns
    - Tracking acceleration metrics
    """

    # Learning rate for EMA updates
    ALPHA = 0.1  # Standard learning rate
    ALPHA_FAST = 0.2  # For fast-changing metrics
    ALPHA_SLOW = 0.05  # For stable metrics

    def __init__(self, user_id: str = "default"):
        """Initialize persona service for a user."""
        self.user_id = user_id
        self._performance_by_hour: dict[int, list[float]] = {h: [] for h in range(24)}

    def get_persona(self) -> LearnerPersona:
        """
        Load or create learner persona.

        Attempts to load from database first, falls back to in-memory cache,
        and creates a default if neither exists.
        """
        # Try database first
        if HAS_DATABASE:
            try:
                return self._load_from_db()
            except Exception as e:
                logger.warning(f"Failed to load persona from DB: {e}")

        # Try cache
        if self.user_id in _persona_cache:
            return _persona_cache[self.user_id]

        # Create default
        persona = LearnerPersona(
            user_id=self.user_id,
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )
        _persona_cache[self.user_id] = persona
        return persona

    def save_persona(self, persona: LearnerPersona) -> None:
        """Save persona to storage."""
        persona.updated_at = datetime.now()

        # Update cache
        _persona_cache[self.user_id] = persona

        # Save to database if available
        if HAS_DATABASE:
            try:
                self._save_to_db(persona)
            except Exception as e:
                logger.warning(f"Failed to save persona to DB: {e}")

    def update_from_session(self, stats: SessionStatistics) -> LearnerPersona:
        """
        Update persona based on session performance.

        Uses Exponential Moving Averages to balance recent performance
        with historical patterns.

        Args:
            stats: SessionStatistics from the completed session

        Returns:
            Updated LearnerPersona
        """
        persona = self.get_persona()
        alpha = self.ALPHA

        # === Update Knowledge Type Strengths ===
        type_mapping = {
            "factual": "strength_factual",
            "conceptual": "strength_conceptual",
            "procedural": "strength_procedural",
            "strategic": "strength_strategic",
        }

        for ktype, attr in type_mapping.items():
            correct = stats.correct_by_type.get(ktype, 0)
            incorrect = stats.incorrect_by_type.get(ktype, 0)
            total = correct + incorrect

            if total > 0:
                session_accuracy = correct / total
                current = getattr(persona, attr)
                new_value = current * (1 - alpha) + session_accuracy * alpha
                setattr(persona, attr, max(0.0, min(1.0, new_value)))

        # === Update Mechanism Effectiveness ===
        mechanism_mapping = {
            "retrieval": ("flashcard", "cloze"),
            "generation": ("numeric", "parsons"),
            "elaboration": ("compare", "explain"),
            "application": ("mcq", "problem"),
            "discrimination": ("true_false", "matching"),
        }

        for mechanism, atom_types in mechanism_mapping.items():
            correct = sum(stats.correct_by_mechanism.get(t, 0) for t in atom_types)
            incorrect = sum(stats.incorrect_by_mechanism.get(t, 0) for t in atom_types)
            total = correct + incorrect

            if total > 0:
                session_accuracy = correct / total
                attr = f"effectiveness_{mechanism}"
                current = getattr(persona, attr)
                new_value = current * (1 - alpha) + session_accuracy * alpha
                setattr(persona, attr, max(0.0, min(1.0, new_value)))

        # === Update Processing Speed ===
        avg_time = stats.avg_response_time_ms
        accuracy = stats.overall_accuracy

        if avg_time < 3000 and accuracy > 0.8:
            persona.processing_speed = ProcessingSpeed.FAST_ACCURATE
        elif avg_time < 3000:
            persona.processing_speed = ProcessingSpeed.FAST_INACCURATE
        elif accuracy > 0.8:
            persona.processing_speed = ProcessingSpeed.SLOW_ACCURATE
        elif accuracy < 0.6:
            persona.processing_speed = ProcessingSpeed.SLOW_INACCURATE
        else:
            persona.processing_speed = ProcessingSpeed.MODERATE

        # === Update Calibration Score ===
        self._update_calibration(persona, stats)

        # === Update Chronotype (from performance patterns) ===
        self._update_chronotype(persona, stats)

        # === Update Interference Patterns ===
        if stats.confusion_pairs:
            for pair in stats.confusion_pairs[:5]:  # Keep top 5
                concept_name = f"{pair[0]} ↔ {pair[1]}"
                if concept_name not in persona.interference_prone_topics:
                    persona.interference_prone_topics.append(concept_name)
            # Keep only recent 10
            persona.interference_prone_topics = persona.interference_prone_topics[-10:]

        # === Update Velocity and Acceleration ===
        self._update_velocity(persona, stats)

        # === Update Cumulative Stats ===
        persona.total_study_hours += stats.session_duration_minutes / 60
        persona.total_atoms_seen += stats.total_correct + stats.total_incorrect
        persona.last_session_at = datetime.now()

        # Update streak
        today = datetime.now().date()
        if persona.last_session_at:
            last_date = persona.last_session_at.date()
            if (today - last_date).days == 1:
                persona.current_streak_days += 1
            elif (today - last_date).days > 1:
                persona.current_streak_days = 1
        else:
            persona.current_streak_days = 1

        if persona.current_streak_days > persona.longest_streak_days:
            persona.longest_streak_days = persona.current_streak_days

        # === Update P-FIT and Hippocampal Efficiency ===
        # P-FIT efficiency derived from procedural/strategic performance
        pfit_signal = (persona.strength_procedural + persona.strength_strategic) / 2
        persona.pfit_efficiency = persona.pfit_efficiency * 0.9 + pfit_signal * 0.1

        # Hippocampal efficiency derived from discrimination effectiveness
        hippo_signal = persona.effectiveness_discrimination
        persona.hippocampal_efficiency = persona.hippocampal_efficiency * 0.9 + hippo_signal * 0.1

        # Save and return
        self.save_persona(persona)

        logger.info(
            f"Persona updated: accuracy={stats.overall_accuracy:.1%}, "
            f"velocity={persona.current_velocity:.1f} atoms/hr, "
            f"calibration={persona.calibration_score:.2f}"
        )

        return persona

    def _update_calibration(self, persona: LearnerPersona, stats: SessionStatistics) -> None:
        """
        Update metacognitive calibration score.

        Calibration measures how well confidence predicts performance:
        - 0.5 = perfectly calibrated
        - >0.5 = overconfident (high confidence but wrong)
        - <0.5 = underconfident (low confidence but right)
        """
        # If we have confidence data
        total_high_conf = stats.high_confidence_correct + stats.high_confidence_incorrect
        total_low_conf = stats.low_confidence_correct + stats.low_confidence_incorrect

        if total_high_conf + total_low_conf < 3:
            return  # Not enough data

        # Calculate miscalibration
        # Overconfidence: high confidence but wrong
        overconfidence_rate = (
            stats.high_confidence_incorrect / total_high_conf if total_high_conf > 0 else 0
        )

        # Underconfidence: low confidence but right
        underconfidence_rate = (
            stats.low_confidence_correct / total_low_conf if total_low_conf > 0 else 0
        )

        # Calibration score: 0.5 + (overconfidence - underconfidence) / 2
        session_calibration = 0.5 + (overconfidence_rate - underconfidence_rate) / 2

        # Update with slow learning rate (calibration is stable)
        persona.calibration_score = (
            persona.calibration_score * (1 - self.ALPHA_SLOW)
            + session_calibration * self.ALPHA_SLOW
        )

    def _update_chronotype(self, persona: LearnerPersona, stats: SessionStatistics) -> None:
        """
        Infer chronotype from performance patterns by hour.

        Tracks accuracy at different hours to find peak performance time.
        """
        hour = stats.session_hour
        accuracy = stats.overall_accuracy

        # Record this hour's performance
        self._performance_by_hour[hour].append(accuracy)

        # Keep only last 10 sessions per hour
        self._performance_by_hour[hour] = self._performance_by_hour[hour][-10:]

        # Find peak hour (need data from multiple hours)
        hours_with_data = [
            (h, sum(accs) / len(accs))
            for h, accs in self._performance_by_hour.items()
            if len(accs) >= 2
        ]

        if len(hours_with_data) < 3:
            return  # Need more data

        # Find best hour
        best_hour, best_acc = max(hours_with_data, key=lambda x: x[1])
        persona.peak_performance_hour = best_hour

        # Infer chronotype
        if best_hour < 10:
            persona.chronotype = Chronotype.MORNING_LARK
            persona.low_energy_hours = [20, 21, 22, 23]
        elif best_hour >= 20:
            persona.chronotype = Chronotype.NIGHT_OWL
            persona.low_energy_hours = [6, 7, 8, 9]
        else:
            persona.chronotype = Chronotype.NEUTRAL
            persona.low_energy_hours = [14, 15, 16]  # Afternoon dip

    def _update_velocity(self, persona: LearnerPersona, stats: SessionStatistics) -> None:
        """
        Update learning velocity and acceleration metrics.

        Velocity = atoms mastered per hour
        Acceleration = change in velocity over time
        """
        if stats.session_duration_minutes <= 0:
            return

        # Current session velocity (atoms per hour)
        session_atoms = stats.total_correct + stats.total_incorrect
        session_hours = stats.session_duration_minutes / 60
        session_velocity = session_atoms / session_hours if session_hours > 0 else 0

        # Update velocity with EMA
        prev_velocity = persona.current_velocity
        persona.current_velocity = (
            prev_velocity * (1 - self.ALPHA_FAST) + session_velocity * self.ALPHA_FAST
        )

        # Update acceleration rate (weighted by mastery gain)
        mastery_rate = stats.total_correct / session_hours if session_hours > 0 else 0
        persona.acceleration_rate = (
            persona.acceleration_rate * (1 - self.ALPHA) + mastery_rate * self.ALPHA
        )

        # Determine trend
        velocity_change = persona.current_velocity - prev_velocity
        if velocity_change > 0.5:
            persona.velocity_trend = "improving"
        elif velocity_change < -0.5:
            persona.velocity_trend = "declining"
        else:
            persona.velocity_trend = "stable"

    def _load_from_db(self) -> LearnerPersona:
        """Load persona from database."""
        with engine.connect() as conn:
            result = conn.execute(
                text("""
                SELECT
                    strength_factual,
                    strength_conceptual,
                    strength_procedural,
                    strength_strategic,
                    effectiveness_retrieval,
                    effectiveness_generation,
                    effectiveness_elaboration,
                    effectiveness_application,
                    effectiveness_discrimination,
                    calibration_score,
                    preferred_session_duration_min,
                    optimal_study_hour,
                    total_study_hours,
                    current_streak_days,
                    longest_streak_days
                FROM learner_profiles
                WHERE user_id = :user_id
            """),
                {"user_id": self.user_id},
            )

            row = result.fetchone()

            if not row:
                # Create default
                persona = LearnerPersona(
                    user_id=self.user_id,
                    created_at=datetime.now(),
                )
                self._save_to_db(persona)
                return persona

            return LearnerPersona(
                user_id=self.user_id,
                strength_factual=float(row.strength_factual or 0.5),
                strength_conceptual=float(row.strength_conceptual or 0.5),
                strength_procedural=float(row.strength_procedural or 0.5),
                strength_strategic=float(row.strength_strategic or 0.5),
                effectiveness_retrieval=float(row.effectiveness_retrieval or 0.5),
                effectiveness_generation=float(row.effectiveness_generation or 0.5),
                effectiveness_elaboration=float(row.effectiveness_elaboration or 0.5),
                effectiveness_application=float(row.effectiveness_application or 0.5),
                effectiveness_discrimination=float(row.effectiveness_discrimination or 0.5),
                calibration_score=float(row.calibration_score or 0.5),
                preferred_session_length=int(row.preferred_session_duration_min or 25),
                peak_performance_hour=int(row.optimal_study_hour or 10),
                total_study_hours=float(row.total_study_hours or 0.0),
                current_streak_days=int(row.current_streak_days or 0),
                longest_streak_days=int(row.longest_streak_days or 0),
            )

    def _save_to_db(self, persona: LearnerPersona) -> None:
        """Save persona to database."""
        with engine.connect() as conn:
            conn.execute(
                text("""
                INSERT INTO learner_profiles (
                    id, user_id,
                    strength_factual, strength_conceptual,
                    strength_procedural, strength_strategic,
                    effectiveness_retrieval, effectiveness_generation,
                    effectiveness_elaboration, effectiveness_application,
                    effectiveness_discrimination,
                    calibration_score,
                    preferred_session_duration_min,
                    optimal_study_hour,
                    total_study_hours,
                    current_streak_days,
                    longest_streak_days,
                    updated_at
                ) VALUES (
                    gen_random_uuid(), :user_id,
                    :sf, :sc, :sp, :ss,
                    :er, :eg, :ee, :ea, :ed,
                    :cal, :session_dur, :peak_hour,
                    :total_hours, :streak, :longest_streak,
                    NOW()
                )
                ON CONFLICT (user_id) DO UPDATE SET
                    strength_factual = :sf,
                    strength_conceptual = :sc,
                    strength_procedural = :sp,
                    strength_strategic = :ss,
                    effectiveness_retrieval = :er,
                    effectiveness_generation = :eg,
                    effectiveness_elaboration = :ee,
                    effectiveness_application = :ea,
                    effectiveness_discrimination = :ed,
                    calibration_score = :cal,
                    preferred_session_duration_min = :session_dur,
                    optimal_study_hour = :peak_hour,
                    total_study_hours = :total_hours,
                    current_streak_days = :streak,
                    longest_streak_days = :longest_streak,
                    updated_at = NOW()
            """),
                {
                    "user_id": persona.user_id,
                    "sf": persona.strength_factual,
                    "sc": persona.strength_conceptual,
                    "sp": persona.strength_procedural,
                    "ss": persona.strength_strategic,
                    "er": persona.effectiveness_retrieval,
                    "eg": persona.effectiveness_generation,
                    "ee": persona.effectiveness_elaboration,
                    "ea": persona.effectiveness_application,
                    "ed": persona.effectiveness_discrimination,
                    "cal": persona.calibration_score,
                    "session_dur": persona.preferred_session_length,
                    "peak_hour": persona.peak_performance_hour,
                    "total_hours": persona.total_study_hours,
                    "streak": persona.current_streak_days,
                    "longest_streak": persona.longest_streak_days,
                },
            )
            conn.commit()


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================


def get_default_persona() -> LearnerPersona:
    """Get the default user's persona."""
    service = PersonaService("default")
    return service.get_persona()


def update_persona_from_interaction(
    user_id: str,
    is_correct: bool,
    response_time_ms: int,
    atom_type: str,
    knowledge_type: str,
    confidence: str | None = None,  # "high" or "low"
    confused_with: str | None = None,
) -> None:
    """
    Quick update for a single interaction.

    For bulk updates, use PersonaService.update_from_session().
    """
    # Build mini-stats
    stats = SessionStatistics(
        total_correct=1 if is_correct else 0,
        total_incorrect=0 if is_correct else 1,
        avg_response_time_ms=response_time_ms,
        session_duration_minutes=1,  # Rough estimate
        session_hour=datetime.now().hour,
    )

    # Update type counts
    if is_correct:
        stats.correct_by_type[knowledge_type] = 1
        stats.correct_by_mechanism[atom_type] = 1
    else:
        stats.incorrect_by_type[knowledge_type] = 1
        stats.incorrect_by_mechanism[atom_type] = 1

    # Confidence tracking
    if confidence == "high":
        if is_correct:
            stats.high_confidence_correct = 1
        else:
            stats.high_confidence_incorrect = 1
    elif confidence == "low":
        if is_correct:
            stats.low_confidence_correct = 1
        else:
            stats.low_confidence_incorrect = 1

    # Confusion tracking
    if confused_with:
        stats.confusion_pairs.append((atom_type, confused_with))

    # Update
    service = PersonaService(user_id)
    service.update_from_session(stats)
