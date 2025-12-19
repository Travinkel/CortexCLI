"""
Robust Learning Atom Generator.

Implements a multi-stage generation pipeline:
1. Structured extraction from source content (pre-LLM)
2. LLM generation with quality-focused prompts
3. Post-generation validation and filtering
4. Regeneration for failed atoms

Key improvements:
- Extracts structure BEFORE LLM call (reduces hallucination)
- Type-specific prompts with negative examples
- Multiple validation passes
- Automatic retry for fixable issues
"""

from __future__ import annotations

import json
import re
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

from loguru import logger

from config import get_settings

from .enhanced_quality_validator import (
    EnhancedQualityValidator,
    EnhancedValidationResult,
)
from .prompts import (
    get_prompt,
    get_system_prompt,
    get_types_for_section,
)


class GenerationStatus(str, Enum):
    """Status of atom generation."""

    SUCCESS = "success"
    FAILED = "failed"
    FILTERED = "filtered"  # Rejected by quality filter
    RETRY = "retry"  # Can be fixed by regeneration


@dataclass
class ExtractedContent:
    """Structured content extracted from source before LLM generation."""

    section_id: str
    title: str
    raw_text: str

    # Extracted elements
    key_terms: list[dict] = field(default_factory=list)  # [{term, definition}]
    cli_commands: list[dict] = field(default_factory=list)  # [{command, mode, purpose}]
    tables: list[dict] = field(default_factory=list)  # [{headers, rows}]
    concepts: list[str] = field(default_factory=list)  # Main concepts mentioned
    facts: list[str] = field(default_factory=list)  # Extractable facts

    # Metadata
    word_count: int = 0
    has_procedures: bool = False


@dataclass
class GeneratedAtom:
    """A generated learning atom."""

    id: str
    card_id: str
    atom_type: str
    front: str
    back: str
    section_id: str

    # Type-specific content
    content_json: dict | None = None

    # Quality metrics
    quality_score: float = 100.0
    quality_grade: str = "A"
    validation_result: EnhancedValidationResult | None = None

    # Metadata
    tags: list[str] = field(default_factory=list)
    knowledge_type: str = "factual"
    generated_at: datetime = field(default_factory=datetime.now)
    generation_attempt: int = 1
    status: GenerationStatus = GenerationStatus.SUCCESS


@dataclass
class GenerationResult:
    """Result of generating atoms for a section."""

    section_id: str
    atoms: list[GeneratedAtom] = field(default_factory=list)
    filtered_atoms: list[GeneratedAtom] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    # Statistics
    total_generated: int = 0
    total_passed: int = 0
    total_filtered: int = 0
    by_type: dict = field(default_factory=dict)


