"""
Neuro-Cognitive Diagnosis Engine (NCDE) Pipeline.

This module implements the middleware architecture for intercepting
learner interactions and routing them through the cognitive diagnosis
pipeline. It transforms the CortexSession from a simple FSM into an
Event-Driven Cognitive Loop.

Architecture:
1. InteractionInterceptor - Captures raw telemetry
2. FeatureExtractor - Normalizes behavioral signals
3. ConfusionMatrix - Tracks PSI for pattern separation
4. FatigueVectorCalculator - Multi-dimensional fatigue tracking
5. NeuroModelClassifier - Error classification
6. RemediationSelector - Strategy dispatch

Reference Architecture:
- Section 1.2: From FSM to Event-Driven Cognitive Loops
- Section 2: Telemetry Interception and Feature Extraction
- Section 3: The NCDE Implementation

Author: Cortex System
Version: 2.0.0 (Neuromorphic Architecture)
"""

from __future__ import annotations

import math
from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from loguru import logger

from .neuro_model import (
    CognitiveDiagnosis,
    FailMode,
    RemediationType,
    diagnose_interaction,
)

# =============================================================================
# TELEMETRY DATA STRUCTURES
# =============================================================================


@dataclass
class RawInteractionEvent:
    """
    Raw telemetry captured from user interaction.

    This is the "sensory layer" input - unprocessed behavioral signals
    that the NCDE will analyze to infer cognitive state.
    """

    # Core interaction
    atom_id: str
    atom_type: str
    is_correct: bool
    user_answer: str
    correct_answer: str

    # Timing (milliseconds)
    response_time_ms: int
    time_to_first_keystroke_ms: int | None = None
    dwell_time_ms: int = 0  # Time spent before first interaction

    # Mouse dynamics (if available)
    cursor_path_length: float = 0.0  # Pixels traveled
    cursor_direct_distance: float = 0.0  # Straight-line distance
    click_accuracy: float = 1.0  # Distance from button center (normalized)
    selection_changes: int = 0  # Number of times user changed selection

    # Keystroke dynamics (if available)
    total_keystrokes: int = 0
    backspace_count: int = 0
    average_inter_key_latency_ms: float | None = None

    # Context
    session_duration_seconds: int = 0
    session_index: int = 0  # Position in session queue
    timestamp: datetime = field(default_factory=datetime.now)

    # Lure tracking (for MCQ)
    selected_distractor_id: str | None = None
    distractor_similarity: float | None = None  # PSI to correct answer


@dataclass
class NormalizedTelemetry:
    """
    Z-scored telemetry signals normalized against learner's baseline.

    Z-scoring ensures the diagnosis is robust to individual differences
    in speed, motor control, and interaction style.
    """

    # Z-scored metrics
    z_response_time: float = 0.0  # Z-score of RT
    z_dwell_time: float = 0.0
    z_cursor_efficiency: float = 0.0  # Path efficiency (direct/actual)

    # Derived metrics
    path_efficiency: float = 1.0  # Direct distance / path length
    hesitation_index: float = 0.0  # Backspaces / total keystrokes
    selection_volatility: int = 0  # Selection changes

    # Raw values (for debugging)
    raw_response_time_ms: int = 0
    raw_dwell_time_ms: int = 0


@dataclass
class FatigueVector:
    """
    Multi-dimensional fatigue representation.

    Fatigue is not scalar - we distinguish:
    - Physical (motor) fatigue
    - Cognitive (resource) depletion
    - Motivational decay (disengagement)

    Reference: Section 3.2.2 - Calculation Logic
    """

    physical: float = 0.0  # Motor fatigue (cursor jitter, click accuracy)
    cognitive: float = 0.0  # Resource depletion (RT variability)
    motivation: float = 0.0  # Engagement drop (gaming behaviors)

    @property
    def norm(self) -> float:
        """Euclidean norm of the fatigue vector."""
        return math.sqrt(self.physical**2 + self.cognitive**2 + self.motivation**2)

    @property
    def is_critical(self) -> bool:
        """Check if fatigue exceeds safe threshold (raised to reduce false positives)."""
        return self.norm > 0.95  # Raised from 0.85 - 3D norm reaches 0.85 too quickly

    def to_dict(self) -> dict[str, float]:
        return {
            "physical": round(self.physical, 3),
            "cognitive": round(self.cognitive, 3),
            "motivation": round(self.motivation, 3),
            "norm": round(self.norm, 3),
        }


