# Greenlight Integration

> **Integration Partner:** Greenlight is an IDE-based learning integration for cortex-cli (similar to [right-learning](./adaptive-learning.md)). It extends cortex-cli's capabilities to runtime-dependent learning atoms while cortex-cli remains focused on terminal-based drills.

---

## Overview

Greenlight is an IDE-based coding lab that handles runtime-dependent learning atoms for cortex-cli. While cortex-cli excels at terminal-based drills for recognition, recall, and lightweight practice, Greenlight provides a full development environment for code construction, debugging, and project-scale learning tasks.

**Key Principle:** Cortex-CLI orchestrates the learning experience; Greenlight executes code-based atoms and returns results.

---

## Integration Architecture

### Division of Responsibility

#### Cortex-CLI (Terminal Learning Tool)

**Owns these atom types:**
- **Recognition & Discrimination:** MCQ, true/false, error-spotting (text-based)
- **Recall & Entry:** Flashcards, cloze, short answer, numeric calculations
- **Structural Drills:** Matching, sequencing, Parsons problems
- **Meta-Cognitive Prompts:** Confidence ratings, difficulty assessment, reflection
- **Comparison & Explanation:** Text-based reasoning (A vs B, trade-offs, why/why-not)

**Characteristics:**
- Fast feedback loops (<5 seconds per atom)
- No runtime dependencies
- Terminal-native UX (Rich library)
- Spaced repetition focus (FSRS scheduling)
- Works offline

#### Greenlight (IDE-Based Coding Lab)

**Owns these atom types:**
- **Code Submission:** Write code with test execution and performance gates
- **Debugging & Fault Isolation:** Bug identification, root-cause analysis, minimal fix tasks
- **Code Understanding:** Output prediction, state tracing, control-flow analysis
- **Code Construction:** Fill line/function, skeleton completion, pseudocode→code translation
- **Configuration & CLI:** Command sequencing, terminal emulation with state
- **Project-Scale Tasks:** Git workflows (branches/worktrees), diff review, multi-file refactoring
- **Diff Analysis:** "What changed?", "Find bug in diff", regression test generation
- **System/Architecture Reasoning:** Trade-offs, failure modes, security boundaries (in code context)
- **Testing & Verification:** Test case generation, boundary reasoning, coverage gap identification

**Characteristics:**
- Runtime execution required (compile, run, test)
- IDE UX (editor, test console, diff viewer, terminal emulator)
- Longer feedback loops (30s - 10min per atom)
- Requires online connectivity (for API handoff)
- Project/workspace context

---

## Shared Atom Schema

Both systems use a common atom envelope defined in [`atom-envelope.schema.json`](../reference/atom-envelope.schema.json).

### Example: Code Submission Atom

