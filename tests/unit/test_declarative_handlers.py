"""
Unit tests for Batch 3a: Declarative Memory Handlers.

Tests the validate(), check(), and hint() methods of each handler:
- cloze_dropdown
- short_answer_exact
- short_answer_regex
- list_recall
- ordered_list_recall
"""

import pytest
from src.cortex.atoms import AtomType, HANDLERS, get_handler
from src.cortex.atoms.base import AnswerResult


class TestClozeDropdownHandler:
    """Test the cloze dropdown handler."""

    @pytest.fixture
    def handler(self):
        return get_handler(AtomType.CLOZE_DROPDOWN)

    @pytest.fixture
    def sample_atom(self):
        return {
            "cloze_text": "The OSI model has {{c1::seven}} layers.",
            "options": ["five", "seven", "nine", "twelve"],
            "correct_answer": "seven",
        }

    def test_handler_registered(self, handler):
        """Handler should be registered."""
        assert handler is not None

    def test_validate_valid_atom(self, handler, sample_atom):
        """Should validate atom with cloze text, options, and correct answer."""
        assert handler.validate(sample_atom) is True

    def test_validate_missing_options(self, handler):
        """Should reject atom without options."""
        atom = {
            "cloze_text": "The OSI model has {{c1::seven}} layers.",
            "correct_answer": "seven",
        }
        assert handler.validate(atom) is False

    def test_validate_missing_blank(self, handler):
        """Should reject atom without blank marker."""
        atom = {
            "cloze_text": "The OSI model has seven layers.",
            "options": ["five", "seven", "nine"],
            "correct_answer": "seven",
        }
        assert handler.validate(atom) is False

    def test_check_correct_answer(self, handler, sample_atom):
        """Should mark correct selection as correct."""
        answer = {"selected": "seven", "choice": 2}
        result = handler.check(sample_atom, answer)

        assert result.correct is True
        assert "Correct" in result.feedback

    def test_check_incorrect_answer(self, handler, sample_atom):
        """Should mark incorrect selection as incorrect."""
        answer = {"selected": "five", "choice": 1}
        result = handler.check(sample_atom, answer)

        assert result.correct is False
        assert "seven" in result.correct_answer

    def test_check_dont_know(self, handler, sample_atom):
        """Should handle 'I don't know' response."""
        answer = {"dont_know": True}
        result = handler.check(sample_atom, answer)

        assert result.correct is False
        assert result.dont_know is True

    def test_hint_eliminates_option(self, handler, sample_atom):
        """First hint should eliminate a wrong option."""
        hint = handler.hint(sample_atom, attempt=1)

        assert hint is not None
        assert "NOT" in hint

    def test_hint_second_eliminates_another(self, handler, sample_atom):
        """Second hint should eliminate another wrong option."""
        hint = handler.hint(sample_atom, attempt=2)

        assert hint is not None
        assert "NOT" in hint or "also" in hint


class TestShortAnswerExactHandler:
    """Test the short answer exact match handler."""

    @pytest.fixture
    def handler(self):
        return get_handler(AtomType.SHORT_ANSWER_EXACT)

    @pytest.fixture
    def sample_atom(self):
        return {
            "front": "What is the default port for HTTP?",
            "back": "80",
        }

    def test_handler_registered(self, handler):
        """Handler should be registered."""
        assert handler is not None

    def test_validate_valid_atom(self, handler, sample_atom):
        """Should validate atom with question and answer."""
        assert handler.validate(sample_atom) is True

    def test_validate_missing_answer(self, handler):
        """Should reject atom without answer."""
        atom = {"front": "What is the default port for HTTP?"}
        assert handler.validate(atom) is False

    def test_check_exact_match(self, handler, sample_atom):
        """Should match exact answers."""
        result = handler.check(sample_atom, {"answer": "80"})

        assert result.correct is True

    def test_check_case_insensitive(self, handler):
        """Should match case-insensitively by default."""
        atom = {"front": "What protocol uses TCP?", "back": "HTTP"}
        result = handler.check(atom, {"answer": "http"})

        assert result.correct is True

    def test_check_case_sensitive_when_specified(self, handler):
        """Should respect case_sensitive flag."""
        atom = {"front": "What is the acronym?", "back": "HTTP", "case_sensitive": True}
        result = handler.check(atom, {"answer": "http"})

        assert result.correct is False

    def test_check_incorrect_answer(self, handler, sample_atom):
        """Should reject incorrect answers."""
        result = handler.check(sample_atom, {"answer": "443"})

        assert result.correct is False
        assert "80" in result.correct_answer

    def test_check_with_whitespace(self, handler, sample_atom):
        """Should strip whitespace before comparing."""
        result = handler.check(sample_atom, {"answer": "  80  "})

        assert result.correct is True

    def test_hint_first_letter(self, handler, sample_atom):
        """First hint should show first letter."""
        hint = handler.hint(sample_atom, attempt=1)

        assert hint is not None
        assert "8" in hint


