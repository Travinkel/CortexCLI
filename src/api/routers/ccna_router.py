"""
CCNA Generation API Router.

Provides REST API endpoints for:
- Content analysis and coverage tracking
- Atom generation (full pipeline or by type)
- Quality assurance and regrading
- Anki learning state migration
"""

from __future__ import annotations

from pathlib import Path
import re
import yaml
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from loguru import logger
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from config import get_settings
from src.db.database import get_session
from src.delivery.atom_deck import AtomDeck
from src.adaptive.path_sequencer import PathSequencer
from src.db.models.adaptive import LearningPathSession, SessionAtomResponse, RemediationEvent
from src.db.models.canonical import CleanAtom, CleanConcept
from datetime import datetime, timedelta
from uuid import UUID

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
    last_generated_at: str | None = None


class GenerationRequest(BaseModel):
    """Request model for generation endpoint."""

    preserve_good_cards: bool = Field(
        True, description="Keep Grade A/B cards instead of regenerating"
    )
    include_migration: bool = Field(
        True, description="Attempt to migrate learning state from replaced cards"
    )
    dry_run: bool = Field(False, description="Preview without saving to database")


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
    grade_distribution: dict[str, int]
    errors: list[str] = Field(default_factory=list)


class QAReportResponse(BaseModel):
    """Response model for QA report."""

    module_id: str
    total_atoms: int
    passed: int
    flagged: int
    rejected: int
    grade_distribution: dict[str, int]
    avg_quality_score: float
    issues_summary: dict[str, int]


class MigrationResponse(BaseModel):
    """Response model for migration operations."""

    total_old_cards: int
    total_new_cards: int
    matched: int
    unmatched_old: int
    transfers_successful: int
    transfers_failed: int


class NeighborAtom(BaseModel):
    """Lightweight atom representation used for neighbor/cluster lookups."""

    atom_id: str
    atom_type: str | None = None
    difficulty: int | None = None
    concept_id: str | None = None
    front_preview: str | None = None


class ObjectiveNeighborsResponse(BaseModel):
    """Neighbor atoms for a concept/objective."""

    concept_id: str
    neighbors: list[NeighborAtom] = Field(default_factory=list)


class ObjectiveClusterResponse(BaseModel):
    """Cluster context for an objective with sample members."""

    concept_id: str
    concept_name: str | None = None
    cluster_id: str | None = None
    cluster_name: str | None = None
    members: list[NeighborAtom] = Field(default_factory=list)


# ============================================================================
# Content Analysis Endpoints
# ============================================================================


@router.get("/modules", response_model=list[ModuleSummary], summary="List available modules")
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
            summaries.append(
                ModuleSummary(
                    module_id=summary["module_id"],
                    module_number=summary["module_number"],
                    title=summary["title"],
                    total_lines=summary["total_lines"],
                    section_count=summary["section_count"],
                    total_commands=summary["total_commands"],
                    total_tables=summary["total_tables"],
                    total_key_terms=summary["total_key_terms"],
                    estimated_atoms=summary["estimated_atoms"],
                )
            )
        except Exception as e:
            logger.error(f"Failed to parse {module_path}: {e}")

    return summaries


@router.get("/modules/{module_id}", summary="Get module details")
def get_module_details(module_id: str) -> dict[str, Any]:
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
    "/modules/{module_id}/coverage", response_model=ModuleCoverage, summary="Get module coverage"
)
def get_module_coverage(module_id: str, db: Session = Depends(get_session)) -> ModuleCoverage:
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
        raise HTTPException(status_code=404, detail=f"No coverage data for module {module_id}")

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
def get_module_gaps(module_id: str, db: Session = Depends(get_session)) -> dict[str, Any]:
    """
    Identify gaps in module coverage.

    Returns:
    - Sections without atoms
    - Low-quality sections (high F rate)
    - Recommended actions
    """
    from sqlalchemy import text

    from src.ccna.content_parser import CCNAContentParser

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
            missing_sections.append(
                {
                    "section_id": section.id,
                    "title": section.title,
                    "estimated_atoms": expected,
                }
            )
        elif expected > 0 and (generated / expected) < 0.5:
            low_coverage_sections.append(
                {
                    "section_id": section.id,
                    "title": section.title,
                    "generated": generated,
                    "estimated": expected,
                    "coverage": round(generated / expected * 100, 1),
                }
            )

    return {
        "module_id": module_id,
        "total_sections": module.section_count,
        "missing_sections": missing_sections,
        "low_coverage_sections": low_coverage_sections,
        "recommendations": [
            f"Generate content for {len(missing_sections)} missing sections",
            f"Improve {len(low_coverage_sections)} low-coverage sections",
        ]
        if missing_sections or low_coverage_sections
        else ["Module coverage is adequate"],
    }


# ============================================================================
# Generation Endpoints
# ============================================================================


