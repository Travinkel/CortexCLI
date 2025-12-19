"""
Knowledge Graph for Cortex.

Implements the Learning Atom ontology and knowledge graph traversal.
Atoms are the fundamental units of instruction with rich metadata for
cognitive adaptation.

Key Features:
- Learning Atom schema with ps_index (Pattern Separation Index)
- pfit_index (P-FIT Integration Index)
- Prerequisite inference from embeddings
- Confusable neighbor detection
- Knowledge graph traversal algorithms
- Spivak-style rigorous text decomposition

Atom Types:
- Definition: Core concept definition
- Theorem: Mathematical theorem
- Lemma: Supporting lemma
- Proof_Step: Individual proof step
- Intuition_Pump: Conceptual explanation
- Counter_Example: Counterexample for boundaries
- Adversarial_Lure: Confusable item for discrimination training

Based on research from:
- Norman & O'Reilly (2003): Pattern Separation
- Semantic embedding research
- Knowledge graph learning

Author: Cortex System
Version: 2.0.0 (Neuromorphic Architecture)
"""

from __future__ import annotations

import math
from collections.abc import Iterator
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any
from uuid import uuid4

from loguru import logger

# Try to import numpy for vector operations
try:
    import numpy as np

    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False


# =============================================================================
# ENUMERATIONS
# =============================================================================


class AtomType(str, Enum):
    """Types of Learning Atoms."""

    DEFINITION = "definition"  # Core concept definition
    THEOREM = "theorem"  # Mathematical theorem
    LEMMA = "lemma"  # Supporting lemma
    COROLLARY = "corollary"  # Direct consequence
    PROOF_STEP = "proof_step"  # Individual proof step
    INTUITION_PUMP = "intuition_pump"  # Conceptual explanation
    COUNTER_EXAMPLE = "counter_example"  # Counterexample
    EXAMPLE = "example"  # Worked example
    ADVERSARIAL_LURE = "adversarial_lure"  # Confusable item
    PROCEDURE = "procedure"  # Step-by-step process
    FACT = "fact"  # Atomic fact


class CognitiveModality(str, Enum):
    """Cognitive modality required to process the atom."""

    SYMBOLIC = "symbolic"  # Pure symbolic manipulation
    VISUAL_SPATIAL = "visual_spatial"  # Geometric/visual
    VERBAL = "verbal"  # Language-based
    PROCEDURAL = "procedural"  # Sequential steps
    INTEGRATIVE = "integrative"  # Requires combining modalities


class ConnectionType(str, Enum):
    """Types of connections between atoms."""

    PREREQUISITE = "prerequisite"  # Must learn A before B
    SUPPORTS = "supports"  # A helps understand B
    CONTRASTS = "contrasts"  # A and B are commonly confused
    GENERALIZES = "generalizes"  # B is more general than A
    SPECIALIZES = "specializes"  # B is specific case of A
    PROVES = "proves"  # A is used to prove B
    APPLIES = "applies"  # A is application of B
    ADVERSARIAL = "adversarial"  # A is adversarial lure for B


# =============================================================================
# LEARNING ATOM SCHEMA
# =============================================================================


@dataclass
class AtomContent:
    """Content representation of an atom."""

    text: str  # Natural language description
    latex: str | None = None  # Formal LaTeX representation
    lean_code: str | None = None  # Lean 4 formalization (optional)
    visual_description: str | None = None  # For visual content


@dataclass
class AtomMetadata:
    """Metadata for cognitive processing."""

    source: str = ""  # E.g., "Spivak Calculus 4th Ed, pg 102"
    chapter: int | None = None
    section: str | None = None
    page: int | None = None
    atom_type: AtomType = AtomType.FACT
    cognitive_modality: CognitiveModality = CognitiveModality.SYMBOLIC

    # Cognitive indices (0-1)
    ps_index: float = 0.5  # Pattern Separation Index
    pfit_index: float = 0.5  # P-FIT Integration Index
    hippocampal_index: float = 0.5  # Memory consolidation difficulty
    intrinsic_load: float = 0.5  # Cognitive load

    # Timestamps
    created_at: datetime | None = None
    updated_at: datetime | None = None


