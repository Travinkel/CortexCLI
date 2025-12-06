"""
CCNA Generation API Router.

Provides REST API endpoints for:
- Content analysis and coverage tracking
- Atom generation (full pipeline or by type)
- Quality assurance and regrading
- Anki learning state migration
"""
from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from loguru import logger
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from config import get_settings
from src.db.database import get_session

router = APIRouter()


# ============================================================================
# Request/Response Models
# ============================================================================


class ModuleSummary(BaseModel):
    """Summary of a parsed CCNA module."""

    module_id: str
    module_number: int
    title: str
    total_lines: int
    section_count: int
    total_commands: int
    total_tables: int
    total_key_terms: int
    estimated_atoms: int


class ModuleCoverage(BaseModel):
    """Coverage statistics for a module."""

    module_id: str
    title: str
    total_sections: int
    estimated_atoms: int
    actual_atoms: int
    coverage_percentage: float
    grade_a_count: int
    grade_b_count: int
    grade_c_count: int
    grade_d_count: int
    grade_f_count: int
    good_quality_percentage: float
    status: str
    last_generated_at: Optional[str] = None


class GenerationRequest(BaseModel):
    """Request model for generation endpoint."""

    preserve_good_cards: bool = Field(
        True, description="Keep Grade A/B cards instead of regenerating"
    )
    include_migration: bool = Field(
        True, description="Attempt to migrate learning state from replaced cards"
    )
    dry_run: bool = Field(
        False, description="Preview without saving to database"
    )


class GenerationResponse(BaseModel):
    """Response model for generation endpoint."""

    job_id: str
    module_id: str
    status: str
    atoms_generated: int
    atoms_passed_qa: int
    atoms_flagged: int
    atoms_rejected: int
    avg_quality_score: float
    grade_distribution: Dict[str, int]
    errors: List[str] = Field(default_factory=list)


class QAReportResponse(BaseModel):
    """Response model for QA report."""

    module_id: str
    total_atoms: int
    passed: int
    flagged: int
    rejected: int
    grade_distribution: Dict[str, int]
    avg_quality_score: float
    issues_summary: Dict[str, int]


class MigrationResponse(BaseModel):
    """Response model for migration operations."""

    total_old_cards: int
    total_new_cards: int
    matched: int
    unmatched_old: int
    transfers_successful: int
    transfers_failed: int


# ============================================================================
# Content Analysis Endpoints
# ============================================================================


@router.get("/modules", response_model=List[ModuleSummary], summary="List available modules")
def list_modules():
    """
    List all available CCNA module files with basic metadata.

    Returns parsed information about each module including:
    - Module ID and number
    - Title
    - Line count
    - Section count
    - Estimated atoms needed
    """
    from src.ccna.content_parser import CCNAContentParser

    settings = get_settings()
    parser = CCNAContentParser(settings.ccna_modules_path)

    modules = parser.get_available_modules()
    summaries = []

    for module_path in modules:
        try:
            module = parser.parse_module(module_path)
            summary = parser.get_module_summary(module)
            summaries.append(ModuleSummary(
                module_id=summary["module_id"],
                module_number=summary["module_number"],
                title=summary["title"],
                total_lines=summary["total_lines"],
                section_count=summary["section_count"],
                total_commands=summary["total_commands"],
                total_tables=summary["total_tables"],
                total_key_terms=summary["total_key_terms"],
                estimated_atoms=summary["estimated_atoms"],
            ))
        except Exception as e:
            logger.error(f"Failed to parse {module_path}: {e}")

    return summaries


@router.get("/modules/{module_id}", summary="Get module details")
def get_module_details(module_id: str) -> Dict[str, Any]:
    """
    Get detailed information about a specific module.

    Includes:
    - Full section hierarchy
    - Command breakdown
    - Key terms
    - Estimated atoms per section
    """
    from src.ccna.content_parser import CCNAContentParser

    settings = get_settings()
    parser = CCNAContentParser(settings.ccna_modules_path)

    # Find matching module
    for module_path in parser.get_available_modules():
        module = parser.parse_module(module_path)
        if module.module_id == module_id:
            return parser.get_module_summary(module)

    raise HTTPException(status_code=404, detail=f"Module {module_id} not found")


