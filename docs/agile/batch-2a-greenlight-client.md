# Batch 2a: Greenlight HTTP Client

**Branch:** `batch-2a-greenlight-client`
**Worktree:** `../cortex-batch-2a-greenlight-client`
**Priority:** HIGH (Infrastructure - Independent)
**Estimated Effort:** 2 days
**Status:** Pending

## Objective

Implement HTTP client for Greenlight handoff protocol with retry logic, async execution, and result polling.

## Dependencies

**Required:**
- Python httpx library (`pip install httpx`)
- Greenlight API specification (mocked for now)

**Blocks:**
- Batch 2b (SessionManager integration needs this client)

## Files to Create

### 1. src/integrations/greenlight_client.py

```python
"""
Greenlight HTTP Client for Runtime Atom Execution.

This module handles communication with the Greenlight IDE/runtime environment
for executing code-based atoms, debugging tasks, and CLI simulations.
"""

import httpx
from typing import Optional, Dict, Any
from dataclasses import dataclass, field
import logging
import asyncio

logger = logging.getLogger(__name__)

@dataclass
class GreenlightAtomRequest:
    """Request payload for Greenlight atom execution."""
    atom_id: str
    atom_type: str
    front: str
    back: str
    content_json: Dict[str, Any]
    session_context: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        """Convert to dict for JSON serialization."""
        return {
            "atom_id": self.atom_id,
            "atom_type": self.atom_type,
            "front": self.front,
            "back": self.back,
            "content_json": self.content_json,
            "session_context": self.session_context
        }

@dataclass
class GreenlightAtomResult:
    """Response from Greenlight execution."""
    atom_id: str
    partial_score: float            # 0.0 to 1.0
    tests_passed: int
    tests_total: int
    test_results: list[Dict[str, Any]]  # Detailed test outcomes
    error_class: Optional[str] = None      # syntax, logic, runtime, timeout
    git_suggestions: Optional[list[str]] = None  # Typed suggestions for learner
    execution_time_ms: int = 0
    meta_cognitive: Optional[Dict[str, Any]] = None  # Confidence, difficulty rating

class GreenlightClient:
    """
    HTTP client for Greenlight handoff protocol.

    Handles:
    - Atom execution requests
    - Retry logic with exponential backoff
    - Queuing for async execution
    - Result polling
    """

    def __init__(
        self,
        base_url: str,
        timeout_ms: int = 30000,
        retry_attempts: int = 3
    ):
        """
        Initialize Greenlight client.

        Args:
            base_url: Greenlight API base URL (e.g., http://localhost:8080)
            timeout_ms: Request timeout in milliseconds
            retry_attempts: Maximum retry attempts on timeout/error
        """
        self.base_url = base_url.rstrip('/')
        self.timeout_ms = timeout_ms
        self.retry_attempts = retry_attempts
        self.client = httpx.AsyncClient(timeout=timeout_ms / 1000.0)

    async def close(self):
        """Close HTTP client connection."""
        await self.client.aclose()

    async def execute_atom(
        self,
        request: GreenlightAtomRequest
    ) -> GreenlightAtomResult:
        """
        Execute atom in Greenlight environment.

        POST /greenlight/run-atom
        {
            "atom_id": "uuid",
            "atom_type": "code_submission",
            "front": "Write a function...",
            "back": "def solution()...",
            "content_json": {
                "language": "python",
                "entrypoint": "solution.py",
                "tests": [...],
                "runner_limits": {"cpu_ms": 5000, "memory_mb": 256}
            },
            "session_context": {
                "learner_id": "uuid",
                "mastery_level": 0.65,
                "recent_errors": ["off_by_one"]
            }
        }

        Response:
        {
            "atom_id": "uuid",
            "partial_score": 0.75,
            "tests_passed": 3,
            "tests_total": 4,
            "test_results": [{...}],
            "error_class": "logic",
            "git_suggestions": ["Check loop condition"],
            "execution_time_ms": 2340,
            "meta_cognitive": {"difficulty_rating": 3}
        }

        Args:
            request: GreenlightAtomRequest object

        Returns:
            GreenlightAtomResult object

        Raises:
            httpx.TimeoutException: If request times out after all retries
            httpx.HTTPStatusError: If server returns error status
        """
        url = f"{self.base_url}/greenlight/run-atom"
        payload = request.to_dict()

        for attempt in range(self.retry_attempts):
            try:
                logger.info(f"Greenlight execute_atom attempt {attempt + 1}/{self.retry_attempts}: {request.atom_id}")
                response = await self.client.post(url, json=payload)
                response.raise_for_status()
                data = response.json()

                return GreenlightAtomResult(
                    atom_id=data["atom_id"],
                    partial_score=data.get("partial_score", 0.0),
                    tests_passed=data.get("tests_passed", 0),
                    tests_total=data.get("tests_total", 0),
                    test_results=data.get("test_results", []),
                    error_class=data.get("error_class"),
                    git_suggestions=data.get("git_suggestions"),
                    execution_time_ms=data.get("execution_time_ms", 0),
                    meta_cognitive=data.get("meta_cognitive")
                )

            except httpx.TimeoutException:
                logger.warning(
                    f"Greenlight timeout on attempt {attempt + 1}/{self.retry_attempts} "
                    f"for atom {request.atom_id}"
                )
                if attempt == self.retry_attempts - 1:
                    raise
                # Exponential backoff: 2^attempt seconds
                await asyncio.sleep(2 ** attempt)

            except httpx.HTTPStatusError as e:
                logger.error(
                    f"Greenlight HTTP error {e.response.status_code}: {e.response.text} "
                    f"for atom {request.atom_id}"
                )
                raise

    async def queue_atom(
        self,
        request: GreenlightAtomRequest
    ) -> str:
        """
        Queue atom for async execution (for long-running atoms).

        POST /greenlight/queue-atom

        Args:
            request: GreenlightAtomRequest object

        Returns:
            execution_id (str) to poll for results

        Raises:
            httpx.HTTPStatusError: If server returns error status
        """
        url = f"{self.base_url}/greenlight/queue-atom"
        payload = request.to_dict()

        logger.info(f"Greenlight queue_atom: {request.atom_id}")
        response = await self.client.post(url, json=payload)
        response.raise_for_status()
        data = response.json()

        execution_id = data["execution_id"]
        logger.info(f"Queued atom {request.atom_id} with execution_id: {execution_id}")

        return execution_id

    async def poll_execution(
        self,
        execution_id: str
    ) -> Optional[GreenlightAtomResult]:
        """
        Poll for queued atom execution result.

        GET /greenlight/execution/{execution_id}

        Args:
            execution_id: Execution ID from queue_atom()

        Returns:
            GreenlightAtomResult if complete, None if still pending

        Raises:
            httpx.HTTPStatusError: If server returns error status
        """
        url = f"{self.base_url}/greenlight/execution/{execution_id}"

        logger.debug(f"Polling execution: {execution_id}")
        response = await self.client.get(url)
        response.raise_for_status()
        data = response.json()

        status = data.get("status")

        if status == "complete":
            result_data = data["result"]
            return GreenlightAtomResult(
                atom_id=data["atom_id"],
                partial_score=result_data["partial_score"],
                tests_passed=result_data["tests_passed"],
                tests_total=result_data["tests_total"],
                test_results=result_data["test_results"],
                error_class=result_data.get("error_class"),
                git_suggestions=result_data.get("git_suggestions"),
                execution_time_ms=result_data["execution_time_ms"],
                meta_cognitive=result_data.get("meta_cognitive")
            )
        elif status == "failed":
            logger.error(f"Execution {execution_id} failed: {data.get('error_message')}")
            raise RuntimeError(f"Execution failed: {data.get('error_message')}")
        else:
            # Still pending or running
            return None

    async def poll_until_complete(
        self,
        execution_id: str,
        poll_interval_sec: float = 2.0,
        max_wait_sec: float = 300.0
    ) -> GreenlightAtomResult:
        """
        Poll execution until complete or timeout.

        Args:
            execution_id: Execution ID from queue_atom()
            poll_interval_sec: Seconds between polls
            max_wait_sec: Maximum wait time before timeout

        Returns:
            GreenlightAtomResult when complete

        Raises:
            TimeoutError: If max_wait_sec exceeded
            RuntimeError: If execution fails
        """
        start_time = asyncio.get_event_loop().time()

        while True:
            result = await self.poll_execution(execution_id)

            if result is not None:
                return result

            # Check timeout
            elapsed = asyncio.get_event_loop().time() - start_time
            if elapsed > max_wait_sec:
                raise TimeoutError(
                    f"Execution {execution_id} timed out after {elapsed:.1f} seconds"
                )

            # Wait before next poll
            await asyncio.sleep(poll_interval_sec)
```

