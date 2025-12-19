"""
Unit tests for NoteActionsService.

Tests the smart deduplication logic and service methods.
"""

import pytest
from unittest.mock import Mock, MagicMock, patch, AsyncMock
from uuid import UUID, uuid4

from src.learning.note_actions import (
    NoteActionsService,
    DuplicationPolicy,
    DuplicationResult,
    AtomInsertionResult,
)


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def mock_db_session():
    """Mock database session."""
    session = Mock()
    session.execute = Mock(return_value=Mock(fetchall=Mock(return_value=[])))
    session.commit = Mock()
    session.rollback = Mock()
    return session


@pytest.fixture
def mock_similarity_service():
    """Mock SemanticSimilarityService."""
    service = Mock()
    service.find_similar_to_text = Mock(return_value=[])
    return service


@pytest.fixture
def mock_anki_client():
    """Mock AnkiClient."""
    client = Mock()
    client.check_connection = Mock(return_value=True)
    client.create_filtered_deck = Mock(return_value=True)
    return client


@pytest.fixture
def mock_content_reader():
    """Mock ContentReader."""
    reader = Mock()
    section = Mock()
    section.title = "Test Section"
    section.content = "This is test content about networking concepts."
    reader.get_section = Mock(return_value=section)
    return reader


@pytest.fixture
def note_actions_service(
    mock_db_session,
    mock_similarity_service,
    mock_anki_client,
    mock_content_reader,
):
    """Create NoteActionsService with mocked dependencies."""
    service = NoteActionsService(
        db_session=mock_db_session,
        similarity_service=mock_similarity_service,
        anki_client=mock_anki_client,
        content_reader=mock_content_reader,
    )
    return service


@pytest.fixture
def sample_note():
    """Sample note dict for testing."""
    return {
        "id": str(uuid4()),
        "section_id": "7.1",
        "module_number": 7,
        "title": "Ethernet Frames",
        "content": "This is a study note about Ethernet frames...",
    }


# ============================================================================
# Deduplication Logic Tests
# ============================================================================


class TestCheckForDuplicates:
    """Test the check_for_duplicates method."""

    def test_novel_content_returns_insert_policy(self, note_actions_service):
        """When no similar atoms found, return INSERT policy."""
        # No matches
        note_actions_service._similarity_service.find_similar_to_text.return_value = []

        result = note_actions_service.check_for_duplicates(
            front="What is a MAC address?",
            back="A unique hardware identifier",
            atom_type="flashcard",
        )

        assert result.policy == DuplicationPolicy.INSERT
        assert result.existing_atom_id is None

    def test_exact_duplicate_returns_skip_policy(self, note_actions_service):
        """When exact duplicate found (>0.85 + same type), return SKIP."""
        existing_id = uuid4()
        match = Mock()
        match.atom_id_2 = existing_id
        match.front_2 = "What is a MAC address?"
        match.similarity_score = 0.92  # Above threshold

        note_actions_service._similarity_service.find_similar_to_text.return_value = [match]

        # Mock getting atom types - same type as new atom
        note_actions_service._get_atom_types_for_ids = Mock(
            return_value={existing_id: "flashcard"}
        )

        result = note_actions_service.check_for_duplicates(
            front="What is a MAC address?",
            back="A unique hardware identifier",
            atom_type="flashcard",  # Same type
        )

        assert result.policy == DuplicationPolicy.SKIP_EXACT
        assert result.existing_atom_id == existing_id
        assert result.similarity_score == 0.92

    def test_cross_format_duplicate_returns_allow_policy(self, note_actions_service):
        """When same concept but different format (>0.85), return ALLOW."""
        existing_id = uuid4()
        match = Mock()
        match.atom_id_2 = existing_id
        match.front_2 = "A {{c1::MAC address}} is a unique hardware identifier"
        match.similarity_score = 0.88  # Above threshold

        note_actions_service._similarity_service.find_similar_to_text.return_value = [match]

        # Mock getting atom types - different type
        note_actions_service._get_atom_types_for_ids = Mock(
            return_value={existing_id: "cloze"}  # Existing is cloze
        )

        result = note_actions_service.check_for_duplicates(
            front="What is a MAC address?",
            back="A unique hardware identifier",
            atom_type="flashcard",  # New is flashcard - different!
        )

        assert result.policy == DuplicationPolicy.ALLOW_CROSS_FORMAT
        assert result.existing_atom_id == existing_id
        assert result.existing_type == "cloze"

    def test_borderline_similarity_returns_prompt_policy(self, note_actions_service):
        """When similarity is borderline (0.70-0.85), return PROMPT."""
        existing_id = uuid4()
        match = Mock()
        match.atom_id_2 = existing_id
        match.front_2 = "Explain MAC addresses"
        match.similarity_score = 0.78  # Borderline

        note_actions_service._similarity_service.find_similar_to_text.return_value = [match]

        note_actions_service._get_atom_types_for_ids = Mock(
            return_value={existing_id: "flashcard"}
        )

        result = note_actions_service.check_for_duplicates(
            front="What is a MAC address?",
            back="A unique hardware identifier",
            atom_type="flashcard",
        )

        assert result.policy == DuplicationPolicy.PROMPT_BORDERLINE
        assert result.similarity_score == 0.78

    def test_similarity_service_failure_returns_insert(self, note_actions_service):
        """When similarity check fails, default to INSERT (fail open)."""
        note_actions_service._similarity_service.find_similar_to_text.side_effect = Exception(
            "DB error"
        )

        result = note_actions_service.check_for_duplicates(
            front="What is a MAC address?",
            back="A unique hardware identifier",
            atom_type="flashcard",
        )

        assert result.policy == DuplicationPolicy.INSERT


