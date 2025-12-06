"""
Atom Deck: JSON Loader for Learning Atoms.

Loads and manages learning atoms from the generated JSON files:
- Auto-discovers outputs/module_*_atoms_*.json files
- Groups atoms by module and type for interleaving
- Filters by quality threshold
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Iterator

from loguru import logger


# =============================================================================
# Atom Data Class
# =============================================================================

@dataclass
class Atom:
    """
    A learning atom loaded from JSON.

    Represents a single reviewable item with its content,
    metadata, and quality metrics.
    """
    id: str
    card_id: str
    atom_type: str
    front: str
    back: str

    # Source traceability
    source_refs: list[dict] = field(default_factory=list)

    # Type-specific content (MCQ options, cloze deletions, etc.)
    content_json: Optional[dict] = None

    # Quality metrics
    quality_score: float = 0.0
    quality_grade: str = "C"

    # Metadata
    tags: list[str] = field(default_factory=list)
    module_number: int = 0
    knowledge_type: str = "factual"
    difficulty: int = 3
    blooms_level: str = "understand"
    derived_from_visual: bool = False

    # Fidelity tracking
    is_hydrated: bool = False
    fidelity_type: str = "verbatim_extract"
    source_fact_basis: Optional[str] = None

    @classmethod
    def from_dict(cls, data: dict) -> "Atom":
        """
        Create an Atom from a dictionary (JSON).

        Args:
            data: Dictionary from JSON file

        Returns:
            Atom instance
        """
        metadata = data.get("metadata", {})

        return cls(
            id=data["id"],
            card_id=data.get("card_id", data["id"]),
            atom_type=data["atom_type"],
            front=data["front"],
            back=data["back"],
            source_refs=data.get("source_refs", []),
            content_json=data.get("content_json"),
            quality_score=data.get("quality_score", 0),
            quality_grade=data.get("quality_grade", "C"),
            tags=data.get("tags", []),
            module_number=metadata.get("module_number", 0),
            knowledge_type=metadata.get("knowledge_type", "factual"),
            difficulty=metadata.get("difficulty", 3),
            blooms_level=metadata.get("blooms_level", "understand"),
            derived_from_visual=metadata.get("derived_from_visual", False),
            is_hydrated=metadata.get("is_hydrated", False),
            fidelity_type=metadata.get("fidelity_type", "verbatim_extract"),
            source_fact_basis=metadata.get("source_fact_basis"),
        )

    @property
    def is_interactive(self) -> bool:
        """Check if atom type requires user interaction (not just reveal)."""
        return self.atom_type in {"mcq", "true_false", "matching", "parsons", "numeric"}

    @property
    def has_options(self) -> bool:
        """Check if atom has multiple choice options."""
        return self.atom_type == "mcq" and self.content_json is not None

    def get_options(self) -> list[dict]:
        """Get MCQ options if available."""
        if not self.content_json:
            return []
        return self.content_json.get("options", [])

    def get_correct_answer(self) -> Optional[str]:
        """Get the correct answer for interactive types."""
        if not self.content_json:
            return None

        if self.atom_type == "mcq":
            correct_idx = self.content_json.get("correct_index", 0)
            options = self.content_json.get("options", [])
            if correct_idx < len(options):
                return options[correct_idx].get("text", "")

        elif self.atom_type == "true_false":
            return str(self.content_json.get("correct_answer", "")).lower()

        return None


# =============================================================================
# Atom Deck
# =============================================================================

class AtomDeck:
    """
    Manages a collection of learning atoms.

    Features:
    - Auto-discovery of JSON output files
    - Quality filtering (default: 85.0 threshold)
    - Grouping by module and atom type
    - Iteration and sampling methods
    """

    DEFAULT_OUTPUT_DIR = Path("outputs")
    DEFAULT_QUALITY_THRESHOLD = 85.0

    def __init__(
        self,
        output_dir: Optional[Path] = None,
        quality_threshold: float = DEFAULT_QUALITY_THRESHOLD,
    ):
        """
        Initialize the atom deck.

        Args:
            output_dir: Directory containing JSON files (default: outputs/)
            quality_threshold: Minimum quality score for inclusion
        """
        self.output_dir = output_dir or self.DEFAULT_OUTPUT_DIR
        self.quality_threshold = quality_threshold

        # Storage
        self._atoms: dict[str, Atom] = {}  # id -> Atom
        self._by_module: dict[int, list[str]] = {}  # module -> [atom_ids]
        self._by_type: dict[str, list[str]] = {}  # type -> [atom_ids]

        # Stats
        self._files_loaded: list[Path] = []
        self._atoms_filtered: int = 0

    @property
    def total_atoms(self) -> int:
        """Total atoms in the deck."""
        return len(self._atoms)

    @property
    def modules(self) -> list[int]:
        """List of modules with atoms."""
        return sorted(self._by_module.keys())

    @property
    def atom_types(self) -> list[str]:
        """List of atom types in the deck."""
        return sorted(self._by_type.keys())

    def load(self) -> int:
        """
        Load atoms from all discovered JSON files.

        Returns:
            Number of atoms loaded
        """
        self._atoms.clear()
        self._by_module.clear()
        self._by_type.clear()
        self._files_loaded.clear()
        self._atoms_filtered = 0

        # Discover JSON files
        pattern = "module_*_atoms_*.json"
        json_files = list(self.output_dir.glob(pattern))

        if not json_files:
            logger.warning(f"No JSON files found in {self.output_dir}")
            return 0

        # Load each file
        for json_path in sorted(json_files):
            self._load_file(json_path)

        logger.info(
            f"AtomDeck loaded: {self.total_atoms} atoms from {len(self._files_loaded)} files "
            f"({self._atoms_filtered} filtered below {self.quality_threshold} threshold)"
        )

        return self.total_atoms

    def _load_file(self, path: Path) -> int:
        """
        Load atoms from a single JSON file.

        Args:
            path: Path to JSON file

        Returns:
            Number of atoms loaded from this file
        """
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            logger.error(f"Failed to load {path}: {e}")
            return 0

        atoms_list = data if isinstance(data, list) else data.get("atoms", [])
        loaded = 0

        for atom_data in atoms_list:
            try:
                atom = Atom.from_dict(atom_data)

                # Quality filter
                if atom.quality_score < self.quality_threshold:
                    self._atoms_filtered += 1
                    continue

                # Store atom
                self._atoms[atom.id] = atom

                # Index by module
                if atom.module_number not in self._by_module:
                    self._by_module[atom.module_number] = []
                self._by_module[atom.module_number].append(atom.id)

                # Index by type
                if atom.atom_type not in self._by_type:
                    self._by_type[atom.atom_type] = []
                self._by_type[atom.atom_type].append(atom.id)

                loaded += 1

            except (KeyError, TypeError) as e:
                logger.warning(f"Invalid atom in {path}: {e}")
                continue

        self._files_loaded.append(path)
        logger.debug(f"Loaded {loaded} atoms from {path.name}")
        return loaded

    # =========================================================================
    # Access Methods
    # =========================================================================

    def get(self, atom_id: str) -> Optional[Atom]:
        """Get an atom by ID."""
        return self._atoms.get(atom_id)

    def get_all(self) -> list[Atom]:
        """Get all atoms."""
        return list(self._atoms.values())

    def get_atom_ids(self) -> list[str]:
        """Get all atom IDs."""
        return list(self._atoms.keys())

    def get_by_module(self, module_number: int) -> list[Atom]:
        """Get all atoms from a specific module."""
        atom_ids = self._by_module.get(module_number, [])
        return [self._atoms[aid] for aid in atom_ids]

    def get_by_type(self, atom_type: str) -> list[Atom]:
        """Get all atoms of a specific type."""
        atom_ids = self._by_type.get(atom_type, [])
        return [self._atoms[aid] for aid in atom_ids]

    def get_by_ids(self, atom_ids: list[str]) -> list[Atom]:
        """
        Get atoms by a list of IDs.

        Args:
            atom_ids: List of atom IDs

        Returns:
            List of Atoms (skips missing IDs)
        """
        return [
            self._atoms[aid]
            for aid in atom_ids
            if aid in self._atoms
        ]

    def __iter__(self) -> Iterator[Atom]:
        """Iterate over all atoms."""
        return iter(self._atoms.values())

    def __len__(self) -> int:
        """Number of atoms in deck."""
        return len(self._atoms)

    def __contains__(self, atom_id: str) -> bool:
        """Check if atom ID exists in deck."""
        return atom_id in self._atoms

    # =========================================================================
    # Filtering Methods
    # =========================================================================

    def filter_new(self, reviewed_ids: set[str]) -> list[Atom]:
        """
        Get atoms that haven't been reviewed yet.

        Args:
            reviewed_ids: Set of already reviewed atom IDs

        Returns:
            List of new (unreviewed) atoms
        """
        return [
            atom for atom in self._atoms.values()
            if atom.id not in reviewed_ids
        ]

    def filter_by_difficulty(
        self,
        min_difficulty: int = 1,
        max_difficulty: int = 5,
    ) -> list[Atom]:
        """
        Filter atoms by difficulty range.

        Args:
            min_difficulty: Minimum difficulty (1-5)
            max_difficulty: Maximum difficulty (1-5)

        Returns:
            Filtered atoms
        """
        return [
            atom for atom in self._atoms.values()
            if min_difficulty <= atom.difficulty <= max_difficulty
        ]

    def filter_interactive(self) -> list[Atom]:
        """Get only interactive atoms (MCQ, true/false, etc.)."""
        return [atom for atom in self._atoms.values() if atom.is_interactive]

    # =========================================================================
    # Statistics
    # =========================================================================

    def get_stats(self) -> dict:
        """
        Get deck statistics.

        Returns:
            Dictionary with deck stats
        """
        if not self._atoms:
            return {"status": "empty", "files_loaded": 0, "total_atoms": 0}

        quality_scores = [a.quality_score for a in self._atoms.values()]
        difficulties = [a.difficulty for a in self._atoms.values()]

        return {
            "files_loaded": len(self._files_loaded),
            "total_atoms": self.total_atoms,
            "atoms_filtered": self._atoms_filtered,
            "modules": {
                mod: len(ids)
                for mod, ids in sorted(self._by_module.items())
            },
            "by_type": {
                t: len(ids)
                for t, ids in sorted(self._by_type.items())
            },
            "quality": {
                "min": min(quality_scores),
                "max": max(quality_scores),
                "avg": sum(quality_scores) / len(quality_scores),
            },
            "difficulty": {
                "min": min(difficulties),
                "max": max(difficulties),
                "avg": sum(difficulties) / len(difficulties),
            },
        }

    def sync(self) -> int:
        """
        Reload atoms from disk (alias for load).

        Returns:
            Number of atoms loaded
        """
        return self.load()
