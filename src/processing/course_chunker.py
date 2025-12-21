"""
UniversalChunker: Multi-Format Parser for Learning Content.

Handles diverse content formats across all source materials:
1. CCNA markdown (hierarchical sections with # **X.X.X**)
2. Moodle week-based course tables (SDE2, PROGII)
3. Q&A pairs and exam materials
4. Curriculum tables

Auto-detects format and delegates to specialized parsers while normalizing
output to the common TextChunk format for downstream processing.

Design Goals:
- Format agnostic: Works with any structure
- Extensible: Easy to add new format parsers
- Consistent output: All parsers return TextChunk objects
- Metadata rich: Captures format-specific features for template selection
"""

from __future__ import annotations

import re
from collections.abc import Iterator
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Protocol

# Import existing CCNAChunker
from .chunker import CCNAChunker, ChunkType, TextChunk


class ContentFormat(str, Enum):
    """Detected content format types."""

    CCNA_HIERARCHICAL = "ccna_hierarchical"  # CCNA modules with # **X.X.X** structure
    MOODLE_WEEKLY = "moodle_weekly"          # Week-based course plan tables
    QA_PAIRS = "qa_pairs"                    # Question-answer format
    CURRICULUM_TABLE = "curriculum_table"    # Structured curriculum tables
    FREE_FORM = "free_form"                  # General markdown/text


class FormatParser(Protocol):
    """Protocol for format-specific parsers."""

    def can_parse(self, content: str, file_path: Path) -> bool:
        """Check if this parser can handle the given content."""
        ...

    def parse(self, content: str, file_path: Path) -> Iterator[TextChunk]:
        """Parse content into TextChunk objects."""
        ...


class CCNAParser:
    """Parser for CCNA hierarchical markdown format."""

    def can_parse(self, content: str, file_path: Path) -> bool:
        """Detect CCNA format by looking for # **X.X.X** section headers."""
        # Check file path first (performance optimization)
        if "CCNA" not in str(file_path):
            return False

        # Verify content has CCNA section structure
        return bool(re.search(r"#\s+\*\*\d+\.\d+\.\d+", content))

    def parse(self, content: str, file_path: Path) -> Iterator[TextChunk]:
        """Delegate to existing CCNAChunker."""
        # Extract module number from filename
        module_match = re.search(r"Module\s*(\d+)", file_path.stem, re.IGNORECASE)
        module_number = int(module_match.group(1)) if module_match else None

        chunker = CCNAChunker()
        chunks = chunker.parse_module(content, module_number)
        yield from chunks


class MoodleWeeklyParser:
    """Parser for Moodle week-based course structure."""

    def can_parse(self, content: str, file_path: Path) -> bool:
        """Detect Moodle format by looking for week table and week sections."""
        has_week_table = bool(re.search(r"Week\s+Topic\s+Learning objectives", content, re.IGNORECASE))
        has_week_sections = bool(re.search(r"W\d+\s*-\s*\d+\.\s*\w+", content))
        return has_week_table or has_week_sections

    def parse(self, content: str, file_path: Path) -> Iterator[TextChunk]:
        """Parse Moodle week-based course content."""
        course_name = self._extract_course_name(content)

        # Split content into weeks by the "W## - Date (Topic)" pattern
        week_pattern = r"(W\d+\s*-\s*\d+\.\s*\w+.*?)(?=W\d+\s*-\s*|\Z)"
        weeks = re.findall(week_pattern, content, re.DOTALL)

        for week_content in weeks:
            # Extract week metadata
            week_match = re.match(r"W(\d+)\s*-\s*(\d+\.\s*\w+)\s*\((.*?)\)", week_content)
            if not week_match:
                continue

            week_num = int(week_match.group(1))
            date = week_match.group(2)
            topic = week_match.group(3)

            # Split week content into sections (Before Class, During Class, etc.)
            sections = self._split_week_sections(week_content)

            for section_name, section_content in sections.items():
                if not section_content.strip():
                    continue

                chunk_id = f"W{week_num}.{section_name}"
                title = f"{topic} - {section_name}"
                parent_context = f"{course_name} > Week {week_num}: {topic}"

                # Determine chunk type based on section name
                chunk_type = self._infer_section_type(section_name)

                chunk = TextChunk(
                    chunk_id=chunk_id,
                    title=title,
                    parent_context=parent_context,
                    content=section_content.strip(),
                    module_number=week_num,
                    chunk_type=chunk_type,
                )

                yield chunk

    def _extract_course_name(self, content: str) -> str:
        """Extract course name from first line."""
        first_line = content.split('\n')[0].strip()
        # Remove common suffixes like "(E2025)"
        return re.sub(r'\s*\([^)]+\)\s*$', '', first_line)

    def _split_week_sections(self, week_content: str) -> dict[str, str]:
        """Split week content into sections (Before Class, During Class, etc.)."""
        sections = {}

        # Common Moodle section headers
        section_headers = [
            "Before Class",
            "During Class",
            "Workshop",
            "Quiz",
            "After Class",
            "Learning Resources",
            "Learning resources",
            "Learning activities"
        ]

        # Build pattern to split on any of these headers
        pattern = r"(" + "|".join(re.escape(h) for h in section_headers) + r")"
        parts = re.split(pattern, week_content)

        # Reconstruct sections
        current_section = None
        for part in parts[1:]:  # Skip week header
            if part in section_headers:
                current_section = part
                sections[current_section] = ""
            elif current_section:
                sections[current_section] += part

        return sections

    def _infer_section_type(self, section_name: str) -> ChunkType:
        """Map Moodle section names to ChunkType."""
        section_lower = section_name.lower()

        if "quiz" in section_lower:
            return ChunkType.PRACTICE
        elif "workshop" in section_lower or "exercise" in section_lower:
            return ChunkType.PRACTICE
        elif "resources" in section_lower:
            return ChunkType.REFERENCE
        elif "before class" in section_lower:
            return ChunkType.INTRODUCTION
        else:
            return ChunkType.CONCEPTUAL


