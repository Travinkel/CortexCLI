"""
Base Grading Strategy.

Provides the abstract base for all grading strategies and
a registry for strategy discovery and instantiation.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, ClassVar

from ..models import GradingLogic, GradingMode, TransformedAtom

logger = logging.getLogger(__name__)


# =============================================================================
# Grading Result
# =============================================================================


@dataclass
class GradingResult:
    """
    Result of grading a learner response.

    Contains scoring, feedback, and diagnostic information.
    """

    # Correctness
    is_correct: bool
    partial_score: float  # 0.0 to 1.0

    # Feedback
    feedback_message: str
    explanation: str | None = None
    hint: str | None = None

    # Diagnostic
    error_class: str | None = None  # slip, misconception, missing_prerequisite
    misconception_code: str | None = None  # Links to misconception_library

    # Metadata
    grading_mode: GradingMode = GradingMode.EXACT_MATCH
    latency_ms: int = 0

    # Details
    expected: Any = None
    actual: Any = None
    details: dict[str, Any] = field(default_factory=dict)

    @property
    def passed(self) -> bool:
        """Alias for is_correct."""
        return self.is_correct

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "is_correct": self.is_correct,
            "partial_score": self.partial_score,
            "feedback_message": self.feedback_message,
            "explanation": self.explanation,
            "hint": self.hint,
            "error_class": self.error_class,
            "misconception_code": self.misconception_code,
            "grading_mode": self.grading_mode.value,
            "expected": self.expected,
            "actual": self.actual,
            "details": self.details,
        }


# =============================================================================
# Strategy Registry
# =============================================================================


class StrategyRegistry:
    """
    Registry for grading strategies.

    Enables automatic strategy selection based on GradingMode.

    Example:
        # Register a strategy
        @StrategyRegistry.register(GradingMode.EXACT_MATCH)
        class ExactMatchStrategy(GradingStrategy):
            ...

        # Get a strategy
        strategy = StrategyRegistry.get(GradingMode.EXACT_MATCH)

        # Auto-select from atom
        strategy = StrategyRegistry.for_atom(atom)
    """

    _strategies: ClassVar[dict[GradingMode, type[GradingStrategy]]] = {}

    @classmethod
    def register(cls, mode: GradingMode):
        """
        Decorator to register a grading strategy.

        Args:
            mode: GradingMode this strategy handles
        """

        def decorator(strategy_class: type[GradingStrategy]):
            cls._strategies[mode] = strategy_class
            strategy_class.grading_mode = mode
            logger.debug(f"Registered strategy: {mode.value} -> {strategy_class.__name__}")
            return strategy_class

        return decorator

    @classmethod
    def get(cls, mode: GradingMode) -> type[GradingStrategy]:
        """Get strategy class by grading mode."""
        if mode not in cls._strategies:
            raise KeyError(f"No strategy registered for mode: {mode.value}")
        return cls._strategies[mode]

    @classmethod
    def for_atom(cls, atom: TransformedAtom) -> GradingStrategy:
        """
        Create strategy instance for an atom.

        Args:
            atom: Atom to grade

        Returns:
            Configured strategy instance
        """
        if not atom.grading_logic:
            # Default to exact match
            mode = GradingMode.EXACT_MATCH
        else:
            mode = atom.grading_logic.mode

        strategy_class = cls.get(mode)
        return strategy_class(atom.grading_logic)

    @classmethod
    def list_strategies(cls) -> dict[str, type[GradingStrategy]]:
        """List all registered strategies."""
        return {mode.value: cls._strategies[mode] for mode in cls._strategies}


# =============================================================================
# Base Grading Strategy
# =============================================================================


class GradingStrategy(ABC):
    """
    Abstract base class for grading strategies.

    Strategies encapsulate the logic for grading a specific type of response.
    Each strategy knows how to:
    1. Validate the response format
    2. Compare against the expected answer
    3. Calculate partial credit
    4. Generate appropriate feedback

    Subclasses must implement:
    - grade(): Main grading logic
    - _validate_response(): Check response format
    """

    grading_mode: ClassVar[GradingMode] = GradingMode.EXACT_MATCH
    name: ClassVar[str] = "base_strategy"
    version: ClassVar[str] = "1.0.0"

    def __init__(self, grading_logic: GradingLogic | None = None):
        """
        Initialize strategy.

        Args:
            grading_logic: Configuration for this grading instance
        """
        self.grading_logic = grading_logic or GradingLogic(mode=self.grading_mode)

    @abstractmethod
    def grade(self, response: Any, atom: TransformedAtom) -> GradingResult:
        """
        Grade a learner response.

        Args:
            response: The learner's response (format depends on atom type)
            atom: The atom being graded

        Returns:
            GradingResult with score and feedback
        """
        ...

    def _validate_response(self, response: Any) -> tuple[bool, str | None]:
        """
        Validate the response format.

        Args:
            response: The learner's response

        Returns:
            (is_valid, error_message)
        """
        if response is None:
            return False, "No response provided"
        return True, None

    def _normalize(self, text: str) -> str:
        """Normalize text for comparison."""
        if not isinstance(text, str):
            return str(text)
        return text.strip().lower()

    def _generate_feedback(
        self,
        is_correct: bool,
        expected: Any,
        actual: Any,
        atom: TransformedAtom,
    ) -> str:
        """Generate appropriate feedback message."""
        if is_correct:
            return "Correct!"

        # Try to get explanation from content
        if atom.content and atom.content.answer:
            return f"Incorrect. The correct answer is: {atom.content.answer}"

        return "Incorrect."


# =============================================================================
# Composite Strategy (for multi-part grading)
# =============================================================================


class CompositeStrategy(GradingStrategy):
    """
    Strategy that combines multiple sub-strategies.

    Useful for atoms with multiple parts that use different grading modes.

    Example:
        strategy = CompositeStrategy([
            (0.5, ExactMatchStrategy(), "part1"),
            (0.5, NumericStrategy(), "part2"),
        ])
    """

    name = "composite"

    def __init__(
        self,
        strategies: list[tuple[float, GradingStrategy, str]],
        grading_logic: GradingLogic | None = None,
    ):
        """
        Initialize composite strategy.

        Args:
            strategies: List of (weight, strategy, key) tuples
            grading_logic: Optional override configuration
        """
        super().__init__(grading_logic)
        self.strategies = strategies

        # Validate weights sum to 1.0
        total_weight = sum(weight for weight, _, _ in strategies)
        if abs(total_weight - 1.0) > 0.001:
            raise ValueError(f"Strategy weights must sum to 1.0, got {total_weight}")

    def grade(self, response: dict[str, Any], atom: TransformedAtom) -> GradingResult:
        """
        Grade each part and combine results.

        Args:
            response: Dictionary with keys matching strategy keys
            atom: The atom being graded

        Returns:
            Combined GradingResult
        """
        total_score = 0.0
        all_correct = True
        feedback_parts = []
        details = {}

        for weight, strategy, key in self.strategies:
            part_response = response.get(key)

            if part_response is None:
                all_correct = False
                feedback_parts.append(f"{key}: No response")
                continue

            result = strategy.grade(part_response, atom)

            total_score += weight * result.partial_score
            if not result.is_correct:
                all_correct = False

            feedback_parts.append(f"{key}: {result.feedback_message}")
            details[key] = result.to_dict()

        return GradingResult(
            is_correct=all_correct,
            partial_score=total_score,
            feedback_message=" | ".join(feedback_parts),
            grading_mode=GradingMode.EXACT_MATCH,  # Composite mode
            details={"parts": details},
        )
