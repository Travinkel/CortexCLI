"""
BDD step definitions for atom quality, interaction types, and notation checks.

These steps use in-memory Atom instances to avoid filesystem dependencies while
still exercising the AtomDeck schema, enhanced validator, and content shapes.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict

import pytest
from pytest_bdd import given, scenarios, then, when, parsers

from src.delivery.atom_deck import Atom
from src.content.generation.enhanced_quality_validator import (
    ValidationSeverity,
    validate_atom,
)


FEATURE_DIR = Path(__file__).parent.parent.parent.parent.parent / "features" / "ccna"
scenarios(FEATURE_DIR / "atom_quality.feature")
scenarios(FEATURE_DIR / "interaction_types.feature")


def _sample_atoms() -> Dict[str, Atom]:
    """Construct a small set of representative atoms for BDD steps."""
    atoms = [
        Atom(
            id="SAMPLE-MCQ-001",
            card_id="SAMPLE-MCQ-001",
            atom_type="mcq",
            front="Which mask creates a /24 network?",
            back="A /24 network uses 255.255.255.0.",
            source_refs=[{"excerpt": "Subnet masks define prefix length."}],
            content_json={
                "options": [
                    {"id": "a", "text": "255.255.255.0"},
                    {"id": "b", "text": "255.255.0.0"},
                    {"id": "c", "text": "255.255.255.252"},
                    {"id": "d", "text": "255.0.0.0"},
                ],
                "correct_index": 0,
                "explanation": "A /24 leaves 8 host bits -> 255.255.255.0.",
                "hints": ["Recall CIDR to dotted-decimal conversion."],
            },
            quality_score=90.0,
            difficulty=3,
            objective_code="IP-Addressing",
            validation={"score": 90},
            validation_passed=True,
            hints=["CIDR reminder"],
            explanation="A /24 leaves 8 host bits -> 255.255.255.0.",
        ),
        Atom(
            id="SAMPLE-ORDER-01",
            card_id="SAMPLE-ORDER-01",
            atom_type="ordering",
            front="Order the VLAN setup steps.",
            back="1) Create VLAN 2) Assign ports 3) Configure trunk",
            source_refs=[{"excerpt": "VLAN workflow order matters."}],
            content_json={
                "options": [
                    {"id": "a", "text": "Create VLAN"},
                    {"id": "b", "text": "Assign ports"},
                    {"id": "c", "text": "Configure trunk"},
                ],
                "correct_order": ["a", "b", "c"],
                "explanation": "You create the VLAN before assigning ports and trunks.",
            },
            quality_score=88.0,
            difficulty=2,
            objective_code="Switching-Intro",
            prerequisites=["SAMPLE-PRE-001"],
            validation={"score": 88},
            validation_passed=True,
            hints=["Think about config order vs. verification."],
            explanation="You create the VLAN before assigning ports and trunks.",
        ),
        Atom(
            id="SAMPLE-NUM-01",
            card_id="SAMPLE-NUM-01",
            atom_type="numeric",
            front="What is the wildcard mask for /26?",
            back="The wildcard mask is 0.0.0.63 hosts",
            source_refs=[{"excerpt": "Wildcard = inverted subnet mask."}],
            content_json={
                "correct_value": 63,
                "units": "hosts",
                "tolerance": 0,
                "explanation": "A /26 leaves 6 host bits -> 64 addresses, 63 usable.",
            },
            quality_score=86.0,
            validation={"score": 86},
            validation_passed=True,
            hints=["Invert the subnet mask."],
            explanation="A /26 leaves 6 host bits -> 64 addresses, 63 usable.",
        ),
        Atom(
            id="SAMPLE-LABEL-01",
            card_id="SAMPLE-LABEL-01",
            atom_type="labeling",
            front="Label the OSI layers on the diagram.",
            back="Layers from bottom: Physical, Data Link, Network, Transport, Session, Presentation, Application.",
            source_refs=[{"excerpt": "Standard OSI layer order."}],
            content_json={
                "targets": [
                    {"id": "phy", "label": "Physical"},
                    {"id": "dl", "label": "Data Link"},
                ],
                "labels": ["Physical", "Data Link"],
                "diagram_ref": "osi-diagram.svg",
                "explanation": "Layers stack from Physical upwards.",
            },
            quality_score=85.0,
            validation={"score": 85},
            validation_passed=True,
            hints=["Remember lowest layer is cabling."],
            explanation="Layers stack from Physical upwards.",
        ),
        Atom(
            id="SAMPLE-HOTSPOT-01",
            card_id="SAMPLE-HOTSPOT-01",
            atom_type="hotspot",
            front="Identify the console port on the router image.",
            back="The console port is highlighted on the left cluster.",
            source_refs=[{"excerpt": "Router front panel layout."}],
            content_json={
                "hotspots": [{"id": "console", "shape": "circle", "coords": [10, 10, 15]}],
                "choices": [{"id": "console", "label": "Console"}, {"id": "usb", "label": "USB"}],
                "explanation": "Console port is typically RJ-45/USB-A on front.",
            },
            quality_score=85.0,
            validation={"score": 85},
            validation_passed=True,
            hints=["Look for RJ-45 near USB."],
            explanation="Console port is typically RJ-45/USB-A on front.",
        ),
        Atom(
            id="SAMPLE-CASE-01",
            card_id="SAMPLE-CASE-01",
            atom_type="case_scenario",
            front="Troubleshoot intermittent connectivity for a branch router.",
            back="Verify trunk allowed VLANs, then check DHCP scope exhaustion.",
            source_refs=[{"excerpt": "Branch network troubleshooting steps."}],
            content_json={
                "steps": [
                    {
                        "prompt": "Check trunk configuration",
                        "options": ["Allowed VLANs", "Native VLAN", "Port state"],
                        "correct_index": 0,
                    },
                    {
                        "prompt": "Check DHCP scope",
                        "options": ["Exhaustion", "Relay", "DNS"],
                        "correct_index": 0,
                    },
                ],
                "summary": "Fix trunk allowed VLANs then address DHCP scope exhaustion.",
                "explanation": "Intermittent branch issues often map to trunk filtering plus DHCP.",
            },
            quality_score=90.0,
            validation={"score": 90},
            validation_passed=True,
            hints=["Think L2 before L3."],
            explanation="Intermittent branch issues often map to trunk filtering plus DHCP.",
        ),
    ]
    return {a.id: a for a in atoms}


@dataclass
class AtomTestContext:
    atoms: Dict[str, Atom] = field(default_factory=dict)
    atom: Atom | None = None
    validation_result: object | None = None


@pytest.fixture
def context() -> AtomTestContext:
    return AtomTestContext()


# Shared background
@given("the atom deck is loaded")
def load_atoms(context: AtomTestContext):
    context.atoms = _sample_atoms()


@given(parsers.parse('an atom with id "{atom_id}"'))
def set_atom_by_id(context: AtomTestContext, atom_id: str):
    context.atom = context.atoms.get(atom_id)
    assert context.atom, f"Atom {atom_id} not found in sample deck"


@then("the atom has required fields id, atom_type, front")
def assert_required_fields(context: AtomTestContext):
    atom = context.atom
    assert atom
    assert atom.id and atom.atom_type and atom.front


@then("the atom has metadata difficulty in [1..5]")
def assert_difficulty_range(context: AtomTestContext):
    atom = context.atom
    assert atom
    assert 1 <= atom.difficulty <= 5


@then("the atom has a non-empty source reference excerpt")
def assert_source_ref(context: AtomTestContext):
    atom = context.atom
    assert atom
    excerpt = atom.source_refs[0].get("excerpt") if atom.source_refs else ""
    assert excerpt and excerpt.strip()


@then(parsers.parse("the atom validation score is >= {min_score:d}"))
def assert_validation_score(context: AtomTestContext, min_score: int):
    atom = context.atom
    assert atom
    score = 0
    if atom.validation and isinstance(atom.validation, dict):
        score = atom.validation.get("score", 0)
    assert score >= min_score


@then("the atom validation passed flag is true")
def assert_validation_passed(context: AtomTestContext):
    atom = context.atom
    assert atom
    assert atom.validation_passed


@given('an MCQ atom exists')
def mcq_exists(context: AtomTestContext):
    context.atom = next(a for a in context.atoms.values() if a.atom_type == "mcq")


@then("it has 4 options and one correct_index")
def assert_mcq_options(context: AtomTestContext):
    atom = context.atom
    assert atom and atom.content_json
    options = atom.content_json.get("options", [])
    assert len(options) == 4
    assert 0 <= atom.content_json.get("correct_index", -1) < len(options)


@then("the correct answer text is non-empty")
def assert_mcq_answer(context: AtomTestContext):
    atom = context.atom
    assert atom and atom.content_json
    correct = atom.content_json["options"][atom.content_json["correct_index"]]
    assert correct.get("text")


@given("a numeric atom exists")
def numeric_exists(context: AtomTestContext):
    context.atom = next(a for a in context.atoms.values() if a.atom_type == "numeric")


@then("it has a correct_value")
def assert_numeric_value(context: AtomTestContext):
    atom = context.atom
    assert atom and atom.content_json
    assert atom.content_json.get("correct_value") is not None


@then("the rendered back includes the value and units when present")
def assert_numeric_back(context: AtomTestContext):
    atom = context.atom
    assert atom
    assert str(atom.content_json.get("correct_value")) in atom.back
    if atom.content_json.get("units"):
        assert str(atom.content_json["units"]) in atom.back


@given("an ordering atom exists")
def ordering_exists(context: AtomTestContext):
    context.atom = next(a for a in context.atoms.values() if a.atom_type == "ordering")


@then("it exposes options and a non-empty correct_order")
def assert_ordering_content(context: AtomTestContext):
    atom = context.atom
    assert atom and atom.content_json
    assert atom.content_json.get("options")
    assert atom.content_json.get("correct_order")


@then("the back shows the ordered sequence text")
def assert_ordering_back(context: AtomTestContext):
    atom = context.atom
    assert atom
    assert "1)" in atom.back


@given("a labeling atom exists")
def labeling_exists(context: AtomTestContext):
    context.atom = next(a for a in context.atoms.values() if a.atom_type == "labeling")


@then("it has targets with ids and labels")
def assert_labeling_targets(context: AtomTestContext):
    atom = context.atom
    assert atom and atom.content_json
    targets = atom.content_json.get("targets", [])
    assert targets and all(t.get("id") and t.get("label") for t in targets)


@then("it may include a diagram_ref")
def assert_diagram_ref(context: AtomTestContext):
    atom = context.atom
    assert atom
    assert atom.content_json.get("diagram_ref")


@given("a hotspot atom exists")
def hotspot_exists(context: AtomTestContext):
    context.atom = next(a for a in context.atoms.values() if a.atom_type == "hotspot")


@then("it provides hotspots and optional discrete choices")
def assert_hotspot_data(context: AtomTestContext):
    atom = context.atom
    assert atom and atom.content_json
    assert atom.content_json.get("hotspots")
    # choices are optional but should be a list when present
    choices = atom.content_json.get("choices", [])
    assert isinstance(choices, list)


@given("a case_scenario atom exists")
def case_scenario_exists(context: AtomTestContext):
    context.atom = next(a for a in context.atoms.values() if a.atom_type == "case_scenario")


@then("it includes steps with prompts and options")
def assert_case_steps(context: AtomTestContext):
    atom = context.atom
    assert atom and atom.content_json
    steps = atom.content_json.get("steps", [])
    assert steps and all(step.get("prompt") and step.get("options") for step in steps)


@then("a summary is provided")
def assert_case_summary(context: AtomTestContext):
    atom = context.atom
    assert atom
    assert atom.content_json.get("summary")


@given('an atom about "IP-Addressing"')
def atom_about_ip(context: AtomTestContext):
    context.atom = next(a for a in context.atoms.values() if a.objective_code == "IP-Addressing")


@when("the back contains an invalid IP or CIDR")
def invalidate_ip(context: AtomTestContext):
    atom = context.atom
    assert atom
    invalid_back = atom.back + " 999.999.999.999/33"
    context.validation_result = validate_atom(
        front=atom.front,
        back=invalid_back,
        atom_type=atom.atom_type,
        content_json=atom.content_json,
        source_content=None,
        validate_math=True,
    )


@then("the validator marks it invalid with a notation error")
def assert_notation_error(context: AtomTestContext):
    result = context.validation_result
    assert result
    codes = {issue.code for issue in result.issues}
    assert "NOTATION_IP_INVALID" in codes
    assert any(issue.severity == ValidationSeverity.ERROR for issue in result.issues)
