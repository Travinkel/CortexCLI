# Batch 2b: Greenlight SessionManager Integration

**Branch:** `batch-2b-greenlight-integration`
**Worktree:** `../cortex-batch-2b-greenlight-integration`
**Priority:** 🟡 MEDIUM (Depends on Batch 2a)
**Estimated Effort:** 2 days
**Status:** 🔴 Pending

## Objective

Integrate Greenlight handoff logic into SessionManager to route runtime atoms to Greenlight and display results in terminal.

## Dependencies

**Required:**
- ✅ Batch 2a complete (needs `GreenlightClient`)
- ✅ Existing `src/learning/session_manager.py`
- ✅ Rich library for terminal UI

**Blocks:**
- None (independent of other batches)

## Files to Modify

### 1. src/learning/session_manager.py (extend existing)

**Add these components:**

```python
from integrations.greenlight_client import GreenlightClient, GreenlightAtomRequest
from rich.table import Table
from rich.panel import Panel

class SessionManager:
    """Extended with Greenlight handoff logic."""

    def __init__(self, config):
        # Existing init
        ...

        # Greenlight client (if enabled)
        self.greenlight_enabled = config.get("GREENLIGHT_ENABLED", False)
        if self.greenlight_enabled:
            self.greenlight_client = GreenlightClient(
                base_url=config["GREENLIGHT_API_URL"],
                timeout_ms=config.get("GREENLIGHT_HANDOFF_TIMEOUT_MS", 30000),
                retry_attempts=config.get("GREENLIGHT_RETRY_ATTEMPTS", 3)
            )
        else:
            self.greenlight_client = None

    async def present_atom(self, atom: Atom) -> AtomResult:
        """
        Present atom to learner.

        If atom.owner == "greenlight" or atom.grading_mode == "runtime",
        hand off to Greenlight instead of rendering in terminal.
        """
        # Check if this is a Greenlight atom
        content_json = atom.content_json or {}
        owner = content_json.get("owner", "cortex")
        grading_mode = content_json.get("grading_mode", "static")

        if owner == "greenlight" or grading_mode == "runtime":
            if not self.greenlight_enabled:
                # Fallback: Queue for later or skip
                logger.warning(f"Greenlight atom {atom.id} but Greenlight disabled. Queuing.")
                return await self._queue_for_greenlight(atom)

            return await self._handoff_to_greenlight(atom)

        # Normal terminal rendering
        return await self._render_terminal_atom(atom)

    async def _handoff_to_greenlight(self, atom: Atom) -> AtomResult:
        """
        Hand off atom to Greenlight for execution.

        Steps:
        1. Show handoff UI panel in terminal
        2. Send request to Greenlight
        3. Wait for result (or queue if async)
        4. Display result in terminal
        5. Record in FSRS
        """
        # Step 1: Show handoff UI
        console.print(Panel(
            f"[bold cyan]Handing off to Greenlight IDE...[/bold cyan]\\n\\n"
            f"Atom: {atom.atom_type}\\n"
            f"This requires code execution in a sandboxed environment.\\n\\n"
            f"[dim]Opening Greenlight...[/dim]",
            title="🚀 Greenlight Handoff",
            border_style="cyan"
        ))

        # Step 2: Build request
        request = GreenlightAtomRequest(
            atom_id=atom.id,
            atom_type=atom.atom_type,
            front=atom.front,
            back=atom.back,
            content_json=atom.content_json,
            session_context={
                "learner_id": self.learner_id,
                "mastery_level": self.current_mastery,
                "recent_errors": self.recent_error_classes
            }
        )

        # Step 3: Execute or queue
        try:
            if atom.content_json.get("async_execution", False):
                # Queue for async execution
                execution_id = await self.greenlight_client.queue_atom(request)
                console.print(f"[yellow]Queued for execution: {execution_id}[/yellow]")
                return await self._poll_greenlight_execution(execution_id)
            else:
                # Synchronous execution
                result = await self.greenlight_client.execute_atom(request)

                # Step 4: Display result
                await self._display_greenlight_result(result)

                # Step 5: Record in FSRS
                is_correct = result.partial_score >= 0.7
                await self.fsrs_tracker.record_response(
                    atom_id=atom.id,
                    is_correct=is_correct,
                    latency_ms=result.execution_time_ms,
                    partial_score=result.partial_score
                )

                return result

        except Exception as e:
            logger.error(f"Greenlight handoff failed: {e}")
            console.print(f"[red]Greenlight handoff failed: {e}[/red]")
            # Fall back to queuing or skipping
            return await self._handle_greenlight_failure(atom, e)

    async def _display_greenlight_result(self, result: GreenlightAtomResult):
        """Display Greenlight execution result in terminal."""
        # Test results table
        test_table = Table(title="Test Results")
        test_table.add_column("Test", style="cyan")
        test_table.add_column("Status", style="bold")
        test_table.add_column("Details")

        for test in result.test_results:
            status = "✓ PASS" if test["passed"] else "✗ FAIL"
            status_style = "green" if test["passed"] else "red"
            test_table.add_row(
                test["name"],
                f"[{status_style}]{status}[/{status_style}]",
                test.get("message", "")
            )

        console.print(test_table)

        # Overall score
        score_color = "green" if result.partial_score >= 0.7 else "yellow" if result.partial_score >= 0.4 else "red"
        console.print(f"\\n[{score_color}]Score: {result.partial_score * 100:.0f}%[/{score_color}]")
        console.print(f"Tests Passed: {result.tests_passed}/{result.tests_total}")

        # Git suggestions (if any)
        if result.git_suggestions:
            console.print("\\n[bold cyan]Suggestions:[/bold cyan]")
            for suggestion in result.git_suggestions:
                console.print(f"  • {suggestion}")

        # Error class (if any)
        if result.error_class:
            console.print(f"\\n[yellow]Error Type: {result.error_class}[/yellow]")

    async def _poll_greenlight_execution(self, execution_id: str) -> AtomResult:
        """
        Poll for queued execution result.

        Shows progress spinner while waiting.
        """
        with console.status("[cyan]Waiting for execution to complete...", spinner="dots"):
            result = await self.greenlight_client.poll_until_complete(
                execution_id,
                poll_interval_sec=2.0,
                max_wait_sec=300.0
            )

        await self._display_greenlight_result(result)

        is_correct = result.partial_score >= 0.7
        await self.fsrs_tracker.record_response(
            atom_id=result.atom_id,
            is_correct=is_correct,
            latency_ms=result.execution_time_ms,
            partial_score=result.partial_score
        )

        return result

    async def _handle_greenlight_failure(self, atom: Atom, error: Exception) -> AtomResult:
        """
        Handle Greenlight failure gracefully.

        Options:
        1. Queue for retry later
        2. Skip atom
        3. Show error to learner
        """
        console.print(
            f"[red]Failed to execute atom via Greenlight.[/red]\\n"
            f"Error: {str(error)}\\n\\n"
            f"This atom will be skipped for now."
        )

        # Record as failed attempt
        return AtomResult(
            atom_id=atom.id,
            is_correct=False,
            latency_ms=0,
            user_answer="",
            correct_answer=atom.back,
            partial_score=0.0,
            error_message=str(error)
        )

    async def _queue_for_greenlight(self, atom: Atom) -> AtomResult:
        """Queue atom for later Greenlight execution."""
        console.print(
            f"[yellow]Greenlight is disabled but this atom requires runtime execution.[/yellow]\\n"
            f"Atom {atom.id} queued for later execution."
        )

        # Store in greenlight_queue table (Batch 2c handles this)
        # For now, just skip
        return AtomResult(
            atom_id=atom.id,
            is_correct=False,
            latency_ms=0,
            user_answer="",
            correct_answer=atom.back,
            partial_score=0.0,
            error_message="Greenlight disabled - atom queued"
        )
```