@router.post(
    "/generate/{module_id}",
    response_model=GenerationResponse,
    summary="Generate content for module",
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
    priority_modules: str | None = Query(
        None, description="Comma-separated module numbers to process first (e.g., '7,9,10,15,16')"
    ),
    db: Session = Depends(get_session),
) -> dict[str, Any]:
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
                status_code=400, detail="priority_modules must be comma-separated integers"
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
) -> dict[str, Any]:
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


@router.get("/qa/report", response_model=list[QAReportResponse], summary="Get overall QA report")
def get_qa_report(db: Session = Depends(get_session)) -> list[QAReportResponse]:
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
        results.append(
            QAReportResponse(
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
            )
        )

    return results


@router.get("/qa/report/{module_id}", summary="Get module QA report")
def get_module_qa_report(
    module_id: str,
    db: Session = Depends(get_session),
) -> dict[str, Any]:
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
    module_id: str | None = Query(None, description="Limit to specific module"),
    db: Session = Depends(get_session),
) -> dict[str, Any]:
    """
    Re-grade all generated atoms using the QA pipeline.

    Useful after QA algorithm updates.
    """
    from sqlalchemy import text

    from src.ccna.atomizer_service import AtomType, GeneratedAtom, KnowledgeType
    from src.ccna.qa_pipeline import QAPipeline

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
            atoms.append(
                GeneratedAtom(
                    card_id=row.card_id,
                    atom_type=AtomType(row.atom_type),
                    front=row.front,
                    back=row.back,
                    knowledge_type=KnowledgeType(row.knowledge_type),
                    tags=row.tags or [],
                )
            )
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

        db.execute(
            update_query,
            {
                "card_id": qa_result.atom.card_id,
                "grade": qa_result.quality_grade,
                "score": qa_result.quality_score,
                "is_atomic": qa_result.is_atomic,
                "needs_review": qa_result.needs_review,
            },
        )

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
    module_id: str | None = Query(None),
    limit: int = Query(50, le=200),
    db: Session = Depends(get_session),
) -> list[dict[str, Any]]:
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
        dict(row._mapping) for row in db.execute(query, {"module_id": module_id, "limit": limit})
    ]


# ============================================================================
# Migration Endpoints
# ============================================================================


@router.post("/migrate/export", summary="Export Anki learning state")
async def export_anki_state(
    module_id: str | None = Query(None, description="Limit to specific module"),
    db: Session = Depends(get_session),
) -> dict[str, Any]:
    """
    Export current learning state from Anki cards.

    Backs up FSRS state for potential migration to regenerated cards.
    """
    from sqlalchemy import text

    from src.ccna.anki_migration import AnkiMigrationService

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

                db.execute(
                    query,
                    {
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
                    },
                )

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
) -> dict[str, Any]:
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


# ============================================================================
# Study Loop Endpoints (learn mode)
# ============================================================================

class StudyAtomPayload(BaseModel):
    """UI-ready payload for study atoms."""

    id: str
    atom_type: str
    front: str
    back: str
    hints: list[str] = Field(default_factory=list)
    explanation: str | None = None
    keyboard_hints: list[str] = Field(default_factory=list)
    aria_role: str | None = None
    aria_label: str | None = None
    source_ref: dict[str, Any] | None = None
    prerequisites: list[str] = Field(default_factory=list)
    difficulty: int | None = None


class AttemptRequest(BaseModel):
    """Attempt submission payload."""

    atom_id: str
    correct: bool
    hint_used: bool = False
    time_ms: int | None = None


class ProgressResponse(BaseModel):
    """Progress summary response."""

    total_attempts: int
    mastered_atoms: int
    accuracy: float
    struggle_objectives: list[str] = Field(default_factory=list)


_STUDY_OUTCOMES: dict[str, list[dict[str, Any]]] = {}
_MASTERED: set[str] = set()
_TELEMETRY_DIR = Path("data") / "telemetry"
# spaced repetition queue: list of {"atom_id": str, "due_at": datetime}
_REVIEW_QUEUE: list[dict[str, Any]] = []
_SEQUENCER = PathSequencer(session=None)
# Struggle map cache (atom_id -> incorrect count)
_STRUGGLE_CACHE: dict[str, int] = {}
# In-memory session cache for demo purposes (learner_id -> session_id)
_SESSION_CACHE: dict[str, UUID] = {}


def _preview_text(text_value: str | None, limit: int = 120) -> str:
    """Compact a prompt/front for accessibility labels."""
    if not text_value:
        return ""
    cleaned = re.sub(r"\s+", " ", text_value).strip()
    if len(cleaned) > limit:
        return cleaned[: limit - 3] + "..."
    return cleaned


