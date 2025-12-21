"""
Unit tests for Cortex atom handlers.

Tests the check() and hint() methods of each handler.
"""

import pytest
from src.cortex.atoms import AtomType, HANDLERS, get_handler
from src.cortex.atoms.base import AnswerResult


class TestHandlerRegistry:
    """Test the handler registry."""

    def test_all_handlers_registered(self):
        """All 22 atom types should have handlers (7 original + 5 batch 3a + 5 batch 3b + 5 batch 3c)."""
        assert len(HANDLERS) == 22

    def test_get_handler_by_string(self):
        """Should get handler by string type name."""
        handler = get_handler("mcq")
        assert handler is not None

    def test_get_handler_by_enum(self):
        """Should get handler by AtomType enum."""
        handler = get_handler(AtomType.MCQ)
        assert handler is not None

    def test_get_handler_invalid_type(self):
        """Should return None for invalid type."""
        handler = get_handler("invalid_type")
        assert handler is None


class TestMCQHandler:
    """Test the MCQ handler."""

    @pytest.fixture
    def handler(self):
        return get_handler(AtomType.MCQ)

    @pytest.fixture
    def sample_atom(self):
        return {
            "front": "What is the default subnet mask for a Class C network?",
            "options": [
                {"text": "255.0.0.0", "correct": False},
                {"text": "255.255.0.0", "correct": False},
                {"text": "255.255.255.0", "correct": True},
                {"text": "255.255.255.255", "correct": False},
            ],
            "_shuffled_options": [
                {"text": "255.0.0.0", "correct": False},
                {"text": "255.255.0.0", "correct": False},
                {"text": "255.255.255.0", "correct": True},
                {"text": "255.255.255.255", "correct": False},
            ],
        }

    def test_check_correct_answer(self, handler, sample_atom):
        """Should mark correct answer as correct."""
        answer = {"choice": "3", "is_multi": False}
        result = handler.check(sample_atom, answer)

        assert result.correct is True
        assert "Correct" in result.feedback

    def test_check_incorrect_answer(self, handler, sample_atom):
        """Should mark incorrect answer as incorrect."""
        answer = {"choice": "1", "is_multi": False}
        result = handler.check(sample_atom, answer)

        assert result.correct is False
        assert "255.255.255.0" in result.correct_answer

    def test_hint_eliminates_option(self, handler, sample_atom):
        """First hint should eliminate a wrong option."""
        hint = handler.hint(sample_atom, attempt=1)

        assert hint is not None
        assert "NOT" in hint


class TestNumericHandler:
    """Test the numeric handler."""

    @pytest.fixture
    def handler(self):
        return get_handler(AtomType.NUMERIC)

    def test_check_exact_match(self, handler):
        """Should match exact numeric answers."""
        atom = {"back": "255"}
        result = handler.check(atom, {"answer": "255"})

        assert result.correct is True

    def test_check_ip_address(self, handler):
        """Should match IP addresses."""
        atom = {"back": "192.168.1.1"}
        result = handler.check(atom, {"answer": "192.168.1.1"})

        assert result.correct is True

    def test_check_binary_answer(self, handler):
        """Should normalize binary answers."""
        atom = {"back": "11111111", "numeric_answer": 255}
        result = handler.check(atom, {"answer": "0b11111111"})

        assert result.correct is True

    def test_hint_shows_formula(self, handler):
        """Should show formula hint for subnet questions."""
        atom = {"front": "How many hosts in a /24 subnet?"}
        hint = handler.hint(atom, attempt=1)

        assert hint is not None
        assert "2^" in hint or "Hosts" in hint


class TestTrueFalseHandler:
    """Test the True/False handler."""

    @pytest.fixture
    def handler(self):
        return get_handler(AtomType.TRUE_FALSE)

    def test_check_true_correct(self, handler):
        """Should accept 'True' for true questions."""
        atom = {"back": "True"}
        result = handler.check(atom, "True")

        assert result.correct is True

    def test_check_false_correct(self, handler):
        """Should accept 'False' for false questions."""
        atom = {"back": "False"}
        result = handler.check(atom, "False")

        assert result.correct is True

    def test_check_wrong_answer(self, handler):
        """Should reject wrong answer."""
        atom = {"back": "True"}
        result = handler.check(atom, "False")

        assert result.correct is False


