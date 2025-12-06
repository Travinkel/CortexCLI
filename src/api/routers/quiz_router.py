"""
Quiz router for question management and quality assurance.

Endpoints for:
- Quiz question CRUD
- Quality analysis
- Question pool management
- Quiz definitions
- Export for right-learning integration

Phase 3 implementation for quiz quality assurance.
"""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from loguru import logger
from pydantic import BaseModel, Field

from src.db.database import get_async_session
from sqlalchemy.ext.asyncio import AsyncSession


router = APIRouter()


# ========================================
# Request/Response Models
# ========================================


class QuestionCreateRequest(BaseModel):
    """Request model for creating a quiz question."""

    atom_id: str = Field(..., description="Associated learning atom ID")
    question_type: str = Field(
        ...,
        description="Question type: mcq, true_false, short_answer, matching, ranking, sequence, parsons, cloze, explain, compare, problem, prediction, passage_based"
    )
    question_content: Dict[str, Any] = Field(
        ...,
        description="Type-specific question content JSON"
    )
    knowledge_type: str = Field(
        "factual",
        description="Knowledge type: factual, conceptual, procedural, metacognitive"
    )
    difficulty: Optional[float] = Field(None, ge=0, le=1, description="Difficulty score (0-1)")
    pool_id: Optional[str] = Field(None, description="Question pool ID")


class QuestionResponse(BaseModel):
    """Response model for a quiz question."""

    id: str
    atom_id: str
    question_type: str
    question_content: Dict[str, Any]
    knowledge_type: Optional[str]
    difficulty: Optional[float]
    distractor_quality_score: Optional[float]
    answer_clarity_score: Optional[float]
    quality_grade: Optional[str]
    pool_id: Optional[str]
    is_active: bool
    created_at: datetime


class QuestionUpdateRequest(BaseModel):
    """Request model for updating a question."""

    question_content: Optional[Dict[str, Any]] = None
    knowledge_type: Optional[str] = None
    difficulty: Optional[float] = Field(None, ge=0, le=1)
    pool_id: Optional[str] = None
    is_active: Optional[bool] = None


class QualityAnalysisResponse(BaseModel):
    """Response model for quality analysis."""

    question_id: str
    overall_score: float
    grade: str  # A, B, C, D, F
    distractor_quality_score: Optional[float]
    answer_clarity_score: Optional[float]
    issues: List[str]
    recommendations: List[str]
    details: Dict[str, Any]


class BatchAnalysisResponse(BaseModel):
    """Response model for batch quality analysis."""

    total_analyzed: int
    grade_distribution: Dict[str, int]
    avg_quality_score: float
    improvement_needed: int
    results: List[QualityAnalysisResponse]


class QualitySummaryResponse(BaseModel):
    """Response model for quality summary."""

    total_questions: int
    by_grade: Dict[str, int]
    by_type: Dict[str, int]
    by_knowledge_type: Dict[str, int]
    avg_quality: float
    improvement_queue: List[Dict[str, Any]]


class PoolCreateRequest(BaseModel):
    """Request model for creating a question pool."""

    name: str = Field(..., description="Pool name")
    concept_id: Optional[str] = Field(None, description="Associated concept ID")
    concept_cluster_id: Optional[str] = Field(None, description="Associated cluster ID")
    target_difficulty: Optional[float] = Field(None, ge=0, le=1)
    min_questions: int = Field(5, ge=1, description="Minimum questions for quiz generation")
    description: Optional[str] = None


class PoolResponse(BaseModel):
    """Response model for a question pool."""

    id: str
    name: str
    concept_id: Optional[str]
    concept_cluster_id: Optional[str]
    target_difficulty: Optional[float]
    min_questions: int
    description: Optional[str]
    is_active: bool
    created_at: datetime


class PoolStatisticsResponse(BaseModel):
    """Response model for pool statistics."""

    pool_id: str
    pool_name: str
    total_questions: int
    active_questions: int
    avg_difficulty: Optional[float]
    difficulty_distribution: Dict[str, int]
    type_distribution: Dict[str, int]
    knowledge_type_distribution: Dict[str, int]
    quality_distribution: Dict[str, int]
    has_sufficient_questions: bool
    min_questions_required: int


class SelectQuestionsRequest(BaseModel):
    """Request model for selecting questions from a pool."""

    count: int = Field(10, ge=1, le=100, description="Number of questions to select")
    seed: Optional[str] = Field(None, description="Seed for reproducible selection")
    exclude_ids: List[str] = Field(default_factory=list, description="Question IDs to exclude")
    difficulty_range: Optional[List[float]] = Field(None, description="[min, max] difficulty")
    question_types: Optional[List[str]] = Field(None, description="Filter by question types")
    diversity_weights: Optional[Dict[str, float]] = Field(None, description="Weights for diversity")


class SelectedQuestionResponse(BaseModel):
    """Response model for a selected question."""

    question_id: str
    atom_id: str
    question_type: str
    difficulty: Optional[float]
    front: str
    question_content: Dict[str, Any]


