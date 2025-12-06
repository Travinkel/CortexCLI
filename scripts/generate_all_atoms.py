#!/usr/bin/env python
"""
Generate ALL Learning Atoms for CCNA Content.

This script extracts learnable elements from CCNA module content and generates
atoms of all types based on what's actually IN the content:

Target totals (based on content analysis):
- Flashcards: ~3,200 (definitions, facts, Q&A)
- Cloze: ~2,700 (terminology, fill-in-the-blank)
- MCQ: ~1,400 (conceptual understanding)
- True/False: ~900 (common misconceptions)
- Matching: ~350 (related concepts)
- Parsons: ~250 (CLI procedures)
- TOTAL: ~8,800 atoms

Usage:
    python scripts/generate_all_atoms.py --module 1
    python scripts/generate_all_atoms.py --all
    python scripts/generate_all_atoms.py --dry-run --module 1
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from loguru import logger
from rich import print as rprint
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn
from rich.table import Table

from src.cleaning.atomicity import CardQualityAnalyzer
from src.cleaning.thresholds import ANKI_MIN_QUALITY_SCORE

console = Console()

# Initialize quality analyzer for scoring generated atoms
quality_analyzer = CardQualityAnalyzer()


@dataclass
class LearningAtom:
    """A generated learning atom."""
    id: str
    atom_type: str  # flashcard, cloze, mcq, true_false, matching, parsons
    front: str
    back: str
    section_id: str
    module_number: int
    metadata: dict = field(default_factory=dict)
    quality_score: float = 0.0


@dataclass
class SectionContent:
    """Parsed content from a CCNA section."""
    section_id: str
    title: str
    module_number: int
    content: str
    word_count: int

    # Extracted elements
    definitions: list[tuple[str, str]] = field(default_factory=list)  # (term, explanation)
    tables: list[list[dict]] = field(default_factory=list)  # list of table rows as dicts
    lists: list[list[str]] = field(default_factory=list)  # list of list items
    commands: list[str] = field(default_factory=list)  # CLI commands
    facts: list[str] = field(default_factory=list)  # Specific facts with numbers
    acronyms: list[tuple[str, str]] = field(default_factory=list)  # (acronym, expansion)


def extract_section_content(module_path: Path, section_id: str) -> Optional[SectionContent]:
    """Extract and parse content for a specific section."""
    content = module_path.read_text(encoding='utf-8')
    module_num = int(re.search(r'Module\s*(\d+)', module_path.stem).group(1))

    # Find section content
    # Handle multiple formats:
    # 1. ## X.Y Title (markdown)
    # 2. X.Y Title (plain text at start of line)
    # 3. **X.Y Title** (bold)
    escaped_id = re.escape(section_id)

    # Try multiple markdown formats
    # Format 1: ## X.Y Title or ### X.Y.Z Title
    pattern = r'^#{1,4}\s*' + escaped_id + r'\s+(.+?)$'
    header_match = re.search(pattern, content, re.MULTILINE)

    if not header_match:
        # Format 2: # **X.Y.Z Title** (bold in header)
        pattern = r'^#\s*\*\*' + escaped_id + r'\s+(.+?)\*\*$'
        header_match = re.search(pattern, content, re.MULTILINE)

    if not header_match:
        # Format 3: Plain section ID at start of line
        pattern = r'^' + escaped_id + r'\s+(.+?)$'
        header_match = re.search(pattern, content, re.MULTILINE)

    if not header_match:
        # Format 4: **X.Y Title** (bold without hash)
        pattern = rf'^\*\*{escaped_id}\s+(.+?)\*\*$'
        header_match = re.search(pattern, content, re.MULTILINE)

    if not header_match:
        return None

    title = header_match.group(1).strip().rstrip('*')  # Remove trailing asterisks
    start_pos = header_match.end()

    # Find end of section (next section header or end of file)
    # Match section patterns like:
    # - # 11.1.3 Title or # **11.1.3 Title**
    # - ## 11.1.3 Title
    # - 11.1.3 Title (plain at start of line)
    # Must have a number pattern like X.Y or X.Y.Z
    next_section = re.search(
        r'^(?:#\s*(?:\*\*)?|##\s*|###\s*)?\d+\.\d+(?:\.\d+)?\s+[A-Z]',
        content[start_pos:],
        re.MULTILINE
    )
    if next_section:
        section_text = content[start_pos:start_pos + next_section.start()]
    else:
        section_text = content[start_pos:]

    # Limit section text to avoid over-extraction (max 3000 words)
    words = section_text.split()
    if len(words) > 3000:
        section_text = ' '.join(words[:3000])

    section = SectionContent(
        section_id=section_id,
        title=title,
        module_number=module_num,
        content=section_text.strip(),
        word_count=len(section_text.split()),
    )

    # Extract definitions (bold terms followed by explanation)
    def_pattern = r'\*\*([^*]+)\*\*\s*[-—:]\s*([^*\n]+)'
    for match in re.finditer(def_pattern, section_text):
        term = match.group(1).strip()
        explanation = match.group(2).strip()
        if len(term) > 2 and len(explanation) > 10:
            section.definitions.append((term, explanation))

    # Also get bold terms that might be defined in context
    bold_pattern = r'\*\*([A-Z][^*]{2,50})\*\*'
    for match in re.finditer(bold_pattern, section_text):
        term = match.group(1).strip()
        # Get surrounding context
        start = max(0, match.start() - 50)
        end = min(len(section_text), match.end() + 200)
        context = section_text[start:end]
        # Check if not already in definitions
        if not any(term == d[0] for d in section.definitions):
            # Try to extract definition from context
            after_term = section_text[match.end():match.end()+300]
            sentences = re.split(r'[.!?]', after_term)
            if sentences and len(sentences[0].strip()) > 10:
                section.definitions.append((term, sentences[0].strip()))

    # Extract tables
    table_pattern = r'\|(.+)\|'
    table_rows = re.findall(table_pattern, section_text)
    if len(table_rows) >= 2:  # At least header + 1 data row
        # Parse table
        headers = [h.strip() for h in table_rows[0].split('|') if h.strip() and '---' not in h]
        for row in table_rows[2:]:  # Skip header and separator
            if '---' in row:
                continue
            cells = [c.strip() for c in row.split('|') if c.strip()]
            if len(cells) == len(headers):
                section.tables.append([dict(zip(headers, cells))])

    # Extract lists
    list_pattern = r'^[\-\*]\s+(.+)$'
    current_list = []
    for match in re.finditer(list_pattern, section_text, re.MULTILINE):
        item = match.group(1).strip()
        if len(item) > 5:
            current_list.append(item)
    if current_list:
        section.lists.append(current_list)

    # Extract CLI commands
    cmd_pattern = r'(?:Router|Switch|S\d|R\d)[#>]\s*(.+?)(?:\n|$)'
    for match in re.finditer(cmd_pattern, section_text):
        cmd = match.group(1).strip()
        if cmd:
            section.commands.append(cmd)

    # Extract facts with numbers
    fact_pattern = r'([^.]+\d+(?:\.\d+)?\s*(?:Mbps|Gbps|MHz|GHz|bits|bytes|meters|feet|ms|Kbps|seconds|minutes|hours)[^.]*\.)'
    for match in re.finditer(fact_pattern, section_text, re.IGNORECASE):
        fact = match.group(1).strip()
        if len(fact) > 20:
            section.facts.append(fact)

    # Extract key sentences (those with bold terms or important patterns)
    sentences = re.split(r'(?<=[.!?])\s+', section_text)
    for sentence in sentences:
        sentence = sentence.strip()
        # Skip short sentences or those that are just headers
        if len(sentence) < 30 or len(sentence) > 300:
            continue
        # Skip if starts with certain patterns
        if sentence.startswith(('|', '#', '>', '-', '*', 'Note:', 'Click')):
            continue
        # Check if contains a definition pattern or important fact
        if re.search(r'\b(?:is|are|refers to|means|called|known as|defined as)\b', sentence, re.IGNORECASE):
            # This is a definition-style sentence
            if sentence not in [d[1] for d in section.definitions]:
                section.facts.append(sentence)

    # Extract acronyms
    acronym_pattern = r'\b([A-Z]{2,6})\b\s*\(([^)]+)\)'
    for match in re.finditer(acronym_pattern, section_text):
        acronym = match.group(1)
        expansion = match.group(2).strip()
        section.acronyms.append((acronym, expansion))

    # Also find "X (acronym)" pattern
    reverse_pattern = r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)\s*\(([A-Z]{2,6})\)'
    for match in re.finditer(reverse_pattern, section_text):
        expansion = match.group(1).strip()
        acronym = match.group(2)
        if (acronym, expansion) not in section.acronyms:
            section.acronyms.append((acronym, expansion))

    # Extract key comparison statements (X vs Y, X and Y, X or Y)
    comparison_pattern = r'([A-Z][a-z]+(?:\s+[a-z]+)*)\s+(?:vs\.?|versus|and|or)\s+([A-Z][a-z]+(?:\s+[a-z]+)*)'
    for match in re.finditer(comparison_pattern, section_text):
        # These make good comparison questions
        term1 = match.group(1).strip()
        term2 = match.group(2).strip()
        if len(term1) > 2 and len(term2) > 2:
            section.facts.append(f"Comparison: {term1} vs {term2}")

    return section


def generate_flashcards(section: SectionContent) -> list[LearningAtom]:
    """Generate flashcard atoms from section content."""
    atoms = []

    # From definitions
    for term, explanation in section.definitions:
        # What is X?
        atoms.append(LearningAtom(
            id=str(uuid.uuid4()),
            atom_type='flashcard',
            front=f"What is {term}?",
            back=explanation[:200],  # Limit length
            section_id=section.section_id,
            module_number=section.module_number,
            metadata={'source': 'definition', 'term': term},
        ))

        # Reverse: X is the term for ___
        if len(explanation) < 150:
            atoms.append(LearningAtom(
                id=str(uuid.uuid4()),
                atom_type='flashcard',
                front=f"What networking term describes: {explanation}?",
                back=term,
                section_id=section.section_id,
                module_number=section.module_number,
                metadata={'source': 'definition_reverse', 'term': term},
            ))

    # From acronyms
    for acronym, expansion in section.acronyms:
        atoms.append(LearningAtom(
            id=str(uuid.uuid4()),
            atom_type='flashcard',
            front=f"What does {acronym} stand for?",
            back=expansion,
            section_id=section.section_id,
            module_number=section.module_number,
            metadata={'source': 'acronym'},
        ))

    # From facts
    for fact in section.facts:
        # Extract the key value
        numbers = re.findall(r'\d+(?:\.\d+)?\s*(?:Mbps|Gbps|MHz|GHz|Kbps)', fact, re.IGNORECASE)
        if numbers:
            # Create question about the value
            fact_question = re.sub(r'\d+(?:\.\d+)?\s*(?:Mbps|Gbps|MHz|GHz|Kbps)', '___', fact, count=1, flags=re.IGNORECASE)
            atoms.append(LearningAtom(
                id=str(uuid.uuid4()),
                atom_type='flashcard',
                front=f"Fill in the value: {fact_question}",
                back=numbers[0],
                section_id=section.section_id,
                module_number=section.module_number,
                metadata={'source': 'fact_value'},
            ))

        # For definition-style facts, create Q&A
        is_match = re.search(r'^(.+?)\s+(is|are|refers to|means)\s+(.+)$', fact, re.IGNORECASE)
        if is_match:
            subject = is_match.group(1).strip()
            verb = is_match.group(2).strip().lower()
            predicate = is_match.group(3).strip()
            # Validate subject is reasonable (not truncated garbage)
            if (len(subject) > 2 and len(subject) < 100 and
                len(predicate) > 10 and
                not re.search(r'[,]{2,}', subject) and  # No repeated commas
                not subject.lower().startswith('the ') and  # Avoid "The concept of..."
                len(subject.split()) < 10):  # Not too many words
                atoms.append(LearningAtom(
                    id=str(uuid.uuid4()),
                    atom_type='flashcard',
                    front=f"What {verb} {subject}?",
                    back=predicate[:200],
                    section_id=section.section_id,
                    module_number=section.module_number,
                    metadata={'source': 'fact_definition'},
                ))

    # From lists - each item can be a knowledge point
    for item_list in section.lists:
        for i, item in enumerate(item_list[:10]):  # Limit to 10 items
            # Create a flashcard for each list item
            if len(item) > 10 and len(item) < 200:
                atoms.append(LearningAtom(
                    id=str(uuid.uuid4()),
                    atom_type='flashcard',
                    front=f"In {section.title}, what is one example or component?",
                    back=item,
                    section_id=section.section_id,
                    module_number=section.module_number,
                    metadata={'source': 'list_item'},
                ))

    return atoms


def generate_cloze(section: SectionContent) -> list[LearningAtom]:
    """Generate cloze deletion atoms from section content."""
    atoms = []

    # From definitions - key term as cloze
    for term, explanation in section.definitions:
        if len(term) > 2 and len(term) < 30:
            # Find a sentence containing the term
            sentences = re.split(r'[.!?]', section.content)
            for sentence in sentences:
                if term.lower() in sentence.lower() and len(sentence) > 30:
                    # Create cloze with term blanked
                    cloze_text = re.sub(
                        rf'\b{re.escape(term)}\b',
                        '{{c1::' + term + '}}',
                        sentence.strip(),
                        flags=re.IGNORECASE,
                        count=1
                    )
                    if '{{c1::' in cloze_text:
                        atoms.append(LearningAtom(
                            id=str(uuid.uuid4()),
                            atom_type='cloze',
                            front=cloze_text,
                            back=term,
                            section_id=section.section_id,
                            module_number=section.module_number,
                            metadata={'source': 'definition_cloze'},
                        ))
                        break

    # From acronyms
    for acronym, expansion in section.acronyms:
        atoms.append(LearningAtom(
            id=str(uuid.uuid4()),
            atom_type='cloze',
            front=f"{{{{c1::{acronym}}}}} stands for {expansion}",
            back=acronym,
            section_id=section.section_id,
            module_number=section.module_number,
            metadata={'source': 'acronym_cloze'},
        ))
        atoms.append(LearningAtom(
            id=str(uuid.uuid4()),
            atom_type='cloze',
            front=f"{acronym} stands for {{{{c1::{expansion}}}}}",
            back=expansion,
            section_id=section.section_id,
            module_number=section.module_number,
            metadata={'source': 'acronym_expansion_cloze'},
        ))

    # From commands
    for cmd in section.commands:
        parts = cmd.split()
        if len(parts) >= 2:
            # Cloze the command keyword
            cloze_text = '{{c1::' + parts[0] + '}} ' + ' '.join(parts[1:])
            atoms.append(LearningAtom(
                id=str(uuid.uuid4()),
                atom_type='cloze',
                front=f"CLI Command: {cloze_text}",
                back=parts[0],
                section_id=section.section_id,
                module_number=section.module_number,
                metadata={'source': 'command_cloze'},
            ))

    # From facts - create cloze for key terms in sentences
    for fact in section.facts:
        # Find bold terms or key nouns to blank out
        bold_in_fact = re.findall(r'\*\*([^*]+)\*\*', fact)
        if bold_in_fact:
            for term in bold_in_fact[:1]:  # Only first bold term
                cloze_fact = fact.replace(f'**{term}**', '{{c1::' + term + '}}')
                atoms.append(LearningAtom(
                    id=str(uuid.uuid4()),
                    atom_type='cloze',
                    front=cloze_fact,
                    back=term,
                    section_id=section.section_id,
                    module_number=section.module_number,
                    metadata={'source': 'fact_cloze'},
                ))
        else:
            # Try to find key networking terms to blank
            networking_terms = re.findall(r'\b((?:IP|TCP|UDP|LAN|WAN|MAC|DNS|DHCP|HTTP|FTP|SMTP|ICMP|ARP|NAT|VLAN|VPN|OSI|PDU|MTU|TTL)[A-Za-z]*)\b', fact, re.IGNORECASE)
            if networking_terms:
                term = networking_terms[0]
                cloze_fact = re.sub(rf'\b{re.escape(term)}\b', '{{c1::' + term + '}}', fact, count=1)
                atoms.append(LearningAtom(
                    id=str(uuid.uuid4()),
                    atom_type='cloze',
                    front=cloze_fact,
                    back=term,
                    section_id=section.section_id,
                    module_number=section.module_number,
                    metadata={'source': 'fact_term_cloze'},
                ))

    # From lists - create cloze with list items
    for item_list in section.lists:
        for item in item_list[:5]:
            # Find key terms in list items
            key_terms = re.findall(r'\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\b', item)
            if key_terms and len(key_terms[0]) > 2:
                term = key_terms[0]
                cloze_item = re.sub(rf'\b{re.escape(term)}\b', '{{c1::' + term + '}}', item, count=1)
                if '{{c1::' in cloze_item:
                    atoms.append(LearningAtom(
                        id=str(uuid.uuid4()),
                        atom_type='cloze',
                        front=f"In {section.title}: {cloze_item}",
                        back=term,
                        section_id=section.section_id,
                        module_number=section.module_number,
                        metadata={'source': 'list_cloze'},
                    ))

    return atoms


def generate_mcq(section: SectionContent) -> list[LearningAtom]:
    """Generate multiple choice question atoms from section content."""
    atoms = []

    # From lists - "Which of the following" questions
    for item_list in section.lists:
        if len(item_list) >= 3:
            # Generate MCQ for each item in the list
            for i, correct_item in enumerate(item_list[:4]):
                # Get wrong answers from other items
                wrong_items = [item for j, item in enumerate(item_list) if j != i][:3]
                if len(wrong_items) >= 2:
                    all_options = [correct_item[:100]] + [w[:100] for w in wrong_items]
                    atoms.append(LearningAtom(
                        id=str(uuid.uuid4()),
                        atom_type='mcq',
                        front=f"Which of the following is correct for {section.title}?",
                        back=json.dumps({
                            'correct': correct_item[:100],
                            'options': all_options,
                        }),
                        section_id=section.section_id,
                        module_number=section.module_number,
                        metadata={'source': 'list_mcq'},
                    ))

    # From definitions - "What is the definition of X"
    if len(section.definitions) >= 2:
        for i, (term, explanation) in enumerate(section.definitions):
            # Get other definitions as distractors
            other_explanations = [e for t, e in section.definitions if t != term][:3]
            if len(other_explanations) >= 1:
                # Pad with generic wrong answers if needed
                while len(other_explanations) < 3:
                    other_explanations.append("This is not the correct definition")
                options = [explanation[:100]] + [e[:100] for e in other_explanations[:3]]
                atoms.append(LearningAtom(
                    id=str(uuid.uuid4()),
                    atom_type='mcq',
                    front=f"What is the correct definition of '{term}'?",
                    back=json.dumps({
                        'correct': explanation[:100],
                        'options': options,
                    }),
                    section_id=section.section_id,
                    module_number=section.module_number,
                    metadata={'source': 'definition_mcq'},
                ))

    # From acronyms - "What does X stand for?"
    if len(section.acronyms) >= 2:
        for acronym, expansion in section.acronyms:
            other_expansions = [e for a, e in section.acronyms if a != acronym][:3]
            if len(other_expansions) >= 1:
                while len(other_expansions) < 3:
                    other_expansions.append("Not a valid expansion")
                options = [expansion] + other_expansions[:3]
                atoms.append(LearningAtom(
                    id=str(uuid.uuid4()),
                    atom_type='mcq',
                    front=f"What does {acronym} stand for?",
                    back=json.dumps({
                        'correct': expansion,
                        'options': options,
                    }),
                    section_id=section.section_id,
                    module_number=section.module_number,
                    metadata={'source': 'acronym_mcq'},
                ))

    return atoms


def generate_true_false(section: SectionContent) -> list[LearningAtom]:
    """Generate true/false atoms from section content."""
    atoms = []

    # From definitions - create true statements and false variants
    for term, explanation in section.definitions:
        # True statement
        atoms.append(LearningAtom(
            id=str(uuid.uuid4()),
            atom_type='true_false',
            front=f"{term} is defined as: {explanation[:150]}",
            back=json.dumps({'answer': True, 'explanation': 'This is the correct definition.'}),
            section_id=section.section_id,
            module_number=section.module_number,
            metadata={'source': 'definition_tf_true'},
        ))

        # False statement - swap with another definition if available
        other_defs = [e for t, e in section.definitions if t != term]
        if other_defs:
            false_explanation = other_defs[0]
            atoms.append(LearningAtom(
                id=str(uuid.uuid4()),
                atom_type='true_false',
                front=f"{term} is defined as: {false_explanation[:150]}",
                back=json.dumps({
                    'answer': False,
                    'explanation': f'This is actually the definition of something else. {term} means: {explanation[:100]}'
                }),
                section_id=section.section_id,
                module_number=section.module_number,
                metadata={'source': 'definition_tf_false'},
            ))

    # From facts - create true/false statements
    for fact in section.facts:
        # True statement from fact
        if len(fact) > 30 and len(fact) < 250:
            atoms.append(LearningAtom(
                id=str(uuid.uuid4()),
                atom_type='true_false',
                front=f"True or False: {fact}",
                back=json.dumps({'answer': True, 'explanation': 'This is a correct statement from the CCNA material.'}),
                section_id=section.section_id,
                module_number=section.module_number,
                metadata={'source': 'fact_tf_true'},
            ))

    # From acronyms - true/false
    for acronym, expansion in section.acronyms:
        atoms.append(LearningAtom(
            id=str(uuid.uuid4()),
            atom_type='true_false',
            front=f"True or False: {acronym} stands for {expansion}.",
            back=json.dumps({'answer': True, 'explanation': f'Correct. {acronym} = {expansion}'}),
            section_id=section.section_id,
            module_number=section.module_number,
            metadata={'source': 'acronym_tf_true'},
        ))

    return atoms


def generate_matching(section: SectionContent) -> list[LearningAtom]:
    """Generate matching atoms from section content."""
    atoms = []

    # From tables with at least 3 rows
    for table in section.tables:
        if len(table) >= 3:
            # Create matching pairs from first two columns
            pairs = []
            for row in table:
                if len(row) >= 1:
                    keys = list(row[0].keys())
                    if len(keys) >= 2:
                        pairs.append((row[0][keys[0]], row[0][keys[1]]))

            if len(pairs) >= 3:
                atoms.append(LearningAtom(
                    id=str(uuid.uuid4()),
                    atom_type='matching',
                    front=f"Match the items from {section.title}:",
                    back=json.dumps({'pairs': pairs[:6]}),
                    section_id=section.section_id,
                    module_number=section.module_number,
                    metadata={'source': 'table_matching'},
                ))

    # From acronyms if we have enough
    if len(section.acronyms) >= 4:
        pairs = [(a, e) for a, e in section.acronyms[:6]]
        atoms.append(LearningAtom(
            id=str(uuid.uuid4()),
            atom_type='matching',
            front="Match the acronyms to their meanings:",
            back=json.dumps({'pairs': pairs}),
            section_id=section.section_id,
            module_number=section.module_number,
            metadata={'source': 'acronym_matching'},
        ))

    # From definitions if we have enough (match term to definition)
    if len(section.definitions) >= 4:
        # Take first 6 definitions
        pairs = [(term, expl[:80]) for term, expl in section.definitions[:6]]
        atoms.append(LearningAtom(
            id=str(uuid.uuid4()),
            atom_type='matching',
            front=f"Match the terms to their definitions from {section.title}:",
            back=json.dumps({'pairs': pairs}),
            section_id=section.section_id,
            module_number=section.module_number,
            metadata={'source': 'definition_matching'},
        ))

    return atoms


def generate_parsons(section: SectionContent) -> list[LearningAtom]:
    """Generate Parsons problem atoms from section content."""
    atoms = []

    # From CLI commands - order the steps
    if len(section.commands) >= 3:
        # Commands in sequence form a procedure
        atoms.append(LearningAtom(
            id=str(uuid.uuid4()),
            atom_type='parsons',
            front=f"Arrange these CLI commands in the correct order:",
            back=json.dumps({
                'correct_order': section.commands[:6],
                'scrambled': sorted(section.commands[:6], key=lambda x: hash(x)),
            }),
            section_id=section.section_id,
            module_number=section.module_number,
            metadata={'source': 'cli_parsons'},
        ))

    # From numbered lists (procedures)
    for item_list in section.lists:
        # Check if items look like steps
        if len(item_list) >= 3:
            step_pattern = r'^(?:Step\s+\d|First|Then|Next|Finally|\d+\.|[a-z]\))'
            if any(re.match(step_pattern, item, re.IGNORECASE) for item in item_list):
                atoms.append(LearningAtom(
                    id=str(uuid.uuid4()),
                    atom_type='parsons',
                    front=f"Arrange these steps in the correct order for {section.title}:",
                    back=json.dumps({
                        'correct_order': item_list[:6],
                        'scrambled': sorted(item_list[:6], key=lambda x: hash(x)),
                    }),
                    section_id=section.section_id,
                    module_number=section.module_number,
                    metadata={'source': 'procedure_parsons'},
                ))

    # Look for explicit procedures in content (numbered steps pattern)
    numbered_pattern = r'(\d+)\.\s+(.+?)(?=\n\d+\.|\n\n|$)'
    numbered_matches = re.findall(numbered_pattern, section.content, re.DOTALL)
    if len(numbered_matches) >= 3:
        steps = [match[1].strip()[:100] for match in numbered_matches[:6]]
        atoms.append(LearningAtom(
            id=str(uuid.uuid4()),
            atom_type='parsons',
            front=f"Arrange these numbered steps in the correct order for {section.title}:",
            back=json.dumps({
                'correct_order': steps,
                'scrambled': sorted(steps, key=lambda x: hash(x)),
            }),
            section_id=section.section_id,
            module_number=section.module_number,
            metadata={'source': 'numbered_parsons'},
        ))

    # From OSI/TCP model layers (common in networking)
    osi_pattern = r'(?:Layer\s*(\d+)|(\w+)\s+[Ll]ayer)'
    osi_matches = re.findall(osi_pattern, section.content)
    if len(osi_matches) >= 4:
        # Extract unique layer references
        layers = []
        for num, name in osi_matches:
            layer = f"Layer {num}" if num else f"{name} Layer"
            if layer not in layers:
                layers.append(layer)
        if len(layers) >= 4:
            atoms.append(LearningAtom(
                id=str(uuid.uuid4()),
                atom_type='parsons',
                front="Arrange these network layers in the correct order (top to bottom):",
                back=json.dumps({
                    'correct_order': layers[:7],
                    'scrambled': sorted(layers[:7], key=lambda x: hash(x)),
                }),
                section_id=section.section_id,
                module_number=section.module_number,
                metadata={'source': 'layer_parsons'},
            ))

    return atoms


def validate_and_score_atom(atom: LearningAtom) -> tuple[bool, float]:
    """
    Validate atom content and calculate quality score.

    Returns:
        (is_valid, quality_score) tuple
        - is_valid: False if atom has malformed/garbage content
        - quality_score: 0-1 scale score for atoms that pass validation
    """
    front = atom.front.strip()
    back = atom.back.strip()

    # =========================================================================
    # Text coherence validation (catches garbage from regex extraction)
    # =========================================================================

    # Check for repeated punctuation (truncation artifacts)
    if re.search(r'[,]{2,}|[.]{3,}[^.]', front) or re.search(r'[,]{2,}|[.]{3,}[^.]', back):
        return False, 0.0

    # Check for malformed questions ("what concept The concept", "what is This")
    malformed_patterns = [
        r'what\s+\w+\s+The\s+',  # "what concept The concept"
        r'what\s+is\s+This\b',   # "what is This" (vague)
        r'In\s+\w+,\s+what\s+is\s+This\b',  # "In X, what is This"
        r'^\s*In\s+[\w\s]+:\s*$',  # Just "In X:" with nothing else
        r'\?\s*\?',  # Double question marks
    ]
    for pattern in malformed_patterns:
        if re.search(pattern, front, re.IGNORECASE):
            return False, 0.0

    # Check for too-short content
    if len(front) < 15 or len(back) < 3:
        return False, 0.0

    # Check for broken markdown (unclosed tags)
    if front.count('{{') != front.count('}}'):
        return False, 0.0
    if front.count('**') % 2 != 0:
        return False, 0.0

    # =========================================================================
    # Quality scoring (using CardQualityAnalyzer)
    # =========================================================================
    try:
        report = quality_analyzer.analyze(front, back, atom.atom_type)
        # Convert 0-100 score to 0-1 scale
        quality_score = report.score / 100.0
        return True, quality_score
    except Exception as e:
        logger.debug(f"Quality analysis failed: {e}")
        return True, 0.5  # Default score if analysis fails


def process_section(section: SectionContent) -> list[LearningAtom]:
    """Generate all atom types for a section with quality validation."""
    all_atoms = []
    rejected_count = 0

    # Generate raw atoms
    raw_atoms = []
    raw_atoms.extend(generate_flashcards(section))
    raw_atoms.extend(generate_cloze(section))
    raw_atoms.extend(generate_mcq(section))
    raw_atoms.extend(generate_true_false(section))
    raw_atoms.extend(generate_matching(section))
    raw_atoms.extend(generate_parsons(section))

    # Validate and score each atom
    for atom in raw_atoms:
        is_valid, score = validate_and_score_atom(atom)
        if is_valid:
            atom.quality_score = score
            all_atoms.append(atom)
        else:
            rejected_count += 1

    if rejected_count > 0:
        logger.debug(f"Section {section.section_id}: Rejected {rejected_count} malformed atoms")

    return all_atoms


def save_atoms_to_db(atoms: list[LearningAtom], dry_run: bool = False) -> int:
    """Save atoms to the database."""
    if dry_run:
        return len(atoms)

    from sqlalchemy import text
    from src.db.database import engine

    inserted = 0

    with engine.connect() as conn:
        for atom in atoms:
            try:
                conn.execute(
                    text("""
                        INSERT INTO clean_atoms
                        (id, atom_type, front, back, ccna_section_id, quality_score, source, created_at)
                        VALUES (:id, :type, :front, :back, :section, :quality, :source, :created)
                        ON CONFLICT (id) DO NOTHING
                    """),
                    {
                        'id': atom.id,
                        'type': atom.atom_type,
                        'front': atom.front,
                        'back': atom.back,
                        'section': atom.section_id,
                        'quality': atom.quality_score,
                        'source': 'generated',
                        'created': datetime.now(),
                    }
                )
                inserted += 1
            except Exception as e:
                logger.error(f"Error inserting atom: {e}")

        conn.commit()

    return inserted


def main():
    parser = argparse.ArgumentParser(description="Generate comprehensive CCNA atoms")
    parser.add_argument("--module", type=int, help="Generate for specific module (1-16)")
    parser.add_argument("--all", action="store_true", help="Generate for all modules")
    parser.add_argument("--dry-run", action="store_true", help="Preview without saving")
    parser.add_argument("--section", type=str, help="Generate for specific section (e.g., 1.2.1)")
    args = parser.parse_args()

    modules_dir = Path(__file__).parent.parent / 'docs' / 'CCNA'

    rprint("\n[bold]CCNA Comprehensive Atom Generation[/bold]\n")

    # Get sections from database
    from sqlalchemy import text
    from src.db.database import engine

    with engine.connect() as conn:
        if args.section:
            result = conn.execute(
                text("SELECT section_id, module_number FROM ccna_sections WHERE section_id = :id"),
                {'id': args.section}
            )
        elif args.module:
            result = conn.execute(
                text("SELECT section_id, module_number FROM ccna_sections WHERE module_number = :mod AND level = 3 ORDER BY display_order"),
                {'mod': args.module}
            )
        elif args.all:
            # Process BOTH level 2 and level 3 sections
            result = conn.execute(
                text("SELECT section_id, module_number FROM ccna_sections ORDER BY module_number, display_order")
            )
        else:
            rprint("[yellow]Specify --module N, --section X.Y.Z, or --all[/yellow]")
            return 1

        sections = list(result)

    rprint(f"Processing {len(sections)} sections...")

    total_atoms = {
        'flashcard': 0,
        'cloze': 0,
        'mcq': 0,
        'true_false': 0,
        'matching': 0,
        'parsons': 0,
    }

    all_generated = []

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        console=console,
    ) as progress:
        task = progress.add_task("Generating atoms...", total=len(sections))

        for section_id, module_num in sections:
            # Find the right module file
            module_file = modules_dir / f'CCNA Module {module_num}.txt'
            if not module_file.exists():
                progress.advance(task)
                continue

            section = extract_section_content(module_file, section_id)
            if section:
                atoms = process_section(section)
                for atom in atoms:
                    total_atoms[atom.atom_type] += 1
                all_generated.extend(atoms)

            progress.advance(task)

    # Display results
    table = Table(title="Generated Atoms Summary")
    table.add_column("Type", style="cyan")
    table.add_column("Count", justify="right", style="green")

    for atom_type, count in sorted(total_atoms.items(), key=lambda x: -x[1]):
        table.add_row(atom_type, str(count))

    table.add_section()
    table.add_row("[bold]TOTAL[/bold]", f"[bold]{sum(total_atoms.values())}[/bold]")

    console.print(table)

    if args.dry_run:
        rprint("\n[yellow]DRY RUN - No atoms saved[/yellow]")
        # Show sample atoms
        rprint("\n[bold]Sample atoms:[/bold]")
        for atom_type in total_atoms.keys():
            samples = [a for a in all_generated if a.atom_type == atom_type][:2]
            for s in samples:
                rprint(f"\n[cyan]{s.atom_type}[/cyan] ({s.section_id}):")
                rprint(f"  Q: {s.front[:80]}...")
                rprint(f"  A: {s.back[:80]}...")
    else:
        # Save to database
        inserted = save_atoms_to_db(all_generated)
        rprint(f"\n[green]Saved {inserted} atoms to database[/green]")

    return 0


if __name__ == "__main__":
    sys.exit(main())