def _build_accessibility(atom_type: str, prompt: str | None = None) -> tuple[list[str], str, str]:
    """
    Derive keyboard hints, aria_role, and aria_label per atom type.

    Keeps hints consistent across DB-backed and JSON-backed decks.
    """
    normalized = (atom_type or "flashcard").lower()
    prompt_preview = _preview_text(prompt)

    keyboard_map = {
        "mcq": [
            "Tab/Arrow keys to navigate options",
            "1..4 or A-D to choose an option",
            "Enter or Space to submit",
        ],
        "true_false": [
            "Tab/Arrow keys to navigate options",
            "1/2 or Left/Right arrows to choose true vs false",
            "Enter or Space to submit",
        ],
        "numeric": [
            "Type your answer, then press Enter to submit",
            "Tab to focus the input field",
        ],
        "ordering": [
            "Tab or Arrow keys to move between items",
            "Ctrl/Cmd+Up/Down to reorder the focused item",
            "Enter to confirm order",
        ],
        "labeling": [
            "Tab/Shift+Tab to move between targets",
            "Space or Enter to place the selected label",
        ],
        "hotspot": [
            "Tab through hotspots",
            "Space/Enter to activate the focused hotspot",
        ],
        "case_scenario": [
            "Number keys to pick a response",
            "Enter to submit",
            "Tab to review scenario text",
        ],
        "parsons": [
            "Arrow keys to select a line",
            "Ctrl/Cmd+Up/Down to move the line",
            "Enter to submit order",
        ],
        "matching": [
            "Tab between pairs",
            "Arrow keys to choose an answer for the focused prompt",
            "Enter to lock in the pair",
        ],
    }

    aria_roles = {
        "mcq": "radiogroup",
        "true_false": "radiogroup",
        "ordering": "list",
        "parsons": "list",
        "matching": "list",
        "labeling": "group",
        "hotspot": "group",
        "case_scenario": "article",
    }

    keyboard_hints = keyboard_map.get(
        normalized,
        [
            "Tab to move focus through the prompt",
            "Enter or Space to reveal the answer or submit",
        ],
    )
    aria_role = aria_roles.get(normalized, "article")
    aria_label = f"{normalized} prompt: {prompt_preview}" if prompt_preview else f"{normalized} atom"

    return keyboard_hints, aria_role, aria_label


def _emit_event(event_type: str, payload: dict[str, Any]) -> None:
    """Emit a telemetry event to JSONL without failing the request."""
    try:
        _TELEMETRY_DIR.mkdir(parents=True, exist_ok=True)
        out_path = _TELEMETRY_DIR / f"{event_type}.jsonl"
        with out_path.open("a", encoding="utf-8") as f:
            f.write(f"{payload}\n")
        # Track struggle counts for quick hotspots (incorrect attempts)
        if event_type == "attempt_submitted" and payload.get("correct") is False:
            atom_id = payload.get("atom_id")
            if atom_id:
                _STRUGGLE_CACHE[atom_id] = _STRUGGLE_CACHE.get(atom_id, 0) + 1
    except Exception as exc:  # pragma: no cover
        logger.debug(f"Telemetry emit skipped: {exc}")