# =============================================================================
# CONFUSION MATRIX FOR PSI CALCULATION
# =============================================================================


class ConfusionMatrix:
    """
    Dynamic confusion matrix for Pattern Separation Index calculation.

    Tracks which concepts the learner confuses with which others.
    Used to detect Discrimination Failures (Dentate Gyrus pattern
    separation issues).

    Reference: Section 3.1.2 - The Confusion Matrix
    """

    def __init__(
        self,
        alpha: float = 0.2,  # Learning rate for confusion
        beta: float = 0.1,  # Decay rate for correct discriminations
    ):
        """
        Initialize the confusion matrix.

        Args:
            alpha: Learning rate for updating confusion probabilities
            beta: Decay rate for correct discriminations
        """
        self.alpha = alpha
        self.beta = beta
        self._matrix: dict[tuple[str, str], float] = {}
        self._timestamps: dict[tuple[str, str], datetime] = {}

    def record_confusion(self, target: str, selected: str) -> None:
        """
        Record a confusion event (user selected 'selected' when 'target' was correct).

        Update rule: M_ij ← M_ij + α(1 - M_ij)

        Args:
            target: The correct concept ID
            selected: The incorrectly selected concept ID
        """
        if target == selected:
            return  # Not a confusion

        key = (target, selected)
        current = self._matrix.get(key, 0.0)

        # Increase confusion probability
        new_value = current + self.alpha * (1 - current)
        self._matrix[key] = min(1.0, new_value)
        self._timestamps[key] = datetime.now()

        logger.debug(f"ConfusionMatrix: {target} → {selected}: {current:.3f} → {new_value:.3f}")

    def record_discrimination(self, target: str, selected: str) -> None:
        """
        Record a correct discrimination (user correctly identified target).

        Decay rule: M_ij ← M_ij * (1 - β)

        Args:
            target: The correct concept ID
            selected: The correctly selected concept ID
        """
        if target != selected:
            return  # This is a confusion, not discrimination

        # Decay all confusion probabilities involving this target
        keys_to_decay = [k for k in self._matrix.keys() if k[0] == target]

        for key in keys_to_decay:
            current = self._matrix[key]
            new_value = current * (1 - self.beta)
            self._matrix[key] = max(0.0, new_value)

    def get_psi(self, target: str) -> float:
        """
        Calculate Pattern Separation Index for a target concept.

        PSI_T = 1 - max(M_Tk for all k ≠ T)

        PSI ≈ 1: High separation (concepts are distinct)
        PSI ≈ 0: High interference (concepts are blurred)

        Args:
            target: The concept to calculate PSI for

        Returns:
            PSI value between 0 and 1
        """
        confusion_probs = [prob for (t, _), prob in self._matrix.items() if t == target]

        if not confusion_probs:
            return 1.0  # No confusion recorded = high separation

        max_confusion = max(confusion_probs)
        psi = 1 - max_confusion

        return max(0.0, min(1.0, psi))

    def get_worst_pair(self, target: str) -> tuple[str, float] | None:
        """
        Find the concept most confused with the target.

        Returns:
            Tuple of (confusable_id, confusion_probability) or None
        """
        pairs = [(selected, prob) for (t, selected), prob in self._matrix.items() if t == target]

        if not pairs:
            return None

        return max(pairs, key=lambda x: x[1])

    def get_confusables(self, target: str, threshold: float = 0.3) -> list[str]:
        """
        Get all concepts that exceed confusion threshold with target.

        Args:
            target: The target concept
            threshold: Minimum confusion probability

        Returns:
            List of confusable concept IDs
        """
        return [
            selected
            for (t, selected), prob in self._matrix.items()
            if t == target and prob >= threshold
        ]


# =============================================================================
# FATIGUE VECTOR CALCULATOR
# =============================================================================


