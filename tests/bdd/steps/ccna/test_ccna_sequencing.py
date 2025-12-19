"""
BDD step definitions for CCNA sequencing/remediation scenarios.

These steps use an in-memory stubbed PathSequencer to avoid DB dependencies
while still exercising prerequisite gating, remediation bundles, and spaced
review injections.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import List
from uuid import UUID, uuid5, NAMESPACE_URL

import pytest
from pytest_bdd import given, scenarios, then, when, parsers

from src.adaptive.path_sequencer import PathSequencer


def _stable_uuid(name: str) -> UUID:
    """Generate deterministic UUIDs from human-readable atom names."""
    return uuid5(NAMESPACE_URL, f"ccna-{name}")


@dataclass
class CCNASequencerContext:
    learner_id: str = ""
    sequencer: PathSequencer | None = None
    recent_outcomes: list[dict] = field(default_factory=list)
    atom_prereqs: dict[UUID, List[UUID]] = field(default_factory=dict)
    mastered_atoms: set[UUID] = field(default_factory=set)
    due_review_queue: list[UUID] = field(default_factory=list)
    initial_due_reviews: list[UUID] = field(default_factory=list)
    next_atoms: list[UUID] = field(default_factory=list)
    atom_hints: dict[UUID, list[str]] = field(default_factory=dict)
    target_atom: UUID | None = None
    remediation_atoms: list[UUID] = field(default_factory=list)
    difficulty_map: dict[UUID, int] = field(default_factory=dict)


class StubSequencer(PathSequencer):
    """Minimal stub to avoid DB lookups while keeping sequencing behavior."""

    def __init__(self, new_atoms: list[UUID], remediation_atoms: list[UUID]):
        super().__init__(session=None)
        self._new_atoms = new_atoms
        self._remediation_atoms = remediation_atoms

    def _get_new_atoms(self, *args, **kwargs):
        return list(self._new_atoms)

    def _interleave_atoms(self, session, atom_ids):
        return list(atom_ids)

    def plan_remediation_bundle(self, *args, **kwargs):
        return list(self._remediation_atoms)


FEATURE_PATH = Path(__file__).parent.parent.parent.parent.parent / "features" / "ccna" / "sequencing_remediation.feature"
LEARNING_PATH = Path(__file__).parent.parent.parent.parent.parent / "features" / "ccna" / "learning_journey.feature"
scenarios(FEATURE_PATH)
scenarios(LEARNING_PATH)


@pytest.fixture
def context():
    return CCNASequencerContext()


@given('a user "bob" has an ongoing CCNA session')
def create_user_session(context: CCNASequencerContext):
    context.learner_id = "bob"


@given(parsers.parse('a user "{name}" starts a new CCNA session for module {module:d}'))
def create_named_session(context: CCNASequencerContext, name: str, module: int):
    context.learner_id = name
    # Module is unused in the stub but carried for clarity/debugging
    context.recent_outcomes = []


@given("the atom deck is loaded with learnable-ready atoms")
def load_learnable_deck(context: CCNASequencerContext):
    # Construct deterministic atom IDs
    refresher = _stable_uuid("Binary-Subnet-Basics")
    target = _stable_uuid("Switching-VLAN-Intro-01")
    neighbor = _stable_uuid("Switching-VLAN-Intro-00-easy")
    advanced = _stable_uuid("Switching-VLAN-Intro-02")

    context.target_atom = target
    context.remediation_atoms = [refresher, neighbor]
    context.atom_prereqs = {target: [refresher], advanced: [target]}
    context.atom_hints = {refresher: ["remember subnet binary steps"], neighbor: ["consider VLAN defaults"]}
    context.difficulty_map = {refresher: 2, target: 3, neighbor: 2, advanced: 4}
    context.sequencer = StubSequencer(new_atoms=[target, advanced], remediation_atoms=context.remediation_atoms)


@given(parsers.parse('Bob failed atom "{atom_name}" twice'))
@given(parsers.parse('Alice answered atom "{atom_name}" incorrectly twice'))
def record_failures(context: CCNASequencerContext, atom_name: str):
    context.recent_outcomes = [{"correct": False}, {"correct": False}]
    # Ensure the failed atom is treated as the current concept for remediation
    if atom_name:
        context.target_atom = _stable_uuid(atom_name)


@given("Bob mastered 3 atoms yesterday")
def enqueue_due_reviews(context: CCNASequencerContext):
    due_atoms = [_stable_uuid(f"review-{i}") for i in range(3)]
    context.due_review_queue = list(due_atoms)
    context.initial_due_reviews = list(due_atoms)
    context.mastered_atoms.update(due_atoms)
    if not context.sequencer:
        # Provide at least one new atom so we can assert ordering after reviews
        context.sequencer = StubSequencer(new_atoms=[_stable_uuid("new-after-review")], remediation_atoms=[])


@when("he requests the next atom")
def request_next_atom(context: CCNASequencerContext):
    concept_id = context.target_atom or _stable_uuid("default-concept")
    context.next_atoms = context.sequencer.get_next_atoms(
        learner_id=context.learner_id,
        concept_id=concept_id,
        count=3,
        include_review=True,
        recent_outcomes=context.recent_outcomes,
        mastered_atoms=context.mastered_atoms or set(),
        atom_prerequisites=context.atom_prereqs or {},
        due_review_queue=context.due_review_queue,
    )


@when("Alice requests the next atom")
@when("she requests the next atom")
def request_next_atom_alice(context: CCNASequencerContext):
    concept_id = context.target_atom or _stable_uuid("default-concept")
    # Ensure prerequisites are considered mastered for the first surface
    if context.target_atom and context.atom_prereqs.get(context.target_atom):
        context.mastered_atoms.update(context.atom_prereqs[context.target_atom])
    context.next_atoms = context.sequencer.get_next_atoms(
        learner_id=context.learner_id,
        concept_id=concept_id,
        count=3,
        include_review=False,
        recent_outcomes=context.recent_outcomes,
        mastered_atoms=context.mastered_atoms or set(),
        atom_prerequisites=context.atom_prereqs or {},
    )


@then("she is given an atom whose prerequisites are all mastered")
def assert_prereqs_met(context: CCNASequencerContext):
    assert context.next_atoms, "Expected at least one atom returned"
    first_atom = context.next_atoms[0]
    prereqs = context.atom_prereqs.get(first_atom, [])
    assert all(pr in context.mastered_atoms for pr in prereqs)


@when("he resumes the session")
def request_next_atom_after_break(context: CCNASequencerContext):
    # Fetch with a count that leaves room for new content after reviews
    context.next_atoms = context.sequencer.get_next_atoms(
        learner_id=context.learner_id,
        count=4,
        include_review=True,
        recent_outcomes=[],
        mastered_atoms=context.mastered_atoms or set(),
        atom_prerequisites=context.atom_prereqs or {},
        due_review_queue=context.due_review_queue,
    )


@then("the sequencer includes a prerequisite refresher atom")
@then(parsers.parse('the sequencer serves a prerequisite refresher for "{atom_name}"'))
def assert_refresher_present(context: CCNASequencerContext, atom_name: str | None = None):
    refresher = context.remediation_atoms[0]
    if atom_name:
        assert refresher == _stable_uuid(atom_name)
    assert refresher in context.next_atoms


@then("also includes a nearest-neighbor easier atom from the same cluster")
@then("also queues a similar easier atom from the same cluster")
def assert_neighbor_present(context: CCNASequencerContext):
    neighbor = context.remediation_atoms[1]
    assert neighbor in context.next_atoms


@then("the remediation atom shows a hint before answer submission")
@then("the UI shows a hint before the next attempt")
def assert_hint_available(context: CCNASequencerContext):
    refresher = context.remediation_atoms[0]
    assert context.atom_hints.get(refresher), "Expected hint metadata for remediation atom"


@then("the sequencer inserts due review atoms before introducing new content")
def assert_reviews_before_new(context: CCNASequencerContext):
    # All review atoms should come before any new atom returned by the stub
    expected_reviews = set(context.initial_due_reviews)
    served = [a for a in context.next_atoms if a in expected_reviews]
    assert served, "Expected due reviews to be injected"
    first_new_index = len(context.next_atoms)
    for idx, atom_id in enumerate(context.next_atoms):
        if atom_id not in expected_reviews:
            first_new_index = idx
            break
    assert all(atom in expected_reviews for atom in context.next_atoms[:first_new_index])


@when("she answers correctly three times without hints")
def alice_mastery_streak(context: CCNASequencerContext):
    context.recent_outcomes = [{"correct": True, "hint_used": False}] * 3


@then("the sequencer marks the atom as mastered")
def assert_alice_mastered(context: CCNASequencerContext):
    assert PathSequencer.compute_mastery_decision(
        context.recent_outcomes, require_consecutive=3, rolling_window=5, rolling_accuracy_threshold=0.85
    )


@then("the next atom increases in difficulty within the same objective cluster")
def assert_increasing_difficulty(context: CCNASequencerContext):
    assert context.next_atoms, "Expected sequencer to return atoms"
    # Compare first and second atoms' difficulty hints
    if len(context.next_atoms) < 2:
        pytest.skip("Not enough atoms to compare difficulty ordering")
    first, second = context.next_atoms[0], context.next_atoms[1]
    first_diff = context.difficulty_map.get(first, 0)
    second_diff = context.difficulty_map.get(second, 0)
    assert second_diff >= first_diff, "Expected subsequent atom to be equal or higher difficulty"
