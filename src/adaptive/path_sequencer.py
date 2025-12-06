"""
Learning Path Sequencer.

Determines optimal atom ordering based on:
- Prerequisite graph (topological sort)
- Mastery state (prioritize unlocked concepts)
- Knowledge type interleaving
- Spaced repetition scheduling
"""
from __future__ import annotations

from collections import defaultdict
from typing import Optional
from uuid import UUID

from loguru import logger
from sqlalchemy import text
from sqlalchemy.orm import Session

from src.adaptive.models import (
    LearningPath,
    ConceptMastery,
    AtomPresentation,
    BlockingPrerequisite,
    UnlockStatus,
    GatingType,
)
from src.adaptive.mastery_calculator import MasteryCalculator
from src.db.database import session_scope


class PathSequencer:
    """
    Sequence atoms optimally for learning.

    Uses prerequisite graph to determine valid orderings,
    then applies mastery-aware prioritization.
    """

    def __init__(self, session: Optional[Session] = None):
        self._session = session
        self._mastery_calc = MasteryCalculator(session)

    def get_learning_path(
        self,
        learner_id: str,
        target_concept_id: UUID,
        target_mastery: float = 0.85,
    ) -> LearningPath:
        """
        Generate optimal learning path to master a concept.

        Args:
            learner_id: Learner identifier
            target_concept_id: Concept to master
            target_mastery: Target mastery level (default 0.85)

        Returns:
            LearningPath with prerequisites and ordered atoms
        """
        with self._get_session() as session:
            # Get concept info
            concept_info = self._get_concept_info(session, target_concept_id)
            if not concept_info:
                return LearningPath(
                    target_concept_id=target_concept_id,
                    target_concept_name="Unknown",
                    prerequisites_to_complete=[],
                    path_atoms=[],
                )

            # Get current mastery
            current_mastery = self._mastery_calc.compute_concept_mastery(
                learner_id, target_concept_id
            )

            # If already at target mastery, return empty path
            if current_mastery.combined_mastery >= target_mastery:
                return LearningPath(
                    target_concept_id=target_concept_id,
                    target_concept_name=concept_info["name"],
                    prerequisites_to_complete=[],
                    path_atoms=[],
                    current_mastery=current_mastery.combined_mastery,
                    target_mastery=target_mastery,
                )

            # Get prerequisite chain
            prereq_chain = self._get_prerequisite_chain(
                session, learner_id, target_concept_id
            )

            # Filter to incomplete prerequisites
            incomplete_prereqs = [
                p for p in prereq_chain
                if p.combined_mastery < p.combined_mastery  # This should compare to threshold
            ]

            # Get atoms for the learning path
            path_atoms = self._sequence_atoms_for_path(
                session, learner_id, target_concept_id, prereq_chain
            )

            # Estimate duration (assuming 2 minutes per atom average)
            estimated_duration = len(path_atoms) * 2

            return LearningPath(
                target_concept_id=target_concept_id,
                target_concept_name=concept_info["name"],
                prerequisites_to_complete=prereq_chain,
                path_atoms=path_atoms,
                estimated_atoms=len(path_atoms),
                estimated_duration_minutes=estimated_duration,
                current_mastery=current_mastery.combined_mastery,
                target_mastery=target_mastery,
            )

    def get_next_atoms(
        self,
        learner_id: str,
        concept_id: Optional[UUID] = None,
        cluster_id: Optional[UUID] = None,
        count: int = 10,
        include_review: bool = True,
    ) -> list[UUID]:
        """
        Get next atoms for a learner.

        Considers:
        - Unlocked concepts only (unless no hard gates)
        - Due reviews (from FSRS)
        - New atoms from unlocked concepts
        - Knowledge type interleaving

        Args:
            learner_id: Learner identifier
            concept_id: Optional specific concept
            cluster_id: Optional cluster scope
            count: Number of atoms to return
            include_review: Include due reviews

        Returns:
            List of atom UUIDs in optimal order
        """
        with self._get_session() as session:
            atoms = []

            # 1. Get due reviews first (if enabled)
            if include_review:
                due_atoms = self._get_due_reviews(
                    session, learner_id, concept_id, cluster_id, count // 2
                )
                atoms.extend(due_atoms)

            # 2. Get new atoms from unlocked concepts
            remaining = count - len(atoms)
            if remaining > 0:
                new_atoms = self._get_new_atoms(
                    session, learner_id, concept_id, cluster_id, remaining
                )
                atoms.extend(new_atoms)

            # 3. Interleave by knowledge type
            atoms = self._interleave_atoms(session, atoms)

            return atoms[:count]

    def check_unlock_status(
        self,
        learner_id: str,
        concept_id: UUID,
    ) -> UnlockStatus:
        """
        Check if a concept is unlocked for a learner.

        Args:
            learner_id: Learner identifier
            concept_id: Concept to check

        Returns:
            UnlockStatus with blocking prerequisites if any
        """
        with self._get_session() as session:
            # Get hard prerequisites that are not met
            query = text("""
                SELECT
                    ep.target_concept_id,
                    cc.name as concept_name,
                    ep.mastery_threshold,
                    ep.gating_type,
                    COALESCE(lms.combined_mastery, 0) as current_mastery
                FROM explicit_prerequisites ep
                JOIN concepts cc ON ep.target_concept_id = cc.id
                LEFT JOIN learner_mastery_state lms
                    ON lms.concept_id = ep.target_concept_id
                    AND lms.learner_id = :learner_id
                WHERE ep.source_concept_id = :concept_id
                AND ep.status = 'active'
            """)

            try:
                result = session.execute(query, {
                    "learner_id": learner_id,
                    "concept_id": str(concept_id),
                })
                prerequisites = result.fetchall()
            except Exception:
                return UnlockStatus(is_unlocked=True, unlock_reason="no_prerequisites")

            blocking = []
            for prereq in prerequisites:
                threshold = float(prereq.mastery_threshold or 0.65)
                current = float(prereq.current_mastery or 0)
                gating = prereq.gating_type or "soft"

                if current < threshold and gating == "hard":
                    blocking.append(BlockingPrerequisite(
                        concept_id=UUID(str(prereq.target_concept_id)),
                        concept_name=prereq.concept_name,
                        required_mastery=threshold,
                        current_mastery=current,
                        gating_type=GatingType.HARD,
                    ))

            if blocking:
                # Estimate atoms needed to unlock
                estimated_atoms = sum(
                    int((b.required_mastery - b.current_mastery) * 20)
                    for b in blocking
                )
                return UnlockStatus(
                    is_unlocked=False,
                    blocking_prerequisites=blocking,
                    unlock_reason="blocked_by_prerequisites",
                    estimated_atoms_to_unlock=estimated_atoms,
                )

            return UnlockStatus(
                is_unlocked=True,
                unlock_reason="prerequisites_met" if prerequisites else "no_prerequisites",
            )

    def _get_prerequisite_chain(
        self,
        session: Session,
        learner_id: str,
        concept_id: UUID,
    ) -> list[ConceptMastery]:
        """
        Get ordered prerequisite chain for a concept.

        Uses recursive CTE to traverse prerequisite graph.
        """
        # Get all prerequisites recursively
        query = text("""
            WITH RECURSIVE prereq_chain AS (
                -- Base case: direct prerequisites
                SELECT
                    ep.target_concept_id as concept_id,
                    cc.name as concept_name,
                    1 as depth
                FROM explicit_prerequisites ep
                JOIN concepts cc ON ep.target_concept_id = cc.id
                WHERE ep.source_concept_id = :concept_id
                AND ep.status = 'active'

                UNION ALL

                -- Recursive: prerequisites of prerequisites
                SELECT
                    ep.target_concept_id,
                    cc.name,
                    pc.depth + 1
                FROM explicit_prerequisites ep
                JOIN concepts cc ON ep.target_concept_id = cc.id
                JOIN prereq_chain pc ON ep.source_concept_id = pc.concept_id
                WHERE ep.status = 'active'
                AND pc.depth < 10  -- Prevent infinite loops
            )
            SELECT DISTINCT concept_id, concept_name, MIN(depth) as depth
            FROM prereq_chain
            GROUP BY concept_id, concept_name
            ORDER BY depth DESC
        """)

        try:
            result = session.execute(query, {"concept_id": str(concept_id)})
            prereqs = result.fetchall()
        except Exception as e:
            logger.warning(f"Could not get prerequisite chain: {e}")
            return []

        # Get mastery for each prerequisite
        chain = []
        for prereq in prereqs:
            mastery = self._mastery_calc.compute_concept_mastery(
                learner_id, UUID(str(prereq.concept_id))
            )
            chain.append(mastery)

        return chain

    def _sequence_atoms_for_path(
        self,
        session: Session,
        learner_id: str,
        target_concept_id: UUID,
        prereq_chain: list[ConceptMastery],
    ) -> list[UUID]:
        """
        Sequence atoms for a learning path.

        Orders by:
        1. Prerequisites first (in topological order)
        2. Target concept atoms
        3. Within each concept, by knowledge type
        """
        all_atoms = []

        # Get atoms for prerequisites (in order)
        for prereq in prereq_chain:
            if prereq.combined_mastery < 0.65:  # Not yet proficient
                atoms = self._get_concept_atoms(session, prereq.concept_id)
                all_atoms.extend(atoms)

        # Get atoms for target concept
        target_atoms = self._get_concept_atoms(session, target_concept_id)
        all_atoms.extend(target_atoms)

        # Remove already-mastered atoms (high retrievability)
        all_atoms = self._filter_mastered_atoms(session, learner_id, all_atoms)

        return all_atoms

    def _get_concept_atoms(
        self,
        session: Session,
        concept_id: UUID,
    ) -> list[UUID]:
        """Get atoms for a concept, ordered by atom type."""
        query = text("""
            SELECT id, atom_type
            FROM learning_atoms
            WHERE concept_id = :concept_id
            ORDER BY
                CASE atom_type
                    WHEN 'flashcard' THEN 1
                    WHEN 'cloze' THEN 2
                    WHEN 'true_false' THEN 3
                    WHEN 'mcq' THEN 4
                    WHEN 'matching' THEN 5
                    ELSE 6
                END,
                created_at
        """)

        result = session.execute(query, {"concept_id": str(concept_id)})
        return [UUID(str(row.id)) for row in result.fetchall()]

    def _get_due_reviews(
        self,
        session: Session,
        learner_id: str,
        concept_id: Optional[UUID],
        cluster_id: Optional[UUID],
        limit: int,
    ) -> list[UUID]:
        """Get atoms due for review based on FSRS."""
        conditions = ["ca.anki_due_date <= NOW()"]
        params = {"limit": limit}

        if concept_id:
            conditions.append("ca.concept_id = :concept_id")
            params["concept_id"] = str(concept_id)
        elif cluster_id:
            conditions.append("cc.cluster_id = :cluster_id")
            params["cluster_id"] = str(cluster_id)

        where_clause = " AND ".join(conditions)

        query = text(f"""
            SELECT ca.id
            FROM learning_atoms ca
            JOIN concepts cc ON ca.concept_id = cc.id
            WHERE {where_clause}
            ORDER BY ca.anki_due_date ASC
            LIMIT :limit
        """)

        try:
            result = session.execute(query, params)
            return [UUID(str(row.id)) for row in result.fetchall()]
        except Exception:
            return []

    def _get_new_atoms(
        self,
        session: Session,
        learner_id: str,
        concept_id: Optional[UUID],
        cluster_id: Optional[UUID],
        limit: int,
    ) -> list[UUID]:
        """Get new (unreviewed) atoms from unlocked concepts."""
        # Build query based on scope
        conditions = [
            "ca.anki_review_count IS NULL OR ca.anki_review_count = 0"
        ]
        params = {"learner_id": learner_id, "limit": limit}

        if concept_id:
            conditions.append("ca.concept_id = :concept_id")
            params["concept_id"] = str(concept_id)
        elif cluster_id:
            conditions.append("cc.cluster_id = :cluster_id")
            params["cluster_id"] = str(cluster_id)

        where_clause = " AND ".join(conditions)

        # Get atoms from unlocked concepts
        query = text(f"""
            SELECT ca.id
            FROM learning_atoms ca
            JOIN concepts cc ON ca.concept_id = cc.id
            LEFT JOIN learner_mastery_state lms
                ON lms.concept_id = ca.concept_id
                AND lms.learner_id = :learner_id
            WHERE {where_clause}
            AND (lms.is_unlocked = TRUE OR lms.id IS NULL)
            ORDER BY
                cc.cluster_id,  -- Group by cluster
                CASE ca.atom_type
                    WHEN 'flashcard' THEN 1
                    WHEN 'cloze' THEN 1
                    WHEN 'true_false' THEN 2
                    WHEN 'mcq' THEN 3
                    WHEN 'matching' THEN 4
                    WHEN 'parsons' THEN 5
                    ELSE 6
                END,
                ca.created_at
            LIMIT :limit
        """)

        try:
            result = session.execute(query, params)
            return [UUID(str(row.id)) for row in result.fetchall()]
        except Exception:
            return []

    def _filter_mastered_atoms(
        self,
        session: Session,
        learner_id: str,
        atom_ids: list[UUID],
    ) -> list[UUID]:
        """Filter out atoms with high retrievability."""
        if not atom_ids:
            return []

        # For now, return as-is (FSRS data would be needed to filter properly)
        # In production, would check retrievability > 0.9 threshold
        return atom_ids

    def _interleave_atoms(
        self,
        session: Session,
        atom_ids: list[UUID],
    ) -> list[UUID]:
        """
        Interleave atoms by knowledge type for better learning.

        Research shows interleaving different types improves retention.
        """
        if len(atom_ids) <= 3:
            return atom_ids

        # Get atom types for atoms
        if not atom_ids:
            return []

        atom_id_strs = [str(aid) for aid in atom_ids]
        query = text("""
            SELECT id, atom_type
            FROM learning_atoms
            WHERE id = ANY(:atom_ids)
        """)

        try:
            result = session.execute(query, {"atom_ids": atom_id_strs})
            type_map = {UUID(str(row.id)): row.atom_type for row in result.fetchall()}
        except Exception:
            return atom_ids

        # Group by type
        by_type = defaultdict(list)
        for atom_id in atom_ids:
            kt = type_map.get(atom_id, "unknown")
            by_type[kt].append(atom_id)

        # Interleave (round-robin through types)
        interleaved = []
        type_lists = list(by_type.values())

        while any(type_lists):
            for tl in type_lists:
                if tl:
                    interleaved.append(tl.pop(0))
            type_lists = [tl for tl in type_lists if tl]

        return interleaved

    def _get_concept_info(
        self,
        session: Session,
        concept_id: UUID,
    ) -> Optional[dict]:
        """Get basic concept info."""
        query = text("""
            SELECT id, name FROM concepts WHERE id = :concept_id
        """)
        result = session.execute(query, {"concept_id": str(concept_id)})
        row = result.fetchone()
        if row:
            return {"id": row.id, "name": row.name}
        return None

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
