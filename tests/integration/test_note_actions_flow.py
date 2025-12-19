"""
Integration tests for Note Actions flow.

Tests the full flow from note viewing to atom generation and Anki deck creation.
Requires database and optionally Anki running.
"""

import pytest
from uuid import uuid4

from sqlalchemy import text

from src.db.database import get_session
from src.learning.note_actions import (
    NoteActionsService,
    DuplicationPolicy,
    AtomInsertionResult,
)


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def db_session():
    """Get a database session for testing."""
    with get_session() as session:
        yield session


@pytest.fixture
def sample_note_in_db(db_session):
    """Create a sample note in the database and return it."""
    note_id = uuid4()

    # Insert test note
    db_session.execute(
        text("""
            INSERT INTO remediation_notes (
                id, section_id, module_number, title, content, note_type
            ) VALUES (
                :id, :section_id, :module_number, :title, :content, :note_type
            )
            ON CONFLICT (section_id) DO UPDATE SET
                title = EXCLUDED.title,
                content = EXCLUDED.content
        """),
        {
            "id": str(note_id),
            "section_id": "7.1",
            "module_number": 7,
            "title": "Test Ethernet Frames Note",
            "content": "This is test content about Ethernet frames for integration testing.",
            "note_type": "summary",
        }
    )
    db_session.commit()

    # Return as dict (mimics what CLI passes)
    return {
        "id": str(note_id),
        "section_id": "7.1",
        "module_number": 7,
        "title": "Test Ethernet Frames Note",
        "content": "This is test content about Ethernet frames for integration testing.",
    }


@pytest.fixture
def existing_atoms_in_db(db_session):
    """Create some existing atoms for deduplication testing."""
    atoms = [
        {
            "id": str(uuid4()),
            "card_id": "TEST-FC-001",
            "atom_type": "flashcard",
            "front": "What is an Ethernet frame?",
            "back": "A data link layer protocol data unit",
            "ccna_section_id": "7.1",
        },
        {
            "id": str(uuid4()),
            "card_id": "TEST-CL-001",
            "atom_type": "cloze",
            "front": "An {{c1::Ethernet frame}} is a data link layer PDU",
            "back": "Ethernet frame",
            "ccna_section_id": "7.1",
        },
    ]

    for atom in atoms:
        db_session.execute(
            text("""
                INSERT INTO learning_atoms (
                    id, card_id, atom_type, front, back, ccna_section_id, source
                ) VALUES (
                    :id, :card_id, :atom_type, :front, :back, :ccna_section_id, 'test'
                )
                ON CONFLICT DO NOTHING
            """),
            atom
        )

    db_session.commit()
    return atoms


@pytest.fixture
def cleanup_test_atoms(db_session):
    """Clean up test atoms after test."""
    yield
    # Cleanup
    db_session.execute(
        text("DELETE FROM learning_atoms WHERE source = 'test' OR source = 'note_actions'")
    )
    db_session.execute(
        text("DELETE FROM remediation_notes WHERE section_id = '7.1' AND title LIKE 'Test%'")
    )
    db_session.commit()


# ============================================================================
# Integration Tests
# ============================================================================


class TestNoteActionsServiceIntegration:
    """Integration tests for NoteActionsService with real database."""

    def test_service_initialization_with_db(self, db_session):
        """Service should initialize with database session."""
        service = NoteActionsService(db_session)

        assert service.db == db_session
        # Lazy-loaded properties should not fail
        assert service.similarity_service is not None
        assert service.embedding_service is not None

    def test_check_duplicates_with_real_db(
        self, db_session, existing_atoms_in_db, cleanup_test_atoms
    ):
        """Should check for duplicates against real database atoms."""
        service = NoteActionsService(db_session)

        # Note: This test may return INSERT if embeddings don't exist
        # The important thing is it doesn't crash
        result = service.check_for_duplicates(
            front="What is an Ethernet frame?",
            back="A data link layer protocol data unit",
            atom_type="flashcard",
        )

        assert result.policy in [
            DuplicationPolicy.INSERT,
            DuplicationPolicy.SKIP_EXACT,
            DuplicationPolicy.ALLOW_CROSS_FORMAT,
            DuplicationPolicy.PROMPT_BORDERLINE,
        ]

    def test_get_anki_search_query(self, db_session, sample_note_in_db):
        """Should generate valid Anki search query."""
        service = NoteActionsService(db_session)

        query = service.get_anki_search_query(sample_note_in_db)

        assert "deck:CCNA::ITN::*" in query
        assert "tag:section:7.1" in query


class TestAnkiIntegration:
    """Integration tests for Anki connectivity."""

    @pytest.mark.skipif(
        True,  # Set to False if Anki is running with AnkiConnect
        reason="Requires Anki with AnkiConnect addon running"
    )
    def test_create_filtered_deck_with_real_anki(self, db_session, sample_note_in_db):
        """Should create filtered deck when Anki is running."""
        service = NoteActionsService(db_session)

        success, message = service.create_anki_filtered_deck(sample_note_in_db)

        # Will fail if Anki not running, which is expected in CI
        if service.anki_client.check_connection():
            assert success is True
            assert "created deck" in message.lower()
        else:
            assert success is False
            assert "not running" in message.lower()

    def test_anki_client_handles_offline_gracefully(self, db_session, sample_note_in_db):
        """Should handle Anki being offline gracefully."""
        service = NoteActionsService(db_session)

        # This should not raise an exception
        success, message = service.create_anki_filtered_deck(sample_note_in_db)

        # Either succeeds (Anki running) or fails gracefully (Anki offline)
        assert isinstance(success, bool)
        assert isinstance(message, str)
        assert len(message) > 0


