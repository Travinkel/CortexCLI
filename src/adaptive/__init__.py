"""
Adaptive Learning Engine package.

Note: To keep package import lightweight for tests that only need stateless
utilities (e.g., PathSequencer helpers), submodule imports are guarded.
This avoids importing database-dependent modules during package import.
"""

# Guarded imports to avoid raising on optional dependencies during test collection.
# Do NOT import DB-dependent modules here to keep package import light.
LearningEngine = None  # type: ignore
MasteryCalculator = None  # type: ignore

try:  # Data models (pure)
    from src.adaptive.models import (  # type: ignore
        COMPREHENSION_LEVELS,
        AnswerResult,
        AtomPresentation,
        BlockingPrerequisite,
        ChapterReadingProgress,
        ConceptMastery,
        ContentFeatures,
        GatingType,
        KnowledgeBreakdown,
        KnowledgeGap,
        LearningPath,
        MasteryLevel,
        RemediationPlan,
        ReReadRecommendation,
        SessionMode,
        SessionState,
        SessionStatus,
        SuitabilityScore,
        TriggerType,
        UnlockStatus,
    )
except Exception:  # pragma: no cover
    # Provide minimal fallbacks so attribute access doesn't crash in light tests
    COMPREHENSION_LEVELS = None  # type: ignore
    AnswerResult = None  # type: ignore
    AtomPresentation = None  # type: ignore
    BlockingPrerequisite = None  # type: ignore
    ChapterReadingProgress = None  # type: ignore
    ConceptMastery = None  # type: ignore
    ContentFeatures = None  # type: ignore
    GatingType = None  # type: ignore
    KnowledgeBreakdown = None  # type: ignore
    KnowledgeGap = None  # type: ignore
    LearningPath = None  # type: ignore
    MasteryLevel = None  # type: ignore
    RemediationPlan = None  # type: ignore
    ReReadRecommendation = None  # type: ignore
    SessionMode = None  # type: ignore
    SessionState = None  # type: ignore
    SessionStatus = None  # type: ignore
    SuitabilityScore = None  # type: ignore
    TriggerType = None  # type: ignore
    UnlockStatus = None  # type: ignore

try:  # Sequencer and auxiliary scorers (should be pure or lazily import DB)
    from src.adaptive.path_sequencer import PathSequencer  # type: ignore
except Exception:  # pragma: no cover
    PathSequencer = None  # type: ignore

try:
    from src.adaptive.remediation_router import RemediationRouter  # type: ignore
except Exception:  # pragma: no cover
    RemediationRouter = None  # type: ignore

try:
    from src.adaptive.suitability_scorer import SuitabilityScorer  # type: ignore
except Exception:  # pragma: no cover
    SuitabilityScorer = None  # type: ignore

try:
    from src.adaptive.jit_generator import (  # type: ignore
        ContentType,
        GenerationRequest,
        GenerationResult,
        GenerationTrigger,
        JITGenerationService,
    )
except Exception:  # pragma: no cover
    JITGenerationService = None  # type: ignore
    GenerationRequest = None  # type: ignore
    GenerationResult = None  # type: ignore
    GenerationTrigger = None  # type: ignore
    ContentType = None  # type: ignore

try:  # NCDE Struggle Weight Update Functions
    from src.adaptive.ncde_pipeline import (  # type: ignore
        StruggleUpdateData,
        prepare_struggle_update,
        update_struggle_weight_async,
        update_struggle_weight_sync,
    )
except Exception:  # pragma: no cover
    StruggleUpdateData = None  # type: ignore
    prepare_struggle_update = None  # type: ignore
    update_struggle_weight_async = None  # type: ignore
    update_struggle_weight_sync = None  # type: ignore

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
    # JIT Generation
    "JITGenerationService",
    "GenerationRequest",
    "GenerationResult",
    "GenerationTrigger",
    "ContentType",
    # NCDE Struggle Weight Update
    "StruggleUpdateData",
    "prepare_struggle_update",
    "update_struggle_weight_async",
    "update_struggle_weight_sync",
]