class QuizDefinitionCreateRequest(BaseModel):
    """Request model for creating a quiz definition."""

    name: str = Field(..., description="Quiz name")
    concept_id: Optional[str] = Field(None, description="Associated concept ID")
    concept_cluster_id: Optional[str] = Field(None, description="Associated cluster ID")
    question_pool_ids: List[str] = Field(default_factory=list, description="Question pool IDs")
    question_count: int = Field(10, ge=1, le=100)
    time_limit_seconds: Optional[int] = Field(None, description="Time limit in seconds")
    passing_score: float = Field(0.70, ge=0, le=1)
    quiz_weight: float = Field(0.375, ge=0, le=1, description="Weight for mastery calculation")
    review_weight: float = Field(0.625, ge=0, le=1, description="Weight for review score")
    description: Optional[str] = None


class QuizDefinitionResponse(BaseModel):
    """Response model for a quiz definition."""

    id: str
    name: str
    concept_id: Optional[str]
    concept_cluster_id: Optional[str]
    question_pool_ids: List[str]
    question_count: int
    time_limit_seconds: Optional[int]
    passing_score: float
    quiz_weight: float
    review_weight: float
    description: Optional[str]
    is_active: bool
    created_at: datetime


class ValidationResultResponse(BaseModel):
    """Response model for structure validation."""

    is_valid: bool
    errors: List[str]
    warnings: List[str]


# ========================================
# Question CRUD Endpoints
# ========================================


@router.post(
    "/questions",
    response_model=QuestionResponse,
    summary="Create quiz question",
)
async def create_question(
    request: QuestionCreateRequest,
    db: AsyncSession = Depends(get_async_session),
) -> QuestionResponse:
    """
    Create a new quiz question.

    Question types:
    - mcq: Multiple choice (options array, correct index)
    - true_false: True/false (correct_answer: bool)
    - short_answer: Fill in blank (expected_answer, acceptable array)
    - matching: Match pairs (pairs array with left/right)
    - ranking: Order items (items array, correct_order)
    - sequence: Procedural steps (steps array)
    - parsons: Code arrangement (code_blocks, distractors)
    - cloze: Fill in blanks (text with {{c1::answer}} format)
    - explain: Open explanation (key_concepts array)
    - compare: Compare items (items, dimensions)
    - problem: Problem solving (solution, steps)
    - prediction: Predict outcome (expected, reasoning)
    - passage_based: Questions about passage (passage_id, questions)
    """
    logger.info(f"Creating {request.question_type} question for atom {request.atom_id}")

    try:
        from sqlalchemy import select
        from src.db.models import QuizQuestion, CleanAtom

        # Verify atom exists
        result = await db.execute(
            select(CleanAtom).where(CleanAtom.id == UUID(request.atom_id))
        )
        atom = result.scalar_one_or_none()
        if not atom:
            raise HTTPException(status_code=404, detail="Atom not found")

        question = QuizQuestion(
            atom_id=UUID(request.atom_id),
            question_type=request.question_type,
            question_content=request.question_content,
            knowledge_type=request.knowledge_type,
            difficulty=Decimal(str(request.difficulty)) if request.difficulty else None,
            pool_id=UUID(request.pool_id) if request.pool_id else None,
            is_active=True,
        )

        db.add(question)
        await db.flush()

        # Run quality analysis
        from src.quiz import QuizQuestionAnalyzer
        analyzer = QuizQuestionAnalyzer()
        analysis = analyzer.analyze_question(
            question_type=request.question_type,
            question_content=request.question_content,
            front=atom.front,
            back=atom.back,
        )

        # Update with quality scores
        question.distractor_quality_score = Decimal(str(analysis.distractor_quality_score)) if analysis.distractor_quality_score else None
        question.answer_clarity_score = Decimal(str(analysis.answer_clarity_score)) if analysis.answer_clarity_score else None
        question.quality_grade = analysis.grade
        question.quality_issues = analysis.issues

        await db.commit()

        return QuestionResponse(
            id=str(question.id),
            atom_id=str(question.atom_id),
            question_type=question.question_type,
            question_content=question.question_content,
            knowledge_type=question.knowledge_type,
            difficulty=float(question.difficulty) if question.difficulty else None,
            distractor_quality_score=float(question.distractor_quality_score) if question.distractor_quality_score else None,
            answer_clarity_score=float(question.answer_clarity_score) if question.answer_clarity_score else None,
            quality_grade=question.quality_grade,
            pool_id=str(question.pool_id) if question.pool_id else None,
            is_active=question.is_active,
            created_at=question.created_at,
        )

    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Failed to create question")
        raise HTTPException(status_code=500, detail=str(exc))