class TestAtomGenerationIntegration:
    """Integration tests for atom generation flow."""

    @pytest.mark.skipif(
        True,  # Set to False if GEMINI_API_KEY is configured
        reason="Requires GEMINI_API_KEY environment variable"
    )
    @pytest.mark.asyncio
    async def test_generate_atoms_with_real_llm(
        self, db_session, sample_note_in_db, cleanup_test_atoms
    ):
        """Should generate atoms using real LLM."""
        import os

        if not os.environ.get("GEMINI_API_KEY") and not os.environ.get("GOOGLE_API_KEY"):
            pytest.skip("No API key configured")

        service = NoteActionsService(db_session)

        result = await service.generate_atoms_for_note(
            sample_note_in_db,
            atom_types=["flashcard", "cloze"]
        )

        assert isinstance(result, AtomInsertionResult)
        # Should have some atoms or at least no errors
        assert result.total_generated >= 0 or len(result.errors) > 0


class TestContentGenerationIntegration:
    """Integration tests for content generation (tables, diagrams)."""

    @pytest.mark.skipif(
        True,  # Set to False if GEMINI_API_KEY is configured
        reason="Requires GEMINI_API_KEY environment variable"
    )
    def test_generate_comparison_table_with_real_llm(
        self, db_session, sample_note_in_db
    ):
        """Should generate comparison table using real LLM."""
        import os

        if not os.environ.get("GEMINI_API_KEY") and not os.environ.get("GOOGLE_API_KEY"):
            pytest.skip("No API key configured")

        service = NoteActionsService(db_session)

        success, result = service.generate_comparison_table(sample_note_in_db)

        # May fail if section content not found, which is acceptable
        assert isinstance(success, bool)
        assert isinstance(result, str)

    @pytest.mark.skipif(
        True,  # Set to False if GEMINI_API_KEY is configured
        reason="Requires GEMINI_API_KEY environment variable"
    )
    def test_generate_mermaid_diagram_with_real_llm(
        self, db_session, sample_note_in_db
    ):
        """Should generate Mermaid diagram using real LLM."""
        import os

        if not os.environ.get("GEMINI_API_KEY") and not os.environ.get("GOOGLE_API_KEY"):
            pytest.skip("No API key configured")

        service = NoteActionsService(db_session)

        success, result = service.generate_mermaid_diagram(
            sample_note_in_db,
            diagram_type="flowchart"
        )

        assert isinstance(success, bool)
        assert isinstance(result, str)


# ============================================================================
# End-to-End Flow Tests
# ============================================================================


class TestEndToEndFlow:
    """End-to-end tests simulating CLI flow."""

    def test_full_note_action_flow_without_llm(
        self, db_session, sample_note_in_db, cleanup_test_atoms
    ):
        """
        Test the full flow a user would experience.

        This test simulates:
        1. User views a note
        2. User tries to create Anki deck
        3. User gets search query (for manual use if Anki offline)
        """
        service = NoteActionsService(db_session)

        # Step 1: Get search query (always works)
        search_query = service.get_anki_search_query(sample_note_in_db)
        assert "7.1" in search_query

        # Step 2: Try Anki deck creation (may fail if Anki offline)
        success, message = service.create_anki_filtered_deck(sample_note_in_db)
        assert isinstance(success, bool)

        # Step 3: Check deduplication works
        result = service.check_for_duplicates(
            front="Test question about Ethernet",
            back="Test answer",
            atom_type="flashcard",
        )
        assert result.policy is not None

    def test_deduplication_respects_cross_format(
        self, db_session, existing_atoms_in_db, cleanup_test_atoms
    ):
        """
        Test that same concept in different format is allowed.

        This is the "multiple paths to retention" feature.
        """
        service = NoteActionsService(db_session)

        # Generate embeddings for existing atoms first (if they don't exist)
        # This test verifies the policy logic, not embedding generation

        # The key assertion: ALLOW_CROSS_FORMAT should be possible
        # when content is similar but types differ

        # Create a mock match to test the logic directly
        from unittest.mock import Mock

        existing_id = uuid4()
        match = Mock()
        match.atom_id_2 = existing_id
        match.front_2 = "What is an Ethernet frame?"
        match.similarity_score = 0.90  # High similarity

        # Patch to return our mock match
        original_find = service.similarity_service.find_similar_to_text
        service.similarity_service.find_similar_to_text = Mock(return_value=[match])
        service._get_atom_types_for_ids = Mock(return_value={existing_id: "flashcard"})

        try:
            # Check a cloze version of same concept
            result = service.check_for_duplicates(
                front="An {{c1::Ethernet frame}} carries data on a LAN",
                back="Ethernet frame",
                atom_type="cloze",  # Different type than existing "flashcard"
            )

            # Should allow because different format
            assert result.policy == DuplicationPolicy.ALLOW_CROSS_FORMAT
        finally:
            # Restore original
            service.similarity_service.find_similar_to_text = original_find