class RobustAtomGenerator:
    """
    Multi-stage learning atom generator with quality focus.

    Pipeline:
    1. Extract structured content from source
    2. Determine atom types based on content
    3. Generate atoms with type-specific prompts
    4. Validate and filter generated atoms
    5. Retry failed atoms (up to max attempts)
    """

    MAX_REGENERATION_ATTEMPTS = 3
    MAX_CONTENT_LENGTH = 8000  # Gemini context limit

    def __init__(
        self,
        api_key: str | None = None,
        model_name: str | None = None,
        strict_validation: bool = False,
    ):
        """
        Initialize the generator.

        Args:
            api_key: Gemini API key (uses settings if not provided)
            model_name: Model to use (uses settings if not provided)
            strict_validation: Apply stricter quality thresholds
        """
        settings = get_settings()
        self.api_key = api_key or settings.gemini_api_key
        self.model_name = model_name or settings.ai_model

        if not self.api_key:
            raise ValueError("Gemini API key required")

        # Initialize LLM client
        self._client = None

        # Initialize validator
        self.validator = EnhancedQualityValidator(
            use_perplexity=True,
            use_grammar=True,
            strict_mode=strict_validation,
        )

        # Compile extraction patterns
        self._compile_patterns()

    def _compile_patterns(self):
        """Compile regex patterns for content extraction."""
        # Key term patterns (bold text with definition)
        self.term_pattern = re.compile(
            r"\*\*([^*]+)\*\*\s*[-—:]\s*([^.]+\.)",
            re.IGNORECASE,
        )

        # CLI command patterns
        self.cli_patterns = [
            re.compile(r"Router[>#]\s*(.+)$", re.MULTILINE),
            re.compile(r"Switch[>#]\s*(.+)$", re.MULTILINE),
            re.compile(r"Router\(config[^)]*\)#\s*(.+)$", re.MULTILINE),
            re.compile(r"Switch\(config[^)]*\)#\s*(.+)$", re.MULTILINE),
        ]

        # Table pattern (markdown tables)
        self.table_pattern = re.compile(
            r"\|(.+)\|\n\|[-| ]+\|\n((?:\|.+\|\n?)+)",
            re.MULTILINE,
        )

        # Section header pattern
        self.section_pattern = re.compile(
            r"^(?:#{1,4}\s*)?(\d+\.\d+(?:\.\d+)?)\s+(.+?)$",
            re.MULTILINE,
        )

    @property
    def client(self):
        """Lazy-load Gemini client."""
        if self._client is None:
            import google.generativeai as genai

            genai.configure(api_key=self.api_key)
            self._client = genai.GenerativeModel(
                model_name=self.model_name,
                system_instruction=get_system_prompt(),
            )
        return self._client

    # =========================================================================
    # Stage 1: Content Extraction
    # =========================================================================

    def extract_content(
        self,
        section_id: str,
        title: str,
        raw_text: str,
    ) -> ExtractedContent:
        """
        Extract structured content from raw source text.

        This pre-processing step:
        - Identifies key terms and definitions
        - Extracts CLI commands with modes
        - Parses tables for matching exercises
        - Identifies main concepts
        - Extracts atomic facts

        Returns:
            ExtractedContent with structured data
        """
        content = ExtractedContent(
            section_id=section_id,
            title=title,
            raw_text=raw_text,
            word_count=len(raw_text.split()),
        )

        # Extract key terms (bold with definitions)
        for match in self.term_pattern.finditer(raw_text):
            term = match.group(1).strip()
            definition = match.group(2).strip()
            content.key_terms.append(
                {
                    "term": term,
                    "definition": definition,
                }
            )

        # Extract CLI commands
        for pattern in self.cli_patterns:
            for match in pattern.finditer(raw_text):
                cmd = match.group(1).strip()
                # Determine mode from context
                mode = self._detect_cli_mode(match.group(0))
                content.cli_commands.append(
                    {
                        "command": cmd,
                        "mode": mode,
                        "context": raw_text[max(0, match.start() - 50) : match.end() + 50],
                    }
                )

        # Extract tables
        for match in self.table_pattern.finditer(raw_text):
            headers = [h.strip() for h in match.group(1).split("|") if h.strip()]
            rows = []
            for row in match.group(2).strip().split("\n"):
                cells = [c.strip() for c in row.split("|") if c.strip()]
                if cells:
                    rows.append(cells)
            if headers and rows:
                content.tables.append(
                    {
                        "headers": headers,
                        "rows": rows,
                    }
                )

        # Extract concepts (capitalized terms, networking keywords)
        concept_pattern = re.compile(
            r"\b(OSPF|EIGRP|BGP|VLAN|STP|DHCP|DNS|NAT|ACL|TCP|UDP|IP|"
            r"Router|Switch|Gateway|Subnet|Protocol|Layer\s+\d|"
            r"Ethernet|Frame|Packet|Port|Interface)\b",
            re.IGNORECASE,
        )
        concepts = set()
        for match in concept_pattern.finditer(raw_text):
            concepts.add(match.group(1).upper())
        content.concepts = list(concepts)[:20]  # Limit to top 20

        # Check for procedural content
        content.has_procedures = bool(content.cli_commands) or bool(
            re.search(r"step\s+\d|first.*then|configure.*by", raw_text, re.IGNORECASE)
        )

        return content

    def _detect_cli_mode(self, command_line: str) -> str:
        """Detect CLI mode from command prompt."""
        if "(config-if)" in command_line:
            return "interface"
        elif "(config-router)" in command_line:
            return "router"
        elif "(config-line)" in command_line:
            return "line"
        elif "(config)" in command_line:
            return "global"
        elif "#" in command_line and ">" not in command_line:
            return "privileged"
        else:
            return "user"

    # =========================================================================
    # Stage 2: Atom Generation
    # =========================================================================

    async def generate_for_section(
        self,
        section_id: str,
        title: str,
        content: str,
        target_types: list[str] | None = None,
    ) -> GenerationResult:
        """
        Generate learning atoms for a section.

        Args:
            section_id: Section identifier (e.g., "1.2.3")
            title: Section title
            content: Raw section content
            target_types: Specific types to generate (auto-detect if None)

        Returns:
            GenerationResult with atoms and statistics
        """
        result = GenerationResult(section_id=section_id)

        # Stage 1: Extract structured content
        extracted = self.extract_content(section_id, title, content)

        # Stage 2: Determine atom types
        if target_types is None:
            target_types = get_types_for_section(
                has_commands=bool(extracted.cli_commands),
                has_key_terms=bool(extracted.key_terms),
                has_tables=bool(extracted.tables),
                concept_count=len(extracted.concepts),
            )

        logger.info(f"Generating {target_types} for section {section_id}")

        # Stage 3: Generate each type
        for atom_type in target_types:
            try:
                atoms = await self._generate_type(
                    atom_type=atom_type,
                    extracted=extracted,
                )
                result.total_generated += len(atoms)

                # Stage 4: Validate and filter
                for atom in atoms:
                    validation = self.validator.validate(
                        front=atom.front,
                        back=atom.back,
                        atom_type=atom.atom_type,
                        content_json=atom.content_json,
                        source_content=extracted.raw_text,
                    )

                    atom.validation_result = validation
                    atom.quality_score = validation.score
                    atom.quality_grade = self._score_to_grade(validation.score)

                    if validation.is_valid:
                        atom.status = GenerationStatus.SUCCESS
                        result.atoms.append(atom)
                        result.total_passed += 1
                    elif (
                        validation.can_be_fixed
                        and atom.generation_attempt < self.MAX_REGENERATION_ATTEMPTS
                    ):
                        # Stage 5: Retry
                        atom.status = GenerationStatus.RETRY
                        retry_atom = await self._retry_generation(atom, extracted)
                        if retry_atom:
                            result.atoms.append(retry_atom)
                            result.total_passed += 1
                        else:
                            result.filtered_atoms.append(atom)
                            result.total_filtered += 1
                    else:
                        atom.status = GenerationStatus.FILTERED
                        result.filtered_atoms.append(atom)
                        result.total_filtered += 1

                # Track by type
                result.by_type[atom_type] = len(
                    [a for a in result.atoms if a.atom_type == atom_type]
                )

            except Exception as e:
                error_msg = f"Error generating {atom_type} for {section_id}: {e}"
                logger.error(error_msg)
                result.errors.append(error_msg)

        return result

    async def _generate_type(
        self,
        atom_type: str,
        extracted: ExtractedContent,
    ) -> list[GeneratedAtom]:
        """Generate atoms of a specific type."""
        # Prepare content for prompt
        if atom_type == "parsons" and extracted.cli_commands:
            # Focus on commands for Parsons
            content = self._format_commands_for_prompt(extracted)
        elif atom_type == "cloze" and extracted.key_terms:
            # Focus on key terms for cloze
            content = self._format_terms_for_prompt(extracted)
        elif atom_type == "matching" and extracted.tables:
            # Focus on tables for matching
            content = self._format_tables_for_prompt(extracted)
        else:
            # Use full content
            content = extracted.raw_text

        # Truncate if needed
        if len(content) > self.MAX_CONTENT_LENGTH:
            content = content[: self.MAX_CONTENT_LENGTH] + "..."

        # Get prompt
        prompt = get_prompt(
            atom_type=atom_type,
            section_id=extracted.section_id,
            content=content,
            include_negative_examples=True,
        )

        # Call LLM
        response = await self._call_llm(prompt)
        if not response:
            return []

        # Parse response
        atoms = self._parse_response(
            response=response,
            atom_type=atom_type,
            section_id=extracted.section_id,
        )

        return atoms

    def _format_commands_for_prompt(self, extracted: ExtractedContent) -> str:
        """Format CLI commands for Parsons prompt."""
        lines = ["CLI COMMANDS:"]
        for cmd in extracted.cli_commands:
            mode = cmd.get("mode", "")
            command = cmd.get("command", "")
            lines.append(f"  [{mode}] {command}")

        lines.append("\nCONTEXT:")
        lines.append(extracted.raw_text[:2000])
        return "\n".join(lines)

    def _format_terms_for_prompt(self, extracted: ExtractedContent) -> str:
        """Format key terms for cloze prompt."""
        lines = ["KEY TERMS:"]
        for term in extracted.key_terms:
            lines.append(f"  - {term['term']}: {term['definition']}")

        lines.append("\nCONTEXT:")
        lines.append(extracted.raw_text[:2000])
        return "\n".join(lines)

    def _format_tables_for_prompt(self, extracted: ExtractedContent) -> str:
        """Format tables for matching prompt."""
        lines = ["TABLES:"]
        for table in extracted.tables:
            lines.append(f"Headers: {table['headers']}")
            for row in table["rows"][:6]:  # Max 6 rows
                lines.append(f"  {row}")
            lines.append("")

        lines.append("CONTEXT:")
        lines.append(extracted.raw_text[:2000])
        return "\n".join(lines)

    async def _call_llm(self, prompt: str) -> str | None:
        """Call Gemini API."""
        try:
            response = self.client.generate_content(
                prompt,
                generation_config={
                    "temperature": 0.3,
                    "top_p": 0.8,
                    "max_output_tokens": 4096,
                },
            )

            if response.text:
                return response.text

            logger.warning("Empty response from Gemini")
            return None

        except Exception as e:
            logger.error(f"Gemini API error: {e}")
            return None

    def _parse_response(
        self,
        response: str,
        atom_type: str,
        section_id: str,
    ) -> list[GeneratedAtom]:
        """Parse LLM response into GeneratedAtom objects."""
        atoms = []

        # Extract JSON
        json_match = re.search(r"\[[\s\S]*\]", response)
        if not json_match:
            # Try extracting from code block
            code_match = re.search(r"```(?:json)?\s*([\s\S]*?)```", response)
            if code_match:
                json_str = code_match.group(1).strip()
            else:
                logger.warning(f"No JSON found in response for {section_id}")
                return atoms
        else:
            json_str = json_match.group(0)

        try:
            data = json.loads(json_str)
            if not isinstance(data, list):
                data = [data]
        except json.JSONDecodeError as e:
            logger.error(f"JSON parse error for {section_id}: {e}")
            return atoms

        # Convert to atoms
        for i, item in enumerate(data):
            atom = self._item_to_atom(item, atom_type, section_id, i)
            if atom:
                atoms.append(atom)

        return atoms

    def _item_to_atom(
        self,
        item: dict,
        atom_type: str,
        section_id: str,
        index: int,
    ) -> GeneratedAtom | None:
        """Convert parsed item to GeneratedAtom."""
        try:
            # Get card_id
            card_id = item.get("card_id", f"{section_id}-{atom_type[:2].upper()}-{index + 1:03d}")

            # Handle different structures
            if atom_type == "mcq":
                front = item.get("front", item.get("stem", ""))
                back = item.get("correct_answer", "")
                content_json = {
                    "options": [back] + item.get("distractors", []),
                    "correct_index": 0,
                    "explanation": item.get("explanation", ""),
                }
            elif atom_type == "true_false":
                front = item.get("front", "")
                back = "True" if item.get("correct", True) else "False"
                content_json = {
                    "correct": item.get("correct", True),
                    "explanation": item.get("explanation", ""),
                }
            elif atom_type == "parsons":
                front = item.get("scenario", "")
                sequence = item.get("correct_sequence", [])
                back = " → ".join(sequence)
                content_json = {
                    "blocks": sequence,
                    "distractors": item.get("distractors", []),
                    "starting_mode": item.get("starting_mode", "user EXEC"),
                }
            elif atom_type == "matching":
                front = item.get("front", "Match the following:")
                pairs = item.get("pairs", [])
                back = "\n".join([f"{p.get('left', '')} → {p.get('right', '')}" for p in pairs])
                content_json = {"pairs": pairs}
            else:
                # Flashcard/cloze
                front = item.get("front", "")
                back = item.get("back", "")
                content_json = None

            # Basic validation
            if not front or (not back and atom_type not in ["mcq", "true_false"]):
                return None

            return GeneratedAtom(
                id=str(uuid.uuid4()),
                card_id=card_id,
                atom_type=atom_type,
                front=front,
                back=back,
                section_id=section_id,
                content_json=content_json,
                tags=item.get("tags", []),
                knowledge_type=item.get("knowledge_type", "factual"),
            )

        except Exception as e:
            logger.error(f"Error converting item to atom: {e}")
            return None

    async def _retry_generation(
        self,
        failed_atom: GeneratedAtom,
        extracted: ExtractedContent,
    ) -> GeneratedAtom | None:
        """Retry generation for a failed atom."""
        failed_atom.generation_attempt += 1

        # Create focused prompt for retry
        issues = []
        if failed_atom.validation_result:
            issues = [i.message for i in failed_atom.validation_result.issues]

        retry_prompt = f"""The previous generation had these issues:
{chr(10).join(f"- {i}" for i in issues)}

Please regenerate a single {failed_atom.atom_type} that fixes these issues.

Original question: {failed_atom.front}
Original answer: {failed_atom.back}

REQUIREMENTS:
1. Fix ALL identified issues
2. Ensure answer is COMPLETE (ends with punctuation)
3. Ensure answer is at least 10 words
4. Ensure question is grammatically correct

Return a single JSON object (not array):
{{"front": "...", "back": "...", "knowledge_type": "..."}}

Source content for reference:
{extracted.raw_text[:1000]}"""

        response = await self._call_llm(retry_prompt)
        if not response:
            return None

        # Parse single object
        try:
            json_match = re.search(r"\{[\s\S]*\}", response)
            if json_match:
                item = json.loads(json_match.group(0))
                atom = self._item_to_atom(
                    item,
                    failed_atom.atom_type,
                    failed_atom.section_id,
                    0,
                )

                if atom:
                    # Validate retry
                    validation = self.validator.validate(
                        front=atom.front,
                        back=atom.back,
                        atom_type=atom.atom_type,
                        content_json=atom.content_json,
                    )

                    if validation.is_valid:
                        atom.generation_attempt = failed_atom.generation_attempt
                        return atom

        except Exception as e:
            logger.debug(f"Retry parse error: {e}")

        return None

    def _score_to_grade(self, score: float) -> str:
        """Convert score to letter grade."""
        if score >= 90:
            return "A"
        elif score >= 75:
            return "B"
        elif score >= 60:
            return "C"
        elif score >= 40:
            return "D"
        return "F"