@router.get(
    "/questions",
    response_model=List[QuestionResponse],
    summary="List questions",
)
async def list_questions(
    atom_id: Optional[str] = Query(None),
    question_type: Optional[str] = Query(None),
    knowledge_type: Optional[str] = Query(None),
    pool_id: Optional[str] = Query(None),
    min_quality: Optional[str] = Query(None, description="Minimum quality grade (A, B, C, D)"),
    is_active: bool = Query(True),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_async_session),
) -> List[QuestionResponse]:
    """List quiz questions with filters."""
    try:
        from sqlalchemy import select, and_
        from src.db.models import QuizQuestion

        conditions = [QuizQuestion.is_active == is_active]

        if atom_id:
            conditions.append(QuizQuestion.atom_id == UUID(atom_id))
        if question_type:
            conditions.append(QuizQuestion.question_type == question_type)
        if knowledge_type:
            conditions.append(QuizQuestion.knowledge_type == knowledge_type)
        if pool_id:
            conditions.append(QuizQuestion.pool_id == UUID(pool_id))
        if min_quality:
            grade_order = {"A": 5, "B": 4, "C": 3, "D": 2, "F": 1}
            min_grade = grade_order.get(min_quality.upper(), 0)
            # Filter by grade (simplified)
            if min_quality.upper() in grade_order:
                valid_grades = [g for g, v in grade_order.items() if v >= min_grade]
                conditions.append(QuizQuestion.quality_grade.in_(valid_grades))

        query = (
            select(QuizQuestion)
            .where(and_(*conditions))
            .order_by(QuizQuestion.created_at.desc())
            .limit(limit)
            .offset(offset)
        )

        result = await db.execute(query)
        questions = result.scalars().all()

        return [
            QuestionResponse(
                id=str(q.id),
                atom_id=str(q.atom_id),
                question_type=q.question_type,
                question_content=q.question_content,
                knowledge_type=q.knowledge_type,
                difficulty=float(q.difficulty) if q.difficulty else None,
                distractor_quality_score=float(q.distractor_quality_score) if q.distractor_quality_score else None,
                answer_clarity_score=float(q.answer_clarity_score) if q.answer_clarity_score else None,
                quality_grade=q.quality_grade,
                pool_id=str(q.pool_id) if q.pool_id else None,
                is_active=q.is_active,
                created_at=q.created_at,
            )
            for q in questions
        ]

    except Exception as exc:
        logger.exception("Failed to list questions")
        raise HTTPException(status_code=500, detail=str(exc))


@router.get(
    "/questions/{question_id}",
    response_model=QuestionResponse,
    summary="Get question",
)
async def get_question(
    question_id: str,
    db: AsyncSession = Depends(get_async_session),
) -> QuestionResponse:
    """Get a specific question by ID."""
    try:
        from sqlalchemy import select
        from src.db.models import QuizQuestion

        result = await db.execute(
            select(QuizQuestion).where(QuizQuestion.id == UUID(question_id))
        )
        question = result.scalar_one_or_none()

        if not question:
            raise HTTPException(status_code=404, detail="Question not found")

        return QuestionResponse(
            id=str(question.id),
            atom_id=str(question.atom_id),
            question_type=question.question_type,
            question_content=question.question_content,
            knowledge_type=question.knowledge_type,
            difficulty=float(question.difficulty) if question.difficulty else None,
            distractor_quality_score=float(question.distractor_quality_score) if question.distractor_quality_score else None,
            answer_clarity_score=float(question.answer_clarity_score) if question.answer_clarity_score else None,
            quality_grade=question.quality_grade,
            pool_id=str(question.pool_id) if question.pool_id else None,
            is_active=question.is_active,
            created_at=question.created_at,
        )

    except HTTPException:
        raise
    except Exception as exc:
        logger.exception(f"Failed to get question {question_id}")
        raise HTTPException(status_code=500, detail=str(exc))


