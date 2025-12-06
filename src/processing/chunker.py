"""
Section-Based Chunker for CCNA Module Content.

Implements hierarchical parsing that respects the document structure to avoid
the "Lost in the Middle" phenomenon where LLMs ignore content in the middle
of long contexts.

Key Features:
1. Parses at sub-section level (## or # **X.X.X**) for optimal context size
2. Carries parent context (Module > Section > Sub-Section) into each chunk
3. Preserves [source] tags and figure descriptions for traceability
4. Handles multiple CCNA formatting patterns

Based on research showing LLMs perform best with focused, 500-2000 token chunks
rather than entire documents. Each chunk should yield 3-5 high-quality atoms.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Iterator, Optional


class ChunkType(str, Enum):
    """Type of content in a chunk."""
    INTRODUCTION = "introduction"  # Module intro (X.0.X)
    CONCEPTUAL = "conceptual"      # Theory/explanation sections
    PROCEDURAL = "procedural"      # Step-by-step configuration
    REFERENCE = "reference"        # Tables, command references
    PRACTICE = "practice"          # Labs, Packet Tracer activities
    SUMMARY = "summary"            # Module summary sections


@dataclass
class SourceTag:
    """Represents a [source] tag from the content."""
    tag_id: int
    position: int  # Character position in chunk content


@dataclass
class TextChunk:
    """
    A semantic chunk of CCNA content at the sub-section level.

    Attributes:
        chunk_id: Section number (e.g., "10.1.1", "5.2.3")
        title: Sub-section title (e.g., "Basic Router Configuration Steps")
        parent_context: Hierarchical context (e.g., "Module 10: Basic Router Configuration > Configure Initial Router Settings")
        content: The actual text content
        module_number: Module number for organization
        chunk_type: Type of content for specialized processing
        has_cli_commands: Whether chunk contains Cisco CLI commands
        has_visuals: Whether chunk contains figure/image descriptions
        has_tables: Whether chunk contains markdown tables
        source_tags: List of [source] tags found in content
        word_count: Approximate word count for context size estimation
    """
    chunk_id: str
    title: str
    parent_context: str
    content: str
    module_number: int
    chunk_type: ChunkType = ChunkType.CONCEPTUAL
    has_cli_commands: bool = False
    has_visuals: bool = False
    has_tables: bool = False
    source_tags: list[SourceTag] = field(default_factory=list)
    word_count: int = 0

    def __post_init__(self):
        """Calculate derived fields after initialization."""
        if self.word_count == 0:
            self.word_count = len(self.content.split())

        # Detect CLI commands (code blocks with Router prompts)
        if re.search(r"Router[>#\(]|R\d+[>#\(]|Switch[>#\(]|S\d+[>#\(]", self.content):
            self.has_cli_commands = True

        # Detect visuals
        if re.search(r"\[VISUAL:|!\[.*\]\(|figure|diagram|image|animation shows", self.content, re.IGNORECASE):
            self.has_visuals = True

        # Detect tables
        if re.search(r"\|.*\|.*\|", self.content):
            self.has_tables = True

        # Determine chunk type
        self._infer_chunk_type()

    def _infer_chunk_type(self):
        """Infer the type of content based on patterns."""
        content_lower = self.content.lower()
        title_lower = self.title.lower()

        # Introduction sections (X.0.X)
        if ".0." in self.chunk_id:
            self.chunk_type = ChunkType.INTRODUCTION
        # Practice/lab activities
        elif any(kw in title_lower for kw in ["packet tracer", "lab", "syntax checker", "practice"]):
            self.chunk_type = ChunkType.PRACTICE
        # Procedural content (configuration steps)
        elif self.has_cli_commands or any(kw in title_lower for kw in ["configure", "configuration", "steps"]):
            self.chunk_type = ChunkType.PROCEDURAL
        # Summary sections
        elif any(kw in title_lower for kw in ["summary", "review", "what did i learn"]):
            self.chunk_type = ChunkType.SUMMARY
        # Reference tables
        elif self.has_tables and "command" in content_lower:
            self.chunk_type = ChunkType.REFERENCE
        else:
            self.chunk_type = ChunkType.CONCEPTUAL

    @property
    def formatted_context(self) -> str:
        """Get formatted context string for LLM prompts."""
        return f"""=== CONTEXT ===
{self.parent_context}

