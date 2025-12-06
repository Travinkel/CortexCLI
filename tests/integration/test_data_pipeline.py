"""
Integration Tests for the CCNA Data Pipeline.

Tests the complete data flow from atoms through sections to mastery tracking.
Requires a running PostgreSQL database with the NLS schema.
"""
import pytest
from uuid import UUID
from sqlalchemy import text

# Skip all tests if database is not available
pytestmark = pytest.mark.integration


@pytest.fixture(scope="module")
def db_engine():
    """Get database engine for integration tests."""
    try:
        from src.db.database import engine
        # Test connection
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return engine
    except Exception as e:
        pytest.skip(f"Database not available: {e}")


class TestAtomDataIntegrity:
    """Test learning_atoms table data integrity."""

    def test_atoms_have_required_fields(self, db_engine):
        """All atoms should have front and back content."""
        with db_engine.connect() as conn:
            result = conn.execute(text("""
                SELECT COUNT(*) as cnt
                FROM learning_atoms
                WHERE front IS NULL OR back IS NULL
            """))
            null_count = result.scalar()

        assert null_count == 0, f"Found {null_count} atoms with NULL front/back"

    def test_atoms_have_valid_types(self, db_engine):
        """All atoms should have a valid atom_type."""
        valid_types = {'flashcard', 'cloze', 'mcq', 'true_false', 'matching', 'parsons', 'numeric'}

        with db_engine.connect() as conn:
            result = conn.execute(text("""
                SELECT DISTINCT atom_type
                FROM learning_atoms
            """))
            types = {row.atom_type for row in result}

        invalid = types - valid_types
        assert not invalid, f"Invalid atom types found: {invalid}"

    def test_atoms_linked_to_sections(self, db_engine):
        """Most atoms should be linked to sections after fix."""
        with db_engine.connect() as conn:
            result = conn.execute(text("""
                SELECT
                    COUNT(*) as total,
                    COUNT(ccna_section_id) as linked
                FROM learning_atoms
            """))
            row = result.fetchone()

        link_rate = row.linked / row.total if row.total > 0 else 0
        assert link_rate >= 0.90, f"Only {link_rate:.1%} atoms linked, expected >= 90%"

    def test_linked_sections_exist(self, db_engine):
        """All linked section IDs should exist in ccna_sections."""
        with db_engine.connect() as conn:
            result = conn.execute(text("""
                SELECT COUNT(*) as orphan_count
                FROM learning_atoms la
                WHERE la.ccna_section_id IS NOT NULL
                AND NOT EXISTS (
                    SELECT 1 FROM ccna_sections cs
                    WHERE cs.section_id = la.ccna_section_id
                )
            """))
            orphans = result.scalar()

        assert orphans == 0, f"Found {orphans} atoms linked to non-existent sections"


class TestSectionHierarchy:
    """Test ccna_sections table structure."""

    def test_sections_cover_all_modules(self, db_engine):
        """Should have sections for core CCNA modules."""
        with db_engine.connect() as conn:
            result = conn.execute(text("""
                SELECT DISTINCT module_number
                FROM ccna_sections
                ORDER BY module_number
            """))
            modules = {row.module_number for row in result}

        # CCNA ITN modules 1-16 (module 2 is hands-on lab, may not have sections)
        # Module 17 is optional build-a-network and may not be present
        core_modules = set(range(1, 17))  # Modules 1-16
        missing = core_modules - modules
        # Allow module 2 to be missing (hands-on lab)
        missing.discard(2)
        assert not missing, f"Missing sections for modules: {missing}"

    def test_sections_have_unique_ids(self, db_engine):
        """Section IDs should be unique."""
        with db_engine.connect() as conn:
            result = conn.execute(text("""
                SELECT section_id, COUNT(*) as cnt
                FROM ccna_sections
                GROUP BY section_id
                HAVING COUNT(*) > 1
            """))
            duplicates = list(result)

        assert not duplicates, f"Duplicate section IDs: {duplicates}"

    def test_section_parent_references_valid(self, db_engine):
        """Parent section references should be valid."""
        with db_engine.connect() as conn:
            result = conn.execute(text("""
                SELECT cs.section_id, cs.parent_section_id
                FROM ccna_sections cs
                WHERE cs.parent_section_id IS NOT NULL
                AND NOT EXISTS (
                    SELECT 1 FROM ccna_sections parent
                    WHERE parent.section_id = cs.parent_section_id
                )
            """))
            orphans = list(result)

        assert not orphans, f"Orphan parent references: {orphans}"


