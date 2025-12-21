"""
Grading Strategy Implementations.

Concrete implementations of grading strategies for each GradingMode.
"""

from __future__ import annotations

import logging
import re
from difflib import SequenceMatcher
from typing import Any

from ..models import GradingLogic, GradingMode, TransformedAtom
from .base import GradingResult, GradingStrategy, StrategyRegistry

logger = logging.getLogger(__name__)


# =============================================================================
# EXACT_MATCH Strategy
# =============================================================================


@StrategyRegistry.register(GradingMode.EXACT_MATCH)
class ExactMatchStrategy(GradingStrategy):
    """
    Grade by exact string matching.

    Supports:
    - Case sensitivity toggle
    - Whitespace normalization
    - Multiple correct answers
    """

    name = "exact_match"

    def grade(self, response: Any, atom: TransformedAtom) -> GradingResult:
        """Grade by exact match."""
        is_valid, error = self._validate_response(response)
        if not is_valid:
            return GradingResult(
                is_correct=False,
                partial_score=0.0,
                feedback_message=error or "Invalid response",
                grading_mode=GradingMode.EXACT_MATCH,
            )

        response_str = str(response).strip()
        expected = self.grading_logic.correct_answer or ""

        # Handle case sensitivity
        if not self.grading_logic.case_sensitive:
            response_str = response_str.lower()
            expected = expected.lower()

        is_correct = response_str == expected

        return GradingResult(
            is_correct=is_correct,
            partial_score=1.0 if is_correct else 0.0,
            feedback_message=self._generate_feedback(is_correct, expected, response_str, atom),
            grading_mode=GradingMode.EXACT_MATCH,
            expected=expected,
            actual=response_str,
        )


# =============================================================================
# FUZZY_MATCH Strategy
# =============================================================================


@StrategyRegistry.register(GradingMode.FUZZY_MATCH)
class FuzzyMatchStrategy(GradingStrategy):
    """
    Grade by fuzzy string matching.

    Uses SequenceMatcher for similarity scoring.
    Supports threshold-based partial credit.
    """

    name = "fuzzy_match"

    # Similarity thresholds
    CORRECT_THRESHOLD = 0.90
    PARTIAL_THRESHOLD = 0.70

    def grade(self, response: Any, atom: TransformedAtom) -> GradingResult:
        """Grade by fuzzy match."""
        is_valid, error = self._validate_response(response)
        if not is_valid:
            return GradingResult(
                is_correct=False,
                partial_score=0.0,
                feedback_message=error or "Invalid response",
                grading_mode=GradingMode.FUZZY_MATCH,
            )

        response_str = self._normalize(str(response))
        expected = self._normalize(self.grading_logic.correct_answer or "")

        # Calculate similarity
        similarity = SequenceMatcher(None, response_str, expected).ratio()

        is_correct = similarity >= self.CORRECT_THRESHOLD

        # Partial credit
        if similarity >= self.CORRECT_THRESHOLD:
            partial_score = 1.0
        elif similarity >= self.PARTIAL_THRESHOLD:
            partial_score = similarity
        else:
            partial_score = 0.0

        # Generate feedback
        if is_correct:
            feedback = "Correct!"
        elif similarity >= self.PARTIAL_THRESHOLD:
            feedback = f"Close! You got {similarity:.0%} correct."
        else:
            feedback = f"Incorrect. The correct answer is: {self.grading_logic.correct_answer}"

        return GradingResult(
            is_correct=is_correct,
            partial_score=partial_score,
            feedback_message=feedback,
            grading_mode=GradingMode.FUZZY_MATCH,
            expected=expected,
            actual=response_str,
            details={"similarity": similarity},
        )


# =============================================================================
# REGEX Strategy
# =============================================================================


@StrategyRegistry.register(GradingMode.REGEX)
class RegexStrategy(GradingStrategy):
    """
    Grade by regex pattern matching.

    Supports pattern validation and capture group extraction.
    """

    name = "regex"

    def grade(self, response: Any, atom: TransformedAtom) -> GradingResult:
        """Grade by regex pattern."""
        is_valid, error = self._validate_response(response)
        if not is_valid:
            return GradingResult(
                is_correct=False,
                partial_score=0.0,
                feedback_message=error or "Invalid response",
                grading_mode=GradingMode.REGEX,
            )

        response_str = str(response).strip()
        pattern = self.grading_logic.pattern or ""

        try:
            # Compile and match
            flags = 0 if self.grading_logic.case_sensitive else re.IGNORECASE
            regex = re.compile(pattern, flags)
            match = regex.fullmatch(response_str)

            is_correct = match is not None

            # Extract groups if matched
            groups = match.groups() if match else None

            if is_correct:
                feedback = "Correct!"
            else:
                feedback = "Incorrect. Your answer doesn't match the expected format."

            return GradingResult(
                is_correct=is_correct,
                partial_score=1.0 if is_correct else 0.0,
                feedback_message=feedback,
                grading_mode=GradingMode.REGEX,
                expected=pattern,
                actual=response_str,
                details={"groups": groups},
            )

        except re.error as e:
            logger.error(f"Invalid regex pattern '{pattern}': {e}")
            return GradingResult(
                is_correct=False,
                partial_score=0.0,
                feedback_message="Grading error: Invalid pattern",
                grading_mode=GradingMode.REGEX,
                details={"error": str(e)},
            )


