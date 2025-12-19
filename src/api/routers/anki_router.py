"""
Anki router for import and management operations.

Endpoints for:
- Importing Anki decks into PostgreSQL staging
- Viewing import statistics
- Managing imported cards
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query
from loguru import logger
from pydantic import BaseModel, Field

router = APIRouter()


# ========================================
# Request/Response Models
# ========================================


class AnkiImportRequest(BaseModel):
    """Request model for Anki deck import."""

    deck_name: str | None = Field(
        None,
        description="Anki deck name to import (default: from config)",
    )
    dry_run: bool = Field(
        False,
        description="Preview import without writing to database",
    )
    quality_analysis: bool = Field(
        True,
        description="Run quality analysis during import (word counts, grading)",
    )


class AnkiImportResponse(BaseModel):
    """Response model for Anki import operation."""

    success: bool
    message: str
    cards_imported: int
    cards_with_fsrs: int = 0
    cards_with_prerequisites: int = 0
    cards_needing_split: int = 0
    grade_distribution: dict[str, int] = Field(
        default_factory=dict,
        description="Quality grade distribution (A/B/C/D/F)",
    )
    import_batch_id: str | None = None
    errors: list[str] = Field(default_factory=list)


class ImportStatsResponse(BaseModel):
    """Response model for import statistics."""

    import_batch_id: str
    deck_name: str
    started_at: str
    completed_at: str | None
    status: str
    cards_imported: int = 0
    cards_with_fsrs: int = 0
    cards_with_prerequisites: int = 0
    cards_needing_split: int = 0
    grade_a_count: int = 0
    grade_b_count: int = 0
    grade_c_count: int = 0
    grade_d_count: int = 0
    grade_f_count: int = 0
    error_message: str | None = None


# ========================================
# Import Endpoints
# ========================================


@router.post("/import", response_model=AnkiImportResponse, summary="Import Anki deck")
def import_anki_deck(request: AnkiImportRequest = AnkiImportRequest()) -> AnkiImportResponse:
    """
    Import all cards from an Anki deck into PostgreSQL staging table.

    Workflow:
    1. Connect to Anki via AnkiConnect (port 8765)
    2. Fetch all cards from specified deck
    3. Extract FSRS scheduling stats
    4. Parse prerequisite tags (tag:prereq:domain:topic:subtopic)
    5. Run quality analysis (if enabled)
    6. Insert into stg_anki_cards table

    The imported cards are stored in the stg_anki_cards staging table
    where they can be analyzed, split, and processed through the
    cleaning pipeline.

    **Returns:**
    - Import statistics including card counts and quality distribution
    - Import batch ID for tracking

    **Requires:**
    - Anki must be running
    - AnkiConnect add-on must be installed
    - Deck must exist in Anki

    **Example Response:**
    ```json
    {
        "success": true,
        "message": "Imported 500 cards from deck 'CCNA Study'",
        "cards_imported": 500,
        "cards_with_fsrs": 432,
        "cards_with_prerequisites": 127,
        "cards_needing_split": 45,
        "grade_distribution": {
            "A": 203,
            "B": 145,
            "C": 75,
            "D": 52,
            "F": 25
        },
        "import_batch_id": "abc-123-def-456"
    }
    ```
    """
    logger.info(
        "Anki import requested: deck={}, dry_run={}, quality_analysis={}",
        request.deck_name,
        request.dry_run,
        request.quality_analysis,
    )

    try:
        # Import service
        from src.anki.import_service import AnkiImportService

        service = AnkiImportService()

        # Check AnkiConnect connection
        if not service.anki_client.check_connection():
            raise HTTPException(
                status_code=503,
                detail="Failed to connect to AnkiConnect. Ensure Anki is running with AnkiConnect add-on installed.",
            )

        # Run import
        result = service.import_deck(
            deck_name=request.deck_name,
            dry_run=request.dry_run,
            quality_analysis=request.quality_analysis,
        )

        if not result.get("success"):
            error = result.get("error", "Unknown error")
            logger.error(f"Import failed: {error}")
            raise HTTPException(status_code=500, detail=error)

        # Build response
        deck_name = request.deck_name or service.settings.anki_deck_name
        message = (
            f"Imported {result['cards_imported']} cards from deck '{deck_name}'"
            if not request.dry_run
            else f"Preview: {result['cards_imported']} cards would be imported from deck '{deck_name}'"
        )

        return AnkiImportResponse(
            success=True,
            message=message,
            cards_imported=result["cards_imported"],
            cards_with_fsrs=result["cards_with_fsrs"],
            cards_with_prerequisites=result["cards_with_prerequisites"],
            cards_needing_split=result["cards_needing_split"],
            grade_distribution=result.get("grade_distribution", {}),
            import_batch_id=service.import_batch_id,
            errors=result.get("errors", []),
        )

    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Unexpected error during Anki import")
        raise HTTPException(
            status_code=500,
            detail=f"Import failed: {str(exc)}",
        )


@router.get(
    "/import/stats/{batch_id}",
    response_model=ImportStatsResponse,
    summary="Get import statistics",
)
def get_import_stats(batch_id: str) -> ImportStatsResponse:
    """
    Get import statistics for a specific batch.

    Returns detailed statistics about a previous import operation,
    including card counts, quality distribution, and any errors.

    **Args:**
    - batch_id: Import batch ID (returned from POST /import)

    **Returns:**
    - Complete import statistics including grade distribution

    **Example Response:**
    ```json
    {
        "import_batch_id": "abc-123-def-456",
        "deck_name": "CCNA Study",
        "started_at": "2025-12-02T10:30:00Z",
        "completed_at": "2025-12-02T10:32:15Z",
        "status": "completed",
        "cards_imported": 500,
        "cards_with_fsrs": 432,
        "cards_with_prerequisites": 127,
        "cards_needing_split": 45,
        "grade_a_count": 203,
        "grade_b_count": 145,
        "grade_c_count": 75,
        "grade_d_count": 52,
        "grade_f_count": 25
    }
    ```
    """
    logger.info("Import stats requested: batch_id={}", batch_id)

    try:
        from src.anki.import_service import AnkiImportService

        service = AnkiImportService()
        stats = service.get_import_stats(batch_id)

        if not stats:
            raise HTTPException(
                status_code=404,
                detail=f"Import batch not found: {batch_id}",
            )

        return ImportStatsResponse(**stats)

    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Failed to fetch import stats")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch stats: {str(exc)}",
        )


@router.get(
    "/import/latest",
    response_model=ImportStatsResponse,
    summary="Get latest import statistics",
)
def get_latest_import() -> ImportStatsResponse:
    """
    Get statistics for the most recent import operation.

    Convenience endpoint for checking the status and results of
    the last import without needing to track the batch ID.

    **Returns:**
    - Statistics for the most recent import batch
    """
    logger.info("Latest import stats requested")

    try:
        from sqlalchemy import text

        from src.db.database import get_db

        db = next(get_db())

        # Query latest import
        query = text("""
            SELECT
                import_batch_id,
                deck_name,
                started_at,
                completed_at,
                status,
                cards_imported,
                cards_with_fsrs,
                cards_with_prerequisites,
                cards_needing_split,
                grade_a_count,
                grade_b_count,
                grade_c_count,
                grade_d_count,
                grade_f_count,
                error_message
            FROM anki_import_log
            ORDER BY started_at DESC
            LIMIT 1
        """)

        result = db.execute(query).fetchone()

        if not result:
            raise HTTPException(
                status_code=404,
                detail="No import history found",
            )

        return ImportStatsResponse(**dict(result._mapping))

    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Failed to fetch latest import")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch latest import: {str(exc)}",
        )


@router.get("/cards/quality", summary="Get quality distribution")
def get_quality_distribution(
    deck: str | None = Query(None, description="Filter by deck name"),
) -> dict[str, Any]:
    """
    Get quality grade distribution for imported cards.

    Returns the count and percentage of cards at each quality grade (A-F),
    helpful for understanding how many cards need improvement or splitting.

    **Query Parameters:**
    - deck: Optional deck name filter

    **Returns:**
    ```json
    {
        "total_cards": 500,
        "distribution": {
            "A": {"count": 203, "percentage": 40.6},
            "B": {"count": 145, "percentage": 29.0},
            "C": {"count": 75, "percentage": 15.0},
            "D": {"count": 52, "percentage": 10.4},
            "F": {"count": 25, "percentage": 5.0}
        },
        "needs_split_count": 45,
        "non_atomic_count": 77
    }
    ```
    """
    logger.info("Quality distribution requested: deck={}", deck)

    try:
        from sqlalchemy import text

        from src.db.database import get_db

        db = next(get_db())

        # Build query with optional deck filter
        where_clause = "WHERE deck_name = :deck" if deck else ""
        params = {"deck": deck} if deck else {}

        query = text(f"""
            SELECT
                quality_grade,
                COUNT(*) as count,
                ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER (), 2) as percentage
            FROM stg_anki_cards
            {where_clause}
            GROUP BY quality_grade
            ORDER BY quality_grade
        """)

        results = db.execute(query, params).fetchall()

        # Count cards needing split
        needs_split_query = text(f"""
            SELECT
                COUNT(*) FILTER (WHERE needs_split = true) as needs_split,
                COUNT(*) FILTER (WHERE is_atomic = false) as non_atomic,
                COUNT(*) as total
            FROM stg_anki_cards
            {where_clause}
        """)

        counts = db.execute(needs_split_query, params).fetchone()

        # Build response
        distribution = {}
        for row in results:
            distribution[row.quality_grade or "Unknown"] = {
                "count": row.count,
                "percentage": float(row.percentage),
            }

        return {
            "total_cards": counts.total if counts else 0,
            "distribution": distribution,
            "needs_split_count": counts.needs_split if counts else 0,
            "non_atomic_count": counts.non_atomic if counts else 0,
        }

    except Exception as exc:
        logger.exception("Failed to fetch quality distribution")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch distribution: {str(exc)}",
        )


@router.get("/cards/prerequisites", summary="Get prerequisite statistics")
def get_prerequisite_stats(
    deck: str | None = Query(None, description="Filter by deck name"),
) -> dict[str, Any]:
    """
    Get statistics about prerequisite tags in imported cards.

    Returns counts of cards with prerequisites, unique prerequisite
    domains/topics, and the prerequisite hierarchy.

    **Returns:**
    ```json
    {
        "cards_with_prerequisites": 127,
        "cards_without_prerequisites": 373,
        "unique_domains": ["cs", "ccna"],
        "unique_topics": ["networking", "security"],
        "prerequisite_hierarchy": [
            {"domain": "cs", "topic": "networking", "card_count": 45},
            {"domain": "ccna", "topic": "routing", "card_count": 32}
        ]
    }
    ```
    """
    logger.info("Prerequisite stats requested: deck={}", deck)

    try:
        from sqlalchemy import text

        from src.db.database import get_db

        db = next(get_db())

        # Build query with optional deck filter
        where_clause = "WHERE deck_name = :deck" if deck else ""
        params = {"deck": deck} if deck else {}

        # Get counts
        count_query = text(f"""
            SELECT
                COUNT(*) FILTER (WHERE has_prerequisites = true) as with_prereqs,
                COUNT(*) FILTER (WHERE has_prerequisites = false) as without_prereqs
            FROM stg_anki_cards
            {where_clause}
        """)

        counts = db.execute(count_query, params).fetchone()

        # Get hierarchy (using view created in migration)
        if deck:
            hierarchy_query = text("""
                SELECT
                    domain,
                    topic,
                    subtopic,
                    card_count
                FROM v_anki_prerequisite_graph
                WHERE prerequisite_tag IN (
                    SELECT UNNEST(prerequisite_tags)
                    FROM stg_anki_cards
                    WHERE deck_name = :deck
                )
                ORDER BY domain, topic, subtopic
                LIMIT 50
            """)
            hierarchy = db.execute(hierarchy_query, params).fetchall()
        else:
            hierarchy_query = text("""
                SELECT
                    domain,
                    topic,
                    subtopic,
                    card_count
                FROM v_anki_prerequisite_graph
                ORDER BY domain, topic, subtopic
                LIMIT 50
            """)
            hierarchy = db.execute(hierarchy_query).fetchall()

        # Build response
        unique_domains = set()
        unique_topics = set()
        hierarchy_list = []

        for row in hierarchy:
            if row.domain:
                unique_domains.add(row.domain)
            if row.topic:
                unique_topics.add(row.topic)

            hierarchy_list.append(
                {
                    "domain": row.domain,
                    "topic": row.topic,
                    "subtopic": row.subtopic,
                    "card_count": row.card_count,
                }
            )

        return {
            "cards_with_prerequisites": counts.with_prereqs if counts else 0,
            "cards_without_prerequisites": counts.without_prereqs if counts else 0,
            "unique_domains": sorted(list(unique_domains)),
            "unique_topics": sorted(list(unique_topics)),
            "prerequisite_hierarchy": hierarchy_list,
        }

    except Exception as exc:
        logger.exception("Failed to fetch prerequisite stats")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch prerequisite stats: {str(exc)}",
        )
