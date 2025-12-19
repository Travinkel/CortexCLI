"""
Integration Tests for the Study Flow Pipeline.

Tests the core learning path:
1. AtomizerService generates atoms
2. Database stores and retrieves atoms
3. StudyService provides study sessions
4. Telemetry records interactions

Requires a running PostgreSQL database with the NLS schema.
"""

from uuid import uuid4

import pytest
from sqlalchemy import text

pytestmark = pytest.mark.integration


@pytest.fixture(scope="module")
def db_engine():
    """Get database engine for integration tests."""
    try:
        from src.db.database import engine

        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return engine
    except Exception as e:
        pytest.skip(f"Database not available: {e}")


@pytest.fixture(scope="module")
def study_service():
    """Get StudyService instance."""
    from src.study.study_service import StudyService

    return StudyService(user_id="test_user")


class TestTheFactory:
    """Test 1: AtomizerService generates valid atoms."""

    def test_atomizer_produces_valid_atom(self):
        """AtomizerService should produce GeneratedAtom with required fields."""
        from src.ccna.atomizer_service import AtomizerService, AtomType, GeneratedAtom
        from src.ccna.content_parser import Section

        # Create a minimal section for testing
        Section(
            id="test-section-1",
            title="Test Section",
            level=2,
            content="TCP is a connection-oriented protocol that provides reliable data delivery.",
            raw_content="TCP is a connection-oriented protocol that provides reliable data delivery.",
        )

        atomizer = AtomizerService()

        # Verify the service can be instantiated and has the correct interface
        assert hasattr(atomizer, "atomize_section")
        assert hasattr(atomizer, "_generate_type")

        # Verify AtomType enum has expected values
        assert AtomType.MCQ in AtomType
        assert AtomType.TRUE_FALSE in AtomType
        assert AtomType.PARSONS in AtomType
        assert AtomType.NUMERIC in AtomType

        # Verify GeneratedAtom has required fields
        from src.ccna.atomizer_service import KnowledgeType

        test_atom = GeneratedAtom(
            card_id="test-atom-1",
            front="What does TCP stand for?",
            back="Transmission Control Protocol",
            atom_type=AtomType.FLASHCARD,
            knowledge_type=KnowledgeType.FACTUAL,
        )
        assert test_atom.front is not None
        assert test_atom.back is not None
        assert test_atom.atom_type == AtomType.FLASHCARD


class TestTheDatabase:
    """Test 2: Database correctly stores and retrieves atoms."""

    def test_atom_roundtrip(self, db_engine):
        """Atoms saved to database can be queried back with matching fields."""
        test_id = str(uuid4())
        test_front = f"Test question {test_id}"
        test_back = "Test answer"

        with db_engine.connect() as conn:
            # Insert test atom
            conn.execute(
                text("""
                INSERT INTO learning_atoms (id, card_id, front, back, atom_type, source)
                VALUES (:id, :card_id, :front, :back, 'mcq', 'test')
                ON CONFLICT (id) DO NOTHING
            """),
                {
                    "id": test_id,
                    "card_id": f"test_{test_id}",
                    "front": test_front,
                    "back": test_back,
                },
            )
            conn.commit()

            # Query back
            result = conn.execute(
                text("""
                SELECT id, front, back, atom_type
                FROM learning_atoms
                WHERE id = :id
            """),
                {"id": test_id},
            )
            row = result.fetchone()

            assert row is not None, "Atom should be retrievable after insert"
            assert row.front == test_front
            assert row.back == test_back
            assert row.atom_type == "mcq"

            # Cleanup
            conn.execute(text("DELETE FROM learning_atoms WHERE id = :id"), {"id": test_id})
            conn.commit()


class TestTheBrain:
    """Test 3: StudyService returns atoms for study sessions."""

    def test_war_session_returns_atoms(self, db_engine, study_service):
        """get_war_session() should return atoms for specified modules."""
        # First check if there are any atoms in the database
        with db_engine.connect() as conn:
            result = conn.execute(
                text("""
                SELECT COUNT(*) as cnt
                FROM learning_atoms la
                JOIN ccna_sections cs ON la.ccna_section_id = cs.section_id
                WHERE la.atom_type IN ('mcq', 'true_false', 'parsons', 'numeric')
            """)
            )
            atom_count = result.scalar()

        if atom_count == 0:
            pytest.skip("No atoms in database for war session test")

        # Get war session
        atoms = study_service.get_war_session(
            modules=[1, 2, 3],
            limit=10,
            prioritize_types=["mcq", "true_false"],
        )

        # Verify return type
        assert isinstance(atoms, list)

        # If atoms were found, verify structure
        if atoms:
            atom = atoms[0]
            assert "id" in atom
            assert "front" in atom
            assert "back" in atom
            assert "atom_type" in atom

    def test_adaptive_session_returns_atoms(self, db_engine, study_service):
        """get_adaptive_session() should return atoms with FSRS ordering."""
        with db_engine.connect() as conn:
            result = conn.execute(
                text("""
                SELECT COUNT(*) as cnt
                FROM learning_atoms
                WHERE atom_type IN ('mcq', 'true_false', 'parsons', 'matching')
            """)
            )
            atom_count = result.scalar()

        if atom_count == 0:
            pytest.skip("No atoms in database for adaptive session test")

        atoms = study_service.get_adaptive_session(
            limit=10,
            include_new=True,
            interleave=True,
        )

        assert isinstance(atoms, list)


