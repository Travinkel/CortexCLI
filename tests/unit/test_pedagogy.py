"""
Pedagogical Logic Validator.

Validates cognitive-science-aligned interventions without needing a DB:
1) CLS (hippocampal discrimination)
2) P-FIT efficiency
3) Intra-individual variability (attention)
4) Dual process (impulsivity vs insight)
5) Metacognitive honesty
6) Flow state acceleration
"""

from __future__ import annotations

import statistics
from dataclasses import dataclass
from enum import Enum


class Remediation(Enum):
    REVIEW = "standard_review"
    CONTRASTIVE = "contrastive_lure_training"
    WORKED_EXAMPLE = "worked_example"
    FOCUS_RESET = "focus_reset"
    SELF_EXPLANATION = "self_explanation"
    ACCELERATE = "accelerate"
    SHOW_ANSWER_NO_PENALTY = "show_no_penalty"


@dataclass
class LearningState:
    stability: float
    review_count: int
    psi_index: float = 0.0
    visual_load: float = 0.0
    symbolic_load: float = 0.0
    recent_response_times: list[int] | None = None

    def get_variance(self) -> float:
        """Standard deviation of recent response times (attention stability)."""
        if not self.recent_response_times or len(self.recent_response_times) < 2:
            return 0.0
        return statistics.stdev(self.recent_response_times)


def diagnose_pedagogical_intervention(
    is_correct: bool,
    state: LearningState,
    response_time_ms: int,
) -> Remediation:
    """Decide intervention based on cognitive signals."""
    # Dual process: implausibly fast correct -> likely guessing
    if is_correct and response_time_ms < 500 and state.stability < 100:
        return Remediation.SELF_EXPLANATION

    # Metacognition: fast honest failure on known item -> show answer without penalty
    if not is_correct and response_time_ms < 2000 and state.stability > 5:
        return Remediation.SHOW_ANSWER_NO_PENALTY

    # Attention variance: high variance means mind-wandering
    if state.get_variance() > 4000:
        return Remediation.FOCUS_RESET

    # Flow: low variance + experience -> accelerate
    if is_correct and state.get_variance() < 500 and state.review_count > 5:
        return Remediation.ACCELERATE

    # Hippocampal interference: high PSI + failure on known item
    if not is_correct and state.stability > 5.0 and state.psi_index > 0.85:
        return Remediation.CONTRASTIVE

    # P-FIT inefficiency: heavy load or very long latency despite correctness
    total_load = state.visual_load + state.symbolic_load
    if total_load > 1.5 or (is_correct and response_time_ms > 15000):
        return Remediation.WORKED_EXAMPLE

    return Remediation.REVIEW


class TestCognitiveScienceCompliance:
    def test_cls_discrimination_triggers_contrastive(self):
        state = LearningState(stability=20.0, review_count=5, psi_index=0.90)
        intervention = diagnose_pedagogical_intervention(False, state, 5000)
        assert intervention == Remediation.CONTRASTIVE

    def test_pfit_efficiency_triggers_worked_example(self):
        state = LearningState(stability=10.0, review_count=3)
        intervention = diagnose_pedagogical_intervention(True, state, 20000)
        assert intervention == Remediation.WORKED_EXAMPLE

    def test_dual_process_blocks_impulsive_guessing(self):
        state = LearningState(stability=5.0, review_count=2)
        intervention = diagnose_pedagogical_intervention(True, state, 300)
        assert intervention == Remediation.SELF_EXPLANATION

    def test_attention_variability_triggers_focus_reset(self):
        times = [2000, 12000, 3000, 9000, 2000]
        state = LearningState(stability=10.0, review_count=10, recent_response_times=times)
        intervention = diagnose_pedagogical_intervention(True, state, 3000)
        assert intervention == Remediation.FOCUS_RESET

    def test_metacognition_fast_failure_no_penalty(self):
        state = LearningState(stability=15.0, review_count=5)
        intervention = diagnose_pedagogical_intervention(False, state, 1500)
        assert intervention == Remediation.SHOW_ANSWER_NO_PENALTY

    def test_flow_state_accelerates(self):
        times = [3000, 3200, 2900, 3100, 3000]
        state = LearningState(stability=10.0, review_count=10, recent_response_times=times)
        intervention = diagnose_pedagogical_intervention(True, state, 3000)
        assert intervention == Remediation.ACCELERATE


# =============================================================================
# Deep Encoding / Transfer Validators
# =============================================================================

class ResponseType(Enum):
    SHOW_ANSWER = "show_answer"
    SHOW_HINT = "show_hint"


class MasteryLevel(Enum):
    PRACTICING = "practicing"
    MASTERED = "mastered"


@dataclass
class LearningAtom:
    knowledge_type: str
    has_hints: bool = False
    content: str | None = None
    media_tags: list[str] | None = None


