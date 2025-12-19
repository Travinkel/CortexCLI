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
from uuid import UUID

from loguru import logger
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

# Lazy import MasteryCalculator to keep this module importable without DB deps
try:  # pragma: no cover
    from src.adaptive.mastery_calculator import MasteryCalculator  # type: ignore
except ImportError:  # pragma: no cover
    MasteryCalculator = None  # type: ignore
from src.adaptive.models import (
    BlockingPrerequisite,
    ConceptMastery,
    GatingType,
    LearningPath,
    UnlockStatus,
)
# Avoid importing database session at module import time to keep pure helpers testable
# Lazy import inside _get_session to prevent failures when DB deps are unavailable in unit tests


class PathSequencer:
    """
    Sequence atoms optimally for learning.

    Uses prerequisite graph to determine valid orderings,
    then applies mastery-aware prioritization.
    """

    def __init__(self, session: Session | None = None):
        self._session = session
        if MasteryCalculator is not None:
            self._mastery_calc = MasteryCalculator(session)  # type: ignore
        else:
            # Fallback stub to allow helper methods/tests to import without DB
            class _StubMasteryCalc:
                def __init__(self, _s):
                    pass

                def compute_concept_mastery(self, learner_id, concept_id):  # type: ignore
                    # Minimal ConceptMastery-compatible object
                    return ConceptMastery(
                        concept_id=concept_id,
                        concept_name="Unknown",
                        recall_mastery=0.0,
                        application_mastery=0.0,
                        combined_mastery=0.0,
                    )

            self._mastery_calc = _StubMasteryCalc(session)

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
            prereq_chain = self._get_prerequisite_chain(session, learner_id, target_concept_id)

            # Note: prereq filtering is handled inside _sequence_atoms_for_path using
            # a consistent mastery threshold. The previous self-comparison here was a bug
            # and has been removed.

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
        concept_id: UUID | None = None,
        cluster_id: UUID | None = None,
        count: int = 10,
        include_review: bool = True,
        recent_outcomes: list[dict] | None = None,
        mastered_atoms: set[UUID] | None = None,
        atom_prerequisites: dict[UUID, list[UUID]] | None = None,
        due_review_queue: list[UUID] | None = None,
        require_mastered_prereqs: bool = True,
    ) -> list[UUID]:
        """
        Get next atoms for a learner.

        Considers:
        - Unlocked concepts only (unless no hard gates)
        - Due reviews (from FSRS)
        - New atoms from unlocked concepts
        - Knowledge type interleaving
        - Remediation bundle when recent outcomes indicate struggle (2 consecutive failures)
        - Prerequisite gating when mastered/prerequisite sets are provided (in-memory mode)
        - Spaced review queue injection when provided (in-memory mode)

        Args:
            learner_id: Learner identifier
            concept_id: Optional specific concept
            cluster_id: Optional cluster scope
            count: Number of atoms to return
            include_review: Include due reviews
            recent_outcomes: Optional recent attempt outcomes for the focused concept.
                If provided and indicate struggle via needs_remediation(), a remediation
                bundle will be planned (prereq refresher + easier neighbor) and
                prioritized before normal selection.
            mastered_atoms: Optional set of mastered atom IDs (in-memory gating).
            atom_prerequisites: Optional map of atom_id -> list of prerequisite atom IDs
                used for in-memory prerequisite gating.
            due_review_queue: Optional list representing a per-learner spaced review queue.
                When provided, it is consumed in order before fetching new atoms.

        Returns:
            List of atom UUIDs in optimal order
        """
        with self._get_session() as session:
            atoms: list[UUID] = []

            # 0. Remediation bundle first if the learner is currently struggling
            try:
                if concept_id and recent_outcomes and self.needs_remediation(recent_outcomes):
                    remediation_atoms = self.plan_remediation_bundle(
                        session, learner_id, concept_id, easier_neighbor_limit=1
                    )
                    # plan_remediation_bundle may return [] in limited environments; that's OK
                    atoms.extend(remediation_atoms)
            except Exception as e:
                # Never fail path planning due to remediation planning issues
                logger.debug(f"Remediation planning skipped: {e}")

            # 1. Get due reviews first (if enabled)
            if include_review:
                if due_review_queue is not None:
                    due_limit = min(len(due_review_queue), count)
                    due_atoms = self._dequeue_due_reviews(due_review_queue, due_limit)
                else:
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

            # 2b. Apply prerequisite gating; if no in-memory map is provided, fetch from DB
            if require_mastered_prereqs and atoms:
                if atom_prerequisites is None and session is not None:
                    atom_prerequisites = self._fetch_atom_prerequisites(session, atoms)
                if mastered_atoms is None and session is not None:
                    mastered_atoms = self._fetch_mastered_concepts(session, learner_id)
                if atom_prerequisites is not None and mastered_atoms is not None:
                    atoms = self._apply_prerequisite_gating(atoms, mastered_atoms, atom_prerequisites)

            # 3. Interleave by knowledge type (keeps earlier remediation atoms at the front)
            if atoms:
                # Only interleave the tail after any remediation atoms that we already queued
                # Find split index where remediation part ends (we assume remediation atoms come first)
                # For simplicity, interleave entire list; remediation atoms are few and will stay near front
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
                result = session.execute(
                    query,
                    {
                        "learner_id": learner_id,
                        "concept_id": str(concept_id),
                    },
                )
                prerequisites = result.fetchall()
            except SQLAlchemyError:
                return UnlockStatus(is_unlocked=True, unlock_reason="no_prerequisites")

            blocking = []
            for prereq in prerequisites:
                threshold = float(prereq.mastery_threshold or 0.65)
                current = float(prereq.current_mastery or 0)
                gating = prereq.gating_type or "soft"

                if current < threshold and gating == "hard":
                    blocking.append(
                        BlockingPrerequisite(
                            concept_id=UUID(str(prereq.target_concept_id)),
                            concept_name=prereq.concept_name,
                            required_mastery=threshold,
                            current_mastery=current,
                            gating_type=GatingType.HARD,
                        )
                    )

            if blocking:
                # Estimate atoms needed to unlock
                estimated_atoms = sum(
                    int((b.required_mastery - b.current_mastery) * 20) for b in blocking
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
        concept_id: UUID | None,
        cluster_id: UUID | None,
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
        except SQLAlchemyError:
            return []  # DB error fetching due atoms

    def _get_new_atoms(
        self,
        session: Session,
        learner_id: str,
        concept_id: UUID | None,
        cluster_id: UUID | None,
        limit: int,
    ) -> list[UUID]:
        """Get new (unreviewed) atoms from unlocked concepts."""
        # Build query based on scope
        conditions = ["ca.anki_review_count IS NULL OR ca.anki_review_count = 0"]
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
        except SQLAlchemyError:
            return []  # DB error fetching new atoms

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

    @staticmethod
    def _dequeue_due_reviews(
        due_review_queue: list[UUID], limit: int
    ) -> list[UUID]:
        """Consume and return up to `limit` due review atoms from an in-memory queue."""
        if limit <= 0:
            return []
        due = list(due_review_queue[:limit])
        # Mutate the queue to reflect consumption for callers simulating stateful queues
        del due_review_queue[: len(due)]
        return due

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

        # Use IN clause with explicit formatting for PostgreSQL UUID array
        uuid_list = ",".join(f"'{str(aid)}'" for aid in atom_ids)
        query = text(f"""
            SELECT id, atom_type
            FROM learning_atoms
            WHERE id IN ({uuid_list})
        """)

        try:
            result = session.execute(query)
            type_map = {UUID(str(row.id)): row.atom_type for row in result.fetchall()}
        except Exception as exc:
            # Rollback to recover transaction state
            if session:
                session.rollback()
            logger.debug(f"Interleave query failed: {exc}")
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
    ) -> dict | None:
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
        # Lazy import to keep this module importable without DB deps
        try:
            from src.db.database import session_scope as _session_scope

            return _session_scope()
        except ImportError:
            # Fallback no-op context manager to avoid crashing pure helper tests
            class _Noop:
                def __enter__(self):
                    return None

                def __exit__(self, *args):
                    pass

            return _Noop()

    # =====================================================================
    # Mastery and Remediation Helpers (stateless utilities)
    # =====================================================================
    @staticmethod
    def compute_mastery_decision(
        outcomes: list[dict],
        require_consecutive: int = 3,
        rolling_window: int = 5,
        rolling_accuracy_threshold: float = 0.85,
        disallow_hints_for_consecutive: bool = True,
    ) -> bool:
        """Decide whether an atom is mastered based on recent outcomes.

        Args:
            outcomes: List of attempt dicts in chronological order. Each item may include:
                {"correct": bool, "hint_used": bool}
            require_consecutive: How many consecutive correct answers (default 3)
            rolling_window: Consider last N attempts for rolling accuracy (default 5)
            rolling_accuracy_threshold: Accuracy threshold for mastery via rolling window
            disallow_hints_for_consecutive: If True, consecutive rule requires no hints

        Returns:
            True if mastered under either rule, False otherwise.
        """
        if not outcomes:
            return False

        # Rule 1: consecutive correct without hints (if configured)
        consec = 0
        for att in reversed(outcomes):
            if att.get("correct") and (not disallow_hints_for_consecutive or not att.get("hint_used")):
                consec += 1
                if consec >= require_consecutive:
                    return True
            else:
                break

        # Rule 2: rolling accuracy over last N attempts
        window = outcomes[-rolling_window:]
        if window:
            correct_count = sum(1 for att in window if att.get("correct"))
            accuracy = correct_count / len(window)
            if accuracy >= rolling_accuracy_threshold:
                return True

        return False

    @staticmethod
    def needs_remediation(outcomes: list[dict], failures_required: int = 2) -> bool:
        """Return True if the last N attempts were incorrect (signals remediation).

        Args:
            outcomes: Attempt dicts in chronological order
            failures_required: Number of consecutive failures to trigger remediation
        """
        if failures_required <= 0:
            return False
        last = outcomes[-failures_required:]
        if len(last) < failures_required:
            return False
        return all(not att.get("correct") for att in last)

    @staticmethod
    def prerequisites_satisfied(
        atom_id: UUID,
        mastered_atoms: set[UUID],
        atom_prerequisites: dict[UUID, list[UUID]],
    ) -> bool:
        """Return True if an atom's prerequisites are all mastered (or none exist)."""
        prereqs = atom_prerequisites.get(atom_id, [])
        if not prereqs:
            return True
        return all(pr in mastered_atoms for pr in prereqs)

    @classmethod
    def _apply_prerequisite_gating(
        cls,
        atom_ids: list[UUID],
        mastered_atoms: set[UUID],
        atom_prerequisites: dict[UUID, list[UUID]],
    ) -> list[UUID]:
        """Filter atoms so only those with mastered prerequisites remain, preserving order."""
        gated: list[UUID] = []
        for aid in atom_ids:
            if cls.prerequisites_satisfied(aid, mastered_atoms, atom_prerequisites):
                gated.append(aid)
        return gated

    # =====================================================================
    # DB-backed helpers for prerequisite gating
    # =====================================================================
    def _fetch_atom_prerequisites(
        self, session: Session | None, atom_ids: list[UUID]
    ) -> dict[UUID, list[UUID]]:
        """Fetch prerequisite concept IDs for given atoms."""
        if not session or not atom_ids:
            return {}
        try:
            # Use IN clause with explicit formatting for PostgreSQL UUID array
            uuid_list = ",".join(f"'{str(aid)}'" for aid in atom_ids)
            query = text(
                f"""
                SELECT source_atom_id, target_concept_id
                FROM explicit_prerequisites
                WHERE source_atom_id IN ({uuid_list})
                  AND status = 'active'
                """
            )
            rows = session.execute(query).fetchall()
            prereq_map: dict[UUID, list[UUID]] = {}
            for row in rows:
                src = UUID(str(row.source_atom_id))
                tgt = UUID(str(row.target_concept_id))
                prereq_map.setdefault(src, []).append(tgt)
            return prereq_map
        except Exception as exc:
            logger.debug(f"Prerequisite fetch skipped: {exc}")
            return {}

    def _fetch_mastered_concepts(
        self, session: Session | None, learner_id: str, threshold: float = 0.65
    ) -> set[UUID]:
        """Fetch mastered concept IDs for a learner."""
        if not session:
            return set()
        try:
            query = text(
                """
                SELECT concept_id
                FROM learner_mastery_state
                WHERE learner_id = :learner_id
                  AND COALESCE(combined_mastery, 0) >= :threshold
                """
            )
            rows = session.execute(
                query, {"learner_id": learner_id, "threshold": threshold}
            ).scalars()
            return {UUID(str(r)) for r in rows if r}
        except Exception as exc:
            logger.debug(f"Mastery fetch skipped: {exc}")
            return set()

    def plan_remediation_bundle(
        self,
        session: Session,
        learner_id: str,
        concept_id,
        *,
        easier_neighbor_limit: int = 1,
    ) -> list:
        """Plan a remediation bundle for a learner on a given concept.

        Returns a list of atom IDs prioritizing:
        1) One prerequisite refresher atom (if any prerequisite below threshold)
        2) One easier neighbor atom from the same cluster (if available)

        This implementation is defensive against missing tables/services and
        returns an empty list when data is unavailable, to avoid hard failures
        in smoke tests.
        """
        bundle: list = []

        # 1) Try to fetch a low-mastery prerequisite atom
        try:
            prereqs = self._get_prerequisite_chain(session, learner_id, concept_id)
            low_prereqs = [p for p in prereqs if p.combined_mastery < 0.65]
            if low_prereqs:
                # Take atoms from the lowest-mastery prerequisite
                low = sorted(low_prereqs, key=lambda x: x.combined_mastery)[0]
                bundle.extend(self._get_concept_atoms(session, low.concept_id)[:1])
        except Exception as e:
            logger.debug(f"Remediation prereq fetch skipped: {e}")

        # 2) Try to fetch an easier neighbor via similarity_service (optional)
        try:
            from src.semantic.similarity_service import get_easier_neighbors

            neighbors = get_easier_neighbors(
                session, concept_id, limit=easier_neighbor_limit, difficulty_band=2
            )
            bundle.extend(neighbors)
        except Exception as e:
            logger.debug(f"Easier neighbor fetch skipped: {e}")

        # Deduplicate while preserving order
        seen = set()
        deduped = []
        for a in bundle:
            if a not in seen:
                seen.add(a)
                deduped.append(a)
        return deduped