class FatigueVectorCalculator:
    """
    Calculates multi-dimensional fatigue from telemetry history.

    Implements the fatigue vector model from Section 3.2:
    - f_physical: Motor fatigue (jitter, click accuracy)
    - f_cognitive: Resource depletion (RT variability)
    - f_motivation: Engagement drop (gaming behaviors)
    """

    def __init__(
        self,
        physical_jitter_threshold: float = 2.0,  # Z-score threshold
        cognitive_cv_threshold: float = 0.4,  # Coefficient of variation
        motivation_min_rt_ms: int = 500,  # Minimum human reading time
        window_size: int = 10,  # Rolling window for calculations
    ):
        self.physical_jitter_threshold = physical_jitter_threshold
        self.cognitive_cv_threshold = cognitive_cv_threshold
        self.motivation_min_rt_ms = motivation_min_rt_ms
        self.window_size = window_size

        # State
        self._history: list[NormalizedTelemetry] = []
        self._rt_history: list[int] = []
        self._baseline_rt_mean: float = 5000.0
        self._baseline_rt_std: float = 2000.0

    def update_baseline(self, rt_history: list[int]) -> None:
        """Update baseline statistics from learner history."""
        if len(rt_history) < 5:
            return

        self._baseline_rt_mean = sum(rt_history) / len(rt_history)
        variance = sum((x - self._baseline_rt_mean) ** 2 for x in rt_history)
        self._baseline_rt_std = math.sqrt(variance / len(rt_history))

    def add_observation(self, telemetry: NormalizedTelemetry) -> None:
        """Add a new telemetry observation."""
        self._history.append(telemetry)
        self._rt_history.append(telemetry.raw_response_time_ms)

        # Keep rolling window
        if len(self._history) > self.window_size * 2:
            self._history = self._history[-self.window_size * 2 :]
        if len(self._rt_history) > self.window_size * 2:
            self._rt_history = self._rt_history[-self.window_size * 2 :]

    def reset(self) -> None:
        """
        Clear history after a micro-break to reset fatigue calculation.

        Called when the learner takes a break, so fatigue doesn't
        immediately re-calculate to high values from old data.
        """
        self._history = []
        self._rt_history = []

    def calculate(self) -> FatigueVector:
        """
        Calculate current fatigue vector from recent history.

        Returns:
            FatigueVector with physical, cognitive, and motivation components
        """
        if len(self._history) < 3:
            return FatigueVector()

        recent = self._history[-self.window_size :]
        recent_rt = self._rt_history[-self.window_size :]

        # === Physical Fatigue (Motor) ===
        # Derived from cursor efficiency deviation
        efficiency_scores = [t.path_efficiency for t in recent if t.path_efficiency > 0]
        if efficiency_scores:
            avg_efficiency = sum(efficiency_scores) / len(efficiency_scores)
            # Lower efficiency = higher fatigue
            f_physical = max(0.0, 1 - avg_efficiency)
        else:
            f_physical = 0.0

        # === Cognitive Fatigue (Resource Depletion) ===
        # Derived from RT variability (coefficient of variation)
        if len(recent_rt) >= 3:
            rt_mean = sum(recent_rt) / len(recent_rt)
            rt_variance = sum((x - rt_mean) ** 2 for x in recent_rt) / len(recent_rt)
            rt_std = math.sqrt(rt_variance)
            cv = rt_std / rt_mean if rt_mean > 0 else 0

            # High CV = variable = fatigued
            f_cognitive = min(1.0, cv / self.cognitive_cv_threshold)
        else:
            f_cognitive = 0.0

        # Check for monotonic RT increase (slowing down)
        if len(recent_rt) >= 5:
            diffs = [recent_rt[i + 1] - recent_rt[i] for i in range(len(recent_rt) - 1)]
            increasing = sum(1 for d in diffs if d > 0)
            if increasing / len(diffs) > 0.7:
                f_cognitive = min(1.0, f_cognitive + 0.2)

        # === Motivational Fatigue (Disengagement) ===
        # Derived from "gaming" behaviors
        f_motivation = 0.0

        # Fast guesses (below human reading speed)
        fast_guesses = sum(1 for t in recent if t.raw_response_time_ms < self.motivation_min_rt_ms)
        if len(recent) > 0:
            fast_ratio = fast_guesses / len(recent)
            f_motivation = max(f_motivation, fast_ratio)

        # High selection volatility
        avg_volatility = sum(t.selection_volatility for t in recent) / len(recent)
        if avg_volatility > 2:
            f_motivation = max(f_motivation, 0.5)

        return FatigueVector(
            physical=round(f_physical, 3),
            cognitive=round(f_cognitive, 3),
            motivation=round(f_motivation, 3),
        )


