"""
PDF Content Extractor.

Extracts structured content from PDF textbooks using PyMuPDF.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, ClassVar
from uuid import uuid4

from ..models import RawChunk
from .base import BaseExtractor, ExtractionConfig, ExtractorRegistry

logger = logging.getLogger(__name__)


@dataclass
class PDFExtractionConfig(ExtractionConfig):
    """Configuration for PDF extraction."""

    extract_images: bool = False
    detect_chapters: bool = True
    detect_code_blocks: bool = True
    min_section_words: int = 50
    max_section_words: int = 1000


@ExtractorRegistry.register("pdf", extensions=[".pdf"])
class PDFExtractor(BaseExtractor):
    """
    Extract structured content from PDF textbooks.

    Features:
    - Chapter/section detection
    - Code block extraction
    - CLI command identification
    - Table detection
    """

    source_type: ClassVar[str] = "pdf"
    version: ClassVar[str] = "1.0.0"

    def __init__(
        self,
        source: str | Path,
        config: PDFExtractionConfig | None = None,
    ):
        super().__init__(source, config or PDFExtractionConfig())
        self.config: PDFExtractionConfig = self.config

    async def extract(self) -> list[RawChunk]:
        """Extract chunks from PDF."""
        try:
            import fitz
        except ImportError:
            logger.warning("PyMuPDF not installed, using fallback text extraction")
            return await self._extract_fallback()

        chunks: list[RawChunk] = []

        try:
            doc = fitz.open(str(self.source))

            current_chapter = "Introduction"
            current_section = ""
            accumulated_text = ""
            page_start = 0

            for page_num, page in enumerate(doc):
                text = page.get_text()

                chapter_match = re.search(
                    r"^(?:Chapter|CHAPTER)\s+(\d+)[:\s]+(.+)$",
                    text,
                    re.MULTILINE,
                )
                if chapter_match:
                    if accumulated_text.strip():
                        chunk = self._create_chunk(
                            chunk_id=str(uuid4()),
                            title=f"{current_chapter} - {current_section}".strip(" -"),
                            content=accumulated_text.strip(),
                            module_number=self._extract_module_number(current_chapter),
                        )
                        if self._filter_chunk(chunk):
                            chunks.append(chunk)

                    current_chapter = f"Chapter {chapter_match.group(1)}: {chapter_match.group(2)}"
                    accumulated_text = ""
                    page_start = page_num

                section_match = re.search(
                    r"^(?:\d+\.\d+)\s+(.+)$",
                    text,
                    re.MULTILINE,
                )
                if section_match:
                    current_section = section_match.group(1)

                accumulated_text += f"\n{text}"

                if len(accumulated_text.split()) > self.config.max_section_words:
                    chunk = self._create_chunk(
                        chunk_id=str(uuid4()),
                        title=f"{current_chapter} - {current_section}".strip(" -"),
                        content=accumulated_text.strip()[:5000],
                        module_number=self._extract_module_number(current_chapter),
                    )
                    if self._filter_chunk(chunk):
                        chunks.append(chunk)
                    accumulated_text = ""

            if accumulated_text.strip():
                chunk = self._create_chunk(
                    chunk_id=str(uuid4()),
                    title=f"{current_chapter} - {current_section}".strip(" -"),
                    content=accumulated_text.strip()[:5000],
                    module_number=self._extract_module_number(current_chapter),
                )
                if self._filter_chunk(chunk):
                    chunks.append(chunk)

            doc.close()

        except Exception as e:
            logger.error(f"PDF extraction failed: {e}")
            return await self._extract_fallback()

        logger.info(f"Extracted {len(chunks)} chunks from {self.source.name}")
        return chunks

    async def _extract_fallback(self) -> list[RawChunk]:
        """Fallback extraction when PyMuPDF is not available."""
        logger.warning(f"Using fallback extraction for {self.source}")
        return []

    def _parse_content(self, raw_content: str) -> list[dict[str, Any]]:
        """Parse raw PDF text into sections."""
        sections: list[dict[str, Any]] = []

        chapter_pattern = re.compile(
            r"(?:Chapter|CHAPTER)\s+(\d+)[:\s]+(.+?)(?=(?:Chapter|CHAPTER)\s+\d+|$)",
            re.DOTALL,
        )

        for match in chapter_pattern.finditer(raw_content):
            chapter_num = match.group(1)
            chapter_content = match.group(2).strip()

            sections.append({
                "title": f"Chapter {chapter_num}",
                "content": chapter_content[:5000],
                "metadata": {"chapter": int(chapter_num)},
            })

        return sections

    def _extract_module_number(self, chapter_title: str) -> int | None:
        """Extract module/chapter number from title."""
        match = re.search(r"(\d+)", chapter_title)
        return int(match.group(1)) if match else None


class CCNAPDFExtractor(PDFExtractor):
    """
    Specialized extractor for CCNA Official Cert Guide PDFs.

    Handles CCNA-specific formatting:
    - "Key Topics" sections
    - CLI command examples
    - Network topology diagrams
    """

    source_type = "ccna_pdf"

    def _parse_content(self, raw_content: str) -> list[dict[str, Any]]:
        """Parse CCNA-specific content structure."""
        sections = super()._parse_content(raw_content)

        for section in sections:
            content = section["content"]

            key_topics = re.findall(
                r"Key Topics?[:\s]+(.+?)(?=\n\n|\Z)",
                content,
                re.DOTALL | re.IGNORECASE,
            )
            if key_topics:
                section["metadata"]["key_topics"] = key_topics

            cli_blocks = re.findall(
                r"((?:Router|Switch|R\d|S\d)[#>].+?)(?=\n\n|\Z)",
                content,
                re.DOTALL,
            )
            if cli_blocks:
                section["metadata"]["cli_commands"] = cli_blocks

        return sections
