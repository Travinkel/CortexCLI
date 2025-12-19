"""
Cortex-CLI Operating Modes

Defines the three operating modes for the cortex-cli tool:
1. API Mode - Syncs with right-learning platform
2. Pipeline Mode - CI/CD content validation and ETL
3. Offline Mode - Local-only with SQLite (original behavior)

This module enables notion-learning-sync to specialize as the
"Swiss Army Knife" utility complementing the right-learning platform.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings


class OperatingMode(str, Enum):
    """Operating mode for cortex-cli."""

    API = "api"  # Connected to right-learning platform
    PIPELINE = "pipeline"  # CI/CD content validation
    OFFLINE = "offline"  # Local-only, air-gapped


class ApiConfig(BaseModel):
    """Configuration for API mode (right-learning sync)."""

    base_url: str = "https://api.rightlearning.io"
    api_key: str | None = None
    learner_id: str | None = None
    sync_interval_seconds: int = 300  # 5 minutes
    auto_sync: bool = True

    # Endpoints
    atoms_endpoint: str = "/api/v1/atoms"
    reviews_endpoint: str = "/api/v1/reviews"
    progress_endpoint: str = "/api/v1/progress"
    struggles_endpoint: str = "/api/v1/struggles"


class PipelineConfig(BaseModel):
    """Configuration for Pipeline mode (CI/CD)."""

    content_dir: Path = Path("docs/source-materials")
    output_dir: Path = Path("outputs/validated")
    strict_validation: bool = True
    fail_on_warning: bool = False

    # Validation rules
    validate_parsons: bool = True
    validate_cloze_syntax: bool = True
    validate_mcq_distractors: bool = True
    min_atom_quality_score: float = 0.7

    # Publishing
    auto_publish: bool = False
    publish_endpoint: str | None = None


class OfflineConfig(BaseModel):
    """Configuration for Offline mode (local-only)."""

    database_path: Path = Path("data/cortex.db")
    export_dir: Path = Path("exports")

    # Sync points for later reconciliation
    track_pending_syncs: bool = True
    max_offline_days: int = 30

    # Local features
    enable_local_ai: bool = False  # Ollama/local LLM
    local_model: str = "llama3.2"


class CortexCliConfig(BaseSettings):
    """
    Main configuration for cortex-cli.

    Supports three operating modes:
    - api: Connected to right-learning platform
    - pipeline: CI/CD content validation
    - offline: Local-only operation

    Configuration precedence:
    1. Environment variables (CORTEX_*)
    2. Config file (~/.cortex/config.toml)
    3. Command-line arguments
    4. Defaults
    """

    model_config = {"env_prefix": "CORTEX_", "env_nested_delimiter": "__"}

    # Operating mode
    mode: OperatingMode = OperatingMode.OFFLINE

    # Mode-specific configs
    api: ApiConfig = Field(default_factory=ApiConfig)
    pipeline: PipelineConfig = Field(default_factory=PipelineConfig)
    offline: OfflineConfig = Field(default_factory=OfflineConfig)

    # Common settings
    log_level: str = "INFO"
    data_dir: Path = Path.home() / ".cortex"
    telemetry_enabled: bool = False

    # Study preferences
    session_duration_minutes: int = 25  # Pomodoro
    new_cards_per_session: int = 20
    max_reviews_per_session: int = 100

    @property
    def is_connected(self) -> bool:
        """Check if we're in a connected mode."""
        return self.mode == OperatingMode.API

    @property
    def is_pipeline(self) -> bool:
        """Check if we're in pipeline mode."""
        return self.mode == OperatingMode.PIPELINE

    @property
    def is_offline(self) -> bool:
        """Check if we're in offline mode."""
        return self.mode == OperatingMode.OFFLINE

    def get_database_url(self) -> str:
        """Get the appropriate database URL for current mode."""
        if self.mode == OperatingMode.API:
            # API mode uses local cache + remote sync
            cache_db = self.data_dir / "cache.db"
            return f"sqlite:///{cache_db}"
        elif self.mode == OperatingMode.PIPELINE:
            # Pipeline mode uses in-memory for validation
            return "sqlite:///:memory:"
        else:
            # Offline mode uses persistent local DB
            return f"sqlite:///{self.offline.database_path}"


@dataclass
class ModeContext:
    """Runtime context for the current operating mode."""

    config: CortexCliConfig
    mode: OperatingMode
    session_id: str | None = None
    sync_pending: list[dict[str, Any]] = field(default_factory=list)

    # Connection state (API mode)
    is_authenticated: bool = False
    last_sync: str | None = None

    # Validation state (Pipeline mode)
    validation_errors: list[str] = field(default_factory=list)
    validation_warnings: list[str] = field(default_factory=list)

    # Offline state
    pending_reviews: int = 0
    days_offline: int = 0


# =============================================================================
# Mode Switching
# =============================================================================


