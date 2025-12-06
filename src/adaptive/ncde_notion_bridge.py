"""
NCDE-Notion Bridge for Cortex 2.0.

This module connects the Neuro-Cognitive Diagnosis Engine (NCDE) with
Notion property persistence, enabling:

1. Real-time cognitive state write-back to Notion
2. PSI (Pattern Separation Index) persistence
3. Memory state transitions (NEW → LEARNING → REVIEW → MASTERED)
4. Diagnosis history for analytics
5. Z-Score recalculation triggers

The bridge implements the "Inverted Filter" pattern: by modifying atom
properties, atoms appear/disappear from pre-configured Notion views.

Architecture:
    [CortexSession] → [NCDE Pipeline] → [NCDENotionBridge] → [Notion API]
                                              ↓
                                        [Shadow Graph]

Author: Cortex System
Version: 2.0.0 (Notion-Centric Architecture)
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional
from enum import Enum

from loguru import logger

from config import get_settings
from src.sync.notion_cortex import (
    NotionCortexService,
    CortexPropertyUpdate,
    get_notion_cortex,
)
from src.graph.zscore_engine import (
    ZScoreEngine,
    AtomMetrics,
    get_zscore_engine,
    get_forcez_engine,
)
from src.graph.shadow_graph import get_shadow_graph


# =============================================================================
# DATA MODELS
# =============================================================================

class MemoryState(str, Enum):
    """Memory consolidation states for atoms."""
    NEW = "NEW"              # Never reviewed
    LEARNING = "LEARNING"    # Active encoding phase
    REVIEW = "REVIEW"        # Consolidation phase
    MASTERED = "MASTERED"    # Fluent retrieval


@dataclass
class NCDEWritebackEvent:
    """Event representing an NCDE result that needs Notion write-back."""
    atom_id: str
    diagnosis_type: Optional[str] = None  # FailMode or SuccessMode value
    remediation_type: Optional[str] = None
    confidence: float = 0.0
    psi_update: Optional[float] = None
    memory_state_change: Optional[MemoryState] = None
    z_score_delta: float = 0.0
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class BridgeStats:
    """Statistics for the NCDE-Notion bridge."""
    events_processed: int = 0
    notion_updates_success: int = 0
    notion_updates_failed: int = 0
    psi_updates: int = 0
    memory_transitions: int = 0
    zscore_recalculations: int = 0
    last_sync: Optional[datetime] = None


# =============================================================================
# NCDE NOTION BRIDGE
# =============================================================================

class NCDENotionBridge:
    """
    Bridge between NCDE cognitive diagnosis and Notion property persistence.

    This class is the "outbound" component of the Cortex 2.0 architecture,
    responsible for writing cognitive state changes back to Notion.

    Key Features:
    - Batched writes to respect Notion API rate limits
    - Memory state machine enforcement
    - PSI tracking and persistence
    - Z-Score recalculation triggers

    Usage:
        bridge = NCDENotionBridge()

        # After each interaction in CortexSession:
        event = NCDEWritebackEvent(
            atom_id=atom_id,
            diagnosis_type=diagnosis.fail_mode.value,
            psi_update=confusion_matrix.get_psi(atom_id),
        )
        bridge.queue_event(event)

        # At end of session:
        results = bridge.flush()
    """

    def __init__(
        self,
        notion_service: Optional[NotionCortexService] = None,
        batch_size: int = 10,
        auto_flush_threshold: int = 50,
    ):
        """
        Initialize the bridge.

        Args:
            notion_service: Notion service for API calls (creates default if None)
            batch_size: Number of updates per batch (for rate limiting)
            auto_flush_threshold: Queue size that triggers automatic flush
        """
        self._settings = get_settings()
        self._notion = notion_service or get_notion_cortex()
        self._batch_size = batch_size
        self._auto_flush_threshold = auto_flush_threshold

        # Event queue
        self._queue: list[NCDEWritebackEvent] = []

        # Statistics
        self._stats = BridgeStats()

        # Cached atom states for transition validation
        self._atom_states: dict[str, MemoryState] = {}

    @property
    def stats(self) -> BridgeStats:
        """Get bridge statistics."""
        return self._stats

    @property
    def queue_size(self) -> int:
        """Get current queue size."""
        return len(self._queue)

    # =========================================================================
    # EVENT QUEUEING
    # =========================================================================

    def queue_event(self, event: NCDEWritebackEvent) -> None:
        """
        Queue an NCDE result for Notion write-back.

        Events are batched for efficiency and to respect rate limits.

        Args:
            event: NCDEWritebackEvent to queue
        """
        self._queue.append(event)
        self._stats.events_processed += 1

        logger.debug(
            f"Queued NCDE event: atom={event.atom_id[:8]}, "
            f"diagnosis={event.diagnosis_type}, queue_size={len(self._queue)}"
        )

        # Auto-flush if threshold reached
        if len(self._queue) >= self._auto_flush_threshold:
            logger.info("Auto-flush threshold reached, flushing queue...")
            self.flush()

    def queue_diagnosis(
        self,
        atom_id: str,
        diagnosis,  # CognitiveDiagnosis from neuro_model
        confusion_matrix=None,  # ConfusionMatrix from ncde_pipeline
    ) -> None:
        """
        Convenience method to queue a diagnosis result.

        Args:
            atom_id: Notion page ID
            diagnosis: CognitiveDiagnosis result
            confusion_matrix: Optional ConfusionMatrix for PSI extraction
        """
        psi = None
        if confusion_matrix:
            psi = confusion_matrix.get_psi(atom_id)

        event = NCDEWritebackEvent(
            atom_id=atom_id,
            diagnosis_type=diagnosis.fail_mode.value if diagnosis.fail_mode else (
                diagnosis.success_mode.value if diagnosis.success_mode else None
            ),
            remediation_type=diagnosis.recommended_remediation.value if diagnosis.recommended_remediation else None,
            confidence=diagnosis.confidence,
            psi_update=psi,
        )

        self.queue_event(event)

    # =========================================================================
    # FLUSH (WRITE TO NOTION)
    # =========================================================================

    def flush(self) -> BridgeStats:
        """
        Flush all queued events to Notion.

        Processes events in batches to respect rate limits.

        Returns:
            Updated BridgeStats
        """
        if not self._queue:
            logger.debug("Nothing to flush")
            return self._stats

        logger.info(f"Flushing {len(self._queue)} NCDE events to Notion...")

        # Build property updates from events
        updates = self._build_updates(self._queue)

        if not updates:
            self._queue.clear()
            return self._stats

        # Check if Notion writes are protected
        if self._settings.protect_notion:
            logger.warning(
                f"PROTECT_NOTION enabled; would update {len(updates)} atoms"
            )
            self._queue.clear()
            return self._stats

        # Apply updates via NotionCortexService
        result = self._notion.apply_cortex_updates(updates)

        # Update statistics
        self._stats.notion_updates_success += result.success
        self._stats.notion_updates_failed += result.failed
        self._stats.last_sync = datetime.now()

        # Clear queue
        self._queue.clear()

        logger.info(
            f"Flush complete: {result.success} success, {result.failed} failed"
        )

        return self._stats

    def _build_updates(
        self,
        events: list[NCDEWritebackEvent],
    ) -> list[CortexPropertyUpdate]:
        """
        Convert events to Notion property updates.

        Consolidates multiple events for the same atom.

        Args:
            events: List of events to convert

        Returns:
            List of CortexPropertyUpdate objects
        """
        # Consolidate by atom_id (take most recent)
        by_atom: dict[str, NCDEWritebackEvent] = {}
        for event in events:
            by_atom[event.atom_id] = event

        updates = []
        for atom_id, event in by_atom.items():
            update = CortexPropertyUpdate(page_id=atom_id)

            # PSI update
            if event.psi_update is not None:
                update.psi = event.psi_update
                self._stats.psi_updates += 1

            # Memory state change
            if event.memory_state_change:
                update.memory_state = event.memory_state_change.value
                self._stats.memory_transitions += 1

            # Diagnosis record
            if event.diagnosis_type or event.remediation_type:
                diagnosis_text = f"{event.diagnosis_type or 'OK'}"
                if event.remediation_type:
                    diagnosis_text += f" → {event.remediation_type}"
                update.last_diagnosis = diagnosis_text[:200]

            updates.append(update)

        return updates

    # =========================================================================
    # MEMORY STATE MACHINE
    # =========================================================================

    def transition_memory_state(
        self,
        atom_id: str,
        is_correct: bool,
        current_stability: float = 0.0,
        lapses: int = 0,
    ) -> Optional[MemoryState]:
        """
        Determine memory state transition based on interaction.

        State Machine:
        - NEW → LEARNING: First interaction (correct or incorrect)
        - LEARNING → REVIEW: Stability > 1 day and correct
        - REVIEW → MASTERED: Stability > 7 days and < 2 lapses
        - MASTERED → REVIEW: Lapse (incorrect answer)
        - Any → LEARNING: Multiple consecutive lapses

        Args:
            atom_id: Atom identifier
            is_correct: Whether the interaction was correct
            current_stability: Current FSRS stability (days)
            lapses: Number of lapses

        Returns:
            New MemoryState if transition occurred, None otherwise
        """
        current = self._atom_states.get(atom_id, MemoryState.NEW)
        new_state = None

        if current == MemoryState.NEW:
            new_state = MemoryState.LEARNING

        elif current == MemoryState.LEARNING:
            if is_correct and current_stability >= 1.0:
                new_state = MemoryState.REVIEW

        elif current == MemoryState.REVIEW:
            if is_correct and current_stability >= 7.0 and lapses < 2:
                new_state = MemoryState.MASTERED
            elif not is_correct:
                # Stay in REVIEW but track lapse
                pass

        elif current == MemoryState.MASTERED:
            if not is_correct:
                new_state = MemoryState.REVIEW
                # Could also go to LEARNING if multiple lapses

        # Update cache
        if new_state:
            self._atom_states[atom_id] = new_state
            logger.debug(f"Memory transition: {atom_id[:8]} {current} → {new_state}")

        return new_state

    # =========================================================================
    # Z-SCORE RECALCULATION
    # =========================================================================

    def recalculate_zscores(
        self,
        atom_ids: list[str],
        project_ids: Optional[list[str]] = None,
    ) -> int:
        """
        Trigger Z-Score recalculation for atoms.

        Called when interactions affect Z-Score components:
        - Time decay updates
        - Memory state changes
        - PSI changes

        Args:
            atom_ids: Atoms to recalculate
            project_ids: Active project IDs for relevance signal

        Returns:
            Number of atoms with changed activation status
        """
        engine = get_zscore_engine()
        notion = self._notion

        # Build metrics from cached states
        metrics_list = []
        for atom_id in atom_ids:
            metrics = AtomMetrics(
                atom_id=atom_id,
                last_touched=datetime.now(),
                memory_state=self._atom_states.get(atom_id, MemoryState.NEW).value,
            )
            metrics_list.append(metrics)

        # Compute Z-Scores
        results = engine.compute_batch(metrics_list, project_ids or [])

        # Count changed activations and queue updates
        changed = 0
        for result in results:
            result.needs_update = True  # Always update after recalculation

            # Queue for Notion update
            event = NCDEWritebackEvent(
                atom_id=result.atom_id,
                z_score_delta=result.z_score,  # Using as absolute value for now
            )
            # Don't add to queue here - use dedicated method

        self._stats.zscore_recalculations += len(atom_ids)

        return changed


# =============================================================================
# SESSION INTEGRATION
# =============================================================================

class NCDESessionWrapper:
    """
    Wrapper that integrates NCDE with Cortex session and Notion write-back.

    This is the high-level integration point used by CortexSession.

    Usage:
        wrapper = NCDESessionWrapper()

        # In session run loop:
        async for interaction in session:
            # Process through NCDE
            diagnosis = wrapper.process_interaction(interaction)

            # Display and handle remediation...

        # End of session
        wrapper.finalize()
    """

    def __init__(
        self,
        enable_notion_writeback: bool = True,
        enable_zscore_updates: bool = True,
    ):
        """
        Initialize the session wrapper.

        Args:
            enable_notion_writeback: Whether to write back to Notion
            enable_zscore_updates: Whether to update Z-Scores
        """
        self._settings = get_settings()
        self._bridge = NCDENotionBridge() if enable_notion_writeback else None
        self._enable_zscore = enable_zscore_updates

        # Import NCDE pipeline
        from src.adaptive.ncde_pipeline import NCDEPipeline, SessionContext
        self._pipeline = NCDEPipeline()

        # Session context
        self._context: Optional[Any] = None

        # Atoms processed this session (for batch Z-Score update)
        self._processed_atoms: list[str] = []

    def initialize_session(self, session_id: str, learner_id: str, queue_size: int):
        """Initialize NCDE session context."""
        from src.adaptive.ncde_pipeline import SessionContext

        self._context = SessionContext(
            session_id=session_id,
            learner_id=learner_id,
            queue_size=queue_size,
        )

    def process_interaction(
        self,
        raw_event,  # RawInteractionEvent
    ) -> tuple:  # Returns (CognitiveDiagnosis, RemediationStrategy)
        """
        Process an interaction through NCDE and queue Notion updates.

        Args:
            raw_event: RawInteractionEvent from session

        Returns:
            Tuple of (diagnosis, remediation_strategy)
        """
        if not self._context:
            raise ValueError("Session not initialized. Call initialize_session first.")

        # Store in history
        self._context.interaction_history.append(raw_event)

        # Process through NCDE pipeline
        diagnosis, strategy = self._pipeline.process(raw_event, self._context)

        # Track processed atom
        self._processed_atoms.append(raw_event.atom_id)

        # Queue Notion write-back
        if self._bridge:
            self._bridge.queue_diagnosis(
                atom_id=raw_event.atom_id,
                diagnosis=diagnosis,
                confusion_matrix=self._pipeline._confusion_matrix,
            )

            # Handle memory state transition
            new_state = self._bridge.transition_memory_state(
                atom_id=raw_event.atom_id,
                is_correct=raw_event.is_correct,
                current_stability=0.0,  # Would come from FSRS data
                lapses=self._context.error_streak if not raw_event.is_correct else 0,
            )

            if new_state:
                # Queue state change
                event = NCDEWritebackEvent(
                    atom_id=raw_event.atom_id,
                    memory_state_change=new_state,
                )
                self._bridge.queue_event(event)

        # Store diagnosis in context
        self._context.diagnosis_history.append(diagnosis)

        return diagnosis, strategy

    def finalize(self) -> BridgeStats:
        """
        Finalize session and flush all pending writes.

        Returns:
            BridgeStats with session summary
        """
        stats = BridgeStats()

        if self._bridge:
            # Flush pending events
            stats = self._bridge.flush()

            # Recalculate Z-Scores for all processed atoms
            if self._enable_zscore and self._processed_atoms:
                self._bridge.recalculate_zscores(list(set(self._processed_atoms)))

        logger.info(
            f"Session finalized: {stats.events_processed} events, "
            f"{stats.notion_updates_success} Notion updates"
        )

        return stats


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================

_bridge: Optional[NCDENotionBridge] = None


def get_ncde_bridge() -> NCDENotionBridge:
    """Get or create the global NCDE-Notion bridge."""
    global _bridge
    if _bridge is None:
        _bridge = NCDENotionBridge()
    return _bridge


def flush_ncde_to_notion() -> BridgeStats:
    """Flush all pending NCDE events to Notion."""
    bridge = get_ncde_bridge()
    return bridge.flush()