## Checklist

- [ ] Create `src/integrations/` directory
- [ ] Create `greenlight_client.py` with all dataclasses and methods
- [ ] Implement `execute_atom()` with retry logic
- [ ] Implement `queue_atom()` for async execution
- [ ] Implement `poll_execution()` for result polling
- [ ] Implement `poll_until_complete()` helper
- [ ] Add exponential backoff (2^attempt seconds)
- [ ] Write unit tests with mock httpx responses
- [ ] Test timeout handling
- [ ] Test retry logic
- [ ] Test error handling (4xx, 5xx)

## Testing

### Manual Validation

```bash
# Unit tests with mocked httpx
pytest tests/integrations/test_greenlight_client.py -v

# Manual test with mock server
python -c "
from src.integrations.greenlight_client import GreenlightClient, GreenlightAtomRequest
import asyncio

async def test():
    client = GreenlightClient(base_url='http://localhost:8080')

    request = GreenlightAtomRequest(
        atom_id='test-atom-123',
        atom_type='code_submission',
        front='Write a function that adds two numbers',
        back='def add(a, b): return a + b',
        content_json={'language': 'python', 'tests': []},
        session_context={'learner_id': 'test-learner'}
    )

    # Test synchronous execution
    result = await client.execute_atom(request)
    print(f'Score: {result.partial_score}, Tests: {result.tests_passed}/{result.tests_total}')

    # Test async execution
    execution_id = await client.queue_atom(request)
    result = await client.poll_until_complete(execution_id)
    print(f'Async execution complete: {result.partial_score}')

    await client.close()

asyncio.run(test())
"
```



