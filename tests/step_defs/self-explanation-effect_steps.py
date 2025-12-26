
from pytest_bdd import scenarios, given, when, then, parsers
from unittest.mock import patch
import io
import sys

# Add src to path to allow importing main
sys.path.insert(0, './src')
from main import prompt_for_self_explanation

# Point to the feature file
scenarios('../features/self_explanation_effect.feature')

@given('the user is engaged in a problem-solving task')
def user_is_problem_solving():
    """A placeholder for the initial state."""
    pass

@when('the system determines that a self-explanation is needed')
def system_determines_need():
    """A placeholder for the trigger."""
    pass

@then(parsers.parse('the user is prompted to "{prompt_text}"'))
def user_is_prompted(prompt_text):
    with patch('builtins.input', return_value='some explanation'), \
         patch('sys.stdout', new_callable=io.StringIO) as mock_stdout:
        prompt_for_self_explanation(prompt_text)
        assert prompt_text in mock_stdout.getvalue()

@then(parsers.parse('the user\'s explanation of "{explanation}" is recorded'))
def user_explanation_is_recorded(explanation):
    with patch('builtins.input', return_value=explanation):
        response = prompt_for_self_explanation("Any prompt")
        assert response == explanation
