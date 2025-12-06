"""
Neuromorphic Cognitive Engine for Cortex.

Implements PhD-level cognitive science for error classification and remediation.
Maps behavioral signatures to brain regions and cognitive processes:

HIPPOCAMPAL SYSTEM:
- Dentate Gyrus: Pattern separation (distinguishing similar concepts)
- CA3: Pattern completion (retrieving from partial cues)
- CA1: Memory consolidation

P-FIT (Parieto-Frontal Integration Theory):
- Parietal cortex: Symbolic manipulation
- Frontal cortex: Working memory, executive control
- Integration: Fluid reasoning ability

PREFRONTAL CORTEX:
- Executive function: Impulse control, task switching
- Cognitive control: Attention, inhibition

Based on research from:
- Norman & O'Reilly (2003): Hippocampal pattern separation
- Jung & Haier (2007): P-FIT theory of intelligence
- Cognitive Load Theory (Sweller, 1988)
- Perceptual Learning research (Kellman & Garrigan, 2009)

Author: Cortex System
Version: 2.0.0 (Neuromorphic Architecture)
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Optional
from uuid import UUID

from loguru import logger


# =============================================================================
# COGNITIVE STATE MACHINE
# =============================================================================

class CognitiveState(str, Enum):
    """
    Learner's current cognitive state (Csikszentmihalyi's Flow Model).

    Maps to the challenge-skill balance:
    - FLOW: Optimal engagement (challenge ≈ skill)
    - ANXIETY: Overwhelmed (challenge >> skill)
    - BOREDOM: Disengaged (skill >> challenge)
    - FATIGUE: Resource depletion (time/effort exhausted)
    - DISTRACTED: Attention fragmented (external/internal interrupts)
    """
    FLOW = "flow"              # Challenge matches skill - optimal learning
    ANXIETY = "anxiety"        # Challenge exceeds skill - overwhelmed
    BOREDOM = "boredom"        # Skill exceeds challenge - disengaged
    FATIGUE = "fatigue"        # Cognitive resources depleted
    DISTRACTED = "distracted"  # Attention elsewhere


# =============================================================================
# FAILURE MODE TAXONOMY
# =============================================================================

class FailMode(str, Enum):
    """
    Classification of error types by cognitive system.

    Each fail mode maps to a specific brain region and requires
    a different remediation strategy:

    HIPPOCAMPAL (Memory):
    - ENCODING_ERROR: Never consolidated (Dentate Gyrus failure)
    - RETRIEVAL_ERROR: Stored but can't access (CA3/CA1 failure)
    - DISCRIMINATION_ERROR: Confused similar items (Pattern separation failure)

    P-FIT (Reasoning):
    - INTEGRATION_ERROR: Facts don't connect (Parietal-Frontal disconnection)

    PREFRONTAL (Executive):
    - EXECUTIVE_ERROR: Impulsivity, didn't read carefully (PFC failure)

    GLOBAL:
    - FATIGUE_ERROR: Cognitive exhaustion (Resource depletion)
    """
    # Hippocampal failures
    ENCODING_ERROR = "encoding"           # Never learned - Hippocampus
    RETRIEVAL_ERROR = "retrieval"         # Forgot - CA3/CA1
    DISCRIMINATION_ERROR = "discrimination"  # Confused similar - Dentate Gyrus

    # P-FIT failures
    INTEGRATION_ERROR = "integration"     # Can't connect facts - P-FIT

    # Prefrontal failures
    EXECUTIVE_ERROR = "executive"         # Impulsive/careless - PFC

    # Global failures
    FATIGUE_ERROR = "fatigue"             # Exhausted - Global


class SuccessMode(str, Enum):
    """
    Classification of success patterns.

    Understanding HOW the learner succeeded is as important as
    knowing THAT they succeeded:

    RECALL: Retrieved from memory (tests hippocampal consolidation)
    RECOGNITION: Identified among options (easier, primed by cues)
    INFERENCE: Derived from related knowledge (tests P-FIT integration)
    FLUENCY: Automatic, effortless (<2s, tests proceduralization)
    """
    RECALL = "recall"              # Retrieved from memory
    RECOGNITION = "recognition"    # Recognized among options
    INFERENCE = "inference"        # Derived from related knowledge
    FLUENCY = "fluency"            # Automatic, effortless (<2s)


# =============================================================================
# REMEDIATION STRATEGIES
# =============================================================================

class RemediationType(str, Enum):
    """
    Remediation strategies mapped to fail modes.

    Each strategy targets the specific cognitive deficit:
    """
    # For ENCODING_ERROR
    ELABORATE = "elaborate"           # Explain differently, analogies
    READ_SOURCE = "read_source"       # Go back to source material

    # For RETRIEVAL_ERROR
    SPACED_REPEAT = "spaced_repeat"   # Standard FSRS (default)
    RETRIEVAL_PRACTICE = "retrieval"  # Generate answer, not recognize

    # For DISCRIMINATION_ERROR
    CONTRASTIVE = "contrastive"       # Compare/contrast similar items
    ADVERSARIAL = "adversarial"       # Practice with confusable lures

    # For INTEGRATION_ERROR
    WORKED_EXAMPLE = "worked_example" # Step-by-step walkthrough
    SCAFFOLDED = "scaffolded"         # Hints that fade over time

    # For EXECUTIVE_ERROR
    SLOW_DOWN = "slow_down"           # Forced delay before answering
    INHIBITION = "inhibition"         # Explicit "read carefully" prompt

    # For FATIGUE_ERROR
    REST = "rest"                     # Take a break
    MODE_SWITCH = "mode_switch"       # Switch to easier modality

    # Success continuation
    CONTINUE = "continue"             # Keep going
    ACCELERATE = "accelerate"         # Increase difficulty


# =============================================================================
# COGNITIVE DIAGNOSIS
# =============================================================================

@dataclass
class CognitiveDiagnosis:
    """
    Complete cognitive diagnosis for an interaction.

    This is the core output of the neuromorphic engine - it tells us:
    1. WHY the learner failed/succeeded (not just that they did)
    2. WHAT brain system is involved
    3. HOW to remediate effectively

    The diagnosis drives all downstream decisions including:
    - Remediation routing
    - LLM prompt construction
    - Calendar scheduling
    - Learner persona updates
    """
    # Core classification
    fail_mode: Optional[FailMode] = None
    success_mode: Optional[SuccessMode] = None
    cognitive_state: CognitiveState = CognitiveState.FLOW

    # Confidence and evidence
    confidence: float = 0.0  # 0-1 confidence in diagnosis
    evidence: list[str] = field(default_factory=list)

    # Remediation
    remediation_type: RemediationType = RemediationType.SPACED_REPEAT
    remediation_params: dict[str, Any] = field(default_factory=dict)
    remediation_target: Optional[str] = None  # Source section or concept ID

    # Additional context
    ps_index: float = 0.0  # Pattern separation index for discrimination
    pfit_index: float = 0.0  # P-FIT index for integration
    hippocampal_index: float = 0.0  # Memory consolidation index

    # Explanation for learner
    explanation: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "fail_mode": self.fail_mode.value if self.fail_mode else None,
            "success_mode": self.success_mode.value if self.success_mode else None,
            "cognitive_state": self.cognitive_state.value,
            "confidence": round(self.confidence, 3),
            "evidence": self.evidence,
            "remediation_type": self.remediation_type.value,
            "remediation_params": self.remediation_params,
            "remediation_target": self.remediation_target,
            "ps_index": round(self.ps_index, 3),
            "pfit_index": round(self.pfit_index, 3),
            "hippocampal_index": round(self.hippocampal_index, 3),
            "explanation": self.explanation,
        }


# =============================================================================
# THRESHOLDS (Evidence-Based)
# =============================================================================

THRESHOLDS = {
    # Response time thresholds (milliseconds)
    "fluency_max_ms": 2000,         # < 2s = automatic/fluent
    "impulsivity_max_ms": 1500,     # < 1.5s + wrong = impulsive
    "normal_min_ms": 2000,          # 2-10s = normal thinking
    "normal_max_ms": 10000,         # > 10s = struggling or fatigued
    "fatigue_threshold_ms": 12000,  # > 12s = likely fatigued

    # PLM (Perceptual Learning) thresholds
    "plm_target_ms": 1000,          # Target for perceptual fluency
    "plm_window_size": 10,          # Items to check for fluency pattern

    # Session thresholds
    "fatigue_session_minutes": 45,  # After 45 min, fatigue likely
    "fatigue_error_streak": 5,      # 5 errors in a row = fatigue
    "optimal_session_minutes": 25,  # Pomodoro-style optimal

    # Encoding failure thresholds
    "encoding_min_reviews": 3,      # Need 3+ reviews before it's retrieval
    "encoding_max_stability": 7,    # Stability < 7 days = still encoding

    # Pattern separation thresholds
    "ps_high_threshold": 0.8,       # High similarity = discrimination risk
    "ps_adversarial_threshold": 0.9,  # Very high = adversarial lure

    # Struggle pattern thresholds
    "struggle_window_size": 5,      # Look at last 5 interactions
    "struggle_failure_rate": 0.4,   # 40% failure = struggling
    "critical_failure_rate": 0.6,   # 60% = critical, stop quizzing

    # Lapses thresholds
    "chronic_lapse_threshold": 3,   # 3+ lapses = encoding problem
    "acute_lapse_threshold": 5,     # 5+ lapses = fundamental gap
}


# =============================================================================
# CORE DIAGNOSIS FUNCTION
# =============================================================================

def diagnose_interaction(
    atom: dict[str, Any],
    is_correct: bool,
    response_time_ms: int,
    recent_history: list[dict[str, Any]],
    session_duration_seconds: int = 0,
    session_error_streak: int = 0,
    confusable_atoms: Optional[list[dict]] = None,
) -> CognitiveDiagnosis:
    """
    Analyze an interaction to produce a cognitive diagnosis.

    This is the core function of the neuromorphic engine. It analyzes
    behavioral signatures to determine the cognitive cause of success/failure.

    Algorithm:
    1. If correct: classify success type (fluency, recall, inference)
    2. If incorrect: classify failure type based on:
       - Response time (fast fail = executive error)
       - Atom type (numeric/parsons = integration error)
       - History (repeated fail = encoding error)
       - Similarity (high ps_index = discrimination error)
       - Session state (long/many errors = fatigue error)

    Args:
        atom: The atom dict with fields like id, atom_type, lapses, etc.
        is_correct: Whether the answer was correct
        response_time_ms: Time taken to answer in milliseconds
        recent_history: Last 10-20 interactions for pattern detection
        session_duration_seconds: How long the current session has run
        session_error_streak: Consecutive errors in current session
        confusable_atoms: List of similar atoms for discrimination analysis

    Returns:
        CognitiveDiagnosis with fail_mode, success_mode, remediation, etc.
    """
    evidence = []
    candidates: list[tuple[FailMode, float, list[str]]] = []  # (mode, confidence, evidence)

    # Extract atom metadata
    atom_type = atom.get("atom_type", "flashcard")
    lapses = atom.get("lapses", 0) or atom.get("anki_lapses", 0) or 0
    review_count = atom.get("review_count", 0) or atom.get("anki_review_count", 0) or 0
    stability = atom.get("stability", 0) or atom.get("anki_stability", 0) or 0
    ps_index = atom.get("ps_index", 0) or atom.get("pattern_separation_index", 0) or 0.5
    pfit_index = atom.get("pfit_index", 0) or 0.5

    # === HANDLE SUCCESS ===
    if is_correct:
        return _diagnose_success(
            atom=atom,
            response_time_ms=response_time_ms,
            recent_history=recent_history,
            ps_index=ps_index,
            pfit_index=pfit_index,
        )

    # === FAILURE DIAGNOSIS ===

    # Check 1: EXECUTIVE ERROR (PFC failure - impulsivity)
    if response_time_ms < THRESHOLDS["impulsivity_max_ms"]:
        confidence = 1.0 - (response_time_ms / THRESHOLDS["impulsivity_max_ms"])
        evidence_item = f"Response time {response_time_ms}ms < {THRESHOLDS['impulsivity_max_ms']}ms (impulsive)"
        candidates.append((
            FailMode.EXECUTIVE_ERROR,
            min(0.85, confidence * 0.9),  # Cap at 0.85
            [evidence_item]
        ))

    # Check 2: FATIGUE ERROR (Global depletion)
    fatigue_signals = 0
    fatigue_evidence = []

    if response_time_ms > THRESHOLDS["fatigue_threshold_ms"]:
        fatigue_signals += 1
        fatigue_evidence.append(f"Slow response: {response_time_ms}ms")

    session_minutes = session_duration_seconds / 60
    if session_minutes > THRESHOLDS["fatigue_session_minutes"]:
        fatigue_signals += 1
        fatigue_evidence.append(f"Session duration: {session_minutes:.0f} minutes")

    if session_error_streak >= THRESHOLDS["fatigue_error_streak"]:
        fatigue_signals += 2  # Double weight
        fatigue_evidence.append(f"Error streak: {session_error_streak} consecutive")

    if fatigue_signals >= 2:
        candidates.append((
            FailMode.FATIGUE_ERROR,
            min(0.9, fatigue_signals * 0.25),
            fatigue_evidence
        ))

    # Check 3: ENCODING ERROR (Hippocampus - never consolidated)
    if review_count < THRESHOLDS["encoding_min_reviews"] and stability < THRESHOLDS["encoding_max_stability"]:
        encoding_confidence = 0.7 - (review_count * 0.15)
        encoding_evidence = [
            f"Low review count: {review_count}",
            f"Low stability: {stability:.1f} days"
        ]
        candidates.append((
            FailMode.ENCODING_ERROR,
            max(0.4, encoding_confidence),
            encoding_evidence
        ))

    # Check 4: ENCODING ERROR (Chronic lapses)
    if lapses >= THRESHOLDS["chronic_lapse_threshold"]:
        lapse_confidence = min(0.85, 0.5 + (lapses * 0.1))
        lapse_evidence = [f"Chronic lapses: {lapses} (threshold: {THRESHOLDS['chronic_lapse_threshold']})"]
        candidates.append((
            FailMode.ENCODING_ERROR,
            lapse_confidence,
            lapse_evidence
        ))

    # Check 5: DISCRIMINATION ERROR (Dentate Gyrus - pattern separation failure)
    if ps_index > THRESHOLDS["ps_high_threshold"]:
        disc_confidence = 0.6 + (ps_index - THRESHOLDS["ps_high_threshold"]) * 2
        disc_evidence = [f"High pattern separation index: {ps_index:.2f} (confusable content)"]

        # Check if there are similar atoms in history
        if confusable_atoms:
            disc_evidence.append(f"Confusable with {len(confusable_atoms)} similar atoms")
            disc_confidence += 0.1

        candidates.append((
            FailMode.DISCRIMINATION_ERROR,
            min(0.9, disc_confidence),
            disc_evidence
        ))

    # Check 6: INTEGRATION ERROR (P-FIT failure)
    if atom_type in ("numeric", "parsons", "ranking", "sequence"):
        integration_confidence = 0.7
        integration_evidence = [f"Procedural atom type: {atom_type}"]

        # Higher confidence if pfit_index is high (requires more integration)
        if pfit_index > 0.7:
            integration_confidence += 0.1
            integration_evidence.append(f"High P-FIT index: {pfit_index:.2f}")

        candidates.append((
            FailMode.INTEGRATION_ERROR,
            integration_confidence,
            integration_evidence
        ))

    # === SELECT BEST DIAGNOSIS ===
    if not candidates:
        # Default to retrieval failure
        return CognitiveDiagnosis(
            fail_mode=FailMode.RETRIEVAL_ERROR,
            success_mode=None,
            cognitive_state=CognitiveState.FLOW,
            confidence=0.5,
            evidence=["Default: No specific pattern detected"],
            remediation_type=RemediationType.SPACED_REPEAT,
            explanation="Standard memory decay. Continued spaced repetition will strengthen this memory.",
            ps_index=ps_index,
            pfit_index=pfit_index,
            hippocampal_index=_compute_hippocampal_index(stability, lapses, review_count),
        )

    # Sort by confidence
    candidates.sort(key=lambda x: x[1], reverse=True)
    best_mode, best_confidence, best_evidence = candidates[0]

    # Build diagnosis
    diagnosis = CognitiveDiagnosis(
        fail_mode=best_mode,
        success_mode=None,
        cognitive_state=_infer_cognitive_state(best_mode, session_minutes, session_error_streak),
        confidence=best_confidence,
        evidence=best_evidence,
        ps_index=ps_index,
        pfit_index=pfit_index,
        hippocampal_index=_compute_hippocampal_index(stability, lapses, review_count),
    )

    # Set remediation
    _set_remediation(diagnosis, atom)

    logger.debug(
        f"Cognitive diagnosis: {diagnosis.fail_mode.value} "
        f"(confidence={diagnosis.confidence:.2f}) - {diagnosis.evidence}"
    )

    return diagnosis


def _diagnose_success(
    atom: dict[str, Any],
    response_time_ms: int,
    recent_history: list[dict[str, Any]],
    ps_index: float,
    pfit_index: float,
) -> CognitiveDiagnosis:
    """
    Diagnose the type of success (fluency, recall, inference, recognition).
    """
    stability = atom.get("stability", 0) or atom.get("anki_stability", 0) or 0
    lapses = atom.get("lapses", 0) or atom.get("anki_lapses", 0) or 0
    review_count = atom.get("review_count", 0) or atom.get("anki_review_count", 0) or 0
    atom_type = atom.get("atom_type", "flashcard")

    # FLUENCY: Fast and correct (< 2s) indicates automaticity
    if response_time_ms < THRESHOLDS["fluency_max_ms"]:
        return CognitiveDiagnosis(
            fail_mode=None,
            success_mode=SuccessMode.FLUENCY,
            cognitive_state=CognitiveState.FLOW,
            confidence=0.8,
            evidence=[f"Fast response: {response_time_ms}ms (automatic retrieval)"],
            remediation_type=RemediationType.ACCELERATE,
            explanation="Excellent! This knowledge is becoming automatic.",
            ps_index=ps_index,
            pfit_index=pfit_index,
            hippocampal_index=_compute_hippocampal_index(stability, lapses, review_count),
        )

    # INFERENCE: Success on integration-heavy atoms
    if atom_type in ("numeric", "parsons", "ranking") and pfit_index > 0.6:
        return CognitiveDiagnosis(
            fail_mode=None,
            success_mode=SuccessMode.INFERENCE,
            cognitive_state=CognitiveState.FLOW,
            confidence=0.7,
            evidence=[f"Success on {atom_type} with P-FIT index {pfit_index:.2f}"],
            remediation_type=RemediationType.CONTINUE,
            explanation="Good integration! You're connecting facts into understanding.",
            ps_index=ps_index,
            pfit_index=pfit_index,
            hippocampal_index=_compute_hippocampal_index(stability, lapses, review_count),
        )

    # RECOGNITION: MCQ/True-False (cued recall, easier)
    if atom_type in ("mcq", "true_false", "matching"):
        return CognitiveDiagnosis(
            fail_mode=None,
            success_mode=SuccessMode.RECOGNITION,
            cognitive_state=CognitiveState.FLOW,
            confidence=0.6,
            evidence=[f"Recognition-based success on {atom_type}"],
            remediation_type=RemediationType.CONTINUE,
            remediation_params={"suggest_upgrade": "Consider flashcard for deeper encoding"},
            explanation="Good recognition! Try free recall next time for deeper learning.",
            ps_index=ps_index,
            pfit_index=pfit_index,
            hippocampal_index=_compute_hippocampal_index(stability, lapses, review_count),
        )

    # RECALL: Default success (free recall)
    return CognitiveDiagnosis(
        fail_mode=None,
        success_mode=SuccessMode.RECALL,
        cognitive_state=CognitiveState.FLOW,
        confidence=0.7,
        evidence=["Successful free recall"],
        remediation_type=RemediationType.CONTINUE,
        explanation="Solid recall! Memory trace strengthened.",
        ps_index=ps_index,
        pfit_index=pfit_index,
        hippocampal_index=_compute_hippocampal_index(stability, lapses, review_count),
    )


def _compute_hippocampal_index(stability: float, lapses: int, review_count: int) -> float:
    """
    Compute hippocampal consolidation index (0-1).

    Higher = better consolidated memory.
    """
    if review_count == 0:
        return 0.0

    # Stability contribution (normalized to ~30 days max)
    stability_score = min(1.0, stability / 30) * 0.5

    # Lapse penalty
    lapse_penalty = min(0.3, lapses * 0.05)

    # Review count contribution (diminishing returns after 10)
    review_score = min(0.3, math.log1p(review_count) / 10)

    return max(0.0, min(1.0, stability_score + review_score - lapse_penalty))


def _infer_cognitive_state(
    fail_mode: FailMode,
    session_minutes: float,
    error_streak: int,
) -> CognitiveState:
    """Infer cognitive state from fail mode and session context."""
    if fail_mode == FailMode.FATIGUE_ERROR:
        return CognitiveState.FATIGUE

    if fail_mode == FailMode.EXECUTIVE_ERROR:
        return CognitiveState.DISTRACTED

    if session_minutes > 40 or error_streak >= 4:
        return CognitiveState.FATIGUE

    if fail_mode in (FailMode.ENCODING_ERROR, FailMode.INTEGRATION_ERROR):
        return CognitiveState.ANXIETY  # Material is too hard

    return CognitiveState.FLOW


def _set_remediation(diagnosis: CognitiveDiagnosis, atom: dict[str, Any]) -> None:
    """Set remediation strategy based on diagnosis."""
    source_section = atom.get("source_fact_basis") or atom.get("section_id") or atom.get("ccna_section_id")
    concept_id = atom.get("concept_id")

    if diagnosis.fail_mode == FailMode.EXECUTIVE_ERROR:
        diagnosis.remediation_type = RemediationType.SLOW_DOWN
        diagnosis.remediation_params = {"delay_ms": 3000}
        diagnosis.explanation = (
            "You answered too quickly. Take a breath, read carefully, "
            "then respond. Speed isn't the goal - accuracy is."
        )

    elif diagnosis.fail_mode == FailMode.FATIGUE_ERROR:
        diagnosis.remediation_type = RemediationType.REST
        diagnosis.remediation_params = {"break_minutes": 10}
        diagnosis.explanation = (
            "Cognitive fatigue detected. Your brain needs rest to consolidate. "
            "Take a 10-minute break - you've earned it."
        )

    elif diagnosis.fail_mode == FailMode.ENCODING_ERROR:
        diagnosis.remediation_type = RemediationType.READ_SOURCE
        diagnosis.remediation_target = source_section
        diagnosis.remediation_params = {
            "action": "read_source",
            "section": source_section,
        }
        diagnosis.explanation = (
            "This concept wasn't fully encoded. Go back to the source material "
            f"and re-read it with intention. Section: {source_section or 'Unknown'}"
        )

    elif diagnosis.fail_mode == FailMode.DISCRIMINATION_ERROR:
        diagnosis.remediation_type = RemediationType.CONTRASTIVE
        diagnosis.remediation_target = concept_id
        diagnosis.remediation_params = {
            "action": "contrastive_review",
            "concept_id": concept_id,
        }
        diagnosis.explanation = (
            "You're confusing similar concepts. Let's do a side-by-side "
            "comparison to highlight the differences."
        )

    elif diagnosis.fail_mode == FailMode.INTEGRATION_ERROR:
        diagnosis.remediation_type = RemediationType.WORKED_EXAMPLE
        diagnosis.remediation_target = atom.get("id")
        diagnosis.remediation_params = {
            "action": "worked_example",
            "atom_id": atom.get("id"),
        }
        diagnosis.explanation = (
            "The pieces aren't connecting. Let me walk you through "
            "a worked example step-by-step."
        )

    else:  # RETRIEVAL_ERROR
        diagnosis.remediation_type = RemediationType.SPACED_REPEAT
        diagnosis.explanation = (
            "Normal forgetting curve. Spaced repetition will strengthen "
            "this memory trace over time."
        )


# =============================================================================
# PERCEPTUAL LEARNING MODULE (PLM)
# =============================================================================

@dataclass
class PLMResult:
    """
    Result from Perceptual Learning Module analysis.

    PLMs train rapid pattern recognition (<1000ms) for:
    - Visual discrimination (similar-looking formulas)
    - Conceptual discrimination (similar-meaning concepts)
    - Procedural discrimination (similar-looking steps)
    """
    is_fluent: bool = False
    avg_response_ms: float = 0.0
    fluency_rate: float = 0.0
    needs_plm_training: bool = False
    confusable_pairs: list[tuple[str, str]] = field(default_factory=list)
    recommendation: str = ""


def analyze_perceptual_fluency(
    atom_id: str,
    recent_history: list[dict[str, Any]],
    target_ms: int = THRESHOLDS["plm_target_ms"],
) -> PLMResult:
    """
    Analyze if learner has achieved perceptual fluency for an atom.

    Perceptual Learning Modules (PLMs) train rapid categorization:
    - Goal: <1000ms response time with >90% accuracy
    - Method: High-volume, varied presentations of confusable pairs

    Args:
        atom_id: The atom to analyze
        recent_history: Recent interactions (last 20+)
        target_ms: Target response time for fluency

    Returns:
        PLMResult with fluency analysis and recommendations
    """
    # Filter history for this atom
    atom_history = [
        h for h in recent_history
        if h.get("atom_id") == atom_id
    ]

    if len(atom_history) < 3:
        return PLMResult(
            is_fluent=False,
            needs_plm_training=False,
            recommendation="Insufficient data for PLM analysis",
        )

    # Calculate metrics
    response_times = [h.get("response_time_ms", 5000) for h in atom_history]
    correct_count = sum(1 for h in atom_history if h.get("is_correct", False))

    avg_response = sum(response_times) / len(response_times)
    accuracy = correct_count / len(atom_history)

    # Check fluency criteria
    fast_responses = sum(1 for t in response_times if t < target_ms)
    fluency_rate = fast_responses / len(response_times)

    is_fluent = fluency_rate > 0.8 and accuracy > 0.9
    needs_training = fluency_rate < 0.5 and accuracy > 0.7  # Accurate but slow

    return PLMResult(
        is_fluent=is_fluent,
        avg_response_ms=avg_response,
        fluency_rate=fluency_rate,
        needs_plm_training=needs_training,
        recommendation=(
            "Perceptual fluency achieved! Consider increasing difficulty."
            if is_fluent else
            "PLM training recommended: Practice rapid discrimination."
            if needs_training else
            "Continue standard practice."
        ),
    )


# =============================================================================
# STRUGGLE PATTERN DETECTION
# =============================================================================

@dataclass
class StrugglePattern:
    """Detected pattern of struggle requiring intervention."""
    concept_id: str
    concept_name: str
    failure_count: int
    total_attempts: int
    failure_rate: float
    avg_response_time_ms: float
    primary_fail_mode: Optional[FailMode] = None
    recommendation: str = ""
    source_reference: Optional[str] = None
    priority: str = "medium"  # "critical", "high", "medium", "low"

    @property
    def is_critical(self) -> bool:
        """Critical if failure rate > 60% or 5+ consecutive failures."""
        return self.failure_rate > THRESHOLDS["critical_failure_rate"] or self.failure_count >= 5


def detect_struggle_pattern(
    session_history: list[dict[str, Any]],
    window_size: int = THRESHOLDS["struggle_window_size"],
) -> Optional[StrugglePattern]:
    """
    Detect if learner is struggling with a specific concept.

    This triggers the metacognitive intervention:
    "Stop quizzing. Go read Section X.Y.Z."

    Args:
        session_history: Recent interactions
        window_size: Number of recent interactions to analyze

    Returns:
        StrugglePattern if detected, None otherwise
    """
    if len(session_history) < window_size:
        return None

    recent = session_history[-window_size:]

    # Group by concept
    concept_stats: dict[str, dict] = {}
    for interaction in recent:
        cid = interaction.get("concept_id")
        if not cid:
            continue

        if cid not in concept_stats:
            concept_stats[cid] = {
                "name": interaction.get("concept_name", "Unknown"),
                "section": interaction.get("section_id") or interaction.get("source_fact_basis"),
                "failures": 0,
                "total": 0,
                "response_times": [],
                "fail_modes": [],
            }

        concept_stats[cid]["total"] += 1
        if not interaction.get("is_correct", True):
            concept_stats[cid]["failures"] += 1
            if interaction.get("fail_mode"):
                concept_stats[cid]["fail_modes"].append(interaction["fail_mode"])

        concept_stats[cid]["response_times"].append(
            interaction.get("response_time_ms", 0)
        )

    # Find struggling concepts
    for cid, stats in concept_stats.items():
        if stats["total"] < 2:
            continue

        failure_rate = stats["failures"] / stats["total"]

        if failure_rate >= THRESHOLDS["struggle_failure_rate"]:
            avg_rt = sum(stats["response_times"]) / len(stats["response_times"])

            # Determine primary fail mode
            fail_mode_counts: dict[str, int] = {}
            for fm in stats["fail_modes"]:
                fail_mode_counts[fm] = fail_mode_counts.get(fm, 0) + 1

            primary_mode = None
            if fail_mode_counts:
                primary_mode = FailMode(max(fail_mode_counts, key=fail_mode_counts.get))

            # Generate recommendation
            if failure_rate >= THRESHOLDS["critical_failure_rate"]:
                recommendation = (
                    f"CRITICAL: Stop flashcards. Re-read Section {stats['section']}. "
                    f"Error pattern: {primary_mode.value if primary_mode else 'mixed'} failures."
                )
                priority = "critical"
            else:
                recommendation = (
                    f"Consider reviewing Section {stats['section']} before continuing. "
                    f"Failure rate: {failure_rate:.0%}"
                )
                priority = "high" if failure_rate > 0.5 else "medium"

            return StrugglePattern(
                concept_id=cid,
                concept_name=stats["name"],
                failure_count=stats["failures"],
                total_attempts=stats["total"],
                failure_rate=failure_rate,
                avg_response_time_ms=avg_rt,
                primary_fail_mode=primary_mode,
                recommendation=recommendation,
                source_reference=stats["section"],
                priority=priority,
            )

    return None


# =============================================================================
# COGNITIVE LOAD ESTIMATION
# =============================================================================

@dataclass
class CognitiveLoadMetrics:
    """Cognitive load estimation for session management."""
    load_percent: int = 0
    load_level: str = "low"  # "low", "moderate", "high", "critical"
    intrinsic_load: float = 0.0  # Complexity of material
    extraneous_load: float = 0.0  # Environmental/presentation factors
    germane_load: float = 0.0  # Productive learning effort
    recommendation: str = ""
    factors: dict[str, float] = field(default_factory=dict)


def compute_cognitive_load(
    session_history: list[dict[str, Any]],
    session_duration_seconds: int,
    current_atom: Optional[dict[str, Any]] = None,
) -> CognitiveLoadMetrics:
    """
    Compute current cognitive load using Sweller's CLT model.

    Total Load = Intrinsic + Extraneous + Germane

    When Total Load > Working Memory Capacity:
    - Learning fails
    - Need to reduce extraneous or pause

    Args:
        session_history: Recent interactions
        session_duration_seconds: Session duration
        current_atom: Current atom (for intrinsic load)

    Returns:
        CognitiveLoadMetrics with breakdown and recommendations
    """
    if not session_history:
        return CognitiveLoadMetrics(
            load_percent=0,
            load_level="low",
            recommendation="Ready to learn! Cognitive resources available.",
        )

    recent = session_history[-10:] if len(session_history) >= 10 else session_history

    # === INTRINSIC LOAD (Material complexity) ===
    # Estimated from atom type and P-FIT index
    intrinsic = 0.3  # Base
    if current_atom:
        atom_type = current_atom.get("atom_type", "flashcard")
        pfit = current_atom.get("pfit_index", 0.5)

        type_complexity = {
            "flashcard": 0.2, "cloze": 0.3, "true_false": 0.2,
            "mcq": 0.4, "matching": 0.4,
            "parsons": 0.7, "numeric": 0.8, "ranking": 0.6,
        }
        intrinsic = type_complexity.get(atom_type, 0.3) * (0.5 + pfit)

    # === EXTRANEOUS LOAD (Session fatigue) ===
    session_minutes = session_duration_seconds / 60

    # Time factor (increases after 25 min)
    time_factor = min(0.3, max(0, session_minutes - 25) / 50)

    # Error streak factor
    error_streak = 0
    for h in reversed(recent):
        if not h.get("is_correct", True):
            error_streak += 1
        else:
            break
    streak_factor = min(0.3, error_streak * 0.06)

    # Response time factor (slowing = higher load)
    avg_rt = sum(h.get("response_time_ms", 5000) for h in recent) / len(recent)
    rt_factor = min(0.2, (avg_rt - 5000) / 25000)

    extraneous = time_factor + streak_factor + max(0, rt_factor)

    # === GERMANE LOAD (Productive learning) ===
    # Estimated from accuracy and improvement
    correct = sum(1 for h in recent if h.get("is_correct", False))
    accuracy = correct / len(recent)
    germane = accuracy * 0.3  # High accuracy = good germane load

    # === TOTAL LOAD ===
    total_load = min(1.0, intrinsic + extraneous + germane)
    load_percent = int(total_load * 100)

    # Determine level
    if load_percent < 30:
        level = "low"
        rec = "Cognitive resources available. Good time for challenging content."
    elif load_percent < 50:
        level = "moderate"
        rec = "Optimal load range. Continue at current pace."
    elif load_percent < 75:
        level = "high"
        rec = "Approaching capacity. Consider easier content or short break."
    else:
        level = "critical"
        rec = "Working memory overloaded. Take a 10-minute break immediately."

    return CognitiveLoadMetrics(
        load_percent=load_percent,
        load_level=level,
        intrinsic_load=round(intrinsic, 3),
        extraneous_load=round(extraneous, 3),
        germane_load=round(germane, 3),
        recommendation=rec,
        factors={
            "intrinsic": round(intrinsic * 100, 1),
            "time": round(time_factor * 100, 1),
            "error_streak": round(streak_factor * 100, 1),
            "response_time": round(max(0, rt_factor) * 100, 1),
            "germane": round(germane * 100, 1),
        }
    )


# =============================================================================
# REWARD FUNCTION (For HRL Scheduler)
# =============================================================================

def compute_learning_reward(
    diagnosis: CognitiveDiagnosis,
    delta_knowledge: float,
    fluency_score: float,
    fatigue_level: float,
    offloading_detected: bool,
) -> float:
    """
    Compute reward for the HRL scheduler.

    R_t = w1·ΔKnowledge + w2·FluencyScore - w3·FatiguePenalty - w4·OffloadingPenalty

    This reward function is used by the Hierarchical Reinforcement Learning
    scheduler to optimize atom selection.

    Args:
        diagnosis: The cognitive diagnosis
        delta_knowledge: Estimated knowledge gain (0-1)
        fluency_score: Fluency improvement (0-1)
        fatigue_level: Current fatigue (0-1)
        offloading_detected: Whether cognitive offloading was detected

    Returns:
        Reward value (can be negative)
    """
    # Weights from spec
    w1 = 0.4  # Knowledge gain
    w2 = 0.3  # Fluency
    w3 = 0.2  # Fatigue penalty
    w4 = 0.3  # Offloading penalty

    # Base reward
    reward = w1 * delta_knowledge + w2 * fluency_score

    # Penalties
    reward -= w3 * fatigue_level

    if offloading_detected:
        reward -= w4

    # Bonus for flow state
    if diagnosis.cognitive_state == CognitiveState.FLOW:
        reward *= 1.1

    # Penalty for anxiety (material too hard)
    if diagnosis.cognitive_state == CognitiveState.ANXIETY:
        reward *= 0.8

    return round(reward, 4)


# =============================================================================
# LLM PROMPT GENERATION
# =============================================================================

def generate_remediation_prompt(
    atom: dict[str, Any],
    diagnosis: CognitiveDiagnosis,
    learner_context: Optional[str] = None,
) -> Optional[str]:
    """
    Generate a prompt for AI-powered remediation.

    Based on the cognitive diagnosis, generates a prompt for
    Vertex AI / Gemini to provide personalized remediation.

    Args:
        atom: The atom that was answered incorrectly
        diagnosis: The cognitive diagnosis
        learner_context: Optional learner persona context

    Returns:
        Prompt string for AI model, or None if not applicable
    """
    question = atom.get("front", "")
    correct_answer = atom.get("back", "")
    concept_name = atom.get("concept_name", "this concept")

    base_context = f"""
