"""
Unit tests for Anki client.

Tests client initialization, query building, and search logic
WITHOUT requiring Anki to be running.
"""

import pytest
from unittest.mock import Mock, patch

from src.anki.anki_client import AnkiClient


class TestAnkiClientInit:
    """Tests for AnkiClient initialization."""

    def test_default_initialization(self):
        """Client should initialize with default settings."""
        with patch("src.anki.anki_client.get_settings") as mock_settings:
            mock_settings.return_value = Mock(
                anki_connect_url="http://localhost:8765",
                anki_deck_name="TestDeck",
                anki_note_type="TestType",
            )
            client = AnkiClient()

            assert client.base_url == "http://localhost:8765"
            assert client.deck_name == "TestDeck"
            assert client.note_type == "TestType"
            assert client.timeout == 60

    def test_custom_initialization(self):
        """Client should accept custom parameters."""
        with patch("src.anki.anki_client.get_settings") as mock_settings:
            mock_settings.return_value = Mock(
                anki_connect_url="http://localhost:8765",
                anki_deck_name="Default",
                anki_note_type="Default",
            )
            client = AnkiClient(
                base_url="http://custom:9999",
                deck_name="CustomDeck",
                note_type="CustomType",
                timeout=30,
            )

            assert client.base_url == "http://custom:9999"
            assert client.deck_name == "CustomDeck"
            assert client.note_type == "CustomType"
            assert client.timeout == 30


class TestSearchQueryBuilding:
    """Tests for search query building."""

    def test_find_note_by_card_id_queries(self):
        """find_note_by_card_id should use correct query format."""
        with patch("src.anki.anki_client.get_settings") as mock_settings:
            mock_settings.return_value = Mock(
                anki_connect_url="http://localhost:8765",
                anki_deck_name="CCNA",
                anki_note_type="LearningOS-v2",
            )
            client = AnkiClient()

            # Mock _invoke to capture query
            queries_used = []
            def capture_invoke(action, params=None):
                if action == "findNotes" and params:
                    queries_used.append(params.get("query", ""))
                return []  # Return empty to keep searching

            client._invoke = capture_invoke
            client.find_note_by_card_id("NET-M1-001")

            # Should try concept_id search first
            assert any('concept_id:"NET-M1-001"' in q for q in queries_used)


class TestFieldMapping:
    """Tests for field mapping from Anki notes."""

    def test_field_value_extraction(self):
        """_field_value should extract value from field dict."""
        assert AnkiClient._field_value({"value": "test"}) == "test"
        assert AnkiClient._field_value({"text": "test"}) == "test"
        assert AnkiClient._field_value(None) == ""
        assert AnkiClient._field_value({}) == ""

    def test_field_value_strips_whitespace(self):
        """_field_value should strip whitespace."""
        assert AnkiClient._field_value({"value": "  test  "}) == "test"


class TestCardTypeMapping:
    """Tests for card type and queue mapping."""

    @pytest.mark.parametrize("code,label", [
        (0, "new"),
        (1, "learning"),
        (2, "review"),
        (3, "relearning"),
        (99, "unknown"),
    ])
    def test_card_type_mapping(self, code, label):
        """Card type codes should map to correct labels."""
        assert AnkiClient._map_card_type(code) == label

    @pytest.mark.parametrize("code,label", [
        (-3, "manually_suspended"),
        (-2, "scheduler_suspended"),
        (-1, "suspended"),
        (0, "new"),
        (1, "learning"),
        (2, "review"),
        (3, "day_learning"),
        (4, "preview"),
        (99, "unknown"),
    ])
    def test_queue_mapping(self, code, label):
        """Queue codes should map to correct labels."""
        assert AnkiClient._map_queue(code) == label


class TestEaseFormatting:
    """Tests for ease factor formatting."""

    def test_ease_factor_conversion(self):
        """Ease factor should be converted from integer * 1000."""
        assert AnkiClient._format_ease(2500) == 2.5
        assert AnkiClient._format_ease(1300) == 1.3
        assert AnkiClient._format_ease(None) is None


