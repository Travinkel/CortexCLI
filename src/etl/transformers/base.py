"""
Base Transformer Class.

Provides the abstract base for all atom transformers.
Supports chain of responsibility pattern for composable transformations.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, ClassVar

from ..models import RawChunk, TransformedAtom

logger = logging.getLogger(__name__)


# =============================================================================
# Transformer Configuration
# =============================================================================


@dataclass
class TransformerConfig:
    """Base configuration for transformers."""

    # Generation settings
    max_atoms_per_chunk: int = 5
    min_quality_score: float = 0.6

    # Validation
    validate_output: bool = True

    # Logging
    log_transformations: bool = True


# =============================================================================
# Base Transformer
# =============================================================================


class BaseTransformer(ABC):
    """
    Abstract base class for atom transformers.

    Transformers are responsible for:
    1. Converting RawChunks into TransformedAtoms (initial transformer)
    2. Enhancing existing atoms with additional metadata (enhancement transformers)

    Two modes of operation:
    - transform(): Converts chunks to atoms (first in chain)
    - enhance(): Adds metadata to existing atoms (subsequent in chain)

    Subclasses must implement at least one of:
    - _transform_chunk(): For initial transformation
    - _enhance_atom(): For enhancement
    """

    name: ClassVar[str] = "base_transformer"
    version: ClassVar[str] = "1.0.0"

    def __init__(self, config: TransformerConfig | None = None):
        """
        Initialize transformer.

        Args:
            config: Transformer configuration
        """
        self.config = config or TransformerConfig()
        self._stats = TransformationStats()

    async def transform(self, chunks: list[RawChunk]) -> list[TransformedAtom]:
        """
        Transform raw chunks into atoms.

        This is the main entry point for the first transformer in a chain.

        Args:
            chunks: Raw content chunks

        Returns:
            List of transformed atoms
        """
        atoms: list[TransformedAtom] = []

        for chunk in chunks:
            try:
                chunk_atoms = await self._transform_chunk(chunk)

                # Apply quality filter
                for atom in chunk_atoms:
                    if atom.quality_score >= self.config.min_quality_score:
                        atoms.append(atom)
                        self._stats.atoms_created += 1
                    else:
                        self._stats.atoms_filtered += 1

            except Exception as e:
                logger.error(f"Failed to transform chunk {chunk.chunk_id}: {e}")
                self._stats.chunks_failed += 1

        self._stats.chunks_processed = len(chunks)
        self._log_stats()
        return atoms

    async def enhance(self, atoms: list[TransformedAtom]) -> list[TransformedAtom]:
        """
        Enhance existing atoms with additional metadata.

        This is the entry point for subsequent transformers in a chain.

        Args:
            atoms: Atoms to enhance

        Returns:
            Enhanced atoms
        """
        enhanced: list[TransformedAtom] = []

        for atom in atoms:
            try:
                enhanced_atom = await self._enhance_atom(atom)
                enhanced.append(enhanced_atom)
                self._stats.atoms_enhanced += 1
            except Exception as e:
                logger.error(f"Failed to enhance atom {atom.card_id}: {e}")
                enhanced.append(atom)  # Keep original on failure
                self._stats.atoms_failed += 1

        self._log_stats()
        return enhanced

    @abstractmethod
    async def _transform_chunk(self, chunk: RawChunk) -> list[TransformedAtom]:
        """
        Transform a single chunk into atoms.

        Override this for initial transformation (chunk -> atoms).

        Args:
            chunk: Raw content chunk

        Returns:
            List of atoms generated from this chunk
        """
        ...

    async def _enhance_atom(self, atom: TransformedAtom) -> TransformedAtom:
        """
        Enhance a single atom with additional metadata.

        Override this for enhancement transformation (atom -> atom).

        Args:
            atom: Atom to enhance

        Returns:
            Enhanced atom
        """
        # Default: no enhancement
        return atom

    def _log_stats(self) -> None:
        """Log transformation statistics."""
        if self.config.log_transformations:
            logger.info(
                f"{self.name}: processed={self._stats.chunks_processed}, "
                f"created={self._stats.atoms_created}, "
                f"enhanced={self._stats.atoms_enhanced}, "
                f"filtered={self._stats.atoms_filtered}, "
                f"failed={self._stats.atoms_failed}"
            )


# =============================================================================
# Transformation Statistics
# =============================================================================


@dataclass
class TransformationStats:
    """Statistics for a transformation run."""

    chunks_processed: int = 0
    chunks_failed: int = 0
    atoms_created: int = 0
    atoms_enhanced: int = 0
    atoms_filtered: int = 0
    atoms_failed: int = 0

    def to_dict(self) -> dict[str, int]:
        """Serialize to dictionary."""
        return {
            "chunks_processed": self.chunks_processed,
            "chunks_failed": self.chunks_failed,
            "atoms_created": self.atoms_created,
            "atoms_enhanced": self.atoms_enhanced,
            "atoms_filtered": self.atoms_filtered,
            "atoms_failed": self.atoms_failed,
        }


# =============================================================================
# Transformer Chain
# =============================================================================


class TransformerChain:
    """
    Chain of transformers for composable transformations.

    Example:
        chain = TransformerChain([
            AtomGenerator(),      # Chunk -> Atoms
            ICAPClassifier(),     # Atom -> Atom (add ICAP)
            SkillMapper(),        # Atom -> Atom (add skills)
            QualityScorer(),      # Atom -> Atom (add quality score)
        ])

        atoms = await chain.run(chunks)
    """

    def __init__(self, transformers: list[BaseTransformer]):
        """
        Initialize chain.

        Args:
            transformers: Ordered list of transformers
        """
        if not transformers:
            raise ValueError("Chain requires at least one transformer")
        self.transformers = transformers

    async def run(self, chunks: list[RawChunk]) -> list[TransformedAtom]:
        """
        Run the transformation chain.

        Args:
            chunks: Raw content chunks

        Returns:
            Fully transformed atoms
        """
        # First transformer: chunks -> atoms
        atoms = await self.transformers[0].transform(chunks)

        # Subsequent transformers: atoms -> atoms (enhancement)
        for transformer in self.transformers[1:]:
            atoms = await transformer.enhance(atoms)

        return atoms


# =============================================================================
# Common Utility Transformers
# =============================================================================


class PassthroughTransformer(BaseTransformer):
    """
    Passthrough transformer that does nothing.

    Useful for testing and as a placeholder.
    """

    name = "passthrough"

    async def _transform_chunk(self, chunk: RawChunk) -> list[TransformedAtom]:
        """Create a minimal atom from chunk."""
        from ..models import AtomContent

        atom = TransformedAtom(
            card_id=f"{chunk.source_type}_{chunk.chunk_id}",
            atom_type="flashcard",
            content=AtomContent(
                prompt=chunk.title,
                answer=chunk.content[:500],  # Truncate for safety
            ),
            source_chunk_id=chunk.chunk_id,
            source_file=chunk.source_file,
            source_type=chunk.source_type,
            quality_score=0.5,
        )
        return [atom]


class FilterTransformer(BaseTransformer):
    """
    Filter transformer that removes atoms based on criteria.
    """

    name = "filter"

    def __init__(
        self,
        min_quality: float = 0.0,
        allowed_types: list[str] | None = None,
        required_fields: list[str] | None = None,
    ):
        """
        Initialize filter.

        Args:
            min_quality: Minimum quality score to keep
            allowed_types: Only keep these atom types (None = all)
            required_fields: Atoms must have these fields non-empty
        """
        super().__init__()
        self.min_quality = min_quality
        self.allowed_types = allowed_types
        self.required_fields = required_fields or []

    async def _transform_chunk(self, chunk: RawChunk) -> list[TransformedAtom]:
        """Not used - this is an enhancement-only transformer."""
        return []

    async def _enhance_atom(self, atom: TransformedAtom) -> TransformedAtom:
        """Mark atom as invalid if it doesn't pass filters."""
        # Quality check
        if atom.quality_score < self.min_quality:
            atom.validation_passed = False
            atom.validation_issues.append(
                f"Quality {atom.quality_score:.2f} below threshold {self.min_quality:.2f}"
            )

        # Type check
        if self.allowed_types and atom.atom_type not in self.allowed_types:
            atom.validation_passed = False
            atom.validation_issues.append(
                f"Type '{atom.atom_type}' not in allowed types"
            )

        # Required fields check
        for field in self.required_fields:
            value = getattr(atom, field, None)
            if value is None or value == "" or value == []:
                atom.validation_passed = False
                atom.validation_issues.append(f"Required field '{field}' is empty")

        return atom
