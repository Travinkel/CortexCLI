"""
Enhanced Quality Validator for Learning Atoms.

Comprehensive validation for all 6 learning atom types:
- Flashcard (Anki)
- Cloze (Anki)
- MCQ (NSL)
- True/False (NSL)
- Parsons (NSL)
- Matching (NSL)

Key improvements over basic validator:
1. Sentence completion detection (catches truncated answers)
2. Tighter perplexity thresholds (catches garbled text earlier)
3. Type-specific validation rules
4. Negative example pattern matching
5. Source content validation
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional

from loguru import logger


class AtomType(str, Enum):
    """Supported atom types."""
    FLASHCARD = "flashcard"
    CLOZE = "cloze"
    MCQ = "mcq"
    TRUE_FALSE = "true_false"
    PARSONS = "parsons"
    MATCHING = "matching"


class ValidationSeverity(str, Enum):
    """Severity levels for validation issues."""
    ERROR = "error"      # Reject immediately
    WARNING = "warning"  # Flag for review
    INFO = "info"        # Log but pass


@dataclass
class ValidationIssue:
    """A single validation issue."""
    code: str
    severity: ValidationSeverity
    message: str
    field: str = "general"  # front, back, content_json, general


@dataclass
class EnhancedValidationResult:
    """Result of enhanced validation."""
    is_valid: bool
    can_be_fixed: bool = False  # Can be fixed by regeneration
    score: float = 100.0  # 0-100 quality score
    issues: list[ValidationIssue] = field(default_factory=list)

    # Detailed metrics
    perplexity: Optional[float] = None
    grammar_valid: Optional[bool] = None
    is_complete: bool = True  # No truncation
    is_coherent: bool = True  # Makes grammatical sense
    is_atomic: bool = True    # One fact per atom

    @property
    def has_errors(self) -> bool:
        return any(i.severity == ValidationSeverity.ERROR for i in self.issues)

    @property
    def has_warnings(self) -> bool:
        return any(i.severity == ValidationSeverity.WARNING for i in self.issues)

    def add_issue(
        self,
        code: str,
        severity: ValidationSeverity,
        message: str,
        field: str = "general",
        penalty: float = 0,
    ):
        """Add an issue and apply score penalty."""
        self.issues.append(ValidationIssue(code, severity, message, field))
        self.score = max(0, self.score - penalty)
        if severity == ValidationSeverity.ERROR:
            self.is_valid = False


# =============================================================================
# Pattern Definitions (Evidence-Based)
# =============================================================================

# Patterns that indicate malformed/garbled text (REJECT)
MALFORMED_PATTERNS = [
    # Garbled questions with sentence fragments
    (re.compile(r"what\s+\w+\s+The\s+\w+", re.IGNORECASE), "GARBLED_WHAT_THE", "Question contains 'what X The Y' garbled pattern"),
    (re.compile(r"what\s+\w+\s+However\b", re.IGNORECASE), "GARBLED_HOWEVER", "Question contains 'what X However' fragment"),
    (re.compile(r"what\s+\w+\s+If\s+", re.IGNORECASE), "GARBLED_IF", "Question contains 'what X If' fragment"),
    (re.compile(r"what\s+\w+\s+Some\s+", re.IGNORECASE), "GARBLED_SOME", "Question contains 'what X Some' fragment"),
    (re.compile(r"what\s+is\s+This\b(?!\s+called)", re.IGNORECASE), "VAGUE_THIS", "Question uses vague 'What is This'"),
    (re.compile(r"what\s+type\s+This\s+type", re.IGNORECASE), "GARBLED_TYPE", "Question contains 'what type This type' pattern"),

    # Questions about formatting elements
    (re.compile(r"what\s+is\s+Note:\s*\?", re.IGNORECASE), "FORMAT_NOTE", "Question about markdown Note: element"),
    (re.compile(r"what\s+is\s+Step\s+\d", re.IGNORECASE), "FORMAT_STEP", "Question about step number"),
    (re.compile(r"what\s+is\s+Example", re.IGNORECASE), "FORMAT_EXAMPLE", "Question about Example: element"),

    # Repeated words (sign of generation error)
    (re.compile(r"\b(\w{4,})\s+\1\b", re.IGNORECASE), "REPEATED_WORD", "Contains repeated word (generation error)"),
]

# Patterns that indicate truncated content (REJECT)
TRUNCATION_PATTERNS = [
    # Ends with article/preposition (mid-sentence truncation)
    (re.compile(r"\s+(a|an|the)\s*$", re.IGNORECASE), "TRUNCATED_ARTICLE", "Ends with article (truncated)"),
    (re.compile(r"\s+(of|to|for|with|by|at|in|on|from)\s*$", re.IGNORECASE), "TRUNCATED_PREPOSITION", "Ends with preposition (truncated)"),
    (re.compile(r"\s+(or|and|but|nor)\s*$", re.IGNORECASE), "TRUNCATED_CONJUNCTION", "Ends with conjunction (truncated)"),
    (re.compile(r"\s+(is|are|was|were|be|been|being)\s*$", re.IGNORECASE), "TRUNCATED_VERB", "Ends with linking verb (truncated)"),

    # Ends with comma or open punctuation
    (re.compile(r",\s*$"), "TRUNCATED_COMMA", "Ends with comma (truncated)"),
    (re.compile(r":\s*$"), "TRUNCATED_COLON", "Ends with colon (truncated)"),
    (re.compile(r"—\s*$"), "TRUNCATED_DASH", "Ends with dash (truncated)"),
]

# Patterns that indicate incoherent text (REJECT)
INCOHERENT_PATTERNS = [
    (re.compile(r",{2,}"), "DOUBLE_COMMA", "Multiple consecutive commas"),
    (re.compile(r"\?\s*\?"), "DOUBLE_QUESTION", "Multiple consecutive question marks"),
    (re.compile(r"\.{4,}"), "EXCESSIVE_DOTS", "Excessive dots"),
    (re.compile(r"\*\*\s*\*\*"), "EMPTY_BOLD", "Empty bold markers"),
    (re.compile(r"^\s*$"), "EMPTY_CONTENT", "Empty content"),
]

# Patterns that indicate quality issues (WARNING)
QUALITY_WARNING_PATTERNS = [
    # Bare definition questions (need context)
    (re.compile(r"^What\s+is\s+\w+\?\s*$"), "BARE_DEFINITION", "Simple 'What is X?' lacks context"),
    (re.compile(r"^Define\s+\w+\.?\s*$", re.IGNORECASE), "BARE_DEFINE", "Simple 'Define X' lacks context"),

    # Very short content
    (re.compile(r"^.{1,14}$"), "TOO_SHORT", "Content too short (<15 chars)"),

    # MCQ weak distractors
    (re.compile(r"all\s+of\s+the\s+above", re.IGNORECASE), "WEAK_DISTRACTOR_ALL", "'All of the above' is weak"),
    (re.compile(r"none\s+of\s+the\s+above", re.IGNORECASE), "WEAK_DISTRACTOR_NONE", "'None of the above' is weak"),
    (re.compile(r"both\s+[A-D]\s+and\s+[A-D]", re.IGNORECASE), "WEAK_DISTRACTOR_BOTH", "'Both X and Y' is weak"),
]


class EnhancedQualityValidator:
    """
    Comprehensive quality validator for all learning atom types.

    Implements multiple validation passes:
    1. Quick regex rejection (fast, catches obvious garbage)
    2. Perplexity scoring (catches incoherent text)
    3. Sentence completion check (catches truncation)
    4. Type-specific validation (MCQ options, Parsons blocks, etc.)
    5. Atomicity check (one fact per atom)
    """

    # Perplexity thresholds (tightened from original)
    PERPLEXITY_REJECT = 300.0   # Was 2000.0 - now catches more garbage
    PERPLEXITY_WARN = 100.0     # Was 500.0 - earlier warning
    PERPLEXITY_OPTIMAL = 50.0   # Good text typically under 50

    # Length thresholds
    QUESTION_WORDS_MIN = 5
    QUESTION_WORDS_OPTIMAL = 15
    QUESTION_WORDS_MAX = 25

    ANSWER_WORDS_MIN_FLASHCARD = 8   # Increased from original
    ANSWER_WORDS_OPTIMAL = 15
    ANSWER_WORDS_MAX = 30

    # Type-specific thresholds
    MCQ_OPTIONS_MIN = 3
    MCQ_OPTIONS_MAX = 6
    MATCHING_PAIRS_MIN = 3
    MATCHING_PAIRS_MAX = 6
    PARSONS_BLOCKS_MIN = 3
    PARSONS_BLOCKS_MAX = 10

    def __init__(
        self,
        use_perplexity: bool = True,
        use_grammar: bool = True,
        strict_mode: bool = False,
    ):
        """
        Initialize the enhanced validator.

        Args:
            use_perplexity: Enable perplexity scoring (requires transformers)
            use_grammar: Enable grammar validation (requires spaCy)
            strict_mode: Apply stricter thresholds
        """
        self.strict_mode = strict_mode

        # Initialize perplexity scorer
        self.perplexity_scorer = None
        if use_perplexity:
            try:
                from src.generation.quality_validator import PerplexityScorer
                self.perplexity_scorer = PerplexityScorer()
                if not self.perplexity_scorer.available:
                    self.perplexity_scorer = None
            except Exception as e:
                logger.warning(f"Perplexity scoring not available: {e}")

        # Initialize grammar validator
        self.grammar_validator = None
        if use_grammar:
            try:
                from src.generation.quality_validator import GrammarValidator
                self.grammar_validator = GrammarValidator()
                if not self.grammar_validator.available:
                    self.grammar_validator = None
            except Exception as e:
                logger.warning(f"Grammar validation not available: {e}")

    def validate(
        self,
        front: str,
        back: str,
        atom_type: str | AtomType,
        content_json: Optional[dict[str, Any]] = None,
        source_content: Optional[str] = None,
    ) -> EnhancedValidationResult:
        """
        Validate a learning atom comprehensively.

        Args:
            front: Question/prompt text
            back: Answer text
            atom_type: Type of atom (flashcard, mcq, etc.)
            content_json: Type-specific content (options, pairs, blocks)
            source_content: Original source for accuracy check

        Returns:
            EnhancedValidationResult with detailed issues and score
        """
        if isinstance(atom_type, str):
            try:
                atom_type = AtomType(atom_type)
            except ValueError:
                atom_type = AtomType.FLASHCARD

        result = EnhancedValidationResult(is_valid=True)
        front = (front or "").strip()
        back = (back or "").strip()

        # Pass 1: Quick regex rejection
        self._check_malformed_patterns(front, back, result)
        if result.has_errors:
            result.can_be_fixed = True
            return result

        # Pass 2: Truncation detection
        self._check_truncation(front, back, result)
        if result.has_errors:
            result.can_be_fixed = True
            return result

        # Pass 3: Incoherence detection
        self._check_incoherence(front, back, result)
        if result.has_errors:
            result.can_be_fixed = True
            return result

        # Pass 4: Length validation
        self._check_length(front, back, atom_type, result)

        # Pass 5: Perplexity check
        if self.perplexity_scorer:
            self._check_perplexity(front, result)

        # Pass 6: Grammar check
        if self.grammar_validator:
            self._check_grammar(front, result)

        # Pass 7: Type-specific validation
        self._check_type_specific(atom_type, front, back, content_json, result)

        # Pass 8: Quality warnings
        self._check_quality_warnings(front, back, result)

        # Pass 9: Atomicity check
        self._check_atomicity(back, result)

        # Pass 10: Source accuracy (if provided)
        if source_content:
            self._check_source_accuracy(front, back, source_content, result)

        return result

    def _check_malformed_patterns(
        self,
        front: str,
        back: str,
        result: EnhancedValidationResult,
    ):
        """Check for malformed/garbled text patterns."""
        combined = f"{front} ||| {back}"

        for pattern, code, message in MALFORMED_PATTERNS:
            if pattern.search(combined):
                result.add_issue(
                    code=code,
                    severity=ValidationSeverity.ERROR,
                    message=message,
                    field="front" if pattern.search(front) else "back",
                    penalty=50,
                )
                result.is_coherent = False

    def _check_truncation(
        self,
        front: str,
        back: str,
        result: EnhancedValidationResult,
    ):
        """Check for truncated content."""
        # Check back (answer) for truncation - most common
        for pattern, code, message in TRUNCATION_PATTERNS:
            if pattern.search(back):
                result.add_issue(
                    code=code,
                    severity=ValidationSeverity.ERROR,
                    message=message,
                    field="back",
                    penalty=40,
                )
                result.is_complete = False

        # Check if answer ends properly
        if back and len(back) > 10:
            # Should end with punctuation or complete word
            if not re.search(r"[.!?)\]\"']$", back):
                # Check if it ends mid-word
                last_word = back.split()[-1] if back.split() else ""
                if len(last_word) < 3 or last_word.islower():
                    result.add_issue(
                        code="INCOMPLETE_SENTENCE",
                        severity=ValidationSeverity.WARNING,
                        message="Answer may be incomplete (no ending punctuation)",
                        field="back",
                        penalty=15,
                    )
                    result.is_complete = False

    def _check_incoherence(
        self,
        front: str,
        back: str,
        result: EnhancedValidationResult,
    ):
        """Check for incoherent text patterns."""
        combined = f"{front} ||| {back}"

        for pattern, code, message in INCOHERENT_PATTERNS:
            if pattern.search(combined):
                result.add_issue(
                    code=code,
                    severity=ValidationSeverity.ERROR,
                    message=message,
                    penalty=50,
                )
                result.is_coherent = False

    def _check_length(
        self,
        front: str,
        back: str,
        atom_type: AtomType,
        result: EnhancedValidationResult,
    ):
        """Check content length requirements."""
        front_words = len(front.split())
        back_words = len(back.split())

        # Question length
        if front_words < self.QUESTION_WORDS_MIN:
            result.add_issue(
                code="QUESTION_TOO_SHORT",
                severity=ValidationSeverity.WARNING,
                message=f"Question has {front_words} words (min: {self.QUESTION_WORDS_MIN})",
                field="front",
                penalty=10,
            )
        elif front_words > self.QUESTION_WORDS_MAX:
            result.add_issue(
                code="QUESTION_TOO_LONG",
                severity=ValidationSeverity.WARNING,
                message=f"Question has {front_words} words (max: {self.QUESTION_WORDS_MAX})",
                field="front",
                penalty=15,
            )

        # Answer length (varies by type)
        if atom_type == AtomType.FLASHCARD:
            if back_words < self.ANSWER_WORDS_MIN_FLASHCARD:
                result.add_issue(
                    code="ANSWER_TOO_SHORT",
                    severity=ValidationSeverity.ERROR,
                    message=f"Flashcard answer has {back_words} words (min: {self.ANSWER_WORDS_MIN_FLASHCARD})",
                    field="back",
                    penalty=30,
                )
        elif atom_type not in [AtomType.MCQ, AtomType.TRUE_FALSE]:
            # Other types have minimum answer length too
            if back_words < 3:
                result.add_issue(
                    code="ANSWER_TOO_SHORT",
                    severity=ValidationSeverity.WARNING,
                    message=f"Answer has only {back_words} words",
                    field="back",
                    penalty=10,
                )

        if back_words > self.ANSWER_WORDS_MAX * 2:  # Hard limit
            result.add_issue(
                code="ANSWER_TOO_LONG",
                severity=ValidationSeverity.WARNING,
                message=f"Answer has {back_words} words (max: {self.ANSWER_WORDS_MAX * 2})",
                field="back",
                penalty=20,
            )

    def _check_perplexity(
        self,
        front: str,
        result: EnhancedValidationResult,
    ):
        """Check text perplexity (coherence)."""
        ppl = self.perplexity_scorer.calculate_perplexity(front)
        result.perplexity = ppl

        if ppl > self.PERPLEXITY_REJECT:
            result.add_issue(
                code="HIGH_PERPLEXITY",
                severity=ValidationSeverity.ERROR,
                message=f"Text perplexity {ppl:.0f} exceeds threshold {self.PERPLEXITY_REJECT:.0f}",
                field="front",
                penalty=50,
            )
            result.is_coherent = False
        elif ppl > self.PERPLEXITY_WARN:
            result.add_issue(
                code="ELEVATED_PERPLEXITY",
                severity=ValidationSeverity.WARNING,
                message=f"Text perplexity {ppl:.0f} above optimal {self.PERPLEXITY_WARN:.0f}",
                field="front",
                penalty=10,
            )

    def _check_grammar(
        self,
        front: str,
        result: EnhancedValidationResult,
    ):
        """Check grammatical structure."""
        is_valid, issues = self.grammar_validator.validate(front)
        result.grammar_valid = is_valid

        if not is_valid:
            for issue in issues:
                result.add_issue(
                    code="GRAMMAR_ISSUE",
                    severity=ValidationSeverity.WARNING,
                    message=issue,
                    field="front",
                    penalty=10,
                )

    def _check_type_specific(
        self,
        atom_type: AtomType,
        front: str,
        back: str,
        content_json: Optional[dict],
        result: EnhancedValidationResult,
    ):
        """Type-specific validation."""
        if atom_type == AtomType.MCQ:
            self._validate_mcq(content_json, result)
        elif atom_type == AtomType.TRUE_FALSE:
            self._validate_true_false(content_json, result)
        elif atom_type == AtomType.MATCHING:
            self._validate_matching(content_json, result)
        elif atom_type == AtomType.PARSONS:
            self._validate_parsons(content_json, result)
        elif atom_type == AtomType.CLOZE:
            self._validate_cloze(front, result)
        elif atom_type == AtomType.FLASHCARD:
            self._validate_flashcard(front, back, result)

    def _validate_mcq(self, content_json: Optional[dict], result: EnhancedValidationResult):
        """Validate MCQ structure."""
        if not content_json:
            result.add_issue(
                code="MCQ_NO_CONTENT",
                severity=ValidationSeverity.ERROR,
                message="MCQ requires content_json with options",
                penalty=50,
            )
            return

        options = content_json.get("options", [])
        correct_index = content_json.get("correct_index")

        if not options:
            result.add_issue(
                code="MCQ_NO_OPTIONS",
                severity=ValidationSeverity.ERROR,
                message="MCQ must have options array",
                penalty=50,
            )
            return

        if len(options) < self.MCQ_OPTIONS_MIN:
            result.add_issue(
                code="MCQ_FEW_OPTIONS",
                severity=ValidationSeverity.ERROR,
                message=f"MCQ has {len(options)} options (min: {self.MCQ_OPTIONS_MIN})",
                penalty=30,
            )
        elif len(options) > self.MCQ_OPTIONS_MAX:
            result.add_issue(
                code="MCQ_MANY_OPTIONS",
                severity=ValidationSeverity.WARNING,
                message=f"MCQ has {len(options)} options (max: {self.MCQ_OPTIONS_MAX})",
                penalty=15,
            )

        if correct_index is None:
            result.add_issue(
                code="MCQ_NO_CORRECT",
                severity=ValidationSeverity.ERROR,
                message="MCQ must have correct_index",
                penalty=50,
            )
        elif not (0 <= correct_index < len(options)):
            result.add_issue(
                code="MCQ_INVALID_INDEX",
                severity=ValidationSeverity.ERROR,
                message=f"correct_index {correct_index} out of range",
                penalty=50,
            )

        # Check for weak distractors
        for i, option in enumerate(options):
            if i == correct_index:
                continue
            option_lower = option.lower()
            if "all of the above" in option_lower or "none of the above" in option_lower:
                result.add_issue(
                    code="MCQ_WEAK_DISTRACTOR",
                    severity=ValidationSeverity.WARNING,
                    message="'All/None of the above' is a weak distractor",
                    penalty=10,
                )

    def _validate_true_false(self, content_json: Optional[dict], result: EnhancedValidationResult):
        """Validate True/False structure."""
        if not content_json:
            result.add_issue(
                code="TF_NO_CONTENT",
                severity=ValidationSeverity.ERROR,
                message="True/False requires content_json",
                penalty=50,
            )
            return

        if "correct" not in content_json:
            result.add_issue(
                code="TF_NO_CORRECT",
                severity=ValidationSeverity.ERROR,
                message="True/False must have 'correct' boolean",
                penalty=50,
            )

        # Check for explanation
        if "explanation" not in content_json:
            result.add_issue(
                code="TF_NO_EXPLANATION",
                severity=ValidationSeverity.WARNING,
                message="True/False should have explanation",
                penalty=10,
            )

    def _validate_matching(self, content_json: Optional[dict], result: EnhancedValidationResult):
        """Validate Matching structure."""
        if not content_json:
            result.add_issue(
                code="MATCH_NO_CONTENT",
                severity=ValidationSeverity.ERROR,
                message="Matching requires content_json",
                penalty=50,
            )
            return

        pairs = content_json.get("pairs", [])

        if not pairs:
            result.add_issue(
                code="MATCH_NO_PAIRS",
                severity=ValidationSeverity.ERROR,
                message="Matching must have pairs array",
                penalty=50,
            )
            return

        if len(pairs) < self.MATCHING_PAIRS_MIN:
            result.add_issue(
                code="MATCH_FEW_PAIRS",
                severity=ValidationSeverity.WARNING,
                message=f"Matching has {len(pairs)} pairs (min: {self.MATCHING_PAIRS_MIN})",
                penalty=10,
            )
        elif len(pairs) > self.MATCHING_PAIRS_MAX:
            result.add_issue(
                code="MATCH_MANY_PAIRS",
                severity=ValidationSeverity.ERROR,
                message=f"Matching has {len(pairs)} pairs (max: {self.MATCHING_PAIRS_MAX} for working memory)",
                penalty=25,
            )

        # Validate pair structure
        for i, pair in enumerate(pairs):
            if "left" not in pair or "right" not in pair:
                result.add_issue(
                    code="MATCH_INVALID_PAIR",
                    severity=ValidationSeverity.ERROR,
                    message=f"Pair {i} missing 'left' or 'right'",
                    penalty=20,
                )

    def _validate_parsons(self, content_json: Optional[dict], result: EnhancedValidationResult):
        """Validate Parsons problem structure."""
        if not content_json:
            result.add_issue(
                code="PARSONS_NO_CONTENT",
                severity=ValidationSeverity.ERROR,
                message="Parsons requires content_json",
                penalty=50,
            )
            return

        blocks = content_json.get("blocks", content_json.get("correct_sequence", []))

        if not blocks:
            result.add_issue(
                code="PARSONS_NO_BLOCKS",
                severity=ValidationSeverity.ERROR,
                message="Parsons must have blocks array",
                penalty=50,
            )
            return

        if len(blocks) < self.PARSONS_BLOCKS_MIN:
            result.add_issue(
                code="PARSONS_FEW_BLOCKS",
                severity=ValidationSeverity.WARNING,
                message=f"Parsons has {len(blocks)} blocks (min: {self.PARSONS_BLOCKS_MIN})",
                penalty=10,
            )
        elif len(blocks) > self.PARSONS_BLOCKS_MAX:
            result.add_issue(
                code="PARSONS_MANY_BLOCKS",
                severity=ValidationSeverity.WARNING,
                message=f"Parsons has {len(blocks)} blocks (max: {self.PARSONS_BLOCKS_MAX})",
                penalty=15,
            )

        # Check for incomplete commands
        for block in blocks:
            if isinstance(block, str) and len(block.split()) == 1 and not block.startswith("!"):
                result.add_issue(
                    code="PARSONS_INCOMPLETE_BLOCK",
                    severity=ValidationSeverity.WARNING,
                    message=f"Block '{block}' may be incomplete",
                    penalty=5,
                )

    def _validate_cloze(self, front: str, result: EnhancedValidationResult):
        """Validate Cloze structure."""
        # Check for cloze syntax
        if "{{c1::" not in front:
            result.add_issue(
                code="CLOZE_NO_DELETION",
                severity=ValidationSeverity.ERROR,
                message="Cloze must contain {{c1::...}} deletion",
                penalty=50,
            )
            return

        # Check for balanced braces
        if front.count("{{") != front.count("}}"):
            result.add_issue(
                code="CLOZE_UNBALANCED",
                severity=ValidationSeverity.ERROR,
                message="Cloze has unbalanced braces",
                penalty=30,
            )

        # Check for multiple deletions (warning, not error)
        if "{{c2::" in front:
            result.add_issue(
                code="CLOZE_MULTIPLE",
                severity=ValidationSeverity.WARNING,
                message="Cloze has multiple deletions (prefer single deletion)",
                penalty=10,
            )

    def _validate_flashcard(self, front: str, back: str, result: EnhancedValidationResult):
        """Validate Flashcard structure."""
        # Check question ends with ?
        if front and not front.strip().endswith("?"):
            # Not all flashcards are questions (some are prompts)
            if any(front.lower().startswith(w) for w in ["what", "how", "why", "when", "where", "which", "who"]):
                result.add_issue(
                    code="FLASHCARD_NO_QUESTION_MARK",
                    severity=ValidationSeverity.WARNING,
                    message="Question word used but no question mark",
                    penalty=5,
                )

    def _check_quality_warnings(
        self,
        front: str,
        back: str,
        result: EnhancedValidationResult,
    ):
        """Check for quality warning patterns."""
        combined = f"{front} ||| {back}"

        for pattern, code, message in QUALITY_WARNING_PATTERNS:
            if pattern.search(combined):
                result.add_issue(
                    code=code,
                    severity=ValidationSeverity.WARNING,
                    message=message,
                    penalty=10,
                )

    def _check_atomicity(self, back: str, result: EnhancedValidationResult):
        """Check that answer contains one atomic fact."""
        if not back:
            return

        # Check for enumeration
        if re.search(r"^\s*[-•*]\s+", back, re.MULTILINE):
            list_items = len(re.findall(r"^\s*[-•*]\s+", back, re.MULTILINE))
            if list_items >= 2:
                result.add_issue(
                    code="ATOMICITY_ENUMERATION",
                    severity=ValidationSeverity.WARNING,
                    message=f"Answer has {list_items} bullet points (prefer atomic facts)",
                    penalty=15,
                )
                result.is_atomic = False

        if re.search(r"^\s*\d+[.)]\s+", back, re.MULTILINE):
            list_items = len(re.findall(r"^\s*\d+[.)]\s+", back, re.MULTILINE))
            if list_items >= 2:
                result.add_issue(
                    code="ATOMICITY_NUMBERED",
                    severity=ValidationSeverity.WARNING,
                    message=f"Answer has {list_items} numbered items (prefer atomic facts)",
                    penalty=15,
                )
                result.is_atomic = False

        # Check for multiple sentences
        sentences = len(re.findall(r"[.!?]+", back))
        if sentences > 2:
            result.add_issue(
                code="ATOMICITY_SENTENCES",
                severity=ValidationSeverity.WARNING,
                message=f"Answer has {sentences} sentences (prefer 1-2)",
                penalty=10,
            )
            result.is_atomic = False

        # Check for "and also", "additionally", etc.
        multi_fact_markers = [
            r"\band\s+also\b",
            r"\badditionally\b",
            r"\bfurthermore\b",
            r"\bmoreover\b",
            r"\bin addition\b",
        ]
        for marker in multi_fact_markers:
            if re.search(marker, back, re.IGNORECASE):
                result.add_issue(
                    code="ATOMICITY_MARKER",
                    severity=ValidationSeverity.WARNING,
                    message=f"Answer contains multi-fact marker",
                    penalty=10,
                )
                result.is_atomic = False
                break

    def _check_source_accuracy(
        self,
        front: str,
        back: str,
        source: str,
        result: EnhancedValidationResult,
    ):
        """Check if content is grounded in source."""
        # Extract key terms from atom
        atom_text = f"{front} {back}".lower()
        source_lower = source.lower()

        # Find networking terms in atom
        networking_terms = re.findall(
            r"\b(?:router|switch|vlan|subnet|protocol|ethernet|packet|frame|tcp|udp|"
            r"port|interface|bandwidth|gateway|dns|dhcp|ospf|eigrp|bgp|acl|nat|stp|"
            r"ip\s+address|mac\s+address|layer\s+\d)\b",
            atom_text,
            re.IGNORECASE,
        )

        if networking_terms:
            unmatched = [t for t in networking_terms if t not in source_lower]
            if len(unmatched) > len(networking_terms) * 0.3:
                result.add_issue(
                    code="SOURCE_ACCURACY",
                    severity=ValidationSeverity.WARNING,
                    message=f"Terms not found in source: {unmatched[:3]}",
                    penalty=15,
                )


# =============================================================================
# Math Validator for Module 5 (Binary/Decimal/Hexadecimal)
# =============================================================================

class NumberSystemValidator:
    """
    Validates mathematical correctness of binary/decimal/hexadecimal conversions.

    Used specifically for Module 5 atoms to ensure conversion examples are accurate.
    This catches LLM hallucinations in math calculations.
    """

    # Pattern matchers for different number formats
    BINARY_PATTERN = re.compile(r"\b([01]{4,8}(?:\.[01]{8}){0,3})\b")  # e.g., 11000000 or 11000000.10101000.00001010.00001010
    DECIMAL_OCTET_PATTERN = re.compile(r"\b(\d{1,3}(?:\.\d{1,3}){3})\b")  # e.g., 192.168.10.10
    HEX_PATTERN = re.compile(r"\b([0-9A-Fa-f]{2,4})\b")  # e.g., A8, D2, 2001

    # Common conversion claims in text
    CONVERSION_PATTERNS = [
        # "X in binary: Y" or "binary: X"
        re.compile(r"(\d{1,3})\s*(?:in\s+binary|→|=)\s*[`\"']?([01]{8})[`\"']?", re.IGNORECASE),
        # "binary X = decimal Y"
        re.compile(r"[`\"']?([01]{8})[`\"']?\s*(?:=|→|is)\s*(?:\*\*)?(\d{1,3})(?:\*\*)?", re.IGNORECASE),
        # "Convert X to binary... Result: Y"
        re.compile(r"convert\s+(\d{1,3}).*?(?:result|=|→)[:\s]*[`\"']?([01]{8})[`\"']?", re.IGNORECASE | re.DOTALL),
        # Hex conversions: "X in hex: Y" or "hex: Y"
        re.compile(r"(\d{1,3})\s*(?:in\s+hex(?:adecimal)?|→|=)\s*[`\"']?([0-9A-Fa-f]{2})[`\"']?", re.IGNORECASE),
        # "hex X = decimal Y"
        re.compile(r"[`\"']?([0-9A-Fa-f]{2})[`\"']?\s*(?:=|→|is)\s*(?:\*\*)?(\d{1,3})(?:\*\*)?", re.IGNORECASE),
    ]

    @staticmethod
    def binary_to_decimal(binary_str: str) -> int:
        """Convert binary string to decimal."""
        # Remove any dots for IPv4-style binary
        binary_clean = binary_str.replace(".", "")
        return int(binary_clean, 2)

    @staticmethod
    def decimal_to_binary(decimal_val: int, pad_to: int = 8) -> str:
        """Convert decimal to binary with optional padding."""
        return format(decimal_val, f"0{pad_to}b")

    @staticmethod
    def hex_to_decimal(hex_str: str) -> int:
        """Convert hexadecimal string to decimal."""
        return int(hex_str, 16)

    @staticmethod
    def decimal_to_hex(decimal_val: int) -> str:
        """Convert decimal to hexadecimal (uppercase)."""
        return format(decimal_val, "X")

    @staticmethod
    def validate_ipv4_binary(binary_ipv4: str, decimal_ipv4: str) -> tuple[bool, str]:
        """
        Validate an IPv4 address binary to decimal conversion.

        Args:
            binary_ipv4: e.g., "11000000.10101000.00001010.00001010"
            decimal_ipv4: e.g., "192.168.10.10"

        Returns:
            (is_valid, error_message)
        """
        try:
            binary_octets = binary_ipv4.split(".")
            decimal_octets = decimal_ipv4.split(".")

            if len(binary_octets) != 4 or len(decimal_octets) != 4:
                return False, "IPv4 must have exactly 4 octets"

            for i, (bin_oct, dec_oct) in enumerate(zip(binary_octets, decimal_octets)):
                if len(bin_oct) != 8:
                    return False, f"Octet {i+1}: Binary must be 8 bits, got {len(bin_oct)}"

                expected_decimal = int(bin_oct, 2)
                actual_decimal = int(dec_oct)

                if expected_decimal != actual_decimal:
                    return False, f"Octet {i+1}: {bin_oct} = {expected_decimal}, not {actual_decimal}"

            return True, ""
        except ValueError as e:
            return False, f"Invalid format: {e}"

    @staticmethod
    def validate_single_octet(binary_str: str, decimal_val: int) -> tuple[bool, str]:
        """
        Validate a single octet binary to decimal conversion.

        Args:
            binary_str: e.g., "11000000"
            decimal_val: e.g., 192

        Returns:
            (is_valid, error_message)
        """
        try:
            if len(binary_str) != 8 or not all(c in "01" for c in binary_str):
                return False, f"Invalid binary format: {binary_str}"

            if not 0 <= decimal_val <= 255:
                return False, f"Decimal {decimal_val} out of octet range (0-255)"

            expected = int(binary_str, 2)
            if expected != decimal_val:
                return False, f"{binary_str} = {expected}, not {decimal_val}"

            return True, ""
        except ValueError as e:
            return False, f"Conversion error: {e}"

    @staticmethod
    def validate_hex_conversion(hex_str: str, decimal_val: int) -> tuple[bool, str]:
        """
        Validate a hexadecimal to decimal conversion.

        Args:
            hex_str: e.g., "A8", "D2"
            decimal_val: e.g., 168, 210

        Returns:
            (is_valid, error_message)
        """
        try:
            expected = int(hex_str, 16)
            if expected != decimal_val:
                return False, f"0x{hex_str} = {expected}, not {decimal_val}"
            return True, ""
        except ValueError as e:
            return False, f"Invalid hex format: {e}"

    def validate_atom_math(self, front: str, back: str) -> list[ValidationIssue]:
        """
        Validate all math claims in a learning atom's question and answer.

        Returns list of validation issues found.
        """
        issues = []
        combined = f"{front} {back}"

        # Check for conversion claims
        for pattern in self.CONVERSION_PATTERNS:
            matches = pattern.finditer(combined)
            for match in matches:
                groups = match.groups()
                if len(groups) >= 2:
                    # Determine conversion type based on pattern match
                    val1, val2 = groups[0], groups[1]

                    # Binary to Decimal check
                    if all(c in "01" for c in val1) and val1.isdigit() == False:
                        try:
                            expected = int(val1, 2)
                            actual = int(val2)
                            if expected != actual:
                                issues.append(ValidationIssue(
                                    code="MATH_BINARY_DECIMAL",
                                    severity=ValidationSeverity.ERROR,
                                    message=f"Binary {val1} = {expected}, not {actual}",
                                    field="back",
                                ))
                        except ValueError:
                            pass

                    # Decimal to Binary check
                    elif val1.isdigit() and all(c in "01" for c in val2):
                        try:
                            decimal_val = int(val1)
                            expected = format(decimal_val, "08b")
                            if expected != val2 and expected.lstrip("0") != val2.lstrip("0"):
                                issues.append(ValidationIssue(
                                    code="MATH_DECIMAL_BINARY",
                                    severity=ValidationSeverity.ERROR,
                                    message=f"Decimal {val1} = {expected}, not {val2}",
                                    field="back",
                                ))
                        except ValueError:
                            pass

                    # Hex to Decimal check
                    elif all(c in "0123456789ABCDEFabcdef" for c in val1) and not val1.isdigit():
                        try:
                            expected = int(val1, 16)
                            actual = int(val2)
                            if expected != actual:
                                issues.append(ValidationIssue(
                                    code="MATH_HEX_DECIMAL",
                                    severity=ValidationSeverity.ERROR,
                                    message=f"Hex {val1} = {expected}, not {actual}",
                                    field="back",
                                ))
                        except ValueError:
                            pass

                    # Decimal to Hex check
                    elif val1.isdigit() and all(c in "0123456789ABCDEFabcdef" for c in val2):
                        try:
                            decimal_val = int(val1)
                            expected = format(decimal_val, "X")
                            if expected.upper() != val2.upper():
                                issues.append(ValidationIssue(
                                    code="MATH_DECIMAL_HEX",
                                    severity=ValidationSeverity.ERROR,
                                    message=f"Decimal {val1} = 0x{expected}, not 0x{val2}",
                                    field="back",
                                ))
                        except ValueError:
                            pass

        # Check IPv4 binary/decimal pairs
        binary_ipv4_matches = re.findall(r"([01]{8}\.[01]{8}\.[01]{8}\.[01]{8})", combined)
        decimal_ipv4_matches = self.DECIMAL_OCTET_PATTERN.findall(combined)

        if binary_ipv4_matches and decimal_ipv4_matches:
            for bin_ip in binary_ipv4_matches:
                for dec_ip in decimal_ipv4_matches:
                    # Check if this could be the same IP
                    is_valid, error = self.validate_ipv4_binary(bin_ip, dec_ip)
                    if not is_valid:
                        # Only report if they seem related (e.g., mentioned together)
                        if bin_ip in combined and dec_ip in combined:
                            issues.append(ValidationIssue(
                                code="MATH_IPV4_CONVERSION",
                                severity=ValidationSeverity.WARNING,
                                message=f"Possible IPv4 mismatch: {error}",
                                field="back",
                            ))

        return issues


# =============================================================================
# Convenience Functions
# =============================================================================

_validator_instance: Optional[EnhancedQualityValidator] = None
_math_validator_instance: Optional[NumberSystemValidator] = None


def get_math_validator() -> NumberSystemValidator:
    """Get or create singleton math validator."""
    global _math_validator_instance
    if _math_validator_instance is None:
        _math_validator_instance = NumberSystemValidator()
    return _math_validator_instance


def get_enhanced_validator() -> EnhancedQualityValidator:
    """Get or create singleton validator."""
    global _validator_instance
    if _validator_instance is None:
        _validator_instance = EnhancedQualityValidator()
    return _validator_instance


def validate_atom(
    front: str,
    back: str,
    atom_type: str = "flashcard",
    content_json: Optional[dict] = None,
    source_content: Optional[str] = None,
    validate_math: bool = False,
) -> EnhancedValidationResult:
    """
    Convenience function to validate an atom.

    Args:
        front: Question/prompt text
        back: Answer text
        atom_type: Type of atom (flashcard, mcq, etc.)
        content_json: Type-specific content (options, pairs, etc.)
        source_content: Original source for accuracy check
        validate_math: Enable math validation for Module 5 atoms (binary/hex)

    Returns:
        EnhancedValidationResult with detailed issues and score
    """
    result = get_enhanced_validator().validate(
        front=front,
        back=back,
        atom_type=atom_type,
        content_json=content_json,
        source_content=source_content,
    )

    # Add math validation for Module 5
    if validate_math:
        math_issues = get_math_validator().validate_atom_math(front, back)
        for issue in math_issues:
            result.add_issue(
                code=issue.code,
                severity=issue.severity,
                message=issue.message,
                field=issue.field,
                penalty=30 if issue.severity == ValidationSeverity.ERROR else 10,
            )

    return result


# =============================================================================
# Test Cases
# =============================================================================

if __name__ == "__main__":
    # Test the validator
    test_cases = [
        # Good examples
        ("What routing protocol uses Dijkstra's algorithm?", "OSPF uses Dijkstra's shortest path first algorithm to calculate the best route to each destination.", "flashcard"),
        ("What is the purpose of a VLAN in enterprise networks?", "VLANs logically segment a physical network into separate broadcast domains, improving security and reducing congestion.", "flashcard"),

        # Bad examples (should fail)
        ("In networking, what circuits The circuits?", "Something about circuits", "flashcard"),
        ("What is This?", "Some answer", "flashcard"),
        ("What is Business DSL?", "Business DSL is", "flashcard"),  # Truncated
        ("What is the purpose?", "Provides the", "flashcard"),  # Truncated
        ("What layer handles routing?", "Layer 3", "flashcard"),  # Too short

        # MCQ test
        ("Which protocol operates at Layer 4?", None, "mcq"),
    ]

    validator = EnhancedQualityValidator(use_perplexity=False, use_grammar=False)

    print("\n=== Enhanced Quality Validator Test ===\n")
    for front, back, atom_type in test_cases:
        content = {"options": ["TCP", "IP", "Ethernet", "ARP"], "correct_index": 0} if atom_type == "mcq" else None
        result = validator.validate(front, back or "", atom_type, content)

        status = "PASS" if result.is_valid else "FAIL"
        print(f"[{status}] ({result.score:.0f}) {front[:50]}...")
        if result.issues:
            for issue in result.issues:
                print(f"   [{issue.severity.value}] {issue.code}: {issue.message}")
        print()

    # =============================================================================
    # Math Validator Test Cases (Module 5)
    # =============================================================================

    print("\n=== Number System Math Validator Test ===\n")

    math_validator = NumberSystemValidator()

    math_test_cases = [
        # Correct conversions
        (
            "What is 192 in binary?",
            "192 in binary = 11000000 (128 + 64 = 192)",
            True,
            "Correct decimal to binary"
        ),
        (
            "Convert the binary 11000000 to decimal.",
            "The binary 11000000 = 192 in decimal.",
            True,
            "Correct binary to decimal"
        ),
        (
            "What is 168 in hexadecimal?",
            "168 in hex = A8 (10*16 + 8 = 168)",
            True,
            "Correct decimal to hex"
        ),
        (
            "Convert D2 to decimal.",
            "D2 in hex is 210 in decimal.",
            True,
            "Correct hex to decimal"
        ),
        (
            "Convert IPv4 address",
            "11000000.10101000.00001010.00001010 = 192.168.10.10",
            True,
            "Correct IPv4 conversion"
        ),

        # INCORRECT conversions (should be caught)
        (
            "What is 192 in binary?",
            "192 in binary = 11000001",  # Wrong! Should be 11000000
            False,
            "Incorrect binary (off by 1)"
        ),
        (
            "Convert 11000000 to decimal.",
            "11000000 = 190 in decimal.",  # Wrong! Should be 192
            False,
            "Incorrect decimal calculation"
        ),
        (
            "What is 168 in hexadecimal?",
            "168 in hex = B8",  # Wrong! Should be A8
            False,
            "Incorrect hex digit"
        ),
        (
            "Convert D2 to decimal.",
            "D2 = 200 in decimal.",  # Wrong! Should be 210
            False,
            "Incorrect hex to decimal"
        ),
    ]

    for front, back, should_pass, description in math_test_cases:
        issues = math_validator.validate_atom_math(front, back)
        has_errors = any(i.severity == ValidationSeverity.ERROR for i in issues)

        if should_pass and not has_errors:
            status = "✓ PASS"
        elif not should_pass and has_errors:
            status = "✓ PASS (caught error)"
        else:
            status = "✗ FAIL"

        print(f"[{status}] {description}")
        if issues:
            for issue in issues:
                print(f"   {issue.code}: {issue.message}")
        print()

    # Test specific validator methods
    print("\n=== Direct Conversion Tests ===\n")

    # Test validate_single_octet
    test_octets = [
        ("11000000", 192, True),
        ("10101000", 168, True),
        ("00001010", 10, True),
        ("11000000", 190, False),  # Wrong
        ("10101000", 160, False),  # Wrong
    ]

    for binary, decimal, expected_valid in test_octets:
        is_valid, error = math_validator.validate_single_octet(binary, decimal)
        status = "✓" if is_valid == expected_valid else "✗"
        print(f"[{status}] {binary} = {decimal}: {'Valid' if is_valid else error}")
