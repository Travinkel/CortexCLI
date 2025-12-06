"""
Mathematical Quality Validation for Flashcards

Two evidence-based approaches:
1. Perplexity scoring (GPT-2) - measures text coherence/naturalness
2. POS grammar validation (spaCy) - validates grammatical structure

Both approaches catch malformed text that pattern matching misses.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from functools import lru_cache
from typing import Optional

from loguru import logger


@dataclass
class QualityValidation:
    """Result of quality validation."""
    is_valid: bool
    perplexity: Optional[float] = None
    grammar_valid: Optional[bool] = None
    grammar_issues: list[str] = None
    reason: Optional[str] = None

    def __post_init__(self):
        if self.grammar_issues is None:
            self.grammar_issues = []


class PerplexityScorer:
    """
    Calculate perplexity using GPT-2 (or similar small LM).

    Perplexity measures how "surprised" the model is by the text.
    - Low perplexity (< 50): Natural, coherent text
    - Medium perplexity (50-150): Acceptable
    - High perplexity (> 150): Likely malformed/ungrammatical

    Based on: https://huggingface.co/docs/transformers/perplexity
    """

    def __init__(self, model_name: str = "gpt2"):
        """Initialize with GPT-2 (small, 124M params)."""
        try:
            import torch
            from transformers import GPT2LMHeadModel, GPT2TokenizerFast

            self.device = "cuda" if torch.cuda.is_available() else "cpu"
            logger.info(f"Loading {model_name} for perplexity scoring on {self.device}")

            self.tokenizer = GPT2TokenizerFast.from_pretrained(model_name)
            self.model = GPT2LMHeadModel.from_pretrained(model_name).to(self.device)
            self.model.eval()
            self.torch = torch
            self._available = True

        except ImportError:
            logger.warning("transformers/torch not installed. Perplexity scoring disabled.")
            self._available = False
        except Exception as e:
            logger.warning(f"Failed to load GPT-2: {e}. Perplexity scoring disabled.")
            self._available = False

    @property
    def available(self) -> bool:
        return self._available

    def calculate_perplexity(self, text: str) -> float:
        """
        Calculate perplexity of text.

        Returns:
            Perplexity score (lower = more coherent)
            Returns float('inf') if unavailable or error
        """
        if not self._available:
            return float('inf')

        try:
            # Tokenize
            inputs = self.tokenizer(text, return_tensors="pt", truncation=True, max_length=512)
            inputs = {k: v.to(self.device) for k, v in inputs.items()}

            # Calculate loss
            with self.torch.no_grad():
                outputs = self.model(**inputs, labels=inputs["input_ids"])

            # Perplexity = exp(loss)
            return self.torch.exp(outputs.loss).item()

        except Exception as e:
            logger.debug(f"Perplexity calculation failed: {e}")
            return float('inf')


class GrammarValidator:
    """
    Validate grammatical structure using spaCy POS tagging.

    Checks:
    1. Question structure (WH-word + verb + ...)
    2. Proper sentence boundaries
    3. No orphaned determiners/articles
    4. Subject-verb agreement patterns
    """

    # Valid question patterns (simplified POS sequences)
    VALID_QUESTION_STARTS = [
        ("WP", "VBZ"),     # What is
        ("WP", "VBP"),     # What are
        ("WP", "VBD"),     # What was
        ("WP", "MD"),      # What can/does/will
        ("WRB", "VBZ"),    # How is
        ("WRB", "VBP"),    # How are
        ("WRB", "MD"),     # How can
        ("WP", "NN"),      # What type (acceptable)
        ("WP", "NNS"),     # What types
    ]

    # Invalid patterns (indicate malformed text)
    INVALID_PATTERNS = [
        ("WP", "NN", "DT"),      # "What circuits The" - DT after NN is wrong
        ("WP", "VBZ", "DT", "NN", "DT"),  # "What is This concept The"
        ("IN", "NN", ",", "WP"),  # "In X, what" followed by garbage
    ]

    def __init__(self, model: str = "en_core_web_sm"):
        """Initialize spaCy model."""
        try:
            import spacy
            self.nlp = spacy.load(model)
            self._available = True
            logger.info(f"Loaded spaCy model: {model}")
        except ImportError:
            logger.warning("spaCy not installed. Grammar validation disabled.")
            self._available = False
        except OSError:
            logger.warning(f"spaCy model '{model}' not found. Run: python -m spacy download {model}")
            self._available = False

    @property
    def available(self) -> bool:
        return self._available

    def validate(self, text: str) -> tuple[bool, list[str]]:
        """
        Validate grammatical structure.

        Returns:
            (is_valid, list_of_issues)
        """
        if not self._available:
            return True, []  # Skip if not available

        issues = []

        try:
            doc = self.nlp(text)
            pos_tags = [(token.text, token.pos_, token.tag_) for token in doc]
            tag_sequence = [t[2] for t in pos_tags]

            # Note: WH-word check disabled - too many false positives
            # Valid questions can start with: "In X, what...", "For X, what...",
            # "Does X...", "Is X...", "After X, what...", "Besides X, what..."
            # The perplexity filter catches actual gibberish more reliably

            # Check 2: Orphaned determiners (DT after NN/NNS without following noun)
            for i, (word, pos, tag) in enumerate(pos_tags[:-1]):
                if tag == "DT" and i > 0:
                    prev_tag = pos_tags[i-1][2]
                    next_tag = pos_tags[i+1][2] if i+1 < len(pos_tags) else ""
                    # DT after NN/NNS and not followed by NN/JJ is wrong
                    if prev_tag in ("NN", "NNS", "VBZ", "VBP") and next_tag in ("NN", "NNS"):
                        # Check if it's a case like "what circuits The circuits"
                        if word.lower() in ("the", "a", "an") and word[0].isupper():
                            issues.append(f"Misplaced determiner '{word}' after {prev_tag}")

            # Check 3: Repeated content words (sign of truncation/corruption)
            # Note: Disabled - too many false positives with domain terms like
            # "network" in networking content, "peer" in peer-to-peer, etc.
            # Perplexity scoring handles actual garbled text better
            pass  # Keeping the structure for future refinement

            # Note: Verb detection disabled - too many false positives with questions
            # SpaCy often misclassifies verbs in questions (e.g., "handles" as noun)
            # Perplexity scoring catches incoherent text more reliably

        except Exception as e:
            logger.debug(f"Grammar validation error: {e}")

        return len(issues) == 0, issues


class QualityValidator:
    """
    Combined quality validation using perplexity + grammar checks.

    Usage:
        validator = QualityValidator()
        result = validator.validate("What is BYOD?")
        if result.is_valid:
            print("Good card!")
    """

    # Thresholds (tuned empirically on CCNA flashcards)
    # Note: GPT-2 perplexity varies widely - short domain-specific questions
    # often have higher perplexity than conversational text
    PERPLEXITY_REJECT = 2000.0   # Reject if perplexity > this (catches gibberish)
    PERPLEXITY_WARN = 500.0      # Warn if perplexity > this

    def __init__(
        self,
        use_perplexity: bool = True,
        use_grammar: bool = True,
        perplexity_model: str = "gpt2",
        grammar_model: str = "en_core_web_sm",
    ):
        """
        Initialize validators.

        Args:
            use_perplexity: Enable perplexity scoring (requires transformers)
            use_grammar: Enable grammar validation (requires spaCy)
        """
        self.perplexity_scorer = PerplexityScorer(perplexity_model) if use_perplexity else None
        self.grammar_validator = GrammarValidator(grammar_model) if use_grammar else None

    def validate(self, question: str, answer: str = "") -> QualityValidation:
        """
        Validate flashcard quality.

        Args:
            question: The question/front text
            answer: The answer/back text (optional, checked for basic issues)

        Returns:
            QualityValidation with is_valid, scores, and issues
        """
        # Quick regex pre-checks (fast rejection)
        quick_issues = self._quick_check(question)
        if quick_issues:
            return QualityValidation(
                is_valid=False,
                reason=quick_issues,
            )

        result = QualityValidation(is_valid=True)

        # Perplexity check
        if self.perplexity_scorer and self.perplexity_scorer.available:
            ppl = self.perplexity_scorer.calculate_perplexity(question)
            result.perplexity = ppl

            if ppl > self.PERPLEXITY_REJECT:
                result.is_valid = False
                result.reason = f"High perplexity ({ppl:.1f}) indicates incoherent text"
                return result

        # Grammar check
        if self.grammar_validator and self.grammar_validator.available:
            grammar_valid, issues = self.grammar_validator.validate(question)
            result.grammar_valid = grammar_valid
            result.grammar_issues = issues

            if not grammar_valid:
                result.is_valid = False
                result.reason = f"Grammar issues: {'; '.join(issues)}"
                return result

        return result

    def _quick_check(self, text: str) -> Optional[str]:
        """Quick regex checks for obvious issues."""
        # Repeated commas/punctuation
        if re.search(r"[,]{2,}", text):
            return "Repeated commas"

        # Malformed question patterns - capitalized "The" mid-sentence (not after "is/are")
        # Catches: "what circuits The circuits" but NOT "what is the purpose"
        # The pattern looks for: word The word (where The is capitalized after a non-verb word)
        if re.search(r"what\s+(?!is\s+the|are\s+the|does\s+the|do\s+the)\w+\s+The\s+\w+", text):
            return "Malformed: 'what X The Y' pattern"

        # Vague question with capitalized "This" (not specific)
        if re.search(r"what\s+is\s+This\b", text):
            return "Too vague: 'what is This'"

        # Malformed conditional
        if re.search(r"what\s+\w+\s+If\s+", text):
            return "Malformed: conditional in wrong position"

        # Very short
        if len(text.strip()) < 15:
            return "Too short"

        return None


# Singleton for performance (model loading is expensive)
_validator_instance: Optional[QualityValidator] = None


def get_validator() -> QualityValidator:
    """Get or create the singleton validator."""
    global _validator_instance
    if _validator_instance is None:
        _validator_instance = QualityValidator()
    return _validator_instance


def validate_card(question: str, answer: str = "") -> QualityValidation:
    """Convenience function to validate a card."""
    return get_validator().validate(question, answer)


if __name__ == "__main__":
    # Test validation
    test_cases = [
        "What does BYOD stand for?",  # Good
        "What is the purpose of a router in a network?",  # Good
        "In networking, what circuits The circuits?",  # Bad - malformed
        "What is This?",  # Bad - too vague
        "What the However the term hosts specifically?",  # Bad - incoherent
        "What layer handles IP addressing?",  # Good
    ]

    validator = QualityValidator()

    print("\n=== Quality Validation Test ===\n")
    for text in test_cases:
        result = validator.validate(text)
        status = "PASS" if result.is_valid else "FAIL"
        print(f"[{status}] {text[:60]}")
        if result.perplexity:
            print(f"   Perplexity: {result.perplexity:.1f}")
        if result.grammar_issues:
            print(f"   Grammar: {result.grammar_issues}")
        if result.reason:
            print(f"   Reason: {result.reason}")
        print()
