# Behavior-Driven Development Testing Strategy

## Overview

This document defines the testing approach for Cortex-CLI's adaptive learning engine, emphasizing behavior-driven development (BDD) to ensure cognitive science principles are correctly implemented in code.

## Testing Philosophy

Testing in a DARPA-class learning system differs from standard software testing. We verify not just correctness, but **cognitive validity**—does the system accurately model human learning?

### Core Principles

1. **Atom Behaviors Are Cognitive Operations**: Each atom type tests a specific mental process (recall, recognition, procedural sequencing). Tests must verify the cognitive load and learning outcome match research expectations.

2. **Misconception Detection Is First-Class**: Tests verify that wrong answers map to specific cognitive errors, not random failures.

3. **State Transitions Are Probabilistic**: Unlike deterministic systems, mastery updates are Bayesian. Tests verify probability distributions, not exact values.

4. **Latency Is Diagnostic**: Response time distinguishes guessing (fast+wrong) from struggle (slow+wrong). Tests must verify timing-based inference logic.

## Test Hierarchy

### Unit Tests (Cognitive Primitives)

**Target:** Individual atom handlers, grading logic, mastery update formulas.

**Framework:** pytest with hypothesis for property-based testing.

**Coverage Target:** 85% minimum for core learning engine.

**Example Test Structure:**

```python
# tests/unit/test_bayesian_mastery.py

import pytest
from hypothesis import given, strategies as st
from src.learning.skill_mastery_tracker import SkillMasteryTracker

class TestBayesianUpdate:
    """Verify Bayesian mastery update formula."""

    @given(
        prior=st.floats(min_value=0.0, max_value=1.0),
        confidence=st.integers(min_value=1, max_value=5),
        weight=st.floats(min_value=0.0, max_value=1.0)
    )
    def test_correct_answer_increases_mastery(self, prior, confidence, weight):
        """Property: Correct answer must increase mastery."""
        tracker = SkillMasteryTracker(mock_db)
        new_mastery = tracker._bayesian_update(
            prior_mastery=prior,
            is_correct=True,
            weight=weight,
            confidence=confidence
        )
        assert new_mastery >= prior
        assert 0.0 <= new_mastery <= 1.0

    def test_hypercorrection_effect(self):
        """High confidence + wrong = larger penalty (hypercorrection)."""
        prior = 0.7

        low_conf_result = tracker._bayesian_update(
            prior, is_correct=False, weight=1.0, confidence=2
        )
        high_conf_result = tracker._bayesian_update(
            prior, is_correct=False, weight=1.0, confidence=5
        )

        # High confidence wrong should have bigger drop
        assert (prior - high_conf_result) > (prior - low_conf_result)
```

**Key Unit Test Scenarios:**

- **Mastery Updates**: Bayesian formula correctness, boundary conditions, hypercorrection
- **FSRS Parameters**: Stability growth, retrievability decay, difficulty adjustment
- **Atom Grading**: Each atom type's grading logic (exact match, fuzzy, unit tests, rubric)
- **Misconception Mapping**: Distractor selection triggers correct misconception ID
- **Z-Score Ranking**: Skill gap targeting prioritizes weakest skills

### Integration Tests (Cognitive Workflows)

**Target:** Multi-component interactions (SessionManager + SkillTracker + AtomSelector).

**Framework:** pytest-asyncio for async workflows.

**Coverage Target:** All critical paths (session start → atom selection → response → mastery update).

**Example Test Structure:**

```python
# tests/integration/test_adaptive_session.py

@pytest.mark.asyncio
async def test_skill_gap_session_flow():
    """
    Given: Learner has low mastery in "NET_OSI_LAYERS" (0.3)
    When: Start adaptive session for networking module
    Then:
      - First atom targets NET_OSI_LAYERS
      - Difficulty is mastery + 0.1 (0.4)
      - After correct answer, mastery increases
      - Next atom adjusts to new mastery level
    """
    # Setup
    db = await create_test_db()
    await seed_skills(db)
    await set_learner_mastery(db, learner_id="test", skill="NET_OSI_LAYERS", mastery=0.3)

    tracker = SkillMasteryTracker(db)
    selector = SkillBasedAtomSelector(db, tracker)
    session = SessionManager(db, tracker, selector, learner_id="test")

    # Act
    first_atom = await session.next_atom(module_id="networking-101")

    # Assert
    assert "NET_OSI_LAYERS" in first_atom.primary_skills
    assert 0.35 <= first_atom.difficulty <= 0.45  # mastery 0.3 + 0.1 ± 0.05

    # Simulate correct answer
    await session.process_response(
        atom_id=first_atom.id,
        is_correct=True,
        latency_ms=3000,
        confidence=4
    )

    # Verify mastery increased
    new_state = await tracker._get_skill_mastery("test", first_atom.skill_ids[0])
    assert new_state.mastery_level > 0.3

    # Verify next atom adapts
    second_atom = await session.next_atom(module_id="networking-101")
    assert second_atom.difficulty > first_atom.difficulty  # Harder now
```