@router.put(
    "/questions/{question_id}",
    response_model=QuestionResponse,
    summary="Update question",
)
async def update_question(
    question_id: str,
    request: QuestionUpdateRequest,
    db: AsyncSession = Depends(get_async_session),
) -> QuestionResponse:
    """Update a question."""
    try:
        from sqlalchemy import select
        from src.db.models import QuizQuestion

        result = await db.execute(
            select(QuizQuestion).where(QuizQuestion.id == UUID(question_id))
        )
        question = result.scalar_one_or_none()

        if not question:
            raise HTTPException(status_code=404, detail="Question not found")

        # Update fields
        if request.question_content is not None:
            question.question_content = request.question_content
        if request.knowledge_type is not None:
            question.knowledge_type = request.knowledge_type
        if request.difficulty is not None:
            question.difficulty = Decimal(str(request.difficulty))
        if request.pool_id is not None:
            question.pool_id = UUID(request.pool_id) if request.pool_id else None
        if request.is_active is not None:
            question.is_active = request.is_active

        # Re-run quality analysis if content changed
        if request.question_content is not None:
            from src.quiz import QuizQuestionAnalyzer
            from sqlalchemy.orm import selectinload

            # Get atom for analysis
            result = await db.execute(
                select(QuizQuestion)
                .options(selectinload(QuizQuestion.atom))
                .where(QuizQuestion.id == UUID(question_id))
            )
            question = result.scalar_one()

            analyzer = QuizQuestionAnalyzer()
            analysis = analyzer.analyze_question(
                question_type=question.question_type,
                question_content=question.question_content,
                front=question.atom.front if question.atom else "",
                back=question.atom.back if question.atom else "",
            )

            question.distractor_quality_score = Decimal(str(analysis.distractor_quality_score)) if analysis.distractor_quality_score else None
            question.answer_clarity_score = Decimal(str(analysis.answer_clarity_score)) if analysis.answer_clarity_score else None
            question.quality_grade = analysis.grade
            question.quality_issues = analysis.issues

        await db.commit()

        return QuestionResponse(
            id=str(question.id),
            atom_id=str(question.atom_id),
            question_type=question.question_type,
            question_content=question.question_content,
            knowledge_type=question.knowledge_type,
            difficulty=float(question.difficulty) if question.difficulty else None,
            distractor_quality_score=float(question.distractor_quality_score) if question.distractor_quality_score else None,
            answer_clarity_score=float(question.answer_clarity_score) if question.answer_clarity_score else None,
            quality_grade=question.quality_grade,
            pool_id=str(question.pool_id) if question.pool_id else None,
            is_active=question.is_active,
            created_at=question.created_at,
        )

    except HTTPException:
        raise
    except Exception as exc:
        logger.exception(f"Failed to update question {question_id}")
        raise HTTPException(status_code=500, detail=str(exc))


@router.delete(
    "/questions/{question_id}",
    summary="Delete question",
)
async def delete_question(
    question_id: str,
    db: AsyncSession = Depends(get_async_session),
) -> Dict[str, Any]:
    """Soft delete a question."""
    try:
        from sqlalchemy import select
        from src.db.models import QuizQuestion

        result = await db.execute(
            select(QuizQuestion).where(QuizQuestion.id == UUID(question_id))
        )
        question = result.scalar_one_or_none()

        if not question:
            raise HTTPException(status_code=404, detail="Question not found")

        question.is_active = False
        await db.commit()

        return {"success": True, "message": "Question deactivated"}

    except HTTPException:
        raise
    except Exception as exc:
        logger.exception(f"Failed to delete question {question_id}")
        raise HTTPException(status_code=500, detail=str(exc))


# ========================================
# Quality Analysis Endpoints
# ========================================


@router.post(
    "/questions/{question_id}/analyze",
    response_model=QualityAnalysisResponse,
    summary="Analyze question quality",
)
async def analyze_question_quality(
    question_id: str,
    db: AsyncSession = Depends(get_async_session),
) -> QualityAnalysisResponse:
    """
    Run quality analysis on a question.

    Analyzes:
    - Distractor quality (for MCQ)
    - Answer clarity
    - Structure validity
    - Evidence-based thresholds
    """
    try:
        from sqlalchemy import select
        from sqlalchemy.orm import selectinload
        from src.db.models import QuizQuestion
        from src.quiz import QuizQuestionAnalyzer

        result = await db.execute(
            select(QuizQuestion)
            .options(selectinload(QuizQuestion.atom))
            .where(QuizQuestion.id == UUID(question_id))
        )
        question = result.scalar_one_or_none()

        if not question:
            raise HTTPException(status_code=404, detail="Question not found")

        analyzer = QuizQuestionAnalyzer()
        analysis = analyzer.analyze_question(
            question_type=question.question_type,
            question_content=question.question_content,
            front=question.atom.front if question.atom else "",
            back=question.atom.back if question.atom else "",
        )

        # Update question with scores
        question.distractor_quality_score = Decimal(str(analysis.distractor_quality_score)) if analysis.distractor_quality_score else None
        question.answer_clarity_score = Decimal(str(analysis.answer_clarity_score)) if analysis.answer_clarity_score else None
        question.quality_grade = analysis.grade
        question.quality_issues = analysis.issues

        await db.commit()

        return QualityAnalysisResponse(
            question_id=question_id,
            overall_score=analysis.overall_score,
            grade=analysis.grade,
            distractor_quality_score=analysis.distractor_quality_score,
            answer_clarity_score=analysis.answer_clarity_score,
            issues=analysis.issues,
            recommendations=analysis.recommendations,
            details=analysis.details,
        )

    except HTTPException:
        raise
    except Exception as exc:
        logger.exception(f"Failed to analyze question {question_id}")
        raise HTTPException(status_code=500, detail=str(exc))


