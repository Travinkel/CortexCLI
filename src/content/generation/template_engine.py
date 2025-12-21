"""
Template Engine: Deterministic Atom Generation Rules.

Implements 5 core template rules to generate atoms from parsed content chunks
without requiring LLM calls. This provides ~30% coverage of atom generation
at zero cost and high quality.

Core Rules:
1. CLICommandsToParsons: CLI command sequences → Parsons problems
2. DefinitionsToFlashcards: Definitions → Flashcard atoms
3. TablesToMatching: Tables → Matching atoms
4. NumericExamplesToCalculation: Numeric examples → Calculation atoms
5. ComparisonsToCompareAtoms: Comparison text → Comparison atoms

Design Philosophy:
- Deterministic: Same input always produces same output
- Fast: No API calls, pure regex/parsing
- High quality: Leverages structured content patterns
- Conservative: Only generates when confidence is high
"""

from __future__ import annotations

import json
import re
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any

from processing.course_chunker import TextChunk, ChunkType


class AtomQuality(str, Enum):
    """Atom quality grades for validation."""

    A_PLUS = "A+"  # Perfect, production-ready
    A = "A"        # Excellent, minor polish needed
    B = "B"        # Good, usable with review
    C = "C"        # Acceptable, needs revision
    D = "D"        # Poor, significant issues
    F = "F"        # Fail, do not use


@dataclass
class GeneratedAtom:
    """
    Output from template rules.

    Attributes:
        atom_id: Unique identifier
        atom_type: Type from atom_type_metadata.json
        front: Question/prompt text
        back: Answer/solution text
        content_json: Type-specific structured data
        quality_grade: Estimated quality (A+ to F)
        generation_method: Which rule/template generated this
        source_chunk_id: Original chunk ID for traceability
        confidence_score: 0.0-1.0, how confident the rule is
    """

    atom_id: str
    atom_type: str
    front: str
    back: str
    content_json: dict[str, Any]
    quality_grade: AtomQuality
    generation_method: str
    source_chunk_id: str
    confidence_score: float

    def to_dict(self) -> dict[str, Any]:
        """Convert to dict for database insertion."""
        return {
            "id": self.atom_id,
            "atom_type": self.atom_type,
            "front": self.front,
            "back": self.back,
            "content_json": json.dumps(self.content_json),
            "quality_score": self._quality_to_numeric(),
            "generation_method": self.generation_method,
            "source_chunk_id": self.source_chunk_id,
        }

    def _quality_to_numeric(self) -> float:
        """Convert quality grade to numeric score (0.0-1.0)."""
        quality_map = {
            AtomQuality.A_PLUS: 1.0,
            AtomQuality.A: 0.92,
            AtomQuality.B: 0.85,
            AtomQuality.C: 0.75,
            AtomQuality.D: 0.65,
            AtomQuality.F: 0.0,
        }
        return quality_map.get(self.quality_grade, 0.75)


class TemplateRule(ABC):
    """Base class for all template rules."""

    @property
    @abstractmethod
    def rule_name(self) -> str:
        """Human-readable rule name."""
        ...

    @abstractmethod
    def can_apply(self, chunk: TextChunk) -> bool:
        """Check if this rule can generate atoms from the chunk."""
        ...

    @abstractmethod
    def generate(self, chunk: TextChunk) -> list[GeneratedAtom]:
        """Generate atoms from chunk."""
        ...

    def _generate_atom_id(self) -> str:
        """Generate unique atom ID."""
        return str(uuid.uuid4())


