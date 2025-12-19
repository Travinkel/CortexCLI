# Architecture Overview

This document explains the high-level architecture of Cortex and the design decisions behind it.

---

## System Overview

Cortex is an adaptive learning system for CCNA study that synchronizes content from Notion to PostgreSQL, integrates with Anki for spaced repetition, and provides a CLI for interactive study sessions with cognitive diagnosis and Socratic tutoring.

```
                                    +-----------+
                                    |  Notion   |
                                    |  (Source) |
                                    +-----+-----+
                                          |
                                          v
+-------------+    +---------+    +-------+-------+
|   Anki      |<-->|  Sync   |<-->|  PostgreSQL   |
| (SRS Client)|    | Service |    |  (Canonical)  |
+-------------+    +---------+    +-------+-------+
                         |                |
                         v                v
              +----------+----------------+----------+
              |          |                |          |
              v          v                v          v
         +--------+ +--------+ +----------------+ +--------+
         | Cortex | |  API   | |    Adaptive    | |  JIT   |
         |  CLI   | | Server | |     Engine     | |  Gen   |
         +--------+ +--------+ +----------------+ +--------+
              |                       |
              v                       v
    +---------+---------+   +---------+---------+
    |  Atom   | Socratic|   |  NCDE   | Struggle|
    |Handlers | Tutor   |   |Pipeline | Weights |
    +---------+---------+   +---------+---------+
```

---

## Design Principles

### 1. Source of Truth Hierarchy

**Notion > PostgreSQL > Anki**

- Notion is the authoritative source for content creation
- PostgreSQL stores canonical, cleaned data
- Anki receives a subset for mobile study

This hierarchy ensures:
- Content creators work in familiar Notion interface
- Data cleaning and validation happen in PostgreSQL
- Anki contains only high-quality, approved cards

### 2. Staging-Canonical Pattern

Raw data from external systems lands in staging tables (`stg_*`) before transformation into canonical tables (`clean_*`).

**Benefits**:
- Raw data preserved for debugging
- Transformation logic is explicit and testable
- Staging can be rebuilt without affecting canonical data

### 3. Evidence-Based Defaults

All thresholds and algorithms derive from cognitive science research:

| Setting | Source | Rationale |
|---------|--------|-----------|
| 5-word optimal answer | SuperMemo | Highest retention |
| 25-word max question | Wozniak's 20 Rules | Cognitive load |
| 90% target retention | FSRS research | Optimal efficiency |
| 80% success rate | Desirable Difficulty | Learning zone |

### 4. Atom-Centric Design

The `clean_atoms` table is the central entity:
- All learning content reduces to atoms
- Atoms link to concepts, modules, and Anki cards
- Quality metrics attach to individual atoms

---

## Component Architecture

### Sync Layer

Handles data movement between systems.

```
src/sync/
  notion_client.py    # Notion API wrapper
  notion_adapter.py   # Raw -> Staging transformation
  sync_service.py     # Orchestration
```

**Data Flow**:
1. Fetch pages from Notion API
2. Store raw JSONB in staging tables
3. Transform to canonical schema
4. Compute quality scores
5. Update Anki (push/pull)

### Adaptive Layer

Implements learning science algorithms.

```
src/adaptive/
  learning_engine.py      # Card selection
  mastery_calculator.py   # Progress tracking
  knowledge_graph.py      # Concept relationships
  neuro_model.py          # Failure mode classification
  ncde_pipeline.py        # Cognitive diagnosis pipeline
  persona_service.py      # Learner profile tracking
  path_sequencer.py       # Prerequisite ordering
  remediation_router.py   # Strategy dispatch with fail mode mapping
```

**Key Algorithms**:
- **FSRS-4**: Memory stability and retrievability
- **Z-Score**: Multi-factor prioritization (decay, centrality, project, novelty)
- **Force Z**: Prerequisite gap detection and backtracking
- **NCDE**: Neuro-Cognitive Diagnosis Engine for error classification

