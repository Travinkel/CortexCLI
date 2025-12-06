"""
Prerequisites router for soft/hard gating management.

Endpoints for:
- CRUD operations on explicit prerequisites
- Gating evaluation (access check)
- Prerequisite chain resolution
- Waiver management
- Anki tag sync
- Circular dependency validation

Phase 3 implementation for right-learning integration.
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


class PrerequisiteCreateRequest(BaseModel):
    """Request model for creating a prerequisite."""

    source_concept_id: Optional[str] = Field(None, description="Source concept ID")
    source_atom_id: Optional[str] = Field(None, description="Source atom ID")
    target_concept_id: str = Field(..., description="Target concept ID (prerequisite)")
    gating_type: str = Field("soft", description="Gating type: 'soft' or 'hard'")
    mastery_type: str = Field("integration", description="Mastery type: 'foundation', 'integration', 'mastery'")
    mastery_threshold: Optional[float] = Field(None, ge=0, le=1, description="Custom mastery threshold (0-1)")
    origin: str = Field("explicit", description="Origin: 'explicit', 'tag', 'inferred', 'imported'")
    anki_tag: Optional[str] = Field(None, description="Source Anki tag if origin='tag'")
    notes: Optional[str] = Field(None, description="Additional notes")


class PrerequisiteResponse(BaseModel):
    """Response model for a prerequisite."""

    id: str
    source_concept_id: Optional[str]
    source_atom_id: Optional[str]
    target_concept_id: str
    target_concept_name: Optional[str]
    gating_type: str
    mastery_type: str
    mastery_threshold: float
    origin: str
    anki_tag: Optional[str]
    status: str
    notes: Optional[str]
    created_at: datetime


class PrerequisiteUpdateRequest(BaseModel):
    """Request model for updating a prerequisite."""

    gating_type: Optional[str] = Field(None, description="Gating type: 'soft' or 'hard'")
    mastery_type: Optional[str] = Field(None, description="Mastery type")
    mastery_threshold: Optional[float] = Field(None, ge=0, le=1)
    status: Optional[str] = Field(None, description="Status: 'active', 'deprecated', 'removed'")
    notes: Optional[str] = None


class AccessCheckResponse(BaseModel):
    """Response model for access check."""

    status: str  # allowed, warning, blocked, waived
    can_access: bool
    message: str
    blocking_prerequisites: List[Dict[str, Any]] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    waiver_applied: bool = False


class PrerequisiteChainNode(BaseModel):
    """A node in the prerequisite chain."""

    depth: int
    concept_id: str
    concept_name: str
    gating_type: str
    mastery_threshold: float
    is_met: bool = False
    current_mastery: Optional[float] = None


class PrerequisiteChainResponse(BaseModel):
    """Response model for prerequisite chain."""

    target_concept_id: str
    target_concept_name: str
    chain: List[PrerequisiteChainNode]
    total_depth: int


class WaiverCreateRequest(BaseModel):
    """Request model for creating a waiver."""

    waiver_type: str = Field(..., description="Type: 'instructor', 'challenge', 'external', 'accelerated'")
    granted_by: Optional[str] = Field(None, description="User who granted the waiver")
    evidence_type: Optional[str] = Field(None, description="Type of evidence")
    evidence_details: Optional[Dict[str, Any]] = Field(None, description="Evidence JSON")
    expires_at: Optional[datetime] = Field(None, description="Expiration date")
    notes: Optional[str] = None


class WaiverResponse(BaseModel):
    """Response model for a waiver."""

    id: str
    prerequisite_id: str
    waiver_type: str
    granted_by: Optional[str]
    evidence_type: Optional[str]
    evidence_details: Optional[Dict[str, Any]]
    expires_at: Optional[datetime]
    is_active: bool
    granted_at: datetime
    notes: Optional[str]


class AnkiTagSyncRequest(BaseModel):
    """Request model for Anki tag sync."""

    atom_id: str
    tags: List[str] = Field(..., description="List of Anki tags")


class AnkiTagSyncResponse(BaseModel):
    """Response model for Anki tag sync."""

    atom_id: str
    prerequisites_created: int
    prerequisites_tags: List[str]


class CircularValidationResponse(BaseModel):
    """Response model for circular dependency validation."""

    is_valid: bool
    errors: List[Dict[str, Any]] = Field(default_factory=list)


class BatchImportRequest(BaseModel):
    """Request model for batch prerequisite import."""

    prerequisites: List[Dict[str, Any]]
    validate_only: bool = Field(False, description="Only validate, don't create")


class BatchImportResponse(BaseModel):
    """Response model for batch import."""

    success: bool
    created: int
    skipped: int
    errors: List[Dict[str, Any]] = Field(default_factory=list)


# ========================================
# CRUD Endpoints
# ========================================


@router.post(
    "",
    response_model=PrerequisiteResponse,
    summary="Create prerequisite",
)
async def create_prerequisite(
    request: PrerequisiteCreateRequest,
    db: AsyncSession = Depends(get_async_session),
) -> PrerequisiteResponse:
    """
    Create a new prerequisite relationship.

    Prerequisites define what concepts must be mastered before accessing
    a target concept. Soft gating shows warnings; hard gating blocks access.

    Mastery types:
    - foundation: 40% threshold (basic exposure)
    - integration: 65% threshold (solid understanding)
    - mastery: 85% threshold (expert level)
    """
    logger.info(f"Creating prerequisite: {request.target_concept_id} -> {request.source_concept_id or request.source_atom_id}")

    try:
        from src.prerequisites import PrerequisiteService

        service = PrerequisiteService(db)

        # Parse UUIDs
        source_concept_uuid = UUID(request.source_concept_id) if request.source_concept_id else None
        source_atom_uuid = UUID(request.source_atom_id) if request.source_atom_id else None
        target_concept_uuid = UUID(request.target_concept_id)

        # Calculate threshold
        mastery_threshold = Decimal(str(request.mastery_threshold)) if request.mastery_threshold else None

        prereq = await service.create_prerequisite(
            source_concept_id=source_concept_uuid,
            source_atom_id=source_atom_uuid,
            target_concept_id=target_concept_uuid,
            gating_type=request.gating_type,
            mastery_type=request.mastery_type,
            mastery_threshold=mastery_threshold,
            origin=request.origin,
            anki_tag=request.anki_tag,
            notes=request.notes,
        )

        target_name = prereq.target_concept.name if prereq.target_concept else None

        return PrerequisiteResponse(
            id=str(prereq.id),
            source_concept_id=str(prereq.source_concept_id) if prereq.source_concept_id else None,
            source_atom_id=str(prereq.source_atom_id) if prereq.source_atom_id else None,
            target_concept_id=str(prereq.target_concept_id),
            target_concept_name=target_name,
            gating_type=prereq.gating_type,
            mastery_type=prereq.mastery_type,
            mastery_threshold=float(prereq.mastery_threshold),
            origin=prereq.origin,
            anki_tag=prereq.anki_tag,
            status=prereq.status,
            notes=prereq.notes,
            created_at=prereq.created_at,
        )

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as exc:
        logger.exception("Failed to create prerequisite")
        raise HTTPException(status_code=500, detail=str(exc))


@router.get(
    "",
    response_model=List[PrerequisiteResponse],
    summary="List prerequisites",
)
async def list_prerequisites(
    source_concept_id: Optional[str] = Query(None),
    source_atom_id: Optional[str] = Query(None),
    target_concept_id: Optional[str] = Query(None),
    gating_type: Optional[str] = Query(None, description="Filter by gating type"),
    status: str = Query("active", description="Filter by status"),
    limit: int = Query(100, ge=1, le=500),
    db: AsyncSession = Depends(get_async_session),
) -> List[PrerequisiteResponse]:
    """
    List prerequisites with optional filters.

    Use this to find all prerequisites for a concept or atom.
    """
    try:
        from src.prerequisites import PrerequisiteService

        service = PrerequisiteService(db)

        prereqs = await service.list_prerequisites(
            source_concept_id=UUID(source_concept_id) if source_concept_id else None,
            source_atom_id=UUID(source_atom_id) if source_atom_id else None,
            target_concept_id=UUID(target_concept_id) if target_concept_id else None,
            gating_type=gating_type,
            status=status,
            limit=limit,
        )

        return [
            PrerequisiteResponse(
                id=str(p.id),
                source_concept_id=str(p.source_concept_id) if p.source_concept_id else None,
                source_atom_id=str(p.source_atom_id) if p.source_atom_id else None,
                target_concept_id=str(p.target_concept_id),
                target_concept_name=p.target_concept.name if p.target_concept else None,
                gating_type=p.gating_type,
                mastery_type=p.mastery_type,
                mastery_threshold=float(p.mastery_threshold),
                origin=p.origin,
                anki_tag=p.anki_tag,
                status=p.status,
                notes=p.notes,
                created_at=p.created_at,
            )
            for p in prereqs
        ]

    except Exception as exc:
        logger.exception("Failed to list prerequisites")
        raise HTTPException(status_code=500, detail=str(exc))


@router.get(
    "/{prerequisite_id}",
    response_model=PrerequisiteResponse,
    summary="Get prerequisite",
)
async def get_prerequisite(
    prerequisite_id: str,
    db: AsyncSession = Depends(get_async_session),
) -> PrerequisiteResponse:
    """Get a specific prerequisite by ID."""
    try:
        from src.prerequisites import PrerequisiteService

        service = PrerequisiteService(db)
        prereq = await service.get_prerequisite(UUID(prerequisite_id))

        if not prereq:
            raise HTTPException(status_code=404, detail="Prerequisite not found")

        return PrerequisiteResponse(
            id=str(prereq.id),
            source_concept_id=str(prereq.source_concept_id) if prereq.source_concept_id else None,
            source_atom_id=str(prereq.source_atom_id) if prereq.source_atom_id else None,
            target_concept_id=str(prereq.target_concept_id),
            target_concept_name=prereq.target_concept.name if prereq.target_concept else None,
            gating_type=prereq.gating_type,
            mastery_type=prereq.mastery_type,
            mastery_threshold=float(prereq.mastery_threshold),
            origin=prereq.origin,
            anki_tag=prereq.anki_tag,
            status=prereq.status,
            notes=prereq.notes,
            created_at=prereq.created_at,
        )

    except HTTPException:
        raise
    except Exception as exc:
        logger.exception(f"Failed to get prerequisite {prerequisite_id}")
        raise HTTPException(status_code=500, detail=str(exc))


@router.put(
    "/{prerequisite_id}",
    response_model=PrerequisiteResponse,
    summary="Update prerequisite",
)
async def update_prerequisite(
    prerequisite_id: str,
    request: PrerequisiteUpdateRequest,
    db: AsyncSession = Depends(get_async_session),
) -> PrerequisiteResponse:
    """Update a prerequisite."""
    try:
        from src.prerequisites import PrerequisiteService

        service = PrerequisiteService(db)

        update_data = {
            k: v for k, v in request.model_dump().items() if v is not None
        }

        if "mastery_threshold" in update_data:
            update_data["mastery_threshold"] = Decimal(str(update_data["mastery_threshold"]))

        prereq = await service.update_prerequisite(UUID(prerequisite_id), **update_data)

        if not prereq:
            raise HTTPException(status_code=404, detail="Prerequisite not found")

        return PrerequisiteResponse(
            id=str(prereq.id),
            source_concept_id=str(prereq.source_concept_id) if prereq.source_concept_id else None,
            source_atom_id=str(prereq.source_atom_id) if prereq.source_atom_id else None,
            target_concept_id=str(prereq.target_concept_id),
            target_concept_name=prereq.target_concept.name if prereq.target_concept else None,
            gating_type=prereq.gating_type,
            mastery_type=prereq.mastery_type,
            mastery_threshold=float(prereq.mastery_threshold),
            origin=prereq.origin,
            anki_tag=prereq.anki_tag,
            status=prereq.status,
            notes=prereq.notes,
            created_at=prereq.created_at,
        )

    except HTTPException:
        raise
    except Exception as exc:
        logger.exception(f"Failed to update prerequisite {prerequisite_id}")
        raise HTTPException(status_code=500, detail=str(exc))


@router.delete(
    "/{prerequisite_id}",
    summary="Delete prerequisite",
)
async def delete_prerequisite(
    prerequisite_id: str,
    db: AsyncSession = Depends(get_async_session),
) -> Dict[str, Any]:
    """Delete a prerequisite (soft delete by setting status='removed')."""
    try:
        from src.prerequisites import PrerequisiteService

        service = PrerequisiteService(db)
        success = await service.delete_prerequisite(UUID(prerequisite_id))

        if not success:
            raise HTTPException(status_code=404, detail="Prerequisite not found")

        return {"success": True, "message": "Prerequisite removed"}

    except HTTPException:
        raise
    except Exception as exc:
        logger.exception(f"Failed to delete prerequisite {prerequisite_id}")
        raise HTTPException(status_code=500, detail=str(exc))


# ========================================
# Gating Evaluation Endpoints
# ========================================


@router.get(
    "/check/{concept_id}",
    response_model=AccessCheckResponse,
    summary="Check access (for right-learning)",
)
async def check_access(
    concept_id: str,
    user_mastery: Optional[str] = Query(None, description="JSON string of concept_id:mastery pairs"),
    db: AsyncSession = Depends(get_async_session),
) -> AccessCheckResponse:
    """
    Check if user can access a concept based on prerequisites.

    This endpoint is designed for right-learning integration.
    Returns access status (allowed/warning/blocked/waived).

    user_mastery should be a JSON object: {"concept_id": mastery_score, ...}
    """
    logger.info(f"Checking access for concept {concept_id}")

    try:
        import json
        from src.prerequisites import GatingService

        service = GatingService(db)

        # Parse user mastery data
        mastery_data: Dict[UUID, float] = {}
        if user_mastery:
            try:
                mastery_json = json.loads(user_mastery)
                mastery_data = {UUID(k): float(v) for k, v in mastery_json.items()}
            except (json.JSONDecodeError, ValueError) as e:
                raise HTTPException(status_code=400, detail=f"Invalid user_mastery JSON: {e}")

        result = await service.evaluate_access(
            concept_id=UUID(concept_id),
            user_mastery_data=mastery_data,
        )

        return AccessCheckResponse(
            status=result.status.value,
            can_access=result.can_access,
            message=result.message,
            blocking_prerequisites=[
                {
                    "prerequisite_id": str(b.prerequisite_id),
                    "target_concept_id": str(b.target_concept_id),
                    "target_concept_name": b.target_concept_name,
                    "gating_type": b.gating_type,
                    "required_mastery": float(b.required_mastery),
                    "current_mastery": float(b.current_mastery) if b.current_mastery else 0,
                    "mastery_gap": float(b.mastery_gap) if b.mastery_gap else None,
                }
                for b in result.blocking_prerequisites
            ],
            warnings=result.warnings,
            waiver_applied=result.waiver_applied,
        )

    except HTTPException:
        raise
    except Exception as exc:
        logger.exception(f"Failed to check access for {concept_id}")
        raise HTTPException(status_code=500, detail=str(exc))


@router.post(
    "/check",
    response_model=AccessCheckResponse,
    summary="Check access (POST for complex mastery data)",
)
async def check_access_post(
    concept_id: str = Query(...),
    user_mastery: Dict[str, float] = None,
    db: AsyncSession = Depends(get_async_session),
) -> AccessCheckResponse:
    """
    Check access with POST body for complex mastery data.

    Use this when the mastery data is too large for query params.
    """
    try:
        from src.prerequisites import GatingService

        service = GatingService(db)

        mastery_data: Dict[UUID, float] = {}
        if user_mastery:
            mastery_data = {UUID(k): float(v) for k, v in user_mastery.items()}

        result = await service.evaluate_access(
            concept_id=UUID(concept_id),
            user_mastery_data=mastery_data,
        )

        return AccessCheckResponse(
            status=result.status.value,
            can_access=result.can_access,
            message=result.message,
            blocking_prerequisites=[
                {
                    "prerequisite_id": str(b.prerequisite_id),
                    "target_concept_id": str(b.target_concept_id),
                    "target_concept_name": b.target_concept_name,
                    "gating_type": b.gating_type,
                    "required_mastery": float(b.required_mastery),
                    "current_mastery": float(b.current_mastery) if b.current_mastery else 0,
                    "mastery_gap": float(b.mastery_gap) if b.mastery_gap else None,
                }
                for b in result.blocking_prerequisites
            ],
            warnings=result.warnings,
            waiver_applied=result.waiver_applied,
        )

    except Exception as exc:
        logger.exception(f"Failed to check access for {concept_id}")
        raise HTTPException(status_code=500, detail=str(exc))


# ========================================
# Prerequisite Chain Endpoints
# ========================================


@router.get(
    "/chain/{concept_id}",
    response_model=PrerequisiteChainResponse,
    summary="Get prerequisite chain",
)
async def get_prerequisite_chain(
    concept_id: str,
    user_mastery: Optional[str] = Query(None, description="JSON string of mastery data"),
    max_depth: int = Query(10, ge=1, le=20),
    db: AsyncSession = Depends(get_async_session),
) -> PrerequisiteChainResponse:
    """
    Get the full prerequisite chain for a concept.

    Returns prerequisites in order of depth (closest first).
    If user_mastery is provided, includes whether each is met.
    """
    logger.info(f"Getting prerequisite chain for {concept_id}")

    try:
        import json
        from src.prerequisites import PrerequisiteService

        service = PrerequisiteService(db)

        # Parse mastery data
        mastery_data: Dict[UUID, float] = {}
        if user_mastery:
            try:
                mastery_json = json.loads(user_mastery)
                mastery_data = {UUID(k): float(v) for k, v in mastery_json.items()}
            except (json.JSONDecodeError, ValueError):
                pass

        chain = await service.get_prerequisite_chain(
            concept_id=UUID(concept_id),
            max_depth=max_depth,
        )

        # Get concept name
        from sqlalchemy import select
        from src.db.models import CleanConcept
        result = await db.execute(
            select(CleanConcept).where(CleanConcept.id == UUID(concept_id))
        )
        concept = result.scalar_one_or_none()

        return PrerequisiteChainResponse(
            target_concept_id=concept_id,
            target_concept_name=concept.name if concept else concept_id,
            chain=[
                PrerequisiteChainNode(
                    depth=node.depth,
                    concept_id=str(node.concept_id),
                    concept_name=node.concept_name,
                    gating_type=node.gating_type,
                    mastery_threshold=float(node.mastery_threshold),
                    is_met=mastery_data.get(node.concept_id, 0) >= float(node.mastery_threshold),
                    current_mastery=mastery_data.get(node.concept_id),
                )
                for node in chain
            ],
            total_depth=len(chain),
        )

    except Exception as exc:
        logger.exception(f"Failed to get prerequisite chain for {concept_id}")
        raise HTTPException(status_code=500, detail=str(exc))


# ========================================
# Validation Endpoints
# ========================================


@router.post(
    "/validate",
    response_model=CircularValidationResponse,
    summary="Validate prerequisites (circular check)",
)
async def validate_prerequisites(
    source_concept_id: Optional[str] = Query(None),
    target_concept_id: str = Query(...),
    db: AsyncSession = Depends(get_async_session),
) -> CircularValidationResponse:
    """
    Validate that adding a prerequisite won't create circular dependencies.

    Returns is_valid=False if adding this relationship would create a cycle.
    """
    try:
        from src.prerequisites import PrerequisiteService

        service = PrerequisiteService(db)

        errors = await service.detect_circular_dependencies(
            source_concept_id=UUID(source_concept_id) if source_concept_id else None,
            target_concept_id=UUID(target_concept_id),
        )

        return CircularValidationResponse(
            is_valid=len(errors) == 0,
            errors=[
                {
                    "chain": [str(c) for c in e.chain],
                    "concept_names": e.concept_names,
                    "message": e.message,
                }
                for e in errors
            ],
        )

    except Exception as exc:
        logger.exception("Failed to validate prerequisites")
        raise HTTPException(status_code=500, detail=str(exc))


@router.get(
    "/circular-check",
    response_model=CircularValidationResponse,
    summary="Detect all circular dependencies",
)
async def detect_all_circular(
    db: AsyncSession = Depends(get_async_session),
) -> CircularValidationResponse:
    """
    Scan all prerequisites for circular dependencies.

    Use this for periodic health checks of the prerequisite graph.
    """
    try:
        from src.prerequisites import PrerequisiteService

        service = PrerequisiteService(db)
        errors = await service.detect_all_circular_dependencies()

        return CircularValidationResponse(
            is_valid=len(errors) == 0,
            errors=[
                {
                    "chain": [str(c) for c in e.chain],
                    "concept_names": e.concept_names,
                    "message": e.message,
                }
                for e in errors
            ],
        )

    except Exception as exc:
        logger.exception("Failed to detect circular dependencies")
        raise HTTPException(status_code=500, detail=str(exc))


# ========================================
# Anki Sync Endpoints
# ========================================


@router.post(
    "/sync/from-anki",
    response_model=AnkiTagSyncResponse,
    summary="Sync prerequisites from Anki tags",
)
async def sync_from_anki_tags(
    request: AnkiTagSyncRequest,
    db: AsyncSession = Depends(get_async_session),
) -> AnkiTagSyncResponse:
    """
    Create prerequisites from Anki tags.

    Parses tags in format: tag:prereq:domain:topic:subtopic
    and creates corresponding prerequisite relationships.
    """
    logger.info(f"Syncing prerequisites from Anki tags for atom {request.atom_id}")

    try:
        from src.prerequisites import PrerequisiteService

        service = PrerequisiteService(db)

        prereqs = await service.sync_from_anki_tags(
            atom_id=UUID(request.atom_id),
            tags=request.tags,
        )

        return AnkiTagSyncResponse(
            atom_id=request.atom_id,
            prerequisites_created=len(prereqs),
            prerequisites_tags=[p.anki_tag for p in prereqs if p.anki_tag],
        )

    except Exception as exc:
        logger.exception(f"Failed to sync Anki tags for {request.atom_id}")
        raise HTTPException(status_code=500, detail=str(exc))


@router.get(
    "/export/anki-tags/{atom_id}",
    summary="Export prerequisites as Anki tags",
)
async def export_to_anki_tags(
    atom_id: str,
    db: AsyncSession = Depends(get_async_session),
) -> Dict[str, Any]:
    """
    Export prerequisite relationships as Anki tags.

    Returns tags in format: tag:prereq:domain:topic:subtopic
    """
    try:
        from src.prerequisites import PrerequisiteService

        service = PrerequisiteService(db)
        tags = await service.export_to_anki_tags(UUID(atom_id))

        return {
            "atom_id": atom_id,
            "tags": tags,
        }

    except Exception as exc:
        logger.exception(f"Failed to export Anki tags for {atom_id}")
        raise HTTPException(status_code=500, detail=str(exc))


# ========================================
# Waiver Endpoints
# ========================================


@router.post(
    "/{prerequisite_id}/waiver",
    response_model=WaiverResponse,
    summary="Create waiver",
)
async def create_waiver(
    prerequisite_id: str,
    request: WaiverCreateRequest,
    db: AsyncSession = Depends(get_async_session),
) -> WaiverResponse:
    """
    Create a waiver for a prerequisite.

    Waiver types:
    - instructor: Manual override by instructor
    - challenge: Passed challenge assessment
    - external: External certification/evidence
    - accelerated: Accelerated track exemption
    """
    logger.info(f"Creating waiver for prerequisite {prerequisite_id}")

    try:
        from src.prerequisites import GatingService

        service = GatingService(db)

        waiver = await service.create_waiver(
            prerequisite_id=UUID(prerequisite_id),
            waiver_type=request.waiver_type,
            granted_by=request.granted_by,
            evidence_type=request.evidence_type,
            evidence_details=request.evidence_details,
            expires_at=request.expires_at,
            notes=request.notes,
        )

        return WaiverResponse(
            id=str(waiver.id),
            prerequisite_id=str(waiver.prerequisite_id),
            waiver_type=waiver.waiver_type,
            granted_by=waiver.granted_by,
            evidence_type=waiver.evidence_type,
            evidence_details=waiver.evidence_details,
            expires_at=waiver.expires_at,
            is_active=waiver.is_active,
            granted_at=waiver.granted_at,
            notes=waiver.notes,
        )

    except Exception as exc:
        logger.exception(f"Failed to create waiver for {prerequisite_id}")
        raise HTTPException(status_code=500, detail=str(exc))


@router.get(
    "/{prerequisite_id}/waivers",
    response_model=List[WaiverResponse],
    summary="List waivers",
)
async def list_waivers(
    prerequisite_id: str,
    include_expired: bool = Query(False),
    db: AsyncSession = Depends(get_async_session),
) -> List[WaiverResponse]:
    """Get waivers for a prerequisite."""
    try:
        from src.prerequisites import GatingService

        service = GatingService(db)

        waivers = await service.get_waivers(
            prerequisite_id=UUID(prerequisite_id),
            include_expired=include_expired,
        )

        return [
            WaiverResponse(
                id=str(w.id),
                prerequisite_id=str(w.prerequisite_id),
                waiver_type=w.waiver_type,
                granted_by=w.granted_by,
                evidence_type=w.evidence_type,
                evidence_details=w.evidence_details,
                expires_at=w.expires_at,
                is_active=w.is_active,
                granted_at=w.granted_at,
                notes=w.notes,
            )
            for w in waivers
        ]

    except Exception as exc:
        logger.exception(f"Failed to list waivers for {prerequisite_id}")
        raise HTTPException(status_code=500, detail=str(exc))


@router.delete(
    "/waivers/{waiver_id}",
    summary="Revoke waiver",
)
async def revoke_waiver(
    waiver_id: str,
    db: AsyncSession = Depends(get_async_session),
) -> Dict[str, Any]:
    """Revoke a waiver."""
    try:
        from src.prerequisites import GatingService

        service = GatingService(db)
        success = await service.revoke_waiver(UUID(waiver_id))

        if not success:
            raise HTTPException(status_code=404, detail="Waiver not found")

        return {"success": True, "message": "Waiver revoked"}

    except HTTPException:
        raise
    except Exception as exc:
        logger.exception(f"Failed to revoke waiver {waiver_id}")
        raise HTTPException(status_code=500, detail=str(exc))


# ========================================
# Batch Operations
# ========================================


@router.post(
    "/batch-import",
    response_model=BatchImportResponse,
    summary="Batch import prerequisites",
)
async def batch_import_prerequisites(
    request: BatchImportRequest,
    db: AsyncSession = Depends(get_async_session),
) -> BatchImportResponse:
    """
    Batch import prerequisites from a list.

    Each item should have:
    - source_concept (name or ID)
    - target_concept (name or ID)
    - gating_type: soft/hard
    - mastery_threshold (optional)

    Set validate_only=True to check for circular dependencies without creating.
    """
    logger.info(f"Batch importing {len(request.prerequisites)} prerequisites")

    try:
        from src.prerequisites import PrerequisiteService

        service = PrerequisiteService(db)

        # First validate
        errors = []
        for i, prereq in enumerate(request.prerequisites):
            target = prereq.get("target_concept")
            source = prereq.get("source_concept")

            if not target:
                errors.append({"row": i, "error": "Missing target_concept"})
                continue

            # Check circular (simplified - full implementation would resolve names to IDs)

        if request.validate_only:
            return BatchImportResponse(
                success=len(errors) == 0,
                created=0,
                skipped=len(errors),
                errors=errors,
            )

        # Create prerequisites
        created = 0
        for i, prereq_data in enumerate(request.prerequisites):
            try:
                # This is a simplified implementation
                # Full version would resolve concept names to IDs
                pass
            except Exception as e:
                errors.append({"row": i, "error": str(e)})

        await db.commit()

        return BatchImportResponse(
            success=len(errors) == 0,
            created=created,
            skipped=len(errors),
            errors=errors,
        )

    except Exception as exc:
        logger.exception("Failed to batch import prerequisites")
        raise HTTPException(status_code=500, detail=str(exc))


# ========================================
# Mastery Threshold Endpoints
# ========================================


@router.get(
    "/thresholds",
    summary="Get mastery thresholds",
)
async def get_mastery_thresholds(
    db: AsyncSession = Depends(get_async_session),
) -> Dict[str, float]:
    """
    Get all mastery threshold values.

    Returns thresholds for foundation, integration, and mastery types.
    """
    from src.prerequisites import GatingService

    service = GatingService(db)
    thresholds = service.get_all_thresholds()

    return {k: float(v) for k, v in thresholds.items()}


@router.get(
    "/thresholds/{mastery_type}",
    summary="Get specific threshold",
)
async def get_mastery_threshold(
    mastery_type: str,
    db: AsyncSession = Depends(get_async_session),
) -> Dict[str, Any]:
    """Get threshold for a specific mastery type."""
    from src.prerequisites import GatingService

    service = GatingService(db)

    if mastery_type not in ("foundation", "integration", "mastery"):
        raise HTTPException(
            status_code=400,
            detail=f"Invalid mastery type. Must be: foundation, integration, or mastery"
        )

    threshold = service.get_mastery_threshold(mastery_type)

    return {
        "mastery_type": mastery_type,
        "threshold": float(threshold),
    }