@dataclass
class AtomConnection:
    """Connection to another atom in the knowledge graph."""

    target_id: str
    connection_type: ConnectionType
    strength: float = 0.5  # Connection strength (0-1)
    inferred: bool = False  # Was this inferred from embeddings?


@dataclass
class LearningAtom:
    """
    The fundamental unit of instruction in Cortex.

    A Learning Atom is:
    - Semantically atomic (one concept/fact)
    - Richly connected (prerequisite graph)
    - Cognitively indexed (ps_index, pfit_index)
    - Multimodal (text, LaTeX, visual)

    The ps_index (Pattern Separation Index) indicates how likely this
    atom is to be confused with similar atoms. High ps_index = high
    confusion risk = needs discrimination training.
    """

    id: str
    content: AtomContent
    metadata: AtomMetadata
    embedding: list[float] | None = None  # Semantic embedding vector
    connections: list[AtomConnection] = field(default_factory=list)

    # FSRS-style spaced repetition data
    stability: float = 0.0
    difficulty: float = 0.3
    lapses: int = 0
    review_count: int = 0
    last_review: datetime | None = None

    # Concept association
    concept_id: str | None = None
    concept_name: str | None = None

    def __post_init__(self):
        """Initialize timestamps if not set."""
        if self.metadata.created_at is None:
            self.metadata.created_at = datetime.now()

    @property
    def ps_index(self) -> float:
        """Pattern Separation Index - higher = more confusable."""
        return self.metadata.ps_index

    @property
    def pfit_index(self) -> float:
        """P-FIT Index - higher = more integration required."""
        return self.metadata.pfit_index

    @property
    def prerequisites(self) -> list[str]:
        """Get prerequisite atom IDs."""
        return [
            c.target_id
            for c in self.connections
            if c.connection_type == ConnectionType.PREREQUISITE
        ]

    @property
    def adversarial_lures(self) -> list[str]:
        """Get adversarial lure atom IDs."""
        return [
            c.target_id for c in self.connections if c.connection_type == ConnectionType.ADVERSARIAL
        ]

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "id": self.id,
            "content": {
                "text": self.content.text,
                "latex": self.content.latex,
                "lean_code": self.content.lean_code,
            },
            "metadata": {
                "source": self.metadata.source,
                "chapter": self.metadata.chapter,
                "section": self.metadata.section,
                "atom_type": self.metadata.atom_type.value,
                "cognitive_modality": self.metadata.cognitive_modality.value,
                "ps_index": self.metadata.ps_index,
                "pfit_index": self.metadata.pfit_index,
                "hippocampal_index": self.metadata.hippocampal_index,
            },
            "connections": [
                {
                    "target_id": c.target_id,
                    "type": c.connection_type.value,
                    "strength": c.strength,
                }
                for c in self.connections
            ],
            "concept_id": self.concept_id,
            "concept_name": self.concept_name,
            "stability": self.stability,
            "difficulty": self.difficulty,
            "lapses": self.lapses,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> LearningAtom:
        """Create atom from dictionary."""
        content_data = data.get("content", {})
        metadata_data = data.get("metadata", {})

        content = AtomContent(
            text=content_data.get("text", ""),
            latex=content_data.get("latex"),
            lean_code=content_data.get("lean_code"),
        )

        metadata = AtomMetadata(
            source=metadata_data.get("source", ""),
            chapter=metadata_data.get("chapter"),
            section=metadata_data.get("section"),
            atom_type=AtomType(metadata_data.get("atom_type", "fact")),
            cognitive_modality=CognitiveModality(
                metadata_data.get("cognitive_modality", "symbolic")
            ),
            ps_index=metadata_data.get("ps_index", 0.5),
            pfit_index=metadata_data.get("pfit_index", 0.5),
            hippocampal_index=metadata_data.get("hippocampal_index", 0.5),
        )

        connections = [
            AtomConnection(
                target_id=c["target_id"],
                connection_type=ConnectionType(c["type"]),
                strength=c.get("strength", 0.5),
            )
            for c in data.get("connections", [])
        ]

        return cls(
            id=data.get("id", str(uuid4())),
            content=content,
            metadata=metadata,
            connections=connections,
            concept_id=data.get("concept_id"),
            concept_name=data.get("concept_name"),
            stability=data.get("stability", 0.0),
            difficulty=data.get("difficulty", 0.3),
            lapses=data.get("lapses", 0),
        )


