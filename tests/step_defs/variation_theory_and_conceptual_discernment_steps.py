from pytest_bdd import given, when, then, parsers
import pytest
from src.cli import CLI

def get_divisors(n):
    divisors = 0
    for i in range(1, n + 1):
        if n % i == 0:
            divisors += 1
    return divisors

class NumberConcept:
    def __init__(self, value):
        self.value = value
        self.is_even = value % 2 == 0
        self.divisors = get_divisors(value)

# Fixtures
@pytest.fixture
def cli():
    return CLI()

# Step Definitions
@given(parsers.parse('a concept "{concept}"'))
def a_concept(cli, concept):
    cli.set_concept(concept)

@when(parsers.parse('the learner is presented with an example "{value}"'))
def presented_with_example(cli, value):
    cli.present_example(NumberConcept(int(value)))

@when(parsers.parse('the learner is presented with a non-example "{value}"'))
def presented_with_non_example(cli, value):
    cli.present_non_example(NumberConcept(int(value)))

@then(parsers.parse('the learner should be able to discern the critical features of the concept'))
def discern_critical_features(cli):
    assert cli.has_learner_discerned_concept()
