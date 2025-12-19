"""
Write-protection adapter for Notion API operations.

This module provides a safe wrapper around NotionClient that:
- Enforces PROTECT_NOTION setting for all write operations
- Validates [Computed] field naming convention
- Provides clear logging for bidirectional sync operations
- Handles the sync-back of PostgreSQL computed values

Architectural Pattern:
    Notion: Authoring + GUI
    PostgreSQL: Computation + Processing
    Adapter: Safety layer for writes

Field Categories:
    - BIDIRECTIONAL: User editable in both systems (last-write-wins)
    - COMPUTED: PostgreSQL-owned, synced back with [Computed] prefix (overwrite)
    - NOTION_ONLY: Authored in Notion, never written by PostgreSQL
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from loguru import logger

from config import Settings, get_settings
from src.sync.notion_client import NotionClient


class NotionAdapter:
    """
    Safe wrapper around NotionClient with write protection.

    Responsibilities:
    - Enforce PROTECT_NOTION setting globally
    - Validate [Computed] prefix on computed fields
    - Log all write operations with clear intent
    - Provide specialized methods for sync-back operations
    """

    # Fields that are BIDIRECTIONAL (editable in both systems)
    BIDIRECTIONAL_FIELDS = {
        "Status",  # Can change in Notion or via API
        "Tags",  # Can be added in either place
        "Notes",  # Free-form annotations
        "Comments",  # User comments
    }

    # Computed field prefix (must be present on all PostgreSQL-computed fields)
    COMPUTED_PREFIX = "[Computed]"

    def __init__(self, settings: Settings | None = None):
        """
        Initialize the adapter.

        Args:
            settings: Optional settings instance (uses get_settings() if None)
        """
        self._settings = settings or get_settings()
        self._client = NotionClient(settings=self._settings)
        logger.info(f"NotionAdapter initialized (PROTECT_NOTION={self._settings.protect_notion})")

    # ========================================
    # Read Operations (pass-through)
    # ========================================

    def fetch_flashcards(self) -> list[dict[str, Any]]:
        """Fetch all flashcards from Notion."""
        return self._client.fetch_flashcards()

    def fetch_concepts(self) -> list[dict[str, Any]]:
        """Fetch all concepts from Notion."""
        return self._client.fetch_concepts()

    def fetch_concept_areas(self) -> list[dict[str, Any]]:
        """Fetch all concept areas from Notion."""
        return self._client.fetch_concept_areas()

    def fetch_concept_clusters(self) -> list[dict[str, Any]]:
        """Fetch all concept clusters from Notion."""
        return self._client.fetch_concept_clusters()

    def fetch_modules(self) -> list[dict[str, Any]]:
        """Fetch all modules from Notion."""
        return self._client.fetch_modules()

    def fetch_tracks(self) -> list[dict[str, Any]]:
        """Fetch all tracks from Notion."""
        return self._client.fetch_tracks()

    def fetch_programs(self) -> list[dict[str, Any]]:
        """Fetch all programs from Notion."""
        return self._client.fetch_programs()

    def fetch_activities(self) -> list[dict[str, Any]]:
        """Fetch all activities from Notion."""
        return self._client.fetch_activities()

    def fetch_sessions(self) -> list[dict[str, Any]]:
        """Fetch all sessions from Notion."""
        return self._client.fetch_sessions()

    def fetch_quizzes(self) -> list[dict[str, Any]]:
        """Fetch all quizzes from Notion."""
        return self._client.fetch_quizzes()

    def fetch_critical_skills(self) -> list[dict[str, Any]]:
        """Fetch all critical skills from Notion."""
        return self._client.fetch_critical_skills()

    def fetch_resources(self) -> list[dict[str, Any]]:
        """Fetch all resources from Notion."""
        return self._client.fetch_resources()

    def fetch_mental_models(self) -> list[dict[str, Any]]:
        """Fetch all mental models from Notion."""
        return self._client.fetch_mental_models()

    def fetch_evidence(self) -> list[dict[str, Any]]:
        """Fetch all evidence from Notion."""
        return self._client.fetch_evidence()

    def fetch_brain_regions(self) -> list[dict[str, Any]]:
        """Fetch all brain regions from Notion."""
        return self._client.fetch_brain_regions()

    def fetch_training_protocols(self) -> list[dict[str, Any]]:
        """Fetch all training protocols from Notion."""
        return self._client.fetch_training_protocols()

    def fetch_practice_logs(self) -> list[dict[str, Any]]:
        """Fetch all practice logs from Notion."""
        return self._client.fetch_practice_logs()

    def fetch_assessments(self) -> list[dict[str, Any]]:
        """Fetch all assessments from Notion."""
        return self._client.fetch_assessments()

    def fetch_all(self) -> dict[str, list[dict[str, Any]]]:
        """Fetch all configured databases in bulk."""
        return self._client.fetch_all()

    def fetch_page_content(self, page_id: str) -> str:
        """Fetch the full content of a Notion page."""
        return self._client.fetch_page_content(page_id)

    # ========================================
    # Write Operations (protected)
    # ========================================

    def sync_computed_fields(
        self, page_id: str, computed_values: dict[str, Any], dry_run: bool = False
    ) -> bool:
        """
        Sync PostgreSQL-computed values back to Notion.

        This is the PRIMARY method for writing computed fields back to Notion.
        All field names MUST have the [Computed] prefix.

        Args:
            page_id: Notion page ID
            computed_values: Dict of field_name -> value (all names must have [Computed] prefix)
            dry_run: If True, log but don't actually update

        Returns:
            True if update succeeded (or was skipped due to protection), False on error

        Example:
            adapter.sync_computed_fields(
                page_id="abc123",
                computed_values={
                    "[Computed] Quality Grade": "A",
                    "[Computed] Is Atomic": True,
                    "[Computed] Mastery Score": 85.5,
                    "[Computed] Due Date": "2025-12-03",
                }
            )
        """
        # Validate all field names have [Computed] prefix
        invalid_fields = [
            name for name in computed_values if not name.startswith(self.COMPUTED_PREFIX)
        ]
        if invalid_fields:
            logger.error(
                f"Computed field names must start with '{self.COMPUTED_PREFIX}': {invalid_fields}"
            )
            return False

        # Check PROTECT_NOTION setting
        if self._settings.protect_notion:
            logger.warning(
                f"Skipping computed field sync to page {page_id}: PROTECT_NOTION=true "
                f"(would update: {list(computed_values.keys())})"
            )
            return True  # Not an error, just protected

        # Apply dry_run override
        effective_dry_run = dry_run or self._settings.dry_run
        if effective_dry_run:
            logger.info(f"DRY RUN: Would sync computed fields to page {page_id}: {computed_values}")
            return True

        # Build Notion properties structure
        properties = self._build_notion_properties(computed_values)

        # Add Last Synced timestamp
        properties[f"{self.COMPUTED_PREFIX} Last Synced"] = {
            "date": {"start": datetime.now().isoformat()}
        }

        # Execute update
        logger.info(f"Syncing {len(computed_values)} computed fields to Notion page {page_id}")
        result = self._client.update_page(page_id, properties)

        if result:
            logger.debug(f"Successfully synced computed fields to {page_id}")
            return True
        else:
            logger.error(f"Failed to sync computed fields to {page_id}")
            return False

    def update_bidirectional_field(
        self,
        page_id: str,
        field_name: str,
        value: Any,
        source: str = "postgresql",
        dry_run: bool = False,
    ) -> bool:
        """
        Update a bidirectional field (editable in both systems).

        Uses last-write-wins strategy. Fields in BIDIRECTIONAL_FIELDS can be
        edited in Notion or via API.

        Args:
            page_id: Notion page ID
            field_name: Name of the field (must be in BIDIRECTIONAL_FIELDS)
            value: New value
            source: "notion" or "postgresql" (where the change originated)
            dry_run: If True, log but don't actually update

        Returns:
            True if update succeeded, False on error
        """
        if field_name not in self.BIDIRECTIONAL_FIELDS:
            logger.error(
                f"Field '{field_name}' is not in BIDIRECTIONAL_FIELDS. "
                f"Use sync_computed_fields() for computed fields."
            )
            return False

        # Check PROTECT_NOTION if source is PostgreSQL
        if source == "postgresql" and self._settings.protect_notion:
            logger.warning(
                f"Skipping bidirectional field update to page {page_id}: PROTECT_NOTION=true "
                f"(field: {field_name})"
            )
            return True

        # Apply dry_run override
        effective_dry_run = dry_run or self._settings.dry_run
        if effective_dry_run:
            logger.info(
                f"DRY RUN: Would update bidirectional field '{field_name}' "
                f"on page {page_id} to: {value}"
            )
            return True

        # Build properties
        properties = self._build_notion_properties({field_name: value})

        # Execute update
        logger.info(
            f"Updating bidirectional field '{field_name}' on page {page_id} (source: {source})"
        )
        result = self._client.update_page(page_id, properties)

        if result:
            logger.debug(f"Successfully updated field '{field_name}' on {page_id}")
            return True
        else:
            logger.error(f"Failed to update field '{field_name}' on {page_id}")
            return False

    def bulk_sync_computed_fields(
        self, updates: list[dict[str, Any]], dry_run: bool = False
    ) -> dict[str, int]:
        """
        Sync computed fields for multiple pages in bulk.

        Args:
            updates: List of dicts with 'page_id' and 'computed_values' keys
            dry_run: If True, log but don't actually update

        Returns:
            Dict with 'success', 'failed', 'skipped' counts

        Example:
            results = adapter.bulk_sync_computed_fields([
                {
                    "page_id": "abc123",
                    "computed_values": {
                        "[Computed] Quality Grade": "A",
                        "[Computed] Mastery Score": 85.5,
                    }
                },
                {
                    "page_id": "def456",
                    "computed_values": {
                        "[Computed] Quality Grade": "B",
                        "[Computed] Mastery Score": 72.0,
                    }
                }
            ])
        """
        stats = {"success": 0, "failed": 0, "skipped": 0}

        logger.info(f"Starting bulk sync of computed fields for {len(updates)} pages")

        for update in updates:
            page_id = update.get("page_id")
            computed_values = update.get("computed_values", {})

            if not page_id or not computed_values:
                logger.warning(f"Skipping invalid update entry: {update}")
                stats["skipped"] += 1
                continue

            success = self.sync_computed_fields(page_id, computed_values, dry_run)
            if success:
                stats["success"] += 1
            else:
                stats["failed"] += 1

        logger.info(
            f"Bulk sync complete: {stats['success']} success, "
            f"{stats['failed']} failed, {stats['skipped']} skipped"
        )
        return stats

    # ========================================
    # Helper Methods
    # ========================================

    def _build_notion_properties(self, field_values: dict[str, Any]) -> dict[str, Any]:
        """
        Build Notion API properties structure from field values.

        Automatically detects value types and builds correct Notion property format.

        Args:
            field_values: Dict of field_name -> python_value

        Returns:
            Dict formatted for Notion API properties parameter
        """
        properties = {}

        for field_name, value in field_values.items():
            if value is None:
                # Explicitly clear the field
                properties[field_name] = self._get_empty_property_for_type(field_name)
            elif isinstance(value, bool):
                properties[field_name] = {"checkbox": value}
            elif isinstance(value, (int, float)):
                properties[field_name] = {"number": value}
            elif isinstance(value, str):
                # Could be text, select, or date - try to infer
                if self._is_iso_date(value):
                    properties[field_name] = {"date": {"start": value}}
                elif (
                    field_name.endswith("(select)")
                    or "Grade" in field_name
                    or "Status" in field_name
                ):
                    properties[field_name] = {"select": {"name": value}}
                else:
                    # Rich text
                    properties[field_name] = {
                        "rich_text": [{"type": "text", "text": {"content": value}}]
                    }
            elif isinstance(value, list):
                # Multi-select or relation
                if value and isinstance(value[0], str):
                    # Could be multi-select or relation IDs
                    if all(len(v) == 32 and "-" in v for v in value):  # UUIDs
                        properties[field_name] = {"relation": [{"id": v} for v in value]}
                    else:
                        properties[field_name] = {"multi_select": [{"name": v} for v in value]}
            else:
                logger.warning(f"Unknown value type for field '{field_name}': {type(value)}")

        return properties

    def _get_empty_property_for_type(self, field_name: str) -> dict[str, Any]:
        """Get an empty Notion property to clear a field."""
        # For now, return empty rich_text (safest default)
        return {"rich_text": []}

    def _is_iso_date(self, value: str) -> bool:
        """Check if a string looks like an ISO date."""
        try:
            datetime.fromisoformat(value.replace("Z", "+00:00"))
            return True
        except (ValueError, AttributeError):
            return False

    @property
    def is_write_protected(self) -> bool:
        """Check if write operations are currently protected."""
        return self._settings.protect_notion

    @property
    def is_dry_run(self) -> bool:
        """Check if dry run mode is enabled."""
        return self._settings.dry_run
