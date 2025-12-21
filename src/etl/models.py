"""
ETL Pipeline Data Models.

These models represent the data flowing through the ETL pipeline,
using ICAP Framework and polymorphic JSONB schema from the start.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID, uuid4


# =============================================================================
# ICAP Framework Enums (Replaces Bloom's Taxonomy)
# =============================================================================


class EngagementMode(str, Enum):
    """
    ICAP Framework engagement modes (Chi & Wylie, 2014).

    Higher modes = better retention and transfer.
    """
    PASSIVE = "passive"          # Receiving information (lowest retention)
    ACTIVE = "active"            # Manipulating without generating
    CONSTRUCTIVE = "constructive"  # Generating new output
    INTERACTIVE = "interactive"  # Co-creating knowledge (highest retention)


class KnowledgeDimension(str, Enum):
    """
    Knowledge Dimension (Krathwohl, 2002).

    Classifies WHAT is being learned.
    """
    FACTUAL = "factual"          # Terminology, specific details
    CONCEPTUAL = "conceptual"    # Classifications, principles, theories
    PROCEDURAL = "procedural"    # Skills, techniques, methods
    METACOGNITIVE = "metacognitive"  # Self-awareness, strategy selection


class GradingMode(str, Enum):
    """How to evaluate learner responses."""
    EXACT_MATCH = "exact_match"      # String comparison
    FUZZY_MATCH = "fuzzy_match"      # Similarity threshold
    REGEX = "regex"                  # Pattern matching
    ORDER_MATCH = "order_match"      # Sequence comparison (Parsons)
    SET_MATCH = "set_match"          # Unordered set (multiple select)
    NUMERIC = "numeric"              # Tolerance-based
    RUNTIME = "runtime"              # Unit test execution (Greenlight)
    RUBRIC = "rubric"                # LLM-graded
    HUMAN = "human"                  # Manual review


class AtomOwner(str, Enum):
    """Which system owns atom execution."""
    CORTEX = "cortex"      # Terminal-based execution
    GREENLIGHT = "greenlight"  # IDE/runtime execution


# =============================================================================
# Raw Extraction Models
# =============================================================================


@dataclass
class RawChunk:
    """
    Raw content chunk extracted from a source.

    This is the output of an Extractor, before any transformation.
    """
    chunk_id: str
    source_file: str
    source_type: str  # "ccna", "security", "prog", etc.

    # Content
    title: str
    content: str

    # Hierarchy
    module_number: int | None = None
    section_id: str | None = None
    parent_context: str | None = None

    # Metadata
    word_count: int = 0
    has_code: bool = False
    has_cli_commands: bool = False
    has_diagram: bool = False

    # Source tracking
    extracted_at: datetime = field(default_factory=datetime.now)
    extractor_version: str = "1.0.0"


# =============================================================================
# Transformed Atom Models
# =============================================================================


@dataclass
class DistractorOption:
    """
    A single answer option (correct or distractor).

    For MCQ, matching, and other selection-based atoms.
    """
    text: str
    is_correct: bool = False
    misconception_code: str | None = None  # Links to misconception_library
    selection_count: int = 0  # For psychometric tracking


@dataclass
class GradingLogic:
    """
    Type-specific grading rules stored as JSONB.

    The structure varies by atom_type, but always includes `mode`.
    """
    mode: GradingMode

    # For exact/fuzzy match
    correct_answer: str | None = None
    case_sensitive: bool = False

    # For order match (Parsons)
    correct_order: list[int] | None = None

    # For set match (multiple select)
    correct_set: set[str] | None = None

    # For numeric
    expected_value: float | None = None
    tolerance: float | None = None

    # For regex
    pattern: str | None = None

    # For runtime (Greenlight)
    test_command: str | None = None
    entrypoint: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Serialize to JSONB-compatible dict."""
        result = {"mode": self.mode.value}
        for k, v in self.__dict__.items():
            if k != "mode" and v is not None:
                if isinstance(v, set):
                    result[k] = list(v)
                elif isinstance(v, Enum):
                    result[k] = v.value
                else:
                    result[k] = v
        return result