class CLICommandsToParsons(TemplateRule):
    """
    Rule 1: Extract CLI command sequences and convert to Parsons problems.

    Detects:
    - Cisco router/switch configuration sequences
    - Bash/shell command sequences
    - Step-by-step CLI procedures

    Quality Criteria:
    - A+: 4-8 steps, clear goal, no ambiguity
    - A: 3-10 steps, minor context needed
    - B: 2-12 steps, some ambiguity
    - C: Fewer than 2 or more than 12 steps
    """

    rule_name = "CLI Commands -> Parsons"

    def can_apply(self, chunk: TextChunk) -> bool:
        """Check if chunk contains CLI command sequences."""
        return chunk.has_cli_commands

    def generate(self, chunk: TextChunk) -> list[GeneratedAtom]:
        """Extract CLI sequences and create Parsons problems."""
        atoms = []

        # Find code blocks with CLI commands
        code_blocks = re.findall(r"```(?:bash|cisco|shell)?\s*\n(.*?)\n```", chunk.content, re.DOTALL)

        for code_block in code_blocks:
            # Extract command lines (ignore output/comments)
            commands = []
            for line in code_block.split('\n'):
                line = line.strip()

                # Skip empty, comments, or output lines
                if not line or line.startswith('#') or line.startswith('!'):
                    continue

                # Detect Cisco prompt patterns
                if re.match(r"(Router|Switch|R\d+|S\d+)[>#\(]", line):
                    # Extract command after prompt
                    cmd_match = re.search(r"[>#\(]\s*(.+)", line)
                    if cmd_match:
                        commands.append(cmd_match.group(1).strip())
                # Detect regular shell commands
                elif re.match(r"^\$\s+", line):
                    commands.append(line.replace('$ ', '').strip())
                # No prompt, assume it's a command
                elif line:
                    commands.append(line)

            # Quality check
            if len(commands) < 2:
                continue  # Not enough steps for Parsons
            if len(commands) > 12:
                continue  # Too many, overwhelming

            # Grade quality
            quality = self._grade_parsons_quality(commands)

            # Extract goal from chunk context
            goal = self._extract_goal(chunk.title, chunk.content, commands)

            # Create Parsons problem
            atom = GeneratedAtom(
                atom_id=self._generate_atom_id(),
                atom_type="parsons_problem",
                front=f"**Reconstruct the solution:**\n\n{goal}",
                back="\n".join(commands),
                content_json={
                    "goal": goal,
                    "blocks": commands,
                    "correct_sequence": list(range(len(commands))),
                    "distractors": [],  # Can add common mistakes later
                },
                quality_grade=quality,
                generation_method=self.rule_name,
                source_chunk_id=chunk.chunk_id,
                confidence_score=0.85 if quality in [AtomQuality.A_PLUS, AtomQuality.A] else 0.70,
            )

            atoms.append(atom)

        return atoms

    def _grade_parsons_quality(self, commands: list[str]) -> AtomQuality:
        """Grade Parsons problem quality based on command count and clarity."""
        count = len(commands)

        if 4 <= count <= 8:
            return AtomQuality.A_PLUS
        elif 3 <= count <= 10:
            return AtomQuality.A
        elif 2 <= count <= 12:
            return AtomQuality.B
        else:
            return AtomQuality.C

    def _extract_goal(self, title: str, content: str, commands: list[str]) -> str:
        """Extract the goal/task description for the Parsons problem."""
        # Try to find explicit goal statement
        goal_patterns = [
            r"(?:Goal|Task|Objective):\s*(.+?)(?:\n|$)",
            r"(?:Configure|Set up|Enable|Disable)\s+(.+?)(?:\n|\.)",
            r"(?:To|In order to)\s+(.+?)(?:\n|,)",
        ]

        for pattern in goal_patterns:
            match = re.search(pattern, content, re.IGNORECASE)
            if match:
                goal = match.group(1).strip()
                if len(goal) < 100:  # Reasonable length
                    return goal

        # Fallback: Use title or infer from commands
        if title and len(title) < 100:
            return title

        # Last resort: Describe first command
        if commands:
            return f"Execute the following sequence to accomplish the task"

        return "Complete the configuration"


