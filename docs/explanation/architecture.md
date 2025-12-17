# Architecture Overview

This document explains the high-level architecture of Cortex and the design decisions behind it.

---

## System Overview

Cortex is an adaptive learning system that synchronizes content from Notion to PostgreSQL, integrates with Anki for spaced repetition, and provides a CLI for interactive study sessions.

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
                                          |
                        +--------+--------+--------+
                        |        |        |        |
                        v        v        v        v
                   +------+ +-------+ +-----+ +--------+
                   | CLI  | |  API  | | AI  | |Adaptive|
                   |Study | |Server | |Gen  | | Engine |
                   +------+ +-------+ +-----+ +--------+
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
  neuro_model.py          # NCDE diagnosis
```

**Key Algorithms**:
- **FSRS-4**: Memory stability and retrievability
- **Z-Score**: Multi-factor prioritization
- **Force Z**: Prerequisite gap detection
- **NCDE**: Cognitive error diagnosis

### Delivery Layer

Presents content to learners with visual effects and tutoring.

```
src/delivery/
  tutor.py           # Socratic tutoring with LLM
  scheduler.py       # Card queue management
  atom_deck.py       # Content rendering
  telemetry.py       # Response logging
  cortex_visuals.py  # 3D ASCII art engine
  animated_brain.py  # Brain pulse animation
```

**3D Visual Engine**: `cortex_visuals.py` provides volumetric ASCII art rendering with depth shading using gradient characters (`░▒▓█`). Components include 3D panels, holographic headers, depth meters, and isometric cubes for status displays.

**Socratic Tutor**: `tutor.py` implements LLM-powered tutoring that guides learners through questions instead of revealing answers directly. Uses progressive scaffolding (5 levels from pure Socratic to full reveal).

### CLI Layer

Command-line interface using Typer.

```
src/cli/
  main.py            # Entry point
  cortex.py          # Study commands
  cortex_sync.py     # Sync commands
```

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

## See Also

- [Database Schema](../reference/database-schema.md)
- [FSRS Algorithm](fsrs-algorithm.md)
- [Adaptive Learning](adaptive-learning.md)