class TestParsonsHandler:
    """Test the Parsons problem handler."""

    @pytest.fixture
    def handler(self):
        return get_handler(AtomType.PARSONS)

    @pytest.fixture
    def sample_atom(self):
        return {
            "front": "Order the OSI layers from bottom to top",
            "steps": ["Physical", "Data Link", "Network", "Transport"],
        }

    def test_check_correct_order(self, handler, sample_atom):
        """Should accept correct ordering."""
        answer = {
            "user_order": ["Physical", "Data Link", "Network", "Transport"],
            "correct_order": ["Physical", "Data Link", "Network", "Transport"],
            "user_input": "1 2 3 4",
        }
        result = handler.check(sample_atom, answer)

        assert result.correct is True
        assert result.partial_score == 1.0

    def test_check_partial_credit(self, handler, sample_atom):
        """Should give partial credit for partial correct."""
        answer = {
            "user_order": ["Physical", "Network", "Data Link", "Transport"],
            "correct_order": ["Physical", "Data Link", "Network", "Transport"],
            "user_input": "1 3 2 4",
        }
        result = handler.check(sample_atom, answer)

        assert result.correct is False
        assert 0 < result.partial_score < 1.0

    def test_hint_shows_first_step(self, handler, sample_atom):
        """First hint should show first step."""
        hint = handler.hint(sample_atom, attempt=1)

        assert hint is not None
        assert "Physical" in hint or "first" in hint.lower()


class TestClozeHandler:
    """Test the cloze deletion handler."""

    @pytest.fixture
    def handler(self):
        return get_handler(AtomType.CLOZE)

    def test_check_correct_answer(self, handler):
        """Should accept correct cloze answer."""
        atom = {
            "front": "The {{c1::router}} forwards packets between networks",
            "back": "router",
        }
        result = handler.check(atom, {"answer": "router"})

        assert result.correct is True

    def test_check_case_insensitive(self, handler):
        """Should match case-insensitively."""
        atom = {"front": "The {{c1::Router}} forwards packets", "back": "Router"}
        result = handler.check(atom, {"answer": "router"})

        assert result.correct is True

    def test_hint_shows_first_letter(self, handler):
        """First hint should show first letter."""
        atom = {"front": "The {{c1::router}} forwards packets", "back": "router"}
        hint = handler.hint(atom, attempt=1)

        assert hint is not None
        assert "r" in hint.lower()


class TestFlashcardHandler:
    """Test the flashcard handler."""

    @pytest.fixture
    def handler(self):
        return get_handler(AtomType.FLASHCARD)

    def test_check_self_reported_correct(self, handler):
        """Should accept self-reported correct."""
        atom = {"front": "Q", "back": "A"}
        result = handler.check(atom, True)

        assert result.correct is True

    def test_check_self_reported_incorrect(self, handler):
        """Should accept self-reported incorrect."""
        atom = {"front": "Q", "back": "A"}
        result = handler.check(atom, False)

        assert result.correct is False

    def test_no_hints_for_flashcards(self, handler):
        """Flashcards should not have hints (pure recall)."""
        atom = {"front": "Q", "back": "A"}
        hint = handler.hint(atom, attempt=1)

        assert hint is None


class TestMatchingHandler:
    """Test the matching handler."""

    @pytest.fixture
    def handler(self):
        return get_handler(AtomType.MATCHING)

    def test_check_skipped(self, handler):
        """Should handle skipped questions."""
        atom = {}
        result = handler.check(atom, {"skipped": True})

        assert result.correct is True
        assert "Skipped" in result.feedback


# =============================================================================
# Batch 3c: Metacognitive & Diagnostic Handlers
# =============================================================================