@router.get(
    "/modules/{module_id}/coverage",
    response_model=ModuleCoverage,
    summary="Get module coverage"
)
def get_module_coverage(
    module_id: str,
    db: Session = Depends(get_session)
) -> ModuleCoverage:
    """
    Get content coverage and quality statistics for a module.

    Shows:
    - Estimated vs actual atoms
    - Quality grade distribution
    - Coverage percentage
    """
    from sqlalchemy import text

    query = text("""
        SELECT * FROM ccna_module_quality_summary
        WHERE module_id = :module_id
    """)

    result = db.execute(query, {"module_id": module_id}).first()

    if not result:
        raise HTTPException(
            status_code=404,
            detail=f"No coverage data for module {module_id}"
        )

    return ModuleCoverage(
        module_id=result.module_id,
        title=result.title,
        total_sections=result.total_sections,
        estimated_atoms=result.estimated_atoms,
        actual_atoms=result.actual_atoms,
        coverage_percentage=float(result.coverage_percentage or 0),
        grade_a_count=result.grade_a_count,
        grade_b_count=result.grade_b_count,
        grade_c_count=result.grade_c_count,
        grade_d_count=result.grade_d_count,
        grade_f_count=result.grade_f_count,
        good_quality_percentage=float(result.good_quality_percentage or 0),
        status=result.status,
        last_generated_at=str(result.last_generated_at) if result.last_generated_at else None,
    )


@router.get("/modules/{module_id}/gaps", summary="Identify content gaps")
def get_module_gaps(
    module_id: str,
    db: Session = Depends(get_session)
) -> Dict[str, Any]:
    """
    Identify gaps in module coverage.

    Returns:
    - Sections without atoms
    - Low-quality sections (high F rate)
    - Recommended actions
    """
    from src.ccna.content_parser import CCNAContentParser
    from sqlalchemy import text

    settings = get_settings()
    parser = CCNAContentParser(settings.ccna_modules_path)

    # Find and parse module
    module = None
    for module_path in parser.get_available_modules():
        parsed = parser.parse_module(module_path)
        if parsed.module_id == module_id:
            module = parsed
            break

    if not module:
        raise HTTPException(status_code=404, detail=f"Module {module_id} not found")

    # Get section coverage from database
    query = text("""
        SELECT section_id, atoms_generated, atoms_approved
        FROM ccna_section_status
        WHERE module_id = :module_id
    """)

    section_status = {
        row.section_id: {
            "atoms_generated": row.atoms_generated,
            "atoms_approved": row.atoms_approved,
        }
        for row in db.execute(query, {"module_id": module_id})
    }

    # Identify gaps
    missing_sections = []
    low_coverage_sections = []

    for section in module.sections:
        status = section_status.get(section.id, {})
        generated = status.get("atoms_generated", 0)
        expected = section.estimated_atoms

        if generated == 0:
            missing_sections.append({
                "section_id": section.id,
                "title": section.title,
                "estimated_atoms": expected,
            })
        elif expected > 0 and (generated / expected) < 0.5:
            low_coverage_sections.append({
                "section_id": section.id,
                "title": section.title,
                "generated": generated,
                "estimated": expected,
                "coverage": round(generated / expected * 100, 1),
            })

    return {
        "module_id": module_id,
        "total_sections": module.section_count,
        "missing_sections": missing_sections,
        "low_coverage_sections": low_coverage_sections,
        "recommendations": [
            f"Generate content for {len(missing_sections)} missing sections",
            f"Improve {len(low_coverage_sections)} low-coverage sections",
        ] if missing_sections or low_coverage_sections else ["Module coverage is adequate"],
    }


# ============================================================================
# Generation Endpoints
# ============================================================================