@router.post(
    "/questions/batch-analyze",
    response_model=BatchAnalysisResponse,
    summary="Batch analyze questions",
)
async def batch_analyze_questions(
    question_ids: Optional[List[str]] = None,
    pool_id: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=500),
    db: AsyncSession = Depends(get_async_session),
) -> BatchAnalysisResponse:
    """
    Batch analyze multiple questions.

    Either provide question_ids or pool_id to filter.
    """
    try:
        from sqlalchemy import select, and_
        from sqlalchemy.orm import selectinload
        from src.db.models import QuizQuestion
        from src.quiz import QuizQuestionAnalyzer

        conditions = [QuizQuestion.is_active == True]

        if question_ids:
            conditions.append(QuizQuestion.id.in_([UUID(qid) for qid in question_ids]))
        elif pool_id:
            conditions.append(QuizQuestion.pool_id == UUID(pool_id))

        result = await db.execute(
            select(QuizQuestion)
            .options(selectinload(QuizQuestion.atom))
            .where(and_(*conditions))
            .limit(limit)
        )
        questions = result.scalars().all()

        analyzer = QuizQuestionAnalyzer()
        results = []
        grade_dist = {"A": 0, "B": 0, "C": 0, "D": 0, "F": 0}
        total_score = 0

        for question in questions:
            analysis = analyzer.analyze_question(
                question_type=question.question_type,
                question_content=question.question_content,
                front=question.atom.front if question.atom else "",
                back=question.atom.back if question.atom else "",
            )

            # Update question
            question.distractor_quality_score = Decimal(str(analysis.distractor_quality_score)) if analysis.distractor_quality_score else None
            question.answer_clarity_score = Decimal(str(analysis.answer_clarity_score)) if analysis.answer_clarity_score else None
            question.quality_grade = analysis.grade
            question.quality_issues = analysis.issues

            grade_dist[analysis.grade] = grade_dist.get(analysis.grade, 0) + 1
            total_score += analysis.overall_score

            results.append(QualityAnalysisResponse(
                question_id=str(question.id),
                overall_score=analysis.overall_score,
                grade=analysis.grade,
                distractor_quality_score=analysis.distractor_quality_score,
                answer_clarity_score=analysis.answer_clarity_score,
                issues=analysis.issues,
                recommendations=analysis.recommendations,
                details=analysis.details,
            ))

        await db.commit()

        return BatchAnalysisResponse(
            total_analyzed=len(results),
            grade_distribution=grade_dist,
            avg_quality_score=total_score / len(results) if results else 0,
            improvement_needed=grade_dist.get("D", 0) + grade_dist.get("F", 0),
            results=results,
        )

    except Exception as exc:
        logger.exception("Failed to batch analyze questions")
        raise HTTPException(status_code=500, detail=str(exc))


@router.get(
    "/questions/quality-summary",
    response_model=QualitySummaryResponse,
    summary="Get quality summary (for right-learning)",
)
async def get_quality_summary(
    db: AsyncSession = Depends(get_async_session),
) -> QualitySummaryResponse:
    """
    Get overall quality summary for all questions.

    Designed for right-learning dashboard integration.
    """
    try:
        from sqlalchemy import select, func
        from src.db.models import QuizQuestion

        # Total count
        total_result = await db.execute(
            select(func.count(QuizQuestion.id)).where(QuizQuestion.is_active == True)
        )
        total = total_result.scalar() or 0

        # By grade
        grade_result = await db.execute(
            select(QuizQuestion.quality_grade, func.count(QuizQuestion.id))
            .where(QuizQuestion.is_active == True)
            .group_by(QuizQuestion.quality_grade)
        )
        by_grade = {row[0] or "ungraded": row[1] for row in grade_result}

        # By type
        type_result = await db.execute(
            select(QuizQuestion.question_type, func.count(QuizQuestion.id))
            .where(QuizQuestion.is_active == True)
            .group_by(QuizQuestion.question_type)
        )
        by_type = {row[0]: row[1] for row in type_result}

        # By knowledge type
        knowledge_result = await db.execute(
            select(QuizQuestion.knowledge_type, func.count(QuizQuestion.id))
            .where(QuizQuestion.is_active == True)
            .group_by(QuizQuestion.knowledge_type)
        )
        by_knowledge = {row[0] or "unclassified": row[1] for row in knowledge_result}

        # Average quality
        avg_result = await db.execute(
            select(func.avg(QuizQuestion.answer_clarity_score))
            .where(QuizQuestion.is_active == True)
        )
        avg_quality = float(avg_result.scalar() or 0)

        # Improvement queue (D and F grades)
        improvement_result = await db.execute(
            select(QuizQuestion)
            .where(
                QuizQuestion.is_active == True,
                QuizQuestion.quality_grade.in_(["D", "F"])
            )
            .order_by(QuizQuestion.answer_clarity_score.asc())
            .limit(20)
        )
        improvement_questions = improvement_result.scalars().all()

        return QualitySummaryResponse(
            total_questions=total,
            by_grade=by_grade,
            by_type=by_type,
            by_knowledge_type=by_knowledge,
            avg_quality=avg_quality,
            improvement_queue=[
                {
                    "question_id": str(q.id),
                    "question_type": q.question_type,
                    "grade": q.quality_grade,
                    "issues": q.quality_issues or [],
                }
                for q in improvement_questions
            ],
        )

    except Exception as exc:
        logger.exception("Failed to get quality summary")
        raise HTTPException(status_code=500, detail=str(exc))


# ========================================
# Validation Endpoints
# ========================================