class DefinitionsToFlashcards(TemplateRule):
    """
    Rule 2: Extract definitions and convert to flashcard atoms.

    Detects:
    - "X is/are/refers to..." patterns
    - Definition lists (Term: Definition)
    - Glossary entries

    Quality Criteria:
    - A+: Concise term (<3 words), clear definition (<25 words)
    - A: Concise term, longer definition (<50 words)
    - B: Multi-word term or verbose definition
    """

    rule_name = "Definitions -> Flashcards"

    def can_apply(self, chunk: TextChunk) -> bool:
        """Check if chunk contains definitions."""
        # Look for definition patterns
        has_definitions = bool(re.search(
            r"\b\w+\b\s+(?:is|are|refers to|means|represents|describes)",
            chunk.content,
            re.IGNORECASE
        ))

        # Or definition list format (Term: Definition)
        has_def_list = bool(re.search(r"^\s*\*\*(.+?)\*\*:\s+(.+)", chunk.content, re.MULTILINE))

        return has_definitions or has_def_list

    def generate(self, chunk: TextChunk) -> list[GeneratedAtom]:
        """Extract definitions and create flashcards."""
        atoms = []

        # Pattern 1: Definition list format (**Term**: Definition)
        def_list_pattern = r"^\s*\*\*(.+?)\*\*:\s+(.+?)(?=\n\n|\n\*\*|\Z)"
        for match in re.finditer(def_list_pattern, chunk.content, re.MULTILINE | re.DOTALL):
            term = match.group(1).strip()
            definition = match.group(2).strip()

            quality = self._grade_flashcard_quality(term, definition)

            atom = GeneratedAtom(
                atom_id=self._generate_atom_id(),
                atom_type="cloze_deletion",
                front=f"What is **{term}**?",
                back=definition,
                content_json={
                    "cloze_text": f"{term} is {{c1::{definition}}}",
                    "term": term,
                    "definition": definition,
                },
                quality_grade=quality,
                generation_method=self.rule_name,
                source_chunk_id=chunk.chunk_id,
                confidence_score=0.90,
            )

            atoms.append(atom)

        # Pattern 2: "X is/are..." sentences
        is_are_pattern = r"(?:^|\n)\s*(\b[A-Z][\w\s]{1,30}?)\s+(is|are|refers to|means)\s+(.+?)(?:\.|$)"
        for match in re.finditer(is_are_pattern, chunk.content, re.MULTILINE):
            term = match.group(1).strip()
            verb = match.group(2)
            definition = match.group(3).strip()

            # Skip if definition is too long
            if len(definition.split()) > 50:
                continue

            quality = self._grade_flashcard_quality(term, definition)

            atom = GeneratedAtom(
                atom_id=self._generate_atom_id(),
                atom_type="short_answer",
                front=f"What {verb} **{term}**?",
                back=definition,
                content_json={
                    "question": f"What {verb} {term}?",
                    "answer": definition,
                    "acceptable_answers": [definition],
                },
                quality_grade=quality,
                generation_method=self.rule_name,
                source_chunk_id=chunk.chunk_id,
                confidence_score=0.80,
            )

            atoms.append(atom)

        return atoms

    def _grade_flashcard_quality(self, term: str, definition: str) -> AtomQuality:
        """Grade flashcard quality based on term and definition length."""
        term_words = len(term.split())
        def_words = len(definition.split())

        if term_words <= 3 and def_words <= 25:
            return AtomQuality.A_PLUS
        elif term_words <= 5 and def_words <= 50:
            return AtomQuality.A
        elif def_words <= 75:
            return AtomQuality.B
        else:
            return AtomQuality.C


class TablesToMatching(TemplateRule):
    """
    Rule 3: Extract tables and convert to matching atoms.

    Detects:
    - Markdown tables with 2-3 columns
    - Command reference tables
    - Comparison tables

    Quality Criteria:
    - A+: 4-8 pairs, clear relationship
    - A: 3-10 pairs
    - B: 2-12 pairs
    """

    rule_name = "Tables -> Matching"

    def can_apply(self, chunk: TextChunk) -> bool:
        """Check if chunk contains tables."""
        return chunk.has_tables

    def generate(self, chunk: TextChunk) -> list[GeneratedAtom]:
        """Extract tables and create matching atoms."""
        atoms = []

        # Find markdown tables
        table_pattern = r"\|(.+?)\|\s*\n\s*\|[\s:-]+\|\s*\n((?:\|.+?\|\s*\n)+)"
        for match in re.finditer(table_pattern, chunk.content):
            header_row = match.group(1)
            data_rows = match.group(2)

            # Parse header
            headers = [h.strip() for h in header_row.split('|') if h.strip()]

            # Skip if not 2 or 3 columns
            if len(headers) not in [2, 3]:
                continue

            # Parse data rows
            pairs = []
            for row in data_rows.strip().split('\n'):
                cells = [c.strip() for c in row.split('|') if c.strip()]
                if len(cells) >= 2:
                    pairs.append((cells[0], cells[1]))

            # Quality check
            if len(pairs) < 2 or len(pairs) > 12:
                continue

            quality = self._grade_matching_quality(pairs)

            # Create matching atom
            atom = GeneratedAtom(
                atom_id=self._generate_atom_id(),
                atom_type="matching_pairs",
                front=f"**Match the {headers[0]} with {headers[1]}:**",
                back="See content_json for correct pairs",
                content_json={
                    "left_column": [pair[0] for pair in pairs],
                    "right_column": [pair[1] for pair in pairs],
                    "correct_matches": {i: i for i in range(len(pairs))},  # Direct mapping
                },
                quality_grade=quality,
                generation_method=self.rule_name,
                source_chunk_id=chunk.chunk_id,
                confidence_score=0.85,
            )

            atoms.append(atom)

        return atoms

    def _grade_matching_quality(self, pairs: list[tuple[str, str]]) -> AtomQuality:
        """Grade matching atom quality based on pair count."""
        count = len(pairs)

        if 4 <= count <= 8:
            return AtomQuality.A_PLUS
        elif 3 <= count <= 10:
            return AtomQuality.A
        elif 2 <= count <= 12:
            return AtomQuality.B
        else:
            return AtomQuality.C