def _load_learnable_deck(session: Session | None = None) -> list[dict[str, Any]]:
    """Load a learnable-ready deck; prefers DB rows, falls back to JSON deck."""
    if session:
        try:
            rows = session.execute(
                text(
                    """
                    SELECT id, atom_type, front, back, quality_score,
                           concept_id, quiz_question_metadata, difficulty
                    FROM learning_atoms
                    WHERE front IS NOT NULL AND back IS NOT NULL
                      AND (quality_score IS NULL OR quality_score >= 70)
                    LIMIT 200
                    """
                )
            ).mappings().all()
            serialized: list[dict[str, Any]] = []
            for row in rows:
                cq = row.quiz_question_metadata or {}
                content_json = cq.get("content_json") if isinstance(cq, dict) else {}
                hints = (content_json or {}).get("hints") or []
                explanation = (content_json or {}).get("explanation") or cq.get("explanation")
                prerequisites = (content_json or {}).get("prerequisites") or cq.get("prerequisites") or []
                # Enforce learnability gate: difficulty >=3 requires explanation
                if getattr(row, "difficulty", None) is not None:
                    try:
                        if int(row.difficulty) >= 3 and not explanation:
                            continue
                    except (ValueError, TypeError):
                        pass  # Non-numeric difficulty
                # Attach source reference if present
                source_ref = (content_json or {}).get("source_ref") or cq.get("source_ref")
                keyboard_override = (cq or {}).get("keyboard_hints") or (content_json or {}).get(
                    "keyboard_hints"
                )
                aria_role_override = (cq or {}).get("aria_role") or (content_json or {}).get(
                    "aria_role"
                )
                aria_label_override = (cq or {}).get("aria_label") or (content_json or {}).get(
                    "aria_label"
                )
                keyboard_hints, aria_role, aria_label = _build_accessibility(
                    row.atom_type, row.front
                )
                if keyboard_override:
                    keyboard_hints = keyboard_override
                if aria_role_override:
                    aria_role = aria_role_override
                if aria_label_override:
                    aria_label = aria_label_override
                serialized.append(
                    {
                        "id": str(row.id),
                        "atom_type": row.atom_type,
                        "front": row.front,
                        "back": row.back or "",
                        "hints": hints,
                        "explanation": explanation,
                        "keyboard_hints": keyboard_hints,
                        "aria_role": aria_role,
                        "aria_label": aria_label,
                        "source_ref": source_ref,
                        "prerequisites": prerequisites,
                        "difficulty": int(row.difficulty) if getattr(row, "difficulty", None) else None,
                        "concept_id": str(row.concept_id) if row.concept_id else None,
                    }
                )
            if serialized:
                return serialized
        except Exception as exc:
            logger.debug(f"DB deck load failed, falling back to JSON: {exc}")

    # Fallback to JSON deck on disk
    deck = AtomDeck()
    deck.load()
    ready = deck.filter_learnable_ready(min_quality=0)
    serialized: list[dict[str, Any]] = []
    for atom in ready:
        keyboard_override = None
        aria_role_override = None
        aria_label_override = None
        if atom.content_json:
            keyboard_override = atom.content_json.get("keyboard_hints")
            aria_role_override = atom.content_json.get("aria_role")
            aria_label_override = atom.content_json.get("aria_label")
        keyboard_hints, aria_role, aria_label = _build_accessibility(atom.atom_type, atom.front)
        if keyboard_override:
            keyboard_hints = keyboard_override
        if aria_role_override:
            aria_role = aria_role_override
        if aria_label_override:
            aria_label = aria_label_override
        source_ref = atom.source_refs[0] if atom.source_refs else None
        hints = atom.hints if atom.hints else []
        if not hints and atom.content_json:
            hints = atom.content_json.get("hints") or []
        explanation = atom.explanation
        if explanation is None and atom.content_json:
            explanation = atom.content_json.get("explanation")

        serialized.append(
            {
                "id": atom.id,
                "atom_type": atom.atom_type,
                "front": atom.front,
                "back": atom.back,
                "hints": hints,
                "explanation": explanation,
                "keyboard_hints": keyboard_hints,
                "aria_role": aria_role,
                "aria_label": aria_label,
                "source_ref": source_ref,
                "prerequisites": atom.prerequisites,
                "difficulty": atom.difficulty,
                "concept_id": None,
            }
        )
    return serialized


def _build_prereq_map(atoms: list[dict[str, Any]], session: Session | None = None) -> dict[str, list[str]]:
    """Create map atom_id -> prerequisite concept ids."""
    prereq_map: dict[str, list[str]] = {}
    for atom in atoms:
        prereqs = atom.get("prerequisites") or []
        if prereqs:
            prereq_map[atom["id"]] = prereqs
    if session:
        try:
            rows = session.execute(
                text(
                    """
                    SELECT source_atom_id::text as atom_id, target_concept_id::text as prereq_concept
                    FROM explicit_prerequisites
                    WHERE source_atom_id IS NOT NULL AND status = 'active'
                    """
                )
            ).mappings()
            for row in rows:
                if row.atom_id not in prereq_map:
                    prereq_map[row.atom_id] = []
                prereq_map[row.atom_id].append(row.prereq_concept)
        except Exception as exc:  # pragma: no cover
            logger.debug(f"Prereq map fallback: {exc}")
    return prereq_map


def _build_mastered_set(session: Session | None = None, learner_id: str = "ccna-user") -> set[str]:
    """Return mastered concepts/atoms recorded so far."""
    mastered_atoms = set(_MASTERED)
    if session:
        try:
            rows = session.execute(
                text(
                    """
                    SELECT concept_id FROM learner_mastery_state
                    WHERE learner_id = :learner_id AND combined_mastery >= 0.65
                    """
                ),
                {"learner_id": learner_id},
            ).scalars()
            mastered_atoms.update({str(cid) for cid in rows if cid})
        except Exception as exc:  # pragma: no cover
            logger.debug(f"Mastered set fallback: {exc}")
    return mastered_atoms


def _due_review_ids(now: datetime) -> list[str]:
    """Return due review atom ids and consume them from the queue."""
    due: list[str] = []
    remaining: list[dict[str, Any]] = []
    for item in _REVIEW_QUEUE:
        if item.get("due_at") and item["due_at"] <= now:
            due.append(item["atom_id"])
        else:
            remaining.append(item)
    _REVIEW_QUEUE[:] = remaining
    return due


def _schedule_reviews(atom_id: str) -> None:
    """Schedule spaced reviews at 10/24/48h."""
    now = datetime.utcnow()
    for hours in (10, 24, 48):
        _REVIEW_QUEUE.append({"atom_id": atom_id, "due_at": now + timedelta(hours=hours)})


