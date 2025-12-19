"""
Quiz Question Quality Analyzer.

Extends CardQualityAnalyzer to provide quality analysis for quiz questions
with type-specific thresholds and distractor quality assessment.

Learning Atom Types Supported:
- flashcard: Standard Q&A with free recall
- cloze: Fill-in-blank contextual recall
- mcq: Multiple choice with discrimination
- true_false: Binary discrimination
- short_answer: Free recall with multiple correct answers
- matching: Pair discrimination (max 6 pairs)
- ranking: Order discrimination (max 8 items)
- sequence: Step reordering from memory
- prediction: Predict outcome before feedback
- parsons: Code block arrangement (6-10 lines)
- explain: Essay-style elaboration
- compare: Contrast two concepts
- problem: Solve/implement task
- project: Complex build task

Quality Criteria (from right-learning research):
- Question: 8-15 words optimal, 16-25 warning, >25 reject
- Answer: 1-5 words optimal, 6-15 warning, >15 reject
- Characters: Question max 200, Answer max 120
- Code: 2-5 lines optimal, 6-10 max
- Matching/Ranking: Max 6 items (working memory limit)
- Atomicity: 1 fact per atom

Grade Distribution:
- A (90-100): All metrics optimal
- B (75-89): All metrics within warning
- C (60-74): 1-2 metrics in warning zone
- D (40-59): Any metric in reject zone, needs rewrite
- F (<40): Multiple metrics in reject zone, block
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
from typing import Any


class QuestionType(Enum):
    """Supported quiz question types."""

    MCQ = "mcq"
    TRUE_FALSE = "true_false"
    SHORT_ANSWER = "short_answer"
    MATCHING = "matching"
    RANKING = "ranking"
    PASSAGE_BASED = "passage_based"
    CLOZE = "cloze"
    SEQUENCE = "sequence"
    PREDICTION = "prediction"
    PARSONS = "parsons"
    EXPLAIN = "explain"
    COMPARE = "compare"
    PROBLEM = "problem"


class KnowledgeType(Enum):
    """Knowledge types from cognitive science."""

    FACTUAL = "factual"  # Passing 70%
    CONCEPTUAL = "conceptual"  # Passing 80%
    PROCEDURAL = "procedural"  # Passing 85%
    STRATEGIC = "strategic"  # Passing 85%


class LearningMechanism(Enum):
    """Learning mechanisms from educational research."""

    RETRIEVAL = "retrieval"  # d=0.7 for free recall
    GENERATION = "generation"  # d=0.5
    ELABORATION = "elaboration"  # d=0.6
    DISCRIMINATION = "discrimination"  # d=0.6
    APPLICATION = "application"  # d=0.5


@dataclass
class QuestionQualityIssue:
    """Detected quality issue."""

    code: str
    severity: str  # 'error', 'warning', 'info'
    message: str
    penalty: int = 0


@dataclass
class QuestionQualityReport:
    """Quality analysis report for a quiz question."""

    score: float
    grade: str  # A-F
    issues: list[QuestionQualityIssue]
    recommendations: list[str]

    # Content metrics
    question_word_count: int = 0
    question_char_count: int = 0
    answer_word_count: int = 0
    answer_char_count: int = 0
    code_line_count: int = 0

    # Type-specific metrics
    option_count: int | None = None
    distractor_quality_score: float | None = None
    answer_clarity_score: float | None = None

    # Flags
    is_atomic: bool = True
    needs_rewrite: bool = False
    is_valid_structure: bool = True

    @property
    def has_errors(self) -> bool:
        return any(i.severity == "error" for i in self.issues)

    @property
    def has_warnings(self) -> bool:
        return any(i.severity == "warning" for i in self.issues)


@dataclass
class TypeSpecificThresholds:
    """Thresholds adjusted by question type."""

    question_chars_adjustment: int = 0
    answer_chars_adjustment: int = 0
    answer_words_adjustment: int = 0
    code_lines_adjustment: int = 0
    max_items: int | None = None  # For matching/ranking


class QuizQuestionAnalyzer:
    """
    Analyzer for quiz question quality.

    Implements evidence-based quality criteria from learning science research.
    """

    VERSION = "1.0.0"

    # Base thresholds (from right-learning research)
    QUESTION_WORDS_OPTIMAL = 15
    QUESTION_WORDS_MAX = 25
    QUESTION_CHARS_MAX = 200

    ANSWER_WORDS_OPTIMAL = 5
    ANSWER_WORDS_WARNING = 15
    ANSWER_WORDS_MAX = 25
    ANSWER_CHARS_MAX = 120

    CODE_LINES_OPTIMAL = 5
    CODE_LINES_MAX = 10

    # Grade boundaries
    GRADE_A_MIN = 90
    GRADE_B_MIN = 75
    GRADE_C_MIN = 60
    GRADE_D_MIN = 40

    # Type-specific threshold adjustments
    TYPE_ADJUSTMENTS: dict[QuestionType, TypeSpecificThresholds] = {
        QuestionType.CLOZE: TypeSpecificThresholds(question_chars_adjustment=50),
        QuestionType.MATCHING: TypeSpecificThresholds(max_items=6),
        QuestionType.RANKING: TypeSpecificThresholds(max_items=8),
        QuestionType.PARSONS: TypeSpecificThresholds(code_lines_adjustment=5),
        QuestionType.EXPLAIN: TypeSpecificThresholds(answer_chars_adjustment=100),
        QuestionType.COMPARE: TypeSpecificThresholds(answer_chars_adjustment=50),
        QuestionType.PROBLEM: TypeSpecificThresholds(code_lines_adjustment=10),
        QuestionType.MCQ: TypeSpecificThresholds(),
        QuestionType.TRUE_FALSE: TypeSpecificThresholds(),
        QuestionType.SHORT_ANSWER: TypeSpecificThresholds(),
        QuestionType.SEQUENCE: TypeSpecificThresholds(max_items=8),
        QuestionType.PREDICTION: TypeSpecificThresholds(),
        QuestionType.PASSAGE_BASED: TypeSpecificThresholds(question_chars_adjustment=100),
    }

    # Learning mechanism to question type mapping
    MECHANISM_MAPPING: dict[QuestionType, LearningMechanism] = {
        QuestionType.MCQ: LearningMechanism.DISCRIMINATION,
        QuestionType.TRUE_FALSE: LearningMechanism.DISCRIMINATION,
        QuestionType.SHORT_ANSWER: LearningMechanism.RETRIEVAL,
        QuestionType.MATCHING: LearningMechanism.DISCRIMINATION,
        QuestionType.RANKING: LearningMechanism.DISCRIMINATION,
        QuestionType.CLOZE: LearningMechanism.RETRIEVAL,
        QuestionType.SEQUENCE: LearningMechanism.RETRIEVAL,
        QuestionType.PREDICTION: LearningMechanism.GENERATION,
        QuestionType.PARSONS: LearningMechanism.APPLICATION,
        QuestionType.EXPLAIN: LearningMechanism.ELABORATION,
        QuestionType.COMPARE: LearningMechanism.DISCRIMINATION,
        QuestionType.PROBLEM: LearningMechanism.APPLICATION,
        QuestionType.PASSAGE_BASED: LearningMechanism.ELABORATION,
    }

    def __init__(self):
        self.version = self.VERSION

    def analyze(
        self,
        front: str,
        back: str | None,
        question_type: str | QuestionType,
        question_content: dict[str, Any] | None = None,
        knowledge_type: str | None = None,
    ) -> QuestionQualityReport:
        """
        Analyze quiz question quality.

        Args:
            front: Question text
            back: Answer text (may be None for MCQ)
            question_type: Type of question
            question_content: Type-specific content (options, pairs, etc.)
            knowledge_type: Knowledge type (factual, conceptual, etc.)

        Returns:
            QuestionQualityReport with score, grade, and issues
        """
        if isinstance(question_type, str):
            try:
                question_type = QuestionType(question_type)
            except ValueError:
                question_type = QuestionType.MCQ  # Default

        issues: list[QuestionQualityIssue] = []
        recommendations: list[str] = []
        score = 100.0

        # Get type-specific adjustments
        adjustments = self.TYPE_ADJUSTMENTS.get(question_type, TypeSpecificThresholds())

        # Calculate effective thresholds
        question_chars_max = self.QUESTION_CHARS_MAX + adjustments.question_chars_adjustment
        answer_chars_max = self.ANSWER_CHARS_MAX + adjustments.answer_chars_adjustment
        code_lines_max = self.CODE_LINES_MAX + adjustments.code_lines_adjustment

        # Analyze question text
        question_word_count = len(front.split()) if front else 0
        question_char_count = len(front) if front else 0

        # Check question length
        if question_word_count > self.QUESTION_WORDS_MAX:
            penalty = 30
            issues.append(
                QuestionQualityIssue(
                    code="QUESTION_TOO_LONG",
                    severity="error",
                    message=f"Question has {question_word_count} words (max: {self.QUESTION_WORDS_MAX})",
                    penalty=penalty,
                )
            )
            recommendations.append(f"Simplify the question to ≤{self.QUESTION_WORDS_MAX} words")
            score -= penalty
        elif question_word_count > self.QUESTION_WORDS_OPTIMAL:
            penalty = 10
            issues.append(
                QuestionQualityIssue(
                    code="QUESTION_VERBOSE",
                    severity="warning",
                    message=f"Question has {question_word_count} words (optimal: ≤{self.QUESTION_WORDS_OPTIMAL})",
                    penalty=penalty,
                )
            )
            score -= penalty

        # Check question characters
        if question_char_count > question_chars_max:
            penalty = 20
            issues.append(
                QuestionQualityIssue(
                    code="QUESTION_CHARS_EXCEEDED",
                    severity="error",
                    message=f"Question has {question_char_count} chars (max: {question_chars_max})",
                    penalty=penalty,
                )
            )
            recommendations.append("Reduce visual complexity by shortening question")
            score -= penalty

        # Analyze answer text (if applicable)
        answer_word_count = 0
        answer_char_count = 0
        code_line_count = 0

        if back and question_type not in [QuestionType.MCQ, QuestionType.TRUE_FALSE]:
            answer_word_count, code_line_count = self._count_words_excluding_code(back)
            answer_char_count = len(back)

            # Check answer length
            if answer_word_count > self.ANSWER_WORDS_MAX:
                penalty = 30
                issues.append(
                    QuestionQualityIssue(
                        code="ANSWER_TOO_LONG",
                        severity="error",
                        message=f"Answer has {answer_word_count} words (max: {self.ANSWER_WORDS_MAX})",
                        penalty=penalty,
                    )
                )
                recommendations.append("Consider splitting into multiple atomic cards")
                score -= penalty
            elif answer_word_count > self.ANSWER_WORDS_WARNING:
                penalty = 10
                issues.append(
                    QuestionQualityIssue(
                        code="ANSWER_VERBOSE",
                        severity="warning",
                        message=f"Answer has {answer_word_count} words (optimal: ≤{self.ANSWER_WORDS_OPTIMAL})",
                        penalty=penalty,
                    )
                )
                score -= penalty

            # Check answer characters
            if answer_char_count > answer_chars_max:
                penalty = 20
                issues.append(
                    QuestionQualityIssue(
                        code="ANSWER_CHARS_EXCEEDED",
                        severity="error",
                        message=f"Answer has {answer_char_count} chars (max: {answer_chars_max})",
                        penalty=penalty,
                    )
                )
                score -= penalty

            # Check code lines
            if code_line_count > code_lines_max:
                penalty = 25
                issues.append(
                    QuestionQualityIssue(
                        code="CODE_TOO_LONG",
                        severity="error",
                        message=f"Code has {code_line_count} lines (max: {code_lines_max})",
                        penalty=penalty,
                    )
                )
                recommendations.append("Focus on the key snippet only")
                score -= penalty
            elif code_line_count > self.CODE_LINES_OPTIMAL:
                penalty = 10
                issues.append(
                    QuestionQualityIssue(
                        code="CODE_VERBOSE",
                        severity="warning",
                        message=f"Code has {code_line_count} lines (optimal: ≤{self.CODE_LINES_OPTIMAL})",
                        penalty=penalty,
                    )
                )
                score -= penalty

        # Check atomicity
        is_atomic = True
        if back:
            if self._has_enumeration(back):
                penalty = 30
                issues.append(
                    QuestionQualityIssue(
                        code="ENUMERATION_DETECTED",
                        severity="error",
                        message="Enumeration detected in answer",
                        penalty=penalty,
                    )
                )
                recommendations.append("Split into separate cards for each item")
                score -= penalty
                is_atomic = False

            if self._has_multiple_facts(back):
                penalty = 30
                issues.append(
                    QuestionQualityIssue(
                        code="MULTIPLE_FACTS",
                        severity="error",
                        message="Multiple facts detected in answer",
                        penalty=penalty,
                    )
                )
                recommendations.append("One atomic fact per card is optimal")
                score -= penalty
                is_atomic = False

        # Check multi-subquestion
        if self._has_multi_subquestion(front):
            penalty = 30
            issues.append(
                QuestionQualityIssue(
                    code="MULTI_SUBQUESTION",
                    severity="error",
                    message="Multiple sub-questions detected",
                    penalty=penalty,
                )
            )
            recommendations.append("Split into separate questions")
            score -= penalty
            is_atomic = False

        # Type-specific validation
        option_count = None
        distractor_quality = None
        answer_clarity = None
        is_valid_structure = True

        if question_content:
            validation_result = self._validate_type_specific(
                question_type, question_content, adjustments
            )
            is_valid_structure = validation_result["is_valid"]
            option_count = validation_result.get("option_count")
            distractor_quality = validation_result.get("distractor_quality")
            answer_clarity = validation_result.get("answer_clarity")

            for issue in validation_result.get("issues", []):
                issues.append(issue)
                score -= issue.penalty

            for rec in validation_result.get("recommendations", []):
                recommendations.append(rec)

        # Ensure score doesn't go negative
        score = max(0, score)

        # Calculate grade
        grade = self._calculate_grade(score)

        # Determine if rewrite needed
        needs_rewrite = grade in ["D", "F"]

        return QuestionQualityReport(
            score=score,
            grade=grade,
            issues=issues,
            recommendations=recommendations,
            question_word_count=question_word_count,
            question_char_count=question_char_count,
            answer_word_count=answer_word_count,
            answer_char_count=answer_char_count,
            code_line_count=code_line_count,
            option_count=option_count,
            distractor_quality_score=distractor_quality,
            answer_clarity_score=answer_clarity,
            is_atomic=is_atomic,
            needs_rewrite=needs_rewrite,
            is_valid_structure=is_valid_structure,
        )

    def _count_words_excluding_code(self, text: str) -> tuple[int, int]:
        """Count words excluding code blocks and return code line count."""
        # Extract code blocks
        code_pattern = r"```[\s\S]*?```|`[^`]+`"
        code_blocks = re.findall(code_pattern, text)

        # Count code lines
        code_lines = 0
        for block in code_blocks:
            lines = block.strip().split("\n")
            # Exclude opening/closing ``` markers
            code_lines += max(0, len(lines) - 2)

        # Remove code blocks for word count
        text_without_code = re.sub(code_pattern, "", text)
        word_count = len(text_without_code.split())

        return word_count, code_lines

    def _has_enumeration(self, text: str) -> bool:
        """Detect bullet/numbered lists."""
        patterns = [
            r"^\s*[-•*]\s+",  # Bullet points
            r"^\s*\d+[.)]\s+",  # Numbered lists
            r"^\s*[a-z][.)]\s+",  # Letter lists
        ]
        lines = text.split("\n")
        list_lines = sum(
            1 for line in lines if any(re.match(p, line, re.IGNORECASE) for p in patterns)
        )
        return list_lines >= 2

    def _has_multiple_facts(self, text: str) -> bool:
        """Detect multiple facts via sentence count and causal markers."""
        # Count sentences
        sentences = re.split(r"[.!?]+", text)
        sentence_count = len([s for s in sentences if s.strip()])

        if sentence_count > 2:
            return True

        # Check for causal markers
        causal_markers = ["because", "therefore", "since", "thus", "hence", "so that"]
        text_lower = text.lower()
        marker_count = sum(1 for m in causal_markers if m in text_lower)

        return marker_count >= 2

    def _has_multi_subquestion(self, text: str) -> bool:
        """Detect multiple sub-questions."""
        # Count question marks
        question_marks = text.count("?")
        if question_marks > 1:
            return True

        # Check for compound questions
        compound_patterns = [
            r"\band\s+what\b",
            r"\band\s+how\b",
            r"\band\s+why\b",
            r"\band\s+when\b",
        ]
        text_lower = text.lower()
        return any(re.search(p, text_lower) for p in compound_patterns)

    def _validate_type_specific(
        self,
        question_type: QuestionType,
        content: dict[str, Any],
        adjustments: TypeSpecificThresholds,
    ) -> dict[str, Any]:
        """Validate type-specific content structure and quality."""
        result = {
            "is_valid": True,
            "issues": [],
            "recommendations": [],
        }

        if question_type == QuestionType.MCQ:
            return self._validate_mcq(content, adjustments)
        elif question_type == QuestionType.TRUE_FALSE:
            return self._validate_true_false(content)
        elif question_type == QuestionType.SHORT_ANSWER:
            return self._validate_short_answer(content)
        elif question_type == QuestionType.MATCHING:
            return self._validate_matching(content, adjustments)
        elif question_type == QuestionType.RANKING:
            return self._validate_ranking(content, adjustments)
        elif question_type == QuestionType.PARSONS:
            return self._validate_parsons(content, adjustments)

        return result

    def _validate_mcq(
        self, content: dict[str, Any], adjustments: TypeSpecificThresholds
    ) -> dict[str, Any]:
        """Validate MCQ structure and distractor quality."""
        result = {
            "is_valid": True,
            "issues": [],
            "recommendations": [],
        }

        options = content.get("options", [])
        correct_index = content.get("correct_index")

        if not options:
            result["is_valid"] = False
            result["issues"].append(
                QuestionQualityIssue(
                    code="MCQ_NO_OPTIONS",
                    severity="error",
                    message="MCQ requires options array",
                    penalty=50,
                )
            )
            return result

        result["option_count"] = len(options)

        # Validate option count (3-6 for working memory)
        if len(options) < 3:
            result["issues"].append(
                QuestionQualityIssue(
                    code="MCQ_TOO_FEW_OPTIONS",
                    severity="warning",
                    message=f"MCQ has {len(options)} options (recommend 3-4)",
                    penalty=10,
                )
            )
        elif len(options) > 6:
            result["issues"].append(
                QuestionQualityIssue(
                    code="MCQ_TOO_MANY_OPTIONS",
                    severity="error",
                    message=f"MCQ has {len(options)} options (max 6 for working memory)",
                    penalty=20,
                )
            )
            result["recommendations"].append("Reduce to 4-6 options (working memory limit)")

        # Validate correct_index
        if correct_index is None:
            result["is_valid"] = False
            result["issues"].append(
                QuestionQualityIssue(
                    code="MCQ_NO_CORRECT_INDEX",
                    severity="error",
                    message="MCQ requires correct_index",
                    penalty=50,
                )
            )
        elif not 0 <= correct_index < len(options):
            result["is_valid"] = False
            result["issues"].append(
                QuestionQualityIssue(
                    code="MCQ_INVALID_CORRECT_INDEX",
                    severity="error",
                    message=f"correct_index {correct_index} out of range",
                    penalty=50,
                )
            )

        # Analyze distractor quality
        if len(options) >= 3 and result["is_valid"]:
            distractor_score = self._analyze_distractor_quality(options, correct_index)
            result["distractor_quality"] = distractor_score

            if distractor_score < 0.6:
                result["issues"].append(
                    QuestionQualityIssue(
                        code="MCQ_POOR_DISTRACTORS",
                        severity="warning",
                        message=f"Distractor quality score {distractor_score:.2f} (recommend ≥0.6)",
                        penalty=15,
                    )
                )
                result["recommendations"].append("Improve distractors to be more plausible")

        return result

    def _validate_true_false(self, content: dict[str, Any]) -> dict[str, Any]:
        """Validate True/False structure."""
        result = {
            "is_valid": True,
            "issues": [],
            "recommendations": [],
        }

        if "correct" not in content:
            result["is_valid"] = False
            result["issues"].append(
                QuestionQualityIssue(
                    code="TF_NO_CORRECT",
                    severity="error",
                    message="True/False requires 'correct' boolean",
                    penalty=50,
                )
            )

        return result

    def _validate_short_answer(self, content: dict[str, Any]) -> dict[str, Any]:
        """Validate short answer structure."""
        result = {
            "is_valid": True,
            "issues": [],
            "recommendations": [],
        }

        correct_answers = content.get("correct_answers", [])
        if not correct_answers:
            result["is_valid"] = False
            result["issues"].append(
                QuestionQualityIssue(
                    code="SA_NO_CORRECT_ANSWERS",
                    severity="error",
                    message="Short answer requires 'correct_answers' array",
                    penalty=50,
                )
            )
        elif len(correct_answers) == 1:
            result["recommendations"].append("Consider adding alternative acceptable answers")

        return result

    def _validate_matching(
        self, content: dict[str, Any], adjustments: TypeSpecificThresholds
    ) -> dict[str, Any]:
        """Validate matching question structure."""
        result = {
            "is_valid": True,
            "issues": [],
            "recommendations": [],
        }

        pairs = content.get("pairs", [])
        max_items = adjustments.max_items or 6

        if not pairs:
            result["is_valid"] = False
            result["issues"].append(
                QuestionQualityIssue(
                    code="MATCH_NO_PAIRS",
                    severity="error",
                    message="Matching requires 'pairs' array",
                    penalty=50,
                )
            )
            return result

        result["option_count"] = len(pairs)

        if len(pairs) > max_items:
            result["issues"].append(
                QuestionQualityIssue(
                    code="MATCH_TOO_MANY_PAIRS",
                    severity="error",
                    message=f"Matching has {len(pairs)} pairs (max {max_items} for working memory)",
                    penalty=25,
                )
            )
            result["recommendations"].append(f"Reduce to ≤{max_items} pairs (working memory limit)")

        # Validate pair structure
        for i, pair in enumerate(pairs):
            if "left" not in pair or "right" not in pair:
                result["is_valid"] = False
                result["issues"].append(
                    QuestionQualityIssue(
                        code="MATCH_INVALID_PAIR",
                        severity="error",
                        message=f"Pair {i} missing 'left' or 'right'",
                        penalty=20,
                    )
                )

        return result

    def _validate_ranking(
        self, content: dict[str, Any], adjustments: TypeSpecificThresholds
    ) -> dict[str, Any]:
        """Validate ranking question structure."""
        result = {
            "is_valid": True,
            "issues": [],
            "recommendations": [],
        }

        items = content.get("items", [])
        correct_order = content.get("correct_order", [])
        max_items = adjustments.max_items or 8

        if not items:
            result["is_valid"] = False
            result["issues"].append(
                QuestionQualityIssue(
                    code="RANK_NO_ITEMS",
                    severity="error",
                    message="Ranking requires 'items' array",
                    penalty=50,
                )
            )
            return result

        if not correct_order:
            result["is_valid"] = False
            result["issues"].append(
                QuestionQualityIssue(
                    code="RANK_NO_ORDER",
                    severity="error",
                    message="Ranking requires 'correct_order' array",
                    penalty=50,
                )
            )
            return result

        result["option_count"] = len(items)

        if len(items) > max_items:
            result["issues"].append(
                QuestionQualityIssue(
                    code="RANK_TOO_MANY_ITEMS",
                    severity="error",
                    message=f"Ranking has {len(items)} items (max {max_items} for cognitive load)",
                    penalty=25,
                )
            )

        if len(items) != len(correct_order):
            result["is_valid"] = False
            result["issues"].append(
                QuestionQualityIssue(
                    code="RANK_MISMATCHED_LENGTH",
                    severity="error",
                    message="Items and correct_order must have same length",
                    penalty=50,
                )
            )

        return result

    def _validate_parsons(
        self, content: dict[str, Any], adjustments: TypeSpecificThresholds
    ) -> dict[str, Any]:
        """Validate Parsons problem structure."""
        result = {
            "is_valid": True,
            "issues": [],
            "recommendations": [],
        }

        blocks = content.get("blocks", content.get("items", []))
        max_lines = self.CODE_LINES_MAX + (adjustments.code_lines_adjustment or 5)

        if not blocks:
            result["is_valid"] = False
            result["issues"].append(
                QuestionQualityIssue(
                    code="PARSONS_NO_BLOCKS",
                    severity="error",
                    message="Parsons requires 'blocks' array",
                    penalty=50,
                )
            )
            return result

        result["option_count"] = len(blocks)

        if len(blocks) < 3:
            result["issues"].append(
                QuestionQualityIssue(
                    code="PARSONS_TOO_FEW_BLOCKS",
                    severity="warning",
                    message=f"Parsons has only {len(blocks)} blocks (recommend 6-10)",
                    penalty=10,
                )
            )

        if len(blocks) > max_lines:
            result["issues"].append(
                QuestionQualityIssue(
                    code="PARSONS_TOO_MANY_BLOCKS",
                    severity="error",
                    message=f"Parsons has {len(blocks)} blocks (max {max_lines})",
                    penalty=20,
                )
            )
            result["recommendations"].append(
                f"Reduce to ≤{max_lines} blocks to limit cognitive load"
            )

        return result

    def _analyze_distractor_quality(self, options: list[str], correct_index: int) -> float:
        """
        Analyze the quality of MCQ distractors.

        Good distractors should be:
        - Similar in length to correct answer
        - Grammatically consistent
        - Plausible but clearly wrong
        - Not obviously incorrect

        Returns:
            Quality score 0-1
        """
        if not options or correct_index is None:
            return 0.0

        correct = options[correct_index]
        correct_len = len(correct)

        scores = []

        for i, option in enumerate(options):
            if i == correct_index:
                continue

            option_len = len(option)

            # Length similarity (0-1)
            len_ratio = min(option_len, correct_len) / max(option_len, correct_len, 1)

            # Check for obviously wrong patterns
            penalty = 0.0
            option_lower = option.lower()

            # "All of the above" or "None of the above" are weak distractors
            if "all of the" in option_lower or "none of the" in option_lower:
                penalty += 0.3

            # Very short options are often weak
            if option_len < 10:
                penalty += 0.2

            # Options with "never" or "always" are often obviously wrong
            if " never " in option_lower or " always " in option_lower:
                penalty += 0.1

            score = max(0, len_ratio - penalty)
            scores.append(score)

        return sum(scores) / len(scores) if scores else 0.5

    def _calculate_grade(self, score: float) -> str:
        """Calculate letter grade from score."""
        if score >= self.GRADE_A_MIN:
            return "A"
        elif score >= self.GRADE_B_MIN:
            return "B"
        elif score >= self.GRADE_C_MIN:
            return "C"
        elif score >= self.GRADE_D_MIN:
            return "D"
        return "F"

    def get_passing_threshold(self, knowledge_type: str | KnowledgeType) -> float:
        """Get passing threshold for knowledge type."""
        if isinstance(knowledge_type, str):
            try:
                knowledge_type = KnowledgeType(knowledge_type)
            except ValueError:
                return 0.70

        thresholds = {
            KnowledgeType.FACTUAL: 0.70,
            KnowledgeType.CONCEPTUAL: 0.80,
            KnowledgeType.PROCEDURAL: 0.85,
            KnowledgeType.STRATEGIC: 0.85,
        }
        return thresholds.get(knowledge_type, 0.70)

    def get_primary_mechanism(self, question_type: str | QuestionType) -> LearningMechanism | None:
        """Get primary learning mechanism for question type."""
        if isinstance(question_type, str):
            try:
                question_type = QuestionType(question_type)
            except ValueError:
                return None
        return self.MECHANISM_MAPPING.get(question_type)
