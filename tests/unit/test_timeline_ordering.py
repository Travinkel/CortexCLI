"""
Unit tests for the Timeline Ordering handler.

Tests chronological ordering with partial credit.
"""

import pytest
from src.cortex.atoms.timeline_ordering import TimelineOrderingHandler


class TestTimelineOrderingHandler:
    """Test the timeline ordering handler."""

    @pytest.fixture
    def handler(self):
        return TimelineOrderingHandler()

    @pytest.fixture
    def sample_atom(self):
        return {
            "front": "Order these networking milestones chronologically",
            "events": [
                {"year": 1969, "event": "ARPANET created"},
                {"year": 1983, "event": "TCP/IP becomes standard"},
                {"year": 1989, "event": "World Wide Web invented"},
                {"year": 1995, "event": "JavaScript created"},
            ],
        }

    def test_validate_valid_atom(self, handler, sample_atom):
        """Should validate atom with events."""
        assert handler.validate(sample_atom) is True

    def test_validate_missing_events(self, handler):
        """Should reject atom without events."""
        atom = {"front": "Order these"}
        assert handler.validate(atom) is False

    def test_validate_insufficient_events(self, handler):
        """Should reject atom with less than 2 events."""
        atom = {"events": [{"year": 1969, "event": "ARPANET"}]}
        assert handler.validate(atom) is False

    def test_validate_missing_year(self, handler):
        """Should reject events without year/date."""
        atom = {"events": [
            {"event": "Event 1"},
            {"event": "Event 2"},
        ]}
        assert handler.validate(atom) is False

    def test_validate_missing_event_name(self, handler):
        """Should reject events without event/name."""
        atom = {"events": [
            {"year": 1969},
            {"year": 1983},
        ]}
        assert handler.validate(atom) is False

    def test_validate_with_date_field(self, handler):
        """Should accept 'date' as alternative to 'year'."""
        atom = {"events": [
            {"date": "1969-10-29", "event": "First ARPANET message"},
            {"date": "1983-01-01", "event": "TCP/IP adoption"},
        ]}
        assert handler.validate(atom) is True

    def test_validate_with_name_field(self, handler):
        """Should accept 'name' as alternative to 'event'."""
        atom = {"events": [
            {"year": 1969, "name": "ARPANET"},
            {"year": 1983, "name": "TCP/IP"},
        ]}
        assert handler.validate(atom) is True

    def test_check_correct_order(self, handler, sample_atom):
        """Should return full credit for correct chronological order."""
        # Events in correct chronological order
        correct_events = sorted(sample_atom["events"], key=lambda e: e["year"])
        answer = {
            "user_order": correct_events,
            "correct_order": correct_events,
            "user_input": "1 2 3 4",
        }
        result = handler.check(sample_atom, answer)

        assert result.correct is True
        assert result.partial_score == 1.0

    def test_check_wrong_order(self, handler, sample_atom):
        """Should reject incorrect chronological order."""
        correct_events = sorted(sample_atom["events"], key=lambda e: e["year"])
        # Swap first two events
        wrong_order = [correct_events[1], correct_events[0]] + correct_events[2:]
        answer = {
            "user_order": wrong_order,
            "correct_order": correct_events,
            "user_input": "2 1 3 4",
        }
        result = handler.check(sample_atom, answer)

        assert result.correct is False
        # 2 out of 4 in correct position (positions 2 and 3)
        assert result.partial_score == pytest.approx(0.5, abs=0.01)

    def test_check_partial_credit(self, handler, sample_atom):
        """Should calculate partial credit correctly."""
        correct_events = sorted(sample_atom["events"], key=lambda e: e["year"])
        # Positions 0 and 2 correct (1969 at 0, 1989 at 2)
        wrong_order = [
            correct_events[0],  # 1969 - correct position
            correct_events[3],  # 1995 - wrong (should be 1983)
            correct_events[2],  # 1989 - correct position
            correct_events[1],  # 1983 - wrong (should be 1995)
        ]
        answer = {
            "user_order": wrong_order,
            "correct_order": correct_events,
            "user_input": "1 4 3 2",
        }
        result = handler.check(sample_atom, answer)

        assert result.correct is False
        # 2 out of 4 in correct position (positions 0 and 2)
        assert result.partial_score == pytest.approx(0.5, abs=0.01)

    def test_check_skipped(self, handler, sample_atom):
        """Should handle skipped answers."""
        answer = {"skipped": True}
        result = handler.check(sample_atom, answer)

        assert result.correct is True
        assert "Skipped" in result.feedback

    def test_check_dont_know(self, handler, sample_atom):
        """Should handle 'I don't know' answers."""
        correct_events = sorted(sample_atom["events"], key=lambda e: e["year"])
        answer = {
            "dont_know": True,
            "correct_order": correct_events,
        }
        result = handler.check(sample_atom, answer)

        assert result.correct is False
        assert result.dont_know is True
        assert "1969" in result.correct_answer
        assert "ARPANET" in result.correct_answer

    def test_hint_first_attempt(self, handler, sample_atom):
        """First hint should show earliest event."""
        hint = handler.hint(sample_atom, attempt=1)

        assert hint is not None
        assert "1969" in hint
        assert "ARPANET" in hint or "earliest" in hint.lower()

    def test_hint_second_attempt(self, handler, sample_atom):
        """Second hint should show most recent event."""
        hint = handler.hint(sample_atom, attempt=2)

        assert hint is not None
        assert "1995" in hint
        assert "JavaScript" in hint or "recent" in hint.lower()

    def test_hint_third_attempt(self, handler, sample_atom):
        """Third hint should show middle event."""
        hint = handler.hint(sample_atom, attempt=3)

        assert hint is not None
        # Middle of 4 events (index 2) is 1989 WWW
        assert "1989" in hint or "1983" in hint

    def test_hint_no_more_hints(self, handler, sample_atom):
        """Should return None when hints exhausted."""
        hint = handler.hint(sample_atom, attempt=10)

        assert hint is None

    def test_format_timeline(self, handler, sample_atom):
        """Should format timeline with years and events."""
        events = sorted(sample_atom["events"], key=lambda e: e["year"])
        formatted = handler._format_timeline(events)

        assert "1969" in formatted
        assert "ARPANET" in formatted
        assert "->" in formatted

    def test_check_with_dates(self, handler):
        """Should work with date fields instead of year."""
        atom = {"events": [
            {"date": "1989-03-12", "event": "WWW proposal"},
            {"date": "1969-10-29", "event": "First ARPANET message"},
        ]}
        correct_order = sorted(atom["events"], key=lambda e: e["date"])

        answer = {
            "user_order": correct_order,
            "correct_order": correct_order,
            "user_input": "2 1",
        }
        handler_instance = TimelineOrderingHandler()
        result = handler_instance.check(atom, answer)

        assert result.correct is True