@router.post(
    "/generate/{module_id}",
    response_model=GenerationResponse,
    summary="Generate content for module"
)
async def generate_module_content(
    module_id: str,
    request: GenerationRequest = GenerationRequest(),
    background_tasks: BackgroundTasks = None,
    db: Session = Depends(get_session),
) -> GenerationResponse:
    """
    Generate learning atoms for a single CCNA module.

    This runs the full pipeline:
    1. Parse module content
    2. Generate atoms (flashcards, MCQ, cloze, Parsons)
    3. QA grade all atoms
    4. Migrate learning state (if enabled)
    5. Save to database (unless dry_run)

    **Note**: This may take several minutes for large modules.
    """
    from src.ccna.content_parser import CCNAContentParser
    from src.ccna.generation_pipeline import CCNAGenerationPipeline

    settings = get_settings()
    parser = CCNAContentParser(settings.ccna_modules_path)

    # Find module path
    module_path = None
    for path in parser.get_available_modules():
        if parser._extract_module_number(path.stem) == int(module_id.replace("NET-M", "")):
            module_path = path
            break

    if not module_path:
        raise HTTPException(status_code=404, detail=f"Module {module_id} not found")

    try:
        pipeline = CCNAGenerationPipeline(db_session=db)
        result = await pipeline.process_module(
            module_path,
            preserve_good_cards=request.preserve_good_cards,
            include_migration=request.include_migration,
            dry_run=request.dry_run,
        )

        return GenerationResponse(
            job_id=result.job_id,
            module_id=result.module_id,
            status=result.status,
            atoms_generated=result.atoms_generated,
            atoms_passed_qa=result.atoms_passed_qa,
            atoms_flagged=result.atoms_flagged,
            atoms_rejected=result.atoms_rejected,
            avg_quality_score=result.avg_quality_score,
            grade_distribution=result.grade_distribution,
            errors=result.errors,
        )

    except Exception as e:
        logger.exception(f"Generation failed for {module_id}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/generate/all", summary="Generate content for all modules")
async def generate_all_modules(
    request: GenerationRequest = GenerationRequest(),
    priority_modules: Optional[str] = Query(
        None,
        description="Comma-separated module numbers to process first (e.g., '7,9,10,15,16')"
    ),
    db: Session = Depends(get_session),
) -> Dict[str, Any]:
    """
    Generate learning atoms for all CCNA modules.

    **Warning**: This is a long-running operation that may take 30+ minutes.

    Optional: Specify priority_modules to process certain modules first
    (e.g., modules with known quality issues).
    """
    from src.ccna.generation_pipeline import CCNAGenerationPipeline

    # Parse priority modules
    priority = None
    if priority_modules:
        try:
            priority = [int(m.strip()) for m in priority_modules.split(",")]
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail="priority_modules must be comma-separated integers"
            )

    try:
        pipeline = CCNAGenerationPipeline(db_session=db)
        report = await pipeline.process_all_modules(
            priority_modules=priority,
            dry_run=request.dry_run,
        )

        return {
            "total_modules": report.total_modules,
            "modules_completed": report.modules_completed,
            "modules_failed": report.modules_failed,
            "total_atoms_generated": report.total_atoms_generated,
            "total_atoms_approved": report.total_atoms_approved,
            "overall_pass_rate": report.overall_pass_rate,
            "started_at": report.started_at.isoformat(),
            "completed_at": report.completed_at.isoformat() if report.completed_at else None,
            "module_summaries": [r.to_dict() for r in report.module_results],
        }

    except Exception as e:
        logger.exception("Full generation failed")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/generate/status/{job_id}", summary="Get generation job status")
def get_job_status(
    job_id: str,
    db: Session = Depends(get_session),
) -> Dict[str, Any]:
    """Get the status of a generation job."""
    from sqlalchemy import text

    query = text("""
        SELECT * FROM ccna_generation_jobs
        WHERE id = :job_id::uuid
    """)

    result = db.execute(query, {"job_id": job_id}).first()

    if not result:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")

    return dict(result._mapping)


# ============================================================================
# Quality Assurance Endpoints
# ============================================================================


