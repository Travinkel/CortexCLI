"""
Right-Learning Platform Client

HTTP client for syncing cortex-cli with the right-learning platform.
Handles authentication, bidirectional sync, and offline reconciliation.

Usage:
    client = PlatformClient(config.api)
    await client.authenticate()
    due_atoms = await client.get_due_atoms()
    await client.record_review(atom_id, grade, response_ms)
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

import httpx
from loguru import logger

from .modes import ApiConfig


@dataclass
class SyncResult:
    """Result of a sync operation."""

    success: bool
    uploaded_reviews: int = 0
    downloaded_atoms: int = 0
    conflicts: list[dict[str, Any]] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    sync_timestamp: datetime = field(default_factory=datetime.utcnow)


@dataclass
class AuthResult:
    """Result of authentication."""

    success: bool
    learner_id: str | None = None
    token: str | None = None
    expires_at: datetime | None = None
    error: str | None = None


class PlatformClient:
    """
    HTTP client for right-learning platform API.

    Supports:
    - API key authentication
    - Bidirectional sync (reviews up, atoms down)
    - Offline queue reconciliation
    - Progress tracking
    """

    def __init__(self, config: ApiConfig):
        self.config = config
        self._client: httpx.AsyncClient | None = None
        self._token: str | None = None
        self._learner_id: str | None = config.learner_id

    async def __aenter__(self) -> "PlatformClient":
        await self._ensure_client()
        return self

    async def __aexit__(self, *args: Any) -> None:
        await self.close()

    async def _ensure_client(self) -> httpx.AsyncClient:
        if self._client is None:
            headers = {"Content-Type": "application/json"}
            if self.config.api_key:
                headers["X-API-Key"] = self.config.api_key
            if self._token:
                headers["Authorization"] = f"Bearer {self._token}"

            self._client = httpx.AsyncClient(
                base_url=self.config.base_url,
                headers=headers,
                timeout=30.0,
            )
        return self._client

    async def close(self) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None

    # =========================================================================
    # Authentication
    # =========================================================================

    async def authenticate(self) -> AuthResult:
        """
        Authenticate with the right-learning platform.

        Uses API key to obtain a session token.
        """
        if not self.config.api_key:
            return AuthResult(success=False, error="No API key configured")

        try:
            client = await self._ensure_client()
            response = await client.post(
                "/api/v1/auth/token",
                json={"api_key": self.config.api_key},
            )

            if response.status_code == 200:
                data = response.json()
                self._token = data.get("token")
                self._learner_id = data.get("learner_id")

                # Update client headers with token
                if self._client and self._token:
                    self._client.headers["Authorization"] = f"Bearer {self._token}"

                logger.info(f"Authenticated as learner: {self._learner_id}")
                return AuthResult(
                    success=True,
                    learner_id=self._learner_id,
                    token=self._token,
                    expires_at=datetime.fromisoformat(data.get("expires_at", "")),
                )
            else:
                error = response.json().get("detail", "Authentication failed")
                logger.error(f"Authentication failed: {error}")
                return AuthResult(success=False, error=error)

        except httpx.RequestError as e:
            logger.error(f"Connection error during auth: {e}")
            return AuthResult(success=False, error=str(e))

    async def is_authenticated(self) -> bool:
        """Check if we have a valid authentication token."""
        return self._token is not None

    # =========================================================================
    # Atoms
    # =========================================================================

    async def get_due_atoms(self, limit: int = 50) -> list[dict[str, Any]]:
        """
        Fetch atoms due for review from the platform.

        Args:
            limit: Maximum number of atoms to fetch

        Returns:
            List of atom dictionaries
        """
        try:
            client = await self._ensure_client()
            response = await client.get(
                self.config.atoms_endpoint,
                params={"due": "true", "limit": limit, "learner_id": self._learner_id},
            )

            if response.status_code == 200:
                atoms = response.json().get("atoms", [])
                logger.debug(f"Fetched {len(atoms)} due atoms from platform")
                return atoms
            else:
                logger.warning(f"Failed to fetch due atoms: {response.status_code}")
                return []

        except httpx.RequestError as e:
            logger.error(f"Connection error fetching atoms: {e}")
            return []

    async def get_atom(self, atom_id: str) -> dict[str, Any] | None:
        """Fetch a single atom by ID."""
        try:
            client = await self._ensure_client()
            response = await client.get(f"{self.config.atoms_endpoint}/{atom_id}")

            if response.status_code == 200:
                return response.json()
            return None

        except httpx.RequestError as e:
            logger.error(f"Connection error fetching atom {atom_id}: {e}")
            return None

    # =========================================================================
    # Reviews
    # =========================================================================

    async def record_review(
        self,
        atom_id: str,
        grade: int,
        response_ms: int,
        session_id: str | None = None,
    ) -> dict[str, Any]:
        """
        Record a review on the platform.

        Args:
            atom_id: ID of the reviewed atom
            grade: FSRS grade (1-4)
            response_ms: Response time in milliseconds
            session_id: Optional study session ID

        Returns:
            Review result with updated scheduling info
        """
        payload = {
            "atom_id": atom_id,
            "learner_id": self._learner_id,
            "grade": grade,
            "response_time_ms": response_ms,
            "session_id": session_id,
            "timestamp": datetime.utcnow().isoformat(),
        }

        try:
            client = await self._ensure_client()
            response = await client.post(self.config.reviews_endpoint, json=payload)

            if response.status_code in (200, 201):
                result = response.json()
                logger.debug(f"Recorded review for {atom_id}: grade={grade}")
                return {
                    "success": True,
                    "next_review": result.get("next_review"),
                    "new_stability": result.get("stability"),
                    "new_difficulty": result.get("difficulty"),
                }
            else:
                error = response.json().get("detail", "Unknown error")
                logger.warning(f"Failed to record review: {error}")
                return {"success": False, "error": error, "queued": True}

        except httpx.RequestError as e:
            logger.error(f"Connection error recording review: {e}")
            # Queue for later sync
            return {"success": False, "error": str(e), "queued": True}

    async def bulk_upload_reviews(
        self, reviews: list[dict[str, Any]]
    ) -> dict[str, Any]:
        """
        Upload multiple reviews in a single request.

        Used for syncing offline reviews.
        """
        try:
            client = await self._ensure_client()
            response = await client.post(
                f"{self.config.reviews_endpoint}/bulk",
                json={"reviews": reviews, "learner_id": self._learner_id},
            )

            if response.status_code in (200, 201):
                result = response.json()
                return {
                    "success": True,
                    "uploaded": result.get("uploaded", len(reviews)),
                    "conflicts": result.get("conflicts", []),
                }
            else:
                return {"success": False, "error": response.json().get("detail")}

        except httpx.RequestError as e:
            return {"success": False, "error": str(e)}

    # =========================================================================
    # Progress & Struggles
    # =========================================================================

    async def get_progress(self) -> dict[str, Any]:
        """Fetch learner progress from platform."""
        try:
            client = await self._ensure_client()
            response = await client.get(
                self.config.progress_endpoint,
                params={"learner_id": self._learner_id},
            )

            if response.status_code == 200:
                return response.json()
            return {}

        except httpx.RequestError as e:
            logger.error(f"Connection error fetching progress: {e}")
            return {}

    async def get_struggles(self) -> list[dict[str, Any]]:
        """Fetch current struggle zones from platform."""
        try:
            client = await self._ensure_client()
            response = await client.get(
                self.config.struggles_endpoint,
                params={"learner_id": self._learner_id},
            )

            if response.status_code == 200:
                return response.json().get("struggles", [])
            return []

        except httpx.RequestError as e:
            logger.error(f"Connection error fetching struggles: {e}")
            return []

    async def update_struggle(
        self, concept_id: str, weight: float, evidence: str
    ) -> bool:
        """Update a struggle zone on the platform."""
        try:
            client = await self._ensure_client()
            response = await client.post(
                f"{self.config.struggles_endpoint}/{concept_id}",
                json={
                    "learner_id": self._learner_id,
                    "weight": weight,
                    "evidence": evidence,
                },
            )
            return response.status_code in (200, 201)

        except httpx.RequestError:
            return False

    # =========================================================================
    # Sync Operations
    # =========================================================================

    async def full_sync(
        self, pending_reviews: list[dict[str, Any]] | None = None
    ) -> SyncResult:
        """
        Perform full bidirectional sync with platform.

        1. Upload pending offline reviews
        2. Download updated atom schedules
        3. Resolve conflicts
        """
        result = SyncResult(success=True)

        # Upload pending reviews
        if pending_reviews:
            upload_result = await self.bulk_upload_reviews(pending_reviews)
            if upload_result.get("success"):
                result.uploaded_reviews = upload_result.get("uploaded", 0)
                result.conflicts.extend(upload_result.get("conflicts", []))
            else:
                result.errors.append(f"Upload failed: {upload_result.get('error')}")

        # Download progress updates
        progress = await self.get_progress()
        if progress:
            result.downloaded_atoms = progress.get("atoms_updated", 0)

        result.success = len(result.errors) == 0
        logger.info(
            f"Sync complete: ↑{result.uploaded_reviews} ↓{result.downloaded_atoms} "
            f"conflicts={len(result.conflicts)}"
        )

        return result

    async def export_for_offline(self) -> dict[str, Any]:
        """
        Export learner profile for offline use.

        Downloads:
        - All atoms for the learner
        - Current scheduling state
        - Struggle zones
        - Progress data
        """
        try:
            client = await self._ensure_client()
            response = await client.get(
                "/api/v1/export",
                params={"learner_id": self._learner_id, "format": "cortex"},
            )

            if response.status_code == 200:
                data = response.json()
                logger.info(
                    f"Exported {data.get('atom_count', 0)} atoms for offline use"
                )
                return data
            else:
                return {"error": response.json().get("detail")}

        except httpx.RequestError as e:
            return {"error": str(e)}

    # =========================================================================
    # Health Check
    # =========================================================================

    async def health_check(self) -> bool:
        """Check if the platform is reachable."""
        try:
            client = await self._ensure_client()
            response = await client.get("/health", timeout=5.0)
            return response.status_code == 200
        except (httpx.RequestError, asyncio.TimeoutError):
            return False