#### Fail Mode Remediation Strategies

The `remediation_router.py` module maps NCDE fail modes to targeted remediation strategies:

| Fail Mode | Code | Note Type | Atom Types | Exercise Count |
|-----------|------|-----------|------------|----------------|
| Encoding Error | FM1 | Elaborative | flashcard, cloze | 8 |
| Retrieval Error | FM2 | None (practice only) | flashcard, cloze, mcq | 10 |
| Discrimination Error | FM3 | Contrastive | matching, mcq, true_false | 6 |
| Integration Error | FM4 | Procedural | parsons, numeric | 5 |
| Executive Error | FM5 | Summary | mcq, true_false | 8 |
| Fatigue Error | FM6 | None | None (suggest break) | 0 |

**Note Types**:
- `elaborative`: Deep explanation with multiple examples
- `contrastive`: Side-by-side comparison of similar concepts
- `procedural`: Step-by-step worked examples
- `summary`: High-level overview and key takeaways

The `get_remediation_strategy()` function returns the appropriate strategy for a given fail mode, with fuzzy matching for various input formats.

### Cortex Module

The core CLI study experience.

```
src/cortex/
  __init__.py            # Module exports
  session.py             # CortexSession orchestrator
  session_store.py       # Session persistence
  socratic.py            # Socratic tutoring engine
  dialogue_recorder.py   # Dialogue persistence
  remediation_recommender.py  # Post-session recommendations
  atoms/                 # Type-specific handlers
    __init__.py          # Registry and AtomType enum
    base.py              # AnswerResult dataclass, AtomHandler protocol
    flashcard.py         # Basic Q&A
    cloze.py             # Fill-in-the-blank
    mcq.py               # Multiple choice (single/multi-select)
    true_false.py        # Binary choice with LLM explanation
    numeric.py           # Subnetting calculations
    parsons.py           # Code/command ordering
    matching.py          # Term-definition pairing
```

**Atom Handler Protocol**: Each handler implements `validate()`, `present()`, `get_input()`, `check()`, and `hint()`. Handlers are registered via `@register(AtomType.X)` decorator and retrieved with `get_handler(atom_type)`.

### Delivery Layer

Presents content to learners with visual effects and tutoring.

```
src/delivery/
  tutor.py           # Legacy tutoring (superseded by cortex/socratic.py)
  scheduler.py       # Card queue management
  atom_deck.py       # Content rendering
  telemetry.py       # Response logging
  cortex_visuals.py  # 3D ASCII art engine
  animated_brain.py  # Brain pulse animation
  state_store.py     # State persistence
```

**3D Visual Engine**: `cortex_visuals.py` provides volumetric ASCII art rendering with depth shading using gradient characters (`░▒▓█`). Components include 3D panels, holographic headers, depth meters, and isometric cubes for status displays.

**Socratic Tutor**: `src/cortex/socratic.py` implements LLM-powered tutoring that guides learners through questions instead of revealing answers directly. Uses progressive scaffolding (5 levels from pure Socratic to full reveal). Sessions are recorded in `socratic_dialogues` table via `DialogueRecorder`.

### Anki Integration Layer

Bidirectional sync with Anki via AnkiConnect.

```
src/anki/
  anki_client.py     # AnkiConnect HTTP wrapper
  config.py          # Note types, deck names, tag structure
  push_service.py    # DB -> Anki (batched, 50x faster)
  pull_service.py    # Anki -> DB (FSRS stats)
  background_sync.py # Async sync operations
```

**Push Service**: Filters atoms by quality (A/B grade), routes to correct note type (`LearningOS-v2` for flashcards, `LearningOS-v2 Cloze-NEW` for cloze), organizes into module subdecks (`CCNA::ITN::M01 Networking Today`), and applies proper tags (`cortex`, `ccna-itn`, `ccna-itn:m{N}`, `type:{type}`, `section:{id}`).