```json
{
  "id": "ccna-3.2.4-code-subnet-calc-001",
  "atom_type": "code_submission",
  "owner": "greenlight",
  "grading_mode": "runtime",
  "front": "Write a Python function `calculate_network_address(ip, cidr)` that returns the network address. Example: `calculate_network_address('192.168.1.45', 26)` → `'192.168.1.0'`",
  "back": "```python\ndef calculate_network_address(ip: str, cidr: int) -> str:\n    # Convert IP to binary, apply subnet mask, convert back\n    octets = [int(x) for x in ip.split('.')]\n    mask = (0xFFFFFFFF << (32 - cidr)) & 0xFFFFFFFF\n    ip_int = (octets[0] << 24) + (octets[1] << 16) + (octets[2] << 8) + octets[3]\n    network_int = ip_int & mask\n    return f'{(network_int >> 24) & 0xFF}.{(network_int >> 16) & 0xFF}.{(network_int >> 8) & 0xFF}.{network_int & 0xFF}'\n```",
  "content_json": {
    "runner": {
      "language": "python",
      "version": "3.11",
      "entrypoint": "subnet_calc.py",
      "tests": [
        {
          "input": {"ip": "192.168.1.45", "cidr": 26},
          "expected": "192.168.1.0"
        },
        {
          "input": {"ip": "10.0.0.255", "cidr": 24},
          "expected": "10.0.0.0"
        },
        {
          "input": {"ip": "172.16.50.100", "cidr": 30},
          "expected": "172.16.50.100"
        }
      ],
      "time_limit_ms": 5000,
      "memory_limit_mb": 128
    },
    "sandbox_policy": "isolated",
    "git_guidance": true,
    "hints": [
      "Convert IP octets to a 32-bit integer first",
      "Use bitwise AND with the subnet mask",
      "Remember to handle the mask calculation: (2^32 - 1) << (32 - CIDR)"
    ]
  },
  "metadata": {
    "difficulty": "medium",
    "estimated_time_minutes": 8,
    "prerequisite_atoms": ["ccna-3.2.1-num-001", "ccna-3.2.2-mcq-001"]
  }
}
```

### Key Fields for Greenlight Atoms

| Field | Purpose | Required |
|-------|---------|----------|
| `owner` | Set to `"greenlight"` to trigger handoff | Yes |
| `grading_mode` | `"runtime"` (execution), `"hybrid"` (execution + manual review), or `"static"` (cortex-cli) | Yes |
| `content_json.runner` | Execution environment spec (language, tests, limits) | Yes for code atoms |
| `content_json.sandbox_policy` | Isolation level (`isolated`, `network`, `filesystem`) | No (default: `isolated`) |
| `content_json.git_guidance` | Enable git command suggestions | No (default: `false`) |

---

## Handoff Protocol

When cortex-cli encounters a Greenlight-owned atom during a study session:

### Step 1: Detection

```python
atom = session.get_next_atom()
if atom.get("owner") == "greenlight" or atom.get("grading_mode") in ["runtime", "hybrid"]:
    # Trigger Greenlight handoff
    result = greenlight_client.run_atom(atom)
