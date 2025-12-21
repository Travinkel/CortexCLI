"""
Unit tests for SkillMasteryTracker.

Tests:
- Bayesian update formula
- Hypercorrection logic (high confidence + wrong = bigger penalty)
- FSRS parameter updates
- Confidence interval computation
"""

import math

import pytest

from src.learning.skill_mastery_tracker import (
    SkillMasteryState,
    SkillMasteryTracker,
    SkillUpdate,
)


class MockDB:
    """Mock database connection for testing."""

    def __init__(self):
        self.queries = []
        self.mock_data = {}

    async def fetch(self, query: str, *args):
        """Mock fetch method."""
        self.queries.append((query, args))
        return self.mock_data.get("fetch", [])

    async def fetchrow(self, query: str, *args):
        """Mock fetchrow method."""
        self.queries.append((query, args))
        return self.mock_data.get("fetchrow")

    async def execute(self, query: str, *args):
        """Mock execute method."""
        self.queries.append((query, args))
        return "EXECUTED"


@pytest.fixture
def mock_db():
    """Create mock database connection."""
    return MockDB()


@pytest.fixture
def tracker(mock_db):
    """Create SkillMasteryTracker instance with mock DB."""
    return SkillMasteryTracker(mock_db)


class TestBayesianUpdate:
    """Tests for Bayesian mastery update formula."""

    def test_correct_answer_increases_mastery(self, tracker):
        """Test that correct answers increase mastery."""
        result = tracker._bayesian_update(
            prior_mastery=0.5, is_correct=True, weight=1.0, confidence=4
        )

        # Expected: 0.5 + (1.0 * 0.8 * 0.1) = 0.58
        assert result == pytest.approx(0.58, rel=0.01)
        assert result > 0.5  # Mastery increased

    def test_incorrect_answer_decreases_mastery(self, tracker):
        """Test that incorrect answers decrease mastery."""
        result = tracker._bayesian_update(
            prior_mastery=0.7, is_correct=False, weight=1.0, confidence=3
        )

        # Expected: 0.7 - (1.0 * 1.0 * 0.15) = 0.55
        assert result == pytest.approx(0.55, rel=0.01)
        assert result < 0.7  # Mastery decreased

    def test_hypercorrection_high_confidence_wrong(self, tracker):
        """Test hypercorrection: high confidence + wrong = bigger penalty."""
        # High confidence (5/5) when wrong
        result_high_conf = tracker._bayesian_update(
            prior_mastery=0.7, is_correct=False, weight=1.0, confidence=5
        )

        # Low confidence (2/5) when wrong
        result_low_conf = tracker._bayesian_update(
            prior_mastery=0.7, is_correct=False, weight=1.0, confidence=2
        )

        # High confidence error should have bigger penalty
        assert result_high_conf < result_low_conf
        # High confidence uses 1.5x penalty factor
        # Expected: 0.7 - (1.0 * 1.5 * 0.15) = 0.475
        assert result_high_conf == pytest.approx(0.475, rel=0.01)

    def test_weight_affects_update_size(self, tracker):
        """Test that atom weight affects update magnitude."""
        # High weight atom (1.0)
        result_high_weight = tracker._bayesian_update(
            prior_mastery=0.5, is_correct=True, weight=1.0, confidence=5
        )

        # Low weight atom (0.3)
        result_low_weight = tracker._bayesian_update(
            prior_mastery=0.5, is_correct=True, weight=0.3, confidence=5
        )

        # High weight should cause bigger update
        assert (result_high_weight - 0.5) > (result_low_weight - 0.5)

    def test_confidence_affects_update_size(self, tracker):
        """Test that learner confidence affects update magnitude."""
        # High confidence (5/5)
        result_high_conf = tracker._bayesian_update(
            prior_mastery=0.5, is_correct=True, weight=1.0, confidence=5
        )

        # Low confidence (1/5)
        result_low_conf = tracker._bayesian_update(
            prior_mastery=0.5, is_correct=True, weight=1.0, confidence=1
        )

        # High confidence should cause bigger update
        assert (result_high_conf - 0.5) > (result_low_conf - 0.5)

    def test_mastery_bounds(self, tracker):
        """Test that mastery stays within [0, 1] bounds."""
        # Test upper bound
        result_max = tracker._bayesian_update(
            prior_mastery=0.95, is_correct=True, weight=1.0, confidence=5
        )
        assert result_max <= 1.0

        # Test lower bound
        result_min = tracker._bayesian_update(
            prior_mastery=0.05, is_correct=False, weight=1.0, confidence=5
        )
        assert result_min >= 0.0