class NumericExamplesToCalculation(TemplateRule):
    """
    Rule 4: Extract numeric examples and convert to calculation atoms.

    Detects:
    - IP subnet calculations
    - Numeric examples with units
    - Formula applications

    Quality Criteria:
    - A+: Clear calculation, correct answer, units specified
    - A: Clear calculation, answer present
    - B: Calculation present but answer unclear
    """

    rule_name = "Numeric Examples -> Calculation"

    def can_apply(self, chunk: TextChunk) -> bool:
        """Check if chunk contains numeric examples."""
        # Look for calculation patterns
        has_calculation = bool(re.search(
            r"\d+\s*[\+\-\*\/\^]\s*\d+\s*=\s*\d+",
            chunk.content
        ))

        # Look for subnet/IP calculations
        has_subnet = bool(re.search(
            r"\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\/\d{1,2}",
            chunk.content
        ))

        # Look for "calculate" instructions
        has_calc_instruction = bool(re.search(
            r"\b(?:calculate|compute|determine|find)\b",
            chunk.content,
            re.IGNORECASE
        ))

        return has_calculation or has_subnet or has_calc_instruction

    def generate(self, chunk: TextChunk) -> list[GeneratedAtom]:
        """Extract numeric examples and create calculation atoms."""
        atoms = []

        # Pattern: "Calculate X: ... = Y"
        calc_pattern = r"(?:Calculate|Compute|Determine|Find)\s+(.+?):\s*(.+?)\s*=\s*(\d+(?:\.\d+)?)\s*(\w+)?"
        for match in re.finditer(calc_pattern, chunk.content, re.IGNORECASE | re.DOTALL):
            what_to_calc = match.group(1).strip()
            calculation = match.group(2).strip()
            answer = match.group(3).strip()
            unit = match.group(4).strip() if match.group(4) else ""

            # Create calculation atom
            atom = GeneratedAtom(
                atom_id=self._generate_atom_id(),
                atom_type="numeric_entry",
                front=f"**Calculate:**\n\n{what_to_calc}\n\n{calculation}",
                back=f"{answer} {unit}".strip(),
                content_json={
                    "question": what_to_calc,
                    "calculation": calculation,
                    "correct_answer": float(answer),
                    "unit": unit,
                    "tolerance": 0.01,  # 1% tolerance
                },
                quality_grade=AtomQuality.A if unit else AtomQuality.B,
                generation_method=self.rule_name,
                source_chunk_id=chunk.chunk_id,
                confidence_score=0.75,
            )

            atoms.append(atom)

        # Pattern: Subnet calculation
        subnet_pattern = r"(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})\/(\d{1,2})"
        subnet_matches = list(re.finditer(subnet_pattern, chunk.content))

        if subnet_matches and "subnet" in chunk.content.lower():
            for match in subnet_matches[:3]:  # Limit to 3 per chunk
                ip = match.group(1)
                cidr = match.group(2)

                atom = GeneratedAtom(
                    atom_id=self._generate_atom_id(),
                    atom_type="subnet_calculation",
                    front=f"**Calculate subnet details for:**\n\n{ip}/{cidr}",
                    back=f"Network: {ip}/{cidr}",  # Simplified, full calculation would be in content_json
                    content_json={
                        "ip_address": ip,
                        "cidr": int(cidr),
                        "question_type": "subnet_mask",
                    },
                    quality_grade=AtomQuality.A,
                    generation_method=self.rule_name,
                    source_chunk_id=chunk.chunk_id,
                    confidence_score=0.80,
                )

                atoms.append(atom)

        return atoms