# =============================================================================
# NUMERIC Strategy
# =============================================================================


@StrategyRegistry.register(GradingMode.NUMERIC)
class NumericStrategy(GradingStrategy):
    """
    Grade numeric responses with tolerance.

    Supports absolute and relative tolerance.
    """

    name = "numeric"

    def grade(self, response: Any, atom: TransformedAtom) -> GradingResult:
        """Grade numeric response."""
        is_valid, error = self._validate_response(response)
        if not is_valid:
            return GradingResult(
                is_correct=False,
                partial_score=0.0,
                feedback_message=error or "Invalid response",
                grading_mode=GradingMode.NUMERIC,
            )

        # Parse response as number
        try:
            actual = float(str(response).strip())
        except ValueError:
            return GradingResult(
                is_correct=False,
                partial_score=0.0,
                feedback_message="Please enter a valid number.",
                grading_mode=GradingMode.NUMERIC,
                actual=response,
            )

        expected = self.grading_logic.expected_value or 0.0
        tolerance = self.grading_logic.tolerance or 0.0

        # Calculate error
        error = abs(actual - expected)
        is_correct = error <= tolerance

        # Partial credit based on proximity
        if tolerance > 0:
            partial_score = max(0.0, 1.0 - (error / (tolerance * 2)))
        else:
            partial_score = 1.0 if is_correct else 0.0

        if is_correct:
            feedback = "Correct!"
        else:
            feedback = f"Incorrect. The correct answer is: {expected}"
            if tolerance > 0:
                feedback += f" (tolerance: ±{tolerance})"

        return GradingResult(
            is_correct=is_correct,
            partial_score=partial_score,
            feedback_message=feedback,
            grading_mode=GradingMode.NUMERIC,
            expected=expected,
            actual=actual,
            details={"error": error, "tolerance": tolerance},
        )


# =============================================================================
# ORDER_MATCH Strategy (for Parsons problems)
# =============================================================================


@StrategyRegistry.register(GradingMode.ORDER_MATCH)
class OrderMatchStrategy(GradingStrategy):
    """
    Grade ordered sequence responses (Parsons problems).

    Supports:
    - Exact order matching
    - Partial credit for partially correct ordering
    - Distractor detection
    """

    name = "order_match"

    def grade(self, response: Any, atom: TransformedAtom) -> GradingResult:
        """Grade ordered sequence."""
        is_valid, error = self._validate_response(response)
        if not is_valid:
            return GradingResult(
                is_correct=False,
                partial_score=0.0,
                feedback_message=error or "Invalid response",
                grading_mode=GradingMode.ORDER_MATCH,
            )

        # Response should be a list of indices
        if not isinstance(response, list):
            return GradingResult(
                is_correct=False,
                partial_score=0.0,
                feedback_message="Please provide an ordered sequence.",
                grading_mode=GradingMode.ORDER_MATCH,
            )

        correct_order = self.grading_logic.correct_order or []

        # Check for exact match
        is_correct = response == correct_order

        # Calculate partial credit using LCS (Longest Common Subsequence)
        lcs_length = self._lcs_length(response, correct_order)
        partial_score = lcs_length / len(correct_order) if correct_order else 0.0

        # Count correct positions
        correct_positions = sum(
            1 for i, item in enumerate(response)
            if i < len(correct_order) and item == correct_order[i]
        )

        if is_correct:
            feedback = "Correct! All items in the right order."
        elif partial_score >= 0.5:
            feedback = f"Partially correct. {correct_positions}/{len(correct_order)} items in correct position."
        else:
            feedback = "Incorrect ordering. Review the sequence logic."

        return GradingResult(
            is_correct=is_correct,
            partial_score=partial_score,
            feedback_message=feedback,
            grading_mode=GradingMode.ORDER_MATCH,
            expected=correct_order,
            actual=response,
            details={
                "correct_positions": correct_positions,
                "lcs_length": lcs_length,
            },
        )

    def _lcs_length(self, a: list, b: list) -> int:
        """Calculate Longest Common Subsequence length."""
        if not a or not b:
            return 0

        m, n = len(a), len(b)
        dp = [[0] * (n + 1) for _ in range(m + 1)]

        for i in range(1, m + 1):
            for j in range(1, n + 1):
                if a[i - 1] == b[j - 1]:
                    dp[i][j] = dp[i - 1][j - 1] + 1
                else:
                    dp[i][j] = max(dp[i - 1][j], dp[i][j - 1])

        return dp[m][n]


# =============================================================================
# SET_MATCH Strategy (for multiple selection)
# =============================================================================