def _touch_spaced_review(db: Session, atom_id: str) -> None:
    """Persist earliest spaced review due date to learning_atoms.anki_due_date."""
    try:
        db.execute(
            text(
                """
                UPDATE learning_atoms
                SET anki_due_date = :due_date
                WHERE id = :atom_id::uuid
                """
            ),
            {"atom_id": atom_id, "due_date": datetime.utcnow() + timedelta(hours=10)},
        )
        db.commit()
    except Exception as exc:  # pragma: no cover
        logger.debug(f"Spaced review persist skipped: {exc}")


def _build_remediation_bundle(db: Session, atom_id: str) -> dict[str, Any]:
    """Return remediation bundle for an atom, reusing remediation endpoint logic."""
    atoms = _load_learnable_deck(session=db)
    target = next((a for a in atoms if a["id"] == atom_id), atoms[0] if atoms else None)
    if not target:
        return {}
    bundle = {
        "atom_id": target["id"],
        "hints": target.get("hints", []),
        "explanation": target.get("explanation"),
        "source_ref": target.get("source_ref"),
        "keyboard_hints": target.get("keyboard_hints", []),
        "aria_role": target.get("aria_role"),
        "aria_label": target.get("aria_label"),
    }
    if target.get("concept_id"):
        try:
            from src.semantic.similarity_service import get_easier_neighbors

            neighbors = get_easier_neighbors(
                db_session=db,
                concept_id=UUID(str(target["concept_id"])),
                limit=2,
                difficulty_band=2,
            )
            bundle["neighbors"] = [str(n) for n in neighbors]
            _record_remediation_event(
                db=db,
                learner_id="ccna-user",
                concept_id=str(target["concept_id"]),
                trigger_atom_id=atom_id,
                remediation_atoms=bundle.get("neighbors"),
            )
        except Exception as exc:  # pragma: no cover
            logger.debug(f"Neighbor fetch skipped: {exc}")
    _emit_event("remediation_offered", {"atom_id": bundle["atom_id"]})
    return bundle


def _ensure_session(db: Session, learner_id: str, concept_id: str | None = None) -> UUID | None:
    """Get or create an active LearningPathSession for a learner."""
    try:
        if learner_id in _SESSION_CACHE:
            return _SESSION_CACHE[learner_id]

        # Try to find an active session
        query = text(
            """
            SELECT id FROM learning_path_sessions
            WHERE learner_id = :learner_id AND status = 'active'
            ORDER BY started_at DESC LIMIT 1
            """
        )
        row = db.execute(query, {"learner_id": learner_id}).fetchone()
        if row and getattr(row, "id", None):
            _SESSION_CACHE[learner_id] = row.id
            return row.id

        # Create a new session
        insert = text(
            """
            INSERT INTO learning_path_sessions (learner_id, target_concept_id, status)
            VALUES (:learner_id, :concept_id, 'active')
            RETURNING id
            """
        )
        res = db.execute(insert, {"learner_id": learner_id, "concept_id": concept_id})
        new_id = res.scalar()
        db.commit()
        if new_id:
            _SESSION_CACHE[learner_id] = new_id
        return new_id
    except Exception as exc:  # pragma: no cover
        logger.debug(f"Session ensure skipped: {exc}")
        return None


def _record_response(
    db: Session,
    learner_id: str,
    atom_id: str,
    concept_id: str | None,
    correct: bool,
    hint_used: bool,
    time_ms: int | None,
    was_remediation: bool = False,
) -> None:
    """Persist SessionAtomResponse and a lightweight mastery update."""
    session_id = _ensure_session(db, learner_id, concept_id)
    try:
        db.add(
            SessionAtomResponse(
                session_id=session_id,
                atom_id=UUID(atom_id),
                is_correct=correct,
                was_remediation=was_remediation,
                time_spent_ms=time_ms,
                hint_level_used=1 if hint_used else 0,
            )
        )
        db.commit()
    except Exception as exc:  # pragma: no cover
        logger.debug(f"Response persist skipped: {exc}")
        db.rollback()

    # Naive mastery update
    try:
        if not concept_id:
            return
        delta = 0.1 if correct else -0.05
        update = text(
            """
            INSERT INTO learner_mastery_state (learner_id, concept_id, combined_mastery, review_count, last_review_at, is_unlocked)
            VALUES (:learner_id, :concept_id, :combined, 1, now(), true)
            ON CONFLICT (learner_id, concept_id) DO UPDATE
            SET combined_mastery = LEAST(1.0, GREATEST(0, learner_mastery_state.combined_mastery + :delta)),
                review_count = learner_mastery_state.review_count + 1,
                last_review_at = now(),
                is_unlocked = true
            RETURNING combined_mastery
            """
        )
        db.execute(
            update,
            {
                "learner_id": learner_id,
                "concept_id": concept_id,
                "combined": max(0, min(1, 0.5 + delta)),
                "delta": delta,
            },
        )
        db.commit()
    except Exception as exc:  # pragma: no cover
        logger.debug(f"Mastery update skipped: {exc}")
        db.rollback()


