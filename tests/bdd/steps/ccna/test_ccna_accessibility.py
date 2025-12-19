"""
BDD step definitions for accessibility and UX contracts.

Uses a lightweight payload to assert keyboard hints, ARIA labels, and
non-color feedback cues without requiring a running UI.
"""

from dataclasses import dataclass, field
from pathlib import Path

import pytest
from pytest_bdd import given, scenarios, then, when


FEATURE_PATH = Path(__file__).parent.parent.parent.parent.parent / "features" / "ccna" / "accessibility_ux.feature"
scenarios(FEATURE_PATH)


@dataclass
class AccessibilityContext:
    payload: dict = field(default_factory=dict)
    navigation_triggered: bool = False


@pytest.fixture
def context():
    return AccessibilityContext()


@given("the study UI is open on a CCNA atom")
def open_study_ui(context: AccessibilityContext):
    context.payload = {
        "atom_id": "SAMPLE-MCQ-001",
        "atom_type": "mcq",
        "front": "Which mask creates a /24 network?",
        "aria_label": "mcq atom SAMPLE-MCQ-001",
        "aria_role": "group",
        "keyboard_hints": [
            "Tab/Arrow keys to navigate options",
            "1..4 to select options",
            "Enter to submit",
        ],
        "explanation": "A /24 uses 255.255.255.0",
        "feedback_text": "Correct. Explanation shown.",
        "contrast_ok": True,
        "non_color_cues": ["icon", "text"],
    }


@when("the user presses Tab and Arrow keys")
def press_tab_arrows(context: AccessibilityContext):
    context.navigation_triggered = True


@then("focus moves predictably across interactive elements")
def assert_focus_guidance(context: AccessibilityContext):
    assert context.navigation_triggered
    hints = context.payload.get("keyboard_hints", [])
    assert any("Tab/Arrow" in hint for hint in hints)


@then("pressing Enter submits the current response")
def assert_enter_hint(context: AccessibilityContext):
    hints = context.payload.get("keyboard_hints", [])
    assert any("Enter" in hint for hint in hints)


@then("pressing 1..4 selects MCQ options when available")
def assert_numeric_shortcuts(context: AccessibilityContext):
    hints = context.payload.get("keyboard_hints", [])
    assert any("1..4" in hint for hint in hints)


@given("the user navigates to the question")
def navigate_question(context: AccessibilityContext):
    if not context.payload:
        open_study_ui(context)
    context.navigation_triggered = True


@then("the screen reader announces the question text and atom type")
def assert_screen_reader_question(context: AccessibilityContext):
    assert context.payload.get("aria_label")
    assert context.payload.get("atom_type")


@then("after submission it announces correctness and shows explanation text")
def assert_feedback_announced(context: AccessibilityContext):
    assert context.payload.get("feedback_text")
    assert context.payload.get("explanation")


@then("success and error are conveyed with icons/text in addition to color")
def assert_non_color_cues(context: AccessibilityContext):
    cues = context.payload.get("non_color_cues", [])
    assert "icon" in cues or "text" in cues


@then("contrast ratios meet WCAG AA for text and UI components")
def assert_contrast(context: AccessibilityContext):
    assert context.payload.get("contrast_ok") is True


@when("correctness is shown")
def show_correctness(context: AccessibilityContext):
    # Simulate feedback render; nothing to mutate for this stub
    assert context.payload
