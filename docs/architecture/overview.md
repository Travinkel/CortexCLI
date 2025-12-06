# Architecture Overview

This document describes the technical architecture of notion-learning-sync.

## System Design Principles

### 1. Staging-Canonical Pattern

The core architectural pattern separates raw data from clean data:

```mermaid
graph TD
    A[Notion API] -->|Raw JSONB| B[Staging Tables]
    B -->|Cleaning Pipeline| C[Canonical Tables]
    C -->|Push Cards| D[Anki]
    D -->|Pull Stats| C
    C -->|Export| E[right-learning ETL]
    C -->|Personal Use| F[Study Apps]
```

**Benefits**:
- Notion remains the single source of truth
- Staging tables can be rebuilt without data loss
- Quality improvements don't affect raw data
- Multiple consumers use the same clean output

### 2. Read-Mostly Architecture

Notion is **write-protected by default** (`PROTECT_NOTION=true`):
- Prevents accidental data loss
- Enables safe experimentation
- Staging sync is one-way: Notion → Service
- Anki sync is bidirectional: Service ↔ Anki

### 3. Quality-First Design

Every piece of content passes through quality gates:
1. **Atomicity validation** - Is it simple enough?
2. **Duplicate detection** - Have we seen this before?
3. **Prefix normalization** - Consistent formatting
4. **AI rewriting** (optional) - Fix verbose content

## Data Flow

### Full Sync Flow

```mermaid
sequenceDiagram
    participant U as User/Scheduler
    participant API as FastAPI
    participant NS as NotionSync
    participant CP as CleaningPipeline
    participant AS as AnkiSync
    participant DB as PostgreSQL
    participant N as Notion API
    participant A as AnkiConnect

    U->>API: POST /api/sync/notion
    API->>NS: sync_all_databases()

    loop For each configured database
        NS->>N: Query database
        N-->>NS: Pages with properties
        NS->>DB: UPSERT stg_notion_*
    end

    NS->>CP: run_cleaning_pipeline()
    CP->>DB: SELECT from stg_*

    loop For each staging record
        CP->>CP: validate_atomicity()
        CP->>CP: detect_duplicates()
        CP->>CP: normalize_prefix()
        alt Needs AI rewriting
            CP->>CP: queue_for_ai_rewrite()
        end
        CP->>DB: INSERT/UPDATE clean_*
    end

    alt Anki sync enabled
        API->>AS: push_to_anki()
        AS->>DB: SELECT clean_atoms WHERE anki_note_id IS NULL
        AS->>A: addNotes()
        A-->>AS: note_ids
        AS->>DB: UPDATE clean_atoms SET anki_note_id

        AS->>AS: pull_stats_from_anki()
        AS->>A: cardsInfo()
        A-->>AS: ease, interval, reviews
        AS->>DB: UPDATE clean_atoms SET anki_*
    end

    API-->>U: Sync complete
```

### Incremental Sync Flow

For efficiency, incremental sync uses Notion's `last_edited_time`:

```mermaid
graph LR
    A[Get last_synced_at] --> B[Query Notion with filter]
    B --> C{Changes found?}
    C -->|Yes| D[Update staging]
    C -->|No| E[Skip]
    D --> F[Run cleaning on changed items]
    F --> G[Update canonical]
```

## Component Architecture

### 1. Sync Engine (`src/sync/`)

Handles Notion API communication:

```
src/sync/
├── __init__.py
├── notion_client.py      # Notion API wrapper
├── sync_service.py       # Orchestrates syncs
└── databases/            # Database-specific extractors
    ├── flashcards.py
    ├── concepts.py
    ├── curriculum.py
    └── __init__.py
```

**Key responsibilities**:
- Query Notion databases with pagination
- Extract properties from Notion's complex JSON
- Handle rate limiting (3 requests/second)
- Compute sync hashes for change detection
- Store raw JSONB in staging tables

