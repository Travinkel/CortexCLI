"""
Focus Stream: Intelligent Review Queue Prioritization.

Implements the Z-Score algorithm to prevent "Anki Hell" by:
1. Limiting daily review count (budget)
2. Prioritizing by relevance, urgency, and centrality
3. Supporting attestation decay

Z(a) = w_d·D(t) + w_c·C(a) + w_p·P(a) + w_n·N(a)

Where:
- D(t) = Time decay signal (urgency)
- C(a) = Centrality signal (how foundational)
- P(a) = Project relevance signal (current work)
- N(a) = Novelty signal (has user seen this)
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any


@dataclass
class FocusStreamConfig:
    """Configuration for Focus Stream prioritization."""

    # Z-Score weights (must sum to 1.0)
    weight_decay: float = 0.30
    weight_centrality: float = 0.25
    weight_project: float = 0.25
    weight_novelty: float = 0.20

    # Thresholds
    activation_threshold: float = 0.40  # Minimum Z to enter queue
    decay_half_life_days: int = 7

    # Budget
    daily_budget: int = 30  # Hard cap on daily reviews

    def validate(self) -> bool:
        """Validate that weights sum to 1.0."""
        total = (
            self.weight_decay
            + self.weight_centrality
            + self.weight_project
            + self.weight_novelty
        )
        return abs(total - 1.0) < 0.01


@dataclass
class AtomScore:
    """Scored atom with Z-Score components."""

    atom_id: str
    z_score: float
    decay: float
    centrality: float
    project_relevance: float
    novelty: float

    # Atom data
    front: str = ""
    back: str = ""
    atom_type: str = "flashcard"
    concept: str = ""
    course_code: str = ""
    due_date: datetime | None = None


@dataclass
class ProjectContext:
    """Context for project relevance scoring."""

    active_courses: list[str] = field(default_factory=list)
    active_concepts: list[str] = field(default_factory=list)
    recent_files: list[str] = field(default_factory=list)
    keywords: list[str] = field(default_factory=list)


class FocusStream:
    """
    Focus Stream queue manager.

    Transforms a list of due atoms into a prioritized queue
    using the Z-Score algorithm.
    """

    def __init__(self, config: FocusStreamConfig | None = None):
        self.config = config or FocusStreamConfig()
        self.context = ProjectContext()

        # Caches
        self._centrality_cache: dict[str, float] = {}
        self._review_history: dict[str, list[datetime]] = {}

    def set_context(self, context: ProjectContext) -> None:
        """Set project context for relevance scoring."""
        self.context = context

    def add_to_context(
        self,
        courses: list[str] | None = None,
        concepts: list[str] | None = None,
        keywords: list[str] | None = None,
    ) -> None:
        """Add items to current context."""
        if courses:
            self.context.active_courses.extend(courses)
        if concepts:
            self.context.active_concepts.extend(concepts)
        if keywords:
            self.context.keywords.extend(keywords)

    def get_queue(
        self,
        atoms: list[dict[str, Any]],
        budget: int | None = None,
    ) -> list[AtomScore]:
        """
        Get prioritized queue from due atoms.

        Args:
            atoms: List of atom dicts with keys: id, front, back, atom_type,
                   concept, course_code, due_date, review_count
            budget: Override daily budget (default: config.daily_budget)

        Returns:
            List of AtomScore sorted by Z-Score descending
        """
        budget = budget or self.config.daily_budget

        # Score all atoms
        scored = []
        for atom in atoms:
            score = self._score_atom(atom)
            if score.z_score >= self.config.activation_threshold:
                scored.append(score)

        # Sort by Z-Score descending
        scored.sort(key=lambda x: x.z_score, reverse=True)

        # Apply budget cap
        return scored[:budget]

    def _score_atom(self, atom: dict[str, Any]) -> AtomScore:
        """Calculate Z-Score for a single atom."""
        atom_id = atom.get("id", "")

        # Calculate each component
        d_t = self._decay_signal(atom)
        c_a = self._centrality_signal(atom)
        p_a = self._project_relevance(atom)
        n_a = self._novelty_signal(atom)

        # Weighted sum
        z_score = (
            self.config.weight_decay * d_t
            + self.config.weight_centrality * c_a
            + self.config.weight_project * p_a
            + self.config.weight_novelty * n_a
        )

        return AtomScore(
            atom_id=atom_id,
            z_score=z_score,
            decay=d_t,
            centrality=c_a,
            project_relevance=p_a,
            novelty=n_a,
            front=atom.get("front", ""),
            back=atom.get("back", ""),
            atom_type=atom.get("atom_type", "flashcard"),
            concept=atom.get("concept", ""),
            course_code=atom.get("course_code", ""),
            due_date=atom.get("due_date"),
        )

    def _decay_signal(self, atom: dict[str, Any]) -> float:
        """
        Calculate time decay signal D(t).

        Higher value = more urgent (longer since review).
        """
        due_date = atom.get("due_date")
        last_review = atom.get("last_review")

        if last_review is None:
            # Never reviewed = high urgency
            return 1.0

        if isinstance(last_review, str):
            try:
                last_review = datetime.fromisoformat(last_review)
            except ValueError:
                return 0.5

        days_since = (datetime.now() - last_review).days
        if days_since <= 0:
            return 0.0

        # Exponential decay toward 1.0
        half_life = self.config.decay_half_life_days
        return 1.0 - math.exp(-days_since / half_life)

    def _centrality_signal(self, atom: dict[str, Any]) -> float:
        """
        Calculate centrality signal C(a).

        Higher value = more foundational concept.
        """
        concept = atom.get("concept", "")

        # Check cache
        if concept in self._centrality_cache:
            return self._centrality_cache[concept]

        # Simple heuristic: certain concepts are more foundational
        foundational_terms = [
            "basic", "fundamental", "introduction", "overview",
            "what is", "definition", "core", "principle",
        ]

        score = 0.5  # Default
        concept_lower = concept.lower()

        for term in foundational_terms:
            if term in concept_lower:
                score = 0.8
                break

        # Boost for first few weeks (foundational)
        week = atom.get("week_number", 99)
        if week and week <= 3:
            score = min(1.0, score + 0.2)

        self._centrality_cache[concept] = score
        return score

    def _project_relevance(self, atom: dict[str, Any]) -> float:
        """
        Calculate project relevance signal P(a).

        Higher value = more relevant to current work.
        """
        if not self.context.active_courses and not self.context.keywords:
            return 0.5  # No context = neutral

        score = 0.0
        course = atom.get("course_code", "")
        concept = atom.get("concept", "").lower()
        front = atom.get("front", "").lower()

        # Course match
        if course in self.context.active_courses:
            score += 0.4

        # Concept match
        for active_concept in self.context.active_concepts:
            if active_concept.lower() in concept:
                score += 0.3
                break

        # Keyword match
        text = f"{concept} {front}"
        for keyword in self.context.keywords:
            if keyword.lower() in text:
                score += 0.2
                break

        return min(1.0, score)

    def _novelty_signal(self, atom: dict[str, Any]) -> float:
        """
        Calculate novelty signal N(a).

        Higher value = less seen (prioritize new content).
        """
        review_count = atom.get("review_count", 0)

        if review_count == 0:
            return 1.0  # Never seen = maximum novelty

        # Novelty decays with exposure
        # After 5 reviews, novelty approaches 0
        return math.exp(-review_count / 3)

    def get_debug_info(self, atoms: list[dict[str, Any]]) -> list[dict]:
        """Get detailed scoring info for debugging."""
        scored = []
        for atom in atoms:
            score = self._score_atom(atom)
            scored.append({
                "id": score.atom_id,
                "front": score.front[:50] + "..." if len(score.front) > 50 else score.front,
                "z_score": round(score.z_score, 3),
                "components": {
                    "D(t)": round(score.decay, 3),
                    "C(a)": round(score.centrality, 3),
                    "P(a)": round(score.project_relevance, 3),
                    "N(a)": round(score.novelty, 3),
                },
                "passes_threshold": score.z_score >= self.config.activation_threshold,
            })

        scored.sort(key=lambda x: x["z_score"], reverse=True)
        return scored


# Convenience functions


def get_focus_queue(
    atoms: list[dict[str, Any]],
    budget: int = 30,
    context: ProjectContext | None = None,
) -> list[AtomScore]:
    """
    Get a prioritized focus queue.

    Convenience function for quick queue generation.
    """
    stream = FocusStream()
    if context:
        stream.set_context(context)
    return stream.get_queue(atoms, budget)


def score_atoms(
    atoms: list[dict[str, Any]],
    context: ProjectContext | None = None,
) -> list[dict]:
    """
    Score atoms and return debug info.

    Useful for understanding why atoms are prioritized.
    """
    stream = FocusStream()
    if context:
        stream.set_context(context)
    return stream.get_debug_info(atoms)
