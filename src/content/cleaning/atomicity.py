"""
Card Quality Analyzer (ADR-002)

Evidence-based quality analysis for learning atoms (flashcards, quiz questions, etc.)
based on learning science research.

See:
- docs/foundations/flashcard-quality-science.md
- docs/adr/002-flashcard-quality-standards.md
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum

from .thresholds import (
    BACK_CHARS_MAX,
    BACK_WORDS_MAX,
    BACK_WORDS_OPTIMAL,
    CODE_LINES_MAX,
    CODE_LINES_OPTIMAL,
    FRONT_CHARS_MAX,
    FRONT_WORDS_MAX,
    FRONT_WORDS_OPTIMAL,
    GRADE_A_MIN,
    GRADE_B_MIN,
    GRADE_C_MIN,
    GRADE_D_MIN,
    PENALTY_BACK_CHARS,
    PENALTY_BACK_TOO_LONG,
    PENALTY_BACK_VERBOSE,
    PENALTY_CODE_TOO_LONG,
    PENALTY_CODE_VERBOSE,
    PENALTY_ENUMERATION,
    PENALTY_FRONT_CHARS,
    PENALTY_FRONT_TOO_LONG,
    PENALTY_FRONT_VERBOSE,
    PENALTY_GENERIC_QUESTION,
    PENALTY_INCOHERENT_TEXT,
    PENALTY_MALFORMED_QUESTION,
    PENALTY_MULTIPLE_FACTS,
    PENALTY_TOO_SHORT,
)


class QualityIssue(str, Enum):
    """Quality issues detected in learning atoms."""

    # Word count issues
    FRONT_TOO_LONG = "FRONT_TOO_LONG"  # Front >25 words
    FRONT_VERBOSE = "FRONT_VERBOSE"  # Front >15 words (warning)
    BACK_TOO_LONG = "BACK_TOO_LONG"  # Back >15 words
    BACK_VERBOSE = "BACK_VERBOSE"  # Back >5 words (warning)

    # Character count issues
    FRONT_CHARS_EXCEEDED = "FRONT_CHARS_EXCEEDED"  # Front >200 chars
    BACK_CHARS_EXCEEDED = "BACK_CHARS_EXCEEDED"  # Back >120 chars

    # Code issues
    CODE_TOO_LONG = "CODE_TOO_LONG"  # Code >10 lines
    CODE_VERBOSE = "CODE_VERBOSE"  # Code >5 lines (warning)

    # Atomicity issues
    ENUMERATION_DETECTED = "ENUMERATION_DETECTED"  # List markers found
    MULTIPLE_FACTS = "MULTIPLE_FACTS"  # Multiple facts in answer
    MULTI_SUBQUESTION = "MULTI_SUBQUESTION"  # Multiple questions in prompt

    # Text coherence issues (added for quality pipeline v2)
    MALFORMED_QUESTION = "MALFORMED_QUESTION"  # Truncated or garbled question text
    INCOHERENT_TEXT = "INCOHERENT_TEXT"  # Repeated punctuation, missing words
    TOO_SHORT = "TOO_SHORT"  # Content too brief to be meaningful
    GENERIC_QUESTION = "GENERIC_QUESTION"  # Vague "what is This?" style questions


class QualityGrade(str, Enum):
    """Letter grades based on quality score."""

    A = "A"  # 90-100: Excellent, no action needed
    B = "B"  # 75-89: Good, no action needed
    C = "C"  # 60-74: Acceptable, spot-check sampling
    D = "D"  # 40-59: Poor, needs rewrite
    F = "F"  # 0-39: Fail, block from review queue


@dataclass
class QualityReport:
    """Quality analysis report for a learning atom."""

    score: float  # 0-100 composite score
    grade: QualityGrade  # Letter grade
    issues: list[QualityIssue] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)

    # Computed metrics
    front_word_count: int = 0
    back_word_count: int = 0
    front_char_count: int = 0
    back_char_count: int = 0
    code_line_count: int = 0

    # Flags
    is_atomic: bool = True
    is_verbose: bool = False
    needs_split: bool = False
    needs_rewrite: bool = False

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "score": self.score,
            "grade": self.grade.value,
            "issues": [issue.value for issue in self.issues],
            "recommendations": self.recommendations,
            "front_word_count": self.front_word_count,
            "back_word_count": self.back_word_count,
            "front_char_count": self.front_char_count,
            "back_char_count": self.back_char_count,
            "code_line_count": self.code_line_count,
            "is_atomic": self.is_atomic,
            "is_verbose": self.is_verbose,
            "needs_split": self.needs_split,
            "needs_rewrite": self.needs_rewrite,
        }


# Detection patterns
LIST_PREFIXES = ("-", "*", "+", "•", "◦", "▪")
NUMBERED_PATTERN = re.compile(r"^\s*\d+[\.\)]\s+")
LETTER_PATTERN = re.compile(r"^\s*[a-zA-Z][\.\)]\s+")
CAUSAL_MARKERS = ("because", "due to", "therefore", "since", "hence", "as a result")
CODE_FENCE_PATTERN = re.compile(r"```[\w]*\n[\s\S]*?```")
CODE_BLOCK_PATTERN = re.compile(r"<code>[\s\S]*?</code>")
INLINE_CODE_PATTERN = re.compile(r"`[^`]+`")

# Text coherence patterns (v2 - detect malformed/garbage text)
MALFORMED_QUESTION_PATTERNS = [
    re.compile(r"what\s+\w+\s+The\s+", re.IGNORECASE),  # "what concept The concept"
    re.compile(r"what\s+is\s+This\b", re.IGNORECASE),  # "what is This" (vague)
    re.compile(r"what\s+is\s+Note:\?", re.IGNORECASE),  # "what is Note:?"
    re.compile(r"what\s+is\s+Step\s+\d", re.IGNORECASE),  # "what is Step 4.?"
    re.compile(r"what\s+is\s+Example", re.IGNORECASE),  # "what is Example:?"
    re.compile(r"what\s+is\s+Examples", re.IGNORECASE),  # "what is Examples:?"
    re.compile(r"In\s+\w+,\s+what\s+is\s+This\b", re.IGNORECASE),  # "In X, what is This"
    re.compile(
        r"In\s+networking,\s+what\s+\w+\s+The\s+", re.IGNORECASE
    ),  # "In networking, what internet The internet"
    re.compile(
        r"what\s+networking\s+term\s+describes:\s*are\b", re.IGNORECASE
    ),  # "describes: are a type"
    re.compile(r"what\s+type\s+This\s+type", re.IGNORECASE),  # "what type This type of"
    re.compile(r"what\s+the\s+However", re.IGNORECASE),  # "what the However, the term..."
    re.compile(r"what\s+\w+\s+Some\s+", re.IGNORECASE),  # "what hosts Some hosts"
    re.compile(r"what\s+\w+\s+However", re.IGNORECASE),  # "what X However"
    re.compile(
        r"networking\s+term\s+describes:\s*[A-Z][a-z]+\s+layer", re.IGNORECASE
    ),  # "describes: Application layer" (just OSI layer name)
    re.compile(r"what\s+\w+\s+If\s+", re.IGNORECASE),  # "what one If one path fails"
    re.compile(
        r"In\s+networking,\s+what\s+\w+\s+If\s+", re.IGNORECASE
    ),  # "In networking, what X If"
]
INCOHERENT_PATTERNS = [
    re.compile(r"[,]{2,}"),  # Repeated commas
    re.compile(r"[.]{3,}[^.]"),  # Multiple dots (not ellipsis)
    re.compile(r"\?\s*\?"),  # Double question marks
    re.compile(r"^\s*:\s*$"),  # Just a colon
    re.compile(r"^\s*\*\*\s*\*\*\s*$"),  # Empty bold markers
]
GENERIC_QUESTION_PATTERNS = [
    re.compile(r"^What\s+is\s+\w+\?\s*$"),  # "What is X?" (too simple, needs context)
    re.compile(r"^What\s+is\s+This\?\s*$", re.IGNORECASE),  # "What is This?"
]


class CardQualityAnalyzer:
    """
    Analyzes learning atoms (flashcards, quiz questions) for quality issues
    based on evidence-based thresholds from learning science research.
    """

    def __init__(self, version: str = "1.0.0"):
        """
        Initialize the analyzer.

        Args:
            version: Version string for tracking which analyzer ran on each card.
        """
        self.version = version

    def analyze(
        self,
        front_content: str,
        back_content: str | None = None,
        atom_type: str = "flashcard",
    ) -> QualityReport:
        """
        Analyze a learning atom and return a quality report.

        Args:
            front_content: The question/prompt content.
            back_content: The answer/solution content (optional for essays/projects).
            atom_type: Type of learning atom (flashcard, quiz_question, essay, etc.)

        Returns:
            QualityReport with score, grade, issues, and recommendations.
        """
        front = (front_content or "").strip()
        back = (back_content or "").strip()

        issues: list[QualityIssue] = []
        recommendations: list[str] = []

        # Calculate metrics
        front_word_count = self._count_words(front)
        back_word_count = self._count_words(back)
        front_char_count = len(front)
        back_char_count = len(back)
        code_line_count = self._count_code_lines(back)

        # ============================================================
        # Front content checks
        # ============================================================
        if front_word_count > FRONT_WORDS_MAX:
            issues.append(QualityIssue.FRONT_TOO_LONG)
            recommendations.append(
                f"Front has {front_word_count} words (max: {FRONT_WORDS_MAX}). "
                "Consider simplifying the question."
            )
        elif front_word_count > FRONT_WORDS_OPTIMAL:
            issues.append(QualityIssue.FRONT_VERBOSE)
            recommendations.append(
                f"Front has {front_word_count} words (optimal: ≤{FRONT_WORDS_OPTIMAL}). "
                "Consider making it more concise."
            )

        if front_char_count > FRONT_CHARS_MAX:
            issues.append(QualityIssue.FRONT_CHARS_EXCEEDED)
            recommendations.append(
                f"Front has {front_char_count} chars (max: {FRONT_CHARS_MAX}). "
                "Reduce visual complexity."
            )

        # ============================================================
        # Back content checks
        # ============================================================
        if back:
            if back_word_count > BACK_WORDS_MAX:
                issues.append(QualityIssue.BACK_TOO_LONG)
                recommendations.append(
                    f"Back has {back_word_count} words (max: {BACK_WORDS_MAX}). "
                    "Consider splitting into multiple atomic cards."
                )
            elif back_word_count > BACK_WORDS_OPTIMAL:
                issues.append(QualityIssue.BACK_VERBOSE)
                recommendations.append(
                    f"Back has {back_word_count} words (optimal: ≤{BACK_WORDS_OPTIMAL}). "
                    "Consider making it more concise."
                )

            if back_char_count > BACK_CHARS_MAX:
                issues.append(QualityIssue.BACK_CHARS_EXCEEDED)
                recommendations.append(
                    f"Back has {back_char_count} chars (max: {BACK_CHARS_MAX}). "
                    "Reduce answer complexity."
                )

            # Code-specific checks
            if code_line_count > 0:
                if code_line_count > CODE_LINES_MAX:
                    issues.append(QualityIssue.CODE_TOO_LONG)
                    recommendations.append(
                        f"Code has {code_line_count} lines (max: {CODE_LINES_MAX}). "
                        "Focus on the key snippet only."
                    )
                elif code_line_count > CODE_LINES_OPTIMAL:
                    issues.append(QualityIssue.CODE_VERBOSE)
                    recommendations.append(
                        f"Code has {code_line_count} lines (optimal: ≤{CODE_LINES_OPTIMAL}). "
                        "Consider trimming to essential lines."
                    )

            # Atomicity checks
            if self._contains_enumeration(back):
                issues.append(QualityIssue.ENUMERATION_DETECTED)
                recommendations.append(
                    "Enumeration detected in answer. "
                    "Consider splitting into separate cards for each item."
                )

            if self._count_facts(back) > 1:
                issues.append(QualityIssue.MULTIPLE_FACTS)
                recommendations.append(
                    "Multiple facts detected in answer. "
                    "One atomic fact per card is optimal for retrieval."
                )

        # Multi-question check
        if self._detect_multi_subquestion(front):
            issues.append(QualityIssue.MULTI_SUBQUESTION)
            recommendations.append(
                "Multiple sub-questions detected in prompt. Consider splitting into separate cards."
            )

        # ============================================================
        # Text coherence checks (v2 - catch malformed/garbage)
        # ============================================================
        if self._detect_malformed_question(front):
            issues.append(QualityIssue.MALFORMED_QUESTION)
            recommendations.append(
                "Question appears malformed or truncated. Regenerate from source content."
            )

        if self._detect_incoherent_text(front) or self._detect_incoherent_text(back):
            issues.append(QualityIssue.INCOHERENT_TEXT)
            recommendations.append(
                "Text contains incoherent patterns (repeated punctuation, broken structure). "
                "Review and clean source content."
            )

        if self._detect_too_short(front, back):
            issues.append(QualityIssue.TOO_SHORT)
            recommendations.append(
                "Content too brief to be meaningful for learning. Add more context or detail."
            )

        if self._detect_generic_question(front):
            issues.append(QualityIssue.GENERIC_QUESTION)
            recommendations.append(
                "Question is too generic/vague. Add context about what aspect is being asked."
            )

        # ============================================================
        # Calculate score and grade
        # ============================================================
        score = self._calculate_score(issues)
        grade = self._score_to_grade(score)

        # Determine flags
        is_atomic = (
            QualityIssue.ENUMERATION_DETECTED not in issues
            and QualityIssue.MULTIPLE_FACTS not in issues
        )
        is_verbose = QualityIssue.BACK_VERBOSE in issues or QualityIssue.BACK_TOO_LONG in issues
        needs_split = (
            QualityIssue.ENUMERATION_DETECTED in issues
            or QualityIssue.MULTIPLE_FACTS in issues
            or QualityIssue.MULTI_SUBQUESTION in issues
        )
        needs_rewrite = grade in (QualityGrade.D, QualityGrade.F)

        return QualityReport(
            score=score,
            grade=grade,
            issues=issues,
            recommendations=recommendations,
            front_word_count=front_word_count,
            back_word_count=back_word_count,
            front_char_count=front_char_count,
            back_char_count=back_char_count,
            code_line_count=code_line_count,
            is_atomic=is_atomic,
            is_verbose=is_verbose,
            needs_split=needs_split,
            needs_rewrite=needs_rewrite,
        )

    def _count_words(self, text: str) -> int:
        """Count words in text, excluding code blocks."""
        # Remove code blocks for word counting
        text_without_code = CODE_FENCE_PATTERN.sub("", text)
        text_without_code = CODE_BLOCK_PATTERN.sub("", text_without_code)
        text_without_code = INLINE_CODE_PATTERN.sub("", text_without_code)

        return len([token for token in text_without_code.strip().split() if token])

    def _count_code_lines(self, text: str) -> int:
        """Count lines of code in fenced code blocks."""
        total_lines = 0

        # Count fenced code blocks (```...```)
        for match in CODE_FENCE_PATTERN.finditer(text):
            code_content = match.group()
            # Remove the fence markers and count non-empty lines
            lines = code_content.strip().split("\n")[1:-1]  # Skip ``` lines
            total_lines += len([line for line in lines if line.strip()])

        # Count <code>...</code> blocks
        for match in CODE_BLOCK_PATTERN.finditer(text):
            code_content = match.group()
            lines = code_content.strip().split("\n")
            total_lines += len([line for line in lines if line.strip()])

        return total_lines

    def _contains_enumeration(self, text: str) -> bool:
        """Detect if text contains list markers (enumeration)."""
        if not text.strip():
            return False

        lines = [line.strip() for line in text.splitlines() if line.strip()]
        list_line_count = 0

        for line in lines:
            # Check bullet markers
            if (
                any(line.startswith(prefix) for prefix in LIST_PREFIXES)
                or NUMBERED_PATTERN.match(line)
                or LETTER_PATTERN.match(line)
            ):
                list_line_count += 1

        # If 2+ lines look like list items, it's an enumeration
        return list_line_count >= 2

    def _count_facts(self, text: str) -> int:
        """
        Estimate number of facts in text.

        Heuristic: Count sentences and causal markers.
        Multiple sentences or causal chains suggest multiple facts.
        """
        if not text.strip():
            return 0

        # Count sentence-ending punctuation
        sentences = len(re.findall(r"[.!?]+", text))

        # Count causal markers (indicates explanation chains)
        lower_text = text.lower()
        causal_count = sum(lower_text.count(marker) for marker in CAUSAL_MARKERS)

        # Heuristic: If >1 sentence or multiple causal markers, likely multiple facts
        if sentences > 1 or causal_count > 1:
            return max(sentences, causal_count + 1)

        return 1

    def _detect_multi_subquestion(self, text: str) -> bool:
        """Detect if question contains multiple sub-questions."""
        # Count question marks (multiple indicates sub-questions)
        question_marks = text.count("?")
        if question_marks > 1:
            return True

        # Check for "and" patterns suggesting compound questions
        lower = text.lower()
        compound_patterns = [
            " and what ",
            " and how ",
            " and why ",
            " and when ",
            " and where ",
            ", and ",
        ]
        return bool(any(pattern in lower for pattern in compound_patterns))

    def _detect_malformed_question(self, text: str) -> bool:
        """Detect malformed or truncated question text."""
        return any(pattern.search(text) for pattern in MALFORMED_QUESTION_PATTERNS)

    def _detect_incoherent_text(self, text: str) -> bool:
        """Detect incoherent text patterns (repeated punctuation, etc.)."""
        return any(pattern.search(text) for pattern in INCOHERENT_PATTERNS)

    def _detect_too_short(self, front: str, back: str) -> bool:
        """Detect if content is too brief to be meaningful."""
        # Front should be at least 15 characters
        if len(front.strip()) < 15:
            return True
        # Back should be at least 3 characters
        return len(back.strip()) < 3

    def _detect_generic_question(self, text: str) -> bool:
        """Detect overly generic/vague questions."""
        return any(pattern.search(text) for pattern in GENERIC_QUESTION_PATTERNS)

    def _calculate_score(self, issues: list[QualityIssue]) -> float:
        """Calculate quality score (0-100) based on issues detected."""
        score = 100.0

        for issue in issues:
            if issue == QualityIssue.FRONT_TOO_LONG:
                score -= PENALTY_FRONT_TOO_LONG
            elif issue == QualityIssue.FRONT_VERBOSE:
                score -= PENALTY_FRONT_VERBOSE
            elif issue == QualityIssue.BACK_TOO_LONG:
                score -= PENALTY_BACK_TOO_LONG
            elif issue == QualityIssue.BACK_VERBOSE:
                score -= PENALTY_BACK_VERBOSE
            elif issue == QualityIssue.FRONT_CHARS_EXCEEDED:
                score -= PENALTY_FRONT_CHARS
            elif issue == QualityIssue.BACK_CHARS_EXCEEDED:
                score -= PENALTY_BACK_CHARS
            elif issue == QualityIssue.CODE_TOO_LONG:
                score -= PENALTY_CODE_TOO_LONG
            elif issue == QualityIssue.CODE_VERBOSE:
                score -= PENALTY_CODE_VERBOSE
            elif issue == QualityIssue.ENUMERATION_DETECTED:
                score -= PENALTY_ENUMERATION
            elif issue == QualityIssue.MULTIPLE_FACTS:
                score -= PENALTY_MULTIPLE_FACTS
            elif issue == QualityIssue.MULTI_SUBQUESTION:
                score -= PENALTY_ENUMERATION  # Same penalty as enumeration
            # Text coherence issues (v2)
            elif issue == QualityIssue.MALFORMED_QUESTION:
                score -= PENALTY_MALFORMED_QUESTION
            elif issue == QualityIssue.INCOHERENT_TEXT:
                score -= PENALTY_INCOHERENT_TEXT
            elif issue == QualityIssue.TOO_SHORT:
                score -= PENALTY_TOO_SHORT
            elif issue == QualityIssue.GENERIC_QUESTION:
                score -= PENALTY_GENERIC_QUESTION

        return max(0.0, score)

    def _score_to_grade(self, score: float) -> QualityGrade:
        """Convert numeric score to letter grade."""
        if score >= GRADE_A_MIN:
            return QualityGrade.A
        elif score >= GRADE_B_MIN:
            return QualityGrade.B
        elif score >= GRADE_C_MIN:
            return QualityGrade.C
        elif score >= GRADE_D_MIN:
            return QualityGrade.D
        else:
            return QualityGrade.F
