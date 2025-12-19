"""
Unit tests for PathSequencer mastery and remediation helpers.

Focused on the stateless utilities so these tests do not require a DB.
"""

from uuid import UUID

from src.adaptive.path_sequencer import PathSequencer


class TestMasteryDecision:
    def test_consecutive_correct_without_hints_mastered(self):
        outcomes = [
            {"correct": False, "hint_used": False},
            {"correct": True, "hint_used": False},
            {"correct": True, "hint_used": False},
            {"correct": True, "hint_used": False},
        ]
        assert PathSequencer.compute_mastery_decision(outcomes) is True

    def test_consecutive_broken_not_mastered(self):
        outcomes = [
            {"correct": True, "hint_used": False},
            {"correct": False, "hint_used": False},
            {"correct": True, "hint_used": False},
            {"correct": True, "hint_used": False},
        ]
        assert PathSequencer.compute_mastery_decision(outcomes) is False

    def test_rolling_accuracy_mastered(self):
        # 4/5 correct in last window meets 0.85 threshold (0.8 < 0.85, so ensure 5/5)
        outcomes = [
            {"correct": False, "hint_used": False},
            {"correct": True, "hint_used": True},
            {"correct": True, "hint_used": False},
            {"correct": True, "hint_used": False},
            {"correct": True, "hint_used": False},
            {"correct": True, "hint_used": False},
        ]
        # Last 5 are all correct → accuracy 1.0
        assert PathSequencer.compute_mastery_decision(outcomes) is True


class TestNeedsRemediation:
    def test_two_consecutive_failures_triggers_remediation(self):
        outcomes = [
            {"correct": True},
            {"correct": False},
            {"correct": False},
        ]
        assert PathSequencer.needs_remediation(outcomes) is True

    def test_non_consecutive_failures_no_remediation(self):
        outcomes = [
            {"correct": False},
            {"correct": True},
            {"correct": False},
        ]
        assert PathSequencer.needs_remediation(outcomes) is False


class TestPrerequisiteGating:
    def test_prerequisites_satisfied_when_all_mastered(self):
        a1, a2 = UUID(int=1), UUID(int=2)
        prereq_map = {a2: [a1]}
        mastered = {a1}
        assert PathSequencer.prerequisites_satisfied(a2, mastered, prereq_map) is True

    def test_apply_prerequisite_gating_filters_locked_atoms(self):
        a1, a2, a3 = UUID(int=1), UUID(int=2), UUID(int=3)
        prereq_map = {a2: [a1], a3: [a1, a2]}
        mastered = {a1}
        atoms = [a1, a2, a3]
        gated = PathSequencer._apply_prerequisite_gating(atoms, mastered, prereq_map)
        assert gated == [a1, a2]


class StubSequencer(PathSequencer):
    def __init__(self, new_atoms: list[UUID] | None = None, remediation_atoms: list[UUID] | None = None):
        super().__init__(session=None)
        self._new_atoms = new_atoms or []
        self._remediation_atoms = remediation_atoms or []

    def _get_new_atoms(self, *args, **kwargs):
        return list(self._new_atoms)

    def _interleave_atoms(self, session, atom_ids):
        # Keep order stable for unit tests
        return atom_ids

    def plan_remediation_bundle(self, *args, **kwargs):
        return list(self._remediation_atoms)


class TestSequencerOrdering:
    def test_due_reviews_are_injected_before_new_atoms(self):
        new_atoms = [UUID(int=10), UUID(int=11)]
        seq = StubSequencer(new_atoms=new_atoms)
        due_queue = [UUID(int=1), UUID(int=2)]

        atoms = seq.get_next_atoms(
            learner_id="bob",
            count=3,
            include_review=True,
            due_review_queue=due_queue,
        )

        assert atoms[:2] == [UUID(int=1), UUID(int=2)]
        # Queue should be consumed
        assert due_queue == []
        # New atoms are appended after reviews
        assert atoms[2] == UUID(int=10)

    def test_remediation_bundle_precedes_new_atoms_on_struggle(self):
        remediation = [UUID(int=99)]
        new_atoms = [UUID(int=10)]
        seq = StubSequencer(new_atoms=new_atoms, remediation_atoms=remediation)
        outcomes = [{"correct": False}, {"correct": False}]

        atoms = seq.get_next_atoms(
            learner_id="bob",
            concept_id=UUID(int=5),
            count=2,
            include_review=False,
            recent_outcomes=outcomes,
        )

        assert atoms[0] == UUID(int=99)
        assert atoms[1] == UUID(int=10)