**Pull Service**: Retrieves FSRS scheduling data (interval, ease, reps, lapses) and updates `learning_atoms` with derived stability and difficulty values.

### CLI Layer

Command-line interface using Typer.

```
src/cli/
  main.py            # Entry point and command groups
  cortex.py          # Study commands (start, optimize, war, stats)
  cortex_sync.py     # Sync commands (notion, anki-push, anki-pull)
  cortex_stats.py    # Extracted statistics functions
  source_presets.py  # Subdivided adaptive mode presets
```

#### Source Presets Module

The `source_presets.py` module provides filtering for subdivided adaptive learning:

| Component | Purpose |
|-----------|---------|
| `SOURCE_PRESETS` | Dict of 21 named presets (module ranges, ITN assessments, topic themes) |
| `parse_modules_arg()` | Parses flexible module specifications (e.g., "1-3,11-13") |
| `parse_sections_arg()` | Parses comma-separated section IDs |
| `resolve_filters()` | Resolves CLI arguments to concrete filter values |
| `describe_filters()` | Generates human-readable filter description |

**Preset Categories**:
- **Module Ranges**: `modules-1-3`, `modules-4-7`, `modules-8-10`, `modules-11-13`, `modules-14-15`, `modules-16-17`
- **ITN Assessments**: `itn-final`, `itn-practice`, `itn-test`, `itn-skills`
- **Topic Themes**: `subnetting`, `osi-model`, `binary-math`, `ipv6`, `switching`, `routing`, `security`, `transport`, `ios-config`, `arp-dhcp`, `ethernet`

---

## Data Architecture

### Entity Relationships

```
clean_programs
    |
    +-- clean_tracks (1:N)
            |
            +-- clean_modules (1:N)
                    |
                    +-- clean_atoms (1:N)
                            |
                            +-- anki_cards (1:1)

clean_concept_areas
    |
    +-- clean_concept_clusters (1:N)
            |
            +-- clean_concepts (1:N)
                    |
                    +-- clean_atoms (N:1)
```

### Key Tables

| Table | Purpose | Row Count (typical) |
|-------|---------|-------------------|
| `learning_atoms` | Learning content | 5,000+ |
| `concepts` | Knowledge units | 500+ |
| `concept_clusters` | Knowledge groupings | 50-100 |
| `ccna_sections` | CCNA curriculum structure | 100+ |
| `review_queue` | AI-generated pending approval | 0-100 |
| `sync_log` | Audit trail | Growing |

**Note**: Table naming convention changed in migration 013. Legacy code may reference `clean_*` prefixes.

### Centralized Queries Module

The `src/db/queries.py` module provides a centralized repository of SQL queries:

```python
from src.db.queries import QUERIES
result = session.execute(text(QUERIES["struggle_atoms"]), params)
```

**Query Categories**:

| Category | Queries | Purpose |
|----------|---------|---------|
| Adaptive Session | `struggle_atoms`, `due_atoms`, `new_atoms` | Atom selection for study sessions |
| Struggle Stats | `struggle_weights`, `struggle_priority` | Struggle weight display |
| Sections | `sections_with_counts`, `section_atoms` | Section-based filtering |
| Remediation | `remediation_by_concept`, `remediation_by_section` | Targeted remediation |
| Socratic | `high_scaffold_dialogues` | Dialogue analysis |
| Anki | `atoms_for_sync` | Sync operations |
| Stats | `atom_distribution`, `module_coverage` | Analytics |

**Benefits**:
- Single location for query optimization
- Consistent filter clause injection
- Easier auditing and debugging
- Reusable across services

---

## Integration Points

### Notion Integration

- **Protocol**: REST API v2022-06-28
- **Authentication**: Integration token
- **Rate Limits**: Respected via throttling
- **Data Format**: JSONB in staging tables

### Anki Integration

- **Protocol**: AnkiConnect HTTP API
- **Port**: 8765 (default)
- **Operations**: Create, update, get card info
- **Sync Direction**: Bidirectional (push cards, pull stats)