class TestShortAnswerRegexHandler:
    """Test the short answer regex match handler."""

    @pytest.fixture
    def handler(self):
        return get_handler(AtomType.SHORT_ANSWER_REGEX)

    @pytest.fixture
    def sample_atom(self):
        return {
            "front": "What command enables OSPF on a router?",
            "pattern": r"router\s+ospf\s+\d+",
            "back": "router ospf 1",
        }

    def test_handler_registered(self, handler):
        """Handler should be registered."""
        assert handler is not None

    def test_validate_valid_atom(self, handler, sample_atom):
        """Should validate atom with pattern."""
        assert handler.validate(sample_atom) is True

    def test_validate_invalid_regex(self, handler):
        """Should reject atom with invalid regex pattern."""
        atom = {
            "front": "Test question",
            "pattern": r"[invalid(regex",  # Invalid regex
            "back": "answer",
        }
        assert handler.validate(atom) is False

    def test_check_regex_match(self, handler, sample_atom):
        """Should match valid regex patterns."""
        result = handler.check(sample_atom, {"answer": "router ospf 1"})
        assert result.correct is True

        result = handler.check(sample_atom, {"answer": "router  ospf  10"})
        assert result.correct is True

    def test_check_regex_no_match(self, handler, sample_atom):
        """Should reject non-matching answers."""
        result = handler.check(sample_atom, {"answer": "ospf router 1"})

        assert result.correct is False

    def test_check_case_insensitive(self, handler, sample_atom):
        """Should match case-insensitively by default."""
        result = handler.check(sample_atom, {"answer": "ROUTER OSPF 1"})

        assert result.correct is True

    def test_check_fallback_to_exact_match(self, handler):
        """Should fall back to exact match if no pattern."""
        atom = {"front": "Question", "back": "answer"}
        result = handler.check(atom, {"answer": "answer"})

        assert result.correct is True


class TestListRecallHandler:
    """Test the list recall handler (order-independent)."""

    @pytest.fixture
    def handler(self):
        return get_handler(AtomType.LIST_RECALL)

    @pytest.fixture
    def sample_atom(self):
        return {
            "front": "Name the 4 layers of the TCP/IP model",
            "correct": ["Application", "Transport", "Internet", "Network Access"],
        }

    def test_handler_registered(self, handler):
        """Handler should be registered."""
        assert handler is not None

    def test_validate_valid_atom(self, handler, sample_atom):
        """Should validate atom with prompt and correct list."""
        assert handler.validate(sample_atom) is True

    def test_validate_string_list(self, handler):
        """Should accept comma-separated string as correct list."""
        atom = {
            "front": "Name the layers",
            "correct": "Layer1, Layer2, Layer3",
        }
        assert handler.validate(atom) is True

    def test_check_all_correct_any_order(self, handler, sample_atom):
        """Should accept all items in any order."""
        answer = {"answers": ["Network Access", "Application", "Transport", "Internet"]}
        result = handler.check(sample_atom, answer)

        assert result.correct is True
        assert result.partial_score == 1.0

    def test_check_partial_credit(self, handler, sample_atom):
        """Should give partial credit for partial answers."""
        answer = {"answers": ["Application", "Transport"]}
        result = handler.check(sample_atom, answer)

        assert result.correct is False
        assert result.partial_score == 0.5  # 2 out of 4

    def test_check_missing_items(self, handler, sample_atom):
        """Should report missing items."""
        answer = {"answers": ["Application", "Transport"]}
        result = handler.check(sample_atom, answer)

        assert "Missing" in result.feedback

    def test_check_extra_items(self, handler, sample_atom):
        """Should report extra items."""
        answer = {"answers": ["Application", "Transport", "Internet", "Network Access", "Extra"]}
        result = handler.check(sample_atom, answer)

        assert result.correct is False
        assert "Extra" in result.feedback

    def test_check_case_insensitive(self, handler, sample_atom):
        """Should match case-insensitively."""
        answer = {"answers": ["application", "transport", "internet", "network access"]}
        result = handler.check(sample_atom, answer)

        assert result.correct is True

    def test_hint_shows_count(self, handler, sample_atom):
        """First hint should show remaining count."""
        hint = handler.hint(sample_atom, attempt=1, current_answers=[])

        assert hint is not None
        assert "4" in hint or "remaining" in hint