@dataclass
class AtomContent:
    """
    Type-specific content payload stored as JSONB.

    Replaces the rigid front/back TEXT columns.
    """
    # Universal
    prompt: str

    # For flashcard/cloze
    answer: str | None = None

    # For MCQ/matching
    options: list[DistractorOption] | None = None

    # For Parsons
    blocks: list[str] | None = None
    distractors: list[str] | None = None
    starting_mode: str | None = None

    # For code atoms
    code: str | None = None
    language: str | None = None

    # For numeric
    unit: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Serialize to JSONB-compatible dict."""
        result = {"prompt": self.prompt}
        for k, v in self.__dict__.items():
            if k != "prompt" and v is not None:
                if isinstance(v, list) and v and isinstance(v[0], DistractorOption):
                    result[k] = [
                        {"text": opt.text, "is_correct": opt.is_correct,
                         "misconception_code": opt.misconception_code}
                        for opt in v
                    ]
                else:
                    result[k] = v
        return result


@dataclass
class TransformedAtom:
    """
    A fully transformed learning atom ready for loading.

    This is the output of the Transformer chain, before database insertion.
    Uses ICAP Framework and polymorphic JSONB schema.
    """
    # Identity
    id: UUID = field(default_factory=uuid4)
    card_id: str = ""
    atom_type: str = "flashcard"

    # POLYMORPHIC CONTENT (replaces front/back)
    content: AtomContent | None = None
    grading_logic: GradingLogic | None = None

    # ICAP Framework (replaces Bloom's)
    engagement_mode: EngagementMode = EngagementMode.ACTIVE
    element_interactivity: float = 0.5  # 0.0-1.0 (Cognitive Load Theory)
    knowledge_dimension: KnowledgeDimension = KnowledgeDimension.FACTUAL

    # Ownership
    owner: AtomOwner = AtomOwner.CORTEX

    # Skill linkage (many-to-many)
    skill_codes: list[str] = field(default_factory=list)
    primary_skill_code: str | None = None

    # Misconception tags
    misconception_codes: list[str] = field(default_factory=list)

    # Source tracking
    source_chunk_id: str | None = None
    source_file: str | None = None
    source_type: str | None = None

    # Fidelity tracking
    is_hydrated: bool = False
    fidelity_type: str = "verbatim_extract"
    source_fact_basis: str | None = None

    # Quality
    quality_score: float = 0.0
    validation_passed: bool = True
    validation_issues: list[str] = field(default_factory=list)

    # Metadata
    tags: list[str] = field(default_factory=list)
    estimated_duration_sec: int = 30

    # Timestamps
    generated_at: datetime = field(default_factory=datetime.now)

    # Legacy compatibility (to be removed after migration)
    @property
    def front(self) -> str:
        """Legacy accessor for front field."""
        return self.content.prompt if self.content else ""

    @property
    def back(self) -> str:
        """Legacy accessor for back field."""
        if self.content and self.content.answer:
            return self.content.answer
        if self.grading_logic and self.grading_logic.correct_answer:
            return self.grading_logic.correct_answer
        return ""

    def to_dict(self) -> dict[str, Any]:
        """Serialize to database-ready dict."""
        return {
            "id": str(self.id),
            "card_id": self.card_id,
            "atom_type": self.atom_type,
            "content": self.content.to_dict() if self.content else {},
            "grading_logic": self.grading_logic.to_dict() if self.grading_logic else {},
            "engagement_mode": self.engagement_mode.value,
            "element_interactivity": self.element_interactivity,
            "knowledge_dimension": self.knowledge_dimension.value,
            "owner": self.owner.value,
            "skill_codes": self.skill_codes,
            "primary_skill_code": self.primary_skill_code,
            "misconception_codes": self.misconception_codes,
            "source_chunk_id": self.source_chunk_id,
            "source_file": self.source_file,
            "source_type": self.source_type,
            "is_hydrated": self.is_hydrated,
            "fidelity_type": self.fidelity_type,
            "source_fact_basis": self.source_fact_basis,
            "quality_score": self.quality_score,
            "tags": self.tags,
            "estimated_duration_sec": self.estimated_duration_sec,
            # Legacy compatibility
            "front": self.front,
            "back": self.back,
        }


@dataclass
class AtomEnvelope:
    """
    Universal atom envelope for validation against JSON schema.

    This matches the structure defined in atom-envelope-v2.schema.json.
    """
    id: str
    atom_type: str
    owner: str
    grading_mode: str
    content: dict[str, Any]
    grading_logic: dict[str, Any]
    skills: list[dict[str, Any]] = field(default_factory=list)
    misconception_tags: list[str] = field(default_factory=list)
    runner_config: dict[str, Any] | None = None
    meta_cognitive_prompts: dict[str, bool] | None = None