### AI Integration

- **Providers**: Gemini, Claude, Vertex AI
- **Use Cases**: Content generation, rewriting, quality assessment
- **Output**: Review queue for human approval

---

## Security Considerations

### Data Protection

- `PROTECT_NOTION=true` prevents accidental writes
- API keys stored in `.env` (not committed)
- No authentication on localhost API (deployment requires auth)

### Data Flow Controls

- Dry-run mode for previewing changes
- Sync logs for audit trail
- Review queue for AI-generated content

---

## Scalability

### Current Design

Optimized for single-user study (1,000-10,000 atoms):
- PostgreSQL handles concurrent reads well
- Anki sync is batch-oriented
- CLI sessions are single-threaded

### Future Considerations

For multi-user or large-scale deployment:
- Add user authentication layer
- Implement connection pooling
- Consider read replicas for analytics

---

## Decision Log

### Why PostgreSQL over SQLite?

- JSONB support for flexible staging data
- Better tooling for production deployment
- Concurrent access for API + CLI

### Why Notion as Source?

- Rich editing experience
- Existing user workflows
- Relation support for concept linking

### Why Separate from Anki?

- Anki lacks quality metrics
- Need for quiz types beyond flashcards
- Centralized progress tracking

---

## Advanced Subsystems

### NCDE Pipeline (Neuro-Cognitive Diagnosis Engine)

The NCDE pipeline (`src/adaptive/ncde_pipeline.py`) transforms the study session from a simple state machine into an event-driven cognitive loop.

**Architecture Components**:

| Component | Purpose |
|-----------|---------|
| `RawInteractionEvent` | Captures telemetry: response time, cursor path, keystroke dynamics |
| `NormalizedTelemetry` | Z-scores metrics against learner's baseline |
| `ConfusionMatrix` | Tracks concept confusion for Pattern Separation Index (PSI) |
| `FatigueVector` | 3D fatigue representation: physical, cognitive, motivational |
| `SessionContext` | Aggregated session state for diagnosis |

**Failure Modes** (from `neuro_model.py`):

| Mode | Code | Description |
|------|------|-------------|
| Encoding | FM1 | Information never properly stored |
| Retrieval | FM2 | Stored but cannot access |
| Discrimination | FM3 | Confuses similar concepts (low PSI) |
| Integration | FM4 | Cannot combine concepts |
| Executive | FM5 | Wrong strategy selection |
| Fatigue | FM6 | Resource depletion |

**Processing Flow**:
1. `create_raw_event()` captures interaction telemetry
2. `FeatureExtractor.extract()` normalizes signals
3. `diagnose_interaction()` classifies failure mode
4. `prepare_struggle_update()` adjusts section weights
5. `RemediationRouter` selects intervention strategy

### Socratic Dialogue System

When learners indicate "I don't know", the system engages in Socratic tutoring rather than immediate answer reveal.

**Components**:

| File | Purpose |
|------|---------|
| `src/cortex/socratic.py` | `SocraticTutor` class with LLM integration |
| `src/cortex/dialogue_recorder.py` | Persistence to `socratic_dialogues` table |

**Scaffold Levels**:

| Level | Name | Behavior |
|-------|------|----------|
| 0 | `PURE_SOCRATIC` | Questions only, no hints |
| 1 | `NUDGE` | Conceptual nudge ("Think about...") |
| 2 | `PARTIAL` | Partial reveal ("The answer involves...") |
| 3 | `WORKED` | Worked example with gaps |
| 4 | `REVEAL` | Full answer with explanation |

**Cognitive Signals Detected**:
- `CONFUSED`: Long latency, "I don't understand"
- `PROGRESSING`: Building on previous response
- `BREAKTHROUGH`: Sudden correct insight
- `STUCK`: Repeated short responses
- `PREREQUISITE_GAP`: Missing foundational knowledge

**Resolution Outcomes**: `self_solved`, `guided_solved`, `gave_up`, `revealed`

### Dynamic Struggle Weights

