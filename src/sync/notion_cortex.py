"""
Notion Cortex Service for Cortex 2.0.

This service extends the base NotionClient with Cortex 2.0 specific operations:
- Z-Score property updates (Focus Stream activation)
- Memory state management
- PSI (Pattern Separation Index) persistence
- NCDE diagnosis write-back

The "Inverted Filter" Pattern:
Since Notion's database views are immutable via API, we modify data properties
instead. Pre-configured views filter on these computed properties, causing
atoms to appear/disappear from views as their properties change.

Key Properties:
- Z_Score (Number): Computed attention-worthiness score [0, 1]
- Z_Activation (Checkbox): Focus Stream membership flag
- Memory_State (Status): NEW → LEARNING → REVIEW → MASTERED
- PSI (Number): Pattern Separation Index for discrimination training
- Validation_Status (Text): Quality validation status

Reference: Cortex 2.0 Architecture Specification, Section 2.4

Author: Cortex System
Version: 2.0.0 (Notion-Centric Architecture)
"""
from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Optional

from loguru import logger

from config import get_settings
from src.sync.notion_client import NotionClient
from src.graph.zscore_engine import ZScoreResult


# =============================================================================
# DATA MODELS
# =============================================================================

@dataclass
class CortexPropertyUpdate:
    """A batch of Cortex property updates for a Notion page."""
    page_id: str
    z_score: Optional[float] = None
    z_activation: Optional[bool] = None
    memory_state: Optional[str] = None
    psi: Optional[float] = None
    validation_status: Optional[str] = None
    last_diagnosis: Optional[str] = None
    last_remediation: Optional[str] = None


@dataclass
class NotionUpdateResult:
    """Result of a batch update operation."""
    total: int = 0
    success: int = 0
    failed: int = 0
    skipped: int = 0  # Protected or dry run
    errors: list[str] = None

    def __post_init__(self):
        if self.errors is None:
            self.errors = []


# =============================================================================
# NOTION CORTEX SERVICE
# =============================================================================