=== SECTION: {self.chunk_id} - {self.title} ===

{self.content}"""

    @property
    def is_suitable_for_atoms(self) -> bool:
        """Check if this chunk should be used for atom generation."""
        # Skip very short chunks
        if self.word_count < 50:
            return False
        # Skip practice activities (no content to extract)
        if self.chunk_type == ChunkType.PRACTICE and self.word_count < 100:
            return False
        return True


class CCNAChunker:
    """
    Hierarchical parser for CCNA module content.

    Handles multiple formatting patterns found in CCNA modules:
    - Pattern 1: `## X.X Section` and `### X.X.X Sub-section` (Module 1 style)
    - Pattern 2: `# X.X Section` and `# **X.X.X Sub-section**` (Module 4, 10 style)
    - Pattern 3: Mixed patterns with standalone `# Title` for figures

    The chunker preserves parent context to help LLMs understand where
    each chunk fits in the overall module structure.
    """

    # Regex patterns for different header styles
    PATTERNS = {
        # Module 1 style: ## 1.2 Section Title
        "md_section": re.compile(r"^##\s+([\d\.]+)\s+(.+)$", re.MULTILINE),
        # Module 1 style: ### 1.2.3 Sub-Section Title
        "md_subsection": re.compile(r"^###\s+([\d\.]+)\s+(.+)$", re.MULTILINE),

        # Module 4/10 style: # X.X Section Title (no bold)
        "hash_section": re.compile(r"^#\s+([\d]+\.[\d]+)\s+([^*\n].+)$", re.MULTILINE),
        # Module 4/10 style: # **X.X.X Sub-Section Title**
        "hash_bold_subsection": re.compile(r"^#\s+\*\*([\d\.]+)\s+(.+?)\*\*$", re.MULTILINE),

        # Module 14 style: Plain text headers like "14.0.1 Title" at line start
        "plain_section": re.compile(r"^([\d]+\.[\d]+)\s+([A-Z][^\n]+)$", re.MULTILINE),
        "plain_subsection": re.compile(r"^([\d]+\.[\d]+\.[\d]+)\s+([A-Z][^\n]+)$", re.MULTILINE),

        # Source tags: [source:1234]
        "source_tag": re.compile(r"\[source:(\d+)\]"),

        # Module number from content
        "module_number": re.compile(r"Module\s+(\d+)|^#?\s*(\d+)\.0", re.MULTILINE | re.IGNORECASE),

        # Figure/visual descriptions (often in bold or after images)
        "visual_marker": re.compile(r"!\[.*?\]\(.*?\)|The figure shows|The animation shows|The image shows", re.IGNORECASE),
    }

    def __init__(self, min_chunk_words: int = 50, max_chunk_words: int = 2000):
        """
        Initialize the chunker.

        Args:
            min_chunk_words: Minimum words for a valid chunk (skip smaller)
            max_chunk_words: Maximum words before splitting (avoid context overflow)
        """
        self.min_chunk_words = min_chunk_words
        self.max_chunk_words = max_chunk_words

    def parse_module(self, content: str, module_number: Optional[int] = None) -> list[TextChunk]:
        """
        Parse a CCNA module into semantic chunks.

        Args:
            content: Full text content of the module
            module_number: Module number (auto-detected if not provided)

        Returns:
            List of TextChunk objects, one per sub-section
        """
        # Auto-detect module number if not provided
        if module_number is None:
            module_number = self._detect_module_number(content)

        # Count patterns to determine best strategy
        md_section_count = len(self.PATTERNS["md_section"].findall(content))
        md_subsection_count = len(self.PATTERNS["md_subsection"].findall(content))
        hash_section_count = len(self.PATTERNS["hash_section"].findall(content))
        hash_bold_count = len(self.PATTERNS["hash_bold_subsection"].findall(content))
        plain_section_count = len(self.PATTERNS["plain_section"].findall(content))
        plain_subsection_count = len(self.PATTERNS["plain_subsection"].findall(content))

        md_total = md_section_count + md_subsection_count
        hash_total = hash_section_count + hash_bold_count
        plain_total = plain_section_count + plain_subsection_count

        # Use whichever pattern has more matches
        # This handles mixed-format modules like Module 4
        if hash_total >= md_total and hash_total >= plain_total and hash_total > 0:
            return self._parse_hash_bold_style(content, module_number)
        elif md_total >= plain_total and md_total > 0:
            return self._parse_markdown_style(content, module_number)
        elif plain_total > 0:
            return self._parse_plain_style(content, module_number)
        else:
            # Fallback: try all and use whichever produces more chunks
            md_chunks = self._parse_markdown_style(content, module_number)
            hash_chunks = self._parse_hash_bold_style(content, module_number)
            plain_chunks = self._parse_plain_style(content, module_number)
            all_results = [md_chunks, hash_chunks, plain_chunks]
            return max(all_results, key=len)

    def _detect_module_number(self, content: str) -> int:
        """Detect module number from content."""
        match = self.PATTERNS["module_number"].search(content)
        if match:
            return int(match.group(1) or match.group(2))
        return 0

    def _parse_markdown_style(self, content: str, module_number: int) -> list[TextChunk]:
        """Parse content with ## and ### style headers (Module 1 format)."""
        chunks = []

        # Find all section headers (##)
        section_matches = list(self.PATTERNS["md_section"].finditer(content))
        # Find all sub-section headers (###)
        subsection_matches = list(self.PATTERNS["md_subsection"].finditer(content))

        # Combine and sort by position
        all_headers = []
        for m in section_matches:
            all_headers.append(("section", m.group(1), m.group(2).strip(), m.start(), m.end()))
        for m in subsection_matches:
            all_headers.append(("subsection", m.group(1), m.group(2).strip(), m.start(), m.end()))

        all_headers.sort(key=lambda x: x[3])  # Sort by start position

        # Build context stack and extract chunks
        current_section = "Introduction"
        module_title = self._extract_module_title(content, module_number)

        for i, (header_type, section_id, title, start_pos, end_pos) in enumerate(all_headers):
            if header_type == "section":
                current_section = title

            # Get content until next header or end
            if i + 1 < len(all_headers):
                chunk_content = content[end_pos:all_headers[i + 1][3]]
            else:
                chunk_content = content[end_pos:]

            # Clean up content
            chunk_content = self._clean_content(chunk_content)

            # Skip if too short
            if len(chunk_content.split()) < self.min_chunk_words:
                continue

            # Build parent context
            parent_context = f"Module {module_number}: {module_title}"
            if header_type == "subsection":
                parent_context += f" > {current_section}"

            # Extract source tags
            source_tags = self._extract_source_tags(chunk_content)

            chunks.append(TextChunk(
                chunk_id=section_id,
                title=title,
                parent_context=parent_context,
                content=chunk_content,
                module_number=module_number,
                source_tags=source_tags,
            ))

        return chunks

    def _parse_hash_bold_style(self, content: str, module_number: int) -> list[TextChunk]:
        """Parse content with # X.X and # **X.X.X** style headers (Module 4/10 format)."""
        chunks = []

        # Find section headers: # X.X Section Title
        section_matches = list(self.PATTERNS["hash_section"].finditer(content))
        # Find sub-section headers: # **X.X.X Title**
        subsection_matches = list(self.PATTERNS["hash_bold_subsection"].finditer(content))

        # Combine and sort
        all_headers = []
        for m in section_matches:
            all_headers.append(("section", m.group(1), m.group(2).strip(), m.start(), m.end()))
        for m in subsection_matches:
            all_headers.append(("subsection", m.group(1), m.group(2).strip(), m.start(), m.end()))

        all_headers.sort(key=lambda x: x[3])

        # Build context and extract
        current_section = "Introduction"
        module_title = self._extract_module_title(content, module_number)

        for i, (header_type, section_id, title, start_pos, end_pos) in enumerate(all_headers):
            if header_type == "section":
                current_section = title

            # Get content until next header
            if i + 1 < len(all_headers):
                chunk_content = content[end_pos:all_headers[i + 1][3]]
            else:
                chunk_content = content[end_pos:]

            # Clean up
            chunk_content = self._clean_content(chunk_content)

            if len(chunk_content.split()) < self.min_chunk_words:
                continue

            parent_context = f"Module {module_number}: {module_title}"
            if header_type == "subsection":
                parent_context += f" > {current_section}"

            source_tags = self._extract_source_tags(chunk_content)

            chunks.append(TextChunk(
                chunk_id=section_id,
                title=title,
                parent_context=parent_context,
                content=chunk_content,
                module_number=module_number,
                source_tags=source_tags,
            ))

        return chunks

    def _parse_plain_style(self, content: str, module_number: int) -> list[TextChunk]:
        """Parse content with plain text headers like '14.0.1 Title' (Module 14 format)."""
        chunks = []

        # Find section headers: X.X Title
        section_matches = list(self.PATTERNS["plain_section"].finditer(content))
        # Find sub-section headers: X.X.X Title
        subsection_matches = list(self.PATTERNS["plain_subsection"].finditer(content))

        # Combine and sort
        all_headers = []
        for m in section_matches:
            all_headers.append(("section", m.group(1), m.group(2).strip(), m.start(), m.end()))
        for m in subsection_matches:
            all_headers.append(("subsection", m.group(1), m.group(2).strip(), m.start(), m.end()))

        all_headers.sort(key=lambda x: x[3])

        # Build context and extract
        current_section = "Introduction"
        module_title = self._extract_module_title(content, module_number)

        for i, (header_type, section_id, title, start_pos, end_pos) in enumerate(all_headers):
            if header_type == "section":
                current_section = title

            # Get content until next header
            if i + 1 < len(all_headers):
                chunk_content = content[end_pos:all_headers[i + 1][3]]
            else:
                chunk_content = content[end_pos:]

            # Clean up
            chunk_content = self._clean_content(chunk_content)

            if len(chunk_content.split()) < self.min_chunk_words:
                continue

            parent_context = f"Module {module_number}: {module_title}"
            if header_type == "subsection":
                parent_context += f" > {current_section}"

            source_tags = self._extract_source_tags(chunk_content)

            chunks.append(TextChunk(
                chunk_id=section_id,
                title=title,
                parent_context=parent_context,
                content=chunk_content,
                module_number=module_number,
                source_tags=source_tags,
            ))

        return chunks

    def _extract_module_title(self, content: str, module_number: int) -> str:
        """Extract module title from content."""
        # Look for "Module Title:" pattern
        match = re.search(r"\*\*Module Title:\*\*\s*(.+)", content)
        if match:
            return match.group(1).strip()

        # Look for module objective
        match = re.search(rf"Module\s+{module_number}[:\s]+([^\n]+)", content, re.IGNORECASE)
        if match:
            return match.group(1).strip()

        return f"Module {module_number}"

    def _clean_content(self, content: str) -> str:
        """
        Clean up chunk content IN-MEMORY only.

        IMPORTANT: This does NOT modify source files. We keep raw text for
        source_ref traceability, but remove navigation artifacts that would
        confuse the LLM during generation.

        The LLM handles:
        - Broken ASCII tables (fuzzy parsing)
        - CLI typos like "hostnamehostname" (fixes in output, not input)
        - Fragmented text across lines

        We remove:
        - Navigation artifacts ("Scroll to begin", "Click Play")
        - Excessive whitespace
        - Standalone figure caption headers
        """
        # Remove navigation artifacts (in-memory only)
        content = re.sub(r"Scroll to begin\s*", "", content)
        content = re.sub(r"Click Play[^\n]*", "", content)
        content = re.sub(r"Show me\s*Show all\s*Reset\s*", "", content, flags=re.IGNORECASE)

        # Remove empty table placeholders (but keep the surrounding text)
        # These are tables like "| | |\n| --- | --- |\n| | |"
        content = re.sub(
            r"\|\s*\|\s*\|\s*\n\|\s*-+\s*\|\s*-+\s*\|\s*\n(\|\s*\|\s*\|\s*\n?)+",
            "[EMPTY TABLE - No content to extract]\n",
            content
        )

        # Remove excessive whitespace
        content = re.sub(r"\n{3,}", "\n\n", content)

        # Remove standalone hash headers that are just titles for images
        # (These are not real sections, just figure captions like "# Wireless Router")
        content = re.sub(r"^#\s+(?!\d|\*)[^*\n]+$", "", content, flags=re.MULTILINE)

        # Clean up image markdown but preserve the alt text for context
        # ![alt text](url) -> [IMAGE: alt text] or [IMAGE] if no alt text
        def replace_image(match):
            alt_text = match.group(1).strip()
            if alt_text:
                return f"[IMAGE: {alt_text}]"
            return "[IMAGE]"

        content = re.sub(r"!\[([^\]]*)\]\([^)]+\)", replace_image, content)

        return content.strip()

    def _extract_source_tags(self, content: str) -> list[SourceTag]:
        """Extract [source:XXX] tags from content."""
        tags = []
        for match in self.PATTERNS["source_tag"].finditer(content):
            tags.append(SourceTag(
                tag_id=int(match.group(1)),
                position=match.start(),
            ))
        return tags

    def parse_file(self, file_path: str | Path) -> list[TextChunk]:
        """
        Parse a CCNA module file.

        Args:
            file_path: Path to the .txt file

        Returns:
            List of TextChunk objects
        """
        path = Path(file_path)
        content = path.read_text(encoding="utf-8")

        # Try to extract module number from filename
        module_match = re.search(r"Module\s*(\d+)", path.name, re.IGNORECASE)
        module_number = int(module_match.group(1)) if module_match else None

        return self.parse_module(content, module_number)

    def iter_chunks(self, file_path: str | Path) -> Iterator[TextChunk]:
        """
        Iterate over chunks from a file (memory-efficient for large files).

        Args:
            file_path: Path to the .txt file

        Yields:
            TextChunk objects one at a time
        """
        for chunk in self.parse_file(file_path):
            if chunk.is_suitable_for_atoms:
                yield chunk