def _record_remediation_event(
    db: Session,
    learner_id: str,
    concept_id: str | None,
    trigger_atom_id: str | None,
    remediation_atoms: list[str] | None,
) -> None:
    """Persist a remediation event for audit."""
    if not concept_id or not remediation_atoms:
        return
    try:
        session_id = _ensure_session(db, learner_id, concept_id)
        db.add(
            RemediationEvent(
                session_id=session_id,
                learner_id=learner_id,
                trigger_atom_id=UUID(trigger_atom_id) if trigger_atom_id else None,
                trigger_concept_id=UUID(concept_id),
                trigger_type="incorrect_answer",
                gap_concept_id=UUID(concept_id),
                remediation_atoms=[UUID(r) for r in remediation_atoms],
                remediation_concept_ids=[UUID(concept_id)],
                mastery_at_trigger=None,
                required_mastery=None,
                mastery_gap=None,
            )
        )
        db.commit()
    except Exception as exc:  # pragma: no cover
        logger.debug(f"Remediation persist skipped: {exc}")
        db.rollback()


@router.get(
    "/ccna/next",
    response_model=StudyAtomPayload,
    summary="Get next CCNA atom",
)
def get_next_ccna_atom(
    concept_id: str | None = Query(None, description="Optional concept scope"),
    db: Session = Depends(get_session),
) -> StudyAtomPayload:
    """Return the next learnable-ready atom with accessibility metadata."""
    atoms = _load_learnable_deck(session=db)
    if not atoms:
        raise HTTPException(status_code=404, detail="No learnable-ready atoms available")

    prereq_map = _build_prereq_map(atoms, session=db)
    mastered = _build_mastered_set(session=db)
    now = datetime.utcnow()
    due_reviews = _due_review_ids(now)
    # Build recent outcomes placeholder per atom if needed
    next_ids = _SEQUENCER.get_next_atoms(
        learner_id="ccna-user",
        count=5,
        include_review=True,
        recent_outcomes=[],
        mastered_atoms=mastered,
        atom_prerequisites=prereq_map,
        due_review_queue=due_reviews,
        require_mastered_prereqs=True,
        concept_id=UUID(concept_id) if concept_id else None,
    )
    chosen_id = next_ids[0] if next_ids else atoms[0]["id"]
    chosen = next((a for a in atoms if a["id"] == chosen_id), atoms[0])
    _emit_event("atom_shown", {"atom_id": chosen["id"], "type": chosen["atom_type"]})
    return StudyAtomPayload(**chosen)


@router.post("/ccna/attempt", summary="Submit an attempt on an atom")
def submit_ccna_attempt(req: AttemptRequest) -> dict[str, Any]:
    """Record an attempt and compute mastery status."""
    outcomes = _STUDY_OUTCOMES.setdefault(req.atom_id, [])
    outcomes.append({"correct": req.correct, "hint_used": req.hint_used})
    mastered = PathSequencer.compute_mastery_decision(outcomes)
    remediation: dict[str, Any] | None = None
    if mastered:
        _MASTERED.add(req.atom_id)
        _schedule_reviews(req.atom_id)
        try:
            with next(get_session()) as db:
                _touch_spaced_review(db, req.atom_id)
        except SQLAlchemyError:
            pass  # DB error updating spaced review
    elif PathSequencer.needs_remediation(outcomes):
        try:
            with next(get_session()) as db:
                remediation = _build_remediation_bundle(db, req.atom_id)
        except SQLAlchemyError:  # pragma: no cover
            remediation = {"note": "remediation unavailable"}

    _emit_event(
        "attempt_submitted",
        {
            "atom_id": req.atom_id,
            "correct": req.correct,
            "hint_used": req.hint_used,
            "mastered": mastered,
            "time_ms": req.time_ms,
        },
    )
    try:
        with next(get_session()) as db:
            # Attempt to fetch concept for persistence
            concept_row = db.execute(
                text("SELECT concept_id FROM learning_atoms WHERE id = :aid"),
                {"aid": req.atom_id},
            ).fetchone()
            concept_id = str(concept_row.concept_id) if concept_row and concept_row.concept_id else None
            _record_response(
                db=db,
                learner_id="ccna-user",
                atom_id=req.atom_id,
                concept_id=concept_id,
                correct=req.correct,
                hint_used=req.hint_used,
                time_ms=req.time_ms,
                was_remediation=False,
            )
    except SQLAlchemyError:
        pass  # DB error recording response
    response: dict[str, Any] = {"atom_id": req.atom_id, "mastered": mastered, "attempts": len(outcomes)}
    if remediation:
        response["remediation"] = remediation
    return response