class NotionCortexService:
    """
    Extended Notion client for Cortex 2.0 operations.

    This service handles all write-back operations from Cortex to Notion,
    implementing the "Inverted Filter" pattern for Focus Stream management.

    Responsibilities:
    - Update Z-Score and activation properties
    - Manage Memory State transitions
    - Persist NCDE diagnosis results
    - Handle rate limiting and write protection

    Usage:
        service = NotionCortexService()
        results = [ZScoreResult(...), ZScoreResult(...)]
        update_result = service.update_zscores(results)
    """

    def __init__(self, notion_client: Optional[NotionClient] = None):
        """
        Initialize the Cortex Notion service.

        Args:
            notion_client: Existing NotionClient (creates new if None)
        """
        self._settings = get_settings()
        self._client = notion_client or NotionClient()

        # Property name mappings from settings
        self._prop_z_score = self._settings.notion_prop_z_score
        self._prop_z_activation = self._settings.notion_prop_z_activation
        self._prop_memory_state = self._settings.notion_prop_memory_state
        self._prop_psi = self._settings.notion_prop_psi
        self._prop_validation = self._settings.notion_prop_validation

    @property
    def is_ready(self) -> bool:
        """Check if the service is ready to make updates."""
        return self._client.ready

    @property
    def is_protected(self) -> bool:
        """Check if writes are protected."""
        return self._settings.protect_notion

    # =========================================================================
    # Z-SCORE UPDATES
    # =========================================================================

    def update_zscores(
        self,
        results: list[ZScoreResult],
        dry_run: bool = False,
    ) -> NotionUpdateResult:
        """
        Update Z-Score properties for multiple atoms.

        This is the primary interface for the "Inverted Filter" pattern.
        By updating Z_Activation, atoms appear/disappear from Focus Stream views.

        Args:
            results: List of ZScoreResults from ZScoreEngine
            dry_run: If True, log but don't execute

        Returns:
            NotionUpdateResult with statistics
        """
        update_result = NotionUpdateResult(total=len(results))

        if self.is_protected:
            logger.warning("Notion writes protected; skipping Z-Score updates")
            update_result.skipped = len(results)
            return update_result

        for result in results:
            if not result.needs_update:
                update_result.skipped += 1
                continue

            properties = {
                self._prop_z_score: {"number": round(result.z_score, 3)},
                self._prop_z_activation: {"checkbox": result.z_activation},
            }

            if dry_run or self._settings.dry_run:
                logger.info(
                    f"DRY RUN: Would update {result.atom_id}: "
                    f"Z={result.z_score:.3f}, Active={result.z_activation}"
                )
                update_result.skipped += 1
                continue

            response = self._client.update_page(result.atom_id, properties)

            if response:
                update_result.success += 1
            else:
                update_result.failed += 1
                update_result.errors.append(f"Failed to update {result.atom_id}")

            # Rate limiting (3 req/sec)
            time.sleep(0.35)

        logger.info(
            f"Z-Score update: {update_result.success} success, "
            f"{update_result.failed} failed, {update_result.skipped} skipped"
        )
        return update_result

    def activate_focus_stream(
        self,
        page_ids: list[str],
        activate: bool = True,
    ) -> NotionUpdateResult:
        """
        Bulk activate/deactivate atoms in Focus Stream.

        Args:
            page_ids: List of Notion page IDs
            activate: True to activate, False to deactivate

        Returns:
            NotionUpdateResult with statistics
        """
        update_result = NotionUpdateResult(total=len(page_ids))

        if self.is_protected:
            logger.warning("Notion writes protected; skipping activation")
            update_result.skipped = len(page_ids)
            return update_result

        for page_id in page_ids:
            properties = {
                self._prop_z_activation: {"checkbox": activate},
            }

            response = self._client.update_page(page_id, properties)

            if response:
                update_result.success += 1
            else:
                update_result.failed += 1

            time.sleep(0.35)

        return update_result

    # =========================================================================
    # MEMORY STATE MANAGEMENT
    # =========================================================================

    def update_memory_state(
        self,
        page_id: str,
        new_state: str,
    ) -> bool:
        """
        Update the memory state for an atom.

        Valid states: NEW → LEARNING → REVIEW → MASTERED

        Args:
            page_id: Notion page ID
            new_state: New memory state

        Returns:
            True if successful
        """
        valid_states = ["NEW", "LEARNING", "REVIEW", "MASTERED"]
        if new_state not in valid_states:
            logger.warning(f"Invalid memory state: {new_state}")
            return False

        if self.is_protected:
            logger.warning(f"Protected: Would set {page_id} to {new_state}")
            return False

        # Try as Status property first, fall back to Select
        properties = {
            self._prop_memory_state: {"status": {"name": new_state}},
        }

        response = self._client.update_page(page_id, properties)

        if not response:
            # Try as Select property
            properties = {
                self._prop_memory_state: {"select": {"name": new_state}},
            }
            response = self._client.update_page(page_id, properties)

        return response is not None

    def batch_update_memory_states(
        self,
        updates: dict[str, str],
    ) -> NotionUpdateResult:
        """
        Batch update memory states for multiple atoms.

        Args:
            updates: Dictionary mapping page_id to new_state

        Returns:
            NotionUpdateResult with statistics
        """
        result = NotionUpdateResult(total=len(updates))

        for page_id, new_state in updates.items():
            if self.update_memory_state(page_id, new_state):
                result.success += 1
            else:
                result.failed += 1

            time.sleep(0.35)

        return result

    # =========================================================================
    # PSI (PATTERN SEPARATION INDEX) UPDATES
    # =========================================================================

    def update_psi(
        self,
        page_id: str,
        psi_value: float,
    ) -> bool:
        """
        Update the PSI (Pattern Separation Index) for an atom.

        PSI indicates how confusable this atom is with others.
        Higher PSI = more confusable = needs discrimination training.

        Args:
            page_id: Notion page ID
            psi_value: PSI value in [0, 1]

        Returns:
            True if successful
        """
        if self.is_protected:
            logger.warning(f"Protected: Would set PSI for {page_id} to {psi_value:.3f}")
            return False

        properties = {
            self._prop_psi: {"number": round(psi_value, 3)},
        }

        response = self._client.update_page(page_id, properties)
        return response is not None

    def batch_update_psi(
        self,
        updates: dict[str, float],
    ) -> NotionUpdateResult:
        """
        Batch update PSI values for multiple atoms.

        Args:
            updates: Dictionary mapping page_id to PSI value

        Returns:
            NotionUpdateResult with statistics
        """
        result = NotionUpdateResult(total=len(updates))

        for page_id, psi_value in updates.items():
            if self.update_psi(page_id, psi_value):
                result.success += 1
            else:
                result.failed += 1

            time.sleep(0.35)

        return result

    # =========================================================================
    # NCDE DIAGNOSIS WRITE-BACK
    # =========================================================================

    def record_diagnosis(
        self,
        page_id: str,
        fail_mode: Optional[str],
        remediation: Optional[str],
        confidence: float = 0.0,
    ) -> bool:
        """
        Record NCDE diagnosis result to Notion.

        This persists the cognitive diagnosis for analytics and
        future session planning.

        Args:
            page_id: Notion page ID
            fail_mode: Diagnosed failure mode (e.g., "ENCODING_ERROR")
            remediation: Applied remediation strategy
            confidence: Diagnosis confidence

        Returns:
            True if successful
        """
        if self.is_protected:
            logger.debug(f"Protected: Would record diagnosis for {page_id}")
            return False

        # Build diagnosis record
        diagnosis_text = f"{fail_mode or 'SUCCESS'} @ {confidence:.0%}"
        if remediation:
            diagnosis_text += f" → {remediation}"

        properties = {
            "Last_Diagnosis": {"rich_text": [{"text": {"content": diagnosis_text[:200]}}]},
        }

        response = self._client.update_page(page_id, properties)
        return response is not None

    # =========================================================================
    # BATCH CORTEX UPDATES
    # =========================================================================

    def apply_cortex_updates(
        self,
        updates: list[CortexPropertyUpdate],
        dry_run: bool = False,
    ) -> NotionUpdateResult:
        """
        Apply a batch of Cortex property updates.

        This is the most efficient way to update multiple properties
        at once, as it batches all changes for each page.

        Args:
            updates: List of CortexPropertyUpdate objects
            dry_run: If True, log but don't execute

        Returns:
            NotionUpdateResult with statistics
        """
        result = NotionUpdateResult(total=len(updates))

        if self.is_protected:
            logger.warning("Notion writes protected; skipping batch update")
            result.skipped = len(updates)
            return result

        for update in updates:
            properties = {}

            if update.z_score is not None:
                properties[self._prop_z_score] = {"number": round(update.z_score, 3)}

            if update.z_activation is not None:
                properties[self._prop_z_activation] = {"checkbox": update.z_activation}

            if update.memory_state is not None:
                properties[self._prop_memory_state] = {"status": {"name": update.memory_state}}

            if update.psi is not None:
                properties[self._prop_psi] = {"number": round(update.psi, 3)}

            if update.validation_status is not None:
                properties[self._prop_validation] = {
                    "rich_text": [{"text": {"content": update.validation_status[:200]}}]
                }

            if not properties:
                result.skipped += 1
                continue

            if dry_run or self._settings.dry_run:
                logger.info(f"DRY RUN: Would update {update.page_id}: {list(properties.keys())}")
                result.skipped += 1
                continue

            response = self._client.update_page(update.page_id, properties)

            if response:
                result.success += 1
            else:
                result.failed += 1
                result.errors.append(f"Failed to update {update.page_id}")

            time.sleep(0.35)

        logger.info(
            f"Cortex batch update: {result.success} success, "
            f"{result.failed} failed, {result.skipped} skipped"
        )
        return result

    # =========================================================================
    # FOCUS STREAM QUERIES
    # =========================================================================

    def get_focus_stream(self) -> list[dict[str, Any]]:
        """
        Get all atoms currently in the Focus Stream.

        This queries atoms where Z_Activation is True.

        Returns:
            List of Notion page dictionaries
        """
        # Use the flashcards database
        db_id = self._settings.flashcards_db_id
        if not db_id:
            logger.warning("No FLASHCARDS_DB_ID configured")
            return []

        # Query with filter for Z_Activation = True
        # Note: NotionClient doesn't support filters yet, so we fetch all and filter
        all_pages = self._client.fetch_flashcards()

        focus_stream = []
        for page in all_pages:
            props = page.get("properties", {})
            activation_prop = props.get(self._prop_z_activation, {})
            if activation_prop.get("checkbox", False):
                focus_stream.append(page)

        logger.info(f"Focus Stream contains {len(focus_stream)} atoms")
        return focus_stream

    def get_atoms_needing_review(self) -> list[dict[str, Any]]:
        """
        Get atoms in LEARNING or REVIEW state.

        Returns:
            List of Notion page dictionaries
        """
        all_pages = self._client.fetch_flashcards()

        review_atoms = []
        for page in all_pages:
            props = page.get("properties", {})
            state_prop = props.get(self._prop_memory_state, {})

            # Extract state from Status or Select property
            state = None
            if "status" in state_prop and state_prop["status"]:
                state = state_prop["status"].get("name")
            elif "select" in state_prop and state_prop["select"]:
                state = state_prop["select"].get("name")

            if state in ("LEARNING", "REVIEW"):
                review_atoms.append(page)

        logger.info(f"Found {len(review_atoms)} atoms needing review")
        return review_atoms


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================

_service: Optional[NotionCortexService] = None


def get_notion_cortex() -> NotionCortexService:
    """Get or create the global Notion Cortex service."""
    global _service
    if _service is None:
        _service = NotionCortexService()
    return _service


def update_focus_stream(zscore_results: list[ZScoreResult]) -> NotionUpdateResult:
    """
    Update Focus Stream based on Z-Score results.

    Convenience function for the common pattern of computing Z-Scores
    and updating Notion properties.

    Args:
        zscore_results: List of ZScoreResult from ZScoreEngine

    Returns:
        NotionUpdateResult with statistics
    """
    service = get_notion_cortex()

    # Mark results that need update (where activation status changed)
    for result in zscore_results:
        result.needs_update = True  # In production, compare with current state

    return service.update_zscores(zscore_results)
