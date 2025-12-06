"""
Cleaning pipeline router.

Endpoints for running atomicity checks, duplicate detection, and AI rewriting.
Includes curriculum-scoped pipeline for filtering cards by module.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from loguru import logger
from pydantic import BaseModel, Field

from src.db.database import get_session
from sqlalchemy.orm import Session

router = APIRouter()


# ========================================
# Request/Response Models
# ========================================


class CleaningRequest(BaseModel):
    """Request model for cleaning pipeline."""

    dry_run: bool = False
    enable_rewrite: bool = False
    min_grade_for_rewrite: str = "D"


class CleaningResponse(BaseModel):
    """Response model for cleaning operations."""

    success: bool
    message: str
    stats: Dict[str, int]


class QualityCheckResponse(BaseModel):
    """Response model for quality check."""

    total_checked: int
    grade_distribution: Dict[str, int]
    average_quality: float
    issues_found: List[Dict[str, Any]]


class CurriculumPipelineRequest(BaseModel):
    """Request model for curriculum-scoped pipeline."""

    module_name: str = Field(..., description="Name of the module (e.g., 'CCNA Module 1')")
    source: str = Field("anki", description="Data source: 'anki' or 'learning_atoms'")
    deck_name: Optional[str] = Field(None, description="Optional Anki deck name filter")
    auto_split: bool = Field(True, description="Automatically split verbose cards")
    generate_embeddings: bool = Field(True, description="Generate embeddings for semantic analysis")
    remove_duplicates: bool = Field(True, description="Remove duplicate cards")
    dry_run: bool = Field(False, description="Preview without making changes")


class CurriculumPipelineResponse(BaseModel):
    """Response model for curriculum-scoped pipeline."""

    success: bool
    module_name: str
    total_cards_processed: int
    cards_in_module: int
    cards_reassigned: int
    cards_split: int
    duplicates_removed: int
    quality_distribution: Dict[str, int]
    reassignment_suggestions: List[Dict[str, Any]]
    processing_time_seconds: float
    errors: List[str] = Field(default_factory=list)


# ========================================
# Cleaning Endpoints
# ========================================


@router.post("/run", response_model=CleaningResponse, summary="Run cleaning pipeline")
def run_cleaning_pipeline(request: CleaningRequest = CleaningRequest()) -> CleaningResponse:
    """
    Run full cleaning pipeline on staging tables.

    Transforms staging → canonical with:
    - Atomicity validation (word counts, complexity)
    - Duplicate detection (exact + fuzzy + semantic)
    - AI rewriting for grade D/F (if enabled)
    - Quality grading (A-F scale)

    **Phase 3 Implementation Required**
    """
    logger.info(
        f"Cleaning pipeline requested (rewrite={request.enable_rewrite}, dry_run={request.dry_run})"
    )

    # TODO: Phase 3 - Implement with CleaningPipeline
    raise HTTPException(
        status_code=501,
        detail="Cleaning pipeline not yet implemented (Phase 3)",
    )

    # from src.cleaning.pipeline import CleaningPipeline
    # pipeline = CleaningPipeline()
    # results = pipeline.process_all(enable_rewrite=request.enable_rewrite)
    #
    # return CleaningResponse(
    #     success=True,
    #     message=f"Processed {results['processed']} atoms",
    #     stats=results,
    # )


@router.get("/check", response_model=QualityCheckResponse, summary="Check quality without modifications")
def check_quality(
    limit: int = 100,
    source: str = "staging",
) -> QualityCheckResponse:
    """
    Check atomicity quality without modifications.

    Analyzes cards and reports quality distribution without
    making any changes to the database.

    **Phase 3 Implementation Required**
    """
    logger.info(f"Quality check requested (limit={limit}, source={source})")

    # TODO: Phase 3 - Implement with CardQualityAnalyzer
    raise HTTPException(
        status_code=501,
        detail="Quality checking not yet implemented (Phase 3)",
    )


@router.get("/duplicates", summary="Detect duplicates")
def detect_duplicates(
    method: str = "fuzzy",
    threshold: float = 0.85,
) -> Dict[str, Any]:
    """
    Detect duplicate cards using various methods.

    Methods:
    - exact: Exact string matching
    - fuzzy: rapidfuzz similarity (default)
    - semantic: Embedding-based similarity

    **Phase 3 Implementation Required**
    """
    logger.info(f"Duplicate detection requested (method={method}, threshold={threshold})")

    # TODO: Phase 3 - Implement duplicate detection
    raise HTTPException(
        status_code=501,
        detail="Duplicate detection not yet implemented (Phase 3)",
    )


@router.post("/rewrite/{atom_id}", summary="Rewrite a specific atom")
def rewrite_atom(
    atom_id: str,
    dry_run: bool = False,
) -> Dict[str, Any]:
    """
    Rewrite a specific atom using Gemini AI.

    Uses prompt templates to improve atomicity for grade D/F cards.

    **Phase 3 Implementation Required**
    """
    logger.info(f"Rewrite requested for atom: {atom_id}")

    # TODO: Phase 3 - Implement with AIRewriter
    raise HTTPException(
        status_code=501,
        detail="AI rewriting not yet implemented (Phase 3)",
    )


@router.get("/stats", summary="Get cleaning pipeline stats")
def get_cleaning_stats() -> Dict[str, Any]:
    """
    Get statistics about the cleaning pipeline.

    Returns:
    - Total atoms processed
    - Quality grade distribution
    - Rewrite success rate
    - Duplicate merge suggestions

    **Phase 3 Implementation Required**
    """
    # TODO: Phase 3 - Query cleaning_logs table
    raise HTTPException(
        status_code=501,
        detail="Cleaning stats not yet implemented (Phase 3)",
    )


# ========================================
# Curriculum-Scoped Pipeline (Phase 2.5)
# ========================================


@router.post(
    "/curriculum",
    response_model=CurriculumPipelineResponse,
    summary="Run curriculum-scoped pipeline",
)
def run_curriculum_pipeline(
    request: CurriculumPipelineRequest,
    db: Session = Depends(get_session),
) -> CurriculumPipelineResponse:
    """
    Run curriculum-scoped cleaning pipeline for a specific module.

    Workflow:
    1. Fetch cards from source (Anki or learning_atoms)
    2. Filter cards by module using existing links + semantic similarity
    3. Run quality analysis on module cards
    4. Split verbose cards automatically (if enabled)
    5. Detect and remove duplicates within module scope
    6. Generate reassignment suggestions for misplaced cards

    Example:
        POST /api/clean/curriculum
        {
            "module_name": "CCNA Module 1",
            "source": "anki",
            "deck_name": "CCNA::Module1",
            "auto_split": true
        }
    """
    logger.info(f"Curriculum pipeline requested for module: {request.module_name}")

    try:
        from src.cleaning.curriculum_pipeline import CurriculumPipeline

        pipeline = CurriculumPipeline(db)
        result = pipeline.process_module(
            module_name=request.module_name,
            source=request.source,
            deck_name=request.deck_name,
            auto_split=request.auto_split,
            generate_embeddings=request.generate_embeddings,
            remove_duplicates=request.remove_duplicates,
            dry_run=request.dry_run,
        )

        return CurriculumPipelineResponse(
            success=len(result.errors) == 0,
            module_name=result.module_name,
            total_cards_processed=result.total_cards_processed,
            cards_in_module=result.cards_in_module,
            cards_reassigned=result.cards_reassigned,
            cards_split=result.cards_split,
            duplicates_removed=result.duplicates_removed,
            quality_distribution=result.quality_distribution,
            reassignment_suggestions=result.reassignment_suggestions,
            processing_time_seconds=result.processing_time_seconds,
            errors=result.errors,
        )

    except Exception as exc:
        logger.exception("Curriculum pipeline failed")
        raise HTTPException(status_code=500, detail=str(exc))


@router.get(
    "/curriculum/{module_name}/summary",
    summary="Get module summary",
)
def get_module_summary(
    module_name: str,
    db: Session = Depends(get_session),
) -> Dict[str, Any]:
    """
    Get a summary of cards assigned to a module.

    Returns card counts, quality distribution, and atomic vs verbose breakdown.
    """
    try:
        from src.cleaning.curriculum_pipeline import CurriculumPipeline

        pipeline = CurriculumPipeline(db)
        return pipeline.get_module_summary(module_name)

    except Exception as exc:
        logger.exception(f"Failed to get summary for module: {module_name}")
        raise HTTPException(status_code=500, detail=str(exc))