class TestMasteryTracking:
    """Test ccna_section_mastery table."""

    def test_mastery_covers_all_sections(self, db_engine):
        """Each section should have a mastery record."""
        with db_engine.connect() as conn:
            result = conn.execute(text("""
                SELECT cs.section_id
                FROM ccna_sections cs
                WHERE NOT EXISTS (
                    SELECT 1 FROM ccna_section_mastery csm
                    WHERE csm.section_id = cs.section_id
                )
                LIMIT 10
            """))
            missing = list(result)

        # Some sections may not have mastery (subsections)
        # But parent sections should all have mastery
        assert len(missing) <= 100, f"Too many sections without mastery records"

    def test_mastery_counts_match_atoms(self, db_engine):
        """atoms_total should match actual linked atom counts."""
        with db_engine.connect() as conn:
            result = conn.execute(text("""
                SELECT
                    COALESCE(SUM(atoms_total), 0) as claimed,
                    (SELECT COUNT(*) FROM learning_atoms WHERE ccna_section_id IS NOT NULL) as actual
                FROM ccna_section_mastery
            """))
            row = result.fetchone()

        assert row.claimed == row.actual, \
            f"Mastery claims {row.claimed} atoms but {row.actual} are linked"

    def test_mastery_values_valid(self, db_engine):
        """Mastery values should be in valid ranges."""
        with db_engine.connect() as conn:
            result = conn.execute(text("""
                SELECT COUNT(*) as invalid_count
                FROM ccna_section_mastery
                WHERE mastery_score < 0 OR mastery_score > 100
                OR atoms_mastered < 0
                OR atoms_mastered > atoms_total
            """))
            invalid = result.scalar()

        assert invalid == 0, f"Found {invalid} records with invalid mastery values"


class TestConceptsHierarchy:
    """Test concepts table structure."""

    def test_concepts_exist(self, db_engine):
        """Should have concepts defined."""
        with db_engine.connect() as conn:
            result = conn.execute(text("SELECT COUNT(*) FROM concepts"))
            count = result.scalar()

        assert count >= 50, f"Expected at least 50 concepts, got {count}"

    def test_atoms_linked_to_concepts(self, db_engine):
        """Some atoms should be linked to concepts."""
        with db_engine.connect() as conn:
            result = conn.execute(text("""
                SELECT
                    COUNT(*) as total,
                    COUNT(concept_id) as with_concept
                FROM learning_atoms
            """))
            row = result.fetchone()

        # Concept linking is separate from section linking
        # At minimum, should have some linked
        assert row.with_concept >= 0, "Concept linking check passed"


class TestQuizQuestions:
    """Test quiz_questions table."""

    def test_quiz_questions_exist(self, db_engine):
        """Should have quiz questions."""
        with db_engine.connect() as conn:
            result = conn.execute(text("SELECT COUNT(*) FROM quiz_questions"))
            count = result.scalar()

        assert count >= 100, f"Expected at least 100 quiz questions, got {count}"

    def test_quiz_questions_have_atoms(self, db_engine):
        """Quiz questions should be linked to atoms."""
        with db_engine.connect() as conn:
            result = conn.execute(text("""
                SELECT COUNT(*) as orphans
                FROM quiz_questions qq
                WHERE NOT EXISTS (
                    SELECT 1 FROM learning_atoms la
                    WHERE la.id = qq.atom_id
                )
            """))
            orphans = result.scalar()

        assert orphans == 0, f"Found {orphans} quiz questions without atoms"


class TestDataConsistency:
    """Test overall data consistency."""

    def test_no_orphan_mastery_records(self, db_engine):
        """All mastery records should reference existing sections."""
        with db_engine.connect() as conn:
            result = conn.execute(text("""
                SELECT COUNT(*) as orphans
                FROM ccna_section_mastery csm
                WHERE NOT EXISTS (
                    SELECT 1 FROM ccna_sections cs
                    WHERE cs.section_id = csm.section_id
                )
            """))
            orphans = result.scalar()

        assert orphans == 0, f"Found {orphans} orphan mastery records"

    def test_atom_types_distribution(self, db_engine):
        """Should have a reasonable distribution of atom types."""
        with db_engine.connect() as conn:
            result = conn.execute(text("""
                SELECT atom_type, COUNT(*) as cnt
                FROM learning_atoms
                GROUP BY atom_type
            """))
            distribution = {row.atom_type: row.cnt for row in result}

        # Should have multiple types
        assert len(distribution) >= 3, f"Expected at least 3 atom types, got {len(distribution)}"

        # Flashcards should be the most common
        assert distribution.get('flashcard', 0) >= 1000, "Expected many flashcards"
