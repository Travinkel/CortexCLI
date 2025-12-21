"""
Skill Mastery Tracker with Bayesian Updates and FSRS Integration.

This module tracks learner mastery per skill using:
- Weighted Bayesian updates based on atom responses
- FSRS scheduling parameters per skill
- Confidence interval estimation
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class SkillUpdate:
    """Result of skill mastery update."""

    skill_id: str
    skill_code: str
    old_mastery: float
    new_mastery: float
    confidence_interval: float
    retrievability: float
    stability: float  # FSRS stability in days
    next_review_date: datetime


@dataclass
class SkillMasteryState:
    """Current mastery state for a skill."""

    skill_id: str
    skill_code: str
    mastery_level: float
    confidence_interval: float
    practice_count: int
    consecutive_correct: int
    last_practiced: datetime | None
    retrievability: float
    difficulty: float
    stability: float


class SkillMasteryTracker:
    """
    Track learner mastery per skill using weighted Bayesian update + FSRS.

    Formula:
    - Mastery = Weighted average of atom responses targeting this skill
    - Update uses Bayes' theorem with prior = current mastery
    - FSRS parameters update per skill for scheduling
    """

    def __init__(self, db_connection: Any):
        """
        Initialize tracker with database connection.

        Args:
            db_connection: AsyncPG connection or SQLAlchemy session
        """
        self.db = db_connection

    async def update_skill_mastery(
        self,
        learner_id: str,
        atom_id: str,
        is_correct: bool,
        latency_ms: int,
        confidence: int,
    ) -> list[SkillUpdate]:
        """
        Update all skills linked to this atom based on learner response.

        Args:
            learner_id: Learner UUID
            atom_id: Atom UUID
            is_correct: Did learner answer correctly?
            latency_ms: Time taken to answer (milliseconds)
            confidence: Learner's confidence rating (1-5)

        Returns:
            List of SkillUpdate objects (one per skill linked to atom)
        """
        # Get all skills linked to this atom
        skill_links = await self._get_atom_skills(atom_id)

        if not skill_links:
            logger.warning(f"Atom {atom_id} has no skill links - skipping mastery update")
            return []

        updates = []
        for link in skill_links:
            # Get current mastery state
            current_state = await self._get_skill_mastery(learner_id, link["skill_id"])

            # Bayesian update
            new_mastery = self._bayesian_update(
                prior_mastery=current_state.mastery_level,
                is_correct=is_correct,
                weight=link["weight"],
                confidence=confidence,
            )

            # Update FSRS parameters
            fsrs_update = await self._update_fsrs_parameters(
                skill_id=link["skill_id"],
                learner_id=learner_id,
                is_correct=is_correct,
                latency_ms=latency_ms,
                current_difficulty=current_state.difficulty,
                current_stability=current_state.stability,
            )

            # Compute confidence interval
            confidence_interval = self._compute_confidence_interval(
                new_mastery, current_state.practice_count + 1
            )

            # Store update
            await self._save_skill_mastery(
                learner_id=learner_id,
                skill_id=link["skill_id"],
                mastery_level=new_mastery,
                confidence_interval=confidence_interval,
                practice_count=current_state.practice_count + 1,
                consecutive_correct=current_state.consecutive_correct + 1 if is_correct else 0,
                retrievability=fsrs_update["retrievability"],
                difficulty=fsrs_update["difficulty"],
                stability=fsrs_update["stability"],
            )

            updates.append(
                SkillUpdate(
                    skill_id=link["skill_id"],
                    skill_code=link["skill_code"],
                    old_mastery=current_state.mastery_level,
                    new_mastery=new_mastery,
                    confidence_interval=confidence_interval,
                    retrievability=fsrs_update["retrievability"],
                    stability=fsrs_update["stability"],
                    next_review_date=datetime.now() + timedelta(days=fsrs_update["stability"]),
                )
            )

        return updates

    def _bayesian_update(
        self, prior_mastery: float, is_correct: bool, weight: float, confidence: int
    ) -> float:
        """
        Bayesian update of mastery given new evidence.

        P(mastery | correct) = P(correct | mastery) * P(mastery) / P(correct)

        Args:
            prior_mastery: Current mastery estimate (0-1)
            is_correct: Did learner answer correctly?
            weight: How much this atom measures this skill (0-1)
            confidence: Learner's confidence (1-5)

        Returns:
            Updated mastery estimate (0-1)
        """
        # Confidence adjustment: High confidence + correct = bigger update
        confidence_factor = confidence / 5.0

        if is_correct:
            # Correct answer increases mastery
            # Higher weight = bigger update
            update_size = weight * confidence_factor * 0.1
            new_mastery = min(1.0, prior_mastery + update_size)
        else:
            # Incorrect answer decreases mastery
            # Higher weight = bigger penalty
            # High confidence + wrong = hypercorrection (bigger update)
            penalty_factor = 1.5 if confidence >= 4 else 1.0
            update_size = weight * penalty_factor * 0.15
            new_mastery = max(0.0, prior_mastery - update_size)

        return new_mastery

    async def _update_fsrs_parameters(
        self,
        skill_id: str,
        learner_id: str,
        is_correct: bool,
        latency_ms: int,
        current_difficulty: float,
        current_stability: float,
    ) -> dict[str, float]:
        """
        Update FSRS parameters for this skill.

        Args:
            skill_id: Skill UUID
            learner_id: Learner UUID
            is_correct: Response correctness
            latency_ms: Time taken
            current_difficulty: Current FSRS difficulty
            current_stability: Current FSRS stability (days)

        Returns:
            dict with updated difficulty, stability, retrievability
        """
        # FSRS difficulty update
        if is_correct:
            # Decrease difficulty slightly (skill getting easier)
            new_difficulty = max(0.1, current_difficulty - 0.05)
        else:
            # Increase difficulty (skill is harder than thought)
            new_difficulty = min(1.0, current_difficulty + 0.1)

        # FSRS stability update
        if is_correct:
            # Increase stability (retention improves with correct answer)
            new_stability = current_stability * 2.0
        else:
            # Reset stability (forgot, need to review sooner)
            new_stability = max(1.0, current_stability * 0.5)

        # Calculate retrievability (current recall probability)
        # R(t) = e^(-t/S) where t = time since last review
        # For now, assume immediate retrieval after update
        retrievability = 1.0 if is_correct else 0.5

        return {
            "difficulty": new_difficulty,
            "stability": new_stability,
            "retrievability": retrievability,
        }

    def _compute_confidence_interval(self, mastery: float, practice_count: int) -> float:
        """
        Compute confidence interval for mastery estimate.

        More practice = narrower confidence interval.

        Args:
            mastery: Current mastery estimate (0-1)
            practice_count: Number of practice attempts

        Returns:
            Confidence interval width (0-1)
        """
        # Start with wide interval, narrow with more practice
        base_interval = 0.5
        decay_rate = 0.1

        # CI = base * e^(-decay * practice_count)
        confidence_interval = base_interval * math.exp(-decay_rate * practice_count)

        return max(0.05, confidence_interval)  # Minimum 5% uncertainty

    async def _get_atom_skills(self, atom_id: str) -> list[dict[str, Any]]:
        """
        Get all skills linked to this atom.

        Returns:
            List of dicts with skill_id, skill_code, weight, is_primary
        """
        query = """
        SELECT
            s.id AS skill_id,
            s.skill_code,
            asw.weight,
            asw.is_primary
        FROM atom_skill_weights asw
        JOIN skills s ON asw.skill_id = s.id
        WHERE asw.atom_id = $1
        ORDER BY asw.is_primary DESC, asw.weight DESC
        """
        rows = await self.db.fetch(query, atom_id)
        return [dict(row) for row in rows]

    async def _get_skill_mastery(
        self, learner_id: str, skill_id: str
    ) -> SkillMasteryState:
        """
        Get current mastery state for a skill.

        If no record exists, create default state.
        """
        query = """
        SELECT
            lsm.mastery_level,
            lsm.confidence_interval,
            lsm.practice_count,
            lsm.consecutive_correct,
            lsm.last_practiced,
            lsm.retrievability,
            lsm.difficulty,
            lsm.stability,
            s.skill_code
        FROM learner_skill_mastery lsm
        JOIN skills s ON lsm.skill_id = s.id
        WHERE lsm.learner_id = $1 AND lsm.skill_id = $2
        """
        row = await self.db.fetchrow(query, learner_id, skill_id)

        if row:
            return SkillMasteryState(
                skill_id=skill_id,
                skill_code=row["skill_code"],
                mastery_level=float(row["mastery_level"]),
                confidence_interval=float(row["confidence_interval"]),
                practice_count=row["practice_count"],
                consecutive_correct=row["consecutive_correct"],
                last_practiced=row["last_practiced"],
                retrievability=float(row["retrievability"]),
                difficulty=float(row["difficulty"]),
                stability=float(row["stability"]),
            )
        else:
            # Create default state for new skill
            skill_code = await self._get_skill_code(skill_id)
            return SkillMasteryState(
                skill_id=skill_id,
                skill_code=skill_code,
                mastery_level=0.0,
                confidence_interval=0.5,
                practice_count=0,
                consecutive_correct=0,
                last_practiced=None,
                retrievability=1.0,
                difficulty=0.3,
                stability=1.0,
            )

    async def _save_skill_mastery(
        self,
        learner_id: str,
        skill_id: str,
        mastery_level: float,
        confidence_interval: float,
        practice_count: int,
        consecutive_correct: int,
        retrievability: float,
        difficulty: float,
        stability: float,
    ) -> None:
        """
        Save updated skill mastery state.

        Uses UPSERT (INSERT ... ON CONFLICT UPDATE).
        """
        query = """
        INSERT INTO learner_skill_mastery (
            learner_id,
            skill_id,
            mastery_level,
            confidence_interval,
            practice_count,
            consecutive_correct,
            last_practiced,
            retrievability,
            difficulty,
            stability,
            last_updated
        ) VALUES ($1, $2, $3, $4, $5, $6, NOW(), $7, $8, $9, NOW())
        ON CONFLICT (learner_id, skill_id)
        DO UPDATE SET
            mastery_level = EXCLUDED.mastery_level,
            confidence_interval = EXCLUDED.confidence_interval,
            practice_count = EXCLUDED.practice_count,
            consecutive_correct = EXCLUDED.consecutive_correct,
            last_practiced = EXCLUDED.last_practiced,
            retrievability = EXCLUDED.retrievability,
            difficulty = EXCLUDED.difficulty,
            stability = EXCLUDED.stability,
            last_updated = NOW()
        """
        await self.db.execute(
            query,
            learner_id,
            skill_id,
            mastery_level,
            confidence_interval,
            practice_count,
            consecutive_correct,
            retrievability,
            difficulty,
            stability,
        )

    async def _get_skill_code(self, skill_id: str) -> str:
        """Get skill_code for a skill_id."""
        query = "SELECT skill_code FROM skills WHERE id = $1"
        row = await self.db.fetchrow(query, skill_id)
        return row["skill_code"] if row else "UNKNOWN"

    async def get_learner_skill_gaps(
        self, learner_id: str, module_id: str, limit: int = 5
    ) -> list[dict[str, Any]]:
        """
        Identify learner's weakest skills for a module.

        Used by AtomSelector to target skill gaps.

        Args:
            learner_id: Learner UUID
            module_id: Module UUID
            limit: Number of skills to return

        Returns:
            List of dicts with skill_id, skill_code, mastery_level, retrievability
        """
        query = """
        SELECT
            s.id AS skill_id,
            s.skill_code,
            s.name AS skill_name,
            COALESCE(lsm.mastery_level, 0.0) AS mastery_level,
            COALESCE(lsm.retrievability, 0.0) AS retrievability,
            COUNT(DISTINCT a.id) AS available_atoms
        FROM skills s
        JOIN atom_skill_weights asw ON s.id = asw.skill_id AND asw.is_primary = TRUE
        JOIN learning_atoms a ON asw.atom_id = a.id
        LEFT JOIN learner_skill_mastery lsm ON s.id = lsm.skill_id AND lsm.learner_id = $1
        WHERE a.module_id = $2 AND s.is_active = TRUE
        GROUP BY s.id, s.skill_code, s.name, lsm.mastery_level, lsm.retrievability
        HAVING COUNT(DISTINCT a.id) > 0
        ORDER BY
            COALESCE(lsm.mastery_level, 0.0) ASC,  -- Lowest mastery first
            COALESCE(lsm.retrievability, 0.0) ASC  -- Most forgotten first
        LIMIT $3
        """
        rows = await self.db.fetch(query, learner_id, module_id, limit)
        return [dict(row) for row in rows]