The struggle weight system combines static user-declared weak areas with real-time NCDE-driven updates.

**Database Schema** (`015_struggle_weights.sql`):

```sql
struggle_weights (
    id UUID PRIMARY KEY,
    module_number INTEGER NOT NULL,
    section_id TEXT,              -- NULL = entire module
    severity TEXT,                -- critical, high, medium, low
    weight DECIMAL(3,2),          -- 0.0-1.0 (static)
    ncde_weight DECIMAL(3,2),     -- Dynamic from NCDE
    failure_modes TEXT[],         -- ['FM1', 'FM3']
    last_diagnosis_at TIMESTAMPTZ
)
```

**Priority View** (`v_struggle_priority`):
```sql
priority_score = struggle_weight * 3.0
               + ncde_weight * 2.0
               + (1 - retrievability) * 1.0
```

**Flow**:
1. User declares struggles via `nls cortex struggle --modules 11,12`
2. NCDE diagnoses errors during study session
3. `CortexSession._update_struggle_weight()` updates `ncde_weight`
4. `path_sequencer.py` uses priority view for card selection

### User Flagging System

Users can flag problematic questions during study for later review.

**Database Schema** (`022_user_flags.sql`):

```sql
user_flags (
    id UUID PRIMARY KEY,
    atom_id UUID REFERENCES learning_atoms(id),
    user_id TEXT,
    flag_type TEXT,        -- wrong_answer, ambiguous, typo, outdated, too_easy, too_hard
    flag_reason TEXT,
    session_id UUID,
    created_at TIMESTAMPTZ,
    resolved_at TIMESTAMPTZ,
    resolution_notes TEXT,
    resolved_by TEXT
)
```

**Flag Types**:

| Type | Description |
|------|-------------|
| `wrong_answer` | Marked answer is incorrect |
| `ambiguous` | Question is unclear |
| `typo` | Spelling or formatting error |
| `outdated` | Information is no longer accurate |
| `too_easy` | Not challenging enough |
| `too_hard` | Requires knowledge not covered |

**View** (`v_flagged_atoms`): Aggregates flags by atom for prioritized review.

### Atom Handler System

Each question type has a dedicated handler implementing the `AtomHandler` protocol.

**Protocol Methods**:

```python
class AtomHandler(Protocol):
    def validate(self, atom: dict) -> bool:
        """Check if atom has required fields."""
    def present(self, atom: dict, console: Console) -> None:
        """Display the question."""
    def get_input(self, atom: dict, console: Console) -> Any:
        """Capture user's answer."""
    def check(self, atom: dict, answer: Any, console: Console | None) -> AnswerResult:
        """Validate and return result."""
    def hint(self, atom: dict, attempt: int) -> str | None:
        """Progressive hints."""
```

**AnswerResult Dataclass**:

```python
@dataclass
class AnswerResult:
    correct: bool
    feedback: str
    user_answer: str
    correct_answer: str
    partial_score: float = 1.0    # 0.0-1.0 for partial credit
    explanation: str | None = None
    dont_know: bool = False       # Triggers Socratic dialogue
```

**Handler Features by Type**:

| Type | Key Features |
|------|--------------|
| `flashcard` | Space to reveal, quality rating 1-4 |
| `cloze` | Exact/fuzzy matching, {{c1::}} syntax |
| `mcq` | Option shuffling, multi-select, LLM hints |
| `true_false` | Binary T/F, LLM error explanation |
| `numeric` | Tolerance ranges, step-by-step hints |
| `parsons` | Partial credit by position, visual diff, LLM analysis |
| `matching` | Drag-drop simulation, pair scoring |

---

## See Also

- [Database Schema](../reference/database-schema.md)
- [FSRS Algorithm](fsrs-algorithm.md)
- [Adaptive Learning](adaptive-learning.md)
- [Cognitive Diagnosis](cognitive-diagnosis.md)
- [Struggle-Aware System](struggle-aware-system.md)