class TestDuplicationPolicyThresholds:
    """Test threshold edge cases for deduplication."""

    @pytest.mark.parametrize(
        "similarity,same_type,expected_policy",
        [
            (0.86, True, DuplicationPolicy.SKIP_EXACT),  # Just above exact threshold
            (0.85, True, DuplicationPolicy.PROMPT_BORDERLINE),  # At borderline (not >0.85)
            (0.84, True, DuplicationPolicy.PROMPT_BORDERLINE),  # Below exact, above borderline
            (0.71, True, DuplicationPolicy.PROMPT_BORDERLINE),  # Above borderline threshold
            (0.90, False, DuplicationPolicy.ALLOW_CROSS_FORMAT),  # High sim, different type
        ],
    )
    def test_threshold_boundaries(
        self, note_actions_service, similarity, same_type, expected_policy
    ):
        """Test exact threshold boundaries."""
        existing_id = uuid4()
        match = Mock()
        match.atom_id_2 = existing_id
        match.front_2 = "Similar content"
        match.similarity_score = similarity

        note_actions_service._similarity_service.find_similar_to_text.return_value = [match]

        existing_type = "flashcard" if same_type else "cloze"
        note_actions_service._get_atom_types_for_ids = Mock(
            return_value={existing_id: existing_type}
        )

        result = note_actions_service.check_for_duplicates(
            front="Test content",
            back="Test back",
            atom_type="flashcard",
            exact_threshold=0.85,
            borderline_threshold=0.70,
        )

        assert result.policy == expected_policy

    def test_below_borderline_returns_insert(self, note_actions_service):
        """When similarity is below borderline threshold, return INSERT."""
        # No matches returned when below threshold
        note_actions_service._similarity_service.find_similar_to_text.return_value = []

        result = note_actions_service.check_for_duplicates(
            front="Completely novel content",
            back="Novel back",
            atom_type="flashcard",
        )

        assert result.policy == DuplicationPolicy.INSERT


# ============================================================================
# Content Generation Tests
# ============================================================================


class TestGenerateComparisonTable:
    """Test comparison table generation."""

    def test_returns_error_when_llm_not_configured(self, mock_db_session, sample_note):
        """Should return error when LLM is not configured."""
        service = NoteActionsService(db_session=mock_db_session)
        service._model = None  # No LLM configured

        success, result = service.generate_comparison_table(sample_note)

        assert success is False
        assert "not configured" in result.lower()

    def test_returns_error_when_section_not_found(
        self, note_actions_service, sample_note
    ):
        """Should return error when section not found."""
        note_actions_service._content_reader.get_section.return_value = None

        # Mock the model to be available
        note_actions_service._model = Mock()

        success, result = note_actions_service.generate_comparison_table(sample_note)

        assert success is False
        assert "not found" in result.lower()

    def test_successful_table_generation(self, note_actions_service, sample_note):
        """Should return markdown table on success."""
        mock_response = Mock()
        mock_response.text = "| Feature | A | B |\n|---|---|---|\n| Speed | Fast | Slow |"

        mock_model = Mock()
        mock_model.generate_content = Mock(return_value=mock_response)
        note_actions_service._model = mock_model

        success, result = note_actions_service.generate_comparison_table(sample_note)

        assert success is True
        assert "|" in result  # Markdown table