@router.post(
    "/questions/validate",
    response_model=ValidationResultResponse,
    summary="Validate question structure",
)
async def validate_question_structure(
    question_type: str = Query(...),
    question_content: Dict[str, Any] = None,
    db: AsyncSession = Depends(get_async_session),
) -> ValidationResultResponse:
    """
    Validate question content structure without creating.

    Returns validation errors and warnings.
    """
    try:
        from src.quiz import QuizQuestionAnalyzer

        analyzer = QuizQuestionAnalyzer()
        validation = analyzer.validate_structure(question_type, question_content or {})

        return ValidationResultResponse(
            is_valid=validation.is_valid,
            errors=validation.errors,
            warnings=validation.warnings,
        )

    except Exception as exc:
        logger.exception("Failed to validate question")
        raise HTTPException(status_code=500, detail=str(exc))


# ========================================
# Pool Management Endpoints
# ========================================


@router.post(
    "/pools",
    response_model=PoolResponse,
    summary="Create question pool",
)
async def create_pool(
    request: PoolCreateRequest,
    db: AsyncSession = Depends(get_async_session),
) -> PoolResponse:
    """Create a new question pool."""
    try:
        from src.quiz import QuizPoolManager

        manager = QuizPoolManager(db)

        pool = await manager.create_pool(
            name=request.name,
            concept_id=UUID(request.concept_id) if request.concept_id else None,
            concept_cluster_id=UUID(request.concept_cluster_id) if request.concept_cluster_id else None,
            target_difficulty=request.target_difficulty,
            min_questions=request.min_questions,
            description=request.description,
        )

        await db.commit()

        return PoolResponse(
            id=str(pool.id),
            name=pool.name,
            concept_id=str(pool.concept_id) if pool.concept_id else None,
            concept_cluster_id=str(pool.concept_cluster_id) if pool.concept_cluster_id else None,
            target_difficulty=float(pool.target_difficulty) if pool.target_difficulty else None,
            min_questions=pool.min_questions,
            description=pool.description,
            is_active=pool.is_active,
            created_at=pool.created_at,
        )

    except Exception as exc:
        logger.exception("Failed to create pool")
        raise HTTPException(status_code=500, detail=str(exc))


@router.get(
    "/pools",
    response_model=List[PoolResponse],
    summary="List pools",
)
async def list_pools(
    concept_id: Optional[str] = Query(None),
    is_active: bool = Query(True),
    db: AsyncSession = Depends(get_async_session),
) -> List[PoolResponse]:
    """List question pools."""
    try:
        from src.quiz import QuizPoolManager

        manager = QuizPoolManager(db)
        pools = await manager.list_pools(
            concept_id=UUID(concept_id) if concept_id else None,
            is_active=is_active,
        )

        return [
            PoolResponse(
                id=str(p.id),
                name=p.name,
                concept_id=str(p.concept_id) if p.concept_id else None,
                concept_cluster_id=str(p.concept_cluster_id) if p.concept_cluster_id else None,
                target_difficulty=float(p.target_difficulty) if p.target_difficulty else None,
                min_questions=p.min_questions,
                description=p.description,
                is_active=p.is_active,
                created_at=p.created_at,
            )
            for p in pools
        ]

    except Exception as exc:
        logger.exception("Failed to list pools")
        raise HTTPException(status_code=500, detail=str(exc))


@router.get(
    "/pools/{pool_id}",
    response_model=PoolStatisticsResponse,
    summary="Get pool statistics",
)
async def get_pool_statistics(
    pool_id: str,
    db: AsyncSession = Depends(get_async_session),
) -> PoolStatisticsResponse:
    """Get detailed statistics for a pool."""
    try:
        from src.quiz import QuizPoolManager

        manager = QuizPoolManager(db)
        stats = await manager.get_pool_statistics(UUID(pool_id))

        if not stats:
            raise HTTPException(status_code=404, detail="Pool not found")

        return PoolStatisticsResponse(
            pool_id=str(stats.pool_id),
            pool_name=stats.pool_name,
            total_questions=stats.total_questions,
            active_questions=stats.active_questions,
            avg_difficulty=stats.avg_difficulty,
            difficulty_distribution=stats.difficulty_distribution,
            type_distribution=stats.type_distribution,
            knowledge_type_distribution=stats.knowledge_type_distribution,
            quality_distribution=stats.quality_distribution,
            has_sufficient_questions=stats.has_sufficient_questions,
            min_questions_required=stats.min_questions_required,
        )

    except HTTPException:
        raise
    except Exception as exc:
        logger.exception(f"Failed to get pool statistics for {pool_id}")
        raise HTTPException(status_code=500, detail=str(exc))