@router.get("/ccna/progress", response_model=ProgressResponse, summary="Get CCNA progress")
def get_ccna_progress() -> ProgressResponse:
    """Return simple progress metrics."""
    total_attempts = sum(len(v) for v in _STUDY_OUTCOMES.values())
    correct = sum(1 for v in _STUDY_OUTCOMES.values() for att in v if att.get("correct"))
    accuracy = 0.0 if total_attempts == 0 else round(correct / total_attempts, 2)
    return ProgressResponse(
        total_attempts=total_attempts,
        mastered_atoms=len(_MASTERED),
        accuracy=accuracy,
        struggle_objectives=[],
    )


@router.get("/ccna/remediation", summary="Get remediation suggestions")
def get_ccna_remediation(atom_id: str | None = None) -> dict[str, Any]:
    """Return remediation bundle with hints, explanation, and source references."""
    with next(get_session()) as db:
        atoms = _load_learnable_deck(session=db)
    target = next((a for a in atoms if a["id"] == atom_id), atoms[0] if atoms else None)
    if not target:
        raise HTTPException(status_code=404, detail="No atoms available for remediation")

    remediation = {
        "atom_id": target["id"],
        "hints": target.get("hints", []),
        "explanation": target.get("explanation"),
        "source_ref": target.get("source_ref"),
        "keyboard_hints": target.get("keyboard_hints", []),
        "aria_role": target.get("aria_role"),
        "aria_label": target.get("aria_label"),
    }
    # Try to append easier neighbors for the same concept
    if target.get("concept_id"):
        try:
            from src.semantic.similarity_service import get_easier_neighbors

            neighbors = get_easier_neighbors(
                db_session=db,
                concept_id=UUID(str(target["concept_id"])),
                limit=2,
                difficulty_band=2,
            )
            remediation["neighbors"] = [str(n) for n in neighbors]
            _record_remediation_event(
                db=db,
                learner_id="ccna-user",
                concept_id=str(target["concept_id"]),
                trigger_atom_id=atom_id,
                remediation_atoms=remediation.get("neighbors"),
            )
        except Exception as exc:  # pragma: no cover
            logger.debug(f"Neighbor fetch skipped: {exc}")
    _emit_event("remediation_offered", {"atom_id": remediation["atom_id"]})
    return remediation