**Example flow**:
```python
# Simplified sync logic
async def sync_flashcards():
    # 1. Query Notion
    pages = notion_client.query_database(FLASHCARDS_DB_ID)

    # 2. Process each page
    for page in pages:
        # 3. Extract properties
        raw_props = extract_properties(page)

        # 4. Compute hash for change detection
        sync_hash = compute_hash(raw_props)

        # 5. Upsert to staging
        db.upsert(StgNotionFlashcard(
            notion_page_id=page.id,
            raw_properties=raw_props,
            sync_hash=sync_hash
        ))
```

### 2. Cleaning Pipeline (`src/cleaning/`)

Transforms raw data into canonical output:

```
src/cleaning/
├── __init__.py
├── atomicity.py          # Wozniak/Gwern-based validation
├── duplicates.py         # Fuzzy matching with rapidfuzz
├── prefix_normalizer.py  # Standardize prefixes
├── ai_rewriter.py        # Gemini/Vertex integration
└── pipeline.py           # Orchestrator
```

**Pipeline stages**:

```mermaid
graph TD
    A[Raw Flashcard] --> B{Atomicity Check}
    B -->|Pass| C[Duplicate Detection]
    B -->|Fail| D[Mark needs_review]
    C -->|Unique| E[Prefix Normalization]
    C -->|Duplicate| F[Mark for merge]
    E --> G{Quality Score}
    G -->|High| H[Insert to clean_atoms]
    G -->|Low| I[Queue for AI rewrite]
    I --> J[Insert to review_queue]
    D --> J
    F --> J
```