class TestOrderedListRecallHandler:
    """Test the ordered list recall handler (order-dependent)."""

    @pytest.fixture
    def handler(self):
        return get_handler(AtomType.ORDERED_LIST_RECALL)

    @pytest.fixture
    def sample_atom(self):
        return {
            "front": "List the OSI layers from bottom to top (first 4)",
            "correct": ["Physical", "Data Link", "Network", "Transport"],
        }

    def test_handler_registered(self, handler):
        """Handler should be registered."""
        assert handler is not None

    def test_validate_valid_atom(self, handler, sample_atom):
        """Should validate atom with prompt and correct sequence."""
        assert handler.validate(sample_atom) is True

    def test_validate_requires_multiple_items(self, handler):
        """Should require at least 2 items for ordered list."""
        atom = {"front": "Name one layer", "correct": ["Physical"]}
        assert handler.validate(atom) is False

    def test_check_correct_order(self, handler, sample_atom):
        """Should accept items in correct order."""
        answer = {"answers": ["Physical", "Data Link", "Network", "Transport"]}
        result = handler.check(sample_atom, answer)

        assert result.correct is True
        assert result.partial_score == 1.0

    def test_check_wrong_order(self, handler, sample_atom):
        """Should reject items in wrong order."""
        answer = {"answers": ["Data Link", "Physical", "Network", "Transport"]}
        result = handler.check(sample_atom, answer)

        assert result.correct is False
        assert result.partial_score == 0.5  # 2 out of 4 positions correct

    def test_check_partial_credit(self, handler, sample_atom):
        """Should give partial credit based on correct positions."""
        answer = {"answers": ["Physical", "Network", "Data Link", "Transport"]}
        result = handler.check(sample_atom, answer)

        assert result.correct is False
        # Physical (pos 0) and Transport (pos 3) are correct
        assert result.partial_score == 0.5

    def test_check_missing_items(self, handler, sample_atom):
        """Should handle incomplete answers."""
        answer = {"answers": ["Physical", "Data Link"]}
        result = handler.check(sample_atom, answer)

        assert result.correct is False
        assert result.partial_score == 0.5  # 2 out of 4

    def test_check_case_insensitive(self, handler, sample_atom):
        """Should match case-insensitively."""
        answer = {"answers": ["physical", "data link", "network", "transport"]}
        result = handler.check(sample_atom, answer)

        assert result.correct is True

    def test_hint_reveals_first(self, handler, sample_atom):
        """First hint should reveal first item."""
        hint = handler.hint(sample_atom, attempt=1)

        assert hint is not None
        assert "Physical" in hint

    def test_hint_reveals_last(self, handler, sample_atom):
        """Second hint should reveal last item."""
        hint = handler.hint(sample_atom, attempt=2)

        assert hint is not None
        assert "Transport" in hint


class TestHandlerRegistryWithNewHandlers:
    """Test that all new handlers are properly registered."""

    def test_all_new_handlers_registered(self):
        """All 5 new atom types should have handlers."""
        new_types = [
            AtomType.CLOZE_DROPDOWN,
            AtomType.SHORT_ANSWER_EXACT,
            AtomType.SHORT_ANSWER_REGEX,
            AtomType.LIST_RECALL,
            AtomType.ORDERED_LIST_RECALL,
        ]

        for atom_type in new_types:
            handler = get_handler(atom_type)
            assert handler is not None, f"Handler missing for {atom_type}"

    def test_get_handler_by_string(self):
        """Should get new handlers by string type name."""
        assert get_handler("cloze_dropdown") is not None
        assert get_handler("short_answer_exact") is not None
        assert get_handler("short_answer_regex") is not None
        assert get_handler("list_recall") is not None
        assert get_handler("ordered_list_recall") is not None

    def test_total_handler_count(self):
        """Should have 12 total handlers (7 original + 5 new)."""
        assert len(HANDLERS) == 12


