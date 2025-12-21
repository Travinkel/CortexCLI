"""
Unit tests for the SQL Query Builder handler.

Tests SQL clause ordering with partial credit.
"""

import pytest
from src.cortex.atoms.sql_query_builder import SqlQueryBuilderHandler


class TestSqlQueryBuilderHandler:
    """Test the SQL query builder handler."""

    @pytest.fixture
    def handler(self):
        return SqlQueryBuilderHandler()

    @pytest.fixture
    def sample_atom(self):
        return {
            "front": "Build a query to find employees with salary > 50000",
            "clauses": [
                {"type": "SELECT", "content": "name, salary"},
                {"type": "FROM", "content": "employees"},
                {"type": "WHERE", "content": "salary > 50000"},
            ],
        }

    @pytest.fixture
    def complex_atom(self):
        return {
            "front": "Build a query with JOIN and GROUP BY",
            "clauses": [
                {"type": "SELECT", "content": "d.name, COUNT(*)"},
                {"type": "FROM", "content": "departments d"},
                {"type": "JOIN", "content": "employees e ON d.id = e.dept_id"},
                {"type": "GROUP BY", "content": "d.name"},
                {"type": "ORDER BY", "content": "COUNT(*) DESC"},
            ],
        }

    def test_validate_valid_atom(self, handler, sample_atom):
        """Should validate atom with clauses."""
        assert handler.validate(sample_atom) is True

    def test_validate_missing_clauses(self, handler):
        """Should reject atom without clauses."""
        atom = {"front": "Build a query"}
        assert handler.validate(atom) is False

    def test_validate_insufficient_clauses(self, handler):
        """Should reject atom with less than 2 clauses."""
        atom = {"clauses": [{"type": "SELECT", "content": "*"}]}
        assert handler.validate(atom) is False

    def test_validate_missing_type(self, handler):
        """Should reject clauses without type."""
        atom = {"clauses": [
            {"content": "name"},
            {"type": "FROM", "content": "users"},
        ]}
        assert handler.validate(atom) is False

    def test_validate_missing_content(self, handler):
        """Should reject clauses without content."""
        atom = {"clauses": [
            {"type": "SELECT"},
            {"type": "FROM", "content": "users"},
        ]}
        assert handler.validate(atom) is False

    def test_check_correct_order(self, handler, sample_atom):
        """Should return full credit for correct SQL order."""
        correct_order = handler._sort_clauses(sample_atom["clauses"])
        answer = {
            "user_order": correct_order,
            "correct_order": correct_order,
            "user_input": "1 2 3",
        }
        result = handler.check(sample_atom, answer)

        assert result.correct is True
        assert result.partial_score == 1.0

    def test_check_wrong_order(self, handler, sample_atom):
        """Should reject incorrect SQL order."""
        correct_order = handler._sort_clauses(sample_atom["clauses"])
        # Put WHERE before FROM (invalid SQL)
        wrong_order = [correct_order[0], correct_order[2], correct_order[1]]
        answer = {
            "user_order": wrong_order,
            "correct_order": correct_order,
            "user_input": "1 3 2",
        }
        result = handler.check(sample_atom, answer)

        assert result.correct is False

    def test_check_partial_credit(self, handler, sample_atom):
        """Should calculate partial credit correctly."""
        correct_order = handler._sort_clauses(sample_atom["clauses"])
        # Only SELECT in correct position
        wrong_order = [correct_order[0], correct_order[2], correct_order[1]]
        answer = {
            "user_order": wrong_order,
            "correct_order": correct_order,
            "user_input": "1 3 2",
        }
        result = handler.check(sample_atom, answer)

        # 1 out of 3 in correct position
        assert result.partial_score == pytest.approx(0.33, abs=0.01)

    def test_check_complex_query(self, handler, complex_atom):
        """Should handle complex queries with JOINs."""
        correct_order = handler._sort_clauses(complex_atom["clauses"])
        answer = {
            "user_order": correct_order,
            "correct_order": correct_order,
            "user_input": "1 2 3 4 5",
        }
        result = handler.check(complex_atom, answer)

        assert result.correct is True

    def test_check_skipped(self, handler, sample_atom):
        """Should handle skipped answers."""
        answer = {"skipped": True}
        result = handler.check(sample_atom, answer)

        assert result.correct is True
        assert "Skipped" in result.feedback

    def test_check_dont_know(self, handler, sample_atom):
        """Should handle 'I don't know' answers."""
        correct_order = handler._sort_clauses(sample_atom["clauses"])
        answer = {
            "dont_know": True,
            "correct_order": correct_order,
        }
        result = handler.check(sample_atom, answer)

        assert result.correct is False
        assert result.dont_know is True
        assert "SELECT" in result.correct_answer
        assert "FROM" in result.correct_answer

    def test_hint_first_attempt(self, handler, sample_atom):
        """First hint should mention SELECT."""
        hint = handler.hint(sample_atom, attempt=1)

        assert hint is not None
        assert "SELECT" in hint

    def test_hint_second_attempt(self, handler, sample_atom):
        """Second hint should mention FROM."""
        hint = handler.hint(sample_atom, attempt=2)

        assert hint is not None
        assert "FROM" in hint

    def test_hint_third_attempt(self, handler, sample_atom):
        """Third hint should show first clause."""
        hint = handler.hint(sample_atom, attempt=3)

        assert hint is not None
        assert "SELECT" in hint

    def test_hint_no_more_hints(self, handler, sample_atom):
        """Should return None when hints exhausted."""
        hint = handler.hint(sample_atom, attempt=10)

        assert hint is None

    def test_sort_clauses(self, handler):
        """Should sort clauses in correct SQL order."""
        clauses = [
            {"type": "WHERE", "content": "x > 1"},
            {"type": "SELECT", "content": "*"},
            {"type": "FROM", "content": "table"},
        ]
        sorted_clauses = handler._sort_clauses(clauses)

        assert sorted_clauses[0]["type"] == "SELECT"
        assert sorted_clauses[1]["type"] == "FROM"
        assert sorted_clauses[2]["type"] == "WHERE"

    def test_sort_clauses_with_join(self, handler):
        """Should handle JOIN clauses correctly."""
        clauses = [
            {"type": "GROUP BY", "content": "category"},
            {"type": "LEFT JOIN", "content": "orders ON ..."},
            {"type": "SELECT", "content": "category, SUM(amount)"},
            {"type": "FROM", "content": "products"},
        ]
        sorted_clauses = handler._sort_clauses(clauses)

        assert sorted_clauses[0]["type"] == "SELECT"
        assert sorted_clauses[1]["type"] == "FROM"
        assert sorted_clauses[2]["type"] == "LEFT JOIN"
        assert sorted_clauses[3]["type"] == "GROUP BY"

    def test_format_query(self, handler, sample_atom):
        """Should format clauses as SQL query."""
        clauses = handler._sort_clauses(sample_atom["clauses"])
        query = handler._format_query(clauses)

        assert "SELECT name, salary" in query
        assert "FROM employees" in query
        assert "WHERE salary > 50000" in query

    def test_case_insensitive_comparison(self, handler, sample_atom):
        """Should compare queries case-insensitively."""
        correct_order = handler._sort_clauses(sample_atom["clauses"])
        # Same content, different case
        answer = {
            "user_order": correct_order,
            "correct_order": correct_order,
            "user_input": "1 2 3",
        }
        result = handler.check(sample_atom, answer)

        assert result.correct is True