# =============================================================================
# FEATURE EXTRACTOR
# =============================================================================


class FeatureExtractor:
    """
    Normalizes raw telemetry into z-scored features.

    Z-scoring ensures that "fast" for one learner isn't misinterpreted
    when compared to another learner's baseline.

    Reference: Section 2.3.1 - Response Time Dynamics
    """

    def __init__(self):
        # Baseline statistics (from learner history)
        self._rt_mean: float = 5000.0
        self._rt_std: float = 2000.0
        self._dwell_mean: float = 2000.0
        self._dwell_std: float = 1000.0
        self._efficiency_mean: float = 0.8
        self._efficiency_std: float = 0.15

    def update_baseline(
        self,
        rt_history: list[int],
        dwell_history: list[int] | None = None,
    ) -> None:
        """Update baseline statistics from learner's history."""
        if len(rt_history) >= 5:
            self._rt_mean = sum(rt_history) / len(rt_history)
            variance = sum((x - self._rt_mean) ** 2 for x in rt_history)
            self._rt_std = max(1.0, math.sqrt(variance / len(rt_history)))

        if dwell_history and len(dwell_history) >= 5:
            self._dwell_mean = sum(dwell_history) / len(dwell_history)
            variance = sum((x - self._dwell_mean) ** 2 for x in dwell_history)
            self._dwell_std = max(1.0, math.sqrt(variance / len(dwell_history)))

    def extract(self, raw: RawInteractionEvent) -> NormalizedTelemetry:
        """
        Extract normalized telemetry from raw interaction.

        Args:
            raw: The raw interaction event

        Returns:
            NormalizedTelemetry with z-scored features
        """
        # Z-score response time
        z_rt = (raw.response_time_ms - self._rt_mean) / self._rt_std

        # Z-score dwell time
        z_dwell = (raw.dwell_time_ms - self._dwell_mean) / self._dwell_std

        # Path efficiency
        if raw.cursor_path_length > 0:
            path_efficiency = raw.cursor_direct_distance / raw.cursor_path_length
        else:
            path_efficiency = 1.0

        # Hesitation index
        if raw.total_keystrokes > 0:
            hesitation_index = raw.backspace_count / raw.total_keystrokes
        else:
            hesitation_index = 0.0

        return NormalizedTelemetry(
            z_response_time=round(z_rt, 3),
            z_dwell_time=round(z_dwell, 3),
            z_cursor_efficiency=round(
                (path_efficiency - self._efficiency_mean) / self._efficiency_std, 3
            ),
            path_efficiency=round(path_efficiency, 3),
            hesitation_index=round(hesitation_index, 3),
            selection_volatility=raw.selection_changes,
            raw_response_time_ms=raw.response_time_ms,
            raw_dwell_time_ms=raw.dwell_time_ms,
        )


# =============================================================================
# REMEDIATION STRATEGIES
# =============================================================================


class RemediationStrategy(ABC):
    """Base class for remediation strategies."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Strategy name."""
        pass

    @abstractmethod
    def execute(self, session_context: SessionContext) -> RemediationResult:
        """Execute the remediation strategy."""
        pass


@dataclass
class RemediationResult:
    """Result of executing a remediation strategy."""

    strategy_name: str
    nodes_to_inject: list[dict] = field(default_factory=list)
    mode_switch: str | None = None  # "plm", "break", None
    message: str = ""
    should_suspend_current: bool = False


class StandardFlowStrategy(RemediationStrategy):
    """Continue with standard flow (no remediation needed)."""

    @property
    def name(self) -> str:
        return "standard"

    def execute(self, session_context: SessionContext) -> RemediationResult:
        return RemediationResult(
            strategy_name=self.name,
            message="Continue with standard flow",
        )


class MicroBreakStrategy(RemediationStrategy):
    """Trigger a micro-break due to fatigue."""

    def __init__(self, break_minutes: int = 5):
        self.break_minutes = break_minutes

    @property
    def name(self) -> str:
        return "micro_break"

    @property
    def message(self) -> str:
        return f"Cognitive fatigue detected. Take a {self.break_minutes}-minute break."

    def execute(self, session_context: SessionContext) -> RemediationResult:
        return RemediationResult(
            strategy_name=self.name,
            mode_switch="break",
            message=self.message,
            should_suspend_current=True,
        )