```

### Step 2: Handoff Display

Cortex-CLI shows a handoff message:

```
┌─────────────────────────────────────────┐
│  Opening in Greenlight IDE...          │
│                                         │
│  Task: Write subnet calculator function │
│  Type: Code Submission (Python)         │
│  Tests: 5 test cases                    │
│                                         │
│  [Press Ctrl+C to cancel]               │
└─────────────────────────────────────────┘
```

### Step 3: Greenlight Execution

Greenlight IDE:
1. Opens with task prompt and starter code
2. Provides editor pane, test runner, output console
3. Allows learner to write/debug code
4. Runs tests on submit
5. Generates feedback based on test results

### Step 4: Result Return

Greenlight sends result payload back to cortex-cli:

```json
{
  "atom_id": "ccna-3.2.4-code-subnet-calc-001",
  "result": {
    "correct": false,
    "partial_score": 0.6,
    "tests_passed": 3,
    "tests_failed": 2,
    "execution_time_ms": 247,
    "feedback": "3 of 5 tests passed. Edge case handling needs work.",
    "error_class": "boundary_condition",
    "errors": [
      {"test": "Test 3", "expected": "172.16.50.100", "got": "172.16.50.0", "message": "/30 subnet edge case failed"},
      {"test": "Test 5", "expected": "0.0.0.0", "got": "Error: division by zero", "message": "/0 CIDR not handled"}
    ],
    "git_suggestions": [
      "git add subnet_calc.py",
      "git commit -m 'feat: Add subnet calculator with partial edge case handling'"
    ]
  },
  "meta": {
    "confidence": 0.7,
    "difficulty_rating": "hard",
    "learner_reflection": "I forgot to handle /30 and /0 edge cases",
    "time_spent_seconds": 512
  }
}
```

### Step 5: Recording in Cortex-CLI

Cortex-CLI:
1. Stores result in local database for FSRS scheduling
2. Updates mastery score using partial credit (0.6 in example)
3. Logs error class (`boundary_condition`) for remediation
4. Continues session with next atom

---

## API Contract

### Endpoint: `POST /greenlight/run-atom`

See [`api-endpoints.md`](../reference/api-endpoints.md) for complete specification and [`greenlight-handoff.openapi.yaml`](../reference/greenlight-handoff.openapi.yaml) for the OpenAPI schema.

**Request:**

```json
{
  "atom_id": "uuid-string",
  "atom_type": "code_submission",
  "content": {
    "front": "Question/prompt text",
    "back": "Expected solution/explanation",
    "content_json": { /* runner, tests, etc. */ }
  },
  "session_context": {
    "learner_id": "uuid-string",
    "current_mastery": 0.65,
    "recent_errors": ["off-by-one", "null-check"],
    "session_id": "session-uuid"
  }
}
```

**Response:**

```json
{
  "atom_id": "uuid-string",
  "result": {
    "correct": false,
    "partial_score": 0.6,
    "tests_passed": 3,
    "tests_failed": 2,
    "execution_time_ms": 247,
    "feedback": "User-facing feedback message",
    "error_class": "boundary_condition",
    "git_suggestions": ["git add file.py"]
  },
  "meta": {
    "confidence": 0.7,
    "difficulty": "hard",
    "learner_reflection": "Text entered by learner"
  }
}
```

---

## When to Use Greenlight vs Cortex-CLI

### Use Cortex-CLI for:

✓ **Fast recall drills** - Spaced repetition focus, <5s per atom
✓ **Concept verification** - "Do you know X?" style questions
✓ **Quick practice sessions** - 10-20 atoms in 5-10 minutes
✓ **Pure memory/recognition** - Facts, definitions, syntax
✓ **Lightweight reasoning** - Compare A vs B, text-based explanations

### Use Greenlight for:

✓ **Building something** - Write actual code, not just recall syntax
✓ **Debugging real programs** - Interactive debugging, not just "spot the error"
✓ **Multi-file projects** - Refactoring, architecture changes
✓ **Performance optimization** - Profiling, benchmarking
✓ **Git workflow practice** - Branches, merges, cherry-picks in sandbox
✓ **Any task requiring compilation/execution** - Tests must run

---

## Integration Example: CCNA Subnetting

### Cortex-CLI Atoms (Terminal-Based)

1. **Numeric:** "How many host bits in a /26 subnet?" → `6`
2. **True/False:** "192.168.1.0/24 allows 254 usable hosts" → `True`
3. **Matching:** Match subnet masks to CIDR notation
   - 255.255.255.192 ↔ /26
   - 255.255.255.0 ↔ /24
4. **MCQ:** "Which address is the broadcast address for 10.0.0.0/23?"
   - A) 10.0.0.255
   - B) 10.0.1.255 ✓
   - C) 10.0.2.255
5. **Parsons:** Arrange subnetting calculation steps in order

### Greenlight Atoms (IDE-Based)

1. **Code Submission:** Write function to calculate network address from IP/mask
2. **Debugging:** Fix this subnetting script—broadcast calculation is incorrect
3. **Code Understanding:** Predict output of VLSM allocation algorithm for given inputs
4. **Project-Scale:** Implement subnet calculator CLI tool with:
   - Input validation
   - VLSM support
   - Unit tests (>80% coverage)
   - Git workflow (feature branch → PR)

**Combined Learning Path:**
1. Cortex-CLI: Learn facts and formulas (numeric, MCQ, matching)
2. Cortex-CLI: Practice mental math (cloze, numeric with CIDR calculations)
3. Greenlight: Apply knowledge in code (subnet calculator function)
4. Cortex-CLI: Reinforce weak areas identified by Greenlight errors
5. Greenlight: Build complete subnet analysis tool (project-scale)

---

## Configuration

### Cortex-CLI Settings

Add to `.env`:

```bash
# ========================================
# Greenlight Integration
# ========================================
GREENLIGHT_ENABLED=true
GREENLIGHT_API_URL=http://localhost:8090
GREENLIGHT_HANDOFF_TIMEOUT_MS=30000
GREENLIGHT_RETRY_ATTEMPTS=3
GREENLIGHT_FALLBACK_MODE=queue  # queue, skip, or manual
```

#### Configuration Options

| Variable | Default | Purpose |
|----------|---------|---------|
| `GREENLIGHT_ENABLED` | `false` | Enable/disable Greenlight integration |
| `GREENLIGHT_API_URL` | `http://localhost:8090` | Greenlight API base URL |
| `GREENLIGHT_HANDOFF_TIMEOUT_MS` | `30000` | Max wait time for handoff (30s) |
| `GREENLIGHT_RETRY_ATTEMPTS` | `3` | Retry count on API failure |
| `GREENLIGHT_FALLBACK_MODE` | `queue` | Behavior when Greenlight unavailable:<br>- `queue`: Save for later<br>- `skip`: Mark skipped, continue session<br>- `manual`: Require manual review |

### Greenlight Settings

