"""
Content: Local content parsing, quality analysis, and generation.

Subpackages:
- cleaning/: Quality analysis, atomicity validation, thresholds
- generation/: LLM-based atom generation, prompts, schemas

Core modules:
- parser: Content file parsing (.txt, .md)
- loader: Batch file loading
- importer: Content to atom conversion
- reader: Content search and navigation
"""

# Re-export from subpackages for convenience
from .cleaning import CardQualityAnalyzer, QualityGrade, QualityReport
from .generation import LLMFlashcardGenerator
from .importer import ContentImporter, ImportedAtom, ImportResult, preview_import
from .loader import ContentLoader
from .parser import ContentParser, ContentSection, ParsedContent
from .reader import ContentReader, SearchResult, TOCEntry

__all__ = [
    # Core content modules
    "ContentParser",
    "ParsedContent",
    "ContentSection",
    "ContentLoader",
    "ContentImporter",
    "ImportedAtom",
    "ImportResult",
    "preview_import",
    "ContentReader",
    "SearchResult",
    "TOCEntry",
    # Quality analysis
    "CardQualityAnalyzer",
    "QualityGrade",
    "QualityReport",
    # Generation
    "LLMFlashcardGenerator",
]