# =============================================================================
# KNOWLEDGE GRAPH
# =============================================================================


class KnowledgeGraph:
    """
    Graph structure for Learning Atoms.

    Provides:
    - Atom storage and retrieval
    - Prerequisite traversal
    - Confusable neighbor detection
    - Topological sorting for learning paths
    """

    def __init__(self):
        """Initialize empty knowledge graph."""
        self._atoms: dict[str, LearningAtom] = {}
        self._by_concept: dict[str, list[str]] = {}  # concept_id -> atom_ids
        self._adjacency: dict[str, list[str]] = {}  # atom_id -> connected atom_ids

    def add_atom(self, atom: LearningAtom) -> None:
        """Add an atom to the graph."""
        self._atoms[atom.id] = atom

        # Index by concept
        if atom.concept_id:
            if atom.concept_id not in self._by_concept:
                self._by_concept[atom.concept_id] = []
            self._by_concept[atom.concept_id].append(atom.id)

        # Build adjacency list
        self._adjacency[atom.id] = [c.target_id for c in atom.connections]

    def get_atom(self, atom_id: str) -> LearningAtom | None:
        """Get an atom by ID."""
        return self._atoms.get(atom_id)

    def get_atoms_for_concept(self, concept_id: str) -> list[LearningAtom]:
        """Get all atoms for a concept."""
        atom_ids = self._by_concept.get(concept_id, [])
        return [self._atoms[aid] for aid in atom_ids if aid in self._atoms]

    def get_prerequisites(self, atom_id: str) -> list[LearningAtom]:
        """Get all prerequisite atoms for an atom."""
        atom = self._atoms.get(atom_id)
        if not atom:
            return []

        prereq_ids = atom.prerequisites
        return [self._atoms[pid] for pid in prereq_ids if pid in self._atoms]

    def get_confusable_neighbors(
        self,
        atom_id: str,
        threshold: float = 0.7,
    ) -> list[tuple[LearningAtom, float]]:
        """
        Get atoms that might be confused with this one.

        Uses:
        1. Explicit adversarial connections
        2. High embedding similarity (if embeddings available)
        3. Same concept with high ps_index

        Returns:
            List of (atom, similarity_score) tuples
        """
        atom = self._atoms.get(atom_id)
        if not atom:
            return []

        confusables = []

        # 1. Explicit adversarial lures
        for lure_id in atom.adversarial_lures:
            if lure_id in self._atoms:
                confusables.append((self._atoms[lure_id], 0.95))

        # 2. Same concept atoms with high ps_index
        if atom.concept_id:
            for other_id in self._by_concept.get(atom.concept_id, []):
                if other_id != atom_id:
                    other = self._atoms[other_id]
                    if other.ps_index > threshold:
                        confusables.append((other, other.ps_index))

        # 3. Embedding similarity (if available)
        if atom.embedding and HAS_NUMPY:
            for other_id, other in self._atoms.items():
                if other_id != atom_id and other.embedding:
                    sim = self._cosine_similarity(atom.embedding, other.embedding)
                    if sim > threshold:
                        confusables.append((other, sim))

        # Deduplicate and sort by similarity
        seen = set()
        unique = []
        for a, score in sorted(confusables, key=lambda x: -x[1]):
            if a.id not in seen:
                seen.add(a.id)
                unique.append((a, score))

        return unique[:10]  # Top 10 confusables

    def _cosine_similarity(self, v1: list[float], v2: list[float]) -> float:
        """Calculate cosine similarity between two vectors."""
        if not HAS_NUMPY:
            # Fallback without numpy
            dot = sum(a * b for a, b in zip(v1, v2))
            norm1 = math.sqrt(sum(a * a for a in v1))
            norm2 = math.sqrt(sum(b * b for b in v2))
            return dot / (norm1 * norm2) if norm1 > 0 and norm2 > 0 else 0

        a1 = np.array(v1)
        a2 = np.array(v2)
        return float(np.dot(a1, a2) / (np.linalg.norm(a1) * np.linalg.norm(a2)))

    def get_learning_path(
        self,
        target_atom_id: str,
        mastered_atoms: set[str] | None = None,
    ) -> list[LearningAtom]:
        """
        Get the optimal learning path to master an atom.

        Uses topological sort on prerequisites, filtering out mastered atoms.

        Args:
            target_atom_id: The atom to learn
            mastered_atoms: Set of already-mastered atom IDs

        Returns:
            Ordered list of atoms to learn
        """
        if mastered_atoms is None:
            mastered_atoms = set()

        if target_atom_id not in self._atoms:
            return []

        # DFS to collect all prerequisites
        to_learn = set()
        visited = set()

        def collect_prereqs(atom_id: str) -> None:
            if atom_id in visited:
                return
            visited.add(atom_id)

            atom = self._atoms.get(atom_id)
            if not atom:
                return

            for prereq_id in atom.prerequisites:
                collect_prereqs(prereq_id)

            if atom_id not in mastered_atoms:
                to_learn.add(atom_id)

        collect_prereqs(target_atom_id)

        # Topological sort
        sorted_atoms = self._topological_sort(to_learn)

        return [self._atoms[aid] for aid in sorted_atoms if aid in self._atoms]

    def _topological_sort(self, atom_ids: set[str]) -> list[str]:
        """Topological sort of atoms by prerequisites."""
        in_degree = {aid: 0 for aid in atom_ids}
        graph = {aid: [] for aid in atom_ids}

        for aid in atom_ids:
            atom = self._atoms.get(aid)
            if not atom:
                continue
            for prereq_id in atom.prerequisites:
                if prereq_id in atom_ids:
                    graph[prereq_id].append(aid)
                    in_degree[aid] += 1

        # Kahn's algorithm
        queue = [aid for aid in atom_ids if in_degree[aid] == 0]
        result = []

        while queue:
            current = queue.pop(0)
            result.append(current)

            for neighbor in graph.get(current, []):
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)

        return result

    def infer_prerequisites(
        self,
        similarity_threshold: float = 0.8,
    ) -> list[AtomConnection]:
        """
        Infer prerequisite connections from embeddings.

        Uses semantic similarity to suggest missing prerequisite links.

        Returns:
            List of inferred connections (not yet added to graph)
        """
        if not HAS_NUMPY:
            logger.warning("Numpy required for prerequisite inference")
            return []

        inferred = []

        # Get atoms with embeddings
        atoms_with_embeddings = [a for a in self._atoms.values() if a.embedding is not None]

        if len(atoms_with_embeddings) < 2:
            return []

        # Compare all pairs
        for i, atom_a in enumerate(atoms_with_embeddings):
            for atom_b in atoms_with_embeddings[i + 1 :]:
                sim = self._cosine_similarity(atom_a.embedding, atom_b.embedding)

                if sim > similarity_threshold:
                    # Check if connection already exists
                    existing_connections = {c.target_id for c in atom_a.connections}

                    if atom_b.id not in existing_connections:
                        # Determine direction based on atom type hierarchy
                        if self._should_be_prerequisite(atom_a, atom_b):
                            inferred.append(
                                AtomConnection(
                                    target_id=atom_a.id,
                                    connection_type=ConnectionType.PREREQUISITE,
                                    strength=sim,
                                    inferred=True,
                                )
                            )
                        elif self._should_be_prerequisite(atom_b, atom_a):
                            inferred.append(
                                AtomConnection(
                                    target_id=atom_b.id,
                                    connection_type=ConnectionType.PREREQUISITE,
                                    strength=sim,
                                    inferred=True,
                                )
                            )

        return inferred

    def _should_be_prerequisite(self, atom_a: LearningAtom, atom_b: LearningAtom) -> bool:
        """Determine if atom_a should be a prerequisite for atom_b."""
        # Type hierarchy: definition < lemma < theorem < corollary
        type_order = {
            AtomType.DEFINITION: 0,
            AtomType.FACT: 1,
            AtomType.LEMMA: 2,
            AtomType.THEOREM: 3,
            AtomType.COROLLARY: 4,
            AtomType.PROOF_STEP: 3,
            AtomType.EXAMPLE: 4,
        }

        order_a = type_order.get(atom_a.metadata.atom_type, 2)
        order_b = type_order.get(atom_b.metadata.atom_type, 2)

        return order_a < order_b

    def calculate_ps_index(self, atom: LearningAtom) -> float:
        """
        Calculate Pattern Separation Index for an atom.

        Higher ps_index = more confusable with other atoms = needs
        more discrimination training.

        Factors:
        - Embedding similarity to other atoms
        - Number of atoms in same concept
        - Similar-sounding content
        """
        if atom.id not in self._atoms:
            return 0.5

        scores = []

        # Factor 1: Embedding similarity
        if atom.embedding:
            similarities = []
            for other_id, other in self._atoms.items():
                if other_id != atom.id and other.embedding:
                    sim = self._cosine_similarity(atom.embedding, other.embedding)
                    if sim > 0.5:  # Only count meaningful similarities
                        similarities.append(sim)

            if similarities:
                scores.append(max(similarities))

        # Factor 2: Concept crowding
        if atom.concept_id:
            concept_atoms = len(self._by_concept.get(atom.concept_id, []))
            crowding = min(1.0, concept_atoms / 20)  # Normalize to 20 atoms
            scores.append(crowding)

        # Factor 3: Existing adversarial lures
        if atom.adversarial_lures:
            scores.append(0.8 + 0.05 * len(atom.adversarial_lures))

        return sum(scores) / len(scores) if scores else 0.5

    def __len__(self) -> int:
        """Return number of atoms in graph."""
        return len(self._atoms)

    def __iter__(self) -> Iterator[LearningAtom]:
        """Iterate over atoms."""
        return iter(self._atoms.values())


