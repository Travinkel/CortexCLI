# Batch 2: Greenlight Integration

**Branch:** `batch-2-greenlight`
**Worktree:** `../cortex-batch-2-greenlight`
**Priority:** 🔴 CRITICAL (Infrastructure - Blocks runtime atoms)
**Estimated Effort:** 4-6 days
**Status:** 🔴 Pending

## Objective

Enable cortex-cli to hand off runtime atoms (code execution, debugging, CLI simulation) to Greenlight IDE/runtime environment via HTTP API.

## Dependencies

**Required Before Starting:**
- ✅ Existing `SessionManager` class
- ✅ Python httpx library
- ✅ Greenlight API documentation

**Blocks:**
- All runtime atom types (sandboxed_code, debugging_fix, etc.)
- Batch 3b (procedural handlers may need runtime execution)

## Checklist

### 1. Greenlight Client (HTTP)

- [ ] Create `src/integrations/greenlight_client.py`
  - [ ] `GreenlightAtomRequest` dataclass
  - [ ] `GreenlightAtomResult` dataclass
  - [ ] `GreenlightClient` class with async httpx
  - [ ] `execute_atom()` method with retry logic
  - [ ] `queue_atom()` method for async execution
  - [ ] `poll_execution()` method for result polling
  - [ ] Exponential backoff on timeout

**Acceptance Criteria:**
- Client handles 200 OK responses
- Retry logic works (max 3 attempts)
- Exponential backoff (2^attempt seconds)
- Proper error handling for 4xx, 5xx

**Code Template:** Plan lines 533-724

### 2. Session Manager Integration

- [ ] Extend `src/learning/session_manager.py`
  - [ ] Add `greenlight_enabled` config check
  - [ ] Initialize `GreenlightClient` in `__init__`
  - [ ] Update `present_atom()` to check `owner` field
  - [ ] Add `_handoff_to_greenlight()` method
  - [ ] Add `_display_greenlight_result()` method
  - [ ] Add `_handle_greenlight_failure()` fallback

**Acceptance Criteria:**
- Atoms with `owner="greenlight"` routed correctly
- Handoff UI displayed in terminal
- Test results rendered as table
- Score and suggestions displayed

**Code Template:** Plan lines 726-875

### 3. Queuing System (Database)

- [ ] Create `src/db/migrations/031_greenlight_queue.sql`
  - [ ] `greenlight_queue` table
  - [ ] Indexes on status and learner_id
  - [ ] JSONB for request/result payloads

**Acceptance Criteria:**
- Table created successfully
- Indexes optimize queries
- JSONB columns support flexible payloads

**SQL Template:** Plan lines 877-892

### 4. Integration Testing

- [ ] Create mock Greenlight server
- [ ] Test synchronous execution
- [ ] Test async execution + polling
- [ ] Test timeout handling
- [ ] Test retry logic

## Files to Create

| Priority | File Path | Lines of Code |
|----------|-----------|---------------|
| HIGH | `src/integrations/greenlight_client.py` | ~200 |
| HIGH | `src/db/migrations/031_greenlight_queue.sql` | ~20 |
| MEDIUM | `tests/test_greenlight_client.py` | ~100 |
| MEDIUM | `tests/mock_greenlight_server.py` | ~50 |

## Files to Modify

| File Path | Changes | Lines Added |
|-----------|---------|-------------|
| `src/learning/session_manager.py` | Add Greenlight handoff logic | ~150 |
| `config.py` | Add Greenlight config options | ~5 |

## Commit Strategy

```bash
git add src/integrations/greenlight_client.py
git commit -m "feat(batch2): Implement GreenlightClient with retry logic and queuing"

git add src/db/migrations/031_greenlight_queue.sql
git commit -m "feat(batch2): Add greenlight_queue table for async execution"

git add src/learning/session_manager.py
git commit -m "feat(batch2): Extend SessionManager with Greenlight handoff"

git add tests/test_greenlight_client.py tests/mock_greenlight_server.py
git commit -m "test(batch2): Add integration tests for Greenlight handoff"

git push -u origin batch-2-greenlight
```

## GitHub Issues

```bash
gh issue create \
  --title "[Batch 2] Greenlight API Client" \
  --body "HTTP client for Greenlight handoff protocol with retry logic.\n\n**Status:** ✅ Complete" \
  --label "batch-2,greenlight,enhancement"

gh issue create \
  --title "[Batch 2] Session Manager Greenlight Integration" \
  --body "Route runtime atoms to Greenlight IDE.\n\n**Status:** ✅ Complete" \
  --label "batch-2,greenlight,session-manager,enhancement"
```

## Testing

```python
# Test synchronous execution
client = GreenlightClient("http://localhost:8080")
request = GreenlightAtomRequest(...)
result = await client.execute_atom(request)
assert result.partial_score >= 0.0
assert result.tests_total > 0

# Test timeout + retry
# (Mock server delays 5s, should retry)

# Test queue + poll
execution_id = await client.queue_atom(request)
result = None
while not result:
    await asyncio.sleep(1)
    result = await client.poll_execution(execution_id)
assert result.status == "complete"
```

## Success Metrics

- [ ] Client handles all HTTP status codes correctly
- [ ] Retry logic tested (max 3 attempts)
- [ ] Greenlight queue operational
- [ ] Terminal UI displays test results
- [ ] Integration tests pass

---

**Reference:** Plan lines 501-892
**Status:** 🔴 Pending
