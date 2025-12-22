# Batch 2c: Greenlight Database Queue

**Branch:** `batch-2c-greenlight-database`
**Worktree:** `../cortex-batch-2c-greenlight-database`
**Priority:** MEDIUM (Independent)
**Estimated Effort:** 1 day
**Status:** Pending

## Objective

Create database table and indexes for queueing Greenlight atoms for async execution with status tracking.

## Dependencies

**Required:**
- PostgreSQL database running
- Existing `learning_atoms` table

**Blocks:**
- None (independent of other batches)

## Files to Create

### 1. src/db/migrations/031_greenlight_queue.sql

```sql
-- Greenlight async execution queue
CREATE TABLE greenlight_queue (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    atom_id UUID REFERENCES learning_atoms(id) ON DELETE CASCADE,
    learner_id UUID NOT NULL,
    execution_id VARCHAR(100) UNIQUE,  -- From Greenlight API
    status VARCHAR(20) DEFAULT 'pending',  -- pending, executing, complete, failed
    request_payload JSONB NOT NULL,
    result_payload JSONB,
    queued_at TIMESTAMPTZ DEFAULT NOW(),
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    error_message TEXT,
    retry_count INTEGER DEFAULT 0,
    max_retries INTEGER DEFAULT 3
);

-- Indexes for fast queries
CREATE INDEX idx_greenlight_queue_status ON greenlight_queue(status, queued_at);
CREATE INDEX idx_greenlight_queue_learner ON greenlight_queue(learner_id, status);
CREATE INDEX idx_greenlight_queue_execution_id ON greenlight_queue(execution_id) WHERE execution_id IS NOT NULL;

-- Comments for documentation
COMMENT ON TABLE greenlight_queue IS 'Queue for async Greenlight atom execution with retry logic';
COMMENT ON COLUMN greenlight_queue.status IS 'pending = queued, executing = in progress, complete = finished, failed = error';
COMMENT ON COLUMN greenlight_queue.request_payload IS 'JSON payload sent to Greenlight API';
COMMENT ON COLUMN greenlight_queue.result_payload IS 'JSON response from Greenlight API';
COMMENT ON COLUMN greenlight_queue.execution_id IS 'Greenlight execution ID for polling';
```

## Checklist

- [ ] Create `src/db/migrations/031_greenlight_queue.sql`
- [ ] Test migration on PostgreSQL database
- [ ] Verify table created with correct columns
- [ ] Verify indexes created
- [ ] Test JSONB columns can store request/result payloads
- [ ] Test status transitions (pending -> executing -> complete)

## Testing

### Manual Validation

```bash
# Apply migration
psql -U postgres -d cortex_cli -f "src/db/migrations/031_greenlight_queue.sql"

# Verify table
psql -U postgres -d cortex_cli -c "\\d greenlight_queue"

# Test insert
psql -U postgres -d cortex_cli -c "
INSERT INTO greenlight_queue (atom_id, learner_id, request_payload, status)
VALUES (
    (SELECT id FROM learning_atoms LIMIT 1),
    gen_random_uuid(),
    '{\"atom_type\": \"code_submission\", \"language\": \"python\"}',
    'pending'
);
"

# Test query by status
psql -U postgres -d cortex_cli -c "SELECT * FROM greenlight_queue WHERE status = 'pending';"

# Test update status
psql -U postgres -d cortex_cli -c "
UPDATE greenlight_queue
SET status = 'executing', started_at = NOW()
WHERE status = 'pending'
RETURNING *;
"

# Check indexes
psql -U postgres -d cortex_cli -c "
SELECT indexname, indexdef
FROM pg_indexes
WHERE tablename = 'greenlight_queue';
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

## Optional: Queue Manager Class

**File:** `src/integrations/greenlight_queue_manager.py` (optional for this batch)

```python
"""Greenlight Queue Manager for async execution tracking."""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional, List
import logging

logger = logging.getLogger(__name__)

@dataclass
class QueuedExecution:
    """Queued Greenlight execution record."""
    id: str
    atom_id: str
    learner_id: str
    execution_id: Optional[str]
    status: str
    request_payload: dict
    result_payload: Optional[dict]
    queued_at: datetime
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    error_message: Optional[str]
    retry_count: int
    max_retries: int

