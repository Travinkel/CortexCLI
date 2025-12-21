"""
Unit tests for the Distractor Parsons handler.

Tests ordering + distractor discarding with partial credit.
"""

import pytest
from src.cortex.atoms.distractor_parsons import DistractorParsonsHandler


class TestDistractorParsonsHandler:
    """Test the distractor Parsons problem handler."""

    @pytest.fixture
    def handler(self):
        return DistractorParsonsHandler()

    @pytest.fixture
    def sample_atom(self):
        return {
            "front": "Order the OSPF configuration steps (discard invalid commands)",
            "correct_lines": [
                "configure terminal",
                "router ospf 1",
                "network 10.1.1.0 0.0.0.255 area 0",
                "exit",
            ],
            "distractors": [
                "router rip",
                "enable secret cisco",
                "ip route 0.0.0.0 0.0.0.0 192.168.1.1",
            ],
        }

    def test_validate_valid_atom(self, handler, sample_atom):
        """Should validate atom with correct_lines and distractors."""
        assert handler.validate(sample_atom) is True

    def test_validate_missing_correct_lines(self, handler):
        """Should reject atom without correct_lines."""
        atom = {"distractors": ["fake line"]}
        assert handler.validate(atom) is False

    def test_validate_insufficient_correct_lines(self, handler):
        """Should reject atom with less than 2 correct lines."""
        atom = {"correct_lines": ["single line"], "distractors": ["fake"]}
        assert handler.validate(atom) is False

    def test_validate_missing_distractors(self, handler):
        """Should reject atom without distractors."""
        atom = {"correct_lines": ["line 1", "line 2"]}
        assert handler.validate(atom) is False

    def test_check_all_correct(self, handler, sample_atom):
        """Should return full credit when order is correct and all distractors discarded."""
        answer = {
            "user_order": [
                "configure terminal",
                "router ospf 1",
                "network 10.1.1.0 0.0.0.255 area 0",
                "exit",
            ],
            "correct_order": sample_atom["correct_lines"],
            "discarded_lines": [
                "router rip",
                "enable secret cisco",
                "ip route 0.0.0.0 0.0.0.0 192.168.1.1",
            ],
            "distractors": sample_atom["distractors"],
            "user_input": "1 2 3 4",
        }
        result = handler.check(sample_atom, answer)

        assert result.correct is True
        assert result.partial_score == 1.0
        assert "Perfect" in result.feedback

    def test_check_included_distractor(self, handler, sample_atom):
        """Should penalize for including a distractor in selection."""
        answer = {
            "user_order": [
                "configure terminal",
                "router rip",  # This is a distractor!
                "router ospf 1",
                "exit",
            ],
            "correct_order": sample_atom["correct_lines"],
            "discarded_lines": [
                "enable secret cisco",
                "ip route 0.0.0.0 0.0.0.0 192.168.1.1",
                "network 10.1.1.0 0.0.0.255 area 0",  # Wrongly discarded
            ],
            "distractors": sample_atom["distractors"],
            "user_input": "1 5 2 4",
        }
        result = handler.check(sample_atom, answer)

        assert result.correct is False
        assert "fake" in result.feedback.lower() or "Included" in result.feedback

    def test_check_discarded_valid_line(self, handler, sample_atom):
        """Should penalize for discarding a valid line."""
        answer = {
            "user_order": [
                "configure terminal",
                "router ospf 1",
                "exit",
            ],
            "correct_order": sample_atom["correct_lines"],
            "discarded_lines": [
                "router rip",
                "enable secret cisco",
                "ip route 0.0.0.0 0.0.0.0 192.168.1.1",
                "network 10.1.1.0 0.0.0.255 area 0",  # Wrongly discarded!
            ],
            "distractors": sample_atom["distractors"],
            "user_input": "1 2 4",
        }
        result = handler.check(sample_atom, answer)

        assert result.correct is False
        assert "Discarded" in result.feedback or result.partial_score < 1.0

    def test_check_wrong_order_correct_distractors(self, handler, sample_atom):
        """Should give partial credit for wrong order but correct distractor handling."""
        answer = {
            "user_order": [
                "router ospf 1",
                "configure terminal",
                "network 10.1.1.0 0.0.0.255 area 0",
                "exit",
            ],
            "correct_order": sample_atom["correct_lines"],
            "discarded_lines": sample_atom["distractors"],
            "distractors": sample_atom["distractors"],
            "user_input": "2 1 3 4",
        }
        result = handler.check(sample_atom, answer)

        assert result.correct is False
        # Partial credit: some order points + full distractor points
        assert result.partial_score > 0.4

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
            "correct_order": sample_atom["correct_lines"],
            "distractors": sample_atom["distractors"],
        }
        result = handler.check(sample_atom, answer)

        assert result.correct is False
        assert result.dont_know is True
        assert "router ospf" in result.correct_answer.lower()
        assert "Discard" in result.correct_answer

    def test_hint_first_attempt(self, handler, sample_atom):
        """First hint should show first correct line."""
        hint = handler.hint(sample_atom, attempt=1)

        assert hint is not None
        assert "configure terminal" in hint.lower()

    def test_hint_second_attempt(self, handler, sample_atom):
        """Second hint should show last correct line."""
        hint = handler.hint(sample_atom, attempt=2)

        assert hint is not None
        assert "exit" in hint.lower()

    def test_hint_third_attempt_reveals_distractor(self, handler, sample_atom):
        """Third hint should reveal one distractor."""
        hint = handler.hint(sample_atom, attempt=3)

        assert hint is not None
        assert "fake" in hint.lower() or "rip" in hint.lower()

    def test_hint_fourth_attempt_reveals_another_distractor(self, handler, sample_atom):
        """Fourth hint should reveal another distractor."""
        hint = handler.hint(sample_atom, attempt=4)

        assert hint is not None
        assert "enable secret" in hint.lower() or "fake" in hint.lower()

    def test_hint_no_more_hints(self, handler, sample_atom):
        """Should return None when hints exhausted."""
        hint = handler.hint(sample_atom, attempt=10)

        assert hint is None

    def test_partial_score_calculation(self, handler, sample_atom):
        """Should calculate correct partial score with mixed results."""
        # 2/4 in correct position + 2/3 distractors discarded
        answer = {
            "user_order": [
                "configure terminal",
                "network 10.1.1.0 0.0.0.255 area 0",
                "router ospf 1",
                "exit",
            ],
            "correct_order": sample_atom["correct_lines"],
            "discarded_lines": [
                "router rip",
                "enable secret cisco",
            ],
            "distractors": sample_atom["distractors"],
            "user_input": "1 3 2 4",
        }
        result = handler.check(sample_atom, answer)

        assert result.correct is False
        # 2/4 order = 0.5 * 0.6 = 0.3
        # 2/3 distractors = 0.666 * 0.4 = 0.266
        # Total ~= 0.566
        assert 0.4 < result.partial_score < 0.7
