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
        """All 12 atom types should have handlers (7 original + 5 batch 3a)."""
        assert len(HANDLERS) == 12

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