def validate_pedagogical_schedule(schedule: list[dict]) -> bool:
    """Reject blocked practice when adjacent topics match (enforce interleaving)."""
    for i in range(1, len(schedule)):
        if schedule[i]["topic"] == schedule[i - 1]["topic"]:
            return False
    return True


def determine_failure_response(atom: LearningAtom, attempt_count: int) -> ResponseType:
    """Force hint-first for complex items on first failure."""
    if atom.knowledge_type in {"procedural", "conceptual"} and attempt_count == 1 and atom.has_hints:
        return ResponseType.SHOW_HINT
    return ResponseType.SHOW_ANSWER


def validate_atom_quality(atom: LearningAtom) -> bool:
    """Reject spatial/process atoms that lack visual media tags."""
    spatial_types = {"topology", "process", "diagram", "architecture"}
    if atom.knowledge_type in spatial_types:
        if not atom.media_tags:
            return False
    return True


def validate_pedagogical_sequence(sequence: list[dict]) -> bool:
    """Ensure new topics start with prediction/problem (not immediate definition)."""
    if not sequence:
        return True
    first_atom = sequence[0]
    if first_atom.get("is_new") and first_atom.get("type") == "definition":
        return False
    return True


def calculate_next_interval(history: list[dict]) -> int:
    """
    Return days until next review; suspend overlearned items.
    """
    perfect_run = 0
    for review in reversed(history):
        if (
            review.get("result") == "correct"
            and review.get("latency", 0) < 2000
            and review.get("confidence") == "high"
        ):
            perfect_run += 1
        else:
            break
    if perfect_run >= 3:
        return 365  # effectively suspend
    return 1


def calculate_concept_mastery(history: list[dict]) -> MasteryLevel:
    """
    Require variation for mastery: must include at least one non-factual success.
    """
    if not history:
        return MasteryLevel.PRACTICING
    if any(item.get("result") != "correct" for item in history):
        return MasteryLevel.PRACTICING
    seen_types = {item.get("type") for item in history}
    if seen_types - {"factual"}:
        return MasteryLevel.MASTERED
    return MasteryLevel.PRACTICING


class TestDeepEncodingStrategies:
    """
    Validates deep processing strategies:
    1) Interleaving similar concepts
    2) Generative feedback
    3) Context variation for transfer
    """

    def test_enforces_strategic_interleaving(self):
        schedule = [
            {"topic": "OSPF", "type": "config"},
            {"topic": "OSPF", "type": "config"},
            {"topic": "EIGRP", "type": "config"},
            {"topic": "EIGRP", "type": "config"},
        ]
        is_valid = validate_pedagogical_schedule(schedule)
        assert is_valid is False, "Blocked practice should be rejected; interleave similar topics."

    def test_enforces_generative_feedback_loop(self):
        atom = LearningAtom(knowledge_type="procedural", has_hints=True)
        outcome = determine_failure_response(atom, attempt_count=1)
        assert outcome == ResponseType.SHOW_HINT, "Complex first failure should show a hint, not the answer."

    def test_enforces_context_variation_for_mastery(self):
        history = [
            {"type": "factual", "result": "correct"},
            {"type": "factual", "result": "correct"},
            {"type": "factual", "result": "correct"},
        ]
        mastery_status = calculate_concept_mastery(history)
        assert mastery_status != MasteryLevel.MASTERED, "Mastery needs varied contexts, not only definitions."


class TestAdvancedCognitiveStrategies:
    """
    Validates advanced learning strategies:
    1) Dual coding (visual + verbal)
    2) Schema priming (pre-testing)
    3) Desirable difficulty (avoid junk volume)
    """

    def test_enforces_dual_coding_for_complex_topics(self):
        atom = LearningAtom(
            knowledge_type="topology",
            content="OSPF Area 0 is the backbone...",
            media_tags=[],
        )
        is_valid = validate_atom_quality(atom)
        assert is_valid is False, "Spatial concepts require visuals (dual coding)."

    def test_enforces_schema_priming_sequence(self):
        sequence = [
            {"type": "definition", "topic": "IPv6", "is_new": True},
            {"type": "prediction", "topic": "IPv6", "is_new": True},
        ]
        is_valid = validate_pedagogical_sequence(sequence)
        assert is_valid is False, "New topics should start with prediction/problem (pre-testing)."

    def test_prevents_junk_volume_overlearning(self):
        history = [
            {"result": "correct", "latency": 1200, "confidence": "high"},
            {"result": "correct", "latency": 1100, "confidence": "high"},
            {"result": "correct", "latency": 1000, "confidence": "high"},
        ]
        next_interval = calculate_next_interval(history)
        assert next_interval > 300, f"Overlearned items should be suspended; got interval {next_interval}"
