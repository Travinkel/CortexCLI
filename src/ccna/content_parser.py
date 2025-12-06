"""
CCNA Content Parser.

Parses CCNA module TXT files into structured content for learning atom generation.
Extracts sections, CLI commands, tables, and key terms with content density estimation.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class CLICommand:
    """Cisco IOS CLI command extracted from content."""

    command: str
    mode: str  # user, privileged, config, interface, etc.
    purpose: str
    example: Optional[str] = None
    context_section: str = ""

    def __post_init__(self):
        """Normalize command mode."""
        mode_map = {
            "router>": "user",
            "router#": "privileged",
            "router(config)#": "config",
            "router(config-if)#": "interface",
            "router(config-line)#": "line",
            "router(config-router)#": "router",
            "switch>": "user",
            "switch#": "privileged",
            "switch(config)#": "config",
            "switch(config-if)#": "interface",
        }
        lower_mode = self.mode.lower().strip()
        for prompt, normalized in mode_map.items():
            if prompt in lower_mode or normalized == lower_mode:
                self.mode = normalized
                break


@dataclass
class KeyTerm:
    """Key terminology extracted from content."""

    term: str
    definition: str
    context: str  # Section where defined
    is_bold: bool = False  # Was marked as bold in source


@dataclass
class Table:
    """Markdown table extracted from content."""

    headers: list[str]
    rows: list[list[str]]
    caption: str = ""
    context_section: str = ""

    @property
    def column_count(self) -> int:
        """Number of columns in the table."""
        return len(self.headers) if self.headers else 0

    @property
    def row_count(self) -> int:
        """Number of data rows (excluding header)."""
        return len(self.rows)


@dataclass
class ContentDensity:
    """Content density estimation for a section."""

    fact_count: int = 0
    command_count: int = 0
    concept_count: int = 0
    procedure_count: int = 0
    table_row_count: int = 0

    @property
    def estimated_flashcards(self) -> int:
        """Estimate number of flashcards based on content density."""
        # Each fact = 1 card, each command = 1-2 cards, each concept = 2-3 cards
        # Each procedure step = 1 card, each table row = 1 card
        return (
            self.fact_count
            + self.command_count * 2
            + self.concept_count * 2
            + self.procedure_count
            + self.table_row_count
        )

    @property
    def estimated_mcq(self) -> int:
        """Estimate number of MCQ questions."""
        # Concepts and procedures work well as MCQ
        return max(1, (self.concept_count + self.procedure_count) // 2)

    @property
    def estimated_parsons(self) -> int:
        """Estimate number of Parsons problems (for CLI procedures)."""
        # Each multi-step command sequence = 1 Parsons problem
        return max(0, self.procedure_count // 3)

    @property
    def total_estimated_atoms(self) -> int:
        """Total estimated learning atoms."""
        return (
            self.estimated_flashcards
            + self.estimated_mcq
            + self.estimated_parsons
        )


@dataclass
class Section:
    """A section or subsection of the CCNA module content."""

    id: str  # e.g., NET-M1-S1, NET-M1-S1-1
    title: str
    level: int  # 1=topic (#), 2=topic (##), 3=subtopic (###), 4=sub-subtopic (####)
    content: str
    raw_content: str  # Unparsed original content
    subsections: list["Section"] = field(default_factory=list)
    commands: list[CLICommand] = field(default_factory=list)
    tables: list[Table] = field(default_factory=list)
    key_terms: list[KeyTerm] = field(default_factory=list)
    bullet_points: list[str] = field(default_factory=list)
    numbered_lists: list[list[str]] = field(default_factory=list)
    _density: Optional[ContentDensity] = field(default=None, repr=False)

    @property
    def density(self) -> ContentDensity:
        """Calculate content density for this section."""
        if self._density is not None:
            return self._density

        density = ContentDensity()

        # Count facts from sentences (rough estimate: ~1 fact per 2 sentences)
        sentences = re.split(r"[.!?]+", self.content)
        sentences = [s.strip() for s in sentences if len(s.strip()) > 20]
        density.fact_count = len(sentences) // 2

        # Count commands
        density.command_count = len(self.commands)

        # Count concepts (key terms + bold definitions)
        density.concept_count = len(self.key_terms)

        # Count procedure steps (numbered list items)
        for numbered_list in self.numbered_lists:
            density.procedure_count += len(numbered_list)

        # Count table rows
        for table in self.tables:
            density.table_row_count += table.row_count

        # Include subsections
        for subsection in self.subsections:
            sub_density = subsection.density
            density.fact_count += sub_density.fact_count
            density.command_count += sub_density.command_count
            density.concept_count += sub_density.concept_count
            density.procedure_count += sub_density.procedure_count
            density.table_row_count += sub_density.table_row_count

        self._density = density
        return density

    @property
    def estimated_atoms(self) -> int:
        """Estimated total learning atoms for this section."""
        return self.density.total_estimated_atoms

    @property
    def all_commands(self) -> list[CLICommand]:
        """Get all commands including from subsections."""
        commands = list(self.commands)
        for subsection in self.subsections:
            commands.extend(subsection.all_commands)
        return commands

    @property
    def all_tables(self) -> list[Table]:
        """Get all tables including from subsections."""
        tables = list(self.tables)
        for subsection in self.subsections:
            tables.extend(subsection.all_tables)
        return tables

    @property
    def all_key_terms(self) -> list[KeyTerm]:
        """Get all key terms including from subsections."""
        terms = list(self.key_terms)
        for subsection in self.subsections:
            terms.extend(subsection.all_key_terms)
        return terms


@dataclass
class ModuleContent:
    """Complete parsed content of a CCNA module."""

    module_id: str  # e.g., NET-M1, NET-M2
    module_number: int
    title: str
    description: str
    sections: list[Section]
    total_lines: int
    file_path: Path
    objectives: list[dict[str, str]] = field(default_factory=list)

    @property
    def estimated_atoms(self) -> int:
        """Total estimated learning atoms for the module."""
        return sum(s.estimated_atoms for s in self.sections)

    @property
    def total_commands(self) -> int:
        """Total CLI commands in the module."""
        return sum(len(s.all_commands) for s in self.sections)

    @property
    def total_tables(self) -> int:
        """Total tables in the module."""
        return sum(len(s.all_tables) for s in self.sections)

    @property
    def total_key_terms(self) -> int:
        """Total key terms in the module."""
        return sum(len(s.all_key_terms) for s in self.sections)

    @property
    def section_count(self) -> int:
        """Total number of sections (including subsections)."""
        count = 0
        for section in self.sections:
            count += 1 + self._count_subsections(section)
        return count

    def _count_subsections(self, section: Section) -> int:
        """Recursively count subsections."""
        count = len(section.subsections)
        for sub in section.subsections:
            count += self._count_subsections(sub)
        return count

    def get_section_by_id(self, section_id: str) -> Optional[Section]:
        """Find a section by its ID."""
        for section in self.sections:
            if section.id == section_id:
                return section
            result = self._find_in_subsections(section, section_id)
            if result:
                return result
        return None

    def _find_in_subsections(
        self, section: Section, target_id: str
    ) -> Optional[Section]:
        """Recursively search subsections for a target ID."""
        for sub in section.subsections:
            if sub.id == target_id:
                return sub
            result = self._find_in_subsections(sub, target_id)
            if result:
                return result
        return None


class CCNAContentParser:
    """
    Parser for CCNA module TXT files.

    Hardened for format variations:
    - Flexible header detection (markdown # and Cisco numbered formats)
    - Multiple header styles: "Part 1:", "Section 1.1", "1.0 Introduction"
    - Validation logging to detect parsing gaps
    """

    # Patterns for content extraction - FLEXIBLE to handle format variations
    # Markdown headers: # through #### (single # now supported)
    HEADER_PATTERN = re.compile(r"^(#{1,4})\s+(.+)$", re.MULTILINE)

    # Cisco course format: "9.1.1 Topic Title" or "9.0 Introduction"
    # Also captures variations like "9.1.1. Topic" (with trailing dot)
    CISCO_HEADER_PATTERN = re.compile(
        r"^(\d+(?:\.\d+){0,2})\.?\s+([A-Z][^\n]+)$", re.MULTILINE
    )

    # Alternative header formats commonly seen in course materials
    # "Part 1: Title", "Section 1.1: Title", "Module 1 - Title"
    ALT_HEADER_PATTERNS = [
        re.compile(r"^(?:Part|Section|Module|Unit|Chapter)\s+(\d+(?:\.\d+)*)[:\s\-]+(.+)$", re.MULTILINE | re.IGNORECASE),
        re.compile(r"^(\d+(?:\.\d+)*)\s*[:\-–—]\s*(.+)$", re.MULTILINE),  # "1.1: Title" or "1.1 - Title"
    ]

    TABLE_HEADER_PATTERN = re.compile(r"^\|(.+)\|$", re.MULTILINE)
    TABLE_SEPARATOR_PATTERN = re.compile(r"^\|[\s\-:|]+\|$", re.MULTILINE)
    CODE_BLOCK_PATTERN = re.compile(r"```(\w*)\n([\s\S]*?)```", re.MULTILINE)
    BOLD_PATTERN = re.compile(r"\*\*([^*]+)\*\*")
    BULLET_PATTERN = re.compile(r"^[-*]\s+(.+)$", re.MULTILINE)
    NUMBERED_PATTERN = re.compile(r"^\d+\.\s+(.+)$", re.MULTILINE)
    SECTION_NUMBER_PATTERN = re.compile(r"^(\d+(?:\.\d+)*)\s+(.+)$")

    # CLI command patterns
    CLI_PROMPT_PATTERNS = [
        re.compile(r"^(Router|Switch|R\d|S\d|[\w-]+)[>#](.+)$", re.IGNORECASE),
        re.compile(r"^(Router|Switch|[\w-]+)\(config(?:-\w+)?\)#(.+)$", re.IGNORECASE),
    ]

    def __init__(self, modules_path: str | Path = "docs/CCNA"):
        """Initialize parser with path to CCNA modules directory."""
        self.modules_path = Path(modules_path)

    def get_available_modules(self) -> list[Path]:
        """List all available CCNA module files."""
        if not self.modules_path.exists():
            return []
        return sorted(
            self.modules_path.glob("CCNA Module *.txt"),
            key=lambda p: self._extract_module_number(p.stem),
        )

    def _extract_module_number(self, stem: str) -> int:
        """Extract module number from filename stem."""
        match = re.search(r"Module\s*(\d+)", stem, re.IGNORECASE)
        return int(match.group(1)) if match else 0

    def parse_module(self, file_path: Path | str) -> ModuleContent:
        """Parse a CCNA module TXT file into structured content."""
        file_path = Path(file_path)

        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()

        lines = content.split("\n")
        total_lines = len(lines)

        # Extract module number from filename
        module_number = self._extract_module_number(file_path.stem)
        module_id = f"NET-M{module_number}"

        # Extract title and description from first lines
        title, description = self._extract_title_description(content)

        # Extract module objectives
        objectives = self._extract_objectives(content)

        # Parse sections
        sections = self._parse_sections(content, module_id)

        return ModuleContent(
            module_id=module_id,
            module_number=module_number,
            title=title,
            description=description,
            sections=sections,
            total_lines=total_lines,
            file_path=file_path,
            objectives=objectives,
        )

    def parse_all_modules(self) -> list[ModuleContent]:
        """Parse all available CCNA modules."""
        modules = []
        for file_path in self.get_available_modules():
            modules.append(self.parse_module(file_path))
        return modules

    def _extract_title_description(self, content: str) -> tuple[str, str]:
        """Extract title and description from module header."""
        lines = content.split("\n")
        title = ""
        description = ""

        for line in lines[:10]:  # Check first 10 lines
            line = line.strip()
            if line.startswith("> **"):
                # Format: > **CCNA: Introduction to Networks** — Module 1...
                match = re.match(r">\s*\*\*([^*]+)\*\*\s*[—-]\s*(.+)", line)
                if match:
                    title = match.group(1).strip()
                    description = match.group(2).strip()
                    break
            elif line.startswith("# "):
                title = line[2:].strip()
                break

        return title, description

    def _extract_objectives(self, content: str) -> list[dict[str, str]]:
        """Extract module objectives from the objectives table."""
        objectives = []

        # Find the objectives section
        obj_match = re.search(
            r"##\s*Module Objectives\s*\n\n([\s\S]+?)(?=\n---|\n##|$)",
            content,
            re.IGNORECASE,
        )

        if not obj_match:
            return objectives

        obj_content = obj_match.group(1)

        # Parse the table
        table = self._parse_table(obj_content)
        if table and table.headers:
            for row in table.rows:
                if len(row) >= 2:
                    objectives.append({
                        "topic": row[0].strip(),
                        "objective": row[1].strip(),
                    })

        return objectives

    def _parse_sections(self, content: str, module_id: str) -> list[Section]:
        """
        Parse all sections from content.

        Hardened to detect multiple header formats and log coverage gaps.
        """
        sections = []
        current_section = None
        current_subsection = None
        section_counter = 0

        # Collect all headers (both markdown and Cisco format)
        header_matches = []

        # Markdown headers (# through ####)
        for match in self.HEADER_PATTERN.finditer(content):
            level = len(match.group(1))  # Number of #
            title = match.group(2).strip()
            header_matches.append({
                "pos": match.start(),
                "end": match.end(),
                "level": level,
                "title": title,
                "section_number": None,
                "format": "markdown",
            })

        # Cisco course format (9.1.1 Title)
        for match in self.CISCO_HEADER_PATTERN.finditer(content):
            section_number = match.group(1)
            title = match.group(2).strip()

            # Skip lines that are just instructions like "Scroll to begin"
            if title.lower() in ("scroll to begin", "check your understanding"):
                continue

            # Determine level from section number depth
            # 9.0 = level 2 (main topic)
            # 9.1 = level 2 (main topic)
            # 9.1.1 = level 3 (subtopic)
            parts = section_number.split(".")
            if len(parts) <= 2:
                level = 2  # Main section (9.0, 9.1)
            else:
                level = 3  # Subsection (9.1.1)

            header_matches.append({
                "pos": match.start(),
                "end": match.end(),
                "level": level,
                "title": title,
                "section_number": section_number,
                "format": "cisco",
            })

        # Alternative header formats (Part 1:, Section 1.1:, etc.)
        for alt_pattern in self.ALT_HEADER_PATTERNS:
            for match in alt_pattern.finditer(content):
                section_number = match.group(1)
                title = match.group(2).strip()

                # Skip if position already captured by another pattern
                already_captured = any(
                    abs(h["pos"] - match.start()) < 20 for h in header_matches
                )
                if already_captured:
                    continue

                parts = section_number.split(".")
                level = 2 if len(parts) <= 2 else 3

                header_matches.append({
                    "pos": match.start(),
                    "end": match.end(),
                    "level": level,
                    "title": title,
                    "section_number": section_number,
                    "format": "alternative",
                })

        # Sort by position in content
        header_matches.sort(key=lambda h: h["pos"])

        # Remove duplicate headers (same position, different format)
        seen_positions = set()
        unique_headers = []
        for h in header_matches:
            # Use position rounded to account for minor differences
            pos_key = h["pos"] // 10
            if pos_key not in seen_positions:
                seen_positions.add(pos_key)
                unique_headers.append(h)

        header_matches = unique_headers

        for i, header in enumerate(header_matches):
            level = header["level"]
            title = header["title"]
            section_number = header["section_number"]

            # Skip module objectives section
            if "module objectives" in title.lower():
                continue

            # Get content until next header
            start = header["end"]
            end = header_matches[i + 1]["pos"] if i + 1 < len(header_matches) else len(content)
            section_content = content[start:end].strip()

            # Generate section ID
            if section_number:
                section_id = f"{module_id}-S{section_number.replace('.', '-')}"
            else:
                # Extract section number from title if present (for markdown headers)
                section_num_match = self.SECTION_NUMBER_PATTERN.match(title)
                if section_num_match:
                    section_number = section_num_match.group(1)
                    title = section_num_match.group(2).strip()
                    section_id = f"{module_id}-S{section_number.replace('.', '-')}"
                else:
                    section_counter += 1
                    section_id = f"{module_id}-S{section_counter}"

            # Parse section components
            commands = self._extract_commands(section_content, section_id)
            tables = self._extract_tables(section_content, section_id)
            key_terms = self._extract_key_terms(section_content, section_id)
            bullet_points = self._extract_bullet_points(section_content)
            numbered_lists = self._extract_numbered_lists(section_content)

            # Clean content (remove parsed elements for cleaner text)
            clean_content = self._clean_content(section_content)

            section = Section(
                id=section_id,
                title=title,
                level=level,
                content=clean_content,
                raw_content=section_content,
                commands=commands,
                tables=tables,
                key_terms=key_terms,
                bullet_points=bullet_points,
                numbered_lists=numbered_lists,
            )

            # Organize into hierarchy
            # Level 1 (#) and Level 2 (##) are both treated as main sections
            if level <= 2:
                if current_section:
                    sections.append(current_section)
                current_section = section
                current_subsection = None
            elif level == 3 and current_section:
                current_section.subsections.append(section)
                current_subsection = section
            elif level == 4 and current_subsection:
                current_subsection.subsections.append(section)
            else:
                # Fallback: add as top-level if hierarchy is unclear
                if current_section:
                    current_section.subsections.append(section)
                else:
                    sections.append(section)

        # Don't forget the last section
        if current_section:
            sections.append(current_section)

        return sections

    def _extract_commands(self, content: str, context: str) -> list[CLICommand]:
        """Extract CLI commands from content."""
        commands = []

        # Look for code blocks first
        for match in self.CODE_BLOCK_PATTERN.finditer(content):
            lang = match.group(1).lower()
            code = match.group(2).strip()

            # Check if it's a CLI command block
            if lang in ("", "cisco", "ios", "cli", "shell", "bash"):
                for line in code.split("\n"):
                    line = line.strip()
                    if not line:
                        continue

                    cmd = self._parse_cli_line(line, context)
                    if cmd:
                        commands.append(cmd)

        # Also look for inline commands (Router#, Switch#, etc.)
        for pattern in self.CLI_PROMPT_PATTERNS:
            for match in pattern.finditer(content):
                prompt = match.group(1)
                cmd_text = match.group(2).strip()

                mode = self._determine_mode(prompt)
                commands.append(
                    CLICommand(
                        command=cmd_text,
                        mode=mode,
                        purpose="",  # Will be inferred from context
                        context_section=context,
                    )
                )

        return commands

    def _parse_cli_line(self, line: str, context: str) -> Optional[CLICommand]:
        """Parse a single CLI line into a CLICommand."""
        # Check for prompt patterns
        for pattern in self.CLI_PROMPT_PATTERNS:
            match = pattern.match(line)
            if match:
                prompt = match.group(1)
                cmd_text = match.group(2).strip()
                mode = self._determine_mode(prompt)

                return CLICommand(
                    command=cmd_text,
                    mode=mode,
                    purpose="",
                    context_section=context,
                )

        # Check for commands without prompts (common in documentation)
        if line and not line.startswith("#") and not line.startswith("!"):
            # Looks like a command if it starts with known keywords
            cmd_keywords = [
                "show", "configure", "interface", "ip", "router", "enable",
                "hostname", "line", "password", "service", "no", "exit",
                "end", "copy", "write", "ping", "traceroute", "debug",
            ]
            first_word = line.split()[0].lower() if line.split() else ""
            if first_word in cmd_keywords:
                return CLICommand(
                    command=line,
                    mode="unknown",
                    purpose="",
                    context_section=context,
                )

        return None

    def _determine_mode(self, prompt: str) -> str:
        """Determine CLI mode from prompt string."""
        prompt_lower = prompt.lower()
        if "(config-if)" in prompt_lower:
            return "interface"
        elif "(config-line)" in prompt_lower:
            return "line"
        elif "(config-router)" in prompt_lower:
            return "router"
        elif "(config" in prompt_lower:
            return "config"
        elif prompt.endswith("#"):
            return "privileged"
        elif prompt.endswith(">"):
            return "user"
        return "unknown"

    def _extract_tables(self, content: str, context: str) -> list[Table]:
        """Extract markdown tables from content."""
        tables = []
        lines = content.split("\n")
        i = 0

        while i < len(lines):
            line = lines[i].strip()

            # Check if this is a table header line
            if line.startswith("|") and line.endswith("|"):
                # Look for separator line
                if i + 1 < len(lines):
                    next_line = lines[i + 1].strip()
                    if self.TABLE_SEPARATOR_PATTERN.match(next_line):
                        table = self._parse_table_from_lines(lines, i, context)
                        if table:
                            tables.append(table)
                            # Skip past the table
                            i += 2 + table.row_count
                            continue

            i += 1

        return tables

    def _parse_table_from_lines(
        self, lines: list[str], start: int, context: str
    ) -> Optional[Table]:
        """Parse a markdown table starting at the given line index."""
        header_line = lines[start].strip()
        headers = [h.strip() for h in header_line.split("|")[1:-1]]

        if not headers:
            return None

        rows = []
        i = start + 2  # Skip header and separator

        while i < len(lines):
            line = lines[i].strip()
            if not line.startswith("|") or not line.endswith("|"):
                break

            cells = [c.strip() for c in line.split("|")[1:-1]]
            if len(cells) == len(headers):
                rows.append(cells)
            i += 1

        if not rows:
            return None

        # Try to find a caption (text immediately before the table)
        caption = ""
        if start > 0:
            prev_line = lines[start - 1].strip()
            if prev_line and not prev_line.startswith("|") and not prev_line.startswith("#"):
                caption = prev_line

        return Table(
            headers=headers,
            rows=rows,
            caption=caption,
            context_section=context,
        )

    def _parse_table(self, content: str) -> Optional[Table]:
        """Parse a single table from content string."""
        tables = self._extract_tables(content, "")
        return tables[0] if tables else None

    def _extract_key_terms(self, content: str, context: str) -> list[KeyTerm]:
        """Extract key terms (bold definitions) from content."""
        terms = []

        # Find bold terms with definitions
        # Pattern: **Term** — definition or **Term**: definition
        pattern = re.compile(
            r"\*\*([^*]+)\*\*\s*[—:\-–]\s*([^.\n]+(?:\.[^\n]*)?)",
            re.MULTILINE,
        )

        for match in pattern.finditer(content):
            term = match.group(1).strip()
            definition = match.group(2).strip()

            # Clean up definition
            definition = re.sub(r"\s+", " ", definition)

            terms.append(
                KeyTerm(
                    term=term,
                    definition=definition,
                    context=context,
                    is_bold=True,
                )
            )

        # Also look for simpler bold terms that might be important
        for match in self.BOLD_PATTERN.finditer(content):
            term = match.group(1).strip()

            # Skip if already captured as a definition
            if any(t.term == term for t in terms):
                continue

            # Skip short terms or common words
            if len(term) < 3 or term.lower() in ("note", "example", "tip", "warning"):
                continue

            # Try to extract context around the term
            start = max(0, match.start() - 50)
            end = min(len(content), match.end() + 100)
            context_text = content[start:end]

            terms.append(
                KeyTerm(
                    term=term,
                    definition="",  # No explicit definition
                    context=context_text,
                    is_bold=True,
                )
            )

        return terms

    def _extract_bullet_points(self, content: str) -> list[str]:
        """Extract bullet point items from content."""
        return [match.group(1).strip() for match in self.BULLET_PATTERN.finditer(content)]

    def _extract_numbered_lists(self, content: str) -> list[list[str]]:
        """Extract numbered lists from content."""
        lists = []
        current_list = []

        lines = content.split("\n")
        for line in lines:
            match = re.match(r"^\d+\.\s+(.+)$", line.strip())
            if match:
                current_list.append(match.group(1).strip())
            elif current_list:
                lists.append(current_list)
                current_list = []

        if current_list:
            lists.append(current_list)

        return lists

    def _clean_content(self, content: str) -> str:
        """Clean content by removing code blocks, tables, etc."""
        # Remove code blocks
        content = self.CODE_BLOCK_PATTERN.sub("", content)

        # Remove tables (lines starting and ending with |)
        lines = content.split("\n")
        clean_lines = []
        skip_table = False

        for line in lines:
            stripped = line.strip()
            if stripped.startswith("|") and stripped.endswith("|"):
                skip_table = True
                continue
            elif skip_table and not stripped:
                skip_table = False
                continue
            elif not skip_table:
                clean_lines.append(line)

        content = "\n".join(clean_lines)

        # Remove blockquotes markers
        content = re.sub(r"^>\s*", "", content, flags=re.MULTILINE)

        # Remove horizontal rules
        content = re.sub(r"^---+\s*$", "", content, flags=re.MULTILINE)

        # Clean up excessive whitespace
        content = re.sub(r"\n{3,}", "\n\n", content)

        return content.strip()

    def get_module_summary(self, module: ModuleContent) -> dict:
        """Generate a summary of the parsed module content."""
        return {
            "module_id": module.module_id,
            "module_number": module.module_number,
            "title": module.title,
            "description": module.description,
            "total_lines": module.total_lines,
            "section_count": module.section_count,
            "top_level_sections": len(module.sections),
            "total_commands": module.total_commands,
            "total_tables": module.total_tables,
            "total_key_terms": module.total_key_terms,
            "estimated_atoms": module.estimated_atoms,
            "objectives": module.objectives,
            "sections": [
                {
                    "id": s.id,
                    "title": s.title,
                    "level": s.level,
                    "subsection_count": len(s.subsections),
                    "commands": len(s.all_commands),
                    "tables": len(s.all_tables),
                    "key_terms": len(s.all_key_terms),
                    "estimated_atoms": s.estimated_atoms,
                }
                for s in module.sections
            ],
        }

    def validate_coverage(self, module: ModuleContent) -> dict:
        """
        Validate parsing coverage to detect content gaps.

        Returns:
            Dict with coverage metrics and warnings:
            - content_coverage_pct: % of file content captured in sections
            - empty_sections: Sections with no meaningful content
            - warnings: List of potential issues
        """
        warnings = []

        # Check for empty sections
        empty_sections = []

        def check_section_content(section: Section) -> None:
            # Consider "empty" if < 50 chars of clean content
            if len(section.content.strip()) < 50:
                empty_sections.append({
                    "id": section.id,
                    "title": section.title,
                    "content_length": len(section.content.strip()),
                })
            for sub in section.subsections:
                check_section_content(sub)

        for section in module.sections:
            check_section_content(section)

        if empty_sections:
            warnings.append(
                f"Found {len(empty_sections)} sections with <50 chars content. "
                f"Check if headers are being parsed correctly."
            )

        # Calculate content coverage
        total_section_chars = sum(
            len(s.raw_content) for s in module.sections
        )
        with open(module.file_path, "r", encoding="utf-8") as f:
            total_file_chars = len(f.read())

        coverage_pct = (total_section_chars / max(1, total_file_chars)) * 100

        if coverage_pct < 70:
            warnings.append(
                f"Only {coverage_pct:.1f}% of file content captured in sections. "
                f"This suggests header patterns may not match the file format."
            )

        # Check for expected section counts based on module number
        # CCNA modules typically have 5-15 sections
        if len(module.sections) == 0:
            warnings.append(
                "No sections found! Check if the file uses an unsupported header format."
            )
        elif len(module.sections) < 3:
            warnings.append(
                f"Only {len(module.sections)} sections found. "
                f"Expected 5-15 for a CCNA module."
            )

        return {
            "content_coverage_pct": round(coverage_pct, 1),
            "total_sections": module.section_count,
            "empty_sections": empty_sections,
            "warnings": warnings,
            "is_valid": len(warnings) == 0,
        }
