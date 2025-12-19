"""
Sync Service - Orchestrates Notion → PostgreSQL synchronization.

Core responsibilities:
- Fetch data from all configured Notion databases
- Upsert to staging tables with deduplication
- Track sync runs and timestamps for incremental sync
- Handle errors gracefully with transaction rollback
- Support dry-run mode and progress callbacks
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from typing import Any

from loguru import logger
from sqlalchemy import func, select

from config import get_settings
from src.db.database import session_scope
from src.db.models.staging import (
    StgNotionConcept,
    StgNotionConceptArea,
    StgNotionConceptCluster,
    StgNotionFlashcard,
    StgNotionModule,
    StgNotionProgram,
    StgNotionTrack,
)
from src.sync.notion_client import NotionClient


class SyncStats:
    """Statistics for a sync operation."""

    def __init__(self) -> None:
        self.added = 0
        self.updated = 0
        self.skipped = 0
        self.errors = 0
        self.start_time = datetime.now()
        self.end_time: datetime | None = None
        self.error_details: list[str] = []

    def finish(self) -> None:
        """Mark sync as finished."""
        self.end_time = datetime.now()

    def duration_seconds(self) -> float:
        """Calculate duration in seconds."""
        end = self.end_time or datetime.now()
        return (end - self.start_time).total_seconds()

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for logging/API responses."""
        return {
            "added": self.added,
            "updated": self.updated,
            "skipped": self.skipped,
            "errors": self.errors,
            "duration_seconds": round(self.duration_seconds(), 2),
            "error_details": self.error_details[:10],  # Limit to 10 errors
        }


