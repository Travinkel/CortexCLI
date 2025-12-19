"""
Prerequisite models for soft/hard gating.

Implements the prerequisite system with:
- Explicit prerequisites (soft/hard gating)
- Prerequisite waivers for exceptional cases
- Question pools for quiz randomization

Gating Types:
- soft: Warning shown but access allowed
- hard: Access blocked until mastery threshold met

Mastery Thresholds (from right-learning research):
- foundation: 0.40 (basic exposure sufficient)
- integration: 0.65 (solid understanding required) - DEFAULT
- mastery: 0.85 (expert level required)
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import Boolean, ForeignKey, Integer, Numeric, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base

if TYPE_CHECKING:
    from .canonical import CleanAtom, CleanConcept, CleanConceptCluster


class ExplicitPrerequisite(Base):
    """
    Explicit prerequisite relationship with soft/hard gating.

    A prerequisite links a source (concept or atom) to a target concept that
    must be mastered before access is allowed (hard) or recommended (soft).

    Attributes:
        gating_type: 'soft' (warning only) or 'hard' (blocked until mastery)
        mastery_threshold: Required mastery level (0-1 scale)
        mastery_type: Category affecting default threshold (foundation/integration/mastery)
        origin: How the prerequisite was created (explicit/tag/inferred/imported)
        anki_tag: Tag format for Anki sync (tag:prereq:domain:topic:subtopic)
    """

    __tablename__ = "explicit_prerequisites"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )

    # Source: The concept/atom that requires the prerequisite
    source_concept_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("concepts.id", ondelete="CASCADE")
    )
    source_atom_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("learning_atoms.id", ondelete="CASCADE")
    )

    # Target: The prerequisite concept that must be mastered
    target_concept_id: Mapped[UUID] = mapped_column(
        ForeignKey("concepts.id", ondelete="CASCADE"), nullable=False
    )

    # Gating configuration
    gating_type: Mapped[str] = mapped_column(Text, nullable=False)  # 'soft' or 'hard'
    mastery_threshold: Mapped[Decimal] = mapped_column(Numeric(3, 2), default=Decimal("0.65"))
    mastery_type: Mapped[str] = mapped_column(
        Text, default="integration"
    )  # foundation/integration/mastery

    # Origin tracking
    origin: Mapped[str] = mapped_column(Text, default="explicit")
    anki_tag: Mapped[str | None] = mapped_column(Text)

    # Review workflow
    status: Mapped[str] = mapped_column(Text, default="active")
    created_by: Mapped[str | None] = mapped_column(Text)
    approved_by: Mapped[str | None] = mapped_column(Text)
    approved_at: Mapped[datetime | None] = mapped_column()
    notes: Mapped[str | None] = mapped_column(Text)

    created_at: Mapped[datetime] = mapped_column(default=func.now())
    updated_at: Mapped[datetime] = mapped_column(default=func.now(), onupdate=func.now())

    # Relationships
    source_concept: Mapped[CleanConcept | None] = relationship(
        "CleanConcept", foreign_keys=[source_concept_id], back_populates="prerequisites_as_source"
    )
    source_atom: Mapped[CleanAtom | None] = relationship(
        "CleanAtom", foreign_keys=[source_atom_id], back_populates="explicit_prerequisites"
    )
    target_concept: Mapped[CleanConcept] = relationship(
        "CleanConcept", foreign_keys=[target_concept_id], back_populates="prerequisites_as_target"
    )
    waivers: Mapped[list[PrerequisiteWaiver]] = relationship(
        back_populates="prerequisite", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        source = (
            f"concept:{self.source_concept_id}"
            if self.source_concept_id
            else f"atom:{self.source_atom_id}"
        )
        return f"<ExplicitPrerequisite({source} -> concept:{self.target_concept_id}, {self.gating_type})>"

    @property
    def is_soft(self) -> bool:
        """Check if this is a soft-gating prerequisite."""
        return self.gating_type == "soft"

    @property
    def is_hard(self) -> bool:
        """Check if this is a hard-gating prerequisite."""
        return self.gating_type == "hard"

    @property
    def has_active_waiver(self) -> bool:
        """Check if there's an active (non-expired) waiver."""
        now = datetime.utcnow()
        return any(w.expires_at is None or w.expires_at > now for w in self.waivers)

    def get_threshold_for_type(self) -> Decimal:
        """Get the default threshold based on mastery_type."""
        thresholds = {
            "foundation": Decimal("0.40"),
            "integration": Decimal("0.65"),
            "mastery": Decimal("0.85"),
        }
        return thresholds.get(self.mastery_type, Decimal("0.65"))