def detect_mode() -> OperatingMode:
    """
    Auto-detect the appropriate operating mode.

    Detection logic:
    1. If CORTEX_MODE env var is set, use that
    2. If running in CI (CI=true), use pipeline
    3. If right-learning API is reachable, use api
    4. Otherwise, use offline
    """
    import os

    # Explicit mode override
    if mode_env := os.getenv("CORTEX_MODE"):
        return OperatingMode(mode_env.lower())

    # CI detection
    if os.getenv("CI") == "true" or os.getenv("GITHUB_ACTIONS"):
        return OperatingMode.PIPELINE

    # API reachability check
    if _check_api_reachable():
        return OperatingMode.API

    return OperatingMode.OFFLINE


def _check_api_reachable() -> bool:
    """Check if right-learning API is reachable."""
    import socket

    try:
        socket.create_connection(("api.rightlearning.io", 443), timeout=2)
        return True
    except (socket.timeout, OSError):
        return False


# =============================================================================
# Mode-Specific Behaviors
# =============================================================================


class ModeStrategy:
    """Strategy pattern for mode-specific behaviors."""

    def __init__(self, config: CortexCliConfig):
        self.config = config

    async def initialize(self) -> ModeContext:
        """Initialize the mode context."""
        raise NotImplementedError

    async def record_review(
        self, atom_id: str, grade: int, response_ms: int
    ) -> dict[str, Any]:
        """Record a review in the appropriate backend."""
        raise NotImplementedError

    async def get_due_atoms(self, limit: int = 50) -> list[dict[str, Any]]:
        """Get atoms due for review."""
        raise NotImplementedError

    async def sync(self) -> dict[str, Any]:
        """Perform sync operation (if applicable)."""
        raise NotImplementedError


class ApiModeStrategy(ModeStrategy):
    """Strategy for API mode - syncs with right-learning."""

    async def initialize(self) -> ModeContext:
        from loguru import logger

        logger.info("Initializing API mode - connecting to right-learning")

        # Authenticate with API
        # This would use the api config to establish connection
        return ModeContext(
            config=self.config,
            mode=OperatingMode.API,
            is_authenticated=True,  # After successful auth
        )

    async def record_review(
        self, atom_id: str, grade: int, response_ms: int
    ) -> dict[str, Any]:
        # Send to right-learning API
        # Also cache locally for offline access
        return {"synced": True, "atom_id": atom_id}

    async def get_due_atoms(self, limit: int = 50) -> list[dict[str, Any]]:
        # Fetch from right-learning API
        return []

    async def sync(self) -> dict[str, Any]:
        # Full bidirectional sync with platform
        return {"status": "synced", "uploaded": 0, "downloaded": 0}


class PipelineModeStrategy(ModeStrategy):
    """Strategy for Pipeline mode - CI/CD validation."""

    async def initialize(self) -> ModeContext:
        from loguru import logger

        logger.info("Initializing Pipeline mode - content validation")

        return ModeContext(
            config=self.config,
            mode=OperatingMode.PIPELINE,
        )

    async def record_review(
        self, atom_id: str, grade: int, response_ms: int
    ) -> dict[str, Any]:
        # Pipeline mode doesn't record reviews
        raise NotImplementedError("Reviews not supported in pipeline mode")

    async def get_due_atoms(self, limit: int = 50) -> list[dict[str, Any]]:
        # Pipeline mode doesn't have due atoms
        raise NotImplementedError("Due atoms not supported in pipeline mode")

    async def sync(self) -> dict[str, Any]:
        # Validate and optionally publish content
        return {"status": "validated", "errors": 0, "warnings": 0}


class OfflineModeStrategy(ModeStrategy):
    """Strategy for Offline mode - local-only operation."""

    async def initialize(self) -> ModeContext:
        from loguru import logger

        logger.info("Initializing Offline mode - local database")

        return ModeContext(
            config=self.config,
            mode=OperatingMode.OFFLINE,
        )

    async def record_review(
        self, atom_id: str, grade: int, response_ms: int
    ) -> dict[str, Any]:
        # Record locally, mark for future sync
        return {"synced": False, "atom_id": atom_id, "pending_sync": True}

    async def get_due_atoms(self, limit: int = 50) -> list[dict[str, Any]]:
        # Fetch from local SQLite
        return []

    async def sync(self) -> dict[str, Any]:
        # Export pending changes for manual sync
        return {"status": "offline", "pending_syncs": 0}


def get_mode_strategy(config: CortexCliConfig) -> ModeStrategy:
    """Get the appropriate strategy for the current mode."""
    strategies = {
        OperatingMode.API: ApiModeStrategy,
        OperatingMode.PIPELINE: PipelineModeStrategy,
        OperatingMode.OFFLINE: OfflineModeStrategy,
    }
    return strategies[config.mode](config)
