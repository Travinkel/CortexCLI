# Cortex-CLI: Build Plan

**Goal**: Transform notion-learning-sync into a working cortex-cli that you can use TODAY.

**Constraint**: Use knowledge from your actual courses (EASV curriculum files).

---

## Phase 1: Minimal Viable CLI (TODAY)

### Step 1: Restructure as cortex-cli

```
notion-learning-sync/  →  cortex-cli/
├── src/
│   ├── cortex/           # KEEP: Study session engine
│   ├── client/           # NEW: API client layer
│   ├── curriculum/       # NEW: EASV curriculum parser
│   └── cli/              # KEEP: Typer CLI
├── cortex.py             # Entry point
├── pyproject.toml        # Package config
└── .env                  # Local config
```

### Step 2: Parse Your Curriculum Files

Files to process:
- `docs/EXAM.txt` → Exam dates, deadlines
- `docs/PROGII.txt.txt` → Programming II concepts
- `docs/CDS.Security.txt` → Security fundamentals
- `docs/CDS.Networking.txt` → Networking fundamentals
- `docs/SDE2.txt` → Systems Development (Git, CI/CD)
- `docs/SDE2Testing.txt` → Testing concepts

### Step 3: Generate Atoms

Extract concepts → Generate flashcards/cloze → Store in SQLite (offline-first).

---

## Architecture Decision

```
┌─────────────────────────────────────────────────────────────────────┐
│                    TWO SEPARATE REPOS                                │
│                                                                      │
│   cortex-cli (THIS REPO)              right-learning (SEPARATE)     │
│   ──────────────────────              ─────────────────────────     │
│   Python CLI tool                     C# + React web platform       │
│   Standalone                          Enterprise features           │
│   Offline-first SQLite                PostgreSQL                    │
│   API client when online              REST API server               │
│                                                                      │
│   They share:                                                        │
│   - Same ontology (Atom/Concept/Competency/Domain)                  │
│   - Same FSRS algorithm                                              │
│   - Sync via REST API when online                                   │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Implementation Steps

### 1. Package Setup (5 min)

```bash
# In notion-learning-sync/
pip install -e ".[dev]"
```

### 2. Curriculum Parser (30 min)

Create `src/curriculum/easv_parser.py`:
- Parse week/topic structure from SDE2.txt
- Extract learning objectives (K1, S3, C3, etc.)
- Generate atoms from content

### 3. Local Database (20 min)

Use existing SQLite with schema:
```sql
atoms (id, front, back, type, concept_id, domain_id)
progress (atom_id, stability, difficulty, due_date, reviews)
concepts (id, name, domain_id, mastery)
domains (id, name)  -- SDE2, PROGII, CDS.Security, etc.
```

### 4. Focus Stream (30 min)

Implement in `src/delivery/focus_stream.py`:
```python
def get_queue(budget=30) -> list[Atom]:
    due = get_due_atoms()
    scored = [(a, calculate_z_score(a)) for a in due]
    return sorted(scored, key=lambda x: x[1], reverse=True)[:budget]
```

### 5. CLI Commands (20 min)

```bash
# Import your curriculum
cortex import docs/SDE2.txt --domain "Systems Development"

# Start studying
cortex start --budget 20

# See what's due
cortex queue

# Stats
cortex stats
```

---

## Files to Create/Modify

### NEW: `src/curriculum/easv_parser.py`

```python
"""Parse EASV curriculum files into atoms."""

def parse_sde2(content: str) -> list[dict]:
    """Parse SDE2.txt into atoms."""
    atoms = []
    # Extract week/topic structure
    # Generate flashcards for each concept
    return atoms
```

### NEW: `src/client/api_client.py`

```python
"""Client for right-learning API (when online)."""

class RightLearningClient:
    def __init__(self, base_url: str, api_key: str):
        self.base_url = base_url
        self.api_key = api_key

    async def sync_progress(self): ...
    async def get_queue(self, budget: int): ...
```

### MODIFY: `src/cli/main.py`

Add commands:
- `cortex import <file>` - Import curriculum
- `cortex start` - Study session with Focus Stream
- `cortex queue` - Show prioritized queue
- `cortex sync` - Sync with right-learning (when online)

---

## TODAY's Goal

By end of session, you should be able to run:

```bash
# 1. Import your SDE2 curriculum
cortex import docs/SDE2.txt

# 2. See generated atoms
cortex atoms list --domain SDE2

# 3. Start studying
cortex start --budget 10

# 4. Answer questions about Git, CI/CD, etc.
# 5. See your progress
cortex stats
```

---

## What We're NOT Building Today

- ❌ right-learning web integration (separate repo)
- ❌ Greenlight IDE plugin (future)
- ❌ AI-powered atom generation (use templates first)
- ❌ Neo4j knowledge graph (SQLite is enough)
- ❌ Multi-user (single user first)

---

## Let's Start

Run this to begin:

```bash
cd E:/Repo/project-astartes/notion-learning-sync
python -m venv .venv
.venv/Scripts/activate
pip install -e ".[dev]"
```

Then we build the curriculum parser.
