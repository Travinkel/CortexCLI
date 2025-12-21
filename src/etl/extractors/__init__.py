"""
Content Extractors.

Plugins for extracting raw content from different sources.
Each extractor handles a specific content format or source type.
"""

from .base import BaseExtractor, ExtractorRegistry

__all__ = ["BaseExtractor", "ExtractorRegistry"]