class TestPrerequisiteTagParsing:
    """Tests for prerequisite tag parsing."""

    def test_parse_prereq_tags(self):
        """Should parse tag:prereq:domain:topic:subtopic format."""
        with patch("src.anki.anki_client.get_settings") as mock_settings:
            mock_settings.return_value = Mock(
                anki_connect_url="http://localhost:8765",
                anki_deck_name="Test",
                anki_note_type="Test",
            )
            client = AnkiClient()

            tags = ["tag:prereq:networking:layer2:switching", "other-tag"]
            result = client._parse_prerequisite_tags(tags)

            assert result["has_prerequisites"] is True
            assert len(result["prerequisite_tags"]) == 1
            assert result["parsed_hierarchy"][0]["domain"] == "networking"
            assert result["parsed_hierarchy"][0]["topic"] == "layer2"

    def test_parse_no_prereq_tags(self):
        """Should return empty result for no prereq tags."""
        with patch("src.anki.anki_client.get_settings") as mock_settings:
            mock_settings.return_value = Mock(
                anki_connect_url="http://localhost:8765",
                anki_deck_name="Test",
                anki_note_type="Test",
            )
            client = AnkiClient()

            tags = ["module::01", "other-tag"]
            result = client._parse_prerequisite_tags(tags)

            assert result["has_prerequisites"] is False
            assert result["prerequisite_tags"] == []


class TestBatchMethodSignatures:
    """Tests for batch method signatures (without calling Anki)."""

    def test_batch_find_notes_signature(self):
        """batch_find_notes should accept list of queries."""
        with patch("src.anki.anki_client.get_settings") as mock_settings:
            mock_settings.return_value = Mock(
                anki_connect_url="http://localhost:8765",
                anki_deck_name="Test",
                anki_note_type="Test",
            )
            client = AnkiClient()

            # Mock _invoke_multi
            client._invoke_multi = Mock(return_value=[[], [], []])

            result = client.batch_find_notes(["query1", "query2", "query3"])

            # Should call _invoke_multi with correct actions
            client._invoke_multi.assert_called_once()
            actions = client._invoke_multi.call_args[0][0]
            assert len(actions) == 3
            assert all(a["action"] == "findNotes" for a in actions)

    def test_batch_update_notes_signature(self):
        """batch_update_notes should accept list of update dicts."""
        with patch("src.anki.anki_client.get_settings") as mock_settings:
            mock_settings.return_value = Mock(
                anki_connect_url="http://localhost:8765",
                anki_deck_name="Test",
                anki_note_type="Test",
            )
            client = AnkiClient()

            client._invoke_multi = Mock(return_value=[None, None])

            updates = [
                {"id": 1, "fields": {"front": "Q1"}},
                {"id": 2, "fields": {"front": "Q2"}},
            ]
            client.batch_update_notes(updates)

            client._invoke_multi.assert_called_once()
            actions = client._invoke_multi.call_args[0][0]
            assert len(actions) == 2
            assert all(a["action"] == "updateNoteFields" for a in actions)

    def test_batch_add_notes_signature(self):
        """batch_add_notes should accept list of note dicts."""
        with patch("src.anki.anki_client.get_settings") as mock_settings:
            mock_settings.return_value = Mock(
                anki_connect_url="http://localhost:8765",
                anki_deck_name="Test",
                anki_note_type="Test",
            )
            client = AnkiClient()

            client._invoke_multi = Mock(return_value=[12345, 12346])

            notes = [
                {"deckName": "Test", "modelName": "Basic", "fields": {}},
                {"deckName": "Test", "modelName": "Basic", "fields": {}},
            ]
            result = client.batch_add_notes(notes)

            client._invoke_multi.assert_called_once()
            actions = client._invoke_multi.call_args[0][0]
            assert len(actions) == 2
            assert all(a["action"] == "addNote" for a in actions)
            assert result == [12345, 12346]
