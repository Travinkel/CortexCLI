# Services Reference

Comprehensive API documentation for all service classes in notion-learning-sync.

## Table of Contents

- [SyncService](#syncservice) - Notion database synchronization
- [CleaningPipeline](#cleaningpipeline) - Data transformation and quality processing
- [CardQualityAnalyzer](#cardqualityanalyzer) - Flashcard quality grading
- [DuplicateDetector](#duplicatedetector) - Duplicate card detection
- [AIRewriter](#airewriter) - AI-powered card improvements
- [AnkiImportService](#ankiimportservice) - Anki deck import
- [NotionClient](#notionclient) - Notion API wrapper
- [AnkiClient](#ankiclient) - AnkiConnect wrapper

---

## SyncService

**Location**: `src/sync/sync_service.py`

**Purpose**: Orchestrate synchronization from Notion to PostgreSQL staging tables.

### Constructor

```python
class SyncService:
    def __init__(
        self,
        settings: Settings,
        notion_client: NotionClient,
        db_session: Session
    ):
        """
        Initialize sync service with dependencies.

        Args:
            settings: Application settings (database IDs, thresholds)
            notion_client: Configured Notion API client
            db_session: SQLAlchemy database session
        """
```

### Methods

#### `sync_all_databases(incremental: bool = True) -> Dict[str, Dict[str, int]]`

Sync all 18 configured Notion databases.

**Parameters**:
- `incremental` (bool): If True, only sync pages changed since last sync. Default: True.

**Returns**: Dictionary mapping database type to statistics:
```python
{
    "flashcards": {"created": 150, "updated": 50, "skipped": 300},
    "concepts": {"created": 20, "updated": 10, "skipped": 70},
    ...
}
```

**Raises**:
- `NotionAPIError`: If Notion API is unreachable
- `DatabaseError`: If database write fails
- `ConfigurationError`: If database IDs not configured

**Example**:
```python
sync_service = SyncService(settings, notion_client, db_session)
results = sync_service.sync_all_databases(incremental=True)

for db_type, stats in results.items():
    print(f"{db_type}: {stats['created']} created, {stats['updated']} updated")
```

**Performance**: ~30-60 seconds for 18 databases with incremental sync.

---

#### `sync_database(db_type: str, db_id: str, incremental: bool = True) -> Tuple[int, int]`

Sync a single Notion database.

**Parameters**:
- `db_type` (str): Database type identifier ("flashcards", "concepts", etc.)
- `db_id` (str): Notion database ID (UUID format)
- `incremental` (bool): Only sync changed pages

**Returns**: Tuple of (created_count, updated_count)

**Example**:
```python
created, updated = sync_service.sync_database(
    "flashcards",
    "abc-123-def-456",
    incremental=True
)
print(f"Synced: {created} new, {updated} updated")
```

---

#### `get_last_sync_time(db_type: str) -> datetime | None`

Get timestamp of last successful sync for a database.

**Parameters**:
- `db_type` (str): Database type identifier

**Returns**: Last sync timestamp or None if never synced

**Example**:
```python
last_sync = sync_service.get_last_sync_time("flashcards")
if last_sync:
    print(f"Last synced: {last_sync.isoformat()}")
else:
    print("Never synced before")
```

---

#### `record_sync_run(db_type: str, stats: Dict) -> None`

Record sync run in audit table.

**Parameters**:
- `db_type` (str): Database type
- `stats` (Dict): Sync statistics (created, updated, errors, duration, etc.)

**Example**:
```python
sync_service.record_sync_run("flashcards", {
    "started_at": datetime.now(),
    "completed_at": datetime.now(),
    "status": "completed",
    "records_created": 150,
    "records_updated": 50,
    "error_message": None
})
```

---

## CleaningPipeline

**Location**: `src/cleaning/pipeline.py`

**Purpose**: Orchestrate transformation of staging data to canonical tables with quality checks.

### Constructor

```python
class CleaningPipeline:
    def __init__(
        self,
        settings: Settings,
        db_session: Session,
        quality_analyzer: CardQualityAnalyzer,
        duplicate_detector: DuplicateDetector,
        ai_rewriter: AIRewriter
    ):
        """
        Initialize cleaning pipeline with dependencies.

        Args:
            settings: Application settings
            db_session: Database session
            quality_analyzer: Card quality grader
            duplicate_detector: Duplicate detection service
            ai_rewriter: AI rewriting service
        """
```

### Methods

#### `process_all(enable_rewrite: bool = False, min_grade: str = "D") -> Dict[str, int]`

Run full cleaning pipeline from staging to canonical.

**Parameters**:
- `enable_rewrite` (bool): If True, queue low-quality cards for AI rewriting
- `min_grade` (str): Minimum grade for rewriting ("D" or "F")

**Returns**: Dictionary of pipeline statistics:
```python
{
    "transformed": 500,
    "graded": 500,
    "duplicates_found": 12,
    "queued_for_rewrite": 77,
    "total_time_seconds": 45
}
```

**Pipeline Stages**:
1. **Transform**: staging → canonical (JSONB extraction, field mapping)
2. **Quality Analysis**: Grade all cards A-F, set flags
3. **Duplicate Detection**: Find exact and fuzzy duplicates
4. **AI Rewriting** (optional): Queue low-quality cards for improvement
5. **Summary**: Generate statistics

**Example**:
```python
pipeline = CleaningPipeline(settings, db, analyzer, detector, rewriter)
stats = pipeline.process_all(enable_rewrite=True, min_grade="D")

print(f"Transformed: {stats['transformed']} cards")
print(f"Grade D/F: {stats['queued_for_rewrite']} cards")
print(f"Duplicates: {stats['duplicates_found']} groups")
```

**Performance**: ~45-60 seconds for 500 cards.

---

#### `transform_staging_to_canonical() -> int`

Transform staging records to canonical tables.

**Returns**: Number of records transformed

**Transformations**:
- Extract properties from Notion JSONB
- Map staging fields to canonical schema
- Set source metadata (notion, anki, ai_generated)
- Handle missing/invalid fields gracefully

**Example**:
```python
count = pipeline.transform_staging_to_canonical()
print(f"Transformed {count} records")
```

---

#### `run_quality_analysis(atoms: List[CleanAtom]) -> None`

Analyze quality and assign grades to atoms.

**Parameters**:
- `atoms` (List[CleanAtom]): Atoms to analyze

**Side Effects**:
- Updates `quality_grade`, `quality_score`, `quality_issues` columns
- Sets `is_atomic`, `is_verbose`, `needs_split`, `needs_rewrite` flags
- Updates `last_quality_check` timestamp

**Example**:
```python
atoms = db.query(CleanAtom).filter(CleanAtom.quality_grade.is_(None)).all()
pipeline.run_quality_analysis(atoms)
db.commit()
```

---

#### `run_duplicate_detection(threshold: float = 0.85) -> int`

Detect duplicate cards using fuzzy matching.

**Parameters**:
- `threshold` (float): Similarity threshold (0.0-1.0). Default: 0.85.

**Returns**: Number of duplicate groups found

**Detection Methods**:
1. **Exact**: Identical front and back text
2. **Fuzzy**: Similar text with rapidfuzz (>= threshold)
3. **Semantic** (Phase 2.5): Embedding-based similarity

**Example**:
```python
groups = pipeline.run_duplicate_detection(threshold=0.90)
print(f"Found {groups} duplicate groups")
```

---

#### `run_ai_rewriting(min_grade: str = "D") -> int`

Queue low-quality cards for AI rewriting.

**Parameters**:
- `min_grade` (str): Minimum grade to queue ("D" or "F")

**Returns**: Number of cards queued

**Queuing Logic**:
- Grade F → Queue with `rewrite_type="split"` (if ENUMERATION_DETECTED)
- Grade F → Queue with `rewrite_type="improve"` (other cases)
- Grade D → Queue with `rewrite_type="improve"`

**Example**:
```python
queued = pipeline.run_ai_rewriting(min_grade="D")
print(f"Queued {queued} cards for AI rewriting")
```

---

## CardQualityAnalyzer

**Location**: `src/cleaning/atomicity.py`

**Purpose**: Grade flashcards A-F based on evidence-based atomicity thresholds.

### Constructor

```python
class CardQualityAnalyzer:
    def __init__(self, settings: Settings | None = None):
        """
        Initialize analyzer with thresholds from settings.

        Args:
            settings: Optional settings override
        """
```

### Methods

#### `analyze(front: str, back: str, code: str | None = None) -> QualityReport`

Analyze a flashcard and generate quality report.

**Parameters**:
- `front` (str): Question/prompt text
- `back` (str): Answer text
- `code` (str, optional): Code block content

**Returns**: `QualityReport` object with:
- `score` (float): 0-100 composite quality score
- `grade` (QualityGrade): Letter grade (A, B, C, D, F)
- `issues` (List[QualityIssue]): Detected problems
- `recommendations` (List[str]): Improvement suggestions
- Computed metrics: word counts, char counts, flags

**Quality Thresholds** (evidence-based):
| Metric | Optimal | Warning | Reject | Source |
|--------|---------|---------|--------|--------|
| Front words | 8-15 | 16-25 | >25 | Wozniak (SuperMemo), Gwern |
| Back words | 1-5 | 6-15 | >15 | SuperMemo research |
| Front chars | 50-100 | 101-200 | >200 | Cognitive Load Theory |
| Back chars | 10-40 | 41-120 | >120 | CLT |
| Code lines | 2-5 | 6-10 | >10 | CLT + programming |

**Example**:
```python
analyzer = CardQualityAnalyzer()
report = analyzer.analyze(
    front="What is TCP?",
    back="Transmission Control Protocol"
)

print(f"Grade: {report.grade}")  # Grade.A
print(f"Score: {report.score}")  # 100
print(f"Atomic: {report.is_atomic}")  # True
print(f"Issues: {report.issues}")  # []
```

**Example with issues**:
```python
report = analyzer.analyze(
    front="What are the seven layers of the OSI model and what does each layer do?",
    back="1. Physical - cables. 2. Data Link - MAC. 3. Network - IP. ..."
)

print(f"Grade: {report.grade}")  # Grade.F
print(f"Score: {report.score}")  # 10
print(f"Issues: {report.issues}")
# [FRONT_TOO_LONG, BACK_TOO_LONG, ENUMERATION_DETECTED, MULTI_SUBQUESTION]
print(f"Recommendations: {report.recommendations}")
# ["Front has 30 words (max: 25). Consider simplifying...",
#  "Enumeration detected. Consider splitting into separate cards..."]
```

---

#### `calculate_score(front_words: int, back_words: int, issues: List[QualityIssue]) -> float`

Calculate composite quality score from metrics and issues.

**Parameters**:
- `front_words` (int): Front word count
- `back_words` (int): Back word count
- `issues` (List[QualityIssue]): Detected quality issues

**Returns**: Score from 0-100

**Scoring Algorithm**:
```python
base_score = 100
for issue in issues:
    base_score -= PENALTY_MAP[issue]  # 10-30 points per issue
return max(0, base_score)
```

**Penalties**:
- FRONT_TOO_LONG: -30
- BACK_TOO_LONG: -30
- ENUMERATION_DETECTED: -30
- MULTIPLE_FACTS: -20
- FRONT_VERBOSE: -10
- BACK_VERBOSE: -10

---

#### `detect_issues(front: str, back: str, code: str | None) -> List[QualityIssue]`

Detect all quality issues in a card.

**Returns**: List of `QualityIssue` enums

**Detected Issues**:
1. `FRONT_TOO_LONG` - Front >25 words
2. `FRONT_VERBOSE` - Front >15 words (warning)
3. `BACK_TOO_LONG` - Back >15 words
4. `BACK_VERBOSE` - Back >5 words (warning)
5. `FRONT_CHARS_EXCEEDED` - Front >200 chars
6. `BACK_CHARS_EXCEEDED` - Back >120 chars
7. `CODE_TOO_LONG` - Code >10 lines
8. `CODE_VERBOSE` - Code >5 lines (warning)
9. `ENUMERATION_DETECTED` - List markers (-, 1., a), bullets)
10. `MULTIPLE_FACTS` - Multiple sentences/causal chains
11. `MULTI_SUBQUESTION` - Multiple questions in front

---

## DuplicateDetector

**Location**: `src/cleaning/duplicates.py`

**Purpose**: Detect duplicate flashcards using exact, fuzzy, and semantic methods.

### Constructor

```python
class DuplicateDetector:
    def __init__(self, db_session: Session):
        """
        Initialize duplicate detector.

        Args:
            db_session: Database session for querying/storing duplicates
        """
```

### Methods

#### `detect_exact(atoms: List[CleanAtom]) -> List[Tuple[str, str]]`

Find exact duplicate cards (identical front and back).

**Parameters**:
- `atoms` (List[CleanAtom]): Atoms to check

**Returns**: List of (atom_id_1, atom_id_2) pairs

**Example**:
```python
detector = DuplicateDetector(db_session)
atoms = db.query(CleanAtom).all()
exact_dupes = detector.detect_exact(atoms)

for id1, id2 in exact_dupes:
    print(f"Exact duplicate: {id1} == {id2}")
```

---

#### `detect_fuzzy(atoms: List[CleanAtom], threshold: float = 0.85) -> List[Tuple[str, str, float]]`

Find similar cards using fuzzy string matching.

**Parameters**:
- `atoms` (List[CleanAtom]): Atoms to check
- `threshold` (float): Similarity threshold (0.0-1.0)

**Returns**: List of (atom_id_1, atom_id_2, similarity_score) tuples

**Algorithm**: Uses `rapidfuzz` library with token_set_ratio:
```python
from rapidfuzz import fuzz

similarity = fuzz.token_set_ratio(card1.back, card2.back)
if similarity >= threshold * 100:
    # Cards are similar
```

**Example**:
```python
fuzzy_dupes = detector.detect_fuzzy(atoms, threshold=0.90)

for id1, id2, score in fuzzy_dupes:
    print(f"Fuzzy match: {id1} ~ {id2} (score: {score:.2f})")
```

**Performance**: O(n²) comparison, optimized with early exit for low scores.

---

#### `detect_semantic(atoms: List[CleanAtom], threshold: float = 0.85) -> List[Tuple[str, str, float]]`

Find semantically similar cards using embeddings (Phase 2.5).

**Status**: Placeholder for Phase 2.5 implementation.

**Planned Implementation**:
- Generate embeddings with sentence-transformers
- Store in pgvector column
- Use cosine similarity for matching
- Index with HNSW for fast search

---

#### `merge_duplicates(pair: Tuple[str, str], keep: str) -> None`

Merge duplicate cards, keeping one and marking the other as superseded.

**Parameters**:
- `pair` (Tuple[str, str]): Pair of duplicate atom IDs
- `keep` (str): Which atom ID to keep

**Side Effects**:
- Mark non-kept atom as `is_deleted=True`
- Update `superseded_by_id` to point to kept atom
- Migrate any references (e.g., Anki note ID) to kept atom

**Example**:
```python
detector.merge_duplicates(("atom-123", "atom-456"), keep="atom-123")
# atom-456 is now marked as deleted, superseded by atom-123
```

---

## AIRewriter

**Location**: `src/cleaning/ai_rewriter.py`

**Purpose**: Generate improved flashcard versions using Gemini 2.0 Flash AI.

### Constructor

```python
class AIRewriter:
    def __init__(self, settings: Settings):
        """
        Initialize AI rewriter with Gemini API credentials.

        Args:
            settings: Settings with ai_model and gemini_api_key
        """
```

### Methods

#### `rewrite_card(front: str, back: str, issues: List[str]) -> RewriteResult`

Generate improved version of a flashcard.

**Parameters**:
- `front` (str): Original front text
- `back` (str): Original back text
- `issues` (List[str]): Quality issues to fix (e.g., ["BACK_TOO_LONG", "MULTIPLE_FACTS"])

**Returns**: `RewriteResult` with:
- `suggested_front` (str): Improved front text
- `suggested_back` (str): Improved back text
- `quality_improvement_estimate` (float): Estimated new score (0-100)
- `ai_reasoning` (str): Explanation of changes

**Example**:
```python
rewriter = AIRewriter(settings)
result = rewriter.rewrite_card(
    front="What are the layers of TCP/IP?",
    back="Application, Transport, Internet, Network Access layers handle different protocol functions",
    issues=["BACK_TOO_LONG", "MULTIPLE_FACTS"]
)

print(f"New front: {result.suggested_front}")
# "What is the top layer of the TCP/IP stack?"
print(f"New back: {result.suggested_back}")
# "Application layer"
print(f"Estimated improvement: {result.quality_improvement_estimate}")
# 85.0 (estimated grade B)
```

---

#### `split_card(front: str, back: str) -> List[Tuple[str, str]]`

Split a non-atomic card into multiple atomic cards.

**Parameters**:
- `front` (str): Original question
- `back` (str): Answer containing multiple facts

**Returns**: List of (new_front, new_back) tuples

**Example**:
```python
splits = rewriter.split_card(
    front="What are the OSI layers?",
    back="1. Physical 2. Data Link 3. Network 4. Transport 5. Session 6. Presentation 7. Application"
)

for new_front, new_back in splits:
    print(f"Q: {new_front}\nA: {new_back}\n")
# Q: What is Layer 1 of the OSI model?
# A: Physical
# Q: What is Layer 2 of the OSI model?
# A: Data Link
# ...
```

---

#### `generate_prompt(front: str, back: str, issues: List[str]) -> str`

Build AI prompt from card and quality issues.

**Parameters**:
- `front`, `back`, `issues`: Card data

**Returns**: Formatted prompt string for Gemini API

**Prompt Template**:
```
You are an expert flashcard creator following evidence-based learning science.

Original Card:
Front: {front}
Back: {back}

Quality Issues Detected:
- BACK_TOO_LONG: Answer has 42 words (max: 15)
- ENUMERATION_DETECTED: List markers found

Task: Rewrite this flashcard to be atomic (one fact per card).

Requirements:
1. Front: ≤25 words, ≤200 characters
2. Back: ≤15 words, ≤120 characters (optimal: ≤5 words)
3. Eliminate list structures - create separate cards instead
4. Keep scientific accuracy

Return JSON:
{
  "suggested_front": "...",
  "suggested_back": "...",
  "reasoning": "..."
}
```

---

## AnkiImportService

**Location**: `src/anki/import_service.py`

**Purpose**: Import Anki decks via AnkiConnect, extract FSRS stats, and run quality analysis.

### Constructor

```python
class AnkiImportService:
    def __init__(
        self,
        settings: Settings,
        anki_client: AnkiClient,
        quality_analyzer: CardQualityAnalyzer,
        db_session: Session
    ):
        """
        Initialize import service.

        Args:
            settings: Application settings
            anki_client: AnkiConnect client
            quality_analyzer: Quality grader
            db_session: Database session
        """
```

### Methods

#### `import_deck(deck_name: str, quality_analysis: bool = True) -> Dict[str, Any]`

Import an Anki deck to staging table.

**Parameters**:
- `deck_name` (str): Name of Anki deck to import
- `quality_analysis` (bool): Run quality grading after import

**Returns**: Dictionary with import statistics:
```python
{
    "import_batch_id": "abc-123-def-456",
    "deck_name": "CCNA Study",
    "cards_imported": 500,
    "cards_with_fsrs": 432,
    "cards_with_prerequisites": 127,
    "grade_distribution": {"A": 203, "B": 145, "C": 75, "D": 52, "F": 25},
    "import_time_seconds": 45
}
```

**Example**:
```python
import_service = AnkiImportService(settings, anki_client, analyzer, db)
result = import_service.import_deck("CCNA Study", quality_analysis=True)

print(f"Imported {result['cards_imported']} cards")
print(f"Grade distribution: {result['grade_distribution']}")
```

---

#### `extract_fsrs(card_info: Dict) -> Dict[str, Any]`

Extract FSRS scheduling data from Anki card.

**Parameters**:
- `card_info` (Dict): Card info from AnkiConnect

**Returns**: Dictionary with FSRS metrics:
```python
{
    "fsrs_stability_days": 45.2,
    "fsrs_difficulty": 0.63,
    "fsrs_retrievability": 0.85,
    "fsrs_last_review": datetime(2025, 11, 15),
    "fsrs_due_date": datetime(2025, 12, 30)
}
```

**FSRS Formulas** (reference):
- Stability = f(interval, ease, reviews)
- Difficulty = f(ease, lapses)
- Retrievability = e^(-days_since_review / stability)

---

#### `parse_prerequisites(tags: List[str]) -> Dict[str, Any]`

Extract prerequisite hierarchy from Anki tags.

**Tag Format**: `tag:prereq:domain:topic:subtopic`

**Example**: `tag:prereq:ccna:layer1:ipv4`

**Returns**:
```python
{
    "prerequisite_tags": ["tag:prereq:ccna:layer1:ipv4"],
    "prerequisite_hierarchy": {
        "domain": "ccna",
        "topic": "layer1",
        "subtopic": "ipv4",
        "path": "ccna/layer1/ipv4"
    },
    "has_prerequisites": True
}
```

**Example**:
```python
prereqs = import_service.parse_prerequisites([
    "networking",
    "tag:prereq:ccna:layer1:ipv4",
    "tag:prereq:ccna:layer1:binary"
])

print(f"Prerequisites: {prereqs['prerequisite_hierarchy']}")
# [{"domain": "ccna", "topic": "layer1", "subtopic": "ipv4"}, ...]
```

---

## NotionClient

**Location**: `src/sync/notion_client.py`

**Purpose**: Typed wrapper around official Notion Python SDK.

### Constructor

```python
class NotionClient:
    def __init__(self, api_key: str | None = None):
        """
        Initialize Notion client.

        Args:
            api_key: Notion integration token (or use settings)
        """
```

### Methods

#### `fetch_from_database(database_id: str, entity_type: str = "pages") -> List[Dict[str, Any]]`

Fetch all pages from a Notion database with pagination.

**Parameters**:
- `database_id` (str): Notion database ID
- `entity_type` (str): Type name for logging

**Returns**: List of page dictionaries (raw Notion format)

**Features**:
- Automatic pagination (handles `has_more` and `next_cursor`)
- Rate limiting (3 req/sec)
- Retry logic for transient errors

**Example**:
```python
client = NotionClient()
pages = client.fetch_from_database("abc-123-def-456", "flashcards")

for page in pages:
    page_id = page["id"]
    properties = page["properties"]
    print(f"Page {page_id}: {properties}")
```

---

#### `query_database(database_id: str, filter: Dict | None = None) -> List[Dict]`

Query Notion database with optional filters.

**Parameters**:
- `database_id` (str): Database ID
- `filter` (Dict, optional): Notion filter object

**Returns**: List of matching pages

**Example with filter**:
```python
# Get only active flashcards
pages = client.query_database(
    "abc-123",
    filter={
        "property": "Status",
        "select": {
            "equals": "Active"
        }
    }
)
```

---

## AnkiClient

**Location**: `src/anki/anki_client.py`

**Purpose**: Wrapper for AnkiConnect API v6.

### Constructor

```python
class AnkiClient:
    def __init__(self, url: str = "http://localhost:8765"):
        """
        Initialize AnkiConnect client.

        Args:
            url: AnkiConnect endpoint URL
        """
```

### Methods

#### `get_deck_names() -> List[str]`

Get list of all Anki deck names.

**Returns**: List of deck name strings

**Example**:
```python
client = AnkiClient()
decks = client.get_deck_names()
print(f"Available decks: {decks}")
# ["Default", "CCNA Study", "Python Quiz"]
```

---

#### `get_cards_from_deck(deck_name: str) -> List[Dict]`

Get all cards from a deck.

**Parameters**:
- `deck_name` (str): Name of Anki deck

**Returns**: List of card dictionaries with note info

**Example**:
```python
cards = client.get_cards_from_deck("CCNA Study")

for card in cards:
    print(f"Note ID: {card['note_id']}")
    print(f"Front: {card['fields']['Front']}")
    print(f"Back: {card['fields']['Back']}")
```

---

#### `cards_info(card_ids: List[int]) -> List[Dict]`

Get detailed info for specific cards.

**Parameters**:
- `card_ids` (List[int]): List of Anki card IDs

**Returns**: List of card info dictionaries with FSRS stats

**Returned Fields**:
- `cardId`, `noteId`, `deckName`
- `factor` (ease factor * 1000)
- `interval` (days)
- `reviews` (review count)
- `lapses` (lapse count)
- `lastReview` (timestamp)
- `due` (due date)

---

## Usage Examples

### Complete Workflow: Notion Sync → Cleaning → Anki Export

```python
from src.sync.sync_service import SyncService
from src.cleaning.pipeline import CleaningPipeline
from src.anki.push_service import AnkiPushService

# 1. Sync from Notion
sync_service = SyncService(settings, notion_client, db_session)
sync_results = sync_service.sync_all_databases(incremental=True)
print(f"Synced {sum(r['created'] for r in sync_results.values())} new records")

# 2. Run cleaning pipeline
pipeline = CleaningPipeline(settings, db_session, analyzer, detector, rewriter)
clean_stats = pipeline.process_all(enable_rewrite=True, min_grade="D")
print(f"Cleaned {clean_stats['transformed']} records")
print(f"Found {clean_stats['duplicates_found']} duplicates")
print(f"Queued {clean_stats['queued_for_rewrite']} for AI rewriting")

# 3. Push clean atoms to Anki
push_service = AnkiPushService(settings, anki_client, db_session)
pushed = push_service.push_clean_atoms()
print(f"Pushed {pushed} cards to Anki")
```

### Error Handling Example

```python
from src.sync.sync_service import SyncService
from src.exceptions import NotionAPIError, DatabaseError

try:
    sync_service = SyncService(settings, notion_client, db_session)
    results = sync_service.sync_all_databases()
except NotionAPIError as e:
    logger.error(f"Notion API failed: {e}")
    # Retry or alert
except DatabaseError as e:
    logger.error(f"Database write failed: {e}")
    # Rollback handled automatically
except Exception as e:
    logger.critical(f"Unexpected error: {e}")
    raise
```

---

## Performance Guidelines

### SyncService
- **Incremental sync**: 30-60 seconds for 18 databases
- **Full sync**: 2-5 minutes for 18 databases (depending on size)
- **Memory**: ~100-200 MB peak

### CleaningPipeline
- **Speed**: ~1,000 cards per minute (quality analysis)
- **Duplicate detection**: O(n²) for fuzzy, O(n log n) for exact
- **Memory**: ~500 MB for 10,000 cards

### AnkiImportService
- **Speed**: ~100-200 cards per second from AnkiConnect
- **Large decks**: Use batching (500 cards per batch)
- **Memory**: ~300 MB for 5,000 cards

---

## Testing Services

All services support dependency injection for easy testing:

```python
import pytest
from unittest.mock import Mock

@pytest.fixture
def mock_notion_client():
    client = Mock(spec=NotionClient)
    client.fetch_from_database.return_value = [
        {"id": "page-1", "properties": {"Front": "Q1", "Back": "A1"}},
    ]
    return client

def test_sync_service(mock_notion_client):
    sync_service = SyncService(settings, mock_notion_client, db_session)
    created, updated = sync_service.sync_database("flashcards", "db-id")

    assert created == 1
    assert updated == 0
    mock_notion_client.fetch_from_database.assert_called_once()
```

---

## Configuration

All services use Pydantic Settings for type-safe configuration:

```python
from config import get_settings

settings = get_settings()

# Access typed settings
print(settings.notion_api_key)  # str
print(settings.atomicity_front_max_words)  # int = 25
print(settings.ai_model)  # str = "gemini-2.0-flash"
```

See [Configuration Guide](./configuration.md) for full settings reference.

---

## Further Reading

- [Architecture Overview](./architecture.md) - System design and patterns
- [API Reference](./api-reference.md) - REST API endpoints
- [Testing Guide](./testing-guide.md) - Testing strategies
- [Deployment Guide](./deployment-guide.md) - Production setup
