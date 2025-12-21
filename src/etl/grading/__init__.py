"""
Grading Strategies.

Strategy Pattern implementation for atom grading.
Replaces the monolithic if/elif evaluator with pluggable grading strategies.
"""

from .base import GradingStrategy, GradingResult, StrategyRegistry
from .strategies import (
    ExactMatchStrategy,
    FuzzyMatchStrategy,
    RegexStrategy,
    NumericStrategy,
    OrderMatchStrategy,
    SetMatchStrategy,
    RuntimeStrategy,
    RubricStrategy,
)

__all__ = [
    # Base classes
    "GradingStrategy",
    "GradingResult",
    "StrategyRegistry",
    # Strategies
    "ExactMatchStrategy",
    "FuzzyMatchStrategy",
    "RegexStrategy",
    "NumericStrategy",
    "OrderMatchStrategy",
    "SetMatchStrategy",
    "RuntimeStrategy",
    "RubricStrategy",
]
