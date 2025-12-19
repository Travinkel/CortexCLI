"""
Just-In-Time Content Generation Service.

Generates learning content on-the-fly to fill gaps when:
1. Learner fails a question and remediation atoms are exhausted
2. A concept has no atoms (missing coverage)
3. User explicitly requests more practice
4. System predicts learner will need content (proactive)

Integrates with:
- RemediationRouter for gap detection
- AtomizerService for content generation
- VertexTutor for guidance while generating
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID

from loguru import logger
from sqlalchemy import text
from sqlalchemy.orm import Session

from src.ccna.atomizer_service import (
    AtomizerService,
    AtomType,
    GeneratedAtom,
    KnowledgeType,
)
from src.ccna.content_parser import Section
from src.db.database import session_scope


class GenerationTrigger(str, Enum):
    """What triggered JIT generation."""

    FAILED_QUESTION = "failed_question"  # Learner failed, remediation exhausted
    MISSING_COVERAGE = "missing_coverage"  # Concept has no atoms
    USER_REQUEST = "user_request"  # Learner asked for more practice
    PROACTIVE = "proactive"  # System predicted need


class ContentType(str, Enum):
    """Type of content to generate."""

    PRACTICE = "practice"  # Flashcards, MCQ, cloze
    EXPLANATION = "explanation"  # Elaborative content
    WORKED_EXAMPLE = "worked_example"  # Step-by-step walkthrough


@dataclass
class GenerationRequest:
    """Request for JIT content generation."""

    concept_id: UUID
    trigger: GenerationTrigger
    content_types: list[ContentType] = field(default_factory=lambda: [ContentType.PRACTICE])
    atom_count: int = 3  # Target number of atoms
    learner_id: str | None = None
    fail_mode: str | None = None  # From NCDE diagnosis
    context: dict[str, Any] = field(default_factory=dict)


@dataclass
class GenerationResult:
    """Result of JIT generation."""

    concept_id: UUID
    atoms: list[GeneratedAtom]
    trigger: GenerationTrigger
    generation_time_ms: int
    from_cache: bool = False
    errors: list[str] = field(default_factory=list)


class JITGenerationService:
    """
    Just-In-Time content generation for filling learning gaps.

    Features:
    - Generates content on-demand when gaps detected
    - Caches results to avoid regeneration
    - Integrates with NCDE fail modes for targeted content
    - Supports multiple content types (practice, explanation, examples)
    """

    def __init__(
        self,
        session: Session | None = None,
        atomizer: AtomizerService | None = None,
    ):
        self._session = session
        self._atomizer = atomizer
        self._cache: dict[str, GenerationResult] = {}  # In-memory cache

    @property
    def atomizer(self) -> AtomizerService:
        """Lazy-load atomizer service."""
        if self._atomizer is None:
            self._atomizer = AtomizerService()
        return self._atomizer

    async def generate_for_gap(
        self,
        request: GenerationRequest,
    ) -> GenerationResult:
        """
        Generate content for a knowledge gap.

        Args:
            request: Generation request with concept and parameters

        Returns:
            GenerationResult with generated atoms
        """
        start_time = datetime.now()
        cache_key = self._make_cache_key(request)

        # Check cache first
        if cache_key in self._cache:
            cached = self._cache[cache_key]
            logger.info(f"JIT cache hit for concept {request.concept_id}")
            return GenerationResult(
                concept_id=request.concept_id,
                atoms=cached.atoms,
                trigger=request.trigger,
                generation_time_ms=0,
                from_cache=True,
            )

        logger.info(
            f"JIT generating for concept {request.concept_id}, "
            f"trigger={request.trigger.value}, types={[t.value for t in request.content_types]}"
        )

        errors: list[str] = []
        atoms: list[GeneratedAtom] = []

        try:
            # Get source content for concept
            source_content = await self._get_concept_source_content(request.concept_id)

            if not source_content:
                errors.append(f"No source content found for concept {request.concept_id}")
                logger.warning(errors[-1])
            else:
                # Create a synthetic Section for the atomizer
                section = self._create_section_from_content(
                    concept_id=request.concept_id,
                    content=source_content,
                )

                # Determine atom types based on request
                atom_types = self._map_content_types_to_atom_types(
                    request.content_types,
                    request.fail_mode,
                )

                # Generate atoms
                for atom_type in atom_types:
                    try:
                        type_atoms = await self.atomizer._generate_type(section, atom_type)
                        atoms.extend(type_atoms[:request.atom_count])

                        if len(atoms) >= request.atom_count:
                            break
                    except Exception as e:
                        errors.append(f"Failed to generate {atom_type.value}: {e}")
                        logger.error(errors[-1])

                # Mark atoms as JIT-generated
                for atom in atoms:
                    atom.tags.append("jit_generated")
                    atom.tags.append(f"trigger:{request.trigger.value}")

        except Exception as e:
            errors.append(f"JIT generation failed: {e}")
            logger.exception(errors[-1])

        # Calculate generation time
        elapsed_ms = int((datetime.now() - start_time).total_seconds() * 1000)

        result = GenerationResult(
            concept_id=request.concept_id,
            atoms=atoms,
            trigger=request.trigger,
            generation_time_ms=elapsed_ms,
            from_cache=False,
            errors=errors,
        )

        # Cache successful results
        if atoms and not errors:
            self._cache[cache_key] = result
            logger.info(f"JIT generated {len(atoms)} atoms in {elapsed_ms}ms, cached")

        return result

    async def generate_for_failed_question(
        self,
        concept_id: UUID,
        learner_id: str,
        fail_mode: str | None = None,
        existing_atom_count: int = 0,
    ) -> GenerationResult:
        """
        Generate content after a failed question when remediation is exhausted.

        Args:
            concept_id: Concept the question tested
            learner_id: Learner who failed
            fail_mode: NCDE diagnosis (encoding_error, discrimination_error, etc.)
            existing_atom_count: How many remediation atoms already exist

        Returns:
            GenerationResult with new atoms
        """
        # Only trigger if we don't have enough remediation atoms
        if existing_atom_count >= 5:
            logger.debug(f"Sufficient atoms exist ({existing_atom_count}), skipping JIT")
            return GenerationResult(
                concept_id=concept_id,
                atoms=[],
                trigger=GenerationTrigger.FAILED_QUESTION,
                generation_time_ms=0,
            )

        # Map fail mode to content type
        content_types = self._fail_mode_to_content_types(fail_mode)

        request = GenerationRequest(
            concept_id=concept_id,
            trigger=GenerationTrigger.FAILED_QUESTION,
            content_types=content_types,
            atom_count=5 - existing_atom_count,  # Fill the gap
            learner_id=learner_id,
            fail_mode=fail_mode,
        )

        return await self.generate_for_gap(request)

    async def generate_for_missing_coverage(
        self,
        concept_id: UUID,
        atom_count: int = 5,
    ) -> GenerationResult:
        """
        Generate content for a concept with no atoms.

        Args:
            concept_id: Concept missing atoms
            atom_count: How many atoms to generate

        Returns:
            GenerationResult with new atoms
        """
        request = GenerationRequest(
            concept_id=concept_id,
            trigger=GenerationTrigger.MISSING_COVERAGE,
            content_types=[ContentType.PRACTICE],
            atom_count=atom_count,
        )

        return await self.generate_for_gap(request)

    async def generate_on_user_request(
        self,
        concept_id: UUID,
        learner_id: str,
        content_type: ContentType = ContentType.PRACTICE,
    ) -> GenerationResult:
        """
        Generate content when user explicitly requests more practice.

        Args:
            concept_id: Concept to practice
            learner_id: Requesting learner
            content_type: Type of content requested

        Returns:
            GenerationResult with new atoms
        """
        request = GenerationRequest(
            concept_id=concept_id,
            trigger=GenerationTrigger.USER_REQUEST,
            content_types=[content_type],
            atom_count=3,
            learner_id=learner_id,
        )

        return await self.generate_for_gap(request)

    async def proactive_generation(
        self,
        learner_id: str,
        upcoming_concepts: list[UUID],
    ) -> dict[UUID, GenerationResult]:
        """
        Proactively generate content for concepts the learner will need soon.

        Args:
            learner_id: Learner identifier
            upcoming_concepts: Concepts predicted to be needed

        Returns:
            Dict mapping concept_id to GenerationResult
        """
        results: dict[UUID, GenerationResult] = {}

        for concept_id in upcoming_concepts[:3]:  # Limit to 3 to avoid overload
            # Check if concept needs content
            atom_count = await self._get_concept_atom_count(concept_id)

            if atom_count < 3:
                request = GenerationRequest(
                    concept_id=concept_id,
                    trigger=GenerationTrigger.PROACTIVE,
                    content_types=[ContentType.PRACTICE],
                    atom_count=3 - atom_count,
                    learner_id=learner_id,
                )

                results[concept_id] = await self.generate_for_gap(request)

        return results

    async def _get_concept_source_content(self, concept_id: UUID) -> str | None:
        """
        Get source content for a concept to use for generation.

        Looks for:
        1. Concept description/notes
        2. Existing atoms (to understand the topic)
        3. Parent cluster/area context
        """
        with self._get_session() as session:
            # Get concept info
            concept_query = text("""
                SELECT
                    c.name,
                    c.description,
                    cc.name as cluster_name,
                    ca.name as area_name
                FROM concepts c
                LEFT JOIN concept_clusters cc ON c.cluster_id = cc.id
                LEFT JOIN concept_areas ca ON cc.area_id = ca.id
                WHERE c.id = :concept_id
            """)

            result = session.execute(concept_query, {"concept_id": str(concept_id)})
            concept = result.fetchone()

            if not concept:
                return None

            # Build content from available sources
            content_parts = []

            # Add concept context
            if concept.area_name:
                content_parts.append(f"Domain: {concept.area_name}")
            if concept.cluster_name:
                content_parts.append(f"Topic: {concept.cluster_name}")
            content_parts.append(f"Concept: {concept.name}")

            if concept.description:
                content_parts.append(f"\n{concept.description}")

            # Get existing atoms for context (what we already cover)
            atoms_query = text("""
                SELECT front, back, atom_type, knowledge_type
                FROM learning_atoms
                WHERE concept_id = :concept_id
                ORDER BY created_at
                LIMIT 5
            """)

            atoms_result = session.execute(atoms_query, {"concept_id": str(concept_id)})
            existing_atoms = atoms_result.fetchall()

            if existing_atoms:
                content_parts.append("\n\nExisting coverage (for context):")
                for atom in existing_atoms:
                    content_parts.append(f"- {atom.front}")
                content_parts.append("\nGenerate content that complements the above.")

            return "\n".join(content_parts)

    async def _get_concept_atom_count(self, concept_id: UUID) -> int:
        """Get the number of atoms for a concept."""
        with self._get_session() as session:
            query = text("""
                SELECT COUNT(*) as count
                FROM learning_atoms
                WHERE concept_id = :concept_id
            """)
            result = session.execute(query, {"concept_id": str(concept_id)})
            row = result.fetchone()
            return row.count if row else 0

    def _create_section_from_content(
        self,
        concept_id: UUID,
        content: str,
    ) -> Section:
        """Create a synthetic Section object for the atomizer."""
        return Section(
            id=f"JIT-{concept_id}",
            title=f"JIT Generation for {concept_id}",
            raw_content=content,
            depth=0,
            parent_id=None,
        )

    def _map_content_types_to_atom_types(
        self,
        content_types: list[ContentType],
        fail_mode: str | None = None,
    ) -> list[AtomType]:
        """Map requested content types to atom types."""
        atom_types = []

        for content_type in content_types:
            if content_type == ContentType.PRACTICE:
                atom_types.extend([AtomType.FLASHCARD, AtomType.MCQ, AtomType.CLOZE])

            elif content_type == ContentType.EXPLANATION:
                # For explanations, we generate flashcards with conceptual focus
                atom_types.append(AtomType.FLASHCARD)

            elif content_type == ContentType.WORKED_EXAMPLE:
                atom_types.extend([AtomType.PARSONS, AtomType.NUMERIC])

        # Adjust based on fail mode if provided
        if fail_mode:
            if fail_mode == "discrimination_error":
                # Prioritize comparison and true/false
                atom_types = [AtomType.TRUE_FALSE, AtomType.COMPARE] + atom_types

            elif fail_mode == "encoding_error":
                # Prioritize elaborative content
                atom_types = [AtomType.FLASHCARD, AtomType.CLOZE] + atom_types

            elif fail_mode == "integration_error":
                # Prioritize worked examples
                atom_types = [AtomType.PARSONS, AtomType.NUMERIC] + atom_types

        # Deduplicate while preserving order
        seen = set()
        unique_types = []
        for t in atom_types:
            if t not in seen:
                seen.add(t)
                unique_types.append(t)

        return unique_types[:3]  # Limit to 3 types per generation

    def _fail_mode_to_content_types(
        self,
        fail_mode: str | None,
    ) -> list[ContentType]:
        """Map NCDE fail mode to appropriate content types."""
        if not fail_mode:
            return [ContentType.PRACTICE]

        mapping = {
            "encoding_error": [ContentType.EXPLANATION, ContentType.PRACTICE],
            "retrieval_error": [ContentType.PRACTICE],
            "discrimination_error": [ContentType.PRACTICE],  # Need comparison items
            "integration_error": [ContentType.WORKED_EXAMPLE, ContentType.PRACTICE],
            "executive_error": [ContentType.PRACTICE],  # More practice needed
            "fatigue_error": [],  # Don't generate - suggest break instead
        }

        return mapping.get(fail_mode, [ContentType.PRACTICE])

    def _make_cache_key(self, request: GenerationRequest) -> str:
        """Create a cache key for a generation request."""
        types_str = ",".join(sorted(t.value for t in request.content_types))
        return f"{request.concept_id}:{request.trigger.value}:{types_str}"

    def clear_cache(self, concept_id: UUID | None = None) -> int:
        """
        Clear the generation cache.

        Args:
            concept_id: If provided, only clear cache for this concept

        Returns:
            Number of entries cleared
        """
        if concept_id:
            keys_to_remove = [k for k in self._cache if str(concept_id) in k]
            for key in keys_to_remove:
                del self._cache[key]
            return len(keys_to_remove)
        else:
            count = len(self._cache)
            self._cache.clear()
            return count

    def _get_session(self):
        """Get session context manager."""
        if self._session:

            class SessionWrapper:
                def __init__(self, s):
                    self.session = s

                def __enter__(self):
                    return self.session

                def __exit__(self, *args):
                    pass

            return SessionWrapper(self._session)
        return session_scope()


# Convenience function for quick generation
async def generate_content_for_concept(
    concept_id: UUID,
    trigger: GenerationTrigger = GenerationTrigger.USER_REQUEST,
    content_types: list[ContentType] | None = None,
    atom_count: int = 3,
) -> GenerationResult:
    """
    Quick helper to generate content for a concept.

    Args:
        concept_id: Concept needing content
        trigger: What triggered the generation
        content_types: Types of content to generate
        atom_count: Number of atoms to generate

    Returns:
        GenerationResult with generated atoms
    """
    service = JITGenerationService()
    request = GenerationRequest(
        concept_id=concept_id,
        trigger=trigger,
        content_types=content_types or [ContentType.PRACTICE],
        atom_count=atom_count,
    )
    return await service.generate_for_gap(request)