See [Greenlight documentation](https://github.com/project-astartes/Greenlight) for:
- IDE plugin installation
- Workspace configuration
- Language runtime setup
- Test framework integration

---

## Telemetry & Analytics

Both systems share telemetry for unified learning analytics.

### Metrics Tracked in Cortex-CLI

- **Attempt count** - How many tries before correct
- **Latency** - Time to first attempt
- **Error classes** - Tagged misconceptions (e.g., `off-by-one`, `null-check`)
- **FSRS signals** - Retrievability, stability, difficulty

### Metrics from Greenlight

- **Runtime metrics** - Test pass/fail count, execution time, memory usage
- **Code quality** - Cyclomatic complexity, test coverage, linting violations
- **Git activity** - Commits, branch operations, diff analysis

### Combined Mastery Scoring

Mastery calculation uses signals from both systems:

```python
mastery_score = (
    0.40 * retrievability_fsrs +      # From cortex-cli spaced repetition
    0.25 * (1 - lapse_rate) +         # From cortex-cli error tracking
    0.25 * quiz_performance +         # From cortex-cli MCQ/matching scores
    0.10 * greenlight_test_pass_rate  # From Greenlight code execution
)
```

See [`adaptive-learning.md`](./adaptive-learning.md) for complete mastery formula.

---

## Error Handling

### Greenlight Unavailable

**Scenario:** Greenlight IDE not running or API unreachable

**Behavior:**
1. Cortex-CLI displays error message:
   ```
   ⚠ Greenlight unavailable

   Options:
   [1] Queue for later (continue session)
   [2] Skip this atom
   [3] Exit session
   ```
2. If `GREENLIGHT_FALLBACK_MODE=queue`:
   - Atom saved to `greenlight_queue` table
   - Session continues with next atom
   - Queued atoms shown in `cortex stats --greenlight`
3. If `GREENLIGHT_FALLBACK_MODE=skip`:
   - Atom marked as skipped in session history
   - Does not affect mastery score
4. If `GREENLIGHT_FALLBACK_MODE=manual`:
   - Session pauses, user must resolve manually

### Timeout Handling

**Scenario:** Learner takes too long in Greenlight (exceeds `GREENLIGHT_HANDOFF_TIMEOUT_MS`)

**Behavior:**
1. If tests have started executing:
   - Return partial result with tests passed so far
   - Partial score = `tests_passed / total_tests`
2. If no tests started:
   - Mark atom as `incomplete`
   - Offer retry or queue for later

### Compilation/Runtime Errors

**Scenario:** Code fails to compile or crashes during execution

**Behavior:**
1. Greenlight returns `correct: false` with error details
2. Cortex-CLI displays compiler/runtime error as feedback
3. Error class tagged for remediation (e.g., `syntax_error`, `runtime_exception`)
4. Learner can retry immediately or continue session

---

## Implementation Status

**Current Status:** Planned integration (not yet implemented)

**Prerequisites (Completed):**
- ✓ Atom envelope schema defined (`atom-envelope.schema.json`)
- ✓ OpenAPI contract specified (`greenlight-handoff.openapi.yaml`)
- ✓ Vision and architecture documented

**Next Steps:**
1. Implement Greenlight API client in cortex-cli (`src/integrations/greenlight_client.py`)
2. Add handoff logic to session manager (`src/cortex/session.py`)
3. Create `greenlight_queue` database table for offline queue
4. Build Greenlight IDE plugin (see [Greenlight repo](https://github.com/project-astartes/Greenlight))
5. Add integration tests

See [`ROADMAP.md`](../ROADMAP.md) Phase 5 for timeline.

---

## See Also

- **[Vision: DARPA Digital Tutor](./vision-darpa-tutor.md)** - Overall architecture and Greenlight's role
- **[API Endpoints](../reference/api-endpoints.md)** - Complete Greenlight handoff API spec
- **[Atom Envelope Schema](../reference/atom-envelope.schema.json)** - Shared data model
- **[TUI Design](./tui-design.md)** - Cortex-CLI interface patterns (terminal-based)
- **[Adaptive Learning](./adaptive-learning.md)** - Right-learning integration (mastery sync)
- **[Learning Atoms Taxonomy](../reference/learning-atoms.md)** - Complete atom type catalog with routing guidance