### 2. config.py (add Greenlight settings)

```python
# Greenlight Integration Settings
GREENLIGHT_ENABLED = os.getenv("GREENLIGHT_ENABLED", "false").lower() == "true"
GREENLIGHT_API_URL = os.getenv("GREENLIGHT_API_URL", "http://localhost:8080")
GREENLIGHT_HANDOFF_TIMEOUT_MS = int(os.getenv("GREENLIGHT_HANDOFF_TIMEOUT_MS", "30000"))
GREENLIGHT_RETRY_ATTEMPTS = int(os.getenv("GREENLIGHT_RETRY_ATTEMPTS", "3"))
```

## Checklist

- [ ] Read existing `src/learning/session_manager.py`
- [ ] Add Greenlight client initialization in `__init__`
- [ ] Update `present_atom()` to check owner/grading_mode
- [ ] Implement `_handoff_to_greenlight()` method
- [ ] Implement `_display_greenlight_result()` method
- [ ] Implement `_poll_greenlight_execution()` method
- [ ] Implement `_handle_greenlight_failure()` method
- [ ] Implement `_queue_for_greenlight()` method
- [ ] Add Greenlight config to `config.py`
- [ ] Write integration tests
- [ ] Test with mock Greenlight server

## Testing

```bash
# Integration test with SessionManager
python -c "
from src.learning.session_manager import SessionManager
from src.db.models import Atom
import asyncio

async def test():
    config = {
        'GREENLIGHT_ENABLED': True,
        'GREENLIGHT_API_URL': 'http://localhost:8080'
    }
    session = SessionManager(config)

    # Mock atom with runtime execution
    atom = Atom(
        id='test-atom',
        atom_type='code_submission',
        front='Write a function',
        back='def add(a, b): return a + b',
        content_json={
            'owner': 'greenlight',
            'language': 'python'
        }
    )

    result = await session.present_atom(atom)
    print(f'Result: {result.partial_score}')

asyncio.run(test())
"
```