@router.get("/qa/report", response_model=List[QAReportResponse], summary="Get overall QA report")
def get_qa_report(db: Session = Depends(get_session)) -> List[QAReportResponse]:
    """
    Get quality assurance report for all modules.

    Shows quality grade distribution and common issues.
    """
    from sqlalchemy import text

    query = text("""
        SELECT
            module_id,
            actual_atoms as total_atoms,
            grade_a_count + grade_b_count as passed,
            grade_c_count as flagged,
            grade_d_count + grade_f_count as rejected,
            grade_a_count, grade_b_count, grade_c_count,
            grade_d_count, grade_f_count,
            avg_quality_score
        FROM ccna_module_coverage
        ORDER BY module_id
    """)

    results = []
    for row in db.execute(query):
        results.append(QAReportResponse(
            module_id=row.module_id,
            total_atoms=row.total_atoms or 0,
            passed=row.passed or 0,
            flagged=row.flagged or 0,
            rejected=row.rejected or 0,
            grade_distribution={
                "A": row.grade_a_count or 0,
                "B": row.grade_b_count or 0,
                "C": row.grade_c_count or 0,
                "D": row.grade_d_count or 0,
                "F": row.grade_f_count or 0,
            },
            avg_quality_score=float(row.avg_quality_score or 0),
            issues_summary={},  # Would need additional query
        ))

    return results


@router.get("/qa/report/{module_id}", summary="Get module QA report")
def get_module_qa_report(
    module_id: str,
    db: Session = Depends(get_session),
) -> Dict[str, Any]:
    """Get detailed QA report for a specific module."""
    from sqlalchemy import text

    # Get module stats
    stats_query = text("""
        SELECT * FROM ccna_module_quality_summary
        WHERE module_id = :module_id
    """)

    stats = db.execute(stats_query, {"module_id": module_id}).first()
    if not stats:
        raise HTTPException(status_code=404, detail=f"No QA data for {module_id}")

    # Get atom-level issues
    issues_query = text("""
        SELECT
            quality_grade,
            COUNT(*) as count,
            AVG(quality_score) as avg_score
        FROM ccna_generated_atoms
        WHERE module_id = :module_id
        GROUP BY quality_grade
        ORDER BY quality_grade
    """)

    grade_breakdown = {
        row.quality_grade: {
            "count": row.count,
            "avg_score": float(row.avg_score) if row.avg_score else 0,
        }
        for row in db.execute(issues_query, {"module_id": module_id})
    }

    # Get flagged atoms
    flagged_query = text("""
        SELECT card_id, front, quality_grade, quality_score, quality_details
        FROM ccna_generated_atoms
        WHERE module_id = :module_id
        AND needs_review = true
        ORDER BY quality_score
        LIMIT 20
    """)

    flagged = [
        {
            "card_id": row.card_id,
            "front": row.front[:100],
            "grade": row.quality_grade,
            "score": float(row.quality_score) if row.quality_score else 0,
        }
        for row in db.execute(flagged_query, {"module_id": module_id})
    ]

    return {
        "module_id": module_id,
        "summary": dict(stats._mapping),
        "grade_breakdown": grade_breakdown,
        "flagged_atoms": flagged,
    }


@router.post("/qa/regrade", summary="Re-grade all cards")
async def regrade_all_cards(
    module_id: Optional[str] = Query(None, description="Limit to specific module"),
    db: Session = Depends(get_session),
) -> Dict[str, Any]:
    """
    Re-grade all generated atoms using the QA pipeline.

    Useful after QA algorithm updates.
    """
    from src.ccna.qa_pipeline import QAPipeline
    from src.ccna.atomizer_service import AtomType, GeneratedAtom, KnowledgeType
    from sqlalchemy import text

    qa_pipeline = QAPipeline()

    # Fetch atoms
    query = text("""
        SELECT card_id, atom_type, front, back, knowledge_type, tags
        FROM ccna_generated_atoms
        WHERE (:module_id IS NULL OR module_id = :module_id)
    """)

    atoms = []
    for row in db.execute(query, {"module_id": module_id}):
        try:
            atoms.append(GeneratedAtom(
                card_id=row.card_id,
                atom_type=AtomType(row.atom_type),
                front=row.front,
                back=row.back,
                knowledge_type=KnowledgeType(row.knowledge_type),
                tags=row.tags or [],
            ))
        except Exception as e:
            logger.warning(f"Skipping atom {row.card_id}: {e}")

    if not atoms:
        return {"message": "No atoms to regrade", "count": 0}

    # Re-grade
    report = qa_pipeline.batch_qa(atoms)

    # Update database
    for qa_result in report.results:
        update_query = text("""
            UPDATE ccna_generated_atoms
            SET quality_grade = :grade,
                quality_score = :score,
                is_atomic = :is_atomic,
                needs_review = :needs_review,
                last_qa_at = NOW()
            WHERE card_id = :card_id
        """)

        db.execute(update_query, {
            "card_id": qa_result.atom.card_id,
            "grade": qa_result.quality_grade,
            "score": qa_result.quality_score,
            "is_atomic": qa_result.is_atomic,
            "needs_review": qa_result.needs_review,
        })

    db.commit()

    return {
        "message": "Regrade complete",
        "total_processed": report.total_processed,
        "passed": report.passed,
        "flagged": report.flagged,
        "rejected": report.rejected,
        "grade_distribution": report.grade_distribution,
    }