class GreenlightQueueManager:
    """Manage Greenlight execution queue."""

    def __init__(self, db_connection):
        self.db = db_connection

    async def enqueue(
        self,
        atom_id: str,
        learner_id: str,
        request_payload: dict,
        execution_id: Optional[str] = None
    ) -> str:
        """
        Add atom to Greenlight queue.

        Args:
            atom_id: Atom UUID
            learner_id: Learner UUID
            request_payload: Greenlight request payload
            execution_id: Optional Greenlight execution ID

        Returns:
            Queue record ID (UUID)
        """
        query = """
        INSERT INTO greenlight_queue (
            atom_id, learner_id, execution_id, request_payload, status
        ) VALUES ($1, $2, $3, $4, 'pending')
        RETURNING id
        """

        row = await self.db.fetchrow(
            query,
            atom_id,
            learner_id,
            execution_id,
            request_payload
        )

        queue_id = row["id"]
        logger.info(f"Enqueued atom {atom_id} for learner {learner_id}: queue_id={queue_id}")

        return queue_id

    async def mark_executing(self, queue_id: str):
        """Mark queued item as executing."""
        query = """
        UPDATE greenlight_queue
        SET status = 'executing', started_at = NOW()
        WHERE id = $1 AND status = 'pending'
        """
        await self.db.execute(query, queue_id)
        logger.info(f"Marked queue item {queue_id} as executing")

    async def mark_complete(
        self,
        queue_id: str,
        result_payload: dict
    ):
        """Mark queued item as complete with result."""
        query = """
        UPDATE greenlight_queue
        SET status = 'complete', result_payload = $2, completed_at = NOW()
        WHERE id = $1
        """
        await self.db.execute(query, queue_id, result_payload)
        logger.info(f"Marked queue item {queue_id} as complete")

    async def mark_failed(
        self,
        queue_id: str,
        error_message: str,
        increment_retry: bool = True
    ):
        """Mark queued item as failed."""
        if increment_retry:
            query = """
            UPDATE greenlight_queue
            SET status = 'failed', error_message = $2, retry_count = retry_count + 1
            WHERE id = $1
            RETURNING retry_count, max_retries
            """
            row = await self.db.fetchrow(query, queue_id, error_message)

            if row and row["retry_count"] < row["max_retries"]:
                # Retry available, reset to pending
                await self.db.execute(
                    "UPDATE greenlight_queue SET status = 'pending' WHERE id = $1",
                    queue_id
                )
                logger.warning(
                    f"Queue item {queue_id} failed (attempt {row['retry_count']}/{row['max_retries']}), "
                    f"requeuing for retry"
                )
            else:
                logger.error(
                    f"Queue item {queue_id} failed permanently after {row['retry_count']} retries: {error_message}"
                )
        else:
            query = """
            UPDATE greenlight_queue
            SET status = 'failed', error_message = $2
            WHERE id = $1
            """
            await self.db.execute(query, queue_id, error_message)
            logger.error(f"Queue item {queue_id} failed: {error_message}")

    async def get_pending(self, limit: int = 10) -> List[QueuedExecution]:
        """Get pending queue items."""
        query = """
        SELECT * FROM greenlight_queue
        WHERE status = 'pending'
        ORDER BY queued_at ASC
        LIMIT $1
        """
        rows = await self.db.fetch(query, limit)
        return [self._row_to_queued_execution(row) for row in rows]

    def _row_to_queued_execution(self, row) -> QueuedExecution:
        """Convert database row to QueuedExecution."""
        return QueuedExecution(
            id=row["id"],
            atom_id=row["atom_id"],
            learner_id=row["learner_id"],
            execution_id=row["execution_id"],
            status=row["status"],
            request_payload=row["request_payload"],
            result_payload=row["result_payload"],
            queued_at=row["queued_at"],
            started_at=row["started_at"],
            completed_at=row["completed_at"],
            error_message=row["error_message"],
            retry_count=row["retry_count"],
            max_retries=row["max_retries"]
        )
```

## Commit Strategy

```bash
cd ../cortex-batch-2c-greenlight-database

git add src/db/migrations/031_greenlight_queue.sql
git commit -m "feat(batch2c): Add Greenlight async execution queue table

Created greenlight_queue table with:
- Status tracking (pending, executing, complete, failed)
- JSONB payloads for request/result
- Retry logic support
- Indexes for fast queries

- Generated with Claude Code

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>"

# Optional: If implementing queue manager
git add src/integrations/greenlight_queue_manager.py
git commit -m "feat(batch2c): Add GreenlightQueueManager for queue operations

- Generated with Claude Code

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>"

git push -u origin batch-2c-greenlight-database
```

## GitHub Issues

```bash
gh issue create \
  --title "[Batch 2c] Greenlight Database Queue" \
  --body "Create database queue for Greenlight async execution.\\n\\n**File:** src/db/migrations/031_greenlight_queue.sql\\n\\n**Features:**\\n- Queue table with status tracking\\n- JSONB payloads\\n- Retry logic support\\n- Indexes for fast queries\\n\\n**Status:** Complete" \
  --label "batch-2c,greenlight,database,enhancement" \
  --milestone "Phase 1: Foundation"
```

## Success Metrics

- [ ] Migration runs without errors
- [ ] Table created with correct columns
- [ ] All 3 indexes created
- [ ] JSONB columns work correctly
- [ ] Status transitions work
- [ ] Retry logic supported

## Reference

### Strategy Documents
- [BDD Testing Strategy](../explanation/bdd-testing-strategy.md) - Testing approach for cognitive validity
- [CI/CD Pipeline](../explanation/ci-cd-pipeline.md) - Automated quality gates and deployment
- [Atom Type Taxonomy](../explanation/learning-atom-taxonomy.md) - 100+ atom types with ICAP classification
- [Schema Migration Plan](../explanation/schema-migration-plan.md) - Migration to polymorphic JSONB atoms

### Work Orders
- **Master Plan:** `C:\\Users\\Shadow\\.claude\\plans\\tidy-conjuring-moonbeam.md` lines 877-892
- **Parent Work Order:** `docs/agile/batch-2-greenlight.md`


---

**Status:** Pending
**AI Coder:** Ready for assignment
**Start Condition:** START IMMEDIATELY (no dependencies)
## testing and ci

- add or update tests relevant to this batch
- add or update bdd scenarios where applicable
- ensure pr-checks.yml passes before merge



