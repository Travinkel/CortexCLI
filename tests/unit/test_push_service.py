"""
Unit tests for Anki push service.

Tests deck naming, tag generation, and field building logic
WITHOUT requiring Anki to be running.
"""

import json

import pytest

from src.anki.config import (
    BASE_DECK,
    CCNA_ITN_MODULE_NAMES,
    CURRICULUM_ID,
    SOURCE_TAG,
    get_module_deck_name,
)
from src.anki.push_service import (
    _build_fields,
    _build_tags,
    _extract_module_number,
)


class TestModuleDecks:
    """Tests for module deck naming."""

    def test_module_names_complete(self):
        """All 17 modules should have names defined."""
        assert len(CCNA_ITN_MODULE_NAMES) == 17
        for i in range(1, 18):
            assert i in CCNA_ITN_MODULE_NAMES, f"Module {i} missing from CCNA_ITN_MODULE_NAMES"

    def test_base_deck_defined(self):
        """Base deck should be CCNA::ITN."""
        assert BASE_DECK == "CCNA::ITN"

    def test_get_module_deck_name_format(self):
        """Module deck names should have proper hierarchy."""
        deck_name = get_module_deck_name(1)
        assert deck_name == "CCNA::ITN::M01 Networking Today"

    @pytest.mark.parametrize("module_num,expected_name", [
        (1, "CCNA::ITN::M01 Networking Today"),
        (5, "CCNA::ITN::M05 Number Systems"),
        (10, "CCNA::ITN::M10 Basic Router Configuration"),
        (17, "CCNA::ITN::M17 Build a Small Network"),
    ])
    def test_get_module_deck_name_all_modules(self, module_num, expected_name):
        """All module decks should follow naming pattern."""
        assert get_module_deck_name(module_num) == expected_name

    def test_get_module_deck_name_unknown_module(self):
        """Unknown modules should get fallback name."""
        deck_name = get_module_deck_name(99)
        assert deck_name == "CCNA::ITN::M99 Module 99"


class TestExtractModuleNumber:
    """Tests for _extract_module_number function."""

    @pytest.mark.parametrize("card_id,expected_module", [
        ("NET-M1-S1-2-1-FC-001", 1),
        ("NET-M2-S2-1-FC-001", 2),
        ("NET-M9-S9-1-FC-001", 9),
        ("NET-M10-S10-1-FC-001", 10),
        ("NET-M17-S17-1-FC-001", 17),
    ])
    def test_extract_valid_module_numbers(self, card_id, expected_module):
        """Valid card IDs should extract correct module number."""
        assert _extract_module_number(card_id) == expected_module

    def test_extract_from_empty_card_id(self):
        """Empty card_id should return None."""
        assert _extract_module_number("") is None

    def test_extract_from_none_card_id(self):
        """None card_id should return None."""
        assert _extract_module_number(None) is None

    def test_extract_from_invalid_format(self):
        """Card IDs not matching pattern should return None."""
        assert _extract_module_number("INVALID-FORMAT") is None


class TestBuildTags:
    """Tests for _build_tags function."""

    def test_basic_tags_structure(self):
        """Tags should include source and curriculum."""
        tags = _build_tags("NET-M1-001", "flashcard", "S1-2", 1)
        assert SOURCE_TAG in tags
        assert CURRICULUM_ID in tags

    def test_module_tag_generated(self):
        """Tags should include module identifier."""
        tags = _build_tags("NET-M5-001", "flashcard", None, 5)
        assert f"{CURRICULUM_ID}:m5" in tags

    def test_type_tag_generated(self):
        """Tags should include atom type."""
        tags = _build_tags("NET-M1-001", "cloze", None, 1)
        assert "type:cloze" in tags

    def test_section_tag_generated(self):
        """Tags should include section when provided."""
        tags = _build_tags("NET-M1-001", "flashcard", "S1-2-1", 1)
        assert "section:S1-2-1" in tags

    def test_empty_section_not_in_tags(self):
        """No section tag when section_id is None."""
        tags = _build_tags("NET-M1-001", "flashcard", None, 1)
        section_tags = [t for t in tags if t.startswith("section:")]
        assert len(section_tags) == 0


class TestBuildFields:
    """Tests for _build_fields function."""

    def test_fields_structure(self):
        """Fields dict should have all required Anki fields."""
        fields = _build_fields(
            card_id="NET-M1-001",
            front="Question?",
            back="Answer.",
            tags=["cortex", "ccna-itn"],
            atom_type="flashcard",
            section_id="S1-2",
            module_number=1,
        )

        required_fields = ["front", "back", "concept_id", "tags", "source", "metadata_json"]
        for field in required_fields:
            assert field in fields, f"Missing field: {field}"

    def test_fields_content(self):
        """Fields should contain correct values."""
        fields = _build_fields(
            card_id="NET-M1-001",
            front="What is TCP?",
            back="Transmission Control Protocol",
            tags=["cortex"],
            atom_type="flashcard",
            section_id=None,
            module_number=1,
        )

        assert fields["front"] == "What is TCP?"
        assert fields["back"] == "Transmission Control Protocol"
        assert fields["concept_id"] == "NET-M1-001"
        assert fields["source"] == SOURCE_TAG

    def test_fields_metadata_json(self):
        """Metadata JSON should contain expected keys."""
        fields = _build_fields(
            card_id="NET-M1-001",
            front="Q",
            back="A",
            tags=[],
            atom_type="cloze",
            section_id="S1-2-1",
            module_number=5,
        )

        metadata = json.loads(fields["metadata_json"])
        assert metadata["curriculum_id"] == CURRICULUM_ID
        assert metadata["module_number"] == 5
        assert metadata["section_id"] == "S1-2-1"
        assert metadata["atom_type"] == "cloze"

    def test_fields_with_none_back(self):
        """None back should become empty string."""
        fields = _build_fields(
            card_id="NET-M1-001",
            front="Question?",
            back=None,
            tags=[],
            atom_type="flashcard",
            section_id=None,
            module_number=1,
        )
        assert fields["back"] == ""

    def test_fields_with_empty_values(self):
        """Empty values should be preserved."""
        fields = _build_fields(
            card_id="",
            front="",
            back="",
            tags=[],
            atom_type="",
            section_id=None,
            module_number=None,
        )
        assert fields["front"] == ""
        assert fields["back"] == ""
        assert fields["concept_id"] == ""


class TestDeckHierarchy:
    """Tests for deck hierarchy consistency."""

    def test_all_module_decks_have_parent(self):
        """All generated deck names should be under BASE_DECK."""
        for module_num in range(1, 18):
            deck_name = get_module_deck_name(module_num)
            assert deck_name.startswith(f"{BASE_DECK}::"), f"Deck {deck_name} not under {BASE_DECK}"

    def test_deck_names_sortable(self):
        """Deck names should sort correctly by module number."""
        deck_names = []
        for module_num in range(1, 18):
            deck_names.append(get_module_deck_name(module_num))

        # Sorted order should be same as generation order
        assert deck_names == sorted(deck_names)