# =============================================================================
# Convenience Functions
# =============================================================================


async def generate_atoms(
    section_id: str,
    title: str,
    content: str,
    types: list[str] | None = None,
) -> GenerationResult:
    """Convenience function to generate atoms."""
    generator = RobustAtomGenerator()
    return await generator.generate_for_section(
        section_id=section_id,
        title=title,
        content=content,
        target_types=types,
    )


# =============================================================================
# CLI Entry Point
# =============================================================================

if __name__ == "__main__":
    import asyncio

    # Test content
    test_content = """
    ## 1.5.3 Business Internet Connections

    **Dedicated Leased Line** — Leased lines are reserved circuits within the service provider's network that connect geographically separated offices for private voice and/or data networking. The circuits are rented at a monthly or yearly rate.

    **Metro Ethernet** — This is sometimes known as Ethernet WAN. Metro ethernets extend LAN access technology into the WAN. Ethernet is a LAN technology.

    **Business DSL** — Business DSL is available in various formats. A popular choice is Symmetric Digital Subscriber Line (SDSL) which is similar to the consumer version of DSL but provides uploads and downloads at the same high speeds.
    """

    async def test():
        generator = RobustAtomGenerator()
        result = await generator.generate_for_section(
            section_id="1.5.3",
            title="Business Internet Connections",
            content=test_content,
            target_types=["flashcard", "mcq"],
        )

        print("\n=== Generation Results ===")
        print(f"Generated: {result.total_generated}")
        print(f"Passed: {result.total_passed}")
        print(f"Filtered: {result.total_filtered}")
        print(f"By type: {result.by_type}")

        print("\n=== Generated Atoms ===")
        for atom in result.atoms:
            print(f"\n[{atom.atom_type}] {atom.card_id}")
            print(f"  Q: {atom.front[:80]}...")
            print(f"  A: {atom.back[:80]}...")
            print(f"  Score: {atom.quality_score:.0f} ({atom.quality_grade})")

        if result.filtered_atoms:
            print("\n=== Filtered Atoms ===")
            for atom in result.filtered_atoms[:3]:
                print(f"\n[FILTERED] {atom.front[:50]}...")
                if atom.validation_result:
                    for issue in atom.validation_result.issues:
                        print(f"  - {issue.message}")

    asyncio.run(test())
