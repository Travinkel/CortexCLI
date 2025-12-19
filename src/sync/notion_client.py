"""
Notion Client - Typed wrapper around the official Notion SDK.

IMPORTANT: Uses official Notion Python SDK (notion_client).
Allowed methods: client.data_sources.query(), client.pages.retrieve(),
                 client.pages.update(), client.pages.create()
"""

from __future__ import annotations

import time
from typing import Any

from loguru import logger
from notion_client import Client

from config import get_settings


class NotionClient:
    """
    Typed wrapper around the official Notion SDK with multi-database support.

    Handles:
    - Pagination for large databases
    - Rate limiting (3 req/sec)
    - Fallback query methods (data_sources → databases)
    - Write protection via PROTECT_NOTION setting
    """

    def __init__(
        self,
        api_key: str | None = None,
    ) -> None:
        self._settings = get_settings()
        self.api_key = api_key or self._settings.notion_api_key
        self._client: Client | None = None
        self._warned_raw_request = False

        if self.api_key:
            self._client = Client(auth=self.api_key, notion_version=self._settings.notion_version)
            logger.info("Notion client initialized")
        else:
            logger.warning("Notion credentials missing. Set NOTION_API_KEY to enable syncing.")

    @property
    def ready(self) -> bool:
        """Check if client is ready to make API calls."""
        return self._client is not None

    # =========================================================================
    # CORE FETCHING
    # =========================================================================

    def fetch_from_database(
        self,
        database_id: str,
        entity_type: str = "pages",
    ) -> list[dict[str, Any]]:
        """
        Generic method to fetch all pages from a Notion database.

        Args:
            database_id: The Notion database ID to query
            entity_type: Entity type for logging (e.g., "flashcards", "concepts")

        Returns:
            List of raw Notion page dictionaries
        """
        if not self._client:
            logger.warning(f"Notion client not ready; returning empty list for {entity_type}")
            return []

        pages = []
        start_cursor: str | None = None
        logger.info(f"Querying Notion database {database_id} for {entity_type}")

        while True:
            response = self._query_any_database(database_id, start_cursor=start_cursor)
            results = response.get("results", [])
            pages.extend(results)

            logger.debug(f"Fetched batch of {len(results)} {entity_type}")

            if not response.get("has_more"):
                break
            start_cursor = response.get("next_cursor")

        logger.info(f"Fetched {len(pages)} {entity_type} from Notion")
        return pages

    def _query_any_database(
        self,
        database_id: str,
        start_cursor: str | None = None,
    ) -> dict:
        """
        Query any Notion database by ID using data_sources API.

        Tries methods in order:
        1. data_sources.query SDK method (if available)
        2. Raw request to data_sources/{id}/query endpoint
        3. databases.query SDK method (fallback)
        4. Raw request to databases/{id}/query (last resort)

        Args:
            database_id: Notion database ID
            start_cursor: Pagination cursor

        Returns:
            Response dict with "results", "has_more", "next_cursor"
        """
        if not self._client:
            return {"results": [], "has_more": False}

        payload = {
            "start_cursor": start_cursor,
            "page_size": 100,
        }

        # 1. Try data_sources.query SDK method
        data_sources = getattr(self._client, "data_sources", None)
        if data_sources is not None:
            query_fn = getattr(data_sources, "query", None)
            if callable(query_fn):
                try:
                    kwargs = dict(payload)
                    kwargs["data_source_id"] = database_id
                    return query_fn(**kwargs)
                except TypeError:
                    pass

        # 2. Raw request to data_sources endpoint
        request_fn = getattr(self._client, "request", None)
        if callable(request_fn):
            body = {k: v for k, v in payload.items() if v is not None}
            try:
                if not self._warned_raw_request:
                    logger.info("Using raw request to data_sources endpoint (SDK lacks wrapper)")
                    self._warned_raw_request = True
                return request_fn(
                    path=f"data_sources/{database_id}/query",
                    method="POST",
                    body=body or {},
                )
            except Exception as e:
                logger.debug(f"Raw data_sources request failed for {database_id}: {e}")

        # 3. Fallback to databases.query
        databases = getattr(self._client, "databases", None)
        if databases is not None:
            query_fn = getattr(databases, "query", None)
            if callable(query_fn):
                try:
                    kwargs = dict(payload)
                    kwargs["database_id"] = database_id
                    return query_fn(**kwargs)
                except Exception as e:
                    logger.debug(f"databases.query failed for {database_id}: {e}")

        # 4. Last resort: raw request to databases endpoint
        if callable(request_fn):
            body = {k: v for k, v in payload.items() if v is not None}
            try:
                return request_fn(
                    path=f"databases/{database_id}/query",
                    method="POST",
                    body=body or {},
                )
            except Exception as e:
                logger.error(f"All query methods failed for {database_id}: {e}")

        return {"results": [], "has_more": False}

    # =========================================================================
    # TYPED FETCH METHODS (one per database type)
    # =========================================================================

    def fetch_flashcards(self) -> list[dict[str, Any]]:
        """Fetch all flashcards from the Flashcards database."""
        db_id = self._settings.flashcards_db_id
        if not db_id:
            logger.warning("No FLASHCARDS_DB_ID configured")
            return []
        return self.fetch_from_database(db_id, "flashcards")

    def fetch_concepts(self) -> list[dict[str, Any]]:
        """Fetch all concepts from the Concepts database."""
        db_id = self._settings.concepts_db_id
        if not db_id:
            logger.warning("No CONCEPTS_DB_ID configured")
            return []
        return self.fetch_from_database(db_id, "concepts")

    def fetch_concept_areas(self) -> list[dict[str, Any]]:
        """Fetch all concept areas (L0) from the Concept Areas database."""
        db_id = self._settings.concept_areas_db_id
        if not db_id:
            logger.warning("No CONCEPT_AREAS_DB_ID configured")
            return []
        return self.fetch_from_database(db_id, "concept_areas")

    def fetch_concept_clusters(self) -> list[dict[str, Any]]:
        """Fetch all concept clusters (L1) from the Concept Clusters database."""
        db_id = self._settings.concept_clusters_db_id
        if not db_id:
            logger.warning("No CONCEPT_CLUSTERS_DB_ID configured")
            return []
        return self.fetch_from_database(db_id, "concept_clusters")

    def fetch_modules(self) -> list[dict[str, Any]]:
        """Fetch all modules from the Modules database."""
        db_id = self._settings.modules_db_id
        if not db_id:
            logger.warning("No MODULES_DB_ID configured")
            return []
        return self.fetch_from_database(db_id, "modules")

    def fetch_tracks(self) -> list[dict[str, Any]]:
        """Fetch all tracks from the Tracks database."""
        db_id = self._settings.tracks_db_id
        if not db_id:
            logger.warning("No TRACKS_DB_ID configured")
            return []
        return self.fetch_from_database(db_id, "tracks")

    def fetch_programs(self) -> list[dict[str, Any]]:
        """Fetch all programs from the Programs database."""
        db_id = self._settings.programs_db_id
        if not db_id:
            logger.warning("No PROGRAMS_DB_ID configured")
            return []
        return self.fetch_from_database(db_id, "programs")

    def fetch_activities(self) -> list[dict[str, Any]]:
        """Fetch all activities from the Activities database."""
        db_id = self._settings.activities_db_id
        if not db_id:
            logger.warning("No ACTIVITIES_DB_ID configured")
            return []
        return self.fetch_from_database(db_id, "activities")

    def fetch_sessions(self) -> list[dict[str, Any]]:
        """Fetch all sessions from the Sessions database."""
        db_id = self._settings.sessions_db_id
        if not db_id:
            logger.warning("No SESSIONS_DB_ID configured")
            return []
        return self.fetch_from_database(db_id, "sessions")

    def fetch_quizzes(self) -> list[dict[str, Any]]:
        """Fetch all quizzes from the Quizzes database."""
        db_id = self._settings.quizzes_db_id
        if not db_id:
            logger.warning("No QUIZZES_DB_ID configured")
            return []
        return self.fetch_from_database(db_id, "quizzes")

    def fetch_critical_skills(self) -> list[dict[str, Any]]:
        """Fetch all critical skills from the Critical Skills database."""
        db_id = self._settings.critical_skills_db_id
        if not db_id:
            logger.warning("No CRITICAL_SKILLS_DB_ID configured")
            return []
        return self.fetch_from_database(db_id, "critical_skills")

    def fetch_resources(self) -> list[dict[str, Any]]:
        """Fetch all resources from the Resources database."""
        db_id = self._settings.resources_db_id
        if not db_id:
            logger.warning("No RESOURCES_DB_ID configured")
            return []
        return self.fetch_from_database(db_id, "resources")

    def fetch_mental_models(self) -> list[dict[str, Any]]:
        """Fetch all mental models from the Mental Models database."""
        db_id = self._settings.mental_models_db_id
        if not db_id:
            logger.warning("No MENTAL_MODELS_DB_ID configured")
            return []
        return self.fetch_from_database(db_id, "mental_models")

    def fetch_evidence(self) -> list[dict[str, Any]]:
        """Fetch all evidence from the Evidence database."""
        db_id = self._settings.evidence_db_id
        if not db_id:
            logger.warning("No EVIDENCE_DB_ID configured")
            return []
        return self.fetch_from_database(db_id, "evidence")

    def fetch_brain_regions(self) -> list[dict[str, Any]]:
        """Fetch all brain regions from the Brain Regions database."""
        db_id = self._settings.brain_regions_db_id
        if not db_id:
            logger.warning("No BRAIN_REGIONS_DB_ID configured")
            return []
        return self.fetch_from_database(db_id, "brain_regions")

    def fetch_training_protocols(self) -> list[dict[str, Any]]:
        """Fetch all training protocols from the Training Protocols database."""
        db_id = self._settings.training_protocols_db_id
        if not db_id:
            logger.warning("No TRAINING_PROTOCOLS_DB_ID configured")
            return []
        return self.fetch_from_database(db_id, "training_protocols")

    def fetch_practice_logs(self) -> list[dict[str, Any]]:
        """Fetch all practice logs from the Practice Logs database."""
        db_id = self._settings.practice_logs_db_id
        if not db_id:
            logger.warning("No PRACTICE_LOGS_DB_ID configured")
            return []
        return self.fetch_from_database(db_id, "practice_logs")

    def fetch_assessments(self) -> list[dict[str, Any]]:
        """Fetch all assessments from the Assessments database."""
        db_id = self._settings.assessments_db_id
        if not db_id:
            logger.warning("No ASSESSMENTS_DB_ID configured")
            return []
        return self.fetch_from_database(db_id, "assessments")

    # =========================================================================
    # BULK FETCH
    # =========================================================================

    def fetch_all(self) -> dict[str, list[dict[str, Any]]]:
        """
        Fetch data from all configured Notion databases.

        Returns:
            Dictionary with entity type as key and list of raw pages as value.
            Only includes databases that are configured (have IDs set).
        """
        results: dict[str, list[dict[str, Any]]] = {}
        configured = self._settings.get_configured_notion_databases()

        logger.info(f"Starting fetch_all for {len(configured)} configured databases")

        for entity_type, db_id in configured.items():
            try:
                # Try to call the typed fetch method
                fetch_method = getattr(self, f"fetch_{entity_type}", None)
                if callable(fetch_method):
                    data = fetch_method()
                    results[entity_type] = data
                    logger.info(f"Fetched {len(data)} {entity_type}")
                else:
                    # Fallback to generic fetch
                    data = self.fetch_from_database(db_id, entity_type)
                    results[entity_type] = data
                    logger.info(f"Fetched {len(data)} {entity_type} (generic)")
            except Exception as e:
                logger.error(f"Failed to fetch {entity_type}: {e}")
                results[entity_type] = []

        return results

    def get_configured_database_count(self) -> int:
        """Return the number of configured databases."""
        return len(self._settings.get_configured_notion_databases())

    # =========================================================================
    # WRITE OPERATIONS (protected by PROTECT_NOTION)
    # =========================================================================

    def update_page(
        self,
        page_id: str,
        properties: dict[str, Any],
        dry_run: bool = False,
    ) -> dict[str, Any] | None:
        """
        Update a Notion page with new properties.

        Respects PROTECT_NOTION setting. Used for syncing computed fields back.

        Args:
            page_id: Notion page ID
            properties: Properties to update (e.g., {"[Computed] Quality Grade": ...})
            dry_run: If True, log but don't execute

        Returns:
            Updated page response or None if protected/dry_run
        """
        if not self._client:
            logger.warning("Notion client not ready")
            return None

        if self._settings.protect_notion:
            logger.warning(f"Skipping update to page {page_id}: PROTECT_NOTION=true")
            return None

        if dry_run or self._settings.dry_run:
            logger.info(f"DRY RUN: Would update page {page_id} with {properties}")
            return None

        try:
            return self._client.pages.update(page_id=page_id, properties=properties)
        except Exception as e:
            logger.error(f"Failed to update page {page_id}: {e}")
            return None

    # =========================================================================
    # PAGE CONTENT BLOCK FETCHING (for AI enrichment)
    # =========================================================================

    def fetch_page_content(self, page_id: str) -> dict[str, Any]:
        """
        Fetch all content blocks from a Notion page.

        Returns:
            Dictionary with:
                - blocks: List of parsed block dictionaries
                - text_content: Combined plain text from all blocks
                - has_images: Whether page contains images
                - has_code: Whether page contains code blocks
                - block_count: Total number of blocks
        """
        if not self._client:
            logger.warning("Notion client not ready; cannot fetch page content")
            return {
                "blocks": [],
                "text_content": "",
                "has_images": False,
                "has_code": False,
                "block_count": 0,
            }

        blocks = self._fetch_all_blocks(page_id)
        parsed_blocks = [self._parse_block(block) for block in blocks]

        # Combine all text content
        text_parts = []
        has_images = False
        has_code = False

        for block in parsed_blocks:
            if block.get("text"):
                text_parts.append(block["text"])
            if block.get("type") == "image":
                has_images = True
            if block.get("type") == "code":
                has_code = True

        return {
            "blocks": parsed_blocks,
            "text_content": "\n\n".join(text_parts),
            "has_images": has_images,
            "has_code": has_code,
            "block_count": len(parsed_blocks),
        }

    def _fetch_all_blocks(self, block_id: str, depth: int = 0) -> list[dict[str, Any]]:
        """
        Recursively fetch all blocks from a page/block.

        Args:
            block_id: The block/page ID to fetch children from
            depth: Current recursion depth (max 3 levels)

        Returns:
            Flat list of all blocks including nested children
        """
        if depth > 3:
            logger.debug(f"Max depth reached for block {block_id}")
            return []

        if not self._client:
            return []

        all_blocks = []
        start_cursor: str | None = None

        try:
            while True:
                blocks_api = getattr(self._client, "blocks", None)
                if blocks_api is None:
                    logger.warning("blocks API not available in Notion client")
                    break

                children = getattr(blocks_api, "children", None)
                if children is None:
                    logger.warning("blocks.children API not available")
                    break

                list_fn = getattr(children, "list", None)
                if not callable(list_fn):
                    logger.warning("blocks.children.list not callable")
                    break

                kwargs = {"block_id": block_id, "page_size": 100}
                if start_cursor:
                    kwargs["start_cursor"] = start_cursor

                response = list_fn(**kwargs)
                results = response.get("results", [])

                for block in results:
                    all_blocks.append(block)
                    # Recursively fetch nested blocks
                    if block.get("has_children", False):
                        child_blocks = self._fetch_all_blocks(block["id"], depth=depth + 1)
                        all_blocks.extend(child_blocks)

                if not response.get("has_more"):
                    break
                start_cursor = response.get("next_cursor")

        except Exception as e:
            logger.error(f"Failed to fetch blocks for {block_id}: {e}")

        return all_blocks

    def _parse_block(self, block: dict[str, Any]) -> dict[str, Any]:
        """Parse a Notion block into a simplified structure."""
        block_type = block.get("type", "unknown")
        block_data = block.get(block_type, {})

        result = {
            "id": block.get("id"),
            "type": block_type,
            "text": "",
            "metadata": {},
        }

        # Extract text from rich_text arrays
        if "rich_text" in block_data:
            result["text"] = self._extract_rich_text(block_data["rich_text"])
        elif "text" in block_data:
            result["text"] = self._extract_rich_text(block_data["text"])

        return result

    def _extract_rich_text(self, rich_text_array: list[dict[str, Any]]) -> str:
        """Extract plain text from Notion's rich_text array."""
        if not rich_text_array:
            return ""

        parts = []
        for item in rich_text_array:
            text = item.get("plain_text", "") or item.get("text", {}).get("content", "")
            parts.append(text)

        return "".join(parts)

    def fetch_page_content_batch(
        self,
        page_ids: list[str],
        rate_limit_delay: float = 0.35,
    ) -> dict[str, dict[str, Any]]:
        """
        Fetch content for multiple pages with rate limiting.

        Args:
            page_ids: List of Notion page IDs to fetch
            rate_limit_delay: Seconds to wait between requests (~3 req/sec)

        Returns:
            Dictionary mapping page_id to content dict
        """
        results: dict[str, dict[str, Any]] = {}
        total = len(page_ids)

        for i, page_id in enumerate(page_ids):
            try:
                content = self.fetch_page_content(page_id)
                results[page_id] = content
                logger.debug(f"Fetched content for page {i + 1}/{total}: {page_id}")
            except Exception as e:
                logger.error(f"Failed to fetch content for {page_id}: {e}")
                results[page_id] = {
                    "blocks": [],
                    "text_content": "",
                    "has_images": False,
                    "has_code": False,
                    "block_count": 0,
                    "error": str(e),
                }

            # Rate limiting
            if i < total - 1:
                time.sleep(rate_limit_delay)

        return results