class TestConfidenceSliderHandler:
    """Test the confidence slider handler for calibration tracking."""

    @pytest.fixture
    def handler(self):
        return get_handler(AtomType.CONFIDENCE_SLIDER)

    @pytest.fixture
    def sample_atom(self):
        return {
            "front": "What is the default port for HTTPS?",
            "back": "443",
        }

    def test_validate_valid_atom(self, handler, sample_atom):
        """Should validate atom with front and back."""
        assert handler.validate(sample_atom) is True

    def test_validate_invalid_atom(self, handler):
        """Should reject atom without required fields."""
        assert handler.validate({}) is False
        assert handler.validate({"front": "Q"}) is False

    def test_check_correct_with_high_confidence(self, handler, sample_atom):
        """Should report good calibration for correct answer with high confidence."""
        answer = {"answer": "443", "confidence": 90}
        result = handler.check(sample_atom, answer)

        assert result.correct is True
        assert "calibrat" in result.feedback.lower() or "Correct" in result.feedback

    def test_check_correct_with_low_confidence(self, handler, sample_atom):
        """Should report underconfidence for correct answer with low confidence."""
        answer = {"answer": "443", "confidence": 20}
        result = handler.check(sample_atom, answer)

        assert result.correct is True
        assert "80" in result.explanation  # Calibration error = |20 - 100| = 80

    def test_check_incorrect_with_high_confidence(self, handler, sample_atom):
        """Should report overconfidence for incorrect answer with high confidence."""
        answer = {"answer": "80", "confidence": 95}
        result = handler.check(sample_atom, answer)

        assert result.correct is False
        assert "Overconfident" in result.feedback or "95" in result.explanation

    def test_check_dont_know(self, handler, sample_atom):
        """Should handle don't know response."""
        answer = {"dont_know": True, "confidence": 50}
        result = handler.check(sample_atom, answer)

        assert result.correct is False
        assert result.dont_know is True

    def test_hint_first_attempt(self, handler, sample_atom):
        """Should provide first letter hint."""
        hint = handler.hint(sample_atom, attempt=1)

        assert hint is not None
        assert "4" in hint  # First character of "443"


class TestEffortRatingHandler:
    """Test the effort rating handler for cognitive load tracking."""

    @pytest.fixture
    def handler(self):
        return get_handler(AtomType.EFFORT_RATING)

    @pytest.fixture
    def sample_atom(self):
        return {
            "front": "What protocol operates at Layer 4?",
            "back": "TCP",
        }

    def test_validate_valid_atom(self, handler, sample_atom):
        """Should validate atom with front and back."""
        assert handler.validate(sample_atom) is True

    def test_check_correct_with_effort(self, handler, sample_atom):
        """Should record effort level with correct answer."""
        answer = {"answer": "tcp", "effort": 2}
        result = handler.check(sample_atom, answer)

        assert result.correct is True
        assert "2/5" in result.feedback or "2/5" in result.explanation

    def test_check_incorrect_with_high_effort(self, handler, sample_atom):
        """Should record high effort for difficult incorrect answer."""
        answer = {"answer": "UDP", "effort": 5}
        result = handler.check(sample_atom, answer)

        assert result.correct is False
        assert "5/5" in result.feedback or "5/5" in result.explanation

    def test_check_dont_know_max_effort(self, handler, sample_atom):
        """Should record max effort for don't know."""
        answer = {"dont_know": True, "effort": 5}
        result = handler.check(sample_atom, answer)

        assert result.correct is False
        assert result.dont_know is True


