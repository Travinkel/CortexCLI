# tests/step_defs/worked-example-effect-and-completion-problems_steps.py
import subprocess
import pytest
from pytest_bdd import scenarios, given, when, then, parsers

scenarios('../features/worked_example.feature')

@pytest.fixture
def context():
    return {}

@given(parsers.parse('the CLI is invoked with the "{command}" command'), target_fixture="context")
def cli_invoked(context, command):
    context["command"] = command
    return context

@when(parsers.parse('the user requests a worked example for "{topic}"'))
def user_requests_worked_example(context, topic):
    command = ["wo-cli", context["command"], topic]
    result = subprocess.run(command, capture_output=True, text=True, check=True)
    context["output"] = result.stdout

@when(parsers.parse('the user requests a completion problem for "{topic}"'))
def user_requests_completion_problem(context, topic):
    command = ["wo-cli", context["command"], topic]
    result = subprocess.run(command, capture_output=True, text=True, check=True)
    context["output"] = result.stdout


@then(parsers.parse('the CLI should display a step-by-step solution for an {topic} problem'))
def display_worked_example(context, topic):
    assert f"Displaying worked example for: {topic}" in context["output"]

@then(parsers.parse('the CLI should display a partial solution for a {topic} problem, with steps for the user to complete'))
def display_completion_problem(context, topic):
    assert f"Displaying completion problem for: {topic}" in context["output"]
