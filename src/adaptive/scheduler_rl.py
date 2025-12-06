"""
Hierarchical Reinforcement Learning (HRL) Scheduler for Cortex.

Implements intelligent non-linear scheduling that:
1. Selects the optimal next atom based on cognitive state
2. Executes "Force Z" backtracking when prerequisites are missing
3. Adapts to real-time calendar changes
4. Balances learning objectives with fatigue management

Architecture:
- Meta-Controller: Weekly goal planning (which concepts to master)
- Micro-Controller: Moment-to-moment atom selection
- State Space: Knowledge state + Fatigue + Time context
- Reward Function: ΔKnowledge + Fluency - Fatigue - Offloading

The scheduler uses a modified MDP (Markov Decision Process) formulation
where states include learner cognitive state and actions are atom selections.

Based on research from:
- Dayan & Hinton (1993): Feudal Reinforcement Learning
- Kulkarni et al. (2016): Hierarchical Deep RL
- Deep Knowledge Tracing (Piech et al., 2015)
- Optimal Scheduling Theory

Author: Cortex System
Version: 2.0.0 (Neuromorphic Architecture)
"""
from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable, Optional
from uuid import UUID, uuid4

from loguru import logger

# Import from our modules
from src.adaptive.neuro_model import (
    CognitiveDiagnosis,
    CognitiveState,
    FailMode,
    compute_cognitive_load,
    compute_learning_reward,
)
from src.adaptive.persona_service import LearnerPersona
from src.adaptive.knowledge_graph import LearningAtom, KnowledgeGraph


# =============================================================================
# CONFIGURATION
# =============================================================================

# Reward function weights
REWARD_WEIGHTS = {
    "knowledge_gain": 0.4,
    "fluency": 0.3,
    "fatigue_penalty": 0.2,
    "offloading_penalty": 0.3,
}

# Scheduling parameters
MAX_SESSION_MINUTES = 90
OPTIMAL_SESSION_MINUTES = 25
FATIGUE_THRESHOLD = 0.7
FORCE_BREAK_THRESHOLD = 0.85
NEW_ATOM_PROBABILITY = 0.3
INTERLEAVING_PROBABILITY = 0.4

# Mastery thresholds
MASTERY_THRESHOLD = 0.85
PREREQUISITE_THRESHOLD = 0.65


# =============================================================================
# ENUMERATIONS
# =============================================================================

class SchedulerAction(str, Enum):
    """Actions the scheduler can take."""
    PRESENT_ATOM = "present_atom"         # Show next atom
    FORCE_PREREQUISITE = "force_prerequisite"  # Force Z backtracking
    SUGGEST_BREAK = "suggest_break"       # Cognitive fatigue
    END_SESSION = "end_session"           # Session complete
    SWITCH_MODALITY = "switch_modality"   # Change atom type
    PLM_DRILL = "plm_drill"               # Perceptual learning drill
    INTERLEAVE = "interleave"             # Switch topic for interleaving


class GoalType(str, Enum):
    """Types of learning goals."""
    MASTER_CONCEPT = "master_concept"     # Full mastery of a concept
    REVIEW_DUE = "review_due"             # Review due items
    STRENGTHEN_WEAK = "strengthen_weak"   # Strengthen weak areas
    EXPLORE_NEW = "explore_new"           # Learn new material
    MAINTAIN = "maintain"                 # Maintenance mode


# =============================================================================
# STATE REPRESENTATION
# =============================================================================

@dataclass
class SchedulerState:
    """
    Complete state for the scheduler MDP.

    Includes:
    - Knowledge state (mastery levels)
    - Cognitive state (fatigue, flow, etc.)
    - Session context (duration, items seen)
    - Calendar context (available time)
    """
    # Knowledge state
    concept_mastery: dict[str, float] = field(default_factory=dict)
    atom_due_count: int = 0
    atoms_seen_this_session: int = 0
    correct_this_session: int = 0

    # Cognitive state
    cognitive_load: float = 0.0
    fatigue_level: float = 0.0
    current_state: CognitiveState = CognitiveState.FLOW
    error_streak: int = 0
    fluency_rate: float = 0.0

    # Session context
    session_duration_minutes: float = 0.0
    session_start: Optional[datetime] = None
    last_break: Optional[datetime] = None

    # Calendar context
    available_minutes: float = 60.0
    is_peak_hour: bool = False
    next_calendar_event: Optional[datetime] = None

    # Recent history
    recent_atoms: list[str] = field(default_factory=list)
    recent_concepts: list[str] = field(default_factory=list)

    def to_vector(self) -> list[float]:
        """Convert state to numerical vector for RL."""
        return [
            self.cognitive_load,
            self.fatigue_level,
            float(self.current_state == CognitiveState.FLOW),
            float(self.current_state == CognitiveState.ANXIETY),
            float(self.current_state == CognitiveState.BOREDOM),
            self.error_streak / 10,  # Normalized
            self.fluency_rate,
            self.session_duration_minutes / MAX_SESSION_MINUTES,
            self.atoms_seen_this_session / 50,
            self.correct_this_session / max(1, self.atoms_seen_this_session),
            self.available_minutes / 60,
            float(self.is_peak_hour),
        ]


