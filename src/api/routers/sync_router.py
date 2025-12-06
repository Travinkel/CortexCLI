"""
Sync operations router.

Endpoints for triggering Notion sync, Anki push/pull, and checking sync status.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict

from fastapi import APIRouter, HTTPException
from loguru import logger
from pydantic import BaseModel

from config import get_settings

router = APIRouter()
settings = get_settings()


# ========================================
# Request/Response Models
# ========================================


class SyncRequest(BaseModel):
    """Request model for sync operations."""

    dry_run: bool = False
    incremental: bool = True
    parallel: bool = False


class SyncResponse(BaseModel):
    """Response model for sync operations."""

    success: bool
    message: str
    stats: Dict[str, Any]
    timestamp: str = datetime.utcnow().isoformat()


class SyncStatusResponse(BaseModel):
    """Response model for sync status."""

    last_sync: str | None
    next_sync: str | None
    status: str
    configured_databases: list[str]


# ========================================
# Sync Endpoints
# ========================================


@router.post("/notion", response_model=SyncResponse, summary="Sync from Notion to PostgreSQL")
def sync_notion(request: SyncRequest = SyncRequest()) -> SyncResponse:
    """
    Trigger Notion → PostgreSQL sync for all configured databases.

    Fetches from all 18 Notion databases (if configured) and upserts to
    staging tables. Supports incremental sync via last_edited_time.

    **Request Body:**
    - `dry_run` (bool): Preview changes without writing (default: false)
    - `incremental` (bool): Only sync changed pages (default: true)
    - `parallel` (bool): Sync databases concurrently (default: false)

    **Response:**
    - `success` (bool): Whether sync completed successfully
    - `message` (str): Summary message
    - `stats` (dict): Per-entity-type statistics with added/updated/skipped/errors counts
    - `timestamp` (str): ISO timestamp of sync completion
    """
    logger.info(
        f"Notion sync requested "
        f"(dry_run={request.dry_run}, incremental={request.incremental}, parallel={request.parallel})"
    )

    try:
        from src.sync.sync_service import SyncService
        from src.sync.notion_client import NotionClient

        # Create service
        sync_service = SyncService(notion_client=NotionClient())

        # Execute sync
        results = sync_service.sync_all_databases(
            incremental=request.incremental,
            dry_run=request.dry_run,
            parallel=request.parallel,
        )

        # Calculate totals
        total_added = sum(r.get("added", 0) for r in results.values())
        total_updated = sum(r.get("updated", 0) for r in results.values())
        total_skipped = sum(r.get("skipped", 0) for r in results.values())
        total_errors = sum(r.get("errors", 0) for r in results.values())

        success = total_errors == 0

        message = (
            f"Synced {len(results)} entity types: "
            f"{total_added} added, {total_updated} updated, {total_skipped} skipped"
        )
        if total_errors > 0:
            message += f", {total_errors} errors"

        return SyncResponse(
            success=success,
            message=message,
            stats={
                "totals": {
                    "added": total_added,
                    "updated": total_updated,
                    "skipped": total_skipped,
                    "errors": total_errors,
                },
                "by_entity": results,
            },
        )

    except Exception as e:
        logger.exception("Sync failed with exception")
        raise HTTPException(
            status_code=500,
            detail=f"Sync failed: {str(e)}",
        )


@router.post("/anki/push", response_model=SyncResponse, summary="Push clean atoms to Anki")
def sync_anki_push(
    dry_run: bool = False,
    min_quality: str = "B",
) -> SyncResponse:
    """
    Push clean atoms from PostgreSQL to Anki.

    Only pushes cards with quality grade >= min_quality.
    Creates new cards and updates existing ones via AnkiConnect.

    **Phase 4 Implementation Required**
    """
    logger.info(f"Anki push requested (min_quality={min_quality})")

    # TODO: Phase 4 - Implement with AnkiClient
    raise HTTPException(
        status_code=501,
        detail="Anki push not yet implemented (Phase 4: Anki Integration)",
    )


@router.post("/anki/pull", response_model=SyncResponse, summary="Pull FSRS stats from Anki")
def sync_anki_pull(
    dry_run: bool = False,
    deck: str | None = None,
) -> SyncResponse:
    """
    Pull FSRS stats from Anki to PostgreSQL.

    Fetches ease_factor, interval, stability, retrievability, etc.
    Updates learning_atoms table with latest Anki metadata.

    **Phase 4 Implementation Required**
    """
    logger.info(f"Anki pull requested (deck={deck or 'default'})")

    # TODO: Phase 4 - Implement with AnkiClient
    raise HTTPException(
        status_code=501,
        detail="Anki pull not yet implemented (Phase 4: Anki Integration)",
    )


@router.post("/all", response_model=SyncResponse, summary="Full sync pipeline")
def sync_all(request: SyncRequest = SyncRequest()) -> SyncResponse:
    """
    Run full sync pipeline: Notion → PostgreSQL → Clean → Anki.

    Orchestrates:
    1. Notion → PostgreSQL (staging)
    2. Cleaning pipeline (staging → canonical)
    3. Push to Anki (canonical → AnkiConnect)
    4. Pull FSRS stats (Anki → canonical)

    **Phase 2-4 Implementation Required**
    """
    logger.info("Full sync pipeline requested")

    # TODO: Phase 2-4 - Implement full pipeline
    raise HTTPException(
        status_code=501,
        detail="Full sync pipeline not yet implemented (Phases 2-4)",
    )


@router.get("/status", response_model=SyncStatusResponse, summary="Get sync status")
def get_sync_status() -> SyncStatusResponse:
    """
    Get current sync status and configuration.

    Returns information about last sync, next scheduled sync,
    and configured Notion databases.

    **Response:**
    - `last_sync` (str): ISO timestamp of most recent sync across all entity types
    - `next_sync` (str): ISO timestamp of next scheduled sync (if auto-sync enabled)
    - `status` (str): Current sync status ("ready", "syncing", "error")
    - `configured_databases` (list): Names of configured Notion databases
    """
    configured_dbs = list(settings.get_configured_notion_databases().keys())

    # Query last sync timestamp across all entity types
    last_sync_timestamp: str | None = None
    try:
        from src.sync.sync_service import SyncService

        sync_service = SyncService()

        # Find most recent sync across all entity types
        most_recent = None
        for entity_type in configured_dbs:
            last_time = sync_service.get_last_sync_time(entity_type)
            if last_time:
                if most_recent is None or last_time > most_recent:
                    most_recent = last_time

        if most_recent:
            last_sync_timestamp = most_recent.isoformat()

    except Exception as e:
        logger.warning(f"Failed to query last sync time: {e}")

    # Calculate next sync if auto-sync enabled
    next_sync_timestamp: str | None = None
    if settings.sync_interval_minutes > 0 and last_sync_timestamp:
        from datetime import datetime, timedelta

        last_sync_dt = datetime.fromisoformat(last_sync_timestamp)
        next_sync_dt = last_sync_dt + timedelta(minutes=settings.sync_interval_minutes)
        next_sync_timestamp = next_sync_dt.isoformat()

    return SyncStatusResponse(
        last_sync=last_sync_timestamp,
        next_sync=next_sync_timestamp,
        status="ready",
        configured_databases=configured_dbs,
    )
