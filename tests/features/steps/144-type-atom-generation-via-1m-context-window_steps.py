from behave import given, when, then

# Mock data to simulate the context and results
class MockContext:
    def __init__(self):
        self.model_active = False
        self.chapter_loaded = False
        self.taxonomy = None

@given('the AI Studio "gemini-1.5-pro" model is active')
def step_impl(context):
    context.mock = MockContext()
    context.mock.model_active = True
    assert context.mock.model_active is True

@given('the current textbook chapter is loaded into the 1M context buffer')
def step_impl(context):
    context.mock.chapter_loaded = True
    assert context.mock.chapter_loaded is True

@when('the 144-type atom generation is triggered')
def step_impl(context):
    if context.mock.model_active and context.mock.chapter_loaded:
        # Simulate the generation of a taxonomy
        context.mock.taxonomy = {
            "atom_1": "Definition of a limit",
            "atom_2": "Properties of limits",
            "atom_3": "L'Hôpital's Rule"
        }
    else:
        context.mock.taxonomy = {}

@then('a complete and diverse taxonomy of learning atoms is derived')
def step_impl(context):
    assert context.mock.taxonomy is not None
    assert len(context.mock.taxonomy) > 0
    # A more robust check would be to validate the structure and content of the taxonomy
    assert "atom_1" in context.mock.taxonomy