# Additional edge case tests for better coverage

class TestClozeDropdownEdgeCases:
    """Additional edge case tests for cloze dropdown handler."""

    @pytest.fixture
    def handler(self):
        return get_handler(AtomType.CLOZE_DROPDOWN)

    def test_check_skipped(self, handler):
        """Should handle skipped questions."""
        atom = {"correct_answer": "test"}
        result = handler.check(atom, {"skipped": True})

        assert result.correct is True
        assert "Skipped" in result.feedback

    def test_check_string_answer(self, handler):
        """Should handle string answer directly."""
        atom = {"correct_answer": "seven", "options": ["five", "seven"]}
        result = handler.check(atom, "seven")

        assert result.correct is True

    def test_hint_third_attempt(self, handler):
        """Third hint should show first letter."""
        atom = {"correct_answer": "seven", "options": ["five", "seven", "nine", "twelve"]}
        hint = handler.hint(atom, attempt=3)

        assert hint is not None
        assert "S" in hint.upper()

    def test_hint_no_incorrect_options(self, handler):
        """Should handle case with few incorrect options."""
        atom = {"correct_answer": "yes", "options": ["yes"]}
        hint = handler.hint(atom, attempt=1)

        # No incorrect options to eliminate
        assert hint is None or "NOT" not in hint

    def test_validate_with_underscore_blank(self, handler):
        """Should validate atom with underscore blank marker."""
        atom = {
            "cloze_text": "The answer is ___.",
            "options": ["one", "two"],
            "correct_answer": "one",
        }
        assert handler.validate(atom) is True

    def test_format_blanks_with_underscores(self, handler):
        """Should format underscores as blanks."""
        text = "The answer is ___."
        result = handler._format_blanks(text)
        assert "[____]" in str(result)


class TestShortAnswerExactEdgeCases:
    """Additional edge case tests for short answer exact handler."""

    @pytest.fixture
    def handler(self):
        return get_handler(AtomType.SHORT_ANSWER_EXACT)

    def test_check_string_answer(self, handler):
        """Should handle string answer directly."""
        atom = {"back": "80"}
        result = handler.check(atom, "80")

        assert result.correct is True

    def test_hint_no_more_hints(self, handler):
        """Should return None for attempt > 3."""
        atom = {"back": "test"}
        hint = handler.hint(atom, attempt=4)

        assert hint is None

    def test_hint_short_answer(self, handler):
        """Should handle short answers in hints."""
        atom = {"back": "AB"}
        hint = handler.hint(atom, attempt=3)

        # Short answer, may not have first/last hint
        assert hint is None or "A" in hint or "B" in hint

    def test_check_with_question_field(self, handler):
        """Should use 'question' field if 'front' not present."""
        atom = {"question": "What is 1+1?", "correct_answer": "2"}
        result = handler.check(atom, {"answer": "2"})

        assert result.correct is True


class TestShortAnswerRegexEdgeCases:
    """Additional edge case tests for short answer regex handler."""

    @pytest.fixture
    def handler(self):
        return get_handler(AtomType.SHORT_ANSWER_REGEX)

    def test_check_string_answer(self, handler):
        """Should handle string answer directly."""
        atom = {"back": "test", "pattern": r"test"}
        result = handler.check(atom, "test")

        assert result.correct is True

    def test_check_case_sensitive(self, handler):
        """Should respect case_sensitive flag."""
        atom = {"pattern": r"TEST", "back": "TEST", "case_sensitive": True}
        result = handler.check(atom, {"answer": "test"})

        assert result.correct is False

    def test_validate_no_pattern_no_answer(self, handler):
        """Should reject atom without pattern or answer."""
        atom = {"front": "Question only"}
        assert handler.validate(atom) is False

    def test_validate_no_question(self, handler):
        """Should reject atom without question."""
        atom = {"pattern": r"test", "back": "test"}
        assert handler.validate(atom) is False

    def test_grade_invalid_regex_fallback(self, handler):
        """Should handle invalid regex in _grade method."""
        result = handler._grade("test", "[invalid", case_sensitive=False)
        # Falls back to exact match
        assert result is False