class TestCategorizationHandler:
    """Test the categorization handler for bucket sorting."""

    @pytest.fixture
    def handler(self):
        return get_handler(AtomType.CATEGORIZATION)

    @pytest.fixture
    def sample_atom(self):
        import json

        return {
            "front": "Sort these into OSI layers",
            "back": json.dumps({
                "categories": {
                    "Physical": ["Cable", "Hub"],
                    "Network": ["IP", "Router"],
                },
                "items": ["Cable", "Hub", "IP", "Router"],
            }),
        }

    def test_validate_valid_atom(self, handler, sample_atom):
        """Should validate atom with categories and items."""
        assert handler.validate(sample_atom) is True

    def test_validate_invalid_atom(self, handler):
        """Should reject atom without categories."""
        assert handler.validate({}) is False
        assert handler.validate({"back": "{}"}) is False

    def test_check_correct_categorization(self, handler, sample_atom):
        """Should accept correct categorization."""
        sample_atom["_categories"] = {
            "Physical": ["Cable", "Hub"],
            "Network": ["IP", "Router"],
        }
        sample_atom["_items"] = ["Cable", "Hub", "IP", "Router"]

        answer = {
            "mapping": {
                "Physical": ["Cable", "Hub"],
                "Network": ["IP", "Router"],
            },
        }
        result = handler.check(sample_atom, answer)

        assert result.correct is True
        assert result.partial_score == 1.0

    def test_check_partial_categorization(self, handler, sample_atom):
        """Should give partial credit for partial correct."""
        sample_atom["_categories"] = {
            "Physical": ["Cable", "Hub"],
            "Network": ["IP", "Router"],
        }
        sample_atom["_items"] = ["Cable", "Hub", "IP", "Router"]

        answer = {
            "mapping": {
                "Physical": ["Cable"],  # Missing Hub
                "Network": ["IP", "Router", "Hub"],  # Hub misplaced
            },
        }
        result = handler.check(sample_atom, answer)

        assert result.correct is False
        assert 0 < result.partial_score < 1.0

    def test_check_dont_know(self, handler, sample_atom):
        """Should handle don't know response."""
        result = handler.check(sample_atom, {"dont_know": True})

        assert result.correct is False
        assert result.dont_know is True


class TestScriptConcordanceTestHandler:
    """Test the SCT handler for diagnostic reasoning."""

    @pytest.fixture
    def handler(self):
        return get_handler(AtomType.SCRIPT_CONCORDANCE_TEST)

    @pytest.fixture
    def sample_atom(self):
        import json

        return {
            "front": "Diagnostic reasoning test",
            "back": json.dumps({
                "scenario": "Network has intermittent connectivity",
                "hypothesis": "Spanning tree loop",
                "new_info": "MAC table shows port flapping",
                "expert_consensus": 2,
                "expert_distribution": {"-2": 0, "-1": 0, "0": 1, "1": 2, "2": 7},
            }),
        }

    def test_validate_valid_atom(self, handler, sample_atom):
        """Should validate atom with SCT data."""
        assert handler.validate(sample_atom) is True

    def test_validate_invalid_atom(self, handler):
        """Should reject atom without SCT data."""
        assert handler.validate({}) is False
        assert handler.validate({"back": "{}"}) is False

    def test_check_expert_match(self, handler, sample_atom):
        """Should score high for matching expert consensus."""
        sample_atom["_sct_data"] = {
            "scenario": "Network has intermittent connectivity",
            "hypothesis": "Spanning tree loop",
            "new_info": "MAC table shows port flapping",
            "expert_consensus": 2,
            "expert_distribution": {"-2": 0, "-1": 0, "0": 1, "1": 2, "2": 7},
        }

        answer = {"response": 2}
        result = handler.check(sample_atom, answer)

        assert result.correct is True
        assert result.partial_score == 0.7  # 7/10 experts

    def test_check_close_to_consensus(self, handler, sample_atom):
        """Should accept response within 1 of consensus."""
        sample_atom["_sct_data"] = {
            "scenario": "Test",
            "hypothesis": "Test",
            "new_info": "Test",
            "expert_consensus": 2,
            "expert_distribution": {"-2": 0, "-1": 0, "0": 1, "1": 2, "2": 7},
        }

        answer = {"response": 1}
        result = handler.check(sample_atom, answer)

        assert result.correct is True  # Within 1 of consensus
        assert result.partial_score == 0.2  # 2/10 experts said +1

    def test_check_far_from_consensus(self, handler, sample_atom):
        """Should reject response far from consensus."""
        sample_atom["_sct_data"] = {
            "scenario": "Test",
            "hypothesis": "Test",
            "new_info": "Test",
            "expert_consensus": 2,
            "expert_distribution": {"-2": 0, "-1": 0, "0": 1, "1": 2, "2": 7},
        }

        answer = {"response": -2}
        result = handler.check(sample_atom, answer)

        assert result.correct is False
        assert result.partial_score == 0.0  # 0/10 experts said -2

    def test_hint_reveals_direction(self, handler, sample_atom):
        """Second hint should reveal direction."""
        sample_atom["_sct_data"] = {
            "scenario": "Test",
            "hypothesis": "Test",
            "new_info": "Test",
            "expert_consensus": 2,
        }

        hint = handler.hint(sample_atom, attempt=2)

        assert hint is not None
        assert "more likely" in hint.lower()


