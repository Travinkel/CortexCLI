# SQLAlchemy models
from .base import Base
from .staging import (
    StgNotionFlashcard,
    StgNotionConcept,
    StgNotionConceptArea,
    StgNotionConceptCluster,
    StgNotionModule,
    StgNotionTrack,
    StgNotionProgram,
)
from .canonical import (
    CleanConceptArea,
    CleanConceptCluster,
    CleanConcept,
    CleanProgram,
    CleanTrack,
    CleanModule,
    CleanAtom,
    ReviewQueueItem,
    SyncLog,
    CleaningLog,
    SemanticDuplicate,
    InferredPrerequisite,
    KnowledgeCluster,
    KnowledgeClusterMember,
    EmbeddingGenerationLog,
)
from .prerequisites import (
    ExplicitPrerequisite,
    PrerequisiteWaiver,
    QuestionPool,
)
from .quiz import (
    QuizQuestion,
    QuizDefinition,
    QuizPassage,
)
from .adaptive import (
    LearnerMasteryState,
    LearningPathSession,
    SessionAtomResponse,
    AtomTypeSuitability,
    RemediationEvent,
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
]
