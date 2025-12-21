"""
Unit tests for Greenlight API client.
"""

import pytest
import pytest_asyncio
from httpx import AsyncClient, Request, Response

from src.integrations.greenlight_client import (
    GreenlightAtomRequest,
    GreenlightAtomResult,
    GreenlightClient,
    GreenlightExecutionStatus,
)


@pytest.fixture
def sample_request():
    """Sample atom request for testing."""
    return GreenlightAtomRequest(
        atom_id="test-atom-001",
        atom_type="code_submission",
        content={
            "front": "Write a function to add two numbers",
            "back": "def add(a, b): return a + b",
            "content_json": {
                "runner": {
                    "language": "python",
                    "version": "3.11",
                    "entrypoint": "solution.py",
                    "tests": [{"input": [2, 3], "expected": 5}],
                }
            },
        },
        session_context={
            "learner_id": "learner-123",
            "current_mastery": 0.75,
        },
    )


@pytest.fixture
def sample_result_success():
    """Sample successful result for testing."""
    return {
        "atom_id": "test-atom-001",
        "correct": True,
        "partial_score": 1.0,
        "feedback": "All tests passed!",
        "test_results": {
            "passed": ["test_basic_addition"],
            "failed": [],
            "stdout": "Test 1: PASS\n",
            "stderr": "",
        },
        "git_suggestions": ["git add solution.py", "git commit -m 'Add function'"],
        "meta": {
            "confidence": 4,
            "difficulty": 2,
        },
    }


@pytest.fixture
def sample_result_partial():
    """Sample partial success result for testing."""
    return {
        "atom_id": "test-atom-001",
        "correct": False,
        "partial_score": 0.6,
        "feedback": "3 of 5 tests passed. Check edge cases.",
        "test_results": {
            "passed": ["test_basic", "test_positive", "test_negative"],
            "failed": ["test_zero", "test_overflow"],
            "stdout": "Test 1: PASS\nTest 2: PASS\nTest 3: PASS\nTest 4: FAIL\nTest 5: FAIL\n",
            "stderr": "",
        },
        "meta": {
            "confidence": 3,
            "difficulty": 4,
        },
    }


@pytest_asyncio.fixture
async def client():
    """Greenlight client instance."""
    client = GreenlightClient(
        api_url="http://localhost:8090",
        timeout_ms=5000,
        retry_attempts=3,
    )
    yield client
    await client.close()


class TestGreenlightAtomRequest:
    """Tests for GreenlightAtomRequest dataclass."""

    def test_to_dict(self, sample_request):
        """Test converting request to dictionary."""
        data = sample_request.to_dict()

        assert data["atom_id"] == "test-atom-001"
        assert data["atom_type"] == "code_submission"
        assert "content" in data
        assert "session_context" in data
        assert data["session_context"]["learner_id"] == "learner-123"


class TestGreenlightAtomResult:
    """Tests for GreenlightAtomResult dataclass."""

    def test_from_dict_success(self, sample_result_success):
        """Test parsing successful result from dictionary."""
        result = GreenlightAtomResult.from_dict(sample_result_success)

        assert result.atom_id == "test-atom-001"
        assert result.correct is True
        assert result.partial_score == 1.0
        assert result.feedback == "All tests passed!"
        assert len(result.test_results["passed"]) == 1
        assert len(result.git_suggestions) == 2
        assert result.meta["confidence"] == 4

    def test_from_dict_partial(self, sample_result_partial):
        """Test parsing partial success result from dictionary."""
        result = GreenlightAtomResult.from_dict(sample_result_partial)

        assert result.atom_id == "test-atom-001"
        assert result.correct is False
        assert result.partial_score == 0.6
        assert len(result.test_results["passed"]) == 3
        assert len(result.test_results["failed"]) == 2

    def test_from_dict_with_error(self):
        """Test parsing result with error."""
        data = {
            "atom_id": "test-atom-001",
            "correct": False,
            "partial_score": 0.0,
            "error": "Compilation failed",
        }
        result = GreenlightAtomResult.from_dict(data)

        assert result.error == "Compilation failed"
        assert result.partial_score == 0.0


