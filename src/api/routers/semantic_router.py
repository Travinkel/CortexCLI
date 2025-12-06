"""
Semantic analysis router for embedding-based operations.

Endpoints for:
- Generating semantic embeddings
- Finding semantic duplicates
- Inferring prerequisites
- Knowledge clustering

Phase 2.5 implementation using pgvector and sentence-transformers.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from loguru import logger
from pydantic import BaseModel, Field

from src.db.database import get_session
from sqlalchemy.orm import Session


router = APIRouter()


# ========================================
# Request/Response Models
# ========================================


class EmbeddingGenerateRequest(BaseModel):
    """Request model for embedding generation."""

    source: str = Field(
        "learning_atoms",
        description="Table to generate embeddings for (learning_atoms, concepts, stg_anki_cards)",
    )
    batch_size: int = Field(
        32,
        ge=1,
        le=256,
        description="Batch size for processing",
    )
    regenerate: bool = Field(
        False,
        description="Regenerate embeddings for records that already have them",
    )
    limit: Optional[int] = Field(
        None,
        ge=1,
        description="Maximum records to process",
    )


class EmbeddingGenerateResponse(BaseModel):
    """Response model for embedding generation."""

    success: bool
    total_records: int
    records_processed: int
    records_skipped: int = 0
    records_failed: int = 0
    errors: List[str] = Field(default_factory=list)


class EmbeddingCoverageResponse(BaseModel):
    """Response model for embedding coverage statistics."""

    learning_atoms: Dict[str, Any]
    concepts: Dict[str, Any]
    stg_anki_cards: Dict[str, Any]


class DuplicateMatch(BaseModel):
    """A pair of semantically similar atoms."""

    atom_id_1: str
    atom_id_2: str
    front_1: str
    front_2: str
    similarity_score: float


class DuplicatesResponse(BaseModel):
    """Response model for duplicate detection."""

    total_found: int
    threshold: float
    duplicates: List[DuplicateMatch]


class DuplicateStatsResponse(BaseModel):
    """Response model for duplicate statistics."""

    total: int
    by_status: Dict[str, Dict[str, Any]]


class PrerequisiteSuggestionModel(BaseModel):
    """A suggested prerequisite relationship."""

    source_atom_id: str
    target_concept_id: str
    concept_name: str
    concept_definition: Optional[str]
    similarity_score: float
    confidence: str


class PrerequisitesResponse(BaseModel):
    """Response model for prerequisite inference."""

    total_suggestions: int
    suggestions: List[PrerequisiteSuggestionModel]


class PrerequisiteStatsResponse(BaseModel):
    """Response model for prerequisite statistics."""

    total: int
    by_status: Dict[str, int]
    by_confidence: Dict[str, int]


class ClusterInfo(BaseModel):
    """Information about a knowledge cluster."""

    cluster_id: str
    name: str
    size: int
    silhouette_score: Optional[float]
    sample_fronts: List[str]


class ClusteringRequest(BaseModel):
    """Request model for clustering operation."""

    n_clusters: int = Field(10, ge=2, le=100, description="Number of clusters to create")
    concept_area_id: Optional[str] = Field(None, description="Filter to specific concept area")


class ClusteringResponse(BaseModel):
    """Response model for clustering operation."""

    success: bool
    n_clusters: int
    clusters: List[ClusterInfo]


# ========================================
# Embedding Endpoints
# ========================================


@router.post(
    "/embeddings/generate",
    response_model=EmbeddingGenerateResponse,
    summary="Generate embeddings",
)
def generate_embeddings(
    request: EmbeddingGenerateRequest,
    db: Session = Depends(get_session),
) -> EmbeddingGenerateResponse:
    """
    Generate semantic embeddings for atoms that don't have them yet.

    Uses all-MiniLM-L6-v2 model (384 dimensions) from sentence-transformers.
    Embeddings are stored in the database for similarity queries.

    Supported sources:
    - learning_atoms: Flashcard embeddings (front + back combined)
    - concepts: Concept definition embeddings
    - stg_anki_cards: Staging table embeddings
    """
    logger.info(f"Embedding generation requested: source={request.source}, batch={request.batch_size}")

    try:
        from src.semantic import BatchEmbeddingProcessor

        processor = BatchEmbeddingProcessor(db)
        result = processor.generate_embeddings(
            source=request.source,
            batch_size=request.batch_size,
            regenerate=request.regenerate,
            limit=request.limit,
        )

        return EmbeddingGenerateResponse(**result)

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as exc:
        logger.exception("Failed to generate embeddings")
        raise HTTPException(status_code=500, detail=str(exc))


@router.get(
    "/embeddings/coverage",
    response_model=EmbeddingCoverageResponse,
    summary="Get embedding coverage",
)
def get_embedding_coverage(
    db: Session = Depends(get_session),
) -> EmbeddingCoverageResponse:
    """
    Get embedding coverage statistics for all supported tables.

    Shows how many records have embeddings vs total records.
    """
    try:
        from src.semantic import BatchEmbeddingProcessor

        processor = BatchEmbeddingProcessor(db)
        coverage = processor.get_embedding_coverage()

        return EmbeddingCoverageResponse(**coverage)

    except Exception as exc:
        logger.exception("Failed to get embedding coverage")
        raise HTTPException(status_code=500, detail=str(exc))


# ========================================
# Duplicate Detection Endpoints
# ========================================


@router.get(
    "/duplicates",
    response_model=DuplicatesResponse,
    summary="Find semantic duplicates",
)
def find_semantic_duplicates(
    threshold: float = Query(0.85, ge=0.5, le=1.0, description="Similarity threshold"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum results"),
    concept_id: Optional[str] = Query(None, description="Filter to specific concept"),
    db: Session = Depends(get_session),
) -> DuplicatesResponse:
    """
    Find semantically similar cards (potential duplicates).

    Cards with cosine similarity above the threshold are returned.
    Default threshold of 0.85 catches true duplicates with different wording.
    """
    logger.info(f"Duplicate detection: threshold={threshold}, limit={limit}")

    try:
        from src.semantic import SemanticSimilarityService

        service = SemanticSimilarityService(db)

        concept_uuid = UUID(concept_id) if concept_id else None
        matches = service.find_semantic_duplicates(
            threshold=threshold,
            limit=limit,
            concept_id=concept_uuid,
        )

        return DuplicatesResponse(
            total_found=len(matches),
            threshold=threshold,
            duplicates=[
                DuplicateMatch(
                    atom_id_1=str(m.atom_id_1),
                    atom_id_2=str(m.atom_id_2),
                    front_1=m.front_1,
                    front_2=m.front_2,
                    similarity_score=m.similarity_score,
                )
                for m in matches
            ],
        )

    except Exception as exc:
        logger.exception("Failed to find duplicates")
        raise HTTPException(status_code=500, detail=str(exc))


@router.get(
    "/duplicates/{atom_id}",
    response_model=DuplicatesResponse,
    summary="Find similar to atom",
)
def find_similar_to_atom(
    atom_id: str,
    threshold: float = Query(0.7, ge=0.5, le=1.0),
    limit: int = Query(10, ge=1, le=100),
    db: Session = Depends(get_session),
) -> DuplicatesResponse:
    """
    Find atoms similar to a specific atom.

    Lower threshold (0.7) is useful for finding related content,
    while higher threshold (0.85+) finds near-duplicates.
    """
    logger.info(f"Finding similar atoms for {atom_id}")

    try:
        from src.semantic import SemanticSimilarityService

        service = SemanticSimilarityService(db)
        matches = service.find_similar_to_atom(
            atom_id=UUID(atom_id),
            threshold=threshold,
            limit=limit,
        )

        return DuplicatesResponse(
            total_found=len(matches),
            threshold=threshold,
            duplicates=[
                DuplicateMatch(
                    atom_id_1=str(m.atom_id_1),
                    atom_id_2=str(m.atom_id_2),
                    front_1=m.front_1,
                    front_2=m.front_2,
                    similarity_score=m.similarity_score,
                )
                for m in matches
            ],
        )

    except Exception as exc:
        logger.exception(f"Failed to find similar atoms for {atom_id}")
        raise HTTPException(status_code=500, detail=str(exc))


@router.post(
    "/duplicates/store",
    summary="Store duplicate pairs",
)
def store_detected_duplicates(
    threshold: float = Query(0.85, ge=0.5, le=1.0),
    limit: int = Query(500, ge=1, le=5000),
    db: Session = Depends(get_session),
) -> Dict[str, Any]:
    """
    Detect and store semantic duplicate pairs in the database.

    Finds all duplicates above threshold and stores them in
    the semantic_duplicates table for review.
    """
    logger.info(f"Storing duplicate pairs: threshold={threshold}")

    try:
        from src.semantic import SemanticSimilarityService

        service = SemanticSimilarityService(db)
        matches = service.find_semantic_duplicates(threshold=threshold, limit=limit)
        stored = service.store_duplicate_pairs(matches)

        return {
            "success": True,
            "pairs_found": len(matches),
            "pairs_stored": stored,
        }

    except Exception as exc:
        logger.exception("Failed to store duplicate pairs")
        raise HTTPException(status_code=500, detail=str(exc))


@router.get(
    "/duplicates/stats",
    response_model=DuplicateStatsResponse,
    summary="Get duplicate statistics",
)
def get_duplicate_stats(
    db: Session = Depends(get_session),
) -> DuplicateStatsResponse:
    """Get statistics about detected duplicates."""
    try:
        from src.semantic import SemanticSimilarityService

        service = SemanticSimilarityService(db)
        stats = service.get_duplicate_stats()

        return DuplicateStatsResponse(**stats)

    except Exception as exc:
        logger.exception("Failed to get duplicate stats")
        raise HTTPException(status_code=500, detail=str(exc))


# ========================================
# Prerequisite Inference Endpoints
# ========================================


@router.post(
    "/prerequisites/infer",
    response_model=PrerequisitesResponse,
    summary="Infer prerequisites",
)
def infer_prerequisites(
    atom_id: Optional[str] = Query(None, description="Specific atom ID, or None for batch"),
    batch_size: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_session),
) -> PrerequisitesResponse:
    """
    Infer missing prerequisite relationships using embeddings.

    If atom_id is provided, infers prerequisites for that specific atom.
    Otherwise, processes a batch of atoms without prerequisites.

    Similarity threshold > 0.7 suggests a prerequisite relationship.
    """
    logger.info(f"Prerequisite inference: atom_id={atom_id}, batch_size={batch_size}")

    try:
        from src.semantic import PrerequisiteInferenceService

        service = PrerequisiteInferenceService(db)

        if atom_id:
            suggestions = service.infer_prerequisites_for_atom(UUID(atom_id))
        else:
            # Run batch inference and return recently generated
            service.infer_all_missing_prerequisites(batch_size=batch_size)
            suggestions = service.get_suggestions_for_review(limit=batch_size)

        return PrerequisitesResponse(
            total_suggestions=len(suggestions),
            suggestions=[
                PrerequisiteSuggestionModel(
                    source_atom_id=str(s.source_atom_id),
                    target_concept_id=str(s.target_concept_id),
                    concept_name=s.concept_name,
                    concept_definition=s.concept_definition,
                    similarity_score=s.similarity_score,
                    confidence=s.confidence,
                )
                for s in suggestions
            ],
        )

    except Exception as exc:
        logger.exception("Failed to infer prerequisites")
        raise HTTPException(status_code=500, detail=str(exc))


@router.get(
    "/prerequisites/suggestions",
    response_model=PrerequisitesResponse,
    summary="Get prerequisite suggestions",
)
def get_prerequisite_suggestions(
    min_confidence: str = Query("medium", description="Minimum confidence (low, medium, high)"),
    limit: int = Query(50, ge=1, le=500),
    db: Session = Depends(get_session),
) -> PrerequisitesResponse:
    """
    Get pending prerequisite suggestions for review.

    Returns suggestions filtered by minimum confidence level.
    """
    try:
        from src.semantic import PrerequisiteInferenceService

        service = PrerequisiteInferenceService(db)
        suggestions = service.get_suggestions_for_review(
            min_confidence=min_confidence,
            limit=limit,
        )

        return PrerequisitesResponse(
            total_suggestions=len(suggestions),
            suggestions=[
                PrerequisiteSuggestionModel(
                    source_atom_id=str(s.source_atom_id),
                    target_concept_id=str(s.target_concept_id),
                    concept_name=s.concept_name,
                    concept_definition=s.concept_definition,
                    similarity_score=s.similarity_score,
                    confidence=s.confidence,
                )
                for s in suggestions
            ],
        )

    except Exception as exc:
        logger.exception("Failed to get prerequisite suggestions")
        raise HTTPException(status_code=500, detail=str(exc))


@router.post(
    "/prerequisites/{atom_id}/accept/{concept_id}",
    summary="Accept prerequisite",
)
def accept_prerequisite(
    atom_id: str,
    concept_id: str,
    db: Session = Depends(get_session),
) -> Dict[str, Any]:
    """Accept a prerequisite suggestion."""
    try:
        from src.semantic import PrerequisiteInferenceService

        service = PrerequisiteInferenceService(db)
        success = service.accept_suggestion(UUID(atom_id), UUID(concept_id))

        return {"success": success}

    except Exception as exc:
        logger.exception("Failed to accept prerequisite")
        raise HTTPException(status_code=500, detail=str(exc))


@router.post(
    "/prerequisites/{atom_id}/reject/{concept_id}",
    summary="Reject prerequisite",
)
def reject_prerequisite(
    atom_id: str,
    concept_id: str,
    notes: Optional[str] = Query(None),
    db: Session = Depends(get_session),
) -> Dict[str, Any]:
    """Reject a prerequisite suggestion."""
    try:
        from src.semantic import PrerequisiteInferenceService

        service = PrerequisiteInferenceService(db)
        success = service.reject_suggestion(UUID(atom_id), UUID(concept_id), notes)

        return {"success": success}

    except Exception as exc:
        logger.exception("Failed to reject prerequisite")
        raise HTTPException(status_code=500, detail=str(exc))


@router.get(
    "/prerequisites/stats",
    response_model=PrerequisiteStatsResponse,
    summary="Get prerequisite statistics",
)
def get_prerequisite_stats(
    db: Session = Depends(get_session),
) -> PrerequisiteStatsResponse:
    """Get statistics about prerequisite suggestions."""
    try:
        from src.semantic import PrerequisiteInferenceService

        service = PrerequisiteInferenceService(db)
        stats = service.get_suggestion_stats()

        return PrerequisiteStatsResponse(**stats)

    except Exception as exc:
        logger.exception("Failed to get prerequisite stats")
        raise HTTPException(status_code=500, detail=str(exc))


# ========================================
# Clustering Endpoints
# ========================================


@router.post(
    "/clusters",
    response_model=ClusteringResponse,
    summary="Create knowledge clusters",
)
def create_clusters(
    request: ClusteringRequest,
    db: Session = Depends(get_session),
) -> ClusteringResponse:
    """
    Create knowledge clusters from atom embeddings.

    Groups semantically related atoms using K-means clustering.
    Useful for discovering topics and adaptive learning paths.
    """
    logger.info(f"Clustering: n_clusters={request.n_clusters}")

    try:
        from src.semantic import ClusteringService

        service = ClusteringService(db)

        concept_area_uuid = UUID(request.concept_area_id) if request.concept_area_id else None
        clusters = service.cluster_atoms(
            n_clusters=request.n_clusters,
            concept_area_id=concept_area_uuid,
        )

        # Store clusters
        cluster_ids = service.store_clusters(clusters)

        # Get cluster info with samples
        cluster_infos = service.list_clusters(limit=request.n_clusters)

        return ClusteringResponse(
            success=True,
            n_clusters=len(clusters),
            clusters=[
                ClusterInfo(
                    cluster_id=str(c.cluster_db_id),
                    name=c.name,
                    size=c.size,
                    silhouette_score=c.silhouette_score,
                    sample_fronts=c.sample_fronts,
                )
                for c in cluster_infos
            ],
        )

    except Exception as exc:
        logger.exception("Failed to create clusters")
        raise HTTPException(status_code=500, detail=str(exc))


@router.get(
    "/clusters",
    response_model=List[ClusterInfo],
    summary="List clusters",
)
def list_clusters(
    active_only: bool = Query(True),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_session),
) -> List[ClusterInfo]:
    """List existing knowledge clusters."""
    try:
        from src.semantic import ClusteringService

        service = ClusteringService(db)
        clusters = service.list_clusters(active_only=active_only, limit=limit)

        return [
            ClusterInfo(
                cluster_id=str(c.cluster_db_id),
                name=c.name,
                size=c.size,
                silhouette_score=c.silhouette_score,
                sample_fronts=c.sample_fronts,
            )
            for c in clusters
        ]

    except Exception as exc:
        logger.exception("Failed to list clusters")
        raise HTTPException(status_code=500, detail=str(exc))


@router.get(
    "/clusters/{cluster_id}/members",
    summary="Get cluster members",
)
def get_cluster_members(
    cluster_id: str,
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_session),
) -> Dict[str, Any]:
    """Get atoms belonging to a specific cluster."""
    try:
        from src.semantic import ClusteringService

        service = ClusteringService(db)
        members = service.get_cluster_members(UUID(cluster_id), limit=limit)

        return {
            "cluster_id": cluster_id,
            "member_count": len(members),
            "members": members,
        }

    except Exception as exc:
        logger.exception(f"Failed to get cluster members for {cluster_id}")
        raise HTTPException(status_code=500, detail=str(exc))


@router.post(
    "/clusters/recluster",
    response_model=ClusteringResponse,
    summary="Re-run clustering",
)
def recluster(
    n_clusters: int = Query(10, ge=2, le=100),
    deactivate_existing: bool = Query(True),
    db: Session = Depends(get_session),
) -> ClusteringResponse:
    """
    Re-run clustering and replace existing clusters.

    Deactivates old clusters and creates new ones from scratch.
    """
    logger.info(f"Reclustering: n_clusters={n_clusters}, deactivate={deactivate_existing}")

    try:
        from src.semantic import ClusteringService

        service = ClusteringService(db)
        cluster_ids = service.recluster(
            n_clusters=n_clusters,
            deactivate_existing=deactivate_existing,
        )

        clusters = service.list_clusters(limit=n_clusters)

        return ClusteringResponse(
            success=True,
            n_clusters=len(cluster_ids),
            clusters=[
                ClusterInfo(
                    cluster_id=str(c.cluster_db_id),
                    name=c.name,
                    size=c.size,
                    silhouette_score=c.silhouette_score,
                    sample_fronts=c.sample_fronts,
                )
                for c in clusters
            ],
        )

    except Exception as exc:
        logger.exception("Failed to recluster")
        raise HTTPException(status_code=500, detail=str(exc))
