"""
Prerequisite service for managing explicit prerequisites.

Provides CRUD operations, tag parsing, circular dependency detection,
and chain resolution for the prerequisite system.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import and_, select, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.db.models import (
    CleanAtom,
    CleanConcept,
    ExplicitPrerequisite,
    InferredPrerequisite,
)


@dataclass
class ParsedPrerequisiteTag:
    """Parsed prerequisite tag from Anki format."""

    domain: str
    topic: str
    subtopic: str | None = None
    raw_tag: str = ""

    @property
    def full_path(self) -> str:
        """Get full path as string."""
        if self.subtopic:
            return f"{self.domain}:{self.topic}:{self.subtopic}"
        return f"{self.domain}:{self.topic}"


@dataclass
class PrerequisiteChainNode:
    """Node in a prerequisite chain."""

    concept_id: UUID
    concept_name: str
    depth: int
    gating_type: str
    mastery_threshold: Decimal


@dataclass
class CircularDependencyError:
    """Information about a detected circular dependency."""

    chain: list[UUID]
    concept_names: list[str]
    message: str


class PrerequisiteService:
    """
    Service for managing explicit prerequisites.

    Handles:
    - CRUD operations for prerequisites
    - Parsing Anki prerequisite tags
    - Circular dependency detection
    - Prerequisite chain resolution
    - Upgrading inferred to explicit prerequisites
    """

    # Tag pattern: tag:prereq:domain:topic[:subtopic]
    TAG_PATTERN = re.compile(
        r"^tag:prereq:([a-zA-Z0-9_-]+):([a-zA-Z0-9_-]+)(?::([a-zA-Z0-9_-]+))?$"
    )

    def __init__(self, session: AsyncSession):
        self.session = session

    # ========================================
    # CRUD Operations
    # ========================================

    async def create_prerequisite(
        self,
        target_concept_id: UUID,
        gating_type: str,
        source_concept_id: UUID | None = None,
        source_atom_id: UUID | None = None,
        mastery_threshold: float = 0.65,
        mastery_type: str = "integration",
        origin: str = "explicit",
        anki_tag: str | None = None,
        created_by: str | None = None,
        notes: str | None = None,
    ) -> ExplicitPrerequisite:
        """
        Create a new explicit prerequisite.

        Args:
            target_concept_id: The concept that must be mastered (prerequisite)
            gating_type: 'soft' or 'hard'
            source_concept_id: The concept that requires the prerequisite (optional)
            source_atom_id: The atom that requires the prerequisite (optional)
            mastery_threshold: Required mastery level (0-1)
            mastery_type: 'foundation', 'integration', or 'mastery'
            origin: 'explicit', 'tag', 'inferred', or 'imported'
            anki_tag: The Anki tag if applicable
            created_by: User who created the prerequisite
            notes: Additional notes

        Returns:
            The created ExplicitPrerequisite

        Raises:
            ValueError: If neither source_concept_id nor source_atom_id is provided
            ValueError: If circular dependency would be created
        """
        # Validate source
        if source_concept_id is None and source_atom_id is None:
            raise ValueError("Either source_concept_id or source_atom_id must be provided")

        if source_concept_id is not None and source_atom_id is not None:
            raise ValueError("Only one of source_concept_id or source_atom_id should be provided")

        # Check for circular dependency if concept-level
        if source_concept_id is not None:
            is_circular = await self.would_create_circular_dependency(
                source_concept_id, target_concept_id
            )
            if is_circular:
                raise ValueError("Adding this prerequisite would create a circular dependency")

        prerequisite = ExplicitPrerequisite(
            source_concept_id=source_concept_id,
            source_atom_id=source_atom_id,
            target_concept_id=target_concept_id,
            gating_type=gating_type,
            mastery_threshold=Decimal(str(mastery_threshold)),
            mastery_type=mastery_type,
            origin=origin,
            anki_tag=anki_tag,
            created_by=created_by,
            notes=notes,
            status="active",
        )

        self.session.add(prerequisite)
        await self.session.flush()
        return prerequisite

    async def get_prerequisite(self, prerequisite_id: UUID) -> ExplicitPrerequisite | None:
        """Get a prerequisite by ID."""
        result = await self.session.execute(
            select(ExplicitPrerequisite)
            .options(
                selectinload(ExplicitPrerequisite.source_concept),
                selectinload(ExplicitPrerequisite.target_concept),
                selectinload(ExplicitPrerequisite.waivers),
            )
            .where(ExplicitPrerequisite.id == prerequisite_id)
        )
        return result.scalar_one_or_none()

    async def list_prerequisites(
        self,
        source_concept_id: UUID | None = None,
        source_atom_id: UUID | None = None,
        target_concept_id: UUID | None = None,
        gating_type: str | None = None,
        status: str = "active",
        origin: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[ExplicitPrerequisite]:
        """
        List prerequisites with optional filters.

        Args:
            source_concept_id: Filter by source concept
            source_atom_id: Filter by source atom
            target_concept_id: Filter by target concept
            gating_type: Filter by gating type ('soft' or 'hard')
            status: Filter by status (default 'active')
            origin: Filter by origin
            limit: Maximum results
            offset: Result offset

        Returns:
            List of matching prerequisites
        """
        query = select(ExplicitPrerequisite).options(
            selectinload(ExplicitPrerequisite.source_concept),
            selectinload(ExplicitPrerequisite.target_concept),
        )

        conditions = []
        if source_concept_id:
            conditions.append(ExplicitPrerequisite.source_concept_id == source_concept_id)
        if source_atom_id:
            conditions.append(ExplicitPrerequisite.source_atom_id == source_atom_id)
        if target_concept_id:
            conditions.append(ExplicitPrerequisite.target_concept_id == target_concept_id)
        if gating_type:
            conditions.append(ExplicitPrerequisite.gating_type == gating_type)
        if status:
            conditions.append(ExplicitPrerequisite.status == status)
        if origin:
            conditions.append(ExplicitPrerequisite.origin == origin)

        if conditions:
            query = query.where(and_(*conditions))

        query = query.order_by(ExplicitPrerequisite.created_at.desc())
        query = query.limit(limit).offset(offset)

        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def update_prerequisite(
        self,
        prerequisite_id: UUID,
        gating_type: str | None = None,
        mastery_threshold: float | None = None,
        mastery_type: str | None = None,
        status: str | None = None,
        notes: str | None = None,
    ) -> ExplicitPrerequisite | None:
        """Update a prerequisite."""
        prerequisite = await self.get_prerequisite(prerequisite_id)
        if not prerequisite:
            return None

        if gating_type is not None:
            prerequisite.gating_type = gating_type
        if mastery_threshold is not None:
            prerequisite.mastery_threshold = Decimal(str(mastery_threshold))
        if mastery_type is not None:
            prerequisite.mastery_type = mastery_type
        if status is not None:
            prerequisite.status = status
        if notes is not None:
            prerequisite.notes = notes

        await self.session.flush()
        return prerequisite

    async def delete_prerequisite(self, prerequisite_id: UUID) -> bool:
        """Delete a prerequisite."""
        prerequisite = await self.get_prerequisite(prerequisite_id)
        if not prerequisite:
            return False

        await self.session.delete(prerequisite)
        await self.session.flush()
        return True

    # ========================================
    # Tag Parsing
    # ========================================

    def parse_prerequisite_tag(self, tag: str) -> ParsedPrerequisiteTag | None:
        """
        Parse an Anki prerequisite tag.

        Format: tag:prereq:domain:topic[:subtopic]

        Examples:
            - tag:prereq:networking:tcp:handshake
            - tag:prereq:ccna:layer1:ipv4
            - tag:prereq:math:algebra

        Args:
            tag: The tag string to parse

        Returns:
            ParsedPrerequisiteTag if valid, None otherwise
        """
        match = self.TAG_PATTERN.match(tag.strip().lower())
        if not match:
            return None

        return ParsedPrerequisiteTag(
            domain=match.group(1),
            topic=match.group(2),
            subtopic=match.group(3),
            raw_tag=tag,
        )

    def parse_prerequisite_tags(self, tags: list[str]) -> list[ParsedPrerequisiteTag]:
        """
        Parse multiple prerequisite tags.

        Args:
            tags: List of tag strings

        Returns:
            List of successfully parsed tags
        """
        parsed = []
        for tag in tags:
            result = self.parse_prerequisite_tag(tag)
            if result:
                parsed.append(result)
        return parsed

    async def sync_from_anki_tags(
        self,
        atom_id: UUID,
        tags: list[str],
        gating_type: str = "soft",
    ) -> list[ExplicitPrerequisite]:
        """
        Create prerequisites from Anki tags for an atom.

        Parses tags in format tag:prereq:domain:topic[:subtopic] and creates
        prerequisite relationships to matching concepts.

        Args:
            atom_id: The atom ID
            tags: List of Anki tags
            gating_type: Default gating type for new prerequisites

        Returns:
            List of created prerequisites
        """
        parsed_tags = self.parse_prerequisite_tags(tags)
        if not parsed_tags:
            return []

        created = []
        for parsed in parsed_tags:
            # Find matching concept by name/domain
            concept = await self._find_concept_by_path(parsed)
            if not concept:
                continue

            # Check if prerequisite already exists
            existing = await self.session.execute(
                select(ExplicitPrerequisite).where(
                    and_(
                        ExplicitPrerequisite.source_atom_id == atom_id,
                        ExplicitPrerequisite.target_concept_id == concept.id,
                    )
                )
            )
            if existing.scalar_one_or_none():
                continue

            # Create new prerequisite
            try:
                prerequisite = await self.create_prerequisite(
                    source_atom_id=atom_id,
                    target_concept_id=concept.id,
                    gating_type=gating_type,
                    origin="tag",
                    anki_tag=parsed.raw_tag,
                )
                created.append(prerequisite)
            except ValueError:
                # Skip if circular dependency or other error
                continue

        return created

    async def _find_concept_by_path(self, parsed: ParsedPrerequisiteTag) -> CleanConcept | None:
        """Find a concept matching the parsed tag path."""
        # Try exact name match first
        search_name = parsed.subtopic or parsed.topic

        result = await self.session.execute(
            select(CleanConcept).where(CleanConcept.name.ilike(f"%{search_name}%")).limit(1)
        )
        concept = result.scalar_one_or_none()

        if not concept:
            # Try domain match
            result = await self.session.execute(
                select(CleanConcept).where(CleanConcept.domain.ilike(f"%{parsed.domain}%")).limit(1)
            )
            concept = result.scalar_one_or_none()

        return concept

    def export_to_anki_tag(
        self, prerequisite: ExplicitPrerequisite, prefix: str = "tag:prereq"
    ) -> str:
        """
        Generate an Anki tag from a prerequisite.

        Args:
            prerequisite: The prerequisite to export
            prefix: Tag prefix (default "tag:prereq")

        Returns:
            Anki tag string
        """
        if prerequisite.anki_tag:
            return prerequisite.anki_tag

        # Build from target concept
        concept = prerequisite.target_concept
        if not concept:
            return ""

        parts = [prefix]

        # Add domain if available
        if concept.domain:
            parts.append(concept.domain.lower().replace(" ", "_"))
        else:
            parts.append("general")

        # Add concept name
        parts.append(concept.name.lower().replace(" ", "_"))

        return ":".join(parts)

    async def export_prerequisites_to_anki_tags(self, atom_id: UUID) -> list[str]:
        """
        Export all prerequisites for an atom as Anki tags.

        Args:
            atom_id: The atom ID

        Returns:
            List of Anki tag strings
        """
        prerequisites = await self.list_prerequisites(
            source_atom_id=atom_id,
            status="active",
        )

        tags = []
        for prereq in prerequisites:
            tag = self.export_to_anki_tag(prereq)
            if tag:
                tags.append(tag)

        return tags

    # ========================================
    # Circular Dependency Detection
    # ========================================

    async def would_create_circular_dependency(
        self,
        source_concept_id: UUID,
        target_concept_id: UUID,
    ) -> bool:
        """
        Check if adding a prerequisite would create a circular dependency.

        Uses the check_circular_prerequisite SQL function.

        Args:
            source_concept_id: The concept requiring the prerequisite
            target_concept_id: The prerequisite concept

        Returns:
            True if circular dependency would be created
        """
        result = await self.session.execute(
            text("SELECT check_circular_prerequisite(:source, :target)"),
            {"source": str(source_concept_id), "target": str(target_concept_id)},
        )
        return result.scalar() or False

    async def detect_circular_dependencies(self) -> list[CircularDependencyError]:
        """
        Detect all circular dependencies in the prerequisite graph.

        Returns:
            List of CircularDependencyError objects
        """
        # Use the v_prerequisite_chains view to find cycles
        result = await self.session.execute(
            text("""
                WITH RECURSIVE prereq_chain AS (
                    SELECT
                        source_concept_id,
                        target_concept_id,
                        ARRAY[source_concept_id] as chain,
                        1 as depth
                    FROM explicit_prerequisites
                    WHERE status = 'active' AND source_concept_id IS NOT NULL

                    UNION ALL

                    SELECT
                        pc.source_concept_id,
                        ep.target_concept_id,
                        pc.chain || ep.source_concept_id,
                        pc.depth + 1
                    FROM prereq_chain pc
                    JOIN explicit_prerequisites ep ON ep.source_concept_id = pc.target_concept_id
                    WHERE ep.status = 'active'
                      AND pc.depth < 10
                )
                SELECT DISTINCT chain
                FROM prereq_chain
                WHERE source_concept_id = target_concept_id
            """)
        )

        errors = []
        for row in result:
            chain = row[0]
            # Get concept names for the chain
            concepts_result = await self.session.execute(
                select(CleanConcept.id, CleanConcept.name).where(CleanConcept.id.in_(chain))
            )
            concept_map = {str(c.id): c.name for c in concepts_result}
            names = [concept_map.get(str(c), str(c)) for c in chain]

            errors.append(
                CircularDependencyError(
                    chain=chain,
                    concept_names=names,
                    message=f"Circular dependency: {' -> '.join(names)} -> {names[0]}",
                )
            )

        return errors

    # ========================================
    # Prerequisite Chain Resolution
    # ========================================

    async def get_prerequisite_chain(
        self,
        concept_id: UUID,
        max_depth: int = 10,
    ) -> list[PrerequisiteChainNode]:
        """
        Get the full prerequisite chain for a concept.

        Returns all prerequisites (direct and transitive) in order of depth.

        Args:
            concept_id: The concept to get prerequisites for
            max_depth: Maximum chain depth

        Returns:
            List of PrerequisiteChainNode objects
        """
        result = await self.session.execute(
            text("""
                WITH RECURSIVE prereq_chain AS (
                    SELECT
                        ep.target_concept_id as concept_id,
                        c.name as concept_name,
                        1 as depth,
                        ep.gating_type,
                        ep.mastery_threshold
                    FROM explicit_prerequisites ep
                    JOIN concepts c ON ep.target_concept_id = c.id
                    WHERE ep.source_concept_id = :concept_id
                      AND ep.status = 'active'

                    UNION ALL

                    SELECT
                        ep.target_concept_id,
                        c.name,
                        pc.depth + 1,
                        ep.gating_type,
                        ep.mastery_threshold
                    FROM prereq_chain pc
                    JOIN explicit_prerequisites ep ON ep.source_concept_id = pc.concept_id
                    JOIN concepts c ON ep.target_concept_id = c.id
                    WHERE ep.status = 'active'
                      AND pc.depth < :max_depth
                )
                SELECT DISTINCT ON (concept_id) *
                FROM prereq_chain
                ORDER BY concept_id, depth
            """),
            {"concept_id": str(concept_id), "max_depth": max_depth},
        )

        nodes = []
        for row in result:
            nodes.append(
                PrerequisiteChainNode(
                    concept_id=row.concept_id,
                    concept_name=row.concept_name,
                    depth=row.depth,
                    gating_type=row.gating_type,
                    mastery_threshold=row.mastery_threshold,
                )
            )

        # Sort by depth
        nodes.sort(key=lambda n: n.depth)
        return nodes

    # ========================================
    # Upgrade Inferred Prerequisites
    # ========================================

    async def upgrade_inferred_to_explicit(
        self,
        inferred_id: UUID,
        gating_type: str = "soft",
        approved_by: str | None = None,
    ) -> ExplicitPrerequisite | None:
        """
        Upgrade an inferred prerequisite to an explicit one.

        Args:
            inferred_id: ID of the inferred prerequisite
            gating_type: Gating type for the explicit prerequisite
            approved_by: User who approved the upgrade

        Returns:
            The created ExplicitPrerequisite, or None if not found
        """
        # Get the inferred prerequisite
        result = await self.session.execute(
            select(InferredPrerequisite).where(InferredPrerequisite.id == inferred_id)
        )
        inferred = result.scalar_one_or_none()

        if not inferred:
            return None

        # Get the atom's concept if needed
        atom_result = await self.session.execute(
            select(CleanAtom).where(CleanAtom.id == inferred.source_atom_id)
        )
        atom_result.scalar_one_or_none()

        # Create explicit prerequisite
        try:
            prerequisite = await self.create_prerequisite(
                source_atom_id=inferred.source_atom_id,
                target_concept_id=inferred.target_concept_id,
                gating_type=gating_type,
                mastery_threshold=0.65,  # Default to integration level
                origin="inferred",
                notes=f"Upgraded from inferred (similarity: {inferred.similarity_score})",
            )

            # Update the inferred prerequisite status
            inferred.status = "applied"
            inferred.reviewed_by = approved_by
            inferred.reviewed_at = datetime.utcnow()

            if approved_by:
                prerequisite.approved_by = approved_by
                prerequisite.approved_at = datetime.utcnow()

            await self.session.flush()
            return prerequisite

        except ValueError:
            # Log error and return None
            return None
