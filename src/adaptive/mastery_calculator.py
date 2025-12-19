"""
Mastery Calculator.

Computes learner mastery from FSRS review data and quiz performance.

Formula:
    combined_mastery = (review_mastery × 0.625) + (quiz_mastery × 0.375)

Where:
    review_mastery = weighted_avg(retrievability)
                     retrievability = e^(-days_since_review / stability)
                     weight = min(review_count, 20)

    quiz_mastery = best_of_last_3_attempts
"""

from __future__ import annotations

import math
from datetime import UTC, datetime
from uuid import UUID

from loguru import logger
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from src.adaptive.models import (
    ATOM_TYPE_KNOWLEDGE_MAP,
    MASTERY_WEIGHTS,
    ConceptMastery,
    KnowledgeBreakdown,
    MasteryLevel,
)
from src.db.database import session_scope


class MasteryCalculator:
    """
    Calculate learner mastery from review and quiz data.

    Uses FSRS stability/retrievability for review mastery and
    quiz scores for quiz mastery, weighted according to learning
    science research (62.5% review, 37.5% quiz).
    """

    def __init__(self, session: Session | None = None):
        """
        Initialize calculator.

        Args:
            session: Optional SQLAlchemy session. If not provided,
                    uses session_scope context manager.
        """
        self._session = session

    def compute_concept_mastery(
        self,
        learner_id: str,
        concept_id: UUID,
    ) -> ConceptMastery:
        """
        Compute full mastery state for a concept.

        Args:
            learner_id: Learner identifier
            concept_id: Concept UUID

        Returns:
            ConceptMastery with all mastery metrics
        """
        with self._get_session() as session:
            # Get concept info
            concept_info = self._get_concept_info(session, concept_id)
            if not concept_info:
                logger.warning(f"Concept not found: {concept_id}")
                return ConceptMastery(
                    concept_id=concept_id,
                    concept_name="Unknown",
                )

            # Compute review mastery from atom retrievabilities
            review_mastery = self._compute_review_mastery(session, learner_id, concept_id)

            # Compute quiz mastery from quiz attempts
            quiz_mastery = self._compute_quiz_mastery(session, learner_id, concept_id)

            # Combined mastery (62.5% review + 37.5% quiz)
            combined_mastery = (
                review_mastery * MASTERY_WEIGHTS["review"] + quiz_mastery * MASTERY_WEIGHTS["quiz"]
            )

            # Knowledge type breakdown
            knowledge_breakdown = self._compute_knowledge_breakdown(session, learner_id, concept_id)

            # Get activity counts
            activity = self._get_activity_counts(session, learner_id, concept_id)

            # Check unlock status
            is_unlocked, unlock_reason = self._check_unlock_status(
                session, learner_id, concept_id, combined_mastery
            )

            return ConceptMastery(
                concept_id=concept_id,
                concept_name=concept_info["name"],
                review_mastery=review_mastery,
                quiz_mastery=quiz_mastery,
                combined_mastery=combined_mastery,
                knowledge_breakdown=knowledge_breakdown,
                is_unlocked=is_unlocked,
                unlock_reason=unlock_reason,
                review_count=activity.get("review_count", 0),
                quiz_attempt_count=activity.get("quiz_count", 0),
                last_review_at=activity.get("last_review"),
                last_quiz_at=activity.get("last_quiz"),
            )

    def _compute_review_mastery(
        self,
        session: Session,
        learner_id: str,
        concept_id: UUID,
    ) -> float:
        """
        Compute review mastery from FSRS retrievability.

        Uses weighted average where weight = min(review_count, 20).
        Retrievability = e^(-days_since_review / stability)
        """
        # Get atoms for concept with their FSRS metrics
        # Uses anki_stability (from pull_service) as primary stability source,
        # with fallback to stability_days for legacy compatibility
        query = text("""
            SELECT
                ca.id,
                COALESCE(ca.anki_stability, ca.stability_days) as stability_days,
                ca.retrievability,
                ca.anki_synced_at as anki_last_review,
                ca.anki_review_count
            FROM learning_atoms ca
            WHERE ca.concept_id = :concept_id
            AND (ca.anki_stability IS NOT NULL OR ca.stability_days IS NOT NULL)
            AND COALESCE(ca.anki_stability, ca.stability_days, 0) > 0
        """)

        result = session.execute(query, {"concept_id": str(concept_id)})
        atoms = result.fetchall()

        if not atoms:
            return 0.0

        total_weight = 0.0
        weighted_sum = 0.0
        now = datetime.now(UTC)

        for atom in atoms:
            stability = float(atom.stability_days) if atom.stability_days else 0
            last_review = atom.anki_last_review
            review_count = atom.anki_review_count or 0

            if stability <= 0:
                continue

            # Calculate current retrievability
            if last_review:
                # Handle timezone-aware comparison
                if last_review.tzinfo is None:
                    last_review = last_review.replace(tzinfo=UTC)
                days_since = (now - last_review).days
            else:
                days_since = 30  # Default if no review date

            # FSRS retrievability formula
            retrievability = math.exp(-days_since / stability)

            # Weight by review count (capped at 20 to prevent domination)
            weight = min(review_count, 20) if review_count > 0 else 1

            weighted_sum += retrievability * weight
            total_weight += weight

        if total_weight > 0:
            return weighted_sum / total_weight
        return 0.0

    def _compute_quiz_mastery(
        self,
        session: Session,
        learner_id: str,
        concept_id: UUID,
    ) -> float:
        """
        Compute quiz mastery from quiz attempts.

        Uses best score from last 3 attempts.

        Queries BOTH quiz response tables:
        - atom_responses: from in-app quizzes (MCQ, T/F, Matching, Parsons)
        - session_atom_responses: from adaptive learning sessions
        """
        # Query both quiz response tables and union the results
        # atom_responses is the primary source for NLS quizzes
        query = text("""
            WITH all_responses AS (
                -- From in-app quiz engine (MCQ, T/F, Matching, Parsons)
                SELECT
                    NULL::DECIMAL as score,
                    ar.is_correct,
                    ar.responded_at as answered_at
                FROM atom_responses ar
                JOIN learning_atoms ca ON ar.atom_id = ca.id
                WHERE ca.concept_id = :concept_id
                  AND ar.user_id = :learner_id
                  AND ar.responded_at IS NOT NULL

                UNION ALL

                -- From adaptive learning engine
                SELECT
                    sar.score,
                    sar.is_correct,
                    sar.answered_at
                FROM session_atom_responses sar
                JOIN learning_atoms ca ON sar.atom_id = ca.id
                WHERE ca.concept_id = :concept_id
                  AND sar.session_id IN (
                      SELECT id FROM learning_path_sessions
                      WHERE learner_id = :learner_id
                      AND mode IN ('quiz', 'adaptive')
                  )
                  AND sar.answered_at IS NOT NULL
            )
            SELECT score, is_correct, answered_at
            FROM all_responses
            ORDER BY answered_at DESC
            LIMIT 10
        """)

        try:
            result = session.execute(
                query,
                {
                    "concept_id": str(concept_id),
                    "learner_id": learner_id,
                },
            )
            responses = result.fetchall()
        except SQLAlchemyError:
            # Table might not exist yet
            return 0.0

        if not responses:
            return 0.0

        # Get scores from last 3 attempts
        scores = []
        for resp in responses[:3]:
            if resp.score is not None:
                scores.append(float(resp.score))
            elif resp.is_correct is not None:
                scores.append(1.0 if resp.is_correct else 0.0)

        if scores:
            return max(scores)  # Best of last 3
        return 0.0

    def _compute_knowledge_breakdown(
        self,
        session: Session,
        learner_id: str,
        concept_id: UUID,
    ) -> KnowledgeBreakdown:
        """
        Compute mastery breakdown by knowledge type.

        Maps atom types to knowledge categories and averages retrievabilities.
        """
        # Uses anki_stability as primary stability source
        query = text("""
            SELECT
                ca.atom_type,
                COALESCE(ca.anki_stability, ca.stability_days) as stability_days,
                ca.retrievability,
                ca.anki_synced_at as anki_last_review,
                ca.anki_review_count
            FROM learning_atoms ca
            WHERE ca.concept_id = :concept_id
            AND (ca.anki_stability IS NOT NULL OR ca.stability_days IS NOT NULL)
        """)

        result = session.execute(query, {"concept_id": str(concept_id)})
        atoms = result.fetchall()

        # Group by knowledge type
        scores = {
            "declarative": [],
            "procedural": [],
            "application": [],
        }

        now = datetime.now(UTC)

        for atom in atoms:
            atom_type = (atom.atom_type or "flashcard").lower()
            knowledge_type = ATOM_TYPE_KNOWLEDGE_MAP.get(atom_type, "declarative")

            stability = float(atom.stability_days) if atom.stability_days else 0
            if stability <= 0:
                continue

            last_review = atom.anki_last_review
            if last_review:
                if last_review.tzinfo is None:
                    last_review = last_review.replace(tzinfo=UTC)
                days_since = (now - last_review).days
            else:
                days_since = 30

            retrievability = math.exp(-days_since / stability)
            scores[knowledge_type].append(retrievability)

        # Calculate averages (0-10 scale)
        def avg_to_10(values: list) -> float:
            if not values:
                return 0.0
            return sum(values) / len(values) * 10

        return KnowledgeBreakdown(
            dec_score=avg_to_10(scores["declarative"]),
            proc_score=avg_to_10(scores["procedural"]),
            app_score=avg_to_10(scores["application"]),
        )

    def _get_concept_info(
        self,
        session: Session,
        concept_id: UUID,
    ) -> dict | None:
        """Get basic concept information."""
        query = text("""
            SELECT id, name, definition
            FROM concepts
            WHERE id = :concept_id
        """)
        result = session.execute(query, {"concept_id": str(concept_id)})
        row = result.fetchone()
        if row:
            return {"id": row.id, "name": row.name, "definition": row.definition}
        return None

    def _get_activity_counts(
        self,
        session: Session,
        learner_id: str,
        concept_id: UUID,
    ) -> dict:
        """Get review and quiz activity counts."""
        # For now, return from learner_mastery_state if exists
        query = text("""
            SELECT
                review_count,
                quiz_attempt_count,
                last_review_at,
                last_quiz_at
            FROM learner_mastery_state
            WHERE learner_id = :learner_id
            AND concept_id = :concept_id
        """)
        try:
            result = session.execute(
                query,
                {
                    "learner_id": learner_id,
                    "concept_id": str(concept_id),
                },
            )
            row = result.fetchone()
            if row:
                return {
                    "review_count": row.review_count or 0,
                    "quiz_count": row.quiz_attempt_count or 0,
                    "last_review": row.last_review_at,
                    "last_quiz": row.last_quiz_at,
                }
        except SQLAlchemyError:
            pass  # DB error fetching engagement metrics
        return {}

    def _check_unlock_status(
        self,
        session: Session,
        learner_id: str,
        concept_id: UUID,
        current_mastery: float,
    ) -> tuple[bool, str | None]:
        """Check if concept is unlocked for learner."""
        # Check for hard prerequisites that are not met
        query = text("""
            SELECT
                ep.target_concept_id,
                ep.mastery_threshold,
                ep.gating_type,
                COALESCE(lms.combined_mastery, 0) as current_mastery
            FROM explicit_prerequisites ep
            LEFT JOIN learner_mastery_state lms
                ON lms.concept_id = ep.target_concept_id
                AND lms.learner_id = :learner_id
            WHERE ep.source_concept_id = :concept_id
            AND ep.status = 'active'
            AND ep.gating_type = 'hard'
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
            # Table might not exist
            return True, "no_prerequisites"

        # Check if any hard prerequisites are not met
        for prereq in prerequisites:
            threshold = float(prereq.mastery_threshold or 0.65)
            prereq_mastery = float(prereq.current_mastery or 0)
            if prereq_mastery < threshold:
                return False, "blocked_by_prerequisites"

        # All prerequisites met (or no hard prerequisites)
        if not prerequisites:
            return True, "no_prerequisites"
        return True, "prerequisites_met"

    def update_mastery_state(
        self,
        learner_id: str,
        concept_id: UUID,
        review_mastery: float | None = None,
        quiz_mastery: float | None = None,
    ) -> ConceptMastery:
        """
        Update and persist mastery state for a learner/concept.

        Args:
            learner_id: Learner identifier
            concept_id: Concept UUID
            review_mastery: New review mastery (if updating from review)
            quiz_mastery: New quiz mastery (if updating from quiz)

        Returns:
            Updated ConceptMastery
        """
        with self._get_session() as session:
            try:
                # First check if state exists
                check_query = text("""
                    SELECT id, review_mastery, quiz_mastery
                    FROM learner_mastery_state
                    WHERE learner_id = :learner_id AND concept_id = :concept_id
                """)
                result = session.execute(
                    check_query,
                    {
                        "learner_id": learner_id,
                        "concept_id": str(concept_id),
                    },
                )
                existing = result.fetchone()

                if existing:
                    # Get current values if not updating
                    current_review = float(existing.review_mastery or 0)
                    current_quiz = float(existing.quiz_mastery or 0)
                    new_review = review_mastery if review_mastery is not None else current_review
                    new_quiz = quiz_mastery if quiz_mastery is not None else current_quiz

                    # Calculate combined mastery (62.5% review + 37.5% quiz)
                    combined = (
                        new_review * MASTERY_WEIGHTS["review"] + new_quiz * MASTERY_WEIGHTS["quiz"]
                    )

                    # Update existing state
                    update_query = text("""
                        UPDATE learner_mastery_state
                        SET review_mastery = :review_mastery,
                            quiz_mastery = :quiz_mastery,
                            combined_mastery = :combined_mastery,
                            last_review_at = CASE WHEN :is_review_update THEN NOW() ELSE last_review_at END,
                            last_quiz_at = CASE WHEN :is_quiz_update THEN NOW() ELSE last_quiz_at END,
                            review_count = CASE WHEN :is_review_update THEN review_count + 1 ELSE review_count END,
                            quiz_attempt_count = CASE WHEN :is_quiz_update THEN quiz_attempt_count + 1 ELSE quiz_attempt_count END,
                            updated_at = NOW()
                        WHERE learner_id = :learner_id AND concept_id = :concept_id
                    """)
                    session.execute(
                        update_query,
                        {
                            "learner_id": learner_id,
                            "concept_id": str(concept_id),
                            "review_mastery": new_review,
                            "quiz_mastery": new_quiz,
                            "combined_mastery": combined,
                            "is_review_update": review_mastery is not None,
                            "is_quiz_update": quiz_mastery is not None,
                        },
                    )
                else:
                    # Create new state
                    new_review = review_mastery if review_mastery is not None else 0
                    new_quiz = quiz_mastery if quiz_mastery is not None else 0
                    combined = (
                        new_review * MASTERY_WEIGHTS["review"] + new_quiz * MASTERY_WEIGHTS["quiz"]
                    )

                    insert_query = text("""
                        INSERT INTO learner_mastery_state (
                            learner_id, concept_id, review_mastery, quiz_mastery,
                            combined_mastery, review_count, quiz_attempt_count,
                            last_review_at, last_quiz_at, is_unlocked, unlock_reason
                        ) VALUES (
                            :learner_id, :concept_id, :review_mastery, :quiz_mastery,
                            :combined_mastery,
                            CASE WHEN :is_review_update THEN 1 ELSE 0 END,
                            CASE WHEN :is_quiz_update THEN 1 ELSE 0 END,
                            CASE WHEN :is_review_update THEN NOW() ELSE NULL END,
                            CASE WHEN :is_quiz_update THEN NOW() ELSE NULL END,
                            TRUE, 'new_learner'
                        )
                    """)
                    session.execute(
                        insert_query,
                        {
                            "learner_id": learner_id,
                            "concept_id": str(concept_id),
                            "review_mastery": new_review,
                            "quiz_mastery": new_quiz,
                            "combined_mastery": combined,
                            "is_review_update": review_mastery is not None,
                            "is_quiz_update": quiz_mastery is not None,
                        },
                    )

                session.commit()
                logger.debug(
                    f"Updated mastery state for {learner_id}/{concept_id}: review={review_mastery}, quiz={quiz_mastery}"
                )
            except Exception as e:
                logger.warning(f"Could not update mastery state: {e}")
                session.rollback()

            # Return fresh mastery calculation
            return self.compute_concept_mastery(learner_id, concept_id)

    def compute_all_concept_mastery(
        self,
        learner_id: str,
        concept_ids: list[UUID] | None = None,
    ) -> list[ConceptMastery]:
        """
        Compute mastery for multiple concepts.

        Args:
            learner_id: Learner identifier
            concept_ids: Optional list of concept IDs. If None, computes for all.

        Returns:
            List of ConceptMastery objects
        """
        with self._get_session() as session:
            # Get concept IDs if not provided
            if concept_ids is None:
                query = text("SELECT id FROM concepts ORDER BY name")
                result = session.execute(query)
                concept_ids = [UUID(str(row.id)) for row in result.fetchall()]

        masteries = []
        for concept_id in concept_ids:
            mastery = self.compute_concept_mastery(learner_id, concept_id)
            masteries.append(mastery)

        return masteries

    def get_mastery_summary(
        self,
        learner_id: str,
        cluster_id: UUID | None = None,
    ) -> dict:
        """
        Get mastery summary for a learner.

        Args:
            learner_id: Learner identifier
            cluster_id: Optional cluster to filter by

        Returns:
            Summary dict with counts by mastery level
        """
        with self._get_session() as session:
            if cluster_id:
                query = text("""
                    SELECT
                        lms.combined_mastery,
                        lms.is_unlocked
                    FROM learner_mastery_state lms
                    JOIN concepts cc ON lms.concept_id = cc.id
                    WHERE lms.learner_id = :learner_id
                    AND cc.cluster_id = :cluster_id
                """)
                params = {"learner_id": learner_id, "cluster_id": str(cluster_id)}
            else:
                query = text("""
                    SELECT combined_mastery, is_unlocked
                    FROM learner_mastery_state
                    WHERE learner_id = :learner_id
                """)
                params = {"learner_id": learner_id}

            try:
                result = session.execute(query, params)
                rows = result.fetchall()
            except SQLAlchemyError:
                rows = []  # DB error fetching mastery state

            # Count by level
            counts = {level.value: 0 for level in MasteryLevel}
            unlocked = 0
            locked = 0
            total_mastery = 0.0

            for row in rows:
                mastery = float(row.combined_mastery or 0)
                level = MasteryLevel.from_score(mastery)
                counts[level.value] += 1
                total_mastery += mastery

                if row.is_unlocked:
                    unlocked += 1
                else:
                    locked += 1

            total = len(rows)
            avg_mastery = total_mastery / total if total > 0 else 0

            return {
                "total_concepts": total,
                "unlocked": unlocked,
                "locked": locked,
                "average_mastery": avg_mastery,
                "by_level": counts,
            }

    def initialize_mastery_from_anki(
        self,
        learner_id: str,
        track_id: UUID | None = None,
    ) -> int:
        """
        Initialize mastery state from existing Anki review data.

        Reads FSRS metrics (stability_days, retrievability) from learning_atoms
        and creates/updates learner_mastery_state for each concept.

        Args:
            learner_id: Learner identifier
            track_id: Optional track to filter by

        Returns:
            Number of concepts initialized
        """
        with self._get_session() as session:
            # Query to get concepts with their review-based mastery
            track_filter = ""
            params = {"learner_id": learner_id}

            if track_id:
                track_filter = "AND cm.track_id = :track_id"
                params["track_id"] = str(track_id)

            # Use anki_stability as primary stability source
            query = text(f"""
                SELECT
                    cc.id as concept_id,
                    cc.name as concept_name,
                    COUNT(ca.id) as atom_count,
                    SUM(COALESCE(ca.anki_review_count, 0)) as total_reviews,
                    AVG(
                        CASE
                            WHEN COALESCE(ca.anki_stability, ca.stability_days) > 0 AND ca.anki_synced_at IS NOT NULL THEN
                                EXP(-EXTRACT(EPOCH FROM (NOW() - ca.anki_synced_at)) / 86400.0 / COALESCE(ca.anki_stability, ca.stability_days))
                            ELSE 0
                        END
                    ) as avg_retrievability
                FROM concepts cc
                JOIN learning_atoms ca ON ca.concept_id = cc.id
                LEFT JOIN ccna_sections cs ON ca.ccna_section_id = cs.section_id
                WHERE 1=1 {track_filter}
                GROUP BY cc.id, cc.name
                HAVING COUNT(ca.id) > 0
            """)

            result = session.execute(query, params)
            concepts = result.fetchall()

            count = 0
            for concept in concepts:
                # Calculate review mastery from avg retrievability
                review_mastery = float(concept.avg_retrievability or 0)

                # Get or create mastery state
                check_query = text("""
                    SELECT id FROM learner_mastery_state
                    WHERE learner_id = :learner_id AND concept_id = :concept_id
                """)
                existing = session.execute(
                    check_query,
                    {
                        "learner_id": learner_id,
                        "concept_id": str(concept.concept_id),
                    },
                ).fetchone()

                combined = review_mastery * MASTERY_WEIGHTS["review"]

                if existing:
                    update_query = text("""
                        UPDATE learner_mastery_state
                        SET review_mastery = :review_mastery,
                            combined_mastery = :combined_mastery,
                            review_count = :review_count,
                            updated_at = NOW()
                        WHERE learner_id = :learner_id AND concept_id = :concept_id
                    """)
                    session.execute(
                        update_query,
                        {
                            "learner_id": learner_id,
                            "concept_id": str(concept.concept_id),
                            "review_mastery": review_mastery,
                            "combined_mastery": combined,
                            "review_count": int(concept.total_reviews or 0),
                        },
                    )
                else:
                    insert_query = text("""
                        INSERT INTO learner_mastery_state (
                            learner_id, concept_id, review_mastery, quiz_mastery,
                            combined_mastery, review_count, quiz_attempt_count,
                            is_unlocked, unlock_reason
                        ) VALUES (
                            :learner_id, :concept_id, :review_mastery, 0,
                            :combined_mastery, :review_count, 0,
                            TRUE, 'initialized_from_anki'
                        )
                    """)
                    session.execute(
                        insert_query,
                        {
                            "learner_id": learner_id,
                            "concept_id": str(concept.concept_id),
                            "review_mastery": review_mastery,
                            "combined_mastery": combined,
                            "review_count": int(concept.total_reviews or 0),
                        },
                    )

                count += 1

            session.commit()
            logger.info(f"Initialized mastery state for {count} concepts for learner {learner_id}")
            return count

    def _get_session(self):
        """Get session context manager."""
        if self._session:
            # Return a dummy context manager that yields the existing session
            class SessionWrapper:
                def __init__(self, s):
                    self.session = s

                def __enter__(self):
                    return self.session

                def __exit__(self, *args):
                    pass

            return SessionWrapper(self._session)
        return session_scope()


def calculate_combined_mastery(
    review_mastery: float,
    quiz_mastery: float,
) -> float:
    """
    Calculate combined mastery score.

    Formula: 62.5% review + 37.5% quiz

    Args:
        review_mastery: Review mastery (0-1)
        quiz_mastery: Quiz mastery (0-1)

    Returns:
        Combined mastery (0-1)
    """
    return review_mastery * MASTERY_WEIGHTS["review"] + quiz_mastery * MASTERY_WEIGHTS["quiz"]


def calculate_retrievability(
    stability_days: float,
    days_since_review: int,
) -> float:
    """
    Calculate FSRS retrievability.

    Formula: R = e^(-t/S)

    Args:
        stability_days: FSRS stability in days
        days_since_review: Days since last review

    Returns:
        Retrievability (0-1)
    """
    if stability_days <= 0:
        return 0.0
    return math.exp(-days_since_review / stability_days)