**Atomicity rules** (from [20-rules.md](https://www.supermemo.com/en/blog/twenty-rules-of-formulating-knowledge)):

| Metric | Threshold | Source |
|--------|-----------|--------|
| Question length | ≤ 25 words | Wozniak (SuperMemo) |
| Answer optimal | ≤ 5 words | SuperMemo research |
| Answer warning | ≤ 15 words | SuperMemo research |
| Answer max chars | ≤ 120 chars | Cognitive Load Theory |

**Implementation**:
```python
def validate_atomicity(front: str, back: str) -> AtomicityResult:
    front_words = len(front.split())
    back_words = len(back.split())
    back_chars = len(back)

    issues = []

    if front_words > settings.atomicity_front_max_words:
        issues.append(f"Question too long ({front_words} words)")

    if back_words > settings.atomicity_back_warning_words:
        issues.append(f"Answer verbose ({back_words} words)")

    if back_chars > settings.atomicity_back_max_chars:
        issues.append(f"Answer too long ({back_chars} chars)")

    status = "atomic" if not issues else "verbose"
    return AtomicityResult(status=status, issues=issues)
```

### 3. Anki Integration (`src/anki/`, `scripts/anki_full_sync.py`)

Bidirectional sync with Anki via AnkiConnect:

```
src/anki/
├── __init__.py
├── anki_client.py        # AnkiConnect wrapper
scripts/
├── anki_full_sync.py     # Main sync script (flashcard/cloze only)
```

**Atom Type Philosophy**:
- `flashcard`, `cloze` -> Sync to Anki (FSRS scheduling)
- `mcq`, `true_false`, `matching`, `parsons` -> NLS CLI quizzes only

**Push flow** (Service -> Anki):
```python
def push_atoms_to_anki(dry_run: bool = False):
    # 1. Query learning_atoms for flashcard/cloze types
    atoms = session.execute(text("""
        SELECT * FROM learning_atoms
        WHERE atom_type IN ('flashcard', 'cloze')
          AND quality_score >= 0.75
          AND front IS NOT NULL
    """))

    # 2. Create module-based decks: CCNA::ITN::M{XX} {Name}
    deck_name = get_module_deck_name(module_num)

    # 3. Build 6-field notes with metadata
    note = {
        "deckName": deck_name,
        "modelName": "LearningOS-v2",
        "fields": {
            "concept_id": str(atom.concept_id),
            "front": atom.front,
            "back": atom.back,
            "tags": " ".join(tags),
            "source": atom.source,
            "metadata_json": json.dumps(metadata),
        }
    }

    # 4. Add to Anki via AnkiConnect
    anki_invoke("addNotes", {"notes": notes})
```

**Pull flow** (Anki -> Service):
```python
def pull_anki_stats():
    # 1. Get CCNA cards from Anki
    card_ids = anki_invoke("findCards", {"query": "deck:CCNA::ITN*"})
    cards_info = anki_invoke("cardsInfo", {"cards": card_ids})

    # 2. Update learning_atoms with FSRS stats
    session.execute(text("""
        UPDATE learning_atoms SET
            anki_note_id = :note_id,
            anki_interval = :interval,
            anki_ease_factor = :ease,
            anki_review_count = :reps,
            anki_lapses = :lapses,
            anki_stability = :stability,
            anki_difficulty = :difficulty
        WHERE card_id = :card_id
    """), params)
```

### 4. Database Layer (`src/db/`)

SQLAlchemy 2.0 models with PostgreSQL-specific features:

```
src/db/
├── models/
│   ├── base.py           # DeclarativeBase
│   ├── staging.py        # 7 staging models
│   ├── canonical.py      # 10 canonical models
│   └── __init__.py
├── migrations/           # SQL migrations
│   └── 001_initial_schema.sql
└── database.py           # Connection management
```

**Key design decisions**:
- UUID primary keys for canonical tables (better for distributed systems)
- JSONB columns for raw Notion data (flexible schema)
- Partial indexes on filtered queries (performance)
- Materialized views for complex aggregations (future)
- Foreign keys with `ON DELETE SET NULL` (preserve data)

### 5. API Layer (`src/api/`)

FastAPI REST API with automatic OpenAPI docs:

```
src/api/
├── main.py               # App initialization
├── routers/
│   ├── sync_router.py    # POST /api/sync/*
│   ├── cleaning_router.py # POST /api/clean/*
│   ├── review_router.py  # GET/POST /api/review/*
│   ├── anki_router.py    # POST /api/anki/*
│   └── content_router.py # GET /api/atoms, /api/concepts
└── __init__.py
```

**API design principles**:
- RESTful resource naming
- Idempotent operations where possible
- Pagination for list endpoints
- Filtering and sorting via query params
- Structured error responses

## Database Schema Design

### Staging Tables

All staging tables follow this pattern:
- `notion_page_id` (TEXT PRIMARY KEY) - Notion's page ID
- `raw_properties` (JSONB) - Full Notion properties object
- `last_synced_at` (TIMESTAMPTZ) - When we last fetched this
- Optional: `sync_hash` (TEXT) - MD5 for change detection

**Why JSONB?**
- Notion's schema can change without breaking our code
- Enable future features without migrations
- Query nested properties with PostgreSQL's JSON operators
- Flexibility for different property types

### Canonical Tables

Clean, normalized data with proper relational structure:

**Knowledge Hierarchy**:
```
clean_concept_areas (L0)
    |_ 1:N
clean_concept_clusters (L1)
    |_ 1:N
concepts (L2)
    |_ 1:N
learning_atoms (flashcards, cloze, mcq, etc.)
```

**Curriculum Structure**:
```
clean_programs
    |_ 1:N
clean_tracks
    |_ 1:N
learning_modules
    |_ 1:N
learning_atoms (flashcards, cloze, mcq, etc.)
```

**Dual relationships**: A learning atom can belong to both:
- A concept (knowledge hierarchy)
- A module (curriculum structure)

This enables both:
1. "Show me all atoms for 'TCP/IP'" (concept-based)
2. "Show me all atoms for 'Module 7: Ethernet Switching'" (curriculum-based)

### Views for Convenience

Pre-computed views for common queries:

```sql
-- Anki-syncable atoms
CREATE VIEW v_anki_atoms AS
SELECT a.*, c.name as concept_name, m.name as module_name
FROM learning_atoms a
LEFT JOIN concepts c ON a.concept_id = c.id
LEFT JOIN learning_modules m ON a.module_id = m.id
WHERE a.atom_type IN ('flashcard', 'cloze')
  AND a.quality_score >= 0.75;

-- Concept statistics
CREATE VIEW v_concept_atom_stats AS
SELECT
    c.id,
    c.name,
    COUNT(a.id) as total_atoms,
    COUNT(a.id) FILTER (WHERE a.anki_note_id IS NOT NULL) as in_anki,
    AVG(a.anki_ease_factor) as avg_ease,
    AVG(a.anki_interval) as avg_interval
FROM concepts c
LEFT JOIN learning_atoms a ON a.concept_id = c.id
GROUP BY c.id, c.name;
```

## Configuration Management

Pydantic Settings with environment variable support:

```python
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=False,
    )

    # Type-safe settings
    database_url: str
    notion_api_key: str
    atomicity_front_max_words: int = 25

    # Helper methods
    def get_configured_notion_databases(self) -> dict[str, str]:
        # Only return configured database IDs
        ...
```

**Benefits**:
- Type validation at startup
- Clear error messages for missing config
- Default values with evidence-based sources
- Environment variable precedence

## Error Handling Strategy

### Transient Errors (Retry)
- Notion API rate limits → Exponential backoff
- Network timeouts → 3 retries with jitter
- Database deadlocks → Retry transaction

### Permanent Errors (Log & Continue)
- Invalid Notion properties → Log warning, skip item
- Atomicity violations → Mark for review, continue
- AI API failures → Queue for later, continue

### Fatal Errors (Abort)
- Database connection lost → Abort sync
- Invalid configuration → Exit with error
- Authentication failures → Exit with error

## Performance Considerations

### Database Optimization
- Indexes on foreign keys and filtered columns
- Partial indexes for `WHERE` clauses
- JSONB GIN indexes for property queries
- Connection pooling via SQLAlchemy

### API Rate Limits
- Notion: 3 requests/second (official limit)
- AnkiConnect: Local, no limits
- Gemini: 60 requests/minute (free tier)
- Vertex AI: Project quotas

### Batch Processing
- Fetch Notion pages in batches of 100
- Process flashcards in chunks of 500
- Commit to DB every 100 records
- Use bulk inserts where possible

### Caching Strategy
- Notion query results (5 minutes)
- Duplicate detection embeddings (24 hours)
- AI rewrite suggestions (permanent, in review_queue)

## Security Considerations

### API Keys
- Never commit `.env` to git
- Use environment variables in production
- Rotate keys regularly
- Minimum required permissions

### Database Access
- Use connection pooling
- Parameterized queries (SQLAlchemy handles this)
- Read-only views for exports
- Regular backups

### Notion Protection
- `PROTECT_NOTION=true` by default
- Dry run mode for testing
- Audit logs for all operations
- Manual confirmation for bulk operations

## Deployment Architecture

### Local Development
```
┌─────────────────────────────────────┐
│  Windows 11                         │
│  ┌───────────────────────────────┐  │
│  │  notion-learning-sync         │  │
│  │  (uvicorn --reload)           │  │
│  └───────────────────────────────┘  │
│  ┌───────────────────────────────┐  │
│  │  PostgreSQL 15                │  │
│  └───────────────────────────────┘  │
│  ┌───────────────────────────────┐  │
│  │  Anki + AnkiConnect           │  │
│  └───────────────────────────────┘  │
└─────────────────────────────────────┘
```

### Production (Future)
```
┌─────────────────────────────────────┐
│  Cloud VM / Container               │
│  ┌───────────────────────────────┐  │
│  │  Docker: notion-learning-sync │  │
│  └───────────────────────────────┘  │
│  ┌───────────────────────────────┐  │
│  │  Managed PostgreSQL           │  │
│  └───────────────────────────────┘  │
│  ┌───────────────────────────────┐  │
│  │  Cron: Scheduled syncs        │  │
│  └───────────────────────────────┘  │
└─────────────────────────────────────┘
```

## Monitoring & Observability

### Logs
- Structured JSON logs (loguru)
- Rotation by size/time
- Separate log levels per module
- Context: sync_id, batch_id for tracing

### Metrics (Future)
- Sync duration and item counts
- Cleaning pipeline pass/fail rates
- Anki push/pull success rates
- Database query performance

### Alerts (Future)
- Sync failures
- Database connection issues
- API rate limit hits
- Low quality scores (< 0.5)

## Service Layer Architecture

### Dependency Injection Pattern

The service layer uses **constructor injection** for loose coupling and testability:

```python
# Service class with injected dependencies
class SyncService:
    def __init__(
        self,
        settings: Settings,
        notion_client: NotionClient,
        db_session: Session
    ):
        self.settings = settings
        self.notion = notion_client
        self.db = db_session

    def sync_database(self, db_type: str, db_id: str) -> Tuple[int, int]:
        # Uses injected dependencies
        pages = self.notion.fetch_from_database(db_id)
        # ... process pages
        return (created, updated)

# Initialization at API/CLI layer
def get_sync_service() -> SyncService:
    return SyncService(
        settings=get_settings(),
        notion_client=NotionClient(),
        db_session=get_db_session()
    )
```

**Benefits**:
- **Testability**: Mock dependencies in unit tests
- **Flexibility**: Swap implementations (e.g., test vs prod database)
- **Explicit dependencies**: Clear what each service needs
- **Lifecycle management**: Control when resources are created/destroyed

### Service Layer Diagram

```mermaid
graph TB
    subgraph "API Layer"
        API[FastAPI Routers]
    end

    subgraph "Service Layer"
        SS[SyncService]
        CP[CleaningPipeline]
        QA[CardQualityAnalyzer]
        DD[DuplicateDetector]
        AR[AIRewriter]
        AIS[AnkiImportService]
    end

    subgraph "Data Access Layer"
        NC[NotionClient]
        AC[AnkiClient]
        DB[(PostgreSQL)]
    end

    subgraph "External Services"
        NA[Notion API]
        AK[AnkiConnect]
        GEM[Gemini API]
    end

    API -->|inject| SS
    API -->|inject| CP
    API -->|inject| AIS

    SS -->|uses| NC
    SS -->|uses| DB

    CP -->|uses| QA
    CP -->|uses| DD
    CP -->|uses| AR
    CP -->|uses| DB

    AIS -->|uses| AC
    AIS -->|uses| QA
    AIS -->|uses| DB

    NC -->|HTTP| NA
    AC -->|HTTP| AK
    AR -->|HTTP| GEM
```

### Service Responsibilities

| Service | Purpose | Dependencies | Key Methods |
|---------|---------|--------------|-------------|
| **SyncService** | Orchestrate Notion syncs | NotionClient, Database | `sync_all_databases()`, `sync_database()`, `get_last_sync_time()` |
| **CleaningPipeline** | Transform staging → canonical | QualityAnalyzer, DuplicateDetector, AIRewriter, Database | `process_all()`, `run_quality_analysis()`, `run_duplicate_detection()` |
| **CardQualityAnalyzer** | Grade cards A-F | Thresholds config | `analyze()`, `calculate_score()`, `detect_issues()` |
| **DuplicateDetector** | Find duplicate cards | rapidfuzz, Database | `detect_exact()`, `detect_fuzzy()`, `merge_duplicates()` |
| **AIRewriter** | Generate card improvements | Gemini API, Settings | `rewrite_card()`, `split_card()`, `generate_prompt()` |
| **AnkiImportService** | Import Anki decks | AnkiClient, QualityAnalyzer, Database | `import_deck()`, `extract_fsrs()`, `parse_prerequisites()` |

## Error Handling Architecture

### Error Classification

```mermaid
graph TD
    A[Error Occurs] --> B{Error Type?}

    B -->|Transient| C[Retry with Backoff]
    C --> D{Retry Success?}
    D -->|Yes| E[Continue]
    D -->|No after 3 tries| F[Log & Skip]

    B -->|Recoverable| G[Log Warning]
    G --> H[Mark for Review]
    H --> E

    B -->|Fatal| I[Rollback Transaction]
    I --> J[Log Error]
    J --> K[Abort Operation]
    K --> L[Return Error Response]
```

### Error Types & Handling

**1. Transient Errors (Retry)**
```python
# Implemented with tenacity library
from tenacity import retry, stop_after_attempt, wait_exponential

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=10),
    reraise=True
)
def query_notion_with_retry(database_id: str):
    try:
        return notion_client.query_database(database_id)
    except RateLimitError:
        logger.warning("Rate limit hit, retrying...")
        raise  # Trigger retry
    except NetworkTimeout:
        logger.warning("Network timeout, retrying...")
        raise  # Trigger retry
```

**2. Recoverable Errors (Log & Continue)**
```python
def process_flashcards(cards: List[Dict]) -> ProcessResult:
    results = ProcessResult(succeeded=[], failed=[])

    for card in cards:
        try:
            validated = validate_card(card)
            cleaned = clean_card(validated)
            results.succeeded.append(cleaned)
        except ValidationError as e:
            # Log but don't abort
            logger.warning(f"Card {card['id']} failed validation: {e}")
            results.failed.append((card['id'], str(e)))
            continue  # Process remaining cards

    return results
```

**3. Fatal Errors (Abort)**
```python
def sync_databases():
    try:
        with db_transaction():
            # All sync operations
            sync_flashcards()
            sync_concepts()
            sync_modules()
    except DatabaseConnectionError as e:
        # Fatal: can't continue without DB
        logger.error(f"Database connection lost: {e}")
        raise SyncAbortError("Cannot sync without database") from e
    except AuthenticationError as e:
        # Fatal: invalid credentials
        logger.error(f"Notion authentication failed: {e}")
        raise SyncAbortError("Invalid Notion API credentials") from e
```

### Transaction Management

```python
from contextlib import contextmanager

@contextmanager
def db_transaction(db_session: Session):
    """Context manager for database transactions with rollback."""
    try:
        yield db_session
        db_session.commit()
        logger.info("Transaction committed successfully")
    except Exception as e:
        db_session.rollback()
        logger.error(f"Transaction failed, rolled back: {e}")
        raise
    finally:
        db_session.close()

# Usage
def sync_database(db_type: str):
    with db_transaction(get_session()) as session:
        # All operations in this block are atomic
        staging_records = fetch_from_notion()
        session.bulk_insert_mappings(StagingTable, staging_records)
        # If anything fails, entire sync is rolled back
```

## Logging Strategy

### Structured Logging with Loguru

```python
from loguru import logger
import sys

# Configure logging at startup
def configure_logging(settings: Settings):
    # Remove default handler
    logger.remove()

    # Console output with colors
    logger.add(
        sys.stdout,
        level=settings.log_level,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan> - <level>{message}</level>",
        colorize=True
    )

    # File output with rotation
    logger.add(
        "logs/nls_{time:YYYY-MM-DD}.log",
        level="DEBUG",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
        rotation="00:00",  # New file at midnight
        retention="30 days",  # Keep logs for 30 days
        compression="zip"  # Compress old logs
    )

    # Error-only file for quick debugging
    logger.add(
        "logs/errors_{time:YYYY-MM-DD}.log",
        level="ERROR",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}\n{exception}",
        rotation="00:00",
        retention="90 days"
    )
```

### Contextual Logging

```python
from contextvars import ContextVar

# Track request/sync context
sync_id_var: ContextVar[str] = ContextVar("sync_id", default=None)
batch_id_var: ContextVar[str] = ContextVar("batch_id", default=None)

def log_with_context(message: str, **kwargs):
    """Add context to log messages."""
    context = {
        "sync_id": sync_id_var.get(),
        "batch_id": batch_id_var.get(),
        **kwargs
    }
    logger.bind(**context).info(message)

# Usage in sync operations
def sync_database(db_type: str):
    sync_id = str(uuid.uuid4())
    sync_id_var.set(sync_id)

    log_with_context(f"Starting sync for {db_type}", db_type=db_type)
    # All logs in this context will include sync_id

    try:
        # ... sync operations
        log_with_context(f"Sync completed for {db_type}", records=count)
    except Exception as e:
        log_with_context(f"Sync failed for {db_type}", error=str(e))
```

### Log Levels

| Level | When to Use | Example |
|-------|-------------|---------|
| **DEBUG** | Detailed flow for development | "Fetching page abc-123 from Notion", "SQL query: SELECT ..." |
| **INFO** | Normal operations | "Sync started for flashcards", "Processed 500 cards" |
| **WARNING** | Recoverable issues | "Card NET-042 failed validation (skipped)", "Rate limit hit (retrying)" |
| **ERROR** | Errors requiring attention | "Failed to connect to Notion API", "Database constraint violation" |
| **CRITICAL** | System failures | "Database connection lost", "Out of memory" |

## Database Migration Strategy

### Migration Approach

We use **SQL-first migrations** rather than ORM migrations:

```
src/db/migrations/
├── 001_initial_schema.sql       # Staging + canonical tables
├── 002_anki_import.sql           # Anki-specific tables
├── 003_sync_audit.sql            # Sync tracking (Milestone 3)
├── 004_duplicate_detection.sql   # Duplicate groups (Milestone 5)
├── 005_review_queue.sql          # AI rewrite queue (Milestone 6)
└── README.md                     # Migration instructions
```

**Why SQL-first?**
- Full control over PostgreSQL features (JSONB, partial indexes, views)
- Easy to review changes (plain SQL, no magic)
- Consistent with production practices
- Can leverage pgvector for Phase 2.5 embeddings

### Migration Execution

```python
# scripts/run_migrations.py
import psycopg2
from pathlib import Path

def run_migrations(db_url: str):
    """Execute all pending migrations in order."""
    conn = psycopg2.connect(db_url)
    cursor = conn.cursor()

    # Create migrations table if not exists
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS schema_migrations (
            version TEXT PRIMARY KEY,
            executed_at TIMESTAMPTZ DEFAULT NOW()
        )
    """)

    # Get executed migrations
    cursor.execute("SELECT version FROM schema_migrations")
    executed = {row[0] for row in cursor.fetchall()}

    # Find pending migrations
    migrations_dir = Path("src/db/migrations")
    migration_files = sorted(migrations_dir.glob("*.sql"))

    for migration_file in migration_files:
        version = migration_file.stem
        if version in executed:
            print(f"✓ {version} already executed")
            continue

        print(f"⟳ Executing {version}...")
        sql = migration_file.read_text()

        try:
            cursor.execute(sql)
            cursor.execute(
                "INSERT INTO schema_migrations (version) VALUES (%s)",
                (version,)
            )
            conn.commit()
            print(f"✓ {version} executed successfully")
        except Exception as e:
            conn.rollback()
            print(f"✗ {version} failed: {e}")
            raise

    cursor.close()
    conn.close()
```

### Migration Best Practices

1. **Always add, never modify**: Create new migrations, don't edit old ones
2. **Idempotent operations**: Use `IF NOT EXISTS`, `IF EXISTS`
3. **Add comments**: Explain why, not just what
4. **Test rollback**: Ensure `DROP` statements work
5. **Index naming**: `idx_{table}_{column}` convention
6. **Foreign key naming**: `fk_{table}_{ref_table}` convention

## Testing Strategy Overview

### Test Pyramid

```
       /\
      /  \  E2E Tests (10%)
     /----\
    /      \  Integration Tests (30%)
   /--------\
  /          \  Unit Tests (60%)
 /____________\
```

### Test Categories

**1. Unit Tests** (`tests/unit/`)
- Test individual functions/classes in isolation
- Mock external dependencies (Notion API, database, AI)
- Fast execution (< 1 second per test)
- Target: 80%+ code coverage

```python
# Example: Test quality analyzer
def test_quality_analyzer_grades_perfect_card():
    analyzer = CardQualityAnalyzer()
    report = analyzer.analyze(
        front="What is TCP?",
        back="Transmission Control Protocol"
    )
    assert report.grade == QualityGrade.A
    assert report.score == 100
    assert report.is_atomic == True
```

**2. Integration Tests** (`tests/integration/`)
- Test interactions between components
- Use test database (PostgreSQL in Docker)
- Test Notion API with test workspace
- Slower (seconds per test)

```python
# Example: Test full cleaning pipeline
def test_cleaning_pipeline_transforms_staging_to_canonical():
    # Setup: Insert test data to staging
    staging_card = StgAnkiCard(front="Q", back="A")
    db.add(staging_card)
    db.commit()

    # Execute: Run pipeline
    pipeline = CleaningPipeline(settings, db)
    stats = pipeline.process_all()

    # Verify: Check canonical table
    clean_card = db.query(CleanAtom).first()
    assert clean_card is not None
    assert clean_card.quality_grade is not None
    assert stats["transformed"] == 1
```

**3. End-to-End Tests** (`tests/e2e/`)
- Test complete workflows via API
- Use real services (with test accounts)
- Slowest (minutes per test)
- Focus on critical user flows

```python
# Example: Test full sync workflow
def test_sync_notion_to_anki_workflow(api_client):
    # 1. Trigger Notion sync
    response = api_client.post("/api/sync/notion")
    assert response.status_code == 200

    # 2. Wait for completion
    sync_id = response.json()["sync_id"]
    wait_for_sync(sync_id)

    # 3. Verify cards in database
    response = api_client.get("/api/atoms")
    assert len(response.json()["items"]) > 0

    # 4. Push to Anki
    response = api_client.post("/api/anki/push")
    assert response.status_code == 200
```

### Test Fixtures

Common test data and mocks:

```python
# conftest.py
import pytest

@pytest.fixture
def test_settings():
    """Test configuration with safe defaults."""
    return Settings(
        database_url="postgresql://test:test@localhost:5433/test_db",
        notion_api_key="test_key",
        protect_notion=True  # Never write to real Notion
    )

@pytest.fixture
def mock_notion_client():
    """Mock Notion API responses."""
    client = Mock(spec=NotionClient)
    client.fetch_from_database.return_value = [
        {"id": "page-1", "properties": {"Front": "Q1", "Back": "A1"}},
        {"id": "page-2", "properties": {"Front": "Q2", "Back": "A2"}},
    ]
    return client

@pytest.fixture
def test_db_session():
    """Database session for integration tests."""
    # Setup: Create test database
    engine = create_engine("postgresql://test:test@localhost:5433/test_db")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()

    yield session

    # Teardown: Rollback and close
    session.rollback()
    session.close()
```

## Future Enhancements

### Planned Features
1. **CLI interface** - Typer-based commands ✅ (implemented)
2. **Scheduled syncs** - APScheduler integration
3. **Web UI** - Review queue management
4. **Export formats** - CSV, JSON, Anki deck
5. **right-learning integration** - ETL pipeline

### Scalability Improvements
1. **Async/await** - FastAPI + asyncpg
2. **Background tasks** - Celery or RQ
3. **Caching layer** - Redis for embeddings
4. **Horizontal scaling** - Multiple workers
5. **Database sharding** - If >1M flashcards

## References

- [Notion API Documentation](https://developers.notion.com/)
- [AnkiConnect Protocol](https://foosoft.net/projects/anki-connect/)
- [FSRS Algorithm](https://github.com/open-spaced-repetition/fsrs4anki)
- [SuperMemo 20 Rules](https://www.supermemo.com/en/blog/twenty-rules-of-formulating-knowledge)
- [Pydantic Settings](https://docs.pydantic.dev/latest/concepts/pydantic_settings/)
- [SQLAlchemy 2.0](https://docs.sqlalchemy.org/en/20/)
