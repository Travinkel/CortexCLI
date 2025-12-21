"""
Unit tests for the Equation Balancing handler.

Tests coefficient adjustment with partial credit.
"""

import pytest
from src.cortex.atoms.equation_balancing import EquationBalancingHandler


class TestEquationBalancingHandler:
    """Test the equation balancing handler."""

    @pytest.fixture
    def handler(self):
        return EquationBalancingHandler()

    @pytest.fixture
    def sample_atom(self):
        """Simple combustion equation: CH4 + 2O2 -> CO2 + 2H2O"""
        return {
            "front": "Balance the combustion of methane",
            "equation": "CH4 + O2 → CO2 + H2O",
            "reactants": ["CH4", "O2"],
            "products": ["CO2", "H2O"],
            "coefficients": {
                "CH4": 1,
                "O2": 2,
                "CO2": 1,
                "H2O": 2,
            },
        }

    @pytest.fixture
    def complex_atom(self):
        """Complex equation: 2Fe + 3Cl2 -> 2FeCl3"""
        return {
            "front": "Balance the reaction of iron with chlorine",
            "equation": "Fe + Cl2 → FeCl3",
            "reactants": ["Fe", "Cl2"],
            "products": ["FeCl3"],
            "coefficients": {
                "Fe": 2,
                "Cl2": 3,
                "FeCl3": 2,
            },
        }

    def test_validate_valid_atom(self, handler, sample_atom):
        """Should validate atom with reactants and products."""
        assert handler.validate(sample_atom) is True

    def test_validate_equation_only(self, handler):
        """Should validate atom with equation and coefficients."""
        atom = {
            "equation": "H2 + O2 → H2O",
            "coefficients": {"H2": 2, "O2": 1, "H2O": 2},
        }
        assert handler.validate(atom) is True

    def test_validate_missing_reactants(self, handler):
        """Should reject atom without reactants."""
        atom = {"products": ["H2O"]}
        assert handler.validate(atom) is False

    def test_validate_missing_products(self, handler):
        """Should reject atom without products."""
        atom = {"reactants": ["H2", "O2"]}
        assert handler.validate(atom) is False

    def test_check_all_correct(self, handler, sample_atom):
        """Should return full credit for correct coefficients."""
        compounds = sample_atom["reactants"] + sample_atom["products"]
        answer = {
            "user_coefficients": {
                "CH4": 1,
                "O2": 2,
                "CO2": 1,
                "H2O": 2,
            },
            "correct_coefficients": sample_atom["coefficients"],
            "compounds": compounds,
            "user_input": "1 2 1 2",
        }
        result = handler.check(sample_atom, answer)

        assert result.correct is True
        assert result.partial_score == 1.0

    def test_check_partial_correct(self, handler, sample_atom):
        """Should give partial credit for some correct coefficients."""
        compounds = sample_atom["reactants"] + sample_atom["products"]
        answer = {
            "user_coefficients": {
                "CH4": 1,  # correct
                "O2": 1,   # wrong (should be 2)
                "CO2": 1,  # correct
                "H2O": 1,  # wrong (should be 2)
            },
            "correct_coefficients": sample_atom["coefficients"],
            "compounds": compounds,
            "user_input": "1 1 1 1",
        }
        result = handler.check(sample_atom, answer)

        assert result.correct is False
        assert result.partial_score == pytest.approx(0.5, abs=0.01)

    def test_check_all_wrong(self, handler, sample_atom):
        """Should give zero credit for all wrong coefficients."""
        compounds = sample_atom["reactants"] + sample_atom["products"]
        answer = {
            "user_coefficients": {
                "CH4": 5,
                "O2": 5,
                "CO2": 5,
                "H2O": 5,
            },
            "correct_coefficients": sample_atom["coefficients"],
            "compounds": compounds,
            "user_input": "5 5 5 5",
        }
        result = handler.check(sample_atom, answer)

        assert result.correct is False
        assert result.partial_score == 0.0

    def test_check_complex_equation(self, handler, complex_atom):
        """Should handle complex equations."""
        compounds = complex_atom["reactants"] + complex_atom["products"]
        answer = {
            "user_coefficients": {
                "Fe": 2,
                "Cl2": 3,
                "FeCl3": 2,
            },
            "correct_coefficients": complex_atom["coefficients"],
            "compounds": compounds,
            "user_input": "2 3 2",
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
        compounds = sample_atom["reactants"] + sample_atom["products"]
        answer = {
            "dont_know": True,
            "correct_coefficients": sample_atom["coefficients"],
            "compounds": compounds,
        }
        result = handler.check(sample_atom, answer)

        assert result.correct is False
        assert result.dont_know is True
        assert "CH4" in result.correct_answer
        assert "2O2" in result.correct_answer or "O2" in result.correct_answer

    def test_hint_first_attempt(self, handler, sample_atom):
        """First hint should give general guidance."""
        hint = handler.hint(sample_atom, attempt=1)

        assert hint is not None
        assert "count" in hint.lower() or "atom" in hint.lower()

    def test_hint_second_attempt(self, handler, sample_atom):
        """Second hint should give balancing strategy."""
        hint = handler.hint(sample_atom, attempt=2)

        assert hint is not None
        assert "balance" in hint.lower() or "element" in hint.lower()

    def test_hint_third_attempt(self, handler, sample_atom):
        """Third hint should reveal first coefficient."""
        hint = handler.hint(sample_atom, attempt=3)

        assert hint is not None
        assert "CH4" in hint
        assert "1" in hint

    def test_hint_fourth_attempt(self, handler, sample_atom):
        """Fourth hint should reveal second coefficient."""
        hint = handler.hint(sample_atom, attempt=4)

        assert hint is not None
        assert "O2" in hint
        assert "2" in hint

    def test_hint_no_more_hints(self, handler, sample_atom):
        """Should return None when hints exhausted."""
        hint = handler.hint(sample_atom, attempt=10)

        assert hint is None

    def test_build_equation(self, handler):
        """Should build equation string from components."""
        reactants = ["H2", "O2"]
        products = ["H2O"]
        equation = handler._build_equation(reactants, products)

        assert "H2" in equation
        assert "O2" in equation
        assert "H2O" in equation
        assert "+" in equation
        assert "→" in equation

    def test_format_balanced(self, handler):
        """Should format balanced equation with coefficients."""
        compounds = ["H2", "O2", "H2O"]
        coefficients = {"H2": 2, "O2": 1, "H2O": 2}
        formatted = handler._format_balanced(compounds, coefficients)

        assert "2H2" in formatted
        assert "O2" in formatted  # Coefficient 1 is omitted
        assert "2H2O" in formatted

    def test_format_balanced_omits_coefficient_one(self, handler):
        """Should omit coefficient of 1."""
        compounds = ["CH4", "CO2"]
        coefficients = {"CH4": 1, "CO2": 1}
        formatted = handler._format_balanced(compounds, coefficients)

        assert "1CH4" not in formatted
        assert "1CO2" not in formatted
        assert "CH4" in formatted
        assert "CO2" in formatted
