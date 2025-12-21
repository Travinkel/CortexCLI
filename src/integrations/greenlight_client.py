"""
Greenlight API client for runtime atom execution.

Handles HTTP communication with Greenlight IDE for code submission,
debugging, and other runtime-dependent learning atoms.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Any

import httpx

logger = logging.getLogger(__name__)


@dataclass
class GreenlightAtomRequest:
    """Request payload for Greenlight atom execution."""

    atom_id: str
    atom_type: str
    content: dict[str, Any]
    session_context: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert request to API payload format."""
        return {
            "atom_id": self.atom_id,
            "atom_type": self.atom_type,
            "content": self.content,
            "session_context": self.session_context,
        }


@dataclass
class GreenlightAtomResult:
    """Result payload from Greenlight atom execution."""

    atom_id: str
    correct: bool
    partial_score: float
    feedback: str = ""
    test_results: dict[str, Any] = field(default_factory=dict)
    diff_suggestion: str | None = None
    git_suggestions: list[str] = field(default_factory=list)
    meta: dict[str, Any] = field(default_factory=dict)
    error: str | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> GreenlightAtomResult:
        """Parse result from API response."""
        return cls(
            atom_id=data.get("atom_id", ""),
            correct=data.get("correct", False),
            partial_score=data.get("partial_score", 0.0),
            feedback=data.get("feedback", ""),
            test_results=data.get("test_results", {}),
            diff_suggestion=data.get("diff_suggestion"),
            git_suggestions=data.get("git_suggestions", []),
            meta=data.get("meta", {}),
            error=data.get("error"),
        )


@dataclass
class GreenlightExecutionStatus:
    """Status of a queued execution."""

    execution_id: str
    status: str  # "pending", "running", "complete", "failed"
    result: GreenlightAtomResult | None = None
    error: str | None = None


class GreenlightClient:
    """HTTP client for Greenlight IDE integration."""

    def __init__(
        self,
        api_url: str,
        timeout_ms: int = 30000,
        retry_attempts: int = 3,
    ):
        """
        Initialize Greenlight client.

        Args:
            api_url: Base URL for Greenlight API
            timeout_ms: Request timeout in milliseconds
            retry_attempts: Number of retry attempts on failure
        """
        self.api_url = api_url.rstrip("/")
        self.timeout_seconds = timeout_ms / 1000.0
        self.retry_attempts = retry_attempts
        self.client = httpx.AsyncClient(
            timeout=httpx.Timeout(self.timeout_seconds),
            follow_redirects=True,
        )

    async def close(self) -> None:
        """Close the HTTP client."""
        await self.client.aclose()

    async def execute_atom(
        self,
        request: GreenlightAtomRequest,
    ) -> GreenlightAtomResult:
        """
        Execute an atom synchronously with retry logic.

        Args:
            request: Atom execution request

        Returns:
            Execution result with score and feedback

        Raises:
            httpx.HTTPError: On API communication failure
        """
        last_error: Exception | None = None

        for attempt in range(self.retry_attempts):
            try:
                response = await self.client.post(
                    f"{self.api_url}/greenlight/run-atom",
                    json=request.to_dict(),
                )
                response.raise_for_status()

                data = response.json()
                return GreenlightAtomResult.from_dict(data)

            except httpx.TimeoutException as e:
                last_error = e
                wait_time = 2 ** attempt  # Exponential backoff: 1s, 2s, 4s
                logger.warning(
                    f"Greenlight timeout on attempt {attempt + 1}/{self.retry_attempts}. "
                    f"Retrying in {wait_time}s..."
                )
                if attempt < self.retry_attempts - 1:
                    await asyncio.sleep(wait_time)

            except httpx.HTTPStatusError as e:
                last_error = e
                if e.response.status_code >= 500:
                    # Retry on 5xx server errors
                    wait_time = 2 ** attempt
                    logger.warning(
                        f"Greenlight server error {e.response.status_code} on attempt "
                        f"{attempt + 1}/{self.retry_attempts}. Retrying in {wait_time}s..."
                    )
                    if attempt < self.retry_attempts - 1:
                        await asyncio.sleep(wait_time)
                else:
                    # Don't retry on 4xx client errors
                    logger.error(f"Greenlight client error: {e.response.status_code}")
                    raise

            except httpx.RequestError as e:
                last_error = e
                wait_time = 2 ** attempt
                logger.warning(
                    f"Greenlight request error on attempt {attempt + 1}/{self.retry_attempts}: {e}. "
                    f"Retrying in {wait_time}s..."
                )
                if attempt < self.retry_attempts - 1:
                    await asyncio.sleep(wait_time)

        # All retries exhausted
        error_msg = f"Greenlight execution failed after {self.retry_attempts} attempts"
        logger.error(f"{error_msg}: {last_error}")
        return GreenlightAtomResult(
            atom_id=request.atom_id,
            correct=False,
            partial_score=0.0,
            feedback="Greenlight service unavailable. Please try again later.",
            error=str(last_error),
        )

    async def queue_atom(
        self,
        request: GreenlightAtomRequest,
    ) -> str:
        """
        Queue an atom for asynchronous execution.

        Args:
            request: Atom execution request

        Returns:
            Execution ID for polling

        Raises:
            httpx.HTTPError: On API communication failure
        """
        try:
            response = await self.client.post(
                f"{self.api_url}/greenlight/queue-atom",
                json=request.to_dict(),
            )
            response.raise_for_status()

            data = response.json()
            return data.get("execution_id", "")

        except httpx.HTTPError as e:
            logger.error(f"Failed to queue atom for Greenlight execution: {e}")
            raise

    async def poll_execution(
        self,
        execution_id: str,
    ) -> GreenlightExecutionStatus:
        """
        Poll for the status of a queued execution.

        Args:
            execution_id: Execution ID from queue_atom()

        Returns:
            Execution status with optional result

        Raises:
            httpx.HTTPError: On API communication failure
        """
        try:
            response = await self.client.get(
                f"{self.api_url}/greenlight/execution/{execution_id}",
            )
            response.raise_for_status()

            data = response.json()
            status = data.get("status", "unknown")
            result_data = data.get("result")

            return GreenlightExecutionStatus(
                execution_id=execution_id,
                status=status,
                result=GreenlightAtomResult.from_dict(result_data) if result_data else None,
                error=data.get("error"),
            )

        except httpx.HTTPError as e:
            logger.error(f"Failed to poll Greenlight execution {execution_id}: {e}")
            raise

    async def health_check(self) -> bool:
        """
        Check if Greenlight API is available.

        Returns:
            True if API is healthy, False otherwise
        """
        try:
            response = await self.client.get(
                f"{self.api_url}/health",
                timeout=5.0,
            )
            return response.status_code == 200

        except httpx.HTTPError:
            return False
