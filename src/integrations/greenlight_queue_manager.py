"""Greenlight Queue Manager for async execution tracking."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Mapping

from loguru import logger
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


@dataclass
class QueuedExecution:
    """Queued Greenlight execution record."""

    id: str
    atom_id: str | None
    learner_id: str
    execution_id: str | None
    status: str
    request_payload: dict[str, Any]
    result_payload: dict[str, Any] | None
    queued_at: datetime
    started_at: datetime | None
    completed_at: datetime | None
    error_message: str | None
    retry_count: int
    max_retries: int


class GreenlightQueueManager:
    """Manage Greenlight execution queue."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def enqueue(
        self,
        atom_id: str | None,
        learner_id: str,
        request_payload: Mapping[str, Any],
        execution_id: str | None = None,
    ) -> str:
        """
        Add atom to Greenlight queue.

        Args:
            atom_id: Atom UUID (optional)
            learner_id: Learner UUID
            request_payload: Greenlight request payload
            execution_id: Optional Greenlight execution ID

        Returns:
            Queue record ID (UUID)
        """
        query = text(
            """
            INSERT INTO greenlight_queue (
                atom_id, learner_id, execution_id, request_payload, status
            ) VALUES (:atom_id, :learner_id, :execution_id, :request_payload, 'pending')
            RETURNING id
            """
        )
        result = await self.session.execute(
            query,
            {
                "atom_id": atom_id,
                "learner_id": learner_id,
                "execution_id": execution_id,
                "request_payload": dict(request_payload),
            },
        )
        queue_id = result.scalar_one()
        logger.info(
            "Enqueued atom {} for learner {}: queue_id={}",
            atom_id,
            learner_id,
            queue_id,
        )
        return str(queue_id)

    async def mark_executing(self, queue_id: str) -> bool:
        """Mark queued item as executing."""
        query = text(
            """
            UPDATE greenlight_queue
            SET status = 'executing', started_at = NOW()
            WHERE id = :queue_id AND status = 'pending'
            """
        )
        result = await self.session.execute(query, {"queue_id": queue_id})
        updated = result.rowcount == 1
        if updated:
            logger.info("Marked queue item {} as executing", queue_id)
        return updated

    async def mark_complete(
        self,
        queue_id: str,
        result_payload: Mapping[str, Any],
    ) -> None:
        """Mark queued item as complete with result."""
        query = text(
            """
            UPDATE greenlight_queue
            SET status = 'complete', result_payload = :result_payload, completed_at = NOW()
            WHERE id = :queue_id
            """
        )
        await self.session.execute(
            query,
            {"queue_id": queue_id, "result_payload": dict(result_payload)},
        )
        logger.info("Marked queue item {} as complete", queue_id)

    async def mark_failed(
        self,
        queue_id: str,
        error_message: str,
        increment_retry: bool = True,
    ) -> bool:
        """
        Mark queued item as failed.

        Returns:
            True if item was re-queued for retry, False if permanently failed.
        """
        if increment_retry:
            query = text(
                """
                UPDATE greenlight_queue
                SET status = 'failed', error_message = :error_message,
                    retry_count = retry_count + 1
                WHERE id = :queue_id
                RETURNING retry_count, max_retries
                """
            )
            result = await self.session.execute(
                query,
                {"queue_id": queue_id, "error_message": error_message},
            )
            row = result.first()
            if not row:
                logger.warning("Queue item {} not found for failure update", queue_id)
                return False

            retry_count = row[0]
            max_retries = row[1]
            if retry_count < max_retries:
                await self.session.execute(
                    text(
                        "UPDATE greenlight_queue SET status = 'pending' WHERE id = :queue_id"
                    ),
                    {"queue_id": queue_id},
                )
                logger.warning(
                    "Queue item {} failed (attempt {}/{}), re-queued",
                    queue_id,
                    retry_count,
                    max_retries,
                )
                return True

            logger.error(
                "Queue item {} failed permanently after {} retries: {}",
                queue_id,
                retry_count,
                error_message,
            )
            return False

        query = text(
            """
            UPDATE greenlight_queue
            SET status = 'failed', error_message = :error_message
            WHERE id = :queue_id
            """
        )
        await self.session.execute(
            query,
            {"queue_id": queue_id, "error_message": error_message},
        )
        logger.error("Queue item {} failed: {}", queue_id, error_message)
        return False

    async def get_pending(self, limit: int = 10) -> list[QueuedExecution]:
        """Get pending queue items."""
        query = text(
            """
            SELECT *
            FROM greenlight_queue
            WHERE status = 'pending'
            ORDER BY queued_at ASC
            LIMIT :limit
            """
        )
        result = await self.session.execute(query, {"limit": limit})
        return [self._row_to_queued_execution(row) for row in result.fetchall()]

    def _row_to_queued_execution(self, row: Any) -> QueuedExecution:
        """Convert database row to QueuedExecution."""
        mapping = row._mapping if hasattr(row, "_mapping") else row
        return QueuedExecution(
            id=str(mapping["id"]),
            atom_id=str(mapping["atom_id"]) if mapping.get("atom_id") else None,
            learner_id=str(mapping["learner_id"]),
            execution_id=mapping.get("execution_id"),
            status=mapping["status"],
            request_payload=dict(mapping["request_payload"]),
            result_payload=dict(mapping["result_payload"])
            if mapping.get("result_payload") is not None
            else None,
            queued_at=mapping["queued_at"],
            started_at=mapping.get("started_at"),
            completed_at=mapping.get("completed_at"),
            error_message=mapping.get("error_message"),
            retry_count=mapping["retry_count"],
            max_retries=mapping["max_retries"],
        )