class QAPairParser:
    """Parser for Q&A format content."""

    def can_parse(self, content: str, file_path: Path) -> bool:
        """Detect Q&A format by looking for Q: and A: patterns."""
        # Look for multiple Q: A: pairs
        qa_pattern = r"(?:^|\n)Q:|Question \d+:|^\d+\."
        matches = re.findall(qa_pattern, content, re.MULTILINE)
        return len(matches) >= 3  # At least 3 Q&A pairs

    def parse(self, content: str, file_path: Path) -> Iterator[TextChunk]:
        """Parse Q&A pairs into chunks."""
        file_name = file_path.stem

        # Split on question markers
        qa_pairs = re.split(r"(?:^|\n)(?:Q:|Question \d+:|(\d+)\.\s+)", content, flags=re.MULTILINE)

        question_num = 0
        current_question = None

        for i, part in enumerate(qa_pairs):
            if not part or part.isspace():
                continue

            # Check if this is a question number
            if part.isdigit():
                question_num = int(part)
                continue

            # Check if this starts a new question
            if "?" in part or part.strip().startswith("Q:"):
                current_question = part.strip()
                question_num += 1
            elif current_question:
                # This is the answer part
                answer = part.strip()

                chunk = TextChunk(
                    chunk_id=f"Q{question_num}",
                    title=f"Question {question_num}",
                    parent_context=f"{file_name} > Q&A",
                    content=f"{current_question}\n\n{answer}",
                    module_number=question_num,
                    chunk_type=ChunkType.PRACTICE,
                )

                yield chunk
                current_question = None


class CurriculumTableParser:
    """Parser for curriculum table format."""

    def can_parse(self, content: str, file_path: Path) -> bool:
        """Detect curriculum table by looking for table structure with learning objectives."""
        # Look for table with Week | Topic | Learning objectives structure
        table_header = r"Week\s+.*?\s+Topic\s+.*?\s+Learning objectives"
        return bool(re.search(table_header, content, re.IGNORECASE))

    def parse(self, content: str, file_path: Path) -> Iterator[TextChunk]:
        """Parse curriculum table into chunks."""
        file_name = file_path.stem

        # Find the curriculum table
        table_match = re.search(
            r"Week\s+.*?\s+Topic\s+.*?\s+Learning objectives\s*\n(.*?)(?=\n\n|\Z)",
            content,
            re.DOTALL | re.IGNORECASE
        )

        if not table_match:
            return

        table_content = table_match.group(1)

        # Parse each row (tab-separated or multi-space separated)
        rows = table_content.strip().split('\n')

        for row in rows:
            # Split on tabs or multiple spaces
            parts = re.split(r'\t+|\s{2,}', row.strip())

            if len(parts) < 2:
                continue

            week = parts[0].strip()
            topic = parts[1].strip()
            learning_objectives = parts[2].strip() if len(parts) > 2 else ""

            # Skip empty or holiday weeks
            if not topic or "holiday" in topic.lower():
                continue

            chunk = TextChunk(
                chunk_id=f"W{week}",
                title=topic,
                parent_context=f"{file_name} > Week {week}",
                content=f"**Topic:** {topic}\n\n**Learning Objectives:** {learning_objectives}",
                module_number=int(week) if week.isdigit() else 0,
                chunk_type=ChunkType.INTRODUCTION,
            )

            yield chunk


