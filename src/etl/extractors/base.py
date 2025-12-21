"""
Base Extractor Class.

Provides the abstract base for all content extractors.
Uses a registry pattern for plugin discovery.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Any, ClassVar

from ..models import RawChunk

logger = logging.getLogger(__name__)


# =============================================================================
# Extractor Registry (Plugin Pattern)
# =============================================================================


class ExtractorRegistry:
    """
    Registry for extractor plugins.

    Allows dynamic discovery and instantiation of extractors
    based on source type or file extension.

    Example:
        # Register an extractor
        @ExtractorRegistry.register("ccna")
        class CCNAExtractor(BaseExtractor):
            ...

        # Get an extractor by type
        extractor_class = ExtractorRegistry.get("ccna")
        extractor = extractor_class(source_path)

        # Auto-detect from file extension
        extractor = ExtractorRegistry.create_for_file("module1.txt")
    """

    _extractors: ClassVar[dict[str, type[BaseExtractor]]] = {}
    _extension_map: ClassVar[dict[str, str]] = {}

    @classmethod
    def register(
        cls,
        source_type: str,
        extensions: list[str] | None = None,
    ):
        """
        Decorator to register an extractor class.

        Args:
            source_type: Unique identifier for this source type
            extensions: File extensions this extractor handles
        """

        def decorator(extractor_class: type[BaseExtractor]):
            cls._extractors[source_type] = extractor_class
            extractor_class.source_type = source_type

            if extensions:
                for ext in extensions:
                    cls._extension_map[ext.lower()] = source_type

            logger.debug(f"Registered extractor: {source_type} -> {extractor_class.__name__}")
            return extractor_class

        return decorator

    @classmethod
    def get(cls, source_type: str) -> type[BaseExtractor]:
        """Get extractor class by source type."""
        if source_type not in cls._extractors:
            raise KeyError(f"No extractor registered for source type: {source_type}")
        return cls._extractors[source_type]

    @classmethod
    def create_for_file(cls, path: str | Path) -> BaseExtractor:
        """Create extractor instance based on file extension."""
        path = Path(path)
        ext = path.suffix.lower()

        if ext not in cls._extension_map:
            raise KeyError(f"No extractor registered for extension: {ext}")

        source_type = cls._extension_map[ext]
        extractor_class = cls._extractors[source_type]
        return extractor_class(path)

    @classmethod
    def list_extractors(cls) -> dict[str, type[BaseExtractor]]:
        """List all registered extractors."""
        return dict(cls._extractors)

    @classmethod
    def list_extensions(cls) -> dict[str, str]:
        """List all registered extensions and their source types."""
        return dict(cls._extension_map)


# =============================================================================
# Base Extractor
# =============================================================================


@dataclass
class ExtractionConfig:
    """Configuration for extraction."""

    # Chunking
    chunk_size_chars: int = 2000
    chunk_overlap_chars: int = 200

    # Content detection
    detect_code_blocks: bool = True
    detect_cli_commands: bool = True
    detect_diagrams: bool = True

    # Hierarchy
    extract_hierarchy: bool = True
    max_depth: int = 3

    # Quality filters
    min_chunk_words: int = 20
    max_chunk_words: int = 500


class BaseExtractor(ABC):
    """
    Abstract base class for content extractors.

    Extractors are responsible for:
    1. Reading raw content from a source (file, API, database)
    2. Chunking content into meaningful segments
    3. Extracting metadata (hierarchy, code blocks, etc.)
    4. Producing RawChunk objects for transformation

    Subclasses must implement:
    - extract(): Main extraction logic
    - _parse_content(): Source-specific parsing
    """

    source_type: ClassVar[str] = "unknown"
    version: ClassVar[str] = "1.0.0"

    def __init__(
        self,
        source: str | Path,
        config: ExtractionConfig | None = None,
    ):
        """
        Initialize extractor.

        Args:
            source: Path to source file or source identifier
            config: Extraction configuration
        """
        self.source = Path(source) if isinstance(source, str) else source
        self.config = config or ExtractionConfig()
        self._chunks: list[RawChunk] = []

    @abstractmethod
    async def extract(self) -> list[RawChunk]:
        """
        Extract raw chunks from the source.

        Returns:
            List of RawChunk objects
        """
        ...

    @abstractmethod
    def _parse_content(self, raw_content: str) -> list[dict[str, Any]]:
        """
        Parse raw content into structured sections.

        Args:
            raw_content: Raw text content

        Returns:
            List of section dictionaries with title, content, metadata
        """
        ...

    def _read_source(self) -> str:
        """Read content from source file."""
        if not self.source.exists():
            raise FileNotFoundError(f"Source not found: {self.source}")

        return self.source.read_text(encoding="utf-8")

    def _create_chunk(
        self,
        chunk_id: str,
        title: str,
        content: str,
        **metadata,
    ) -> RawChunk:
        """Create a RawChunk with automatic metadata."""
        return RawChunk(
            chunk_id=chunk_id,
            source_file=str(self.source),
            source_type=self.source_type,
            title=title,
            content=content,
            word_count=len(content.split()),
            has_code=self._detect_code(content),
            has_cli_commands=self._detect_cli(content),
            has_diagram=self._detect_diagram(content),
            extractor_version=self.version,
            **metadata,
        )

    def _detect_code(self, content: str) -> bool:
        """Detect if content contains code blocks."""
        if not self.config.detect_code_blocks:
            return False

        code_indicators = [
            "```",
            "def ",
            "class ",
            "function ",
            "import ",
            "from ",
            "const ",
            "let ",
            "var ",
            "public ",
            "private ",
        ]
        return any(indicator in content for indicator in code_indicators)

    def _detect_cli(self, content: str) -> bool:
        """Detect if content contains CLI commands."""
        if not self.config.detect_cli_commands:
            return False

        cli_indicators = [
            "Router#",
            "Router>",
            "Switch#",
            "Switch>",
            "R1#",
            "R1>",
            "S1#",
            "$ ",
            "# ",
            "ping ",
            "show ",
            "configure ",
            "interface ",
        ]
        return any(indicator in content for indicator in cli_indicators)

    def _detect_diagram(self, content: str) -> bool:
        """Detect if content contains diagram references."""
        if not self.config.detect_diagrams:
            return False

        diagram_indicators = [
            "[diagram]",
            "[figure]",
            "[image]",
            "Figure ",
            "Diagram ",
            "Topology:",
            "Network Diagram",
        ]
        return any(indicator in content for indicator in diagram_indicators)

    def _filter_chunk(self, chunk: RawChunk) -> bool:
        """Check if chunk passes quality filters."""
        word_count = chunk.word_count

        if word_count < self.config.min_chunk_words:
            logger.debug(f"Chunk {chunk.chunk_id} too short: {word_count} words")
            return False

        if word_count > self.config.max_chunk_words:
            logger.debug(f"Chunk {chunk.chunk_id} too long: {word_count} words")
            return False

        return True


# =============================================================================
# Composite Extractor (Multiple Sources)
# =============================================================================


class CompositeExtractor(BaseExtractor):
    """
    Extractor that combines multiple extractors.

    Useful for processing a directory of files with different formats.

    Example:
        extractor = CompositeExtractor([
            CCNAExtractor(path1),
            SecurityExtractor(path2),
            ProgrammingExtractor(path3),
        ])
        chunks = await extractor.extract()
    """

    source_type = "composite"

    def __init__(self, extractors: list[BaseExtractor]):
        """
        Initialize composite extractor.

        Args:
            extractors: List of extractors to combine
        """
        self.extractors = extractors
        self._chunks: list[RawChunk] = []

    async def extract(self) -> list[RawChunk]:
        """Extract from all sources."""
        all_chunks: list[RawChunk] = []

        for extractor in self.extractors:
            try:
                chunks = await extractor.extract()
                all_chunks.extend(chunks)
                logger.info(
                    f"Extracted {len(chunks)} chunks from {extractor.source_type}"
                )
            except Exception as e:
                logger.error(f"Extractor {extractor.source_type} failed: {e}")

        self._chunks = all_chunks
        return all_chunks

    def _parse_content(self, raw_content: str) -> list[dict[str, Any]]:
        """Not used in composite extractor."""
        raise NotImplementedError("Composite extractor delegates to child extractors")