class ForceZStrategy(RemediationStrategy):
    """
    Force Z: Structural backtracking to repair foundational misconceptions.

    Named after the traversal shape: Back → Down → Forward

    Reference: Section 4.1 - Force Z: The Deep Backtracking Algorithm
    """

    def __init__(self, target_node_id: str, knowledge_graph: Any = None):
        self.target_node_id = target_node_id
        self.knowledge_graph = knowledge_graph

    @property
    def name(self) -> str:
        return "force_z"

    def execute(self, session_context: SessionContext) -> RemediationResult:
        # Find prerequisite chain
        prereq_path = self._find_prerequisite_path()

        if not prereq_path:
            # No prerequisites found, fall back to standard
            return RemediationResult(
                strategy_name=self.name,
                message="No prerequisite path found. Continuing with hint.",
            )

        return RemediationResult(
            strategy_name=self.name,
            nodes_to_inject=prereq_path,
            message=f"Backtracking to strengthen foundation: {len(prereq_path)} prerequisite(s)",
            should_suspend_current=True,
        )

    def _find_prerequisite_path(self) -> list[dict]:
        """Find the path of prerequisites to revisit."""
        # This would query the knowledge graph for prerequisites
        # For now, return empty - will be wired in integration
        return []


class PLMStrategy(RemediationStrategy):
    """
    PLM: Perceptual Learning Module for rapid discrimination training.

    Targets concepts with low PSI (high confusion) by training
    rapid categorization.

    Reference: Section 4.2 - PLM: The Perceptual Learning Module
    """

    def __init__(self, confusable_pair: tuple[str, str]):
        self.target_concept = confusable_pair[0]
        self.confusable_concept = confusable_pair[1]

    @property
    def name(self) -> str:
        return "plm"

    def execute(self, session_context: SessionContext) -> RemediationResult:
        # Generate PLM stimuli batch
        return RemediationResult(
            strategy_name=self.name,
            mode_switch="plm",
            message=f"Starting PLM: Discriminate '{self.target_concept}' vs '{self.confusable_concept}'",
            should_suspend_current=True,
        )


# =============================================================================
# REMEDIATION FACTORY
# =============================================================================


class RemediationSelector:
    """
    Factory for selecting appropriate remediation strategy.

    Applies a hierarchy of rules based on the NCDE diagnosis:
    1. Safety: If fatigue > threshold → MicroBreak
    2. Foundations: If Knowledge Gap → ForceZ
    3. Fluency: If Discrimination Failure → PLM
    4. Default: StandardFlow

    Reference: Section 4.3 - The Remediation Selector Logic
    """

    def __init__(
        self,
        fatigue_threshold: float = 0.7,
        psi_critical_threshold: float = 0.4,
    ):
        self.fatigue_threshold = fatigue_threshold
        self.psi_critical_threshold = psi_critical_threshold

    def select(
        self,
        diagnosis: CognitiveDiagnosis,
        fatigue: FatigueVector,
        psi: float,
        confusion_matrix: ConfusionMatrix,
        target_concept: str,
        session_context: SessionContext | None = None,
    ) -> RemediationStrategy:
        """
        Select the appropriate remediation strategy.

        Args:
            diagnosis: The cognitive diagnosis
            fatigue: Current fatigue vector
            psi: Pattern Separation Index for target
            confusion_matrix: The confusion matrix
            target_concept: The target concept ID
            session_context: Session context for interaction/time checks

        Returns:
            The selected RemediationStrategy
        """
        # Rule 1 (Safety): Check fatigue - but only after sufficient session activity
        # Evidence-based: Cognitive fatigue detection requires baseline data (min 10 interactions)
        # and meaningful time under load (10+ minutes) to avoid false positives
        if fatigue.is_critical:
            min_interactions_met = False
            min_time_met = False

            if session_context:
                total_interactions = session_context.correct_count + session_context.incorrect_count
                min_interactions_met = total_interactions >= 10
                min_time_met = session_context.duration_seconds >= 600  # 10 minutes

            if min_interactions_met or min_time_met:
                logger.info(f"RemediationSelector: Fatigue critical ({fatigue.norm:.2f})")
                return MicroBreakStrategy(break_minutes=10)
            else:
                logger.debug(
                    f"RemediationSelector: Fatigue signal ({fatigue.norm:.2f}) ignored - "
                    f"insufficient session data (need 10+ interactions or 10+ minutes)"
                )

        # Rule 2 (Foundations): Knowledge Gap → Force Z
        if diagnosis.fail_mode == FailMode.ENCODING_ERROR:
            logger.info("RemediationSelector: Encoding error → Force Z")
            return ForceZStrategy(target_node_id=target_concept)

        # Rule 3 (Fluency): Discrimination Failure → PLM
        if (
            diagnosis.fail_mode == FailMode.DISCRIMINATION_ERROR
            or psi < self.psi_critical_threshold
        ):
            worst_pair = confusion_matrix.get_worst_pair(target_concept)
            if worst_pair:
                logger.info("RemediationSelector: Discrimination failure → PLM")
                return PLMStrategy(confusable_pair=(target_concept, worst_pair[0]))

        # Rule 4 (Default): Standard flow
        return StandardFlowStrategy()