@router.post(
    "/pools/{pool_id}/select",
    response_model=List[SelectedQuestionResponse],
    summary="Select questions from pool",
)
async def select_questions_from_pool(
    pool_id: str,
    request: SelectQuestionsRequest,
    db: AsyncSession = Depends(get_async_session),
) -> List[SelectedQuestionResponse]:
    """
    Select random questions from a pool.

    Uses seed for reproducible selection across attempts.
    """
    try:
        from src.quiz import QuizPoolManager

        manager = QuizPoolManager(db)

        difficulty_range = None
        if request.difficulty_range and len(request.difficulty_range) == 2:
            difficulty_range = (request.difficulty_range[0], request.difficulty_range[1])

        if request.diversity_weights:
            questions = await manager.select_diverse_questions(
                pool_id=UUID(pool_id),
                count=request.count,
                seed=request.seed,
                diversity_weights=request.diversity_weights,
            )
        else:
            questions = await manager.select_questions(
                pool_id=UUID(pool_id),
                count=request.count,
                seed=request.seed,
                exclude_ids=[UUID(eid) for eid in request.exclude_ids],
                difficulty_range=difficulty_range,
                question_types=request.question_types,
            )

        return [
            SelectedQuestionResponse(
                question_id=str(q.question_id),
                atom_id=str(q.atom_id),
                question_type=q.question_type,
                difficulty=q.difficulty,
                front=q.front,
                question_content=q.question_content,
            )
            for q in questions
        ]

    except Exception as exc:
        logger.exception(f"Failed to select questions from pool {pool_id}")
        raise HTTPException(status_code=500, detail=str(exc))


@router.post(
    "/pools/{pool_id}/add-questions",
    summary="Add questions to pool",
)
async def add_questions_to_pool(
    pool_id: str,
    question_ids: List[str],
    db: AsyncSession = Depends(get_async_session),
) -> Dict[str, Any]:
    """Add questions to a pool."""
    try:
        from src.quiz import QuizPoolManager

        manager = QuizPoolManager(db)
        count = await manager.add_questions_to_pool(
            pool_id=UUID(pool_id),
            question_ids=[UUID(qid) for qid in question_ids],
        )

        await db.commit()

        return {"success": True, "questions_added": count}

    except Exception as exc:
        logger.exception(f"Failed to add questions to pool {pool_id}")
        raise HTTPException(status_code=500, detail=str(exc))


# ========================================
# Quiz Definition Endpoints
# ========================================


@router.post(
    "/definitions",
    response_model=QuizDefinitionResponse,
    summary="Create quiz definition",
)
async def create_quiz_definition(
    request: QuizDefinitionCreateRequest,
    db: AsyncSession = Depends(get_async_session),
) -> QuizDefinitionResponse:
    """
    Create a new quiz definition.

    Mastery formula: mastery = (review_score * review_weight) + (quiz_score * quiz_weight)
    Default: 62.5% review + 37.5% quiz
    """
    try:
        from src.db.models import QuizDefinition

        definition = QuizDefinition(
            name=request.name,
            concept_id=UUID(request.concept_id) if request.concept_id else None,
            concept_cluster_id=UUID(request.concept_cluster_id) if request.concept_cluster_id else None,
            question_pool_ids=[UUID(pid) for pid in request.question_pool_ids],
            question_count=request.question_count,
            time_limit_seconds=request.time_limit_seconds,
            passing_score=Decimal(str(request.passing_score)),
            quiz_weight=Decimal(str(request.quiz_weight)),
            review_weight=Decimal(str(request.review_weight)),
            description=request.description,
            is_active=True,
        )

        db.add(definition)
        await db.commit()

        return QuizDefinitionResponse(
            id=str(definition.id),
            name=definition.name,
            concept_id=str(definition.concept_id) if definition.concept_id else None,
            concept_cluster_id=str(definition.concept_cluster_id) if definition.concept_cluster_id else None,
            question_pool_ids=[str(pid) for pid in definition.question_pool_ids],
            question_count=definition.question_count,
            time_limit_seconds=definition.time_limit_seconds,
            passing_score=float(definition.passing_score),
            quiz_weight=float(definition.quiz_weight),
            review_weight=float(definition.review_weight),
            description=definition.description,
            is_active=definition.is_active,
            created_at=definition.created_at,
        )

    except Exception as exc:
        logger.exception("Failed to create quiz definition")
        raise HTTPException(status_code=500, detail=str(exc))


@router.get(
    "/definitions",
    response_model=List[QuizDefinitionResponse],
    summary="List quiz definitions",
)
async def list_quiz_definitions(
    concept_id: Optional[str] = Query(None),
    is_active: bool = Query(True),
    db: AsyncSession = Depends(get_async_session),
) -> List[QuizDefinitionResponse]:
    """List quiz definitions."""
    try:
        from sqlalchemy import select, and_
        from src.db.models import QuizDefinition

        conditions = [QuizDefinition.is_active == is_active]
        if concept_id:
            conditions.append(QuizDefinition.concept_id == UUID(concept_id))

        result = await db.execute(
            select(QuizDefinition).where(and_(*conditions))
        )
        definitions = result.scalars().all()

        return [
            QuizDefinitionResponse(
                id=str(d.id),
                name=d.name,
                concept_id=str(d.concept_id) if d.concept_id else None,
                concept_cluster_id=str(d.concept_cluster_id) if d.concept_cluster_id else None,
                question_pool_ids=[str(pid) for pid in (d.question_pool_ids or [])],
                question_count=d.question_count,
                time_limit_seconds=d.time_limit_seconds,
                passing_score=float(d.passing_score),
                quiz_weight=float(d.quiz_weight),
                review_weight=float(d.review_weight),
                description=d.description,
                is_active=d.is_active,
                created_at=d.created_at,
            )
            for d in definitions
        ]

    except Exception as exc:
        logger.exception("Failed to list quiz definitions")
        raise HTTPException(status_code=500, detail=str(exc))