**Key Integration Test Scenarios:**

- **Session Orchestration**: Goal → Probe → Adaptive Core → Stress Test → Consolidation phases
- **Skill Tracking**: Response updates all linked skills with correct weights
- **Atom Selection**: Z-score ranking prioritizes skill gaps and appropriate difficulty
- **Greenlight Handoff**: Runtime atoms route to Greenlight, results return correctly
- **Retry Logic**: Failed Greenlight requests retry with exponential backoff

### Acceptance Tests (Cognitive Validity)

**Target:** End-to-end learning outcomes matching cognitive science research.

**Framework:** pytest with custom fixtures simulating learner cohorts.

**Coverage Target:** All cognitive subsystems (recall, procedural, diagnostic, generative).

**Example Test Structure:**

```python
# tests/acceptance/test_spaced_repetition.py

@pytest.mark.slow
async def test_fsrs_spacing_effect():
    """
    Given: Learner reviews atom at stability=5 days
    When: 4 days pass (before stability threshold)
    Then: Retrievability should be high (>0.85)

    When: 10 days pass (beyond stability)
    Then: Retrievability drops below 0.70
    """
    atom = create_test_atom(difficulty=0.5)

    # Initial review
    await session.review_atom(atom, is_correct=True)
    state = await get_fsrs_state(atom.id)
    assert state.stability == pytest.approx(5.0, abs=1.0)

    # Check retrievability at day 4
    advance_time(days=4)
    r_day4 = calculate_retrievability(state.stability, days_since=4)
    assert r_day4 >= 0.85  # Still above 90% recall threshold

    # Check retrievability at day 10
    advance_time(days=6)  # Total 10 days
    r_day10 = calculate_retrievability(state.stability, days_since=10)
    assert r_day10 < 0.70  # Significantly decayed
```

**Key Acceptance Test Scenarios:**

- **Spaced Repetition**: FSRS decay curves match research (Ebbinghaus forgetting curve)
- **Transfer Testing**: High mastery on practice atoms → success on novel scenarios
- **Misconception Remediation**: Triggering misconception → remedial atoms → re-test success
- **Cognitive Load Management**: Reducing difficulty when latency indicates overload
- **False Mastery Detection**: High quiz scores but low transfer scores trigger diagnostic

## Test Data Management

### Fixtures and Factories

Use pytest fixtures for reusable test data:

```python
# conftest.py

@pytest.fixture
async def test_db():
    """PostgreSQL test database with schema applied."""
    db = await create_database("test_cortex")
    await run_migrations(db)
    yield db
    await drop_database("test_cortex")

@pytest.fixture
def skill_factory():
    """Factory for creating test skills."""
    def _make_skill(skill_code, domain, mastery=0.5):
        return Skill(
            skill_code=skill_code,
            name=f"Test {skill_code}",
            domain=domain,
            cognitive_level="apply"
        )
    return _make_skill

@pytest.fixture
def atom_factory():
    """Factory for creating test atoms."""
    def _make_atom(atom_type, difficulty=0.5, skills=None):
        return Atom(
            atom_type=atom_type,
            content={"prompt": "Test prompt"},
            grading_logic={"correct": "answer"},
            difficulty=difficulty,
            skills=skills or []
        )
    return _make_atom
```

### Seed Data

Maintain canonical test datasets:

- `tests/fixtures/skills_seed.sql`: 30 skills across 3 domains
- `tests/fixtures/atoms_seed.sql`: 100 atoms covering all types
- `tests/fixtures/misconceptions_seed.sql`: 50 common errors

## Behavior-Driven Scenarios

### Scenario Template (Given/When/Then)

