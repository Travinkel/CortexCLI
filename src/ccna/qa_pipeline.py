"""
CCNA Quality Assurance Pipeline.

Multi-pass quality checking for generated learning atoms using existing
CardQualityAnalyzer and QuizQuestionAnalyzer with CCNA-specific validation.

Quality Grades:
- A (90-100): Atomic, clear, accurate, optimal length
- B (75-89): Minor issues, slightly verbose
- C (60-74): Acceptable but improvable
- D (40-59): Significant issues, needs revision
- F (<40): Replace entirely (hallucinated, multi-fact, unclear)
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from loguru import logger

from config import get_settings
from src.ccna.atomizer_service import AtomType, GeneratedAtom, KnowledgeType
from src.ccna.content_parser import Section
from src.content.cleaning.atomicity import CardQualityAnalyzer
from src.quiz.quiz_quality_analyzer import (
    QuestionType,
    QuizQuestionAnalyzer,
)


@dataclass
class AccuracyResult:
    """Result of accuracy check against source content."""

    is_accurate: bool
    confidence: float  # 0-1
    issues: list[str] = field(default_factory=list)
    matched_terms: list[str] = field(default_factory=list)
    unmatched_terms: list[str] = field(default_factory=list)


@dataclass
class AtomicityResult:
    """Result of atomicity check."""

    is_atomic: bool
    fact_count: int
    issues: list[str] = field(default_factory=list)
    multi_fact_indicators: list[str] = field(default_factory=list)


@dataclass
class LengthResult:
    """Result of length check."""

    is_optimal: bool
    is_within_limits: bool
    question_words: int
    answer_words: int
    issues: list[str] = field(default_factory=list)


@dataclass
class ClarityResult:
    """Result of clarity check."""

    is_clear: bool
    score: float  # 0-1
    issues: list[str] = field(default_factory=list)


@dataclass
class QAResult:
    """Complete QA result for an atom."""

    atom: GeneratedAtom
    quality_score: float  # 0-100
    quality_grade: str  # A-F
    is_approved: bool  # Meets minimum grade threshold
    is_atomic: bool
    is_accurate: bool
    is_clear: bool
    needs_regeneration: bool
    needs_review: bool
    issues: list[str] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)

    # Detailed results
    atomicity_result: AtomicityResult | None = None
    accuracy_result: AccuracyResult | None = None
    length_result: LengthResult | None = None
    clarity_result: ClarityResult | None = None


@dataclass
class QAReport:
    """Report from batch QA processing."""

    total_processed: int
    passed: int
    flagged: int
    rejected: int
    grade_distribution: dict[str, int]
    results: list[QAResult]
    errors: list[str] = field(default_factory=list)


class QAPipeline:
    """
    Quality assurance pipeline for generated CCNA learning atoms.

    Combines existing quality analyzers with CCNA-specific validation
    including source accuracy verification.
    """

    # Multi-fact indicators
    MULTI_FACT_PATTERNS = [
        r"\band\s+also\b",
        r"\badditionally\b",
        r"\bfurthermore\b",
        r"\bmoreover\b",
        r"\bin addition\b",
        r";\s*\w",  # Semicolon followed by word (compound sentence)
    ]

    # Networking term patterns for CCNA
    NETWORKING_TERMS = [
        r"\bip\s+address\b",
        r"\brouter\b",
        r"\bswitch\b",
        r"\bvlan\b",
        r"\bsubnet\b",
        r"\bprotocol\b",
        r"\bethernet\b",
        r"\bpacket\b",
        r"\bframe\b",
        r"\bmac\s+address\b",
        r"\bosi\b",
        r"\blayer\s+\d\b",
        r"\btcp\b",
        r"\budp\b",
        r"\bport\b",
        r"\binterface\b",
        r"\bbandwidth\b",
        r"\bgateway\b",
        r"\bdns\b",
        r"\bdhcp\b",
        r"\bospf\b",
        r"\beigr?p\b",
        r"\bbgp\b",
        r"\bacl\b",
        r"\bnat\b",
        r"\bstp\b",
        r"\bcisco\b",
    ]

    def __init__(self, min_grade: str = "B"):
        """
        Initialize QA pipeline.

        Args:
            min_grade: Minimum grade to pass QA (A, B, C, D)
        """
        settings = get_settings()
        self.min_grade = min_grade or settings.ccna_min_quality_grade

        # Initialize analyzers
        self.card_analyzer = CardQualityAnalyzer()
        self.quiz_analyzer = QuizQuestionAnalyzer()

        # Grade thresholds
        self.grade_thresholds = {
            "A": 90,
            "B": 75,
            "C": 60,
            "D": 40,
            "F": 0,
        }

        # Compile patterns
        self.multi_fact_patterns = [re.compile(p, re.IGNORECASE) for p in self.MULTI_FACT_PATTERNS]
        self.networking_patterns = [re.compile(p, re.IGNORECASE) for p in self.NETWORKING_TERMS]

    def grade_atom(
        self,
        atom: GeneratedAtom,
        source_section: Section | None = None,
    ) -> QAResult:
        """
        Grade a single atom for quality.

        Args:
            atom: Generated atom to grade
            source_section: Original section for accuracy check

        Returns:
            QAResult with score, grade, and issues
        """
        issues = []
        recommendations = []

        # 1. Check atomicity
        atomicity_result = self.check_atomicity(atom)
        if not atomicity_result.is_atomic:
            issues.extend(atomicity_result.issues)

        # 2. Check length
        length_result = self.check_length(atom)
        if not length_result.is_optimal:
            issues.extend(length_result.issues)

        # 3. Check accuracy against source
        accuracy_result = None
        if source_section:
            accuracy_result = self.check_accuracy(atom, source_section)
            if not accuracy_result.is_accurate:
                issues.extend(accuracy_result.issues)

        # 4. Check clarity
        clarity_result = self.check_clarity(atom)
        if not clarity_result.is_clear:
            issues.extend(clarity_result.issues)

        # 5. Use existing quality analyzer based on type
        if atom.atom_type == AtomType.FLASHCARD or atom.atom_type == AtomType.CLOZE:
            analyzer_report = self.card_analyzer.analyze(atom.front, atom.back)
            base_score = analyzer_report.score
            issues.extend([i.value for i in analyzer_report.issues])
            recommendations.extend(analyzer_report.recommendations)
        else:
            # Use quiz analyzer for other types
            question_type = self._map_atom_type_to_question_type(atom.atom_type)
            analyzer_report = self.quiz_analyzer.analyze(
                atom.front,
                atom.back,
                question_type,
                atom.content_json,
            )
            base_score = analyzer_report.score
            issues.extend([i.message for i in analyzer_report.issues])
            recommendations.extend(analyzer_report.recommendations)

        # 6. Calculate final score with CCNA-specific adjustments
        score = self._calculate_final_score(
            base_score,
            atomicity_result,
            accuracy_result,
            length_result,
            clarity_result,
        )

        # 7. Determine grade
        grade = self._score_to_grade(score)

        # 8. Determine if approved
        min_score = self.grade_thresholds.get(self.min_grade, 75)
        is_approved = score >= min_score

        # 9. Determine actions needed
        needs_regeneration = grade in ("D", "F")
        needs_review = grade == "C"

        # Generate recommendations based on issues
        if not atomicity_result.is_atomic:
            recommendations.append("Split into multiple atomic cards")
        if accuracy_result and not accuracy_result.is_accurate:
            recommendations.append("Verify content against source material")
        if not length_result.is_optimal:
            recommendations.append("Adjust length to optimal range")
        if not clarity_result.is_clear:
            recommendations.append("Improve question/answer clarity")

        return QAResult(
            atom=atom,
            quality_score=score,
            quality_grade=grade,
            is_approved=is_approved,
            is_atomic=atomicity_result.is_atomic,
            is_accurate=accuracy_result.is_accurate if accuracy_result else True,
            is_clear=clarity_result.is_clear,
            needs_regeneration=needs_regeneration,
            needs_review=needs_review,
            issues=list(set(issues)),  # Remove duplicates
            recommendations=list(set(recommendations)),
            atomicity_result=atomicity_result,
            accuracy_result=accuracy_result,
            length_result=length_result,
            clarity_result=clarity_result,
        )

    def check_atomicity(self, atom: GeneratedAtom) -> AtomicityResult:
        """
        Verify single-fact principle.

        Checks for indicators of multiple facts:
        - "and", "also", "additionally" patterns
        - Multiple sentences in answer
        - Enumeration markers
        """
        issues = []
        indicators = []

        text = f"{atom.front} {atom.back}".lower()

        # Check for multi-fact patterns
        for pattern in self.multi_fact_patterns:
            if pattern.search(text):
                indicators.append(pattern.pattern)

        # Count sentences in answer
        answer_sentences = len(re.split(r"[.!?]+", atom.back.strip()))
        if answer_sentences > 2:
            issues.append(f"Answer has {answer_sentences} sentences (optimal: 1-2)")
            indicators.append(f"{answer_sentences} sentences")

        # Check for enumeration
        if re.search(r"^\s*[-•*]\s+", atom.back, re.MULTILINE):
            issues.append("Bullet points detected in answer")
            indicators.append("bullet points")

        if re.search(r"^\s*\d+[.)]\s+", atom.back, re.MULTILINE):
            issues.append("Numbered list detected in answer")
            indicators.append("numbered list")

        # Estimate fact count
        fact_count = 1
        if indicators:
            fact_count = max(2, len(indicators))

        is_atomic = len(indicators) == 0

        if not is_atomic:
            issues.append("Multiple facts detected - consider splitting")

        return AtomicityResult(
            is_atomic=is_atomic,
            fact_count=fact_count,
            issues=issues,
            multi_fact_indicators=indicators,
        )

    def check_accuracy(
        self,
        atom: GeneratedAtom,
        source: Section,
    ) -> AccuracyResult:
        """
        Verify content matches source (no hallucination).

        Checks if key terms in the atom appear in the source content.
        """
        issues = []
        matched = []
        unmatched = []

        source_text = source.raw_content.lower()

        # Extract key terms from atom
        atom_text = f"{atom.front} {atom.back}".lower()

        # Find networking terms in atom
        for pattern in self.networking_patterns:
            matches = pattern.findall(atom_text)
            for match in matches:
                term = match.strip()
                if term in source_text:
                    matched.append(term)
                else:
                    # Check if it's a minor variation
                    if not any(term in source_text.replace("-", " ") for _ in [1]):
                        unmatched.append(term)

        # Check for specific values (IPs, port numbers, etc.)
        ip_pattern = re.compile(r"\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}")
        for ip in ip_pattern.findall(atom_text):
            if ip in source_text:
                matched.append(ip)
            else:
                unmatched.append(ip)

        # Calculate confidence
        total_terms = len(matched) + len(unmatched)
        if total_terms == 0:
            confidence = 1.0
        else:
            confidence = len(matched) / total_terms

        # Determine accuracy
        is_accurate = confidence >= 0.7  # 70% of terms must match

        if not is_accurate:
            issues.append(
                f"Content accuracy: {confidence:.0%} terms match source "
                f"(unmatched: {', '.join(unmatched[:3])})"
            )

        return AccuracyResult(
            is_accurate=is_accurate,
            confidence=confidence,
            issues=issues,
            matched_terms=matched,
            unmatched_terms=unmatched,
        )

    def check_length(self, atom: GeneratedAtom) -> LengthResult:
        """Verify optimal word counts."""
        settings = get_settings()
        issues = []

        # Count words
        question_words = len(atom.front.split())
        answer_words = len(atom.back.split())

        # Get thresholds from config
        q_min = settings.ccna_question_optimal_min
        q_max = settings.ccna_question_optimal_max

        # Answer threshold depends on knowledge type
        if atom.knowledge_type == KnowledgeType.FACTUAL:
            a_max = settings.ccna_answer_optimal_factual
        else:
            a_max = settings.ccna_answer_optimal_conceptual

        # Check question length
        is_optimal = True
        is_within_limits = True

        if question_words < q_min:
            issues.append(f"Question too short: {question_words} words (min: {q_min})")
            is_optimal = False
        elif question_words > q_max:
            issues.append(f"Question verbose: {question_words} words (optimal: {q_min}-{q_max})")
            is_optimal = False
            if question_words > 25:
                issues.append(f"Question exceeds max: {question_words} words (max: 25)")
                is_within_limits = False

        # Check answer length
        if answer_words > a_max * 2:  # Hard limit
            issues.append(f"Answer too long: {answer_words} words (max: {a_max * 2})")
            is_within_limits = False
            is_optimal = False
        elif answer_words > a_max:
            issues.append(f"Answer verbose: {answer_words} words (optimal: ≤{a_max})")
            is_optimal = False

        return LengthResult(
            is_optimal=is_optimal,
            is_within_limits=is_within_limits,
            question_words=question_words,
            answer_words=answer_words,
            issues=issues,
        )

    def check_clarity(self, atom: GeneratedAtom) -> ClarityResult:
        """Check question clarity and answer precision."""
        issues = []
        score = 1.0

        # Check for vague question words
        vague_patterns = [
            r"\bwhat\s+is\s+\w+\s*\?$",  # "What is X?" without context
            r"\bdefine\s+\w+\s*\?$",  # "Define X?" without context
        ]

        for pattern in vague_patterns:
            if re.search(pattern, atom.front, re.IGNORECASE):
                issues.append("Question may be too vague - add context")
                score -= 0.2

        # Check for ambiguous answer
        ambiguous_patterns = [
            r"\bit depends\b",
            r"\bvarious\b",
            r"\bmany\s+things\b",
            r"\bsometimes\b",
        ]

        for pattern in ambiguous_patterns:
            if re.search(pattern, atom.back, re.IGNORECASE):
                issues.append("Answer may be ambiguous")
                score -= 0.2

        # Check for missing question mark in question
        if not atom.front.strip().endswith("?") and atom.atom_type == AtomType.FLASHCARD:
            if not any(
                atom.front.lower().startswith(w)
                for w in ["what", "how", "why", "when", "where", "which"]
            ):
                issues.append("Consider phrasing as a question")
                score -= 0.1

        # Check for empty or very short content
        if len(atom.front.strip()) < 10:
            issues.append("Question too short")
            score -= 0.3

        if len(atom.back.strip()) < 3:
            issues.append("Answer too short")
            score -= 0.3

        is_clear = score >= 0.6

        return ClarityResult(
            is_clear=is_clear,
            score=max(0, score),
            issues=issues,
        )

    def _map_atom_type_to_question_type(self, atom_type: AtomType) -> QuestionType:
        """Map AtomType to QuestionType for quiz analyzer."""
        mapping = {
            AtomType.MCQ: QuestionType.MCQ,
            AtomType.TRUE_FALSE: QuestionType.TRUE_FALSE,
            AtomType.MATCHING: QuestionType.MATCHING,
            AtomType.RANKING: QuestionType.RANKING,
            AtomType.PARSONS: QuestionType.PARSONS,
            AtomType.COMPARE: QuestionType.COMPARE,
            AtomType.SHORT_ANSWER: QuestionType.SHORT_ANSWER,
            AtomType.CLOZE: QuestionType.CLOZE,
        }
        return mapping.get(atom_type, QuestionType.SHORT_ANSWER)

    def _calculate_final_score(
        self,
        base_score: float,
        atomicity: AtomicityResult,
        accuracy: AccuracyResult | None,
        length: LengthResult,
        clarity: ClarityResult,
    ) -> float:
        """Calculate final quality score with all factors."""
        score = base_score

        # Atomicity penalty (major)
        if not atomicity.is_atomic:
            penalty = min(30, atomicity.fact_count * 10)
            score -= penalty

        # Accuracy penalty (major)
        if accuracy and not accuracy.is_accurate:
            score -= 30 * (1 - accuracy.confidence)

        # Length penalty (minor)
        if not length.is_optimal:
            score -= 10
        if not length.is_within_limits:
            score -= 20

        # Clarity penalty (minor)
        if not clarity.is_clear:
            score -= 10 * (1 - clarity.score)

        return max(0, min(100, score))

    def _score_to_grade(self, score: float) -> str:
        """Convert numeric score to letter grade."""
        if score >= 90:
            return "A"
        elif score >= 75:
            return "B"
        elif score >= 60:
            return "C"
        elif score >= 40:
            return "D"
        return "F"

    def batch_qa(
        self,
        atoms: list[GeneratedAtom],
        source_section: Section | None = None,
    ) -> QAReport:
        """
        Process a batch of atoms and return a quality report.

        Args:
            atoms: List of atoms to grade
            source_section: Source section for accuracy checking

        Returns:
            QAReport with statistics and results
        """
        results = []
        errors = []
        grade_distribution = {"A": 0, "B": 0, "C": 0, "D": 0, "F": 0}

        for atom in atoms:
            try:
                result = self.grade_atom(atom, source_section)
                results.append(result)
                grade_distribution[result.quality_grade] += 1

                # Update atom with quality info
                atom.quality_score = result.quality_score
                atom.quality_grade = result.quality_grade

            except Exception as e:
                error_msg = f"Error grading atom {atom.card_id}: {e}"
                logger.error(error_msg)
                errors.append(error_msg)

        # Calculate statistics
        passed = grade_distribution["A"] + grade_distribution["B"]
        flagged = grade_distribution["C"]
        rejected = grade_distribution["D"] + grade_distribution["F"]

        return QAReport(
            total_processed=len(atoms),
            passed=passed,
            flagged=flagged,
            rejected=rejected,
            grade_distribution=grade_distribution,
            results=results,
            errors=errors,
        )
