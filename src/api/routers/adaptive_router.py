"""
Adaptive Learning API Router.

Endpoints for the adaptive learning engine:
- Session management (create, get, end)
- Answer processing with remediation
- Mastery tracking and recalculation
- Learning path generation
- Knowledge gap identification
- Suitability scoring

Phase 5 implementation: Knewton-style adaptive learning.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from loguru import logger
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.database import get_async_session

router = APIRouter()


# ========================================
# Request/Response Models
# ========================================


class SessionCreateRequest(BaseModel):
    """Request model for creating a learning session."""

    learner_id: str = Field(..., description="Learner identifier")
    mode: str = Field("adaptive", description="Session mode: adaptive, review, quiz, remediation")
    target_concept_id: str | None = Field(None, description="Target concept UUID")
    target_cluster_id: str | None = Field(None, description="Target cluster UUID")
    atom_count: int = Field(20, ge=1, le=100, description="Number of atoms for session")


class AtomPresentationResponse(BaseModel):
    """Response model for an atom presentation."""

    atom_id: str
    atom_type: str
    front: str
    back: str | None
    content_json: dict[str, Any] | None
    concept_name: str | None
    is_remediation: bool = False
    remediation_for: str | None = None


class SessionProgressResponse(BaseModel):
    """Response model for session progress."""

    atoms_completed: int
    atoms_remaining: int
    atoms_correct: int
    atoms_incorrect: int
    accuracy: float
    remediation_count: int


class SessionResponse(BaseModel):
    """Response model for a learning session."""

    session_id: str
    learner_id: str
    mode: str
    status: str
    target_concept_name: str | None
    target_cluster_name: str | None
    progress: SessionProgressResponse
    current_atom: AtomPresentationResponse | None
    next_atom: AtomPresentationResponse | None
    started_at: datetime | None


class AnswerSubmitRequest(BaseModel):
    """Request model for submitting an answer."""

    atom_id: str = Field(..., description="Atom UUID being answered")
    answer: str = Field(..., description="Learner's answer")
    confidence: float | None = Field(None, ge=0, le=1, description="Self-reported confidence (0-1)")
    time_taken_seconds: int | None = Field(None, ge=0, description="Time spent on the atom")


class RemediationPlanResponse(BaseModel):
    """Response model for a remediation plan."""

    gap_concept_id: str
    gap_concept_name: str
    atoms: list[str]
    priority: str
    gating_type: str
    mastery_target: float
    estimated_duration_minutes: int


class AnswerResultResponse(BaseModel):
    """Response model for answer evaluation."""

    is_correct: bool
    score: float
    explanation: str | None
    correct_answer: str | None
    remediation_triggered: bool
    remediation_plan: RemediationPlanResponse | None


class KnowledgeBreakdownResponse(BaseModel):
    """Response model for knowledge type breakdown."""

    declarative: float
    procedural: float
    application: float


class ConceptMasteryResponse(BaseModel):
    """Response model for concept mastery."""

    concept_id: str
    concept_name: str
    review_mastery: float
    quiz_mastery: float
    combined_mastery: float
    mastery_level: str
    knowledge_breakdown: KnowledgeBreakdownResponse
    is_unlocked: bool
    unlock_reason: str | None
    review_count: int
    quiz_attempt_count: int


class LearningPathResponse(BaseModel):
    """Response model for a learning path."""

    target_concept_id: str
    target_concept_name: str
    prerequisites: list[ConceptMasteryResponse]
    path_atoms: list[str]
    estimated_atoms: int
    estimated_duration_minutes: int
    current_mastery: float
    target_mastery: float
    mastery_to_gain: float


class KnowledgeGapResponse(BaseModel):
    """Response model for a knowledge gap."""

    concept_id: str
    concept_name: str
    current_mastery: float
    required_mastery: float
    gap_size: float
    priority: str
    recommended_atoms: list[str]
    estimated_duration_minutes: int


class SuitabilityScoreResponse(BaseModel):
    """Response model for suitability score."""

    score: float
    knowledge_signal: float
    structure_signal: float
    length_signal: float


class AtomSuitabilityResponse(BaseModel):
    """Response model for atom suitability analysis."""

    atom_id: str
    current_type: str
    recommended_type: str
    recommendation_confidence: float
    type_mismatch: bool
    scores: dict[str, SuitabilityScoreResponse]


class UnlockStatusResponse(BaseModel):
    """Response model for concept unlock status."""

    is_unlocked: bool
    blocking_prerequisites: list[dict[str, Any]]
    unlock_reason: str | None
    estimated_atoms_to_unlock: int


# ========================================
# Session Management Endpoints
# ========================================


@router.post(
    "/sessions",
    response_model=SessionResponse,
    summary="Create learning session",
)
async def create_session(
    request: SessionCreateRequest,
    db: AsyncSession = Depends(get_async_session),
) -> SessionResponse:
    """
    Create a new adaptive learning session.

    Session modes:
    - adaptive: Full adaptive with just-in-time remediation
    - review: Review due items based on FSRS scheduling
    - quiz: Quiz mode (no hints, no remediation)
    - remediation: Focused remediation for knowledge gaps
    """
    logger.info(f"Creating {request.mode} session for learner {request.learner_id}")

    try:
        from src.adaptive import LearningEngine, SessionMode

        engine = LearningEngine()

        mode_map = {
            "adaptive": SessionMode.ADAPTIVE,
            "review": SessionMode.REVIEW,
            "quiz": SessionMode.QUIZ,
            "remediation": SessionMode.REMEDIATION,
        }
        mode = mode_map.get(request.mode, SessionMode.ADAPTIVE)

        session_state = engine.create_session(
            learner_id=request.learner_id,
            mode=mode,
            target_concept_id=UUID(request.target_concept_id)
            if request.target_concept_id
            else None,
            target_cluster_id=UUID(request.target_cluster_id)
            if request.target_cluster_id
            else None,
            atom_count=request.atom_count,
        )

        return _session_to_response(session_state)

    except Exception as exc:
        logger.exception("Failed to create session")
        raise HTTPException(status_code=500, detail=str(exc))


@router.get(
    "/sessions/{session_id}",
    response_model=SessionResponse,
    summary="Get session state",
)
async def get_session(
    session_id: str,
    db: AsyncSession = Depends(get_async_session),
) -> SessionResponse:
    """Get current state of a learning session."""
    try:
        from src.adaptive import LearningEngine

        engine = LearningEngine()
        session_state = engine.get_session(UUID(session_id))

        if not session_state:
            raise HTTPException(status_code=404, detail="Session not found")

        return _session_to_response(session_state)

    except HTTPException:
        raise
    except Exception as exc:
        logger.exception(f"Failed to get session {session_id}")
        raise HTTPException(status_code=500, detail=str(exc))


@router.post(
    "/sessions/{session_id}/end",
    response_model=SessionResponse,
    summary="End session",
)
async def end_session(
    session_id: str,
    status: str = Query("completed", description="Final status: completed, abandoned"),
    db: AsyncSession = Depends(get_async_session),
) -> SessionResponse:
    """End a learning session."""
    try:
        from src.adaptive import LearningEngine, SessionStatus

        engine = LearningEngine()

        status_map = {
            "completed": SessionStatus.COMPLETED,
            "abandoned": SessionStatus.ABANDONED,
        }
        final_status = status_map.get(status, SessionStatus.COMPLETED)

        session_state = engine.end_session(UUID(session_id), final_status)
        return _session_to_response(session_state)

    except Exception as exc:
        logger.exception(f"Failed to end session {session_id}")
        raise HTTPException(status_code=500, detail=str(exc))


# ========================================
# Answer Processing Endpoints
# ========================================


@router.post(
    "/sessions/{session_id}/answer",
    response_model=AnswerResultResponse,
    summary="Submit answer",
)
async def submit_answer(
    session_id: str,
    request: AnswerSubmitRequest,
    db: AsyncSession = Depends(get_async_session),
) -> AnswerResultResponse:
    """
    Submit an answer and get evaluation with potential remediation.

    This is the core adaptive loop:
    1. Evaluates the answer
    2. Checks for knowledge gaps
    3. Triggers remediation if needed
    4. Updates mastery state
    """
    try:
        from src.adaptive import LearningEngine

        engine = LearningEngine()

        result = engine.submit_answer(
            session_id=UUID(session_id),
            atom_id=UUID(request.atom_id),
            answer=request.answer,
            confidence=request.confidence,
            time_taken_seconds=request.time_taken_seconds,
        )

        remediation_response = None
        if result.remediation_plan:
            plan = result.remediation_plan
            remediation_response = RemediationPlanResponse(
                gap_concept_id=str(plan.gap_concept_id),
                gap_concept_name=plan.gap_concept_name,
                atoms=[str(a) for a in plan.atoms],
                priority=plan.priority,
                gating_type=plan.gating_type.value,
                mastery_target=plan.mastery_target,
                estimated_duration_minutes=plan.estimated_duration_minutes,
            )

        return AnswerResultResponse(
            is_correct=result.is_correct,
            score=result.score,
            explanation=result.explanation,
            correct_answer=result.correct_answer,
            remediation_triggered=result.remediation_triggered,
            remediation_plan=remediation_response,
        )

    except Exception as exc:
        logger.exception(f"Failed to submit answer for session {session_id}")
        raise HTTPException(status_code=500, detail=str(exc))


@router.get(
    "/sessions/{session_id}/next-atom",
    response_model=AtomPresentationResponse | None,
    summary="Get next atom",
)
async def get_next_atom(
    session_id: str,
    db: AsyncSession = Depends(get_async_session),
) -> AtomPresentationResponse | None:
    """
    Get the next atom in the session.

    Handles active remediation sequences and normal progression.
    Returns null when session is complete.
    """
    try:
        from src.adaptive import LearningEngine

        engine = LearningEngine()
        atom = engine.get_next_atom(UUID(session_id))

        if not atom:
            return None

        return AtomPresentationResponse(
            atom_id=str(atom.atom_id),
            atom_type=atom.atom_type,
            front=atom.front,
            back=atom.back,
            content_json=atom.content_json,
            concept_name=atom.concept_name,
            is_remediation=atom.is_remediation,
            remediation_for=atom.remediation_for,
        )

    except Exception as exc:
        logger.exception(f"Failed to get next atom for session {session_id}")
        raise HTTPException(status_code=500, detail=str(exc))


# ========================================
# Mastery & Progress Endpoints
# ========================================


@router.get(
    "/mastery/{learner_id}",
    response_model=list[ConceptMasteryResponse],
    summary="Get learner mastery",
)
async def get_learner_mastery(
    learner_id: str,
    concept_ids: str | None = Query(None, description="Comma-separated concept UUIDs"),
    cluster_id: str | None = Query(None, description="Filter by cluster"),
    db: AsyncSession = Depends(get_async_session),
) -> list[ConceptMasteryResponse]:
    """Get mastery state for a learner across concepts."""
    try:
        from src.adaptive import LearningEngine

        engine = LearningEngine()

        concept_uuid_list = None
        if concept_ids:
            concept_uuid_list = [UUID(c.strip()) for c in concept_ids.split(",")]

        mastery_list = engine.get_learner_mastery(
            learner_id=learner_id,
            concept_ids=concept_uuid_list,
            cluster_id=UUID(cluster_id) if cluster_id else None,
        )

        return [
            ConceptMasteryResponse(
                concept_id=str(m.concept_id),
                concept_name=m.concept_name,
                review_mastery=m.review_mastery,
                quiz_mastery=m.quiz_mastery,
                combined_mastery=m.combined_mastery,
                mastery_level=m.mastery_level.value,
                knowledge_breakdown=KnowledgeBreakdownResponse(
                    declarative=m.knowledge_breakdown.dec_score,
                    procedural=m.knowledge_breakdown.proc_score,
                    application=m.knowledge_breakdown.app_score,
                ),
                is_unlocked=m.is_unlocked,
                unlock_reason=m.unlock_reason,
                review_count=m.review_count,
                quiz_attempt_count=m.quiz_attempt_count,
            )
            for m in mastery_list
        ]

    except Exception as exc:
        logger.exception(f"Failed to get mastery for learner {learner_id}")
        raise HTTPException(status_code=500, detail=str(exc))


@router.post(
    "/mastery/recalculate",
    summary="Recalculate mastery",
)
async def recalculate_mastery(
    learner_id: str = Query(..., description="Learner identifier"),
    concept_ids: str | None = Query(None, description="Comma-separated concept UUIDs"),
    db: AsyncSession = Depends(get_async_session),
) -> dict[str, Any]:
    """Trigger mastery recalculation for a learner."""
    try:
        from src.adaptive import LearningEngine

        engine = LearningEngine()

        concept_uuid_list = None
        if concept_ids:
            concept_uuid_list = [UUID(c.strip()) for c in concept_ids.split(",")]

        count = engine.recalculate_mastery(learner_id, concept_uuid_list)

        return {
            "success": True,
            "concepts_updated": count,
            "learner_id": learner_id,
        }

    except Exception as exc:
        logger.exception(f"Failed to recalculate mastery for {learner_id}")
        raise HTTPException(status_code=500, detail=str(exc))


# ========================================
# Learning Path Endpoints
# ========================================


@router.get(
    "/path/{learner_id}/{concept_id}",
    response_model=LearningPathResponse,
    summary="Get learning path",
)
async def get_learning_path(
    learner_id: str,
    concept_id: str,
    target_mastery: float = Query(0.85, ge=0, le=1, description="Target mastery level"),
    db: AsyncSession = Depends(get_async_session),
) -> LearningPathResponse:
    """
    Get optimal learning path to master a concept.

    Returns prerequisites and ordered atoms based on:
    - Prerequisite graph
    - Current mastery state
    - Knowledge type interleaving
    """
    try:
        from src.adaptive import LearningEngine

        engine = LearningEngine()

        path = engine.get_learning_path(
            learner_id=learner_id,
            target_concept_id=UUID(concept_id),
            target_mastery=target_mastery,
        )

        return LearningPathResponse(
            target_concept_id=str(path.target_concept_id),
            target_concept_name=path.target_concept_name,
            prerequisites=[
                ConceptMasteryResponse(
                    concept_id=str(p.concept_id),
                    concept_name=p.concept_name,
                    review_mastery=p.review_mastery,
                    quiz_mastery=p.quiz_mastery,
                    combined_mastery=p.combined_mastery,
                    mastery_level=p.mastery_level.value,
                    knowledge_breakdown=KnowledgeBreakdownResponse(
                        declarative=p.knowledge_breakdown.dec_score,
                        procedural=p.knowledge_breakdown.proc_score,
                        application=p.knowledge_breakdown.app_score,
                    ),
                    is_unlocked=p.is_unlocked,
                    unlock_reason=p.unlock_reason,
                    review_count=p.review_count,
                    quiz_attempt_count=p.quiz_attempt_count,
                )
                for p in path.prerequisites_to_complete
            ],
            path_atoms=[str(a) for a in path.path_atoms],
            estimated_atoms=path.estimated_atoms,
            estimated_duration_minutes=path.estimated_duration_minutes,
            current_mastery=path.current_mastery,
            target_mastery=path.target_mastery,
            mastery_to_gain=path.mastery_to_gain,
        )

    except Exception as exc:
        logger.exception(f"Failed to get learning path for {concept_id}")
        raise HTTPException(status_code=500, detail=str(exc))


@router.get(
    "/next-atom/{learner_id}",
    response_model=list[str],
    summary="Get next optimal atoms",
)
async def get_next_optimal_atoms(
    learner_id: str,
    concept_id: str | None = Query(None, description="Optional concept focus"),
    cluster_id: str | None = Query(None, description="Optional cluster scope"),
    count: int = Query(10, ge=1, le=50, description="Number of atoms to return"),
    include_review: bool = Query(True, description="Include due reviews"),
    db: AsyncSession = Depends(get_async_session),
) -> list[str]:
    """
    Get next optimal atoms for a learner.

    Considers:
    - Due reviews (FSRS scheduling)
    - Unlocked concepts only
    - Knowledge type interleaving
    """
    try:
        from src.adaptive import PathSequencer

        sequencer = PathSequencer()

        atoms = sequencer.get_next_atoms(
            learner_id=learner_id,
            concept_id=UUID(concept_id) if concept_id else None,
            cluster_id=UUID(cluster_id) if cluster_id else None,
            count=count,
            include_review=include_review,
        )

        return [str(a) for a in atoms]

    except Exception as exc:
        logger.exception(f"Failed to get next atoms for {learner_id}")
        raise HTTPException(status_code=500, detail=str(exc))


# ========================================
# Remediation Endpoints
# ========================================


@router.get(
    "/remediation/{learner_id}/gaps",
    response_model=list[KnowledgeGapResponse],
    summary="Get knowledge gaps",
)
async def get_knowledge_gaps(
    learner_id: str,
    cluster_id: str | None = Query(None, description="Optional cluster scope"),
    db: AsyncSession = Depends(get_async_session),
) -> list[KnowledgeGapResponse]:
    """
    Identify knowledge gaps for a learner.

    Returns gaps ordered by priority (high, medium, low).
    """
    try:
        from src.adaptive import LearningEngine

        engine = LearningEngine()

        gaps = engine.get_knowledge_gaps(
            learner_id=learner_id,
            cluster_id=UUID(cluster_id) if cluster_id else None,
        )

        return [
            KnowledgeGapResponse(
                concept_id=str(g.concept_id),
                concept_name=g.concept_name,
                current_mastery=g.current_mastery,
                required_mastery=g.required_mastery,
                gap_size=g.gap_size,
                priority=g.priority,
                recommended_atoms=[str(a) for a in g.recommended_atoms],
                estimated_duration_minutes=g.estimated_duration_minutes,
            )
            for g in gaps
        ]

    except Exception as exc:
        logger.exception(f"Failed to get knowledge gaps for {learner_id}")
        raise HTTPException(status_code=500, detail=str(exc))


@router.post(
    "/remediation/trigger",
    response_model=RemediationPlanResponse,
    summary="Trigger manual remediation",
)
async def trigger_remediation(
    learner_id: str = Query(..., description="Learner identifier"),
    concept_id: str = Query(..., description="Concept to remediate"),
    db: AsyncSession = Depends(get_async_session),
) -> RemediationPlanResponse:
    """Manually trigger remediation for a concept."""
    try:
        from src.adaptive import RemediationRouter, TriggerType

        router = RemediationRouter()

        plan = router.trigger_remediation(
            learner_id=learner_id,
            concept_id=UUID(concept_id),
            trigger_type=TriggerType.MANUAL,
        )

        if not plan:
            raise HTTPException(
                status_code=404, detail="No remediation needed or no atoms available"
            )

        return RemediationPlanResponse(
            gap_concept_id=str(plan.gap_concept_id),
            gap_concept_name=plan.gap_concept_name,
            atoms=[str(a) for a in plan.atoms],
            priority=plan.priority,
            gating_type=plan.gating_type.value,
            mastery_target=plan.mastery_target,
            estimated_duration_minutes=plan.estimated_duration_minutes,
        )

    except HTTPException:
        raise
    except Exception as exc:
        logger.exception(f"Failed to trigger remediation for {concept_id}")
        raise HTTPException(status_code=500, detail=str(exc))


@router.get(
    "/unlock-status/{learner_id}/{concept_id}",
    response_model=UnlockStatusResponse,
    summary="Check unlock status",
)
async def check_unlock_status(
    learner_id: str,
    concept_id: str,
    db: AsyncSession = Depends(get_async_session),
) -> UnlockStatusResponse:
    """Check if a concept is unlocked for a learner."""
    try:
        from src.adaptive import PathSequencer

        sequencer = PathSequencer()

        status = sequencer.check_unlock_status(
            learner_id=learner_id,
            concept_id=UUID(concept_id),
        )

        return UnlockStatusResponse(
            is_unlocked=status.is_unlocked,
            blocking_prerequisites=[
                {
                    "concept_id": str(b.concept_id),
                    "concept_name": b.concept_name,
                    "required_mastery": b.required_mastery,
                    "current_mastery": b.current_mastery,
                    "gating_type": b.gating_type.value,
                    "mastery_gap": b.mastery_gap,
                    "progress_percent": b.progress_percent,
                }
                for b in status.blocking_prerequisites
            ],
            unlock_reason=status.unlock_reason,
            estimated_atoms_to_unlock=status.estimated_atoms_to_unlock,
        )

    except Exception as exc:
        logger.exception(f"Failed to check unlock status for {concept_id}")
        raise HTTPException(status_code=500, detail=str(exc))


# ========================================
# Suitability Endpoints
# ========================================


@router.get(
    "/suitability/{atom_id}",
    response_model=AtomSuitabilityResponse,
    summary="Get atom suitability",
)
async def get_atom_suitability(
    atom_id: str,
    db: AsyncSession = Depends(get_async_session),
) -> AtomSuitabilityResponse:
    """Get suitability scores for an atom across all atom types."""
    try:
        from src.adaptive import LearningEngine

        engine = LearningEngine()
        result = engine.get_atom_suitability(UUID(atom_id))

        return AtomSuitabilityResponse(
            atom_id=result["atom_id"],
            current_type=result["current_type"],
            recommended_type=result["recommended_type"],
            recommendation_confidence=result["recommendation_confidence"],
            type_mismatch=result["type_mismatch"],
            scores={
                k: SuitabilityScoreResponse(
                    score=v["score"],
                    knowledge_signal=v["knowledge_signal"],
                    structure_signal=v["structure_signal"],
                    length_signal=v["length_signal"],
                )
                for k, v in result["scores"].items()
            },
        )

    except Exception as exc:
        logger.exception(f"Failed to get suitability for atom {atom_id}")
        raise HTTPException(status_code=500, detail=str(exc))


@router.post(
    "/suitability/batch",
    summary="Batch compute suitability",
)
async def batch_compute_suitability(
    atom_ids: list[str] | None = None,
    limit: int = Query(100, ge=1, le=1000, description="Max atoms to process"),
    db: AsyncSession = Depends(get_async_session),
) -> dict[str, Any]:
    """
    Batch compute and store suitability scores.

    If atom_ids not provided, processes atoms without scores.
    """
    try:
        from src.adaptive import LearningEngine

        engine = LearningEngine()

        atom_uuid_list = None
        if atom_ids:
            atom_uuid_list = [UUID(a) for a in atom_ids]

        count = engine.batch_compute_suitability(atom_uuid_list, limit)

        return {
            "success": True,
            "atoms_processed": count,
        }

    except Exception as exc:
        logger.exception("Failed to batch compute suitability")
        raise HTTPException(status_code=500, detail=str(exc))


# ========================================
# Helper Functions
# ========================================


def _session_to_response(session_state) -> SessionResponse:
    """Convert SessionState to SessionResponse."""
    current_atom = None
    if session_state.current_atom:
        a = session_state.current_atom
        current_atom = AtomPresentationResponse(
            atom_id=str(a.atom_id),
            atom_type=a.atom_type,
            front=a.front,
            back=a.back,
            content_json=a.content_json,
            concept_name=a.concept_name,
            is_remediation=a.is_remediation,
            remediation_for=a.remediation_for,
        )

    next_atom = None
    if session_state.next_atom:
        a = session_state.next_atom
        next_atom = AtomPresentationResponse(
            atom_id=str(a.atom_id),
            atom_type=a.atom_type,
            front=a.front,
            back=a.back,
            content_json=a.content_json,
            concept_name=a.concept_name,
            is_remediation=a.is_remediation,
            remediation_for=a.remediation_for,
        )

    progress = session_state.progress
    return SessionResponse(
        session_id=str(session_state.session_id),
        learner_id=session_state.learner_id,
        mode=session_state.mode.value,
        status=session_state.status.value,
        target_concept_name=session_state.target_concept_name,
        target_cluster_name=session_state.target_cluster_name,
        progress=SessionProgressResponse(
            atoms_completed=progress.atoms_completed,
            atoms_remaining=progress.atoms_remaining,
            atoms_correct=progress.atoms_correct,
            atoms_incorrect=progress.atoms_incorrect,
            accuracy=progress.accuracy,
            remediation_count=progress.remediation_count,
        ),
        current_atom=current_atom,
        next_atom=next_atom,
        started_at=session_state.started_at,
    )