@router.get(
    "/definitions/{definition_id}",
    response_model=QuizDefinitionResponse,
    summary="Get quiz definition",
)
async def get_quiz_definition(
    definition_id: str,
    db: AsyncSession = Depends(get_async_session),
) -> QuizDefinitionResponse:
    """Get a quiz definition by ID."""
    try:
        from sqlalchemy import select
        from src.db.models import QuizDefinition

        result = await db.execute(
            select(QuizDefinition).where(QuizDefinition.id == UUID(definition_id))
        )
        definition = result.scalar_one_or_none()

        if not definition:
            raise HTTPException(status_code=404, detail="Quiz definition not found")

        return QuizDefinitionResponse(
            id=str(definition.id),
            name=definition.name,
            concept_id=str(definition.concept_id) if definition.concept_id else None,
            concept_cluster_id=str(definition.concept_cluster_id) if definition.concept_cluster_id else None,
            question_pool_ids=[str(pid) for pid in (definition.question_pool_ids or [])],
            question_count=definition.question_count,
            time_limit_seconds=definition.time_limit_seconds,
            passing_score=float(definition.passing_score),
            quiz_weight=float(definition.quiz_weight),
            review_weight=float(definition.review_weight),
            description=definition.description,
            is_active=definition.is_active,
            created_at=definition.created_at,
        )

    except HTTPException:
        raise
    except Exception as exc:
        logger.exception(f"Failed to get quiz definition {definition_id}")
        raise HTTPException(status_code=500, detail=str(exc))


# ========================================
# Export Endpoints (for right-learning)
# ========================================


@router.get(
    "/export/definitions",
    summary="Export quiz definitions for right-learning",
)
async def export_definitions(
    db: AsyncSession = Depends(get_async_session),
) -> Dict[str, Any]:
    """
    Export all quiz definitions for right-learning integration.

    Returns definitions with pool info and mastery weights.
    """
    try:
        from sqlalchemy import select
        from src.db.models import QuizDefinition

        result = await db.execute(
            select(QuizDefinition).where(QuizDefinition.is_active == True)
        )
        definitions = result.scalars().all()

        return {
            "version": "1.0",
            "exported_at": datetime.utcnow().isoformat(),
            "definitions": [
                {
                    "id": str(d.id),
                    "name": d.name,
                    "concept_id": str(d.concept_id) if d.concept_id else None,
                    "question_count": d.question_count,
                    "time_limit_seconds": d.time_limit_seconds,
                    "passing_score": float(d.passing_score),
                    "mastery_formula": {
                        "quiz_weight": float(d.quiz_weight),
                        "review_weight": float(d.review_weight),
                        "formula": "mastery = (review_score * review_weight) + (quiz_score * quiz_weight)"
                    },
                    "pool_ids": [str(pid) for pid in (d.question_pool_ids or [])],
                }
                for d in definitions
            ],
        }

    except Exception as exc:
        logger.exception("Failed to export definitions")
        raise HTTPException(status_code=500, detail=str(exc))


@router.get(
    "/export/questions/{quiz_id}",
    summary="Export quiz questions for right-learning",
)
async def export_quiz_questions(
    quiz_id: str,
    user_id: Optional[str] = Query(None),
    attempt: int = Query(1, ge=1),
    db: AsyncSession = Depends(get_async_session),
) -> Dict[str, Any]:
    """
    Export questions for a specific quiz attempt.

    If user_id is provided, uses it for reproducible selection.
    """
    try:
        from src.quiz import QuizPoolManager

        manager = QuizPoolManager(db)

        questions = await manager.select_questions_for_quiz(
            quiz_definition_id=UUID(quiz_id),
            user_id=user_id or "anonymous",
            attempt_number=attempt,
        )

        return {
            "version": "1.0",
            "quiz_id": quiz_id,
            "attempt": attempt,
            "questions": [
                {
                    "question_id": str(q.question_id),
                    "type": q.question_type,
                    "difficulty": q.difficulty,
                    "content": q.question_content,
                    "front": q.front,
                }
                for q in questions
            ],
            "metadata": {
                "exported_at": datetime.utcnow().isoformat(),
                "question_count": len(questions),
            },
        }

    except Exception as exc:
        logger.exception(f"Failed to export questions for quiz {quiz_id}")
        raise HTTPException(status_code=500, detail=str(exc))