class TestKeyFeatureProblemHandler:
    """Test the KFP handler for critical step selection."""

    @pytest.fixture
    def handler(self):
        return get_handler(AtomType.KEY_FEATURE_PROBLEM)

    @pytest.fixture
    def sample_atom(self):
        import json

        return {
            "front": "Network outage - select critical steps",
            "back": json.dumps({
                "scenario": "Network outage affecting 500 users",
                "options": [
                    "Check cable connections",
                    "Restart all switches",
                    "Verify power to network closet",
                    "Update firmware",
                    "Check spanning tree logs",
                ],
                "key_features": [0, 2, 4],  # Cable, Power, Spanning tree
                "required_count": 3,
                "explanation": "Physical layer first, then L2 diagnostics",
            }),
        }

    def test_validate_valid_atom(self, handler, sample_atom):
        """Should validate atom with KFP data."""
        assert handler.validate(sample_atom) is True

    def test_validate_invalid_atom(self, handler):
        """Should reject atom without KFP data."""
        assert handler.validate({}) is False
        assert handler.validate({"back": "{}"}) is False

    def test_check_all_correct(self, handler, sample_atom):
        """Should accept all correct key features."""
        sample_atom["_kfp_data"] = {
            "options": [
                "Check cable connections",
                "Restart all switches",
                "Verify power to network closet",
                "Update firmware",
                "Check spanning tree logs",
            ],
            "key_features": [0, 2, 4],
            "required_count": 3,
        }

        answer = {"selections": [0, 2, 4]}
        result = handler.check(sample_atom, answer)

        assert result.correct is True
        assert result.partial_score == 1.0

    def test_check_partial_correct(self, handler, sample_atom):
        """Should give partial credit for some correct."""
        sample_atom["_kfp_data"] = {
            "options": [
                "Check cable connections",
                "Restart all switches",
                "Verify power to network closet",
                "Update firmware",
                "Check spanning tree logs",
            ],
            "key_features": [0, 2, 4],
            "required_count": 3,
        }

        answer = {"selections": [0, 1, 2]}  # 2 of 3 correct (0, 2)
        result = handler.check(sample_atom, answer)

        assert result.correct is False
        assert result.partial_score == pytest.approx(2 / 3, rel=0.01)

    def test_check_none_correct(self, handler, sample_atom):
        """Should give zero score for all wrong."""
        sample_atom["_kfp_data"] = {
            "options": [
                "Check cable connections",
                "Restart all switches",
                "Verify power to network closet",
                "Update firmware",
                "Check spanning tree logs",
            ],
            "key_features": [0, 2, 4],
            "required_count": 3,
        }

        answer = {"selections": [1, 3, 1]}  # None are key features
        result = handler.check(sample_atom, answer)

        assert result.correct is False
        assert result.partial_score == 0.0

    def test_hint_reveals_one(self, handler, sample_atom):
        """First hint should reveal one key feature."""
        sample_atom["_kfp_data"] = {
            "options": [
                "Check cable connections",
                "Restart all switches",
                "Verify power to network closet",
            ],
            "key_features": [0, 2],
            "required_count": 2,
        }

        hint = handler.hint(sample_atom, attempt=1)

        assert hint is not None
        assert "Check cable connections" in hint