# =============================================================================
# SESSION CONTEXT
# =============================================================================


@dataclass
class SessionContext:
    """
    Shared context for the NCDE pipeline.

    Maintains the cognitive state across interactions within a session.
    """

    # Session metadata
    session_id: str
    learner_id: str
    start_time: datetime = field(default_factory=datetime.now)

    # Queue state
    current_node_id: str | None = None
    queue_position: int = 0
    queue_size: int = 0

    # Suspension stack for Force Z
    suspension_stack: list[dict] = field(default_factory=list)

    # Cognitive state
    fatigue: FatigueVector = field(default_factory=FatigueVector)
    psi_scores: dict[str, float] = field(default_factory=dict)

    # Cumulative stats
    correct_count: int = 0
    incorrect_count: int = 0
    error_streak: int = 0

    # History
    interaction_history: list[RawInteractionEvent] = field(default_factory=list)
    diagnosis_history: list[CognitiveDiagnosis] = field(default_factory=list)

    @property
    def duration_seconds(self) -> int:
        """Session duration in seconds."""
        return int((datetime.now() - self.start_time).total_seconds())

    @property
    def accuracy(self) -> float:
        """Current session accuracy."""
        total = self.correct_count + self.incorrect_count
        return self.correct_count / max(1, total)


# =============================================================================
# NCDE PIPELINE
# =============================================================================