@dataclass
class SchedulerDecision:
    """A decision made by the scheduler."""
    action: SchedulerAction
    atom_id: Optional[str] = None
    atom: Optional[LearningAtom] = None
    reason: str = ""
    confidence: float = 0.5
    expected_reward: float = 0.0
    alternative_actions: list[dict] = field(default_factory=list)


# =============================================================================
# GOAL HIERARCHY
# =============================================================================

@dataclass
class LearningGoal:
    """A learning goal at any level of the hierarchy."""
    goal_id: str
    goal_type: GoalType
    target: str  # Concept ID or "review" etc.
    target_mastery: float = MASTERY_THRESHOLD
    priority: int = 1  # 1 = highest
    deadline: Optional[datetime] = None
    progress: float = 0.0
    status: str = "active"  # active, completed, abandoned

    @property
    def is_complete(self) -> bool:
        return self.progress >= self.target_mastery


# =============================================================================
# META-CONTROLLER (Weekly Planning)
# =============================================================================

class MetaController:
    """
    High-level goal planning (operates on weekly/daily scale).

    Decides WHAT to learn, not HOW to learn it.
    Sets goals for the Micro-Controller to execute.
    """

    def __init__(self, persona: LearnerPersona):
        self.persona = persona
        self.active_goals: list[LearningGoal] = []
        self.completed_goals: list[LearningGoal] = []

    def plan_session(
        self,
        available_minutes: float,
        concept_mastery: dict[str, float],
        due_atoms: int,
        is_peak_hour: bool,
    ) -> list[LearningGoal]:
        """
        Plan goals for a study session.

        Returns ordered list of goals to pursue.
        """
        goals = []

        # Goal 1: Review due items (always important)
        if due_atoms > 0:
            goals.append(LearningGoal(
                goal_id=str(uuid4()),
                goal_type=GoalType.REVIEW_DUE,
                target="due_items",
                target_mastery=0.85,
                priority=1,
            ))

        # Goal 2: Strengthen weak concepts
        weak_concepts = [
            cid for cid, mastery in concept_mastery.items()
            if mastery < 0.65
        ]
        if weak_concepts:
            # Pick weakest
            weakest = min(weak_concepts, key=lambda c: concept_mastery[c])
            goals.append(LearningGoal(
                goal_id=str(uuid4()),
                goal_type=GoalType.STRENGTHEN_WEAK,
                target=weakest,
                target_mastery=0.65,
                priority=2,
            ))

        # Goal 3: Explore new (if at peak hour and time available)
        if is_peak_hour and available_minutes > 30:
            goals.append(LearningGoal(
                goal_id=str(uuid4()),
                goal_type=GoalType.EXPLORE_NEW,
                target="new_material",
                priority=3,
            ))

        # Sort by priority
        goals.sort(key=lambda g: g.priority)

        self.active_goals = goals
        return goals

    def update_progress(self, goal_id: str, progress: float) -> None:
        """Update progress on a goal."""
        for goal in self.active_goals:
            if goal.goal_id == goal_id:
                goal.progress = progress
                if goal.is_complete:
                    goal.status = "completed"
                    self.completed_goals.append(goal)
                    self.active_goals.remove(goal)
                break


# =============================================================================
# MICRO-CONTROLLER (Atom-by-Atom Selection)
# =============================================================================