## Commit Strategy

```bash
cd ../cortex-batch-2b-greenlight-integration

git add src/learning/session_manager.py
git commit -m "feat(batch2b): Integrate Greenlight handoff into SessionManager

Added methods:
- _handoff_to_greenlight(): Route runtime atoms to Greenlight
- _display_greenlight_result(): Render test results in terminal
- _poll_greenlight_execution(): Poll async execution
- _handle_greenlight_failure(): Graceful failure handling

🤖 Generated with Claude Code

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>"

git add config.py
git commit -m "feat(batch2b): Add Greenlight configuration options

🤖 Generated with Claude Code

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>"

git push -u origin batch-2b-greenlight-integration
```

## GitHub Issues

```bash
gh issue create \
  --title "[Batch 2b] Greenlight SessionManager Integration" \
  --body "Integrate Greenlight handoff into SessionManager.\\n\\n**Files:**\\n- src/learning/session_manager.py\\n- config.py\\n\\n**Features:**\\n- Atom routing logic\\n- Result rendering in terminal\\n- Async execution polling\\n\\n**Status:** ✅ Complete" \
  --label "batch-2b,greenlight,enhancement" \
  --milestone "Phase 1: Foundation"
```

## Success Metrics

- [ ] All integration tests passing
- [ ] Greenlight atoms routed correctly
- [ ] Test results displayed in terminal
- [ ] Async execution polling works
- [ ] Graceful failure handling works

## Reference

- **Master Plan:** `C:\\Users\\Shadow\\.claude\\plans\\tidy-conjuring-moonbeam.md` lines 726-875
- **Parent Work Order:** `docs/agile/batch-2-greenlight.md`
- **Depends On:** `batch-2a-greenlight-client.md` (GreenlightClient must exist)

---

**Status:** 🔴 Pending
**AI Coder:** Ready for assignment
**Start Condition:** ⏳ Wait for Batch 2a to complete and merge to master