@router.get(
    "/ccna/objectives/{concept_id}/neighbors",
    response_model=ObjectiveNeighborsResponse,
    summary="Get easier neighbors for a concept with difficulty banding",
)
def get_objective_neighbors(
    concept_id: str,
    difficulty_band: int = Query(2, ge=0, le=4, description="Difficulty levels below target to search"),
    limit: int = Query(3, ge=1, le=10),
    db: Session = Depends(get_session),
) -> ObjectiveNeighborsResponse:
    """Expose easier neighbors for sequencer/remediation policies."""
    try:
        concept_uuid = UUID(concept_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid concept_id")

    try:
        from src.semantic.similarity_service import get_easier_neighbors

        neighbor_ids = get_easier_neighbors(
            db_session=db,
            concept_id=concept_uuid,
            limit=limit,
            difficulty_band=difficulty_band,
        )
    except Exception as exc:  # pragma: no cover
        logger.debug(f"Neighbor lookup failed: {exc}")
        neighbor_ids = []

    neighbors: list[NeighborAtom] = []
    for nid in neighbor_ids:
        try:
            row = db.execute(
                text(
                    """
                    SELECT id, atom_type, front, difficulty, concept_id
                    FROM learning_atoms
                    WHERE id = :aid
                    """
                ),
                {"aid": str(nid)},
            ).fetchone()
            if not row:
                continue
            neighbors.append(
                NeighborAtom(
                    atom_id=str(row.id),
                    atom_type=getattr(row, "atom_type", None),
                    difficulty=int(row.difficulty) if getattr(row, "difficulty", None) is not None else None,
                    concept_id=str(row.concept_id) if getattr(row, "concept_id", None) else None,
                    front_preview=_preview_text(getattr(row, "front", "")),
                )
            )
        except Exception as exc:  # pragma: no cover
            logger.debug(f"Neighbor detail fetch skipped: {exc}")
            continue

    return ObjectiveNeighborsResponse(concept_id=concept_id, neighbors=neighbors)


@router.get(
    "/ccna/objectives/{concept_id}/cluster",
    response_model=ObjectiveClusterResponse,
    summary="Get cluster context for a concept/objective",
)
def get_objective_cluster(concept_id: str, db: Session = Depends(get_session)) -> ObjectiveClusterResponse:
    """Expose objective cluster info for sequencer policies."""
    try:
        concept_uuid = UUID(concept_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid concept_id")

    concept_row = db.execute(
        text(
            """
            SELECT c.id, c.name, c.cluster_id, cc.name AS cluster_name
            FROM concepts c
            LEFT JOIN concept_clusters cc ON c.cluster_id = cc.id
            WHERE c.id = :cid
            """
        ),
        {"cid": str(concept_uuid)},
    ).fetchone()

    if not concept_row:
        raise HTTPException(status_code=404, detail=f"Concept {concept_id} not found")

    members: list[NeighborAtom] = []
    try:
        rows = db.execute(
            text(
                """
                SELECT id, atom_type, front, difficulty, concept_id
                FROM learning_atoms
                WHERE concept_id = :cid
                ORDER BY COALESCE(difficulty, 3) ASC
                LIMIT 10
                """
            ),
            {"cid": str(concept_uuid)},
        ).fetchall()
        for row in rows:
            members.append(
                NeighborAtom(
                    atom_id=str(row.id),
                    atom_type=getattr(row, "atom_type", None),
                    difficulty=int(row.difficulty) if getattr(row, "difficulty", None) is not None else None,
                    concept_id=str(row.concept_id) if getattr(row, "concept_id", None) else None,
                    front_preview=_preview_text(getattr(row, "front", "")),
                )
            )
    except Exception as exc:  # pragma: no cover
        logger.debug(f"Cluster members fetch skipped: {exc}")

    return ObjectiveClusterResponse(
        concept_id=concept_id,
        concept_name=getattr(concept_row, "name", None),
        cluster_id=str(concept_row.cluster_id) if getattr(concept_row, "cluster_id", None) else None,
        cluster_name=getattr(concept_row, "cluster_name", None),
        members=members,
    )


@router.get("/ccna/struggle-map", summary="Top struggle atoms/objectives")
def get_ccna_struggle_map(limit: int = Query(10, le=25)) -> dict[str, Any]:
    """Return struggle hotspots (atoms and objectives) with remediation hints."""
    # Aggregate telemetry files if present
    counts = dict(_STRUGGLE_CACHE)
    try:
        for path in _TELEMETRY_DIR.glob("attempt_submitted.jsonl"):
            with path.open("r", encoding="utf-8") as f:
                for line in f:
                    if '"correct": False' in line:
                        try:
                            # naive parse for atom_id field
                            if "atom_id" in line:
                                start = line.find("atom_id")
                                aid = line[start:].split(":")[1].split(",")[0].strip().strip(" '\"{}")
                                if aid:
                                    counts[aid] = counts.get(aid, 0) + 1
                        except (IndexError, ValueError):
                            continue  # Malformed line
    except Exception as exc:  # pragma: no cover
        logger.debug(f"Struggle map aggregation skipped: {exc}")

    top = sorted(counts.items(), key=lambda x: x[1], reverse=True)[:limit]
    struggle_map = {"top_struggles": [{"atom_id": aid, "incorrect": cnt} for aid, cnt in top]}

    # Objective-level aggregation and suggested remediations (best-effort)
    concept_counts: dict[str, int] = {}
    suggestions: list[dict[str, Any]] = []
    try:
        with next(get_session()) as db:
            if top:
                rows = db.execute(
                    text(
                        """
                        SELECT id, concept_id FROM learning_atoms WHERE id = ANY(:atom_ids)
                        """
                    ),
                    {"atom_ids": [UUID(aid) for aid, _ in top]},
                ).fetchall()
                atom_concept = {str(r.id): str(r.concept_id) for r in rows if getattr(r, "concept_id", None)}
                for aid, cnt in top:
                    cid = atom_concept.get(aid)
                    if cid:
                        concept_counts[cid] = concept_counts.get(cid, 0) + cnt

                # pick top concepts and suggest remediations via easier neighbors
                for concept_id, cnt in sorted(concept_counts.items(), key=lambda x: x[1], reverse=True)[:3]:
                    try:
                        from src.semantic.similarity_service import get_easier_neighbors

                        neighbors = get_easier_neighbors(
                            db_session=db,
                            concept_id=UUID(concept_id),
                            limit=2,
                            difficulty_band=2,
                        )
                        suggestions.append(
                            {
                                "concept_id": concept_id,
                                "struggle_count": cnt,
                                "remediation_neighbors": [str(n) for n in neighbors],
                            }
                        )
                    except Exception as exc:  # pragma: no cover
                        logger.debug(f"Struggle remediation skip: {exc}")
                        suggestions.append({"concept_id": concept_id, "struggle_count": cnt, "remediation_neighbors": []})
    except Exception as exc:  # pragma: no cover
        logger.debug(f"Struggle objective aggregation skipped: {exc}")

    if concept_counts:
        struggle_map["top_objectives"] = [
            {"concept_id": cid, "incorrect": cnt}
            for cid, cnt in sorted(concept_counts.items(), key=lambda x: x[1], reverse=True)[:limit]
        ]
    if suggestions:
        struggle_map["suggested_remediations"] = suggestions

    # Persist YAML report for downstream use
    try:
        out_path = Path("data") / "ccna_struggle_map.yaml"
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(yaml.safe_dump(struggle_map), encoding="utf-8")
    except Exception as exc:  # pragma: no cover
        logger.debug(f"Struggle map write skipped: {exc}")

    return struggle_map
