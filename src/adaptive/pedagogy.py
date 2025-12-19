from __future__ import annotations

import statistics
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class Remediation(Enum):
    REVIEW = "standard_review"
    CONTRASTIVE = "contrastive_lure_training"
    WORKED_EXAMPLE = "worked_example"
    FOCUS_RESET = "focus_reset"
    SELF_EXPLANATION = "self_explanation"
    ACCELERATE = "accelerate"
    SHOW_ANSWER_NO_PENALTY = "show_no_penalty"
    SHOW_HINT = "show_hint"


@dataclass
class LearningState:
    stability: float
    review_count: int
    psi_index: float = 0.0
    visual_load: float = 0.0
    symbolic_load: float = 0.0
    recent_response_times: list[int] = field(default_factory=list)

    def variance(self) -> float:
        if len(self.recent_response_times) < 2:
            return 0.0
        return statistics.stdev(self.recent_response_times)


@dataclass
class InterventionResponse:
    remediation: Remediation
    show_hint: bool = False
    suspend: bool = False
    next_interval_days: int | None = None
    needs_priming: bool = False
    lure_atom: Any | None = None


class PedagogicalEngine:
    """Adaptive pedagogical engine implementing cognitive guardrails."""

    def __init__(self, *, psi_threshold: float = 0.85) -> None:
        self.psi_threshold = psi_threshold

    def evaluate(
        self,
        *,
        event: Any,
        state: LearningState,
        history: list[dict] | None = None,
        is_new_topic: bool = False,
        card_type: str | None = None,
        hints_available: bool = False,
    ) -> InterventionResponse:
        remediation = Remediation.REVIEW
        show_hint = False
        suspend = False
        next_interval: int | None = None
        needs_priming = False

        # Priming rule: new topic should start with a prediction/problem, not a definition
        if is_new_topic and card_type == "definition":
            needs_priming = True

        # Junk filter: three fast, high-confidence corrects -> suspend/push out
        perfect_run = 0
        for review in reversed(history or []):
            if (
                review.get("result") == "correct"
                and review.get("latency", 0) < 2000
                and str(review.get("confidence", "")).lower() in {"high", "5", "4"}
            ):
                perfect_run += 1
            else:
                break
        if perfect_run >= 3:
            remediation = Remediation.ACCELERATE
            suspend = True
            next_interval = 365
            return InterventionResponse(
                remediation=remediation,
                show_hint=show_hint,
                suspend=suspend,
                next_interval_days=next_interval,
                needs_priming=needs_priming,
            )

        # Dual process: implausibly fast correct answers -> self explanation
        if getattr(event, "is_correct", False) and getattr(event, "response_time_ms", 0) < 500:
            remediation = Remediation.SELF_EXPLANATION
            return InterventionResponse(remediation, needs_priming=needs_priming)

        # Metacognition: quick failures on known material -> show answer without penalty
        if (
            not getattr(event, "is_correct", False)
            and getattr(event, "response_time_ms", 0) < 2000
            and state.stability > 5
        ):
            remediation = Remediation.SHOW_ANSWER_NO_PENALTY
            return InterventionResponse(remediation, needs_priming=needs_priming)

        # Attention variance
        variance = state.variance()
        if variance > 4000:
            remediation = Remediation.FOCUS_RESET
            return InterventionResponse(remediation, needs_priming=needs_priming)

        if getattr(event, "is_correct", False) and variance < 500 and state.review_count > 5:
            remediation = Remediation.ACCELERATE
            return InterventionResponse(remediation, needs_priming=needs_priming)

        # Hippocampal interference
        if not getattr(event, "is_correct", False) and state.stability > 5 and state.psi_index > self.psi_threshold:
            remediation = Remediation.CONTRASTIVE
            return InterventionResponse(remediation, needs_priming=needs_priming)

        # P-FIT / integration inefficiency
        total_load = state.visual_load + state.symbolic_load
        if total_load > 1.5 or (getattr(event, "is_correct", False) and getattr(event, "response_time_ms", 0) > 15000):
            remediation = Remediation.WORKED_EXAMPLE
            return InterventionResponse(remediation, needs_priming=needs_priming)

        # Generative hints for complex items on first failure
        if not getattr(event, "is_correct", False) and hints_available:
            remediation = Remediation.SHOW_HINT
            show_hint = True

        return InterventionResponse(
            remediation=remediation,
            show_hint=show_hint,
            suspend=suspend,
            next_interval_days=next_interval,
            needs_priming=needs_priming,
        )
