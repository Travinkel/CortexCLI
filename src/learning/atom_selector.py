"""Skill-Based Atom Selector.

This module extends atom selection with skill gap targeting capabilities.
Uses learner skill mastery data to select atoms that address weaknesses.
"""
Atom Selection for Adaptive Learning.

Provides intelligent atom selection based on:
- Skill gaps (targets learner's weakest skills)
- Difficulty appropriateness
- Z-score ranking
- Type diversity
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class AtomCandidate:
    """Candidate atom with selection metadata."""

    atom_id: str
    atom_type: str
    difficulty: float  # IRT difficulty (0-1)
    primary_skills: list[str]  # Primary skill codes
    secondary_skills: list[str]  # Secondary skill codes
    z_score: float  # Selection score (higher = better match)


class SkillBasedAtomSelector:
    """
    Select atoms based on learner skill gaps.

    Strategy:
    1. Identify learner's weakest skills for module
    2. Find atoms primarily targeting those skills
    3. Filter by difficulty appropriate to mastery level
    4. Rank candidates by Z-score
    5. Return top N atoms

    Uses SkillMasteryTracker for skill gap identification.
    """

    def __init__(self, db_connection, skill_tracker):
        """
        Initialize SkillBasedAtomSelector.

        Args:
            db_connection: Database connection for querying atoms
            skill_tracker: SkillMasteryTracker instance for gap analysis
        """
        self.db = db_connection
        self.skill_tracker = skill_tracker

    async def select_atoms_by_skill_gap(
        self,
        learner_id: str,
        module_id: str,
        limit: int = 5
    ) -> list[dict[str, Any]]:
        """
        Select atoms targeting learner's weakest skills.

        Strategy:
        1. Find skills with lowest mastery for this module
        2. Find atoms primarily targeting those skills
        3. Filter by difficulty appropriate to mastery level
        4. Return top N by Z-score ranking
        """
        skill_gaps = await self.skill_tracker.get_learner_skill_gaps(
            learner_id=learner_id,
            module_id=module_id,
            limit=3
        )

        if not skill_gaps:
            return []

        weak_skill_ids = [gap["skill_id"] for gap in skill_gaps]
        avg_mastery = sum(gap["mastery_level"] for gap in skill_gaps) / len(skill_gaps)

        candidates = await self._get_atom_candidates(
            module_id=module_id,
            skill_ids=weak_skill_ids,
            limit=limit * 3
        )

        target_difficulty = avg_mastery + 0.1
        filtered = self._filter_by_difficulty(candidates, target_difficulty, 0.3)
        ranked = self._rank_by_zscore(filtered, avg_mastery, skill_gaps)

        return ranked[:limit]

    async def _get_atom_candidates(
        self,
        module_id: str,
        skill_ids: list[str],
        limit: int = 15
    ) -> list[AtomCandidate]:
        """Get candidate atoms that target specified skills."""
        query = """
        SELECT DISTINCT
            a.id AS atom_id,
            a.atom_type,
            a.irt_difficulty,
            ARRAY_AGG(s.skill_code) FILTER (WHERE asw.is_primary) AS primary_skills
        FROM learning_atoms a
        JOIN atom_skill_weights asw ON a.id = asw.atom_id
        JOIN skills s ON asw.skill_id = s.id
        WHERE a.module_id = $1
          AND asw.skill_id = ANY($2)
          AND asw.is_primary = TRUE
        GROUP BY a.id, a.atom_type, a.irt_difficulty
        ORDER BY RANDOM()
        LIMIT $3
        """

        rows = await self.db.fetch(query, module_id, skill_ids, limit)

        return [
            AtomCandidate(
                atom_id=row["atom_id"],
                atom_type=row["atom_type"],
                difficulty=float(row["irt_difficulty"] or 0.5),
                primary_skills=row["primary_skills"] or [],
                secondary_skills=[],
                z_score=0.0
            )
            for row in rows
        ]

    def _filter_by_difficulty(
        self,
        candidates: list[AtomCandidate],
        target_difficulty: float,
        tolerance: float = 0.3
    ) -> list[AtomCandidate]:
        """Filter candidates by difficulty appropriateness."""
        min_d = max(0.0, target_difficulty - tolerance)
        max_d = min(1.0, target_difficulty + tolerance)

        return [c for c in candidates if min_d <= c.difficulty <= max_d]

    def _rank_by_zscore(
        self,
        candidates: list[AtomCandidate],
        learner_mastery: float,
        skill_gaps: list[dict[str, Any]]
    ) -> list[AtomCandidate]:
        """Rank candidates by Z-score."""
        skill_weakness = {
            gap["skill_code"]: (1.0 - gap["mastery_level"])
            for gap in skill_gaps
        }

        target_diff = learner_mastery + 0.1

        for candidate in candidates:
            skill_match = sum(
                skill_weakness.get(sc, 0.0) for sc in candidate.primary_skills
            ) / max(len(candidate.primary_skills), 1)

            diff_delta = abs(candidate.difficulty - target_diff)
            diff_match = 1.0 - min(diff_delta / 0.5, 1.0)

            candidate.z_score = (0.7 * skill_match) + (0.3 * diff_match)

        return sorted(candidates, key=lambda c: c.z_score, reverse=True)