@router.get("/qa/flagged", summary="Get flagged atoms")
def get_flagged_atoms(
    module_id: Optional[str] = Query(None),
    limit: int = Query(50, le=200),
    db: Session = Depends(get_session),
) -> List[Dict[str, Any]]:
    """Get atoms flagged for manual review."""
    from sqlalchemy import text

    query = text("""
        SELECT card_id, module_id, atom_type, front, back,
               quality_grade, quality_score, quality_details
        FROM ccna_generated_atoms
        WHERE needs_review = true
        AND (:module_id IS NULL OR module_id = :module_id)
        ORDER BY quality_score
        LIMIT :limit
    """)

    return [
        dict(row._mapping)
        for row in db.execute(query, {"module_id": module_id, "limit": limit})
    ]


# ============================================================================
# Migration Endpoints
# ============================================================================


@router.post("/migrate/export", summary="Export Anki learning state")
async def export_anki_state(
    module_id: Optional[str] = Query(None, description="Limit to specific module"),
    db: Session = Depends(get_session),
) -> Dict[str, Any]:
    """
    Export current learning state from Anki cards.

    Backs up FSRS state for potential migration to regenerated cards.
    """
    from src.ccna.anki_migration import AnkiMigrationService
    from sqlalchemy import text

    migration_service = AnkiMigrationService()

    try:
        states = await migration_service.export_learning_states(module_id=module_id)

        # Save to backup table
        for state in states:
            if state.has_learning_progress:
                query = text("""
                    INSERT INTO anki_learning_state_backup (
                        card_id, anki_nid, stability, difficulty,
                        due_date, interval_days, ease_factor,
                        total_reviews, total_lapses, last_review_date,
                        front_text, back_text, tags, backup_reason
                    ) VALUES (
                        :card_id, :anki_nid, :stability, :difficulty,
                        :due_date, :interval, :ease,
                        :reviews, :lapses, :last_review,
                        :front, :back, :tags, 'export'
                    )
                """)

                db.execute(query, {
                    "card_id": state.card_id,
                    "anki_nid": state.anki_note_id,
                    "stability": state.stability,
                    "difficulty": state.difficulty,
                    "due_date": state.due_date,
                    "interval": state.interval_days,
                    "ease": state.ease_factor,
                    "reviews": state.total_reviews,
                    "lapses": state.total_lapses,
                    "last_review": state.last_review,
                    "front": state.front_text[:500],
                    "back": state.back_text[:500],
                    "tags": state.tags,
                })

        db.commit()

        with_progress = [s for s in states if s.has_learning_progress]
        mature = [s for s in states if s.is_mature]

        return {
            "total_exported": len(states),
            "with_learning_progress": len(with_progress),
            "mature_cards": len(mature),
            "module_id": module_id,
        }

    except Exception as e:
        logger.exception("Export failed")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/migrate/report", summary="Get migration report")
def get_migration_report(
    db: Session = Depends(get_session),
) -> Dict[str, Any]:
    """Get summary of card migrations."""
    from sqlalchemy import text

    query = text("""
        SELECT
            COUNT(*) as total_migrations,
            COUNT(*) FILTER (WHERE state_transferred) as successful,
            COUNT(*) FILTER (WHERE NOT state_transferred) as failed,
            AVG(similarity_score) as avg_similarity
        FROM anki_card_migrations
    """)

    result = db.execute(query).first()

    return {
        "total_migrations": result.total_migrations or 0,
        "successful": result.successful or 0,
        "failed": result.failed or 0,
        "avg_similarity": float(result.avg_similarity) if result.avg_similarity else 0,
    }
