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
from typing import Any

logger = logging.getLogger(__name__)


class AtomSelector:
    """
    Select atoms for study sessions using adaptive strategies.

    Strategies:
    - Skill-based: Target learner's weakest skills
    - Difficulty-matched: Choose atoms appropriate to mastery level
    - Z-score ranked: Prioritize by spaced repetition signals
    """

    def __init__(self, db_connection: Any):
        """
        Initialize atom selector with database connection.

        Args:
            db_connection: AsyncPG connection or SQLAlchemy session
        """
        self.db = db_connection

    async def select_atoms_by_skill_gap(
        self, learner_id: str, module_id: str, limit: int = 5
    ) -> list[dict[str, Any]]:
        """
        Select atoms targeting learner's weakest skills.

        Strategy:
        1. Find skills with lowest mastery for this module
        2. Find atoms primarily targeting those skills
        3. Filter by difficulty appropriate to mastery level
        4. Return top N by Z-score ranking

        Args:
            learner_id: Learner UUID
            module_id: Module UUID
            limit: Number of atoms to return

        Returns:
            List of atom dicts targeting skill gaps
        """
        # Step 1: Identify weak skills
        weak_skills_query = """
        SELECT
            s.id AS skill_id,
            s.skill_code,
            s.name,
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
        LIMIT 3  -- Focus on top 3 weakest skills
        """

        weak_skills = await self.db.fetch(weak_skills_query, learner_id, module_id)

        if not weak_skills:
            logger.warning(f"No skills found for module {module_id} - falling back to random selection")
            return await self._select_random_atoms(module_id, limit)

        # Extract skill IDs for targeting
        target_skill_ids = [str(skill["skill_id"]) for skill in weak_skills]

        # Step 2: Find atoms targeting these weak skills
        # Filter by difficulty: mastery_level ± 0.1 tolerance
        atoms_query = """
        SELECT DISTINCT
            a.id,
            a.front,
            a.back,
            a.atom_type,
            a.difficulty,
            asw.skill_id,
            asw.weight,
            s.skill_code,
            COALESCE(lsm.mastery_level, 0.0) AS skill_mastery,
            -- Z-score components
            COALESCE(a.stability, 1.0) AS stability,
            COALESCE(a.retrievability, 1.0) AS retrievability,
            a.last_reviewed
        FROM learning_atoms a
        JOIN atom_skill_weights asw ON a.id = asw.atom_id AND asw.is_primary = TRUE
        JOIN skills s ON asw.skill_id = s.id
        LEFT JOIN learner_skill_mastery lsm ON s.id = lsm.skill_id AND lsm.learner_id = $1
        WHERE
            a.module_id = $2
            AND asw.skill_id = ANY($3::uuid[])  -- Target weak skills
            AND a.difficulty >= (COALESCE(lsm.mastery_level, 0.0) - 0.1)  -- Not too easy
            AND a.difficulty <= (COALESCE(lsm.mastery_level, 0.0) + 0.2)  -- Not too hard
            AND s.is_active = TRUE
        ORDER BY
            -- Prioritize by retrievability (lowest first = most forgotten)
            COALESCE(a.retrievability, 1.0) ASC,
            -- Then by skill gap (lowest mastery first)
            COALESCE(lsm.mastery_level, 0.0) ASC,
            -- Finally by weight (higher weight = better match)
            asw.weight DESC
        LIMIT $4
        """

        atoms = await self.db.fetch(atoms_query, learner_id, module_id, target_skill_ids, limit)

        # Convert to list of dicts
        result = [dict(atom) for atom in atoms]

        # If we didn't get enough atoms, backfill with random selection
        if len(result) < limit:
            backfill_count = limit - len(result)
            backfill_atoms = await self._select_random_atoms(
                module_id, backfill_count, exclude_ids=[a["id"] for a in result]
            )
            result.extend(backfill_atoms)

        logger.info(
            f"Selected {len(result)} atoms for learner {learner_id} targeting skills: "
            f"{[s['skill_code'] for s in weak_skills]}"
        )

        return result

    async def _select_random_atoms(
        self, module_id: str, limit: int, exclude_ids: list[str] | None = None
    ) -> list[dict[str, Any]]:
        """
        Fallback: Select random atoms from module.

        Args:
            module_id: Module UUID
            limit: Number of atoms to select
            exclude_ids: List of atom IDs to exclude

        Returns:
            List of random atom dicts
        """
        exclude_clause = ""
        params = [module_id, limit]

        if exclude_ids:
            exclude_clause = "AND a.id != ALL($3::uuid[])"
            params.append(exclude_ids)

        query = f"""
        SELECT
            a.id,
            a.front,
            a.back,
            a.atom_type,
            a.difficulty
        FROM learning_atoms a
        WHERE a.module_id = $1
        {exclude_clause}
        ORDER BY RANDOM()
        LIMIT $2
        """

        atoms = await self.db.fetch(query, *params)
        return [dict(atom) for atom in atoms]

    async def get_skill_coverage_for_module(
        self, learner_id: str, module_id: str
    ) -> dict[str, Any]:
        """
        Get skill coverage statistics for a module.

        Args:
            learner_id: Learner UUID
            module_id: Module UUID

        Returns:
            Dict with skill coverage stats
        """
        query = """
        SELECT
            COUNT(DISTINCT s.id) AS total_skills,
            COUNT(DISTINCT CASE WHEN lsm.mastery_level >= 0.7 THEN s.id END) AS mastered_skills,
            COUNT(DISTINCT CASE WHEN lsm.mastery_level < 0.5 THEN s.id END) AS weak_skills,
            AVG(COALESCE(lsm.mastery_level, 0.0)) AS average_mastery,
            MIN(COALESCE(lsm.mastery_level, 0.0)) AS lowest_mastery,
            MAX(COALESCE(lsm.mastery_level, 0.0)) AS highest_mastery
        FROM skills s
        JOIN atom_skill_weights asw ON s.id = asw.skill_id
        JOIN learning_atoms a ON asw.atom_id = a.id
        LEFT JOIN learner_skill_mastery lsm ON s.id = lsm.skill_id AND lsm.learner_id = $1
        WHERE a.module_id = $2 AND s.is_active = TRUE
        """

        row = await self.db.fetchrow(query, learner_id, module_id)
        return dict(row) if row else {}
