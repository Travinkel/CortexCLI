"""
Base Loader Class.

Provides the abstract base for all atom loaders.
Supports different storage backends and upsert strategies.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, ClassVar

from ..models import TransformedAtom
from ..pipeline import LoadResult

logger = logging.getLogger(__name__)


# =============================================================================
# Loader Configuration
# =============================================================================


class UpsertStrategy(str, Enum):
    """Strategy for handling existing atoms."""

    INSERT_ONLY = "insert_only"  # Fail on conflict
    UPDATE_ALWAYS = "update_always"  # Always update existing
    UPDATE_IF_NEWER = "update_if_newer"  # Update if generated_at is newer
    SKIP_EXISTING = "skip_existing"  # Skip existing atoms


@dataclass
class LoaderConfig:
    """Configuration for loaders."""

    # Upsert behavior
    upsert_strategy: UpsertStrategy = UpsertStrategy.UPDATE_IF_NEWER

    # Batching
    batch_size: int = 100

    # Validation
    validate_before_load: bool = True

    # Logging
    log_operations: bool = True

    # Error handling
    continue_on_error: bool = True


# =============================================================================
# Base Loader
# =============================================================================


class BaseLoader(ABC):
    """
    Abstract base class for atom loaders.

    Loaders are responsible for:
    1. Persisting transformed atoms to storage
    2. Handling upserts (insert or update)
    3. Managing transactions and batching

    Subclasses must implement:
    - _insert_batch(): Insert a batch of atoms
    - _update_batch(): Update existing atoms
    - _check_existing(): Check which atoms already exist
    """

    name: ClassVar[str] = "base_loader"
    version: ClassVar[str] = "1.0.0"

    def __init__(self, config: LoaderConfig | None = None):
        """
        Initialize loader.

        Args:
            config: Loader configuration
        """
        self.config = config or LoaderConfig()
        self._stats = LoaderStats()

    async def load(self, atoms: list[TransformedAtom]) -> LoadResult:
        """
        Load atoms into storage.

        Args:
            atoms: Transformed atoms to load

        Returns:
            LoadResult with counts and errors
        """
        result = LoadResult()

        # Validate if configured
        if self.config.validate_before_load:
            atoms = [a for a in atoms if a.validation_passed]
            result.skipped = len(atoms) - len(atoms)

        # Process in batches
        for i in range(0, len(atoms), self.config.batch_size):
            batch = atoms[i : i + self.config.batch_size]

            try:
                batch_result = await self._process_batch(batch)
                result.inserted += batch_result.inserted
                result.updated += batch_result.updated
                result.skipped += batch_result.skipped
                result.failed += batch_result.failed
                result.errors.extend(batch_result.errors)

            except Exception as e:
                logger.error(f"Batch load failed: {e}")
                result.failed += len(batch)
                result.errors.append(str(e))

                if not self.config.continue_on_error:
                    raise

        self._log_result(result)
        return result

    async def _process_batch(self, batch: list[TransformedAtom]) -> LoadResult:
        """
        Process a single batch of atoms.

        Args:
            batch: Batch of atoms

        Returns:
            LoadResult for this batch
        """
        result = LoadResult()

        # Check which atoms already exist
        atom_ids = [str(atom.id) for atom in batch]
        existing_ids = await self._check_existing(atom_ids)

        # Separate new and existing atoms
        new_atoms = [a for a in batch if str(a.id) not in existing_ids]
        existing_atoms = [a for a in batch if str(a.id) in existing_ids]

        # Handle based on strategy
        strategy = self.config.upsert_strategy

        # Insert new atoms
        if new_atoms:
            insert_result = await self._insert_batch(new_atoms)
            result.inserted = insert_result.inserted
            result.failed += insert_result.failed
            result.errors.extend(insert_result.errors)

        # Handle existing atoms based on strategy
        if existing_atoms:
            if strategy == UpsertStrategy.INSERT_ONLY:
                result.failed += len(existing_atoms)
                result.errors.append(
                    f"{len(existing_atoms)} atoms already exist (INSERT_ONLY mode)"
                )

            elif strategy == UpsertStrategy.SKIP_EXISTING:
                result.skipped += len(existing_atoms)

            elif strategy == UpsertStrategy.UPDATE_ALWAYS:
                update_result = await self._update_batch(existing_atoms)
                result.updated = update_result.updated
                result.failed += update_result.failed
                result.errors.extend(update_result.errors)

            elif strategy == UpsertStrategy.UPDATE_IF_NEWER:
                # Filter to only newer atoms
                newer_atoms = await self._filter_newer(existing_atoms)
                if newer_atoms:
                    update_result = await self._update_batch(newer_atoms)
                    result.updated = update_result.updated
                    result.failed += update_result.failed
                    result.errors.extend(update_result.errors)
                result.skipped += len(existing_atoms) - len(newer_atoms)

        return result

    @abstractmethod
    async def _insert_batch(self, atoms: list[TransformedAtom]) -> LoadResult:
        """
        Insert a batch of new atoms.

        Args:
            atoms: Atoms to insert

        Returns:
            LoadResult for insertions
        """
        ...

    @abstractmethod
    async def _update_batch(self, atoms: list[TransformedAtom]) -> LoadResult:
        """
        Update a batch of existing atoms.

        Args:
            atoms: Atoms to update

        Returns:
            LoadResult for updates
        """
        ...

    @abstractmethod
    async def _check_existing(self, atom_ids: list[str]) -> set[str]:
        """
        Check which atom IDs already exist in storage.

        Args:
            atom_ids: List of atom IDs to check

        Returns:
            Set of IDs that already exist
        """
        ...

    async def _filter_newer(
        self, atoms: list[TransformedAtom]
    ) -> list[TransformedAtom]:
        """
        Filter to atoms newer than existing versions.

        Default implementation returns all atoms.
        Override for storage-specific timestamp comparison.
        """
        return atoms

    def _log_result(self, result: LoadResult) -> None:
        """Log load result."""
        if self.config.log_operations:
            logger.info(
                f"{self.name}: inserted={result.inserted}, "
                f"updated={result.updated}, "
                f"skipped={result.skipped}, "
                f"failed={result.failed}"
            )


# =============================================================================
# Loader Statistics
# =============================================================================


@dataclass
class LoaderStats:
    """Statistics for a loading run."""

    batches_processed: int = 0
    atoms_inserted: int = 0
    atoms_updated: int = 0
    atoms_skipped: int = 0
    atoms_failed: int = 0
    errors: list[str] = field(default_factory=list)


# =============================================================================
# Dry Run Loader (for testing)
# =============================================================================


class DryRunLoader(BaseLoader):
    """
    Loader that simulates loading without persisting.

    Useful for testing pipelines and validating output.
    """

    name = "dry_run"

    def __init__(self, config: LoaderConfig | None = None):
        super().__init__(config)
        self.loaded_atoms: list[TransformedAtom] = []

    async def _insert_batch(self, atoms: list[TransformedAtom]) -> LoadResult:
        """Simulate insert."""
        self.loaded_atoms.extend(atoms)
        return LoadResult(inserted=len(atoms))

    async def _update_batch(self, atoms: list[TransformedAtom]) -> LoadResult:
        """Simulate update."""
        # Replace existing with updated
        for atom in atoms:
            self.loaded_atoms = [a for a in self.loaded_atoms if a.id != atom.id]
            self.loaded_atoms.append(atom)
        return LoadResult(updated=len(atoms))

    async def _check_existing(self, atom_ids: list[str]) -> set[str]:
        """Check against in-memory atoms."""
        existing = {str(a.id) for a in self.loaded_atoms}
        return existing & set(atom_ids)


# =============================================================================
# JSON File Loader (for debugging)
# =============================================================================


class JSONFileLoader(BaseLoader):
    """
    Loader that writes atoms to a JSON file.

    Useful for debugging and manual inspection.
    """

    name = "json_file"

    def __init__(self, output_path: str, config: LoaderConfig | None = None):
        super().__init__(config)
        self.output_path = output_path
        self._atoms: list[dict[str, Any]] = []

    async def _insert_batch(self, atoms: list[TransformedAtom]) -> LoadResult:
        """Append atoms to internal list."""
        for atom in atoms:
            self._atoms.append(atom.to_dict())
        self._write_file()
        return LoadResult(inserted=len(atoms))

    async def _update_batch(self, atoms: list[TransformedAtom]) -> LoadResult:
        """Update atoms in internal list."""
        for atom in atoms:
            atom_dict = atom.to_dict()
            # Find and replace
            for i, existing in enumerate(self._atoms):
                if existing["id"] == atom_dict["id"]:
                    self._atoms[i] = atom_dict
                    break
        self._write_file()
        return LoadResult(updated=len(atoms))

    async def _check_existing(self, atom_ids: list[str]) -> set[str]:
        """Check against file contents."""
        existing = {a["id"] for a in self._atoms}
        return existing & set(atom_ids)

    def _write_file(self) -> None:
        """Write atoms to JSON file."""
        import json
        from pathlib import Path

        Path(self.output_path).write_text(
            json.dumps(self._atoms, indent=2, default=str),
            encoding="utf-8",
        )
