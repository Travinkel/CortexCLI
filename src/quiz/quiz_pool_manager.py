"""
Quiz Pool Manager for question pool management and selection.

Handles question pool creation, randomized selection with reproducible seeds,
and pool statistics for quiz generation.
"""
from __future__ import annotations

import hashlib
import random
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Dict, List, Optional, Tuple
from uuid import UUID

from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.db.models import (
    QuizQuestion,
    QuizDefinition,
    CleanAtom,
    CleanConcept,
)
from src.db.models.prerequisites import QuestionPool


@dataclass
class PoolStatistics:
    """Statistics for a question pool."""
    pool_id: UUID
    pool_name: str
    total_questions: int
    active_questions: int
    avg_difficulty: float | None
    difficulty_distribution: Dict[str, int]  # 'easy', 'medium', 'hard'
    type_distribution: Dict[str, int]  # question_type -> count
    knowledge_type_distribution: Dict[str, int]
    quality_distribution: Dict[str, int]  # 'high', 'medium', 'low'
    has_sufficient_questions: bool
    min_questions_required: int


@dataclass
class SelectedQuestion:
    """A question selected from a pool."""
    question_id: UUID
    atom_id: UUID
    question_type: str
    difficulty: float | None
    front: str
    question_content: dict


class QuizPoolManager:
    """
    Manager for quiz question pools.

    Handles:
    - Pool creation and management
    - Randomized question selection with reproducible seeds
    - Pool statistics and coverage analysis
    - Question diversity enforcement
    """

    def __init__(self, session: AsyncSession):
        self.session = session

    # ========================================
    # Pool CRUD Operations
    # ========================================

    async def create_pool(
        self,
        name: str,
        concept_id: UUID | None = None,
        concept_cluster_id: UUID | None = None,
        target_difficulty: float | None = None,
        min_questions: int = 5,
        description: str | None = None,
    ) -> QuestionPool:
        """
        Create a new question pool.

        Args:
            name: Pool name
            concept_id: Associated concept (optional)
            concept_cluster_id: Associated cluster (optional)
            target_difficulty: Target difficulty level (0-1)
            min_questions: Minimum questions for quiz generation
            description: Pool description

        Returns:
            Created QuestionPool
        """
        pool = QuestionPool(
            name=name,
            concept_id=concept_id,
            concept_cluster_id=concept_cluster_id,
            target_difficulty=Decimal(str(target_difficulty)) if target_difficulty else None,
            min_questions=min_questions,
            description=description,
            is_active=True,
        )

        self.session.add(pool)
        await self.session.flush()
        return pool

    async def get_pool(self, pool_id: UUID) -> QuestionPool | None:
        """Get a pool by ID."""
        result = await self.session.execute(
            select(QuestionPool)
            .options(selectinload(QuestionPool.questions))
            .where(QuestionPool.id == pool_id)
        )
        return result.scalar_one_or_none()

    async def list_pools(
        self,
        concept_id: UUID | None = None,
        concept_cluster_id: UUID | None = None,
        is_active: bool = True,
    ) -> List[QuestionPool]:
        """List question pools with optional filters."""
        query = select(QuestionPool)

        conditions = []
        if is_active is not None:
            conditions.append(QuestionPool.is_active == is_active)
        if concept_id:
            conditions.append(QuestionPool.concept_id == concept_id)
        if concept_cluster_id:
            conditions.append(QuestionPool.concept_cluster_id == concept_cluster_id)

        if conditions:
            query = query.where(and_(*conditions))

        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def add_questions_to_pool(
        self,
        pool_id: UUID,
        question_ids: List[UUID],
    ) -> int:
        """
        Add questions to a pool.

        Args:
            pool_id: Pool ID
            question_ids: Question IDs to add

        Returns:
            Number of questions added
        """
        count = 0
        for question_id in question_ids:
            result = await self.session.execute(
                select(QuizQuestion).where(QuizQuestion.id == question_id)
            )
            question = result.scalar_one_or_none()
            if question:
                question.pool_id = pool_id
                count += 1

        await self.session.flush()
        return count

    async def remove_questions_from_pool(
        self,
        pool_id: UUID,
        question_ids: List[UUID] | None = None,
    ) -> int:
        """
        Remove questions from a pool.

        Args:
            pool_id: Pool ID
            question_ids: Question IDs to remove (None = remove all)

        Returns:
            Number of questions removed
        """
        query = select(QuizQuestion).where(QuizQuestion.pool_id == pool_id)

        if question_ids:
            query = query.where(QuizQuestion.id.in_(question_ids))

        result = await self.session.execute(query)
        questions = result.scalars().all()

        count = 0
        for question in questions:
            question.pool_id = None
            count += 1

        await self.session.flush()
        return count

    # ========================================
    # Question Selection
    # ========================================

    async def select_questions(
        self,
        pool_id: UUID,
        count: int,
        seed: str | int | None = None,
        exclude_ids: List[UUID] | None = None,
        difficulty_range: Tuple[float, float] | None = None,
        question_types: List[str] | None = None,
        knowledge_types: List[str] | None = None,
    ) -> List[SelectedQuestion]:
        """
        Select random questions from a pool.

        Uses a reproducible seed for consistent selection across attempts
        while ensuring different users get different questions.

        Args:
            pool_id: Pool to select from
            count: Number of questions to select
            seed: Random seed for reproducibility (e.g., user_id + attempt_number)
            exclude_ids: Question IDs to exclude (e.g., from previous attempts)
            difficulty_range: Optional (min, max) difficulty filter
            question_types: Optional filter by question types
            knowledge_types: Optional filter by knowledge types

        Returns:
            List of SelectedQuestion objects
        """
        # Build query
        query = (
            select(QuizQuestion)
            .options(selectinload(QuizQuestion.atom))
            .where(
                and_(
                    QuizQuestion.pool_id == pool_id,
                    QuizQuestion.is_active == True,
                )
            )
        )

        # Apply filters
        if exclude_ids:
            query = query.where(QuizQuestion.id.notin_(exclude_ids))

        if difficulty_range:
            min_diff, max_diff = difficulty_range
            query = query.where(
                and_(
                    QuizQuestion.difficulty >= min_diff,
                    QuizQuestion.difficulty <= max_diff,
                )
            )

        if question_types:
            query = query.where(QuizQuestion.question_type.in_(question_types))

        if knowledge_types:
            query = query.where(QuizQuestion.knowledge_type.in_(knowledge_types))

        result = await self.session.execute(query)
        questions = list(result.scalars().all())

        if not questions:
            return []

        # Apply random selection with seed
        if seed is not None:
            # Create reproducible seed
            seed_value = self._create_seed(seed)
            random.seed(seed_value)

        # Shuffle and select
        random.shuffle(questions)
        selected = questions[:count]

        # Reset random state
        random.seed()

        return [
            SelectedQuestion(
                question_id=q.id,
                atom_id=q.atom_id,
                question_type=q.question_type,
                difficulty=float(q.difficulty) if q.difficulty else None,
                front=q.atom.front if q.atom else "",
                question_content=q.question_content,
            )
            for q in selected
        ]

    def _create_seed(self, seed: str | int) -> int:
        """Create a reproducible integer seed from string or int."""
        if isinstance(seed, int):
            return seed

        # Hash string to create seed
        hash_bytes = hashlib.sha256(str(seed).encode()).digest()
        return int.from_bytes(hash_bytes[:8], byteorder='big')

    async def select_questions_for_quiz(
        self,
        quiz_definition_id: UUID,
        user_id: str,
        attempt_number: int,
        previous_question_ids: List[UUID] | None = None,
    ) -> List[SelectedQuestion]:
        """
        Select questions for a quiz attempt.

        Uses user_id and attempt_number to create a reproducible but unique
        question set for each attempt.

        Args:
            quiz_definition_id: Quiz definition ID
            user_id: User identifier
            attempt_number: Attempt number (1-indexed)
            previous_question_ids: Questions from previous attempts to exclude

        Returns:
            List of selected questions
        """
        # Get quiz definition
        result = await self.session.execute(
            select(QuizDefinition).where(QuizDefinition.id == quiz_definition_id)
        )
        quiz_def = result.scalar_one_or_none()

        if not quiz_def:
            return []

        # Get all pool IDs
        pool_ids = quiz_def.question_pool_ids or []

        if not pool_ids:
            return []

        # Create seed from user_id, quiz_id, and attempt_number
        seed = f"{user_id}:{quiz_definition_id}:{attempt_number}"

        # Collect questions from all pools
        all_questions = []
        for pool_id in pool_ids:
            questions = await self.select_questions(
                pool_id=pool_id,
                count=quiz_def.question_count * 2,  # Select extra for filtering
                seed=seed,
                exclude_ids=previous_question_ids,
            )
            all_questions.extend(questions)

        # Final selection based on quiz count
        random.seed(self._create_seed(seed))
        random.shuffle(all_questions)
        selected = all_questions[:quiz_def.question_count]
        random.seed()

        return selected

    # ========================================
    # Pool Statistics
    # ========================================

    async def get_pool_statistics(self, pool_id: UUID) -> PoolStatistics | None:
        """
        Get comprehensive statistics for a question pool.

        Args:
            pool_id: Pool ID

        Returns:
            PoolStatistics or None if pool not found
        """
        # Get pool
        pool = await self.get_pool(pool_id)
        if not pool:
            return None

        # Get questions
        result = await self.session.execute(
            select(QuizQuestion)
            .where(
                and_(
                    QuizQuestion.pool_id == pool_id,
                )
            )
        )
        questions = list(result.scalars().all())

        # Calculate statistics
        total = len(questions)
        active = sum(1 for q in questions if q.is_active)

        # Difficulty distribution
        difficulties = [float(q.difficulty) for q in questions if q.difficulty]
        avg_difficulty = sum(difficulties) / len(difficulties) if difficulties else None

        difficulty_dist = {"easy": 0, "medium": 0, "hard": 0}
        for d in difficulties:
            if d < 0.4:
                difficulty_dist["easy"] += 1
            elif d < 0.7:
                difficulty_dist["medium"] += 1
            else:
                difficulty_dist["hard"] += 1

        # Type distribution
        type_dist: Dict[str, int] = {}
        for q in questions:
            type_dist[q.question_type] = type_dist.get(q.question_type, 0) + 1

        # Knowledge type distribution
        knowledge_dist: Dict[str, int] = {}
        for q in questions:
            if q.knowledge_type:
                knowledge_dist[q.knowledge_type] = knowledge_dist.get(q.knowledge_type, 0) + 1

        # Quality distribution (based on distractor_quality_score)
        quality_dist = {"high": 0, "medium": 0, "low": 0}
        for q in questions:
            if q.distractor_quality_score:
                score = float(q.distractor_quality_score)
                if score >= 0.7:
                    quality_dist["high"] += 1
                elif score >= 0.5:
                    quality_dist["medium"] += 1
                else:
                    quality_dist["low"] += 1

        return PoolStatistics(
            pool_id=pool_id,
            pool_name=pool.name,
            total_questions=total,
            active_questions=active,
            avg_difficulty=avg_difficulty,
            difficulty_distribution=difficulty_dist,
            type_distribution=type_dist,
            knowledge_type_distribution=knowledge_dist,
            quality_distribution=quality_dist,
            has_sufficient_questions=active >= pool.min_questions,
            min_questions_required=pool.min_questions,
        )

    async def ensure_pool_coverage(
        self,
        quiz_definition_id: UUID,
    ) -> Dict[str, any]:
        """
        Verify that pools have enough questions for a quiz definition.

        Args:
            quiz_definition_id: Quiz definition to check

        Returns:
            Coverage report with status and details
        """
        # Get quiz definition
        result = await self.session.execute(
            select(QuizDefinition).where(QuizDefinition.id == quiz_definition_id)
        )
        quiz_def = result.scalar_one_or_none()

        if not quiz_def:
            return {"error": "Quiz definition not found"}

        pool_ids = quiz_def.question_pool_ids or []
        required_count = quiz_def.question_count

        total_available = 0
        pool_reports = []

        for pool_id in pool_ids:
            stats = await self.get_pool_statistics(pool_id)
            if stats:
                total_available += stats.active_questions
                pool_reports.append({
                    "pool_id": str(pool_id),
                    "pool_name": stats.pool_name,
                    "active_questions": stats.active_questions,
                    "sufficient": stats.has_sufficient_questions,
                })

        return {
            "quiz_definition_id": str(quiz_definition_id),
            "required_questions": required_count,
            "total_available": total_available,
            "coverage_met": total_available >= required_count,
            "pools": pool_reports,
            "recommendations": self._get_coverage_recommendations(
                required_count, total_available, pool_reports
            ),
        }

    def _get_coverage_recommendations(
        self,
        required: int,
        available: int,
        pools: List[Dict],
    ) -> List[str]:
        """Generate recommendations for improving pool coverage."""
        recommendations = []

        if available < required:
            gap = required - available
            recommendations.append(
                f"Add {gap} more questions to reach minimum requirement"
            )

        # Check for unbalanced pools
        if pools:
            counts = [p["active_questions"] for p in pools]
            if max(counts) > 0 and min(counts) / max(counts) < 0.5:
                recommendations.append(
                    "Balance question counts across pools for better variety"
                )

        # Recommend multiple attempts buffer
        if available < required * 2:
            recommendations.append(
                "Consider adding more questions to support multiple unique attempts"
            )

        return recommendations

    # ========================================
    # Diversity Enforcement
    # ========================================

    async def select_diverse_questions(
        self,
        pool_id: UUID,
        count: int,
        seed: str | int | None = None,
        diversity_weights: Dict[str, float] | None = None,
    ) -> List[SelectedQuestion]:
        """
        Select questions with enforced diversity across types and knowledge areas.

        Args:
            pool_id: Pool to select from
            count: Number of questions to select
            seed: Random seed
            diversity_weights: Weights for diversity factors
                - "type": Weight for question type diversity (default 0.4)
                - "knowledge": Weight for knowledge type diversity (default 0.3)
                - "difficulty": Weight for difficulty spread (default 0.3)

        Returns:
            Diversified list of questions
        """
        weights = diversity_weights or {
            "type": 0.4,
            "knowledge": 0.3,
            "difficulty": 0.3,
        }

        # Get all available questions
        all_questions = await self.select_questions(
            pool_id=pool_id,
            count=count * 5,  # Get extra for diversity selection
            seed=seed,
        )

        if len(all_questions) <= count:
            return all_questions

        # Group by type
        by_type: Dict[str, List[SelectedQuestion]] = {}
        for q in all_questions:
            by_type.setdefault(q.question_type, []).append(q)

        # Calculate target counts per type
        type_count = len(by_type)
        base_per_type = max(1, count // type_count)

        selected = []
        remaining_count = count

        # First pass: ensure type diversity
        for question_type, questions in by_type.items():
            take = min(base_per_type, len(questions), remaining_count)
            selected.extend(questions[:take])
            remaining_count -= take

        # Fill remaining with random selection
        used_ids = {q.question_id for q in selected}
        remaining_questions = [q for q in all_questions if q.question_id not in used_ids]

        if seed:
            random.seed(self._create_seed(seed))
        random.shuffle(remaining_questions)
        random.seed()

        selected.extend(remaining_questions[:remaining_count])

        return selected[:count]