class SyncService:
    """
    Orchestrates Notion → PostgreSQL synchronization.

    Features:
    - Incremental sync (only changed pages)
    - Transaction safety (rollback on errors)
    - Dry-run mode (log without writes)
    - Progress callbacks (for CLI/API)
    - Parallel sync (concurrent database fetching)
    - Audit logging (sync runs tracked)
    """

    # Map entity types to staging model classes
    MODEL_MAPPING = {
        "flashcards": StgNotionFlashcard,
        "concepts": StgNotionConcept,
        "concept_areas": StgNotionConceptArea,
        "concept_clusters": StgNotionConceptCluster,
        "modules": StgNotionModule,
        "tracks": StgNotionTrack,
        "programs": StgNotionProgram,
    }

    def __init__(
        self,
        notion_client: NotionClient | None = None,
        progress_callback: Callable[[str, int, int], None] | None = None,
    ) -> None:
        """
        Initialize sync service.

        Args:
            notion_client: NotionClient instance (created if not provided)
            progress_callback: Optional callback(entity_type, current, total)
        """
        self._settings = get_settings()
        self._notion = notion_client or NotionClient()
        self._progress_callback = progress_callback

    # =========================================================================
    # PUBLIC API
    # =========================================================================

    def sync_all_databases(
        self,
        incremental: bool = True,
        dry_run: bool = False,
        parallel: bool = False,
    ) -> dict[str, dict[str, int]]:
        """
        Sync all configured Notion databases to PostgreSQL.

        Args:
            incremental: Only sync pages modified since last sync
            dry_run: Log actions without writing to database
            parallel: Fetch databases concurrently (faster but higher API load)

        Returns:
            Dictionary of {entity_type: {added: int, updated: int, skipped: int, errors: int}}
        """
        if not self._notion.ready:
            logger.error("Notion client not ready; cannot sync")
            return {}

        configured = self._settings.get_configured_notion_databases()
        if not configured:
            logger.warning("No Notion databases configured; nothing to sync")
            return {}

        logger.info(
            f"Starting {'incremental' if incremental else 'full'} sync "
            f"of {len(configured)} databases (parallel={parallel}, dry_run={dry_run})"
        )

        results: dict[str, dict[str, int]] = {}

        if parallel:
            results = self._sync_all_parallel(configured, incremental, dry_run)
        else:
            results = self._sync_all_sequential(configured, incremental, dry_run)

        # Log summary
        total_added = sum(r.get("added", 0) for r in results.values())
        total_updated = sum(r.get("updated", 0) for r in results.values())
        total_skipped = sum(r.get("skipped", 0) for r in results.values())
        total_errors = sum(r.get("errors", 0) for r in results.values())

        logger.info(
            f"Sync complete: {total_added} added, {total_updated} updated, "
            f"{total_skipped} skipped, {total_errors} errors"
        )

        return results

    def sync_database(
        self,
        entity_type: str,
        incremental: bool = True,
        dry_run: bool = False,
    ) -> tuple[int, int]:
        """
        Sync a single Notion database to PostgreSQL.

        Args:
            entity_type: Database type (e.g., "flashcards", "concepts")
            incremental: Only sync pages modified since last sync
            dry_run: Log actions without writing to database

        Returns:
            Tuple of (added_count, updated_count)

        Raises:
            ValueError: If entity_type is not configured or not supported
        """
        # Validate entity type
        if entity_type not in self.MODEL_MAPPING:
            raise ValueError(
                f"Unsupported entity type: {entity_type}. "
                f"Supported: {list(self.MODEL_MAPPING.keys())}"
            )

        configured = self._settings.get_configured_notion_databases()
        db_id = configured.get(entity_type)
        if not db_id:
            raise ValueError(f"No database ID configured for {entity_type}")

        logger.info(f"Starting sync for {entity_type} (incremental={incremental})")

        # Fetch from Notion
        fetch_method = getattr(self._notion, f"fetch_{entity_type}", None)
        if not callable(fetch_method):
            raise ValueError(f"No fetch method for {entity_type}")

        pages = fetch_method()
        logger.info(f"Fetched {len(pages)} pages from Notion for {entity_type}")

        if not pages:
            logger.info(f"No pages to sync for {entity_type}")
            return (0, 0)

        # Get last sync time if incremental
        last_sync_time = None
        if incremental:
            last_sync_time = self.get_last_sync_time(entity_type)
            if last_sync_time:
                logger.info(
                    f"Incremental sync since {last_sync_time.isoformat()} for {entity_type}"
                )

        # Upsert to staging
        stats = self._upsert_to_staging(
            entity_type=entity_type,
            pages=pages,
            last_sync_time=last_sync_time,
            dry_run=dry_run,
        )

        # Record sync run
        if not dry_run:
            self.record_sync_run(entity_type, stats.to_dict())

        logger.info(
            f"Sync complete for {entity_type}: "
            f"{stats.added} added, {stats.updated} updated, {stats.skipped} skipped"
        )

        return (stats.added, stats.updated)

    def get_last_sync_time(self, entity_type: str) -> datetime | None:
        """
        Get the timestamp of the last successful sync for an entity type.

        Args:
            entity_type: Database type (e.g., "flashcards")

        Returns:
            Datetime of last sync, or None if never synced
        """
        model = self.MODEL_MAPPING.get(entity_type)
        if not model:
            return None

        try:
            with session_scope() as session:
                # Query max last_synced_at from staging table
                result = session.execute(
                    select(func.max(model.last_synced_at))
                ).scalar_one_or_none()
                return result
        except Exception as e:
            logger.warning(f"Failed to get last sync time for {entity_type}: {e}")
            return None

    def record_sync_run(self, entity_type: str, stats: dict[str, Any]) -> None:
        """
        Record a sync run in the audit log (future: sync_runs table).

        Args:
            entity_type: Database type
            stats: Statistics dictionary from SyncStats.to_dict()
        """
        # TODO: Create sync_runs table in migration 003_sync_audit.sql
        # For now, just log
        logger.info(f"Sync run recorded for {entity_type}: {stats}")

    # =========================================================================
    # INTERNAL HELPERS
    # =========================================================================

    def _sync_all_sequential(
        self,
        configured: dict[str, str],
        incremental: bool,
        dry_run: bool,
    ) -> dict[str, dict[str, int]]:
        """Sync all databases sequentially (one at a time)."""
        results: dict[str, dict[str, int]] = {}

        for entity_type, db_id in configured.items():
            try:
                added, updated = self.sync_database(
                    entity_type=entity_type,
                    incremental=incremental,
                    dry_run=dry_run,
                )
                results[entity_type] = {
                    "added": added,
                    "updated": updated,
                    "skipped": 0,
                    "errors": 0,
                }
            except Exception as e:
                logger.error(f"Failed to sync {entity_type}: {e}")
                results[entity_type] = {
                    "added": 0,
                    "updated": 0,
                    "skipped": 0,
                    "errors": 1,
                }

        return results

    def _sync_all_parallel(
        self,
        configured: dict[str, str],
        incremental: bool,
        dry_run: bool,
    ) -> dict[str, dict[str, int]]:
        """Sync all databases in parallel using ThreadPoolExecutor."""
        results: dict[str, dict[str, int]] = {}

        with ThreadPoolExecutor(max_workers=4) as executor:
            # Submit all sync tasks
            future_to_entity = {
                executor.submit(
                    self.sync_database,
                    entity_type=entity_type,
                    incremental=incremental,
                    dry_run=dry_run,
                ): entity_type
                for entity_type in configured
            }

            # Collect results as they complete
            for future in as_completed(future_to_entity):
                entity_type = future_to_entity[future]
                try:
                    added, updated = future.result()
                    results[entity_type] = {
                        "added": added,
                        "updated": updated,
                        "skipped": 0,
                        "errors": 0,
                    }
                except Exception as e:
                    logger.error(f"Failed to sync {entity_type}: {e}")
                    results[entity_type] = {
                        "added": 0,
                        "updated": 0,
                        "skipped": 0,
                        "errors": 1,
                    }

        return results

    def _upsert_to_staging(
        self,
        entity_type: str,
        pages: list[dict[str, Any]],
        last_sync_time: datetime | None,
        dry_run: bool,
    ) -> SyncStats:
        """
        Upsert pages to staging table.

        Args:
            entity_type: Database type
            pages: List of raw Notion page dictionaries
            last_sync_time: Filter pages modified after this time (None for all)
            dry_run: Log without writing

        Returns:
            SyncStats with operation counts
        """
        stats = SyncStats()
        model = self.MODEL_MAPPING[entity_type]

        if dry_run:
            logger.info(f"DRY RUN: Would upsert {len(pages)} pages for {entity_type}")
            stats.added = len(pages)
            stats.finish()
            return stats

        try:
            with session_scope() as session:
                for i, page in enumerate(pages):
                    try:
                        # Report progress
                        if self._progress_callback and i % 100 == 0:
                            self._progress_callback(entity_type, i, len(pages))

                        # Extract page metadata
                        page_id = page.get("id", "")
                        if not page_id:
                            logger.warning(f"Skipping page without ID for {entity_type}")
                            stats.skipped += 1
                            continue

                        # Check if page was modified recently (for incremental)
                        if last_sync_time:
                            last_edited = page.get("last_edited_time")
                            if last_edited:
                                last_edited_dt = datetime.fromisoformat(
                                    last_edited.replace("Z", "+00:00")
                                )
                                if last_edited_dt <= last_sync_time:
                                    stats.skipped += 1
                                    continue

                        # Compute content hash for change detection
                        properties = page.get("properties", {})
                        content_hash = self._compute_hash(properties)

                        # Check if page exists
                        existing = session.get(model, page_id)

                        if existing:
                            # Check if content changed
                            if existing.sync_hash == content_hash:
                                stats.skipped += 1
                                continue

                            # Update existing
                            existing.raw_properties = properties
                            existing.last_synced_at = datetime.now()
                            existing.sync_hash = content_hash
                            stats.updated += 1
                        else:
                            # Insert new
                            new_entity = model(
                                notion_page_id=page_id,
                                raw_properties=properties,
                                last_synced_at=datetime.now(),
                                sync_hash=content_hash,
                            )
                            session.add(new_entity)
                            stats.added += 1

                    except Exception as e:
                        logger.error(
                            f"Failed to upsert page {page.get('id', '?')} for {entity_type}: {e}"
                        )
                        stats.errors += 1
                        stats.error_details.append(str(e))
                        continue

                # Final progress callback
                if self._progress_callback:
                    self._progress_callback(entity_type, len(pages), len(pages))

        except Exception as e:
            logger.error(f"Transaction failed for {entity_type}: {e}")
            stats.errors += 1
            stats.error_details.append(str(e))
            raise

        stats.finish()
        return stats

    @staticmethod
    def _compute_hash(data: dict[str, Any]) -> str:
        """Compute SHA256 hash of data for change detection."""
        serialized = json.dumps(data, sort_keys=True, default=str)
        return hashlib.sha256(serialized.encode()).hexdigest()