class TestGenerateMermaidDiagram:
    """Test Mermaid diagram generation."""

    def test_successful_diagram_generation(self, note_actions_service, sample_note):
        """Should return Mermaid code on success."""
        mock_response = Mock()
        mock_response.text = "```mermaid\nflowchart TD\n    A-->B\n```"

        mock_model = Mock()
        mock_model.generate_content = Mock(return_value=mock_response)
        note_actions_service._model = mock_model

        success, result = note_actions_service.generate_mermaid_diagram(
            sample_note, diagram_type="flowchart"
        )

        assert success is True
        assert "mermaid" in result.lower()

    @pytest.mark.parametrize("diagram_type", ["flowchart", "sequence", "stateDiagram-v2"])
    def test_supports_different_diagram_types(
        self, note_actions_service, sample_note, diagram_type
    ):
        """Should support different Mermaid diagram types."""
        mock_response = Mock()
        mock_response.text = f"```mermaid\n{diagram_type}\n    A-->B\n```"

        mock_model = Mock()
        mock_model.generate_content = Mock(return_value=mock_response)
        note_actions_service._model = mock_model

        success, result = note_actions_service.generate_mermaid_diagram(
            sample_note, diagram_type=diagram_type
        )

        assert success is True


# ============================================================================
# Anki Integration Tests
# ============================================================================


class TestCreateAnkiFilteredDeck:
    """Test Anki filtered deck creation."""

    def test_returns_error_when_anki_not_running(
        self, note_actions_service, sample_note
    ):
        """Should return error when Anki is not running."""
        note_actions_service._anki_client.check_connection.return_value = False

        success, message = note_actions_service.create_anki_filtered_deck(sample_note)

        assert success is False
        assert "not running" in message.lower()

    def test_successful_deck_creation(self, note_actions_service, sample_note):
        """Should create filtered deck successfully."""
        note_actions_service._anki_client.check_connection.return_value = True
        note_actions_service._anki_client.create_filtered_deck.return_value = True

        success, message = note_actions_service.create_anki_filtered_deck(sample_note)

        assert success is True
        assert "created deck" in message.lower()
        note_actions_service._anki_client.create_filtered_deck.assert_called_once()

    def test_deck_name_format(self, note_actions_service, sample_note):
        """Should create deck with proper naming format."""
        note_actions_service._anki_client.check_connection.return_value = True
        note_actions_service._anki_client.create_filtered_deck.return_value = True

        note_actions_service.create_anki_filtered_deck(sample_note)

        call_args = note_actions_service._anki_client.create_filtered_deck.call_args
        deck_name = call_args.kwargs.get("name") or call_args[1].get("name")

        assert "CCNA::Remediation::" in deck_name
        assert "7.1" in deck_name  # Section ID

    def test_search_query_format(self, note_actions_service, sample_note):
        """Should generate correct search query."""
        search_query = note_actions_service.get_anki_search_query(sample_note)

        assert "deck:CCNA::ITN::*" in search_query
        assert "tag:section:7.1" in search_query


# ============================================================================
# Atom Insertion Result Tests
# ============================================================================


class TestAtomInsertionResult:
    """Test AtomInsertionResult dataclass."""

    def test_total_generated_counts_all_categories(self):
        """Should count atoms from all categories."""
        from src.ccna.atomizer_service import GeneratedAtom, AtomType, KnowledgeType

        mock_atom = Mock()
        mock_atom.front = "Test"

        result = AtomInsertionResult(
            section_id="7.1",
            inserted=[mock_atom, mock_atom],
            skipped_exact=[(mock_atom, Mock())],
            allowed_cross_format=[(mock_atom, Mock())],
            prompted_borderline=[(mock_atom, Mock()), (mock_atom, Mock())],
        )

        assert result.total_generated == 6  # 2 + 1 + 1 + 2

    def test_empty_result(self):
        """Should handle empty result."""
        result = AtomInsertionResult(section_id="7.1")

        assert result.total_generated == 0
        assert len(result.inserted) == 0
        assert len(result.errors) == 0
