"""
Quiz module for question management and quality assurance.

This module provides:
- QuizQuestionAnalyzer: Quality analysis for quiz questions
- QuizPoolManager: Question pool management and selection

Question Types:
- mcq: Multiple choice question
- true_false: True/False
- short_answer: Fill in blank
- matching: Match pairs (max 6)
- ranking: Order items
- passage_based: Question about a passage

Knowledge Types:
- factual: Recall facts (passing 70%)
- conceptual: Understand relationships (passing 80%)
- procedural: Execute steps (passing 85%)
- metacognitive: Self-regulation strategies
"""

from .quiz_pool_manager import QuizPoolManager
from .quiz_quality_analyzer import QuizQuestionAnalyzer

__all__ = [
    "QuizQuestionAnalyzer",
    "QuizPoolManager",
]