```gherkin
# features/adaptive_difficulty.feature

Feature: Adaptive Difficulty Adjustment
  As a learning system
  I want to adjust atom difficulty based on mastery
  So that learners stay in the Zone of Proximal Development

  Scenario: Struggling learner gets easier atoms
    Given learner has mastery 0.3 in "IP Addressing"
    And last 3 atoms were incorrect
    When selecting next atom
    Then atom difficulty should be 0.2 (mastery - 0.1)
    And cognitive load should be reduced

  Scenario: Mastering learner gets harder atoms
    Given learner has mastery 0.8 in "Routing Protocols"
    And last 3 atoms were correct with high confidence
    When selecting next atom
    Then atom difficulty should be 0.9 (mastery + 0.1)
    And atom should test transfer (novel scenario)
```

### Implementation

```python
# tests/bdd/test_adaptive_difficulty.py

from pytest_bdd import scenarios, given, when, then, parsers

scenarios('features/adaptive_difficulty.feature')

@given(parsers.parse('learner has mastery {mastery:f} in "{skill}"'))
def set_learner_mastery(test_db, mastery, skill):
    # Implementation
    pass

@when('selecting next atom')
def select_atom(context):
    context.atom = selector.select_atoms_by_skill_gap(...)

@then(parsers.parse('atom difficulty should be {difficulty:f}'))
def verify_difficulty(context, difficulty):
    assert context.atom.difficulty == pytest.approx(difficulty, abs=0.1)
```

## Continuous Integration Checks

See [ci-cd-pipeline](ci-cd-pipeline.md) for full pipeline specification.

**Pre-Merge Requirements:**

- All unit tests pass (85% coverage minimum)
- Integration tests for modified components pass
- Linting: ruff, mypy (strict mode)
- Migration validation (PostgreSQL)
- No security vulnerabilities (bandit scan)

**Acceptance Tests:**

- Run nightly, not on every PR (too slow)
- Track regression against baseline cohort performance

## Psychometric Validation

### Item Analysis

Every 100 learner responses to an atom, calculate:

- **p-value (difficulty)**: Proportion who get it correct
  - Target: 0.40 - 0.80 (not too easy/hard)
- **Discrimination index**: Point-biserial correlation with total score
  - Target: > 0.30 (distinguishes high/low performers)
- **Distractor effectiveness**: Each wrong answer selected 10-30% of the time
  - Red flag: < 5% (implausible distractor)

### Test Implementation

```python
# tests/psychometric/test_item_analysis.py

def test_atom_difficulty_range():
    """All atoms should have p-value in valid range."""
    atoms = get_atoms_with_100plus_responses()

    for atom in atoms:
        p_value = calculate_p_value(atom)
        assert 0.40 <= p_value <= 0.80, \
            f"Atom {atom.id} p-value {p_value} outside valid range"

def test_distractor_plausibility():
    """All MCQ distractors should attract some responses."""
    mcq_atoms = get_mcq_atoms_with_100plus_responses()

    for atom in mcq_atoms:
        for distractor in atom.distractors:
            selection_rate = calculate_selection_rate(distractor)
            assert selection_rate >= 0.05, \
                f"Distractor '{distractor.text}' too implausible ({selection_rate})"
```

## Test Organization

```
tests/
├── unit/
│   ├── test_bayesian_mastery.py
│   ├── test_fsrs_parameters.py
│   ├── test_atom_grading.py
│   └── atoms/
│       ├── test_mcq_handler.py
│       ├── test_parsons_handler.py
│       └── test_cloze_handler.py
├── integration/
│   ├── test_adaptive_session.py
│   ├── test_skill_tracking.py
│   ├── test_atom_selection.py
│   └── test_greenlight_handoff.py
├── acceptance/
│   ├── test_spaced_repetition.py
│   ├── test_transfer_learning.py
│   └── test_misconception_remediation.py
├── bdd/
│   └── features/
│       ├── adaptive_difficulty.feature
│       ├── skill_mastery.feature
│       └── session_orchestration.feature
├── psychometric/
│   ├── test_item_analysis.py
│   └── test_cohort_performance.py
├── fixtures/
│   ├── skills_seed.sql
│   ├── atoms_seed.sql
│   └── misconceptions_seed.sql
└── conftest.py
```

## Related Documentation

- [CI/CD Pipeline](ci-cd-pipeline.md): Automated test execution
- [Atom Type Taxonomy](atom-type-taxonomy.md): Full list of atom types to test
- [Transfer Testing](transfer-testing.md): Validation of learning transfer

## References

- **Cognitive Load Theory** (Sweller): Informs scaffolding tests
- **Item Response Theory** (Rasch): Informs p-value and discrimination tests
- **Bayesian Knowledge Tracing**: Informs mastery update tests
- **FSRS Algorithm**: Informs spaced repetition tests
