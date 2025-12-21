"""
Canonical table models for clean, validated output.

These tables contain the trusted data that has passed through the cleaning pipeline.
They are the source of truth for all consumers (personal use, Anki, right-learning).
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import (
    ARRAY,
    JSON,
    Boolean,
    Date,
    ForeignKey,
    Integer,
    LargeBinary,
    Numeric,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base

# ========================================
# KNOWLEDGE HIERARCHY
# ========================================


class CleanConceptArea(Base):
    """L0: Top-level knowledge domains (e.g., "Computer Science", "Mathematics")."""

    __tablename__ = "clean_concept_areas"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    notion_id: Mapped[str | None] = mapped_column(Text, unique=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    domain: Mapped[str | None] = mapped_column(Text)
    display_order: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(default=func.now())
    updated_at: Mapped[datetime] = mapped_column(default=func.now(), onupdate=func.now())

    # Relationships
    clusters: Mapped[list[CleanConceptCluster]] = relationship(back_populates="concept_area")


class CleanConceptCluster(Base):
    """L1: Thematic groupings under a ConceptArea."""

    __tablename__ = "concept_clusters"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    notion_id: Mapped[str | None] = mapped_column(Text, unique=True)
    concept_area_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("clean_concept_areas.id", ondelete="SET NULL")
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    exam_weight: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    display_order: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(default=func.now())
    updated_at: Mapped[datetime] = mapped_column(default=func.now(), onupdate=func.now())

    # Relationships
    concept_area: Mapped[CleanConceptArea | None] = relationship(back_populates="clusters")
    concepts: Mapped[list[CleanConcept]] = relationship(back_populates="cluster")


class CleanConcept(Base):
    """L2: Atomic knowledge units (leaf-level concepts)."""

    __tablename__ = "concepts"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    notion_id: Mapped[str | None] = mapped_column(Text, unique=True)
    cluster_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("concept_clusters.id", ondelete="SET NULL")
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    definition: Mapped[str | None] = mapped_column(Text)
    domain: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text, default="to_learn")
    dec_score: Mapped[Decimal | None] = mapped_column(Numeric(4, 2))  # Declarative 0-10
    proc_score: Mapped[Decimal | None] = mapped_column(Numeric(4, 2))  # Procedural 0-10
    app_score: Mapped[Decimal | None] = mapped_column(Numeric(4, 2))  # Application 0-10
    last_reviewed_at: Mapped[datetime | None] = mapped_column()
    created_at: Mapped[datetime] = mapped_column(default=func.now())
    updated_at: Mapped[datetime] = mapped_column(default=func.now(), onupdate=func.now())

    # Semantic Embeddings (Phase 2.5) - stored as BYTEA (serialized numpy array)
    embedding: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    embedding_model: Mapped[str | None] = mapped_column(Text, default="all-MiniLM-L6-v2")
    embedding_generated_at: Mapped[datetime | None] = mapped_column()

    # Relationships
    cluster: Mapped[CleanConceptCluster | None] = relationship(back_populates="concepts")
    atoms: Mapped[list[CleanAtom]] = relationship(back_populates="concept")
    inferred_as_prerequisite: Mapped[list[InferredPrerequisite]] = relationship(
        back_populates="target_concept", foreign_keys="InferredPrerequisite.target_concept_id"
    )
    # Explicit Prerequisites (Phase 3) - concept as source
    prerequisites_as_source: Mapped[list[ExplicitPrerequisite]] = relationship(
        "ExplicitPrerequisite",
        back_populates="source_concept",
        foreign_keys="ExplicitPrerequisite.source_concept_id",
    )
    # Explicit Prerequisites (Phase 3) - concept as target
    prerequisites_as_target: Mapped[list[ExplicitPrerequisite]] = relationship(
        "ExplicitPrerequisite",
        back_populates="target_concept",
        foreign_keys="ExplicitPrerequisite.target_concept_id",
    )

    # Adaptive Learning (Phase 5) - learner mastery states
    learner_mastery_states: Mapped[list[LearnerMasteryState]] = relationship(
        "LearnerMasteryState", back_populates="concept"
    )


# ========================================
# CURRICULUM STRUCTURE
# ========================================


class CleanProgram(Base):
    """Top-level learning path (e.g., degree, certification)."""

    __tablename__ = "clean_programs"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    notion_id: Mapped[str | None] = mapped_column(Text, unique=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text, default="active")
    start_date: Mapped[date | None] = mapped_column(Date)
    end_date: Mapped[date | None] = mapped_column(Date)
    created_at: Mapped[datetime] = mapped_column(default=func.now())
    updated_at: Mapped[datetime] = mapped_column(default=func.now(), onupdate=func.now())

    # Relationships
    tracks: Mapped[list[CleanTrack]] = relationship(back_populates="program")


class CleanTrack(Base):
    """Course-level progression within a program."""

    __tablename__ = "clean_tracks"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    notion_id: Mapped[str | None] = mapped_column(Text, unique=True)
    program_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("clean_programs.id", ondelete="SET NULL")
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    display_order: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(default=func.now())
    updated_at: Mapped[datetime] = mapped_column(default=func.now(), onupdate=func.now())

    # Relationships
    program: Mapped[CleanProgram | None] = relationship(back_populates="tracks")
    modules: Mapped[list[CleanModule]] = relationship(back_populates="track")


class CleanModule(Base):
    """Week/chapter level unit within a track."""

    __tablename__ = "learning_modules"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    notion_id: Mapped[str | None] = mapped_column(Text, unique=True)
    track_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("clean_tracks.id", ondelete="SET NULL")
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    week_order: Mapped[int | None] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(Text, default="not_started")
    created_at: Mapped[datetime] = mapped_column(default=func.now())
    updated_at: Mapped[datetime] = mapped_column(default=func.now(), onupdate=func.now())

    # Relationships
    track: Mapped[CleanTrack | None] = relationship(back_populates="modules")
    atoms: Mapped[list[CleanAtom]] = relationship(back_populates="module")


# ========================================
# LEARNING ATOMS
# ========================================


class CleanAtom(Base):
    """Clean, validated flashcard or other learning content."""

    __tablename__ = "learning_atoms"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    notion_id: Mapped[str | None] = mapped_column(Text)
    card_id: Mapped[str | None] = mapped_column(Text, unique=True)  # e.g., "NET-M1-015-DEC"

    # Content (legacy front/back for backward compatibility)
    atom_type: Mapped[str] = mapped_column(Text, nullable=False, default="flashcard")
    front: Mapped[str] = mapped_column(Text, nullable=False)
    back: Mapped[str | None] = mapped_column(Text)
    media_type: Mapped[str | None] = mapped_column(Text)
    media_code: Mapped[str | None] = mapped_column(Text)
    derived_from_visual: Mapped[bool] = mapped_column(Boolean, default=False)

    # POLYMORPHIC CONTENT (replaces front/back for new atom types)
    # Stores atom-type-specific content as JSONB (prompt, options, code, etc.)
    content: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    # Stores grading configuration as JSONB (mode, correct_answer, pattern, etc.)
    grading_logic: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    # ICAP Framework (replaces Bloom's Taxonomy)
    # Engagement mode: passive, active, constructive, interactive
    engagement_mode: Mapped[str | None] = mapped_column(Text, default="active")
    # Element interactivity: 0.0-1.0 cognitive load factor
    element_interactivity: Mapped[Decimal | None] = mapped_column(Numeric(3, 2), default=0.5)
    # Knowledge dimension: factual, conceptual, procedural, metacognitive
    knowledge_dimension: Mapped[str | None] = mapped_column(Text, default="factual")

    # Atom ownership: cortex (terminal) or greenlight (IDE/runtime)
    owner: Mapped[str] = mapped_column(Text, default="cortex")

    # Relationships
    concept_id: Mapped[UUID | None] = mapped_column(ForeignKey("concepts.id", ondelete="SET NULL"))
    module_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("learning_modules.id", ondelete="SET NULL")
    )

    # Quality metadata
    quality_score: Mapped[Decimal | None] = mapped_column(Numeric(3, 2))
    is_atomic: Mapped[bool] = mapped_column(Boolean, default=True)
    front_word_count: Mapped[int | None] = mapped_column(Integer)
    back_word_count: Mapped[int | None] = mapped_column(Integer)
    atomicity_status: Mapped[str | None] = mapped_column(Text)  # 'atomic', 'verbose', 'needs_split'

    # Review status
    needs_review: Mapped[bool] = mapped_column(Boolean, default=False)
    rewrite_count: Mapped[int] = mapped_column(Integer, default=0)
    last_rewrite_at: Mapped[datetime | None] = mapped_column()

    # Anki sync
    anki_note_id: Mapped[int | None] = mapped_column()
    anki_card_id: Mapped[int | None] = mapped_column()
    anki_deck: Mapped[str | None] = mapped_column(Text)
    anki_exported_at: Mapped[datetime | None] = mapped_column()

    # Anki review stats (pulled back)
    anki_ease_factor: Mapped[Decimal | None] = mapped_column(Numeric(4, 3))
    anki_interval_days: Mapped[int | None] = mapped_column(Integer)
    anki_review_count: Mapped[int] = mapped_column(Integer, default=0)
    anki_lapses: Mapped[int] = mapped_column(Integer, default=0)
    anki_last_review: Mapped[datetime | None] = mapped_column()
    anki_due_date: Mapped[date | None] = mapped_column(Date)

    # FSRS metrics
    stability_days: Mapped[Decimal | None] = mapped_column(Numeric(8, 2))
    retrievability: Mapped[Decimal | None] = mapped_column(Numeric(5, 4))

    # Source tracking
    source: Mapped[str] = mapped_column(Text, default="notion")
    batch_id: Mapped[str | None] = mapped_column(Text)

    # --- FIDELITY TRACKING (Hydration Audit) ---
    # is_hydrated: True if atom uses AI-generated scenario NOT in source text
    is_hydrated: Mapped[bool] = mapped_column(Boolean, default=False)
    # fidelity_type: Content origin classification
    # Values: 'verbatim_extract', 'rephrased_fact', 'ai_scenario_enrichment'
    fidelity_type: Mapped[str | None] = mapped_column(Text, default="verbatim_extract")
    # source_fact_basis: The exact raw fact from source used as anchor for AI scenarios
    source_fact_basis: Mapped[str | None] = mapped_column(Text)

    # Semantic Embeddings (Phase 2.5) - stored as BYTEA (serialized numpy array)
    embedding: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    embedding_model: Mapped[str | None] = mapped_column(Text, default="all-MiniLM-L6-v2")
    embedding_generated_at: Mapped[datetime | None] = mapped_column()

    created_at: Mapped[datetime] = mapped_column(default=func.now())
    updated_at: Mapped[datetime] = mapped_column(default=func.now(), onupdate=func.now())

    # Relationships
    concept: Mapped[CleanConcept | None] = relationship(back_populates="atoms")
    module: Mapped[CleanModule | None] = relationship(back_populates="atoms")

    # Semantic relationships (Phase 2.5)
    duplicate_pairs_as_first: Mapped[list[SemanticDuplicate]] = relationship(
        back_populates="atom_1", foreign_keys="SemanticDuplicate.atom_id_1"
    )
    duplicate_pairs_as_second: Mapped[list[SemanticDuplicate]] = relationship(
        back_populates="atom_2", foreign_keys="SemanticDuplicate.atom_id_2"
    )
    inferred_prerequisites: Mapped[list[InferredPrerequisite]] = relationship(
        back_populates="source_atom", foreign_keys="InferredPrerequisite.source_atom_id"
    )
    cluster_memberships: Mapped[list[KnowledgeClusterMember]] = relationship(back_populates="atom")

    # Explicit Prerequisites (Phase 3) - atom as source
    explicit_prerequisites: Mapped[list[ExplicitPrerequisite]] = relationship(
        "ExplicitPrerequisite",
        back_populates="source_atom",
        foreign_keys="ExplicitPrerequisite.source_atom_id",
    )

    # Quiz Question (Phase 3) - one-to-one with quiz_questions table
    quiz_question: Mapped[QuizQuestion | None] = relationship(
        "QuizQuestion", back_populates="atom", uselist=False
    )

    # Adaptive Learning (Phase 5) - suitability scores
    suitability: Mapped[AtomTypeSuitability | None] = relationship(
        "AtomTypeSuitability", back_populates="atom", uselist=False
    )


# ========================================
# REVIEW QUEUE
# ========================================


class ReviewQueueItem(Base):
    """AI-generated content pending manual approval."""

    __tablename__ = "review_queue"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )

    # Content
    atom_type: Mapped[str] = mapped_column(Text, nullable=False, default="flashcard")
    front: Mapped[str] = mapped_column(Text, nullable=False)
    back: Mapped[str | None] = mapped_column(Text)
    concept_id: Mapped[UUID | None] = mapped_column(ForeignKey("concepts.id", ondelete="SET NULL"))
    module_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("learning_modules.id", ondelete="SET NULL")
    )

    # Original (before rewrite)
    original_front: Mapped[str | None] = mapped_column(Text)
    original_back: Mapped[str | None] = mapped_column(Text)
    original_atom_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("learning_atoms.id", ondelete="SET NULL")
    )

    # Review workflow
    status: Mapped[str] = mapped_column(Text, default="pending")
    source: Mapped[str] = mapped_column(Text, nullable=False)
    batch_id: Mapped[str | None] = mapped_column(Text)

    # Quality metrics
    quality_score: Mapped[Decimal | None] = mapped_column(Numeric(3, 2))
    ai_confidence: Mapped[Decimal | None] = mapped_column(Numeric(3, 2))
    rewrite_reason: Mapped[str | None] = mapped_column(Text)

    # After approval
    approved_at: Mapped[datetime | None] = mapped_column()
    approved_atom_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("learning_atoms.id", ondelete="SET NULL")
    )
    reviewer_notes: Mapped[str | None] = mapped_column(Text)

    created_at: Mapped[datetime] = mapped_column(default=func.now())


# ========================================
# LOGS
# ========================================


class SyncLog(Base):
    """Audit log for sync operations."""

    __tablename__ = "sync_log"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    sync_type: Mapped[str] = mapped_column(Text, nullable=False)
    started_at: Mapped[datetime] = mapped_column(default=func.now())
    completed_at: Mapped[datetime | None] = mapped_column()
    status: Mapped[str] = mapped_column(Text, default="running")
    items_processed: Mapped[int] = mapped_column(Integer, default=0)
    items_added: Mapped[int] = mapped_column(Integer, default=0)
    items_updated: Mapped[int] = mapped_column(Integer, default=0)
    items_removed: Mapped[int] = mapped_column(Integer, default=0)
    error_message: Mapped[str | None] = mapped_column(Text)
    details: Mapped[dict | None] = mapped_column(JSON)


class CleaningLog(Base):
    """Audit log for cleaning operations."""

    __tablename__ = "cleaning_log"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    atom_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("learning_atoms.id", ondelete="CASCADE")
    )
    operation: Mapped[str] = mapped_column(Text, nullable=False)
    old_value: Mapped[dict | None] = mapped_column(JSON)
    new_value: Mapped[dict | None] = mapped_column(JSON)
    performed_at: Mapped[datetime] = mapped_column(default=func.now())


# ========================================
# SEMANTIC ANALYSIS (Phase 2.5)
# ========================================


class SemanticDuplicate(Base):
    """Detected pairs of semantically similar atoms (potential duplicates)."""

    __tablename__ = "semantic_duplicates"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )

    # Atom pair (ordered: atom_id_1 < atom_id_2)
    atom_id_1: Mapped[UUID] = mapped_column(
        ForeignKey("learning_atoms.id", ondelete="CASCADE"), nullable=False
    )
    atom_id_2: Mapped[UUID] = mapped_column(
        ForeignKey("learning_atoms.id", ondelete="CASCADE"), nullable=False
    )

    # Similarity metrics
    similarity_score: Mapped[Decimal] = mapped_column(Numeric(5, 4), nullable=False)
    detection_method: Mapped[str] = mapped_column(Text, default="embedding")

    # Review workflow
    status: Mapped[str] = mapped_column(Text, default="pending")
    reviewed_by: Mapped[str | None] = mapped_column(Text)
    reviewed_at: Mapped[datetime | None] = mapped_column()
    review_notes: Mapped[str | None] = mapped_column(Text)

    # Merge tracking
    merged_into_atom_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("learning_atoms.id", ondelete="SET NULL")
    )

    created_at: Mapped[datetime] = mapped_column(default=func.now())
    updated_at: Mapped[datetime] = mapped_column(default=func.now(), onupdate=func.now())

    # Relationships
    atom_1: Mapped[CleanAtom] = relationship(
        back_populates="duplicate_pairs_as_first", foreign_keys=[atom_id_1]
    )
    atom_2: Mapped[CleanAtom] = relationship(
        back_populates="duplicate_pairs_as_second", foreign_keys=[atom_id_2]
    )


class InferredPrerequisite(Base):
    """AI-suggested prerequisite relationships based on embedding similarity."""

    __tablename__ = "inferred_prerequisites"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )

    # The atom that needs this prerequisite
    source_atom_id: Mapped[UUID] = mapped_column(
        ForeignKey("learning_atoms.id", ondelete="CASCADE"), nullable=False
    )

    # The concept suggested as prerequisite
    target_concept_id: Mapped[UUID] = mapped_column(
        ForeignKey("concepts.id", ondelete="CASCADE"), nullable=False
    )

    # Similarity and confidence
    similarity_score: Mapped[Decimal] = mapped_column(Numeric(5, 4), nullable=False)
    confidence: Mapped[str] = mapped_column(Text, default="medium")
    inference_method: Mapped[str] = mapped_column(Text, default="embedding")

    # Evidence
    evidence_atoms: Mapped[list | None] = mapped_column(ARRAY(PG_UUID(as_uuid=True)))
    evidence_score: Mapped[Decimal | None] = mapped_column(Numeric(5, 4))

    # Review workflow
    status: Mapped[str] = mapped_column(Text, default="suggested")
    reviewed_by: Mapped[str | None] = mapped_column(Text)
    reviewed_at: Mapped[datetime | None] = mapped_column()
    review_notes: Mapped[str | None] = mapped_column(Text)

    created_at: Mapped[datetime] = mapped_column(default=func.now())
    updated_at: Mapped[datetime] = mapped_column(default=func.now(), onupdate=func.now())

    # Relationships
    source_atom: Mapped[CleanAtom] = relationship(
        back_populates="inferred_prerequisites", foreign_keys=[source_atom_id]
    )
    target_concept: Mapped[CleanConcept] = relationship(
        back_populates="inferred_as_prerequisite", foreign_keys=[target_concept_id]
    )


class KnowledgeCluster(Base):
    """Groups of semantically related learning atoms."""

    __tablename__ = "knowledge_clusters"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )

    # Metadata
    name: Mapped[str | None] = mapped_column(Text)
    description: Mapped[str | None] = mapped_column(Text)

    # Cluster centroid embedding - stored as BYTEA (serialized numpy array)
    centroid: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)

    # Clustering parameters
    cluster_method: Mapped[str] = mapped_column(Text, default="kmeans")
    cluster_params: Mapped[dict | None] = mapped_column(JSON)

    # Scope
    concept_area_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("clean_concept_areas.id", ondelete="SET NULL")
    )

    # Quality metrics
    silhouette_score: Mapped[Decimal | None] = mapped_column(Numeric(5, 4))
    intra_cluster_distance: Mapped[Decimal | None] = mapped_column(Numeric(8, 4))

    # Lifecycle
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(default=func.now())
    updated_at: Mapped[datetime] = mapped_column(default=func.now(), onupdate=func.now())

    # Relationships
    concept_area: Mapped[CleanConceptArea | None] = relationship()
    members: Mapped[list[KnowledgeClusterMember]] = relationship(back_populates="cluster")


class KnowledgeClusterMember(Base):
    """Junction table linking atoms to their knowledge clusters."""

    __tablename__ = "knowledge_cluster_members"

    cluster_id: Mapped[UUID] = mapped_column(
        ForeignKey("knowledge_clusters.id", ondelete="CASCADE"), primary_key=True
    )
    atom_id: Mapped[UUID] = mapped_column(
        ForeignKey("learning_atoms.id", ondelete="CASCADE"), primary_key=True
    )

    # Distance metrics
    distance_to_centroid: Mapped[Decimal | None] = mapped_column(Numeric(8, 4))
    membership_probability: Mapped[Decimal] = mapped_column(Numeric(5, 4), default=1.0)

    # Exemplar flag
    is_exemplar: Mapped[bool] = mapped_column(Boolean, default=False)

    created_at: Mapped[datetime] = mapped_column(default=func.now())

    # Relationships
    cluster: Mapped[KnowledgeCluster] = relationship(back_populates="members")
    atom: Mapped[CleanAtom] = relationship(back_populates="cluster_memberships")


class EmbeddingGenerationLog(Base):
    """Audit trail for embedding generation operations."""

    __tablename__ = "embedding_generation_log"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )

    # Batch identification
    batch_id: Mapped[str] = mapped_column(Text, nullable=False)
    source_table: Mapped[str] = mapped_column(Text, nullable=False)

    # Timing
    started_at: Mapped[datetime] = mapped_column(default=func.now())
    completed_at: Mapped[datetime | None] = mapped_column()
    status: Mapped[str] = mapped_column(Text, default="running")

    # Statistics
    total_records: Mapped[int] = mapped_column(Integer, default=0)
    records_processed: Mapped[int] = mapped_column(Integer, default=0)
    records_skipped: Mapped[int] = mapped_column(Integer, default=0)
    records_failed: Mapped[int] = mapped_column(Integer, default=0)

    # Configuration
    model_name: Mapped[str] = mapped_column(Text, default="all-MiniLM-L6-v2")
    batch_size: Mapped[int | None] = mapped_column(Integer)
    regenerate: Mapped[bool] = mapped_column(Boolean, default=False)

    # Error tracking
    error_message: Mapped[str | None] = mapped_column(Text)
    failed_record_ids: Mapped[list | None] = mapped_column(ARRAY(Text))

    details: Mapped[dict | None] = mapped_column(JSON)


# Forward references for Phase 3 & 5 models (resolved at runtime)
# These imports must be at the end to avoid circular imports
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .adaptive import (
        AtomTypeSuitability,
        LearnerMasteryState,
    )
    from .prerequisites import ExplicitPrerequisite
    from .quiz import QuizQuestion