class TestFSRSParameters:
    """Tests for FSRS parameter updates."""

    @pytest.mark.asyncio
    async def test_difficulty_decreases_on_correct(self, tracker):
        """Test that difficulty decreases with correct answers."""
        result = await tracker._update_fsrs_parameters(
            skill_id="skill-123",
            learner_id="learner-456",
            is_correct=True,
            latency_ms=3000,
            current_difficulty=0.5,
            current_stability=2.0,
        )

        assert result["difficulty"] < 0.5  # Difficulty decreased
        assert result["difficulty"] == pytest.approx(0.45, rel=0.01)

    @pytest.mark.asyncio
    async def test_difficulty_increases_on_incorrect(self, tracker):
        """Test that difficulty increases with incorrect answers."""
        result = await tracker._update_fsrs_parameters(
            skill_id="skill-123",
            learner_id="learner-456",
            is_correct=False,
            latency_ms=3000,
            current_difficulty=0.5,
            current_stability=2.0,
        )

        assert result["difficulty"] > 0.5  # Difficulty increased
        assert result["difficulty"] == pytest.approx(0.6, rel=0.01)

    @pytest.mark.asyncio
    async def test_stability_increases_on_correct(self, tracker):
        """Test that stability increases with correct answers."""
        result = await tracker._update_fsrs_parameters(
            skill_id="skill-123",
            learner_id="learner-456",
            is_correct=True,
            latency_ms=3000,
            current_stability=2.0,
            current_difficulty=0.5,
        )

        assert result["stability"] > 2.0  # Stability increased
        assert result["stability"] == pytest.approx(4.0, rel=0.01)  # Doubled

    @pytest.mark.asyncio
    async def test_stability_decreases_on_incorrect(self, tracker):
        """Test that stability resets on incorrect answers."""
        result = await tracker._update_fsrs_parameters(
            skill_id="skill-123",
            learner_id="learner-456",
            is_correct=False,
            latency_ms=3000,
            current_stability=4.0,
            current_difficulty=0.5,
        )

        assert result["stability"] < 4.0  # Stability decreased
        assert result["stability"] == pytest.approx(2.0, rel=0.01)  # Halved

    @pytest.mark.asyncio
    async def test_retrievability_correct_vs_incorrect(self, tracker):
        """Test retrievability differs for correct vs incorrect."""
        result_correct = await tracker._update_fsrs_parameters(
            skill_id="skill-123",
            learner_id="learner-456",
            is_correct=True,
            latency_ms=3000,
            current_stability=2.0,
            current_difficulty=0.5,
        )

        result_incorrect = await tracker._update_fsrs_parameters(
            skill_id="skill-123",
            learner_id="learner-456",
            is_correct=False,
            latency_ms=3000,
            current_stability=2.0,
            current_difficulty=0.5,
        )

        assert result_correct["retrievability"] > result_incorrect["retrievability"]
        assert result_correct["retrievability"] == 1.0
        assert result_incorrect["retrievability"] == 0.5


class TestConfidenceInterval:
    """Tests for confidence interval computation."""

    def test_confidence_narrows_with_practice(self, tracker):
        """Test that confidence interval narrows with more practice."""
        # First practice
        ci_1 = tracker._compute_confidence_interval(mastery=0.5, practice_count=1)

        # After 10 practices
        ci_10 = tracker._compute_confidence_interval(mastery=0.5, practice_count=10)

        # After 50 practices
        ci_50 = tracker._compute_confidence_interval(mastery=0.5, practice_count=50)

        # Confidence interval should narrow
        assert ci_1 > ci_10 > ci_50

    def test_confidence_minimum(self, tracker):
        """Test that confidence interval has minimum bound."""
        # Even with lots of practice, there's always some uncertainty
        ci_large = tracker._compute_confidence_interval(mastery=0.8, practice_count=1000)

        assert ci_large >= 0.05  # Minimum 5% uncertainty

    def test_confidence_formula(self, tracker):
        """Test confidence interval exponential decay formula."""
        practice_count = 10
        ci = tracker._compute_confidence_interval(mastery=0.5, practice_count=practice_count)

        # Expected: 0.5 * exp(-0.1 * 10) = 0.5 * exp(-1.0) ≈ 0.184
        expected = 0.5 * math.exp(-0.1 * practice_count)
        assert ci == pytest.approx(expected, rel=0.01)


class TestSkillMasteryState:
    """Tests for SkillMasteryState dataclass."""

    def test_skill_mastery_state_creation(self):
        """Test creating SkillMasteryState."""
        state = SkillMasteryState(
            skill_id="skill-123",
            skill_code="NET_IP_ADDRESSING",
            mastery_level=0.7,
            confidence_interval=0.15,
            practice_count=10,
            consecutive_correct=3,
            last_practiced=None,
            retrievability=0.85,
            difficulty=0.4,
            stability=5.0,
        )

        assert state.skill_code == "NET_IP_ADDRESSING"
        assert state.mastery_level == 0.7
        assert state.practice_count == 10


class TestSkillUpdate:
    """Tests for SkillUpdate dataclass."""

    def test_skill_update_creation(self):
        """Test creating SkillUpdate."""
        from datetime import datetime, timedelta

        update = SkillUpdate(
            skill_id="skill-123",
            skill_code="NET_IP_ADDRESSING",
            old_mastery=0.5,
            new_mastery=0.6,
            confidence_interval=0.2,
            retrievability=0.9,
            stability=3.0,
            next_review_date=datetime.now() + timedelta(days=3),
        )

        assert update.old_mastery == 0.5
        assert update.new_mastery == 0.6
        assert update.new_mastery > update.old_mastery  # Improvement


class TestEdgeCases:
    """Tests for edge cases and error conditions."""

    def test_zero_weight_atom(self, tracker):
        """Test atom with zero weight has no effect."""
        result = tracker._bayesian_update(
            prior_mastery=0.5, is_correct=True, weight=0.0, confidence=5
        )

        # No change with zero weight
        assert result == pytest.approx(0.5, rel=0.001)

    def test_minimum_confidence(self, tracker):
        """Test with minimum confidence (1/5)."""
        result = tracker._bayesian_update(
            prior_mastery=0.5, is_correct=True, weight=1.0, confidence=1
        )

        # Small update with low confidence
        assert result > 0.5
        assert result <= 0.52  # Changed to <= for boundary case

    def test_maximum_confidence(self, tracker):
        """Test with maximum confidence (5/5)."""
        result = tracker._bayesian_update(
            prior_mastery=0.5, is_correct=True, weight=1.0, confidence=5
        )

        # Larger update with high confidence
        assert result > 0.5
        assert result == pytest.approx(0.6, rel=0.01)
