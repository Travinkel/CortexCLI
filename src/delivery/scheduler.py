"""
SM-2 Spaced Repetition Scheduler with Interleaving.

Implements:
- SM-2 algorithm for optimal review intervals
- Interleaved scheduling to prevent context collapse
- Adaptive new card introduction

SM-2 Grade Scale:
0 - Complete blackout, wrong response
1 - Incorrect, but upon seeing answer remembered
2 - Incorrect, but answer seemed easy to recall
3 - Correct, but with significant difficulty
4 - Correct, with some hesitation
5 - Correct, with perfect recall
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta

from loguru import logger

from .atom_deck import Atom, AtomDeck
from .state_store import SM2State, StateStore

# =============================================================================
# SM-2 Algorithm
# =============================================================================


@dataclass
class SM2Config:
    """Configuration for SM-2 algorithm."""

    initial_easiness: float = 2.5
    minimum_easiness: float = 1.3
    first_interval: int = 1  # Days for first review
    second_interval: int = 6  # Days for second review


class SM2Scheduler:
    """
    Implements the SM-2 spaced repetition algorithm.

    The SuperMemo 2 algorithm calculates optimal review intervals
    based on performance history. Each atom has:
    - Easiness Factor (EF): How easy the item is (2.5 default, min 1.3)
    - Interval: Days until next review
    - Repetitions: Consecutive correct recalls
    """

    def __init__(self, config: SM2Config | None = None):
        """
        Initialize SM-2 scheduler.

        Args:
            config: Custom configuration (uses defaults if None)
        """
        self.config = config or SM2Config()

    def calculate_next_review(
        self,
        state: SM2State,
        grade: int,
    ) -> SM2State:
        """
        Calculate next review date based on grade.

        Args:
            state: Current SM2 state for the atom
            grade: User grade (0-5)

        Returns:
            Updated SM2State with new interval and next_review
        """
        # Update easiness factor
        # EF' = EF + (0.1 - (5 - q) * (0.08 + (5 - q) * 0.02))
        ef_delta = 0.1 - (5 - grade) * (0.08 + (5 - grade) * 0.02)
        new_ef = max(self.config.minimum_easiness, state.easiness_factor + ef_delta)

        # Determine repetitions and interval
        if grade < 3:
            # Failed - reset to beginning
            new_repetitions = 0
            new_interval = self.config.first_interval
        else:
            # Passed - advance
            new_repetitions = state.repetitions + 1

            if new_repetitions == 1:
                new_interval = self.config.first_interval
            elif new_repetitions == 2:
                new_interval = self.config.second_interval
            else:
                new_interval = round(state.interval_days * new_ef)

        # Calculate next review date
        next_review = date.today() + timedelta(days=new_interval)

        return SM2State(
            atom_id=state.atom_id,
            easiness_factor=new_ef,
            interval_days=new_interval,
            repetitions=new_repetitions,
            next_review=next_review,
            last_reviewed=datetime.now(),
        )

    def grade_from_response(
        self,
        is_correct: bool,
        response_ms: int,
        expected_ms: int = 10000,
    ) -> int:
        """
        Convert a response to an SM-2 grade.

        Args:
            is_correct: Whether the answer was correct
            response_ms: Time taken to respond
            expected_ms: Expected response time

        Returns:
            Grade 0-5
        """
        if not is_correct:
            # Incorrect responses: 0-2
            if response_ms < expected_ms * 0.5:
                return 2  # Quick wrong = almost knew it
            elif response_ms < expected_ms:
                return 1  # Wrong but remembered when shown
            else:
                return 0  # Complete blackout

        # Correct responses: 3-5
        if response_ms < expected_ms * 0.5:
            return 5  # Quick and correct = perfect recall
        elif response_ms < expected_ms:
            return 4  # Correct with some hesitation
        else:
            return 3  # Correct but struggled


# =============================================================================
# Interleave Scheduler
# =============================================================================


@dataclass
class InterleaveConfig:
    """Configuration for interleaved scheduling."""

    new_cards_per_session: int = 30
    max_due_cards: int = 100
    max_consecutive_same_module: int = 2
    max_consecutive_same_type: int = 3
    due_priority_weight: float = 2.0  # Due cards are 2x priority


@dataclass
class StudySession:
    """A prepared study session."""

    due_atoms: list[Atom] = field(default_factory=list)
    new_atoms: list[Atom] = field(default_factory=list)
    interleaved_queue: list[Atom] = field(default_factory=list)

    @property
    def total_cards(self) -> int:
        return len(self.interleaved_queue)

    @property
    def estimated_minutes(self) -> int:
        """Estimate study time (30 sec per card average)."""
        return max(1, self.total_cards // 2)


class InterleaveScheduler:
    """
    Builds study sessions with interleaved atoms.

    Key principles:
    1. Due cards always come first (spaced repetition priority)
    2. New cards fill remaining quota
    3. Never 3+ consecutive cards from same module (context switching)
    4. Mix atom types for variety
    """

    def __init__(
        self,
        deck: AtomDeck,
        store: StateStore,
        sm2: SM2Scheduler | None = None,
        config: InterleaveConfig | None = None,
    ):
        """
        Initialize the scheduler.

        Args:
            deck: AtomDeck with loaded atoms
            store: StateStore for review state
            sm2: SM2Scheduler (creates default if None)
            config: Scheduling configuration
        """
        self.deck = deck
        self.store = store
        self.sm2 = sm2 or SM2Scheduler()
        self.config = config or InterleaveConfig()

    def build_session(self) -> StudySession:
        """
        Build a study session for today.

        Returns:
            StudySession with interleaved queue
        """
        session = StudySession()

        # 1. Get due cards
        due_ids = self.store.get_due_atom_ids(limit=self.config.max_due_cards)
        session.due_atoms = self.deck.get_by_ids(due_ids)

        logger.debug(f"Found {len(session.due_atoms)} due atoms")

        # 2. Get new cards
        reviewed_ids = self.store.get_reviewed_atom_ids()
        new_atoms = self.deck.filter_new(reviewed_ids)

        # Limit new cards
        max_new = self.config.new_cards_per_session - len(session.due_atoms)
        max_new = max(0, max_new)

        # Sort new by difficulty (easier first for better learning curve)
        new_atoms.sort(key=lambda a: (a.difficulty, a.module_number))
        session.new_atoms = new_atoms[:max_new]

        logger.debug(f"Selected {len(session.new_atoms)} new atoms")

        # 3. Interleave the queue
        session.interleaved_queue = self._interleave(
            session.due_atoms,
            session.new_atoms,
        )

        logger.info(
            f"Session built: {len(session.due_atoms)} due + "
            f"{len(session.new_atoms)} new = {session.total_cards} cards "
            f"(~{session.estimated_minutes} min)"
        )

        return session

    def _interleave(
        self,
        due: list[Atom],
        new: list[Atom],
    ) -> list[Atom]:
        """
        Interleave due and new atoms for optimal learning.

        Strategy:
        - Start with due cards (spacing priority)
        - Mix in new cards
        - Ensure no 3+ consecutive from same module
        - Randomize within constraints
        """
        result: list[Atom] = []

        # Shuffle due cards to avoid predictable order
        due_shuffled = due.copy()
        random.shuffle(due_shuffled)

        # Shuffle new cards
        new_shuffled = new.copy()
        random.shuffle(new_shuffled)

        # Merge with due cards taking priority
        due_queue = list(due_shuffled)
        new_queue = list(new_shuffled)

        # Interleaving ratio: 2 due : 1 new
        due_batch = 2
        new_batch = 1

        while due_queue or new_queue:
            # Take due cards
            for _ in range(due_batch):
                if due_queue:
                    result.append(due_queue.pop(0))

            # Take new cards
            for _ in range(new_batch):
                if new_queue:
                    result.append(new_queue.pop(0))

        # Apply context-switching constraints
        result = self._apply_interleave_constraints(result)

        return result

    def _apply_interleave_constraints(self, queue: list[Atom]) -> list[Atom]:
        """
        Apply interleaving constraints to prevent context collapse.

        Ensures no more than N consecutive atoms from:
        - Same module
        - Same atom type
        """
        if len(queue) <= 1:
            return queue

        result: list[Atom] = []
        remaining = queue.copy()

        while remaining:
            # Find next valid atom
            found = False

            for i, atom in enumerate(remaining):
                if self._can_add(result, atom):
                    result.append(remaining.pop(i))
                    found = True
                    break

            if not found:
                # No valid option - just add the first one
                result.append(remaining.pop(0))

        return result

    def _can_add(self, queue: list[Atom], atom: Atom) -> bool:
        """Check if atom can be added without violating constraints."""
        if len(queue) < 2:
            return True

        # Check consecutive module constraint
        recent_modules = [
            a.module_number for a in queue[-self.config.max_consecutive_same_module :]
        ]
        if len(recent_modules) >= self.config.max_consecutive_same_module:
            if all(m == atom.module_number for m in recent_modules):
                return False

        # Check consecutive type constraint
        recent_types = [a.atom_type for a in queue[-self.config.max_consecutive_same_type :]]
        if len(recent_types) >= self.config.max_consecutive_same_type:
            if all(t == atom.atom_type for t in recent_types):
                return False

        return True

    def record_review(
        self,
        atom: Atom,
        grade: int,
        response_ms: int,
        confidence: int | None = None,
    ) -> SM2State:
        """
        Record a review and update scheduling state.

        Args:
            atom: The reviewed atom
            grade: SM-2 grade (0-5)
            response_ms: Time to answer in ms
            confidence: Optional self-reported confidence

        Returns:
            Updated SM2State
        """
        # Get current state
        current_state = self.store.get_sm2_state(atom.id)

        # Calculate next review
        new_state = self.sm2.calculate_next_review(current_state, grade)

        # Persist
        self.store.save_sm2_state(new_state)
        self.store.log_review(atom.id, grade, response_ms, confidence)

        logger.debug(
            f"Recorded review for {atom.id}: grade={grade}, "
            f"next_review={new_state.next_review}, interval={new_state.interval_days}d"
        )

        return new_state

    def get_queue_preview(self, limit: int = 10) -> list[tuple[str, str, str]]:
        """
        Get a preview of upcoming cards.

        Returns:
            List of (atom_id, atom_type, status) tuples
        """
        session = self.build_session()
        preview = []

        for atom in session.interleaved_queue[:limit]:
            state = self.store.get_sm2_state(atom.id)
            status = "due" if state.is_due else "new"
            preview.append((atom.id, atom.atom_type, status))

        return preview
