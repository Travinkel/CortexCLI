"""
Atom Deck: Learning Atom Loader.

Loads and manages learning atoms from:
- PostgreSQL database (primary, via load_from_db)
- JSON files (fallback, via load)

Features:
- Groups atoms by module and type for interleaving
- Filters by quality threshold
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

from loguru import logger

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

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
    content_json: dict | None = None

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
    media_type: str | None = None
    media_code: str | None = None

    # Fidelity tracking
    is_hydrated: bool = False
    fidelity_type: str = "verbatim_extract"
    source_fact_basis: str | None = None

    # CCNA-specific metadata
    objective_code: str | None = None
    prerequisites: list[str] = field(default_factory=list)
    validation: dict | None = None
    validation_passed: bool = False
    hints: list[str] = field(default_factory=list)
    explanation: str | None = None

    @classmethod
    def from_dict(cls, data: dict) -> Atom:
        """
        Create an Atom from a dictionary (JSON).

        Args:
            data: Dictionary from JSON file

        Returns:
            Atom instance
        """
        metadata = data.get("metadata", {})
        content_json = data.get("content_json")
        validation = metadata.get("validation") or data.get("validation") or {}
        explanation = None
        hints: list[str] = []
        if isinstance(content_json, dict):
            explanation = content_json.get("explanation")
            hints = content_json.get("hints") or []

        return cls(
            id=data["id"],
            card_id=data.get("card_id", data["id"]),
            atom_type=data["atom_type"],
            front=data["front"],
            back=data["back"],
            source_refs=data.get("source_refs", []),
            content_json=content_json,
            quality_score=data.get("quality_score", 0),
            quality_grade=data.get("quality_grade", "C"),
            tags=data.get("tags", []),
            module_number=metadata.get("module_number", 0),
            knowledge_type=metadata.get("knowledge_type", "factual"),
            difficulty=metadata.get("difficulty", 3),
            blooms_level=metadata.get("blooms_level", "understand"),
            derived_from_visual=metadata.get("derived_from_visual", False),
            media_type=data.get("media_type") or metadata.get("media_type"),
            media_code=data.get("media_code") or metadata.get("media_code"),
            is_hydrated=metadata.get("is_hydrated", False),
            fidelity_type=metadata.get("fidelity_type", "verbatim_extract"),
            source_fact_basis=metadata.get("source_fact_basis"),
            objective_code=metadata.get("objective_code") or data.get("objective_code"),
            prerequisites=metadata.get("prerequisites")
            or data.get("prerequisites", [])
            or [],
            validation=validation if isinstance(validation, dict) else {},
            validation_passed=bool(
                data.get("validation_passed") or metadata.get("validation_passed") or False
            ),
            hints=hints if isinstance(hints, list) else [],
            explanation=explanation,
        )

    @property
    def is_interactive(self) -> bool:
        """Check if atom type requires user interaction (not just reveal).

        New interactive types supported to improve learnability coverage:
        - ordering: user orders items correctly (aka sequencing)
        - labeling: user assigns labels to parts (e.g., diagram labeling)
        - hotspot: user identifies a region or item (e.g., choose the interface on a diagram)
        - case_scenario: interactive multi-step scenario with decisions
        """
        return self.atom_type in {
            "mcq",
            "true_false",
            "matching",
            "parsons",
            "numeric",
            "ordering",
            "labeling",
            "hotspot",
            "case_scenario",
        }

    @property
    def has_options(self) -> bool:
        """Check if atom exposes selectable options.

        Supported option-bearing types:
        - mcq: options[] with one correct_index
        - ordering: options[] with a correct_order (list of indices/ids)
        """
        if not self.content_json:
            return False
        if self.atom_type in {"mcq", "ordering"}:
            return bool(self.content_json.get("options"))
        return False

    def get_options(self) -> list[dict]:
        """Get options for option-bearing types (mcq, ordering)."""
        if not self.content_json:
            return []
        return self.content_json.get("options", [])

    def get_correct_answer(self) -> str | None:
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

        elif self.atom_type == "numeric":
            # Return the canonical string form of the correct value if present
            val = self.content_json.get("correct_value")
            return None if val is None else str(val)

        # For complex types like ordering/labeling/parsons/hotspot, the correct answer
        # is structured; this method intentionally returns None to avoid lossy casting.

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
        output_dir: Path | None = None,
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
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, json.JSONDecodeError) as e:
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

    def load_from_db(self, db: Session | None = None) -> int:
        """
        Load atoms directly from PostgreSQL database.

        This is the preferred method - loads from canonical learning_atoms table.

        Args:
            db: SQLAlchemy session (optional, will create one if not provided)

        Returns:
            Number of atoms loaded
        """
        from sqlalchemy import text
        from src.db.database import get_db

        self._atoms.clear()
        self._by_module.clear()
        self._by_type.clear()
        self._files_loaded.clear()
        self._atoms_filtered = 0

        # Get database session
        if db is None:
            db = next(get_db())

        # Query all valid atoms
        sql = text("""
            SELECT
                id, card_id, atom_type, front, back,
                quality_score, quiz_question_metadata,
                media_type, media_code, source_fact_basis,
                is_hydrated, fidelity_type
            FROM learning_atoms
            WHERE front IS NOT NULL AND back IS NOT NULL
        """)

        rows = db.execute(sql).fetchall()
        loaded = 0

        for row in rows:
            try:
                # Build quality score (0-1 scale, convert to 0-100 for threshold)
                quality = float(row.quality_score) * 100 if row.quality_score else 70.0

                # Quality filter
                if quality < self.quality_threshold:
                    self._atoms_filtered += 1
                    continue

                # Create Atom instance
                atom = Atom(
                    id=str(row.id),
                    card_id=row.card_id or f"CARD-{str(row.id)[:8]}",
                    atom_type=row.atom_type or "flashcard",
                    front=row.front,
                    back=row.back,
                    source_refs=[{"excerpt": row.source_fact_basis}] if row.source_fact_basis else [],
                    content_json=row.quiz_question_metadata,
                    quality_score=quality,
                    media_type=row.media_type,
                    media_code=row.media_code,
                    is_hydrated=row.is_hydrated or False,
                    fidelity_type=row.fidelity_type or "verbatim_extract",
                    difficulty=3,
                    knowledge_type="factual",
                )

                # Store atom
                self._atoms[atom.id] = atom

                # Index by module (default to 0)
                if atom.module_number not in self._by_module:
                    self._by_module[atom.module_number] = []
                self._by_module[atom.module_number].append(atom.id)

                # Index by type
                if atom.atom_type not in self._by_type:
                    self._by_type[atom.atom_type] = []
                self._by_type[atom.atom_type].append(atom.id)

                loaded += 1

            except Exception as e:
                logger.warning(f"Invalid atom {row.id}: {e}")
                continue

        logger.info(
            f"AtomDeck loaded from DB: {self.total_atoms} atoms "
            f"({self._atoms_filtered} filtered below {self.quality_threshold} threshold)"
        )

        return self.total_atoms

    # =========================================================================
    # Access Methods
    # =========================================================================

    def get(self, atom_id: str) -> Atom | None:
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
        return [self._atoms[aid] for aid in atom_ids if aid in self._atoms]

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
        return [atom for atom in self._atoms.values() if atom.id not in reviewed_ids]

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
            atom
            for atom in self._atoms.values()
            if min_difficulty <= atom.difficulty <= max_difficulty
        ]

    def filter_interactive(self) -> list[Atom]:
        """Get only interactive atoms (MCQ, true/false, etc.)."""
        return [atom for atom in self._atoms.values() if atom.is_interactive]

    def filter_learnable_ready(self, min_quality: float | None = None) -> list[Atom]:
        """Filter atoms that are considered learnable-ready.

        Criteria (lightweight, data-available):
        - quality_score >= threshold (deck threshold by default)
        - has non-empty front/back
        - has explanation in content_json when available (preferred)

        Args:
            min_quality: Override minimum quality score; defaults to deck threshold

        Returns:
            List of atoms considered ready for study
        """
        qmin = self.quality_threshold if min_quality is None else float(min_quality)

        def has_explanation(a: Atom) -> bool:
            exp = a.explanation
            if exp is None and a.content_json and isinstance(a.content_json, dict):
                exp = a.content_json.get("explanation")
            return bool(exp and str(exp).strip())

        ready: list[Atom] = []
        for a in self._atoms.values():
            if a.quality_score < qmin:
                continue
            if not (str(a.front).strip() and str(a.back).strip()):
                continue
            # If validation metadata exists, require it to be passing
            if a.validation and not a.validation_passed:
                continue
            # Prefer atoms with explanations when provided for higher difficulties
            if a.difficulty >= 3 and not has_explanation(a):
                continue
            ready.append(a)
        return ready

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
        ready_atoms = self.filter_learnable_ready()
        ready_ids = {a.id for a in ready_atoms}

        # Explanations coverage (proxy for feedback completeness)
        def has_explanation(a: Atom) -> bool:
            exp = a.explanation
            if exp is None and a.content_json and isinstance(a.content_json, dict):
                exp = a.content_json.get("explanation")
            return bool(exp and str(exp).strip())

        explanations_total = sum(1 for a in self._atoms.values() if has_explanation(a))
        ready_count = len(ready_atoms)

        # Objective coverage and prerequisite resolvability
        objective_codes = [a.objective_code for a in self._atoms.values() if a.objective_code]
        unique_objectives = set(objective_codes)

        def prerequisites_resolvable(a: Atom) -> bool:
            if not a.prerequisites:
                return True
            return all(pr in self._atoms for pr in a.prerequisites)

        resolvable_count = sum(1 for a in self._atoms.values() if prerequisites_resolvable(a))

        # Per-module simple completeness metrics
        per_module = {}
        for mod, ids in sorted(self._by_module.items()):
            atoms_mod = [self._atoms[i] for i in ids]
            if not atoms_mod:
                per_module[mod] = {
                    "count": 0,
                    "explanations_pct": 0.0,
                    "ready_pct": 0.0,
                    "objective_coverage_pct": 0.0,
                    "prerequisites_resolvable_pct": 0.0,
                }
                continue
            exp_count = sum(1 for a in atoms_mod if has_explanation(a))
            ready_mod = [a for a in atoms_mod if a.id in ready_ids]
            objectives_mod = {a.objective_code for a in atoms_mod if a.objective_code}
            resolvable_mod = [a for a in atoms_mod if prerequisites_resolvable(a)]
            per_module[mod] = {
                "count": len(atoms_mod),
                "explanations_pct": round(100.0 * exp_count / len(atoms_mod), 1),
                "ready_pct": round(100.0 * len(ready_mod) / len(atoms_mod), 1),
                "objective_coverage_pct": round(100.0 * len(objectives_mod) / len(atoms_mod), 1),
                "prerequisites_resolvable_pct": round(100.0 * len(resolvable_mod) / len(atoms_mod), 1),
            }

        return {
            "files_loaded": len(self._files_loaded),
            "total_atoms": self.total_atoms,
            "atoms_filtered": self._atoms_filtered,
            "modules": {mod: len(ids) for mod, ids in sorted(self._by_module.items())},
            "by_type": {t: len(ids) for t, ids in sorted(self._by_type.items())},
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
            "completeness": {
                "explanations_pct": round(100.0 * explanations_total / self.total_atoms, 1),
                "ready_count": ready_count,
                "ready_pct": round(100.0 * ready_count / self.total_atoms, 1),
                "objective_coverage_pct": round(
                    100.0 * len(unique_objectives) / self.total_atoms, 1
                ),
                "prerequisites_resolvable_pct": round(
                    100.0 * resolvable_count / self.total_atoms, 1
                ),
                "per_module": per_module,
            },
        }

    def sync(self) -> int:
        """
        Reload atoms from disk (alias for load).

        Returns:
            Number of atoms loaded
        """
        return self.load()
