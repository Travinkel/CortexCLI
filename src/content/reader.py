"""
Content Reader Service.

Provides reading access to CCNA source material for the Cortex CLI.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from src.ccna.content_parser import CCNAContentParser, ModuleContent, Section


@dataclass
class SearchResult:
    """A search result within module content."""

    section_id: str
    section_title: str
    line_number: int
    context: str  # Surrounding text with match highlighted
    match_text: str


@dataclass
class TOCEntry:
    """A table of contents entry."""

    section_id: str
    title: str
    level: int
    has_subsections: bool
    estimated_atoms: int


class ContentReader:
    """
    Read and navigate CCNA source material.

    Provides methods to load modules, get specific sections,
    generate table of contents, and search within content.
    """

    DEFAULT_SOURCE_DIR = Path("docs/source-materials/CCNA")

    def __init__(self, source_dir: Path | str | None = None):
        """
        Initialize the content reader.

        Args:
            source_dir: Path to CCNA source materials directory.
                       Defaults to docs/source-materials/CCNA
        """
        if source_dir is None:
            source_dir = self.DEFAULT_SOURCE_DIR
        self.source_dir = Path(source_dir)
        self.parser = CCNAContentParser(str(self.source_dir))
        self._module_cache: dict[int, ModuleContent] = {}

    def get_available_modules(self) -> list[int]:
        """Get list of available module numbers."""
        modules = []
        for path in self.parser.get_available_modules():
            match = re.search(r"Module\s*(\d+)", path.stem, re.IGNORECASE)
            if match:
                modules.append(int(match.group(1)))
        return sorted(modules)

    def get_module(self, module_num: int) -> ModuleContent | None:
        """
        Load and parse a module by number.

        Args:
            module_num: Module number (1-17)

        Returns:
            ModuleContent or None if not found
        """
        if module_num in self._module_cache:
            return self._module_cache[module_num]

        module_path = self.source_dir / f"CCNA Module {module_num}.txt"
        if not module_path.exists():
            return None

        module = self.parser.parse_module(module_path)
        self._module_cache[module_num] = module
        return module

    def get_section(self, module_num: int, section_id: str) -> Section | None:
        """
        Get a specific section from a module.

        Args:
            module_num: Module number (1-17)
            section_id: Section identifier (e.g., "11.2", "11.2.3")

        Returns:
            Section or None if not found
        """
        module = self.get_module(module_num)
        if not module:
            return None

        # Normalize section_id to match parser format
        # User might enter "11.2" but parser stores "NET-M11-S11-2"
        normalized_id = f"NET-M{module_num}-S{section_id.replace('.', '-')}"

        section = module.get_section_by_id(normalized_id)
        if section:
            return section

        # Try finding by section number prefix in title or ID
        all_sections = []
        self._flatten_sections(module.sections, all_sections)

        for sec in all_sections:
            # Check if title starts with section number (e.g., "11.2.3 Title")
            # Handle bold markers: "**11.2.3 Title**"
            clean_title = sec.title.strip("*").strip()
            if clean_title.startswith(section_id):
                return sec

            # Check if internal ID matches
            if sec.id.endswith(f"-S{section_id.replace('.', '-')}"):
                return sec

        return None

    def _find_section_by_number(
        self, sections: list[Section], target_number: str
    ) -> Section | None:
        """Recursively search for a section by its number prefix."""
        for section in sections:
            # Check if section ID ends with the target number pattern
            if section.id.endswith(f"-S{target_number.replace('.', '-')}"):
                return section

            # Check title for section number
            if section.title.startswith(target_number):
                return section

            # Search subsections
            result = self._find_section_by_number(section.subsections, target_number)
            if result:
                return result

        return None

    def get_toc(self, module_num: int) -> list[TOCEntry]:
        """
        Get table of contents for a module.

        Args:
            module_num: Module number (1-17)

        Returns:
            List of TOCEntry items representing the hierarchy
        """
        module = self.get_module(module_num)
        if not module:
            return []

        entries: list[TOCEntry] = []
        self._build_toc(module.sections, entries)
        return entries

    def _build_toc(self, sections: list[Section], entries: list[TOCEntry]) -> None:
        """Recursively build TOC entries from sections."""
        for section in sections:
            # Extract section number from ID (e.g., "NET-M11-S11-2" -> "11.2")
            section_num = self._extract_section_number(section.id)

            entries.append(
                TOCEntry(
                    section_id=section_num or section.id,
                    title=section.title,
                    level=section.level,
                    has_subsections=len(section.subsections) > 0,
                    estimated_atoms=section.estimated_atoms,
                )
            )

            # Add subsections
            self._build_toc(section.subsections, entries)

    def _extract_section_number(self, section_id: str) -> str | None:
        """Extract readable section number from internal ID."""
        # "NET-M11-S11-2-3" -> "11.2.3"
        match = re.search(r"-S(\d+(?:-\d+)*)", section_id)
        if match:
            return match.group(1).replace("-", ".")
        return None

    def search(
        self, module_num: int, query: str, max_results: int = 20
    ) -> list[SearchResult]:
        """
        Search for a keyword within module content.

        Args:
            module_num: Module number (1-17)
            query: Search query (case-insensitive)
            max_results: Maximum number of results to return

        Returns:
            List of SearchResult items with context
        """
        module = self.get_module(module_num)
        if not module:
            return []

        results: list[SearchResult] = []
        pattern = re.compile(re.escape(query), re.IGNORECASE)

        for section in module.sections:
            self._search_section(section, pattern, results, max_results)
            if len(results) >= max_results:
                break

        return results[:max_results]

    def _search_section(
        self,
        section: Section,
        pattern: re.Pattern,
        results: list[SearchResult],
        max_results: int,
    ) -> None:
        """Recursively search a section and its subsections."""
        if len(results) >= max_results:
            return

        # Search in raw content to preserve line numbers
        lines = section.raw_content.split("\n")
        for i, line in enumerate(lines):
            match = pattern.search(line)
            if match:
                # Build context (line before, match line, line after)
                start = max(0, i - 1)
                end = min(len(lines), i + 2)
                context_lines = lines[start:end]
                context = "\n".join(context_lines)

                # Extract section number for display
                section_num = self._extract_section_number(section.id) or section.id

                results.append(
                    SearchResult(
                        section_id=section_num,
                        section_title=section.title,
                        line_number=i + 1,
                        context=context,
                        match_text=match.group(0),
                    )
                )

                if len(results) >= max_results:
                    return

        # Search subsections
        for subsection in section.subsections:
            self._search_section(subsection, pattern, results, max_results)

    def get_section_content_formatted(self, section: Section) -> str:
        """
        Get formatted content for display.

        Preserves structure but cleans up for terminal display.
        """
        lines = []

        # Add section header
        section_num = self._extract_section_number(section.id) or ""
        lines.append(f"## {section_num} {section.title}\n")

        # Add main content
        if section.content.strip():
            lines.append(section.content.strip())
            lines.append("")

        # Add key terms if present
        if section.key_terms:
            lines.append("### Key Terms")
            for term in section.key_terms:
                if term.definition:
                    lines.append(f"  - **{term.term}**: {term.definition}")
                else:
                    lines.append(f"  - **{term.term}**")
            lines.append("")

        # Add tables if present
        for table in section.tables:
            if table.caption:
                lines.append(f"*{table.caption}*")
            # Format as simple table
            if table.headers:
                lines.append("| " + " | ".join(table.headers) + " |")
                lines.append("|" + "|".join(["---"] * len(table.headers)) + "|")
                for row in table.rows:
                    lines.append("| " + " | ".join(row) + " |")
            lines.append("")

        # Add commands if present
        if section.commands:
            lines.append("### CLI Commands")
            for cmd in section.commands:
                mode_prefix = f"({cmd.mode}) " if cmd.mode != "unknown" else ""
                lines.append(f"  {mode_prefix}{cmd.command}")
            lines.append("")

        return "\n".join(lines)

    def get_all_sections_flat(self, module_num: int) -> list[Section]:
        """
        Get all sections as a flat list for sequential reading.

        Args:
            module_num: Module number (1-17)

        Returns:
            Flat list of all sections in reading order
        """
        module = self.get_module(module_num)
        if not module:
            return []

        sections: list[Section] = []
        self._flatten_sections(module.sections, sections)
        return sections

    def _flatten_sections(
        self, sections: list[Section], flat_list: list[Section]
    ) -> None:
        """Recursively flatten section hierarchy."""
        for section in sections:
            flat_list.append(section)
            self._flatten_sections(section.subsections, flat_list)