class MicroController:
    """
    Moment-to-moment atom selection (operates on second scale).

    Decides WHICH atom to present next based on:
    - Current cognitive state
    - Meta-Controller goals
    - Knowledge graph structure
    - Fatigue levels
    """

    def __init__(
        self,
        knowledge_graph: KnowledgeGraph,
        persona: LearnerPersona,
    ):
        self.graph = knowledge_graph
        self.persona = persona
        self._action_history: list[SchedulerDecision] = []

    def select_next_atom(
        self,
        state: SchedulerState,
        goals: list[LearningGoal],
        available_atoms: list[LearningAtom],
    ) -> SchedulerDecision:
        """
        Select the next atom to present.

        This is the core decision function of the scheduler.

        Args:
            state: Current scheduler state
            goals: Active learning goals from Meta-Controller
            available_atoms: Pool of atoms to choose from

        Returns:
            SchedulerDecision with selected action and atom
        """
        # Check termination conditions first
        termination = self._check_termination(state)
        if termination:
            return termination

        # Check for fatigue
        if state.fatigue_level > FATIGUE_THRESHOLD:
            return SchedulerDecision(
                action=SchedulerAction.SUGGEST_BREAK,
                reason=f"Fatigue level {state.fatigue_level:.0%} exceeds threshold",
                confidence=0.9,
            )

        if state.fatigue_level > FORCE_BREAK_THRESHOLD:
            return SchedulerDecision(
                action=SchedulerAction.END_SESSION,
                reason=f"Critical fatigue level {state.fatigue_level:.0%}",
                confidence=0.95,
            )

        # No atoms available
        if not available_atoms:
            return SchedulerDecision(
                action=SchedulerAction.END_SESSION,
                reason="No atoms available",
                confidence=1.0,
            )

        # Get current goal
        current_goal = goals[0] if goals else None

        # === FORCE Z LOGIC ===
        # Check if current atom requires unmastered prerequisites
        force_z_decision = self._check_force_z(state, available_atoms)
        if force_z_decision:
            return force_z_decision

        # === ATOM SELECTION ===
        # Score all available atoms
        scored_atoms = self._score_atoms(state, available_atoms, current_goal)

        # Apply exploration/exploitation balance
        selected = self._select_with_exploration(scored_atoms, state)

        if selected is None:
            return SchedulerDecision(
                action=SchedulerAction.END_SESSION,
                reason="No suitable atoms found",
                confidence=0.5,
            )

        atom, score, reason = selected

        return SchedulerDecision(
            action=SchedulerAction.PRESENT_ATOM,
            atom_id=atom.id,
            atom=atom,
            reason=reason,
            confidence=min(0.95, score),
            expected_reward=self._estimate_reward(atom, state),
            alternative_actions=self._get_alternatives(scored_atoms[:5]),
        )

    def _check_termination(self, state: SchedulerState) -> Optional[SchedulerDecision]:
        """Check if session should end."""
        # Time limit
        if state.session_duration_minutes >= MAX_SESSION_MINUTES:
            return SchedulerDecision(
                action=SchedulerAction.END_SESSION,
                reason=f"Session reached {MAX_SESSION_MINUTES} minute limit",
                confidence=1.0,
            )

        # Calendar conflict
        if state.next_calendar_event:
            minutes_until = (state.next_calendar_event - datetime.now()).total_seconds() / 60
            if minutes_until < 5:
                return SchedulerDecision(
                    action=SchedulerAction.END_SESSION,
                    reason=f"Calendar event in {minutes_until:.0f} minutes",
                    confidence=0.95,
                )

        return None

    def _check_force_z(
        self,
        state: SchedulerState,
        available_atoms: list[LearningAtom],
    ) -> Optional[SchedulerDecision]:
        """
        Check if "Force Z" backtracking is needed.

        If we're trying to learn X but prerequisite Z is missing,
        force the learner to do Z first.
        """
        for atom in available_atoms[:5]:  # Check top candidates
            prereqs = self.graph.get_prerequisites(atom.id)

            for prereq in prereqs:
                prereq_concept = prereq.concept_id
                if prereq_concept:
                    mastery = state.concept_mastery.get(prereq_concept, 0)

                    if mastery < PREREQUISITE_THRESHOLD:
                        # Found a missing prerequisite - Force Z!
                        logger.info(
                            f"Force Z: {atom.concept_name} requires "
                            f"{prereq.concept_name} (mastery: {mastery:.0%})"
                        )

                        return SchedulerDecision(
                            action=SchedulerAction.FORCE_PREREQUISITE,
                            atom_id=prereq.id,
                            atom=prereq,
                            reason=(
                                f"Prerequisite gap detected: {prereq.concept_name} "
                                f"(mastery {mastery:.0%}) needed before {atom.concept_name}"
                            ),
                            confidence=0.9,
                        )

        return None

    def _score_atoms(
        self,
        state: SchedulerState,
        atoms: list[LearningAtom],
        goal: Optional[LearningGoal],
    ) -> list[tuple[LearningAtom, float, str]]:
        """
        Score all atoms for selection.

        Returns list of (atom, score, reason) tuples, sorted by score.
        """
        scored = []

        for atom in atoms:
            score = 0.0
            reasons = []

            # Factor 1: Goal alignment
            if goal:
                if goal.goal_type == GoalType.REVIEW_DUE and atom.review_count > 0:
                    score += 0.3
                    reasons.append("due for review")
                elif goal.goal_type == GoalType.STRENGTHEN_WEAK:
                    if atom.concept_id == goal.target:
                        score += 0.4
                        reasons.append("matches weak concept goal")
                elif goal.goal_type == GoalType.EXPLORE_NEW and atom.review_count == 0:
                    score += 0.3
                    reasons.append("new material")

            # Factor 2: Cognitive load match
            if atom.metadata.intrinsic_load <= (1 - state.fatigue_level):
                score += 0.2
                reasons.append("appropriate difficulty")
            else:
                score -= 0.1
                reasons.append("may be too difficult given fatigue")

            # Factor 3: Interleaving bonus
            if atom.concept_id not in state.recent_concepts[-3:]:
                if random.random() < INTERLEAVING_PROBABILITY:
                    score += 0.15
                    reasons.append("interleaving benefit")

            # Factor 4: Spacing effect
            if atom.id not in state.recent_atoms[-10:]:
                score += 0.1
                reasons.append("spacing effect")

            # Factor 5: ps_index consideration
            if state.current_state == CognitiveState.FLOW:
                # In flow, can handle high ps_index
                if atom.ps_index > 0.7:
                    score += 0.1
                    reasons.append("discrimination practice")
            else:
                # Not in flow, avoid confusable items
                if atom.ps_index > 0.8:
                    score -= 0.2
                    reasons.append("too confusable for current state")

            # Factor 6: FSRS priority
            if atom.stability and atom.stability < 1:
                score += 0.2
                reasons.append("low stability - needs reinforcement")

            scored.append((atom, score, "; ".join(reasons)))

        # Sort by score descending
        scored.sort(key=lambda x: -x[1])
        return scored

    def _select_with_exploration(
        self,
        scored_atoms: list[tuple[LearningAtom, float, str]],
        state: SchedulerState,
    ) -> Optional[tuple[LearningAtom, float, str]]:
        """
        Select atom with exploration/exploitation balance.

        Uses softmax selection with temperature based on session state.
        """
        if not scored_atoms:
            return None

        # Temperature: higher early in session, lower when fatigued
        temperature = max(0.1, 1.0 - state.fatigue_level - state.session_duration_minutes / 100)

        # Softmax probabilities
        scores = [s[1] for s in scored_atoms[:10]]  # Top 10
        max_score = max(scores) if scores else 0
        exp_scores = [math.exp((s - max_score) / temperature) for s in scores]
        sum_exp = sum(exp_scores)
        probs = [e / sum_exp for e in exp_scores]

        # Sample
        r = random.random()
        cumulative = 0
        for i, p in enumerate(probs):
            cumulative += p
            if r < cumulative:
                return scored_atoms[i]

        return scored_atoms[0]  # Fallback to best

    def _estimate_reward(self, atom: LearningAtom, state: SchedulerState) -> float:
        """Estimate expected reward for selecting this atom."""
        # Simple estimation based on current state
        base_reward = 0.5

        # Knowledge gain potential
        if atom.review_count < 3:
            base_reward += 0.2  # New item = more learning

        # Fluency potential
        if atom.stability and atom.stability > 10:
            base_reward += 0.1  # Already stable = fluency practice

        # Fatigue penalty
        base_reward -= state.fatigue_level * 0.3

        return base_reward

    def _get_alternatives(
        self,
        scored_atoms: list[tuple[LearningAtom, float, str]],
    ) -> list[dict]:
        """Get alternative actions for transparency."""
        return [
            {
                "atom_id": atom.id,
                "atom_name": atom.concept_name,
                "score": round(score, 3),
                "reason": reason,
            }
            for atom, score, reason in scored_atoms[1:4]  # Skip first (selected)
        ]


