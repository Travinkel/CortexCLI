"""
Evidence-Based Quality Thresholds (ADR-002)

Sources:
- Wozniak (1999): "20 Rules of Formulating Knowledge" - minimum information principle
- Sweller (1988): Cognitive Load Theory - working memory limits (~4 chunks)
- Karpicke & Roediger (2008): Testing effect - atomicity for retrieval
- Gwern (2009-2020): Spaced repetition meta-analysis

See: docs/foundations/flashcard-quality-science.md
"""

# ============================================================================
# Front (question/prompt) thresholds
# ============================================================================
FRONT_WORDS_OPTIMAL = 15  # Optimal: 8-15 words
FRONT_WORDS_MAX = 25  # Reject if >25 words (Wozniak, Gwern)
FRONT_CHARS_MAX = 200  # Reject if >200 chars (CLT - extraneous load)

# ============================================================================
# Back (answer/solution) thresholds
# Updated for EXPLANATORY style (Phase 6): 15-25 words with why/how context
# ============================================================================
BACK_WORDS_OPTIMAL = 15  # Sweet spot: 10-15 words with context
BACK_WORDS_WARNING = 25  # Warning zone: 16-25 words
BACK_WORDS_MAX = 30  # Reject if >30 words (explanatory style)
BACK_CHARS_WARNING = 200  # Warning zone: 121-200 chars
BACK_CHARS_MAX = 300  # Reject if >300 chars (explanatory style)

# ============================================================================
# Code-specific thresholds
# ============================================================================
CODE_LINES_OPTIMAL = 5  # Optimal: 2-5 lines
CODE_LINES_MAX = 10  # Reject if >10 lines (CLT + programming education)

# ============================================================================
# Quality Grade Score Ranges
# ============================================================================
GRADE_A_MIN = 90
GRADE_B_MIN = 75
GRADE_C_MIN = 60
GRADE_D_MIN = 40
# Below GRADE_D_MIN = F

# ============================================================================
# Issue Score Penalties
# ============================================================================
PENALTY_FRONT_TOO_LONG = 30  # Front >25 words
PENALTY_FRONT_VERBOSE = 10  # Front >15 words
PENALTY_BACK_TOO_LONG = 15  # Back >30 words (reduced for explanatory)
PENALTY_BACK_VERBOSE = 5  # Back >15 words (reduced for explanatory)
PENALTY_FRONT_CHARS = 20  # Front >200 chars
PENALTY_BACK_CHARS = 20  # Back >300 chars (updated for explanatory)
PENALTY_CODE_TOO_LONG = 25  # Code >10 lines
PENALTY_CODE_VERBOSE = 10  # Code >5 lines
PENALTY_ENUMERATION = 30  # List markers detected
PENALTY_MULTIPLE_FACTS = 30  # Multiple facts in answer

# Text coherence penalties (v2)
PENALTY_MALFORMED_QUESTION = 50  # Truncated/garbled text (severe)
PENALTY_INCOHERENT_TEXT = 40  # Repeated punctuation, broken grammar
PENALTY_TOO_SHORT = 35  # Content too brief to be meaningful
PENALTY_GENERIC_QUESTION = 25  # Vague "what is This?" questions

# ============================================================================
# Anki Sync Quality Filters
# ============================================================================
# Minimum quality score (0-1 scale) for pushing cards to Anki
# Cards below this threshold are filtered out as broken/truncated
ANKI_MIN_QUALITY_SCORE = 0.50  # Grade C or better (0.50 = 50%)

# Minimum text length requirements
ANKI_MIN_FRONT_LENGTH = 20  # Minimum chars for question
ANKI_MIN_BACK_LENGTH = 5  # Minimum chars for answer

# Malformed text patterns to exclude (SQL LIKE patterns)
# These are cards with broken grammar, truncated text, or garbled content
ANKI_EXCLUDE_PATTERNS = [
    "%,,,% ",  # Repeated commas (truncation artifact)
    "%what concept The concept%",  # Garbled question structure
    "%what is This%",  # Generic vague questions
    "%In %%, what is This%",  # Placeholder-style garbage
]
