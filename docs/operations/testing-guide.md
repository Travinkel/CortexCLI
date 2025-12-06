# Testing Guide

Comprehensive testing strategy for notion-learning-sync covering unit tests, integration tests, and end-to-end tests.

## Table of Contents

- [Testing Philosophy](#testing-philosophy)
- [Test Pyramid](#test-pyramid)
- [Test Environment Setup](#test-environment-setup)
- [Unit Testing](#unit-testing)
- [Integration Testing](#integration-testing)
- [End-to-End Testing](#end-to-end-testing)
- [Test Fixtures and Mocks](#test-fixtures-and-mocks)
- [Coverage Targets](#coverage-targets)
- [CI/CD Integration](#cicd-integration)
- [Performance Testing](#performance-testing)

---

## Testing Philosophy

### Core Principles

1. **Test behavior, not implementation** - Focus on what the code does, not how
2. **Fast feedback loops** - Unit tests run in seconds, not minutes
3. **Isolation** - Tests don't depend on external services or each other
4. **Reproducibility** - Tests produce same results every time
5. **Readability** - Tests serve as living documentation

### Test-Driven Development (TDD)

While not mandatory, TDD is encouraged for complex logic:

```
1. Write failing test (RED)
   ↓
2. Write minimal code to pass (GREEN)
   ↓
3. Refactor while keeping tests green (REFACTOR)
   ↓
   Repeat
```

**When to use TDD**:
- Complex algorithms (quality scoring, duplicate detection)
- Business logic with many edge cases
- Bug fixes (write test that reproduces bug, then fix)

**When to skip TDD**:
- Simple CRUD operations
- Straightforward integrations
- Exploratory prototypes

---

## Test Pyramid

Our testing strategy follows the test pyramid: more unit tests, fewer integration tests, minimal E2E tests.

```
       /\
      /  \  E2E Tests (10%)
     /----\  - Full workflows via API
    /      \  - Real external services
   /--------\  - Slow (minutes)
  /          \  Integration Tests (30%)
 /            \  - Component interactions
/              \  - Test database
/______________\  - Medium speed (seconds)

   Unit Tests (60%)
   - Individual functions/classes
   - Mocked dependencies
   - Fast (<1 second)
```

### Distribution Guidelines

| Test Type | Percentage | Count (target) | Execution Time |
|-----------|------------|----------------|----------------|
| Unit | 60% | 150-200 tests | <2 minutes total |
| Integration | 30% | 50-75 tests | 5-10 minutes total |
| E2E | 10% | 10-20 tests | 10-20 minutes total |

**Total Coverage Target**: 80%+ code coverage

---

## Test Environment Setup

### Prerequisites

```bash
# Install development dependencies
pip install -r requirements-dev.txt

# Install pytest and plugins
pip install pytest pytest-cov pytest-mock pytest-asyncio

# Install test database
docker run -d \
  --name nls-test-db \
  -e POSTGRES_PASSWORD=test \
  -e POSTGRES_USER=test \
  -e POSTGRES_DB=test_db \
  -p 5433:5432 \
  postgres:15
```

### Environment Variables

Create `.env.test` for test configuration:

```bash
# Database
DATABASE_URL=postgresql://test:test@localhost:5433/test_db

# Notion (test workspace)
NOTION_API_KEY=test_secret_key
PROTECT_NOTION=true  # Never write to production Notion

# Anki (test deck)
ANKI_CONNECT_URL=http://localhost:8765

# AI (use mock in tests)
AI_MODEL=gemini-2.0-flash
GEMINI_API_KEY=test_api_key

# Logging
LOG_LEVEL=WARNING  # Suppress logs in tests
```

### Test Database Setup

```python
# tests/conftest.py
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from src.db.models.base import Base

TEST_DB_URL = "postgresql://test:test@localhost:5433/test_db"

@pytest.fixture(scope="session")
def test_engine():
    """Create test database engine once per session."""
    engine = create_engine(TEST_DB_URL)
    Base.metadata.create_all(engine)
    yield engine
    Base.metadata.drop_all(engine)
    engine.dispose()

@pytest.fixture
def test_db_session(test_engine):
    """Create fresh database session for each test."""
    Session = sessionmaker(bind=test_engine)
    session = Session()

    yield session

    # Rollback and close after test
    session.rollback()
    session.close()
```

---

## Unit Testing

### What to Unit Test

- **Pure functions** - Functions without side effects
- **Business logic** - Quality scoring, duplicate detection algorithms
- **Data transformations** - JSONB extraction, field mapping
- **Validation logic** - Input validation, constraint checking

### Unit Test Structure

Follow **Arrange-Act-Assert** (AAA) pattern:

```python
def test_quality_analyzer_grades_perfect_card():
    # ARRANGE - Set up test data
    analyzer = CardQualityAnalyzer()
    front = "What is TCP?"
    back = "Transmission Control Protocol"

    # ACT - Execute the code under test
    report = analyzer.analyze(front, back)

    # ASSERT - Verify expected outcome
    assert report.grade == QualityGrade.A
    assert report.score == 100
    assert report.is_atomic == True
    assert len(report.issues) == 0
```

### Unit Test Examples

#### Testing Quality Analyzer

```python
# tests/unit/test_quality_analyzer.py
import pytest
from src.cleaning.atomicity import CardQualityAnalyzer, QualityGrade, QualityIssue

class TestCardQualityAnalyzer:
    """Test suite for card quality grading."""

    @pytest.fixture
    def analyzer(self):
        """Create analyzer instance for tests."""
        return CardQualityAnalyzer()

    def test_grade_a_perfect_card(self, analyzer):
        """Perfect card gets grade A with score 100."""
        report = analyzer.analyze(
            front="What is TCP?",
            back="Transmission Control Protocol"
        )

        assert report.grade == QualityGrade.A
        assert report.score == 100
        assert report.is_atomic == True
        assert report.needs_rewrite == False

    def test_grade_f_enumeration_card(self, analyzer):
        """Card with enumeration gets grade F."""
        report = analyzer.analyze(
            front="What are the OSI layers?",
            back="1. Physical 2. Data Link 3. Network 4. Transport"
        )

        assert report.grade == QualityGrade.F
        assert QualityIssue.ENUMERATION_DETECTED in report.issues
        assert report.needs_split == True

    def test_grade_d_verbose_card(self, analyzer):
        """Verbose card gets grade D."""
        report = analyzer.analyze(
            front="What is the purpose of TCP three-way handshake?",
            back="The three-way handshake ensures both client and server are ready to communicate by exchanging SYN and ACK packets"
        )

        assert report.grade == QualityGrade.D
        assert QualityIssue.BACK_TOO_LONG in report.issues
        assert report.needs_rewrite == True

    @pytest.mark.parametrize("front,back,expected_grade", [
        ("Short?", "Short", QualityGrade.A),
        ("A bit longer question?", "A bit longer answer here", QualityGrade.B),
        ("Much longer question that exceeds optimal length?", "Much longer answer", QualityGrade.C),
    ])
    def test_various_lengths(self, analyzer, front, back, expected_grade):
        """Test grading across various card lengths."""
        report = analyzer.analyze(front, back)
        assert report.grade == expected_grade
```

#### Testing Duplicate Detection

```python
# tests/unit/test_duplicate_detector.py
from unittest.mock import Mock
from src.cleaning.duplicates import DuplicateDetector
from src.db.models.canonical import CleanAtom

class TestDuplicateDetector:
    """Test suite for duplicate detection."""

    @pytest.fixture
    def mock_db_session(self):
        """Mock database session."""
        return Mock()

    @pytest.fixture
    def detector(self, mock_db_session):
        """Create detector with mocked DB."""
        return DuplicateDetector(mock_db_session)

    def test_detect_exact_duplicates(self, detector):
        """Exact duplicates are detected."""
        atoms = [
            CleanAtom(id="a1", front_content="What is TCP?", back_content="Protocol"),
            CleanAtom(id="a2", front_content="What is TCP?", back_content="Protocol"),
        ]

        dupes = detector.detect_exact(atoms)

        assert len(dupes) == 1
        assert dupes[0] == ("a1", "a2")

    def test_detect_fuzzy_duplicates(self, detector):
        """Similar cards are detected with fuzzy matching."""
        atoms = [
            CleanAtom(id="a1", front_content="What is TCP?", back_content="Protocol"),
            CleanAtom(id="a2", front_content="What is TCP", back_content="Protocol"),  # Missing ?
        ]

        dupes = detector.detect_fuzzy(atoms, threshold=0.90)

        assert len(dupes) == 1
        atom_id_1, atom_id_2, score = dupes[0]
        assert score >= 0.90

    def test_no_false_positives(self, detector):
        """Different cards are not flagged as duplicates."""
        atoms = [
            CleanAtom(id="a1", front_content="What is TCP?", back_content="Protocol"),
            CleanAtom(id="a2", front_content="What is UDP?", back_content="Protocol"),
        ]

        dupes = detector.detect_fuzzy(atoms, threshold=0.90)

        assert len(dupes) == 0
```

#### Testing with Parametrize

Use `@pytest.mark.parametrize` to test multiple scenarios:

```python
@pytest.mark.parametrize("word_count,expected_issue", [
    (10, None),  # Within limit
    (20, QualityIssue.FRONT_VERBOSE),  # Warning threshold
    (30, QualityIssue.FRONT_TOO_LONG),  # Max threshold
])
def test_front_word_count_thresholds(analyzer, word_count, expected_issue):
    """Test word count thresholds for front text."""
    front = " ".join(["word"] * word_count)
    report = analyzer.analyze(front=front, back="answer")

    if expected_issue:
        assert expected_issue in report.issues
    else:
        assert QualityIssue.FRONT_TOO_LONG not in report.issues
        assert QualityIssue.FRONT_VERBOSE not in report.issues
```

---

## Integration Testing

### What to Integration Test

- **Service interactions** - SyncService → NotionClient → Database
- **Pipeline workflows** - CleaningPipeline orchestrating multiple services
- **Database operations** - CRUD with real PostgreSQL
- **External API integration** - Notion API, AnkiConnect (with test accounts)

### Integration Test Structure

Integration tests use real database and potentially real APIs:

```python
@pytest.mark.integration
class TestSyncService:
    """Integration tests for Notion sync service."""

    @pytest.fixture
    def sync_service(self, test_db_session, mock_notion_client):
        """Create sync service with real DB, mocked Notion."""
        return SyncService(
            settings=get_test_settings(),
            notion_client=mock_notion_client,
            db_session=test_db_session
        )

    def test_sync_flashcards_creates_staging_records(
        self, sync_service, test_db_session
    ):
        """Syncing flashcards creates records in staging table."""
        # ACT
        created, updated = sync_service.sync_database(
            "flashcards",
            "test-db-id",
            incremental=False
        )

        # ASSERT
        assert created > 0

        # Verify records in database
        records = test_db_session.query(StgNotionFlashcard).all()
        assert len(records) == created
```

### Integration Test Examples

#### Testing Cleaning Pipeline

```python
# tests/integration/test_cleaning_pipeline.py
import pytest
from src.cleaning.pipeline import CleaningPipeline
from src.db.models.staging import StgAnkiCard
from src.db.models.canonical import CleanAtom

@pytest.mark.integration
class TestCleaningPipeline:
    """Integration tests for cleaning pipeline."""

    @pytest.fixture
    def pipeline(self, test_db_session, test_settings):
        """Create pipeline with real DB and services."""
        analyzer = CardQualityAnalyzer(test_settings)
        detector = DuplicateDetector(test_db_session)
        rewriter = AIRewriter(test_settings)

        return CleaningPipeline(
            test_settings,
            test_db_session,
            analyzer,
            detector,
            rewriter
        )

    @pytest.fixture
    def setup_staging_data(self, test_db_session):
        """Insert test data into staging table."""
        cards = [
            StgAnkiCard(
                anki_note_id=1,
                front="What is TCP?",
                back="Transmission Control Protocol",
                deck_name="Test Deck"
            ),
            StgAnkiCard(
                anki_note_id=2,
                front="What is UDP?",
                back="User Datagram Protocol",
                deck_name="Test Deck"
            ),
        ]
        test_db_session.add_all(cards)
        test_db_session.commit()

        yield

        # Cleanup
        test_db_session.query(StgAnkiCard).delete()
        test_db_session.query(CleanAtom).delete()
        test_db_session.commit()

    def test_pipeline_transforms_staging_to_canonical(
        self, pipeline, test_db_session, setup_staging_data
    ):
        """Pipeline successfully transforms staging → canonical."""
        # ACT
        stats = pipeline.process_all(enable_rewrite=False)

        # ASSERT
        assert stats["transformed"] == 2

        # Verify canonical records
        clean_atoms = test_db_session.query(CleanAtom).all()
        assert len(clean_atoms) == 2
        assert clean_atoms[0].front_content == "What is TCP?"
        assert clean_atoms[0].quality_grade is not None

    def test_pipeline_detects_duplicates(
        self, pipeline, test_db_session
    ):
        """Pipeline detects duplicate cards."""
        # ARRANGE - Insert duplicates to staging
        cards = [
            StgAnkiCard(anki_note_id=1, front="Q", back="A", deck_name="Test"),
            StgAnkiCard(anki_note_id=2, front="Q", back="A", deck_name="Test"),
        ]
        test_db_session.add_all(cards)
        test_db_session.commit()

        # ACT
        stats = pipeline.process_all()

        # ASSERT
        assert stats["duplicates_found"] == 1

    def test_pipeline_rollback_on_error(
        self, pipeline, test_db_session, setup_staging_data
    ):
        """Pipeline rolls back transaction on errors."""
        # ARRANGE - Inject error
        def mock_transform_with_error():
            raise ValueError("Simulated error")

        pipeline.transform_staging_to_canonical = mock_transform_with_error

        # ACT
        with pytest.raises(ValueError):
            pipeline.process_all()

        # ASSERT - No canonical records created
        clean_atoms = test_db_session.query(CleanAtom).all()
        assert len(clean_atoms) == 0
```

#### Testing Anki Import

```python
# tests/integration/test_anki_import_service.py
import pytest
from unittest.mock import patch
from src.anki.import_service import AnkiImportService

@pytest.mark.integration
@pytest.mark.anki  # Only run if AnkiConnect available
class TestAnkiImportService:
    """Integration tests for Anki import (requires AnkiConnect)."""

    @pytest.fixture
    def import_service(self, test_db_session, test_settings):
        """Create import service with real dependencies."""
        anki_client = AnkiClient()
        analyzer = CardQualityAnalyzer()

        return AnkiImportService(
            test_settings,
            anki_client,
            analyzer,
            test_db_session
        )

    @pytest.mark.skipif(
        not anki_connect_available(),
        reason="AnkiConnect not running"
    )
    def test_import_deck_real_anki(self, import_service):
        """Import actual Anki deck (integration test)."""
        # Requires test deck in Anki named "Test Deck"
        result = import_service.import_deck(
            "Test Deck",
            quality_analysis=True
        )

        assert result["cards_imported"] > 0
        assert "grade_distribution" in result
        assert result["import_batch_id"] is not None
```

---

## End-to-End Testing

### What to E2E Test

- **Critical user workflows** - Notion sync → cleaning → Anki push
- **API endpoints** - Full request/response cycle
- **Error handling** - Graceful degradation, retry logic
- **Performance** - Acceptable latency for common operations

### E2E Test Structure

E2E tests use the full application stack:

```python
@pytest.mark.e2e
class TestFullSyncWorkflow:
    """End-to-end test for complete sync workflow."""

    @pytest.fixture
    def api_client(self):
        """Create test client for FastAPI."""
        from fastapi.testclient import TestClient
        from src.api.main import app

        return TestClient(app)

    def test_notion_to_anki_workflow(self, api_client):
        """Test complete workflow: Notion → DB → Anki."""
        # 1. Trigger Notion sync
        response = api_client.post("/api/sync/notion", json={
            "incremental": False,
            "databases": ["flashcards"]
        })
        assert response.status_code == 200
        sync_id = response.json()["sync_id"]

        # 2. Wait for sync completion
        import time
        for _ in range(30):  # Wait up to 30 seconds
            status_response = api_client.get(f"/api/sync/status/{sync_id}")
            status = status_response.json()["status"]
            if status in ["completed", "failed"]:
                break
            time.sleep(1)

        assert status == "completed"

        # 3. Run cleaning pipeline
        clean_response = api_client.post("/api/clean/run", json={
            "enable_rewrite": False
        })
        assert clean_response.status_code == 200
        assert clean_response.json()["stats"]["transformed"] > 0

        # 4. Verify cards in database
        atoms_response = api_client.get("/api/atoms?limit=10")
        assert atoms_response.status_code == 200
        atoms = atoms_response.json()["items"]
        assert len(atoms) > 0
        assert atoms[0]["quality_grade"] is not None
```

### E2E Test Performance

E2E tests are slow. Optimize by:

1. **Running selectively** - Mark with `@pytest.mark.e2e` and run separately
2. **Parallel execution** - Use `pytest-xdist` plugin
3. **Caching setup** - Reuse database state across tests when possible
4. **Cleanup efficiently** - Truncate tables instead of deleting rows

```bash
# Run only E2E tests in parallel
pytest -m e2e -n 4  # 4 parallel workers
```

---

## Test Fixtures and Mocks

### Common Fixtures

```python
# tests/conftest.py
import pytest
from unittest.mock import Mock
from src.config import Settings

@pytest.fixture
def test_settings():
    """Test configuration with safe defaults."""
    return Settings(
        database_url="postgresql://test:test@localhost:5433/test_db",
        notion_api_key="test_key",
        protect_notion=True,
        log_level="WARNING"
    )

@pytest.fixture
def mock_notion_client():
    """Mock Notion client with predefined responses."""
    client = Mock()
    client.fetch_from_database.return_value = [
        {
            "id": "page-1",
            "properties": {
                "Front": {"title": [{"plain_text": "Q1"}]},
                "Back": {"rich_text": [{"plain_text": "A1"}]},
            }
        },
        {
            "id": "page-2",
            "properties": {
                "Front": {"title": [{"plain_text": "Q2"}]},
                "Back": {"rich_text": [{"plain_text": "A2"}]},
            }
        },
    ]
    return client

@pytest.fixture
def mock_anki_client():
    """Mock AnkiConnect client."""
    client = Mock()
    client.get_deck_names.return_value = ["Default", "Test Deck"]
    client.get_cards_from_deck.return_value = [
        {"note_id": 1, "fields": {"Front": "Q1", "Back": "A1"}},
        {"note_id": 2, "fields": {"Front": "Q2", "Back": "A2"}},
    ]
    return client

@pytest.fixture
def sample_clean_atoms():
    """Sample CleanAtom instances for testing."""
    return [
        CleanAtom(
            id="atom-1",
            front_content="What is TCP?",
            back_content="Transmission Control Protocol",
            source="notion",
            quality_grade="A",
            quality_score=100
        ),
        CleanAtom(
            id="atom-2",
            front_content="What is UDP?",
            back_content="User Datagram Protocol",
            source="notion",
            quality_grade="A",
            quality_score=100
        ),
    ]
```

### Mocking External APIs

Use `@patch` decorator to mock external API calls:

```python
from unittest.mock import patch

@patch('src.sync.notion_client.Client')
def test_sync_with_mocked_notion(mock_notion_class, test_db_session):
    """Test sync without hitting real Notion API."""
    # Setup mock
    mock_instance = mock_notion_class.return_value
    mock_instance.databases.query.return_value = {
        "results": [{"id": "page-1", "properties": {}}]
    }

    # Test sync
    client = NotionClient()
    pages = client.fetch_from_database("db-id")

    assert len(pages) == 1
    mock_instance.databases.query.assert_called_once()
```

---

## Coverage Targets

### Measuring Coverage

```bash
# Run tests with coverage report
pytest --cov=src --cov-report=html --cov-report=term

# View HTML report
open htmlcov/index.html
```

### Coverage Goals

| Component | Target Coverage | Priority |
|-----------|----------------|----------|
| Business Logic | 90%+ | Critical |
| Service Layer | 80%+ | High |
| API Endpoints | 70%+ | Medium |
| Data Models | 60%+ | Low |

### Coverage Configuration

```ini
# .coveragerc
[run]
source = src
omit =
    */tests/*
    */migrations/*
    */__pycache__/*
    */venv/*

[report]
exclude_lines =
    pragma: no cover
    def __repr__
    raise AssertionError
    raise NotImplementedError
    if __name__ == .__main__.:
    if TYPE_CHECKING:
```

---

## CI/CD Integration

### GitHub Actions Workflow

```yaml
# .github/workflows/test.yml
name: Test Suite

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest

    services:
      postgres:
        image: postgres:15
        env:
          POSTGRES_PASSWORD: test
          POSTGRES_USER: test
          POSTGRES_DB: test_db
        ports:
          - 5433:5432
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5

    steps:
      - uses: actions/checkout@v3

      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'

      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          pip install -r requirements-dev.txt

      - name: Run unit tests
        run: pytest tests/unit --cov=src --cov-report=xml

      - name: Run integration tests
        run: pytest tests/integration -m "not anki"
        env:
          DATABASE_URL: postgresql://test:test@localhost:5433/test_db

      - name: Upload coverage
        uses: codecov/codecov-action@v3
        with:
          files: ./coverage.xml
```

### Pre-commit Hooks

```yaml
# .pre-commit-config.yaml
repos:
  - repo: local
    hooks:
      - id: pytest-unit
        name: Run unit tests
        entry: pytest tests/unit -x
        language: system
        pass_filenames: false
        always_run: true
```

---

## Performance Testing

### Load Testing

Test performance under realistic loads:

```python
# tests/performance/test_sync_performance.py
import pytest
import time

@pytest.mark.performance
class TestSyncPerformance:
    """Performance tests for sync operations."""

    def test_sync_5000_cards_under_2_minutes(self, sync_service):
        """Syncing 5000 cards should complete in <2 minutes."""
        start = time.time()

        sync_service.sync_database("flashcards", "test-db-id")

        duration = time.time() - start
        assert duration < 120, f"Sync took {duration:.1f}s (expected <120s)"

    def test_quality_analysis_1000_cards_per_minute(self, pipeline):
        """Quality analysis should process 1000+ cards/min."""
        # Setup: 1000 test cards
        atoms = [create_test_atom() for _ in range(1000)]

        start = time.time()
        pipeline.run_quality_analysis(atoms)
        duration = time.time() - start

        cards_per_second = 1000 / duration
        assert cards_per_second > 16.6, f"Only {cards_per_second:.1f} cards/sec"
```

### Benchmarking

Use `pytest-benchmark` for micro-benchmarks:

```python
import pytest

def test_quality_analyzer_benchmark(benchmark):
    """Benchmark quality analysis."""
    analyzer = CardQualityAnalyzer()

    result = benchmark(
        analyzer.analyze,
        front="What is TCP?",
        back="Transmission Control Protocol"
    )

    # Result includes timing statistics
    assert result.grade == QualityGrade.A
```

---

## Best Practices

### Do's ✅

1. **Write descriptive test names** - `test_quality_analyzer_assigns_grade_f_to_enumeration_cards`
2. **Use fixtures for setup** - Avoid repetitive setup code
3. **Test edge cases** - Empty strings, None values, very large inputs
4. **Isolate tests** - Each test should be independent
5. **Mock external dependencies** - Don't hit real APIs in unit tests
6. **Test error paths** - Verify exception handling
7. **Keep tests fast** - Unit tests should run in milliseconds

### Don'ts ❌

1. **Don't test implementation details** - Test behavior, not internals
2. **Don't share state between tests** - Use fixtures, not global variables
3. **Don't skip cleanup** - Always teardown test data
4. **Don't ignore flaky tests** - Fix or remove them
5. **Don't test framework code** - Trust SQLAlchemy, FastAPI work correctly
6. **Don't write overly complex tests** - If test is hard to understand, simplify
7. **Don't commit failing tests** - Green builds only

---

## Running Tests

### Basic Commands

```bash
# Run all tests
pytest

# Run specific test file
pytest tests/unit/test_quality_analyzer.py

# Run specific test
pytest tests/unit/test_quality_analyzer.py::test_grade_a_perfect_card

# Run tests matching pattern
pytest -k "quality"

# Run with verbose output
pytest -v

# Run with coverage
pytest --cov=src --cov-report=term-missing

# Run in parallel (faster)
pytest -n 4  # 4 workers
```

### Test Markers

```bash
# Run only unit tests
pytest -m unit

# Run only integration tests
pytest -m integration

# Skip E2E tests (slow)
pytest -m "not e2e"

# Run performance tests
pytest -m performance --benchmark-only
```

### Watch Mode

Use `pytest-watch` for continuous testing:

```bash
# Install
pip install pytest-watch

# Run
ptw -- --cov=src
```

---

## Troubleshooting

### Common Issues

**Issue**: Tests pass locally but fail in CI
- **Cause**: Environment differences (Python version, dependencies, timezones)
- **Fix**: Match CI environment locally with Docker, pin dependency versions

**Issue**: Flaky tests (intermittent failures)
- **Cause**: Race conditions, timing dependencies, shared state
- **Fix**: Add explicit waits, increase timeouts, isolate tests

**Issue**: Slow test suite
- **Cause**: Too many integration/E2E tests, no parallelization
- **Fix**: Move logic to unit tests, run in parallel with `pytest-xdist`

**Issue**: Database state pollution
- **Cause**: Tests not cleaning up, transactions not rolled back
- **Fix**: Use fixtures with proper teardown, ensure rollback in finally blocks

---

## Current Test Status

### Test Suite Summary (December 2025)

The test suite currently includes **51 passing tests** across unit and integration levels:

```
tests/unit/test_embedding_service.py    18 tests  # Embedding service functionality
tests/unit/test_section_linking.py      17 tests  # Atom-to-section keyword matching
tests/integration/test_data_pipeline.py 16 tests  # Database integrity checks
```

### Test Categories

#### Unit Tests (`tests/unit/`)

| Module | Tests | Purpose |
|--------|-------|---------|
| `test_embedding_service.py` | 18 | Semantic embedding generation, caching |
| `test_section_linking.py` | 17 | CCNA section keyword matching |

**Section Linking Tests** (`test_section_linking.py`):
- Exact keyword matching scores higher than partial
- No match returns zero score
- Multiple keywords increase score
- Case-insensitive matching
- Correct section assignment for networking, TCP, IPv4, IPv6 content
- Graceful handling of empty strings, very long content, special characters

#### Integration Tests (`tests/integration/`)

| Module | Tests | Purpose |
|--------|-------|---------|
| `test_data_pipeline.py` | 16 | Database integrity, atom linking, mastery counts |

**Data Pipeline Tests** (`test_data_pipeline.py`):
- `TestAtomDataIntegrity` - Atoms have required fields, valid types, linked to sections
- `TestSectionHierarchy` - Modules 1-16 covered, unique IDs, valid parent references
- `TestMasteryTracking` - Mastery counts match actual atoms, valid ranges
- `TestConceptsHierarchy` - Concepts exist and atoms can link to them
- `TestQuizQuestions` - Quiz questions exist and link to atoms
- `TestDataConsistency` - No orphan records, reasonable type distribution

#### Smoke Tests (`tests/smoke/`)

| Module | Tests | Purpose |
|--------|-------|---------|
| `test_cli_commands.py` | ~20 | CLI command execution, output format |

**CLI Command Tests**:
- All help commands work (`--help`, `stats --help`, etc.)
- Core commands run without crashing (`stats`, `path`, `today`)
- Output uses proper formatting (tables, colors)
- No Python exceptions in output
- Performance: help <2s, stats <5s

#### E2E Tests (`tests/e2e/`)

| Module | Tests | Purpose |
|--------|-------|---------|
| `test_study_flow.py` | ~25 | API endpoints, study session workflow |

**API Endpoint Tests** (require running server):
- Health endpoint returns OK
- OpenAPI docs available
- CCNA modules listing
- Study session creation
- Answer submission
- Statistics endpoints

### Running the Test Suite

```bash
# Run unit tests only (fast, no database required)
pytest tests/unit -v

# Run integration tests (requires database)
pytest tests/integration -v -m integration

# Run smoke tests (requires CLI module)
pytest tests/smoke -v -m smoke

# Run E2E tests (requires API server)
pytest tests/e2e -v -m e2e

# Run all except E2E (most common)
pytest tests/ --ignore=tests/e2e -v

# Run with coverage
pytest tests/unit tests/integration --cov=src --cov-report=html
```

### Test Markers

The test suite uses pytest markers for selective execution:

```ini
# In pytest.ini or pyproject.toml
markers =
    unit: Unit tests (no external dependencies)
    integration: Integration tests (require database)
    smoke: Smoke tests for CLI commands
    e2e: End-to-end tests (require API server)
    slow: Slow tests (skip in quick runs)
```

### Data Integrity Verification

The integration tests verify that the CCNA data pipeline is correct:

- **4,574 atoms** linked to CCNA sections (93% link rate)
- **350 atoms** unmatched (pending keyword expansion)
- **63 unique parent sections** with atoms
- **Mastery counts** match actual atom distribution

---

## Further Reading

- [pytest Documentation](https://docs.pytest.org/)
- [Testing Best Practices (Python)](https://docs.python-guide.org/writing/tests/)
- [Test-Driven Development (TDD)](https://www.obeythetestinggoat.com/)
- [Mock vs Stub vs Fake](https://martinfowler.com/articles/mocksArentStubs.html)
