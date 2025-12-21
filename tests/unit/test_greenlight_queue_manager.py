from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from src.integrations.greenlight_queue_manager import GreenlightQueueManager


class FakeResult:
    def __init__(self, scalar_value=None, rowcount=0, first_row=None, rows=None):
        self._scalar_value = scalar_value
        self.rowcount = rowcount
        self._first_row = first_row
        self._rows = rows or []

    def scalar_one(self):
        return self._scalar_value

    def first(self):
        return self._first_row

    def fetchall(self):
        return self._rows


@pytest.mark.asyncio
async def test_enqueue_returns_id():
    session = AsyncMock()
    session.execute.return_value = FakeResult(scalar_value="queue-123")
    manager = GreenlightQueueManager(session)

    queue_id = await manager.enqueue(
        atom_id="atom-1",
        learner_id="learner-1",
        request_payload={"atom_type": "code_submission"},
    )

    assert queue_id == "queue-123"
    assert session.execute.called


@pytest.mark.asyncio
async def test_mark_executing_updates_status():
    session = AsyncMock()
    session.execute.return_value = FakeResult(rowcount=1)
    manager = GreenlightQueueManager(session)

    updated = await manager.mark_executing("queue-123")

    assert updated is True


@pytest.mark.asyncio
async def test_mark_failed_requeues_when_retry_available():
    session = AsyncMock()
    session.execute.side_effect = [
        FakeResult(first_row=(1, 3)),
        FakeResult(),
    ]
    manager = GreenlightQueueManager(session)

    requeued = await manager.mark_failed("queue-123", "boom")

    assert requeued is True
    assert session.execute.call_count == 2


@pytest.mark.asyncio
async def test_mark_failed_stops_after_max_retries():
    session = AsyncMock()
    session.execute.return_value = FakeResult(first_row=(3, 3))
    manager = GreenlightQueueManager(session)

    requeued = await manager.mark_failed("queue-123", "boom")

    assert requeued is False
    assert session.execute.call_count == 1


@pytest.mark.asyncio
async def test_get_pending_maps_rows():
    session = AsyncMock()
    sample_row = SimpleNamespace(
        _mapping={
            "id": "queue-123",
            "atom_id": "atom-1",
            "learner_id": "learner-1",
            "execution_id": "exec-1",
            "status": "pending",
            "request_payload": {"atom_type": "code_submission"},
            "result_payload": None,
            "queued_at": "2025-01-01T00:00:00Z",
            "started_at": None,
            "completed_at": None,
            "error_message": None,
            "retry_count": 0,
            "max_retries": 3,
        }
    )
    session.execute.return_value = FakeResult(rows=[sample_row])
    manager = GreenlightQueueManager(session)

    pending = await manager.get_pending(limit=1)

    assert len(pending) == 1
    assert pending[0].id == "queue-123"