Question: {question}
Correct Answer: {correct_answer}
Concept: {concept_name}
"""

    if learner_context:
        base_context = learner_context + "\n" + base_context

    if diagnosis.fail_mode == FailMode.ENCODING_ERROR:
        return f"""The learner failed to encode this concept properly (hippocampal encoding failure).
{base_context}
Explain this concept using:
1. A vivid analogy or metaphor (for better encoding)
2. A real-world example they can relate to
3. Why it matters (practical application)
4. A mnemonic device if applicable

Keep explanation under 150 words. Use concrete, sensory language for better memory encoding."""

    elif diagnosis.fail_mode == FailMode.DISCRIMINATION_ERROR:
        return f"""The learner is confusing this with similar concepts (pattern separation failure).
{base_context}
Create a clear comparison:
1. What THIS concept is (key defining features)
2. What it is NOT (common confusions)
3. A discriminating mnemonic ("X has Y, while Z has W")
4. A quick decision rule for distinguishing them

Format as a clear comparison table if helpful. Keep under 150 words."""

    elif diagnosis.fail_mode == FailMode.INTEGRATION_ERROR:
        return f"""The learner can recall facts but can't integrate them (P-FIT integration failure).
{base_context}
Provide a worked example that:
1. States the given information
2. Shows EACH reasoning step explicitly
3. Explains WHY each step follows from the previous
4. Highlights the integration points where facts connect

