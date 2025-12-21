import asyncio

from src.cortex.session import CortexSession
from src.integrations.greenlight_client import (
    GreenlightAtomResult,
    GreenlightExecutionStatus,
)


class FakeGreenlightClient:
    def __init__(self, result: GreenlightAtomResult):
        self._result = result

    async def execute_atom(self, request):
        return self._result

    async def queue_atom(self, request):
        return "exec-123"

    async def poll_execution(self, execution_id):
        return GreenlightExecutionStatus(
            execution_id=execution_id,
            status="complete",
            result=self._result,
        )


def test_greenlight_disabled_skips_atom():
    session = CortexSession(modules=[1], limit=1)
    session.greenlight_enabled = False
    session.greenlight_client = None

    note = {
        "id": "atom-1",
        "atom_type": "code_submission",
        "front": "Write a function",
        "back": "def add(a, b): return a + b",
        "content_json": {"owner": "greenlight"},
    }

    result = session._process_atom_interaction(note)

    assert result.get("skipped") is True


def test_greenlight_sync_execution_returns_result():
    session = CortexSession(modules=[1], limit=1)
    session.greenlight_enabled = True
    session.greenlight_client = FakeGreenlightClient(
        GreenlightAtomResult(
            atom_id="atom-1",
            correct=True,
            partial_score=0.8,
            feedback="OK",
            test_results=[{"name": "test_add", "passed": True}],
            meta={"execution_time_ms": 123},
        )
    )
    session._run_async = lambda coro: asyncio.run(coro)

    note = {
        "id": "atom-1",
        "atom_type": "code_submission",
        "front": "Write a function",
        "back": "def add(a, b): return a + b",
        "content_json": {"owner": "greenlight"},
    }

    result = session._process_atom_interaction(note)

    assert result["correct"] is True
    assert result["time_ms"] == 123
