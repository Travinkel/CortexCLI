"""
Unit tests for the Faded Parsons handler.

Tests ordering + blank filling with partial credit.
"""

import pytest
from src.cortex.atoms.faded_parsons import FadedParsonsHandler


class TestFadedParsonsHandler:
    """Test the faded Parsons problem handler."""

    @pytest.fixture
    def handler(self):
        return FadedParsonsHandler()

    @pytest.fixture
    def sample_atom(self):
        return {
            "front": "Configure OSPF on a Cisco router",
            "lines": [
                "configure terminal",
                "___ ospf 1",
                "network 10.1.1.0 0.0.0.255 ___",
            ],
            "blanks": {"1": "router", "2": "area 0"},
        }

    def test_validate_valid_atom(self, handler, sample_atom):
        """Should validate atom with lines and blanks."""
        assert handler.validate(sample_atom) is True

    def test_validate_missing_lines(self, handler):
        """Should reject atom without lines."""
        atom = {"blanks": {"1": "router"}}
        assert handler.validate(atom) is False

    def test_validate_insufficient_lines(self, handler):
        """Should reject atom with less than 2 lines."""
        atom = {"lines": ["single line"], "blanks": {"1": "answer"}}
        assert handler.validate(atom) is False

    def test_validate_missing_blanks(self, handler):
        """Should reject atom without blanks."""
        atom = {"lines": ["line 1", "line 2"]}
        assert handler.validate(atom) is False

    def test_check_all_correct(self, handler, sample_atom):
        """Should return full credit when order and blanks are correct."""
        answer = {
            "user_order": [
                "configure terminal",
                "___ ospf 1",
                "network 10.1.1.0 0.0.0.255 ___",
            ],
            "correct_order": [
                "configure terminal",
                "___ ospf 1",
                "network 10.1.1.0 0.0.0.255 ___",
            ],
            "user_blanks": {"1": "router", "2": "area 0"},
            "correct_blanks": {"1": "router", "2": "area 0"},
            "user_input": "1 2 3",
        }
        result = handler.check(sample_atom, answer)

        assert result.correct is True
        assert result.partial_score == 1.0
        assert "Perfect" in result.feedback

    def test_check_order_correct_blanks_wrong(self, handler, sample_atom):
        """Should give partial credit for correct order but wrong blanks."""
        answer = {
            "user_order": [
                "configure terminal",
                "___ ospf 1",
                "network 10.1.1.0 0.0.0.255 ___",
            ],
            "correct_order": [
                "configure terminal",
                "___ ospf 1",
                "network 10.1.1.0 0.0.0.255 ___",
            ],
            "user_blanks": {"1": "wrong", "2": "wrong"},
            "correct_blanks": {"1": "router", "2": "area 0"},
            "user_input": "1 2 3",
        }
        result = handler.check(sample_atom, answer)

        assert result.correct is False
        # 60% for order + 0% for blanks = 0.6
        assert result.partial_score == pytest.approx(0.6, abs=0.01)

    def test_check_order_wrong_blanks_correct(self, handler, sample_atom):
        """Should give partial credit for wrong order but correct blanks."""
        answer = {
            "user_order": [
                "___ ospf 1",
                "configure terminal",
                "network 10.1.1.0 0.0.0.255 ___",
            ],
            "correct_order": [
                "configure terminal",
                "___ ospf 1",
                "network 10.1.1.0 0.0.0.255 ___",
            ],
            "user_blanks": {"1": "router", "2": "area 0"},
            "correct_blanks": {"1": "router", "2": "area 0"},
            "user_input": "2 1 3",
        }
        result = handler.check(sample_atom, answer)

        assert result.correct is False
        # Only last line in position (1/3 = 0.333 * 0.6) + 40% for blanks
        # = 0.2 + 0.4 = 0.6
        assert result.partial_score == pytest.approx(0.6, abs=0.01)

    def test_check_partial_order_partial_blanks(self, handler, sample_atom):
        """Should calculate combined partial credit."""
        answer = {
            "user_order": [
                "configure terminal",
                "network 10.1.1.0 0.0.0.255 ___",
                "___ ospf 1",
            ],
            "correct_order": [
                "configure terminal",
                "___ ospf 1",
                "network 10.1.1.0 0.0.0.255 ___",
            ],
            "user_blanks": {"1": "router", "2": "wrong"},
            "correct_blanks": {"1": "router", "2": "area 0"},
            "user_input": "1 3 2",
        }
        result = handler.check(sample_atom, answer)

        assert result.correct is False
        # Order: 1/3 correct = 0.333 * 0.6 = 0.2
        # Blanks: 1/2 correct = 0.5 * 0.4 = 0.2
        # Total = 0.4
        assert result.partial_score == pytest.approx(0.4, abs=0.05)

    def test_check_blanks_case_insensitive(self, handler, sample_atom):
        """Should match blanks case-insensitively."""
        answer = {
            "user_order": sample_atom["lines"],
            "correct_order": sample_atom["lines"],
            "user_blanks": {"1": "ROUTER", "2": "AREA 0"},
            "correct_blanks": {"1": "router", "2": "area 0"},
            "user_input": "1 2 3",
        }
        result = handler.check(sample_atom, answer)

        assert result.correct is True

    def test_check_skipped(self, handler, sample_atom):
        """Should handle skipped answers."""
        answer = {"skipped": True}
        result = handler.check(sample_atom, answer)

        assert result.correct is True
        assert "Skipped" in result.feedback

    def test_check_dont_know(self, handler, sample_atom):
        """Should handle 'I don't know' answers."""
        answer = {
            "dont_know": True,
            "correct_order": sample_atom["lines"],
            "blanks": sample_atom["blanks"],
        }
        result = handler.check(sample_atom, answer)

        assert result.correct is False
        assert result.dont_know is True
        assert "router" in result.correct_answer
        assert "area 0" in result.correct_answer

    def test_hint_first_attempt(self, handler, sample_atom):
        """First hint should show first line."""
        hint = handler.hint(sample_atom, attempt=1)

        assert hint is not None
        assert "configure terminal" in hint.lower() or "first" in hint.lower()

    def test_hint_second_attempt(self, handler, sample_atom):
        """Second hint should show last line."""
        hint = handler.hint(sample_atom, attempt=2)

        assert hint is not None
        assert "network" in hint.lower() or "last" in hint.lower()

    def test_hint_third_attempt(self, handler, sample_atom):
        """Third hint should give first letter of first blank."""
        hint = handler.hint(sample_atom, attempt=3)

        assert hint is not None
        assert "r" in hint.lower()  # First letter of "router"

    def test_hint_no_more_hints(self, handler, sample_atom):
        """Should return None when hints exhausted."""
        hint = handler.hint(sample_atom, attempt=10)

        assert hint is None

    def test_mask_blanks(self, handler):
        """Should mask blank placeholders."""
        line = "The ___ command enables ___"
        masked = handler._mask_blanks(line)

        assert "___" in masked
        assert masked.count("___") >= 2

    def test_format_solution(self, handler, sample_atom):
        """Should format complete solution with blanks filled."""
        solution = handler._format_solution(
            sample_atom["lines"],
            sample_atom["blanks"]
        )

        assert "router" in solution
        assert "area 0" in solution
        assert "->" in solution
