"""
Adaptive Learning Data Models.

Dataclasses for the adaptive learning engine, used for passing data
between components without database coupling.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Optional
from uuid import UUID


class MasteryLevel(str, Enum):
    """Mastery level categories based on combined mastery score."""
    NOVICE = "novice"           # < 0.40
    DEVELOPING = "developing"   # 0.40 - 0.64
    PROFICIENT = "proficient"   # 0.65 - 0.84
    MASTERY = "mastery"         # >= 0.85

    @classmethod
    def from_score(cls, score: float) -> "MasteryLevel":
        """Convert mastery score to level."""
        if score >= 0.85:
            return cls.MASTERY
        elif score >= 0.65:
            return cls.PROFICIENT
        elif score >= 0.40:
            return cls.DEVELOPING
        return cls.NOVICE


class GatingType(str, Enum):
    """Types of prerequisite gating."""
    SOFT = "soft"   # Warning shown, access allowed
    HARD = "hard"   # Access blocked until threshold met


class TriggerType(str, Enum):
    """What triggered a remediation event."""
    INCORRECT_ANSWER = "incorrect_answer"
    LOW_CONFIDENCE = "low_confidence"
    PREREQUISITE_GAP = "prerequisite_gap"
    MANUAL = "manual"


class SessionMode(str, Enum):
    """Learning session modes."""
    ADAPTIVE = "adaptive"       # Full adaptive with remediation
    REVIEW = "review"           # Review due items only
    QUIZ = "quiz"               # Quiz mode (no hints)
    REMEDIATION = "remediation" # Focused remediation


class SessionStatus(str, Enum):
    """Learning session status."""
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"
    ABANDONED = "abandoned"


@dataclass
class KnowledgeBreakdown:
    """Breakdown of mastery by knowledge type."""
    dec_score: float = 0.0   # Declarative (0-10)
    proc_score: float = 0.0  # Procedural (0-10)
    app_score: float = 0.0   # Application (0-10)

    def to_dict(self) -> dict:
        return {
            "declarative": self.dec_score,
            "procedural": self.proc_score,
            "application": self.app_score,
        }


@dataclass
class ConceptMastery:
    """Complete mastery state for a concept."""
    concept_id: UUID
    concept_name: str
    review_mastery: float = 0.0
    quiz_mastery: float = 0.0
    combined_mastery: float = 0.0
    knowledge_breakdown: KnowledgeBreakdown = field(default_factory=KnowledgeBreakdown)
    is_unlocked: bool = False
    unlock_reason: Optional[str] = None
    review_count: int = 0
    quiz_attempt_count: int = 0
    last_review_at: Optional[datetime] = None
    last_quiz_at: Optional[datetime] = None

    @property
    def mastery_level(self) -> MasteryLevel:
        return MasteryLevel.from_score(self.combined_mastery)

    def to_dict(self) -> dict:
        return {
            "concept_id": str(self.concept_id),
            "concept_name": self.concept_name,
            "review_mastery": self.review_mastery,
            "quiz_mastery": self.quiz_mastery,
            "combined_mastery": self.combined_mastery,
            "mastery_level": self.mastery_level.value,
            "knowledge_breakdown": self.knowledge_breakdown.to_dict(),
            "is_unlocked": self.is_unlocked,
            "unlock_reason": self.unlock_reason,
            "review_count": self.review_count,
            "quiz_attempt_count": self.quiz_attempt_count,
        }


@dataclass
class BlockingPrerequisite:
    """A prerequisite that is blocking access to a concept."""
    concept_id: UUID
    concept_name: str
    required_mastery: float
    current_mastery: float
    gating_type: GatingType

    @property
    def mastery_gap(self) -> float:
        return max(0, self.required_mastery - self.current_mastery)

    @property
    def progress_percent(self) -> float:
        if self.required_mastery <= 0:
            return 100.0
        return min(100, (self.current_mastery / self.required_mastery) * 100)


@dataclass
class UnlockStatus:
    """Status of concept unlock for a learner."""
    is_unlocked: bool
    blocking_prerequisites: list[BlockingPrerequisite] = field(default_factory=list)
    unlock_reason: Optional[str] = None
    estimated_atoms_to_unlock: int = 0

    @property
    def max_mastery_gap(self) -> float:
        if not self.blocking_prerequisites:
            return 0.0
        return max(p.mastery_gap for p in self.blocking_prerequisites)


@dataclass
class KnowledgeGap:
    """A detected knowledge gap requiring remediation."""
    concept_id: UUID
    concept_name: str
    current_mastery: float
    required_mastery: float
    priority: str = "medium"  # high, medium, low
    recommended_atoms: list[UUID] = field(default_factory=list)
    estimated_duration_minutes: int = 0

    @property
    def gap_size(self) -> float:
        return max(0, self.required_mastery - self.current_mastery)


@dataclass
class RemediationPlan:
    """Plan for addressing a knowledge gap."""
    gap_concept_id: UUID
    gap_concept_name: str
    atoms: list[UUID]
    priority: str = "medium"
    gating_type: GatingType = GatingType.SOFT
    mastery_target: float = 0.65
    estimated_duration_minutes: int = 0
    trigger_type: TriggerType = TriggerType.PREREQUISITE_GAP
    trigger_atom_id: Optional[UUID] = None


@dataclass
class LearningPath:
    """Optimal learning path to master a concept."""
    target_concept_id: UUID
    target_concept_name: str
    prerequisites_to_complete: list[ConceptMastery]
    path_atoms: list[UUID]
    estimated_atoms: int = 0
    estimated_duration_minutes: int = 0
    current_mastery: float = 0.0
    target_mastery: float = 0.85

    @property
    def mastery_to_gain(self) -> float:
        return max(0, self.target_mastery - self.current_mastery)


@dataclass
class ContentFeatures:
    """Extracted features from content for suitability scoring."""
    word_count: int = 0
    sentence_count: int = 0
    char_count: int = 0

    # Structure features
    has_cli_commands: bool = False
    cli_command_count: int = 0
    has_definition_list: bool = False
    list_item_count: int = 0
    has_numbered_steps: bool = False
    step_count: int = 0
    has_bold_terms: bool = False
    technical_term_count: int = 0
    has_comparison_table: bool = False
    comparison_keyword_count: int = 0
    has_code_block: bool = False
    code_line_count: int = 0

    # Semantic features
    concept_count: int = 0
    has_alternatives: bool = False  # Multiple valid approaches
    is_factual: bool = False        # Pure fact recall
    is_procedural: bool = False     # Step-by-step process
    is_conceptual: bool = False     # Relationships/understanding

    def to_dict(self) -> dict:
        return {
            "word_count": self.word_count,
            "sentence_count": self.sentence_count,
            "has_cli_commands": self.has_cli_commands,
            "cli_command_count": self.cli_command_count,
            "has_definition_list": self.has_definition_list,
            "list_item_count": self.list_item_count,
            "has_numbered_steps": self.has_numbered_steps,
            "technical_term_count": self.technical_term_count,
            "has_comparison_table": self.has_comparison_table,
            "has_code_block": self.has_code_block,
        }


@dataclass
class SuitabilityScore:
    """Suitability score for a single atom type."""
    atom_type: str
    score: float              # 0-1 combined score
    knowledge_signal: float   # Primary: knowledge type contribution
    structure_signal: float   # Secondary: content structure contribution
    length_signal: float      # Tertiary: length appropriateness
    confidence: float = 0.0
    reasoning: str = ""


@dataclass
class AtomSuitability:
    """Complete suitability analysis for an atom."""
    atom_id: UUID
    current_type: str
    recommended_type: str
    recommendation_confidence: float
    type_mismatch: bool
    scores: dict[str, SuitabilityScore] = field(default_factory=dict)
    content_features: ContentFeatures = field(default_factory=ContentFeatures)

    def get_score(self, atom_type: str) -> float:
        """Get suitability score for a specific atom type."""
        if atom_type in self.scores:
            return self.scores[atom_type].score
        return 0.0


@dataclass
class AtomPresentation:
    """Atom prepared for presentation to learner."""
    atom_id: UUID
    atom_type: str
    front: str
    back: Optional[str] = None
    content_json: Optional[dict] = None
    concept_id: Optional[UUID] = None
    concept_name: Optional[str] = None
    is_remediation: bool = False
    remediation_for: Optional[str] = None  # Concept name if remediation

    def to_dict(self) -> dict:
        return {
            "atom_id": str(self.atom_id),
            "atom_type": self.atom_type,
            "front": self.front,
            "back": self.back,
            "content_json": self.content_json,
            "concept_name": self.concept_name,
            "is_remediation": self.is_remediation,
            "remediation_for": self.remediation_for,
        }


@dataclass
class AnswerResult:
    """Result of answering an atom."""
    is_correct: bool
    score: float = 0.0  # For partial credit
    explanation: Optional[str] = None
    correct_answer: Optional[str] = None
    remediation_triggered: bool = False
    remediation_plan: Optional[RemediationPlan] = None


@dataclass
class SessionProgress:
    """Progress within a learning session."""
    atoms_completed: int = 0
    atoms_remaining: int = 0
    atoms_correct: int = 0
    atoms_incorrect: int = 0
    current_mastery: float = 0.0
    mastery_gained: float = 0.0
    time_elapsed_seconds: int = 0
    remediation_count: int = 0

    @property
    def accuracy(self) -> float:
        total = self.atoms_correct + self.atoms_incorrect
        if total > 0:
            return (self.atoms_correct / total) * 100
        return 0.0


@dataclass
class SessionState:
    """Complete state of a learning session."""
    session_id: UUID
    learner_id: str
    mode: SessionMode
    status: SessionStatus
    target_concept_name: Optional[str] = None
    target_cluster_name: Optional[str] = None
    progress: SessionProgress = field(default_factory=SessionProgress)
    current_atom: Optional[AtomPresentation] = None
    next_atom: Optional[AtomPresentation] = None
    active_remediation: Optional[RemediationPlan] = None
    started_at: Optional[datetime] = None

    @property
    def is_active(self) -> bool:
        return self.status == SessionStatus.ACTIVE


# Knowledge type affinity matrix for suitability scoring
KNOWLEDGE_TYPE_AFFINITY: dict[str, dict[str, float]] = {
    "factual": {
        "flashcard": 1.0,
        "cloze": 0.9,
        "true_false": 0.7,
        "mcq": 0.6,
        "matching": 0.8,
        "parsons": 0.2,
        "compare": 0.4,
        "ranking": 0.3,
        "sequence": 0.3,
    },
    "conceptual": {
        "flashcard": 0.6,
        "cloze": 0.5,
        "true_false": 0.6,
        "mcq": 0.9,
        "matching": 0.7,
        "parsons": 0.3,
        "compare": 1.0,
        "ranking": 0.6,
        "sequence": 0.4,
    },
    "procedural": {
        "flashcard": 0.3,
        "cloze": 0.4,
        "true_false": 0.3,
        "mcq": 0.5,
        "matching": 0.4,
        "parsons": 1.0,
        "compare": 0.5,
        "ranking": 0.9,
        "sequence": 1.0,
    },
}

# Atom type to knowledge type mapping (for breakdown calculation)
ATOM_TYPE_KNOWLEDGE_MAP: dict[str, str] = {
    "flashcard": "declarative",
    "cloze": "declarative",
    "true_false": "declarative",
    "parsons": "procedural",
    "sequence": "procedural",
    "ranking": "procedural",
    "mcq": "application",
    "problem": "application",
    "compare": "application",
    "matching": "application",
}

# Mastery thresholds by prerequisite type
MASTERY_THRESHOLDS: dict[str, float] = {
    "foundation": 0.40,
    "integration": 0.65,
    "mastery": 0.85,
}

# Mastery weights
MASTERY_WEIGHTS = {
    "review": 0.625,  # 62.5%
    "quiz": 0.375,    # 37.5%
}

# Knowledge type passing scores
PASSING_SCORES: dict[str, float] = {
    "factual": 0.70,
    "conceptual": 0.80,
    "procedural": 0.85,
    "metacognitive": 0.75,
}


# ============================================================================
# Reading Progress Models
# ============================================================================

@dataclass
class ChapterReadingProgress:
    """Track reading progress for a module/chapter."""
    module_id: UUID
    module_name: str
    chapter_number: int
    is_read: bool = False
    read_at: Optional[datetime] = None
    comprehension_level: str = "not_started"  # not_started, skimmed, read, studied

    def to_dict(self) -> dict:
        return {
            "module_id": str(self.module_id),
            "module_name": self.module_name,
            "chapter_number": self.chapter_number,
            "is_read": self.is_read,
            "read_at": self.read_at.isoformat() if self.read_at else None,
            "comprehension_level": self.comprehension_level,
        }


@dataclass
class ReReadRecommendation:
    """Recommendation to re-read a chapter based on low mastery."""
    module_id: UUID
    module_name: str
    chapter_number: int
    reason: str
    current_mastery: float
    target_mastery: float
    priority: str = "medium"  # high, medium, low
    concepts_needing_review: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "module_id": str(self.module_id),
            "module_name": self.module_name,
            "chapter_number": self.chapter_number,
            "reason": self.reason,
            "current_mastery": self.current_mastery,
            "target_mastery": self.target_mastery,
            "priority": self.priority,
            "concepts_needing_review": self.concepts_needing_review,
        }


# Comprehension levels for reading progress
COMPREHENSION_LEVELS = {
    "not_started": 0.0,
    "skimmed": 0.25,
    "read": 0.50,
    "studied": 0.75,
    "mastered": 1.0,
}
