"""
Background Anki sync manager for CORTEX.

Provides bidirectional sync with Anki while the CLI is running:
- Pushes new/updated atoms TO Anki
- Pulls FSRS review stats FROM Anki

Runs in a background thread with periodic sync intervals.
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable

from loguru import logger

from src.anki.anki_client import AnkiClient


@dataclass
class SyncStatus:
    """Current sync status."""

    is_running: bool = False
    is_syncing: bool = False
    anki_connected: bool = False
    last_sync_at: datetime | None = None
    last_sync_success: bool = True
    last_push_count: int = 0
    last_pull_count: int = 0
    error_message: str | None = None
    total_syncs: int = 0


@dataclass
class BackgroundAnkiSync:
    """
    Background Anki sync manager.

    Runs periodic sync in a background thread while CORTEX is active.

    Usage:
        sync_manager = BackgroundAnkiSync(interval_seconds=300)
        sync_manager.start()
        # ... CLI runs ...
        sync_manager.stop()
    """

    interval_seconds: int = 300  # 5 minutes default
    min_quality: str = "B"  # Minimum quality for push
    on_sync_complete: Callable[[SyncStatus], None] | None = None

    # Internal state
    _status: SyncStatus = field(default_factory=SyncStatus)
    _thread: threading.Thread | None = field(default=None, repr=False)
    _stop_event: threading.Event = field(default_factory=threading.Event, repr=False)
    _client: AnkiClient | None = field(default=None, repr=False)

    @property
    def status(self) -> SyncStatus:
        """Get current sync status."""
        return self._status

    def start(self) -> bool:
        """
        Start background sync.

        Returns:
            True if started successfully, False if Anki not available
        """
        if self._status.is_running:
            logger.warning("Background sync already running")
            return True

        # Quick connection check with short timeout
        try:
            self._client = AnkiClient(timeout=5)  # Short timeout for check
            connected = self._client.check_connection(cache_seconds=0)
        except Exception as exc:
            logger.debug("Anki connection check failed: {}", exc)
            connected = False

        if not connected:
            logger.info("Anki not running - background sync disabled")
            self._status.anki_connected = False
            self._status.is_running = False
            return False

        # Use normal timeout for actual sync operations
        self._client = AnkiClient(timeout=30)
        self._status.anki_connected = True
        self._status.is_running = True
        self._stop_event.clear()

        # Start background thread (initial sync happens in thread)
        self._thread = threading.Thread(
            target=self._sync_loop_with_initial,
            name="anki-background-sync",
            daemon=True,
        )
        self._thread.start()

        logger.info(
            "Background Anki sync started (interval: {}s, min_quality: {})",
            self.interval_seconds,
            self.min_quality,
        )

        return True

    def stop(self) -> None:
        """Stop background sync gracefully."""
        if not self._status.is_running:
            return

        logger.info("Stopping background Anki sync...")
        self._stop_event.set()

        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5.0)

        self._status.is_running = False
        logger.info("Background Anki sync stopped")

    def sync_now(self) -> dict[str, Any]:
        """
        Trigger immediate sync (blocking).

        Returns:
            Sync results dict
        """
        return self._do_sync()

    def _sync_loop_with_initial(self) -> None:
        """Background sync loop - NO initial sync to avoid overwhelming Anki on startup."""
        # DISABLED: Initial sync was overwhelming Anki with thousands of atoms
        # Users should explicitly sync via menu option [9] if needed
        # self._do_sync()

        # Just start the regular interval loop (first sync after interval_seconds)
        self._sync_loop()

    def _sync_loop(self) -> None:
        """Background sync loop."""
        while not self._stop_event.is_set():
            # Wait for interval or stop event
            if self._stop_event.wait(timeout=self.interval_seconds):
                break  # Stop event was set

            # Check if Anki is still connected
            try:
                if self._client and not self._client.check_connection():
                    self._status.anki_connected = False
                    logger.debug("Anki disconnected - skipping sync cycle")
                    continue
            except Exception:
                self._status.anki_connected = False
                continue

            self._status.anki_connected = True
            self._do_sync()

    def _do_sync(self) -> dict[str, Any]:
        """
        Execute sync cycle.

        Returns:
            Sync results dict
        """
        if self._status.is_syncing:
            logger.debug("Sync already in progress - skipping")
            return {"skipped": True}

        self._status.is_syncing = True
        results: dict[str, Any] = {}

        try:
            # Check connection
            if not self._client or not self._client.check_connection():
                self._status.anki_connected = False
                self._status.is_syncing = False
                return {"error": "Anki not connected"}

            self._status.anki_connected = True

            # Import here to avoid circular imports
            from src.anki.pull_service import pull_review_stats
            from src.anki.push_service import push_clean_atoms

            # Push new/updated atoms TO Anki
            logger.debug("Background sync: pushing atoms to Anki...")
            try:
                push_result = push_clean_atoms(
                    anki_client=self._client,
                    min_quality=self.min_quality,
                    incremental=True,  # Only push new/changed
                )
                results["push"] = push_result
                self._status.last_push_count = (
                    push_result.get("created", 0) + push_result.get("updated", 0)
                )
            except Exception as exc:
                logger.warning("Push failed: {}", exc)
                results["push_error"] = str(exc)

            # Pull review stats FROM Anki
            logger.debug("Background sync: pulling stats from Anki...")
            try:
                pull_result = pull_review_stats(anki_client=self._client)
                results["pull"] = pull_result
                self._status.last_pull_count = pull_result.get("atoms_updated", 0)
            except Exception as exc:
                logger.warning("Pull failed: {}", exc)
                results["pull_error"] = str(exc)

            # Update status
            self._status.last_sync_at = datetime.now()
            self._status.last_sync_success = "push_error" not in results and "pull_error" not in results
            self._status.error_message = results.get("push_error") or results.get("pull_error")
            self._status.total_syncs += 1

            logger.info(
                "Background sync complete: pushed={}, pulled={}",
                self._status.last_push_count,
                self._status.last_pull_count,
            )

            # Notify callback if set
            if self.on_sync_complete:
                try:
                    self.on_sync_complete(self._status)
                except Exception as exc:
                    logger.warning("Sync callback failed: {}", exc)

        except Exception as exc:
            logger.error("Background sync error: {}", exc)
            self._status.last_sync_success = False
            self._status.error_message = str(exc)
            results["error"] = str(exc)

        finally:
            self._status.is_syncing = False

        return results

    def get_status_line(self) -> str:
        """
        Get a short status line for display.

        Returns:
            Status string like "Anki: synced 2m ago (↑3 ↓12)"
        """
        if not self._status.is_running:
            return "Anki: offline"

        if not self._status.anki_connected:
            return "Anki: disconnected"

        if self._status.is_syncing:
            return "Anki: syncing..."

        if self._status.last_sync_at:
            age = datetime.now() - self._status.last_sync_at
            if age.total_seconds() < 60:
                age_str = "just now"
            elif age.total_seconds() < 3600:
                age_str = f"{int(age.total_seconds() / 60)}m ago"
            else:
                age_str = f"{int(age.total_seconds() / 3600)}h ago"

            if self._status.last_sync_success:
                return f"Anki: synced {age_str} (↑{self._status.last_push_count} ↓{self._status.last_pull_count})"
            else:
                return f"Anki: sync failed {age_str}"

        return "Anki: connected"


# Global singleton for easy access
_background_sync: BackgroundAnkiSync | None = None


def get_background_sync() -> BackgroundAnkiSync | None:
    """Get the global background sync instance."""
    return _background_sync


def start_background_sync(
    interval_seconds: int = 300,
    min_quality: str = "B",
    on_sync_complete: Callable[[SyncStatus], None] | None = None,
) -> BackgroundAnkiSync:
    """
    Start the global background sync manager.

    Args:
        interval_seconds: Sync interval in seconds (default 5 minutes)
        min_quality: Minimum quality grade for push (default B)
        on_sync_complete: Optional callback when sync completes

    Returns:
        The BackgroundAnkiSync instance
    """
    global _background_sync

    if _background_sync and _background_sync.status.is_running:
        return _background_sync

    _background_sync = BackgroundAnkiSync(
        interval_seconds=interval_seconds,
        min_quality=min_quality,
        on_sync_complete=on_sync_complete,
    )
    _background_sync.start()

    return _background_sync


def stop_background_sync() -> None:
    """Stop the global background sync manager."""
    global _background_sync

    if _background_sync:
        _background_sync.stop()
        _background_sync = None