class NCDEPipeline:
    """
    The complete Neuro-Cognitive Diagnosis Engine pipeline.

    Orchestrates the middleware chain:
    1. Feature Extraction
    2. Confusion Matrix Update
    3. Fatigue Calculation
    4. NeuroModel Inference
    5. Remediation Selection

    Reference: Section 1.3 - The Interception Middleware Architecture
    """

    def __init__(
        self,
        confusion_alpha: float = 0.2,
        confusion_beta: float = 0.1,
        fatigue_threshold: float = 0.7,
        psi_critical_threshold: float = 0.4,
    ):
        self.feature_extractor = FeatureExtractor()
        self.confusion_matrix = ConfusionMatrix(alpha=confusion_alpha, beta=confusion_beta)
        self.fatigue_calculator = FatigueVectorCalculator()
        self.remediation_selector = RemediationSelector(
            fatigue_threshold=fatigue_threshold,
            psi_critical_threshold=psi_critical_threshold,
        )

        # Pipeline hooks for extensibility
        self._pre_diagnosis_hooks: list[Callable] = []
        self._post_diagnosis_hooks: list[Callable] = []

    def add_pre_diagnosis_hook(self, hook: Callable) -> None:
        """Add a hook to run before diagnosis."""
        self._pre_diagnosis_hooks.append(hook)

    def add_post_diagnosis_hook(self, hook: Callable) -> None:
        """Add a hook to run after diagnosis."""
        self._post_diagnosis_hooks.append(hook)

    def process(
        self,
        raw_event: RawInteractionEvent,
        context: SessionContext,
    ) -> tuple[CognitiveDiagnosis, RemediationStrategy]:
        """
        Process an interaction through the NCDE pipeline.

        This is the main entry point for the cognitive loop.

        Args:
            raw_event: The raw interaction event
            context: The session context

        Returns:
            Tuple of (CognitiveDiagnosis, RemediationStrategy)
        """
        # Stage 1: Feature Extraction
        telemetry = self.feature_extractor.extract(raw_event)
        self.fatigue_calculator.add_observation(telemetry)

        logger.debug(f"NCDE: Feature extraction complete. Z_RT={telemetry.z_response_time:.2f}")

        # Stage 2: Update Confusion Matrix
        concept_id = raw_event.atom_id  # Use atom_id as concept proxy

        if raw_event.is_correct:
            self.confusion_matrix.record_discrimination(concept_id, concept_id)
        else:
            if raw_event.selected_distractor_id:
                self.confusion_matrix.record_confusion(
                    target=concept_id,
                    selected=raw_event.selected_distractor_id,
                )

        # Stage 3: Calculate Fatigue
        fatigue = self.fatigue_calculator.calculate()
        context.fatigue = fatigue

        logger.debug(f"NCDE: Fatigue vector = {fatigue.to_dict()}")

        # Stage 4: Run pre-diagnosis hooks
        for hook in self._pre_diagnosis_hooks:
            try:
                hook(raw_event, telemetry, context)
            except Exception as e:
                logger.warning(f"Pre-diagnosis hook failed: {e}")

        # Stage 5: NeuroModel Inference
        # Build atom dict for existing diagnose_interaction function
        atom_dict = {
            "id": raw_event.atom_id,
            "atom_type": raw_event.atom_type,
            "lapses": 0,  # Would come from learner persona
            "review_count": 0,
            "stability": 0,
            "ps_index": self.confusion_matrix.get_psi(concept_id),
            "pfit_index": 0.5,  # Default
        }

        # Build history for diagnosis
        recent_history = [
            {
                "atom_id": h.atom_id,
                "is_correct": h.is_correct,
                "response_time_ms": h.response_time_ms,
            }
            for h in context.interaction_history[-20:]
        ]

        diagnosis = diagnose_interaction(
            atom=atom_dict,
            is_correct=raw_event.is_correct,
            response_time_ms=raw_event.response_time_ms,
            recent_history=recent_history,
            session_duration_seconds=context.duration_seconds,
            session_error_streak=context.error_streak,
        )

        # Update diagnosis with fatigue override
        if fatigue.is_critical and diagnosis.fail_mode:
            # Force lapse classification if fatigued
            logger.debug("NCDE: Overriding diagnosis to FATIGUE due to high fatigue vector")
            diagnosis.fail_mode = FailMode.FATIGUE_ERROR
            diagnosis.remediation_type = RemediationType.REST

        # Store diagnosis
        context.diagnosis_history.append(diagnosis)

        logger.debug(
            f"NCDE: Diagnosis complete. "
            f"fail_mode={diagnosis.fail_mode}, "
            f"confidence={diagnosis.confidence:.2f}"
        )

        # Stage 6: Run post-diagnosis hooks
        for hook in self._post_diagnosis_hooks:
            try:
                hook(diagnosis, context)
            except Exception as e:
                logger.warning(f"Post-diagnosis hook failed: {e}")

        # Stage 7: Select Remediation Strategy
        psi = self.confusion_matrix.get_psi(concept_id)
        context.psi_scores[concept_id] = psi

        strategy = self.remediation_selector.select(
            diagnosis=diagnosis,
            fatigue=fatigue,
            psi=psi,
            confusion_matrix=self.confusion_matrix,
            target_concept=concept_id,
            session_context=context,
        )

        logger.debug(f"NCDE: Selected strategy: {strategy.name}")

        return diagnosis, strategy

    def update_learner_baseline(
        self,
        rt_history: list[int],
        dwell_history: list[int] | None = None,
    ) -> None:
        """Update baseline statistics from learner's historical data."""
        self.feature_extractor.update_baseline(rt_history, dwell_history)
        self.fatigue_calculator.update_baseline(rt_history)

    def reset_fatigue(self) -> None:
        """
        Reset fatigue calculator after a micro-break.

        Clears the fatigue calculator's history so that fatigue
        doesn't immediately re-calculate to high values after a break.
        """
        self.fatigue_calculator.reset()
        logger.info("NCDE: Fatigue calculator reset after micro-break")


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================


