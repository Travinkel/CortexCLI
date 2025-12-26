# TODO: This test uses a mock UI. For a real test, the `study_ui` fixture
# should be updated to interact with the actual application's UI.

import pytest
from pytest_bdd import scenarios, given, when, then
from cli_ui import StudyUI

scenarios('../features/ccna_study_flow_accessibility.feature')

@pytest.fixture
def study_ui():
    """Provides a StudyUI instance for the test."""
    elements = ["Button 1", "Input Field", "Link 1", "Button 2"]
    return StudyUI(elements)

@given('the study UI is open on a CCNA atom')
def study_ui_is_open(study_ui):
    """Initializes and opens the mock study UI."""
    study_ui.open()
    assert study_ui.get_focused_element() == "Button 1"

@when('the user navigates through the UI using the keyboard')
def navigate_with_keyboard(study_ui):
    """Simulates navigating through all UI elements with Tab."""
    for _ in range(len(study_ui.elements)):
        study_ui.tab()

@then('all interactive elements are focusable and usable')
def check_accessibility(study_ui):
    """Checks that all elements were focused and are usable."""
    # After tabbing through all elements, focus should be back on the first one.
    assert study_ui.get_focused_element() == "Button 1"

    for element in study_ui.elements:
        assert study_ui.is_element_usable(element)

    print("All elements were successfully navigated and are usable.")