@StrategyRegistry.register(GradingMode.SET_MATCH)
class SetMatchStrategy(GradingStrategy):
    """
    Grade unordered set responses (multiple selection MCQ).

    Supports:
    - Exact set matching
    - Partial credit for subset/superset
    - Negative marking for wrong selections
    """

    name = "set_match"

    def grade(self, response: Any, atom: TransformedAtom) -> GradingResult:
        """Grade set response."""
        is_valid, error = self._validate_response(response)
        if not is_valid:
            return GradingResult(
                is_correct=False,
                partial_score=0.0,
                feedback_message=error or "Invalid response",
                grading_mode=GradingMode.SET_MATCH,
            )

        # Convert to sets
        if isinstance(response, (list, tuple)):
            actual_set = set(response)
        elif isinstance(response, set):
            actual_set = response
        else:
            actual_set = {response}

        correct_set = self.grading_logic.correct_set or set()
        if isinstance(correct_set, list):
            correct_set = set(correct_set)

        # Calculate overlap
        correct_selected = actual_set & correct_set
        incorrect_selected = actual_set - correct_set
        missed = correct_set - actual_set

        is_correct = actual_set == correct_set

        # Partial credit: correct selections minus penalty for wrong ones
        if correct_set:
            credit = len(correct_selected) / len(correct_set)
            penalty = len(incorrect_selected) / len(correct_set) * 0.5
            partial_score = max(0.0, credit - penalty)
        else:
            partial_score = 0.0

        if is_correct:
            feedback = "Correct! All correct options selected."
        elif len(incorrect_selected) > 0:
            feedback = f"Partially correct. You selected {len(incorrect_selected)} incorrect option(s)."
        elif len(missed) > 0:
            feedback = f"Partially correct. You missed {len(missed)} option(s)."
        else:
            feedback = "Incorrect."

        return GradingResult(
            is_correct=is_correct,
            partial_score=partial_score,
            feedback_message=feedback,
            grading_mode=GradingMode.SET_MATCH,
            expected=list(correct_set),
            actual=list(actual_set),
            details={
                "correct_selected": list(correct_selected),
                "incorrect_selected": list(incorrect_selected),
                "missed": list(missed),
            },
        )


# =============================================================================
# RUNTIME Strategy (for Greenlight)
# =============================================================================


@StrategyRegistry.register(GradingMode.RUNTIME)
class RuntimeStrategy(GradingStrategy):
    """
    Grade by runtime execution (Greenlight handoff).

    Delegates actual grading to Greenlight runtime environment.
    This is a placeholder/marker for runtime atoms.
    """

    name = "runtime"

    def grade(self, response: Any, atom: TransformedAtom) -> GradingResult:
        """
        Return placeholder for runtime grading.

        Actual grading is done by Greenlight. This just validates the response
        format and returns a pending result.
        """
        is_valid, error = self._validate_response(response)
        if not is_valid:
            return GradingResult(
                is_correct=False,
                partial_score=0.0,
                feedback_message=error or "Invalid response",
                grading_mode=GradingMode.RUNTIME,
            )

        # Runtime grading happens in Greenlight
        return GradingResult(
            is_correct=False,  # Will be updated by Greenlight
            partial_score=0.0,
            feedback_message="Submitted for runtime evaluation...",
            grading_mode=GradingMode.RUNTIME,
            details={
                "status": "pending",
                "test_command": self.grading_logic.test_command,
                "entrypoint": self.grading_logic.entrypoint,
            },
        )


# =============================================================================
# RUBRIC Strategy (for LLM/human grading)
# =============================================================================


@StrategyRegistry.register(GradingMode.RUBRIC)
class RubricStrategy(GradingStrategy):
    """
    Grade by rubric criteria (LLM or human grading).

    Supports:
    - Multi-criteria rubrics
    - Point-based scoring
    - LLM integration for automated rubric grading
    """

    name = "rubric"

    def grade(self, response: Any, atom: TransformedAtom) -> GradingResult:
        """
        Return placeholder for rubric grading.

        Actual rubric evaluation requires LLM or human review.
        """
        is_valid, error = self._validate_response(response)
        if not is_valid:
            return GradingResult(
                is_correct=False,
                partial_score=0.0,
                feedback_message=error or "Invalid response",
                grading_mode=GradingMode.RUBRIC,
            )

        # Rubric grading requires human/LLM review
        return GradingResult(
            is_correct=False,  # Will be updated by reviewer
            partial_score=0.0,
            feedback_message="Submitted for rubric evaluation...",
            grading_mode=GradingMode.RUBRIC,
            actual=str(response)[:500],  # Truncate for safety
            details={"status": "pending_review"},
        )


# =============================================================================
# HUMAN Strategy (manual review)
# =============================================================================


@StrategyRegistry.register(GradingMode.HUMAN)
class HumanStrategy(GradingStrategy):
    """
    Grade by human review.

    Marks response as pending human evaluation.
    """

    name = "human"

    def grade(self, response: Any, atom: TransformedAtom) -> GradingResult:
        """Return placeholder for human grading."""
        return GradingResult(
            is_correct=False,  # Will be updated by human
            partial_score=0.0,
            feedback_message="Submitted for instructor review.",
            grading_mode=GradingMode.HUMAN,
            actual=str(response)[:500],
            details={"status": "pending_human_review"},
        )
