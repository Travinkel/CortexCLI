"""
Card quality analysis and cleaning services.

Evidence-based quality grading for learning atoms.
"""

from .atomicity import CardQualityAnalyzer, QualityGrade, QualityIssue, QualityReport
from .thresholds import (
    BACK_CHARS_MAX,
    BACK_WORDS_MAX,
    BACK_WORDS_OPTIMAL,
    FRONT_CHARS_MAX,
    FRONT_WORDS_MAX,
    FRONT_WORDS_OPTIMAL,
)

__all__ = [
    "CardQualityAnalyzer",
    "QualityGrade",
    "QualityIssue",
    "QualityReport",
    "FRONT_WORDS_OPTIMAL",
    "FRONT_WORDS_MAX",
    "FRONT_CHARS_MAX",
    "BACK_WORDS_OPTIMAL",
    "BACK_WORDS_MAX",
    "BACK_CHARS_MAX",
]