class TestGreenlightClient:
    """Tests for GreenlightClient class."""

    @pytest.mark.asyncio
    async def test_execute_atom_success(self, client, sample_request, sample_result_success, monkeypatch):
        """Test successful atom execution."""
        async def mock_post(url, **kwargs):
            request = Request("POST", url)
            return Response(200, json=sample_result_success, request=request)

        monkeypatch.setattr(client.client, "post", mock_post)

        result = await client.execute_atom(sample_request)

        assert result.correct is True
        assert result.partial_score == 1.0
        assert result.atom_id == "test-atom-001"

    @pytest.mark.asyncio
    async def test_execute_atom_partial_score(self, client, sample_request, sample_result_partial, monkeypatch):
        """Test atom execution with partial credit."""
        async def mock_post(url, **kwargs):
            request = Request("POST", url)
            return Response(200, json=sample_result_partial, request=request)

        monkeypatch.setattr(client.client, "post", mock_post)

        result = await client.execute_atom(sample_request)

        assert result.correct is False
        assert result.partial_score == 0.6
        assert len(result.test_results["failed"]) == 2

    @pytest.mark.asyncio
    async def test_execute_atom_timeout_retry(self, client, sample_request, sample_result_success, monkeypatch):
        """Test retry logic on timeout."""
        call_count = 0

        async def mock_post(url, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                # First call times out
                from httpx import TimeoutException
                raise TimeoutException("Timeout")
            # Second call succeeds
            request = Request("POST", url)
            return Response(200, json=sample_result_success, request=request)

        monkeypatch.setattr(client.client, "post", mock_post)

        result = await client.execute_atom(sample_request)

        assert call_count == 2  # Should have retried once
        assert result.correct is True

    @pytest.mark.asyncio
    async def test_execute_atom_server_error_retry(self, client, sample_request, sample_result_success, monkeypatch):
        """Test retry logic on 5xx server errors."""
        call_count = 0

        async def mock_post(url, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                # First call returns 500
                from httpx import HTTPStatusError
                req = Request("POST", url)
                response = Response(500, json={"error": "Internal server error"}, request=req)
                raise HTTPStatusError("Server error", request=req, response=response)
            # Second call succeeds
            request = Request("POST", url)
            return Response(200, json=sample_result_success, request=request)

        monkeypatch.setattr(client.client, "post", mock_post)

        result = await client.execute_atom(sample_request)

        assert call_count == 2  # Should have retried once
        assert result.correct is True

    @pytest.mark.asyncio
    async def test_execute_atom_client_error_no_retry(self, client, sample_request, monkeypatch):
        """Test that 4xx errors don't trigger retries."""
        call_count = 0

        async def mock_post(url, **kwargs):
            nonlocal call_count
            call_count += 1
            from httpx import HTTPStatusError
            response = Response(400, json={"error": "Bad request"})
            raise HTTPStatusError("Client error", request=Request("POST", url), response=response)

        monkeypatch.setattr(client.client, "post", mock_post)

        with pytest.raises(Exception):  # Should raise without retrying
            await client.execute_atom(sample_request)

        assert call_count == 1  # Should not have retried

    @pytest.mark.asyncio
    async def test_execute_atom_all_retries_exhausted(self, client, sample_request, monkeypatch):
        """Test behavior when all retries are exhausted."""
        call_count = 0

        async def mock_post(url, **kwargs):
            nonlocal call_count
            call_count += 1
            from httpx import TimeoutException
            raise TimeoutException("Timeout")

        monkeypatch.setattr(client.client, "post", mock_post)

        result = await client.execute_atom(sample_request)

        assert call_count == 3  # Should have tried 3 times
        assert result.correct is False
        assert result.partial_score == 0.0
        assert "unavailable" in result.feedback.lower()
        assert result.error is not None

    @pytest.mark.asyncio
    async def test_queue_atom(self, client, sample_request, monkeypatch):
        """Test queuing an atom for async execution."""
        async def mock_post(url, **kwargs):
            request = Request("POST", url)
            return Response(200, json={"execution_id": "exec-12345"}, request=request)

        monkeypatch.setattr(client.client, "post", mock_post)

        execution_id = await client.queue_atom(sample_request)

        assert execution_id == "exec-12345"

    @pytest.mark.asyncio
    async def test_poll_execution_pending(self, client, monkeypatch):
        """Test polling for a pending execution."""
        async def mock_get(url, **kwargs):
            request = Request("GET", url)
            return Response(200, json={
                "status": "pending",
                "result": None,
                "error": None,
            }, request=request)

        monkeypatch.setattr(client.client, "get", mock_get)

        status = await client.poll_execution("exec-12345")

        assert status.status == "pending"
        assert status.result is None

    @pytest.mark.asyncio
    async def test_poll_execution_complete(self, client, sample_result_success, monkeypatch):
        """Test polling for a completed execution."""
        async def mock_get(url, **kwargs):
            request = Request("GET", url)
            return Response(200, json={
                "status": "complete",
                "result": sample_result_success,
                "error": None,
            }, request=request)

        monkeypatch.setattr(client.client, "get", mock_get)

        status = await client.poll_execution("exec-12345")

        assert status.status == "complete"
        assert status.result is not None
        assert status.result.correct is True
        assert status.result.partial_score == 1.0

    @pytest.mark.asyncio
    async def test_poll_execution_failed(self, client, monkeypatch):
        """Test polling for a failed execution."""
        async def mock_get(url, **kwargs):
            request = Request("GET", url)
            return Response(200, json={
                "status": "failed",
                "result": None,
                "error": "Execution timeout",
            }, request=request)

        monkeypatch.setattr(client.client, "get", mock_get)

        status = await client.poll_execution("exec-12345")

        assert status.status == "failed"
        assert status.error == "Execution timeout"
        assert status.result is None

    @pytest.mark.asyncio
    async def test_health_check_healthy(self, client, monkeypatch):
        """Test health check when service is available."""
        async def mock_get(url, **kwargs):
            request = Request("GET", url)
            return Response(200, json={"status": "healthy"}, request=request)

        monkeypatch.setattr(client.client, "get", mock_get)

        is_healthy = await client.health_check()

        assert is_healthy is True

    @pytest.mark.asyncio
    async def test_health_check_unhealthy(self, client, monkeypatch):
        """Test health check when service is unavailable."""
        async def mock_get(url, **kwargs):
            from httpx import RequestError
            raise RequestError("Connection refused")

        monkeypatch.setattr(client.client, "get", mock_get)

        is_healthy = await client.health_check()

        assert is_healthy is False
