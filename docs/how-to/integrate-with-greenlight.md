# How to Integrate with Greenlight

This guide walks you through integrating cortex-cli with the Greenlight IDE for code execution and debugging tasks.

---

## Prerequisites

Before integrating Greenlight with cortex-cli, ensure you have:

- [ ] **Cortex-CLI** installed and configured (see [Getting Started](../tutorials/getting-started.md))
- [ ] **Greenlight IDE** installed (see [Greenlight documentation](https://github.com/project-astartes/Greenlight))
- [ ] **Network connectivity** (Greenlight API must be reachable)
- [ ] **PostgreSQL database** initialized with cortex-cli schema

---

## Step 1: Install Greenlight

Follow the Greenlight installation guide for your platform:

```bash
# Example: Install Greenlight (exact steps TBD - refer to Greenlight repo)
git clone https://github.com/project-astartes/Greenlight.git
cd Greenlight
pip install -e .
```

**Verify installation:**

```bash
greenlight --version
# Expected output: Greenlight v1.0.0 (or later)
```

---

## Step 2: Configure Greenlight Integration in Cortex-CLI

Add Greenlight settings to your `.env` file:

```bash
# ========================================
# Greenlight Integration
# ========================================

# Enable Greenlight handoff
GREENLIGHT_ENABLED=true

# Greenlight API base URL
GREENLIGHT_API_URL=http://localhost:8090

# Timeout for atom handoff (milliseconds)
GREENLIGHT_HANDOFF_TIMEOUT_MS=30000

# Retry attempts on API failure
GREENLIGHT_RETRY_ATTEMPTS=3

# Fallback behavior when Greenlight is unavailable
# Options: queue (save for later), skip (mark skipped), manual (require user action)
GREENLIGHT_FALLBACK_MODE=queue
```

### Configuration Options

| Variable | Default | Description |
|----------|---------|-------------|
| `GREENLIGHT_ENABLED` | `false` | Enable/disable Greenlight integration |
| `GREENLIGHT_API_URL` | `http://localhost:8090` | Greenlight API base URL |
| `GREENLIGHT_HANDOFF_TIMEOUT_MS` | `30000` | Max wait time for handoff (30s) |
| `GREENLIGHT_RETRY_ATTEMPTS` | `3` | Retry count on API failure |
| `GREENLIGHT_FALLBACK_MODE` | `queue` | Behavior when Greenlight unavailable:<br>- `queue`: Save atom for later<br>- `skip`: Mark skipped, continue session<br>- `manual`: Require manual review |

---

## Step 3: Start Greenlight API Server

Launch the Greenlight API server:

```bash
greenlight serve --port 8090
```

Expected output:

```
[INFO] Greenlight API server starting...
[INFO] Listening on http://localhost:8090
[INFO] Ready to accept atom handoffs
```

**Keep this terminal open** while using cortex-cli.

---

## Step 4: Test the Connection

Verify cortex-cli can reach Greenlight:

```bash
cortex test-integration greenlight
```

Expected output:

```
Testing Greenlight Integration
═══════════════════════════════

✓ Greenlight API reachable at http://localhost:8090
✓ Atom handoff endpoint responding (/greenlight/run-atom)
✓ Version: Greenlight v1.0.0
✓ Atom types supported: code_submission, debugging, code_understanding, cli_emulator

Integration Status: READY
```

**If connection fails:**

- Check that Greenlight server is running (`ps aux | grep greenlight`)
- Verify `GREENLIGHT_API_URL` in `.env` matches server address
- Check firewall rules (port 8090 should be open)

---

## Step 5: Mark Atoms for Greenlight

Atoms require code execution should be marked with `owner: "greenlight"` in their `content_json` field.

### Option A: Update Existing Atoms (SQL)

```sql
-- Mark all code_submission atoms for Greenlight
UPDATE learning_atoms
SET content_json = jsonb_set(
    COALESCE(content_json, '{}'::jsonb),
    '{owner}',
    '"greenlight"'
)
WHERE atom_type IN ('code_submission', 'debugging', 'code_understanding');

-- Verify update
SELECT id, atom_type, content_json->>'owner' as owner
FROM learning_atoms
WHERE atom_type IN ('code_submission', 'debugging', 'code_understanding')
LIMIT 5;
```

### Option B: Use CLI Command

```bash
# Mark specific atom
cortex atom mark-greenlight <atom_id>

# Mark all atoms of a type
cortex atom mark-greenlight --type code_submission

# Mark atoms matching a query
cortex atom mark-greenlight --query "SELECT id FROM learning_atoms WHERE module_id = 8"
```

### Option C: Set During Atom Creation

When creating new atoms, include the `owner` field:

```json
{
  "id": "ccna-8.2.1-code-001",
  "atom_type": "code_submission",
  "owner": "greenlight",
  "grading_mode": "runtime",
  "front": "Write a Python function to calculate subnet broadcast address...",
  "back": "def calculate_broadcast(...): ...",
  "content_json": {
    "runner": {
      "language": "python",
      "version": "3.11",
      "entrypoint": "subnet.py",
      "tests": [...]
    }
  }
}
```

---

## Step 6: Run a Study Session with Greenlight Atoms

Start a normal cortex-cli study session:

```bash
cortex study
```

When a Greenlight-owned atom is encountered:

### Terminal Output (Cortex-CLI):

```
┌─────────────────────────────────────────┐
│  Opening in Greenlight IDE...          │
│                                         │
│  Task: Write subnet calculator function │
│  Type: Code Submission (Python)         │
│  Tests: 5 test cases                    │
│  Expected time: ~8 minutes              │
│                                         │
│  [Press Ctrl+C to cancel]               │
└─────────────────────────────────────────┘

Waiting for Greenlight response...
```

### IDE Opens (Greenlight):

1. **Task pane** displays the question/prompt
2. **Editor pane** opens with starter code (if provided)
3. **Test console** shows available test cases
4. **Output pane** displays execution results

### Workflow in Greenlight:

1. Write your solution in the editor
2. Click "Run Tests" (or press `Ctrl+T`)
3. Review test results
4. Fix errors, iterate
5. Click "Submit" when ready (or press `Ctrl+Enter`)

### Results Return to Cortex-CLI:

```
┌─────────────────────────────────────────┐
│  Results from Greenlight                │
├─────────────────────────────────────────┤
│  Tests Passed: 3 / 5                    │
│  Partial Score: 0.6                     │
│  Execution Time: 247ms                  │
│                                         │
│  Failed Tests:                          │
│  • Test 3: /30 subnet edge case         │
│  • Test 5: /0 CIDR not handled          │
│                                         │
│  Feedback: Edge case handling needs work│
│  Error Class: boundary_condition        │
└─────────────────────────────────────────┘

[Press Enter to continue session]
```

Session continues with the next atom.

---

## Step 7: Review Greenlight Activity

Check Greenlight-specific metrics:

```bash
cortex stats --greenlight
```

**Output:**

```
Greenlight Integration Stats
═════════════════════════════
Total handoffs:       42
Atoms completed:      38
Atoms pending:        4
Average completion:   8m 32s
Test pass rate:       76%
Execution errors:     2

Recent Activity (last 7 days):
┌────────────┬──────────┬─────────┬──────────────┐
│ Date       │ Handoffs │ Pass %  │ Avg Time     │
├────────────┼──────────┼─────────┼──────────────┤
│ 2025-12-21 │ 8        │ 75%     │ 7m 15s       │
│ 2025-12-20 │ 12       │ 83%     │ 9m 42s       │
│ 2025-12-19 │ 10       │ 70%     │ 8m 01s       │
└────────────┴──────────┴─────────┴──────────────┘

Queued Atoms (offline):
  - ccna-8.2.4-code-002 (code_submission)
  - ccna-9.1.3-debug-001 (debugging)
  - ccna-10.2.1-cli-001 (cli_emulator)
  - ccna-11.1.5-diff-001 (diff_review)
```

---

## Troubleshooting

### Problem: Greenlight Not Responding

**Symptoms:**
- "Greenlight unavailable" error during session
- Connection timeout after 30 seconds

**Solutions:**

1. **Check Greenlight is running:**
   ```bash
   ps aux | grep greenlight
   # If not running: greenlight serve --port 8090
   ```

2. **Verify API URL:**
   ```bash
   curl http://localhost:8090/health
   # Expected: {"status": "healthy", "version": "1.0.0"}
   ```

3. **Check firewall:**
   ```bash
   # Linux: allow port 8090
   sudo ufw allow 8090

   # macOS: check firewall settings
   # Windows: check Windows Defender Firewall
   ```

4. **Review logs:**
   ```bash
   cortex logs --filter greenlight --tail 50
   ```

---

### Problem: Atoms Not Handing Off to Greenlight

**Symptoms:**
- Atom executes in cortex-cli terminal instead of opening IDE
- No handoff message displayed

**Solutions:**

1. **Verify atom is marked for Greenlight:**
   ```sql
   SELECT id, atom_type, content_json->>'owner' as owner
   FROM learning_atoms
   WHERE id = 'your-atom-id';
   ```
   Expected: `owner = "greenlight"`

2. **Check atom type is supported:**
   ```bash
   cortex test-integration greenlight --verbose
   ```
   Supported types: `code_submission`, `debugging`, `code_understanding`, `cli_emulator`, `diff_review`

3. **Verify `GREENLIGHT_ENABLED=true` in `.env`**

4. **Clear cache:**
   ```bash
   cortex cache clear
   cortex db refresh
   ```

---

### Problem: IDE Not Opening

**Symptoms:**
- Handoff message appears in cortex-cli
- Greenlight API responds
- But IDE does not open

**Solutions:**

1. **Ensure Greenlight CLI is in PATH:**
   ```bash
   which greenlight
   # Should return: /usr/local/bin/greenlight (or similar)
   ```

2. **Check Greenlight plugin installed:**
   ```bash
   greenlight plugins list
   # Expected: cortex-handoff (v1.0.0)
   ```

3. **Verify workspace configuration:**
   ```bash
   greenlight config show
   # Check: workspace_path, editor_command
   ```

4. **Test manual IDE launch:**
   ```bash
   greenlight open --atom-id test-atom-001
   ```

---

### Problem: Tests Failing to Execute

**Symptoms:**
- IDE opens successfully
- Code editor works
- But "Run Tests" fails with errors

**Solutions:**

1. **Check language runtime installed:**
   ```bash
   # Python
   python3 --version  # Must match runner.version in atom

   # Node.js
   node --version

   # Java
   java --version
   ```

2. **Verify test framework dependencies:**
   ```bash
   # Python
   pip list | grep pytest

   # Node.js
   npm list jest
   ```

3. **Check atom's `runner` configuration:**
   ```json
   "runner": {
     "language": "python",
     "version": "3.11",  // Must match installed version
     "entrypoint": "solution.py",
     "tests": ["test_solution.py"]
   }
   ```

4. **Review Greenlight execution logs:**
   ```bash
   greenlight logs --filter test-runner --tail 100
   ```

---

## Advanced Configuration

### Custom Test Frameworks

Configure Greenlight to use specific test frameworks:

```bash
# .env (cortex-cli side)
GREENLIGHT_PYTHON_TEST_FRAMEWORK=pytest
GREENLIGHT_JS_TEST_FRAMEWORK=jest
GREENLIGHT_JAVA_TEST_FRAMEWORK=junit5
```

### Timeout Adjustments

For complex atoms requiring more time:

```sql
-- Increase timeout for specific atom
UPDATE learning_atoms
SET content_json = jsonb_set(
    content_json,
    '{runner,time_limit_ms}',
    '60000'  -- 60 seconds
)
WHERE id = 'ccna-12.4.1-code-complex-001';
```

### Git Integration

Enable git command suggestions:

```sql
-- Enable git guidance for project-scale atoms
UPDATE learning_atoms
SET content_json = jsonb_set(
    content_json,
    '{git_guidance}',
    'true'::jsonb
)
WHERE atom_type = 'project_scale';
```

When enabled, Greenlight will suggest git commands like:

```
Git Suggestions:
  git add solution.py
  git commit -m "feat: Implement subnet calculator"
  git push origin feature/subnet-calc
```

---

## Offline Mode (Queuing Atoms)

If Greenlight is unavailable, cortex-cli can queue atoms for later:

### Check Queued Atoms

```bash
cortex greenlight queue --list
```

**Output:**

```
Greenlight Queue (4 atoms)
══════════════════════════

1. ccna-8.2.4-code-002 (code_submission) - Queued 2 hours ago
2. ccna-9.1.3-debug-001 (debugging) - Queued 1 hour ago
3. ccna-10.2.1-cli-001 (cli_emulator) - Queued 30 min ago
4. ccna-11.1.5-diff-001 (diff_review) - Queued 5 min ago
```

### Process Queued Atoms

```bash
# Process all queued atoms (opens Greenlight for each)
cortex greenlight queue --process-all

# Process specific atom
cortex greenlight queue --process ccna-8.2.4-code-002

# Clear queue without processing
cortex greenlight queue --clear
```

---

## Uninstalling Greenlight Integration

To remove Greenlight integration:

1. **Disable in configuration:**
   ```bash
   # In .env
   GREENLIGHT_ENABLED=false
   ```

2. **Unmark Greenlight atoms (optional):**
   ```sql
   UPDATE learning_atoms
   SET content_json = content_json - 'owner'
   WHERE content_json->>'owner' = 'greenlight';
   ```

3. **Clear queue:**
   ```bash
   cortex greenlight queue --clear
   ```

4. **Uninstall Greenlight (optional):**
   ```bash
   pip uninstall greenlight
   ```

Cortex-CLI will continue working normally; atoms previously handled by Greenlight will be skipped during sessions.

---

## See Also

- [Greenlight Integration Architecture](../explanation/greenlight-integration.md) - Technical details
- [API Endpoints](../reference/api-endpoints.md) - Greenlight handoff API spec
- [Atom Envelope Schema](../reference/atom-envelope.schema.json) - Shared data model
- [Learning Atoms Taxonomy](../reference/learning-atoms.md) - Which atoms require Greenlight
- [Greenlight Documentation](https://github.com/project-astartes/Greenlight) - IDE setup and usage