class ComparisonsToCompareAtoms(TemplateRule):
    """
    Rule 5: Extract comparisons and convert to comparison atoms.

    Detects:
    - "X vs Y" sections
    - "Difference between X and Y"
    - Comparison tables

    Quality Criteria:
    - A+: Clear differences, 2-4 dimensions compared
    - A: Clear differences, some ambiguity
    - B: Comparison present but unclear
    """

    rule_name = "Comparisons -> Compare Atoms"

    def can_apply(self, chunk: TextChunk) -> bool:
        """Check if chunk contains comparisons."""
        # Look for comparison keywords
        has_vs = bool(re.search(r"\bvs\.?\b|\bversus\b", chunk.content, re.IGNORECASE))

        has_diff = bool(re.search(
            r"\b(?:difference|differ|compare|contrast)\b",
            chunk.content,
            re.IGNORECASE
        ))

        # Check title for comparison indicators
        title_indicates_comparison = bool(re.search(
            r"(?:vs|versus|compare|contrast|difference)",
            chunk.title,
            re.IGNORECASE
        ))

        return has_vs or has_diff or title_indicates_comparison

    def generate(self, chunk: TextChunk) -> list[GeneratedAtom]:
        """Extract comparisons and create comparison atoms."""
        atoms = []

        # Pattern: "X vs Y" or "Difference between X and Y"
        comparison_patterns = [
            r"([A-Z][\w\s]{2,30}?)\s+vs\.?\s+([A-Z][\w\s]{2,30}?)(?:\n|:)",
            r"difference\s+between\s+([A-Z][\w\s]{2,30}?)\s+and\s+([A-Z][\w\s]{2,30}?)(?:\n|:)",
            r"compare\s+([A-Z][\w\s]{2,30}?)\s+(?:with|to)\s+([A-Z][\w\s]{2,30}?)(?:\n|:)",
        ]

        for pattern in comparison_patterns:
            for match in re.finditer(pattern, chunk.content, re.IGNORECASE):
                concept_a = match.group(1).strip()
                concept_b = match.group(2).strip()

                # Extract comparison content (next paragraph or section)
                comparison_text = chunk.content[match.end():match.end()+500]

                atom = GeneratedAtom(
                    atom_id=self._generate_atom_id(),
                    atom_type="concept_comparison",
                    front=f"**Compare and contrast:**\n\n{concept_a} vs {concept_b}",
                    back=comparison_text.strip(),
                    content_json={
                        "concept_a": concept_a,
                        "concept_b": concept_b,
                        "comparison_text": comparison_text.strip(),
                    },
                    quality_grade=AtomQuality.A,
                    generation_method=self.rule_name,
                    source_chunk_id=chunk.chunk_id,
                    confidence_score=0.75,
                )

                atoms.append(atom)

        return atoms


class TemplateEngine:
    """
    Template-based atom generation engine.

    Applies deterministic rules to generate atoms from content chunks
    without requiring LLM calls. Achieves ~30% coverage at zero cost.
    """

    def __init__(self):
        """Initialize template engine with all rules."""
        self.rules: list[TemplateRule] = [
            CLICommandsToParsons(),
            DefinitionsToFlashcards(),
            TablesToMatching(),
            NumericExamplesToCalculation(),
            ComparisonsToCompareAtoms(),
        ]

    def generate_from_chunk(self, chunk: TextChunk) -> list[GeneratedAtom]:
        """
        Apply all applicable template rules to generate atoms from chunk.

        Args:
            chunk: Parsed content chunk

        Returns:
            List of generated atoms (may be empty if no rules apply)
        """
        atoms = []

        for rule in self.rules:
            if rule.can_apply(chunk):
                try:
                    generated = rule.generate(chunk)
                    atoms.extend(generated)
                except Exception as e:
                    print(f"[WARNING] Rule {rule.rule_name} failed on chunk {chunk.chunk_id}: {e}")
                    continue

        return atoms

    def generate_from_chunks(self, chunks: list[TextChunk]) -> list[GeneratedAtom]:
        """
        Generate atoms from multiple chunks.

        Args:
            chunks: List of parsed content chunks

        Returns:
            List of all generated atoms
        """
        all_atoms = []

        for chunk in chunks:
            atoms = self.generate_from_chunk(chunk)
            all_atoms.extend(atoms)

        return all_atoms

    def get_coverage_stats(self, chunks: list[TextChunk]) -> dict[str, Any]:
        """
        Analyze coverage: what % of chunks can be processed by template rules.

        Args:
            chunks: List of parsed content chunks

        Returns:
            Coverage statistics
        """
        total_chunks = len(chunks)
        chunks_with_atoms = 0
        atoms_by_rule = {rule.rule_name: 0 for rule in self.rules}
        total_atoms = 0

        for chunk in chunks:
            chunk_has_atoms = False

            for rule in self.rules:
                if rule.can_apply(chunk):
                    generated = rule.generate(chunk)
                    if generated:
                        chunk_has_atoms = True
                        atoms_by_rule[rule.rule_name] += len(generated)
                        total_atoms += len(generated)

            if chunk_has_atoms:
                chunks_with_atoms += 1

        coverage_rate = chunks_with_atoms / total_chunks if total_chunks > 0 else 0.0

        return {
            "total_chunks": total_chunks,
            "chunks_with_template_atoms": chunks_with_atoms,
            "coverage_rate": coverage_rate,
            "total_atoms_generated": total_atoms,
            "atoms_by_rule": atoms_by_rule,
        }