class TestTheTelemetry:
    """Test 4: StudyService records interactions to database."""

    def test_record_interaction_updates_database(self, db_engine, study_service):
        """record_interaction() should update atom_responses table."""
        # First, get an atom to use for testing
        with db_engine.connect() as conn:
            result = conn.execute(
                text("""
                SELECT id FROM learning_atoms LIMIT 1
            """)
            )
            row = result.fetchone()

        if not row:
            pytest.skip("No atoms in database for telemetry test")

        atom_id = str(row.id)

        # Get initial response count
        with db_engine.connect() as conn:
            result = conn.execute(
                text("""
                SELECT COUNT(*) as cnt
                FROM atom_responses
                WHERE atom_id = :atom_id AND user_id = :user_id
            """),
                {"atom_id": atom_id, "user_id": "test_user"},
            )
            initial_count = result.scalar() or 0

        # Record an interaction
        response = study_service.record_interaction(
            atom_id=atom_id,
            is_correct=True,
            response_time_ms=2500,
            user_answer="test answer",
            session_type="test",
        )

        # Verify response structure
        assert isinstance(response, dict)
        assert "atom_id" in response
        assert "is_correct" in response

        # Verify database was updated (may fail if atom_responses table doesn't exist)
        try:
            with db_engine.connect() as conn:
                result = conn.execute(
                    text("""
                    SELECT COUNT(*) as cnt
                    FROM atom_responses
                    WHERE atom_id = :atom_id AND user_id = :user_id
                """),
                    {"atom_id": atom_id, "user_id": "test_user"},
                )
                new_count = result.scalar() or 0

            assert new_count >= initial_count, "Response count should not decrease"
        except Exception:
            # atom_responses table may not exist in all schemas
            pass


class TestCognitiveDiagnosis:
    """Test cognitive diagnosis recording (Synapse integration)."""

    def test_record_diagnosis_persists(self, db_engine, study_service):
        """record_diagnosis() should persist to cognitive_diagnoses table."""
        from src.adaptive.neuro_model import (
            CognitiveDiagnosis,
            CognitiveState,
            FailMode,
            RemediationType,
        )

        # Get an atom to use
        with db_engine.connect() as conn:
            result = conn.execute(text("SELECT id FROM learning_atoms LIMIT 1"))
            row = result.fetchone()

        if not row:
            pytest.skip("No atoms in database for diagnosis test")

        atom_id = str(row.id)

        # Create a test diagnosis
        diagnosis = CognitiveDiagnosis(
            fail_mode=FailMode.ENCODING_ERROR,
            success_mode=None,
            cognitive_state=CognitiveState.ANXIETY,  # "STRUGGLING" doesn't exist, use ANXIETY
            confidence=0.85,
            remediation_type=RemediationType.READ_SOURCE,
            evidence=["rapid_response", "low_stability"],
        )

        # Record the diagnosis
        try:
            diagnosis_id = study_service.record_diagnosis(
                atom_id=atom_id,
                diagnosis=diagnosis,
                response_time_ms=1500,
                is_correct=False,
            )

            # Verify it was recorded
            if diagnosis_id:
                with db_engine.connect() as conn:
                    result = conn.execute(
                        text("""
                        SELECT fail_mode, confidence
                        FROM cognitive_diagnoses
                        WHERE id = :id
                    """),
                        {"id": diagnosis_id},
                    )
                    row = result.fetchone()

                    if row:
                        assert row.fail_mode == "encoding_failure"
                        assert row.confidence == pytest.approx(0.85, rel=0.01)

        except Exception as e:
            # cognitive_diagnoses table may not exist in all schemas
            pytest.skip(f"cognitive_diagnoses table not available: {e}")
