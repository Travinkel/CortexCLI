"""
Gating service for prerequisite access evaluation.

Provides access evaluation, waiver management, and mastery threshold
calculations for the prerequisite system.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Dict, List, Optional
from uuid import UUID

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.db.models import (
    ExplicitPrerequisite,
    PrerequisiteWaiver,
    CleanConcept,
    CleanAtom,
)


class AccessStatus(Enum):
    """Access status for gating evaluation."""
    ALLOWED = "allowed"  # No prerequisites or all met
    WARNING = "warning"  # Soft-gated prerequisites not met
    BLOCKED = "blocked"  # Hard-gated prerequisites not met
    WAIVED = "waived"    # Prerequisites waived


@dataclass
class BlockingPrerequisite:
    """Information about a prerequisite blocking access."""
    prerequisite_id: UUID
    target_concept_id: UUID
    target_concept_name: str
    gating_type: str
    required_mastery: Decimal
    current_mastery: Decimal | None
    mastery_gap: Decimal | None


@dataclass
class AccessResult:
    """Result of access evaluation."""
    status: AccessStatus
    can_access: bool
    message: str
    blocking_prerequisites: List[BlockingPrerequisite] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    waiver_applied: bool = False

    @property
    def has_warnings(self) -> bool:
        """Check if there are any warnings."""
        return len(self.warnings) > 0

    @property
    def is_blocked(self) -> bool:
        """Check if access is blocked."""
        return self.status == AccessStatus.BLOCKED


class GatingService:
    """
    Service for evaluating prerequisite access and managing waivers.

    Handles:
    - Access evaluation (allowed/warning/blocked)
    - Mastery threshold calculations
    - Waiver creation and validation
    - Blocking prerequisite identification
    """

    # Default mastery thresholds by type
    MASTERY_THRESHOLDS = {
        "foundation": Decimal("0.40"),
        "integration": Decimal("0.65"),
        "mastery": Decimal("0.85"),
    }

    def __init__(self, session: AsyncSession):
        self.session = session

    # ========================================
    # Access Evaluation
    # ========================================

    async def evaluate_access(
        self,
        concept_id: UUID | None = None,
        atom_id: UUID | None = None,
        user_mastery_data: Dict[UUID, float] | None = None,
    ) -> AccessResult:
        """
        Evaluate access to a concept or atom based on prerequisites.

        Args:
            concept_id: The concept to check access for
            atom_id: The atom to check access for
            user_mastery_data: Dict mapping concept_id -> mastery score (0-1)

        Returns:
            AccessResult with status and details
        """
        if concept_id is None and atom_id is None:
            return AccessResult(
                status=AccessStatus.ALLOWED,
                can_access=True,
                message="No target specified, access allowed",
            )

        user_mastery = user_mastery_data or {}

        # Get prerequisites
        prerequisites = await self._get_prerequisites(concept_id, atom_id)

        if not prerequisites:
            return AccessResult(
                status=AccessStatus.ALLOWED,
                can_access=True,
                message="No prerequisites required",
            )

        # Evaluate each prerequisite
        blocking_hard = []
        blocking_soft = []
        waived = False

        for prereq in prerequisites:
            # Check for active waiver
            if await self._has_active_waiver(prereq.id):
                waived = True
                continue

            # Get current mastery
            target_id = prereq.target_concept_id
            current_mastery = Decimal(str(user_mastery.get(target_id, 0)))
            required_mastery = prereq.mastery_threshold

            # Check if met
            if current_mastery >= required_mastery:
                continue

            # Not met - add to blocking list
            concept = await self._get_concept(target_id)
            blocking = BlockingPrerequisite(
                prerequisite_id=prereq.id,
                target_concept_id=target_id,
                target_concept_name=concept.name if concept else str(target_id),
                gating_type=prereq.gating_type,
                required_mastery=required_mastery,
                current_mastery=current_mastery,
                mastery_gap=required_mastery - current_mastery,
            )

            if prereq.gating_type == "hard":
                blocking_hard.append(blocking)
            else:
                blocking_soft.append(blocking)

        # Determine overall status
        if blocking_hard:
            return AccessResult(
                status=AccessStatus.BLOCKED,
                can_access=False,
                message=self._build_blocked_message(blocking_hard),
                blocking_prerequisites=blocking_hard + blocking_soft,
                waiver_applied=waived,
            )
        elif blocking_soft:
            return AccessResult(
                status=AccessStatus.WARNING,
                can_access=True,
                message="Access allowed with warnings",
                blocking_prerequisites=blocking_soft,
                warnings=[
                    f"Recommended prerequisite not met: {b.target_concept_name} "
                    f"(have {float(b.current_mastery):.0%}, need {float(b.required_mastery):.0%})"
                    for b in blocking_soft
                ],
                waiver_applied=waived,
            )
        elif waived:
            return AccessResult(
                status=AccessStatus.WAIVED,
                can_access=True,
                message="Access granted via waiver",
                waiver_applied=True,
            )
        else:
            return AccessResult(
                status=AccessStatus.ALLOWED,
                can_access=True,
                message="All prerequisites met",
            )

    async def _get_prerequisites(
        self,
        concept_id: UUID | None,
        atom_id: UUID | None,
    ) -> List[ExplicitPrerequisite]:
        """Get active prerequisites for a concept or atom."""
        conditions = [ExplicitPrerequisite.status == "active"]

        if concept_id:
            conditions.append(ExplicitPrerequisite.source_concept_id == concept_id)
        if atom_id:
            conditions.append(ExplicitPrerequisite.source_atom_id == atom_id)

        result = await self.session.execute(
            select(ExplicitPrerequisite)
            .options(selectinload(ExplicitPrerequisite.target_concept))
            .where(and_(*conditions))
        )
        return list(result.scalars().all())

    async def _get_concept(self, concept_id: UUID) -> CleanConcept | None:
        """Get a concept by ID."""
        result = await self.session.execute(
            select(CleanConcept).where(CleanConcept.id == concept_id)
        )
        return result.scalar_one_or_none()

    def _build_blocked_message(self, blocking: List[BlockingPrerequisite]) -> str:
        """Build a human-readable message for blocked access."""
        if len(blocking) == 1:
            b = blocking[0]
            return (
                f"Access blocked: Must master '{b.target_concept_name}' "
                f"(need {float(b.required_mastery):.0%}, have {float(b.current_mastery or 0):.0%})"
            )
        else:
            names = [b.target_concept_name for b in blocking]
            return f"Access blocked: Must master prerequisites: {', '.join(names)}"

    # ========================================
    # Blocking Prerequisites
    # ========================================

    async def get_blocking_prerequisites(
        self,
        concept_id: UUID | None = None,
        atom_id: UUID | None = None,
        user_mastery_data: Dict[UUID, float] | None = None,
    ) -> List[BlockingPrerequisite]:
        """
        Get list of prerequisites blocking access.

        Args:
            concept_id: The concept to check
            atom_id: The atom to check
            user_mastery_data: Dict mapping concept_id -> mastery score

        Returns:
            List of BlockingPrerequisite objects
        """
        result = await self.evaluate_access(concept_id, atom_id, user_mastery_data)
        return result.blocking_prerequisites

    # ========================================
    # Mastery Thresholds
    # ========================================

    def get_mastery_threshold(self, mastery_type: str) -> Decimal:
        """
        Get the mastery threshold for a type.

        Args:
            mastery_type: 'foundation', 'integration', or 'mastery'

        Returns:
            Threshold as Decimal (0-1)
        """
        return self.MASTERY_THRESHOLDS.get(
            mastery_type,
            self.MASTERY_THRESHOLDS["integration"]
        )

    def get_all_thresholds(self) -> Dict[str, Decimal]:
        """Get all mastery thresholds."""
        return dict(self.MASTERY_THRESHOLDS)

    # ========================================
    # Waiver Management
    # ========================================

    async def create_waiver(
        self,
        prerequisite_id: UUID,
        waiver_type: str,
        granted_by: str | None = None,
        evidence_type: str | None = None,
        evidence_details: dict | None = None,
        expires_at: datetime | None = None,
        notes: str | None = None,
    ) -> PrerequisiteWaiver:
        """
        Create a waiver for a prerequisite.

        Args:
            prerequisite_id: The prerequisite to waive
            waiver_type: 'instructor', 'challenge', 'external', or 'accelerated'
            granted_by: User granting the waiver
            evidence_type: Type of evidence (quiz_score, certificate, etc.)
            evidence_details: JSON with evidence specifics
            expires_at: Optional expiration date
            notes: Additional notes

        Returns:
            The created PrerequisiteWaiver
        """
        waiver = PrerequisiteWaiver(
            prerequisite_id=prerequisite_id,
            waiver_type=waiver_type,
            granted_by=granted_by,
            evidence_type=evidence_type,
            evidence_details=evidence_details,
            expires_at=expires_at,
            notes=notes,
        )

        self.session.add(waiver)
        await self.session.flush()
        return waiver

    async def get_waivers(
        self,
        prerequisite_id: UUID,
        include_expired: bool = False,
    ) -> List[PrerequisiteWaiver]:
        """
        Get waivers for a prerequisite.

        Args:
            prerequisite_id: The prerequisite ID
            include_expired: Include expired waivers

        Returns:
            List of waivers
        """
        query = select(PrerequisiteWaiver).where(
            PrerequisiteWaiver.prerequisite_id == prerequisite_id
        )

        if not include_expired:
            # Filter out expired waivers
            now = datetime.utcnow()
            query = query.where(
                (PrerequisiteWaiver.expires_at.is_(None)) |
                (PrerequisiteWaiver.expires_at > now)
            )

        query = query.order_by(PrerequisiteWaiver.granted_at.desc())

        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def _has_active_waiver(self, prerequisite_id: UUID) -> bool:
        """Check if a prerequisite has an active waiver."""
        waivers = await self.get_waivers(prerequisite_id, include_expired=False)
        return len(waivers) > 0

    async def validate_waiver(self, waiver_id: UUID) -> bool:
        """
        Validate if a waiver is still active.

        Args:
            waiver_id: The waiver ID

        Returns:
            True if waiver is valid (not expired)
        """
        result = await self.session.execute(
            select(PrerequisiteWaiver).where(PrerequisiteWaiver.id == waiver_id)
        )
        waiver = result.scalar_one_or_none()

        if not waiver:
            return False

        return waiver.is_active

    async def revoke_waiver(self, waiver_id: UUID) -> bool:
        """
        Revoke a waiver by deleting it.

        Args:
            waiver_id: The waiver ID

        Returns:
            True if waiver was deleted
        """
        result = await self.session.execute(
            select(PrerequisiteWaiver).where(PrerequisiteWaiver.id == waiver_id)
        )
        waiver = result.scalar_one_or_none()

        if not waiver:
            return False

        await self.session.delete(waiver)
        await self.session.flush()
        return True

    # ========================================
    # Challenge Waiver for High Performers
    # ========================================

    async def check_challenge_eligibility(
        self,
        concept_id: UUID,
        user_mastery_data: Dict[UUID, float],
        threshold: float = 0.95,
    ) -> bool:
        """
        Check if user is eligible for challenge waiver.

        Users performing at >= 95% on all prerequisites can challenge
        higher-level content without meeting formal prerequisites.

        Args:
            concept_id: The target concept
            user_mastery_data: Dict mapping concept_id -> mastery score
            threshold: Performance threshold (default 95%)

        Returns:
            True if eligible for challenge waiver
        """
        prerequisites = await self._get_prerequisites(concept_id, None)

        if not prerequisites:
            return False  # No prerequisites to waive

        for prereq in prerequisites:
            target_id = prereq.target_concept_id
            mastery = user_mastery_data.get(target_id, 0)

            if mastery < threshold:
                return False

        return True

    async def grant_challenge_waiver(
        self,
        prerequisite_id: UUID,
        score: float,
        granted_by: str | None = None,
    ) -> PrerequisiteWaiver:
        """
        Grant a challenge waiver based on high performance.

        Args:
            prerequisite_id: The prerequisite to waive
            score: The score achieved (0-1)
            granted_by: System or user granting the waiver

        Returns:
            The created waiver
        """
        return await self.create_waiver(
            prerequisite_id=prerequisite_id,
            waiver_type="challenge",
            granted_by=granted_by or "system",
            evidence_type="quiz_score",
            evidence_details={
                "score": score,
                "challenge_passed": True,
                "granted_at": datetime.utcnow().isoformat(),
            },
            notes=f"Challenge waiver granted for score {score:.1%}",
        )
