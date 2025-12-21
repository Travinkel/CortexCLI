"""
ETL Pipeline Orchestrator.

Coordinates extractors, transformers, and loaders in a pluggable architecture.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING, Protocol, runtime_checkable

from .models import RawChunk, TransformedAtom

if TYPE_CHECKING:
    from .extractors.base import BaseExtractor
    from .loaders.base import BaseLoader
    from .transformers.base import BaseTransformer

logger = logging.getLogger(__name__)


# =============================================================================
# Protocol Definitions (for type checking without circular imports)
# =============================================================================


@runtime_checkable
class Extractor(Protocol):
    """Protocol for content extractors."""

    async def extract(self) -> list[RawChunk]:
        """Extract raw chunks from source."""
        ...


@runtime_checkable
class Transformer(Protocol):
    """Protocol for atom transformers."""

    async def transform(self, chunks: list[RawChunk]) -> list[TransformedAtom]:
        """Transform raw chunks into atoms."""
        ...


@runtime_checkable
class Loader(Protocol):
    """Protocol for atom loaders."""

    async def load(self, atoms: list[TransformedAtom]) -> LoadResult:
        """Load atoms into storage."""
        ...


# =============================================================================
# Result Types
# =============================================================================


@dataclass
class LoadResult:
    """Result of loading atoms."""

    inserted: int = 0
    updated: int = 0
    skipped: int = 0
    failed: int = 0
    errors: list[str] = field(default_factory=list)


@dataclass
class PipelineResult:
    """Result of running the full ETL pipeline."""

    # Counts
    chunks_extracted: int = 0
    atoms_transformed: int = 0
    atoms_loaded: int = 0
    atoms_failed: int = 0

    # Quality metrics
    validation_passed: int = 0
    validation_failed: int = 0

    # Timing
    started_at: datetime = field(default_factory=datetime.now)
    completed_at: datetime | None = None
    duration_seconds: float = 0.0

    # Errors
    extraction_errors: list[str] = field(default_factory=list)
    transformation_errors: list[str] = field(default_factory=list)
    loading_errors: list[str] = field(default_factory=list)

    # Details
    atoms_by_type: dict[str, int] = field(default_factory=dict)
    atoms_by_engagement_mode: dict[str, int] = field(default_factory=dict)

    @property
    def success(self) -> bool:
        """Pipeline succeeded if any atoms were loaded."""
        return self.atoms_loaded > 0 and self.atoms_failed == 0

    @property
    def partial_success(self) -> bool:
        """Pipeline had partial success if some atoms loaded despite failures."""
        return self.atoms_loaded > 0 and self.atoms_failed > 0

    def to_dict(self) -> dict:
        """Serialize to dictionary."""
        return {
            "chunks_extracted": self.chunks_extracted,
            "atoms_transformed": self.atoms_transformed,
            "atoms_loaded": self.atoms_loaded,
            "atoms_failed": self.atoms_failed,
            "validation_passed": self.validation_passed,
            "validation_failed": self.validation_failed,
            "duration_seconds": self.duration_seconds,
            "success": self.success,
            "partial_success": self.partial_success,
            "atoms_by_type": self.atoms_by_type,
            "atoms_by_engagement_mode": self.atoms_by_engagement_mode,
            "errors": {
                "extraction": self.extraction_errors,
                "transformation": self.transformation_errors,
                "loading": self.loading_errors,
            },
        }


# =============================================================================
# Pipeline Orchestrator
# =============================================================================


class Pipeline:
    """
    ETL Pipeline orchestrator.

    Coordinates extraction, transformation, and loading in a pluggable way.
    Supports multiple extractors, chained transformers, and multiple loaders.

    Example:
        pipeline = Pipeline(
            extractor=CCNAExtractor(module_path),
            transformers=[
                ICAPClassifier(),
                SkillMapper(skill_taxonomy),
                DistractorEngineer(misconception_library),
            ],
            loader=AtomLoader(db_session),
        )

        result = await pipeline.run()
    """

    def __init__(
        self,
        extractor: Extractor,
        transformers: list[Transformer] | None = None,
        loader: Loader | None = None,
        *,
        validate: bool = True,
        batch_size: int = 100,
        continue_on_error: bool = True,
    ):
        """
        Initialize pipeline.

        Args:
            extractor: Content extractor (source-specific)
            transformers: Chain of transformers to apply
            loader: Atom loader (storage target)
            validate: Whether to validate atoms before loading
            batch_size: Batch size for loading
            continue_on_error: Continue processing on individual errors
        """
        self.extractor = extractor
        self.transformers = transformers or []
        self.loader = loader
        self.validate = validate
        self.batch_size = batch_size
        self.continue_on_error = continue_on_error

        self._result = PipelineResult()

    async def run(self) -> PipelineResult:
        """
        Run the full ETL pipeline.

        Returns:
            PipelineResult with counts and metrics
        """
        self._result = PipelineResult()
        self._result.started_at = datetime.now()

        try:
            # Step 1: Extract
            logger.info("Starting extraction...")
            chunks = await self._extract()
            self._result.chunks_extracted = len(chunks)
            logger.info(f"Extracted {len(chunks)} chunks")

            if not chunks:
                logger.warning("No chunks extracted, pipeline complete")
                return self._finalize()

            # Step 2: Transform
            logger.info("Starting transformation...")
            atoms = await self._transform(chunks)
            self._result.atoms_transformed = len(atoms)
            logger.info(f"Transformed {len(atoms)} atoms")

            if not atoms:
                logger.warning("No atoms transformed, pipeline complete")
                return self._finalize()

            # Step 3: Validate (optional)
            if self.validate:
                logger.info("Validating atoms...")
                atoms = await self._validate(atoms)
                logger.info(
                    f"Validation: {self._result.validation_passed} passed, "
                    f"{self._result.validation_failed} failed"
                )

            # Step 4: Load
            if self.loader:
                logger.info("Loading atoms...")
                await self._load(atoms)
                logger.info(f"Loaded {self._result.atoms_loaded} atoms")

            # Compute metrics
            self._compute_metrics(atoms)

        except Exception as e:
            logger.exception(f"Pipeline failed: {e}")
            self._result.extraction_errors.append(str(e))

        return self._finalize()

    async def _extract(self) -> list[RawChunk]:
        """Run extraction phase."""
        try:
            return await self.extractor.extract()
        except Exception as e:
            logger.error(f"Extraction failed: {e}")
            self._result.extraction_errors.append(str(e))
            if not self.continue_on_error:
                raise
            return []

    async def _transform(self, chunks: list[RawChunk]) -> list[TransformedAtom]:
        """Run transformation phase through all transformers."""
        atoms: list[TransformedAtom] = []

        # First transformer converts chunks to atoms
        if self.transformers:
            first_transformer = self.transformers[0]
            try:
                atoms = await first_transformer.transform(chunks)
            except Exception as e:
                logger.error(f"Initial transformation failed: {e}")
                self._result.transformation_errors.append(str(e))
                if not self.continue_on_error:
                    raise
                return []

            # Subsequent transformers enhance atoms
            for transformer in self.transformers[1:]:
                try:
                    atoms = await transformer.enhance(atoms)
                except Exception as e:
                    logger.error(f"Enhancement failed in {transformer.__class__.__name__}: {e}")
                    self._result.transformation_errors.append(str(e))
                    if not self.continue_on_error:
                        raise

        return atoms

    async def _validate(self, atoms: list[TransformedAtom]) -> list[TransformedAtom]:
        """Validate atoms and filter invalid ones."""
        valid_atoms = []

        for atom in atoms:
            if atom.validation_passed:
                self._result.validation_passed += 1
                valid_atoms.append(atom)
            else:
                self._result.validation_failed += 1
                logger.warning(
                    f"Atom {atom.card_id} failed validation: {atom.validation_issues}"
                )

        return valid_atoms

    async def _load(self, atoms: list[TransformedAtom]) -> None:
        """Load atoms in batches."""
        if not self.loader:
            return

        for i in range(0, len(atoms), self.batch_size):
            batch = atoms[i : i + self.batch_size]
            try:
                result = await self.loader.load(batch)
                self._result.atoms_loaded += result.inserted + result.updated
                self._result.atoms_failed += result.failed
                self._result.loading_errors.extend(result.errors)
            except Exception as e:
                logger.error(f"Loading batch failed: {e}")
                self._result.loading_errors.append(str(e))
                self._result.atoms_failed += len(batch)
                if not self.continue_on_error:
                    raise

    def _compute_metrics(self, atoms: list[TransformedAtom]) -> None:
        """Compute distribution metrics."""
        for atom in atoms:
            # By type
            atom_type = atom.atom_type
            self._result.atoms_by_type[atom_type] = (
                self._result.atoms_by_type.get(atom_type, 0) + 1
            )

            # By engagement mode
            mode = atom.engagement_mode.value
            self._result.atoms_by_engagement_mode[mode] = (
                self._result.atoms_by_engagement_mode.get(mode, 0) + 1
            )

    def _finalize(self) -> PipelineResult:
        """Finalize and return result."""
        self._result.completed_at = datetime.now()
        self._result.duration_seconds = (
            self._result.completed_at - self._result.started_at
        ).total_seconds()
        return self._result


# =============================================================================
# Pipeline Builder (Fluent API)
# =============================================================================


class PipelineBuilder:
    """
    Fluent builder for Pipeline construction.

    Example:
        pipeline = (
            PipelineBuilder()
            .extract_from(CCNAExtractor(path))
            .transform_with(ICAPClassifier())
            .transform_with(SkillMapper(taxonomy))
            .load_to(AtomLoader(session))
            .with_validation()
            .build()
        )
    """

    def __init__(self):
        self._extractor: Extractor | None = None
        self._transformers: list[Transformer] = []
        self._loader: Loader | None = None
        self._validate: bool = True
        self._batch_size: int = 100
        self._continue_on_error: bool = True

    def extract_from(self, extractor: Extractor) -> PipelineBuilder:
        """Set the extractor."""
        self._extractor = extractor
        return self

    def transform_with(self, transformer: Transformer) -> PipelineBuilder:
        """Add a transformer to the chain."""
        self._transformers.append(transformer)
        return self

    def load_to(self, loader: Loader) -> PipelineBuilder:
        """Set the loader."""
        self._loader = loader
        return self

    def with_validation(self, enabled: bool = True) -> PipelineBuilder:
        """Enable or disable validation."""
        self._validate = enabled
        return self

    def with_batch_size(self, size: int) -> PipelineBuilder:
        """Set batch size for loading."""
        self._batch_size = size
        return self

    def continue_on_error(self, enabled: bool = True) -> PipelineBuilder:
        """Set whether to continue on individual errors."""
        self._continue_on_error = enabled
        return self

    def build(self) -> Pipeline:
        """Build the pipeline."""
        if not self._extractor:
            raise ValueError("Extractor is required")

        return Pipeline(
            extractor=self._extractor,
            transformers=self._transformers,
            loader=self._loader,
            validate=self._validate,
            batch_size=self._batch_size,
            continue_on_error=self._continue_on_error,
        )