# =============================================================================
# ATOM FACTORY
# =============================================================================


class AtomFactory:
    """
    Factory for creating Learning Atoms from various sources.

    Handles:
    - Creating atoms from raw text
    - Assigning cognitive indices
    - Generating embeddings
    - Detecting atom types
    """

    def __init__(self, embedding_model: Any | None = None):
        """
        Initialize the factory.

        Args:
            embedding_model: Optional model for generating embeddings
        """
        self.embedding_model = embedding_model

    def create_atom(
        self,
        text: str,
        latex: str | None = None,
        source: str = "",
        concept_name: str | None = None,
        concept_id: str | None = None,
        atom_type: AtomType | None = None,
    ) -> LearningAtom:
        """
        Create a Learning Atom from content.

        Args:
            text: Natural language content
            latex: Optional LaTeX representation
            source: Source reference
            concept_name: Associated concept name
            concept_id: Associated concept ID
            atom_type: Explicit atom type (or infer)

        Returns:
            LearningAtom with computed indices
        """
        # Infer atom type if not provided
        if atom_type is None:
            atom_type = self._infer_atom_type(text, latex)

        # Infer cognitive modality
        modality = self._infer_modality(text, latex)

        # Create atom
        atom = LearningAtom(
            id=str(uuid4()),
            content=AtomContent(
                text=text,
                latex=latex,
            ),
            metadata=AtomMetadata(
                source=source,
                atom_type=atom_type,
                cognitive_modality=modality,
                ps_index=0.5,  # Will be computed later
                pfit_index=self._estimate_pfit_index(text, atom_type),
                hippocampal_index=self._estimate_hippocampal_index(text),
                intrinsic_load=self._estimate_intrinsic_load(text, latex),
                created_at=datetime.now(),
            ),
            concept_id=concept_id,
            concept_name=concept_name,
        )

        # Generate embedding if model available
        if self.embedding_model:
            try:
                atom.embedding = self._generate_embedding(text)
            except Exception as e:
                logger.warning(f"Failed to generate embedding: {e}")

        return atom

    def _infer_atom_type(self, text: str, latex: str | None) -> AtomType:
        """Infer atom type from content."""
        text_lower = text.lower()

        if "definition" in text_lower or "is defined as" in text_lower:
            return AtomType.DEFINITION
        elif "theorem" in text_lower:
            return AtomType.THEOREM
        elif "lemma" in text_lower:
            return AtomType.LEMMA
        elif "corollary" in text_lower:
            return AtomType.COROLLARY
        elif "proof" in text_lower or "we show" in text_lower:
            return AtomType.PROOF_STEP
        elif "example" in text_lower or "consider" in text_lower:
            return AtomType.EXAMPLE
        elif "counter" in text_lower:
            return AtomType.COUNTER_EXAMPLE
        elif "step" in text_lower or "first" in text_lower:
            return AtomType.PROCEDURE
        elif latex and ("\\int" in latex or "\\sum" in latex or "\\frac" in latex):
            return AtomType.THEOREM
        else:
            return AtomType.FACT

    def _infer_modality(self, text: str, latex: str | None) -> CognitiveModality:
        """Infer cognitive modality from content."""
        text_lower = text.lower()

        if latex and len(latex) > 50:
            return CognitiveModality.SYMBOLIC

        if any(word in text_lower for word in ["step", "first", "then", "next", "finally"]):
            return CognitiveModality.PROCEDURAL

        if any(word in text_lower for word in ["graph", "diagram", "visualize", "plot", "curve"]):
            return CognitiveModality.VISUAL_SPATIAL

        if len(text) > 200 and not latex:
            return CognitiveModality.VERBAL

        return CognitiveModality.INTEGRATIVE

    def _estimate_pfit_index(self, text: str, atom_type: AtomType) -> float:
        """
        Estimate P-FIT index (integration difficulty).

        Higher = requires more integration between brain regions.
        """
        # Procedural atoms require more integration
        if atom_type in (AtomType.PROOF_STEP, AtomType.PROCEDURE):
            base = 0.7
        elif atom_type == AtomType.THEOREM:
            base = 0.6
        else:
            base = 0.4

        # Long text suggests more complexity
        length_factor = min(0.2, len(text) / 1000)

        # Multiple clauses suggest integration
        clause_factor = min(0.1, text.count(",") * 0.02)

        return min(1.0, base + length_factor + clause_factor)

    def _estimate_hippocampal_index(self, text: str) -> float:
        """
        Estimate hippocampal encoding difficulty.

        Higher = harder to encode (needs more elaboration).
        """
        # Longer = harder to encode
        length_factor = min(0.3, len(text) / 500)

        # Abstract words = harder to encode
        abstract_words = ["abstract", "concept", "relation", "property", "function"]
        abstract_count = sum(1 for w in abstract_words if w in text.lower())
        abstract_factor = min(0.3, abstract_count * 0.1)

        return 0.4 + length_factor + abstract_factor

    def _estimate_intrinsic_load(self, text: str, latex: str | None) -> float:
        """
        Estimate intrinsic cognitive load.

        Based on Sweller's Cognitive Load Theory.
        """
        load = 0.3  # Base load

        # Text length
        load += min(0.2, len(text) / 500)

        # LaTeX complexity
        if latex:
            symbols = latex.count("\\") + latex.count("{") + latex.count("^")
            load += min(0.3, symbols / 20)

        # Nesting (parentheses, fractions)
        nesting = text.count("(") + (latex.count("\\frac") if latex else 0)
        load += min(0.2, nesting * 0.05)

        return min(1.0, load)

    def _generate_embedding(self, text: str) -> list[float]:
        """Generate embedding vector for text."""
        if self.embedding_model is None:
            raise ValueError("No embedding model configured")

        # This would call the actual embedding model
        # For now, return placeholder
        return self.embedding_model.encode(text).tolist()


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================

# Global knowledge graph instance
_graph: KnowledgeGraph | None = None


def get_knowledge_graph() -> KnowledgeGraph:
    """Get or create the global knowledge graph."""
    global _graph
    if _graph is None:
        _graph = KnowledgeGraph()
    return _graph


def create_atom_from_flashcard(
    front: str,
    back: str,
    concept_name: str | None = None,
    source: str | None = None,
) -> LearningAtom:
    """
    Create a Learning Atom from a simple flashcard.

    Convenience function for migrating existing flashcards.
    """
    factory = AtomFactory()
    return factory.create_atom(
        text=f"{front}\n\nAnswer: {back}",
        source=source or "",
        concept_name=concept_name,
        atom_type=AtomType.FACT,
    )


def get_confusables(atom_id: str) -> list[dict[str, Any]]:
    """
    Get confusable atoms for discrimination training.

    Returns list of dicts with atom info and similarity scores.
    """
    graph = get_knowledge_graph()
    confusables = graph.get_confusable_neighbors(atom_id)

    return [
        {
            "id": atom.id,
            "content": atom.content.text[:200],
            "similarity": round(score, 3),
            "ps_index": round(atom.ps_index, 3),
        }
        for atom, score in confusables
    ]
