"""
Adaptive Learning Engine.

Phase 5: Knewton-style just-in-time remediation with mastery-based content gating.

Components:
- MasteryCalculator: Computes mastery from review + quiz data
- PathSequencer: Orders atoms optimally based on prerequisites
- RemediationRouter: Detects gaps and routes to prerequisite content
- SuitabilityScorer: Scores how suitable content is for each atom type
- LearningEngine: Main orchestration layer
"""
from src.adaptive.models import (
    ConceptMastery,
    KnowledgeBreakdown,
    LearningPath,
    RemediationPlan,
    SuitabilityScore,
    ContentFeatures,
    SessionState,
    AtomPresentation,
    AnswerResult,
    MasteryLevel,
    GatingType,
    TriggerType,
    SessionMode,
    SessionStatus,
    KnowledgeGap,
    UnlockStatus,
    BlockingPrerequisite,
    # Reading progress models
    ChapterReadingProgress,
    ReReadRecommendation,
    COMPREHENSION_LEVELS,
)
from src.adaptive.mastery_calculator import MasteryCalculator
from src.adaptive.path_sequencer import PathSequencer
from src.adaptive.remediation_router import RemediationRouter
from src.adaptive.suitability_scorer import SuitabilityScorer
from src.adaptive.learning_engine import LearningEngine

__all__ = [
    # Main engine
    "LearningEngine",
    # Component classes
    "MasteryCalculator",
    "PathSequencer",
    "RemediationRouter",
    "SuitabilityScorer",
    # Data models
    "ConceptMastery",
    "KnowledgeBreakdown",
    "LearningPath",
    "RemediationPlan",
    "SuitabilityScore",
    "ContentFeatures",
    "SessionState",
    "AtomPresentation",
    "AnswerResult",
    "KnowledgeGap",
    "UnlockStatus",
    "BlockingPrerequisite",
    # Reading progress
    "ChapterReadingProgress",
    "ReReadRecommendation",
    "COMPREHENSION_LEVELS",
    # Enums
    "MasteryLevel",
    "GatingType",
    "TriggerType",
    "SessionMode",
    "SessionStatus",
]