### BDD Testing Requirements

**See:** [BDD Testing Strategy](../explanation/bdd-testing-strategy.md)

Create tests appropriate for this batch:
- Unit tests for all new classes/functions
- Integration tests for database interactions
- Property-based tests for complex logic (use hypothesis)

### CI Checks

**See:** [CI/CD Pipeline](../explanation/ci-cd-pipeline.md)

This batch must pass:
- Linting (ruff check)
- Type checking (mypy --strict)
- Security scan (bandit)
- Unit tests (85% coverage minimum)
- Integration tests (all critical paths)

## Commit Strategy

```bash
cd ../cortex-batch-2a-greenlight-client

git add src/integrations/greenlight_client.py
git commit -m "feat(batch2a): Add Greenlight HTTP client with retry logic

Implemented:
- GreenlightAtomRequest and GreenlightAtomResult dataclasses
- GreenlightClient with async httpx
- execute_atom() with exponential backoff retry
- queue_atom() and poll_execution() for async execution
- poll_until_complete() helper method

- Generated with Claude Code

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>"

git add tests/integrations/test_greenlight_client.py
git commit -m "test(batch2a): Add unit tests for Greenlight client

- Generated with Claude Code

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>"

git push -u origin batch-2a-greenlight-client
```

## GitHub Issues

```bash
gh issue create \
  --title "[Batch 2a] Greenlight HTTP Client" \
  --body "Implement HTTP client for Greenlight handoff protocol.\\n\\n**File:** src/integrations/greenlight_client.py\\n\\n**Features:**\\n- Async HTTP client with httpx\\n- Retry logic with exponential backoff\\n- Async execution and polling\\n\\n**Status:** Complete" \
  --label "batch-2a,greenlight,enhancement" \
  --milestone "Phase 1: Foundation"
```

## Success Metrics

- [ ] All unit tests passing
- [ ] Retry logic works correctly (3 attempts, exponential backoff)
- [ ] Timeout handling works
- [ ] Error handling for 4xx, 5xx works
- [ ] Async execution and polling works

## Reference

### Strategy Documents
- [BDD Testing Strategy](../explanation/bdd-testing-strategy.md) - Testing approach for cognitive validity
- [CI/CD Pipeline](../explanation/ci-cd-pipeline.md) - Automated quality gates and deployment
- [Atom Type Taxonomy](../explanation/learning-atom-taxonomy.md) - 100+ atom types with ICAP classification
- [Schema Migration Plan](../explanation/schema-migration-plan.md) - Migration to polymorphic JSONB atoms

### Work Orders
- **Master Plan:** `C:\\Users\\Shadow\\.claude\\plans\\tidy-conjuring-moonbeam.md` lines 533-724
- **Parent Work Order:** `docs/agile/batch-2-greenlight.md`


---

**Status:** Pending
**AI Coder:** Ready for assignment
**Start Condition:** START IMMEDIATELY (no dependencies)
## testing and ci

- add or update tests relevant to this batch
- add or update bdd scenarios where applicable
- ensure pr-checks.yml passes before merge