# =============================================================================
# Chunk Statistics and Analysis
# =============================================================================

@dataclass
class ChunkingStats:
    """Statistics about chunking results."""
    total_chunks: int = 0
    suitable_for_atoms: int = 0
    chunks_by_type: dict = field(default_factory=dict)
    chunks_with_cli: int = 0
    chunks_with_visuals: int = 0
    chunks_with_tables: int = 0
    avg_word_count: float = 0.0
    min_word_count: int = 0
    max_word_count: int = 0


def analyze_chunks(chunks: list[TextChunk]) -> ChunkingStats:
    """Analyze a list of chunks and return statistics."""
    if not chunks:
        return ChunkingStats()

    word_counts = [c.word_count for c in chunks]

    stats = ChunkingStats(
        total_chunks=len(chunks),
        suitable_for_atoms=sum(1 for c in chunks if c.is_suitable_for_atoms),
        chunks_by_type={},
        chunks_with_cli=sum(1 for c in chunks if c.has_cli_commands),
        chunks_with_visuals=sum(1 for c in chunks if c.has_visuals),
        chunks_with_tables=sum(1 for c in chunks if c.has_tables),
        avg_word_count=sum(word_counts) / len(word_counts),
        min_word_count=min(word_counts),
        max_word_count=max(word_counts),
    )

    # Count by type
    for chunk in chunks:
        chunk_type = chunk.chunk_type.value
        stats.chunks_by_type[chunk_type] = stats.chunks_by_type.get(chunk_type, 0) + 1

    return stats