class PrerequisiteWaiver(Base):
    """
    Waiver for bypassing a prerequisite.

    Used for:
    - Instructor-granted waivers (prior knowledge)
    - Challenge waivers (passed assessment)
    - External credentials (certificates, transfer credit)
    - Accelerated learners (>95% on all prerequisites)

    Attributes:
        waiver_type: Category of waiver (instructor/challenge/external/accelerated)
        evidence_type: Type of supporting evidence
        evidence_details: JSON with evidence specifics
        expires_at: Optional expiration date
    """

    __tablename__ = "prerequisite_waivers"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    prerequisite_id: Mapped[UUID] = mapped_column(
        ForeignKey("explicit_prerequisites.id", ondelete="CASCADE"), nullable=False
    )

    # Waiver type
    waiver_type: Mapped[str] = mapped_column(Text, nullable=False)

    # Evidence
    evidence_type: Mapped[str | None] = mapped_column(Text)
    evidence_details: Mapped[dict | None] = mapped_column(JSONB)

    # Audit trail
    granted_by: Mapped[str | None] = mapped_column(Text)
    granted_at: Mapped[datetime] = mapped_column(default=func.now())
    expires_at: Mapped[datetime | None] = mapped_column()
    notes: Mapped[str | None] = mapped_column(Text)

    created_at: Mapped[datetime] = mapped_column(default=func.now())

    # Relationships
    prerequisite: Mapped[ExplicitPrerequisite] = relationship(back_populates="waivers")

    def __repr__(self) -> str:
        return f"<PrerequisiteWaiver(prereq:{self.prerequisite_id}, type:{self.waiver_type})>"

    @property
    def is_expired(self) -> bool:
        """Check if the waiver has expired."""
        if self.expires_at is None:
            return False
        return datetime.utcnow() > self.expires_at

    @property
    def is_active(self) -> bool:
        """Check if the waiver is currently active."""
        return not self.is_expired


class QuestionPool(Base):
    """
    Named pool for quiz question grouping and selection.

    Questions in the same pool can be randomly selected for quiz attempts,
    ensuring variety across multiple attempts while maintaining topic coverage.

    Attributes:
        name: Display name for the pool
        target_difficulty: Target difficulty level (0-1)
        min_questions: Minimum questions needed for quiz generation
    """

    __tablename__ = "question_pools"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )

    name: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)

    # Scope
    concept_id: Mapped[UUID | None] = mapped_column(ForeignKey("concepts.id", ondelete="SET NULL"))
    concept_cluster_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("concept_clusters.id", ondelete="SET NULL")
    )

    # Pool metadata
    target_difficulty: Mapped[Decimal | None] = mapped_column(Numeric(3, 2))
    min_questions: Mapped[int] = mapped_column(Integer, default=5)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(default=func.now())
    updated_at: Mapped[datetime] = mapped_column(default=func.now(), onupdate=func.now())

    # Relationships
    concept: Mapped[CleanConcept | None] = relationship("CleanConcept")
    concept_cluster: Mapped[CleanConceptCluster | None] = relationship("CleanConceptCluster")
    questions: Mapped[list[QuizQuestion]] = relationship(
        "QuizQuestion", back_populates="pool", foreign_keys="QuizQuestion.pool_id"
    )

    def __repr__(self) -> str:
        return f"<QuestionPool(name={self.name}, questions={len(self.questions) if self.questions else 0})>"

    @property
    def question_count(self) -> int:
        """Get number of active questions in pool."""
        if not self.questions:
            return 0
        return sum(1 for q in self.questions if q.is_active)

    @property
    def has_sufficient_questions(self) -> bool:
        """Check if pool has minimum required questions."""
        return self.question_count >= self.min_questions


# Import QuizQuestion for type hints (avoid circular import)
from .quiz import QuizQuestion  # noqa: E402
