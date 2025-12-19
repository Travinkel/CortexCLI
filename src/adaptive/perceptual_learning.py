"""
Perceptual Learning Module (PLM) for Cortex.

Implements rapid pattern recognition training to develop mathematical intuition.
Unlike conceptual instruction, PLMs train the visual cortex to classify
mathematical structures automatically (<1000ms) through high-volume practice.

Key Concepts:
- Perceptual Fluency: Rapid, effortless recognition of patterns
- Pattern Separation: Distinguishing similar-looking structures
- Automaticity: Processing without conscious effort
- RSVP: Rapid Serial Visual Presentation for training

Training Types:
1. Classification: "Is this a chain rule or product rule?"
2. Completion: "What's the missing step?"
3. Discrimination: "Which integral requires substitution?"
4. Ordering: "Which should be solved first?"

Based on research from:
- Kellman & Garrigan (2009): Perceptual Learning and Human Expertise
- Gibson (1969): Principles of Perceptual Learning
- Goldstone (1998): Perceptual Learning
- Kellman et al. (2010): PLMs in Education

Author: Cortex System
Version: 2.0.0 (Neuromorphic Architecture)
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any
from uuid import uuid4

from loguru import logger

# =============================================================================
# CONFIGURATION
# =============================================================================

# PLM thresholds (milliseconds)
PLM_TARGET_MS = 1000  # Target response time for fluency
PLM_FAST_MS = 500  # Exceptionally fast (automatic)
PLM_SLOW_MS = 3000  # Too slow for perceptual learning
PLM_TIMEOUT_MS = 5000  # Maximum allowed time

# Training parameters
MIN_TRIALS_FOR_MASTERY = 20
MASTERY_ACCURACY = 0.9  # 90% accuracy required
MASTERY_SPEED_RATE = 0.8  # 80% under target time
BLOCK_SIZE = 10  # Trials per block
REST_AFTER_BLOCKS = 3  # Suggest rest after N blocks

# Interleaving parameters
MIN_CATEGORIES = 2  # Minimum categories to interleave
MAX_CATEGORIES = 5  # Maximum categories per session


# =============================================================================
# ENUMERATIONS
# =============================================================================


class PLMTaskType(str, Enum):
    """Types of perceptual learning tasks."""

    CLASSIFICATION = "classification"  # Classify into category
    DISCRIMINATION = "discrimination"  # Is this X or Y?
    COMPLETION = "completion"  # Fill in the missing part
    ORDERING = "ordering"  # Sequence/priority ordering
    MATCHING = "matching"  # Match related items


class PLMDifficulty(str, Enum):
    """Difficulty levels for PLM tasks."""

    EASY = "easy"  # High distinctiveness
    MEDIUM = "medium"  # Moderate overlap
    HARD = "hard"  # Adversarial lures
    ADAPTIVE = "adaptive"  # System-selected


class FluencyLevel(str, Enum):
    """Fluency classification based on response patterns."""

    AUTOMATIC = "automatic"  # <500ms, very high accuracy
    FLUENT = "fluent"  # <1000ms, high accuracy
    DEVELOPING = "developing"  # <2000ms, good accuracy
    EFFORTFUL = "effortful"  # >2000ms, any accuracy
    STRUGGLING = "struggling"  # High error rate


# =============================================================================
# DATA CLASSES
# =============================================================================


@dataclass
class PLMStimulus:
    """
    A single stimulus for perceptual learning.

    Represents one item to be classified/discriminated.
    """

    id: str
    content: str  # The visual content (e.g., equation)
    content_latex: str | None = None  # LaTeX version
    category: str = ""  # Correct category
    category_id: str | None = None
    confusable_with: list[str] = field(default_factory=list)  # Similar categories
    ps_index: float = 0.5  # Pattern separation difficulty
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "content": self.content,
            "content_latex": self.content_latex,
            "category": self.category,
            "ps_index": self.ps_index,
        }


@dataclass
class PLMTrial:
    """
    A single PLM trial (one question-response pair).
    """

    stimulus: PLMStimulus
    options: list[str]  # Available responses
    correct_response: str
    task_type: PLMTaskType
    difficulty: PLMDifficulty

    # Response data
    response: str | None = None
    response_time_ms: int = 0
    is_correct: bool = False
    timestamp: datetime | None = None

    @property
    def is_fast(self) -> bool:
        """Was response under target time?"""
        return self.response_time_ms < PLM_TARGET_MS

    @property
    def is_automatic(self) -> bool:
        """Was response automatic (<500ms)?"""
        return self.response_time_ms < PLM_FAST_MS and self.is_correct


@dataclass
class PLMBlock:
    """
    A block of PLM trials (typically 10-20 trials).
    """

    block_id: str
    trials: list[PLMTrial]
    categories: list[str]  # Categories in this block
    task_type: PLMTaskType
    difficulty: PLMDifficulty

    # Block metrics
    started_at: datetime | None = None
    completed_at: datetime | None = None
    accuracy: float = 0.0
    avg_response_time_ms: float = 0.0
    fast_rate: float = 0.0  # % under target time

    def calculate_metrics(self) -> None:
        """Calculate block-level metrics."""
        completed = [t for t in self.trials if t.response is not None]
        if not completed:
            return

        self.accuracy = sum(1 for t in completed if t.is_correct) / len(completed)
        self.avg_response_time_ms = sum(t.response_time_ms for t in completed) / len(completed)
        self.fast_rate = sum(1 for t in completed if t.is_fast) / len(completed)


@dataclass
class PLMSession:
    """
    A complete PLM training session.
    """

    session_id: str
    user_id: str
    target_category: str | None = None  # Focus category (if any)
    blocks: list[PLMBlock] = field(default_factory=list)

    # Session metrics
    started_at: datetime | None = None
    completed_at: datetime | None = None
    total_trials: int = 0
    overall_accuracy: float = 0.0
    overall_speed_ms: float = 0.0
    fluency_achieved: bool = False

    def calculate_metrics(self) -> None:
        """Calculate session-level metrics."""
        all_trials = []
        for block in self.blocks:
            all_trials.extend([t for t in block.trials if t.response is not None])

        if not all_trials:
            return

        self.total_trials = len(all_trials)
        self.overall_accuracy = sum(1 for t in all_trials if t.is_correct) / len(all_trials)
        self.overall_speed_ms = sum(t.response_time_ms for t in all_trials) / len(all_trials)
        self.fluency_achieved = (
            self.overall_accuracy >= MASTERY_ACCURACY and self.overall_speed_ms <= PLM_TARGET_MS
        )


@dataclass
class CategoryFluency:
    """
    Fluency metrics for a specific category.
    """

    category: str
    category_id: str | None = None
    total_trials: int = 0
    correct_trials: int = 0
    accuracy: float = 0.0
    avg_response_ms: float = 0.0
    fast_rate: float = 0.0
    fluency_level: FluencyLevel = FluencyLevel.EFFORTFUL
    confused_with: dict[str, int] = field(default_factory=dict)  # category -> error count
    last_trained: datetime | None = None

    def update_from_trial(self, trial: PLMTrial) -> None:
        """Update fluency metrics from a trial."""
        self.total_trials += 1
        if trial.is_correct:
            self.correct_trials += 1
        else:
            # Track confusion patterns
            if trial.response:
                self.confused_with[trial.response] = self.confused_with.get(trial.response, 0) + 1

        # Update running averages
        self.accuracy = self.correct_trials / self.total_trials
        # EMA for response time
        alpha = 0.1
        self.avg_response_ms = self.avg_response_ms * (1 - alpha) + trial.response_time_ms * alpha

        # Update fluency level
        self._update_fluency_level()
        self.last_trained = datetime.now()

    def _update_fluency_level(self) -> None:
        """Determine fluency level from metrics."""
        if self.total_trials < 5:
            self.fluency_level = FluencyLevel.DEVELOPING
            return

        if self.accuracy < 0.6:
            self.fluency_level = FluencyLevel.STRUGGLING
        elif self.avg_response_ms < PLM_FAST_MS and self.accuracy > 0.95:
            self.fluency_level = FluencyLevel.AUTOMATIC
        elif self.avg_response_ms < PLM_TARGET_MS and self.accuracy > 0.85:
            self.fluency_level = FluencyLevel.FLUENT
        elif self.avg_response_ms < 2000 and self.accuracy > 0.7:
            self.fluency_level = FluencyLevel.DEVELOPING
        else:
            self.fluency_level = FluencyLevel.EFFORTFUL


# =============================================================================
# PLM GENERATOR
# =============================================================================


class PLMGenerator:
    """
    Generates PLM training tasks from atoms.

    Converts learning atoms into rapid classification tasks
    by identifying confusable pairs and generating options.
    """

    def __init__(self, atoms: list[dict[str, Any]]):
        """
        Initialize with a pool of atoms.

        Args:
            atoms: List of atom dictionaries with category/concept info
        """
        self.atoms = atoms
        self._categories: dict[str, list[dict]] = {}
        self._organize_by_category()

    def _organize_by_category(self) -> None:
        """Organize atoms by category/concept for training generation."""
        for atom in self.atoms:
            category = atom.get("concept_name") or atom.get("category") or "unknown"
            if category not in self._categories:
                self._categories[category] = []
            self._categories[category].append(atom)

    def get_available_categories(self) -> list[str]:
        """Get categories with enough atoms for training."""
        return [cat for cat, atoms in self._categories.items() if len(atoms) >= 3]

    def generate_classification_trial(
        self,
        target_category: str,
        distractor_categories: list[str],
        difficulty: PLMDifficulty = PLMDifficulty.MEDIUM,
    ) -> PLMTrial | None:
        """
        Generate a classification trial.

        "Which category does this belong to?"
        """
        if target_category not in self._categories:
            return None

        # Select a stimulus from target category
        target_atoms = self._categories[target_category]
        if not target_atoms:
            return None

        source_atom = random.choice(target_atoms)

        # Build options
        options = [target_category]
        for dist in distractor_categories[:3]:
            if dist != target_category:
                options.append(dist)
        random.shuffle(options)

        stimulus = PLMStimulus(
            id=str(source_atom.get("id", uuid4())),
            content=source_atom.get("front", ""),
            content_latex=source_atom.get("content_latex"),
            category=target_category,
            ps_index=source_atom.get("ps_index", 0.5),
        )

        return PLMTrial(
            stimulus=stimulus,
            options=options,
            correct_response=target_category,
            task_type=PLMTaskType.CLASSIFICATION,
            difficulty=difficulty,
        )

    def generate_discrimination_trial(
        self,
        category_a: str,
        category_b: str,
        difficulty: PLMDifficulty = PLMDifficulty.MEDIUM,
    ) -> PLMTrial | None:
        """
        Generate a discrimination trial.

        "Is this X or Y?"
        """
        if category_a not in self._categories or category_b not in self._categories:
            return None

        # Randomly select which category the stimulus comes from
        target_category = random.choice([category_a, category_b])
        source_atom = random.choice(self._categories[target_category])

        stimulus = PLMStimulus(
            id=str(source_atom.get("id", uuid4())),
            content=source_atom.get("front", ""),
            content_latex=source_atom.get("content_latex"),
            category=target_category,
            confusable_with=[category_a if target_category == category_b else category_b],
            ps_index=source_atom.get("ps_index", 0.5),
        )

        return PLMTrial(
            stimulus=stimulus,
            options=[category_a, category_b],
            correct_response=target_category,
            task_type=PLMTaskType.DISCRIMINATION,
            difficulty=difficulty,
        )

    def generate_block(
        self,
        categories: list[str],
        task_type: PLMTaskType = PLMTaskType.CLASSIFICATION,
        difficulty: PLMDifficulty = PLMDifficulty.MEDIUM,
        block_size: int = BLOCK_SIZE,
    ) -> PLMBlock | None:
        """
        Generate a block of PLM trials.

        Interleaves categories for optimal learning.
        """
        if len(categories) < 2:
            logger.warning("Need at least 2 categories for PLM training")
            return None

        trials = []
        for _ in range(block_size):
            # Interleave categories
            if task_type == PLMTaskType.CLASSIFICATION:
                target = random.choice(categories)
                distractors = [c for c in categories if c != target]
                trial = self.generate_classification_trial(target, distractors, difficulty)
            else:  # DISCRIMINATION
                pair = random.sample(categories, 2)
                trial = self.generate_discrimination_trial(pair[0], pair[1], difficulty)

            if trial:
                trials.append(trial)

        if not trials:
            return None

        return PLMBlock(
            block_id=str(uuid4()),
            trials=trials,
            categories=categories,
            task_type=task_type,
            difficulty=difficulty,
        )


# =============================================================================
# PLM ENGINE
# =============================================================================


class PLMEngine:
    """
    Main engine for running PLM training sessions.

    Manages:
    - Session creation and tracking
    - Response recording and timing
    - Fluency analysis
    - Adaptive difficulty adjustment
    """

    def __init__(self):
        """Initialize the PLM engine."""
        self._fluency_data: dict[str, CategoryFluency] = {}
        self._active_session: PLMSession | None = None
        self._generators: dict[str, PLMGenerator] = {}

    def register_atoms(self, atoms: list[dict[str, Any]], source: str = "default") -> None:
        """Register atoms for PLM training."""
        self._generators[source] = PLMGenerator(atoms)
        logger.info(f"Registered {len(atoms)} atoms for PLM from source '{source}'")

    def get_available_categories(self, source: str = "default") -> list[str]:
        """Get categories available for training."""
        if source not in self._generators:
            return []
        return self._generators[source].get_available_categories()

    def start_session(
        self,
        user_id: str,
        categories: list[str],
        source: str = "default",
        task_type: PLMTaskType = PLMTaskType.CLASSIFICATION,
        difficulty: PLMDifficulty = PLMDifficulty.ADAPTIVE,
    ) -> PLMSession | None:
        """
        Start a new PLM training session.

        Args:
            user_id: Learner identifier
            categories: Categories to train on
            source: Atom source key
            task_type: Type of PLM task
            difficulty: Difficulty level (ADAPTIVE adjusts based on performance)

        Returns:
            PLMSession if started successfully
        """
        if source not in self._generators:
            logger.error(f"No atoms registered for source '{source}'")
            return None

        generator = self._generators[source]

        # Validate categories
        available = generator.get_available_categories()
        valid_categories = [c for c in categories if c in available]

        if len(valid_categories) < 2:
            logger.error("Need at least 2 valid categories for PLM")
            return None

        session = PLMSession(
            session_id=str(uuid4()),
            user_id=user_id,
            started_at=datetime.now(),
        )

        # Generate first block
        actual_difficulty = (
            self._select_difficulty(valid_categories)
            if difficulty == PLMDifficulty.ADAPTIVE
            else difficulty
        )

        block = generator.generate_block(
            categories=valid_categories,
            task_type=task_type,
            difficulty=actual_difficulty,
        )

        if block:
            block.started_at = datetime.now()
            session.blocks.append(block)

        self._active_session = session
        return session

    def get_next_trial(self) -> PLMTrial | None:
        """Get the next trial in the active session."""
        if not self._active_session or not self._active_session.blocks:
            return None

        current_block = self._active_session.blocks[-1]

        # Find first unanswered trial
        for trial in current_block.trials:
            if trial.response is None:
                return trial

        # All trials answered - block complete
        current_block.completed_at = datetime.now()
        current_block.calculate_metrics()

        return None  # Signal that block is complete

    def record_response(
        self,
        response: str,
        response_time_ms: int,
    ) -> PLMTrial | None:
        """
        Record response for the current trial.

        Args:
            response: The learner's response
            response_time_ms: Time taken to respond

        Returns:
            The completed trial with results
        """
        if not self._active_session:
            return None

        current_block = self._active_session.blocks[-1]

        # Find the current trial (first unanswered)
        current_trial = None
        for trial in current_block.trials:
            if trial.response is None:
                current_trial = trial
                break

        if not current_trial:
            return None

        # Record response
        current_trial.response = response
        current_trial.response_time_ms = response_time_ms
        current_trial.is_correct = response == current_trial.correct_response
        current_trial.timestamp = datetime.now()

        # Update category fluency
        category = current_trial.stimulus.category
        if category not in self._fluency_data:
            self._fluency_data[category] = CategoryFluency(category=category)
        self._fluency_data[category].update_from_trial(current_trial)

        return current_trial

    def generate_next_block(
        self,
        source: str = "default",
    ) -> PLMBlock | None:
        """Generate the next block for the active session."""
        if not self._active_session:
            return None

        if source not in self._generators:
            return None

        generator = self._generators[source]

        # Get categories from current session
        if self._active_session.blocks:
            categories = self._active_session.blocks[-1].categories
            task_type = self._active_session.blocks[-1].task_type
        else:
            categories = generator.get_available_categories()[:4]
            task_type = PLMTaskType.CLASSIFICATION

        # Adaptive difficulty based on last block
        difficulty = self._select_difficulty(categories)

        block = generator.generate_block(
            categories=categories,
            task_type=task_type,
            difficulty=difficulty,
        )

        if block:
            block.started_at = datetime.now()
            self._active_session.blocks.append(block)

        return block

    def _select_difficulty(self, categories: list[str]) -> PLMDifficulty:
        """Select difficulty based on current fluency levels."""
        fluencies = [self._fluency_data.get(cat) for cat in categories if cat in self._fluency_data]

        if not fluencies:
            return PLMDifficulty.EASY

        avg_accuracy = sum(f.accuracy for f in fluencies) / len(fluencies)
        avg_speed = sum(f.avg_response_ms for f in fluencies) / len(fluencies)

        if avg_accuracy > 0.9 and avg_speed < PLM_TARGET_MS:
            return PLMDifficulty.HARD
        elif avg_accuracy > 0.75:
            return PLMDifficulty.MEDIUM
        else:
            return PLMDifficulty.EASY

    def end_session(self) -> PLMSession | None:
        """End the active session and return final metrics."""
        if not self._active_session:
            return None

        session = self._active_session
        session.completed_at = datetime.now()
        session.calculate_metrics()

        self._active_session = None
        return session

    def get_fluency_report(self, categories: list[str] | None = None) -> dict[str, Any]:
        """
        Get a fluency report for specified categories.

        Returns detailed metrics on perceptual fluency development.
        """
        if categories is None:
            categories = list(self._fluency_data.keys())

        report = {
            "timestamp": datetime.now().isoformat(),
            "categories": {},
            "summary": {
                "total_categories": len(categories),
                "automatic": 0,
                "fluent": 0,
                "developing": 0,
                "struggling": 0,
            },
            "recommendations": [],
        }

        for cat in categories:
            if cat not in self._fluency_data:
                continue

            fluency = self._fluency_data[cat]
            report["categories"][cat] = {
                "fluency_level": fluency.fluency_level.value,
                "accuracy": round(fluency.accuracy, 3),
                "avg_response_ms": round(fluency.avg_response_ms),
                "total_trials": fluency.total_trials,
                "confused_with": dict(fluency.confused_with),
            }

            # Update summary counts
            level = fluency.fluency_level
            if level == FluencyLevel.AUTOMATIC:
                report["summary"]["automatic"] += 1
            elif level == FluencyLevel.FLUENT:
                report["summary"]["fluent"] += 1
            elif level == FluencyLevel.DEVELOPING:
                report["summary"]["developing"] += 1
            else:
                report["summary"]["struggling"] += 1

        # Generate recommendations
        for cat, data in report["categories"].items():
            if data["fluency_level"] == "struggling":
                report["recommendations"].append(
                    {
                        "category": cat,
                        "action": "review_source",
                        "reason": f"Low accuracy ({data['accuracy']:.0%}). Review source material before continuing PLM.",
                    }
                )
            elif data["fluency_level"] == "effortful" and data["accuracy"] > 0.7:
                report["recommendations"].append(
                    {
                        "category": cat,
                        "action": "speed_training",
                        "reason": f"Good accuracy but slow ({data['avg_response_ms']}ms). Focus on speed.",
                    }
                )
            elif data["confused_with"]:
                top_confusion = max(data["confused_with"], key=data["confused_with"].get)
                report["recommendations"].append(
                    {
                        "category": cat,
                        "action": "discrimination_training",
                        "reason": f"Often confused with '{top_confusion}'. Practice distinguishing these.",
                    }
                )

        return report


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================

# Global PLM engine instance
_engine: PLMEngine | None = None


def get_plm_engine() -> PLMEngine:
    """Get or create the global PLM engine."""
    global _engine
    if _engine is None:
        _engine = PLMEngine()
    return _engine


def run_plm_trial(
    stimulus: str,
    options: list[str],
    correct: str,
    response: str,
    response_time_ms: int,
) -> dict[str, Any]:
    """
    Quick function to evaluate a single PLM trial.

    Returns metrics about the response.
    """
    is_correct = response == correct
    is_fast = response_time_ms < PLM_TARGET_MS
    is_automatic = response_time_ms < PLM_FAST_MS and is_correct

    # Determine fluency classification
    if is_automatic:
        fluency = FluencyLevel.AUTOMATIC
    elif is_fast and is_correct:
        fluency = FluencyLevel.FLUENT
    elif is_correct:
        fluency = FluencyLevel.DEVELOPING
    else:
        fluency = FluencyLevel.STRUGGLING

    return {
        "is_correct": is_correct,
        "is_fast": is_fast,
        "is_automatic": is_automatic,
        "fluency": fluency.value,
        "response_time_ms": response_time_ms,
        "target_ms": PLM_TARGET_MS,
        "feedback": _generate_feedback(is_correct, response_time_ms, fluency),
    }


def _generate_feedback(is_correct: bool, response_time_ms: int, fluency: FluencyLevel) -> str:
    """Generate appropriate feedback for a PLM trial."""
    if fluency == FluencyLevel.AUTOMATIC:
        return "Excellent! Automatic recognition achieved."
    elif fluency == FluencyLevel.FLUENT:
        return "Good! Fast and accurate."
    elif fluency == FluencyLevel.DEVELOPING and is_correct:
        return f"Correct! Try to respond faster (target: {PLM_TARGET_MS}ms, yours: {response_time_ms}ms)"
    elif is_correct:
        return "Correct, but too slow. Focus on pattern recognition, not calculation."
    else:
        return "Incorrect. Look for the distinguishing features."


def needs_plm_training(
    category: str,
    accuracy: float,
    avg_response_ms: float,
    trial_count: int,
) -> bool:
    """
    Determine if a category needs PLM training.

    Returns True if:
    - Accuracy is good but speed is slow (procedural knowledge, not perceptual)
    - There are confusion patterns with similar categories
    """
    if trial_count < 5:
        return False  # Not enough data

    # Good accuracy but slow = needs perceptual training
    return bool(accuracy > 0.7 and avg_response_ms > PLM_TARGET_MS)