class TestListRecallEdgeCases:
    """Additional edge case tests for list recall handler."""

    @pytest.fixture
    def handler(self):
        return get_handler(AtomType.LIST_RECALL)

    def test_check_string_answer(self, handler):
        """Should handle comma-separated string answer."""
        atom = {"correct": ["A", "B", "C"]}
        result = handler.check(atom, "A, B, C")

        assert result.correct is True

    def test_check_empty_answers(self, handler):
        """Should handle empty answers list."""
        atom = {"correct": ["A", "B"]}
        result = handler.check(atom, {"answers": []})

        assert result.correct is False
        assert result.partial_score == 0.0

    def test_get_correct_list_from_back(self, handler):
        """Should extract list from back field."""
        atom = {"front": "Question", "back": "A, B, C"}
        correct = handler._get_correct_list(atom)

        assert correct == ["A", "B", "C"]

    def test_get_correct_list_empty(self, handler):
        """Should handle missing correct list."""
        atom = {"front": "Question"}
        correct = handler._get_correct_list(atom)

        assert correct == []

    def test_hint_all_recalled(self, handler):
        """Should indicate all items recalled."""
        atom = {"correct": ["A", "B"]}
        hint = handler.hint(atom, attempt=1, current_answers=["A", "B"])

        assert hint is not None
        assert "recalled" in hint.lower() or "all" in hint.lower()

    def test_hint_second_attempt(self, handler):
        """Second hint should show first letter of missing item."""
        atom = {"correct": ["Apple", "Banana"]}
        hint = handler.hint(atom, attempt=2, current_answers=[])

        assert hint is not None
        assert "A" in hint

    def test_hint_third_attempt(self, handler):
        """Third hint should show more details."""
        atom = {"correct": ["Apple", "Banana"]}
        hint = handler.hint(atom, attempt=3, current_answers=[])

        assert hint is not None

    def test_validate_with_items_field(self, handler):
        """Should accept 'items' field for correct list."""
        atom = {"front": "Question", "items": ["A", "B"]}
        assert handler.validate(atom) is True


class TestOrderedListRecallEdgeCases:
    """Additional edge case tests for ordered list recall handler."""

    @pytest.fixture
    def handler(self):
        return get_handler(AtomType.ORDERED_LIST_RECALL)

    def test_check_string_answer(self, handler):
        """Should handle comma-separated string answer."""
        atom = {"correct": ["A", "B", "C"]}
        result = handler.check(atom, "A, B, C")

        assert result.correct is True

    def test_check_empty_answers(self, handler):
        """Should handle empty answers list."""
        atom = {"correct": ["A", "B"]}
        result = handler.check(atom, {"answers": []})

        assert result.correct is False
        assert result.partial_score == 0.0

    def test_get_correct_list_from_sequence(self, handler):
        """Should extract list from sequence field."""
        atom = {"front": "Question", "sequence": ["A", "B", "C"]}
        correct = handler._get_correct_list(atom)

        assert correct == ["A", "B", "C"]

    def test_get_correct_list_empty(self, handler):
        """Should handle missing correct list."""
        atom = {"front": "Question"}
        correct = handler._get_correct_list(atom)

        assert correct == []

    def test_hint_third_attempt(self, handler):
        """Third hint should show next expected item."""
        atom = {"correct": ["A", "B", "C"]}
        hint = handler.hint(atom, attempt=3, current_position=1)

        assert hint is not None
        assert "B" in hint

    def test_grade_extra_items(self, handler):
        """Should handle more items than correct list."""
        result = handler._grade(["A", "B", "C", "D"], ["A", "B", "C"])

        # First 3 positions correct
        assert result["partial_score"] == 1.0
        assert result["is_correct"] is False  # Different length

    def test_validate_with_string_list(self, handler):
        """Should accept comma-separated string for correct."""
        atom = {"front": "Question", "correct": "A, B, C"}
        assert handler.validate(atom) is True
