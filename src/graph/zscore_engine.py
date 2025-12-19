"""
Z-Score Engine for Cortex 2.0.

The Z-Score determines which atoms appear in the Focus Stream by combining
four orthogonal signals into a single attention-worthiness score.

Formula:
    Z(a) = w_d·D(t) + w_c·C(a) + w_p·P(a) + w_n·N(a)

Where:
    D(t) = Time-decay signal (exponential decay since last touch)
    C(a) = Centrality signal (PageRank importance in knowledge graph)
    P(a) = Project relevance signal (alignment with active projects)
    N(a) = Novelty signal (inverse of review count)

The "Inverted Filter" Strategy:
Since Notion's database views are immutable via API, we don't modify views.
Instead, we modify atom properties (Z_Activation checkbox) so atoms
appear/disappear from pre-configured views based on this flag.

Reference: Cortex 2.0 Architecture Specification, Section 2.3

Author: Cortex System
Version: 2.0.0 (Notion-Centric Architecture)
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from loguru import logger

from config import get_settings
from src.graph.shadow_graph import (
    GraphNode,
    ShadowGraphService,
    get_shadow_graph,
)

# =============================================================================
# DATA MODELS
# =============================================================================


@dataclass
class ZScoreComponents:
    """Components of a Z-Score calculation."""

    decay: float = 0.0  # D(t) - time decay
    centrality: float = 0.0  # C(a) - graph centrality
    project: float = 0.0  # P(a) - project relevance
    novelty: float = 0.0  # N(a) - novelty/freshness

    @property
    def total(self) -> float:
        """Calculate weighted total Z-Score."""
        settings = get_settings()
        weights = settings.get_zscore_weights()
        return (
            weights["decay"] * self.decay
            + weights["centrality"] * self.centrality
            + weights["project"] * self.project
            + weights["novelty"] * self.novelty
        )

    @property
    def is_activated(self) -> bool:
        """Check if this score triggers Focus Stream activation."""
        settings = get_settings()
        return self.total >= settings.zscore_activation_threshold

    def to_dict(self) -> dict[str, float]:
        """Convert to dictionary."""
        return {
            "decay": round(self.decay, 3),
            "centrality": round(self.centrality, 3),
            "project": round(self.project, 3),
            "novelty": round(self.novelty, 3),
            "total": round(self.total, 3),
            "activated": self.is_activated,
        }


@dataclass
class AtomMetrics:
    """Metrics for an atom used in Z-Score calculation."""

    atom_id: str
    last_touched: datetime | None = None
    review_count: int = 0
    stability: float = 0.0
    difficulty: float = 0.3
    memory_state: str = "NEW"
    project_ids: list[str] = field(default_factory=list)


@dataclass
class ZScoreResult:
    """Result of a Z-Score batch computation."""

    atom_id: str
    components: ZScoreComponents
    z_score: float
    z_activation: bool
    needs_update: bool = False  # Whether Notion property needs update


# =============================================================================
# Z-SCORE ENGINE
# =============================================================================


class ZScoreEngine:
    """
    Computes Z-Scores for atoms to determine Focus Stream membership.

    The Z-Score Engine is the brain of the Cortex 2.0 attention system.
    It combines multiple signals to decide what the learner should focus on.

    Signals:
    - Decay D(t): How long since the atom was last touched? (exponential decay)
    - Centrality C(a): How important is this atom in the knowledge graph?
    - Project P(a): Is this atom relevant to active learning projects?
    - Novelty N(a): Is this a new/fresh atom that needs initial encoding?

    Usage:
        engine = ZScoreEngine()
        results = engine.compute_batch(atoms)
        for result in results:
            if result.z_activation:
                # This atom should appear in Focus Stream
                update_notion_property(result.atom_id, "Z_Activation", True)
    """

    def __init__(self):
        """Initialize the Z-Score engine."""
        self._settings = get_settings()
        self._graph: ShadowGraphService | None = None
        self._centrality_cache: dict[str, float] = {}
        self._project_atoms_cache: dict[str, set[str]] = {}

    def _get_graph(self) -> ShadowGraphService:
        """Get the Shadow Graph service (lazy initialization)."""
        if self._graph is None:
            self._graph = get_shadow_graph()
        return self._graph

    # =========================================================================
    # SIGNAL FUNCTIONS
    # =========================================================================

    def compute_decay(
        self,
        last_touched: datetime | None,
        now: datetime | None = None,
    ) -> float:
        """
        Compute time-decay signal D(t).

        Uses exponential decay with configurable half-life:
            D(t) = exp(-λ * days_since_touch)

        Where λ = ln(2) / half_life_days

        Returns value in [0, 1] where:
        - 1.0 = never touched (maximum urgency)
        - 0.0 = just touched (no urgency)

        Args:
            last_touched: When the atom was last reviewed/touched
            now: Current time (default: now)

        Returns:
            Decay signal in [0, 1]
        """
        if now is None:
            now = datetime.now()

        # Never touched = maximum decay (needs immediate attention)
        if last_touched is None:
            return 1.0

        # Make both datetimes timezone-naive for comparison
        if last_touched.tzinfo is not None:
            last_touched = last_touched.replace(tzinfo=None)

        days_since = (now - last_touched).total_seconds() / 86400

        if days_since <= 0:
            return 0.0  # Just touched

        # Exponential decay
        half_life = self._settings.zscore_decay_halflife_days
        decay_rate = math.log(2) / half_life

        # Inverted: higher value = more urgent
        decay = 1.0 - math.exp(-decay_rate * days_since)
        return min(1.0, max(0.0, decay))

    def compute_centrality(self, atom_id: str) -> float:
        """
        Compute centrality signal C(a).

        Uses PageRank from the Shadow Graph to determine how
        important this atom is in the knowledge structure.

        Higher centrality = more foundational concept = higher priority.

        Args:
            atom_id: ID of the atom

        Returns:
            Centrality signal in [0, 1]
        """
        # Check cache first
        if atom_id in self._centrality_cache:
            return self._centrality_cache[atom_id]

        graph = self._get_graph()
        if not graph.is_available:
            return 0.5  # Default centrality when graph unavailable

        # Get PageRank for all atoms (cached internally)
        if not self._centrality_cache:
            rankings = graph.compute_pagerank()
            if rankings:
                # Normalize to [0, 1]
                max_rank = max(rankings.values()) if rankings else 1.0
                self._centrality_cache = {
                    aid: rank / max_rank if max_rank > 0 else 0.0 for aid, rank in rankings.items()
                }

        return self._centrality_cache.get(atom_id, 0.5)

    def compute_project_relevance(
        self,
        atom_id: str,
        active_project_ids: list[str],
    ) -> float:
        """
        Compute project relevance signal P(a).

        Checks if the atom is connected to any active learning projects.
        Active projects represent current learning focus areas.

        Args:
            atom_id: ID of the atom
            active_project_ids: List of active project IDs

        Returns:
            Project relevance signal in [0, 1]
        """
        if not active_project_ids:
            return 0.0  # No active projects

        graph = self._get_graph()
        if not graph.is_available:
            return 0.0

        # Check which projects this atom belongs to
        for project_id in active_project_ids:
            if project_id not in self._project_atoms_cache:
                project_atoms = graph.get_project_atoms(project_id)
                self._project_atoms_cache[project_id] = set(project_atoms)

            if atom_id in self._project_atoms_cache.get(project_id, set()):
                return 1.0  # Atom is relevant to an active project

        return 0.0

    def compute_novelty(
        self,
        review_count: int,
        memory_state: str = "NEW",
    ) -> float:
        """
        Compute novelty signal N(a).

        New atoms need initial encoding, so they get priority.
        As review count increases, novelty decreases.

        Formula: N(a) = 1 / (1 + log(1 + review_count))

        Args:
            review_count: Number of times the atom has been reviewed
            memory_state: Current memory state (NEW, LEARNING, REVIEW, MASTERED)

        Returns:
            Novelty signal in [0, 1]
        """
        # New atoms get maximum novelty
        if memory_state == "NEW" or review_count == 0:
            return 1.0

        # Mastered atoms get minimum novelty
        if memory_state == "MASTERED":
            return 0.1

        # Logarithmic decay based on review count
        novelty = 1.0 / (1.0 + math.log(1.0 + review_count))
        return min(1.0, max(0.0, novelty))

    # =========================================================================
    # BATCH COMPUTATION
    # =========================================================================

    def compute(
        self,
        metrics: AtomMetrics,
        active_project_ids: list[str] | None = None,
        now: datetime | None = None,
    ) -> ZScoreResult:
        """
        Compute Z-Score for a single atom.

        Args:
            metrics: Atom metrics for calculation
            active_project_ids: List of active project IDs
            now: Current time

        Returns:
            ZScoreResult with components and activation status
        """
        if active_project_ids is None:
            active_project_ids = []

        components = ZScoreComponents(
            decay=self.compute_decay(metrics.last_touched, now),
            centrality=self.compute_centrality(metrics.atom_id),
            project=self.compute_project_relevance(metrics.atom_id, active_project_ids),
            novelty=self.compute_novelty(metrics.review_count, metrics.memory_state),
        )

        return ZScoreResult(
            atom_id=metrics.atom_id,
            components=components,
            z_score=components.total,
            z_activation=components.is_activated,
        )

    def compute_batch(
        self,
        metrics_list: list[AtomMetrics],
        active_project_ids: list[str] | None = None,
        now: datetime | None = None,
    ) -> list[ZScoreResult]:
        """
        Compute Z-Scores for a batch of atoms.

        More efficient than computing individually as it caches
        centrality rankings.

        Args:
            metrics_list: List of atom metrics
            active_project_ids: List of active project IDs
            now: Current time

        Returns:
            List of ZScoreResults
        """
        if now is None:
            now = datetime.now()

        if active_project_ids is None:
            active_project_ids = []

        # Pre-compute centrality cache
        self._warm_centrality_cache()

        # Pre-compute project atoms cache
        for project_id in active_project_ids:
            if project_id not in self._project_atoms_cache:
                graph = self._get_graph()
                if graph.is_available:
                    atoms = graph.get_project_atoms(project_id)
                    self._project_atoms_cache[project_id] = set(atoms)

        # Compute all Z-Scores
        results = []
        for metrics in metrics_list:
            result = self.compute(metrics, active_project_ids, now)
            results.append(result)

        logger.info(
            f"Computed Z-Scores for {len(results)} atoms, "
            f"{sum(1 for r in results if r.z_activation)} activated"
        )

        return results

    def _warm_centrality_cache(self) -> None:
        """Pre-compute centrality rankings for all atoms."""
        if self._centrality_cache:
            return  # Already warmed

        graph = self._get_graph()
        if not graph.is_available:
            return

        rankings = graph.compute_pagerank()
        if rankings:
            max_rank = max(rankings.values()) if rankings else 1.0
            self._centrality_cache = {
                aid: rank / max_rank if max_rank > 0 else 0.0 for aid, rank in rankings.items()
            }

    def clear_cache(self) -> None:
        """Clear all caches (call when graph structure changes)."""
        self._centrality_cache.clear()
        self._project_atoms_cache.clear()


# =============================================================================
# FORCE Z ENGINE
# =============================================================================


@dataclass
class ForceZResult:
    """Result of a Force Z backtracking analysis."""

    target_atom_id: str
    should_backtrack: bool
    weak_prerequisites: list[GraphNode]
    recommended_path: list[str]
    explanation: str


class ForceZEngine:
    """
    Force Z Backtracking Engine for prerequisite enforcement.

    When a learner is struggling with atom X, Force Z checks if there
    are weak prerequisite atoms Z that need remediation first.

    Algorithm:
    1. Query Shadow Graph for prerequisite chain of X
    2. Check each prerequisite's mastery level
    3. If any prerequisite Z has mastery < threshold:
       - Suspend current queue
       - Inject Z atoms at head
       - Continue with remediation

    Reference: Cortex 2.0 Architecture Specification, Section 2.5

    Usage:
        engine = ForceZEngine()
        result = engine.analyze(atom_id)
        if result.should_backtrack:
            for prereq_id in result.recommended_path:
                session.inject_at_head(prereq_id)
    """

    def __init__(self):
        """Initialize the Force Z engine."""
        self._settings = get_settings()
        self._graph: ShadowGraphService | None = None

    def _get_graph(self) -> ShadowGraphService:
        """Get the Shadow Graph service."""
        if self._graph is None:
            self._graph = get_shadow_graph()
        return self._graph

    def analyze(
        self,
        target_atom_id: str,
        mastery_threshold: float | None = None,
    ) -> ForceZResult:
        """
        Analyze whether Force Z backtracking is needed for an atom.

        Args:
            target_atom_id: ID of the atom the learner is struggling with
            mastery_threshold: Override default mastery threshold

        Returns:
            ForceZResult with backtracking recommendation
        """
        if mastery_threshold is None:
            mastery_threshold = self._settings.force_z_mastery_threshold

        graph = self._get_graph()

        if not graph.is_available:
            return ForceZResult(
                target_atom_id=target_atom_id,
                should_backtrack=False,
                weak_prerequisites=[],
                recommended_path=[],
                explanation="Shadow Graph not available; cannot analyze prerequisites",
            )

        # Get weak prerequisites from the graph
        weak_prereqs = graph.get_weak_prerequisites(target_atom_id, mastery_threshold)

        if not weak_prereqs:
            return ForceZResult(
                target_atom_id=target_atom_id,
                should_backtrack=False,
                weak_prerequisites=[],
                recommended_path=[],
                explanation="All prerequisites are sufficiently mastered",
            )

        # Sort by Z-Score (lowest first = most urgent)
        weak_prereqs.sort(key=lambda n: n.z_score)

        # Build recommended path (topological order, limited by max depth)
        max_depth = self._settings.force_z_max_depth
        recommended = [node.id for node in weak_prereqs[:max_depth]]

        # Build explanation
        prereq_names = [node.title or node.id[:8] for node in weak_prereqs[:3]]
        explanation = (
            f"Found {len(weak_prereqs)} weak prerequisite(s): "
            f"{', '.join(prereq_names)}{'...' if len(weak_prereqs) > 3 else ''}. "
            f"Recommend backtracking to strengthen foundation."
        )

        return ForceZResult(
            target_atom_id=target_atom_id,
            should_backtrack=True,
            weak_prerequisites=weak_prereqs,
            recommended_path=recommended,
            explanation=explanation,
        )

    def get_remediation_queue(
        self,
        target_atom_id: str,
        limit: int = 5,
    ) -> list[dict[str, Any]]:
        """
        Get a remediation queue for Force Z backtracking.

        Returns atoms in the order they should be reviewed,
        starting with the most foundational weak prerequisites.

        Args:
            target_atom_id: ID of the target atom
            limit: Maximum number of remediation atoms

        Returns:
            List of atom dictionaries for the session queue
        """
        result = self.analyze(target_atom_id)

        if not result.should_backtrack:
            return []

        queue = []
        for node in result.weak_prerequisites[:limit]:
            queue.append(
                {
                    "id": node.id,
                    "title": node.title,
                    "memory_state": node.memory_state,
                    "z_score": node.z_score,
                    "is_force_z": True,  # Flag for UI to display differently
                }
            )

        return queue


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================

_zscore_engine: ZScoreEngine | None = None
_forcez_engine: ForceZEngine | None = None


def get_zscore_engine() -> ZScoreEngine:
    """Get or create the global Z-Score engine."""
    global _zscore_engine
    if _zscore_engine is None:
        _zscore_engine = ZScoreEngine()
    return _zscore_engine


def get_forcez_engine() -> ForceZEngine:
    """Get or create the global Force Z engine."""
    global _forcez_engine
    if _forcez_engine is None:
        _forcez_engine = ForceZEngine()
    return _forcez_engine


def compute_zscore(atom_id: str, last_touched: datetime = None) -> float:
    """
    Compute Z-Score for a single atom (convenience function).

    Args:
        atom_id: ID of the atom
        last_touched: When the atom was last reviewed

    Returns:
        Z-Score value
    """
    engine = get_zscore_engine()
    metrics = AtomMetrics(atom_id=atom_id, last_touched=last_touched)
    result = engine.compute(metrics)
    return result.z_score


def should_force_z(atom_id: str) -> bool:
    """
    Check if Force Z backtracking is needed (convenience function).

    Args:
        atom_id: ID of the atom to check

    Returns:
        True if backtracking is recommended
    """
    engine = get_forcez_engine()
    result = engine.analyze(atom_id)
    return result.should_backtrack