class FreeFormParser:
    """Fallback parser for free-form markdown/text."""

    def can_parse(self, content: str, file_path: Path) -> bool:
        """Accept anything as fallback."""
        return True

    def parse(self, content: str, file_path: Path) -> Iterator[TextChunk]:
        """Parse free-form content by splitting on headers."""
        file_name = file_path.stem

        # Split on markdown headers (# Header or ## Header)
        sections = re.split(r'\n(?=#+ )', content)

        for i, section in enumerate(sections):
            if not section.strip():
                continue

            # Extract header and content
            header_match = re.match(r'^(#+)\s+(.+?)$', section, re.MULTILINE)

            if header_match:
                level = len(header_match.group(1))
                title = header_match.group(2).strip()
                content_text = section[header_match.end():].strip()
            else:
                # No header found, use first line or generic title
                lines = section.strip().split('\n')
                title = lines[0][:50] + "..." if len(lines[0]) > 50 else lines[0]
                content_text = section.strip()

            chunk = TextChunk(
                chunk_id=f"S{i+1}",
                title=title,
                parent_context=f"{file_name}",
                content=content_text,
                module_number=i + 1,
                chunk_type=ChunkType.CONCEPTUAL,
            )

            yield chunk


class UniversalChunker:
    """
    Multi-format content parser with automatic format detection.

    Delegates to specialized parsers based on content structure:
    - CCNAParser: CCNA hierarchical markdown
    - MoodleWeeklyParser: Week-based Moodle courses
    - QAPairParser: Q&A formatted content
    - CurriculumTableParser: Curriculum tables
    - FreeFormParser: Generic markdown fallback
    """

    def __init__(self, file_path: str | Path):
        """Initialize with file path."""
        self.file_path = Path(file_path)

        # Register parsers in priority order (most specific first)
        self.parsers: list[FormatParser] = [
            CCNAParser(),
            MoodleWeeklyParser(),
            QAPairParser(),
            CurriculumTableParser(),
            FreeFormParser(),  # Always last (fallback)
        ]

    def detect_format(self, content: str) -> tuple[ContentFormat, FormatParser]:
        """Detect content format and return appropriate parser."""
        for parser in self.parsers:
            if parser.can_parse(content, self.file_path):
                # Map parser class to ContentFormat enum
                format_map = {
                    CCNAParser: ContentFormat.CCNA_HIERARCHICAL,
                    MoodleWeeklyParser: ContentFormat.MOODLE_WEEKLY,
                    QAPairParser: ContentFormat.QA_PAIRS,
                    CurriculumTableParser: ContentFormat.CURRICULUM_TABLE,
                    FreeFormParser: ContentFormat.FREE_FORM,
                }

                format_type = format_map.get(type(parser), ContentFormat.FREE_FORM)
                return format_type, parser

        # Should never reach here (FreeFormParser always accepts)
        return ContentFormat.FREE_FORM, self.parsers[-1]

    def chunk_file(self) -> Iterator[TextChunk]:
        """
        Parse file content into TextChunk objects.

        Auto-detects format and delegates to appropriate parser.

        Yields:
            TextChunk objects with normalized metadata
        """
        if not self.file_path.exists():
            raise FileNotFoundError(f"File not found: {self.file_path}")

        content = self.file_path.read_text(encoding='utf-8')

        # Detect format and get parser
        detected_format, parser = self.detect_format(content)

        # Log detection (can be removed in production)
        # print(f"[UniversalChunker] {self.file_path.name} → {detected_format.value}")

        # Parse and yield chunks
        yield from parser.parse(content, self.file_path)

    @staticmethod
    def chunk_directory(directory: str | Path, pattern: str = "**/*.{txt,md}") -> Iterator[TextChunk]:
        """
        Chunk all files in a directory matching the pattern.

        Args:
            directory: Root directory to scan
            pattern: Glob pattern for files (default: all .txt and .md files)

        Yields:
            TextChunk objects from all matching files
        """
        directory = Path(directory)

        # Expand pattern to handle both .txt and .md
        patterns = pattern.split(',') if ',' in pattern else [pattern]

        for pat in patterns:
            for file_path in directory.glob(pat.strip()):
                if file_path.is_file():
                    chunker = UniversalChunker(file_path)
                    try:
                        yield from chunker.chunk_file()
                    except Exception as e:
                        print(f"[ERROR] Failed to parse {file_path.name}: {e}")
                        continue


# Convenience function for backward compatibility
def chunk_file(file_path: str | Path) -> Iterator[TextChunk]:
    """
    Convenience function to chunk a single file.

    Auto-detects format and returns appropriate chunks.
    """
    chunker = UniversalChunker(file_path)
    return chunker.chunk_file()