def create_raw_event(
    atom_id: str,
    atom_type: str,
    is_correct: bool,
    user_answer: str,
    correct_answer: str,
    response_time_ms: int,
    session_duration_seconds: int = 0,
    session_index: int = 0,
    selected_distractor_id: str | None = None,
) -> RawInteractionEvent:
    """
    Factory function to create a RawInteractionEvent.

    Simplifies event creation from the CortexSession run loop.
    """
    return RawInteractionEvent(
        atom_id=atom_id,
        atom_type=atom_type,
        is_correct=is_correct,
        user_answer=user_answer,
        correct_answer=correct_answer,
        response_time_ms=response_time_ms,
        session_duration_seconds=session_duration_seconds,
        session_index=session_index,
        selected_distractor_id=selected_distractor_id,
    )


# =============================================================================
# STRUGGLE WEIGHT UPDATE - Bridge to Dynamic Struggle Tracking
# =============================================================================


@dataclass
class StruggleUpdateData:
    """Data needed to update struggle weights from NCDE diagnosis."""

    module_number: int
    section_id: str | None
    failure_mode: str
    accuracy: float  # 0.0-1.0, where 0=incorrect, 1=correct
    atom_id: str | None = None
    session_id: str | None = None


def prepare_struggle_update(
    diagnosis: CognitiveDiagnosis,
    module_number: int,
    section_id: str | None,
    is_correct: bool,
    atom_id: str | None = None,
    session_id: str | None = None,
) -> StruggleUpdateData:
    """
    Prepare struggle update data from an NCDE diagnosis.

    This is called after each diagnosis to create data that can be
    passed to the database update function.

    Args:
        diagnosis: The cognitive diagnosis from NCDE
        module_number: CCNA module number (1-17)
        section_id: Section ID (e.g., "5.1.2") or None for module-level
        is_correct: Whether the user answered correctly
        atom_id: UUID of the atom being studied
        session_id: UUID of the current study session

    Returns:
        StruggleUpdateData ready for database insertion
    """
    # Convert correctness to accuracy score
    accuracy = 1.0 if is_correct else 0.0

    # Get failure mode name
    failure_mode = "unknown"
    if diagnosis.fail_mode:
        failure_mode = diagnosis.fail_mode.value

    return StruggleUpdateData(
        module_number=module_number,
        section_id=section_id,
        failure_mode=failure_mode,
        accuracy=accuracy,
        atom_id=atom_id,
        session_id=session_id,
    )


async def update_struggle_weight_async(
    db_session: Any,
    update_data: StruggleUpdateData,
) -> None:
    """
    Update struggle weights in the database (async version).

    Calls the PostgreSQL function update_struggle_from_ncde() which:
    1. Updates the ncde_weight in struggle_weights table
    2. Records the change in struggle_weight_history

    Args:
        db_session: SQLAlchemy async session
        update_data: The struggle update data from prepare_struggle_update
    """
    try:
        from sqlalchemy import text

        await db_session.execute(
            text(
                "SELECT update_struggle_from_ncde(:module, :section, :mode, :accuracy, :atom, :session)"
            ),
            {
                "module": update_data.module_number,
                "section": update_data.section_id,
                "mode": update_data.failure_mode,
                "accuracy": update_data.accuracy,
                "atom": update_data.atom_id,
                "session": update_data.session_id,
            },
        )
        await db_session.commit()
        logger.debug(
            f"NCDE: Updated struggle weight for module {update_data.module_number}, "
            f"section {update_data.section_id}, failure_mode={update_data.failure_mode}"
        )
    except Exception as e:
        logger.error(f"NCDE: Failed to update struggle weight: {e}")
        # Don't raise - struggle updates are non-critical


def update_struggle_weight_sync(
    db_connection: Any,
    update_data: StruggleUpdateData,
) -> None:
    """
    Update struggle weights in the database (sync version).

    For use with synchronous database connections.

    Args:
        db_connection: psycopg2 or similar sync connection
        update_data: The struggle update data from prepare_struggle_update
    """
    try:
        with db_connection.cursor() as cur:
            cur.execute(
                "SELECT update_struggle_from_ncde(%s, %s, %s, %s, %s, %s)",
                (
                    update_data.module_number,
                    update_data.section_id,
                    update_data.failure_mode,
                    update_data.accuracy,
                    update_data.atom_id,
                    update_data.session_id,
                ),
            )
        db_connection.commit()
        logger.debug(
            f"NCDE: Updated struggle weight for module {update_data.module_number}, "
            f"section {update_data.section_id}"
        )
    except Exception as e:
        logger.error(f"NCDE: Failed to update struggle weight: {e}")
        db_connection.rollback()
