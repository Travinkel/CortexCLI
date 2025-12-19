"""
Content loader for batch processing local files.

Handles loading content from directories and preparing
it for atom generation.
"""

from collections.abc import Iterator
from pathlib import Path

from .parser import ContentParser, ParsedContent


class ContentLoader:
    """Load and manage local content for atom generation."""

    def __init__(self, base_path: Path | str | None = None):
        """
        Initialize loader.

        Args:
            base_path: Base directory for content files.
                      Defaults to project's data/content/ directory.
        """
        if base_path is None:
            # Default to project data directory
            project_root = Path(__file__).parent.parent.parent
            base_path = project_root / "data" / "content"

        self.base_path = Path(base_path)
        self.parser = ContentParser()

    def load_all(
        self, patterns: list[str] | None = None
    ) -> Iterator[ParsedContent]:
        """
        Load all content files matching patterns.

        Args:
            patterns: Glob patterns to match. Defaults to ["*.txt", "*.md"]

        Yields:
            ParsedContent for each matched file
        """
        if patterns is None:
            patterns = ["*.txt", "*.md"]

        if not self.base_path.exists():
            print(f"Warning: Content directory not found: {self.base_path}")
            return

        for pattern in patterns:
            for file_path in sorted(self.base_path.rglob(pattern)):
                try:
                    yield self.parser.parse_file(file_path)
                except Exception as e:
                    print(f"Warning: Failed to load {file_path}: {e}")

    def load_file(self, relative_path: str) -> ParsedContent:
        """Load a specific file by relative path."""
        full_path = self.base_path / relative_path
        return self.parser.parse_file(full_path)

    def load_module(self, module_name: str) -> list[ParsedContent]:
        """
        Load all content for a specific module/topic.

        Assumes content is organized by module folders:
        data/content/
          module_1/
            topic1.txt
            topic2.md
          module_2/
            ...
        """
        module_path = self.base_path / module_name
        if not module_path.exists():
            raise FileNotFoundError(f"Module not found: {module_name}")

        return list(self.load_all())

    def list_modules(self) -> list[str]:
        """List available modules (subdirectories)."""
        if not self.base_path.exists():
            return []

        return [
            d.name
            for d in self.base_path.iterdir()
            if d.is_dir() and not d.name.startswith(".")
        ]

    def get_stats(self) -> dict:
        """Get statistics about available content."""
        stats = {
            "total_files": 0,
            "total_sections": 0,
            "total_words": 0,
            "by_extension": {},
        }

        for content in self.load_all():
            stats["total_files"] += 1
            stats["total_sections"] += len(content.sections)
            stats["total_words"] += content.total_words

            ext = Path(content.source_path).suffix.lower()
            stats["by_extension"][ext] = stats["by_extension"].get(ext, 0) + 1

        return stats
