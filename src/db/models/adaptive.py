"""
Adaptive Learning Engine Models.

SQLAlchemy models for the Phase 5 adaptive learning system:
- Learner mastery state tracking
- Learning path sessions
- Atom type suitability scoring
- Remediation events
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import Boolean, ForeignKey, Index, Integer, Numeric, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base


class LearnerMasteryState(Base):
    """
    Tracks current mastery state per learner per concept.

    Mastery is computed as: 62.5% review + 37.5% quiz performance.
    Knowledge breakdown tracks declarative, procedural, and application mastery separately.
    """

    __tablename__ = "learner_mastery_state"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    learner_id: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    concept_id: Mapped[UUID] = mapped_column(
        ForeignKey("concepts.id", ondelete="CASCADE"), nullable=False
    )

    # Mastery scores (0-1 scale)
    review_mastery: Mapped[Decimal | None] = mapped_column(Numeric(5, 4), default=0)
    quiz_mastery: Mapped[Decimal | None] = mapped_column(Numeric(5, 4), default=0)
    combined_mastery: Mapped[Decimal | None] = mapped_column(Numeric(5, 4), default=0)

    # Knowledge type breakdown (0-10 scale, matches concepts)
    dec_score: Mapped[Decimal | None] = mapped_column(Numeric(4, 2), default=0)
    proc_score: Mapped[Decimal | None] = mapped_column(Numeric(4, 2), default=0)
    app_score: Mapped[Decimal | None] = mapped_column(Numeric(4, 2), default=0)

    # Activity tracking
    last_review_at: Mapped[datetime | None] = mapped_column()
    last_quiz_at: Mapped[datetime | None] = mapped_column()
    review_count: Mapped[int] = mapped_column(Integer, default=0)
    quiz_attempt_count: Mapped[int] = mapped_column(Integer, default=0)

    # Unlock state
    is_unlocked: Mapped[bool] = mapped_column(Boolean, default=False)
    unlock_reason: Mapped[str | None] = mapped_column(
        Text
    )  # 'mastery', 'waiver', 'prerequisite_met', 'no_prerequisites'
    unlocked_at: Mapped[datetime | None] = mapped_column()

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(default=func.now())
    updated_at: Mapped[datetime] = mapped_column(default=func.now(), onupdate=func.now())

    # Relationships
    concept: Mapped[CleanConcept] = relationship(back_populates="learner_mastery_states")

    __table_args__ = (
        UniqueConstraint("learner_id", "concept_id", name="uq_learner_concept"),
        Index("idx_mastery_state_unlocked", "learner_id", "is_unlocked"),
        Index("idx_mastery_state_combined", "combined_mastery"),
    )

    def __repr__(self) -> str:
        return f"<LearnerMasteryState learner={self.learner_id} concept={self.concept_id} mastery={self.combined_mastery}>"

    @property
    def mastery_level(self) -> str:
        """Return mastery level category."""
        mastery = float(self.combined_mastery or 0)
        if mastery >= 0.85:
            return "mastery"
        elif mastery >= 0.65:
            return "proficient"
        elif mastery >= 0.40:
            return "developing"
        return "novice"


class LearningPathSession(Base):
    """
    Tracks adaptive learning sessions.

    A session represents a learner working through atoms towards a goal
    (concept mastery, cluster completion, etc.) with adaptive sequencing
    and just-in-time remediation.
    """

    __tablename__ = "learning_path_sessions"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    learner_id: Mapped[str] = mapped_column(Text, nullable=False, index=True)

    # Session scope (one of these should be set)
    target_concept_id: Mapped[UUID | None] = mapped_column(ForeignKey("concepts.id"))
    target_cluster_id: Mapped[UUID | None] = mapped_column(ForeignKey("concept_clusters.id"))
    target_module_id: Mapped[UUID | None] = mapped_column(ForeignKey("learning_modules.id"))

    # Session configuration
    session_mode: Mapped[str] = mapped_column(
        Text, default="adaptive"
    )  # 'adaptive', 'review', 'quiz', 'remediation'

    # Session state
    status: Mapped[str] = mapped_column(
        Text, default="active"
    )  # 'active', 'paused', 'completed', 'abandoned'
    started_at: Mapped[datetime] = mapped_column(default=func.now())
    completed_at: Mapped[datetime | None] = mapped_column()
    paused_at: Mapped[datetime | None] = mapped_column()

    # Progress tracking
    atoms_presented: Mapped[int] = mapped_column(Integer, default=0)
    atoms_correct: Mapped[int] = mapped_column(Integer, default=0)
    atoms_incorrect: Mapped[int] = mapped_column(Integer, default=0)
    atoms_skipped: Mapped[int] = mapped_column(Integer, default=0)
    remediation_count: Mapped[int] = mapped_column(Integer, default=0)

    # Time tracking
    total_time_seconds: Mapped[int] = mapped_column(Integer, default=0)
    avg_response_time_ms: Mapped[int | None] = mapped_column(Integer)

    # Sequencing
    current_atom_id: Mapped[UUID | None] = mapped_column(ForeignKey("learning_atoms.id"))
    atom_sequence: Mapped[list | None] = mapped_column(ARRAY(PG_UUID(as_uuid=True)))
    completed_atoms: Mapped[list | None] = mapped_column(ARRAY(PG_UUID(as_uuid=True)))

    # Remediation tracking
    remediation_atoms: Mapped[list | None] = mapped_column(ARRAY(PG_UUID(as_uuid=True)))
    gap_concepts: Mapped[list | None] = mapped_column(ARRAY(PG_UUID(as_uuid=True)))

    # Mastery progress
    initial_mastery: Mapped[Decimal | None] = mapped_column(Numeric(5, 4))
    final_mastery: Mapped[Decimal | None] = mapped_column(Numeric(5, 4))
    mastery_gained: Mapped[Decimal | None] = mapped_column(Numeric(5, 4))

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(default=func.now())
    updated_at: Mapped[datetime] = mapped_column(default=func.now(), onupdate=func.now())

    # Relationships
    target_concept: Mapped[CleanConcept | None] = relationship(foreign_keys=[target_concept_id])
    target_cluster: Mapped[CleanConceptCluster | None] = relationship(
        foreign_keys=[target_cluster_id]
    )
    target_module: Mapped[CleanModule | None] = relationship(foreign_keys=[target_module_id])
    current_atom: Mapped[CleanAtom | None] = relationship(foreign_keys=[current_atom_id])
    responses: Mapped[list[SessionAtomResponse]] = relationship(
        back_populates="session", cascade="all, delete-orphan"
    )
    remediation_events: Mapped[list[RemediationEvent]] = relationship(back_populates="session")

    __table_args__ = (
        Index("idx_path_session_status", "status"),
        Index("idx_path_session_active", "learner_id", "status"),
    )

    def __repr__(self) -> str:
        return f"<LearningPathSession id={self.id} learner={self.learner_id} status={self.status}>"

    @property
    def accuracy(self) -> float:
        """Calculate session accuracy percentage."""
        if self.atoms_presented and self.atoms_presented > 0:
            return (self.atoms_correct / self.atoms_presented) * 100
        return 0.0

    @property
    def is_active(self) -> bool:
        return self.status == "active"


class SessionAtomResponse(Base):
    """
    Individual atom responses within a learning session.

    Tracks each question-answer interaction including timing,
    confidence, and whether it was part of remediation.
    """

    __tablename__ = "session_atom_responses"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    session_id: Mapped[UUID] = mapped_column(
        ForeignKey("learning_path_sessions.id", ondelete="CASCADE"), nullable=False
    )
    atom_id: Mapped[UUID] = mapped_column(ForeignKey("learning_atoms.id"), nullable=False)

    # Response details
    is_correct: Mapped[bool | None] = mapped_column(Boolean)
    score: Mapped[Decimal | None] = mapped_column(Numeric(5, 4))  # For partial credit (0-1)
    response_content: Mapped[dict | None] = mapped_column(JSONB)  # The actual response
    time_spent_ms: Mapped[int | None] = mapped_column(Integer)
    confidence_rating: Mapped[int | None] = mapped_column(Integer)  # Self-reported 1-5

    # Context
    was_remediation: Mapped[bool] = mapped_column(Boolean, default=False)
    attempt_number: Mapped[int] = mapped_column(Integer, default=1)
    presented_at: Mapped[datetime] = mapped_column(default=func.now())
    answered_at: Mapped[datetime | None] = mapped_column()

    # Feedback shown
    feedback_shown: Mapped[bool] = mapped_column(Boolean, default=False)
    hint_level_used: Mapped[int] = mapped_column(
        Integer, default=0
    )  # 0=none, 1=hint1, 2=hint2, 3=answer

    created_at: Mapped[datetime] = mapped_column(default=func.now())

    # Relationships
    session: Mapped[LearningPathSession] = relationship(back_populates="responses")
    atom: Mapped[CleanAtom] = relationship()

    __table_args__ = (
        Index("idx_atom_response_session", "session_id"),
        Index("idx_atom_response_atom", "atom_id"),
    )

    def __repr__(self) -> str:
        return f"<SessionAtomResponse session={self.session_id} atom={self.atom_id} correct={self.is_correct}>"


class AtomTypeSuitability(Base):
    """
    Pre-computed suitability scores for atoms across all types.

    Suitability = (knowledge_weight x 0.6) + (structure_weight x 0.3) + (length_weight x 0.1)

    Helps identify atoms that might be better served as a different type
    and provides transparency into the scoring process.
    """

    __tablename__ = "atom_type_suitability"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    atom_id: Mapped[UUID] = mapped_column(
        ForeignKey("learning_atoms.id", ondelete="CASCADE"), nullable=False, unique=True
    )

    # Suitability scores per type (0-1)
    flashcard_score: Mapped[Decimal | None] = mapped_column(Numeric(4, 3))
    cloze_score: Mapped[Decimal | None] = mapped_column(Numeric(4, 3))
    mcq_score: Mapped[Decimal | None] = mapped_column(Numeric(4, 3))
    true_false_score: Mapped[Decimal | None] = mapped_column(Numeric(4, 3))
    matching_score: Mapped[Decimal | None] = mapped_column(Numeric(4, 3))
    parsons_score: Mapped[Decimal | None] = mapped_column(Numeric(4, 3))
    compare_score: Mapped[Decimal | None] = mapped_column(Numeric(4, 3))
    ranking_score: Mapped[Decimal | None] = mapped_column(Numeric(4, 3))
    sequence_score: Mapped[Decimal | None] = mapped_column(Numeric(4, 3))

    # Best type recommendation
    recommended_type: Mapped[str | None] = mapped_column(Text)
    current_type: Mapped[str | None] = mapped_column(Text)  # The type it was actually generated as
    recommendation_confidence: Mapped[Decimal | None] = mapped_column(Numeric(4, 3))
    type_mismatch: Mapped[bool] = mapped_column(Boolean, default=False)

    # Scoring signals (for debugging/transparency)
    knowledge_signal: Mapped[Decimal | None] = mapped_column(
        Numeric(4, 3)
    )  # Primary: knowledge type alignment
    structure_signal: Mapped[Decimal | None] = mapped_column(
        Numeric(4, 3)
    )  # Secondary: content structure
    length_signal: Mapped[Decimal | None] = mapped_column(Numeric(4, 3))  # Tertiary: content length

    # Content features used in scoring
    content_features: Mapped[dict | None] = mapped_column(JSONB)

    # Computation metadata
    computed_at: Mapped[datetime] = mapped_column(default=func.now())
    computation_method: Mapped[str] = mapped_column(
        Text, default="rule_based"
    )  # 'rule_based', 'ai_scored', 'hybrid'

    # Relationships
    atom: Mapped[CleanAtom] = relationship(back_populates="suitability")

    __table_args__ = (Index("idx_suitability_mismatch", "type_mismatch"),)

    def __repr__(self) -> str:
        return f"<AtomTypeSuitability atom={self.atom_id} recommended={self.recommended_type}>"

    def get_scores_dict(self) -> dict:
        """Return all suitability scores as a dictionary."""
        return {
            "flashcard": float(self.flashcard_score or 0),
            "cloze": float(self.cloze_score or 0),
            "mcq": float(self.mcq_score or 0),
            "true_false": float(self.true_false_score or 0),
            "matching": float(self.matching_score or 0),
            "parsons": float(self.parsons_score or 0),
            "compare": float(self.compare_score or 0),
            "ranking": float(self.ranking_score or 0),
            "sequence": float(self.sequence_score or 0),
        }


class RemediationEvent(Base):
    """
    Tracks just-in-time remediation events.

    When a learner fails an atom or shows low mastery in a prerequisite,
    the system can trigger remediation. This table tracks the trigger,
    the remediation provided, and the outcome.
    """

    __tablename__ = "remediation_events"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    session_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("learning_path_sessions.id", ondelete="SET NULL")
    )
    learner_id: Mapped[str] = mapped_column(Text, nullable=False, index=True)

    # What triggered remediation
    trigger_atom_id: Mapped[UUID | None] = mapped_column(ForeignKey("learning_atoms.id"))
    trigger_concept_id: Mapped[UUID | None] = mapped_column(ForeignKey("concepts.id"))
    trigger_type: Mapped[str] = mapped_column(
        Text, nullable=False
    )  # 'incorrect_answer', 'low_confidence', 'prerequisite_gap', 'manual'

    # Gap detected
    gap_concept_id: Mapped[UUID] = mapped_column(ForeignKey("concepts.id"), nullable=False)
    mastery_at_trigger: Mapped[Decimal | None] = mapped_column(Numeric(5, 4))
    required_mastery: Mapped[Decimal | None] = mapped_column(Numeric(5, 4))
    mastery_gap: Mapped[Decimal | None] = mapped_column(Numeric(5, 4))
    gating_type: Mapped[str | None] = mapped_column(Text)  # 'soft', 'hard'

    # Remediation provided
    remediation_atoms: Mapped[list | None] = mapped_column(ARRAY(PG_UUID(as_uuid=True)))
    remediation_concept_ids: Mapped[list | None] = mapped_column(ARRAY(PG_UUID(as_uuid=True)))
    remediation_started_at: Mapped[datetime] = mapped_column(default=func.now())
    remediation_completed_at: Mapped[datetime | None] = mapped_column()

    # Outcome
    atoms_completed: Mapped[int] = mapped_column(Integer, default=0)
    atoms_correct: Mapped[int] = mapped_column(Integer, default=0)
    post_remediation_mastery: Mapped[Decimal | None] = mapped_column(Numeric(5, 4))
    mastery_improvement: Mapped[Decimal | None] = mapped_column(Numeric(5, 4))
    remediation_successful: Mapped[bool | None] = mapped_column(
        Boolean
    )  # Did mastery reach threshold?

    # User choice
    was_skipped: Mapped[bool] = mapped_column(Boolean, default=False)
    skip_reason: Mapped[str | None] = mapped_column(Text)

    created_at: Mapped[datetime] = mapped_column(default=func.now())

    # Relationships
    session: Mapped[LearningPathSession | None] = relationship(back_populates="remediation_events")
    trigger_atom: Mapped[CleanAtom | None] = relationship(foreign_keys=[trigger_atom_id])
    trigger_concept: Mapped[CleanConcept | None] = relationship(foreign_keys=[trigger_concept_id])
    gap_concept: Mapped[CleanConcept] = relationship(foreign_keys=[gap_concept_id])

    __table_args__ = (
        Index("idx_remediation_gap", "gap_concept_id"),
        Index("idx_remediation_session", "session_id"),
        Index("idx_remediation_trigger", "trigger_type"),
    )

    def __repr__(self) -> str:
        return f"<RemediationEvent learner={self.learner_id} gap={self.gap_concept_id} success={self.remediation_successful}>"

    @property
    def is_complete(self) -> bool:
        return self.remediation_completed_at is not None

    @property
    def accuracy(self) -> float:
        """Calculate remediation accuracy."""
        if self.atoms_completed and self.atoms_completed > 0:
            return (self.atoms_correct / self.atoms_completed) * 100
        return 0.0


class RemediationNote(Base):
    """
    LLM-generated study notes for weak sections.

    Notes are generated when learners struggle with a section,
    and their effectiveness is tracked to improve over time.
    """

    __tablename__ = "remediation_notes"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    section_id: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    module_number: Mapped[int] = mapped_column(Integer, nullable=False)

    # Content
    title: Mapped[str] = mapped_column(Text, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)  # Markdown
    source_hash: Mapped[str | None] = mapped_column(Text)  # SHA256 of source material

    # Quality metrics
    read_count: Mapped[int] = mapped_column(Integer, default=0)
    user_rating: Mapped[int | None] = mapped_column(Integer)  # 1-5
    pre_error_rate: Mapped[Decimal | None] = mapped_column(Numeric(5, 4))
    post_error_rate: Mapped[Decimal | None] = mapped_column(Numeric(5, 4))

    # Gating
    qualified: Mapped[bool] = mapped_column(Boolean, default=True)
    is_stale: Mapped[bool] = mapped_column(Boolean, default=False)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(default=func.now())
    last_read_at: Mapped[datetime | None] = mapped_column()
    expires_at: Mapped[datetime | None] = mapped_column()

    # Relationships
    read_history: Mapped[list["NoteReadHistory"]] = relationship(back_populates="note")

    __table_args__ = (
        Index("idx_remediation_notes_section", "section_id"),
        Index("idx_remediation_notes_qualified", "qualified", "is_stale"),
        Index("idx_remediation_notes_module", "module_number"),
    )

    def __repr__(self) -> str:
        return f"<RemediationNote section={self.section_id} qualified={self.qualified}>"

    @property
    def effectiveness(self) -> float | None:
        """Calculate effectiveness as improvement in error rate."""
        if self.pre_error_rate is not None and self.post_error_rate is not None:
            return float(self.pre_error_rate - self.post_error_rate)
        return None

    @property
    def is_effective(self) -> bool:
        """Check if note has proven effective (reduces errors)."""
        eff = self.effectiveness
        return eff is not None and eff > 0.1  # At least 10% improvement


class NoteReadHistory(Base):
    """
    Tracks when notes were read and their effectiveness.
    """

    __tablename__ = "note_read_history"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    note_id: Mapped[UUID] = mapped_column(
        ForeignKey("remediation_notes.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[str] = mapped_column(Text, default="default")
    read_at: Mapped[datetime] = mapped_column(default=func.now())
    rating: Mapped[int | None] = mapped_column(Integer)  # 1-5

    # Error rates at time of reading
    section_error_rate_before: Mapped[Decimal | None] = mapped_column(Numeric(5, 4))
    section_error_rate_after: Mapped[Decimal | None] = mapped_column(Numeric(5, 4))

    # Relationship
    note: Mapped[RemediationNote] = relationship(back_populates="read_history")

    __table_args__ = (
        Index("idx_note_read_history_note", "note_id"),
        Index("idx_note_read_history_user", "user_id"),
    )


class StruggleWeight(Base):
    """
    User-declared struggle areas for study prioritization.

    Static weights are imported from struggles.yaml.
    NCDE weights are updated dynamically during study sessions.
    """

    __tablename__ = "struggle_weights"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    module_number: Mapped[int] = mapped_column(Integer, nullable=False)
    section_id: Mapped[str | None] = mapped_column(Text)  # NULL means entire module

    # Static configuration
    severity: Mapped[str] = mapped_column(Text, default="medium")  # critical, high, medium, low
    weight: Mapped[Decimal] = mapped_column(Numeric(3, 2), default=0.5)  # 0.0-1.0
    failure_modes: Mapped[list | None] = mapped_column(ARRAY(Text))
    notes: Mapped[str | None] = mapped_column(Text)

    # Dynamic NCDE adjustments
    ncde_weight: Mapped[Decimal | None] = mapped_column(Numeric(3, 2))  # From real-time diagnosis
    last_diagnosis_at: Mapped[datetime | None] = mapped_column()

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(default=func.now())
    updated_at: Mapped[datetime] = mapped_column(default=func.now(), onupdate=func.now())

    # Relationships
    history: Mapped[list["StruggleWeightHistory"]] = relationship(
        back_populates="struggle_weight",
        foreign_keys="StruggleWeightHistory.module_number",
        primaryjoin="and_(StruggleWeight.module_number==foreign(StruggleWeightHistory.module_number), "
        "or_(StruggleWeight.section_id==foreign(StruggleWeightHistory.section_id), "
        "and_(StruggleWeight.section_id.is_(None), StruggleWeightHistory.section_id.is_(None))))",
        viewonly=True,
    )

    __table_args__ = (
        UniqueConstraint("module_number", "section_id", name="uq_struggle_module_section"),
        Index("idx_struggle_weights_module", "module_number"),
        Index("idx_struggle_weights_section", "section_id"),
        Index("idx_struggle_weights_severity", "severity"),
    )

    def __repr__(self) -> str:
        return f"<StruggleWeight module={self.module_number} section={self.section_id} severity={self.severity}>"

    @property
    def priority_score(self) -> float:
        """Calculate combined priority score."""
        static = float(self.weight or 0.5)
        ncde = float(self.ncde_weight or 0.0)
        return static * 3.0 + ncde * 2.0

    @property
    def severity_weight(self) -> float:
        """Convert severity to numeric weight."""
        mapping = {"critical": 1.0, "high": 0.75, "medium": 0.5, "low": 0.25}
        return mapping.get(self.severity, 0.5)


class StruggleWeightHistory(Base):
    """
    Audit trail of all struggle weight changes.

    Records every update from NCDE diagnosis, YAML imports, manual changes, and decay.
    Enables tracking learning progress over time.
    """

    __tablename__ = "struggle_weight_history"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    module_number: Mapped[int] = mapped_column(Integer, nullable=False)
    section_id: Mapped[str | None] = mapped_column(Text)

    # Snapshot of weights at this point
    static_weight: Mapped[Decimal | None] = mapped_column(Numeric(3, 2))
    ncde_weight: Mapped[Decimal | None] = mapped_column(Numeric(3, 2))
    combined_priority: Mapped[Decimal | None] = mapped_column(Numeric(5, 3))

    # What triggered this update
    trigger_type: Mapped[str] = mapped_column(
        Text, nullable=False
    )  # 'ncde_diagnosis', 'yaml_import', 'manual', 'decay'
    failure_mode: Mapped[str | None] = mapped_column(Text)  # Which failure mode detected
    atom_id: Mapped[UUID | None] = mapped_column(ForeignKey("learning_atoms.id"))

    # Performance snapshot
    session_accuracy: Mapped[Decimal | None] = mapped_column(Numeric(3, 2))  # 0-1
    cumulative_accuracy: Mapped[Decimal | None] = mapped_column(Numeric(3, 2))  # 0-1
    error_count: Mapped[int] = mapped_column(Integer, default=0)

    # Session context
    session_id: Mapped[UUID | None] = mapped_column(ForeignKey("learning_path_sessions.id"))

    created_at: Mapped[datetime] = mapped_column(default=func.now())

    # Relationships
    atom: Mapped[CleanAtom | None] = relationship(foreign_keys=[atom_id])
    session: Mapped[LearningPathSession | None] = relationship(foreign_keys=[session_id])
    struggle_weight: Mapped[StruggleWeight | None] = relationship(
        back_populates="history",
        foreign_keys=[module_number],
        primaryjoin="and_(foreign(StruggleWeightHistory.module_number)==StruggleWeight.module_number, "
        "or_(foreign(StruggleWeightHistory.section_id)==StruggleWeight.section_id, "
        "and_(StruggleWeightHistory.section_id.is_(None), StruggleWeight.section_id.is_(None))))",
        viewonly=True,
    )

    __table_args__ = (
        Index("idx_swh_module", "module_number"),
        Index("idx_swh_section", "section_id"),
        Index("idx_swh_created", "created_at"),
        Index("idx_swh_trigger", "trigger_type"),
        Index("idx_swh_module_time", "module_number", "created_at"),
    )

    def __repr__(self) -> str:
        return f"<StruggleWeightHistory module={self.module_number} trigger={self.trigger_type} ncde={self.ncde_weight}>"


# Forward references for type hints
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .canonical import CleanAtom, CleanConcept, CleanConceptCluster, CleanModule
