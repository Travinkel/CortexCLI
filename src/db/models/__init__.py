# SQLAlchemy models
from .adaptive import (
    AtomTypeSuitability,
    LearnerMasteryState,
    LearningPathSession,
    NoteReadHistory,
    RemediationEvent,
    RemediationNote,
    SessionAtomResponse,
    StruggleWeight,
    StruggleWeightHistory,
)
from .base import Base
from .canonical import (
    CleanAtom,
    CleanConcept,
    CleanConceptArea,
    CleanConceptCluster,
    CleaningLog,
    CleanModule,
    CleanProgram,
    CleanTrack,
    EmbeddingGenerationLog,
    InferredPrerequisite,
    KnowledgeCluster,
    KnowledgeClusterMember,
    ReviewQueueItem,
    SemanticDuplicate,
    SyncLog,
)
from .prerequisites import (
    ExplicitPrerequisite,
    PrerequisiteWaiver,
    QuestionPool,
)
from .quiz import (
    QuizDefinition,
    QuizPassage,
    QuizQuestion,
)
from .staging import (
    StgNotionConcept,
    StgNotionConceptArea,
    StgNotionConceptCluster,
    StgNotionFlashcard,
    StgNotionModule,
    StgNotionProgram,
    StgNotionTrack,
)

__all__ = [
    # Base
    "Base",
    # Staging
    "StgNotionFlashcard",
    "StgNotionConcept",
    "StgNotionConceptArea",
    "StgNotionConceptCluster",
    "StgNotionModule",
    "StgNotionTrack",
    "StgNotionProgram",
    # Canonical
    "CleanConceptArea",
    "CleanConceptCluster",
    "CleanConcept",
    "CleanProgram",
    "CleanTrack",
    "CleanModule",
    "CleanAtom",
    "ReviewQueueItem",
    "SyncLog",
    "CleaningLog",
    # Semantic (Phase 2.5)
    "SemanticDuplicate",
    "InferredPrerequisite",
    "KnowledgeCluster",
    "KnowledgeClusterMember",
    "EmbeddingGenerationLog",
    # Prerequisites (Phase 3)
    "ExplicitPrerequisite",
    "PrerequisiteWaiver",
    "QuestionPool",
    # Quiz (Phase 3)
    "QuizQuestion",
    "QuizDefinition",
    "QuizPassage",
    # Adaptive Learning (Phase 5)
    "LearnerMasteryState",
    "LearningPathSession",
    "SessionAtomResponse",
    "AtomTypeSuitability",
    "RemediationEvent",
    # Remediation Notes (Phase 6)
    "RemediationNote",
    "NoteReadHistory",
    # Struggle Tracking (Dynamic)
    "StruggleWeight",
    "StruggleWeightHistory",
]