# =============================================================================
# Example Usage and Tests
# =============================================================================

if __name__ == "__main__":
    import sys
    from pathlib import Path

    print("\n=== CCNA Chunker Test ===\n")

    # Test with sample content (Module 1 style)
    sample_md_style = """
# CCNA: Introduction to Networks — Module 1

**Module Title:** Introduction to Networking

## 1.2 Network Components

This section covers the basic components of networks.

### 1.2.1 Host Roles

All computers that are connected to a network and participate directly in network
communication are classified as **hosts**. Hosts can be called end devices. Some hosts
are also called clients. However, the term hosts specifically refers to devices on the
network that are assigned a number for communication purposes. This number is called
the **Internet Protocol (IP) address**.

### 1.2.2 Peer-to-Peer

Client and server software usually run on separate computers, but it is also possible
for one computer to be used for both roles at the same time. This type of network is
called a **peer-to-peer network**.

| Advantages | Disadvantages |
| --- | --- |
| Easy to set up | No centralized administration |
| Less complex | Not as secure |

## 1.3 Network Types

Networks come in many sizes and configurations.

### 1.3.1 LANs and WANs

The two most common types of network infrastructures are Local Area Networks (LANs)
and Wide Area Networks (WANs).
"""

    # Test with sample content (Module 10 style)
    sample_hash_style = """
# 10.0 Introduction

**Module Title:** Basic Router Configuration

# 10.1 Configure Initial Router Settings

Scroll to begin

# **10.1.1 Basic Router Configuration Steps**

The following tasks should be completed when configuring initial settings on a router.

1. Configure the device name.

```
Router(config)#hostname hostname
```

2. Secure privileged EXEC mode.

```
Router(config)#enable secret password
```

# **10.1.2 Basic Router Configuration Example**

In this example, router R1 in the topology diagram will be configured with initial settings.

The figure shows a network topology diagram with two PCs, two switches, two routers.

To configure the device name for R1, use the following commands.

`Router> enable`
`Router# configure terminal`
"""

    chunker = CCNAChunker(min_chunk_words=30)

    print("Testing Markdown-style content (Module 1):")
    print("-" * 50)
    md_chunks = chunker.parse_module(sample_md_style, module_number=1)
    for chunk in md_chunks:
        print(f"\n[{chunk.chunk_id}] {chunk.title}")
        print(f"  Type: {chunk.chunk_type.value}")
        print(f"  Words: {chunk.word_count}")
        print(f"  Has CLI: {chunk.has_cli_commands}, Has Tables: {chunk.has_tables}")
        print(f"  Context: {chunk.parent_context}")

    print("\n" + "=" * 50)
    print("\nTesting Hash-bold-style content (Module 10):")
    print("-" * 50)
    hash_chunks = chunker.parse_module(sample_hash_style, module_number=10)
    for chunk in hash_chunks:
        print(f"\n[{chunk.chunk_id}] {chunk.title}")
        print(f"  Type: {chunk.chunk_type.value}")
        print(f"  Words: {chunk.word_count}")
        print(f"  Has CLI: {chunk.has_cli_commands}, Has Visuals: {chunk.has_visuals}")
        print(f"  Context: {chunk.parent_context}")

    # Test with real file if available
    ccna_dir = Path("docs/CCNA")
    if ccna_dir.exists():
        print("\n" + "=" * 50)
        print("\nTesting with real CCNA Module files:")
        print("-" * 50)

        for module_file in sorted(ccna_dir.glob("*.txt"))[:2]:  # Test first 2
            print(f"\nParsing: {module_file.name}")
            chunks = chunker.parse_file(module_file)
            stats = analyze_chunks(chunks)

            print(f"  Total chunks: {stats.total_chunks}")
            print(f"  Suitable for atoms: {stats.suitable_for_atoms}")
            print(f"  Chunk types: {stats.chunks_by_type}")
            print(f"  Avg words/chunk: {stats.avg_word_count:.0f}")
            print(f"  With CLI commands: {stats.chunks_with_cli}")
            print(f"  With visuals: {stats.chunks_with_visuals}")
