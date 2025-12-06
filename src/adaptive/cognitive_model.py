"""
Cognitive Diagnosis Engine.

Implements PhD-level cognitive science for error classification.
Instead of treating all errors as "forgot," this module diagnoses
the neurological/cognitive cause of errors.

Based on research from:
- Cognitive Load Theory (Sweller, 1988)
- Dual-Process Theory (Kahneman, 2011)
- Memory Consolidation Research (McGaugh, 2000)

Error Types:
1. ENCODING_FAILURE (Hippocampus): Never consolidated the memory
2. RETRIEVAL_FAILURE (Normal): Forgot over time (FSRS handles this)
3. INTERFERENCE (Cortical): Confused similar concepts
4. IMPULSIVITY (PFC): Knew answer but didn't read carefully
5. FATIGUE (Global): Cognitive resources depleted

Each diagnosis triggers a different remediation strategy.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Optional
from uuid import UUID

from loguru import logger


class CognitiveState(str, Enum):
    """
    Cognitive diagnosis for why an error occurred.

    Each state maps to a different remediation strategy:
    - ENCODING_FAILURE -> Elaboration (explain like I'm 5)
    - RETRIEVAL_FAILURE -> Spaced repetition (FSRS handles)
    - INTERFERENCE -> Contrastive analysis (compare/contrast)
    - IMPULSIVITY -> Inhibition control (forced delay)
    - FATIGUE -> Break or session end
    """
    ENCODING_FAILURE = "encoding_failure"      # Hippocampal - never learned
    RETRIEVAL_FAILURE = "retrieval_failure"    # Normal forgetting
    INTERFERENCE = "interference"               # Confused similar concepts
    IMPULSIVITY = "impulsivity"                # Fast + wrong (PFC failure)
    FATIGUE = "fatigue"                        # Cognitive exhaustion
    UNKNOWN = "unknown"                        # Insufficient data


class RemediationStrategy(str, Enum):
    """Remediation strategy based on cognitive diagnosis."""
    ELABORATION = "elaboration"           # Explain concept differently
    SPACED_REPETITION = "spaced_repetition"  # Standard FSRS
    CONTRASTIVE_REVIEW = "contrastive_review"  # Compare similar concepts
    INHIBITION_DELAY = "inhibition_delay"    # Force pause before answering
    BREAK_SUGGESTED = "break_suggested"      # Take a break
    READ_SOURCE = "read_source"              # Go back to source material
    MICRO_TUTOR = "micro_tutor"              # Socratic dialogue with AI


@dataclass
class CognitiveDiagnosis:
    """
    Complete cognitive diagnosis for an error.

    Attributes:
        state: The diagnosed cognitive state
        confidence: How confident we are in the diagnosis (0-1)
        evidence: List of evidence supporting the diagnosis
        remediation: Recommended remediation strategy
        remediation_params: Parameters for the remediation
        explanation: Human-readable explanation for the learner
    """
    state: CognitiveState
    confidence: float = 0.0
    evidence: list[str] = field(default_factory=list)
    remediation: RemediationStrategy = RemediationStrategy.SPACED_REPETITION
    remediation_params: dict = field(default_factory=dict)
    explanation: str = ""

    # Additional context
    concept_id: Optional[UUID] = None
    related_concept_id: Optional[UUID] = None  # For interference
    source_reference: Optional[str] = None     # Section to re-read

    def to_dict(self) -> dict:
        return {
            "state": self.state.value,
            "confidence": self.confidence,
            "evidence": self.evidence,
            "remediation": self.remediation.value,
            "remediation_params": self.remediation_params,
            "explanation": self.explanation,
        }


@dataclass
class InteractionRecord:
    """Record of a single learning interaction for analysis."""
    atom_id: str
    concept_id: Optional[str]
    concept_name: Optional[str]
    is_correct: bool
    response_time_ms: int
    timestamp: datetime
    atom_type: str = "flashcard"
    user_answer: str = ""
    correct_answer: str = ""

    # FSRS metrics at time of interaction
    stability: float = 0.0
    difficulty: float = 0.3
    lapses: int = 0
    review_count: int = 0


@dataclass
class StrugglePattern:
    """Detected pattern of struggle on a concept."""
    concept_id: str
    concept_name: str
    failure_count: int
    total_attempts: int
    failure_rate: float
    avg_response_time_ms: float
    recommendation: str
    source_reference: Optional[str] = None
    priority: str = "medium"  # high, medium, low

    @property
    def is_critical(self) -> bool:
        """Critical if failure rate > 60% or 5+ consecutive failures."""
        return self.failure_rate > 0.6 or self.failure_count >= 5


# Thresholds for cognitive diagnosis (evidence-based)
THRESHOLDS = {
    # Response time thresholds (milliseconds)
    "impulsivity_max_ms": 1500,      # < 1.5s = too fast, likely impulsive
    "fatigue_min_ms": 10000,         # > 10s = likely fatigued
    "normal_min_ms": 2000,           # 2-10s = normal thinking time
    "normal_max_ms": 10000,

    # Session thresholds
    "fatigue_session_minutes": 45,   # After 45 min, fatigue likely
    "fatigue_error_streak": 5,       # 5 errors in a row = fatigue

    # Encoding failure thresholds
    "encoding_max_hours": 24,        # Failed within 24h of learning = encoding
    "encoding_min_reviews": 3,       # Need 3+ reviews before it's retrieval

    # Struggle pattern thresholds
    "struggle_window_size": 5,       # Look at last 5 interactions
    "struggle_failure_rate": 0.4,    # 40% failure rate = struggling
    "critical_failure_rate": 0.6,    # 60% = critical, stop and remediate
}


def diagnose_error(
    atom: dict,
    response_time_ms: int,
    history: list[dict],
    session_duration_seconds: int = 0,
    session_error_streak: int = 0,
) -> CognitiveDiagnosis:
    """
    Diagnose the cognitive cause of an error.

    This is the core diagnostic function. It analyzes:
    1. Response time patterns (impulsivity vs fatigue)
    2. Learning history (encoding vs retrieval failure)
    3. Concept confusion patterns (interference)
    4. Session state (fatigue from duration)

    Args:
        atom: The atom that was answered incorrectly
        response_time_ms: Time taken to answer (milliseconds)
        history: List of recent interactions (last 10-20)
        session_duration_seconds: How long the session has been running
        session_error_streak: Consecutive errors in current session

    Returns:
        CognitiveDiagnosis with state, confidence, and remediation
    """
    evidence = []
    candidates = []  # (state, confidence, evidence)

    # === Check 1: IMPULSIVITY (PFC failure) ===
    # Fast response + wrong = didn't read carefully
    if response_time_ms < THRESHOLDS["impulsivity_max_ms"]:
        confidence = 1.0 - (response_time_ms / THRESHOLDS["impulsivity_max_ms"])
        evidence_item = f"Response time {response_time_ms}ms < {THRESHOLDS['impulsivity_max_ms']}ms threshold"
        candidates.append((
            CognitiveState.IMPULSIVITY,
            confidence * 0.8,  # Cap at 0.8 - could still be genuine fast recall
            [evidence_item]
        ))

    # === Check 2: FATIGUE (Global depletion) ===
    fatigue_signals = 0
    fatigue_evidence = []

    # Slow response time
    if response_time_ms > THRESHOLDS["fatigue_min_ms"]:
        fatigue_signals += 1
        fatigue_evidence.append(f"Slow response: {response_time_ms}ms")

    # Long session duration
    session_minutes = session_duration_seconds / 60
    if session_minutes > THRESHOLDS["fatigue_session_minutes"]:
        fatigue_signals += 1
        fatigue_evidence.append(f"Session duration: {session_minutes:.0f} minutes")

    # Error streak
    if session_error_streak >= THRESHOLDS["fatigue_error_streak"]:
        fatigue_signals += 2  # Double weight for error streak
        fatigue_evidence.append(f"Error streak: {session_error_streak} consecutive")

    if fatigue_signals >= 2:
        candidates.append((
            CognitiveState.FATIGUE,
            min(0.9, fatigue_signals * 0.3),
            fatigue_evidence
        ))

    # === Check 3: ENCODING FAILURE (Hippocampus) ===
    # Check if this atom was recently learned and never consolidated
    review_count = atom.get("review_count", 0) or atom.get("anki_review_count", 0) or 0
    stability = atom.get("stability", 0) or atom.get("anki_stability", 0) or 0

    if review_count < THRESHOLDS["encoding_min_reviews"] and stability < 7:
        encoding_confidence = 0.7 - (review_count * 0.2)
        encoding_evidence = [
            f"Low review count: {review_count}",
            f"Low stability: {stability:.1f} days"
        ]
        candidates.append((
            CognitiveState.ENCODING_FAILURE,
            max(0.3, encoding_confidence),
            encoding_evidence
        ))

    # === Check 4: INTERFERENCE (Cortical confusion) ===
    # Check history for confusion with similar concepts
    concept_id = atom.get("concept_id")
    if concept_id and history:
        interference_evidence = _detect_interference(atom, history)
        if interference_evidence:
            candidates.append((
                CognitiveState.INTERFERENCE,
                0.7,
                interference_evidence
            ))

    # === Select best diagnosis ===
    if not candidates:
        # Default to retrieval failure if no other signals
        return CognitiveDiagnosis(
            state=CognitiveState.RETRIEVAL_FAILURE,
            confidence=0.5,
            evidence=["No specific cognitive pattern detected"],
            remediation=RemediationStrategy.SPACED_REPETITION,
            explanation="Standard memory decay. Spaced repetition will help.",
        )

    # Sort by confidence and select best
    candidates.sort(key=lambda x: x[1], reverse=True)
    best_state, best_confidence, best_evidence = candidates[0]

    # Build diagnosis with appropriate remediation
    diagnosis = CognitiveDiagnosis(
        state=best_state,
        confidence=best_confidence,
        evidence=best_evidence,
        concept_id=UUID(concept_id) if concept_id else None,
    )

    # Set remediation based on diagnosis
    _set_remediation(diagnosis, atom)

    logger.debug(
        f"Cognitive diagnosis: {diagnosis.state.value} "
        f"(confidence={diagnosis.confidence:.2f}) - {diagnosis.evidence}"
    )

    return diagnosis


def _detect_interference(atom: dict, history: list[dict]) -> list[str]:
    """
    Detect if error was caused by interference from similar concepts.

    Looks for patterns like:
    - Correct on Concept A, then wrong on similar Concept B
    - User answer matches content from a different concept
    """
    evidence = []
    concept_id = atom.get("concept_id")
    concept_name = atom.get("concept_name", "")

    if not concept_id:
        return []

    # Look for recent interactions with potentially confusing concepts
    # This is a heuristic - ideally we'd have semantic similarity data
    recent_concepts = {}
    for interaction in history[-10:]:
        cid = interaction.get("concept_id")
        cname = interaction.get("concept_name", "")
        if cid and cid != concept_id:
            recent_concepts[cid] = {
                "name": cname,
                "correct": interaction.get("is_correct", True),
            }

    # Check for same-module concepts (likely similar)
    atom_module = atom.get("module_number")
    if atom_module:
        same_module_errors = [
            c for c in history[-5:]
            if c.get("module_number") == atom_module
            and not c.get("is_correct", True)
            and c.get("concept_id") != concept_id
        ]
        if same_module_errors:
            evidence.append(
                f"Multiple errors in Module {atom_module} on different concepts"
            )

    # Check for concept name similarity (simple heuristic)
    # Could be enhanced with embedding similarity
    for cid, cdata in recent_concepts.items():
        if _concepts_similar(concept_name, cdata["name"]):
            if not cdata["correct"]:
                evidence.append(
                    f"Possible confusion between '{concept_name}' and '{cdata['name']}'"
                )

    return evidence


def _concepts_similar(name1: str, name2: str) -> bool:
    """
    Check if two concept names are similar enough to cause confusion.

    Simple heuristic - could be enhanced with embeddings.
    """
    if not name1 or not name2:
        return False

    # Normalize
    n1 = name1.lower().strip()
    n2 = name2.lower().strip()

    # Same prefix
    if len(n1) > 5 and len(n2) > 5:
        if n1[:5] == n2[:5]:
            return True

    # Shared significant words
    words1 = set(n1.split()) - {"the", "a", "an", "of", "in", "to", "and"}
    words2 = set(n2.split()) - {"the", "a", "an", "of", "in", "to", "and"}

    if len(words1 & words2) >= 2:
        return True

    return False


def _set_remediation(diagnosis: CognitiveDiagnosis, atom: dict) -> None:
    """Set appropriate remediation strategy based on diagnosis."""

    if diagnosis.state == CognitiveState.IMPULSIVITY:
        diagnosis.remediation = RemediationStrategy.INHIBITION_DELAY
        diagnosis.remediation_params = {"delay_ms": 3000}
        diagnosis.explanation = (
            "You answered too quickly. Take a moment to read the question "
            "carefully before responding."
        )

    elif diagnosis.state == CognitiveState.FATIGUE:
        diagnosis.remediation = RemediationStrategy.BREAK_SUGGESTED
        diagnosis.remediation_params = {"break_minutes": 10}
        diagnosis.explanation = (
            "Cognitive fatigue detected. A 10-minute break will help "
            "consolidate what you've learned and restore focus."
        )

    elif diagnosis.state == CognitiveState.ENCODING_FAILURE:
        diagnosis.remediation = RemediationStrategy.ELABORATION
        diagnosis.source_reference = atom.get("section_id") or atom.get("ccna_section_id")
        diagnosis.explanation = (
            "This concept wasn't fully encoded. Try explaining it in your "
            "own words or re-read the source material."
        )
        diagnosis.remediation_params = {
            "source_section": diagnosis.source_reference,
            "action": "read_source",
        }

    elif diagnosis.state == CognitiveState.INTERFERENCE:
        diagnosis.remediation = RemediationStrategy.CONTRASTIVE_REVIEW
        diagnosis.explanation = (
            "You may be confusing this with a similar concept. "
            "Let's compare them side-by-side."
        )
        diagnosis.remediation_params = {
            "action": "contrastive_review",
            "concept_id": str(diagnosis.concept_id) if diagnosis.concept_id else None,
        }

    else:  # RETRIEVAL_FAILURE or UNKNOWN
        diagnosis.remediation = RemediationStrategy.SPACED_REPETITION
        diagnosis.explanation = (
            "Normal memory decay. Continued spaced repetition will "
            "strengthen this memory trace."
        )


def detect_struggle_pattern(
    session_history: list[dict],
    window_size: int = 5,
) -> Optional[StrugglePattern]:
    """
    Detect if the learner is struggling with a specific concept.

    Analyzes the last N interactions to find:
    - High failure rate on a specific concept
    - Repeated errors suggesting conceptual misunderstanding

    This triggers the metacognitive intervention:
    "Stop quizzing. Go read Section X.Y.Z."

    Args:
        session_history: List of recent interactions
        window_size: Number of recent interactions to analyze

    Returns:
        StrugglePattern if struggling detected, None otherwise
    """
    if len(session_history) < window_size:
        return None

    # Get recent interactions
    recent = session_history[-window_size:]

    # Group by concept
    concept_stats = {}
    for interaction in recent:
        cid = interaction.get("concept_id")
        if not cid:
            continue

        if cid not in concept_stats:
            concept_stats[cid] = {
                "name": interaction.get("concept_name", "Unknown"),
                "section": interaction.get("section_id") or interaction.get("ccna_section_id"),
                "failures": 0,
                "total": 0,
                "response_times": [],
            }

        concept_stats[cid]["total"] += 1
        if not interaction.get("is_correct", True):
            concept_stats[cid]["failures"] += 1
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

            # Determine recommendation
            if failure_rate >= THRESHOLDS["critical_failure_rate"]:
                recommendation = (
                    f"CRITICAL: Stop flashcards. Re-read Section {stats['section']}. "
                    f"Your error pattern suggests a conceptual gap, not a memory failure."
                )
                priority = "high"
            else:
                recommendation = (
                    f"Consider reviewing Section {stats['section']} to reinforce "
                    f"foundational understanding before continuing."
                )
                priority = "medium"

            return StrugglePattern(
                concept_id=cid,
                concept_name=stats["name"],
                failure_count=stats["failures"],
                total_attempts=stats["total"],
                failure_rate=failure_rate,
                avg_response_time_ms=avg_rt,
                recommendation=recommendation,
                source_reference=stats["section"],
                priority=priority,
            )

    return None


def compute_cognitive_load(
    session_history: list[dict],
    session_duration_seconds: int,
) -> dict:
    """
    Compute current cognitive load based on session metrics.

    Returns a dict with:
    - load_percent: 0-100 cognitive load estimate
    - load_level: "low", "moderate", "high", "critical"
    - recommendation: What to do about it

    Based on:
    - Average response time (increasing = higher load)
    - Error rate (increasing = higher load)
    - Session duration (longer = higher load)
    - Error streaks (indicates overload)
    """
    if not session_history:
        return {
            "load_percent": 0,
            "load_level": "low",
            "recommendation": "Ready to learn!",
        }

    # Factors
    recent = session_history[-10:] if len(session_history) >= 10 else session_history

    # 1. Response time factor (normalized to 0-25)
    avg_rt = sum(h.get("response_time_ms", 3000) for h in recent) / len(recent)
    rt_factor = min(25, (avg_rt / 400))  # 10s -> 25 points

    # 2. Error rate factor (normalized to 0-25)
    errors = sum(1 for h in recent if not h.get("is_correct", True))
    error_rate = errors / len(recent)
    error_factor = error_rate * 25

    # 3. Duration factor (normalized to 0-25)
    session_minutes = session_duration_seconds / 60
    duration_factor = min(25, session_minutes / 2)  # 50 min -> 25 points

    # 4. Error streak factor (normalized to 0-25)
    streak = 0
    for h in reversed(recent):
        if not h.get("is_correct", True):
            streak += 1
        else:
            break
    streak_factor = min(25, streak * 5)  # 5 errors -> 25 points

    # Combine factors
    load_percent = min(100, rt_factor + error_factor + duration_factor + streak_factor)

    # Determine level
    if load_percent < 30:
        level = "low"
        recommendation = "Cognitive resources available. Good time for challenging content."
    elif load_percent < 50:
        level = "moderate"
        recommendation = "Normal load. Continue at current pace."
    elif load_percent < 75:
        level = "high"
        recommendation = "Consider easier content or a short break."
    else:
        level = "critical"
        recommendation = "Take a 10-minute break. Cognitive resources depleted."

    return {
        "load_percent": round(load_percent),
        "load_level": level,
        "recommendation": recommendation,
        "factors": {
            "response_time": round(rt_factor, 1),
            "error_rate": round(error_factor, 1),
            "duration": round(duration_factor, 1),
            "error_streak": round(streak_factor, 1),
        }
    }


def get_remediation_prompt(
    atom: dict,
    diagnosis: CognitiveDiagnosis,
) -> Optional[str]:
    """
    Generate a prompt for AI-powered remediation.

    Based on the cognitive diagnosis, generates a prompt for
    Vertex AI / Gemini to provide personalized remediation.

    Args:
        atom: The atom that was answered incorrectly
        diagnosis: The cognitive diagnosis

    Returns:
        Prompt string for AI model, or None if not applicable
    """
    question = atom.get("front", "")
    correct_answer = atom.get("back", "")
    concept_name = atom.get("concept_name", "this concept")

    if diagnosis.state == CognitiveState.ENCODING_FAILURE:
        return f"""The learner failed to encode this concept properly.

Question: {question}
Correct Answer: {correct_answer}
Concept: {concept_name}

Explain this concept using:
1. A simple analogy or metaphor
2. A real-world example
3. Why it matters (practical application)

Keep explanation under 100 words. Use simple language."""

    elif diagnosis.state == CognitiveState.INTERFERENCE:
        return f"""The learner is confusing similar concepts.

Question: {question}
Correct Answer: {correct_answer}
Concept: {concept_name}

Create a brief comparison table showing:
1. How this concept differs from commonly confused alternatives
2. Key distinguishing features
3. When to use each

Keep response under 150 words."""

    elif diagnosis.state == CognitiveState.IMPULSIVITY:
        return f"""The learner answered too quickly without reading carefully.

Question: {question}
Correct Answer: {correct_answer}

Reframe this question to:
1. Highlight the key detail they likely missed
2. Provide a mnemonic or trigger phrase to remember
3. Suggest what to look for next time

Keep response under 75 words."""

    return None


# === Velocity Tracking ===

@dataclass
class VelocityMetrics:
    """Track learning velocity (rate of mastery acquisition)."""
    atoms_per_hour: float = 0.0
    mastery_gained_per_hour: float = 0.0
    current_trend: str = "stable"  # improving, stable, declining
    estimated_time_to_mastery: Optional[float] = None  # hours

    def to_dict(self) -> dict:
        return {
            "atoms_per_hour": round(self.atoms_per_hour, 1),
            "mastery_gained_per_hour": round(self.mastery_gained_per_hour, 3),
            "current_trend": self.current_trend,
            "estimated_time_to_mastery_hours": (
                round(self.estimated_time_to_mastery, 1)
                if self.estimated_time_to_mastery else None
            ),
        }


def compute_velocity(
    session_history: list[dict],
    session_duration_seconds: int,
    target_mastery: float = 0.85,
    current_mastery: float = 0.0,
) -> VelocityMetrics:
    """
    Compute learning velocity metrics.

    Velocity tracking helps identify:
    - When to stop (diminishing returns)
    - Estimated time to goal
    - Whether current strategy is working
    """
    if not session_history or session_duration_seconds < 60:
        return VelocityMetrics()

    hours = session_duration_seconds / 3600
    atoms_completed = len(session_history)

    # Atoms per hour
    atoms_per_hour = atoms_completed / hours if hours > 0 else 0

    # Estimate mastery gained (simplified)
    correct = sum(1 for h in session_history if h.get("is_correct", False))
    accuracy = correct / atoms_completed if atoms_completed > 0 else 0

    # Rough estimate: 0.01 mastery per correct answer
    mastery_gained = correct * 0.01
    mastery_per_hour = mastery_gained / hours if hours > 0 else 0

    # Trend (compare first half to second half)
    if len(session_history) >= 6:
        mid = len(session_history) // 2
        first_half = session_history[:mid]
        second_half = session_history[mid:]

        first_accuracy = sum(1 for h in first_half if h.get("is_correct", False)) / len(first_half)
        second_accuracy = sum(1 for h in second_half if h.get("is_correct", False)) / len(second_half)

        if second_accuracy > first_accuracy + 0.1:
            trend = "improving"
        elif second_accuracy < first_accuracy - 0.1:
            trend = "declining"
        else:
            trend = "stable"
    else:
        trend = "stable"

    # Time to mastery estimate
    mastery_gap = target_mastery - current_mastery
    if mastery_per_hour > 0 and mastery_gap > 0:
        time_to_mastery = mastery_gap / mastery_per_hour
    else:
        time_to_mastery = None

    return VelocityMetrics(
        atoms_per_hour=atoms_per_hour,
        mastery_gained_per_hour=mastery_per_hour,
        current_trend=trend,
        estimated_time_to_mastery=time_to_mastery,
    )
