"""
Content parser for local text files.

Parses plain text and markdown into structured content
suitable for atom generation.
"""

import re
from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class ContentSection:
    """A section of content (typically a heading + body)."""

    title: str
    content: str
    level: int = 1  # Heading level (1 = H1, 2 = H2, etc.)
    source_file: str = ""
    line_number: int = 0

    @property
    def word_count(self) -> int:
        return len(self.content.split())


@dataclass
class ParsedContent:
    """Result of parsing a content file."""

    source_path: str
    title: str
    sections: list[ContentSection] = field(default_factory=list)
    raw_text: str = ""
    metadata: dict = field(default_factory=dict)

    @property
    def total_words(self) -> int:
        return sum(s.word_count for s in self.sections)

    def iter_chunks(self, max_words: int = 500) -> Iterator[str]:
        """Iterate over content in chunks suitable for LLM processing."""
        for section in self.sections:
            if section.word_count <= max_words:
                yield f"## {section.title}\n\n{section.content}"
            else:
                # Split large sections
                words = section.content.split()
                for i in range(0, len(words), max_words):
                    chunk = " ".join(words[i : i + max_words])
                    yield f"## {section.title} (Part {i // max_words + 1})\n\n{chunk}"


class ContentParser:
    """Parser for local content files."""

    def parse_file(self, path: Path | str) -> ParsedContent:
        """Parse a single file into structured content."""
        path = Path(path)

        if not path.exists():
            raise FileNotFoundError(f"Content file not found: {path}")

        text = path.read_text(encoding="utf-8")

        if path.suffix.lower() == ".md":
            return self._parse_markdown(text, str(path))
        else:
            return self._parse_plaintext(text, str(path))

    def parse_directory(
        self, path: Path | str, pattern: str = "*.txt"
    ) -> list[ParsedContent]:
        """Parse all matching files in a directory."""
        path = Path(path)
        results = []

        for file_path in sorted(path.glob(pattern)):
            try:
                results.append(self.parse_file(file_path))
            except Exception as e:
                print(f"Warning: Failed to parse {file_path}: {e}")

        return results

    def _parse_markdown(self, text: str, source: str) -> ParsedContent:
        """Parse markdown content with heading structure."""
        sections = []
        current_section = None
        current_content = []
        line_number = 0

        # Extract title from first H1 or filename
        title_match = re.search(r"^#\s+(.+)$", text, re.MULTILINE)
        title = title_match.group(1) if title_match else Path(source).stem

        for line in text.split("\n"):
            line_number += 1

            # Check for heading
            heading_match = re.match(r"^(#{1,6})\s+(.+)$", line)

            if heading_match:
                # Save previous section
                if current_section:
                    current_section.content = "\n".join(current_content).strip()
                    if current_section.content:
                        sections.append(current_section)

                # Start new section
                level = len(heading_match.group(1))
                current_section = ContentSection(
                    title=heading_match.group(2).strip(),
                    content="",
                    level=level,
                    source_file=source,
                    line_number=line_number,
                )
                current_content = []
            else:
                current_content.append(line)

        # Save final section
        if current_section:
            current_section.content = "\n".join(current_content).strip()
            if current_section.content:
                sections.append(current_section)
        elif current_content:
            # No headings found - treat entire content as one section
            sections.append(
                ContentSection(
                    title=title,
                    content="\n".join(current_content).strip(),
                    level=1,
                    source_file=source,
                    line_number=1,
                )
            )

        return ParsedContent(
            source_path=source,
            title=title,
            sections=sections,
            raw_text=text,
        )

    def _parse_plaintext(self, text: str, source: str) -> ParsedContent:
        """Parse plain text, splitting on blank lines or paragraph markers."""
        title = Path(source).stem

        # Split into paragraphs
        paragraphs = re.split(r"\n\s*\n+", text.strip())

        sections = []
        for i, para in enumerate(paragraphs):
            para = para.strip()
            if not para:
                continue

            # Use first line as title if it looks like a heading
            lines = para.split("\n")
            first_line = lines[0].strip()

            # Heuristic: short first line followed by content = heading
            if (
                len(lines) > 1
                and len(first_line) < 80
                and not first_line.endswith((".", "!", "?", ","))
            ):
                section_title = first_line
                content = "\n".join(lines[1:]).strip()
            else:
                section_title = f"Section {i + 1}"
                content = para

            sections.append(
                ContentSection(
                    title=section_title,
                    content=content,
                    level=2,
                    source_file=source,
                )
            )

        return ParsedContent(
            source_path=source,
            title=title,
            sections=sections,
            raw_text=text,
        )