# =============================================================================
# MAIN SCHEDULER
# =============================================================================

class HRLScheduler:
    """
    Main Hierarchical RL Scheduler.

    Coordinates Meta-Controller (goals) and Micro-Controller (atom selection)
    to provide intelligent, adaptive learning scheduling.
    """

    def __init__(
        self,
        knowledge_graph: KnowledgeGraph,
        persona: LearnerPersona,
    ):
        self.graph = knowledge_graph
        self.persona = persona
        self.meta = MetaController(persona)
        self.micro = MicroController(knowledge_graph, persona)

        # Session state
        self.state = SchedulerState()
        self.session_active = False

        # Metrics
        self.total_rewards: list[float] = []
        self.decisions: list[SchedulerDecision] = []

    def start_session(
        self,
        available_minutes: float = 60,
        is_peak_hour: Optional[bool] = None,
        concept_mastery: Optional[dict[str, float]] = None,
        due_atoms: int = 0,
    ) -> list[LearningGoal]:
        """
        Start a new learning session.

        Returns the planned goals for the session.
        """
        # Infer peak hour if not provided
        if is_peak_hour is None:
            current_hour = datetime.now().hour
            is_peak_hour = current_hour == self.persona.peak_performance_hour

        # Initialize state
        self.state = SchedulerState(
            concept_mastery=concept_mastery or {},
            atom_due_count=due_atoms,
            session_start=datetime.now(),
            available_minutes=available_minutes,
            is_peak_hour=is_peak_hour,
        )

        self.session_active = True
        self.decisions = []

        # Plan session goals
        goals = self.meta.plan_session(
            available_minutes=available_minutes,
            concept_mastery=concept_mastery or {},
            due_atoms=due_atoms,
            is_peak_hour=is_peak_hour,
        )

        logger.info(
            f"Session started: {available_minutes}min available, "
            f"{len(goals)} goals planned, peak_hour={is_peak_hour}"
        )

        return goals

    def get_next(
        self,
        available_atoms: list[LearningAtom],
    ) -> SchedulerDecision:
        """
        Get the next scheduling decision.

        This is the main entry point during a session.

        Args:
            available_atoms: Pool of atoms to choose from

        Returns:
            SchedulerDecision with action and optional atom
        """
        if not self.session_active:
            return SchedulerDecision(
                action=SchedulerAction.END_SESSION,
                reason="No active session",
                confidence=1.0,
            )

        # Update session duration
        if self.state.session_start:
            elapsed = (datetime.now() - self.state.session_start).total_seconds()
            self.state.session_duration_minutes = elapsed / 60

        # Get decision from Micro-Controller
        decision = self.micro.select_next_atom(
            state=self.state,
            goals=self.meta.active_goals,
            available_atoms=available_atoms,
        )

        # Track decision
        self.decisions.append(decision)

        # Handle session-ending actions
        if decision.action in (SchedulerAction.END_SESSION, SchedulerAction.SUGGEST_BREAK):
            if decision.action == SchedulerAction.END_SESSION:
                self.session_active = False

        return decision

    def record_response(
        self,
        atom_id: str,
        is_correct: bool,
        response_time_ms: int,
        diagnosis: CognitiveDiagnosis,
    ) -> float:
        """
        Record response to an atom and update state.

        Returns the reward for this interaction.
        """
        # Update session stats
        self.state.atoms_seen_this_session += 1
        if is_correct:
            self.state.correct_this_session += 1
            self.state.error_streak = 0
        else:
            self.state.error_streak += 1

        # Update cognitive state
        self.state.current_state = diagnosis.cognitive_state
        self.state.cognitive_load = compute_cognitive_load(
            session_history=[],  # Would include real history
            session_duration_seconds=int(self.state.session_duration_minutes * 60),
        ).load_percent / 100

        # Update fatigue estimate
        self._update_fatigue(diagnosis)

        # Update recent tracking
        self.state.recent_atoms.append(atom_id)
        self.state.recent_atoms = self.state.recent_atoms[-20:]

        # Compute reward
        delta_knowledge = 0.02 if is_correct else -0.01
        fluency_score = 1.0 if response_time_ms < 2000 and is_correct else 0.5

        reward = compute_learning_reward(
            diagnosis=diagnosis,
            delta_knowledge=delta_knowledge,
            fluency_score=fluency_score,
            fatigue_level=self.state.fatigue_level,
            offloading_detected=False,  # Would come from tutor
        )

        self.total_rewards.append(reward)

        return reward

    def _update_fatigue(self, diagnosis: CognitiveDiagnosis) -> None:
        """Update fatigue estimate based on diagnosis."""
        # Fatigue increases with time and errors
        time_factor = self.state.session_duration_minutes / MAX_SESSION_MINUTES
        error_factor = self.state.error_streak / 10

        # Base fatigue
        new_fatigue = 0.1 + time_factor * 0.3 + error_factor * 0.3

        # Cognitive state adjustments
        if diagnosis.cognitive_state == CognitiveState.FATIGUE:
            new_fatigue += 0.2
        elif diagnosis.cognitive_state == CognitiveState.FLOW:
            new_fatigue -= 0.1

        # EMA update
        alpha = 0.2
        self.state.fatigue_level = (
            self.state.fatigue_level * (1 - alpha) +
            max(0, min(1, new_fatigue)) * alpha
        )

    def end_session(self) -> dict[str, Any]:
        """
        End the current session and return summary.
        """
        self.session_active = False

        summary = {
            "duration_minutes": self.state.session_duration_minutes,
            "atoms_seen": self.state.atoms_seen_this_session,
            "correct": self.state.correct_this_session,
            "accuracy": (
                self.state.correct_this_session / self.state.atoms_seen_this_session
                if self.state.atoms_seen_this_session > 0 else 0
            ),
            "total_reward": sum(self.total_rewards),
            "avg_reward": (
                sum(self.total_rewards) / len(self.total_rewards)
                if self.total_rewards else 0
            ),
            "final_fatigue": self.state.fatigue_level,
            "goals_completed": [
                g.target for g in self.meta.completed_goals
            ],
            "decisions_count": len(self.decisions),
        }

        logger.info(f"Session ended: {summary}")

        return summary

    def get_schedule_suggestion(
        self,
        available_hours: list[int],
        target_study_minutes: int = 60,
    ) -> list[dict[str, Any]]:
        """
        Suggest optimal study schedule based on chronotype.

        Returns list of suggested time blocks.
        """
        suggestions = []

        # Sort hours by expected performance
        peak = self.persona.peak_performance_hour
        low_energy = set(self.persona.low_energy_hours)

        def hour_score(h: int) -> float:
            if h in low_energy:
                return 0.3
            distance_from_peak = min(abs(h - peak), 24 - abs(h - peak))
            return max(0.5, 1.0 - distance_from_peak * 0.1)

        scored_hours = [(h, hour_score(h)) for h in available_hours if h not in low_energy]
        scored_hours.sort(key=lambda x: -x[1])

        # Allocate time blocks
        remaining_minutes = target_study_minutes
        for hour, score in scored_hours:
            if remaining_minutes <= 0:
                break

            block_minutes = min(OPTIMAL_SESSION_MINUTES, remaining_minutes)

            suggestions.append({
                "hour": hour,
                "duration_minutes": block_minutes,
                "expected_performance": round(score, 2),
                "task_type": "deep_work" if score > 0.8 else "review",
            })

            remaining_minutes -= block_minutes

        return suggestions


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================

# Global scheduler instance
_scheduler: Optional[HRLScheduler] = None


def get_scheduler(
    knowledge_graph: Optional[KnowledgeGraph] = None,
    persona: Optional[LearnerPersona] = None,
) -> HRLScheduler:
    """Get or create the global scheduler."""
    global _scheduler
    if _scheduler is None:
        from src.adaptive.knowledge_graph import get_knowledge_graph
        from src.adaptive.persona_service import get_default_persona

        _scheduler = HRLScheduler(
            knowledge_graph=knowledge_graph or get_knowledge_graph(),
            persona=persona or get_default_persona(),
        )
    return _scheduler


def should_force_z(
    target_concept: str,
    concept_mastery: dict[str, float],
    prerequisite_map: dict[str, list[str]],
) -> Optional[str]:
    """
    Quick check if Force Z backtracking is needed.

    Returns the prerequisite concept to force, or None.
    """
    prereqs = prerequisite_map.get(target_concept, [])

    for prereq in prereqs:
        mastery = concept_mastery.get(prereq, 0)
        if mastery < PREREQUISITE_THRESHOLD:
            return prereq

    return None