Think out loud. Show the reasoning process, not just the answer. Keep under 200 words."""

    elif diagnosis.fail_mode == FailMode.EXECUTIVE_ERROR:
        return f"""The learner answered too quickly without reading carefully (executive function failure).
{base_context}
Help them slow down:
1. Highlight the KEY detail they likely missed (bold or emphasize it)
2. Create a pre-answer checklist for this type of question
3. Suggest a "stop and think" trigger phrase

Keep response under 100 words. Be direct but supportive."""

    elif diagnosis.fail_mode == FailMode.FATIGUE_ERROR:
        # Don't generate prompt for fatigue - just rest
        return None

    # Default: retrieval failure
    return f"""The learner is experiencing normal forgetting (retrieval failure).
{base_context}
Provide a brief memory boost:
1. Restate the core fact in different words
2. Link it to something they already know
3. Provide a retrieval cue or hint for next time

Keep under 75 words. Focus on making it memorable."""


# =============================================================================
# EMBEDDING-BASED PATTERN SEPARATION (Enhanced PSI Calculation)
# =============================================================================

@dataclass
class LearningAtomEmbed:
    """
    Learning Atom with embedding vector for pattern separation analysis.

    The embedding captures the semantic position in "concept space" -
    atoms close together are prone to hippocampal interference.
    """
    id: str
    content: str
    embedding: list[float]  # Vector representation (e.g., from Gemini/OpenAI)
    modality: str = "symbolic"  # 'symbolic', 'visual', 'mixed'
    confusers: list[str] = field(default_factory=list)  # IDs of confusable atoms
    ps_index: float = 0.5
    pfit_index: float = 0.5

    def to_numpy(self) -> "np.ndarray":
        """Convert embedding to numpy array for vector operations."""
        import numpy as np
        return np.array(self.embedding)


@dataclass
class InteractionEvent:
    """
    A single learner interaction with a Learning Atom.

    Captures the behavioral signature that the cognitive model
    uses to infer what's happening in the learner's brain.
    """
    atom_id: str
    is_correct: bool
    response_latency_ms: int
    selected_lure_id: Optional[str] = None  # ID of the lure they chose (if MCQ)
    fatigue_index: float = 0.0  # 0.0 to 1.0

    # Modality state tracking (for P-FIT analysis)
    time_in_visual_ms: int = 0  # Time spent viewing diagrams/graphs
    time_in_symbolic_ms: int = 0  # Time spent on equations/text

    # Keystroke dynamics (if available)
    time_to_first_keystroke_ms: Optional[int] = None
    total_keystrokes: int = 0
    backspace_count: int = 0  # High backspace = uncertainty


class NeuroCognitiveModel:
    """
    The computational brain of Cortex.

    This class implements the core neuroscientific theories:
    1. Hippocampal Pattern Separation (Norman & O'Reilly, 2003)
    2. P-FIT Integration (Jung & Haier, 2007)
    3. Executive Control (Prefrontal Cortex inhibition)

    It calculates Pattern Separation Indices and diagnoses error types
    based on behavioral signatures, mapping them to brain regions.
    """

    def __init__(
        self,
        pattern_separation_threshold: float = 0.7,
        impulsivity_threshold_ms: int = 1500,
        fatigue_threshold: float = 0.7,
        integration_latency_threshold_ms: int = 5000,
    ):
        """
        Initialize the neuro-cognitive model with configurable thresholds.

        Args:
            pattern_separation_threshold: PSI above this = discrimination risk
            impulsivity_threshold_ms: Responses faster = executive failure
            fatigue_threshold: Fatigue vector above this = depleted resources
            integration_latency_threshold_ms: Slow responses with mixed modality = P-FIT failure
        """
        self.ps_threshold = pattern_separation_threshold
        self.impulsivity_threshold = impulsivity_threshold_ms
        self.fatigue_threshold = fatigue_threshold
        self.integration_threshold = integration_latency_threshold_ms

        logger.info(
            f"NeuroCognitiveModel initialized: "
            f"ps_threshold={pattern_separation_threshold}, "
            f"impulsivity={impulsivity_threshold_ms}ms"
        )

    def calculate_psi(
        self,
        atom_a: LearningAtomEmbed,
        atom_b: LearningAtomEmbed,
    ) -> float:
        """
        Calculate the Pattern Separation Index (PSI) between two atoms.

        PSI measures semantic overlap - the probability that the hippocampus
        will confuse these two memory traces. Uses cosine similarity.

        Higher PSI = Higher overlap = Higher risk of interference

        The Dentate Gyrus performs pattern separation (orthogonalization),
        but when PSI is high, even this mechanism may fail.

        Args:
            atom_a: First learning atom with embedding
            atom_b: Second learning atom with embedding

        Returns:
            PSI score from 0.0 (orthogonal) to 1.0 (identical)
        """
        import numpy as np

        vec_a = atom_a.to_numpy()
        vec_b = atom_b.to_numpy()

        norm_a = np.linalg.norm(vec_a)
        norm_b = np.linalg.norm(vec_b)

        if norm_a == 0 or norm_b == 0:
            logger.warning(f"Zero-norm embedding: {atom_a.id} or {atom_b.id}")
            return 0.0

        similarity = np.dot(vec_a, vec_b) / (norm_a * norm_b)

        # Clamp to valid range (numerical precision can cause >1)
        psi = float(max(0.0, min(1.0, similarity)))

        logger.debug(
            f"PSI({atom_a.id}, {atom_b.id}) = {psi:.3f} "
            f"{'[HIGH INTERFERENCE RISK]' if psi > self.ps_threshold else ''}"
        )

        return psi

    def diagnose_failure(
        self,
        event: InteractionEvent,
        target_atom: LearningAtomEmbed,
        lure_atom: Optional[LearningAtomEmbed] = None,
    ) -> dict[str, Any]:
        """
        Diagnose the cognitive root cause of a failure.

        This is the core diagnostic function that maps behavioral signatures
        to brain regions and cognitive processes.

        Algorithm (priority order):
        1. EXECUTIVE_ERROR: Fast response or high fatigue (PFC failure)
        2. DISCRIMINATION_ERROR: High PSI with lure (DG failure)
        3. INTEGRATION_ERROR: Mixed modality with long latency (P-FIT failure)
        4. ENCODING_ERROR: Default fallback (CA3/CA1 failure)

        Args:
            event: The interaction event with behavioral data
            target_atom: The atom the learner was trying to answer
            lure_atom: The confusable atom they may have selected (if MCQ)

        Returns:
            Diagnosis dict with error_type, region, remediation, reasoning
        """
        if event.is_correct:
            return {
                "status": "SUCCESS",
                "mechanism": "Consolidation",
                "cognitive_state": CognitiveState.FLOW.value,
            }

        # === PRIORITY 1: Executive/Fatigue Error (PFC) ===
        # Fast errors or high fatigue suggest impulsivity or resource depletion
        # The prefrontal cortex failed to inhibit the automatic response
        if event.fatigue_index > self.fatigue_threshold:
            return {
                "error_type": FailMode.EXECUTIVE_ERROR,
                "region": "Prefrontal Cortex (Depleted)",
                "mechanism": "Executive Resource Exhaustion",
                "remediation": RemediationType.REST,
                "reasoning": (
                    f"Fatigue vector {event.fatigue_index:.2f} exceeds threshold "
                    f"{self.fatigue_threshold}. PFC resources depleted."
                ),
            }

        if event.response_latency_ms < self.impulsivity_threshold:
            # Check if this is TTFA-based impulsivity
            ttfa = event.time_to_first_keystroke_ms
            if ttfa and ttfa < 400:
                mechanism = "System 1 Heuristic Bypass"
            else:
                mechanism = "Insufficient Processing Time"

            return {
                "error_type": FailMode.EXECUTIVE_ERROR,
                "region": "Prefrontal Cortex (Inhibition)",
                "mechanism": mechanism,
                "remediation": RemediationType.SLOW_DOWN,
                "reasoning": (
                    f"Response time {event.response_latency_ms}ms < "
                    f"{self.impulsivity_threshold}ms. Inhibitory control failed."
                ),
            }

        # === PRIORITY 2: Discrimination Error (Hippocampus - DG) ===
        # If the user selected a specific lure with high semantic overlap
        if lure_atom:
            psi = self.calculate_psi(target_atom, lure_atom)
            if psi > self.ps_threshold:
                return {
                    "error_type": FailMode.DISCRIMINATION_ERROR,
                    "region": "Hippocampus (Dentate Gyrus)",
                    "mechanism": "Pattern Separation Failure (Orthogonalization)",
                    "remediation": RemediationType.CONTRASTIVE,
                    "psi_score": psi,
                    "confuser_id": lure_atom.id,
                    "reasoning": (
                        f"Failed to separate pattern '{target_atom.id}' from "
                        f"neighbor '{lure_atom.id}' (PSI: {psi:.2f}). "
                        "Dentate Gyrus orthogonalization insufficient."
                    ),
                }

        # === PRIORITY 3: Integration Error (P-FIT) ===
        # Mixed modality tasks with long latency = parietal-frontal disconnect
        if target_atom.modality == 'mixed':
            # Check for visual-symbolic translation failure
            if event.time_in_visual_ms > 0 and event.time_in_symbolic_ms > 0:
                visual_ratio = event.time_in_visual_ms / (
                    event.time_in_visual_ms + event.time_in_symbolic_ms
                )
                # If mostly in visual but failed symbolic output
                if visual_ratio > 0.6 and event.response_latency_ms > self.integration_threshold:
                    return {
                        "error_type": FailMode.INTEGRATION_ERROR,
                        "region": "Parieto-Frontal Network (P-FIT)",
                        "mechanism": "Visual-Symbolic Translation Failure",
                        "remediation": RemediationType.WORKED_EXAMPLE,
                        "visual_ratio": visual_ratio,
                        "reasoning": (
                            f"Spent {visual_ratio:.0%} time in parietal (visual) state "
                            "but failed to produce frontal (symbolic) output. "
                            "P-FIT network integration failure."
                        ),
                    }

            # General P-FIT failure for mixed modality
            if event.response_latency_ms > self.integration_threshold:
                return {
                    "error_type": FailMode.INTEGRATION_ERROR,
                    "region": "Parieto-Frontal Network (P-FIT)",
                    "mechanism": "Cross-Modal Integration Failure",
                    "remediation": RemediationType.SCAFFOLDED,
                    "reasoning": (
                        f"Mixed-modality atom with {event.response_latency_ms}ms latency. "
                        "Parietal-frontal communication breakdown."
                    ),
                }

        # === DEFAULT: Encoding Error (Hippocampus - CA3) ===
        # General failure to retrieve or encode the trace
        return {
            "error_type": FailMode.ENCODING_ERROR,
            "region": "Hippocampus (CA3/CA1)",
            "mechanism": "Trace Consolidation Failure",
            "remediation": RemediationType.ELABORATE,
            "reasoning": (
                "General failure to retrieve or encode the memory trace. "
                "Requires elaborative encoding with spacing."
            ),
        }

    def diagnose_with_full_context(
        self,
        event: InteractionEvent,
        target_atom: LearningAtomEmbed,
        lure_atom: Optional[LearningAtomEmbed] = None,
        session_duration_seconds: int = 0,
        session_error_streak: int = 0,
    ) -> CognitiveDiagnosis:
        """
        Produce a full CognitiveDiagnosis by combining NeuroCognitiveModel
        with the existing diagnostic pipeline.

        This bridges the class-based model with the existing function-based
        diagnosis for backward compatibility.

        Args:
            event: The interaction event
            target_atom: The target atom with embedding
            lure_atom: Optional confusable atom
            session_duration_seconds: Session duration for fatigue detection
            session_error_streak: Consecutive errors for fatigue detection

        Returns:
            Full CognitiveDiagnosis dataclass
        """
        # Get basic diagnosis from the neurocognitive model
        raw_diagnosis = self.diagnose_failure(event, target_atom, lure_atom)

        if raw_diagnosis.get("status") == "SUCCESS":
            # Classify success type
            if event.response_latency_ms < THRESHOLDS["fluency_max_ms"]:
                success_mode = SuccessMode.FLUENCY
            elif target_atom.modality == "mixed":
                success_mode = SuccessMode.INFERENCE
            else:
                success_mode = SuccessMode.RECALL

            return CognitiveDiagnosis(
                fail_mode=None,
                success_mode=success_mode,
                cognitive_state=CognitiveState.FLOW,
                confidence=0.8,
                evidence=["Successful retrieval"],
                remediation_type=RemediationType.CONTINUE,
                ps_index=target_atom.ps_index,
                pfit_index=target_atom.pfit_index,
            )

        # Build full diagnosis from raw
        fail_mode = raw_diagnosis.get("error_type", FailMode.ENCODING_ERROR)

        # Determine cognitive state
        session_minutes = session_duration_seconds / 60
        cognitive_state = _infer_cognitive_state(fail_mode, session_minutes, session_error_streak)

        diagnosis = CognitiveDiagnosis(
            fail_mode=fail_mode,
            success_mode=None,
            cognitive_state=cognitive_state,
            confidence=0.8,
            evidence=[raw_diagnosis.get("reasoning", "")],
            remediation_type=raw_diagnosis.get("remediation", RemediationType.SPACED_REPEAT),
            ps_index=raw_diagnosis.get("psi_score", target_atom.ps_index),
            pfit_index=target_atom.pfit_index,
            explanation=raw_diagnosis.get("reasoning", ""),
        )

        return diagnosis


# =============================================================================
# UTILITY FUNCTIONS FOR EMBEDDING-BASED PSI
# =============================================================================

def compute_psi_matrix(atoms: list[LearningAtomEmbed]) -> dict[tuple[str, str], float]:
    """
    Compute PSI (Pattern Separation Index) for all pairs of atoms.

    Returns a dict mapping (atom_id_1, atom_id_2) -> PSI score.
    Useful for precomputing confusability in a curriculum.

    Args:
        atoms: List of atoms with embeddings

    Returns:
        Dict mapping atom ID pairs to PSI scores
    """
    model = NeuroCognitiveModel()
    psi_matrix = {}

    for i, atom_a in enumerate(atoms):
        for atom_b in atoms[i+1:]:
            psi = model.calculate_psi(atom_a, atom_b)
            psi_matrix[(atom_a.id, atom_b.id)] = psi
            psi_matrix[(atom_b.id, atom_a.id)] = psi  # Symmetric

    return psi_matrix


def find_confusable_neighbors(
    target: LearningAtomEmbed,
    candidates: list[LearningAtomEmbed],
    threshold: float = 0.7,
    max_neighbors: int = 5,
) -> list[tuple[LearningAtomEmbed, float]]:
    """
    Find atoms that are semantically close to the target (confusable).

    These are candidates for:
    1. Adversarial lure generation in MCQs
    2. Contrastive training pairs
    3. Pattern separation exercises

    Args:
        target: The atom to find neighbors for
        candidates: Pool of candidate atoms
        threshold: Minimum PSI to be considered confusable
        max_neighbors: Maximum neighbors to return

    Returns:
        List of (atom, psi_score) tuples sorted by PSI descending
    """
    model = NeuroCognitiveModel()
    neighbors = []

    for candidate in candidates:
        if candidate.id == target.id:
            continue

        psi = model.calculate_psi(target, candidate)
        if psi >= threshold:
            neighbors.append((candidate, psi))

    # Sort by PSI descending
    neighbors.sort(key=lambda x: x[1], reverse=True)

    return neighbors[:max_neighbors]


def generate_adversarial_lures(
    target: LearningAtomEmbed,
    candidates: list[LearningAtomEmbed],
    num_lures: int = 3,
) -> list[LearningAtomEmbed]:
    """
    Generate adversarial lures for MCQ distractor generation.

    Adversarial lures are atoms with high PSI (semantic similarity)
    that the learner is likely to confuse with the target. These
    are more effective than random distractors for training
    hippocampal pattern separation.

    Args:
        target: The correct answer atom
        candidates: Pool of candidate lures
        num_lures: Number of lures to generate

    Returns:
        List of adversarial lure atoms
    """
    neighbors = find_confusable_neighbors(
        target,
        candidates,
        threshold=0.6,  # Lower threshold for more options
        max_neighbors=num_lures * 2,  # Get extra for diversity
    )

    # Take top N by PSI
    lures = [atom for atom, psi in neighbors[:num_lures]]

    logger.info(
        f"Generated {len(lures)} adversarial lures for '{target.id}' "
        f"with PSI scores: {[round(psi, 2) for _, psi in neighbors[:num_lures]]}"
    )

    return lures
